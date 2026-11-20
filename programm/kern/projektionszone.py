"""Projektionsintervall einer zylindrischen Toleranzzone aus ihrem expliziten Austrittsende."""

import numpy as np

from ..i18n import tr
from . import toleranzzone as tz


def _kanten(form):
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer
    ex = TopExp_Explorer(form, TopAbs_EDGE)
    out = []
    while ex.More():
        out.append(ex.Current())
        ex.Next()
    return out


def _beruehren(kanten, andere):
    return any(a.IsSame(b) for a in kanten for b in andere)


def einzelachse(p, form, form_fuer):
    """Mehrere Mantelstuecke eines einzigen Zylinders: gleiche Endlagen und zusammenhaengender Rand."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder
    f0 = tz._achse([form])
    if not f0 or not p.flaechen:
        return False
    start, d, laenge, r, _ = f0
    mitte = start + d * laenge / 2
    netz = []
    for i in p.flaechen:
        f = form_fuer(i)
        a = tz._achse([f]) if f is not None else None
        if a is None or BRepAdaptor_Surface(f).GetType() != GeomAbs_Cylinder:
            return False
        o, achse, laenge_i, radius, _ = a
        if (np.linalg.norm(np.cross(d, achse)) > 1e-7 or abs(laenge_i - laenge) > 1e-5 or
                abs(radius - r) > 1e-5 or np.linalg.norm(o + achse * laenge_i / 2 - mitte) > 1e-5):
            return False
        netz.append(_kanten(f))
    # Schnitt- und Nahtkanten verwenden die topologische Identitaet der Kante.
    erreicht = _kanten(form)
    while netz:
        angrenzend = next((j for j, kanten in enumerate(netz) if _beruehren(erreicht, kanten)), None)
        if angrenzend is None:
            return False
        erreicht.extend(netz.pop(angrenzend))
    return True


def sichtintervall(p, mitte, d, laenge, flaeche_fuer, lage):
    """Projektionsrichtung und -laenge einer Achse anhand ihrer semantischen Austrittsflaeche."""
    from .baugruppe_mass import ebene

    h, offset = p.zonen_wert, getattr(p, "projektionsversatz", 0.)
    if h is None or not np.isfinite(h) or h <= 0 or offset is None or not np.isfinite(offset) or offset < 0:
        return None, tr("Höhe oder Versatz der projizierten Zone")
    # Der Ursprung muss am Ende des tatsaechlichen Mantels liegen. Die Materialnormale weist nach aussen.
    ende = None
    for idx in getattr(p, "projektionsflaechen", ()):
        f = flaeche_fuer(idx)
        pl = ebene(f, lage) if f is not None else None
        if pl is None or np.linalg.norm(np.cross(d, pl[1])) > 1e-7:
            return None, tr("Austrittsfläche der projizierten Zone")
        vorzeichen = 1 if d @ pl[1] > 0 else -1
        if (ende is not None and ende != vorzeichen) or abs((pl[0] - mitte) @ d - vorzeichen * laenge / 2) > 1e-5:
            return None, tr("Austrittsfläche der projizierten Zone")
        ende = vorzeichen
    if ende is None:
        return None, tr("Austrittsfläche der projizierten Zone")
    zentrum = mitte + ende * d * (laenge / 2 + offset + h / 2)
    return ("achse", zentrum, ende * d, float(h)), ""


def messmerkmal(angaben, form, merkmal, lage, form_fuer):
    """Torsor am Mittelpunkt des tatsaechlich tolerierten Achsenabschnitts aufstellen."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder

    if not any(getattr(p, "zone", "") == "Projected" for p in angaben):
        return merkmal, ""
    art, mitte, d, laenge = merkmal
    if art != "achse" or BRepAdaptor_Surface(form).GetType() != GeomAbs_Cylinder:
        return None, tr("Projizierte Zone ohne zylindrisches Messmerkmal")
    kanten = _kanten(form)
    abschnitte = []
    for p in angaben:
        if getattr(p, "zone", "") != "Projected":
            abschnitte.append(merkmal)
            continue
        intervall, hinweis = sichtintervall(p, mitte, d, laenge, form_fuer, lage)
        if hinweis:
            return None, hinweis
        if not any(_beruehren(kanten, _kanten(form_fuer(idx))) for idx in p.projektionsflaechen):
            return None, tr("Austrittsfläche der projizierten Zone")
        abschnitte.append(intervall)
    erster = abschnitte[0]
    if all(abs(a[3] - erster[3]) <= 1e-8 and np.linalg.norm(a[1] - erster[1]) <= 1e-8 for a in abschnitte):
        return erster, ""
    # Auf einer starren Geraden ist der Radialversatz zwischen den Enden linear.
    # Gleich grosse, ortsfeste Kreisscheiben binden daher nur an den beiden aeussersten Enden.
    durchmesser = {(p.wert, getattr(p, "material", ""), getattr(p, "maximum_toleranz", None)) for p in angaben}
    if len(durchmesser) != 1 or any(p.typ != "Position" for p in angaben):
        return None, tr("Verschiedene Geltungsbereiche der Achstoleranzen")
    lagen = [(float((o - mitte) @ d), h / 2) for _, o, _, h in abschnitte]
    unten = min(s - halb for s, halb in lagen)
    oben = max(s + halb for s, halb in lagen)
    return ("achse", mitte + d * ((unten + oben) / 2), d, oben - unten), ""
