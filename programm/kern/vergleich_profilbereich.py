"""Getrimmte Toleranzbereiche mit Innenloechern in der gemeinsamen Einbaulage vergleichen."""

from collections import defaultdict
from itertools import chain
from math import isfinite

from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCC.Core.BRepCheck import BRepCheck_Analyzer
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopTools import TopTools_ListOfShape

from ..i18n import tr
from .profilteilflaeche import _inhalt


def hat_ausschnitt(p):
    return bool(getattr(p, "profilausschnitte", None) or p.profilteil_ids or getattr(p, "profilbereich_offen", False))


def _formen(p, modell, lage):
    teile = getattr(p, "profilausschnitte", {})
    if getattr(p, "profilbereich_offen", False) or set(p.profilteil_ids) - teile.keys():
        return None
    formen = defaultdict(list)
    for idx in p.flaechen:
        if modell is None or not 0 <= idx < len(modell.flaechen):
            return None
        formen[idx].append(modell.flaechen[idx])
    for idx, f in teile.values():
        if idx not in p.flaechen:
            formen[idx].append(f)
    if lage is not None:
        return {idx: [f.Moved(lage) for f in fs] for idx, fs in formen.items()}
    return formen


def _rest(f, werkzeuge, toleranz):
    """Nacheinander abziehen. Mehrere ueberlappende Werkzeuge koennen sonst falsche Reste ergeben."""
    inhalt = _inhalt(f)
    if not isfinite(inhalt) or inhalt <= 0 or not BRepCheck_Analyzer(f).IsValid():
        raise ValueError
    for g in werkzeuge:
        a, b = TopTools_ListOfShape(), TopTools_ListOfShape()
        a.Append(f)
        b.Append(g)
        op = BRepAlgoAPI_Cut()
        op.SetArguments(a)
        op.SetTools(b)
        op.SetNonDestructive(True)
        op.SetFuzzyValue(toleranz)
        op.Build()
        if not op.IsDone() or op.Shape().IsNull():
            raise ValueError
        f = op.Shape()
        if not TopExp_Explorer(f, TopAbs_FACE).More():
            return 0.
        neu = _inhalt(f)
        if not isfinite(neu) or neu < 0 or neu > inhalt + max(1e-10, inhalt * 1e-9) or not BRepCheck_Analyzer(f).IsValid():
            raise ValueError
        inhalt = neu
    return inhalt


def _differenz(quellen, andere, toleranz):
    # Jeder Punkt der eigenen Vereinigung darf nur einmal zur Differenz beitragen.
    return sum(_rest(f, [*andere, *quellen[:i]], toleranz) for i, f in enumerate(quellen))


def bereichsfeld(a, b, zuordnung, zuordnung_ab, modelle, lage, toleranz):
    """Reste beider Vereinigungen je Gruppe zusammengehoeriger Traegerflaechen in mm2."""
    offen = ("profilbereich_offen", "", tr("Flächendeckung nicht eindeutig"))
    alt, neu = _formen(a, modelle[0], None), _formen(b, modelle[1], lage)
    if not alt or not neu:
        return offen
    # Auch ein in einer Revision geteilter Traeger kann mehr als einen Partner haben.
    graph = defaultdict(set)
    for links, rechts in chain(((l, r) for r, l in zuordnung.items()), (zuordnung_ab or {}).items()):
        if rechts not in neu and links not in alt:
            continue
        graph[0, links].add((1, rechts))
        graph[1, rechts].add((0, links))
    knoten = {(0, idx) for idx in alt} | {(1, idx) for idx in neu}
    if knoten - graph.keys():
        return offen
    nur_alt = nur_neu = 0.
    try:
        while knoten:
            start = knoten.pop()
            gruppe, stapel = {start}, [start]
            while stapel:
                rest = graph[stapel.pop()] - gruppe
                gruppe.update(rest)
                stapel.extend(rest)
            knoten.difference_update(gruppe)
            links = [f for seite, idx in sorted(gruppe) if seite == 0 for f in alt.get(idx, ())]
            rechts = [f for seite, idx in sorted(gruppe) if seite == 1 for f in neu.get(idx, ())]
            nur_alt += _differenz(links, rechts, toleranz)
            nur_neu += _differenz(rechts, links, toleranz)
    except (RuntimeError, ValueError):
        return offen
    if max(nur_alt, nur_neu) > max(1e-12, toleranz**2):
        text = tr("Nur in diesem Stand: {:.6g} mm²")
        return "profilteilflaeche", text.format(nur_alt), text.format(nur_neu)
    return None
