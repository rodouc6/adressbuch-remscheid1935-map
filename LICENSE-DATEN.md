# Lizenzen der Daten

**Eigene Daten und Aufbereitung: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.de)**,
Christos Rodouniklis, Bergische Universität Wuppertal.

Darunter fallen die Koordinaten und ihre Genauigkeitsstufen, die
Straßenzuordnung (`data/strassen_mapping.csv`), die Branchenzuordnung
(`data/branchen_mapping.csv`), die Werkzeug-Zuordnung
(`data/werkzeug_konsolidierung.csv`) und die daraus erzeugten Kartendaten in
`docs/data/`, jeweils mit den unten genannten Ausnahmen.

## Ausnahmen

| Bestand | Rechte |
|---|---|
| `data/remscheidABNRW1935.csv` sowie die daraus übernommenen Einträge (Namen, Adressen, Firmen- und Berufsangaben) in `docs/data/gewerbe.geojson` | Erfassung des Adressbuchs Remscheid 1935 durch den Verein für Computergenealogie e.V. (CompGen). **Nicht** unter CC BY; es gelten die Nutzungsbedingungen von CompGen. |
| `data/piktogramme/`, `docs/icons/werkzeug/` | *Herkunft und Lizenz noch zu ergänzen.* |

## Herkunft einzelner Angaben

- Koordinaten: geokodiert über Nominatim, © OpenStreetMap-Mitwirkende. Nach der
  [Geocoding Guideline der OSMF](https://osmfoundation.org/wiki/Licence/Community_Guidelines/Geocoding_-_Guideline)
  lösen einzelne Geokodierungsergebnisse keine Share-alike-Pflicht aus.
- Branchenvorschläge des Sprachmodells (Spalten `unterbranche`, `oberkategorie`,
  `begruendung`): erzeugt mit Mistral Small über KI:connect.nrw und in dieses
  Projekt übernommen.
- Grundkarte der Website: © OpenFreeMap, © OpenMapTiles, Daten ©
  OpenStreetMap-Mitwirkende; sie wird zur Laufzeit geladen und ist nicht Teil
  des Repositorys.
