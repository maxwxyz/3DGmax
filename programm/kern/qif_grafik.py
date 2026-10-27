"""Grafische PMI (PMIDisplaySet) und gespeicherte Ansichten (ViewSet) aus QIF 3.0.

PMIDisplay: Ebene (AnnotationView mit Normale und Richtung, Ursprung), darin 2D-Elemente: Texte (mit Symbolen wie
{POSITION}, Zeilenumbruch {BR}), Rahmen (rechteckig, rund), Hinweislinien mit Pfeil/Punkt, Masshilfslinien und
freie Grafik (Linienzuege, Dreiecksflaechen). Reference verweist auf die semantische PMI (Merkmal, Bezug, Hinweis).
SavedView: Kamera (ViewPlaneOrigin, Orientierung als Quaternion w x y z, Hoehe) und sichtbare Annotationen.
"""

from __future__ import annotations

import numpy as np

from .ansichten import Ansicht
from .praesentation import Grafik, Platzhalter
from .qif import NS, _k, _p, _zahlen

SYMBOLE = {"POSITION": "⌖", "FLATNESS": "⏥", "PERPENDICULARITY": "⟂", "PROFILE_SURFACE": "⌓",
           "PROFILE_LINE": "⌒", "DIAMETER": "⌀", "DIAMETER_SPHERICAL": "S⌀", "DEGREE": "°", "PLUS_MINUS": "±",
           "PARALLELISM": "∥", "ANGULARITY": "∠", "CIRCULARITY": "○", "CYLINDRICITY": "⌭", "STRAIGHTNESS": "⏤",
           "CONCENTRICITY": "◎", "SYMMETRY": "⌯", "RUNOUT_CIRCULAR": "↗", "RUNOUT_TOTAL": "⌰", "M": "Ⓜ",
           "L": "Ⓛ", "F": "Ⓕ", "P": "Ⓟ", "T": "Ⓣ", "E": "Ⓔ", "U": "Ⓤ", "ST": "⟨ST⟩", "CF": "⟨CF⟩",
           "COUNTERBORE": "⌴", "COUNTERSINK": "⌵", "DEPTH": "↧", "SQUARE": "□"}
KOPF_FUELLUNG = {"ARROW_FILLED", "ARROW_FILLED_OPEN", "DOT_FILLED", "TRIANGLE_FILLED"}


def text(roh: str) -> list[str]:
    """QIF-Text in Zeilen: {SYMBOL} -> Unicode, {BR} trennt Zeilen; unbekannte Namen bleiben lesbar."""
    out, i = "", 0
    while i < len(roh):
        if roh[i] == "{" and "}" in roh[i:]:
            j = roh.index("}", i)
            name = roh[i + 1:j]
            out += "\n" if name == "BR" else SYMBOLE.get(name, name)
            i = j + 1
        else:
            out += roh[i]
            i += 1
    return out.split("\n")


class _Ebene:
    """2D-Koordinaten der Schreibebene -> 3D (mm)."""

    def __init__(self, ursprung, x, n, faktor: float):
        self.n = n / (np.linalg.norm(n) or 1.0)
        x = x - self.n * (x @ self.n)
        self.x = x / (np.linalg.norm(x) or 1.0)
        self.y = np.cross(self.n, self.x)
        self.o = np.asarray(ursprung, float) * faktor
        self.f = faktor

    def p(self, uv) -> np.ndarray:
        uv = np.asarray(uv, float).reshape(-1, 2) * self.f
        return self.o + uv[:, :1] * self.x + uv[:, 1:2] * self.y


def _uv(e, pfad):
    x = e.find(_p(pfad))
    return None if x is None or not x.text else np.array(_zahlen(x.text)[:2])


def _kopf(g: Grafik, eb: _Ebene, spitze, von, form: str, hoehe: float):
    """Pfeil oder Punkt an 'spitze', Richtung von 'von' her (2D-Werte der Ebene)."""
    if spitze is None or von is None or not form or form == "NONE":
        return
    d = spitze - von
    laenge = float(np.linalg.norm(d))
    if laenge < 1e-12:
        return
    d = d / laenge
    q = np.array([-d[1], d[0]])
    if form.startswith("DOT"):
        k = np.linspace(0, 2 * np.pi, 13)[:-1]
        r = hoehe / 3
        pts = [spitze] + [spitze + r * np.array([np.cos(w), np.sin(w)]) for w in k]
        tris = np.array([[0, i, i % 12 + 1] for i in range(1, 13)])
    else:
        basis = spitze - d * hoehe
        pts = [spitze, basis + q * hoehe / 3.2, basis - q * hoehe / 3.2]
        tris = np.array([[0, 1, 2]])
    p3 = eb.p(np.array(pts))
    if form in KOPF_FUELLUNG or form.startswith("DOT_FILLED"):
        g.dreiecke.append((p3, tris))
    else:
        g.linien.append(p3[[1, 0, 2]] if len(p3) == 3 else np.vstack([p3[1:], p3[1:2]]))


def _leader(g: Grafik, eb: _Ebene, e):
    art = _k(e)
    a, b = _uv(e, "StartPoint"), _uv(e, "EndPoint")
    if a is None or b is None:
        return
    h = float(e.findtext(_p("HeadHeight")) or 3.0)
    ext = _uv(e, "PointExtension")
    if art == "LeaderDoubleHeadCircular":
        c = _uv(e, "Center")
        if c is not None:
            r = float(np.linalg.norm(a - c))
            w0, w1 = np.arctan2(*(a - c)[::-1]), np.arctan2(*(b - c)[::-1])
            if w1 < w0:
                w1 += 2 * np.pi
            w = np.linspace(w0, w1, 33)
            g.linien.append(eb.p(c + r * np.column_stack([np.cos(w), np.sin(w)])))
    else:
        g.linien.append(eb.p(np.array([a, b] + ([ext] if ext is not None else []))))
    _kopf(g, eb, a, b, e.findtext(_p("HeadForm")) or "", h)
    if art.startswith("LeaderDoubleHead"):
        _kopf(g, eb, b, a, e.findtext(_p("HeadForm2")) or e.findtext(_p("HeadForm")) or "", h)


def _rahmen(g: Grafik, eb: _Ebene, e):
    if _k(e) == "FrameCircular":
        c, r = _uv(e, "XY"), float(e.findtext(_p("Radius")) or 0)
        if c is not None and r > 0:
            w = np.linspace(0, 2 * np.pi, 49)
            g.linien.append(eb.p(c + r * np.column_stack([np.cos(w), np.sin(w)])))
        return
    xy = _uv(e, "XY")
    b, h = float(e.findtext(_p("Width")) or 0), float(e.findtext(_p("Height")) or 0)
    if xy is not None and b > 0 and h > 0:
        ecken = np.array([xy, xy + (b, 0), xy + (b, h), xy + (0, h), xy])
        g.linien.append(eb.p(ecken))


def grafik(dok) -> dict[int, Grafik]:
    """PMIDisplay -> Grafik (Callout-ID: laufende Nummer ab 1, PMI-IDs: Reference)."""
    ansichten = {v.get("id"): v for v in dok.wurzel.iter(NS + "AnnotationView")}
    out: dict[int, Grafik] = {}
    for nr, d in enumerate(dok.wurzel.iter(NS + "PMIDisplay"), 1):
        ebene = d.find(_p("Plane"))
        if ebene is None:
            continue
        av = ansichten.get((ebene.findtext(_p("AnnotationViewId/Id")) or "").strip())
        n = np.array(_zahlen(av.findtext(_p("Normal")) or "0 0 1")) if av is not None else np.array([0, 0, 1.0])
        x = ebene.findtext(_p("Direction")) or (av.findtext(_p("Direction")) if av is not None else None)
        x = np.array(_zahlen(x)) if x else np.array([1.0, 0, 0])
        eb = _Ebene(_zahlen(ebene.findtext(_p("Origin")) or "0 0 0"), x, n, dok.faktor)
        g = Grafik(-1000000 - nr, fertig=True, ebene=(eb.o, eb.x, eb.y, eb.n))
        farbe = _zahlen(d.findtext(_p("Color")) or "")
        g.farbe = tuple(c / 255 for c in farbe[:3]) if len(farbe) >= 3 else None
        g.pmi_ids = {int(i.text) for i in d.iterfind(_p("Reference/Id")) if i.text and i.text.strip().isdigit()}
        texte = d.find(_p("Texts"))
        if texte is not None:
            zeile = float(texte.get("lineHeight") or 3.0)
            for t in texte.iterfind(_p("Text")):
                xy = _uv(t, "XY")
                if xy is None:
                    continue
                for k, z in enumerate(text(t.findtext(_p("Data")) or "")):
                    if z.strip():
                        o = eb.p(xy - (0, 1.35 * zeile * k))[0]
                        # lineHeight ist die Schrifthoehe; Platzhalter.hoehe ist die Kastenhoehe (Schrift 0,8 davon)
                        g.platzhalter.append(Platzhalter(o, eb.x, eb.y, len(z) * zeile * 0.6 * eb.f,
                                                         1.25 * zeile * eb.f, text=z))
        for e in d.iterfind(_p("Frames/*")):
            _rahmen(g, eb, e)
        for e in d:
            if _k(e).startswith("Leader"):
                _leader(g, eb, e)
        w = d.find(_p("WitnessLines"))
        if w is not None:
            for s in w:
                a, b = _uv(s, "StartPoint"), _uv(s, "EndPoint")
                if a is not None and b is not None:
                    g.linien.append(eb.p(np.array([a, b])))
        for pl in d.iterfind(_p("Graphics/Polylines/Polyline")):
            z = _zahlen(pl.findtext(_p("Points")) or "")
            if len(z) >= 4:
                g.linien.append(eb.p(np.array(z[:len(z) // 2 * 2]).reshape(-1, 2)))
        for tri in d.iterfind(_p("Graphics/Areas/Area/Triangulation")):
            v = np.array(_zahlen(tri.findtext(_p("Vertices")) or "")).reshape(-1, 2)
            t = np.array(_zahlen(tri.findtext(_p("Triangles")) or ""), dtype=int).reshape(-1, 3)
            t = t[(t < len(v)).all(axis=1)]
            if len(v) and len(t):
                g.dreiecke.append((eb.p(v), t))
        if not g.leer():
            g.name = " ".join(ph.text for ph in g.platzhalter[:4])
            # rein grafische Notiz: ihre QIF-ID als Callout-ID, damit Liste und Ansichten dieselbe ID nutzen
            notiz = next((i for i in g.pmi_ids if _k(dok.ids.get(str(i), d)) == "Note"), None)
            if notiz is not None and notiz not in out:
                g.callout_id = notiz
            out[g.callout_id] = g
    return out


def _kamera(dok, k, a: Ansicht):
    from scipy.spatial.transform import Rotation
    w = _zahlen(k.findtext(_p("Orientation/Value")) or "")
    if len(w) != 4:
        return
    # Reihenfolge w x y z; Zeilen der Matrix sind die Kameraachsen (gegen den STEP-Export geprueft)
    r = Rotation.from_quat([w[1], w[2], w[3], w[0]]).as_matrix().T
    blick, oben = r[:, 2], r[:, 1]
    hoehe = float(k.findtext(_p("Height")) or 0) * dok.faktor
    ziel = np.array(_zahlen(k.findtext(_p("ViewPlaneOrigin")) or "0 0 0")) * dok.faktor
    abstand = max(hoehe, 1.0) * 2
    a.ort = tuple(float(c) for c in ziel - blick * abstand)
    a.richtung = tuple(float(c) for c in blick)
    a.oben = tuple(float(c) for c in oben)
    a.abstand = abstand
    a.hoehe = hoehe
    a.breite = hoehe * float(k.findtext(_p("Ratio")) or 1.0)


def ansichten(dok, pmi_ids_von_display=None) -> list[Ansicht]:
    """SavedView -> Ansicht mit Kamera und den IDs der sichtbaren semantischen PMI."""
    kameras = {k.get("id"): k for k in dok.wurzel.iter(NS + "Camera")}
    out = []
    for v in dok.wurzel.iter(NS + "SavedView"):
        a = Ansicht(v.get("label") or v.findtext(_p("Name")) or f"View {v.get('id')}", int(v.get("id")))
        kid = (v.findtext(_p("CameraIds/Id")) or "").strip()
        if kid in kameras:
            _kamera(dok, kameras[kid], a)
        a.pmi_ids = {int(i.text) for i in v.iterfind(_p("AnnotationVisibleIds/Id")) if i.text and i.text.isdigit()}
        out.append(a)
    return out
