"""PMI-Liste eines Modells: semantisch aus der STEP-Datei, OCCT (XCAF) zur Gegenpruefung.

Gruende fuer den eigenen Leser (Versuch an NIST-Modellen, siehe docs/Machbarkeit.md):
- OCCT verliert die Flaechenzuordnung, wenn die Datei SET_REPRESENTATION_ITEM nutzt (CTC-01, Bezuege B/C).
- pythonocc bindet XCAFDoc_GeomTolerance nicht ein (Toleranzrahmen sonst nicht lesbar).
- Jede PMI behaelt ihre STEP-#ID; damit lassen sich Ansichten und Praesentation sicher zuordnen.
"""

from __future__ import annotations

import OCC.Core.XCAFDimTolObjects as D
from OCC.Core.TDF import TDF_LabelSequence
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.XCAFDoc import (XCAFDoc_Datum, XCAFDoc_Dimension, XCAFDoc_DimTolTool,
                              XCAFDoc_DocumentTool)

from . import p21, pmi_ableiten
from .p21 import DMIA_PH
from .laden import StepModell
from .pmi import BEZUG, HINWEIS, MASS, Pmi


def _enum_namen(praefix: str) -> dict[int, str]:
    return {getattr(D, n): n[len(praefix):] for n in dir(D) if n.startswith(praefix)}


MASS_TYP = _enum_namen("XCAFDimTolObjects_DimensionType_")
MASS_MOD = _enum_namen("XCAFDimTolObjects_DimensionModif_")
BEZUG_MOD = _enum_namen("XCAFDimTolObjects_DatumSingleModif_")
FORM_ABW = _enum_namen("XCAFDimTolObjects_DimensionFormVariance_")
GRAD = _enum_namen("XCAFDimTolObjects_DimensionGrade_")


def _labels(fn) -> list:
    seq = TDF_LabelSequence()
    fn(seq)
    return [seq.Value(i) for i in range(1, seq.Length() + 1)]


def _seq_liste(seq, namen: dict[int, str]) -> list[str]:
    return [namen.get(seq.Value(i), str(seq.Value(i))) for i in range(1, seq.Length() + 1)]


def _text(hstr) -> str:
    try:
        return hstr.ToCString() if hstr is not None else ""
    except Exception:
        return ""


def _flaechen_von(modell: StepModell, label) -> tuple[set[int], int]:
    """Zugeordnete Flaechenindizes und Anzahl sonstiger Teilformen eines PMI-Labels."""
    erste, zweite = TDF_LabelSequence(), TDF_LabelSequence()
    XCAFDoc_DimTolTool.GetRefShapeLabel(label, erste, zweite)
    flaechen, sonst = set(), 0
    for seq in (erste, zweite):
        for i in range(1, seq.Length() + 1):
            form = modell.shape_tool.GetShape(seq.Value(i))
            gefunden = False
            ex = TopExp_Explorer(form, TopAbs_FACE)
            while ex.More():
                idx = modell.flaechen_index(ex.Current())
                if idx is not None:
                    flaechen.add(idx)
                    gefunden = True
                ex.Next()
            sonst += 0 if gefunden else 1
    return flaechen, sonst


def _lies_mass(modell: StepModell, label) -> Pmi:
    o = XCAFDoc_Dimension.Set(label).GetObject()
    typ = MASS_TYP.get(o.GetType(), str(o.GetType()))
    p = Pmi(MASS, typ=typ, name=_text(o.GetSemanticName()))
    p.flaechen, p.kanten = _flaechen_von(modell, label)
    p.grafisch = _hat_form(o.GetPresentation())
    if typ == "DimensionPresentation":
        p.semantisch = False
        p.nur_grafik_text = _text(o.GetPresentationName())
        return p
    wert = o.GetValue()
    if o.IsDimWithRange():
        p.nennwert = wert
        p.unten, p.oben, p.grenzmass = o.GetLowerBound(), o.GetUpperBound(), True
    elif o.IsDimWithPlusMinusTolerance():
        p.nennwert = wert
        # OCCT liefert das untere Abmass als Betrag (Nennmass - Mindestmass)
        p.oben, p.unten = o.GetUpperTolValue(), -o.GetLowerTolValue()
    elif abs(wert) > 0 or _hat_wert(o):
        p.nennwert = wert
    if o.IsDimWithClassOfTolerance():
        ok, bohrung, abw, grad = o.GetClassOfTolerance()
        if ok:
            fa = FORM_ABW.get(abw, "")
            p.passung = (fa.upper() if bohrung else fa.lower()) + GRAD.get(grad, "").replace("IT", "")
    p.modifikatoren = _seq_liste(o.GetModifiers(), MASS_MOD)
    return p


def _hat_form(form) -> bool:
    return form is not None and not form.IsNull()


def _hat_wert(o) -> bool:
    try:
        vals = o.GetValues()
        return vals is not None and not vals.IsNull() and vals.Length() > 0
    except Exception:
        return False


def _lies_bezuege(modell: StepModell, dt) -> list[Pmi]:
    """Bezuege je Buchstabe zusammenfassen (XCAF legt je Toleranzrahmen eine Kopie an)."""
    je_name: dict[str, Pmi] = {}
    for label in _labels(dt.GetDatumLabels):
        o = XCAFDoc_Datum.Set(label).GetObject()
        name = _text(o.GetName())
        p = je_name.setdefault(name, Pmi(BEZUG, typ="DatumTarget" if o.IsDatumTarget() else "Datum",
                                         name=name))
        fl, sonst = _flaechen_von(modell, label)
        p.flaechen |= fl
        p.kanten = max(p.kanten, sonst)
        p.grafisch |= _hat_form(o.GetPresentation())
    return list(je_name.values())


# --- Ergaenzung aus der STEP-Datei ---

# Verknuepfung Aspekt -> Geometrie (GISU ist Untertyp von IIRU)
NUTZUNGEN = ("ITEM_IDENTIFIED_REPRESENTATION_USAGE", "GEOMETRIC_ITEM_SPECIFIC_USAGE")

def flaechen_von_aspekt(datei: p21.P21Datei, modell: StepModell, aspekt_id: int,
                        tiefe: int = 0) -> set[int]:
    """Flaechen eines SHAPE_ASPECT ueber ITEM_IDENTIFIED_REPRESENTATION_USAGE (auch Gruppen)."""
    if tiefe > 6:
        return set()
    out: set[int] = set()
    for rid in datei.referrers().get(aspekt_id, []):
        e = datei.entities[rid]
        nutzung = next((t for t in NUTZUNGEN if e.is_a(t)), None)
        if nutzung:
            args = e.args(nutzung)
            if isinstance(args[2], p21.Ref) and args[2].id == aspekt_id:
                out |= _flaechen_aus_item(modell, args[4])
        elif e.is_a("SHAPE_ASPECT_RELATIONSHIP") or e.is_a("SHAPE_ASPECT_DERIVING_RELATIONSHIP"):
            args = e.args(next(iter(e.parts)))
            # Gruppe/Verbund: relating = Gruppe, related = Teil
            if args[2] == p21.Ref(aspekt_id) and isinstance(args[3], p21.Ref):
                kind = datei.get(args[3])
                if kind is not None and not kind.is_a("DATUM"):
                    out |= flaechen_von_aspekt(datei, modell, args[3].id, tiefe + 1)
    return out


def _flaechen_aus_item(modell: StepModell, item) -> set[int]:
    if isinstance(item, p21.Ref):
        idx = modell.step_zu_flaeche.get(item.id)
        return {idx} if idx is not None else set()
    if isinstance(item, p21.Typed):
        out = set()
        for teil in item.args:
            out |= _flaechen_aus_item(modell, teil)
        return out
    if isinstance(item, list):
        out = set()
        for teil in item:
            out |= _flaechen_aus_item(modell, teil)
        return out
    return set()


TEILFORM_TYPEN = ("EDGE_CURVE", "ORIENTED_EDGE", "VERTEX_POINT", "TRIMMED_CURVE", "GEOMETRIC_CURVE_SET", "LINE",
                  "POLYLINE", "B_SPLINE_CURVE_WITH_KNOTS", "CIRCLE", "CARTESIAN_POINT", "COMPOSITE_CURVE")


def _refs(item) -> list[int]:
    if isinstance(item, p21.Ref):
        return [item.id]
    if isinstance(item, p21.Typed):
        return [x for teil in item.args for x in _refs(teil)]
    if isinstance(item, list):
        return [x for teil in item for x in _refs(teil)]
    return []


def _punkt(datei: p21.P21Datei, ref) -> tuple | None:
    e = datei.get(ref)
    if e is None or not e.is_a("CARTESIAN_POINT"):
        return None
    return tuple(float(x) for x in e.args("CARTESIAN_POINT")[1])


def _richtung(datei: p21.P21Datei, ref) -> tuple | None:
    e = datei.get(ref)
    if e is None or not e.is_a("DIRECTION"):
        return None
    return tuple(float(x) for x in e.args("DIRECTION")[1])


def _parameterwert(trimmung) -> float | None:
    """Parameter aus einer Trimmangabe: Zahl oder PARAMETER_VALUE(x) in der Liste."""
    for x in trimmung if isinstance(trimmung, list) else [trimmung]:
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, p21.Typed) and x.typ == "PARAMETER_VALUE" and x.args:
            return float(x.args[0])
    return None


def _kurven_aus_datei(datei: p21.P21Datei, eid: int, tiefe: int = 0) -> list:
    """Kanten aus Konstruktionsgeometrie, die OCCT nicht als Form uebertraegt (z. B. Gewindezylinder als
    GEOMETRIC_CURVE_SET): begrenzte Linien (Parameter entlang des Vektors), Kreise (voll), Punkte."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeVertex
    from OCC.Core.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt
    e = datei.get(p21.Ref(eid))
    if e is None or tiefe > 4:
        return []
    if e.is_a("GEOMETRIC_CURVE_SET") or e.is_a("GEOMETRIC_SET"):
        teil = "GEOMETRIC_CURVE_SET" if e.is_a("GEOMETRIC_CURVE_SET") else "GEOMETRIC_SET"
        return [k for r in e.args(teil)[1] if isinstance(r, p21.Ref) for k in _kurven_aus_datei(datei, r.id, tiefe + 1)]
    if e.is_a("CARTESIAN_POINT"):
        q = _punkt(datei, p21.Ref(eid))
        return [BRepBuilderAPI_MakeVertex(gp_Pnt(*q)).Vertex()] if q else []
    if e.is_a("TRIMMED_CURVE"):
        _n, basis, t1, t2, _s, art = e.args("TRIMMED_CURVE")[:6]
        b = datei.get(basis)
        if b is not None and b.is_a("LINE") and str(getattr(art, "name", art)).upper() == "PARAMETER":
            _ln, start, vektor = b.args("LINE")
            v = datei.get(vektor)
            q, (d, laenge) = _punkt(datei, start), (_richtung(datei, v.args("VECTOR")[1]), float(v.args("VECTOR")[2]))
            u1, u2 = _parameterwert(t1), _parameterwert(t2)
            if q and d and u1 is not None and u2 is not None:
                a = gp_Pnt(*(q[i] + d[i] * laenge * u1 for i in range(3)))
                z = gp_Pnt(*(q[i] + d[i] * laenge * u2 for i in range(3)))
                return [BRepBuilderAPI_MakeEdge(a, z).Edge()] if a.Distance(z) > 1e-9 else []
        return _kurven_aus_datei(datei, basis.id, tiefe + 1) if isinstance(basis, p21.Ref) else []
    if e.is_a("CIRCLE"):
        _n, lage, r = e.args("CIRCLE")
        pl = datei.get(lage)
        if pl is None or not pl.is_a("AXIS2_PLACEMENT_3D"):
            return []
        _pn, ort, achse, ref = pl.args("AXIS2_PLACEMENT_3D")
        q, n = _punkt(datei, ort), _richtung(datei, achse) or (0.0, 0.0, 1.0)
        return [BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(*q), gp_Dir(*n)), float(r))).Edge()] if q else []
    return []


def teilformen_von_aspekt(datei: p21.P21Datei, modell: StepModell, aspekt_id: int, tiefe: int = 0) -> list:
    """Kanten und Punkte eines SHAPE_ASPECT (Toleranzen an Kanten/Punkten) als OCCT-Formen."""
    if tiefe > 6 or getattr(modell, "_reader", None) is None:
        return []
    out = []
    for rid in datei.referrers().get(aspekt_id, []):
        e = datei.entities[rid]
        nutzung = next((t for t in NUTZUNGEN if e.is_a(t)), None)
        if nutzung:
            args = e.args(nutzung)
            if isinstance(args[2], p21.Ref) and args[2].id == aspekt_id:
                for eid in _refs(args[4]):
                    ziel = datei.get(p21.Ref(eid))
                    if ziel is not None and any(ziel.is_a(t) for t in TEILFORM_TYPEN):
                        form = modell.form_von_step(eid)
                        if form is not None:
                            out.append(form)
                        else:  # Konstruktionsgeometrie ohne uebertragene Form
                            out += _kurven_aus_datei(datei, eid)
        elif e.is_a("SHAPE_ASPECT_RELATIONSHIP"):
            args = e.args("SHAPE_ASPECT_RELATIONSHIP")
            if args[2] == p21.Ref(aspekt_id) and isinstance(args[3], p21.Ref):
                kind = datei.get(args[3])
                if kind is not None and not kind.is_a("DATUM"):
                    out += teilformen_von_aspekt(datei, modell, args[3].id, tiefe + 1)
    return out


def bezugs_flaechen_aus_datei(modell: StepModell) -> dict[str, set[int]]:
    """Buchstabe -> Flaechen, ueber DATUM_FEATURE --SHAPE_ASPECT_RELATIONSHIP--> DATUM."""
    datei = modell.datei
    out: dict[str, set[int]] = {}
    for sar in datei.of_type("SHAPE_ASPECT_RELATIONSHIP"):
        args = sar.args("SHAPE_ASPECT_RELATIONSHIP")
        ziel = datei.get(args[3]) if isinstance(args[3], p21.Ref) else None
        if ziel is None or not ziel.is_a("DATUM"):
            continue
        buchstabe = ziel.args("DATUM")[4]
        out.setdefault(buchstabe, set()).update(flaechen_von_aspekt(datei, modell, args[2].id))
    # manche Systeme verknuepfen die Geometrie direkt mit dem DATUM (z. B. NIST FTC-06)
    for d in datei.of_type("DATUM"):
        fl = flaechen_von_aspekt(datei, modell, d.id)
        if fl:
            out.setdefault(d.args("DATUM")[4], set()).update(fl)
    return out


def lies_bezuege_step(modell: StepModell) -> list[Pmi]:
    """Bezuege je Buchstabe aus der Datei, mit Flaechen der Bezugselemente."""
    datei = modell.datei
    flaechen = bezugs_flaechen_aus_datei(modell)
    out: dict[str, Pmi] = {}
    for e in sorted(datei.of_type("DATUM"), key=lambda e: e.id):
        name = e.args("DATUM")[4]
        p = out.setdefault(name, Pmi(BEZUG, typ="Datum", name=name, quelle="step", step_id=e.id))
        p.flaechen |= flaechen.get(name, set())
        p.grafisch |= _bezug_hat_grafik(datei, e.id)
    return list(out.values())


def _bezug_hat_grafik(datei: p21.P21Datei, datum_id: int) -> bool:
    for rid in datei.referrers().get(datum_id, []):
        r = datei.entities[rid]
        if r.is_a("SHAPE_ASPECT_RELATIONSHIP"):
            merkmal = r.args("SHAPE_ASPECT_RELATIONSHIP")[2]
            if any(datei.entities[x].is_a("DRAUGHTING_MODEL_ITEM_ASSOCIATION")
                   or datei.entities[x].is_a(DMIA_PH) for x in datei.referrers().get(merkmal.id, [])):
                return True
    return False


def lies_bezugsstellen(modell: StepModell) -> list[Pmi]:
    """Bezugsstellen (Datum Targets) als eigene Eintraege, Name = Buchstabe + Nummer (z. B. A1)."""
    datei = modell.datei
    out = []
    for teil in ("PLACED_DATUM_TARGET_FEATURE", "DATUM_TARGET"):
        for e in sorted(datei.of_type(teil), key=lambda e: e.id):
            if teil == "DATUM_TARGET" and e.is_a("PLACED_DATUM_TARGET_FEATURE"):
                continue
            args = e.args(teil)
            art, nummer = (args[1] or ""), str(args[4] or "")
            buchstabe = ""
            for rid in datei.referrers().get(e.id, []):
                r = datei.entities[rid]
                if r.is_a("SHAPE_ASPECT_RELATIONSHIP"):
                    ziel = datei.get(r.args("SHAPE_ASPECT_RELATIONSHIP")[3])
                    if ziel is not None and ziel.is_a("DATUM"):
                        buchstabe = ziel.args("DATUM")[4]
            p = Pmi(BEZUG, typ="DatumTarget", name=f"{buchstabe}{nummer}", quelle="step", step_id=e.id)
            if art:
                p.modifikatoren.append(art)
            p.flaechen = flaechen_von_aspekt(datei, modell, e.id)
            p.grafisch = _bezug_hat_grafik(datei, e.id) or any(
                datei.entities[x].is_a("DRAUGHTING_MODEL_ITEM_ASSOCIATION") or datei.entities[x].is_a(DMIA_PH)
                for x in datei.referrers().get(e.id, []))
            out.append(p)
    return out


def ergaenze_hinweise(pmi: list[Pmi], grafik: dict) -> list[Pmi]:
    """Callouts ohne Semantik (Notizen, Texte) als Hinweise anhaengen; verknuepft ueber die Callout-#ID."""
    vorhanden = {p.step_id for p in pmi}
    for cid in sorted(grafik):
        g = grafik[cid]
        if g.pmi_ids & vorhanden or g.doppelt or g.leer():
            continue
        p = Pmi(HINWEIS, typ="Note", name=g.name, nur_grafik_text=g.name or tr_hinweis(),
                semantisch=False, grafisch=True, quelle="step", step_id=cid)
        felder = pmi_ableiten.ableiten(g)  # nur grafisch: Art und Werte aus Text/Markup ableiten (zu pruefen)
        if felder is not None:
            for k, v in felder.items():
                setattr(p, k, v)
            p.name = felder.get("name") or g.name  # Bezug: Buchstabe (Suche datum:A, Bezugssystem)
            p.quelle = pmi_ableiten.ABGELEITET
        g.pmi_ids.add(cid)
        pmi.append(p)
    for i, p in enumerate(pmi, 1):
        p.nummer = i
    return pmi


def tr_hinweis() -> str:
    return "Hinweis"


def lies_pmi_xcaf(modell: StepModell) -> list[Pmi]:
    """Masse und Bezuege so, wie OCCT sie liest (Gegenpruefung, Formate ohne STEP-Datei)."""
    dt = XCAFDoc_DocumentTool.DimTolTool(modell.doc.Main())
    liste = [_lies_mass(modell, l) for l in _labels(dt.GetDimensionLabels)]
    return liste + _lies_bezuege(modell, dt)


def lies_pmi(modell: StepModell) -> list[Pmi]:
    """Semantische PMI: aus der STEP-Datei, sonst aus XCAF."""
    from .pmi_step import lies_masse, lies_toleranzen
    if getattr(modell, "qif", None) is not None:
        zu = modell.qif_flaechen
        return modell.qif.merkmale(lambda fid: modell.flaechen_index(zu[fid]) if fid in zu else None)
    if modell.datei is None:
        liste = lies_pmi_xcaf(modell)
    else:
        liste = lies_masse(modell) + lies_toleranzen(modell) + lies_bezuege_step(modell) + \
            lies_bezugsstellen(modell)
    for i, p in enumerate(liste, 1):
        p.nummer = i
    return liste
