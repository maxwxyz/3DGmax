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


def _pruefe_paar(a: Teil, b: Teil, e: Einstellung, gegen: bool):
    """(Art, Abstand, Volumen, Punkte, Durchdringung) oder None ohne Befund."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
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
    for k, (a, b) in enumerate(liste):
        fortschritt(k / max(len(liste), 1))
        ba = _box(a.form, rand) if rand > 0 else boxen[id(a)]
        if ba.IsOut(boxen[id(b)]) and not (gegen and e.hoechst > 0):
            continue  # weit genug auseinander (bei "zu weit" muss jedes Paar gemessen werden)
        erg = _pruefe_paar(a, b, e, gegen)
        if erg is not None:
            art, abstand, volumen, punkte, form = erg
            x = Befund(len(befunde) + 1, a, b, art, abstand, volumen, punkte, form)
            if art == KOLLISION and form is not None:
                x.tiefe = tiefe(form)
                x.kurven = schnittkurven(a.form, b.form)
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
