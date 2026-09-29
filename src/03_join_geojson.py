#!/usr/bin/env python3
"""
Schritt 3: Cache mit Vorbereitungsdatei joinen, finalen CSV + GeoJSON schreiben.

Eingaben:
  output/remscheid1935_geovorbereitung.csv
  output/geocoding_cache.csv

Ausgaben:
  output/remscheid1935_geocoded.csv         (alle Zeilen + lat/lon/match-Felder + genauigkeit)
  output/remscheid1935.geojson              (nur Zeilen mit Treffer)
  output/geocoding_fehlschlaege.csv         (distinkte geoadressen ohne Treffer + Frequenz)

Spalte `genauigkeit` bewertet jeden Treffer:
  haus       Nominatim-Antwort enthaelt eine Hausnummer (Gebaeude oder Adresspunkt)
  strasse    nur die Strasse gefunden (class = highway), Punkt liegt irgendwo auf ihr
  ungefaehr  alles andere, z.B. Hofschaft/Ortsteil als Flaeche oder Punkt
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PREP_FILE = REPO / "output" / "remscheid1935_geovorbereitung.csv"
CACHE_FILE = REPO / "output" / "geocoding_cache.csv"
GEOCODED_FILE = REPO / "output" / "remscheid1935_geocoded.csv"
GEOJSON_FILE = REPO / "output" / "remscheid1935.geojson"
FEHL_FILE = REPO / "output" / "geocoding_fehlschlaege.csv"

GEOJSON_FELDER = [
    "page", "lastname", "firstname", "generation", "Beruf o. ä.",
    "Adresse", "adresse_norm", "Ortsname", "Firmenname",
    "Familienstand", "id",
    "lat", "lon", "match_class", "osm_type", "genauigkeit",
]

# Hausnummern-Komponente in display_name, z.B. "24", "31a", "2-4", "78;80", "2;2a;4"
# (max. 4 Ziffern, damit die fuenfstellige Postleitzahl nicht als Hausnummer gilt)
HAUSNR_KOMPONENTE = re.compile(r"^\d{1,4}[a-z]?(?:[;\-]\d{1,4}[a-z]?)*$", re.IGNORECASE)


def genauigkeit(display_name: str, match_class: str) -> str:
    """Bewertet die Genauigkeit eines Nominatim-Treffers (haus | strasse | ungefaehr)."""
    teile = (t.replace(" ", "") for t in display_name.split(","))
    if any(HAUSNR_KOMPONENTE.match(t) for t in teile):
        return "haus"
    if match_class == "highway":
        return "strasse"
    return "ungefaehr"


def load_cache() -> dict[str, dict]:
    if not CACHE_FILE.exists():
        print(f"Cache fehlt: {CACHE_FILE}", file=sys.stderr)
        sys.exit(1)
    cache: dict[str, dict] = {}
    with open(CACHE_FILE, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cache[row["geoadresse"]] = row
    return cache


def main() -> int:
    cache = load_cache()
    print(f"Cache-Eintraege: {len(cache)}")

    n_total = 0
    n_hit = 0
    fehl_freq: dict[str, int] = {}
    n_genau: Counter[str] = Counter()

    with open(PREP_FILE, encoding="utf-8", newline="") as fin:
        reader = csv.DictReader(fin)
        out_fields = list(reader.fieldnames or []) + ["lat", "lon", "match_class", "osm_type",
                                                      "display_name", "genauigkeit"]
        with open(GEOCODED_FILE, "w", encoding="utf-8", newline="") as fout, \
             open(GEOJSON_FILE, "w", encoding="utf-8") as fgeo:
            writer = csv.DictWriter(fout, fieldnames=out_fields)
            writer.writeheader()
            fgeo.write('{"type":"FeatureCollection","features":[\n')
            first_feature = True

            for row in reader:
                n_total += 1
                g = row.get("geoadresse", "")
                hit = cache.get(g, {}) if g else {}
                for k in ("lat", "lon", "match_class", "osm_type", "display_name"):
                    row[k] = hit.get(k, "")
                lat, lon = row["lat"], row["lon"]
                row["genauigkeit"] = genauigkeit(row["display_name"], row["match_class"]) if lat else ""
                n_genau[row["genauigkeit"]] += 1
                writer.writerow(row)

                if lat and lon:
                    n_hit += 1
                    props = {k: row.get(k, "") for k in GEOJSON_FELDER}
                    feature = {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                        "properties": props,
                    }
                    if not first_feature:
                        fgeo.write(",\n")
                    first_feature = False
                    fgeo.write(json.dumps(feature, ensure_ascii=False))
                else:
                    if g:
                        fehl_freq[g] = fehl_freq.get(g, 0) + 1

            fgeo.write("\n]}\n")

    with open(FEHL_FILE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["geoadresse", "frequency"])
        for g, n in sorted(fehl_freq.items(), key=lambda x: (-x[1], x[0])):
            w.writerow([g, n])

    print(f"Datensaetze gesamt : {n_total}")
    print(f"Mit Koordinaten    : {n_hit} ({100*n_hit/max(n_total,1):.1f} %)")
    print(f"  davon hausgenau  : {n_genau['haus']}")
    print(f"  nur Strasse      : {n_genau['strasse']}")
    print(f"  ungefaehr        : {n_genau['ungefaehr']}")
    print(f"Ohne Treffer       : {n_total - n_hit}")
    print(f"Distinkte Fehl-Adr.: {len(fehl_freq)}")
    print(f"Geschrieben        : {GEOCODED_FILE.name}, {GEOJSON_FILE.name}, {FEHL_FILE.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())