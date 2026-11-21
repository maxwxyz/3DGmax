"""Konstruktionsachsen aus STEP-Kreisen und Mantellinien fuer die projizierte Toleranzzone."""

import numpy as np
from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Circle, GeomAbs_Cylinder, GeomAbs_Line
from OCC.Core.TopAbs import TopAbs_EDGE
from OCC.Core.TopoDS import topods

from ..i18n import tr
from . import projektionszone, toleranzzone as tz


def _abschnitt(mitte, d, r, linien, eindeutig):
    # Je Mantellinie nur den zusammenhaengenden Abschnitt durch den Kreis verwenden.
    spuren = []
    for a, b in linien:
        v = b - a
        if np.linalg.norm(np.cross(v, d)) > 1e-6 or np.linalg.norm(v) < 1e-7:
            continue
        radial = a - mitte - d * ((a - mitte) @ d)
        if abs(np.linalg.norm(radial) - r) > 1e-5:
            continue
        gruppe = next((g for ort, g in spuren if np.linalg.norm(ort - radial) <= 1e-6), None)
        if gruppe is None:
            gruppe = []
            spuren.append((radial, gruppe))
        gruppe.append(sorted(((a - mitte) @ d, (b - mitte) @ d)))
    abschnitte = []
    for _, gruppe in spuren:
        vereinigt = []
        for lo, hi in sorted(gruppe):
            if vereinigt and lo <= vereinigt[-1][1] + 1e-6:
                vereinigt[-1][1] = max(vereinigt[-1][1], hi)
            else:
                vereinigt.append([lo, hi])
        abschnitte.extend((lo, hi) for lo, hi in vereinigt if lo <= 1e-6 and hi >= -1e-6)
    if not abschnitte:
        return 0., 0.
    if eindeutig and max(np.ptp(abschnitte, axis=0)) > 1e-5:
        return None
    return min(lo for lo, _ in abschnitte), max(hi for _, hi in abschnitte)


def kreisachsen(formen, vollkreis=False):
    kreise, linien = [], []
    for f in formen:
        if f.ShapeType() != TopAbs_EDGE:
            continue
        c = BRepAdaptor_Curve(topods.Edge(f))
        if c.GetType() == GeomAbs_Circle:
            if vollkreis and abs(c.LastParameter() - c.FirstParameter() - 2 * np.pi) > 1e-7:
                continue
            kreis = c.Circle()
            kreise.append((np.array(kreis.Location().Coord()), np.array(kreis.Axis().Direction().Coord()), kreis.Radius()))
        elif c.GetType() == GeomAbs_Line:
            linien.append([np.array(c.Value(t).Coord()) for t in (c.FirstParameter(), c.LastParameter())])
    for mitte, d, r in kreise:
        intervall = _abschnitt(mitte, d, r, linien, vollkreis)
        if intervall is not None:
            lo, hi = intervall
            yield mitte + d * lo, d, hi - lo, r


def quellwand(erg, idx):
    """Wand im selben Koordinatensystem wie die Konstruktionskanten, auch bei hinzugefuegten Dateien."""
    modell = erg.modell
    versatz = None
    for zusatz in erg.zusaetze:
        if zusatz.erste_flaeche <= idx < zusatz.erste_flaeche + zusatz.flaechen:
            lokal = idx - zusatz.erste_flaeche
            versatz = modell.flaechen[idx].Location().Multiplied(zusatz.modell.flaechen[lokal].Location().Inverted())
            modell, idx = zusatz.modell, lokal
            break
    eid = modell.flaeche_zu_step.get(idx)
    form = modell.form_von_step(eid) if eid is not None else None
    return form.Moved(versatz) if form is not None and versatz is not None else form


def projektionsziel(pmi, wand, basis, form_fuer, lage):
    """Die Wand waehlt eine koaxiale Innenkontur; Intervall und Toleranz stammen aus der Konstruktion."""
    ungeklart = tr("Keine eindeutige projizierte Konstruktionsachse an dieser Bohrungswand")
    zyl = tz._achse([wand])
    if not zyl or BRepAdaptor_Surface(wand).GetType() != GeomAbs_Cylinder or basis is None or not basis.IsPartner(wand):
        return None, None, ungeklart
    o, n, tiefe, radius, _ = zyl
    if not tz._ist_innen(wand, o, n):
        return None, None, ungeklart
    versatz = wand.Location().Multiplied(basis.Location().Inverted())
    kandidaten = []
    for p in pmi:
        if p.art != "toleranz" or p.flaechen or not getattr(p, "teilformen", None) or p.zone != "Projected":
            continue
        austritte = [form_fuer(i) for i in p.projektionsflaechen]
        if any(f is None for f in austritte):
            continue
        for start, d, laenge, r in kreisachsen([f.Moved(versatz) for f in p.teilformen], vollkreis=True):
            if (laenge <= 1e-7 or r <= radius or np.linalg.norm(np.cross(n, d)) > 1e-7
                    or np.linalg.norm(np.cross(start - o, n)) > 1e-5):
                continue
            stationen = sorted(((start - o) @ n, (start + laenge * d - o) @ n))
            if stationen[0] < -1e-5 or stationen[1] > tiefe + 1e-5:
                continue
            # Eine ebene, nur zufaellig gleich gelegene Kappe eines anderen Koerpers ist kein Ursprung.
            rand = projektionszone._kanten(wand)
            if not all(projektionszone._beruehren(rand, projektionszone._kanten(f)) for f in austritte):
                continue
            mitte = lage[:3, :3] @ (start + d * laenge / 2) + lage[:3, 3]
            zone, fehler = projektionszone.sichtintervall(p, mitte, lage[:3, :3] @ d, laenge, austritte, lage)
            kandidaten.append((p, zone, fehler))
    if len(kandidaten) != 1:
        return None, None, ungeklart
    quelle, zone, fehler = kandidaten[0]
    for p in pmi:
        if p is quelle or p.art != "toleranz":
            continue
        if any(a.IsSame(b) for a in quelle.teilformen for b in getattr(p, "teilformen", ())):
            return None, None, tr("Mehrere Toleranzrahmen an der Konstruktionsgeometrie")
    return quelle, zone, fehler
