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


def _mantelnetz(p, form, form_fuer):
    """Kanten des zusammenhaengenden Mantels und aller zylindrischen Waende des Rahmens."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder
    f0 = tz._achse([form])
    if not f0 or not p.flaechen:
        return [], [], False
    start, d, laenge, r, _ = f0
    mitte = start + d * laenge / 2
    netz, alle = [], []
    for i in p.flaechen:
        f = form_fuer(i)
        achsdaten = tz._achse([f]) if f is not None else None
        if achsdaten is None or BRepAdaptor_Surface(f).GetType() != GeomAbs_Cylinder:
            continue
        o, achse, laenge_i, radius, _ = achsdaten
        kanten = _kanten(f)
        alle.extend(kanten)
        if (np.linalg.norm(np.cross(d, achse)) <= 1e-7 and abs(laenge_i - laenge) <= 1e-5 and
                abs(radius - r) <= 1e-5 and np.linalg.norm(o + achse * laenge_i / 2 - mitte) <= 1e-5):
            netz.append(kanten)
    # Gleiche Lage allein verbindet keine getrennten Koerper oder Zylinderschalen.
    erreicht = _kanten(form)
    anzahl = 0
    while netz:
        angrenzend = next((j for j, kanten in enumerate(netz) if _beruehren(erreicht, kanten)), None)
        if angrenzend is None:
            break
        erreicht.extend(netz.pop(angrenzend))
        anzahl += 1
    return erreicht, alle, anzahl == len(p.flaechen)


def einzelachse(p, form, form_fuer):
    _, _, einzeln = _mantelnetz(p, form, form_fuer)
    return einzeln


def sichtintervall(p, mitte, d, laenge, urspruenge, lage):
    """Projektionsrichtung und -laenge einer Achse anhand ihrer semantischen Austrittsflaechen."""
    from .baugruppe_mass import ebene

    h, offset = p.zonen_wert, getattr(p, "projektionsversatz", 0.)
    if h is None or not np.isfinite(h) or h <= 0 or offset is None or not np.isfinite(offset) or offset < 0:
        return None, tr("Höhe oder Versatz der projizierten Zone")
    # Der Ursprung muss am Ende des tatsaechlichen Mantels liegen. Die Materialnormale weist nach aussen.
    ende = None
    for f in urspruenge:
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


def _austritte_am_mantel(p, form, form_fuer):
    """Jeder Ursprung muss an einer tolerierten Wand liegen; nur lokale gelten fuer diese Achse."""
    urspruenge = [form_fuer(i) for i in getattr(p, "projektionsflaechen", ())]
    if not urspruenge or any(f is None for f in urspruenge):
        return []
    raender = [_kanten(f) for f in urspruenge]
    kanten = _kanten(form)
    if all(_beruehren(kanten, rand) for rand in raender):
        return urspruenge
    if len(p.flaechen) <= 1:
        return []
    mantel, alle, _ = _mantelnetz(p, form, form_fuer)
    if not all(_beruehren(alle, rand) for rand in raender):
        return []
    return [f for f, rand in zip(urspruenge, raender, strict=True) if _beruehren(mantel, rand)]


def messabschnitte(angaben, form, merkmal, lage, form_fuer):
    """Bezugsabschnitt des Torsors und normierte Teilintervalle in der Reihenfolge der PMI."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder

    if not any(getattr(p, "zone", "") == "Projected" for p in angaben):
        return merkmal, None, ""
    art, mitte, d, laenge = merkmal
    if art != "achse" or BRepAdaptor_Surface(form).GetType() != GeomAbs_Cylinder:
        return None, None, tr("Projizierte Zone ohne zylindrisches Messmerkmal")
    abschnitte = []
    for p in angaben:
        if getattr(p, "zone", "") != "Projected":
            abschnitte.append(merkmal)
            continue
        urspruenge = _austritte_am_mantel(p, form, form_fuer)
        intervall, hinweis = sichtintervall(p, mitte, d, laenge, urspruenge, lage)
        if hinweis:
            return None, None, hinweis
        abschnitte.append(intervall)
    erster = abschnitte[0]
    if all(a[3] == erster[3] and np.array_equal(a[1], erster[1]) for a in abschnitte):
        return erster, None, ""
    lagen = [(float((o - mitte) @ d), h / 2) for _, o, _, h in abschnitte]
    unten = min(s - halb for s, halb in lagen)
    oben = max(s + halb for s, halb in lagen)
    laenge = oben - unten
    if not np.isfinite(laenge) or laenge <= 0:
        return None, None, tr("Höhe oder Versatz der projizierten Zone")
    zentrum = unten + laenge / 2
    bereich = ("achse", mitte + d * zentrum, d, laenge)
    intervalle = [((s - halb - zentrum) / laenge, (s + halb - zentrum) / laenge) for s, halb in lagen]
    if any(not lo < hi for lo, hi in intervalle):
        return None, None, tr("Höhe oder Versatz der projizierten Zone")
    return bereich, intervalle, ""
