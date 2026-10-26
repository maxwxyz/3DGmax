"""Materialvergleich zweier Staende: hinzugekommenes und entferntes Volumen (Boolesche Operationen, ohne Qt).

neu und alt werden im System des alten Stands verglichen (Ausrichtung angewendet). Ergebnis: Formen und Volumen
von 'dazu' (neu ohne alt) und 'weg' (alt ohne neu). Kleine Reste unterhalb der Toleranz werden verworfen.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Material:
    dazu: object  # TopoDS_Shape oder None
    weg: object
    vol_dazu: float  # mm3
    vol_weg: float
    teile_dazu: int
    teile_weg: int


def _koerper(form) -> list:
    from OCC.Core.TopAbs import TopAbs_SOLID
    from OCC.Core.TopExp import TopExp_Explorer
    out, ex = [], TopExp_Explorer(form, TopAbs_SOLID)
    while ex.More():
        out.append(ex.Current())
        ex.Next()
    return out


def _nur_koerper(form):
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_Compound
    teile = _koerper(form)
    if not teile:
        return None
    comp = TopoDS_Compound()
    bb = BRep_Builder()
    bb.MakeCompound(comp)
    for k in teile:
        bb.Add(comp, k)
    return comp


def _bereinigt(form, toleranz: float):
    """Kopie mit begrenzten Toleranzen: grosse Kanten-/Punkttoleranzen lassen kleine Aenderungen verschwinden."""
    if form is None:
        return None
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Copy
    from OCC.Core.ShapeFix import ShapeFix_Shape, ShapeFix_ShapeTolerance
    kopie = BRepBuilderAPI_Copy(form).Shape()
    ShapeFix_ShapeTolerance().LimitTolerance(kopie, 1e-7, max(toleranz / 10, 1e-5))
    fix = ShapeFix_Shape(kopie)
    fix.Perform()
    return fix.Shape()


def _vol(form) -> float:
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    g = GProp_GProps()
    brepgprop.VolumeProperties(form, g)
    return abs(g.Mass())


def _differenz(a, b, mindest: float):
    """a ohne b; nur Koerper mit Volumen ueber 'mindest'."""
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.TopoDS import TopoDS_Compound
    schnitt = BRepAlgoAPI_Cut(a, b)
    schnitt.SetFuzzyValue(1e-4)
    schnitt.Build()
    if not schnitt.IsDone():
        raise ValueError("Boolesche Operation fehlgeschlagen")
    teile = [k for k in _koerper(schnitt.Shape()) if _vol(k) > mindest]
    comp = TopoDS_Compound()
    bb = BRep_Builder()
    bb.MakeCompound(comp)
    for k in teile:
        bb.Add(comp, k)
    return (comp if teile else None), sum(_vol(k) for k in teile), len(teile)


def berechne(form_alt, form_neu, trsf=None, toleranz: float = 0.01) -> Material:
    """trsf: Ausrichtung neu -> alt (gp_Trsf) oder None."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    if trsf is not None:
        form_neu = BRepBuilderAPI_Transform(form_neu, trsf, True).Shape()
    mindest = max(toleranz, 1e-3) ** 3 * 10  # Splitter aus Rundungsfehlern ignorieren
    form_alt, form_neu = _nur_koerper(form_alt), _nur_koerper(form_neu)  # Hilfsgeometrie stoert die Booleschen Op.
    form_alt, form_neu = _bereinigt(form_alt, toleranz), _bereinigt(form_neu, toleranz)
    if form_alt is None or form_neu is None:
        raise ValueError("Materialvergleich braucht geschlossene Körper")
    dazu, v_dazu, n_dazu = _differenz(form_neu, form_alt, mindest)
    weg, v_weg, n_weg = _differenz(form_alt, form_neu, mindest)
    return Material(dazu, weg, v_dazu, v_weg, n_dazu, n_weg)
