"""Baugruppenstruktur aus dem XCAF-Dokument."""

from __future__ import annotations

from dataclasses import dataclass, field

from OCC.Core.TDF import TDF_Label, TDF_LabelSequence
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer

from .laden import StepModell


@dataclass
class Knoten:
    name: str
    form: object  # TopoDS_Shape mit Lage
    kinder: list["Knoten"] = field(default_factory=list)
    baugruppe: bool = False
    hilfsgeometrie: bool = False  # keine Flaechen (z. B. Punkte, Linien)
    nummer: int = 0  # laufende Nummer (Schluessel fuer die Ansicht)

    def blaetter(self):
        if not self.kinder:
            yield self
        for k in self.kinder:
            yield from k.blaetter()

    def alle(self):
        yield self
        for k in self.kinder:
            yield from k.alle()


def _hat_flaechen(form) -> bool:
    return TopExp_Explorer(form, TopAbs_FACE).More()


def _name(st, label) -> str:
    name = label.GetLabelName()
    if st.IsComponent(label):
        ref = TDF_Label()
        if st.GetReferredShape(label, ref):
            name = ref.GetLabelName() or name
    return name if name and not name.startswith("=>") else ""


def _knoten(st, label, zaehler, lage=None) -> Knoten:
    """lage: aufsummierte Lage der uebergeordneten Baugruppen (Unterbaugruppen liefern nur ihre eigene)."""
    form = st.GetShape(label)
    if lage is not None and not lage.IsIdentity():
        form = form.Moved(lage)
    ref = TDF_Label()
    proto = ref if st.IsComponent(label) and st.GetReferredShape(label, ref) else label
    k = Knoten(_name(st, label) or "Teil", form, baugruppe=st.IsAssembly(proto))
    zaehler[0] += 1
    k.nummer = zaehler[0]
    if k.baugruppe:
        teile = TDF_LabelSequence()
        st.GetComponents(proto, teile)
        k.kinder = [_knoten(st, teile.Value(i), zaehler, form.Location()) for i in range(1, teile.Length() + 1)]
    k.hilfsgeometrie = not k.kinder and not _hat_flaechen(form)
    return k


def lies_baum(modell: StepModell) -> Knoten:
    """Wurzel 'Modell' mit allen freien Formen als Kinder."""
    import os
    st = modell.shape_tool
    frei = TDF_LabelSequence()
    st.GetFreeShapes(frei)
    zaehler = [0]
    wurzel = Knoten(os.path.basename(modell.pfad), modell.form, baugruppe=True)
    wurzel.kinder = [_knoten(st, frei.Value(i), zaehler) for i in range(1, frei.Length() + 1)]
    return wurzel
