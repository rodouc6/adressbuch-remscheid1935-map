#!/usr/bin/env python3
"""
Schritt 6: GeoJSON-Export der Gewerbe-Einträge fuer die Webkarte.

- Liest output/remscheid1935_geocoded.csv und filtert auf GewVz mit Koordinaten.
- Extrahiert die Erst-Branche aus Firmenname (identisch zu Schritt 4).
- Joint per Erst-Branche mit data/branchen_mapping.csv -> oberkategorie + unterbranche.
- Erzeugt:
    web/data/gewerbe.geojson   minimaler Punktdatensatz
    web/data/branchen.json     Filterhierarchie Oberkategorie -> Unterbranchen mit Frequenz

Output ist bewusst schlank: nur die Properties, die fuer Anzeige, Suche und
Filter wirklich benoetigt werden.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from branchen import extract_erst_branche

REPO = Path(__file__).resolve().parent.parent
GEOCODED_FILE = REPO / "output" / "remscheid1935_geocoded.csv"
MAPPING_FILE = REPO / "data" / "branchen_mapping.csv"
WEB_DIR = REPO / "docs" / "data"
GEOJSON_FILE = WEB_DIR / "gewerbe.geojson"
BRANCHEN_FILE = WEB_DIR / "branchen.json"


def main() -> int:
    if not GEOCODED_FILE.exists():
        print(f"Fehlt: {GEOCODED_FILE}", file=sys.stderr); return 1
    if not MAPPING_FILE.exists():
        print(f"Fehlt: {MAPPING_FILE}", file=sys.stderr); return 1

    # Mapping einlesen
    mapping: dict[str, dict] = {}
    with open(MAPPING_FILE, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            mapping[row["erst_branche"]] = {
                "oberkategorie": row["oberkategorie"] or "Sonstige / nicht klassifiziert",
                "unterbranche": row["unterbranche"] or "",
            }

    WEB_DIR.mkdir(parents=True, exist_ok=True)
    features = []
    branchen_index: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    n_in = 0
    n_geo = 0
    n_no_branche = 0

    with open(GEOCODED_FILE, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if not row.get("page", "").startswith("GewVz-"):
                continue
            n_in += 1
            lat, lon = row.get("lat", ""), row.get("lon", "")
            if not lat or not lon:
                continue
            n_geo += 1

            firmenname = row.get("Firmenname", "") or ""
            branche = extract_erst_branche(firmenname)
            klass = mapping.get(branche, {"oberkategorie": "Sonstige / nicht klassifiziert", "unterbranche": ""})
            if not branche:
                n_no_branche += 1

            ok = klass["oberkategorie"]
            ub = klass["unterbranche"]
            branchen_index[ok][ub or "(ohne Unterbranche)"] += 1

            props = {
                "id": row.get("id", ""),
                "firmenname": firmenname,
                "lastname": row.get("lastname", ""),
                "firstname": row.get("firstname", ""),
                "adresse": row.get("Adresse", ""),
                "ortsname": row.get("Ortsname", ""),
                "oberkategorie": ok,
                "unterbranche": ub,
                "genauigkeit": row.get("genauigkeit", ""),
            }
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                "properties": props,
            })

    geojson = {"type": "FeatureCollection", "features": features}
    GEOJSON_FILE.write_text(json.dumps(geojson, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    branchen = {
        ok: {
            "frequency": sum(ubs.values()),
            "unterbranchen": dict(sorted(ubs.items(), key=lambda x: -x[1])),
        }
        for ok, ubs in sorted(branchen_index.items(), key=lambda x: -sum(x[1].values()))
    }
    BRANCHEN_FILE.write_text(json.dumps(branchen, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"GewVz-Eintraege gesamt    : {n_in}")
    print(f"Davon mit Koordinaten     : {n_geo}")
    print(f"Davon ohne Erst-Branche   : {n_no_branche}")
    print(f"Distinkte Oberkategorien  : {len(branchen)}")
    print(f"Features in GeoJSON       : {len(features)}")
    print(f"Geschrieben               : {GEOJSON_FILE.relative_to(REPO)}")
    print(f"                            {BRANCHEN_FILE.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())