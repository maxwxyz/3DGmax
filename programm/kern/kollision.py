"""Kollisions-, Kontakt- und Bandanalyse zwischen Teilen einer Baugruppe (ohne Qt), PLAN §8.21 Stufe 1-4.

Paare: alle Teile untereinander oder Gruppe A gegen Gruppe B (Teil-Instanzen zaehlen einzeln). Vorauswahl ueber die
Huellquader (um den groessten gesuchten Abstand erweitert), dann je Paar exakt: kleinster Abstand mit Punkten
(BRepExtrema_DistShapeShape) und Durchdringungskoerper (BRepAlgoAPI_Common, Volumen).
Arten: Kollision (Durchdringungsvolumen > 0), Kontakt (Abstand <= Kontakttoleranz, kein Volumen), zu nah
(Abstand < Mindestabstand), zu weit (Abstand > Hoechstabstand, nur fuer Gruppe A gegen B: sonst waere jedes entfernte
Paar ein Befund).
"""

from __future__ import annotations

from dataclasses import dataclass, field

KOLLISION, KONTAKT, ZU_NAH, ZU_WEIT = "kollision", "kontakt", "zu_nah", "zu_weit"
ART_TEXT = {KOLLISION: "Kollision", KONTAKT: "Kontakt", ZU_NAH: "zu nah", ZU_WEIT: "zu weit"}
STATUS = {"offen": "offen", "akzeptiert": "akzeptiert", "ignoriert": "ignoriert"}


@dataclass
class Teil:
    nummer: int  # Knotennummer im Baum
    name: str
    form: object  # TopoDS_Shape in Baugruppenlage


@dataclass
class Befund:
    nummer: int
    a: Teil
    b: Teil
    art: str
    abstand: float
    volumen: float = 0.0
    punkte: tuple = ()  # (Punkt auf a, Punkt auf b) des kleinsten Abstands
    durchdringung: object = None  # TopoDS_Shape der Durchdringung (Kollision)
    status: str = "offen"
    kommentar: str = ""
    tiefe: float = 0.0  # Eindringtiefe (kleinste Kante des orientierten Huellquaders der Durchdringung)
    kurven: object = None  # Schnittkurven der Oberflaechen beider Teile (Kanten, Kollision)
    grenzlage: str = ""  # Befund erst in einer Grenzlage der Toleranzen (Text: Teil und Nummer), sonst leer
    bewegung: str = ""  # Befund erst bei einer Bewegung entlang eines offenen Freiheitsgrads (Text), sonst leer
    netz: bool = False  # aus Dreiecksnetzen geprueft: Abstand, Volumen und Tiefe genaeherte Werte


@dataclass
class Einstellung:
    kontakt: float = 0.01  # mm: bis hierhin gilt eine Beruehrung als Kontakt
    mindest: float = 0.0  # mm: kleinere Abstaende melden (0: aus)
    hoechst: float = 0.0  # mm: groessere Abstaende melden, nur Gruppe A gegen B (0: aus)
    kontakte_melden: bool = True


def _box(form, rand: float):
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    b = Bnd_Box()
    brepbndlib.Add(form, b)
    if rand > 0:
        b.Enlarge(rand)
    return b


def paare(teile: list[Teil], gruppe_b: list[Teil] | None = None) -> list[tuple[Teil, Teil]]:
    if gruppe_b is None:
        return [(teile[i], teile[j]) for i in range(len(teile)) for j in range(i + 1, len(teile))]
    return [(a, b) for a in teile for b in gruppe_b if a.nummer != b.nummer]


def _volumen(form) -> float:
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    g = GProp_GProps()
    brepgprop.VolumeProperties(form, g)
    return abs(g.Mass())


def tiefe(form) -> float:
    """Eindringtiefe einer Durchdringung: kleinste Kantenlaenge des orientierten Huellquaders."""
    from OCC.Core.Bnd import Bnd_OBB
    from OCC.Core.BRepBndLib import brepbndlib
    obb = Bnd_OBB()
    brepbndlib.AddOBB(form, obb, True, True, False)
    if obb.IsVoid():
        return 0.0
    return 2.0 * min(obb.XHSize(), obb.YHSize(), obb.ZHSize())


def schnittkurven(a, b):
    """Schnittkanten der Oberflaechen zweier Formen (Compound) oder None."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Section
    s = BRepAlgoAPI_Section(a, b)
    s.Build()
    return s.Shape() if s.IsDone() else None


NETZ_RASTER = 24  # Rasterpunkte je Achse fuer Volumen und Tiefe einer Durchdringung von Netzteilen
NETZ_TEILUNG = 120.0  # Abtastung der Oberflaeche: Kantenlaenge hoechstens Diagonale / NETZ_TEILUNG


def ist_netz(form) -> bool:
    """True, wenn eine Flaeche nur eine Triangulation hat (STL, OBJ, glTF, PRC-Netz)."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        if BRep_Tool.Surface(topods.Face(ex.Current())) is None:
            return True
        ex.Next()
    return False


def _teile_lange_kanten(a, b, c, laenge: float):
    """Dreiecke an der Mitte ihrer laengsten Kante halbieren, bis alle Kanten hoechstens 'laenge' lang sind
    (lange schmale Dreiecke wachsen so nur linear, nicht quadratisch)."""
    import numpy as np
    fertig = []
    for _ in range(40):
        kanten = np.stack([np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1),
                           np.linalg.norm(a - c, axis=1)], axis=1)
        lang = kanten.max(axis=1) > laenge
        fertig.append((a[~lang], b[~lang], c[~lang]))
        if not lang.any():
            break
        a, b, c, k = a[lang], b[lang], c[lang], kanten[lang].argmax(axis=1)
        # Ecken so drehen, dass die laengste Kante p-q ist (r gegenueber)
        p = np.where((k == 0)[:, None], a, np.where((k == 1)[:, None], b, c))
        q = np.where((k == 0)[:, None], b, np.where((k == 1)[:, None], c, a))
        r = np.where((k == 0)[:, None], c, np.where((k == 1)[:, None], a, b))
        m = (p + q) / 2
        a, b, c = np.vstack([p, m]), np.vstack([m, q]), np.vstack([r, r])
    else:
        fertig.append((a, b, c))
    return tuple(np.vstack([f[i] for f in fertig]) for i in range(3))


_DREHUNG = None  # feste "schiefe" Strahlrichtung fuer den Innen-Test (kein Treffer genau auf Kanten)


def _strahl_drehung():
    global _DREHUNG
    if _DREHUNG is None:
        import numpy as np
        w = np.array([0.3127, -0.2251, 0.9228])
        w /= np.linalg.norm(w)
        u = np.cross(w, [1.0, 0.0, 0.0])
        u /= np.linalg.norm(u)
        _DREHUNG = np.stack([u, np.cross(w, u), w])  # Zeilen: neue x, y, z (Strahl entlang z)
    return _DREHUNG


def innen(punkte, a, b, c, raster: int = 32):
    """Punkte innerhalb eines geschlossenen Dreiecksnetzes (Strahl-Paritaet, Dreiecke im Raster vorsortiert)."""
    import numpy as np
    r = _strahl_drehung()
    p, a, b, c = punkte @ r.T, a @ r.T, b @ r.T, c @ r.T
    lo = np.minimum(np.minimum(a, b), c)
    hi = np.maximum(np.maximum(a, b), c)
    x0, y0 = lo[:, 0].min(), lo[:, 1].min()
    sx = max((hi[:, 0].max() - x0) / raster, 1e-12)
    sy = max((hi[:, 1].max() - y0) / raster, 1e-12)
    zelle_p = np.stack([np.floor((p[:, 0] - x0) / sx), np.floor((p[:, 1] - y0) / sy)], axis=1).astype(int)
    drin = np.all((zelle_p >= 0) & (zelle_p < raster), axis=1)
    treffer = np.zeros(len(p), dtype=int)
    t_lo = np.floor(np.stack([(lo[:, 0] - x0) / sx, (lo[:, 1] - y0) / sy], axis=1)).astype(int)
    t_hi = np.floor(np.stack([(hi[:, 0] - x0) / sx, (hi[:, 1] - y0) / sy], axis=1)).astype(int)
    schluessel = zelle_p[:, 0] * raster + zelle_p[:, 1]
    for k in np.unique(schluessel[drin]):
        i, j = divmod(int(k), raster)
        t = np.nonzero((t_lo[:, 0] <= i) & (t_hi[:, 0] >= i) & (t_lo[:, 1] <= j) & (t_hi[:, 1] >= j))[0]
        if not len(t):
            continue
        sel = np.nonzero(drin & (schluessel == k))[0]
        q = p[sel][:, None, :]  # Punkte x Dreiecke
        ta, tb, tc = a[t][None], b[t][None], c[t][None]
        d = (tb[..., 1] - tc[..., 1]) * (ta[..., 0] - tc[..., 0]) + (tc[..., 0] - tb[..., 0]) * (ta[..., 1] - tc[..., 1])
        d = np.where(np.abs(d) < 1e-300, np.inf, d)  # senkrecht stehende Dreiecke treffen nie
        l1 = ((tb[..., 1] - tc[..., 1]) * (q[..., 0] - tc[..., 0]) + (tc[..., 0] - tb[..., 0]) * (q[..., 1] - tc[..., 1])) / d
        l2 = ((tc[..., 1] - ta[..., 1]) * (q[..., 0] - tc[..., 0]) + (ta[..., 0] - tc[..., 0]) * (q[..., 1] - tc[..., 1])) / d
        l3 = 1 - l1 - l2
        z = l1 * ta[..., 2] + l2 * tb[..., 2] + l3 * tc[..., 2]
        treffer[sel] += np.sum((l1 >= 0) & (l2 >= 0) & (l3 >= 0) & (z > q[..., 2]), axis=1)
    return treffer % 2 == 1


class _Netz:
    """Dreiecke einer Form in Weltlage (exakte Flaechen werden fein vernetzt) mit Abstands- und Innen-Abfrage."""

    def __init__(self, form):
        import numpy as np
        from OCC.Core.BRep import BRep_Tool
        from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.TopLoc import TopLoc_Location
        from OCC.Core.TopoDS import topods
        from .ausrichten import NetzAbstand
        box = _box(form, 0.0)
        x0, y0, z0, x1, y1, z1 = box.Get()
        self.diag = float(np.linalg.norm([x1 - x0, y1 - y0, z1 - z0])) or 1.0
        BRepMesh_IncrementalMesh(form, self.diag * 1e-3, False, 0.2, True)  # Netzflaechen bleiben unveraendert
        netze = []
        ex = TopExp_Explorer(form, TopAbs_FACE)
        while ex.More():
            f = topods.Face(ex.Current())
            ex.Next()
            loc = TopLoc_Location()
            tri = BRep_Tool.Triangulation(f, loc)
            if tri is None or tri.NbTriangles() == 0:
                continue
            t = loc.Transformation()
            pts = np.array([(lambda q: (q.X(), q.Y(), q.Z()))(tri.Node(i).Transformed(t))
                            for i in range(1, tri.NbNodes() + 1)], float)
            netze.append((pts, np.array([tri.Triangle(i).Get() for i in range(1, tri.NbTriangles() + 1)]) - 1))
        if not netze:
            raise ValueError("keine Dreiecke")
        a = np.vstack([p[t[:, 0]] for p, t in netze])
        b = np.vstack([p[t[:, 1]] for p, t in netze])
        c = np.vstack([p[t[:, 2]] for p, t in netze])
        a, b, c = _teile_lange_kanten(a, b, c, self.diag / NETZ_TEILUNG)
        n = len(a)
        self.abstand = NetzAbstand([(np.vstack([a, b, c]), np.arange(3 * n).reshape(3, n).T)], teilung=1.0)
        self.proben = np.vstack([(a + b + c) / 3] + [p for p, _ in netze])  # Oberflaechenpunkte
        self.dreiecke = tuple(np.vstack([p[t[:, k]] for p, t in netze]) for k in range(3))  # fuer den Innen-Test
        self.min, self.max = self.proben.min(axis=0), self.proben.max(axis=0)

    def abfrage(self, punkte):
        """(Abstand, naechster Punkt, innen) je Punkt."""
        d, q, _ = self.abstand.abfrage(punkte)
        return d, q, self.innen(punkte)

    def innen(self, punkte):
        import numpy as np
        out = np.zeros(len(punkte), dtype=bool)
        im_quader = np.all((punkte >= self.min) & (punkte <= self.max), axis=1)
        if im_quader.any():
            out[im_quader] = innen(punkte[im_quader], *self.dreiecke)
        return out


def _pruefe_netz_paar(a: Teil, b: Teil, e: Einstellung, gegen: bool, netze: dict):
    """Wie _pruefe_paar fuer Netzteile (oder gemischte Paare): Abstand der Oberflaechenpunkte zum anderen Netz in
    beide Richtungen; Durchdringung, wenn Punkte tiefer als der Kontaktabstand im anderen Teil liegen. Volumen und
    Tiefe (kleinste Ausdehnung) aus einem Raster ueber den eingedrungenen Punkten. Genau etwa bis zur Netzfeinheit."""
    import numpy as np
    for t in (a, b):
        if id(t.form) not in netze:
            netze[id(t.form)] = _Netz(t.form)
    na, nb = netze[id(a.form)], netze[id(b.form)]
    rand = max(e.kontakt, e.mindest, e.hoechst if gegen else 0.0)
    if (np.any(na.min > nb.max + rand) or np.any(nb.min > na.max + rand)) and not (gegen and e.hoechst > 0):
        return None
    def nahe(von, zu):
        """Punkte von 'von' im erweiterten Huellquader von 'zu' (nur sie koennen eindringen oder nahe sein);
        ohne solche eine Stichprobe fuer den Abstand."""
        grenze = rand + 1e-6
        maske = np.all((von.proben >= zu.min - grenze) & (von.proben <= zu.max + grenze), axis=1)
        if maske.any():
            return von.proben[maske]
        schritt = max(1, len(von.proben) // 4000)
        return von.proben[::schritt]
    pa, pb = nahe(na, nb), nahe(nb, na)
    d_ab, q_ab, in_b = nb.abfrage(pa)
    d_ba, q_ba, in_a = na.abfrage(pb)
    i, j = int(np.argmin(d_ab)), int(np.argmin(d_ba))
    if d_ab[i] <= d_ba[j]:
        abstand, punkte = float(d_ab[i]), (tuple(pa[i]), tuple(q_ab[i]))
    else:
        abstand, punkte = float(d_ba[j]), (tuple(q_ba[j]), tuple(pb[j]))
    tief_a, tief_b = in_b & (d_ab > e.kontakt), in_a & (d_ba > e.kontakt)
    if tief_a.any() or tief_b.any():
        drin = np.vstack([pa[tief_a], pb[tief_b]])
        lo, hi = drin.min(axis=0), drin.max(axis=0)
        achsen = [np.linspace(lo[k], hi[k], NETZ_RASTER) for k in range(3)]
        raster = np.stack(np.meshgrid(*achsen, indexing="ij"), axis=-1).reshape(-1, 3)
        ia, ib = na.innen(raster), nb.innen(raster)
        beide = raster[ia & ib]
        zelle = np.prod(np.maximum(hi - lo, 1e-9) / (NETZ_RASTER - 1))
        volumen = max(float(len(beide) * zelle), 1e-6)
        if len(beide) >= 4:
            mitte = beide - beide.mean(axis=0)
            _, _, vt = np.linalg.svd(mitte, full_matrices=False)
            ausdehnung = np.ptp(mitte @ vt.T, axis=0)
            tiefe_ = float(ausdehnung.min())
        else:
            tiefe_ = float(max(d_ab[tief_a].max(initial=0.0), d_ba[tief_b].max(initial=0.0)))
        return KOLLISION, 0.0, volumen, punkte, None, tiefe_
    if abstand <= e.kontakt:
        return (KONTAKT, abstand, 0.0, punkte, None) if e.kontakte_melden else None
    if e.mindest > 0 and abstand < e.mindest:
        return ZU_NAH, abstand, 0.0, punkte, None
    if gegen and e.hoechst > 0 and abstand > e.hoechst:
        return ZU_WEIT, abstand, 0.0, punkte, None
    return None


def _pruefe_paar(a: Teil, b: Teil, e: Einstellung, gegen: bool, netze: dict | None = None):
    """(Art, Abstand, Volumen, Punkte, Durchdringung[, Tiefe]) oder None ohne Befund; Netzteile ueber Dreiecke."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
    if netze is not None and (netze.setdefault(("netz", id(a.form)), ist_netz(a.form)) or
                              netze.setdefault(("netz", id(b.form)), ist_netz(b.form))):
        return _pruefe_netz_paar(a, b, e, gegen, netze)
    d = BRepExtrema_DistShapeShape(a.form, b.form)
    d.Perform()
    if not d.IsDone():
        return None
    abstand = d.Value()
    punkte = ()
    if d.NbSolution():
        pa, pb = d.PointOnShape1(1), d.PointOnShape2(1)
        punkte = ((pa.X(), pa.Y(), pa.Z()), (pb.X(), pb.Y(), pb.Z()))
    if abstand <= e.kontakt:
        common = BRepAlgoAPI_Common(a.form, b.form)
        if common.IsDone():
            volumen = _volumen(common.Shape())
            if volumen > 1e-6:
                return KOLLISION, 0.0, volumen, punkte, common.Shape()
        return (KONTAKT, abstand, 0.0, punkte, None) if e.kontakte_melden else None
    if e.mindest > 0 and abstand < e.mindest:
        return ZU_NAH, abstand, 0.0, punkte, None
    if gegen and e.hoechst > 0 and abstand > e.hoechst:
        return ZU_WEIT, abstand, 0.0, punkte, None
    return None


def pruefe(teile: list[Teil], gruppe_b: list[Teil] | None = None, e: Einstellung | None = None,
           fortschritt=lambda anteil: None) -> list[Befund]:
    """Befunde aller Paare; fortschritt(0..1) darf eine Ausnahme werfen (Abbruch)."""
    e = e or Einstellung()
    gegen = gruppe_b is not None
    rand = max(e.kontakt, e.mindest)
    liste = paare(teile, gruppe_b)
    boxen = {}
    for t in {id(t): t for p in liste for t in p}.values():
        boxen[id(t)] = _box(t.form, 0.0)
    befunde = []
    netze: dict = {}  # Netze und Netz-Merkmal je Form (einmal je Pruefung)
    for k, (a, b) in enumerate(liste):
        fortschritt(k / max(len(liste), 1))
        ba = _box(a.form, rand) if rand > 0 else boxen[id(a)]
        if ba.IsOut(boxen[id(b)]) and not (gegen and e.hoechst > 0):
            continue  # weit genug auseinander (bei "zu weit" muss jedes Paar gemessen werden)
        erg = _pruefe_paar(a, b, e, gegen, netze)
        if erg is not None:
            art, abstand, volumen, punkte, form, *netz_tiefe = erg
            x = Befund(len(befunde) + 1, a, b, art, abstand, volumen, punkte, form)
            if art == KOLLISION and form is not None:
                x.tiefe = tiefe(form)
                x.kurven = schnittkurven(a.form, b.form)
            elif netz_tiefe:
                x.tiefe = netz_tiefe[0]
            x.netz = bool(netze.get(("netz", id(a.form))) or netze.get(("netz", id(b.form))))
            befunde.append(x)
    fortschritt(1.0)
    ordnung = {KOLLISION: 0, ZU_NAH: 1, KONTAKT: 2, ZU_WEIT: 3}
    befunde.sort(key=lambda x: (ordnung[x.art], -x.volumen, x.abstand))
    for i, x in enumerate(befunde, 1):
        x.nummer = i
    return befunde


SPALTEN = ("Nr", "Teil A", "Teil B", "Art", "Abstand", "Volumen", "Tiefe", "Status", "Kommentar")


def als_csv(befunde: list[Befund]) -> str:
    import csv
    import io
    from ..i18n import tr
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";")
    w.writerow([tr(s) for s in SPALTEN])
    for x in befunde:
        w.writerow([x.nummer, x.a.name, x.b.name, tr(ART_TEXT[x.art]), f"{x.abstand:.4f}".replace(".", ","),
                    f"{x.volumen:.3f}".replace(".", ","), f"{x.tiefe:.3f}".replace(".", ","), tr(STATUS[x.status]),
                    x.kommentar])
    return puffer.getvalue()


def merke(befunde: list[Befund]) -> list[dict]:
    """Status und Kommentare fuer das Projekt (je Teilepaar und Art; Teilnamen und Knotennummern)."""
    return [{"a": x.a.nummer, "b": x.b.nummer, "a_name": x.a.name, "b_name": x.b.name, "art": x.art,
             "status": x.status, "kommentar": x.kommentar} for x in befunde if x.status != "offen" or x.kommentar]


def uebernimm(befunde: list[Befund], gemerkt: list[dict]) -> int:
    """Gemerkte Status und Kommentare nach einer neuen Pruefung wieder zuordnen; Anzahl der Treffer."""
    n = 0
    for g in gemerkt:
        for x in befunde:
            gleich = {x.a.nummer, x.b.nummer} == {g.get("a"), g.get("b")} or \
                {x.a.name, x.b.name} == {g.get("a_name"), g.get("b_name")}
            if gleich and x.art == g.get("art"):
                x.status, x.kommentar = g.get("status", "offen"), g.get("kommentar", "")
                n += 1
                break
    return n


def pruefe_grenzlagen(teile: list[Teil], grenzen: dict, gruppe_b: list[Teil] | None = None,
                      e: Einstellung | None = None, fortschritt=lambda anteil: None,
                      gepaart: set | None = None) -> list[Befund]:
    """Befunde, die erst entstehen, wenn ein Teil eine Grenzlage innerhalb der Toleranzen seiner Verbindungen
    einnimmt (je Teil einzeln, die anderen in Nennlage); grenzen: Knotennummer -> Liste von 4x4-Bewegungen (Welt).
    Nur Arten, die in Nennlage fuer dieses Paar nicht vorkommen; je Paar und Art der schlimmste Fall. gepaart:
    direkt verbundene Paare (frozenset der Nummern) – ihre Relativlage legt die Verbindung fest, eine Durchdringung
    dort waere ein Artefakt des symmetrischen Spiels und wird nicht gemeldet."""
    import numpy as np
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.gp import gp_Trsf
    e = e or Einstellung()
    nenn = {(frozenset((x.a.nummer, x.b.nummer)), x.art) for x in pruefe(teile, gruppe_b, e)}
    schlimmste: dict = {}
    schritte = [(t, k, m) for t in teile + (gruppe_b or []) if t.nummer in grenzen
                for k, m in enumerate(grenzen[t.nummer], 1)]
    for n, (t, k, m) in enumerate(schritte):
        fortschritt(n / max(len(schritte), 1))
        tr_ = gp_Trsf()
        tr_.SetValues(*[float(np.asarray(m)[i][j]) for i in range(3) for j in range(4)])
        bewegt = Teil(t.nummer, t.name, t.form.Moved(TopLoc_Location(tr_)))
        ersetze = lambda liste: [bewegt if x.nummer == t.nummer else x for x in liste]  # noqa: E731
        for x in pruefe(ersetze(teile), ersetze(gruppe_b) if gruppe_b is not None else None, e):
            if t.nummer not in (x.a.nummer, x.b.nummer):
                continue
            schluessel = (frozenset((x.a.nummer, x.b.nummer)), x.art)
            if schluessel in nenn or schluessel[0] in (gepaart or set()):
                continue
            alt = schlimmste.get(schluessel)
            schlimmer = alt is None or (x.volumen > alt.volumen if x.art == KOLLISION else x.abstand < alt.abstand)
            if schlimmer:
                x.grenzlage = f"{t.name}: {k}"
                schlimmste[schluessel] = x
    fortschritt(1.0)
    out = sorted(schlimmste.values(), key=lambda x: ({KOLLISION: 0, ZU_NAH: 1, KONTAKT: 2, ZU_WEIT: 3}[x.art],
                                                     -x.volumen, x.abstand))
    for i, x in enumerate(out, 1):
        x.nummer = i
    return out


def _bewegt(t: Teil, m) -> Teil:
    import numpy as np
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.gp import gp_Trsf
    tr_ = gp_Trsf()
    tr_.SetValues(*[float(np.asarray(m)[i][j]) for i in range(3) for j in range(4)])
    return Teil(t.nummer, t.name, t.form.Moved(TopLoc_Location(tr_)))


def _neue_kollision(t: Teil, andere: list[Teil], e: Einstellung, schon: set) -> Befund | None:
    """Groesste Kollision des Teils mit einem anderen, die es in der Ausgangslage nicht gibt."""
    neu = [x for x in pruefe([t], andere, e) if x.art == KOLLISION and x.b.nummer not in schon]
    return neu[0] if neu else None


def freier_bereich(teil: Teil, andere: list[Teil], bewegung, bis: float, schritte: int = 24,
                   e: Einstellung | None = None, genauigkeit: int = 6, fortschritt=lambda anteil: None):
    """Bewegungsbereich eines Teils entlang eines offenen Freiheitsgrads bis zur ersten Kollision.

    bewegung(wert) -> 4x4-Bewegung in Weltlage (mm bzw. Grad); geprueft wird je Richtung in schritte Schritten bis
    +-bis, die erste Kollision wird durch Halbieren eingegrenzt. Kollisionen, die schon in der Ausgangslage bestehen,
    zaehlen nicht. Ergebnis: (unten, oben, Befunde der Grenzen) – unten/oben ist die letzte freie Lage (bis, wenn
    nichts stoesst)."""
    e = Einstellung(e.kontakt, 0.0, 0.0, False) if e else Einstellung(kontakte_melden=False)
    schon = {x.b.nummer for x in pruefe([teil], andere, e) if x.art == KOLLISION}
    grenzen, befunde = [], []
    for k, vorzeichen in enumerate((-1, 1)):
        frei, stoss = 0.0, None
        for i in range(1, schritte + 1):
            fortschritt((k * schritte + i) / (2 * schritte))
            w = vorzeichen * bis * i / schritte
            stoss = _neue_kollision(_bewegt(teil, bewegung(w)), andere, e, schon)
            if stoss is not None:
                stoss_w = w
                break
            frei = w
        if stoss is not None:
            for _ in range(genauigkeit):  # Grenze zwischen frei und stoss_w eingrenzen
                mitte = (frei + stoss_w) / 2
                x = _neue_kollision(_bewegt(teil, bewegung(mitte)), andere, e, schon)
                if x is None:
                    frei = mitte
                else:
                    stoss_w, stoss = mitte, x
            stoss.bewegung = f"{stoss_w:+.4g}"
            befunde.append(stoss)
        grenzen.append(frei)
    fortschritt(1.0)
    return grenzen[0], grenzen[1], befunde
