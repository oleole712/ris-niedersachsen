#!/usr/bin/env python3
"""Sucht für jeden RIS-Träger (Landkreise, Region, kreisfreie Städte,
Einheitsgemeinden, Samtgemeinden) das Ratsinformationssystem.

Vorgehen je Kommune:
  1. Startseite laden, Links mit RIS-Merkmalen in URL oder Linktext sammeln.
  2. Bis zu MAX_FOLLOW interne Seiten mit passendem Linktext nachladen
     (z. B. "Politik", "Ratsinformationssystem") und dort erneut suchen.
  3. Bestes Ziel wählen, Software am HTML erkennen, OParl-Schnittstelle prüfen.

robots.txt wird beachtet. Zeilen mit quelle=manuell werden nie überschrieben.
Ergebnis: data/ris.csv (aktualisiert) und data/crawler_log.csv (alle Kandidaten).

Aufruf:  python scripts/crawl_ris.py [--nur-offene] [--ars 031510009009 ...]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib import robotparser
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import (DATA, KOMMUNEN_CSV, LINKTEXT_HINT, RIS_TRAEGER, RIS_URL_HINT,  # noqa: E402
                    USER_AGENT, load_ris, read_csv, same_site, save_ris,
                    software_from_html, software_from_url, write_csv)

TIMEOUT = 20
MAX_FOLLOW = 6
WORKERS = 12

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "de"})

_robots: dict[str, robotparser.RobotFileParser | None] = {}
_robots_lock = threading.Lock()


def allowed(url: str) -> bool:
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    with _robots_lock:
        rp = _robots.get(base, "unset")
    if rp == "unset":
        rp = robotparser.RobotFileParser()
        try:
            r = session.get(base + "/robots.txt", timeout=TIMEOUT)
            if r.status_code >= 400:
                rp = None  # keine robots.txt -> alles erlaubt
            else:
                rp.parse(r.text.splitlines())
        except requests.RequestException:
            rp = None
        with _robots_lock:
            _robots[base] = rp
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


def fetch(url: str) -> tuple[requests.Response | None, str]:
    """Lädt eine Seite unter Beachtung von robots.txt (auch bei Weiterleitungen)."""
    if not allowed(url):
        return None, "robots.txt"
    try:
        r = session.get(url, timeout=TIMEOUT, allow_redirects=False)
        hops = 0
        while r.is_redirect and hops < 6:
            nxt = urljoin(r.url, r.headers.get("Location", ""))
            if not allowed(nxt):
                # Ziel der Weiterleitung ist bekannt, auch ohne es zu laden
                fake = requests.Response()
                fake.status_code, fake.url, fake._content = 0, nxt, b""
                return fake, "robots.txt (Ziel)"
            r = session.get(nxt, timeout=TIMEOUT, allow_redirects=False)
            hops += 1
        return r, ""
    except requests.RequestException as e:
        return None, type(e).__name__


def normalize(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc.lower(), p.path or "/", "", p.query, ""))


def ris_root(url: str) -> str:
    """Kürzt Deep-Links auf die Einstiegsseite des RIS."""
    p = urlparse(url)
    path = p.path
    m = re.search(r"^(.*?/(public|allris|bi|buergerinfo|sessionnet[^/]*|ratsinfo/[^/]+|ris/[^/]+|ratsinfo|ris))(/|$)", path, re.I)
    if m:
        path = m.group(1) + "/"
    elif re.search(r"/(si|gr|to|vo|kp|pa)0\d0", path):
        path = re.sub(r"/(si|gr|to|vo|kp|pa)0\d0.*$", "/", path)
    elif re.search(r"\.(asp|php)$", path) and re.search(r"(si|kp|vo|to|info)\d*\.", path):
        path = path.rsplit("/", 1)[0] + "/"
    return urlunparse((p.scheme, p.netloc.lower(), path or "/", "", "", ""))


def score(url: str, text: str, home: str) -> int:
    s = 0
    if software_from_url(url):
        s += 10
    if RIS_URL_HINT.search(url):
        s += 5
    if re.search(r"rats?info|bürgerinfo|buergerinfo|kreistagsinfo|ratsinformation", text, re.I):
        s += 4
    if not same_site(url, home):
        s += 2
    if re.search(r"login|logon|personal|_gi/|mandatstr", url, re.I):
        s -= 6
    if re.search(r"\.(pdf|docx?|jpg|png)$", url, re.I):
        s -= 20
    return s


def links(html: str, base: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        out.append((normalize(urljoin(base, href)), " ".join(a.get_text(" ").split())[:120]))
    for fr in soup.find_all("iframe", src=True):  # eingebettete RIS
        out.append((normalize(urljoin(base, fr["src"])), "iframe"))
    return out


def detect_oparl(ris_url: str, html: str) -> str:
    m = re.search(r"https?://[^\"'<> ]+/oparl[^\"'<> ]*", html, re.I)
    candidates = [m.group(0)] if m else []
    root = ris_root(ris_url)
    candidates += [
        urljoin(root, "oparl/1.0/system.asp"), urljoin(root, "oparl/1.0/system.php"),
        urljoin(root, "oparl/system"), urljoin(root, "oparl/v1.1/system"), urljoin(root, "oparl"),
    ]
    for c in candidates:
        r, _ = fetch(c)
        if r is None or r.status_code != 200:
            continue
        try:
            d = r.json()
        except ValueError:
            continue
        if "oparl.org/schema" in json.dumps(d)[:2000]:
            return r.url
    return ""


def crawl(k: dict) -> tuple[dict, list[dict]]:
    home = k["website"]
    log: list[dict] = []
    if not home:
        return {"status": "keine Website"}, log
    cands: dict[str, tuple[int, str, str]] = {}
    queue, seen = [home], set()

    def consider(url, text, via):
        sc = score(url, text, home)
        if sc >= 9 and (url not in cands or cands[url][0] < sc):
            cands[url] = (sc, text, via)
        log.append({"ars": k["ars"], "url": url, "text": text, "via": via, "score": sc})

    followed = 0
    while queue and followed <= MAX_FOLLOW:
        page = queue.pop(0)
        if page in seen:
            continue
        seen.add(page)
        r, err = fetch(page)
        if r is None:
            continue
        if r.status_code == 0:  # Weiterleitungsziel durch robots gesperrt
            consider(normalize(r.url), "", page)
            continue
        followed += 1
        if not same_site(r.url, home) and RIS_URL_HINT.search(r.url):
            consider(normalize(r.url), "", page)  # Weiterleitung direkt ins RIS
            continue
        if "html" not in r.headers.get("Content-Type", ""):
            continue
        for url, text in links(r.text, r.url):
            if RIS_URL_HINT.search(url) or re.search(r"rats?info|bürgerinfo|buergerinfo|kreistagsinfo", text, re.I):
                consider(url, text, page)
            if LINKTEXT_HINT.search(text) and url not in seen and len(queue) < 30:
                # interne Seiten und Weiterleitungs-Skripte (redirect.phtml) weiterverfolgen
                if same_site(url, home):
                    queue.append(url)

    if not cands:
        return {"status": "nicht gefunden"}, log

    # Externe Ziele hinter Weiterleitungsskripten auflösen und bewerten
    best_url, (best_sc, best_text, _) = max(cands.items(), key=lambda kv: kv[1][0])
    r, err = fetch(best_url)
    final = normalize(r.url) if r is not None and r.url else best_url
    html = r.text if r is not None and r.status_code == 200 else ""
    root = ris_root(final)
    software = software_from_url(final) or software_from_html(html)
    if r is not None and r.status_code in (0, 200):
        status = "gefunden"
    elif r is None and err.startswith("robots"):
        status = "gefunden (Prüfung durch robots.txt untersagt)"
    else:
        status = "prüfen"
    res = {
        "ris_url": root,
        "software": software,
        "oparl_url": detect_oparl(final, html) if html else "",
        "status": status,
        "http_status": str(r.status_code) if r is not None else err,
        "bemerkung": f"Linktext: {best_text}" if best_text else "",
    }
    return res, log


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nur-offene", action="store_true", help="nur Kommunen ohne RIS-URL")
    ap.add_argument("--ars", nargs="*", help="nur diese ARS")
    args = ap.parse_args()

    kommunen = {k["ars"]: k for k in read_csv(KOMMUNEN_CSV) if k["typ"] in RIS_TRAEGER}
    ris = load_ris()
    todo = []
    for ars, k in kommunen.items():
        row = ris[ars]
        if row.get("quelle") == "manuell":
            continue
        if args.ars and ars not in args.ars:
            continue
        if args.nur_offene and row.get("ris_url"):
            continue
        todo.append(k)
    print(f"{len(todo)} Kommunen werden durchsucht …", flush=True)

    today = dt.date.today().isoformat()
    all_log = []
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(crawl, k): k for k in todo}
        for i, f in enumerate(as_completed(futs), 1):
            k = futs[f]
            try:
                res, log = f.result()
            except Exception as e:  # einzelne Ausfälle dürfen den Lauf nicht abbrechen
                res, log = {"status": f"Fehler: {type(e).__name__}"}, []
            all_log += log
            row = ris[k["ars"]]
            row.update({"name": k["name"], "quelle": "crawler", "geprueft_am": today})
            for key in ("ris_url", "software", "oparl_url", "status", "http_status", "bemerkung"):
                if key in res:
                    row[key] = res[key]
            print(f"[{i}/{len(todo)}] {k['name']}: {res.get('ris_url') or res.get('status')}", flush=True)

    save_ris(ris)
    write_csv(DATA / "crawler_log.csv", sorted(all_log, key=lambda x: (x["ars"], -x["score"])),
              ["ars", "score", "url", "text", "via"])
    found = sum(1 for r in ris.values() if r.get("ris_url"))
    print(f"Fertig: {found}/{len(ris)} Träger mit RIS-URL.")


if __name__ == "__main__":
    main()
