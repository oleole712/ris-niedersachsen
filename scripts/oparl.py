#!/usr/bin/env python3
"""Sucht für jedes RIS in data/ris.csv eine OParl-Schnittstelle (https://oparl.org).

Für jede RIS-URL werden die bei SessionNet, ALLRIS, SD.NET und anderen Systemen üblichen
Pfade des OParl-System-Objekts geprüft. Ein Treffer zählt nur, wenn die Antwort JSON mit
einem OParl-Typ (https://schema.oparl.org/1.x/System) ist. robots.txt wird beachtet.
Gefundene Endpunkte landen in der Spalte oparl_url, auch bei manuell gepflegten Einträgen
(die URL des RIS selbst bleibt dort unverändert).
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).parent))
from common import load_ris, save_ris  # noqa: E402
from crawl_ris import fetch, ris_root  # noqa: E402

GENERIC = ["oparl/system", "oparl/v1/system", "oparl/v1.0/system", "oparl/v1.1/system",
           "oparl/1.0/system", "oparl/1.1/system", "oparl"]
SESSIONNET = ["oparl/1.0/system.asp", "oparl/1.0/system.php", "oparl/system.php", "oparl/system.asp"]


def candidates(url: str) -> list[str]:
    root = ris_root(url)
    p = urlparse(url)
    origin = f"{p.scheme}://{p.netloc}/"
    out = []
    for base in dict.fromkeys([root, origin, urljoin(root, "../")]):
        out += [urljoin(base, c) for c in SESSIONNET + GENERIC]
    out += [urljoin(origin, "webservice/oparl/v1.1/system"), urljoin(origin, "public/oparl/system")]
    return list(dict.fromkeys(out))


def is_oparl_system(resp) -> bool:
    if resp is None or resp.status_code != 200:
        return False
    try:
        data = resp.json()
    except ValueError:
        return False
    t = json.dumps(data.get("type", "") if isinstance(data, dict) else "")
    return "oparl.org/schema/1." in t and "System" in t


PROBELOG: dict[str, dict] = {}


def probe(url: str) -> str:
    codes = []
    for c in candidates(url):
        r, err = fetch(c)
        codes.append(err or str(r.status_code))
        if r is not None and r.status_code == 0:
            continue
        if is_oparl_system(r):
            PROBELOG[url] = {"ris": url, "ergebnis": r.url, "antworten": ""}
            return r.url
    from collections import Counter
    PROBELOG[url] = {"ris": url, "ergebnis": "",
                     "antworten": " ".join(f"{k}x{v}" for k, v in Counter(codes).most_common())}
    return ""


def main() -> None:
    ris = load_ris()
    rows = [r for r in ris.values() if r.get("ris_url") and "redirect.phtml" not in r["ris_url"]]
    # gleiche RIS-Hosts nur einmal prüfen (z. B. Samtgemeinde und ihre Mitgliedsgemeinden)
    by_root: dict[str, list[dict]] = {}
    for r in rows:
        by_root.setdefault(ris_root(r["ris_url"]), []).append(r)
    with ThreadPoolExecutor(16) as ex:
        results = dict(zip(by_root, ex.map(probe, by_root)))
    n = 0
    for root, found in results.items():
        for r in by_root[root]:
            if found:
                r["oparl_url"] = found
                n += 1
    save_ris(ris)
    from common import DATA, write_csv
    write_csv(DATA / "oparl_pruefung.csv", sorted(PROBELOG.values(), key=lambda x: x["ris"]),
              ["ris", "ergebnis", "antworten"])
    print(f"OParl-Schnittstelle bei {n} von {len(rows)} Einträgen gefunden.")
    for root, found in sorted(results.items()):
        if found:
            print(" ", found)


if __name__ == "__main__":
    main()
