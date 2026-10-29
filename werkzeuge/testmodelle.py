"""Testvarianten von NIST CTC-01 fuer den Vergleich erzeugen (gezielte Textaenderungen der STEP-Datei).

Aufruf: pixi run python werkzeuge/testmodelle.py   -> tests/daten/varianten/
- ctc01_pmi.stp      Geometrie gleich, PMI geaendert (Toleranzwert, Abmass, Bezugssystem)
- ctc01_geo.stp      Bohrung Ø20 -> Ø21 (Zylinder, Kreise, Ecken, Naht), PMI gleich
- ctc01_geo_pmi.stp  wie ctc01_geo, dazu Mass 20 -> 21
- ctc01_pmi_andere.stp     Geometrie gleich, andere PMI: Ebenheit -> Geradheit, Bezugsreihenfolge A|C|B,
                           Position.2 0.75 -> 1.0
- ctc01_geo_klein.stp      minimale Geometrieaenderung: Bohrung Ø20 um 0.1 mm in X verschoben, PMI gleich
- ctc01_geo_klein_pmi_andere.stp  beides
- ctc01_geo_pmi_deutlich.stp  deutliche Aenderung von Geometrie und PMI (Beispiel "Vergleich"): Bohrung Ø25 bei
                           (160, 45) um 15 mm in +X versetzt (ihr Mass folgt), Bohrung Ø25 bei (-160, -45) entfaellt,
                           Fase 3 mm an der Bohrung Ø25 bei (160, -45) oben; Position.1 0.75 -> 0.5, Position.2
                           Bezuege A|B|C -> A|C|B, Rechtwinkligkeit.1 entfaellt, neue Position Ø0.4 Ⓜ A|B|C an der
                           versetzten Bohrung. Die Geometrie rechnet OCCT, das neue B-Rep ersetzt das alte in der
                           Originaldatei (Verweise der PMI, Farben und Ansichten bleiben, Flaechen geometrisch
                           zugeordnet); die neue PMI schreibt kern.step_schreiben (mit Darstellung)
- ctc01_schnittansicht.stp  Ansicht MBD_0 als Schnittansicht (CAMERA_MODEL_D3_MULTI_CLIPPING): Ebene durch die
                           Bohrungsachse (y = -125, sichtbar +y) und eine Vereinigung aus x < 30 und z > -25
- ctc01_scan.ply           "Scan": feines Netz mit Rauschen (sigma 5 um), gedreht und verschoben (zum Ausrichten)
- ctc01_scan_fehler.ply    wie ctc01_scan, dazu Fase 3 mm an einer Aussenkante, Delle 0.4 mm in der Oberseite und
                           Welligkeit 0.3 mm auf der Ebenheitsflaeche (Ebenheit 0.2 nicht eingehalten)
"""

from __future__ import annotations

import math
import os
import re
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
from programm.kern import p21  # noqa: E402

QUELLE = os.path.join(WURZEL, "tests", "daten", "nist_ctc_01_asme1_ap242-e1.stp")
ZIEL = os.path.join(WURZEL, "tests", "daten", "varianten")
BOHRUNG = (814, 815)  # Flaechen der Bohrung Ø20 (Halbschalen), Achse durch (30, -125, z) in Richtung z
ACHSE = (30.0, -125.0)
R_ALT, R_NEU = 10.0, 10.5


def _ersetze_entitaet(text: str, eid: int, neu: str) -> str:
    """Die Anweisung '#eid=...;' durch 'neu' ersetzen (eine Zeile)."""
    muster = re.compile(rf"^#{eid}=.*?;\s*$", re.M | re.S)
    treffer = muster.search(text)
    if not treffer:
        raise KeyError(eid)
    return text[:treffer.start()] + neu + "\n" + text[treffer.end():].lstrip("\n")


def _zahl(x: float) -> str:
    s = repr(float(x))
    return s if "." in s or "E" in s or "e" in s else s + "."


def _referenzen(d: p21.P21Datei, eid: int, gesehen: set[int]):
    if eid in gesehen:
        return
    gesehen.add(eid)
    e = d.entities[eid]
    for r in p21._refs_in(list(e.parts.values())):
        if d.entities.get(r) is not None and not d.entities[r].is_a("AXIS2_PLACEMENT_3D"):
            _referenzen(d, r, gesehen)


def bohrung_aufweiten(text: str) -> str:
    d = p21.lese_text(text)
    alle: set[int] = set()
    for f in BOHRUNG:
        _referenzen(d, f, alle)
    for eid in sorted(alle):
        e = d.entities[eid]
        if e.is_a("CYLINDRICAL_SURFACE") and abs(e.args()[2] - R_ALT) < 1e-9:
            text = _ersetze_entitaet(text, eid, f"#{eid}=CYLINDRICAL_SURFACE('',#{e.args()[1].id},{_zahl(R_NEU)});")
        elif e.is_a("CIRCLE") and abs(e.args()[2] - R_ALT) < 1e-9:
            text = _ersetze_entitaet(text, eid, f"#{eid}=CIRCLE('{e.args()[0]}',#{e.args()[1].id},{_zahl(R_NEU)});")
        elif e.is_a("CARTESIAN_POINT"):
            x, y, z = e.args()[1]
            dx, dy = x - ACHSE[0], y - ACHSE[1]
            r = math.hypot(dx, dy)
            if abs(r - R_ALT) < 1e-6:
                s = R_NEU / r
                text = _ersetze_entitaet(text, eid, f"#{eid}=CARTESIAN_POINT('{e.args()[0]}',("
                                         f"{_zahl(ACHSE[0] + dx * s)},{_zahl(ACHSE[1] + dy * s)},{_zahl(z)}));")
    return text


def _messwert(text: str, eid: int, neu: float) -> str:
    """Wert in einer (komplexen) MEASURE_WITH_UNIT-Entitaet ersetzen."""
    muster = re.compile(rf"(^#{eid}=.*?(?:LENGTH_MEASURE|POSITIVE_LENGTH_MEASURE)\()([-0-9.Ee+]+)(\))", re.M | re.S)
    t, n = muster.subn(lambda m: m.group(1) + _zahl(neu) + m.group(3), text, count=1)
    if n != 1:
        raise KeyError(eid)
    return t


def pmi_aendern(text: str) -> str:
    d = p21.lese_text(text)
    # 1. Position.1: Toleranzwert 0.75 -> 0.5
    pos = next(e for e in d.of_type("GEOMETRIC_TOLERANCE") if e.args("GEOMETRIC_TOLERANCE")[0] == "Position.1")
    text = _messwert(text, pos.args("GEOMETRIC_TOLERANCE")[2].id, 0.5)
    # 2. Ø35 0/-0.2: unteres Abmass -0.2 -> -0.3
    tv = d.entities[58]  # TOLERANCE_VALUE(#72 unten, #71 oben) des Masses #120
    text = _messwert(text, tv.args()[0].id, -0.3)
    # 3. Flatness.1 0.2 -> 0.1
    flach = next(e for e in d.entities.values() if e.is_a("FLATNESS_TOLERANCE"))
    text = _messwert(text, flach.args()[2].id, 0.1)
    return text


def mass_20_auf_21(text: str) -> str:
    d = p21.lese_text(text)
    for dim in (122, 123):
        dcr = next(d.entities[r] for r in d.referrers()[dim]
                   if d.entities[r].is_a("DIMENSIONAL_CHARACTERISTIC_REPRESENTATION"))
        sdr = d.get(dcr.args()[1])
        for it in sdr.args()[1]:
            e = d.get(it)
            if e.is_a("REPRESENTATION_ITEM") and e.args("REPRESENTATION_ITEM")[0] == "nominal value":
                text = _messwert(text, it.id, 21.0)
    return text


def _punkte_von(d: p21.P21Datei, flaechen) -> set[int]:
    """Alle CARTESIAN_POINTs, die an den Flaechen haengen (auch ueber Achsensysteme)."""
    gesehen: set[int] = set()

    def lauf(eid):
        if eid in gesehen:
            return
        gesehen.add(eid)
        e = d.entities.get(eid)
        if e is None or e.is_a("DIRECTION"):
            return
        for ref in p21._refs_in(list(e.parts.values())):
            lauf(ref)
    for f in flaechen:
        lauf(f)
    return {i for i in gesehen if d.entities.get(i) is not None and d.entities[i].is_a("CARTESIAN_POINT")}


def bohrung_verschieben(text: str, dx: float = 0.1) -> str:
    """Bohrung Ø20 um dx in X verschieben: Punkte der Bohrungsflaechen und ihrer Kanten (nicht die der
    Nachbarflaechen-Geometrie)."""
    d = p21.lese_text(text)
    eigene = _punkte_von(d, BOHRUNG)
    andere_flaechen = [e.id for e in d.of_type("ADVANCED_FACE") if e.id not in BOHRUNG]
    fremd = _punkte_von(d, [d.entities[f].args()[2].id for f in andere_flaechen])  # Flaechengeometrie der anderen
    for eid in sorted(eigene - fremd):
        e = d.entities[eid]
        x, y, z = e.args()[1]
        text = _ersetze_entitaet(text, eid, f"#{eid}=CARTESIAN_POINT('{e.args()[0]}',({_zahl(x + dx)},{_zahl(y)},"
                                            f"{_zahl(z)}));")
    return text


def bezuege_tauschen(text: str) -> str:
    """Bezugssystem .2 (A|B|C): zweites und drittes Fach tauschen -> A|C|B."""
    d = p21.lese_text(text)
    system = next(e for e in d.of_type("DATUM_SYSTEM") if len(e.args()[4]) == 3)
    fach_b, fach_c = (d.entities[r.id] for r in system.args()[4][1:])
    for fach, bezug in ((fach_b, fach_c.args()[4]), (fach_c, fach_b.args()[4])):
        a = fach.args()
        text = _ersetze_entitaet(text, fach.id, f"#{fach.id}=DATUM_REFERENCE_COMPARTMENT('{a[0]}',$,#{a[2].id},"
                                                f".F.,#{bezug.id},$);")
    return text


def bezuege_tauschen_einzeln(text: str, name: str) -> str:
    """Nur die Toleranz 'name' bekommt ein eigenes Bezugssystem mit zweitem und drittem Fach getauscht."""
    d = p21.lese_text(text)
    tol = next(e for e in d.of_type("GEOMETRIC_TOLERANCE") if e.args("GEOMETRIC_TOLERANCE")[0] == name)
    system = d.get(tol.args("GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE")[0][0])
    a = system.args()
    erstes, *rest = (d.entities[r.id] for r in a[4])
    n = max(d.entities) + 1
    neu = [f"#{n + i}=DATUM_REFERENCE_COMPARTMENT('',$,#{f.args()[2].id},.F.,#{f.args()[4].id},$);"
           for i, f in enumerate([erstes] + rest[::-1])]
    faecher, sid = ",".join(f"#{n + i}" for i in range(len(neu))), n + len(neu)
    neu.append(f"#{sid}=DATUM_SYSTEM('{a[0]}',$,#{a[2].id},.F.,({faecher}));")
    muster = re.compile(rf"(^#{tol.id}=.*?GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE\(\()#{system.id}(\)\))",
                        re.M | re.S)
    text, k = muster.subn(rf"\g<1>#{sid}\g<2>", text, count=1)
    assert k == 1
    zeile = "\r\n" if "\r\n" in text else "\n"
    i = text.rindex("ENDSEC;")
    return text[:i] + zeile.join(neu) + zeile + text[i:]


def pmi_andere(text: str) -> str:
    """Andere PMI bei gleicher Geometrie: Toleranzart, Bezugsreihenfolge und ein Wert geaendert."""
    d = p21.lese_text(text)
    flach = next(e for e in d.entities.values() if e.is_a("FLATNESS_TOLERANCE"))
    zeile = re.compile(rf"^#{flach.id}=FLATNESS_TOLERANCE\(", re.M)
    text, n = zeile.subn(f"#{flach.id}=STRAIGHTNESS_TOLERANCE(", text)
    assert n == 1
    text = bezuege_tauschen(text)
    pos = next(e for e in d.of_type("GEOMETRIC_TOLERANCE") if e.args("GEOMETRIC_TOLERANCE")[0] == "Position.2")
    return _messwert(text, pos.args("GEOMETRIC_TOLERANCE")[2].id, 1.0)


def schnittansicht(text: str) -> str:
    """Kamera der Ansicht MBD_0 zur Schnittansicht machen (Ebene und Vereinigung zweier Ebenen, CAx-IF 9.4.3)."""
    d = p21.lese_text(text)
    kamera = next(e for e in d.of_type("CAMERA_MODEL_D3"))
    name, platz, volumen = kamera.args("CAMERA_MODEL_D3")[:3]
    neu, n = [], max(d.entities) + 1

    def ebene(ort, normale):
        nonlocal n
        p, r, a, e = n, n + 1, n + 2, n + 3
        n += 4
        neu.extend([f"#{p}=CARTESIAN_POINT('',({','.join(_zahl(x) for x in ort)}));",
                    f"#{r}=DIRECTION('',({','.join(_zahl(x) for x in normale)}));",
                    f"#{a}=AXIS2_PLACEMENT_3D('',#{p},#{r},$);", f"#{e}=PLANE('',#{a});"])
        return e
    durch_achse = ebene((0.0, ACHSE[1], 0.0), (0.0, 1.0, 0.0))
    links, oben = ebene((ACHSE[0], 0.0, 0.0), (-1.0, 0.0, 0.0)), ebene((0.0, 0.0, -25.0), (0.0, 0.0, 1.0))
    neu.append(f"#{n}=CAMERA_MODEL_D3_MULTI_CLIPPING_UNION('',(#{links},#{oben}));")
    text = _ersetze_entitaet(text, kamera.id, f"#{kamera.id}=CAMERA_MODEL_D3_MULTI_CLIPPING('{name}',#{platz.id},"
                                              f"#{volumen.id},(#{durch_achse},#{n}));")
    zeile = "\r\n" if "\r\n" in text else "\n"
    i = text.rindex("ENDSEC;")  # Ende der DATA-Sektion
    return text[:i] + zeile.join(neu) + zeile + text[i:]


# --- deutliche Aenderung: Geometrie mit OCCT, B-Rep in die Originaldatei einsetzen ---

VERSETZT = (855, 856)  # Bohrung Ø25 bei (160, 45) mit Mass Ø25: in +X versetzt
ENTFAELLT = (857, 858)  # Bohrung Ø25 bei (-160, -45), ohne PMI: gefuellt
GEFAST = (160.0, -45.0)  # Bohrung Ø25: Fase am oberen Rand (z = 0)
VERSATZ, FASE, R_25 = 15.0, 3.0, 12.5
NAHT = (0.877582561890371, -0.479425538604207)  # Richtung der Naht der Bohrungen Ø25 in der Datei
ENTFERNBAR = ("STYLED_ITEM", "OVER_RIDING_STYLED_ITEM", "GEOMETRIC_ITEM_SPECIFIC_USAGE",
              "ITEM_IDENTIFIED_REPRESENTATION_USAGE")  # verweisen nur auf Geometrie, fallen mit ihr weg


def bohrung_fuellen(form, flaechen):
    """Bohrungsflaechen entfernen und ihren Rand aus den Nachbarflaechen streichen (ohne Vereinigung gleicher
    Flaechen, die OCCTs Defeaturing nebenbei auf das ganze Teil anwendet)."""
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.BRepTools import BRepTools_ReShape
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_WIRE
    from OCC.Core.TopExp import TopExp_Explorer, topexp
    from OCC.Core.TopTools import TopTools_IndexedMapOfShape
    from OCC.Core.TopoDS import TopoDS_Iterator, topods
    rand = TopTools_IndexedMapOfShape()
    for f in flaechen:
        topexp.MapShapes(f, TopAbs_EDGE, rand)
    neu, builder = BRepTools_ReShape(), BRep_Builder()
    for f in flaechen:
        neu.Remove(f)
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        f = topods.Face(ex.Current())
        ex.Next()
        if any(f.IsSame(x) for x in flaechen):
            continue
        it, drahte, treffer = TopoDS_Iterator(f), [], False
        while it.More():
            w = it.Value()
            it.Next()
            kanten = TopExp_Explorer(w, TopAbs_EDGE)
            if w.ShapeType() == TopAbs_WIRE and kanten.More() and rand.Contains(kanten.Current()):
                treffer = True
            else:
                drahte.append(w)
        if treffer:
            ersatz = topods.Face(f.EmptyCopied())
            for w in drahte:
                builder.Add(ersatz, w)
            neu.Replace(f, ersatz)
    return neu.Apply(form)


def geometrie_deutlich(modell):
    """Bohrung versetzen (fuellen und neu bohren), eine Bohrung fuellen, Fase an einer dritten."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.BRepFilletAPI import BRepFilletAPI_MakeChamfer
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCC.Core.GeomAbs import GeomAbs_Circle
    from OCC.Core.ShapeUpgrade import ShapeUpgrade_ShapeDivideClosed
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_SOLID
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    form = bohrung_fuellen(modell.form, [modell.flaechen[modell.step_zu_flaeche[eid]] for eid in VERSETZT + ENTFAELLT])
    # wie das Original: Achse -Z, Naht in Richtung der alten Naht, zwei Halbschalen (sonst kein reiner Versatz)
    lage = gp_Ax2(gp_Pnt(160.0 + VERSATZ, 45.0, 1.0), gp_Dir(0, 0, -1), gp_Dir(*NAHT, 0.0))
    form = BRepAlgoAPI_Cut(form, BRepPrimAPI_MakeCylinder(lage, R_25, 52.0).Shape()).Shape()
    teilen = ShapeUpgrade_ShapeDivideClosed(form)
    teilen.Perform()
    form = teilen.Result()
    fase = BRepFilletAPI_MakeChamfer(form)
    ex = TopExp_Explorer(form, TopAbs_EDGE)
    while ex.More():
        k = topods.Edge(ex.Current())
        ex.Next()
        c = BRepAdaptor_Curve(k)
        if c.GetType() == GeomAbs_Circle and abs(c.Circle().Radius() - R_25) < 1e-6:
            m = c.Circle().Location()
            if math.dist((m.X(), m.Y(), m.Z()), (*GEFAST, 0.0)) < 1e-6:
                fase.Add(FASE, k)
    return TopExp_Explorer(fase.Shape(), TopAbs_SOLID).Current()


def _proben(form, n: int = 6) -> list:
    """Punkte im Inneren einer Flaeche (UV-Raster, nur innerhalb der Berandung) oder auf einer Kante (Mitte)."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.BRepClass import BRepClass_FaceClassifier
    from OCC.Core.BRepTools import breptools
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_IN
    from OCC.Core.gp import gp_Pnt2d
    if form.ShapeType() == TopAbs_EDGE:
        c = BRepAdaptor_Curve(form)
        return [c.Value((c.FirstParameter() + c.LastParameter()) / 2)]
    u0, u1, v0, v1 = breptools.UVBounds(form)
    flaeche, out = BRep_Tool.Surface(form), []
    for i in range(n):
        for j in range(n):
            u, v = u0 + (u1 - u0) * (i + 0.5) / n, v0 + (v1 - v0) * (j + 0.5) / n
            if BRepClass_FaceClassifier(form, gp_Pnt2d(u, v), 1e-7).State() == TopAbs_IN:
                out.append(flaeche.Value(u, v))
    return out


def _zuordnung(alt, neu, ids_alt, ids_neu, lage) -> dict[int, int | None]:
    """Alte -> neue STEP-Id gleicher Gestalt: die meisten Probepunkte (verschoben mit lage(id)) liegen darauf."""
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
    from OCC.Core.Bnd import Bnd_Box
    kandidaten = []
    for eid in ids_neu:
        f = neu.form_von_step(eid)
        box = Bnd_Box()
        brepbndlib.Add(f, box)
        box.Enlarge(1e-3)
        kandidaten.append((eid, f, box))
    out = {}
    for eid in ids_alt:
        treffer: dict[int, int] = {}
        for p in _proben(alt.form_von_step(eid)):
            p = p.Translated(lage(eid))
            punkt = BRepBuilderAPI_MakeVertex(p).Vertex()
            for nid, f, box in kandidaten:
                if not box.IsOut(p) and BRepExtrema_DistShapeShape(punkt, f).Value() < 1e-5:
                    treffer[nid] = treffer.get(nid, 0) + 1
        out[eid] = max(treffer, key=treffer.get) if treffer else None
    return out


def _anweisungen(text: str) -> tuple[str, dict[int, str], str]:
    """Kopf bis DATA;, Anweisungen (Id -> Rumpf ohne '#id='), Rest ab ENDSEC;."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    a, b = text.index("DATA;") + 5, text.rindex("ENDSEC;")
    out = {}
    for st in p21._statements(text[a:b]):
        m = re.match(r"^#(\d+)\s*=\s*(.*)$", st, re.S)
        if m:
            out[int(m.group(1))] = " ".join(m.group(2).split()) if "'" not in m.group(2) else m.group(2)
    return text[:a], out, text[b:]


def _verweise(rumpf: str) -> list[int]:
    return [int(x) for x in re.findall(r"#(\d+)", re.sub(r"'[^']*'", "''", rumpf))]


def _ersetze_verweise(rumpf: str, abbildung: dict[int, int]) -> str:
    """#id -> #abbildung[id] ausserhalb von Texten."""
    teile = re.split(r"('[^']*')", rumpf)
    return "".join(t if t.startswith("'") else re.sub(r"#(\d+)", lambda m: f"#{abbildung.get(int(m.group(1)),
                                                                                            int(m.group(1)))}", t)
                   for t in teile)


def _in_liste(rumpf: str, eid: int) -> bool:
    """Steht der Verweis in einer Liste mit weiteren Eintraegen?"""
    d = p21.lese_text(f"DATA;\n#1={rumpf};\nENDSEC;")

    def suche(werte) -> bool:
        for w in werte:
            if isinstance(w, list):
                if any(isinstance(x, p21.Ref) and x.id == eid for x in w) and len(w) > 1:
                    return True
                if suche(w):
                    return True
            elif isinstance(w, p21.Typed) and suche(w.args):
                return True
        return False
    return any(suche(args) for args in d.entities[1].parts.values())


def _entferne(st: dict[int, str], weg: set[int]):
    """Anweisungen entfernen; Verweise darauf aus Listen streichen, sonst die verweisende Anweisung mitnehmen.
    Was danach von niemandem mehr verwiesen wird (vorher schon), faellt ebenfalls weg."""
    zahl = {}
    for rumpf in st.values():
        for r in _verweise(rumpf):
            zahl[r] = zahl.get(r, 0) + 1
    while weg:
        for i in weg:
            for r in _verweise(st.pop(i, "")):
                zahl[r] = zahl.get(r, 1) - 1
        folge = set()
        for i, rumpf in list(st.items()):
            for r in set(_verweise(rumpf)) & weg:
                if _in_liste(rumpf, r):
                    rumpf = re.sub(rf",\s*#{r}(?!\d)", "", rumpf, count=1) if re.search(rf",\s*#{r}(?!\d)", rumpf) \
                        else re.sub(rf"#{r}(?!\d)\s*,\s*", "", rumpf, count=1)
                    zahl[r] -= 1
                else:
                    folge.add(i)
            st[i] = rumpf
        weg = folge | {i for i in st if i in zahl and zahl[i] <= 0}


def _huelle(st: dict[int, str], start) -> set[int]:
    out, offen = set(), list(start)
    while offen:
        i = offen.pop()
        if i in out or i not in st:
            continue
        out.add(i)
        offen += _verweise(st[i])
    return out


def _winkelfaktor(text: str) -> float:
    """Radiant (so schreibt OCCT) -> Winkeleinheit des B-Reps der Datei (NIST: Grad)."""
    from programm.kern.pmi_step import messwert_roh
    d = p21.lese_text(text)
    rep = next(iter(d.of_type("ADVANCED_BREP_SHAPE_REPRESENTATION")))
    for u in d.get(rep.args()[2]).args("GLOBAL_UNIT_ASSIGNED_CONTEXT")[0]:
        e = d.get(u)
        if e.is_a("PLANE_ANGLE_UNIT") and e.is_a("CONVERSION_BASED_UNIT"):
            return 1.0 / float(messwert_roh(d, e.args("CONVERSION_BASED_UNIT")[1])[0])
    return 1.0


def _kegelwinkel(rumpf: str, faktor: float) -> str:
    m = re.match(r"^(CONICAL_SURFACE\('[^']*',#\d+,[^,]+,)([^)]+)\)$", rumpf)
    return f"{m.group(1)}{_zahl(float(m.group(2)) * faktor)})" if m else rumpf


def form_einsetzen(text: str, modell, form, lage) -> str:
    """Das B-Rep der Datei durch 'form' ersetzen: Flaechen und verwiesene Kanten geometrisch zuordnen (lage(id):
    Verschiebung einer alten Flaeche), Verweise umhaengen, Weggefallenes samt Farben und PMI-Verweisen entfernen,
    neue Flaechen in der Farbe der uebrigen."""
    import tempfile
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from programm.kern.laden import lade_step
    pfad = os.path.join(tempfile.mkdtemp(), "form.stp")
    from OCC.Core.Interface import Interface_Static
    Interface_Static.SetIVal("write.surfacecurve.mode", 0)  # ohne Parameterkurven (wie die Originaldatei)
    w = STEPControl_Writer()
    w.Transfer(form, STEPControl_AsIs)
    w.Write(pfad)
    neu = lade_step(pfad)
    with open(pfad, encoding="latin-1") as f:
        _, st_neu, _ = _anweisungen(f.read())
    kopf, st, fuss = _anweisungen(text)
    brep = next(i for i, r in st.items() if r.startswith("MANIFOLD_SOLID_BREP"))
    alt_brep = _huelle(st, [brep])
    brep_neu = next(i for i, r in st_neu.items() if r.startswith("MANIFOLD_SOLID_BREP"))
    versatz = max(st)
    # Verweise von aussen auf Flaechen und Kanten des alten B-Reps
    aussen = {r for i, rumpf in st.items() if i not in alt_brep for r in _verweise(rumpf) if r in alt_brep}
    faces = [i for i in aussen if st[i].startswith("ADVANCED_FACE")]
    kanten = [i for i in aussen if st[i].startswith("EDGE_CURVE")]
    abb = {brep: brep_neu + versatz}
    for ids, art in ((faces, "ADVANCED_FACE"), (kanten, "EDGE_CURVE")):
        ziel = [i for i, r in st_neu.items() if r.startswith(art)]
        for a, b in _zuordnung(modell, neu, ids, ziel, lage).items():
            if b is not None:
                abb[a] = b + versatz
    for i in list(st):
        if i not in alt_brep:
            st[i] = _ersetze_verweise(st[i], abb)
    faktor = _winkelfaktor(text)
    for i in _huelle(st_neu, [brep_neu]):
        rumpf = _kegelwinkel(st_neu[i], faktor)
        st[i + versatz] = _ersetze_verweise(rumpf, {j: j + versatz for j in _verweise(rumpf)})
    # neue Flaechen ohne Vorgaenger: Farbe der uebrigen Flaechen, in derselben Praesentation
    erreicht = {b for b in abb.values()}
    farbe = [(i, r) for i, r in st.items() if r.startswith("STYLED_ITEM") and _verweise(r)[-1] in erreicht
             and st[_verweise(r)[-1]].startswith("ADVANCED_FACE")]
    if farbe:
        vorlage_id, vorlage = farbe[0]
        praes = next(i for i, r in st.items() if not r.startswith("STYLED_ITEM") and vorlage_id in _verweise(r))
        stil = re.search(r"\((#\d+(?:,\s*#\d+)*)\)", vorlage).group(1)
        n = max(st) + 1
        for i in _huelle(st_neu, [brep_neu]):
            if st_neu[i].startswith("ADVANCED_FACE") and i + versatz not in erreicht:
                st[n] = f"STYLED_ITEM('',({stil}),#{i + versatz})"
                st[praes] = re.sub(rf"#{vorlage_id}(?!\d)", f"#{vorlage_id},#{n}", st[praes], count=1)
                n += 1
    # altes B-Rep entfernen; was ausser Farben und Formverweisen noch darauf zeigt (z. B. geteilte Richtungen), bleibt
    halten = _huelle(st, [r for i, rumpf in st.items() if i not in alt_brep and not
                          rumpf.startswith(ENTFERNBAR) for r in _verweise(rumpf) if r in alt_brep])
    _entferne(st, alt_brep - halten)
    zeile = "\r\n" if "\r\n" in text else "\n"
    return kopf + zeile + "".join(f"#{i}={st[i]};{zeile}" for i in sorted(st)) + fuss


def pmi_entfernen(text: str, eid: int) -> str:
    """Eine semantische PMI samt ihrer Darstellung (ueber DRAUGHTING_MODEL_ITEM_ASSOCIATION) entfernen."""
    kopf, st, fuss = _anweisungen(text)
    weg = {eid} | {_verweise(r)[-1] for r in st.values() if r.startswith("DRAUGHTING_MODEL_ITEM_ASSOCIATION") and
                   _verweise(r)[0] == eid}
    _entferne(st, weg)
    zeile = "\r\n" if "\r\n" in text else "\n"
    return kopf + zeile + "".join(f"#{i}={st[i]};{zeile}" for i in sorted(st)) + fuss


def deutlich(text: str) -> str:
    """Beispiel fuer den Vergleich: deutliche Geometrie- und PMI-Aenderungen in einer Datei."""
    import tempfile
    from OCC.Core.gp import gp_Vec
    from programm.kern import step_schreiben
    from programm.kern.laden import lade_step
    from programm.kern.pmi import BezugsRef, Pmi
    from programm.ui.lader import lade_alles
    modell = lade_step(QUELLE)
    lage = {f: gp_Vec(VERSATZ, 0, 0) for f in VERSETZT}
    text = form_einsetzen(text, modell, geometrie_deutlich(modell), lambda eid: lage.get(eid, gp_Vec()))
    d = p21.lese_text(text)
    pos1 = next(e for e in d.of_type("GEOMETRIC_TOLERANCE") if e.args("GEOMETRIC_TOLERANCE")[0] == "Position.1")
    text = _messwert(text, pos1.args("GEOMETRIC_TOLERANCE")[2].id, 0.5)
    text = bezuege_tauschen_einzeln(text, "Position.2")
    senkrecht = next(e for e in d.entities.values() if e.is_a("PERPENDICULARITY_TOLERANCE"))
    text = pmi_entfernen(text, senkrecht.id)
    ordner = tempfile.mkdtemp()
    zwischen, ziel = os.path.join(ordner, "a.stp"), os.path.join(ordner, "b.stp")
    with open(zwischen, "w", encoding="latin-1", newline="") as f:
        f.write(text)
    g = lade_alles(zwischen)
    loch = next(p.flaechen for p in g.pmi if p.typ == "Size_Diameter" and p.nennwert == 25.0)
    pos = Pmi("toleranz", "Position", "Position.4", wert=0.4, material="M", modifikatoren=["Diameter"],
              bezuege=[BezugsRef("A", 1), BezugsRef("B", 2), BezugsRef("C", 3)], flaechen=set(loch))
    pos.quelle, pos.nummer, pos.step_id = "eigen", 900, -1
    bericht = step_schreiben.schreibe(zwischen, ziel, g.pmi + [pos], g.modell)
    assert bericht.neu == [900] and bericht.dargestellt == [900], bericht
    with open(ziel, encoding="latin-1", newline="") as f:
        return f.read()


# --- Netze ("Scans") ---

def _netz(form, abweichung: float = 0.03, laenge: float = 40.0):
    """Dreiecksnetz der Form wie ein Scan: neu vernetzt (feine Sehnen), Ebenen auf hoechstens 'laenge' unterteilt."""
    import numpy as np
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.TopoDS import topods
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepTools import breptools
    from OCC.Core.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane
    breptools.Clean(form)  # vorhandene (grobe) Vernetzung verwerfen
    BRepMesh_IncrementalMesh(form, abweichung, False, 0.3, True)
    punkte, dreiecke, n = [], [], 0
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        f = topods.Face(ex.Current())
        ex.Next()
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation(f, loc)
        if tri is None:
            continue
        t = loc.Transformation()
        p = np.array([[q.X(), q.Y(), q.Z()] for q in (tri.Node(i).Transformed(t)
                                                     for i in range(1, tri.NbNodes() + 1))])
        ds = np.array([tri.Triangle(i).Get() for i in range(1, tri.NbTriangles() + 1)]) - 1
        if f.Orientation() == TopAbs_REVERSED:
            ds = ds[:, [0, 2, 1]]
        # wie ein Scanner: Punkte auch im Inneren der Flaechen. Ebenen beliebig teilen; Zylinder und Kegel nur
        # die langen (achsparallelen) Kanten - deren Mitten liegen exakt auf der Flaeche, Umfangssehnen nicht
        art = BRepAdaptor_Surface(f).GetType()
        if art == GeomAbs_Plane:
            p, ds = _teile_lange_kanten(p, ds, laenge)
        elif art == GeomAbs_Cone or (art == GeomAbs_Cylinder and BRepAdaptor_Surface(f).Cylinder().Radius() >= 3.0):
            # Mantellinien einmal halbieren: Punkte in halber Hoehe (Rundungen mit kleinem Radius nicht)
            p, ds = _teile_lange_kanten(p, ds, 6.0, runden=1)
        if art != GeomAbs_Plane:  # Knoten exakt auf die Flaeche (Sehnenmitten liegen sonst innen: Untermass)
            from OCC.Core.GeomAPI import GeomAPI_ProjectPointOnSurf
            from OCC.Core.gp import gp_Pnt
            geom = BRep_Tool.Surface(f)
            for i, q in enumerate(p):
                pr = GeomAPI_ProjectPointOnSurf(gp_Pnt(*map(float, q)), geom)
                if pr.IsDone() and pr.NbPoints():
                    fuss = pr.NearestPoint()
                    p[i] = (fuss.X(), fuss.Y(), fuss.Z())
        punkte.append(p)
        dreiecke.append(ds + n)
        n += len(p)
    return np.vstack(punkte), np.vstack(dreiecke)


def _teile_lange_kanten(p, t, laenge: float, runden: int = 1000):
    """Laengste Kante halbieren, bis keine Kante laenger als 'laenge' ist (Anzahl waechst nur mit der Flaeche);
    runden begrenzt die Teilungen je Dreieck."""
    import numpy as np
    p, t = [tuple(x) for x in p], [tuple(x) for x in t]
    fertig, offen = [], t
    for _ in range(runden):
        if not offen:
            break
        neu = []
        for a, b, c in offen:
            ecken = (a, b, c)
            kanten = [(np.linalg.norm(np.subtract(p[ecken[i]], p[ecken[(i + 1) % 3]])), i) for i in range(3)]
            lg, i = max(kanten)
            if lg <= laenge:
                fertig.append((a, b, c))
                continue
            u, v, w = ecken[i], ecken[(i + 1) % 3], ecken[(i + 2) % 3]
            p.append(tuple((np.add(p[u], p[v]) / 2).tolist()))
            m = len(p) - 1
            neu += [(u, m, w), (m, v, w)]
        offen = neu
    return np.array(p), np.array(fertig + offen, dtype=int)


def _knotennormalen(p, t):
    import numpy as np
    fn = np.cross(p[t[:, 1]] - p[t[:, 0]], p[t[:, 2]] - p[t[:, 0]])
    n = np.zeros_like(p)
    for k in range(3):
        np.add.at(n, t[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]


def schreibe_ply(pfad: str, p, t):
    """Binaeres PLY mit gemeinsamen Knoten (deutlich kleiner als STL)."""
    import numpy as np
    kopf = (f"ply\nformat binary_little_endian 1.0\ncomment 3DGmax Testdaten (aus NIST CTC-01)\n"
            f"element vertex {len(p)}\nproperty float x\nproperty float y\nproperty float z\n"
            f"element face {len(t)}\nproperty list uchar int vertex_indices\nend_header\n")
    flaechen = np.zeros(len(t), dtype=[("n", "u1"), ("i", "<i4", 3)])
    flaechen["n"], flaechen["i"] = 3, t
    with open(pfad, "wb") as f:
        f.write(kopf.encode("ascii"))
        f.write(np.asarray(p, "<f4").tobytes())
        f.write(flaechen.tobytes())


def schreibe_stl(pfad: str, p, t):
    """Binaeres STL."""
    import numpy as np
    a, b, c = p[t[:, 0]], p[t[:, 1]], p[t[:, 2]]
    n = np.cross(b - a, c - a)
    n /= np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
    daten = np.zeros(len(t), dtype=[("n", "<f4", 3), ("a", "<f4", 3), ("b", "<f4", 3), ("c", "<f4", 3),
                                    ("attr", "<u2")])
    daten["n"], daten["a"], daten["b"], daten["c"] = n, a, b, c
    with open(pfad, "wb") as f:
        f.write(b"3DGmax Testdaten (aus NIST CTC-01)".ljust(80, b" "))
        f.write(np.uint32(len(t)).tobytes())
        f.write(daten.tobytes())


SCAN_LAGE = (2.5, (1.0, 1.0, 1.0), (12.0, -7.0, 3.0))  # Drehung (Grad) um Achse, Verschiebung (mm)


def _als_scan(p, t, rauschen: float = 0.005, zufall: int = 7):
    """Rauschen entlang der Knotennormalen, dann gedreht und verschoben (der Scan liegt nicht im CAD-System)."""
    import numpy as np
    rng = np.random.default_rng(zufall)
    p = p + _knotennormalen(p, t) * rng.normal(0.0, rauschen, (len(p), 1))
    winkel, achse, verschiebung = SCAN_LAGE
    k = np.asarray(achse) / np.linalg.norm(achse)
    w = np.radians(winkel)
    kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    rot = np.eye(3) + np.sin(w) * kx + (1 - np.cos(w)) * kx @ kx
    return p @ rot.T + np.asarray(verschiebung)


def _ctc01_form():
    from programm.kern.laden import lade_step
    return lade_step(QUELLE).form


def scan_fehlerhaft(form):
    """Fase 3 mm an der laengsten senkrechten Aussenkante, Delle und Welligkeit (im CAD-System)."""
    import numpy as np
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCC.Core.BRepFilletAPI import BRepFilletAPI_MakeChamfer
    from OCC.Core.GCPnts import GCPnts_AbscissaPoint
    from OCC.Core.GeomAbs import GeomAbs_Line, GeomAbs_Plane
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    from programm.kern.pmi_lesen import lies_pmi
    from programm.kern.laden import lade_step
    modell = lade_step(QUELLE)
    kanten = []
    ex = TopExp_Explorer(form, TopAbs_EDGE)
    while ex.More():
        e = topods.Edge(ex.Current())
        ex.Next()
        c = BRepAdaptor_Curve(e)
        if c.GetType() == GeomAbs_Line and abs(c.Line().Direction().Z()) > 0.99:
            kanten.append((GCPnts_AbscissaPoint.Length(c), e))
    for _laenge, e in sorted(kanten, key=lambda k: -k[0]):  # laengste geeignete Kante (konvex, zwei Ebenen)
        try:
            fase = BRepFilletAPI_MakeChamfer(form)
            fase.Add(3.0, e)
            neu = fase.Shape()
        except RuntimeError:
            continue
        form = neu
        break
    p, t = _netz(form)
    # Ebenheitsflaeche aus der PMI des Originals: Welligkeit 0.3 mm (Spannweite) senkrecht zur Flaeche
    flach = next(x for x in lies_pmi(modell) if x.typ == "Flatness")
    fl = modell.flaechen[sorted(flach.flaechen)[0]]
    s = BRepAdaptor_Surface(fl)
    ebene = s.Plane()
    o = np.array([ebene.Location().X(), ebene.Location().Y(), ebene.Location().Z()])
    n = np.array([ebene.Axis().Direction().X(), ebene.Axis().Direction().Y(), ebene.Axis().Direction().Z()])
    auf = np.abs((p - o) @ n) < 1e-6
    x = (p - o) @ np.array([ebene.XAxis().Direction().X(), ebene.XAxis().Direction().Y(), ebene.XAxis().Direction().Z()])
    p[auf] += np.outer(0.15 * np.sin(x[auf] / 6.0), n)
    # Delle 0.4 mm in der hoechsten Ebene (Gaussglocke, Radius 8 mm) nahe der Mitte
    oben = np.isclose(p[:, 2], p[:, 2].max(), atol=1e-6)
    mitte = p[oben].mean(axis=0)
    r2 = np.sum((p[:, :2] - mitte[:2]) ** 2, axis=1)
    p[oben, 2] -= 0.4 * np.exp(-r2[oben] / (2 * 4.0 ** 2))
    del GeomAbs_Plane, TopAbs_FACE
    return p, t


def main():
    os.makedirs(ZIEL, exist_ok=True)
    with open(QUELLE, encoding="latin-1", newline="") as f:
        text = f.read()
    varianten = {"ctc01_pmi.stp": pmi_aendern(text), "ctc01_geo.stp": bohrung_aufweiten(text)}
    varianten["ctc01_geo_pmi.stp"] = mass_20_auf_21(varianten["ctc01_geo.stp"])
    varianten["ctc01_pmi_andere.stp"] = pmi_andere(text)
    varianten["ctc01_geo_klein.stp"] = bohrung_verschieben(text)
    varianten["ctc01_geo_klein_pmi_andere.stp"] = pmi_andere(varianten["ctc01_geo_klein.stp"])
    varianten["ctc01_schnittansicht.stp"] = schnittansicht(text)
    varianten["ctc01_geo_pmi_deutlich.stp"] = deutlich(text)
    for name, inhalt in varianten.items():
        with open(os.path.join(ZIEL, name), "w", encoding="latin-1", newline="") as f:
            f.write(inhalt)
        print("geschrieben:", name)
    form = _ctc01_form()
    p, t = _netz(form)
    schreibe_ply(os.path.join(ZIEL, "ctc01_scan.ply"), _als_scan(p, t), t)
    p, t = scan_fehlerhaft(form)
    schreibe_ply(os.path.join(ZIEL, "ctc01_scan_fehler.ply"), _als_scan(p, t, zufall=8), t)
    print("geschrieben: ctc01_scan.ply, ctc01_scan_fehler.ply")


if __name__ == "__main__":
    main()
