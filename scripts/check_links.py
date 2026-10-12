#!/usr/bin/env python3
"""Prüft alle RIS-URLs in data/ris.csv auf Erreichbarkeit.

Schreibt http_status und geprueft_am zurück und setzt status auf
"nicht erreichbar", wenn eine URL dauerhaft fehlschlägt. Manuell gepflegte
Zeilen werden geprüft, ihre URL aber nie verändert.
Gibt am Ende eine Liste der Probleme aus (für das Issue im Workflow).
"""
from __future__ import annotations

import datetime as dt
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import DATA, load_ris, save_ris  # noqa: E402
from crawl_ris import fetch  # noqa: E402  (beachtet robots.txt)


def check(url: str) -> str:
    r, err = fetch(url)
    if r is None:
        return err or "Fehler"
    return str(r.status_code or "Weiterleitung (robots.txt)")


def main() -> None:
    ris = load_ris()
    rows = [r for r in ris.values() if r.get("ris_url")]
    today = dt.date.today().isoformat()
    with ThreadPoolExecutor(12) as ex:
        results = list(ex.map(lambda r: check(r["ris_url"]), rows))
    problems = []
    for row, code in zip(rows, results):
        row["http_status"] = code
        row["geprueft_am"] = today
        ok = code.startswith(("2", "3", "Weiterleitung", "robots"))
        if not ok:
            problems.append(f"| {row['name']} | {row['ris_url']} | {code} |")
            if row.get("quelle") != "manuell":
                row["status"] = "nicht erreichbar"
    save_ris(ris)
    report = DATA.parent / "linkcheck_report.md"
    report.write_text(
        "## Linkprüfung " + today + "\n\n"
        + (f"{len(problems)} RIS-Links nicht erreichbar:\n\n| Kommune | URL | Status |\n|---|---|---|\n"
           + "\n".join(problems) if problems else "Alle RIS-Links erreichbar.") + "\n",
        encoding="utf-8")
    print(report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
