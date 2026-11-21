"""Semantische STEP-Textattribute am Zielformelement eines Toleranzrahmens."""

from collections import Counter
from dataclasses import dataclass

from .p21 import DMIA_PH, Ref
from .pmi_step import TOL_ARTEN, _rahmengrund


@dataclass(frozen=True)
class Merkmalstext:
    aspekt: int
    eigenschaft: int
    darstellung: int
    grafiken: tuple[int, ...]
    zeilen: tuple[str, ...]
    vollstaendig: bool

    def vergleich(self, zeilen):
        if not self.vollstaendig:
            return "offen"
        # Die Items einer REPRESENTATION sind eine Menge. Jede Textzeile bleibt als Einheit erhalten.
        blatt = [" ".join(t.split()) for t in zeilen if t.strip()]
        quelle = [" ".join(t.split()) for t in self.zeilen]
        if len(quelle) == 1:
            return "gleich" if " ".join(blatt) == quelle[0] else "geaendert"
        if Counter(blatt) == Counter(quelle):
            return "gleich"
        if Counter(" ".join(blatt).split()) == Counter(" ".join(quelle).split()):
            return "offen"
        return "geaendert"


def aspekte_am_callout(datei, nr):
    """Nur explizite Zuordnungen des Callouts zu Formelementen."""
    ziel = set()
    for i in datei.referrers().get(nr, ()):
        e = datei.get(i)
        a = e.parts.get("DRAUGHTING_MODEL_ITEM_ASSOCIATION", e.parts.get(DMIA_PH, ()))
        if len(a) < 5 or a[4] != Ref(nr) or not isinstance(a[2], Ref):
            continue
        ent = datei.get(a[2])
        if ent and any(t.endswith("SHAPE_ASPECT") or t in ("DATUM_FEATURE", "DATUM_TARGET") for t in ent.parts):
            ziel.add(ent.id)
    return ziel


def toleranzziel(datei, nr):
    e = datei.get(nr)
    if e is None or not (e.is_a("GEOMETRIC_TOLERANCE") or any(t in TOL_ARTEN for t in e.parts)):
        return None
    grund, _ = _rahmengrund(e)
    if len(grund) < 4 or not isinstance(grund[3], Ref):
        return None
    aspekt = datei.get(grund[3])
    if aspekt and any(t.endswith("SHAPE_ASPECT") or t in ("DATUM_FEATURE", "DATUM_TARGET") for t in aspekt.parts):
        return aspekt.id
    return None


def _grafiken(datei, prop, eltern):
    grafiken = set()
    for e in eltern:
        a = e.parts.get("DRAUGHTING_MODEL_ITEM_ASSOCIATION", e.parts.get(DMIA_PH, ()))
        if len(a) < 5 or a[2] != Ref(prop) or not isinstance(a[4], Ref):
            continue
        g = datei.get(a[4])
        if g and g.is_a("DRAUGHTING_CALLOUT"):
            grafiken.add(g.id)
    return tuple(sorted(grafiken))


def texte_am_aspekt(datei, aspekt):
    rueck = datei.referrers()
    for nr in rueck.get(aspekt, ()):
        p = datei.get(nr)
        a = p.parts.get("PROPERTY_DEFINITION", ())
        if len(a) != 3 or a[0] != "semantic text" or a[2] != Ref(aspekt):
            continue
        eltern = [datei.get(n) for n in rueck.get(nr, ())]
        grafiken = _grafiken(datei, nr, eltern)
        for link in eltern:
            a = link.parts.get("PROPERTY_DEFINITION_REPRESENTATION", ())
            if len(a) != 2 or a[0] != Ref(nr) or not isinstance(a[1], Ref):
                continue
            rep = datei.get(a[1])
            daten = rep.parts.get("REPRESENTATION", ()) if rep else ()
            if len(daten) < 2 or not isinstance(daten[1], list):
                continue
            zeilen = []
            for ref in daten[1]:
                e = datei.get(ref) if isinstance(ref, Ref) else None
                teile = e.parts.get("DESCRIPTIVE_REPRESENTATION_ITEM", ()) if e else ()
                if len(teile) == 2 and isinstance(teile[1], str) and teile[1].strip():
                    zeilen.append(teile[1])
            if zeilen:
                yield Merkmalstext(aspekt, nr, rep.id, grafiken, tuple(zeilen), len(zeilen) == len(daten[1]))
