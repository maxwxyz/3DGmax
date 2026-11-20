"""Semantische Form- und Lagetoleranzen direkt aus der STEP-Datei (AP242) lesen.

pythonocc bindet XCAFDoc_GeomTolerance nicht ein; deshalb werden Toleranzrahmen hier aus dem
Entitaetsgraphen gelesen (nach CAx-IF Recommended Practice for PMI Representation and Presentation).
Werte werden in mm umgerechnet (wie OCCT die Geometrie liefert).
"""

from __future__ import annotations

import math

from .laden import StepModell
from .p21 import DMIA_PH, Entity, Enum, P21Datei, Ref, Typed
from .pmi import TOLERANZ, BezugsRef, Pmi
from .pmi_lesen import flaechen_von_aspekt, teilformen_von_aspekt

TOL_ARTEN = {
    "STRAIGHTNESS_TOLERANCE": "Straightness", "FLATNESS_TOLERANCE": "Flatness",
    "ROUNDNESS_TOLERANCE": "CircularityOrRoundness", "CYLINDRICITY_TOLERANCE": "Cylindricity",
    "LINE_PROFILE_TOLERANCE": "ProfileOfLine", "SURFACE_PROFILE_TOLERANCE": "ProfileOfSurface",
    "ANGULARITY_TOLERANCE": "Angularity", "PERPENDICULARITY_TOLERANCE": "Perpendicularity",
    "PARALLELISM_TOLERANCE": "Parallelism", "POSITION_TOLERANCE": "Position",
    "CONCENTRICITY_TOLERANCE": "Concentricity", "COAXIALITY_TOLERANCE": "Coaxiality",
    "SYMMETRY_TOLERANCE": "Symmetry", "CIRCULAR_RUNOUT_TOLERANCE": "CircularRunout",
    "TOTAL_RUNOUT_TOLERANCE": "TotalRunout",
}

# Modifikatoren nach den Namen in pmi.py / XCAF
TOL_MODS = {
    "MAXIMUM_MATERIAL_REQUIREMENT": "Maximum_Material_Requirement",
    "LEAST_MATERIAL_REQUIREMENT": "Least_Material_Requirement",
    "ALL_AROUND": "All_Around", "ALL_OVER": "All_Over", "FREE_STATE": "Free_State",
    "TANGENT_PLANE": "Tangent_Plane", "STATISTICAL_TOLERANCE": "Statistical_Tolerance",
    "COMMON_ZONE": "Common_Zone", "SEPARATE_REQUIREMENT": "Separate_Requirement",
    "RECIPROCITY_REQUIREMENT": "Reciprocity_Requirement", "LINE_ELEMENT": "Line_Element",
    "EACH_RADIAL_ELEMENT": "Each_Radial_Element", "ANY_CROSS_SECTION": "Any_Cross_Section",
    "MAJOR_DIAMETER": "Major_Diameter", "MINOR_DIAMETER": "Minor_Diameter",
    "PITCH_DIAMETER": "Pitch_Diameter", "NOT_CONVEX": "Not_Convex",
}
BEZUG_MODS = {
    "MAXIMUM_MATERIAL_REQUIREMENT": "MaximumMaterialRequirement",
    "LEAST_MATERIAL_REQUIREMENT": "LeastMaterialRequirement",
    "FREE_STATE": "FreeState", "BASIC": "Basic", "TRANSLATION": "Translation",
    "ORIENTATION": "Orientation", "CONTACTING_FEATURE": "ContactingFeature",
    "POINT": "Point", "LINE": "Line", "PLANE": "Plane",
}


# --- Masse und Einheiten ---

def _laengenfaktor(datei: P21Datei, ref, besucht=()) -> float | None:
    e = datei.get(ref) if isinstance(ref, Ref) else None
    if e is None or e.id in besucht:
        return None
    if e.is_a("SI_UNIT"):
        vorsatz, name = e.args("SI_UNIT")[:2]
        if not isinstance(name, Enum) or name.name != "METRE":
            return None
        if vorsatz is None:
            return 1000.0
        potenz = {"EXA": 18, "PETA": 15, "TERA": 12, "GIGA": 9, "MEGA": 6, "KILO": 3, "HECTO": 2,
                  "DECA": 1, "DECI": -1, "CENTI": -2, "MILLI": -3, "MICRO": -6, "NANO": -9,
                  "PICO": -12, "FEMTO": -15, "ATTO": -18}.get(getattr(vorsatz, "name", None))
        return 10. ** (3 + potenz) if potenz is not None else None
    if e.is_a("CONVERSION_BASED_UNIT"):
        _, mass = e.args("CONVERSION_BASED_UNIT")[:2]
        wert, einheit = messwert_roh(datei, mass)
        faktor = _laengenfaktor(datei, einheit, (*besucht, e.id))
        if faktor is not None and isinstance(wert, (int, float)) and math.isfinite(wert) and wert > 0:
            return wert * faktor
    return None


def einheit_mm(datei: P21Datei, ref) -> float:
    """Faktor einer Laengeneinheit nach mm (1.0 wenn unbekannt)."""
    return _laengenfaktor(datei, ref) or 1.0


def messwert_roh(datei: P21Datei, ref):
    """(Zahl, Einheit-Ref) eines MEASURE_WITH_UNIT."""
    e = datei.get(ref) if isinstance(ref, Ref) else None
    if e is None:
        return (ref.args[0], None) if isinstance(ref, Typed) else (None, None)
    for teil in ("MEASURE_WITH_UNIT", "LENGTH_MEASURE_WITH_UNIT", "PLANE_ANGLE_MEASURE_WITH_UNIT"):
        if e.is_a(teil) and len(e.args(teil)) >= 2:
            wert, einheit = e.args(teil)[:2]
            return (wert.args[0] if isinstance(wert, Typed) else wert), einheit
    return None, None


def laenge_mm(datei: P21Datei, ref) -> float | None:
    wert, einheit = messwert_roh(datei, ref)
    if wert is None:
        return None
    return float(wert) * einheit_mm(datei, einheit)


def _gesicherte_laenge(datei, ref):
    wert, einheit = messwert_roh(datei, ref)
    faktor = _laengenfaktor(datei, einheit)
    if faktor is not None and isinstance(wert, (int, float)) and math.isfinite(wert):
        return wert * faktor
    return None


# --- Bezugssystem ---

def _bezug_name(datei: P21Datei, ref) -> str:
    if isinstance(ref, Typed):  # z. B. COMMON_DATUM_LIST((#1,#2))
        teile = ref.args[0] if ref.args and isinstance(ref.args[0], list) else ref.args
        return "-".join(_bezug_name(datei, t) for t in teile)
    if isinstance(ref, list):
        return "-".join(_bezug_name(datei, t) for t in ref)
    e = datei.get(ref) if isinstance(ref, Ref) else None
    if e is None:
        return "?"
    if e.is_a("DATUM"):
        return e.args("DATUM")[4]
    if e.is_a("COMMON_DATUM") or e.is_a("DATUM_REFERENCE_ELEMENT") or e.is_a("GENERAL_DATUM_REFERENCE"):
        return _bezug_name(datei, _basis(e))
    return "?"


def _basis(e: Entity):
    for teil in ("DATUM_REFERENCE_ELEMENT", "DATUM_REFERENCE_COMPARTMENT", "GENERAL_DATUM_REFERENCE"):
        if e.is_a(teil):
            return e.args(teil)[4]
    return None


def _bezug_mods(datei: P21Datei, e: Entity) -> list[str]:
    for teil in ("DATUM_REFERENCE_COMPARTMENT", "DATUM_REFERENCE_ELEMENT", "GENERAL_DATUM_REFERENCE"):
        if e.is_a(teil) and len(e.args(teil)) > 5 and e.args(teil)[5]:
            out = []
            for m in e.args(teil)[5]:
                if isinstance(m, Typed) and m.args and isinstance(m.args[0], Enum):
                    out.append(BEZUG_MODS.get(m.args[0].name, m.args[0].name))
                elif isinstance(m, Enum):
                    out.append(BEZUG_MODS.get(m.name, m.name))
                elif isinstance(m, Ref):
                    merkmal = datei.get(m)
                    out.append(merkmal.typ if merkmal is not None else "?")
                elif isinstance(m, Typed):
                    out.append(m.typ)
            return out
    return []


def _element_modifikatoren(datei, basis):
    """Modifikatoren am Einzelbezug einer COMMON_DATUM_LIST gelten nur fuer diesen Sitz."""
    if isinstance(basis, Typed) and basis.typ == "COMMON_DATUM_LIST":
        basis = basis.args[0] if len(basis.args) == 1 and isinstance(basis.args[0], list) else basis.args
    out = {}
    if isinstance(basis, list):
        for ref in basis:
            e = datei.get(ref) if isinstance(ref, Ref) else None
            if e is not None and (mods := _bezug_mods(datei, e)):
                out[_bezug_name(datei, ref)] = mods
    return out


def _bezugssystem(datei: P21Datei, refs) -> list[BezugsRef]:
    out: list[BezugsRef] = []
    for r in refs or []:
        e = datei.get(r)
        if e is None:
            continue
        if e.is_a("DATUM_SYSTEM"):
            for stelle, fach in enumerate(e.args("DATUM_SYSTEM")[4], 1):
                fe = datei.get(fach)
                basis = _basis(fe)
                out.append(BezugsRef(_bezug_name(datei, basis), stelle, _bezug_mods(datei, fe),
                                     _element_modifikatoren(datei, basis)))
        elif e.is_a("DATUM_REFERENCE"):
            # AP242 e1 / AP214: DATUM_REFERENCE(precedence, datum)
            prez, dat = e.args("DATUM_REFERENCE")[:2]
            out.append(BezugsRef(_bezug_name(datei, dat), int(prez)))
    return out


# --- Toleranzrahmen ---

def _zonen(datei: P21Datei) -> dict[int, list[Entity]]:
    """Toleranz-ID -> TOLERANCE_ZONE-Entitaeten."""
    out: dict[int, list[Entity]] = {}
    for z in datei.of_type("TOLERANCE_ZONE"):
        for r in z.args("TOLERANCE_ZONE")[4] or []:
            if isinstance(r, Ref):
                out.setdefault(r.id, []).append(z)
    return out


def _projektionsdaten(p, modell, definition):
    """Projektionsursprung, Laenge und ggf. Versatz (einfache oder komplexe STEP-Instanz)."""
    mit_versatz = "PROJECTED_ZONE_DEFINITION_WITH_OFFSET"
    basis = "PROJECTED_ZONE_DEFINITION"
    args = definition.args(mit_versatz) if definition.is_a(mit_versatz) else definition.args(basis)
    if definition.is_a("TOLERANCE_ZONE_DEFINITION") and definition.is_a(basis):
        args = definition.args("TOLERANCE_ZONE_DEFINITION") + definition.args(basis)
        if definition.is_a(mit_versatz):
            args += definition.args(mit_versatz)
    if len(args) != (5 if definition.is_a(mit_versatz) else 4):
        return
    _, grenzen, ende, hoehe, *versatz = args
    if grenzen or not isinstance(ende, Ref):
        return
    p.projektionsflaechen = sorted(flaechen_von_aspekt(modell.datei, modell, ende.id))
    p.zonen_wert = _gesicherte_laenge(modell.datei, hoehe)
    p.projektionsversatz = _gesicherte_laenge(modell.datei, versatz[0]) if versatz else 0.


def _zonen_info(modell: StepModell, p: Pmi, zonen: list[Entity]):
    datei = modell.datei
    projektionen = []
    for z in zonen:
        form = datei.get(z.args("TOLERANCE_ZONE")[5])
        if form is not None and "cylindrical" in str(form.args("TOLERANCE_ZONE_FORM")[0]).lower():
            p.modifikatoren.append("Diameter")
        elif form is not None and "spherical" in str(form.args("TOLERANCE_ZONE_FORM")[0]).lower():
            p.modifikatoren.append("SphericalDiameter")
        for rid in datei.referrers().get(z.id, []):
            pz = datei.entities[rid]
            if pz.is_a("PROJECTED_ZONE_DEFINITION") or pz.is_a("PROJECTED_ZONE_DEFINITION_WITH_OFFSET"):
                projektionen.append(pz)
            elif pz.is_a("RUNOUT_ZONE_DEFINITION"):
                p.zone = "Runout"
            elif pz.is_a("NON_UNIFORM_ZONE_DEFINITION"):
                p.zone = "NonUniform"
    if projektionen:
        eindeutig = len(projektionen) == len(zonen) == 1 and not p.zone
        p.zone = "Projected"
        if eindeutig:
            _projektionsdaten(p, modell, projektionen[0])


def _lies_rahmen(modell: StepModell, e: Entity, zonen: dict[int, list[Entity]]) -> Pmi:
    datei = modell.datei
    if e.is_a("GEOMETRIC_TOLERANCE"):
        grund = e.args("GEOMETRIC_TOLERANCE")
        bezug_refs = (e.args("GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE")[0]
                      if e.is_a("GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE") else None)
    else:
        # einfache Entitaet, z. B. FLATNESS_TOLERANCE(name, beschr, betrag, aspekt[, bezuege])
        grund = e.args()
        bezug_refs = grund[4] if len(grund) > 4 else None
    name, _, betrag, aspekt = grund[:4]
    typ = next((TOL_ARTEN[t] for t in e.parts if t in TOL_ARTEN), "None")
    p = Pmi(TOLERANZ, typ=typ, name=name or "", quelle="step", step_id=e.id)
    p.wert = laenge_mm(datei, betrag)
    if bezug_refs:
        p.bezuege = _bezugssystem(datei, bezug_refs)
    if e.is_a("GEOMETRIC_TOLERANCE_WITH_MODIFIERS"):
        for m in e.args("GEOMETRIC_TOLERANCE_WITH_MODIFIERS")[0] or []:
            if isinstance(m, Enum):
                p.modifikatoren.append(TOL_MODS.get(m.name, m.name))
    if e.is_a("MODIFIED_GEOMETRIC_TOLERANCE"):
        m = e.args("MODIFIED_GEOMETRIC_TOLERANCE")[-1]
        if isinstance(m, Enum) and m.name != "REGARDLESS_OF_FEATURE_SIZE":
            p.modifikatoren.append({"MAXIMUM_MATERIAL_CONDITION": "Maximum_Material_Requirement",
                                    "LEAST_MATERIAL_CONDITION": "Least_Material_Requirement"}.get(m.name, m.name))
    if e.is_a("GEOMETRIC_TOLERANCE_WITH_MAXIMUM_TOLERANCE"):
        args = e.args("GEOMETRIC_TOLERANCE_WITH_MAXIMUM_TOLERANCE")
        p.maximum_toleranz = _gesicherte_laenge(datei, args[0]) if args else None
        if p.maximum_toleranz is None:
            p.modifikatoren.append("Maximum_Tolerance")
    if "Maximum_Material_Requirement" in p.modifikatoren:
        p.material = "M"
    elif "Least_Material_Requirement" in p.modifikatoren:
        p.material = "L"
    if e.is_a("UNEQUALLY_DISPOSED_GEOMETRIC_TOLERANCE"):
        p.modifikatoren.append(f"UZ {laenge_mm(datei, e.args('UNEQUALLY_DISPOSED_GEOMETRIC_TOLERANCE')[0])}")
    if e.is_a("GEOMETRIC_TOLERANCE_WITH_DEFINED_UNIT"):
        p.modifikatoren.append(f"je {laenge_mm(datei, e.args('GEOMETRIC_TOLERANCE_WITH_DEFINED_UNIT')[0])}")
    _zonen_info(modell, p, zonen.get(e.id, []))
    if p.material or p.zone == "Projected":
        p.wert = _gesicherte_laenge(datei, betrag)
    if isinstance(aspekt, Ref):
        p.flaechen = flaechen_von_aspekt(datei, modell, aspekt.id)
        ziel = datei.get(aspekt)
        if ziel is not None and ziel.is_a("PRODUCT_DEFINITION_SHAPE"):
            p.ganzes_teil = True  # Toleranz fuer das ganze Teil (z. B. Flaechenprofil "All Over")
        elif not p.flaechen:  # Toleranz an Kanten, Punkten oder Konstruktionsgeometrie
            p.teilformen = teilformen_von_aspekt(datei, modell, aspekt.id)
    p.grafisch = _hat_praesentation(datei, e.id)
    return p


def _hat_praesentation(datei: P21Datei, eid: int) -> bool:
    for rid in datei.referrers().get(eid, []):
        r = datei.entities[rid]
        if r.is_a("DRAUGHTING_MODEL_ITEM_ASSOCIATION") or r.is_a(DMIA_PH):
            return True
    return False


def lies_toleranzen(modell: StepModell) -> list[Pmi]:
    datei = modell.datei
    zonen = _zonen(datei)
    toleranzen = datei.of_types_by_id(("GEOMETRIC_TOLERANCE", *TOL_ARTEN))
    return [_lies_rahmen(modell, e, zonen) for e in toleranzen]


# --- Masse ---

GROESSEN = {
    "diameter": "Size_Diameter", "radius": "Size_Radius", "thickness": "Size_Thickness",
    "spherical diameter": "Size_SphericalDiameter", "spherical radius": "Size_SphericalRadius",
    "curve length": "Size_CurveLength", "toroidal minor diameter": "Size_ToroidalMinorDiameter",
    "toroidal major diameter": "Size_ToroidalMajorDiameter",
    "toroidal minor radius": "Size_ToroidalMinorRadius",
    "toroidal major radius": "Size_ToroidalMajorRadius",
}
LAGEN = {
    "linear distance": "Location_LinearDistance", "curved distance": "Location_CurvedDistance",
    "linear distance centre outer": "Location_LinearDistance_FromCenterToOuter",
    "linear distance centre inner": "Location_LinearDistance_FromCenterToInner",
    "linear distance outer centre": "Location_LinearDistance_FromOuterToCenter",
    "linear distance outer outer": "Location_LinearDistance_FromOuterToOuter",
    "linear distance outer inner": "Location_LinearDistance_FromOuterToInner",
    "linear distance inner centre": "Location_LinearDistance_FromInnerToCenter",
    "linear distance inner outer": "Location_LinearDistance_FromInnerToOuter",
    "linear distance inner inner": "Location_LinearDistance_FromInnerToInner",
}


def winkel_grad(datei: P21Datei, ref) -> float | None:
    wert, einheit = messwert_roh(datei, ref)
    if wert is None:
        return None
    e = datei.get(einheit) if isinstance(einheit, Ref) else None
    if e is not None and e.is_a("SI_UNIT"):
        return float(wert) * 57.29577951308232  # Radiant -> Grad
    return float(wert)  # 'degree' als CONVERSION_BASED_UNIT


def _ist_winkel(datei: P21Datei, ref) -> bool:
    e = datei.get(ref) if isinstance(ref, Ref) else None
    return e is not None and (e.is_a("PLANE_ANGLE_MEASURE_WITH_UNIT") or any(
        isinstance(a, Typed) and a.typ == "PLANE_ANGLE_MEASURE"
        for a in e.args("MEASURE_WITH_UNIT")[:1]) if e.is_a("MEASURE_WITH_UNIT") else False)


def _wert(datei: P21Datei, ref) -> float | None:
    return winkel_grad(datei, ref) if _ist_winkel(datei, ref) else laenge_mm(datei, ref)


def _item_name(e: Entity) -> str:
    return e.args("REPRESENTATION_ITEM")[0] if e.is_a("REPRESENTATION_ITEM") else ""


def _werte_der_darstellung(datei: P21Datei, dim_id: int) -> dict[str, float]:
    """'nominal value', 'upper limit', 'lower limit' einer Masseintragung."""
    out: dict[str, float] = {}
    for rid in datei.referrers().get(dim_id, []):
        r = datei.entities[rid]
        if not r.is_a("DIMENSIONAL_CHARACTERISTIC_REPRESENTATION"):
            continue
        darst = datei.get(r.args()[1])
        if darst is None:
            continue
        items = darst.args(next(iter(darst.parts)))[1]
        for it in items:
            ie = datei.get(it)
            if ie is None:
                continue
            if ie.is_a("VALUE_RANGE") or ie.is_a("COMPOUND_REPRESENTATION_ITEM"):
                teil = ie.args("COMPOUND_REPRESENTATION_ITEM")[0] if ie.is_a(
                    "COMPOUND_REPRESENTATION_ITEM") else []
                for sub in (teil.args[0] if isinstance(teil, Typed) else teil) or []:
                    se = datei.get(sub)
                    if se is not None:
                        out[_item_name(se)] = _wert(datei, sub)
            elif ie.is_a("DESCRIPTIVE_REPRESENTATION_ITEM"):
                name, text = ie.args("DESCRIPTIVE_REPRESENTATION_ITEM")[:2]
                out.setdefault("_notizen", []).append(text)
            else:
                out[_item_name(ie) or "nominal value"] = _wert(datei, it)
                _qualifikatoren(datei, ie, out)
    return out


def _qualifikatoren(datei: P21Datei, ie: Entity, out: dict):
    """Nachkommastellen (VALUE_FORMAT_TYPE_QUALIFIER 'NR2 1.3') und MIN/MAX/AVG."""
    if not ie.is_a("QUALIFIED_REPRESENTATION_ITEM"):
        return
    for q in ie.args("QUALIFIED_REPRESENTATION_ITEM")[0] or []:
        qe = datei.get(q)
        if qe is None:
            continue
        if qe.is_a("VALUE_FORMAT_TYPE_QUALIFIER"):
            fmt = qe.args("VALUE_FORMAT_TYPE_QUALIFIER")[0]
            if "." in fmt:
                out.setdefault("_dezimalen", int(fmt.rsplit(".", 1)[1]))
        elif qe.is_a("TYPE_QUALIFIER"):
            out["_qualifikator"] = qe.args("TYPE_QUALIFIER")[0]


def _toleranz_des_masses(datei: P21Datei, dim_id: int, p: Pmi, winkel: bool):
    for rid in datei.referrers().get(dim_id, []):
        r = datei.entities[rid]
        if not r.is_a("PLUS_MINUS_TOLERANCE"):
            continue
        bereich = datei.get(r.args("PLUS_MINUS_TOLERANCE")[0])
        if bereich is None:
            continue
        if bereich.is_a("TOLERANCE_VALUE"):
            unten, oben = bereich.args("TOLERANCE_VALUE")[:2]
            f = winkel_grad if winkel else laenge_mm
            p.unten, p.oben = f(datei, unten), f(datei, oben)
        elif bereich.is_a("LIMITS_AND_FITS"):
            abw, art, grad = bereich.args("LIMITS_AND_FITS")[:3]
            p.passung = f"{abw}{grad}"


def _lies_mass_step(modell: StepModell, e: Entity) -> Pmi:
    datei = modell.datei
    from .pmi import MASS
    if e.is_a("ANGULAR_SIZE"):
        aspekte, typ, name = [e.args("ANGULAR_SIZE")[0]], "Size_Angular", e.args("ANGULAR_SIZE")[1]
    elif e.is_a("DIMENSIONAL_SIZE"):
        a, name = e.args("DIMENSIONAL_SIZE")[:2]
        aspekte, typ = [a], GROESSEN.get(name, "Size_Other")
    else:
        teil = next(t for t in e.parts if t in ("ANGULAR_LOCATION", "DIRECTED_DIMENSIONAL_LOCATION",
                                                 "DIMENSIONAL_LOCATION_WITH_PATH", "DIMENSIONAL_LOCATION"))
        name, _, a1, a2 = e.args(teil)[:4]
        aspekte = [a1, a2]
        typ = "Location_Angular" if teil == "ANGULAR_LOCATION" else LAGEN.get(name, "Location_LinearDistance")
    p = Pmi(MASS, typ=typ, name=name or "", quelle="step", step_id=e.id)
    werte = _werte_der_darstellung(datei, e.id)
    for notiz in werte.get("_notizen", []):
        p.modifikatoren.append({"theoretical": "Theoretisch", "auxiliary": "Hilfsmass"}.get(notiz, notiz))
    p.dezimalen = werte.get("_dezimalen")
    if werte.get("_qualifikator"):
        p.modifikatoren.append(werte["_qualifikator"].upper())
    if "nominal value" in werte:
        p.nennwert = werte["nominal value"]
    if "upper limit" in werte and "lower limit" in werte:
        p.oben, p.unten, p.grenzmass = werte["upper limit"], werte["lower limit"], True
        if p.nennwert is None:
            p.nennwert = (p.oben + p.unten) / 2
    _toleranz_des_masses(datei, e.id, p, typ in ("Size_Angular", "Location_Angular"))
    for a in aspekte:
        if isinstance(a, Ref):
            p.flaechen |= flaechen_von_aspekt(datei, modell, a.id)
    p.grafisch = _hat_praesentation(datei, e.id)
    return p


MASS_TYPEN = ("DIMENSIONAL_SIZE", "DIMENSIONAL_LOCATION", "ANGULAR_SIZE", "ANGULAR_LOCATION",
              "DIRECTED_DIMENSIONAL_LOCATION", "DIMENSIONAL_LOCATION_WITH_PATH",
              "DIMENSIONAL_SIZE_WITH_PATH")


def lies_masse(modell: StepModell) -> list[Pmi]:
    return [_lies_mass_step(modell, e) for e in modell.datei.of_types_by_id(MASS_TYPEN)]
