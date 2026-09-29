"""
Gemeinsame Branchen-Extraktion fuer Schritt 4 (Klassifikation) und Schritt 6 (Export).

Beide Schritte muessen die Erst-Branche identisch ableiten, sonst passt der
Join gegen data/branchen_mapping.csv nicht mehr. Deshalb liegt die Logik nur hier.
"""
import re

# Rechtsform-Tokens, die als Erst-Branche uebersprungen werden
RECHTSFORM = re.compile(
    r"^(?:G\.?\s*m\.?\s*b\.?\s*H\.?|A\.?-?G\.?|Kom\.?-?Ges\.?|K\.?G\.?|OHG|o\.\s*H\.?|e\.\s*G\.|e\.\s*V\.|i\.\s*L\.|"
    r"Inh\.?|Inhaber|Geschäftsführer|G\.F\.|Komm\.?-?Ges\.?)$",
    re.IGNORECASE,
)

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
