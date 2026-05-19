#!/usr/bin/env python3
"""
Schritt 2: Batch-Geokodierung der distinkten geoadressen gegen lokales Nominatim.

Ablauf:
  1. Distinkte geoadressen aus output/remscheid1935_geovorbereitung.csv extrahieren.
  2. Bereits gecachte Eintraege ueberspringen.
  3. Verbleibende Adressen gegen NOMINATIM_URL abfragen, Cache inkrementell schreiben.
  4. Resume-faehig: Skript kann jederzeit abgebrochen und neu gestartet werden.

Eingabe : output/remscheid1935_geovorbereitung.csv
Ausgaben: output/unique_geoadressen.csv
          output/geocoding_cache.csv  (geoadresse, lat, lon, display_name, osm_type, match_class)
"""
import csv
import sys
import time
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
INPUT_FILE = REPO / "output" / "remscheid1935_geovorbereitung.csv"
UNIQUE_FILE = REPO / "output" / "unique_geoadressen.csv"
CACHE_FILE = REPO / "output" / "geocoding_cache.csv"

NOMINATIM_URL = "http://localhost:8080/search"
REQUEST_TIMEOUT = 10
SLEEP_BETWEEN = 0.0          # 0 bei lokalem Server; bei oeffentlicher API hoeher setzen
PROGRESS_EVERY = 200

CACHE_FIELDS = ["geoadresse", "lat", "lon", "display_name", "osm_type", "match_class"]


def build_unique(input_path: Path, unique_path: Path) -> list[str]:
    """Schreibt distinkte geoadressen mit Frequenz; gibt Liste der Adressen zurueck."""
    freq: dict[str, int] = {}
    with open(input_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            g = row.get("geoadresse", "")
            if not g:
                continue
            freq[g] = freq.get(g, 0) + 1
    items = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
    with open(unique_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["geoadresse", "frequency"])
        for g, n in items:
            w.writerow([g, n])
    return [g for g, _ in items]


def load_cache(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    cache: dict[str, dict] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cache[row["geoadresse"]] = row
    return cache


def open_cache_writer(path: Path, existed: bool):
    f = open(path, "a", encoding="utf-8", newline="")
    w = csv.DictWriter(f, fieldnames=CACHE_FIELDS)
    if not existed:
        w.writeheader()
        f.flush()
    return f, w


def geocode(adresse: str, session: requests.Session) -> dict:
    """Fragt Nominatim ab und gibt ein cache-Row-Dict zurueck (Treffer oder leeres Ergebnis)."""
    base = {"geoadresse": adresse, "lat": "", "lon": "",
            "display_name": "", "osm_type": "", "match_class": ""}
    try:
        r = session.get(NOMINATIM_URL, params={
            "q": adresse,
            "format": "json",
            "limit": 1,
            "countrycodes": "de",
            "addressdetails": 0,
        }, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            return base
        hits = r.json()
        if not hits:
            return base
        h = hits[0]
        base["lat"] = h.get("lat", "")
        base["lon"] = h.get("lon", "")
        base["display_name"] = h.get("display_name", "")
        base["osm_type"] = h.get("osm_type", "")
        base["match_class"] = h.get("class", "")
        return base
    except Exception as e:
        print(f"  Fehler bei {adresse!r}: {e}", file=sys.stderr)
        return base


def main() -> int:
    if not INPUT_FILE.exists():
        print(f"Eingabedatei fehlt: {INPUT_FILE}", file=sys.stderr)
        return 1
    UNIQUE_FILE.parent.mkdir(parents=True, exist_ok=True)

    print("Sammle distinkte geoadressen ...")
    addresses = build_unique(INPUT_FILE, UNIQUE_FILE)
    print(f"  {len(addresses)} distinkte geoadressen geschrieben nach {UNIQUE_FILE.name}")

    cache_existed = CACHE_FILE.exists()
    cache = load_cache(CACHE_FILE)
    print(f"  Cache-Eintraege bisher: {len(cache)}")

    todo = [a for a in addresses if a not in cache]
    print(f"  Noch abzufragen      : {len(todo)}")
    if not todo:
        print("Nichts zu tun. Cache vollstaendig.")
        return 0

    f_cache, w_cache = open_cache_writer(CACHE_FILE, cache_existed)
    session = requests.Session()
    n_hit = 0
    t0 = time.time()
    try:
        for i, adr in enumerate(todo, 1):
            res = geocode(adr, session)
            w_cache.writerow(res)
            f_cache.flush()
            if res["lat"]:
                n_hit += 1
            if SLEEP_BETWEEN:
                time.sleep(SLEEP_BETWEEN)
            if i % PROGRESS_EVERY == 0 or i == len(todo):
                rate = i / max(time.time() - t0, 0.001)
                print(f"  [{i:5d}/{len(todo)}]  Treffer bisher: {n_hit}  ({rate:.1f}/s)")
    finally:
        f_cache.close()

    print(f"Fertig. Treffer in diesem Lauf: {n_hit}/{len(todo)}")
    print(f"Cache: {CACHE_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())