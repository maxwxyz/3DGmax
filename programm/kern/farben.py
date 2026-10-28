"""Flaechenfarben aus der STEP-Datei (STYLED_ITEM -> ... -> COLOUR_RGB)."""

from __future__ import annotations

from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer

from .laden import StepModell
from .p21 import P21Datei, Ref

VORDEFINIERT = {
    "red": (1, 0, 0), "green": (0, 1, 0), "blue": (0, 0, 1), "yellow": (1, 1, 0),
    "magenta": (1, 0, 1), "cyan": (0, 1, 1), "black": (0, 0, 0), "white": (1, 1, 1),
}
# Entitaeten, deren Flaechen eine Farbe erben (Koerper, Schalen)
KOERPER = ("MANIFOLD_SOLID_BREP", "BREP_WITH_VOIDS", "SHELL_BASED_SURFACE_MODEL", "CLOSED_SHELL",
           "OPEN_SHELL", "FACETED_BREP", "MAPPED_ITEM")


def _flaechenfarbe(datei: P21Datei, ref, tiefe=0):
    """Erste Flaechenfarbe unterhalb eines Stils (Kurvenstile werden uebergangen)."""
    e = datei.get(ref) if isinstance(ref, Ref) else None
    if e is None or tiefe > 8 or e.is_a("CURVE_STYLE"):
        return None
    if e.is_a("COLOUR_RGB"):
        return tuple(float(x) for x in e.args("COLOUR_RGB")[1:4])
    if e.is_a("DRAUGHTING_PRE_DEFINED_COLOUR"):
        return VORDEFINIERT.get(e.args("DRAUGHTING_PRE_DEFINED_COLOUR")[0])
    for werte in e.parts.values():
        for w in werte:
            for r in (w if isinstance(w, list) else [w]):
                farbe = _flaechenfarbe(datei, r, tiefe + 1) if isinstance(r, Ref) else None
                if farbe is not None:
                    return farbe
    return None


def _stil_ziel(stil) -> Ref | None:
    """Gestaltetes Element eines STYLED_ITEM (name, styles, item). Zusammengesetzte Instanzen (z. B. CATIA:
    ANNOTATION_OCCURRENCE() ... STYLED_ITEM(...)) tragen die Argumente nur im Teil STYLED_ITEM; andere Teile sind
    leer - nicht den ersten Teil nehmen."""
    for teil in ("STYLED_ITEM", "OVER_RIDING_STYLED_ITEM", *stil.parts):
        args = stil.parts.get(teil)
        if args and len(args) >= 3 and isinstance(args[2], Ref):
            return args[2]
    return None


def flaechen_farben(modell: StepModell) -> dict[int, tuple[float, float, float]]:
    """Flaechenindex -> RGB (0..1). Koerperfarben zuerst, Flaechenfarben ueberschreiben."""
    datei = modell.datei
    if datei is None:
        return dict(getattr(modell, "prc_farben", {}))
    koerper, flaechen = {}, {}
    for s in datei.of_type("STYLED_ITEM") + datei.of_type("OVER_RIDING_STYLED_ITEM"):
        ref = _stil_ziel(s)
        if ref is None:
            continue
        ziel = datei.get(ref)
        if ziel is None:
            continue
        if ziel.is_a("ADVANCED_FACE") or ziel.is_a("FACE_SURFACE"):
            farbe = _flaechenfarbe(datei, Ref(s.id))
            idx = modell.step_zu_flaeche.get(ziel.id)
            if farbe and idx is not None:
                flaechen[idx] = farbe
        elif any(ziel.is_a(k) for k in KOERPER):
            farbe = _flaechenfarbe(datei, Ref(s.id))
            form = modell.form_von_step(ziel.id) if farbe else None
            if form is not None:
                ex = TopExp_Explorer(form, TopAbs_FACE)
                while ex.More():
                    idx = modell.flaechen_index(ex.Current())
                    if idx is not None:
                        koerper[idx] = farbe
                    ex.Next()
    koerper.update(flaechen)
    return koerper
