#!/usr/bin/env python3
"""
Schritt 1: Filterung und Adressnormalisierung.

Eingabe : data/remscheidABNRW1935.csv         (TSV trotz .csv-Endung; Anfuehrungszeichen
                                              gehoeren zum Text, daher QUOTE_NONE)
Ausgabe : output/remscheid1935_geovorbereitung.csv

- Filtert auf EinwVz + GewVz (BehVz, AllgTl, StrVz, Nachtrag ausgeschlossen).
- Extrahiert Generationszusatz `d. J.` / `d. Ä.` aus firstname in neue Spalte `generation`.
- Normalisiert die Adresse fuer die Geokodierung in Spalte `adresse_norm`:
    Doppelhausnummer mit / -> erste Nummer       (78/80 -> 78)
    Range mit -          -> erste Nummer         (2-4   -> 2)
    Eckangabe           -> erste Strasse ohne Hausnummer
    "xxx nicht in Liste xxx ..."  -> Marker entfernen
    Leere Adresse        -> bleibt leer (wird in Schritt 2 uebersprungen)
- Baut Spalte `geoadresse` im Format: "{adresse_norm}, {ortsname}, Deutschland".
"""
import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INPUT_FILE = REPO / "data" / "remscheidABNRW1935.csv"
STRASSEN_MAPPING_FILE = REPO / "data" / "strassen_mapping.csv"
OUTPUT_FILE = REPO / "output" / "remscheid1935_geovorbereitung.csv"

INCLUDED_SECTIONS = ("EinwVz-", "GewVz-")

GEN_PATTERN = re.compile(r"\s*,?\s*(d\.\s*[JÄ]\.)\s*$")
XXX_MARKER = re.compile(r"^xxx\s+nicht\s+in\s+Liste\s+xxx\s+", re.IGNORECASE)
HAUSNR_SLASH = re.compile(r"(\d+[a-zA-Z]?)\s*/\s*\d+[a-zA-Z]?")
HAUSNR_DASH = re.compile(r"(\d+[a-zA-Z]?)\s*-\s*\d+[a-zA-Z]?")
HAUSNR_UND = re.compile(r"(\d+[a-zA-Z]?)\s+u\.\s*\d+[a-zA-Z]?")
ECKE_PATTERN = re.compile(r"\s+Ecke\s+.*$", re.IGNORECASE)


def extract_generation(firstname: str) -> tuple[str, str]:
    """Trennt Generationszusatz vom Vornamen ab. Gibt (vorname_ohne_zusatz, zusatz) zurueck."""
    if not firstname:
        return firstname, ""
    m = GEN_PATTERN.search(firstname)
    if not m:
        return firstname, ""
    gen = m.group(1).replace(" ", "")
    return firstname[: m.start()].rstrip().rstrip(","), gen


def load_strassen_mapping(path: Path) -> list[tuple[re.Pattern, str]]:
    """Laedt das Strassen-Umbenennungs-Mapping (historisch -> heute) aus CSV."""
    if not path.exists():
        return []
    pairs: list[tuple[re.Pattern, str]] = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rgx = row.get("historic_regex", "").strip()
            cur = row.get("current", "").strip()
            if rgx and cur:
                pairs.append((re.compile(rgx), cur))
    return pairs


def normalize_adresse(adresse: str, mapping: list[tuple[re.Pattern, str]]) -> tuple[str, bool]:
    """Wendet Normalisierung + Strassen-Mapping auf die Adresse an.
    Gibt (neue_adresse, mapping_applied) zurueck."""
    if not adresse:
        return "", False
    a = XXX_MARKER.sub("", adresse).strip()
    a = ECKE_PATTERN.sub("", a)
    a = HAUSNR_SLASH.sub(r"\1", a)
    a = HAUSNR_DASH.sub(r"\1", a)
    a = HAUSNR_UND.sub(r"\1", a)
    mapped = False
    for rgx, cur in mapping:
        new = rgx.sub(cur, a, count=1)
        if new != a:
            a = new
            mapped = True
            break
    return a.strip(), mapped


def build_geoadresse(adresse_norm: str, ortsname: str) -> str:
    if not adresse_norm or not ortsname:
        return ""
    return f"{adresse_norm}, {ortsname}, Deutschland"


def main() -> int:
    if not INPUT_FILE.exists():
        print(f"Eingabedatei fehlt: {INPUT_FILE}", file=sys.stderr)
        return 1
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    mapping = load_strassen_mapping(STRASSEN_MAPPING_FILE)
    print(f"Strassen-Mapping geladen: {len(mapping)} Regeln aus {STRASSEN_MAPPING_FILE.name}")

    n_in = 0
    n_out = 0
    n_gen = 0
    n_adr_changed = 0
    n_adr_mapped = 0
    n_adr_empty = 0
    section_counts: dict[str, int] = {}

    with open(INPUT_FILE, encoding="utf-8", newline="") as fin, \
         open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as fout:
        reader = csv.DictReader(fin, delimiter="\t", quoting=csv.QUOTE_NONE, restkey="_extra")
        out_fields = list(reader.fieldnames or []) + ["generation", "adresse_norm", "geoadresse"]
        writer = csv.DictWriter(fout, fieldnames=out_fields)
        writer.writeheader()

        for row in reader:
            n_in += 1
            page = row.get("page", "")
            section = page.split("-")[0] if "-" in page else page
            if not page.startswith(INCLUDED_SECTIONS):
                continue
            section_counts[section] = section_counts.get(section, 0) + 1

            fn = row.get("firstname", "") or ""
            fn_clean, gen = extract_generation(fn)
            if gen:
                n_gen += 1
            row["firstname"] = fn_clean
            row["generation"] = gen

            adr = row.get("Adresse", "") or ""
            adr_norm, was_mapped = normalize_adresse(adr, mapping)
            if adr_norm != adr:
                n_adr_changed += 1
            if was_mapped:
                n_adr_mapped += 1
            if not adr_norm:
                n_adr_empty += 1
            row["adresse_norm"] = adr_norm

            row["geoadresse"] = build_geoadresse(adr_norm, row.get("Ortsname", "") or "")
            row.pop("_extra", None)
            writer.writerow(row)
            n_out += 1

    print(f"Eingabezeilen      : {n_in}")
    print(f"Ausgabezeilen      : {n_out}")
    print(f"Sektionsverteilung : {section_counts}")
    print(f"Generationszusaetze: {n_gen}")
    print(f"Adressen normiert  : {n_adr_changed}")
    print(f"  davon umbenannt  : {n_adr_mapped} (Strassen-Mapping angewandt)")
    print(f"Adressen leer      : {n_adr_empty}")
    print(f"Geschrieben nach   : {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())