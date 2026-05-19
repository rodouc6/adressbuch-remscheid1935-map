#!/usr/bin/env python3
"""
Schritt 5: LLM-Klassifikation der heuristisch ungematchten Branchen.

Schickt jeden Eintrag aus data/branchen_mapping.csv mit review_needed=1 an
Mistral Small via KIconnect-NRW-Endpunkt. Das LLM ordnet ihn einer der 17
vorgegebenen Oberkategorien zu und schlaegt eine Unterbranche und einen
2-stelligen WZ-2008-Code vor.

Eingaben:
  data/branchen_mapping.csv  (review_needed=1 wird verarbeitet)
  .env mit KICONNECT_API_KEY

Ausgaben:
  output/llm_branchen_cache.json   Resume-faehiger Cache (pro erst_branche)
  data/branchen_mapping.csv        in-place aktualisiert; neue Spalten
                                   `quelle` (= heuristik | llm), `begruendung`

Aufruf:
  python3 src/05_llm_branchen_klassifikation.py [--limit N]
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
MAPPING_FILE = REPO / "data" / "branchen_mapping.csv"
CACHE_FILE = REPO / "output" / "llm_branchen_cache.json"
ENV_FILE = REPO / ".env"

API_URL = "https://chat.kiconnect.nrw/api/v1/chat/completions"
MODEL_ID = "inferenz-mistral-small-4-119b"
REQUEST_TIMEOUT = 60

OBERKATEGORIEN = [
    "Werkzeugindustrie",
    "Metall- und Eisenverarbeitung",
    "Maschinenbau",
    "Elektrotechnik",
    "Bandwirkerei und Textil",
    "Bekleidung und Schuhe",
    "Bau und Holz",
    "Lebensmittel und Genuss",
    "Gastgewerbe",
    "Handel und Vertretung",
    "Verkehr und Brennstoffe",
    "Landwirtschaft und Gartenbau",
    "Druckerei und Medien",
    "Persönliche Dienste",
    "Gesundheit",
    "Sonstige Dienste",
    "Sonstige / nicht klassifiziert",
]

WZ_2008_GROB = {
    "Werkzeugindustrie":            "25",
    "Metall- und Eisenverarbeitung":"25",
    "Maschinenbau":                 "28",
    "Elektrotechnik":               "27",
    "Bandwirkerei und Textil":      "13",
    "Bekleidung und Schuhe":        "14",
    "Bau und Holz":                 "41",
    "Lebensmittel und Genuss":      "10",
    "Gastgewerbe":                  "56",
    "Handel und Vertretung":        "47",
    "Verkehr und Brennstoffe":      "49",
    "Landwirtschaft und Gartenbau": "01",
    "Druckerei und Medien":         "18",
    "Persönliche Dienste":          "96",
    "Gesundheit":                   "86",
    "Sonstige Dienste":             "82",
    "Sonstige / nicht klassifiziert":"",
}

SYSTEM_PROMPT = """Du klassifizierst historische deutsche Gewerbe- und Berufsbezeichnungen aus einem Adressbuch von 1935 (Remscheid).

Aufgabe: Ordne die uebergebene Branchenbezeichnung genau einer Oberkategorie aus folgender Liste zu:

- Werkzeugindustrie (Werkzeugfabriken, Saegen, Feilen, Zangen, Bohrer, Hammer, Schneidwaren, Schleiferei usw.)
- Metall- und Eisenverarbeitung (Schlosserei, Schmiede, Klempnerei, Gravieranstalt, Eisenhandlung, Giesserei)
- Maschinenbau (Maschinen- und Apparatefabriken, Mechaniker, Hebezeuge)
- Elektrotechnik (elektrische Anlagen, Radio, Rundfunk)
- Bandwirkerei und Textil (Bandwirkerei, Weberei, Spinnerei, Tuch-/Manufakturhandel)
- Bekleidung und Schuhe (Kleidermacher, Schneider, Schuhmacherei, Hut, Pelz, Waesche)
- Bau und Holz (Bauunternehmung, Anstreicher, Schreinerei, Glaserei, Maurer, Holzhandel, Verpackung)
- Lebensmittel und Genuss (Baeckerei, Konditorei, Metzgerei, Molkerei, Obst, Kolonialwaren, Getraenke)
- Gastgewerbe (Gast-/Schankwirtschaft, Kaffeewirtschaft, Hotel, Pension)
- Handel und Vertretung (Handelsvertreter, Export/Import, Tabak, Buch, Drogerie, Moebel, Bank, Versicherung, Beratung)
- Verkehr und Brennstoffe (Fuhrgeschaeft, Kohlen, Spedition, KFZ, Tankstelle, Omnibus, Gueterverkehr)
- Landwirtschaft und Gartenbau (Bauer, Landwirt, Gaertnerei, Samenhandlung, Viehhandel)
- Druckerei und Medien (Buchdruckerei, Steindruckerei, Verlag, Buchbinderei, Fotografie)
- Persoenliche Dienste (Friseur, Musiker, Sattlerei, Uhrmacher, Waescherei, Bestattung, Fahrschule)
- Gesundheit (Arzt, Zahnarzt, Hebamme, Apotheke nur wenn Heilkunde, Sanatorium)
- Sonstige Dienste (sehr spezielle Dienstleister, z.B. Bruecken-/Waegeanstalten)
- Sonstige / nicht klassifiziert (nur wenn wirklich keine der obigen passt)

Antworte ausschliesslich als gueltiges JSON-Objekt in folgendem Schema:
{"oberkategorie": "...", "unterbranche": "...", "begruendung": "..."}

- `oberkategorie` MUSS exakt einer der oben genannten Begriffe sein (Schreibweise identisch).
- `unterbranche` ist eine kurze, sinngebende Bezeichnung (max. 6 Worte), z.B. "Werkzeugfabrik (generisch)", "Bestattungsinstitut".
- `begruendung` ist ein knapper Satz, der die Zuordnung kurz erklaert.
"""


def load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("\"'")
    return env


def load_cache(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(path: Path, cache: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def classify(branche: str, api_key: str, session: requests.Session) -> dict:
    """Schickt eine Branchenbezeichnung an das LLM und gibt die geparsten Felder zurueck."""
    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": branche},
        ],
        "temperature": 0.0,
        "max_tokens": 200,
        "response_format": {"type": "json_object"},
    }
    try:
        r = session.post(API_URL, json=payload,
                         headers={"Authorization": f"Bearer {api_key}"},
                         timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
        content = r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return {"error": f"Request failed: {e}"}

    # JSON-Antwort parsen - Mistral umschliesst gelegentlich mit Code-Fences
    cleaned = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.MULTILINE).strip()
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: greife die erste plausible JSON-Klammer
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not m:
            return {"error": f"Antwort nicht parsbar: {content[:200]}"}
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            return {"error": f"Antwort nicht parsbar: {e}"}

    ok = obj.get("oberkategorie", "").strip()
    # Klammer-Beschreibung wegschneiden, falls das LLM die Hilfetext-Klammer mitliefert:
    # "Werkzeugindustrie (Werkzeugfabriken, ...)" -> "Werkzeugindustrie"
    if "(" in ok:
        ok = ok.split("(", 1)[0].strip()
    # Umlaut-/Sonderzeichen-tolerante Validierung
    def _normalize(s: str) -> str:
        return (s.lower()
                .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
                .replace("ß", "ss"))
    match = next((cat for cat in OBERKATEGORIEN if _normalize(cat) == _normalize(ok)), None)
    if not match:
        return {"error": f"Ungueltige Oberkategorie: {ok!r}", "raw": obj}
    ok = match  # auf kanonische Schreibweise normalisieren
    return {
        "oberkategorie": ok,
        "unterbranche": obj.get("unterbranche", "").strip(),
        "begruendung": obj.get("begruendung", "").strip(),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None,
                   help="Nur N ungematchte Eintraege verarbeiten (zum Testen)")
    args = p.parse_args()

    env = load_env(ENV_FILE)
    api_key = env.get("KICONNECT_API_KEY") or os.environ.get("KICONNECT_API_KEY")
    if not api_key:
        print(f"KICONNECT_API_KEY weder in {ENV_FILE} noch in Umgebung gefunden.", file=sys.stderr)
        return 1

    # 1. Mapping einlesen — Heuristik-Klassifikation als Audit-Spalte konservieren
    with open(MAPPING_FILE, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if "heuristik_oberkategorie" not in r or not r.get("heuristik_oberkategorie"):
            r["heuristik_oberkategorie"] = r.get("oberkategorie", "")
            r["heuristik_unterbranche"] = r.get("unterbranche", "")
        r.setdefault("quelle", "")
        r.setdefault("begruendung", "")

    todo = rows  # alle Branchen, nicht nur ungematchte
    print(f"Mapping geladen: {len(rows)} Branchen — alle werden per LLM verifiziert")

    cache = load_cache(CACHE_FILE)
    print(f"Cache-Eintraege: {len(cache)}")

    if args.limit:
        todo = todo[: args.limit]
        print(f"Limit aktiv: {len(todo)} Eintraege werden bearbeitet")

    pending = [r for r in todo if r["erst_branche"] not in cache]
    print(f"Noch abzufragen: {len(pending)}")

    session = requests.Session()
    n_hit = 0
    n_err = 0
    t0 = time.time()
    try:
        for i, r in enumerate(pending, 1):
            res = classify(r["erst_branche"], api_key, session)
            cache[r["erst_branche"]] = res
            if "error" in res:
                n_err += 1
            else:
                n_hit += 1
            if i % 20 == 0 or i == len(pending):
                rate = i / max(time.time() - t0, 0.001)
                save_cache(CACHE_FILE, cache)
                print(f"  [{i:4d}/{len(pending)}]  Treffer {n_hit}  Fehler {n_err}  ({rate:.1f}/s)")
    finally:
        save_cache(CACHE_FILE, cache)

    # 2. Ergebnisse zurueck ins Mapping schreiben - LLM ueberschreibt Heuristik
    n_filled = 0
    n_disagree = 0
    n_fallback = 0
    for r in rows:
        res = cache.get(r["erst_branche"])
        if not res or "error" in res:
            if r["heuristik_oberkategorie"] and r["heuristik_oberkategorie"] != "Sonstige / nicht klassifiziert":
                r["quelle"] = "heuristik"
                n_fallback += 1
            else:
                r["quelle"] = ""
            continue
        old_ok = r["heuristik_oberkategorie"]
        new_ok = res["oberkategorie"]
        r["unterbranche"] = res["unterbranche"]
        r["oberkategorie"] = new_ok
        r["wz_2008"] = WZ_2008_GROB.get(new_ok, "")
        r["review_needed"] = "0" if new_ok != "Sonstige / nicht klassifiziert" else "1"
        r["quelle"] = "llm"
        r["begruendung"] = res["begruendung"]
        if old_ok and old_ok != new_ok and old_ok != "Sonstige / nicht klassifiziert":
            n_disagree += 1
        n_filled += 1

    out_fields = ["erst_branche", "frequency", "unterbranche", "oberkategorie",
                  "wz_2008", "wz_1933", "review_needed", "quelle",
                  "heuristik_oberkategorie", "heuristik_unterbranche",
                  "begruendung", "kommentar"]
    with open(MAPPING_FILE, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in out_fields})

    print()
    print(f"Mapping aktualisiert: {n_filled} Branchen per LLM klassifiziert")
    print(f"  davon Disagreement mit Heuristik: {n_disagree}")
    print(f"  Heuristik-Fallback (LLM-Fehler):  {n_fallback}")
    print(f"Datei: {MAPPING_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())