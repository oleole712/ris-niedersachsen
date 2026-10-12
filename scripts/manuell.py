#!/usr/bin/env python3
"""Trägt ein RIS manuell ein oder korrigiert es (wird vom Crawler nie überschrieben).

Beispiele:
  python scripts/manuell.py 031530017017 https://www.goslar.de/stadt/politik/allris/ --software ALLRIS
  python scripts/manuell.py 031530016016 "" --status "kein öffentliches RIS" --bemerkung "Umstellung angekündigt"
  python scripts/manuell.py 033595407004 https://... --name "Balje"   # eigenes RIS einer Mitgliedsgemeinde
"""
import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import KOMMUNEN_CSV, RIS_FIELDS, load_ris, read_csv, save_ris, software_from_url  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("ars")
ap.add_argument("url")
ap.add_argument("--software", default=None)
ap.add_argument("--oparl", default="")
ap.add_argument("--status", default=None)
ap.add_argument("--bemerkung", default="")
ap.add_argument("--name", default=None)
a = ap.parse_args()

kommunen = {k["ars"]: k for k in read_csv(KOMMUNEN_CSV)}
if a.ars not in kommunen:
    sys.exit(f"Unbekannte ARS {a.ars}")
ris = load_ris()
row = ris.setdefault(a.ars, {f: "" for f in RIS_FIELDS} | {"ars": a.ars})
row.update({
    "name": a.name or kommunen[a.ars]["name"],
    "ris_url": a.url,
    "software": a.software if a.software is not None else software_from_url(a.url),
    "oparl_url": a.oparl,
    "quelle": "manuell",
    "status": a.status or ("gefunden" if a.url else "kein RIS gefunden"),
    "http_status": "",
    "geprueft_am": dt.date.today().isoformat(),
    "bemerkung": a.bemerkung,
})
save_ris(ris)
print(f"{row['name']}: {row['ris_url'] or row['status']} ({row['software'] or 'Software unbekannt'})")
