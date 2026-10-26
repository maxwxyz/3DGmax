"""Grafische PMI aus semantischer PMI erzeugen, wo die Datei keine Darstellung liefert (QIF, rein semantisches STEP).

Erste Stufe: Hinweislinie vom Element (Schwerpunkt der Flaechen) nach aussen und ein Textfeld mit dem Wert,
Toleranzrahmen oder Bezugsbuchstaben. Gestapelt, damit sich Texte nicht ueberdecken. Markiert als 'erzeugt',
damit sie nie mit der Darstellung des Autors verwechselt wird.
"""

from __future__ import annotations

import numpy as np

from .pmi import BEZUG, HINWEIS
from .praesentation import Grafik, Platzhalter


def _schwerpunkt(flaechen) -> np.ndarray | None:
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    summe, gewicht = np.zeros(3), 0.0
    for f in flaechen:  # einzeln: nach innen zeigende Flaechen (Bohrungen) liefern negativen Inhalt
        g = GProp_GProps()
        brepgprop.SurfaceProperties(f, g)
        a = abs(g.Mass())
        if a > 0:
            c = g.CentreOfMass()
            summe += a * np.array([c.X(), c.Y(), c.Z()])
            gewicht += a
    return summe / gewicht if gewicht > 0 else None


def ergaenze(pmi: list, grafik: dict, modell) -> dict:
    """Neue Grafiken (negative Callout-IDs) fuer PMI mit Flaechen, aber ohne vorhandene Darstellung."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    dargestellt = {i for g in grafik.values() for i in g.pmi_ids}
    offen = [p for p in pmi if p.step_id and p.step_id not in dargestellt and p.flaechen and p.art != HINWEIS]
    if not offen:
        return {}
    box = Bnd_Box()
    brepbndlib.Add(modell.form, box)
    x0, y0, z0, x1, y1, z1 = box.Get()
    mitte = np.array([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    diag = float(np.linalg.norm([x1 - x0, y1 - y0, z1 - z0])) or 1.0
    hoehe, abstand = diag / 70, diag / 6
    belegt: list[np.ndarray] = []
    neu = {}
    for i, p in enumerate(offen, 1):
        anker = _schwerpunkt([modell.flaechen[j] for j in sorted(p.flaechen) if j < len(modell.flaechen)])
        if anker is None:
            continue
        richtung = anker - mitte
        if np.linalg.norm(richtung) < 1e-9 * diag:
            richtung = np.array([0.0, 0.0, 1.0])
        richtung = richtung / np.linalg.norm(richtung)
        ort = anker + richtung * abstand
        for _ in range(40):  # nach aussen schieben, bis kein anderes Textfeld zu nah ist
            if all(np.linalg.norm(ort - b) > 4.0 * hoehe for b in belegt):
                break
            ort = ort + richtung * 1.6 * hoehe
        belegt.append(ort)
        null = np.zeros(3)
        neu[-i] = Grafik(-i, name=p.name or p.typ, linien=[np.array([anker, ort])],
                         platzhalter=[Platzhalter(ort, null, null, hoehe * 8, hoehe)],
                         fertig=True, pmi_ids={p.step_id}, erzeugt=True)
        if p.art == BEZUG:
            neu[-i].name = f"[{p.name}]"
    return neu
