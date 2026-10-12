#!/usr/bin/env python3
"""Baut aus data/kommunen.csv und data/ris.csv die SQLite-Datenbank
data/ris-niedersachsen.sqlite sowie die flache Gesamtliste
data/ris-niedersachsen.csv (eine Zeile je Kommune, Mitgliedsgemeinden mit
dem RIS ihrer Samtgemeinde)."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import DATA, KOMMUNEN_CSV, RIS_FIELDS, read_csv, write_csv  # noqa: E402

DB = DATA / "ris-niedersachsen.sqlite"

VIEW = """
CREATE VIEW kommunen_ris AS
SELECT k.ars, k.ags, k.name, k.typ, k.kreis_ars, kr.name AS kreis,
       k.samtgemeinde_ars, sg.name AS samtgemeinde, k.website,
       COALESCE(NULLIF(r.ris_url, ''), rs.ris_url) AS ris_url,
       COALESCE(NULLIF(r.software, ''), rs.software) AS software,
       COALESCE(NULLIF(r.oparl_url, ''), rs.oparl_url) AS oparl_url,
       CASE WHEN NULLIF(r.ris_url, '') IS NOT NULL THEN 'eigenes RIS'
            WHEN NULLIF(rs.ris_url, '') IS NOT NULL THEN 'über Samtgemeinde'
            ELSE 'offen' END AS ris_herkunft,
       COALESCE(r.status, rs.status) AS status,
       COALESCE(r.geprueft_am, rs.geprueft_am) AS geprueft_am,
       k.wikidata, k.gueltig_bis, k.bemerkung
FROM kommunen k
LEFT JOIN kommunen kr ON kr.ars = k.kreis_ars
LEFT JOIN kommunen sg ON sg.ars = k.samtgemeinde_ars
LEFT JOIN ris r  ON r.ars = k.ars
LEFT JOIN ris rs ON rs.ars = k.samtgemeinde_ars
ORDER BY k.ars;
"""


def write_pruefliste(ris: list[dict]) -> None:
    """PRUEFLISTE.md: Einträge, die eine Person im Browser nachprüfen sollte."""
    gruppen = [
        ("Weiterleitung über Gemeinde-Website",
         "Link öffnen, der Weiterleitung folgen und die Ziel-URL eintragen."),
        ("Einstiegsseite",
         "Seite öffnen, den Link ins eigentliche RIS suchen und eintragen."),
        ("nicht erreichbar", "Link war bei der letzten Prüfung tot (404/5xx/Host nicht erreichbar)."),
        ("prüfen", "Link konnte nicht eindeutig bestätigt werden."),
        ("kein", "Kein öffentliches RIS gefunden. Gelegentlich erneut nachsehen."),
    ]
    out = ["# Prüfliste", "",
           "Wird von `scripts/build_db.py` automatisch erzeugt. Erledigte Einträge verschwinden, "
           "sobald sie mit `scripts/manuell.py` korrigiert sind.", "",
           "Eintragen (Beispiel):", "", "```bash",
           "python scripts/manuell.py <ARS> <RIS-URL>", "python scripts/build_db.py", "```", ""]
    total = 0
    for prefix, hinweis in gruppen:
        rows = [r for r in ris if r.get("status", "").startswith(prefix)]
        if not rows:
            continue
        total += len(rows)
        out += [f"## {prefix} ({len(rows)})", "", hinweis, "",
                "| ARS | Kommune | Link | Bemerkung |", "|---|---|---|---|"]
        for r in sorted(rows, key=lambda r: r["ars"]):
            link = f"[öffnen]({r['ris_url']})" if r.get("ris_url") else "–"
            out.append(f"| `{r['ars']}` | {r['name']} | {link} | {r.get('bemerkung', '').replace('|', '/')} |")
        out.append("")
    out.insert(2, f"Offene Einträge: **{total}**")
    out.insert(3, "")
    (DATA.parent / "PRUEFLISTE.md").write_text("\n".join(out), encoding="utf-8")


def main() -> None:
    kommunen = read_csv(KOMMUNEN_CSV)
    ris = read_csv(DATA / "ris.csv")
    DB.unlink(missing_ok=True)
    con = sqlite3.connect(DB)
    kcols = list(kommunen[0].keys())
    con.execute(f"CREATE TABLE kommunen ({', '.join(c + ' TEXT' for c in kcols)}, PRIMARY KEY (ars))")
    con.execute(f"CREATE TABLE ris ({', '.join(c + ' TEXT' for c in RIS_FIELDS)}, PRIMARY KEY (ars))")
    con.executemany(f"INSERT INTO kommunen VALUES ({','.join('?' * len(kcols))})",
                    [[k[c] for c in kcols] for k in kommunen])
    con.executemany(f"INSERT INTO ris VALUES ({','.join('?' * len(RIS_FIELDS))})",
                    [[r.get(c, "") for c in RIS_FIELDS] for r in ris])
    con.executescript(VIEW)
    con.commit()
    cur = con.execute("SELECT * FROM kommunen_ris")
    cols = [d[0] for d in cur.description]
    flat = [dict(zip(cols, row)) for row in cur.fetchall()]
    con.close()
    write_csv(DATA / "ris-niedersachsen.csv", flat, cols)
    write_pruefliste(ris)
    offen = sum(1 for f in flat if f["ris_herkunft"] == "offen")
    print(f"{DB.name}: {len(kommunen)} Kommunen, {len(ris)} RIS-Träger, {offen} ohne RIS-Zuordnung")


if __name__ == "__main__":
    main()
