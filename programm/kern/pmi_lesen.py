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

from . import p21
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
