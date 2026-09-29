#!/usr/bin/env python3
"""
Schritt 3b: Firmenabgleich — welche Gewerbe-Eintraege gehoeren zu derselben Firma?

Das Gewerbeverzeichnis ist nach Branchen geordnet; eine Firma steht unter jeder
ihrer Branchen erneut, oft mit abweichender Schreibweise. Dieser Schritt ordnet
jedem GewVz-Eintrag eine `firma_id` zu.

Ablauf:
  1. Blocking: verglichen wird nur innerhalb derselben `adresse_norm`
     (nicht per Koordinate — bei Strassentreffern teilen sich viele Adressen eine).
  2. Normalisierung des Namenskopfs (Text vor dem ersten Komma): Kleinschreibung,
     &/u./und vereinheitlicht, Rechtsformen und Satzzeichen entfernt,
     Gebr./Wwe./Sohn/Soehne vereinheitlicht.
  3. Sperren: unterschiedliche Generationszusaetze (d. J./d. Ae.) oder bei
     Personennamen unvertraegliche Vornamen (Artur/Richard; Wilh./Wilhelm ist
     vertraeglich) schliessen eine Zusammenfuehrung aus.
  4. Gleicher normalisierter Name -> automatisch dieselbe Firma.
     Aehnlicher Name (>= SCHWELLE oder nur Abkuerzungen verschieden) -> Vorschlag
     in der Pruefliste. Sonst getrennt.
  5. Pruefliste data/firmen_abgleich.csv: Spalte `entscheidung` (ja | nein) wird
     von Hand gefuellt (z.B. mit tools/pruefliste.py) und bleibt bei jedem Lauf
     erhalten; neue Kandidaten werden ergaenzt.

Eingabe : output/remscheid1935_geocoded.csv, data/firmen_abgleich.csv (falls vorhanden)
Ausgabe : data/firmen_abgleich.csv, output/firmen_zuordnung.csv (id -> firma_id)
"""
import csv
import difflib
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from branchen import extract_erst_branche

REPO = Path(__file__).resolve().parent.parent
INPUT_FILE = REPO / "output" / "remscheid1935_geocoded.csv"
PRUEF_FILE = REPO / "data" / "firmen_abgleich.csv"
ZUORDNUNG_FILE = REPO / "output" / "firmen_zuordnung.csv"

SCHWELLE = 0.85

PRUEF_FIELDS = ["adresse", "name_a", "name_b", "eintraege_a", "eintraege_b",
                "branchen_a", "branchen_b", "aehnlichkeit", "grund",
                "entscheidung", "kommentar", "schluessel_a", "schluessel_b"]

RECHTSFORM = re.compile(
    r"(?<!\w)(?:e\.?\s*g\.?\s*m\.?\s*b\.?\s*h\.?|g\.?\s*m\.?\s*b\.?\s*h\.?|a\.?\s*-?\s*g\.?|"
    r"komm?\.?\s*-?\s*ges\.?|k\.?\s*-?\s*g\.?|o\.?\s*h\.?\s*g\.?|e\.?\s*v\.?|i\.?\s*l\.?|"
    r"(?:und|&)\s*(?:comp|co|cie)\.?|(?:comp|co|cie)\.?)(?!\w)"
)
GENERATION = re.compile(r"(?<!\w)(d\.?\s*[jä]\.?|jun\.?|jr\.?|sen\.?|sr\.?)(?!\w)")
UND = re.compile(r"\s*(?:&|(?<!\w)u\.|(?<!\w)und(?!\w))\s*")
FIRMENMERKMAL = re.compile(
    r"&|(?<!\w)u\.|(?<!\w)und(?!\w)|gmbh|g\. ?m\. ?b\. ?h|(?<!\w)ag(?!\w)|(?<!\w)kg(?!\w)|ges\.|"
    r"gebr|söhne|sohn|werk|fabrik|verein|genossenschaft|gesellschaft|handlung|haus(?!\w)|"
    r"sparkasse|bank|(?<!\w)co\.?(?!\w)|cie", re.IGNORECASE)
ERSETZUNGEN = [(re.compile(r"(?<!\w)gebr\.?(?!\w)"), "gebrueder"),
               (re.compile(r"(?<!\w)gebrüder(?!\w)"), "gebrueder"),
               (re.compile(r"(?<!\w)ww(?:e|we)?\.?(?!\w)"), "witwe"),
               (re.compile(r"(?<!\w)söhne(?!\w)"), "sohn")]


def kopf(row: dict) -> str:
    """Namenskopf eines Eintrags: Firmenname vor dem ersten Komma, sonst Vor- + Nachname."""
    fn = (row.get("Firmenname") or "").strip()
    if fn:
        return fn.split(",")[0].strip()
    return f"{row.get('firstname', '')} {row.get('lastname', '')}".strip()


def generation(name: str) -> str:
    m = GENERATION.search(name.lower())
    if not m:
        return ""
    g = re.sub(r"[^a-zä]", "", m.group(1))
    return {"dj": "j", "jun": "j", "jr": "j", "dä": "ä", "sen": "ä", "sr": "ä"}.get(g, g)


def tokens(name: str) -> list[str]:
    """Normalisierte Namensbestandteile; ein Punkt am Ende markiert eine Abkuerzung."""
    s = unicodedata.normalize("NFC", name).lower()
    s = GENERATION.sub(" ", s)
    s = RECHTSFORM.sub(" ", s)
    for rgx, ersatz in ERSETZUNGEN:
        s = rgx.sub(ersatz, s)
    s = UND.sub(" und ", s)
    s = re.sub(r"(\.)(?=\w)", ". ", s)              # "C.H." -> "C. H."
    s = re.sub(r"[^\wäöüß.\s-]", " ", s).replace("-", " ")
    return [t for t in s.split() if t.strip(".")]


UMSCHRIFT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def schluessel(name: str) -> str:
    """Vergleichsschluessel; Umlaute und ß umschrieben (Kögler = Koegler, Großer = Grosser)."""
    return "".join(t.strip(".") for t in tokens(name)).translate(UMSCHRIFT)


def vertraeglich(a: str, b: str) -> bool:
    """Zwei Namensbestandteile passen zusammen: gleich oder Abkuerzung des anderen."""
    ka, kb = a.strip("."), b.strip(".")
    if ka == kb:
        return True
    if a.endswith(".") and kb.startswith(ka):
        return True
    return b.endswith(".") and ka.startswith(kb)


def ist_person(name: str) -> bool:
    return not FIRMENMERKMAL.search(name) and len(tokens(name)) >= 2


def gesperrt(name_a: str, name_b: str) -> bool:
    """Harte Sperren: verschiedene Generation, oder zwei Personen mit unvertraeglichem Vornamen."""
    ga, gb = generation(name_a), generation(name_b)
    if ga and gb and ga != gb:
        return True
    if ist_person(name_a) and ist_person(name_b):
        ta, tb = tokens(name_a), tokens(name_b)
        if not vertraeglich(ta[0], tb[0]):
            return True
    return False


def nur_abkuerzungen(name_a: str, name_b: str) -> bool:
    ta, tb = tokens(name_a), tokens(name_b)
    return len(ta) == len(tb) and ta != tb and all(vertraeglich(x, y) for x, y in zip(ta, tb))


def bewerte(name_a: str, name_b: str) -> tuple[float, str] | None:
    """Kandidatenpaar fuer die Pruefliste oder None, wenn getrennt bleiben."""
    if gesperrt(name_a, name_b):
        return None
    if nur_abkuerzungen(name_a, name_b):
        return 0.99, "Abkürzung"
    ga, gb = generation(name_a), generation(name_b)
    s = difflib.SequenceMatcher(None, schluessel(name_a), schluessel(name_b)).ratio()
    if s < SCHWELLE:
        return None
    if ga != gb:
        return round(s, 3), "Generationszusatz nur bei einem"
    return round(s, 3), "ähnliche Schreibweise"


class UnionFind:
    def __init__(self):
        self.p: dict = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def lade_entscheidungen(path: Path) -> dict[tuple, dict]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8", newline="") as f:
        return {(r["adresse"], r["schluessel_a"], r["schluessel_b"]): r for r in csv.DictReader(f)}


def main() -> int:
    if not INPUT_FILE.exists():
        print(f"Eingabe fehlt: {INPUT_FILE}", file=sys.stderr)
        return 1
    with open(INPUT_FILE, encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("page", "").startswith("GewVz-")]

    # Gruppen gleichen Schluessels je Adresse (Schritt 1, 2, 4a)
    gruppen: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        adr = r.get("adresse_norm", "") or f"(ohne Adresse #{r['id']})"
        name = kopf(r)
        # gleicher Schluessel, aber verschiedene Generation -> eigene Gruppe
        gruppen[(adr, schluessel(name) + "|" + generation(name))].append(r)

    uf = UnionFind()
    for key in gruppen:
        uf.find(key)

    bestand = lade_entscheidungen(PRUEF_FILE)
    je_adresse: dict[str, list[tuple]] = defaultdict(list)
    for key in gruppen:
        je_adresse[key[0]].append(key)

    def anzeige(key):
        return Counter(kopf(r) for r in gruppen[key]).most_common(1)[0][0]

    def branchen(key):
        return " | ".join(sorted({extract_erst_branche(r.get("Firmenname", "")) or "–" for r in gruppen[key]}))

    # Kandidaten (Schritt 3, 4b) und Entscheidungen (Schritt 5)
    pruef: dict[tuple, dict] = {}
    for adr, keys in je_adresse.items():
        keys.sort(key=lambda k: k[1])
        for i, ka in enumerate(keys):
            for kb in keys[i + 1:]:
                na, nb = anzeige(ka), anzeige(kb)
                bew = bewerte(na, nb)
                if not bew:
                    continue
                pk = (adr, ka[1], kb[1])
                alt = bestand.get(pk, {})
                pruef[pk] = {
                    "adresse": adr, "name_a": na, "name_b": nb,
                    "eintraege_a": len(gruppen[ka]), "eintraege_b": len(gruppen[kb]),
                    "branchen_a": branchen(ka), "branchen_b": branchen(kb),
                    "aehnlichkeit": f"{bew[0]:.3f}", "grund": bew[1],
                    "entscheidung": alt.get("entscheidung", ""), "kommentar": alt.get("kommentar", ""),
                    "schluessel_a": ka[1], "schluessel_b": kb[1],
                }
    # Entscheidungen zu Paaren, die es nicht mehr gibt, nicht verwerfen
    for pk, alt in bestand.items():
        if pk not in pruef and alt.get("entscheidung"):
            pruef[pk] = alt

    n_ja = n_nein = n_offen = 0
    for (adr, sa, sb), p in pruef.items():
        e = (p.get("entscheidung") or "").strip().lower()
        if e == "ja":
            n_ja += 1
            if (adr, sa) in gruppen and (adr, sb) in gruppen:
                uf.union((adr, sa), (adr, sb))
        elif e == "nein":
            n_nein += 1
        else:
            n_offen += 1

    PRUEF_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PRUEF_FILE, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PRUEF_FIELDS)
        w.writeheader()
        for p in sorted(pruef.values(), key=lambda p: (-float(p["aehnlichkeit"]), p["adresse"], p["name_a"])):
            w.writerow({k: p.get(k, "") for k in PRUEF_FIELDS})

    # firma_id = kleinste Eintrags-id der Firma (stabil ueber Laeufe)
    mitglieder: dict[tuple, list[dict]] = defaultdict(list)
    for key, rs in gruppen.items():
        mitglieder[uf.find(key)].extend(rs)
    ZUORDNUNG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ZUORDNUNG_FILE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "firma_id", "adresse_norm", "name"])
        for rs in mitglieder.values():
            fid = min(rs, key=lambda r: int(r["id"]))["id"]
            for r in rs:
                w.writerow([r["id"], fid, r.get("adresse_norm", ""), kopf(r)])

    n_auto = sum(len(rs) - 1 for rs in gruppen.values())
    print(f"GewVz-Eintraege             : {len(rows)}")
    print(f"Automatisch zusammengefuehrt: {n_auto} Eintraege (gleicher Name, gleiche Adresse)")
    print(f"Pruefliste                  : {len(pruef)} Paare (ja {n_ja}, nein {n_nein}, offen {n_offen})")
    print(f"Firmen nach Abgleich        : {len(mitglieder)}")
    print(f"Geschrieben                 : {PRUEF_FILE.relative_to(REPO)}, {ZUORDNUNG_FILE.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
