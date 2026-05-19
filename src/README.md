# Pipeline — Adressbuch Remscheid 1935

## Voraussetzungen

- Python 3.10+
- Modul `requests` (`pip install requests`)
- Lokale Nominatim-Instanz auf `http://localhost:8080` (Port in `02_geocodierung.py` konfigurierbar) — z.B. `mediagis/nominatim:4.4` Container

## Ablauf

```bash
# Schritt 1: Filter + Adressnormalisierung
python3 src/01_vorbereitung.py

# Schritt 2: Nominatim-Abfrage (Resume-faehig, kann abgebrochen werden)
python3 src/02_geocodierung.py

# Schritt 3: Cache joinen, finalen CSV + GeoJSON schreiben
python3 src/03_join_geojson.py
```

## Eingabe / Ausgabe

| Datei | Erzeugt von | Inhalt |
|---|---|---|
| `data/remscheidABNRW1935.csv` | (vorhanden) | Quelle (TSV trotz `.csv`-Endung) |
| `output/remscheid1935_geovorbereitung.csv` | 01 | gefiltert auf EinwVz+GewVz, `generation`, `adresse_norm`, `geoadresse` |
| `output/unique_geoadressen.csv` | 02 | distinkte `geoadresse` mit Frequenz |
| `output/geocoding_cache.csv` | 02 | Nominatim-Antworten (inkrementell, resume-faehig) |
| `output/remscheid1935_geocoded.csv` | 03 | alle Zeilen + Koordinaten |
| `output/remscheid1935.geojson` | 03 | nur Zeilen mit Treffer |
| `output/geocoding_fehlschlaege.csv` | 03 | distinkte ungefundene Adressen + Frequenz |

## Filter- und Normalisierungsregeln

Siehe `10-Projekte/Adressbuch-Remscheid-1935/Geokodierung-Vorbereitung.md` im Obsidian-Vault.