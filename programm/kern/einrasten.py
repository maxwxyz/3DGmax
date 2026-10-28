"""Teil im Zusammenbau ziehen und dabei einrasten (wie CATIA Snap), PLAN §8.20 Punkt 5, ohne Qt.

Beim Ziehen bewegt sich das Teil nur in seinen offenen Freiheitsgraden (kern.verbindung): Verschiebungen werden auf
die freien Schieberichtungen projiziert; hat das Teil nur eine Drehung frei (Schraube mit Kopf und Schaft), dreht
das Ziehen um diese Achse. In jeder Lage werden Gegenstuecke gesucht:
- Ebene gegen Ebene: Normalen innerhalb WINKEL gegeneinander, Abstand entlang der Normalen hoechstens weite, die
  Flaechen liegen seitlich uebereinander (Mittenabstand in der Ebene kleiner als die halben Groessen zusammen);
- Achse auf Achse: Achsen innerhalb WINKEL parallel, Achsabstand hoechstens weite, gleiche Hoehe entlang der Achse,
  Radien hoechstens 15 % verschieden (Bolzen in Bohrung).
Der beste Kandidat wird gefangen (verbindung.fangen), aber nur, wenn die bisherigen Verbindungen des Teils dabei
erfuellt bleiben und er etwas Neues bindet (nicht schon aus den bisherigen Verbindungen folgt, z. B. eine zweite
Zylinderflaeche derselben Achse). Beim Loslassen wird daraus eine Verbindung (gleiche Regeln wie Baugruppe.verbinde).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import verbindung as vb

WINKEL = 5.0  # Grad: so nah muessen Richtungen kommen, damit gefangen wird


@dataclass
class Element:
    teil: int
    index: int  # Flaechenindex
    form: object  # Flaeche in Dateilage der Instanz
    art: str  # "ebene" | "achse"
    punkt: np.ndarray  # Dateilage
    richtung: np.ndarray
    mitte: np.ndarray  # Mitte des Huellquaders (Dateilage)
    groesse: float  # halbe Diagonale des Huellquaders
    radius: float = 0.0


@dataclass
class Kandidat:
    element: Element  # am gezogenen Teil
    gegen: Element
    art: str  # vb.EBEN | vb.KOAXIAL
    abstand: float  # Abstand vor dem Fangen (mm)


def _box(form):
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    b = Bnd_Box()
    brepbndlib.Add(form, b)
    if b.IsVoid():
        return None
    x0, y0, z0, x1, y1, z1 = b.Get()
    return np.array([x0, y0, z0]), np.array([x1, y1, z1])


def elemente(teil: int, form, modell) -> list[Element]:
    """Ebenen und Zylinder/Kegel der Teil-Instanz (Dateilage)."""
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    out, gesehen = [], set()
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        f = topods.Face(ex.Current())
        ex.Next()
        idx = modell.flaechen_index(f)
        if idx is None or idx in gesehen:
            continue
        gesehen.add(idx)
        try:
            m = vb.merkmal(f)
        except Exception:  # noqa: BLE001 - Netzflaechen ohne Geometrie
            m = None
        box = _box(f) if m is not None and m[0] in ("ebene", "achse") else None
        if box is None:
            continue
        a, b = box
        out.append(Element(teil, idx, f, m[0], m[1], m[2], (a + b) / 2, float(np.linalg.norm(b - a)) / 2,
                           vb.radius(f) if m[0] == "achse" else 0.0))
    return out


def _in_welt(e: Element, lage: np.ndarray):
    r, t = lage[:3, :3], lage[:3, 3]
    return r @ e.punkt + t, r @ e.richtung, r @ e.mitte + t


def suche(bewegt: list[Element], lage: np.ndarray, gegen: list[tuple[Element, np.ndarray]], weite: float,
          winkel: float = WINKEL) -> list[Kandidat]:
    """Moegliche Gegenstuecke, bestes zuerst. bewegt: Elemente des gezogenen Teils in der Lage lage; gegen:
    (Element, Lage des Teils) der uebrigen Teile."""
    cos = float(np.cos(np.radians(winkel)))
    welt = [(e, *_in_welt(e, l)) for e, l in gegen]
    out = []
    for e in bewegt:
        p, d, c = _in_welt(e, lage)
        for g, q, n, cg in welt:
            if g.art != e.art:
                continue
            if e.art == "ebene":
                if float(d @ n) > -cos:
                    continue
                abstand = abs(float((p - q) @ n))
                seitlich = (c - cg) - n * float((c - cg) @ n)
                if abstand > weite or float(np.linalg.norm(seitlich)) > e.groesse + g.groesse:
                    continue
                guete = abstand + weite * (1 + float(d @ n))
                out.append((guete, Kandidat(e, g, vb.EBEN, abstand)))
            else:
                if abs(float(d @ n)) < cos:
                    continue
                quer = (c - q) - n * float((c - q) @ n)
                abstand = float(np.linalg.norm(quer))
                hoehe = abs(float((c - cg) @ n))
                aehnlich = abs(e.radius - g.radius) <= 0.15 * max(e.radius, g.radius)
                if abstand > weite or hoehe > e.groesse + g.groesse or not aehnlich:
                    continue
                guete = abstand + weite * (1 - abs(float(d @ n)))
                out.append((guete, Kandidat(e, g, vb.KOAXIAL, abstand)))
    out.sort(key=lambda x: x[0])
    return [k for _, k in out]


def schieberichtungen(basis: np.ndarray) -> np.ndarray:
    """Orthonormale reine Verschiebungen im Raum der offenen Freiheitsgrade (m x 3)."""
    if basis is None or not len(basis):
        return np.zeros((0, 3))
    _, s, vt = np.linalg.svd(np.asarray(basis)[:, :3].T)
    rang = int((s > 1e-9).sum())
    c = vt[rang:]  # Koeffizienten ohne Drehanteil
    v = c @ np.asarray(basis)[:, 3:]
    if not len(v):
        return np.zeros((0, 3))
    q, r = np.linalg.qr(v.T)
    return q[:, np.abs(np.diag(r)) > 1e-9].T


def drehachse(basis: np.ndarray):
    """(Richtung, Punkt) der einzigen offenen Drehung, sonst None."""
    if basis is None or len(basis) != 1:
        return None
    art, a, p = vb._gerade_ausrichten(basis[0][:3], basis[0][3:])
    return (a, p) if art == "drehung" else None


def _strahl_ebene(strahl, punkt, normale):
    p, d = (np.asarray(x, float) for x in strahl)
    nenner = float(d @ normale)
    if abs(nenner) < 1e-12:
        return None
    return p + d * float((punkt - p) @ normale) / nenner


class Ziehen:
    """Ein Ziehvorgang: Startlage, offene Freiheitsgrade, Elemente; bewege() liefert die Lage (eingerastet)."""

    def __init__(self, baugruppe: vb.Baugruppe, teil: int, form, modell, andere: list[tuple[int, object]],
                 strahl, weite: float):
        """andere: (Knotennummer, Form) der sichtbaren uebrigen Teile; strahl: (Punkt, Richtung) unter der Maus beim
        Druecken; weite: Fangweite in mm."""
        self.b, self.teil, self.weite = baugruppe, teil, float(weite)
        self.start = np.array(baugruppe.lage(teil))
        self.basis = baugruppe.freiheitsgrade(teil)
        self.schiebe = schieberichtungen(self.basis)
        self.dreh = drehachse(self.basis) if not len(self.schiebe) else None
        self.bewegt = elemente(teil, form, modell)
        vorhanden = {(v.flaeche, v.gegen_teil, v.gegen_flaeche) for v in baugruppe.verbindungen if v.teil == teil} | \
            {(v.gegen_flaeche, v.teil, v.flaeche) for v in baugruppe.verbindungen if v.gegen_teil == teil}
        self.gegen = [(e, baugruppe.lage(nr)) for nr, f in andere if nr != teil for e in elemente(nr, f, modell)]
        self.vorhanden = vorhanden  # schon verbundene Flaechenpaare (nicht noch einmal fangen)
        box = _box(form)
        mitte = (box[0] + box[1]) / 2 if box is not None else np.zeros(3)
        mitte = self.start[:3, :3] @ mitte + self.start[:3, 3]
        p, d = (np.asarray(x, float) for x in strahl)
        self.blick = d / np.linalg.norm(d)
        self.griff = p + self.blick * float((mitte - p) @ self.blick)  # Strahlpunkt naechst der Teilmitte
        self.kandidat: Kandidat | None = None
        self.lage = self.start.copy()

    def frei(self) -> bool:
        return bool(len(self.schiebe)) or self.dreh is not None

    def _bewegung(self, strahl) -> np.ndarray:
        ziel = _strahl_ebene(strahl, self.griff, self.blick)
        m = np.eye(4)
        if ziel is None:
            return m
        weg = ziel - self.griff
        if len(self.schiebe):
            m[:3, 3] = self.schiebe.T @ (self.schiebe @ weg)
        elif self.dreh is not None:
            a, p = self.dreh
            hebel = self.griff - p - a * float((self.griff - p) @ a)
            r = float(np.linalg.norm(hebel))
            if r > 1e-9:
                tangente = np.cross(a, hebel / r)
                z = np.r_[a, -np.cross(a, p)]
                m = vb.bewegung(z, float(np.degrees(float(weg @ tangente) / r)))
        return m

    def _haelt(self, lage: np.ndarray) -> bool:
        """Bleiben die bisherigen Verbindungen des Teils in dieser Lage erfuellt?"""
        alt = self.b.lagen.get(self.teil)
        self.b.lagen[self.teil] = lage
        try:
            return not [v for v in self.b.verletzt() if self.teil in (v.teil, v.gegen_teil)]
        finally:
            if alt is None:
                self.b.lagen.pop(self.teil, None)
            else:
                self.b.lagen[self.teil] = alt

    def bewege(self, strahl) -> np.ndarray:
        """Lage fuer den Strahl unter der Maus: in den offenen Freiheitsgraden verschoben, dann eingerastet."""
        return self.einrasten(self._bewegung(strahl) @ self.start)

    def _bindet(self, k: Kandidat, ma, mb) -> bool:
        """Sperrt die Verbindung eine noch offene Bewegung? (sonst ueberzaehlig)"""
        if not len(self.basis):
            return False
        for zeile in vb.bedingungen(k.art, mb, ma):
            if np.abs(self.basis @ zeile).max() > 1e-6 * max(1.0, float(np.linalg.norm(zeile))):
                return True
        return False

    def einrasten(self, lage: np.ndarray) -> np.ndarray:
        """Lage (schon in den offenen Freiheitsgraden bewegt, z. B. vom 3D-Griff) am besten Gegenstueck fangen."""
        self.kandidat = None
        kandidaten = [k for k in suche(self.bewegt, lage, self.gegen, self.weite)
                      if (k.element.index, k.gegen.teil, k.gegen.index) not in self.vorhanden]
        for k in kandidaten[:8]:
            ma = vb.merkmal(k.element.form, lage)
            mb = vb.merkmal(k.gegen.form, self.b.lage(k.gegen.teil))
            gefangen = vb.fangen(ma, mb, k.art) @ lage
            if self._bindet(k, ma, mb) and self._haelt(gefangen):
                self.kandidat, lage = k, gefangen
                break
        self.lage = lage
        return lage

    def loslassen(self):
        """Lage uebernehmen; mit Kandidat eine Verbindung anlegen (Verbindung oder Fehlertext), sonst None."""
        self.b.lagen[self.teil] = self.lage
        k = self.kandidat
        if k is None:
            return None
        return self.b.verbinde(self.teil, k.element.form, k.element.index, k.gegen.teil, k.gegen.form, k.gegen.index)
