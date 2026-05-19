#!/usr/bin/env python3
"""
Schritt 7: Werkzeug-Konsolidierung in zwei Stufen.

STUFE A — Firmen-Konsolidierung:
  Mehrere Listings derselben Firma (gleicher Firmenname-Kopf an gleicher
  Koordinate) werden zu EINEM logischen Eintrag zusammengefasst. Beispiel:
  'Erlenkötter & Voß, Werkzeugfabrik' + 'Erlenkötter & Voß, Schraubstockfabrik'
  + 'Erlenkötter & Voß, Automobilwerkzeug' + 'Erlenkötter & Voß, Gaswerkzeuge'
  -> 1 Eintrag mit 4 hinterlegten Branchen.

STUFE B — Standort-Aggregation:
  Wenn nach Stufe A immer noch mehrere (jetzt verschiedene) Firmen an derselben
  Koordinate stehen, wird genau einer als Anker fuer das Karten-Symbol gewaehlt;
  alle anderen werden zu Mitgliedern dieses Anker-Eintrags. Klick auf den Anker
  oeffnet die Cluster-Liste.

Symbol-Wahl-Logik (innerhalb einer Firma):
  Priorisierung: spezifische Werkzeug-Symbole > werkzeug_generisch > spezial
  So bekommt Erlenkötter & Voß das 'schraubstock'-Symbol, nicht das generische
  'Werkzeugfabrik'-Symbol.

Eingabe : web/data/gewerbe.geojson
Ausgabe : web/data/gewerbe.geojson (ueberschreibt)
          data/werkzeug_konsolidierung.csv
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GEOJSON_FILE = REPO / "docs" / "data" / "gewerbe.geojson"
AUDIT_FILE = REPO / "data" / "werkzeug_konsolidierung.csv"
WERKZEUG_KAT = "Werkzeugindustrie"

REGELN: list[tuple[re.Pattern, str]] = [
    (re.compile(r"schleif|polier"),              "schleifstein"),
    (re.compile(r"beitel|hobel"),                "beitel"),
    (re.compile(r"säge|saege"),                  "saege"),
    (re.compile(r"feile|raspel"),                "feile"),
    (re.compile(r"bohrer|spiralbohrer"),         "bohrer"),
    (re.compile(r"\bzange|zangen"),              "zange"),
    (re.compile(r"hammer|hämmer"),               "hammer"),
    (re.compile(r"schraub"),                     "schraubstock"),
    (re.compile(r"werkzeugfabrik \(generisch\)|werkzeugindustrie \(generisch\)|werkzeug- und maschinenfabrik|werkzeug- und metallwarenfabrik"),
                                                 "werkzeug_generisch"),
]

# Symbol-Prioritaet: niedrigster Wert = wird zuerst gewaehlt
SYMBOL_PRIO = {
    "saege": 1, "feile": 1, "bohrer": 1, "zange": 1, "hammer": 1,
    "schleifstein": 1, "beitel": 1, "schraubstock": 1,
    "werkzeug_generisch": 2,
    "spezial": 3,
}


def piktogramm(ub: str) -> str:
    norm = (ub or "").lower()
    for rgx, key in REGELN:
        if rgx.search(norm):
            return key
    return "spezial"


def coord_key(coords):
    return (round(coords[0], 6), round(coords[1], 6))


def firma_kopf(firmenname: str) -> str:
    """Normalisierter Firmenname-Kopf: alles vor dem ersten Komma, lowercase, getrimmt."""
    if not firmenname:
        return ""
    return firmenname.split(",", 1)[0].strip().lower()


def pick_symbol(symbols: list[str]) -> str:
    """Wahl nach Prioritaet, bei Gleichstand das haeufigste."""
    if not symbols:
        return "spezial"
    cnt = Counter(symbols)
    # Sortiere nach (Prioritaet, -Frequenz)
    return min(cnt.keys(), key=lambda s: (SYMBOL_PRIO.get(s, 99), -cnt[s]))


def main() -> int:
    if not GEOJSON_FILE.exists():
        print(f"Fehlt: {GEOJSON_FILE}", file=sys.stderr); return 1
    g = json.loads(GEOJSON_FILE.read_text(encoding="utf-8"))

    # Properties saeubern + werkzeug_symbol auf Werkzeug-Features setzen
    werk_feats: list[dict] = []
    audit_sym: Counter[tuple[str, str]] = Counter()
    sym_total: Counter[str] = Counter()
    for feat in g["features"]:
        p = feat["properties"]
        if p.get("oberkategorie") != WERKZEUG_KAT:
            for k in ("werkzeug_symbol", "is_pikto_anchor", "werkzeug_count",
                     "werkzeug_mitglieder", "werkzeug_branchen"):
                p.pop(k, None)
            continue
        sym = piktogramm(p.get("unterbranche", "") or "")
        p["werkzeug_symbol"] = sym
        audit_sym[(sym, p.get("unterbranche", "") or "")] += 1
        sym_total[sym] += 1
        werk_feats.append(feat)

    n_total = len(werk_feats)

    # --- Stufe A: Firmen-Konsolidierung ----------------------------------
    firma_groups: dict[tuple, list[dict]] = defaultdict(list)
    for feat in werk_feats:
        key = (coord_key(feat["geometry"]["coordinates"]),
               firma_kopf(feat["properties"].get("firmenname", "") or ""))
        firma_groups[key].append(feat)

    # Pro Firma einen "Firmen-Anker" markieren und Branchenliste hinterlegen
    firmen_anker: list[dict] = []
    n_consolidated = 0
    for key, members in firma_groups.items():
        # Symbol fuer die Firma waehlen (priorisiert)
        symbols = [m["properties"]["werkzeug_symbol"] for m in members]
        firma_sym = pick_symbol(symbols)
        # Erstes Mitglied mit diesem Symbol = Firmen-Anker
        anchor = next(m for m in members if m["properties"]["werkzeug_symbol"] == firma_sym)
        for m in members:
            m["properties"]["is_pikto_anchor"] = False
        anchor["properties"]["is_pikto_anchor"] = True
        anchor["properties"]["werkzeug_symbol"] = firma_sym
        # Branchenliste der Firma (alle Unterbranchen)
        anchor["properties"]["werkzeug_branchen"] = [
            m["properties"].get("unterbranche", "") or "" for m in members
        ]
        firmen_anker.append(anchor)
        if len(members) > 1:
            n_consolidated += 1

    # --- Stufe B: Standort-Aggregation ---------------------------------
    # Gruppiere Firmen-Anker nach Koordinate (Firmen mit gleicher Adresse)
    coord_groups: dict[tuple, list[dict]] = defaultdict(list)
    for anchor in firmen_anker:
        coord_groups[coord_key(anchor["geometry"]["coordinates"])].append(anchor)

    n_visible_anchors = 0
    n_multi_firm_locations = 0
    for coord, firmen in coord_groups.items():
        if len(firmen) == 1:
            firmen[0]["properties"]["werkzeug_count"] = 1
            n_visible_anchors += 1
            continue
        # Mehrere Firmen am Ort -> einen Primaer-Anker
        n_multi_firm_locations += 1
        symbols = [f["properties"]["werkzeug_symbol"] for f in firmen]
        primary_sym = pick_symbol(symbols)
        primary = next(f for f in firmen if f["properties"]["werkzeug_symbol"] == primary_sym)
        # Mitgliederliste fuer Cluster-Popup (jede Firma einmal, mit allen ihren Branchen)
        mit_liste = [
            {
                "id": f["properties"].get("id", ""),
                "firmenname": f["properties"].get("firmenname", ""),
                "branchen": f["properties"].get("werkzeug_branchen", []),
                "symbol": f["properties"].get("werkzeug_symbol", ""),
            }
            for f in firmen
        ]
        for f in firmen:
            f["properties"]["is_pikto_anchor"] = False
        primary["properties"]["is_pikto_anchor"] = True
        primary["properties"]["werkzeug_count"] = len(firmen)
        primary["properties"]["werkzeug_mitglieder"] = mit_liste
        n_visible_anchors += 1

    # ------- Schreiben + Audit ------------------------------------------
    GEOJSON_FILE.write_text(json.dumps(g, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_FILE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "unterbranche_llm", "frequency"])
        for (sym, ub), n in sorted(audit_sym.items(), key=lambda x: (-sym_total[x[0][0]], -x[1])):
            w.writerow([sym, ub, n])

    print(f"Werkzeug-Features gesamt          : {n_total}")
    print(f"Firmen-Anker (Stufe A)            : {len(firmen_anker)}  (Konsolidierung: {n_total - len(firmen_anker)} Listings gemerged)")
    print(f"Sichtbare Symbol-Anker (Stufe B)  : {n_visible_anchors}")
    print(f"  davon Multi-Firmen-Standorte    : {n_multi_firm_locations}")
    print()
    print(f"Geschrieben: {GEOJSON_FILE.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())