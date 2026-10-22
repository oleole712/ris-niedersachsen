# Ratsinformationssysteme in Niedersachsen

Offenes Verzeichnis aller niedersächsischen Kommunen mit den Links zu ihren
Ratsinformationssystemen (RIS). Erfasst sind Landkreise, die Region Hannover,
kreisfreie Städte, Einheitsgemeinden, Samtgemeinden und Mitgliedsgemeinden.

| Ebene | Anzahl |
|---|---:|
| Landkreise | 36 |
| Region Hannover | 1 |
| Kreisfreie Städte | 8 |
| Einheitsgemeinden (einschl. Hannover und Göttingen) | 281 |
| Samtgemeinden | 114 |
| Mitgliedsgemeinden | 650 |
| **Gesamt** | **1.090** |

Stand des Gebietsbestands: 12.10.2026, also vor dem 01.11.2026 (siehe unten).

## Stand der RIS-Erfassung

<!-- STATUS:START -->
Automatisch erzeugt am 22.10.2026.

- RIS-Träger (ohne Mitgliedsgemeinden) mit Link: **439 von 440**
- Mitgliedsgemeinden mit eigenem Bereich im RIS: **68 von 650**, die übrigen sind über das RIS ihrer Samtgemeinde zugeordnet
- Häufigste Software: SessionNet (135), ALLRIS 4 (95), SD.NET RIM (89), ALLRIS (87), gremien.info (20), SD.NET (6), regisafe RIS (6), Verwaltungsportal (eingebettet) (5)
- OParl-Schnittstellen gefunden: **0**
- Offene Punkte: siehe [PRUEFLISTE.md](PRUEFLISTE.md)

| Status in `data/ris.csv` | Einträge |
|---|---:|
| gefunden | 501 |
| kein separates RIS | 2 |
| Einstiegsseite | 2 |
| kein öffentliches RIS gefunden | 1 |
| kein separates RIS gefunden | 1 |
| prüfen | 1 |
<!-- STATUS:END -->

## Dateien

| Datei | Inhalt |
|---|---|
| `data/kommunen.csv` | Stammdaten: ARS, AGS, Name, Typ, übergeordneter Landkreis bzw. Samtgemeinde, Website, Wikidata-ID |
| `data/ris.csv` | RIS je Träger: URL, Software, OParl-Endpunkt, Herkunft und Prüfstatus. Mitgliedsgemeinden nur, wenn sie einen eigenen Bereich im RIS haben |
| `data/ris-niedersachsen.csv` | Gesamtliste, eine Zeile je Kommune. Mitgliedsgemeinden erhalten das RIS ihrer Samtgemeinde |
| `data/ris-niedersachsen.sqlite` | Dieselben Daten als SQLite-Datenbank mit den Tabellen `kommunen`, `ris` und der View `kommunen_ris` |
| `PRUEFLISTE.md` | Einträge, die im Browser nachgeprüft werden sollten (automatisch erzeugt) |
| `data/gebietsaenderungen.csv` | Bekannte und geplante Gebietsänderungen mit Rechtsgrundlage |
| `data/crawler_log.csv` | Alle Link-Kandidaten der Crawler-Läufe (zur Nachkontrolle, wird fortgeschrieben) |

`ars` ist der zwölfstellige Amtliche Regionalschlüssel. Er dient als Primärschlüssel in allen Dateien.

Beispielabfrage:

```sql
SELECT name, typ, samtgemeinde, ris_url, software
FROM kommunen_ris
WHERE kreis = 'Landkreis Gifhorn';
```

## Wie die Daten gepflegt werden

- **Manuell (`quelle = manuell`):** Diese Einträge wurden von Hand recherchiert oder korrigiert. Der Crawler überschreibt sie nie. Korrekturen also immer in `data/ris.csv` eintragen und `quelle` auf `manuell` setzen.
- **Crawler (`scripts/crawl_ris.py`):** Er durchsucht die Website jeder Kommune nach Links ins RIS, erkennt die Software und prüft, ob eine OParl-Schnittstelle vorhanden ist. Die robots.txt der Websites wird beachtet. Er läuft als GitHub Action, monatlich für offene Einträge und manuell über *Actions → RIS-Crawler → Run workflow*.
- **Linkprüfung (`scripts/check_links.py`):** Sie läuft wöchentlich. Nicht erreichbare Links stehen im Ergebnis des Workflows und in `linkcheck_report.md`.
- **Datenbank (`scripts/build_db.py`):** Sie erzeugt SQLite-Datei und Gesamtliste aus den beiden CSV-Dateien.

Lokal:

```bash
pip install -r requirements.txt
python scripts/crawl_ris.py --nur-offene   # oder: --ars 031510009009
python scripts/build_db.py
```

## Bekannte Grenzen

- Mitgliedsgemeinden haben häufig kein eigenes RIS. Ihre Gremien stehen im RIS der Samtgemeinde, die Spalte `ris_herkunft` weist das aus. Hat eine Mitgliedsgemeinde ein eigenes RIS, kann es in `data/ris.csv` mit ihrer ARS ergänzt werden.
- Einige Anbieter verbieten automatisierte Zugriffe per robots.txt, z. B. `*.sitzung-online.de`. Solche Links sind gefunden, werden aber nicht automatisch geprüft.
- Die Software-Erkennung beruht auf URL-Mustern und Merkmalen im HTML-Quelltext. Sie ist nicht in jedem Fall verlässlich.

## Gebietsänderung zum 01.11.2026

Die Samtgemeinde Nordkehdingen und ihre Mitgliedsgemeinden Balje, Freiburg (Elbe),
Krummendeich, Oederquart und Wischhafen werden aufgelöst. Aus ihnen wird die
Einheitsgemeinde Nordkehdingen neu gebildet (Gesetz vom 03.03.2026, Nds. GVBl. 2026 Nr. 19).
Die betroffenen Einträge haben in `gueltig_bis` den Wert `2026-10-31`. Sobald das
Landesamt für Statistik den neuen Schlüssel veröffentlicht, wird die neue Gemeinde ergänzt.

## Quellen und Lizenz

Die Stammdaten stammen aus Wikidata (CC0). Sie sind gegen den amtlichen Gebietsstand
abgeglichen: 939 Gemeinden, davon 650 Mitgliedsgemeinden in 114 Samtgemeinden.
Die RIS-Links stammen von den Websites der Kommunen.

Daten: [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/deed.de) · Code: MIT
