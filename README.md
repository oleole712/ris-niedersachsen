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

## Stand der RIS-Erfassung (12.10.2026)

Für 439 der 440 RIS-Träger ist ein Link erfasst. Für Braunlage wurde kein öffentliches RIS gefunden, die Stadt stellt laut Website gerade um. Die 650 Mitgliedsgemeinden sind über das RIS ihrer Samtgemeinde zugeordnet.

| Status (`data/ris.csv`) | Anzahl | Bedeutung |
|---|---:|---|
| gefunden | 410 | Direkter Link ins RIS (teils ohne automatische Prüfung, weil robots.txt oder der Server automatische Abrufe blockt) |
| Weiterleitung über Gemeinde-Website | 10 | Der Link ist eine Weiterleitung der Gemeinde-Website (IKISS `redirect.phtml`). Er funktioniert im Browser, das Ziel ist aber wegen robots.txt nicht automatisch ermittelt |
| Einstiegsseite | 9 | Seite der Kommune, die zum RIS führt |
| kein separates RIS | 3 | Sitzungsunterlagen stehen auf der normalen Website |
| prüfen | 7 | Der Prüfserver hat den Link nicht erreicht (Zeitüberschreitung o. Ä.) |

Die Software ist bei 362 Trägern erkannt: SessionNet, ALLRIS/ALLRIS 4, ratsinfomanagement.net, gremien.info, more!rubin u. a.

## Dateien

| Datei | Inhalt |
|---|---|
| `data/kommunen.csv` | Stammdaten: ARS, AGS, Name, Typ, übergeordneter Landkreis bzw. Samtgemeinde, Website, Wikidata-ID |
| `data/ris.csv` | RIS je Träger (alle Ebenen außer Mitgliedsgemeinden): URL, Software, OParl-Endpunkt, Herkunft und Prüfstatus |
| `data/ris-niedersachsen.csv` | Gesamtliste, eine Zeile je Kommune. Mitgliedsgemeinden erhalten das RIS ihrer Samtgemeinde |
| `data/ris-niedersachsen.sqlite` | Dieselben Daten als SQLite-Datenbank mit den Tabellen `kommunen`, `ris` und der View `kommunen_ris` |
| `data/crawler_log.csv` | Alle Kandidaten des letzten Crawler-Laufs (zur Nachkontrolle) |

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
