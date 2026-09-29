# Pipeline — Adressbuch Remscheid 1935

Acht Schritte von der CompGen-Erfassung zu den Kartendaten in `docs/data/`.
Alle Skripte werden aus dem Repository-Hauptordner aufgerufen.

## Voraussetzungen

- Python 3.10+, `pip install -r requirements.txt` (nur `requests`)
- Für Schritt 2: lokale Nominatim-Instanz auf `http://localhost:8080`
  (z. B. Container `mediagis/nominatim:4.4`; URL in `02_geocodierung.py`)
- Für Schritt 5: `KICONNECT_API_KEY` in `.env` (Vorlage: `.env.example`)

## Ablauf

```bash
python3 src/01_vorbereitung.py              # Filter + Adressnormalisierung
python3 src/02_geocodierung.py              # Nominatim, resume-fähig
python3 src/03_join_geojson.py              # Koordinaten + Genauigkeit anfügen
python3 src/03b_firmenabgleich.py           # Einträge derselben Firma erkennen -> Prüfliste
python3 tools/pruefliste.py                 # Prüfliste im Browser durchgehen (optional)
python3 src/04_branchen_klassifikation.py   # Stichwortregeln -> branchen_mapping.csv
python3 src/05_llm_branchen_klassifikation.py [--limit N]   # Sprachmodell, resume-fähig
python3 src/06_gewerbe_export.py            # Kartendaten schreiben
python3 src/07_werkzeug_konsolidierung.py   # Werkzeugfirmen + Piktogramme
```

Schritt 2 und 5 fragen nur ab, was noch nicht im Cache in `output/` steht.
Nach einer Änderung an `strassen_mapping.csv` reichen 01–03 und 06–07; nach
einer Änderung an `branchen_mapping.csv` reichen 06–07. Schritt 7 überschreibt
die Ausgabe von Schritt 6 und lässt sich beliebig oft wiederholen.

Tests (ohne Nominatim und Sprachmodell): `python3 -m unittest discover tests`

## Eingabe / Ausgabe

| Datei | Erzeugt von | Inhalt |
|---|---|---|
| `data/remscheidABNRW1935.csv` | (Quelle) | CompGen-Erfassung, unverändert aus der [Coding-da-Vinci-Freigabe](https://download.codingdavinci.de/s/c8zc6Bn4dZMzyFS) (Stand 06.08.2021); **Tab-getrennt** trotz `.csv`, Anführungszeichen gehören zum Text |
| `data/strassen_mapping.csv` | von Hand | Regex historischer Straßenname → heutiger Name, mit Kommentar |
| `output/remscheid1935_geovorbereitung.csv` | 01 | nur EinwVz + GewVz; `generation`, `adresse_norm`, `geoadresse` |
| `output/unique_geoadressen.csv` | 02 | distinkte `geoadresse` mit Häufigkeit |
| `output/geocoding_cache.csv` | 02 | Nominatim-Antworten (inkrementell) |
| `output/remscheid1935_geocoded.csv` | 03 | alle Zeilen + Koordinaten + `genauigkeit` |
| `output/remscheid1935.geojson` | 03 | alle Zeilen mit Treffer |
| `output/geocoding_fehlschlaege.csv` | 03 | distinkte Adressen ohne Treffer + Häufigkeit |
| `data/firmen_abgleich.csv` | 3b, von Hand | Prüfliste: ähnliche Namen an derselben Adresse, Spalte `entscheidung` (ja/nein) |
| `output/firmen_zuordnung.csv` | 3b | GewVz-`id` → `firma_id` |
| `data/branchen_mapping.csv` | 04, 05 | Erst-Branche → Unterbranche, Oberkategorie, WZ 2008 |
| `output/llm_branchen_cache.json` | 05 | Antworten des Sprachmodells je Erst-Branche |
| `docs/data/gewerbe.geojson` | 06, 07 | GewVz-Punkte für die Karte |
| `docs/data/branchen.json` | 06 | Filterhierarchie Oberkategorie → Unterbranchen |
| `data/werkzeug_konsolidierung.csv` | 07 | Prüfliste: welche Unterbranche welches Piktogramm bekommt |

## Regeln im Einzelnen

**Adressnormalisierung (01).** `78/80` → `78`, `2-4` → `2`, `5 u. 6` → `5`;
„… Ecke …“ und der Marker „xxx nicht in Liste xxx“ entfallen. Danach greift
die erste passende Regel aus `strassen_mapping.csv`. Generationszusätze
(`d. J.`, `d. Ä.`) wandern vom Vornamen in die Spalte `generation`.

**Genauigkeit (03).** `haus`, wenn die Nominatim-Antwort eine Hausnummer
enthält (Gebäude, Adresspunkt oder benanntes Objekt mit Hausnummer);
`strasse`, wenn nur die Straße gefunden wurde (`class = highway`);
sonst `ungefaehr` (Ortsteil, Hofschaft).

**Firmenabgleich (3b).** Das Gewerbeverzeichnis führt eine Firma unter jeder
ihrer Branchen erneut, oft in anderer Schreibweise. Verglichen wird nur
innerhalb derselben `adresse_norm` (Zweigwerke an anderen Adressen bleiben
getrennt). Namen werden normalisiert (Rechtsformen, `&`/`u.`/`und`,
`Gebr.`, `Wwe.`, Umlaute, Satzzeichen); gleicher Schlüssel heißt automatisch
dieselbe Firma. Nie zusammengeführt werden verschiedene Generationen
(`d. J.`/`d. Ä.`) und Personen mit unverträglichem Vornamen (`Artur`/`Richard`;
`Wilh.`/`Wilhelm` ist verträglich). Ähnliche Namen (Abkürzungen, Tippfehler,
Generationszusatz nur bei einem) landen in `data/firmen_abgleich.csv`.
Die Spalte `entscheidung` füllt man von Hand, am bequemsten mit
`python3 tools/pruefliste.py` (Tasten J/N, ←/→; jede Entscheidung wird sofort
gespeichert). Entscheidungen überstehen jeden neuen Lauf.

**Erst-Branche (04, 06).** Die erste Angabe nach dem Firmennamen im Feld
`Firmenname`, Rechtsformen wie `G.m.b.H.` übersprungen, zerteilte Angaben wie
„Weiß-, Bunt- u. Wollwarengeschäft“ wieder zusammengesetzt. Die Logik steht
einmal in `src/branchen.py`, damit 04 und 06 dieselben Schlüssel bilden.

**Branchen-Mapping (04, 05).** 04 schlägt per Stichwortregel eine Kategorie
vor und schreibt sie in die Spalten `heuristik_*`. Existiert das Mapping schon,
wird es zusammengeführt: bekannte Branchen behalten ihre Einordnung, neue
kommen mit `quelle = heuristik` hinzu, weggefallene bleiben mit
`frequency = 0` stehen. 05 lässt jede Branche vom Sprachmodell einer von
17 Oberkategorien zuordnen; das Ergebnis ersetzt die Heuristik, der WZ-2008-Code
ist grob je Oberkategorie gesetzt. **Zeilen mit `quelle = manuell` fassen weder
04 noch 05 inhaltlich an** — so markiert man Korrekturen von Hand.

**Werkzeug-Konsolidierung (07).** Mehrere Einträge derselben Firma (gleicher
Firmenname-Kopf, gleiche Koordinate) werden zu einem; die Firma erhält das
spezifischste Piktogramm (z. B. Schraubstock vor „Werkzeugfabrik“). Stehen
danach mehrere Firmen am selben Punkt, trägt eine davon das Symbol, die
anderen erscheinen in ihrer Liste.
