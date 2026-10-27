"""Scan (Netz) gegen die PMI eines CAD-Modells pruefen: liegt die gemessene Oberflaeche in den Toleranzen?

Ablauf: Scan auf das CAD-Modell ausrichten (Bestpassung oder Punktpaare), jeden Scanpunkt der naechsten CAD-Flaeche
zuordnen (Netzsuche, Abstand exakt auf der B-Rep-Flaeche, Vorzeichen + = ausserhalb des Materials) und je PMI auswerten:
- Formtoleranzen und Profil ohne Bezug: Spannweite der Abstaende (Lage und Richtung frei) <= t.
- Richtungstoleranzen an Ebenen: Spannweite <= t (Annaeherung: Richtung zur Nennlage, Lage frei).
- Profil mit Bezug, Lauf, Position/Symmetrie an Flaechen: alle Abstaende in der (ggf. unsymmetrischen) Zone.
- Achszonen (Position, Koaxialitaet, Richtung mit Durchmesser) an Zylindern: Achsversatz und Radius je Element
  per Ausgleichsrechnung; Istwert = 2 x Achsversatz, zulaessig t plus Bonus bei M/L aus dem Istmass.
- Durchmesser und Radius: Istmass aus derselben Ausgleichsrechnung gegen Hoechst-/Mindestmass.
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
        elif p.art == "toleranz":
            durchmesser = "Diameter" in p.modifikatoren or p.zone == "Diameter"
            if durchmesser and (p.typ in tz.ACHSZONE or p.typ in tz.ACHSE_MIT_DURCHMESSER) and tz._achsen(flaechen):
                out.append(_achsen_auswertung(p, z, modell, flaechen, pmi, weite))
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
