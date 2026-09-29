"""
Tests fuer die Pipeline-Logik, die ohne Nominatim und ohne LLM laeuft.

Aufruf:  python3 -m unittest discover tests
"""
import contextlib
import csv
import importlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from branchen import MAPPING_FIELDS, extract_erst_branche  # noqa: E402

vorbereitung = importlib.import_module("01_vorbereitung")
join = importlib.import_module("03_join_geojson")
klassifikation = importlib.import_module("04_branchen_klassifikation")
werkzeug = importlib.import_module("07_werkzeug_konsolidierung")


def still(fn):
    """Fuehrt fn ohne Konsolenausgabe aus."""
    with contextlib.redirect_stdout(io.StringIO()):
        return fn()


class ErstBrancheTest(unittest.TestCase):
    def test_erste_branche_nach_firmenname(self):
        self.assertEqual(extract_erst_branche("Arnz & Co., Feilenfabrik, Stahlhandel"), "Feilenfabrik")

    def test_rechtsform_wird_uebersprungen(self):
        self.assertEqual(extract_erst_branche("Mannesmann, G.m.b.H., Werkzeugfabrik"), "Werkzeugfabrik")
        self.assertEqual(extract_erst_branche("Voß, Kom.-Ges., Sägenfabrik"), "Sägenfabrik")

    def test_unvollstaendige_branche_wird_zusammengefuegt(self):
        self.assertEqual(
            extract_erst_branche("Müller, Weiß-, Bunt- u. Wollwarengeschäft, Kurzwaren"),
            "Weiß-, Bunt- u. Wollwarengeschäft",
        )

    def test_ohne_komma_keine_branche(self):
        self.assertEqual(extract_erst_branche("Theodor Arnz"), "")
        self.assertEqual(extract_erst_branche(""), "")


class VorbereitungTest(unittest.TestCase):
    MAPPING = [(__import__("re").compile(r"^Adolf Hitler-Straße"), "Alleestraße")]

    def test_hausnummern_werden_vereinfacht(self):
        for roh, erwartet in [
            ("Hauptstraße 78/80", "Hauptstraße 78"),
            ("Hauptstraße 2-4", "Hauptstraße 2"),
            ("Engelbertstraße 5 u. 6", "Engelbertstraße 5"),
            ("Bismarckstraße Ecke Weststraße", "Bismarckstraße"),
            ("xxx nicht in Liste xxx Weststraße 12", "Weststraße 12"),
        ]:
            self.assertEqual(vorbereitung.normalize_adresse(roh, [])[0], erwartet, roh)

    def test_strassen_mapping(self):
        self.assertEqual(vorbereitung.normalize_adresse("Adolf Hitler-Straße 43", self.MAPPING),
                         ("Alleestraße 43", True))

    def test_generationszusatz(self):
        self.assertEqual(vorbereitung.extract_generation("Karl, d. J."), ("Karl", "d.J."))
        self.assertEqual(vorbereitung.extract_generation("Karl"), ("Karl", ""))


class GenauigkeitTest(unittest.TestCase):
    def test_hausnummer_im_treffer(self):
        self.assertEqual(join.genauigkeit("24, Alexanderstraße, Remscheid, 42853, Deutschland", "building"), "haus")
        self.assertEqual(join.genauigkeit("Aldi, 38-40, Kölner Straße, 42897, Deutschland", "shop"), "haus")
        self.assertEqual(join.genauigkeit("Kirchner, 2;2a;4, Rosenhügeler Straße, 42859", "amenity"), "haus")

    def test_postleitzahl_ist_keine_hausnummer(self):
        self.assertEqual(join.genauigkeit("Salemstraße, Alt-Remscheid, 42853, Deutschland", "highway"), "strasse")
        self.assertEqual(join.genauigkeit("Haddenbach, Rath, Remscheid, 42855, Deutschland", "place"), "ungefaehr")


class MappingZusammenfuehrenTest(unittest.TestCase):
    """Schritt 4 darf LLM-Ergebnisse und Handkorrekturen nicht verwerfen."""

    def test_bestand_bleibt_erhalten(self):
        d = Path(tempfile.mkdtemp())
        klassifikation.INPUT_FILE = d / "geocoded.csv"
        klassifikation.OUTPUT_FILE = d / "mapping.csv"
        with open(klassifikation.INPUT_FILE, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["page", "Firmenname"])
            w.writerows([["GewVz-1", "A, Feilenfabrik"], ["GewVz-1", "B, Feilenfabrik"],
                         ["GewVz-2", "C, Bäckerei"], ["EinwVz-1", "D, Metzgerei"]])
        with open(klassifikation.OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, MAPPING_FIELDS)
            w.writeheader()
            w.writerow({"erst_branche": "Feilenfabrik", "frequency": 9, "oberkategorie": "LLM-Wert",
                        "quelle": "llm", "begruendung": "b", "kommentar": "k"})
            w.writerow({"erst_branche": "Weggefallen", "frequency": 3, "quelle": "manuell"})

        still(klassifikation.main)
        with open(klassifikation.OUTPUT_FILE, encoding="utf-8", newline="") as f:
            rows = {r["erst_branche"]: r for r in csv.DictReader(f)}

        feile = rows["Feilenfabrik"]
        self.assertEqual((feile["frequency"], feile["oberkategorie"], feile["begruendung"], feile["kommentar"]),
                         ("2", "LLM-Wert", "b", "k"))
        self.assertEqual(feile["heuristik_oberkategorie"], "Werkzeugindustrie")
        self.assertEqual((rows["Bäckerei"]["quelle"], rows["Bäckerei"]["oberkategorie"]),
                         ("heuristik", "Lebensmittel und Genuss"))
        self.assertEqual((rows["Weggefallen"]["frequency"], rows["Weggefallen"]["quelle"]), ("0", "manuell"))
        self.assertNotIn("Metzgerei", rows)  # EinwVz zaehlt nicht


class WerkzeugKonsolidierungTest(unittest.TestCase):
    @staticmethod
    def feature(fid, firma, ub, lon=7.19, lat=51.18, ok="Werkzeugindustrie"):
        return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"id": fid, "firmenname": firma, "oberkategorie": ok, "unterbranche": ub}}

    def test_konsolidierung_und_wiederholbarkeit(self):
        d = Path(tempfile.mkdtemp())
        werkzeug.REPO = d
        werkzeug.GEOJSON_FILE = d / "gewerbe.geojson"
        werkzeug.AUDIT_FILE = d / "audit.csv"
        feats = [
            self.feature("1", "Erlenkötter & Voß, Werkzeugfabrik", "Werkzeugfabrik (generisch)"),
            self.feature("2", "Erlenkötter & Voß, Schraubstockfabrik", "Schraubstockfabrik"),
            self.feature("3", "Müller, Feilenfabrik", "Feilenfabrik"),
            self.feature("4", "Bäcker Klein, Bäckerei", "Bäckerei", ok="Lebensmittel und Genuss"),
        ]
        werkzeug.GEOJSON_FILE.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))

        still(werkzeug.main)
        erster_lauf = werkzeug.GEOJSON_FILE.read_text()
        props = {f["properties"]["id"]: f["properties"] for f in json.loads(erster_lauf)["features"]}

        anker = [p for p in props.values() if p.get("is_pikto_anchor")]
        self.assertEqual(len(anker), 1)  # zwei Firmen am selben Punkt -> ein Symbol
        self.assertEqual(anker[0]["werkzeug_count"], 2)
        self.assertEqual(props["2"]["werkzeug_symbol"], "schraubstock")  # spezifisch vor generisch
        self.assertNotIn("werkzeug_symbol", props["4"])

        still(werkzeug.main)
        self.assertEqual(werkzeug.GEOJSON_FILE.read_text(), erster_lauf)


if __name__ == "__main__":
    unittest.main()
