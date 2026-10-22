#!/usr/bin/env python3
"""Sucht für Mitgliedsgemeinden eigene Bereiche im RIS ihrer Samtgemeinde.

Viele Samtgemeinden führen die Räte ihrer Mitgliedsgemeinden als eigene Mandanten,
Unterbereiche oder Menüs (z. B. SD.NET RIM: <sg>.ratsinfomanagement.net/<gemeinde>/,
ALLRIS 4: gr010?menu=Gemeinde+X, SessionNet: eigener __cmandant). Gefundene Links
werden als eigenes RIS der Mitgliedsgemeinde eingetragen (quelle=crawler-mitglied).

Quellen: data/crawler_log.csv (Links von den Websites der Samtgemeinden) und mit
--live zusätzlich die Startseiten der Samtgemeinde-RIS (robots.txt wird beachtet).
Manuell gepflegte Einträge werden nie verändert.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).parent))
from common import (DATA, KOMMUNEN_CSV, RIS_FIELDS, VENDOR_PAGES, load_ris, read_csv,  # noqa: E402
                    save_ris, software_from_url)

STRONG = re.compile(r"sitzung-online|/allris|ratsinfomanagement|sessionnet|/bi/|/buergerinfo/|gr010|gr00\d0|"
                    r"si00\d0|__cmandant|ratsportal|//ris\.|ratsinfo", re.I)
SITE_RIS = re.compile(r"/allris|gr010|gr00\d0|si00\d0|/bi/|__cmandant|/public/", re.I)
NOISE = re.compile(r"\.(pdf|docx?|xlsx?|jpg|png)$|getfile|download|login|logon|/personal|pa0\d0|barriere|"
                   r"vo0\d\d|to0\d\d|kp0\d\d|si0\d\d.*(SILFDNR|__ksinr)|VOLFDNR|TOLFDNR", re.I)


def norm(s: str) -> str:
    s = unquote(s).lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", s)


def keys(name: str) -> list[str]:
    """Suchschlüssel einer Gemeinde: voller Name und Name ohne Klammerzusatz."""
    base = re.sub(r"\s*\(.*\)", "", name)
    out = {norm(name), norm(base)}
    return [k for k in out if len(k) >= 4]


def host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()

    kommunen = read_csv(KOMMUNEN_CSV)
    web = {k["ars"]: k["website"] for k in kommunen}
    members = defaultdict(list)
    for k in kommunen:
        if k["typ"] == "Mitgliedsgemeinde":
            members[k["samtgemeinde_ars"]].append(k)
    ris = load_ris()
    log = defaultdict(list)
    for row in read_csv(DATA / "crawler_log.csv"):
        log[row["ars"]].append((row["url"], row["text"]))

    fetch = links = None
    if a.live:
        from crawl_ris import fetch, links  # noqa: WPS433

    today = dt.date.today().isoformat()
    found = 0
    for sg_ars, mems in members.items():
        sg = ris.get(sg_ars, {})
        sg_url = sg.get("ris_url", "")
        sg_host = host(sg_url)
        sg_site = host(web.get(sg_ars, ""))
        sg_key = norm(re.sub(r"^Samtgemeinde\s+", "", sg.get("name", "")))
        cands = list(log.get(sg_ars, []))
        if fetch and sg_url and "redirect.phtml" not in sg_url:
            r, _ = fetch(sg_url)
            if r is not None and r.status_code == 200 and "html" in r.headers.get("Content-Type", ""):
                cands += links(r.text, r.url)
        for m in mems:
            row = ris.get(m["ars"])
            if row and row.get("quelle") == "manuell":
                continue
            ks = keys(m["name"])
            best = None
            for url, text in cands:
                if NOISE.search(url) or VENDOR_PAGES.search(url) or not STRONG.search(url):
                    continue
                if re.search(r"ausschuss|fraktion|ortsrat", text, re.I):
                    continue  # einzelnes Gremium, nicht der Rat bzw. Bereich der Gemeinde
                if re.search(r"\.aspx?/|\.html?/", urlparse(url).path):  # kaputt zusammengesetzte Pfade
                    continue
                if sg_site and host(url) == sg_site and not SITE_RIS.search(url):
                    continue  # normale Seite der Samtgemeinde-Website, kein RIS
                if host(url).endswith("ratsinfomanagement.net"):
                    seg = norm(urlparse(url).path.strip("/").split("/")[0])
                    if not seg or not any(k in seg or seg in k for k in ks):
                        continue
                n_url, n_text = norm(urlparse(url).path + "?" + urlparse(url).query), norm(text)
                # Name der Gemeinde muss im Pfad/Menü oder im Linktext stehen, nicht nur im Hostnamen
                hit_url = any(k in n_url for k in ks)
                hit_text = any(k == n_text or n_text.endswith(k) or n_text.startswith(("gemeinde" + k, "flecken" + k, "stadt" + k, "rat" + k)) for k in ks)
                if not (hit_url or hit_text):
                    continue
                # Heißt die Mitgliedsgemeinde wie die Samtgemeinde, muss eindeutig die Gemeinde gemeint sein
                if norm(m["name"]).startswith(sg_key) or sg_key.startswith(norm(re.sub(r"\s*\(.*\)", "", m["name"]))):
                    q = norm(unquote(unquote(url)))
                    if not re.search(r"(gemeinde|flecken|stadt)" + "|".join(ks), q) or re.search(r"samtgemeinde(" + "|".join(ks) + ")", q):
                        if not (host(url).endswith("ratsinfomanagement.net") and hit_url):
                            continue
                score = (2 if hit_url else 0) + (1 if hit_text else 0) - len(url) / 1000
                if best is None or score > best[0]:
                    best = (score, url, text)
            if best:
                _, url, text = best
                if host(url).endswith("ratsinfomanagement.net"):  # Submandant: nur erstes Pfadsegment
                    seg = urlparse(url).path.strip("/").split("/")[0]
                    url = f"https://{urlparse(url).hostname}/{seg}/"
                row = ris.setdefault(m["ars"], {f: "" for f in RIS_FIELDS} | {"ars": m["ars"]})
                row.update({"name": m["name"], "ris_url": url, "software": software_from_url(url) or sg.get("software", ""),
                            "quelle": "crawler-mitglied", "status": "gefunden", "geprueft_am": today,
                            "bemerkung": f"Bereich im RIS der Samtgemeinde; Linktext: {text}"[:200]})
                found += 1
                print(f"{m['name']} ({sg.get('name')}): {url}")
    save_ris(ris)
    print(f"{found} Mitgliedsgemeinden mit eigenem RIS-Bereich.")


if __name__ == "__main__":
    main()
