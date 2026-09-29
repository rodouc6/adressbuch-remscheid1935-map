// Gewerbe Remscheid 1935 — Webkarte
// Vanilla ES-Modul, kein Build-Schritt. MapLibre als globales `maplibregl`.

import MiniSearch from "https://cdn.jsdelivr.net/npm/minisearch@7.1.1/+esm";

// ----- Farbpalette pro Oberkategorie --------------------------------------
const COLORS = {
  "Werkzeugindustrie":                "#e76f51",
  "Metall- und Eisenverarbeitung":    "#455a64",
  "Maschinenbau":                     "#5b7b9c",
  "Elektrotechnik":                   "#f4a261",
  "Bandwirkerei und Textil":          "#d62828",
  "Bekleidung und Schuhe":            "#a663cc",
  "Bau und Holz":                     "#8d6e63",
  "Lebensmittel und Genuss":          "#6a994e",
  "Gastgewerbe":                      "#bc4749",
  "Handel und Vertretung":            "#2a6f97",
  "Verkehr und Brennstoffe":          "#168aad",
  "Landwirtschaft und Gartenbau":     "#b5c99a",
  "Druckerei und Medien":             "#4c2a85",
  "Persönliche Dienste":              "#76c893",
  "Gesundheit":                       "#f49cbb",
  "Sonstige Dienste":                 "#9ca3af",
  "Sonstige / nicht klassifiziert":   "#d1d5db",
};
const DEFAULT_COLOR = "#9ca3af";
const WERKZEUG_KAT  = "Werkzeugindustrie";

// Piktogramm-Schluessel -> Datei (PNG, 128x128, transparent)
const PIKTOGRAMME = {
  werkzeug_generisch: "icons/werkzeug/werkzeug_generisch.png",
  saege:              "icons/werkzeug/saege.png",
  feile:              "icons/werkzeug/feile.png",
  bohrer:             "icons/werkzeug/bohrer.png",
  zange:              "icons/werkzeug/zange.png",
  schleifstein:       "icons/werkzeug/schleifstein.png",
  beitel:             "icons/werkzeug/beitel.png",
  hammer:             "icons/werkzeug/hammer.png",
  schraubstock:       "icons/werkzeug/schraubstock.png",
  spezial:            "icons/werkzeug/spezial.png",
};

// ----- Daten laden --------------------------------------------------------
const [gewerbe, branchen] = await Promise.all([
  fetch("data/gewerbe.geojson").then(r => r.json()),
  fetch("data/branchen.json").then(r => r.json()),
]);

// Labels fuer Unterkategorie-Buttons (Mind-Map)
const PIKTO_LABELS = {
  saege: "Sägen",
  feile: "Feilen",
  bohrer: "Bohrer",
  zange: "Zangen",
  hammer: "Hämmer",
  schleifstein: "Schleifen",
  beitel: "Beitel/Hobel",
  schraubstock: "Schraubstöcke",
};
const PIKTO_FILTER_KEYS = ["saege", "feile", "bohrer", "zange", "hammer", "schleifstein", "beitel", "schraubstock"];

// State
const state = {
  activeKategorien: new Set(Object.keys(branchen)),
  toolOnly: false,
  searchOpen: false,
  piktoMode: false,
  piktoSubmenuOpen: false,
  werkzeugSymbolFilter: new Set(), // leer = alle Symbole
  popup: null,
};

// ----- Karte aufsetzen ----------------------------------------------------
const REMSCHEID = [7.193, 51.179];
// Bergisches Land — ungefaehre Region: Wuppertal im Norden, Gummersbach im Sueden,
// Solingen im Westen, Bergneustadt/Marienheide im Osten.
const BERGISCHES_LAND = [
  [6.95, 50.92],  // südwest
  [7.70, 51.40],  // nordost
];

const map = new maplibregl.Map({
  container: "map",
  // Vektor-Grundkarte von OpenFreeMap (ohne API-Key); bringt Schriften fuer Text-Layer mit.
  // Attribution (OpenFreeMap, OpenMapTiles, OpenStreetMap) liefert der Stil selbst.
  style: "https://tiles.openfreemap.org/styles/positron",
  center: REMSCHEID,
  zoom: 12.5,
  minZoom: 10,
  maxZoom: 18,
  maxBounds: BERGISCHES_LAND,
  // Namensnennung fuer Daten (CC BY-SA 4.0) und Piktogramme (Flaticon-Lizenz);
  // die vollstaendigen Nachweise mit allen Autoren stehen in LICENSE-DATEN.md
  attributionControl: {
    customAttribution:
      'Daten: <a href="https://github.com/rodouc6/adressbuch-remscheid1935-map/blob/main/LICENSE-DATEN.md" target="_blank" rel="noopener">CompGen, CC BY-SA 4.0</a> · ' +
      'Piktogramme: <a href="https://github.com/rodouc6/adressbuch-remscheid1935-map/blob/main/LICENSE-DATEN.md#bildnachweise-werkzeug-piktogramme" target="_blank" rel="noopener">Flaticon (Autoren)</a>',
  },
});

const COLOR_EXPR = ["match", ["get", "oberkategorie"]];
for (const [k, v] of Object.entries(COLORS)) { COLOR_EXPR.push(k, v); }
COLOR_EXPR.push(DEFAULT_COLOR);

// Verortungsgenauigkeit aus der Pipeline (03_join_geojson.py): haus | strasse | ungefaehr
const IST_HAUSGENAU = ["==", ["get", "genauigkeit"], "haus"];
const GENAUIGKEIT_TEXT = {
  strasse: "nur auf die Straße genau verortet",
  ungefaehr: "nur ungefähr verortet (Ortsteil/Hofschaft)",
};

map.on("load", () => {
  if (window.matchMedia("(max-width: 640px)").matches) {
    document.querySelector(".maplibregl-ctrl-attrib")?.classList.remove("maplibregl-compact-show");
  }
  map.addSource("gewerbe", {
    type: "geojson",
    data: filteredGeoJSON(),
  });

  // Einzel-Punkte ohne Clustering
  map.addLayer({
    id: "points",
    type: "circle",
    source: "gewerbe",
    paint: {
      "circle-color": COLOR_EXPR,
      "circle-radius": [
        "interpolate", ["linear"], ["zoom"],
        10, 2.5,
        13, 4,
        15, 6,
        17, 9,
      ],
      // Nicht hausgenau verortete Punkte: blasse Fuellung, Ring in Kategoriefarbe
      "circle-stroke-width": ["case", IST_HAUSGENAU, 1, 1.5],
      "circle-stroke-color": ["case", IST_HAUSGENAU, "rgba(255,255,255,0.85)", COLOR_EXPR],
      "circle-opacity": POINTS_BASE_OPACITY,
    },
  });

  // Werkzeug-Piktogramme als Symbol-Layer (initial unsichtbar)
  loadPiktogramme().then(() => {
    // Nur Anker-Features anzeigen (pro Koordinate genau einer)
    const ANCHOR_FILTER = ["all",
      ["==", ["get", "oberkategorie"], WERKZEUG_KAT],
      ["==", ["get", "is_pikto_anchor"], true],
    ];
    // Dichte-Punkte für weite Zoom-Stufen (monochrom, Radius nach werkzeug_count)
    map.addLayer({
      id: "points-werkzeug-dots",
      type: "circle",
      source: "gewerbe",
      filter: ANCHOR_FILTER,
      maxzoom: 12.5,
      paint: {
        "circle-color": "#1f2937",
        "circle-opacity": [
          "interpolate", ["linear"], ["zoom"],
          9, 0.55,
          12, 0.8,
        ],
        "circle-radius": [
          "interpolate", ["linear"], ["zoom"],
          9,  ["interpolate", ["linear"], ["coalesce", ["get", "werkzeug_count"], 1], 1, 1.6, 5, 3.2, 15, 5.5],
          12, ["interpolate", ["linear"], ["coalesce", ["get", "werkzeug_count"], 1], 1, 3.0, 5, 5.5, 15, 9.0],
        ],
        "circle-stroke-width": 0.6,
        "circle-stroke-color": "rgba(255,255,255,0.75)",
      },
      layout: { "visibility": "none" },
    });
    map.addLayer({
      id: "points-werkzeug-symbols",
      type: "symbol",
      source: "gewerbe",
      filter: ANCHOR_FILTER,
      minzoom: 12.5,
      layout: {
        "icon-image": ["concat", "wz-", ["get", "werkzeug_symbol"]],
        "icon-size": [
          "interpolate", ["linear"], ["zoom"],
          12.5, 0.12,
          14, 0.20,
          16, 0.30,
          18, 0.44,
        ],
        "icon-allow-overlap": true,
        "icon-ignore-placement": true,
        "visibility": "none",
      },
    });
    // Badge-Layer: zeigt Anzahl, wenn count > 1
    map.addLayer({
      id: "points-werkzeug-badges",
      type: "symbol",
      source: "gewerbe",
      filter: ["all",
        ["==", ["get", "oberkategorie"], WERKZEUG_KAT],
        ["==", ["get", "is_pikto_anchor"], true],
        [">", ["coalesce", ["get", "werkzeug_count"], 0], 1],
      ],
      minzoom: 12.5,
      layout: {
        "text-field": ["to-string", ["get", "werkzeug_count"]],
        "text-font": ["Noto Sans Bold"],
        "text-size": 11,
        "text-offset": [1.0, -1.0],
        "text-allow-overlap": true,
        "text-ignore-placement": true,
        "visibility": "none",
      },
      paint: {
        "text-color": "#ffffff",
        "text-halo-color": "#e76f51",
        "text-halo-width": 3,
      },
    });
    // Klick-Handler: Anker mit count>1 -> Liste, sonst Einzel-Popup
    map.on("click", "points-werkzeug-symbols", (e) => {
      const f = e.features[0];
      const cnt = f.properties.werkzeug_count || 1;
      if (cnt > 1) {
        showClusterPopup(f.geometry.coordinates, f.properties);
      } else {
        showPopup(f.geometry.coordinates, f.properties);
      }
    });
    map.on("mouseenter", "points-werkzeug-symbols", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "points-werkzeug-symbols", () => { map.getCanvas().style.cursor = ""; });
    map.on("click", "points-werkzeug-dots", (e) => {
      const f = e.features[0];
      const cnt = f.properties.werkzeug_count || 1;
      if (cnt > 1) showClusterPopup(f.geometry.coordinates, f.properties);
      else showPopup(f.geometry.coordinates, f.properties);
    });
    map.on("mouseenter", "points-werkzeug-dots", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "points-werkzeug-dots", () => { map.getCanvas().style.cursor = ""; });
  });

  // Interaktionen
  map.on("click", "points", (e) => {
    const f = e.features[0];
    showPopup(f.geometry.coordinates, f.properties);
  });
  map.on("mouseenter", "points", () => { map.getCanvas().style.cursor = "pointer"; });
  map.on("mouseleave", "points", () => { map.getCanvas().style.cursor = ""; });

  buildChips();
  buildSearchIndex();
  document.getElementById("loading").hidden = true;
  triggerAppearAnimation();
});

// ----- Piktogramme laden --------------------------------------------------
function loadPiktogramme() {
  return Promise.all(Object.entries(PIKTOGRAMME).map(([key, url]) => {
    return new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        if (!map.hasImage(`wz-${key}`)) map.addImage(`wz-${key}`, img);
        resolve();
      };
      img.onerror = () => { console.warn(`Piktogramm fehlt: ${url}`); resolve(); };
      img.src = url;
    });
  }));
}

// ----- Filtern ------------------------------------------------------------
// ----- Punkte-Stempel-Animation ----------------------------------------
// Jeder Punkt bekommt einen appear_rank (0..1) auf der SW->NE-Diagonale.
// Nach Filter-/Pikto-Aenderung laeuft eine rAF-Animation, die per
// setPaintProperty Radius und Opacity pro Punkt zeitversetzt einblendet,
// dabei startet jeder Punkt vergroessert ("eingestempelt") und schrumpft
// auf die normale Groesse.
(function setAppearRanks() {
  let minLon = Infinity, maxLon = -Infinity, minLat = Infinity, maxLat = -Infinity;
  for (const f of gewerbe.features) {
    const [lon, lat] = f.geometry.coordinates;
    if (lon < minLon) minLon = lon;
    if (lon > maxLon) maxLon = lon;
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
  }
  const dLon = (maxLon - minLon) || 1;
  const dLat = (maxLat - minLat) || 1;
  for (const f of gewerbe.features) {
    const [lon, lat] = f.geometry.coordinates;
    const nx = (lon - minLon) / dLon;
    const ny = (lat - minLat) / dLat;
    f.properties.appear_rank = (nx + ny) / 2;
  }
})();

const APPEAR_STAGGER_SEC = 0.12;
const APPEAR_FADE_SEC = 0.09;
const APPEAR_TOTAL_SEC = APPEAR_STAGGER_SEC + APPEAR_FADE_SEC + 0.05;
let appearRafId = null;

const POINTS_BASE_RADIUS = [
  "interpolate", ["linear"], ["zoom"], 10, 2.5, 13, 4, 15, 6, 17, 9,
];
const POINTS_BASE_OPACITY = ["case", IST_HAUSGENAU, 0.88, 0.3];
const DOTS_BASE_RADIUS = [
  "interpolate", ["linear"], ["zoom"],
  9,  ["interpolate", ["linear"], ["coalesce", ["get", "werkzeug_count"], 1], 1, 1.6, 5, 3.2, 15, 5.5],
  12, ["interpolate", ["linear"], ["coalesce", ["get", "werkzeug_count"], 1], 1, 3.0, 5, 5.5, 15, 9.0],
];
// Zoom-Ausdruecke duerfen nur ganz oben stehen; der Animationsfaktor p wird
// deshalb in die Stuetzwerte hineinmultipliziert statt aussen herum.
const dotsOpacity = (p = 1) => [
  "interpolate", ["linear"], ["zoom"], 9, ["*", 0.55, p], 12, ["*", 0.8, p],
];
const DOTS_BASE_OPACITY = dotsOpacity();

function progressExpr(T) {
  // T = absolute Zeit in Sekunden (performance.now()/1000).
  // Pro Feature: progress = (T - (_appear_t + rank*STAGGER)) / FADE, geclamped 0..1.
  // Schon laenger sichtbare Features haben _appear_t weit in der Vergangenheit
  // -> progress = 1, kein Flicker. Nur neu sichtbare animieren.
  return ["max", 0,
    ["min", 1,
      ["/",
        ["-",
          T,
          ["+", ["coalesce", ["get", "_appear_t"], 0], ["*", ["get", "appear_rank"], APPEAR_STAGGER_SEC]],
        ],
        APPEAR_FADE_SEC,
      ],
    ],
  ];
}

function applyAppearFrame(t) {
  const p = progressExpr(t);
  if (map.getLayer("points")) {
    map.setPaintProperty("points", "circle-opacity", ["*", POINTS_BASE_OPACITY, p]);
    map.setPaintProperty("points", "circle-stroke-opacity", ["*", 0.85, p]);
  }
  if (map.getLayer("points-werkzeug-dots")) {
    map.setPaintProperty("points-werkzeug-dots", "circle-opacity", dotsOpacity(p));
    map.setPaintProperty("points-werkzeug-dots", "circle-stroke-opacity", ["*", 0.75, p]);
  }
  if (map.getLayer("points-werkzeug-symbols")) {
    map.setPaintProperty("points-werkzeug-symbols", "icon-opacity", p);
  }
}

function applyStaticPaint() {
  if (map.getLayer("points")) {
    map.setPaintProperty("points", "circle-radius", POINTS_BASE_RADIUS);
    map.setPaintProperty("points", "circle-opacity", POINTS_BASE_OPACITY);
    map.setPaintProperty("points", "circle-stroke-opacity", 0.85);
  }
  if (map.getLayer("points-werkzeug-dots")) {
    map.setPaintProperty("points-werkzeug-dots", "circle-radius", DOTS_BASE_RADIUS);
    map.setPaintProperty("points-werkzeug-dots", "circle-opacity", DOTS_BASE_OPACITY);
    map.setPaintProperty("points-werkzeug-dots", "circle-stroke-opacity", 0.75);
  }
  if (map.getLayer("points-werkzeug-symbols")) {
    map.setPaintProperty("points-werkzeug-symbols", "icon-opacity", 1);
  }
}

function triggerAppearAnimation() {
  if (appearRafId) cancelAnimationFrame(appearRafId);
  const start = performance.now();
  const step = () => {
    const elapsed = (performance.now() - start) / 1000;
    if (elapsed > APPEAR_TOTAL_SEC) {
      applyStaticPaint();
      appearRafId = null;
      return;
    }
    applyAppearFrame(performance.now() / 1000);
    appearRafId = requestAnimationFrame(step);
  };
  step();
}

let lastVisibleIds = new Set();
let lastFilterAddedFeatures = true;  // initialer Run: alles ist neu
function filteredGeoJSON() {
  const features = gewerbe.features.filter((f) => {
    const ok = f.properties.oberkategorie;
    if (state.toolOnly) return ok === WERKZEUG_KAT;
    return state.activeKategorien.has(ok);
  });
  // Nur fuer neu sichtbare Features den Zeitstempel "jetzt" setzen;
  // schon zuvor sichtbare behalten ihr altes _appear_t und bleiben stabil.
  const T = performance.now() / 1000;
  const nextIds = new Set();
  let addedAny = false;
  for (const f of features) {
    const id = f.properties.id;
    nextIds.add(id);
    if (!lastVisibleIds.has(id)) {
      f.properties._appear_t = T;
      addedAny = true;
    }
  }
  lastFilterAddedFeatures = addedAny;
  lastVisibleIds = nextIds;
  document.getElementById("countLabel").textContent =
    features.length.toLocaleString("de-DE");
  return { type: "FeatureCollection", features };
}
function refresh() {
  if (!map.getSource("gewerbe")) return;
  map.getSource("gewerbe").setData(filteredGeoJSON());
  if (lastFilterAddedFeatures) {
    triggerAppearAnimation();
  } else {
    // Reines Ausblenden: laufende Animation sofort beenden, alles auf Endzustand.
    if (appearRafId) { cancelAnimationFrame(appearRafId); appearRafId = null; }
    applyStaticPaint();
  }
}

// ----- Chips --------------------------------------------------------------
function buildChips() {
  const chips = document.getElementById("chips");
  // Desktop: Mauserad-vertikal in Horizontal-Scroll uebersetzen
  chips.addEventListener("wheel", (e) => {
    if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
    e.preventDefault();
    chips.scrollLeft += e.deltaY;
  }, { passive: false });

  // Erster Chip: Alle/Keine-Toggle
  const allBtn = document.createElement("button");
  allBtn.type = "button";
  allBtn.className = "chip chip--all";
  allBtn.id = "chipAll";
  allBtn.dataset.allactive = "true";
  allBtn.innerHTML = `<span class="chip__label">Alle</span>`;
  allBtn.style.setProperty("--delay", "0ms");
  allBtn.addEventListener("click", () => {
    const allOn = allBtn.dataset.allactive === "true";
    if (allOn) {
      state.activeKategorien.clear();
    } else {
      state.activeKategorien = new Set(Object.keys(branchen));
    }
    // Werkzeug-Solo-Modus aufloesen
    if (state.toolOnly) {
      state.toolOnly = false;
      document.getElementById("toolToggle").setAttribute("aria-pressed", "false");
    }
    syncChipStates();
    refresh();
  });
  chips.appendChild(allBtn);

  const sorted = Object.entries(branchen).sort((a, b) => b[1].frequency - a[1].frequency);
  sorted.forEach(([name, info], idx) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip";
    btn.dataset.active = "true";
    btn.dataset.kategorie = name;
    const color = COLORS[name] || DEFAULT_COLOR;
    btn.style.setProperty("--chip-color", color);
    btn.style.setProperty("--delay", `${(idx + 1) * 35}ms`);
    btn.innerHTML = `<span class="chip__dot"></span><span>${escapeHtml(name)}</span><span class="chip__count">${info.frequency.toLocaleString("de-DE")}</span>`;
    btn.addEventListener("click", () => toggleKategorie(name, btn));
    chips.appendChild(btn);
  });
  syncChipStates();
}

function toggleKategorie(name, btn) {
  if (state.toolOnly) {
    state.toolOnly = false;
    document.getElementById("toolToggle").setAttribute("aria-pressed", "false");
    state.activeKategorien = new Set(Object.keys(branchen));
  }
  if (state.activeKategorien.has(name)) {
    state.activeKategorien.delete(name);
  } else {
    state.activeKategorien.add(name);
  }
  syncChipStates();
  refresh();
}

// Hält Chip-States und Filter-Indikator konsistent mit state.activeKategorien
function syncChipStates() {
  document.querySelectorAll(".chip[data-kategorie]").forEach((c) => {
    c.dataset.active = state.activeKategorien.has(c.dataset.kategorie) ? "true" : "false";
  });
  const total = Object.keys(branchen).length;
  const allOn = state.activeKategorien.size === total;
  const noneOn = state.activeKategorien.size === 0;
  const allBtn = document.getElementById("chipAll");
  if (allBtn) {
    allBtn.dataset.allactive = allOn ? "true" : "false";
    allBtn.querySelector(".chip__label").textContent = allOn ? "Alle abwählen" : "Alle auswählen";
  }
  // Filter-Indikator-Dot zeigen, wenn Filter aktiv (nicht alle)
  const dot = document.getElementById("filterDot");
  if (dot) dot.hidden = allOn && !state.toolOnly;
}

// ----- Such-UI ------------------------------------------------------------
let search = null;
function buildSearchIndex() {
  search = new MiniSearch({
    fields: ["firmenname", "name", "adresse", "unterbranche"],
    storeFields: ["id", "firmenname", "lastname", "firstname", "adresse", "ortsname", "oberkategorie", "unterbranche", "genauigkeit", "lng", "lat"],
    searchOptions: { boost: { firmenname: 2, name: 1.5 }, prefix: true, fuzzy: 0.2 },
    idField: "fid",
  });
  const docs = gewerbe.features.map((f, i) => ({
    fid: i,
    id: f.properties.id,
    firmenname: f.properties.firmenname,
    lastname: f.properties.lastname,
    firstname: f.properties.firstname,
    name: `${f.properties.lastname} ${f.properties.firstname}`.trim(),
    adresse: f.properties.adresse,
    ortsname: f.properties.ortsname,
    oberkategorie: f.properties.oberkategorie,
    unterbranche: f.properties.unterbranche,
    genauigkeit: f.properties.genauigkeit,
    lng: f.geometry.coordinates[0],
    lat: f.geometry.coordinates[1],
  }));
  search.addAll(docs);
}

const searchPill = document.getElementById("searchPill");
const searchToggle = document.getElementById("searchToggle");
const searchClose = document.getElementById("searchClose");
const searchInput = document.getElementById("searchInput");
const results = document.getElementById("results");

function openSearch() {
  state.searchOpen = true;
  searchPill.dataset.state = "open";
  searchInput.focus();
}
function closeSearch() {
  state.searchOpen = false;
  searchPill.dataset.state = "collapsed";
  searchInput.value = "";
  results.hidden = true;
  results.innerHTML = "";
}
searchToggle.addEventListener("click", () => state.searchOpen ? closeSearch() : openSearch());
searchClose.addEventListener("click", closeSearch);

searchInput.addEventListener("input", () => {
  const q = searchInput.value.trim();
  if (!q || q.length < 2) { results.hidden = true; results.innerHTML = ""; return; }
  const hits = search.search(q, { combineWith: "AND" }).slice(0, 25);
  if (!hits.length) {
    results.innerHTML = `<div class="results__empty">Keine Treffer.</div>`;
    results.hidden = false;
    return;
  }
  results.innerHTML = hits.map((h) => `
    <a class="results__item" data-lng="${h.lng}" data-lat="${h.lat}" data-fid="${h.id}">
      <div class="results__title">${escapeHtml(h.firmenname || `${h.lastname} ${h.firstname}`.trim())}</div>
      <div class="results__sub">${escapeHtml((h.adresse || "") + (h.ortsname ? ", " + h.ortsname : ""))}</div>
    </a>
  `).join("");
  results.hidden = false;
  results.querySelectorAll(".results__item").forEach((el) => {
    el.addEventListener("click", () => {
      const lng = parseFloat(el.dataset.lng), lat = parseFloat(el.dataset.lat);
      map.easeTo({ center: [lng, lat], zoom: 17, duration: 700 });
      // Popup direkt zeigen (Daten aus dem MiniSearch-Eintrag)
      const idx = hits.findIndex((h) => h.id === el.dataset.fid);
      if (idx >= 0) showPopup([lng, lat], hits[idx]);
      if (window.innerWidth < 640) closeSearch();
    });
  });
});

// ----- Werkzeug-Quick-Toggle ---------------------------------------------
const toolToggle = document.getElementById("toolToggle");
let toolToggleLabelTimer = null;
toolToggle.addEventListener("click", () => {
  state.toolOnly = !state.toolOnly;
  toolToggle.setAttribute("aria-pressed", state.toolOnly ? "true" : "false");
  if (state.toolOnly) {
    state.activeKategorien = new Set([WERKZEUG_KAT]);
  } else {
    state.activeKategorien = new Set(Object.keys(branchen));
  }
  // Label nach Aktivierung 5s einblenden, danach automatisch einklappen.
  clearTimeout(toolToggleLabelTimer);
  if (state.toolOnly) {
    toolToggle.dataset.showLabel = "true";
    toolToggleLabelTimer = setTimeout(() => {
      toolToggle.dataset.showLabel = "false";
    }, 5000);
  } else {
    toolToggle.dataset.showLabel = "false";
  }
  syncChipStates();
  refresh();
});

// ----- Piktogramm-Toggle --------------------------------------------------
const piktoToggle = document.getElementById("piktoToggle");
piktoToggle.addEventListener("click", () => {
  if (!state.piktoMode) {
    // OFF -> EXPANDED
    state.piktoMode = true;
    state.piktoSubmenuOpen = true;
  } else if (state.piktoSubmenuOpen) {
    // EXPANDED -> COLLAPSED (Auswahl bleibt)
    state.piktoSubmenuOpen = false;
  } else if (state.werkzeugSymbolFilter.size > 0) {
    // COLLAPSED mit Auswahl -> EXPANDED (Fächer wieder auf)
    state.piktoSubmenuOpen = true;
  } else {
    // COLLAPSED ohne Auswahl -> OFF
    state.piktoMode = false;
  }
  piktoToggle.setAttribute("aria-pressed", state.piktoMode ? "true" : "false");
  piktoToggle.dataset.hasSelection = state.werkzeugSymbolFilter.size > 0 ? "true" : "false";
  applyPiktoMode();
  renderPiktoSubmenu();
});
function applyPiktoMode() {
  if (!map.getLayer("points")) return;
  if (state.piktoMode) {
    map.setFilter("points", ["!=", ["get", "oberkategorie"], WERKZEUG_KAT]);
  } else {
    map.setFilter("points", null);
  }
  const visible = state.piktoMode ? "visible" : "none";
  for (const id of ["points-werkzeug-dots", "points-werkzeug-symbols", "points-werkzeug-badges"]) {
    if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visible);
  }
  applyWerkzeugSymbolFilter();
}
function applyWerkzeugSymbolFilter() {
  const sel = state.werkzeugSymbolFilter;
  const baseFilter = ["all",
    ["==", ["get", "oberkategorie"], WERKZEUG_KAT],
    ["==", ["get", "is_pikto_anchor"], true],
  ];
  const symFilter = sel.size === 0
    ? baseFilter
    : ["all", ...baseFilter.slice(1), ["in", ["get", "werkzeug_symbol"], ["literal", [...sel]]]];
  if (map.getLayer("points-werkzeug-dots"))    map.setFilter("points-werkzeug-dots", symFilter);
  if (map.getLayer("points-werkzeug-symbols")) map.setFilter("points-werkzeug-symbols", symFilter);
  if (map.getLayer("points-werkzeug-badges")) {
    map.setFilter("points-werkzeug-badges", ["all", ...symFilter.slice(1), [">", ["coalesce", ["get", "werkzeug_count"], 0], 1]]);
  }
}

// ----- Piktogramm-Submenu (Mind-Map) -------------------------------------
function renderPiktoSubmenu() {
  let menu = document.getElementById("piktoSubmenu");
  if (!menu) {
    menu = document.createElement("div");
    menu.id = "piktoSubmenu";
    menu.className = "pikto-submenu";
    document.body.appendChild(menu);
    // Vertikaler Stack über dem Haupt-Button. Index 0 sitzt direkt darüber.
    const SPACING = 52;
    const FIRST_OFFSET = 56;
    PIKTO_FILTER_KEYS.forEach((key, i) => {
      const dy = -(FIRST_OFFSET + i * SPACING);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pikto-submenu__btn";
      btn.dataset.symbol = key;
      btn.title = PIKTO_LABELS[key] || key;
      btn.style.setProperty("--dy-open", `${dy}px`);
      btn.style.setProperty("--delay", `${i * 35}ms`);
      btn.innerHTML = `<img src="${PIKTOGRAMME[key]}" alt="${PIKTO_LABELS[key] || key}" /><span class="pikto-submenu__label">${PIKTO_LABELS[key] || key}</span>`;
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (state.werkzeugSymbolFilter.has(key)) state.werkzeugSymbolFilter.delete(key);
        else state.werkzeugSymbolFilter.add(key);
        btn.dataset.selected = state.werkzeugSymbolFilter.has(key) ? "true" : "false";
        piktoToggle.dataset.hasSelection = state.werkzeugSymbolFilter.size > 0 ? "true" : "false";
        applyWerkzeugSymbolFilter();
      });
      menu.appendChild(btn);
    });
  }
  menu.dataset.open = state.piktoSubmenuOpen ? "true" : "false";
  // Auswahlzustand auf Buttons spiegeln
  for (const btn of menu.querySelectorAll(".pikto-submenu__btn")) {
    btn.dataset.selected = state.werkzeugSymbolFilter.has(btn.dataset.symbol) ? "true" : "false";
  }
}

// ----- Filter-Pille: Chip-Leiste ein-/ausblenden ------------------------
const filterToggle = document.getElementById("filterToggle");
filterToggle.addEventListener("click", () => {
  const hidden = document.body.dataset.chipsHidden === "true";
  document.body.dataset.chipsHidden = hidden ? "false" : "true";
  filterToggle.setAttribute("aria-pressed", hidden ? "true" : "false");
});

// ----- UI Toggle ----------------------------------------------------------
document.getElementById("uiToggle").addEventListener("click", () => {
  const hidden = document.body.dataset.uiHidden === "true";
  document.body.dataset.uiHidden = hidden ? "false" : "true";
});

// ----- Popup (Cluster mit mehreren Firmen an einer Adresse) -----------
function parseArray(v) {
  if (Array.isArray(v)) return v;
  if (typeof v !== "string") return [];
  try { return JSON.parse(v); } catch { return []; }
}

// Generische "Werkzeugfabrik"-Branchen werden ausgeblendet, sobald eine
// spezifischere Branche derselben Firma vorliegt.
const _GENERIC_RX = /werkzeugfabrik\s*\(generisch\)|werkzeugindustrie\s*\(generisch\)|werkzeug- und maschinenfabrik|werkzeug- und metallwarenfabrik/i;
function refineBranchen(list) {
  const arr = parseArray(list).filter(Boolean);
  const specific = arr.filter((b) => !_GENERIC_RX.test(b));
  return specific.length ? specific : arr;
}

function showClusterPopup(coords, p) {
  if (state.popup) state.popup.remove();
  const liste = parseArray(p.werkzeug_mitglieder);
  const adresse = (p.adresse || "") + (p.ortsname ? ", " + p.ortsname : "");
  const hinweis = GENAUIGKEIT_TEXT[p.genauigkeit]
    ? `<div class="popup__row popup__row--hinweis">Lage: ${GENAUIGKEIT_TEXT[p.genauigkeit]}</div>` : "";
  const head = `<div class="popup__title">${liste.length} Firmen an dieser Adresse</div>
    <div class="popup__row">${escapeHtml(adresse)}</div>${hinweis}
    <div style="margin-bottom:8px"></div>`;
  const items = liste.map((m) => {
    const branchen = refineBranchen(m.branchen);
    const branchen_html = branchen.length
      ? `<span class="popup__cluster-sub">${branchen.map(escapeHtml).join(" · ")}</span>`
      : "";
    return `
      <div class="popup__cluster-item">
        <span class="popup__cluster-name">${escapeHtml(m.firmenname || "(ohne Namen)")}</span>
        ${branchen_html}
      </div>
    `;
  }).join("");
  state.popup = new maplibregl.Popup({ offset: 14, closeButton: true, maxWidth: "360px" })
    .setLngLat(coords)
    .setHTML(head + `<div class="popup__cluster-list">${items}</div>`)
    .addTo(map);
}

// ----- Popup --------------------------------------------------------------
function showPopup(coords, p) {
  if (state.popup) state.popup.remove();
  const color = COLORS[p.oberkategorie] || DEFAULT_COLOR;
  const name = p.firmenname || `${p.lastname || ""} ${p.firstname || ""}`.trim() || "(ohne Namen)";
  const owner = (p.lastname || p.firstname) && p.firmenname
    ? `${p.lastname || ""} ${p.firstname || ""}`.trim()
    : "";
  // Mehrere Branchen-Listings derselben Firma? Generisches ausblenden, wenn spezifisches vorhanden.
  const branchen = refineBranchen(p.werkzeug_branchen);
  let catHtml;
  if (branchen.length > 1) {
    catHtml = `<div class="popup__cat" style="background:${color}">${escapeHtml(p.oberkategorie)}</div>
      <div class="popup__branchen"><strong>Branchen:</strong>${branchen.map(b => `<span>· ${escapeHtml(b)}</span>`).join("")}</div>`;
  } else {
    const ub = p.unterbranche || (branchen[0] || "");
    catHtml = `<div class="popup__cat" style="background:${color}">${escapeHtml(p.oberkategorie)}${ub ? " · " + escapeHtml(ub) : ""}</div>`;
  }
  const html = `
    <div class="popup__title">${escapeHtml(name)}</div>
    ${owner ? `<div class="popup__row"><strong>Inhaber:</strong> ${escapeHtml(owner)}</div>` : ""}
    <div class="popup__row"><strong>Adresse:</strong> ${escapeHtml(p.adresse || "—")}${p.ortsname ? ", " + escapeHtml(p.ortsname) : ""}</div>
    ${GENAUIGKEIT_TEXT[p.genauigkeit] ? `<div class="popup__row popup__row--hinweis">Lage: ${GENAUIGKEIT_TEXT[p.genauigkeit]}</div>` : ""}
    ${catHtml}
  `;
  state.popup = new maplibregl.Popup({ offset: 12, closeButton: true, maxWidth: "320px" })
    .setLngLat(coords)
    .setHTML(html)
    .addTo(map);
}

// ----- Helpers ------------------------------------------------------------
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}
