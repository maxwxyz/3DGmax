"""Scan (Netz) gegen die PMI eines CAD-Modells pruefen: liegt die gemessene Oberflaeche in den Toleranzen?

Ablauf: Scan auf das CAD-Modell ausrichten (Bestpassung oder Punktpaare), jeden Scanpunkt der naechsten CAD-Flaeche
zuordnen (Netzsuche, Abstand exakt auf der B-Rep-Flaeche, Vorzeichen + = ausserhalb des Materials) und je PMI auswerten:
- Formtoleranzen und Profil ohne Bezug: Spannweite der Abstaende (Lage und Richtung frei) <= t.
- Richtungstoleranzen an Ebenen: Spannweite <= t (Annaeherung: Richtung zur Nennlage, Lage frei).
- Profil mit Bezug, Lauf, Position/Symmetrie an Flaechen: alle Abstaende in der (ggf. unsymmetrischen) Zone.
- Achszonen (Position, Koaxialitaet, Richtung mit Durchmesser) an Zylindern: Achsversatz und Radius je Element
  per Ausgleichsrechnung; Istwert = 2 x Achsversatz, zulaessig t plus Bonus bei M/L aus dem Istmass.
- Durchmesser und Radius: Istmass aus derselben Ausgleichsrechnung gegen Hoechst-/Mindestmass.
- Laengenmasse zwischen Ebenen (oder Ebene und Achse): Flaechen nach Lage entlang der Normalen in zwei Seiten
  geteilt, je Seite Ausgleichsebene (bzw. Ausgleichsachse); Istmass = Abstand der Seiten entlang der Normalen.
- Winkelmasse: Flaechen nach Normalenrichtung in zwei Gruppen, Winkel zwischen den Normalen der Ausgleichsebenen.
- Rundheit und Rundlauf an Zylindern je Querschnitt (QUERSCHNITTE Scheiben entlang der Achse): Rundheit als
  Spannweite um den Ausgleichskreis des Schnitts, Rundlauf als Spannweite der Abstaende im Schnitt (Achse wie
  ausgerichtet); der schlechteste Schnitt zaehlt.
Die Bewertung ist eine Naeherung fuer die Sichtpruefung (keine normgerechte Auswertung nach Messstrategie).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..i18n import tr
from . import toleranzzone as tz

OK, NOK, GRENZ, OFFEN = "ok", "nok", "grenz", "offen"
UNSICHERHEIT = 0.005  # mm: naeher an der Grenze gilt "am Grenzwert" (Messunsicherheit des Scans)
FORM = {"Flatness", "Straightness", "CircularityOrRoundness", "Cylindricity"}
RICHTUNG = {"Parallelism", "Perpendicularity", "Angularity"}
QUERSCHNITTE = 10  # Scheiben je Element fuer Rundheit und Rundlauf
JE_QUERSCHNITT = {"CircularityOrRoundness", "CircularRunout"}


@dataclass
class Ergebnis:
    pmi: object
    status: str  # OK, NOK, GRENZ (innerhalb der Messunsicherheit an der Grenze), OFFEN (nicht auswertbar)
    ist: float | None = None  # Istwert (mm)
    zulaessig: float | None = None  # Grenze (mm)
    text: str = ""
    punkte: int = 0


@dataclass
class Zuordnung:
    punkte: np.ndarray  # Scanpunkte im CAD-System (n, 3)
    abstand: np.ndarray  # mit Vorzeichen (+ = ausserhalb des Materials)
    flaeche: np.ndarray  # Flaechenindex im CAD-Modell (-1 = keine)


def zuordnen(modell, punkte: np.ndarray, feinheit: float | None = None, nur: set[int] | None = None) -> Zuordnung:
    """Scanpunkte (schon im CAD-System) der naechsten CAD-Flaeche zuordnen, Abstand exakt auf der Flaeche.
    nur: Flaechenindizes, fuer die exakt gerechnet wird (die PMI-Flaechen); alle anderen Punkte behalten den
    Netzabstand und werden keiner Flaeche zugeordnet."""
    from .abweichung import _Flaeche, _feinheit, _flaechen_mit_lage
    from .ausrichten import NetzAbstand, tesselliere
    cad_f = _flaechen_mit_lage(modell.form)
    feinheit = feinheit or _feinheit(cad_f)
    netz = NetzAbstand(tesselliere(cad_f, feinheit))
    d, q, fl = netz.abfrage(punkte)
    normalen = netz.normalen(netz.letzte_dreiecke)
    vz = np.sign(np.einsum("ij,ij->i", punkte - q, normalen))
    abstand = d * np.where(vz == 0, 1.0, vz)
    exakt: dict[int, _Flaeche] = {}
    karte = [modell.flaechen_index(f) for f in cad_f]
    index = np.array([-1 if karte[int(f)] is None else karte[int(f)] for f in fl])
    for j, f in enumerate(fl):
        f = int(f)
        if nur is not None and index[j] not in nur:
            index[j] = -1
            continue
        if f not in exakt:
            exakt[f] = _Flaeche(cad_f[f], 2 * feinheit)
        if exakt[f].geom is None:
            continue  # Netzflaeche: Netzabstand
        w = exakt[f].projektion(punkte[j], innen=True)
        if w is None or abs(w[1] - d[j]) > 4 * feinheit + 0.05:
            index[j] = -1  # Fusspunkt ausserhalb der Berandung (Rundung, Fase, Kante): keiner Flaeche zuordnen
        else:
            abstand[j] = w[0]
    return Zuordnung(np.asarray(punkte, float), abstand, index)


def _auswahl(z: Zuordnung, flaechen: set[int], suchweite: float) -> np.ndarray:
    return np.isin(z.flaeche, list(flaechen)) & (np.abs(z.abstand) <= suchweite)


def _ausgleich_zylinder(p: np.ndarray, d: np.ndarray, start, richtung, innen: bool):
    """Achsversatz (Vektor senkrecht zur Achse) und Radiusaenderung aus den Abstaenden: d = s (r_dach . v + dr)."""
    q = p - start
    radial = q - np.outer(q @ richtung, richtung)
    radial /= np.maximum(np.linalg.norm(radial, axis=1), 1e-12)[:, None]
    s = -1.0 if innen else 1.0
    a = np.column_stack([radial * s, np.full(len(p), s)])
    x, *_ = np.linalg.lstsq(a, d, rcond=None)
    versatz = x[:3] - richtung * (x[:3] @ richtung)
    return versatz, float(x[3])


def _elemente(modell, flaechen):
    """Je Achse (Bohrung/Zapfen): (Start, Richtung, Radius, erste Flaeche, Flaechenindizes auf dieser Achse)."""
    out = []
    for start, richtung, _laenge, r, erste in tz._achsen(flaechen):
        idx = set()
        for f in flaechen:
            a = tz._achse([f])
            if a is not None and abs(a[1] @ richtung) > 0.9999 and \
                    np.linalg.norm(np.cross(a[0] - start, richtung)) < 1e-3:
                i = modell.flaechen_index(f)
                if i is not None:
                    idx.add(i)
        out.append((start, richtung, r, erste, idx))
    return out


def _achsen_auswertung(p, z: Zuordnung, modell, flaechen, alle_pmi, suchweite) -> Ergebnis:
    """Je Element Achsversatz und Istmass; das schlechteste Element bestimmt das Ergebnis."""
    t = float(p.wert or 0.0)
    schlechteste, gesamt = None, 0
    for start, richtung, r, erste, idx in _elemente(modell, flaechen):
        sel = _auswahl(z, idx, suchweite)
        if sel.sum() < 6:
            continue
        gesamt += int(sel.sum())
        innen = tz._ist_innen(erste, start, richtung)
        versatz, dr = _ausgleich_zylinder(z.punkte[sel], z.abstand[sel], start, richtung, innen)
        ist = 2 * float(np.linalg.norm(versatz))
        dmin, dmax = tz._groesse(p, alle_pmi, 2 * r)
        istmass = min(max(2 * (r + dr), dmin), dmax)
        zulaessig = t + max(0.0, tz._bonus(p.material, innen, istmass, dmin, dmax))
        if schlechteste is None or ist - zulaessig > schlechteste[0] - schlechteste[1]:
            schlechteste = (ist, zulaessig)
    if schlechteste is None:
        return Ergebnis(p, OFFEN, text=tr("zu wenige Scanpunkte"))
    ist, zul = schlechteste
    return Ergebnis(p, _status(ist - zul), ist, zul, tr("Achsversatz ⌀{:.4g} (zulässig ⌀{:.4g})").format(ist, zul),
                    gesamt)


def _mass_auswertung(p, z: Zuordnung, modell, flaechen, suchweite) -> Ergebnis:
    """Istmass je Element (Ausgleichszylinder); das am weitesten ausserhalb liegende bestimmt das Ergebnis."""
    hoechst, mindest = p.grenzen()
    if hoechst is None or p.nennwert is None:
        return Ergebnis(p, OFFEN, text=tr("ohne Grenzmaße"))
    faktor = 2.0 if p.typ in ("Size_Diameter", "Size_SphericalDiameter") else 1.0
    schlechteste, gesamt = None, 0
    for start, richtung, r, erste, idx in _elemente(modell, flaechen):
        sel = _auswahl(z, idx, suchweite)
        if sel.sum() < 6:
            continue
        gesamt += int(sel.sum())
        _, dr = _ausgleich_zylinder(z.punkte[sel], z.abstand[sel], start, richtung, tz._ist_innen(erste, start, richtung))
        ist = (r + dr) * faktor
        ueber = max(ist - hoechst, mindest - ist)
        if schlechteste is None or ueber > schlechteste[1]:
            schlechteste = (ist, ueber)
    if schlechteste is None:
        return Ergebnis(p, OFFEN, text=tr("nur für Zylinder auswertbar"))
    ist = schlechteste[0]
    return Ergebnis(p, _status(schlechteste[1]), ist, hoechst - mindest,
                    tr("Istmaß {:.4f} (Grenzen {:.4f} … {:.4f})").format(ist, mindest, hoechst), gesamt)


def _flaechen_auswertung(p, z: Zuordnung, suchweite) -> Ergebnis:
    sel = _auswahl(z, set(p.flaechen), suchweite)
    if sel.sum() < 6:
        return Ergebnis(p, OFFEN, text=tr("zu wenige Scanpunkte"))
    d = z.abstand[sel]
    t = float(p.wert)
    frei = p.typ in FORM or p.typ in RICHTUNG or (p.typ in ("ProfileOfSurface", "ProfileOfLine") and not p.bezuege)
    if frei:  # Lage frei: Spannweite gegen die Zonenbreite
        ist = float(d.max() - d.min())
        return Ergebnis(p, _status(ist - t), ist, t,
                        tr("Spannweite {:.4g} (zulässig {:.4g})").format(ist, t), int(sel.sum()))
    aussen, innen = tz._grenzen_aussen_innen(p, t)
    mitte = (aussen + innen) / 2
    ist = 2 * float(np.abs(d - mitte).max())
    return Ergebnis(p, _status(max(d.max() - aussen, innen - d.min())), ist, t,
                    tr("Abweichung {:+.4g} … {:+.4g} (Zone {:+.4g} … {:+.4g})").format(d.min(), d.max(), innen, aussen),
                    int(sel.sum()))


def _querschnitt_auswertung(p, z: Zuordnung, modell, flaechen, suchweite) -> Ergebnis | None:
    """Rundheit/Rundlauf je Querschnitt an Zylinderelementen; None, wenn es keine Achse gibt (dann flaechig)."""
    elemente = _elemente(modell, flaechen)
    if not elemente:
        return None
    t = float(p.wert)
    schlechtester, anzahl, n_punkte = None, 0, 0
    for start, richtung, _r, _erste, idx in elemente:
        sel = _auswahl(z, idx, suchweite)
        if sel.sum() < 12:
            continue
        pts, d = z.punkte[sel], z.abstand[sel]
        lage = (pts - start) @ richtung
        kanten = np.linspace(lage.min(), lage.max(), QUERSCHNITTE + 1)
        innen = _ist_innen_element(modell, idx, start, richtung)
        for k in range(QUERSCHNITTE):
            im = (lage >= kanten[k]) & (lage <= kanten[k + 1])
            if im.sum() < 6:
                continue
            dd = d[im]
            if p.typ == "CircularityOrRoundness":  # Ausgleichskreis des Schnitts: Mitte und Radius frei
                versatz, dr = _ausgleich_zylinder(pts[im], dd, start, richtung, innen)
                q = pts[im] - start
                radial = q - np.outer(q @ richtung, richtung)
                radial /= np.maximum(np.linalg.norm(radial, axis=1), 1e-12)[:, None]
                dd = dd - (-1.0 if innen else 1.0) * (radial @ versatz + dr)
            spanne = float(dd.max() - dd.min())
            anzahl += 1
            n_punkte += int(im.sum())
            if schlechtester is None or spanne > schlechtester[0]:
                schlechtester = (spanne, float((kanten[k] + kanten[k + 1]) / 2))
    if schlechtester is None:
        return Ergebnis(p, OFFEN, text=tr("zu wenige Scanpunkte"))
    ist, lage = schlechtester
    return Ergebnis(p, _status(ist - t), ist, t, tr("je Querschnitt: schlechtester bei {:.1f} mm entlang der Achse, "
                                                     "Spannweite {:.4g} (zulässig {:.4g}, {} Schnitte)").format(
        lage, ist, t, anzahl), n_punkte)


def _ist_innen_element(modell, idx, start, richtung) -> bool:
    i = min(idx)
    return tz._ist_innen(modell.flaechen[i], start, richtung) if i < len(modell.flaechen) else False


def _ausgleich_ebene(p: np.ndarray):
    """Schwerpunkt und Normale der Ausgleichsebene (kleinster Singulaerwert)."""
    c = p.mean(axis=0)
    _, _, vt = np.linalg.svd(p - c, full_matrices=False)
    return c, vt[2]


def _seiten(modell, flaechen: set[int]):
    """Ebene und Zylinderflaechen eines Masses nach Lage entlang der Normalen der ersten Ebene: (Richtung,
    [(Lage, Flaechen, Art)]) mit zwei Eintraegen oder None."""
    from .toleranzkette import _ebene_oder_achse, lage
    geo = {i: _ebene_oder_achse(modell.flaechen[i]) for i in flaechen if i < len(modell.flaechen)}
    ebene = next((g for g in geo.values() if g is not None and g[0] == "ebene"), None)
    if ebene is None:
        return None
    n = ebene[2] / np.linalg.norm(ebene[2])
    gruppen: list[list] = []
    for i, g in geo.items():
        o = lage(modell.flaechen[i], n) if g is not None else None
        if o is None:
            continue
        for gr in gruppen:
            if abs(gr[0] - o) < 1e-4 and gr[2] == g[0]:
                gr[1].add(i)
                break
        else:
            gruppen.append([o, {i}, g[0]])
    if len(gruppen) < 2:
        return None
    gruppen.sort(key=lambda gr: gr[0])
    return n, [gruppen[0], gruppen[-1]]


def _abstand_auswertung(p, z: Zuordnung, modell, suchweite) -> Ergebnis:
    """Abstand der zwei Seiten eines Laengenmasses entlang der Normalen (Ausgleichsebenen bzw. -achsen)."""
    hoechst, mindest = p.grenzen()
    if hoechst is None or p.nennwert is None:
        return Ergebnis(p, OFFEN, text=tr("ohne Grenzmaße"))
    seiten = _seiten(modell, set(p.flaechen))
    if seiten is None:
        return Ergebnis(p, OFFEN, text=tr("Seiten des Maßes nicht als Ebenen/Achsen erkennbar"))
    n, (a, b) = seiten
    orte, gesamt = [], 0
    for _o, idx, art in (a, b):
        sel = _auswahl(z, idx, suchweite)
        if sel.sum() < 6:
            return Ergebnis(p, OFFEN, text=tr("zu wenige Scanpunkte"))
        gesamt += int(sel.sum())
        pts = z.punkte[sel]
        if art == "ebene":
            c, _nn = _ausgleich_ebene(pts)
            orte.append(float(c @ n))
        else:  # Achse: Ausgleichszylinder, Lage des verschobenen Achspunkts
            el = next((e for e in _elemente(modell, [modell.flaechen[i] for i in idx])), None)
            if el is None:
                return Ergebnis(p, OFFEN, text=tr("zu wenige Scanpunkte"))
            start, richtung, _r, erste, _i = el
            versatz, _dr = _ausgleich_zylinder(pts, z.abstand[sel], start, richtung,
                                               tz._ist_innen(erste, start, richtung))
            orte.append(float((start + versatz) @ n))
    ist = abs(orte[1] - orte[0])
    ueber = max(ist - hoechst, mindest - ist)
    return Ergebnis(p, _status(ueber), ist, hoechst - mindest,
                    tr("Istmaß {:.4f} (Grenzen {:.4f} … {:.4f})").format(ist, mindest, hoechst), gesamt)


def _winkel_auswertung(p, z: Zuordnung, modell, suchweite) -> Ergebnis:
    """Winkel zwischen zwei Flaechengruppen (Ausgleichsebenen), naeher am Nennwinkel von w und 180 - w."""
    from .toleranzkette import _ebene_oder_achse
    hoechst, mindest = p.grenzen()
    if hoechst is None or p.nennwert is None:
        return Ergebnis(p, OFFEN, text=tr("ohne Grenzmaße"))
    gruppen: list[list] = []
    for i in sorted(p.flaechen):
        g = _ebene_oder_achse(modell.flaechen[i]) if i < len(modell.flaechen) else None
        if g is None or g[0] != "ebene":
            continue
        for gr in gruppen:
            if abs(abs(float(gr[0] @ g[2])) - 1) < 1e-6:
                gr[1].add(i)
                break
        else:
            gruppen.append([g[2], {i}])
    if len(gruppen) != 2:
        return Ergebnis(p, OFFEN, text=tr("Winkel nur zwischen zwei ebenen Flächengruppen auswertbar"))
    normalen, gesamt = [], 0
    for _n, idx in gruppen:
        sel = _auswahl(z, idx, suchweite)
        if sel.sum() < 6:
            return Ergebnis(p, OFFEN, text=tr("zu wenige Scanpunkte"))
        gesamt += int(sel.sum())
        normalen.append(_ausgleich_ebene(z.punkte[sel])[1])
    w = float(np.degrees(np.arccos(np.clip(abs(normalen[0] @ normalen[1]), -1, 1))))
    ist = min((w, 180 - w), key=lambda x: abs(x - p.nennwert))
    ueber = max(ist - hoechst, mindest - ist)
    return Ergebnis(p, _status(ueber * np.pi / 180 * 10), ist, hoechst - mindest,  # Unsicherheit ~ 0.005 mm/10 mm
                    tr("Istwinkel {:.3f}° (Grenzen {:.3f}° … {:.3f}°)").format(ist, mindest, hoechst), gesamt)


def pmi_flaechen(pmi: list) -> set[int]:
    """Flaechen aller auswertbaren PMI (fuer zuordnen(nur=...))."""
    return {i for p in pmi if p.art in ("mass", "toleranz") for i in p.flaechen}


def bewerte(pmi: list, modell, z: Zuordnung, suchweite: float | None = None) -> list[Ergebnis]:
    """Je Toleranz/Mass mit Flaechen ein Ergebnis; suchweite: Punkte weiter weg gehoeren nicht zur Flaeche."""
    out = []
    for p in pmi:
        if not p.flaechen or (p.art == "toleranz" and p.wert is None):
            continue
        flaechen = [modell.flaechen[i] for i in sorted(p.flaechen) if i < len(modell.flaechen)]
        weite = suchweite or max(1.0, 5 * float(p.wert or 0.0))
        if p.art == "mass" and p.typ in tz.GROESSE:
            out.append(_mass_auswertung(p, z, modell, flaechen, weite))
        elif p.art == "mass" and "Angular" in (p.typ or ""):
            out.append(_winkel_auswertung(p, z, modell, weite))
        elif p.art == "mass" and p.nennwert is not None:
            out.append(_abstand_auswertung(p, z, modell, weite))
        elif p.art == "toleranz":
            durchmesser = "Diameter" in p.modifikatoren or p.zone == "Diameter"
            if durchmesser and (p.typ in tz.ACHSZONE or p.typ in tz.ACHSE_MIT_DURCHMESSER) and tz._achsen(flaechen):
                out.append(_achsen_auswertung(p, z, modell, flaechen, pmi, weite))
            elif p.typ in JE_QUERSCHNITT and (e := _querschnitt_auswertung(p, z, modell, flaechen, weite)):
                out.append(e)
            elif p.typ in tz.FLAECHENZONE or p.typ in tz.ACHSZONE:
                out.append(_flaechen_auswertung(p, z, weite))
    return out


def _fuss_normale(geom, p):
    """Fusspunkt und Normale (Richtung der Flaechenparametrisierung) der Projektion auf die Flaeche oder None."""
    from OCC.Core.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCC.Core.gp import gp_Pnt, gp_Vec
    pr = GeomAPI_ProjectPointOnSurf(gp_Pnt(*map(float, p)), geom)
    if not pr.IsDone() or pr.NbPoints() == 0:
        return None
    u, v = pr.LowerDistanceParameters()
    q, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
    geom.D1(u, v, q, du, dv)
    n = du.Crossed(dv)
    if n.Magnitude() < 1e-12:
        return None
    n.Normalize()
    return np.array([q.X(), q.Y(), q.Z()]), np.array([n.X(), n.Y(), n.Z()])


def feinausrichten(modell, scan_punkte: np.ndarray, matrix: np.ndarray, anzahl: int = 4000,
                   schritte: int = 6) -> np.ndarray:
    """Bestpassung verfeinern: Punkt-zu-Ebene gegen die exakten CAD-Flaechen (die Netzsuche liefert nur den
    Kandidaten). Die Grobausrichtung ist durch die Sehnen des Anzeigenetzes begrenzt (etwa 0.01-0.05 mm)."""
    from OCC.Core.BRep import BRep_Tool
    from .abweichung import _feinheit, _flaechen_mit_lage
    from .ausrichten import NetzAbstand, _drehung, _matrix, tesselliere
    cad_f = _flaechen_mit_lage(modell.form)
    netz = NetzAbstand(tesselliere(cad_f, _feinheit(cad_f)))
    geom = [BRep_Tool.Surface(f) for f in cad_f]
    b = scan_punkte
    if len(b) > anzahl:
        b = b[np.random.default_rng(3).choice(len(b), anzahl, replace=False)]
    m = matrix.copy()
    for _ in range(schritte):
        bt = b @ m[:3, :3].T + m[:3, 3]
        d, _, fl = netz.abfrage(bt)
        zeilen, rechts = [], []
        grenze = np.quantile(d, 0.9)
        for j in np.nonzero(d <= grenze)[0]:
            g = geom[int(fl[j])]
            fn = None if g is None else _fuss_normale(g, bt[j])
            if fn is None:
                continue
            q, n = fn
            zeilen.append(np.concatenate([np.cross(bt[j], n), n]))
            rechts.append(float(n @ (q - bt[j])))
        if len(zeilen) < 6:
            break
        x, *_ = np.linalg.lstsq(np.array(zeilen), np.array(rechts), rcond=None)
        m = _matrix(_drehung(*x[:3]), x[3:]) @ m
        if np.linalg.norm(x) < 1e-9:
            break
    return m


def _status(ueber: float) -> str:
    """Ueberschreitung der Grenze (mm, <= 0: eingehalten) -> Status mit Messunsicherheit."""
    if abs(ueber) <= UNSICHERHEIT:
        return GRENZ
    return OK if ueber < 0 else NOK


def scan_punkte(scan_modell, ausrichtung, anzahl: int = 200000) -> np.ndarray:
    """Knoten des Scans (gleichmaessig ausgeduennt) im CAD-System (ausrichtung: Ausrichtung, 4x4-Matrix oder None)."""
    from .ausrichten import tesselliere
    netze = tesselliere(scan_modell.flaechen)
    p = np.vstack([q for q, _ in netze if len(q)]) if netze else np.zeros((0, 3))
    if len(p) > anzahl:
        p = p[np.random.default_rng(1).choice(len(p), anzahl, replace=False)]
    if ausrichtung is None:
        return p
    m = getattr(ausrichtung, "matrix", ausrichtung)
    return p @ m[:3, :3].T + m[:3, 3]


# --- Ausrichtung am Bezugssystem (3-2-1) ---

def bezugssysteme(pmi: list) -> list[tuple[str, ...]]:
    """Bezugssysteme der Toleranzen (z. B. ('A', 'B', 'C')), haeufigste und vollstaendigste zuerst."""
    zaehler: dict[tuple, int] = {}
    for p in pmi:
        if p.art == "toleranz" and p.bezuege:
            drf = tuple(b.name for b in sorted(p.bezuege, key=lambda b: b.stelle))
            zaehler[drf] = zaehler.get(drf, 0) + 1
    return sorted(zaehler, key=lambda d: (-len(d), -zaehler[d], d))


def bezug_flaechen(pmi: list, name: str) -> set[int]:
    """Flaechen eines Bezugs; gemeinsamer Bezug 'A-B' vereinigt beide Elemente."""
    teile = set(name.split("-"))
    return {i for p in pmi if p.art == "bezug" and p.typ == "Datum" and p.name in teile for i in p.flaechen}


def _nullraum(j: np.ndarray, tol: float = 1e-9) -> np.ndarray:
    """Basis (Spalten) der Bewegungen, die die Zeilen j nicht aendern."""
    _, s, vt = np.linalg.svd(j)
    rang = int((s > tol * max(1.0, float(s.max()) if len(s) else 1.0)).sum())
    return vt[rang:].T


def _anlage(j: np.ndarray, rechts: np.ndarray) -> np.ndarray | None:
    """Anlage nach ISO 5459 (Tschebyscheff mit Nebenbedingung): Bewegung z, nach der alle Punkte im Material oder
    auf der Bezugsflaeche liegen (rechts - j z >= 0, rechts: Tiefe unter der nach aussen zeigenden Flaeche) und der
    groesste Abstand minimal ist."""
    from scipy.optimize import linprog
    k = j.shape[1]
    c = np.r_[np.zeros(k), 1.0]
    a = np.vstack([np.c_[j, np.zeros(len(j))], np.c_[-j, -np.ones(len(j))]])
    b = np.r_[rechts, -rechts]
    erg = linprog(c, A_ub=a, b_ub=b, bounds=[(None, None)] * k + [(0, None)], method="highs")
    return erg.x[:k] if erg.status == 0 else None


def richte_nach_bezug(modell, scan_punkte: np.ndarray, matrix: np.ndarray, stufen: list[set[int]],
                      suchweite: float = 0.5, anzahl: int = 2000, schritte: int = 8, anlage: bool = False) -> np.ndarray:
    """Scan am Bezugssystem ausrichten: Primaerbezug passt in seinen Freiheitsgraden, Sekundaer- und Tertiaerbezug
    nur noch in den verbliebenen. Gauss-Ausgleich je Bezug oder (anlage) die anliegende Bezugsflaeche nach ISO 5459:
    aussen am Material, groesster Abstand minimal (empfindlich fuer Ausreisser im Scan)."""
    from OCC.Core.BRep import BRep_Tool
    from .ausrichten import NetzAbstand, _drehung, _matrix, tesselliere
    netze = []
    for flaechen in stufen:
        formen = [modell.flaechen[i] for i in sorted(flaechen) if i < len(modell.flaechen)]
        if formen:
            netze.append((NetzAbstand(tesselliere(formen)), [BRep_Tool.Surface(f) for f in formen]))
    m = matrix.copy()
    if anlage:  # die Anlage haengt an den aeussersten Punkten: nicht ausduennen
        anzahl = max(anzahl, 20000)
    # je Bezug nur Punkte in seiner Naehe (einmal vorausgewaehlt, die Lage aendert sich nur wenig), hoechstens anzahl
    start = scan_punkte @ m[:3, :3].T + m[:3, 3]
    proben = []
    for netz, _ in netze:
        idx = np.nonzero(netz.in_der_naehe(start, 2 * suchweite))[0]
        if len(idx) > anzahl:
            idx = np.random.default_rng(5).choice(idx, anzahl, replace=False)
        proben.append(scan_punkte[idx])
    for _ in range(schritte):
        frei = np.eye(6)
        x = np.zeros(6)
        for (netz, geom), b in zip(netze, proben):
            if frei.shape[1] == 0:
                break
            bt = b @ m[:3, :3].T + m[:3, 3]
            if not len(bt):
                continue
            d, _, fl = netz.abfrage(bt)
            aussen = netz.normalen(netz.letzte_dreiecke)  # Netznormalen zeigen aus dem Material
            zeilen, rechts = [], []
            for k in np.nonzero(d <= suchweite)[0]:
                g = geom[int(fl[k])]
                fn = None if g is None else _fuss_normale(g, bt[k])
                if fn is None:
                    continue
                q, n = fn
                if abs(abs(float(n @ (q - bt[k]))) - d[k]) > 0.02:
                    continue  # Fusspunkt ausserhalb der Flaeche (Nachbarflaeche am Rand): nicht zum Bezug
                if anlage and float(n @ aussen[k]) < 0:
                    n = -n  # nach aussen: rechts > 0 heisst im Material
                zeilen.append(np.concatenate([np.cross(bt[k], n), n]))
                rechts.append(float(n @ (q - bt[k])))
            if len(zeilen) < 3:
                continue
            j = np.array(zeilen) @ frei
            z = _anlage(j, np.array(rechts)) if anlage else None
            if z is None:
                z, *_ = np.linalg.lstsq(j, np.array(rechts), rcond=None)
            x += frei @ z
            frei = frei @ _nullraum(j)
        if np.linalg.norm(x) < 1e-10:
            break
        m = _matrix(_drehung(*x[:3]), x[3:]) @ m
    return m
