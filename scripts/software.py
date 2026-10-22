#!/usr/bin/env python3
"""Ergänzt die Spalte software in data/ris.csv.

Quellen, in dieser Reihenfolge:
  1. die RIS-URL selbst (Hostname/Pfadmuster der Anbieter),
  2. alle Deep-Links auf denselben RIS-Host aus data/crawler_log.csv
     (z. B. si0040.asp -> SessionNet, si010 -> ALLRIS 4),
  3. mit --live: der HTML-Quelltext der RIS-Startseite (robots.txt wird beachtet).

Manuell gepflegte Einträge werden nur ergänzt, wenn ihre Software-Spalte leer ist.
Bezeichnungen für crawler-Einträge werden neu abgeleitet, damit Korrekturen an den
Erkennungsregeln (z. B. ratsinfomanagement.net = SD.NET RIM) überall ankommen.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))
from common import DATA, load_ris, read_csv, save_ris, software_from_html, software_from_url  # noqa: E402


def host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="RIS-Startseiten abrufen (für GitHub Actions)")
    a = ap.parse_args()

    ris = load_ris()
    deep: dict[str, set[str]] = defaultdict(set)
    for row in read_csv(DATA / "crawler_log.csv"):
        deep[host(row["url"])].add(row["url"])

    fetch = None
    if a.live:
        from crawl_ris import fetch  # noqa: WPS433 (nur bei Bedarf, braucht requests)

    changed = 0
    for r in ris.values():
        url = r.get("ris_url", "")
        if not url or "redirect.phtml" in url:
            continue
        if r.get("quelle") == "manuell" and r.get("software"):
            continue
        sw = software_from_url(url)
        if not sw:
            h, path = host(url), urlparse(url).path
            hits = [software_from_url(u) for u in deep.get(h, ()) if urlparse(u).path.startswith(path.rstrip("/"))]
            hits = [x for x in hits if x]
            if hits:
                sw = max(set(hits), key=hits.count)
        if not sw and fetch is not None:
            resp, _ = fetch(url)
            if resp is not None and resp.status_code == 200:
                sw = software_from_html(resp.text)
        if sw and sw != r.get("software"):
            print(f"{r['name']}: {r.get('software') or '–'} -> {sw}")
            r["software"] = sw
            changed += 1
    save_ris(ris)
    unbekannt = sum(1 for r in ris.values() if r.get("ris_url") and not r.get("software"))
    print(f"{changed} Einträge geändert, {unbekannt} weiterhin ohne Software.")


if __name__ == "__main__":
    main()
