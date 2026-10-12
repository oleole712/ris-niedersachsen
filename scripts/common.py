"""Gemeinsame Hilfsfunktionen für Crawler, Linkprüfung und Datenbank-Build."""
from __future__ import annotations

import csv
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
KOMMUNEN_CSV = DATA / "kommunen.csv"
RIS_CSV = DATA / "ris.csv"

USER_AGENT = (
    "ris-niedersachsen/1.0 (+https://github.com/oleole712/ris-niedersachsen; "
    "Verzeichnis der Ratsinformationssysteme niedersächsischer Kommunen)"
)

RIS_FIELDS = [
    "ars", "name", "ris_url", "software", "oparl_url",
    "quelle", "status", "http_status", "geprueft_am", "bemerkung",
]

# Typen mit eigener Vertretung, die ein eigenes RIS betreiben (können).
# Mitgliedsgemeinden werden über ihre Samtgemeinde abgebildet, sofern sie
# kein eigenes RIS haben.
RIS_TRAEGER = {"Landkreis", "Region", "Kreisfreie Stadt", "Einheitsgemeinde", "Samtgemeinde"}

# Erkennung der Software anhand der URL (erste Treffer gewinnt).
URL_SOFTWARE = [
    (re.compile(r"sitzung-online\.de/(public|personal)", re.I), "ALLRIS 4"),
    (re.compile(r"/allris", re.I), "ALLRIS"),
    (re.compile(r"/(si|gr|to|vo|kp|pa)0\d\d(\?|$|/)", re.I), "ALLRIS 4"),
    (re.compile(r"_e\.asp|/(si|to|vo|kp)0\d0\.asp", re.I), "ALLRIS"),
    (re.compile(r"sessionnet|si0040|si0057|/bi/(info|si|kp|vo|to)\d*\.(asp|php)", re.I), "SessionNet"),
    (re.compile(r"more-rubin", re.I), "more!rubin"),
    (re.compile(r"ratsinfomanagement\.net", re.I), "ratsinfomanagement.net"),
    (re.compile(r"sdnet|sitzungsdienst-", re.I), "SD.NET"),
    (re.compile(r"mandatos", re.I), "Mandatos"),
    (re.compile(r"gremien\.info", re.I), "gremien.info"),
    (re.compile(r"councilservice|mein-intra\.net", re.I), "Verwaltungsportal (eingebettet)"),
    (re.compile(r"ris-portal\.de", re.I), "ris-portal.de"),
    (re.compile(r"ratsinfoservice\.de", re.I), "ratsinfoservice.de"),
    (re.compile(r"kommune-aktiv\.de", re.I), "kommune-aktiv.de"),
]

# Seiten von Software-Herstellern und Verzeichnissen, die kein RIS einer Kommune sind.
VENDOR_PAGES = re.compile(
    r"cc-egov\.de|somacos\.de|sitzungsdienst\.net|sternberg|more-software|findcity\.de|"
    r"wikipedia\.org|facebook\.com|instagram\.com|apps\.apple\.com|play\.google\.com", re.I)

# Erkennung der Software anhand des HTML-Quelltexts der RIS-Seite.
HTML_SOFTWARE = [
    (re.compile(r"SessionNet|Somacos", re.I), "SessionNet"),
    (re.compile(r"ALLRIS", re.I), "ALLRIS"),
    (re.compile(r"more!rubin|more-rubin", re.I), "more!rubin"),
    (re.compile(r"SD\.NET|Sternberg", re.I), "SD.NET"),
    (re.compile(r"Mandatos", re.I), "Mandatos"),
    (re.compile(r"Session\s*IO|Ratsinfo\s*von\s*CC", re.I), "Sonstige"),
]

# URL-Merkmale, die mit hoher Wahrscheinlichkeit auf ein RIS zeigen.
RIS_URL_HINT = re.compile(
    r"sitzung-online\.de|/allris|sessionnet|si0040|si0057|/bi/|buergerinfo|bürgerinfo|"
    r"ratsinfo|ratsinformation|more-rubin|ratsinfomanagement|sdnet|mandatos|"
    r"/(si|gr)0\d0(\?|$|/)|kreistagsinfo|/ris/|//ris[.-]|//www\.ris[.-]|gremieninfo|sitzungsdienst|"
    r"councilservice|/sessionnet|buergerinfo|gremien\.info|mein-intra\.net|ris-portal\.de|"
    r"ratsinformationsdienst\.de|ratsinfoservice\.de|kommune-aktiv\.de",
    re.I,
)

# Linktexte, denen der Crawler auf der Gemeinde-Website folgt.
LINKTEXT_HINT = re.compile(
    r"rats?\s*-?\s*info|ratsinformation|bürger\s*-?\s*info|buerger\s*-?\s*info|"
    r"kreistags?\s*-?\s*info|sitzungskalender|sitzungsdienst|sitzungstermine|sessionnet|"
    r"allris|gremieninfo|ratssitzung|politik|kreistag|ratsarbeit|\brat\b|stadtrat|gemeinderat|"
    r"samtgemeinderat|weiter zur startseite|zur startseite",
    re.I,
)


def software_from_url(url: str) -> str:
    for rx, name in URL_SOFTWARE:
        if rx.search(url):
            return name
    return ""


def software_from_html(html: str) -> str:
    for rx, name in HTML_SOFTWARE:
        if rx.search(html):
            return name
    return ""


def same_site(a: str, b: str) -> bool:
    ha, hb = urlparse(a).hostname or "", urlparse(b).hostname or ""
    strip = lambda h: h[4:] if h.startswith("www.") else h
    return strip(ha) == strip(hb)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def load_ris() -> dict[str, dict]:
    """ris.csv als dict ars -> Zeile; fehlende Träger werden ergänzt."""
    kommunen = read_csv(KOMMUNEN_CSV)
    ris = {r["ars"]: r for r in read_csv(RIS_CSV)}
    for k in kommunen:
        if k["typ"] in RIS_TRAEGER and k["ars"] not in ris:
            ris[k["ars"]] = {f: "" for f in RIS_FIELDS} | {"ars": k["ars"], "name": k["name"]}
    return ris


def save_ris(ris: dict[str, dict]) -> None:
    write_csv(RIS_CSV, sorted(ris.values(), key=lambda r: r["ars"]), RIS_FIELDS)
