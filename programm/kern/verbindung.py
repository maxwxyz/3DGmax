"""Verbindungen zwischen Teilen einer Baugruppe: Fangen und offene Freiheitsgrade (ohne Qt), PLAN §8.20 Stufe 1.

Eine Verbindung bindet eine Flaeche eines beweglichen Teils an eine Flaeche eines anderen Teils:
- eben: Ebene auf Ebene, Normalen gegeneinander, Abstand = Versatz (0: Beruehrung);
- koaxial: Zylinder- oder Kegelachse auf Achse.
Fangen bewegt das Teil so, dass die Verbindung erfuellt ist. Die Freiheitsgrade eines Teils folgen aus den kleinen
Bewegungen (Drehung w, Verschiebung v am Ursprung; ein Punkt p bewegt sich um v + w x p), die alle seine Verbindungen
zulassen: eben verbietet die Verschiebung entlang der Normalen und das Kippen um die zwei Achsen in der Ebene
(3 Bedingungen), koaxial die Querbewegung zweier Achspunkte (4 Bedingungen). Offene Freiheitsgrade = Nullraum,
die Gegenteile gelten dabei als fest.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..i18n import tr

EBEN, KOAXIAL = "eben", "koaxial"
ART_TEXT = {EBEN: "Ebene auf Ebene", KOAXIAL: "koaxial"}


@dataclass
class Verbindung:
    nummer: int
    teil: int  # Knotennummer des bewegten Teils
    flaeche: int  # Flaechenindex am bewegten Teil
    gegen_teil: int
    gegen_flaeche: int
    art: str
    versatz: float = 0.0  # mm, nur eben


def merkmal(flaeche, lage: np.ndarray | None = None):
    """('ebene', Punkt, Normale aus dem Material) oder ('achse', Punkt, Richtung) in Weltlage, sonst None."""
    from .toleranzkette import _aussen_normale, _ebene_oder_achse
    g = _ebene_oder_achse(flaeche)
    if g is None:
        return None
    art, p, d = g
    if art == "ebene":
        d = _aussen_normale(flaeche)
    if lage is not None:
        p = lage[:3, :3] @ p + lage[:3, 3]
        d = lage[:3, :3] @ d
    return art, p, d / np.linalg.norm(d)


def art_fuer(a, b) -> str | None:
    if a is None or b is None or a[0] != b[0]:
        return None
    return EBEN if a[0] == "ebene" else KOAXIAL


def _drehung(von: np.ndarray, nach: np.ndarray) -> np.ndarray:
    """Kleinste Drehung, die die Richtung von auf nach dreht (3x3)."""
    von, nach = von / np.linalg.norm(von), nach / np.linalg.norm(nach)
    c = float(von @ nach)
    if c > 1 - 1e-12:
        return np.eye(3)
    if c < -1 + 1e-12:  # Gegenrichtung: 180 Grad um eine Senkrechte
        s = _senkrechte(von)[0]
        return 2 * np.outer(s, s) - np.eye(3)
    k = np.cross(von, nach)
    kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + kx + kx @ kx / (1 + c)


def _senkrechte(n: np.ndarray):
    a = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    t1 = np.cross(n, a)
    t1 /= np.linalg.norm(t1)
    return t1, np.cross(n, t1)


def fangen(m_teil, m_gegen, art: str, versatz: float = 0.0) -> np.ndarray:
    """Bewegung (4x4, Welt) des Teils, die seine Flaeche auf die Gegenflaeche bringt (Merkmale in Weltlage)."""
    _, p, d = m_teil
    _, q, e = m_gegen
    if art == EBEN:
        r = _drehung(d, -e)  # Normalen gegeneinander
    else:
        r = _drehung(d, e if d @ e >= 0 else -e)  # Achse auf Achse, kleinere Drehung
    p2 = r @ p
    if art == EBEN:
        t = e * (float((q - p2) @ e) + versatz)  # nur entlang der Normalen: Lage in der Ebene bleibt
    else:
        quer = (q - p2) - e * float((q - p2) @ e)  # nur quer zur Achse: Lage entlang der Achse bleibt
        t = quer
    m = np.eye(4)
    m[:3, :3] = r
    m[:3, 3] = t
    return m


def bedingungen(art: str, m_gegen) -> list[np.ndarray]:
    """Zeilen (w, v) der gesperrten kleinen Bewegungen fuer ein Teil an dieser Verbindung."""
    _, q, e = m_gegen
    t1, t2 = _senkrechte(e)
    if art == EBEN:
        return [np.r_[np.cross(q, e), e], np.r_[np.cross(t1, e), 0, 0, 0], np.r_[np.cross(t2, e), 0, 0, 0]]
    return [np.r_[np.cross(p, u), u] for p in (q, q + e) for u in (t1, t2)]


def freiheitsgrade(zeilen: list[np.ndarray]) -> np.ndarray:
    """Basis der offenen Bewegungen (k x 6, je Zeile w, v)."""
    if not zeilen:
        return np.eye(6)
    _, s, vt = np.linalg.svd(np.array(zeilen))
    rang = int((s > 1e-9 * max(1.0, float(s.max()))).sum())
    return vt[rang:]


def _gerade_ausrichten(w: np.ndarray, v: np.ndarray):
    """Offene Bewegung lesbar machen: reine Verschiebung oder Drehung um eine Achse (Richtung, Punkt)."""
    if np.linalg.norm(w) < 1e-9:
        return "verschiebung", v / np.linalg.norm(v), None
    a = w / np.linalg.norm(w)
    punkt = np.cross(w, v) / float(w @ w)  # Punkt der Drehachse (v = -w x p)
    return "drehung", a, punkt


def beschreibe(basis: np.ndarray) -> list[str]:
    """Kurztexte der offenen Freiheitsgrade, z. B. 'Drehung um (0, 0, 1)'."""
    out = []
    for z in basis:
        art, richtung, _ = _gerade_ausrichten(z[:3], z[3:])
        r = ", ".join(f"{x:.2g}" for x in np.round(richtung, 3) + 0.0)
        out.append((tr("Verschiebung entlang ({})") if art == "verschiebung" else tr("Drehung um ({})")).format(r))
    return out


def bewegung(z: np.ndarray, betrag: float, um: np.ndarray | None = None) -> np.ndarray:
    """4x4 der Bewegung entlang eines Freiheitsgrads: Verschiebung in mm bzw. Drehung in Grad um ihre Achse."""
    art, richtung, punkt = _gerade_ausrichten(z[:3], z[3:])
    m = np.eye(4)
    if art == "verschiebung":
        m[:3, 3] = richtung * betrag
        return m
    phi = np.radians(betrag)
    k = np.array([[0, -richtung[2], richtung[1]], [richtung[2], 0, -richtung[0]], [-richtung[1], richtung[0], 0]])
    r = np.eye(3) + np.sin(phi) * k + (1 - np.cos(phi)) * k @ k
    m[:3, :3] = r
    m[:3, 3] = punkt - r @ punkt
    return m


def erfuellt(art: str, m_teil, m_gegen, versatz: float = 0.0, tol: float = 1e-4) -> bool:
    """Verbindung in der aktuellen Lage erfuellt (Richtungen und Abstand)?"""
    _, p, d = m_teil
    _, q, e = m_gegen
    if art == EBEN:
        return float(d @ e) < -1 + 1e-6 and abs(float((p - q) @ e) - versatz) < tol
    quer = (p - q) - e * float((p - q) @ e)
    return abs(abs(float(d @ e)) - 1) < 1e-6 and float(np.linalg.norm(quer)) < tol


class Baugruppe:
    """Verbindungen und Lagen der Teile (Knotennummer -> 4x4 relativ zur Lage in der Datei)."""

    def __init__(self):
        self.verbindungen: list[Verbindung] = []
        self.lagen: dict[int, np.ndarray] = {}
        self.formen: dict[int, tuple] = {}  # Nummer der Verbindung -> (Flaeche am Teil, Gegenflaeche), Dateilage

    def lage(self, teil: int) -> np.ndarray:
        return self.lagen.get(teil, np.eye(4))

    def merkmale(self, v: Verbindung):
        fa, fb = self.formen[v.nummer]
        return merkmal(fa, self.lage(v.teil)), merkmal(fb, self.lage(v.gegen_teil))

    def verbinde(self, teil: int, flaeche, index: int, gegen_teil: int, gegen_flaeche, gegen_index: int,
                 versatz: float = 0.0) -> Verbindung | str:
        """Teil an die Gegenflaeche fangen und die Verbindung merken; Fehlertext bei unpassender Auswahl."""
        if teil == gegen_teil:
            return tr("Die zwei Flächen müssen zu verschiedenen Teilen gehören")
        ma, mb = merkmal(flaeche, self.lage(teil)), merkmal(gegen_flaeche, self.lage(gegen_teil))
        art = art_fuer(ma, mb)
        if art is None:
            return tr("Verbinden geht für zwei Ebenen oder zwei Zylinder-/Kegelflächen")
        self.lagen[teil] = fangen(ma, mb, art, versatz) @ self.lage(teil)
        v = Verbindung(max((x.nummer for x in self.verbindungen), default=0) + 1, teil, index, gegen_teil,
                       gegen_index, art, versatz if art == EBEN else 0.0)
        self.verbindungen.append(v)
        self.formen[v.nummer] = (flaeche, gegen_flaeche)
        return v

    def verletzt(self) -> list[Verbindung]:
        """Verbindungen, die in der aktuellen Lage nicht (mehr) erfuellt sind."""
        return [v for v in self.verbindungen if not erfuellt(v.art, *self.merkmale(v), v.versatz)]

    def freiheitsgrade(self, teil: int) -> np.ndarray:
        """Offene Bewegungen des Teils gegen seine (als fest angenommenen) Verbindungspartner."""
        zeilen = []
        for v in self.verbindungen:
            if teil not in (v.teil, v.gegen_teil):
                continue
            ma, mb = self.merkmale(v)
            zeilen += bedingungen(v.art, mb if v.teil == teil else ma)
        return freiheitsgrade(zeilen)

    def teile(self) -> list[int]:
        return sorted({t for v in self.verbindungen for t in (v.teil, v.gegen_teil)})

    def fest(self, teil: int) -> bool:
        """Bezugsteil: nur Gegenteil, nie bewegt."""
        return all(v.teil != teil for v in self.verbindungen)

    def entferne(self, nummer: int):
        self.verbindungen = [v for v in self.verbindungen if v.nummer != nummer]
        self.formen.pop(nummer, None)

    def zuruecksetzen(self):
        self.verbindungen, self.lagen, self.formen = [], {}, {}

    def als_dict(self) -> dict:
        from dataclasses import asdict
        return {"verbindungen": [asdict(v) for v in self.verbindungen],
                "lagen": {str(k): np.asarray(m).tolist() for k, m in self.lagen.items()}}

    def lade(self, d: dict, flaeche_von):
        """Aus als_dict(); flaeche_von(teil, index) liefert die Flaeche der Instanz in Dateilage."""
        self.zuruecksetzen()
        self.lagen = {int(k): np.array(m) for k, m in d.get("lagen", {}).items()}
        for x in d.get("verbindungen", []):
            v = Verbindung(**x)
            fa, fb = flaeche_von(v.teil, v.flaeche), flaeche_von(v.gegen_teil, v.gegen_flaeche)
            if fa is not None and fb is not None:
                self.verbindungen.append(v)
                self.formen[v.nummer] = (fa, fb)


def flaeche_im_teil(form, index: int, modell):
    """Flaeche mit diesem Index in der Form einer Teil-Instanz (mit deren Lage) oder None."""
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        if modell.flaechen_index(ex.Current()) == index:
            return ex.Current()
        ex.Next()
    return None
