"""Explosionsansicht nach Baugruppenebenen (ohne Qt).

Jede Baugruppe schiebt ihre Kinder vom eigenen Mittelpunkt weg; die Versaetze summieren sich ueber die Ebenen.
Die Ebenen oeffnen sich gestaffelt: bei kleinem Anteil bewegen sich nur die obersten Unterbaugruppen als Einheit,
mit wachsendem Anteil folgen die Teile darin. Bei einer flachen Baugruppe ist das die einfache radiale Explosion.
"""

from __future__ import annotations

FAKTOR = 1.6


def _tiefe(k) -> int:
    """Anzahl der Baugruppenebenen mit mehr als einem Kind unterhalb von k."""
    if not k.kinder:
        return 0
    unten = max(_tiefe(c) for c in k.kinder)
    return unten + (1 if len(k.kinder) > 1 else 0)


ACHSEN = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}


def versaetze(baum, mitten: dict, anteil: float, faktor: float = FAKTOR, achse: str | None = None) -> dict:
    """Versatz je Blatt-Nummer; mitten: Blatt-Nummer -> Mittelpunkt (x, y, z) der Einbaulage. achse "x"/"y"/"z":
    nur entlang dieser Achse (Versatz auf die Achse projiziert), sonst radial."""
    aus: dict = {}
    if anteil <= 0:
        return aus
    stufen = max(1, _tiefe(baum))

    def mitte(k):
        if not k.kinder:
            return mitten.get(k.nummer)
        ms = [m for m in (mitte(c) for c in k.kinder) if m is not None]
        return tuple(sum(m[i] for m in ms) / len(ms) for i in range(3)) if ms else None

    def gehe(k, versatz, ebene):
        if not k.kinder:
            if k.nummer in mitten:
                aus[k.nummer] = versatz
            return
        m0 = mitte(k)
        verzweigt = len(k.kinder) > 1
        lokal = min(1.0, max(0.0, anteil * stufen - ebene)) if verzweigt else 0.0
        for kind in k.kinder:
            m = mitte(kind)
            if m is None:
                continue
            v = tuple(versatz[i] + (m[i] - m0[i]) * faktor * lokal for i in range(3))
            gehe(kind, v, ebene + (1 if verzweigt else 0))

    gehe(baum, (0.0, 0.0, 0.0), 0)
    if achse in ACHSEN:
        a = ACHSEN[achse]
        aus = {n: tuple(sum(v[i] * a[i] for i in range(3)) * a[j] for j in range(3)) for n, v in aus.items()}
    return aus
