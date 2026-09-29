#!/usr/bin/env python3
"""
Pruefoberflaeche fuer data/firmen_abgleich.csv (Schritt 3b).

Zeigt die Kandidatenpaare einzeln an; jede Entscheidung wird sofort in die CSV
geschrieben. Danach src/03b_firmenabgleich.py erneut ausfuehren, damit die
Entscheidungen in die Firmenzuordnung eingehen.

Aufruf:  python3 tools/pruefliste.py [--port 8792]
Tasten:  J = ja (dieselbe Firma)   N = nein   ← / → = blaettern   K = Kommentar
"""
import argparse
import csv
import json
import os
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PRUEF_FILE = REPO / "data" / "firmen_abgleich.csv"
LOCK = threading.Lock()


def lesen() -> tuple[list[str], list[dict]]:
    with open(PRUEF_FILE, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def schreiben(felder: list[str], zeilen: list[dict]) -> None:
    """Atomar schreiben, damit ein Abbruch die Datei nie halb hinterlaesst."""
    fd, tmp = tempfile.mkstemp(dir=PRUEF_FILE.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=felder)
        w.writeheader()
        w.writerows(zeilen)
    os.replace(tmp, PRUEF_FILE)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def antwort(self, code: int, body: bytes, typ: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self.antwort(200, SEITE.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/paare":
            with LOCK:
                _, zeilen = lesen()
            self.antwort(200, json.dumps(zeilen, ensure_ascii=False).encode("utf-8"), "application/json")
        else:
            self.antwort(404, b"", "text/plain")

    def do_POST(self):
        if self.path != "/api/entscheidung":
            self.antwort(404, b"", "text/plain")
            return
        daten = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        schluessel = (daten["adresse"], daten["schluessel_a"], daten["schluessel_b"])
        with LOCK:
            felder, zeilen = lesen()
            for z in zeilen:
                if (z["adresse"], z["schluessel_a"], z["schluessel_b"]) == schluessel:
                    if daten.get("entscheidung") in ("ja", "nein", ""):
                        z["entscheidung"] = daten["entscheidung"]
                    if "kommentar" in daten:
                        z["kommentar"] = daten["kommentar"]
                    break
            else:
                self.antwort(404, b"Paar nicht gefunden", "text/plain")
                return
            schreiben(felder, zeilen)
        self.antwort(200, b"ok", "text/plain")


SEITE = r"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Firmenabgleich prüfen</title>
<style>
:root { --bg:#f6f5f2; --card:#fff; --ink:#1c1b19; --soft:#5f5b54; --mute:#9a958c; --line:#e3e0da;
        --ja:#2f7d4f; --nein:#b4452f; --akz:#2b5d8a; }
* { box-sizing:border-box } body { margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.45 -apple-system, "Segoe UI", Roboto, sans-serif; }
header { display:flex; gap:16px; align-items:center; flex-wrap:wrap; padding:14px 20px; border-bottom:1px solid var(--line); background:var(--card); }
header h1 { font-size:16px; margin:0 12px 0 0; }
.fortschritt { flex:1; min-width:180px; height:8px; background:var(--line); border-radius:4px; overflow:hidden; }
.fortschritt div { height:100%; background:var(--akz); transition:width .2s; }
.zahlen { color:var(--soft); font-variant-numeric:tabular-nums; }
label { color:var(--soft); display:flex; gap:6px; align-items:center; }
main { max-width:980px; margin:24px auto; padding:0 16px; }
.meta { display:flex; justify-content:space-between; color:var(--soft); margin-bottom:10px; flex-wrap:wrap; gap:8px; }
.adresse { font-weight:600; color:var(--ink); }
.grund { background:#ece9e3; border-radius:99px; padding:2px 10px; font-size:13px; }
.paar { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
@media (max-width:700px) { .paar { grid-template-columns:1fr; } }
.seite { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px 18px; }
.name { font-size:21px; font-weight:600; margin-bottom:6px; word-break:break-word; }
.name mark { background:#fde7b0; border-radius:3px; }
.klein { color:var(--mute); font-size:13px; }
.branchen { margin-top:10px; color:var(--soft); font-size:14px; }
.branchen span { display:block; }
.status { margin:18px 0 8px; min-height:26px; font-weight:600; }
.status.ja { color:var(--ja) } .status.nein { color:var(--nein) }
.knoepfe { display:flex; gap:10px; flex-wrap:wrap; }
button { font:inherit; padding:10px 18px; border-radius:8px; border:1px solid var(--line); background:var(--card); cursor:pointer; }
button.ja { background:var(--ja); color:#fff; border-color:var(--ja); }
button.nein { background:var(--nein); color:#fff; border-color:var(--nein); }
kbd { font:12px ui-monospace, monospace; border:1px solid currentColor; border-radius:4px; padding:0 4px; opacity:.8; margin-left:6px; }
textarea { width:100%; margin-top:14px; font:inherit; padding:8px 10px; border:1px solid var(--line); border-radius:8px; min-height:44px; }
.leer { text-align:center; color:var(--soft); margin-top:80px; }
</style></head><body>
<header>
  <h1>Firmenabgleich prüfen</h1>
  <div class="fortschritt"><div id="balken"></div></div>
  <span class="zahlen" id="zahlen"></span>
  <label><input type="checkbox" id="nurOffen" checked> nur offene</label>
</header>
<main id="main"></main>
<script>
let alle = [], liste = [], pos = 0;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

// Unterschiede zwischen den beiden Namen wortweise markieren
function markiere(a, b) {
  const wb = new Set(b.split(/\s+/));
  return a.split(/\s+/).map(w => wb.has(w) ? esc(w) : `<mark>${esc(w)}</mark>`).join(" ");
}

async function laden() {
  alle = await (await fetch("/api/paare")).json();
  filtern(0);
}
function filtern(start) {
  liste = $("nurOffen").checked ? alle.filter(p => !p.entscheidung) : alle.slice();
  pos = Math.min(start, Math.max(liste.length - 1, 0));
  zeigen();
}
function zeigen() {
  const fertig = alle.filter(p => p.entscheidung).length;
  $("balken").style.width = (alle.length ? 100 * fertig / alle.length : 0) + "%";
  $("zahlen").textContent = `${fertig} von ${alle.length} entschieden`;
  const p = liste[pos];
  if (!p) { $("main").innerHTML = `<p class="leer">Keine offenen Paare mehr. Danach <code>python3 src/03b_firmenabgleich.py</code> ausführen.</p>`; return; }
  const seite = (name, andere, n, br) => `<div class="seite">
      <div class="name">${markiere(name, andere)}</div>
      <div class="klein">${n} Eintrag${n == 1 ? "" : "e"}</div>
      <div class="branchen">${br.split(" | ").map(b => `<span>${esc(b)}</span>`).join("")}</div></div>`;
  $("main").innerHTML = `
    <div class="meta"><span><span class="adresse">${esc(p.adresse)}</span> · Paar ${pos + 1} von ${liste.length}</span>
      <span><span class="grund">${esc(p.grund)}</span> Ähnlichkeit ${esc(p.aehnlichkeit)}</span></div>
    <div class="paar">${seite(p.name_a, p.name_b, p.eintraege_a, p.branchen_a)}${seite(p.name_b, p.name_a, p.eintraege_b, p.branchen_b)}</div>
    <div class="status ${p.entscheidung}">${p.entscheidung == "ja" ? "✓ dieselbe Firma" : p.entscheidung == "nein" ? "✗ verschiedene Firmen" : ""}</div>
    <div class="knoepfe">
      <button class="ja" onclick="entscheide('ja')">Dieselbe Firma<kbd>J</kbd></button>
      <button class="nein" onclick="entscheide('nein')">Verschieden<kbd>N</kbd></button>
      <button onclick="entscheide('')">Zurücksetzen<kbd>0</kbd></button>
      <button onclick="gehe(-1)">Zurück<kbd>←</kbd></button>
      <button onclick="gehe(1)">Weiter<kbd>→</kbd></button>
    </div>
    <textarea id="kommentar" placeholder="Kommentar (optional, Taste K)">${esc(p.kommentar)}</textarea>`;
  $("kommentar").addEventListener("change", e => speichern(p, { kommentar: e.target.value }));
}
async function speichern(p, aenderung) {
  const r = await fetch("/api/entscheidung", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ adresse: p.adresse, schluessel_a: p.schluessel_a, schluessel_b: p.schluessel_b, ...aenderung }) });
  if (!r.ok) { alert("Speichern fehlgeschlagen: " + await r.text()); return false; }
  Object.assign(p, aenderung);
  return true;
}
async function entscheide(wert) {
  const p = liste[pos];
  if (!p || !(await speichern(p, { entscheidung: wert }))) return;
  if ($("nurOffen").checked && wert) filtern(pos); else if (wert) gehe(1); else zeigen();
}
function gehe(d) { pos = Math.max(0, Math.min(liste.length - 1, pos + d)); zeigen(); }
document.addEventListener("keydown", e => {
  if (e.target.tagName == "TEXTAREA") { if (e.key == "Escape") e.target.blur(); return; }
  const k = e.key.toLowerCase();
  if (k == "j") entscheide("ja"); else if (k == "n") entscheide("nein"); else if (k == "0") entscheide("");
  else if (k == "arrowright") gehe(1); else if (k == "arrowleft") gehe(-1);
  else if (k == "k") { e.preventDefault(); $("kommentar")?.focus(); }
});
$("nurOffen").addEventListener("change", () => filtern(0));
laden();
</script></body></html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8792)
    ap.add_argument("--kein-browser", action="store_true")
    args = ap.parse_args()
    if not PRUEF_FILE.exists():
        raise SystemExit(f"{PRUEF_FILE} fehlt – zuerst python3 src/03b_firmenabgleich.py ausführen.")
    url = f"http://127.0.0.1:{args.port}/"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Prüfliste: {url}  (Beenden mit Strg+C)")
    if not args.kein_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
