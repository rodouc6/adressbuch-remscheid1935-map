#!/usr/bin/env python3
"""
Schritt 4 (Vorbereitung): Heuristische Branchenklassifikation.

Liest die geokodierten Gewerbeeintraege (GewVz), extrahiert die Erst-Branche
aus Firmenname (nach erstem Komma, Rechtsform-Tokens werden uebersprungen)
und schlaegt per Keyword-Heuristik eine 3-Ebenen-Klassifikation vor:

    Erst-Branche (Original-Freitext)
       -> Unterbranche
          -> Oberkategorie
             -> WZ 2008 (gefuellt)
                WZ 1933 (leer, manuell zu ergaenzen)

Eingabe : output/remscheid1935_geocoded.csv (nur GewVz beruecksichtigt)
Ausgabe : data/branchen_mapping.csv (Review-CSV, sortiert nach Frequenz)

`review_needed = 1`  -> keine Regel hat gegriffen, Sichtung empfohlen
`review_needed = 0`  -> Regel hat gegriffen, Vorschlag pruefen
"""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INPUT_FILE = REPO / "output" / "remscheid1935_geocoded.csv"
OUTPUT_FILE = REPO / "data" / "branchen_mapping.csv"

# Rechtsform-Tokens, die als Erst-Branche uebersprungen werden
RECHTSFORM = re.compile(
    r"^(?:G\.?\s*m\.?\s*b\.?\s*H\.?|A\.?-?G\.?|Kom\.?-?Ges\.?|K\.?G\.?|OHG|o\.\s*H\.?|e\.\s*G\.|e\.\s*V\.|i\.\s*L\.|"
    r"Inh\.?|Inhaber|Geschäftsführer|G\.F\.|Komm\.?-?Ges\.?)$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Klassifikationsregeln
# Reihenfolge ist relevant: spezifischere Keywords zuerst.
# Jede Regel: (regex, unterbranche, oberkategorie, wz_2008)
# Matching gegen normalisierte (lowercase) Erst-Branche.
# Substring-Match ohne harte Wortgrenzen, weil in deutschen Komposita die
# Keywords haeufig nicht als Standalone-Woerter auftreten (Zangenfabrik).
# ---------------------------------------------------------------------------

REGELN: list[tuple[re.Pattern, str, str, str]] = [
    # ---- Werkzeugindustrie ---------------------------------------------
    (re.compile(r"säge|saege"),                          "Sägenfabrik",                  "Werkzeugindustrie",            "25.73"),
    (re.compile(r"feilen|raspel"),                       "Feilen- und Raspelfabrik",     "Werkzeugindustrie",            "25.73"),
    (re.compile(r"zange"),                               "Zangenfabrik",                 "Werkzeugindustrie",            "25.73"),
    (re.compile(r"bohrer"),                              "Bohrerfabrik",                 "Werkzeugindustrie",            "25.73"),
    (re.compile(r"gaswerkzeug|schweiß|schweiss"),        "Gaswerkzeuge / Schweißbedarf", "Werkzeugindustrie",            "25.73"),
    (re.compile(r"hammer(?!stein)|hämmer"),              "Hammerfabrik / Hammerwerk",    "Werkzeugindustrie",            "25.73"),
    (re.compile(r"schraubstock"),                        "Schraubstockfabrik",           "Werkzeugindustrie",            "25.73"),
    (re.compile(r"schere|messer|sense"),                 "Schneidwaren",                 "Werkzeugindustrie",            "25.71"),
    (re.compile(r"beitel|hobeleisen|stemmeisen"),        "Beitel- und Hobeleisenfabrik", "Werkzeugindustrie",            "25.73"),
    (re.compile(r"heftemach|hefte u\."),                 "Heftemacherei",                "Werkzeugindustrie",            "25.73"),
    (re.compile(r"schleif"),                             "Schleiferei",                  "Werkzeugindustrie",            "25.62"),
    (re.compile(r"werkzeugfabrik|werkzeug- u\. instr"),  "Werkzeugfabrik (generisch)",   "Werkzeugindustrie",            "25.73"),
    (re.compile(r"^werkzeuge?\b|werkzeughand|werkzeug-handlung"), "Werkzeuge (Sortiment/Handel)", "Werkzeugindustrie",    "46.74"),
    # ---- Metall- und Eisenverarbeitung ---------------------------------
    (re.compile(r"schloss(?:erei|er)?"),                 "Schlosserei",                  "Metall- und Eisenverarbeitung","25.62"),
    (re.compile(r"klempner|installateur|sanitär|zentralheizung"), "Klempnerei / Installation","Metall- und Eisenverarbeitung","43.22"),
    (re.compile(r"schmied"),                             "Schmiede",                     "Metall- und Eisenverarbeitung","25.50"),
    (re.compile(r"gravier|graveur"),                     "Gravieranstalt",               "Metall- und Eisenverarbeitung","25.61"),
    (re.compile(r"bedachung|dachdecker"),                "Bedachungsgeschäft",           "Metall- und Eisenverarbeitung","43.91"),
    (re.compile(r"eisenhandlung|eisenwaren|eisengießerei|eisengie"),"Eisenhandlung / -gießerei","Metall- und Eisenverarbeitung","47.52"),
    (re.compile(r"metallwaren|stahlwaren|stahlbau|stahllager|stahlhandlung"),"Metall- und Stahlwaren","Metall- und Eisenverarbeitung","25.99"),
    (re.compile(r"drahtzieh|drahtwaren"),                "Drahtwaren",                   "Metall- und Eisenverarbeitung","24.34"),
    (re.compile(r"gießerei|giesserei|gußstahl"),         "Gießerei",                     "Metall- und Eisenverarbeitung","24.51"),
    # ---- Elektrotechnik (neu) ------------------------------------------
    (re.compile(r"elektr|stromzähler"),                  "Elektrotechnik",               "Elektrotechnik",               "27.90"),
    (re.compile(r"radio|rundfunk"),                      "Radio / Rundfunk",             "Elektrotechnik",               "47.43"),
    # ---- Druckerei / Medien (neu) -------------------------------------
    (re.compile(r"druckerei|steindruck|buchdruck|setzerei"), "Druckerei",                "Druckerei und Medien",         "18.12"),
    (re.compile(r"verlag|zeitung|redaktion"),            "Verlag / Zeitung",             "Druckerei und Medien",         "58"),
    (re.compile(r"buchbinder"),                          "Buchbinderei",                 "Druckerei und Medien",         "18.14"),
    (re.compile(r"photograph|fotograph|lichtbild"),      "Fotografie",                   "Druckerei und Medien",         "74.20"),
    # ---- Bandwirkerei & Textil ----------------------------------------
    (re.compile(r"bandwirk|bandweber|bandfabrik|bändchen"),"Bandwirkerei",               "Bandwirkerei und Textil",      "13.20"),
    (re.compile(r"weberei|spinnerei|färberei|faerberei|stricker|wirkerei"),"Textilproduktion","Bandwirkerei und Textil",  "13"),
    (re.compile(r"manufaktur|tuchhandlung|tuchgeschäft|stoffe|wollwaren|weißwaren|buntwaren"),"Manufaktur-/Tuchhandlung","Bandwirkerei und Textil","47.51"),
    # ---- Bekleidung & Schuhe ------------------------------------------
    (re.compile(r"kleidermach|näher(?:in|ei)|schneider(?:ei|in)?|konfektion|weißnäher"),"Kleidermacher/-in/Konfektion","Bekleidung und Schuhe","14.13"),
    (re.compile(r"hut[- ]|hutfabrik|hutmach|mütz|kürschner|pelz"),"Hut-/Mütz-/Pelzgeschäft","Bekleidung und Schuhe",       "14.19"),
    (re.compile(r"schuh|stiefel"),                       "Schuhmacherei/-handel",        "Bekleidung und Schuhe",        "15.20"),
    (re.compile(r"damen[- ]u(?:nd|.) herren|damengeschäft|damenputz|herrengeschäft|herren[- ]u(?:nd|.) damen"),"Bekleidungsgeschäft","Bekleidung und Schuhe","47.71"),
    (re.compile(r"wäsche|krawatten|hemden"),             "Wäsche / Krawatten",           "Bekleidung und Schuhe",        "47.71"),
    # ---- Bau & Holz ---------------------------------------------------
    (re.compile(r"bauunternehm|baugesch|hochbau|tiefbau|fuhr- u\. bauges"), "Bauunternehmung", "Bau und Holz",             "41.20"),
    (re.compile(r"anstreich|maler"),                     "Anstreicher-/Malergeschäft",   "Bau und Holz",                 "43.34"),
    (re.compile(r"schreiner|tischler|drechslerei|drechsler"),"Schreinerei / Drechslerei","Bau und Holz",                 "16.23"),
    (re.compile(r"glaser"),                              "Glaserei",                     "Bau und Holz",                 "43.34"),
    (re.compile(r"zimmer(?:er|mann|ei)"),                "Zimmerei",                     "Bau und Holz",                 "43.91"),
    (re.compile(r"steinmetz|steinbruch|steinhauer"),     "Steinmetzerei",                "Bau und Holz",                 "23.70"),
    (re.compile(r"holzhandlung|holzlager|holzverarb|sägewerk"),"Holzhandel / Sägewerk",  "Bau und Holz",                 "16.10"),
    # ---- Lebensmittel & Genuss ----------------------------------------
    (re.compile(r"bäckerei|brot"),                       "Bäckerei",                     "Lebensmittel und Genuss",      "10.71"),
    (re.compile(r"konditorei"),                          "Konditorei",                   "Lebensmittel und Genuss",      "10.71"),
    (re.compile(r"metzger|fleischer"),                   "Metzgerei",                    "Lebensmittel und Genuss",      "10.13"),
    (re.compile(r"molkerei|milchhandlung|milcherzeug|butter"),"Molkerei/Milch/Butter",   "Lebensmittel und Genuss",      "47.29"),
    (re.compile(r"kolonial|feinkost|lebensmittel|kraemer|krämer|spezerei|viktualien"),"Kolonialwaren/Feinkost","Lebensmittel und Genuss","47.11"),
    (re.compile(r"obst|gemüse|südfrüchte|kartoffel"),    "Obst-, Gemüse- und Kartoffelhandel","Lebensmittel und Genuss", "47.21"),
    (re.compile(r"fisch"),                               "Fischhandlung",                "Lebensmittel und Genuss",      "47.23"),
    (re.compile(r"mehl|getreide"),                       "Mehl- und Getreidehandel",     "Lebensmittel und Genuss",      "47.29"),
    (re.compile(r"kaffeehand|teehand"),                  "Kaffee-/Teehandlung",          "Lebensmittel und Genuss",      "47.29"),
    (re.compile(r"brauerei|brennerei|spirituosen|wein|likör|bier-?groß|getränke"),"Getränke/Wein/Bier","Lebensmittel und Genuss","11"),
    (re.compile(r"zucker|bonbon|süß|honig"),             "Süßwaren / Honig",             "Lebensmittel und Genuss",      "10.82"),
    # ---- Gastgewerbe ---------------------------------------------------
    (re.compile(r"gastwirt|gasthaus|gastwirtsch|schankwirt|gast- u\. schank"),"Gast- und Schankwirtschaft","Gastgewerbe","56.10"),
    (re.compile(r"kaffeewirt|café|cafe[ -]|caféh"),      "Kaffeewirtschaft/Café",        "Gastgewerbe",                  "56.30"),
    (re.compile(r"hotel|pension|fremdenheim|ledigenheim"),"Hotel/Pension",               "Gastgewerbe",                  "55.10"),
    # ---- Handel & Vertretung ------------------------------------------
    (re.compile(r"handelsvertret|vertretung|vertreter"), "Handelsvertretung",            "Handel und Vertretung",        "46.19"),
    (re.compile(r"export|import|außenhandel|auslandsges"),"Außenhandel",                 "Handel und Vertretung",        "46.90"),
    (re.compile(r"zigarren|tabak|rauchwaren|zigarette"), "Tabakhandlung",                "Handel und Vertretung",        "47.26"),
    (re.compile(r"buchhandlung|^buch-|papier|schreibwaren|musikalien|kunsthandlung"),"Buch-/Papier-/Kunsthandlung","Handel und Vertretung","47.61"),
    (re.compile(r"drogen|drogerie|apotheke|parfüm"),     "Drogerie/Apotheke",            "Handel und Vertretung",        "47.73"),
    (re.compile(r"möbel|moebel"),                        "Möbelhandlung",                "Handel und Vertretung",        "47.59"),
    (re.compile(r"galanterie|kurzwaren|gemischtwaren|kramwaren"),"Gemischt-/Kurzwaren",  "Handel und Vertretung",        "47.19"),
    (re.compile(r"haushaltungsgegen|haushaltswaren|porzellan|geschirr"),"Haushaltswaren","Handel und Vertretung",        "47.59"),
    (re.compile(r"blumenhandlung|blumengeschäft"),       "Blumenhandlung",               "Handel und Vertretung",        "47.76"),
    (re.compile(r"schrott|altmetall|alteisen|lumpen"),   "Schrott-/Altwarenhandel",      "Handel und Vertretung",        "46.77"),
    (re.compile(r"farbenhandlung|farben- u\."),          "Farbenhandlung",               "Handel und Vertretung",        "47.52"),
    (re.compile(r"warenhaus|kaufhaus"),                  "Warenhaus / Kaufhaus",         "Handel und Vertretung",        "47.19"),
    # ---- Verkehr & Brennstoffe ----------------------------------------
    (re.compile(r"fuhr(?:geschäft|unternehm|werk)"),     "Fuhrgeschäft",                 "Verkehr und Brennstoffe",      "49.41"),
    (re.compile(r"kohlen|koks|brennholz|brennstoff"),    "Brennstoffhandel",             "Verkehr und Brennstoffe",      "47.78"),
    (re.compile(r"spedition|umzug|transport"),           "Spedition",                    "Verkehr und Brennstoffe",      "52.29"),
    (re.compile(r"droschke|taxi|kraftdroschke|personenbeförd"),"Personenbeförderung",    "Verkehr und Brennstoffe",      "49.32"),
    (re.compile(r"kraftfahrzeug|automobil|kfz|auto-reparatur|autohand"),"Kraftfahrzeuge","Verkehr und Brennstoffe",      "45"),
    (re.compile(r"fahrrad|zweirad"),                     "Fahrrad / Zweirad",            "Verkehr und Brennstoffe",      "47.64"),
    # ---- Landwirtschaft & Gartenbau -----------------------------------
    (re.compile(r"bauer|landwirt"),                      "Landwirtschaft",               "Landwirtschaft und Gartenbau", "01.50"),
    (re.compile(r"gärtner|landschaftsgärt"),             "Gärtnerei",                    "Landwirtschaft und Gartenbau", "01.30"),
    # ---- Maschinenbau (neu) -------------------------------------------
    (re.compile(r"maschinen[- ]?u(?:nd|.)|apparate?fabrik|maschinenfabrik|maschinenbau|mechaniker"), "Maschinen- und Apparatefabrik", "Maschinenbau", "28"),
    # ---- Gesundheit (neu) ---------------------------------------------
    (re.compile(r"praktische(?:r)? ärzt|^arzt|^ärzte"),  "Praktische Ärzte",             "Gesundheit",                   "86.21"),
    (re.compile(r"zahnarzt|dentist"),                    "Zahnarzt / Dentist",           "Gesundheit",                   "86.23"),
    (re.compile(r"tierarzt|veterinär"),                  "Tierarzt",                     "Gesundheit",                   "75"),
    (re.compile(r"hebamme"),                             "Hebamme",                      "Gesundheit",                   "86.90"),
    (re.compile(r"krankenhaus|sanatorium|heilanstalt|kuranstalt"),"Krankenhaus / Sanatorium","Gesundheit",               "86.10"),
    # ---- Erweiterungen Verkehr ----------------------------------------
    (re.compile(r"tankstelle|mineralöl|benzin|kraftstoff"),"Tankstelle / Mineralöl",     "Verkehr und Brennstoffe",      "47.30"),
    (re.compile(r"omnibus|lastkraft|kraftverkehr|kraftwagenbetrieb"),"Omnibus-/Lastkraftverkehr","Verkehr und Brennstoffe","49"),
    (re.compile(r"autovermiet|wagenvermiet"),            "Autovermietung",               "Verkehr und Brennstoffe",      "77.11"),
    # ---- Erweiterungen Bau und Holz -----------------------------------
    (re.compile(r"zimmergeschäft|zimmerhandlung"),       "Zimmerei",                     "Bau und Holz",                 "43.91"),
    (re.compile(r"holzwaren"),                           "Holzwarenfabrik",              "Bau und Holz",                 "16.29"),
    (re.compile(r"^eisen-?$|^eisen\b"),                  "Eisenhandlung",                "Metall- und Eisenverarbeitung","47.52"),
    (re.compile(r"heißmangel|büglerei|bügelei"),         "Bügelei / Heißmangel",         "Persönliche Dienste",          "96.01"),
    (re.compile(r"dekorationsgeschäft|schaufenster"),    "Dekoration",                   "Persönliche Dienste",          "74.10"),
    # ---- Persönliche Dienste ------------------------------------------
    (re.compile(r"friseur|frisör|barbier"),              "Friseur",                      "Persönliche Dienste",          "96.02"),
    (re.compile(r"musiker|kapelle|tanzlehrer|tanzlokal|musiklehrer|musikschule"),"Musiker/Unterhaltung","Persönliche Dienste","90.03"),
    (re.compile(r"sattler|tapezierer|polster"),          "Sattlerei/Polsterei",          "Persönliche Dienste",          "13.92"),
    (re.compile(r"uhrmacher|optiker|juwelier|gold- u\."),"Uhr-/Juwelier-/Goldschmiede",  "Persönliche Dienste",          "47.77"),
    (re.compile(r"wäscherei|reinigung|plätterei"),       "Wäscherei/Reinigung",          "Persönliche Dienste",          "96.01"),
    # ---- Dienstleistung / Finanz / Beratung (unter Handel und Vertretung) ----
    (re.compile(r"bank|sparkasse|kreditanstalt|wechselstube"),"Bank / Sparkasse",        "Handel und Vertretung",        "64.19"),
    (re.compile(r"versicherung"),                        "Versicherung",                 "Handel und Vertretung",        "65"),
    (re.compile(r"treuhand|bücherrevisor|steuerberat|rechtsanw|notar"),"Beratung / Recht","Handel und Vertretung",       "69"),
    # ---- Nachgereicht (haeufige Restposten) ---------------------------
    (re.compile(r"mineralwasser|selterswasser|limonad|sprudel"),"Mineralwasser-/Limonadenfabrik","Lebensmittel und Genuss","11.07"),
    (re.compile(r"flaschenbier|bierverlag|bier-? ?verkauf"),"Bier-/Getränkehandel",       "Lebensmittel und Genuss",      "47.25"),
    (re.compile(r"industriebedarf|industriewaren"),      "Industriebedarf",              "Handel und Vertretung",        "46.69"),
    (re.compile(r"güterfernverkehr|güterverkehr|frachtfuhr"),"Güterverkehr",             "Verkehr und Brennstoffe",      "49.41"),
    (re.compile(r"präzisions[- ]?maschin|maschinenwerkzeug"),"Präzisionswerkzeuge",      "Werkzeugindustrie",            "25.73"),
    (re.compile(r"stahllager|eisenlager"),               "Stahl-/Eisenlager",            "Metall- und Eisenverarbeitung","46.72"),
    (re.compile(r"faßbinder|fassbinder|kistenfabrik|verpackung|kartonage"),"Verpackung / Fassbinderei","Bau und Holz","16.24"),
    (re.compile(r"herd-? |ofen-? |wasch[- ]?maschin|wringmaschin|haushaltsmaschin"),"Haushaltsmaschinen","Handel und Vertretung","47.54"),
    (re.compile(r"beerdigung|bestattung|sarg|leichen"),  "Bestattungsinstitut",          "Persönliche Dienste",          "96.03"),
    (re.compile(r"maurer"),                              "Maurer",                       "Bau und Holz",                 "41.20"),
    (re.compile(r"fahrschule|kraftfahrschule"),          "Fahrschule",                   "Persönliche Dienste",          "85.53"),
    (re.compile(r"baumaterial|bauartikel|baubedarf|baubüro|bauausführung"),"Baumaterialhandel / Baubüro","Bau und Holz","47.52"),
    (re.compile(r"gummiwaren|stempelfabrik|gummi-? u\."),"Gummi- und Stempelwaren",      "Metall- und Eisenverarbeitung","22.19"),
    (re.compile(r"fuhrg?schäft|fuhrgesch"),              "Fuhrgeschäft",                 "Verkehr und Brennstoffe",      "49.41"),
    (re.compile(r"charnier|scharnier|beschläge"),        "Scharniere und Beschläge",     "Werkzeugindustrie",            "25.72"),
    (re.compile(r"brückenwaag|waaganstalt|wäageanstalt"),"Brückenwaage / Wägeanstalt",   "Sonstige Dienste",             "82.99"),
    (re.compile(r"spielwaren|spielzeug"),                "Spielwaren",                   "Handel und Vertretung",        "47.65"),
    (re.compile(r"^export$|^import$"),                   "Außenhandel",                  "Handel und Vertretung",        "46.90"),
    (re.compile(r"winde[- ]|hebezeug|seilzug"),          "Winden / Hebezeuge",           "Maschinenbau",                 "28.22"),
    (re.compile(r"praktischer? arzt|praktischer?\s*ärzt"),"Praktische Ärzte",             "Gesundheit",                   "86.21"),
    (re.compile(r"waschanstalt"),                        "Wäscherei/Reinigung",          "Persönliche Dienste",          "96.01"),
    (re.compile(r"samenhandlung|saatgut"),               "Samen- und Saatguthandel",     "Landwirtschaft und Gartenbau", "47.76"),
    (re.compile(r"viehhand|viehhandlung"),               "Viehhandel",                   "Landwirtschaft und Gartenbau", "46.23"),
    (re.compile(r"tapeten|linoleum|bodenbelag"),         "Tapeten / Bodenbeläge",        "Bau und Holz",                 "47.53"),
    (re.compile(r"büroeinrichtung|büromaschin|büroartikel|büroberdarf"),"Büromaschinen / Büroartikel","Handel und Vertretung","46.65"),
    (re.compile(r"mode[- ]|putzwaren|tapisserie"),       "Mode-/Putzwarengeschäft",      "Bekleidung und Schuhe",        "47.71"),
    (re.compile(r"rohprodukten|altmaterial|alteisen"),   "Rohprodukten-/Altmaterialhandel","Handel und Vertretung",      "46.77"),
    (re.compile(r"abladeunternehm|abladen"),             "Abladeunternehmung",           "Verkehr und Brennstoffe",      "52.24"),
    (re.compile(r"hufbeschlag|wagenbau"),                "Wagenbau / Hufbeschlag",       "Verkehr und Brennstoffe",      "30.99"),
]


_INCOMPLETE = re.compile(r"(?:[-‐]|\bu\.|\bund)\s*$")


def extract_erst_branche(firmenname: str) -> str:
    """Extrahiert die Erst-Branche aus Firmenname.

    - Komma-Split, anschliessend Rechtsform-Tokens (G.m.b.H., Kom.-Ges. etc.) ueberspringen.
    - Wenn ein Token mit '-', ' u.' oder ' und' endet, ist es ein Praefix einer
      zusammengesetzten Branche (z.B. 'Weiß-' aus 'Weiß-, Bunt- u. Wollwarengeschäft').
      Solche Tokens werden mit den naechsten Tokens (per ', ' verbunden) zusammengefuegt,
      bis ein vollstaendiges Ende erreicht ist.
    """
    if not firmenname or "," not in firmenname:
        return ""
    parts = [p.strip() for p in firmenname.split(",")]
    # parts[0] = Firmenname-Kopf, parts[1:] = Branchen + ggf. Rechtsformen
    buf = ""
    for p in parts[1:]:
        if not p or RECHTSFORM.match(p):
            continue
        buf = p if not buf else f"{buf}, {p}"
        if _INCOMPLETE.search(buf):
            continue
        return buf
    return buf  # Edge-Case: Letztes Token war unvollstaendig - trotzdem zurueckgeben


def klassifiziere(branche: str) -> tuple[str, str, str, int]:
    norm = branche.lower()
    for rgx, ub, ok, wz in REGELN:
        if rgx.search(norm):
            return ub, ok, wz, 0
    return "", "Sonstige / nicht klassifiziert", "", 1


def main() -> int:
    if not INPUT_FILE.exists():
        print(f"Eingabe fehlt: {INPUT_FILE}", file=sys.stderr)
        return 1

    counter: Counter[str] = Counter()
    with open(INPUT_FILE, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if not row.get("page", "").startswith("GewVz-"):
                continue
            branche = extract_erst_branche(row.get("Firmenname", "") or "")
            if branche:
                counter[branche] += 1

    print(f"Distinkte Erst-Branchen: {len(counter)}")
    print(f"Gesamtzeilen mit extrahierter Branche: {sum(counter.values())}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["erst_branche", "frequency", "unterbranche", "oberkategorie",
                    "wz_2008", "wz_1933", "review_needed", "kommentar"])
        klass_counter: Counter[str] = Counter()
        match_counter: Counter[str] = Counter()
        for b, freq in counter.most_common():
            ub, ok, wz, rev = klassifiziere(b)
            klass_counter[ok] += freq
            match_counter["ungematcht" if rev else "gematcht"] += freq
            w.writerow([b, freq, ub, ok, wz, "", rev, ""])

    print()
    print(f"Geschrieben: {OUTPUT_FILE}")
    print()
    print("Match-Status (gewichtet nach Frequenz):")
    total = sum(match_counter.values())
    for k, v in match_counter.most_common():
        print(f"  {k:12s} {v:6d}  ({100*v/total:.1f} %)")
    print()
    print("Oberkategorien (gewichtet nach Frequenz):")
    for k, v in sorted(klass_counter.items(), key=lambda x: -x[1]):
        print(f"  {v:6d}  ({100*v/total:5.1f} %)  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())