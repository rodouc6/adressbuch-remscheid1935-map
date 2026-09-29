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

## Herkunft einzelner Angaben

- Koordinaten: geokodiert über Nominatim, © OpenStreetMap-Mitwirkende. Nach der
  [Geocoding Guideline der OSMF](https://osmfoundation.org/wiki/Licence/Community_Guidelines/Geocoding_-_Guideline)
  lösen einzelne Geokodierungsergebnisse keine Share-alike-Pflicht nach der ODbL aus.
- Branchenvorschläge des Sprachmodells (Spalten `unterbranche`, `oberkategorie`,
  `begruendung`): erzeugt mit Mistral Small über KI:connect.nrw.
- Grundkarte der Website: © OpenFreeMap, © OpenMapTiles, Daten ©
  OpenStreetMap-Mitwirkende; sie wird zur Laufzeit geladen und ist nicht Teil
  des Repositorys.
