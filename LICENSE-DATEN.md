# Lizenzen der Daten

**Daten: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.de)**

Die Quelldaten stehen unter CC BY-SA 4.0. Alles, was dieses Projekt daraus
erzeugt, ist eine Bearbeitung und steht deshalb unter derselben Lizenz. Das
gilt für alle Dateien in `data/` (außer `data/piktogramme/`) und `docs/data/`.

## Quelldaten

| | |
|---|---|
| Datei | `data/remscheidABNRW1935.csv`, unverändert |
| Rechteinhaber | Verein für Computergenealogie e.V. (CompGen) |
| Datensatz | *Historische Adressbücher aus dem Rheinland und Ruhrgebiet* (25 Adressbücher, 1856–1957), bereitgestellt für den Kultur-Hackathon Coding da Vinci Nieder.Rhein.Land (11.09.–06.11.2021) |
| Nachweis | [Datensatzseite (Internet Archive, 06.09.2021)](https://web.archive.org/web/20210906074729/https://codingdavinci.de/daten/historische-adressbuecher-aus-dem-rheinland-und-ruhrgebiet), [Download](https://download.codingdavinci.de/s/c8zc6Bn4dZMzyFS) |
| Lizenz | CC BY-SA 4.0 |
| Vorlage | Einwohner- und Geschäfts-Handbuch für Groß-Remscheid: Remscheid – Lennep – Lüttringhausen, Remscheid: Ziegler 1935 |

**Namensnennung für Weiterverwendungen:** Daten: Verein für Computergenealogie
e.V., CC BY-SA 4.0; Aufbereitung: Christos Rodouniklis, CC BY-SA 4.0.

## Eigene Bearbeitung

Christos Rodouniklis, Bergische Universität Wuppertal: Auswahl und
Normalisierung der Adressen, Straßenzuordnung (`data/strassen_mapping.csv`),
Koordinaten und Genauigkeitsstufen, Branchenzuordnung
(`data/branchen_mapping.csv`), Werkzeug-Zuordnung
(`data/werkzeug_konsolidierung.csv`) und die Kartendaten in `docs/data/`.

## Bildnachweise: Werkzeug-Piktogramme

Die Piktogramme in `data/piktogramme/` (Web-Fassung: `docs/icons/werkzeug/`)
stammen von [Flaticon](https://www.flaticon.com) und stehen unter der
[Flaticon-Lizenz](https://www.flaticon.com/legal) (kostenlos mit
Namensnennung), **nicht** unter CC BY-SA. Die Namensnennung auf der Website
steht in der Quellenzeile der Karte. Die Zuordnung ist per Bildabgleich
geprüft: Die Umrisse aller zehn Dateien sind mit den Flaticon-Vorlagen
deckungsgleich.

| Piktogramm | Web-Datei | Flaticon-Icon | Autor |
|---|---|---|---|
| Beitel | `beitel.png` | [Beitel, 2085451](https://www.flaticon.com/de/kostenloses-icon/beitel_2085451) | [Magnific](https://www.flaticon.com/authors/magnific) |
| Feile | `feile.png` | [Raspel, 8836998](https://www.flaticon.com/free-icon/rasp_8836998) | [Magnific](https://www.flaticon.com/authors/magnific) |
| Hammer | `hammer.png` | [Hammer, 8661121](https://www.flaticon.com/de/kostenloses-icon/hammer_8661121) | Icon Mela |
| Schleifstein | `schleifstein.png` | [Schärfen, 16508300](https://www.flaticon.com/de/kostenloses-icon/scharfen_16508300) | ronindesign |
| Schraubstock | `schraubstock.png` | [Schraubstock, 252804](https://www.flaticon.com/de/kostenloses-icon/schraubstock_252804) | [Smashicons](https://www.flaticon.com/authors/smashicons) |
| Spiralbohrer | `bohrer.png` | [Bohrer, 12479160](https://www.flaticon.com/de/kostenloses-icon/bohrer_12479160) | [juicy_fish](https://www.flaticon.com/authors/juicy-fish) |
| Stern | `spezial.png` | [Stern, 118669](https://www.flaticon.com/free-icon/star_118669) | Revicon |
| Säge | `saege.png` | [Säge, 385637](https://www.flaticon.com/de/kostenloses-icon/sage_385637) | [Magnific](https://www.flaticon.com/authors/magnific) |
| Zange | `zange.png` | [Zange, 8043292](https://www.flaticon.com/de/kostenloses-icon/zange_8043292) | Mayor Icons |
| gekreuzte Werkzeuge | `werkzeug_generisch.png` | [Werkzeug, 7414126](https://www.flaticon.com/de/kostenloses-icon/werkzeug_7414126) | Uniconlabs |

## Herkunft einzelner Angaben

- Koordinaten: geokodiert über Nominatim, © OpenStreetMap-Mitwirkende. Nach der
  [Geocoding Guideline der OSMF](https://osmfoundation.org/wiki/Licence/Community_Guidelines/Geocoding_-_Guideline)
  lösen einzelne Geokodierungsergebnisse keine Share-alike-Pflicht nach der ODbL aus.
- Branchenvorschläge des Sprachmodells (Spalten `unterbranche`, `oberkategorie`,
  `begruendung`): erzeugt mit Mistral Small über KI:connect.nrw.
- Grundkarte der Website: © OpenFreeMap, © OpenMapTiles, Daten ©
  OpenStreetMap-Mitwirkende; sie wird zur Laufzeit geladen und ist nicht Teil
  des Repositorys.
