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
    if len(item := e.parts.get("MEASURE_REPRESENTATION_ITEM", [])) == 3:
        _, wert, einheit = item
        return (wert.args[0] if isinstance(wert, Typed) else wert), einheit
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
    for r in refs if isinstance(refs, list) else ():
        e = datei.get(r) if isinstance(r, Ref) else None
        if e is None:
            continue
        if e.is_a("DATUM_SYSTEM"):
            daten = e.args("DATUM_SYSTEM")
            faecher = daten[4] if len(daten) > 4 and isinstance(daten[4], list) else ()
            for stelle, fach in enumerate(faecher, 1):
                fe = datei.get(fach) if isinstance(fach, Ref) else None
                if fe is None:
                    out.append(BezugsRef("?", stelle))
                    continue
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


def _rahmengrund(e):
    if e.is_a("GEOMETRIC_TOLERANCE"):
        refs = e.args("GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE") if e.is_a("GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE") else []
        return e.args("GEOMETRIC_TOLERANCE"), refs[0] if refs else None
    grund = e.args()
    return grund, grund[4] if len(grund) > 4 else None


def _lies_rahmen(modell: StepModell, e: Entity, zonen: dict[int, list[Entity]], bereichsleser) -> Pmi:
    datei = modell.datei
    grund, bezug_refs = _rahmengrund(e)
    name, beschreibung, betrag, aspekt = grund[:4]
    typ = next((TOL_ARTEN[t] for t in e.parts if t in TOL_ARTEN), "None")
    p = Pmi(TOLERANZ, typ=typ, name=name or "", quelle="step", step_id=e.id)
    p.beschreibung = beschreibung if isinstance(beschreibung, str) else ""
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
        refs = e.args("GEOMETRIC_TOLERANCE_WITH_DEFINED_UNIT")
        einheit = refs[0] if len(refs) == 1 else None
        gebiet = e.parts.get("GEOMETRIC_TOLERANCE_WITH_DEFINED_AREA_UNIT", ())
        if len(gebiet) == 2 and gebiet[0] == Enum("RECTANGULAR"):
            seiten = []
            for ref in (einheit, gebiet[1]):
                messung = datei.get(ref) if isinstance(ref, Ref) else None
                mm = _gesicherte_laenge(datei, ref) if messung and messung.is_a("LENGTH_MEASURE_WITH_UNIT") else None
                seiten.append(mm if mm is not None and mm > 0 else None)
            p.einheitslaenge, p.einheitsbreite = seiten
            if p.einheitslaenge is None and p.einheitsbreite is None:
                p.modifikatoren.append("RECTANGULAR")
        else:
            p.modifikatoren.append(f"je {laenge_mm(datei, einheit)}")
    _zonen_info(modell, p, zonen.get(e.id, []))
    if p.material or p.zone == "Projected":
        p.wert = _gesicherte_laenge(datei, betrag)
    if isinstance(aspekt, Ref):
        p.flaechen = flaechen_von_aspekt(datei, modell, aspekt.id)
        ziel = datei.get(aspekt)
        if ziel and ziel.is_a("BETWEEN_SHAPE_ASPECT"):
            from .pmi_zwischenbereich import lies_grenzen
            p.bereichsgrenzen = lies_grenzen(datei, ziel.id, p.grenzgrafiken) or None
            if not p.flaechen and p.typ == "ProfileOfSurface":
                from .profilteilflaeche import lies_ausschnitte
                lies_ausschnitte(modell, ziel, p, bereichsleser)
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


def _bezugsbasis(datei, refs):
    """Die referenzierte Basis in dieser Datei, einschliesslich der Rangfolge alter DATUM_REFERENCEs."""
    if not isinstance(refs, list) or not refs:
        return None
    basis = set()
    for ref in refs:
        e = datei.get(ref) if isinstance(ref, Ref) else None
        if e is None:
            return None
        if e.is_a("DATUM_SYSTEM"):
            basis.add(("system", e.id))
        elif e.is_a("DATUM_REFERENCE"):
            rang, datum = e.args("DATUM_REFERENCE")[:2]
            element = datei.get(datum) if isinstance(datum, Ref) else None
            if element is None or not element.is_a("DATUM"):
                return None
            # Ein erweiterter Bezugsverweis kann eigene Modifikatoren tragen.
            basis.add(("datum", rang, datum.id) if len(e.parts) == 1 else ("verweis", e.id))
        else:
            return None
    return frozenset(basis)


def lies_toleranzen(modell: StepModell) -> list[Pmi]:
    datei = modell.datei
    zonen = _zonen(datei)
    toleranzen = datei.of_types_by_id(("GEOMETRIC_TOLERANCE", *TOL_ARTEN))

    from functools import cache

    @cache
    def bereichsleser():
        from .profilteilflaeche import Bereichsleser
        return Bereichsleser(modell)

    rahmen = {e.id: _lies_rahmen(modell, e, zonen, bereichsleser) for e in toleranzen}
    basis = {}
    nachbarn = {}
    for link in datei.of_type("GEOMETRIC_TOLERANCE_RELATIONSHIP"):
        args = link.args("GEOMETRIC_TOLERANCE_RELATIONSHIP")
        if len(args) != 4:
            continue
        art = str(args[0]).strip().lower()
        a, b = args[2:]
        if (art not in ("composite", "simultaneity") or not isinstance(a, Ref) or not isinstance(b, Ref)
                or a == b or a.id not in rahmen or b.id not in rahmen):
            continue
        if art == "composite":
            nachbarn.setdefault((a.id, "folgetoleranzen"), set()).add(b.id)
        else:
            for nr in (a.id, b.id):
                if nr not in basis:
                    _, refs = _rahmengrund(datei.get(nr))
                    bezuege = rahmen[nr].bezuege
                    lesbar = bezuege and all(b.name and "?" not in b.name for b in bezuege)
                    basis[nr] = _bezugsbasis(datei, refs) if lesbar else None
            feld = "simultan_mit" if basis[a.id] and basis[a.id] == basis[b.id] else "simultan_offen"
            nachbarn.setdefault((a.id, feld), set()).add(b.id)
            nachbarn.setdefault((b.id, feld), set()).add(a.id)
    for (nr, feld), partner in nachbarn.items():
        setattr(rahmen[nr], feld, sorted(partner))
    return list(rahmen.values())


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

# CAx-IF PMI RP 5.3: Typ 1 direkt an der Darstellung, Typ 2 als Gruppe.
MASS_TYP1 = {"auxiliary": "Hilfsmass", "theoretical": "Theoretisch"}
MASS_TYP2 = {"controlled radius": "ControlledRadius", "statistical": "StatisticalTolerance"}


def winkel_grad(datei: P21Datei, ref) -> float | None:
    wert, einheit = messwert_roh(datei, ref)
    if wert is None:
        return None
    e = datei.get(einheit) if isinstance(einheit, Ref) else None
    if e is not None and e.is_a("SI_UNIT"):
        return float(wert) * 57.29577951308232  # Radiant -> Grad
    return float(wert)  # 'degree' als CONVERSION_BASED_UNIT


def ist_winkelmass(e: Entity) -> bool:
    if e.is_a("PLANE_ANGLE_MEASURE_WITH_UNIT"):
        return True
    wert = e.parts.get("MEASURE_WITH_UNIT", [])[:1] or e.parts.get("MEASURE_REPRESENTATION_ITEM", [])[1:2]
    return bool(wert and isinstance(wert[0], Typed)
                and wert[0].typ in ("PLANE_ANGLE_MEASURE", "POSITIVE_PLANE_ANGLE_MEASURE"))


def _wert(datei: P21Datei, e: Entity) -> float | None:
    return (winkel_grad if ist_winkelmass(e) else laenge_mm)(datei, Ref(e.id))


def mass_item_name(e: Entity) -> str:
    a = e.parts.get("REPRESENTATION_ITEM", e.parts.get("MEASURE_REPRESENTATION_ITEM", []))
    return a[0] if a else ""


def mass_items(datei: P21Datei, darst: Entity):
    """Blaetter der Massdarstellung in Dateireihenfolge, auch bei gruppierten Werten und Notizen."""
    basis = darst.parts.get("REPRESENTATION", darst.args())
    offen = list(reversed(basis[1])) if len(basis) >= 2 and isinstance(basis[1], list) else []
    besucht = set()
    while offen:
        ref = offen.pop()
        if not isinstance(ref, Ref) or ref.id in besucht:
            continue
        besucht.add(ref.id)
        e = datei.get(ref)
        if e is None:
            continue
        gruppe = e.parts.get("COMPOUND_REPRESENTATION_ITEM", e.parts.get("VALUE_RANGE"))
        if gruppe is None:
            yield e
        elif gruppe:
            kinder = gruppe[-1]
            if isinstance(kinder, Typed) and kinder.args:
                kinder = kinder.args[0]
            if isinstance(kinder, list):
                offen.extend(reversed(kinder))


def _werte_der_darstellung(datei: P21Datei, dim_id: int) -> dict:
    """'nominal value', 'upper limit', 'lower limit' einer Masseintragung."""
    out = {}
    for rid in datei.referrers().get(dim_id, []):
        r = datei.entities[rid]
        if not r.is_a("DIMENSIONAL_CHARACTERISTIC_REPRESENTATION"):
            continue
        darst = datei.get(r.args()[1])
        if darst is None:
            continue
        basis = darst.parts.get("REPRESENTATION", darst.args())
        if basis and basis[0] == "envelope requirement":
            out["_huelle"] = True
        for ie in mass_items(datei, darst):
            if ie.is_a("DESCRIPTIVE_REPRESENTATION_ITEM"):
                inhalt = ie.args("DESCRIPTIVE_REPRESENTATION_ITEM")
                if inhalt and isinstance(inhalt[-1], str):
                    out.setdefault("_notizen", []).append(inhalt[-1])
            elif (wert := _wert(datei, ie)) is not None:
                out[mass_item_name(ie) or "nominal value"] = wert
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
    if typ == "Location_LinearDistance" and len(aspekte) == 2:
        p.mittenabstand = all(isinstance(a, Ref) and (ziel := datei.get(a)) is not None
                              and ziel.is_a("CENTRE_OF_SYMMETRY") for a in aspekte)
    werte = _werte_der_darstellung(datei, e.id)
    for notiz in werte.get("_notizen", []):
        mod = MASS_TYP1.get(notiz, MASS_TYP2.get(notiz, notiz))
        if mod not in p.modifikatoren:
            p.modifikatoren.append(mod)
    if werte.get("_huelle"):
        p.modifikatoren.append("Envelope")
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
    for i,a in enumerate(aspekte):
        if isinstance(a, Ref):
            flaechen = flaechen_von_aspekt(datei, modell, a.id)
            if (i == 1 and typ == "Location_LinearDistance_FromOuterToCenter" and len(flaechen) == 2
                    and len(p.flaechen) == 1 and not (p.flaechen & flaechen)
                    and datei.get(a) is not None and datei.get(a).is_a("CENTRE_OF_SYMMETRY")):
                p.mittenbezug, = p.flaechen
            p.flaechen |= flaechen
            if not flaechen and p.typ in ("Size_Diameter", "Location_LinearDistance"):
                formen = teilformen_von_aspekt(datei, modell, a.id)
                if formen:
                    p.teilformen = getattr(p, "teilformen", []) + formen
                    p.kanten = len(p.teilformen)
    p.grafisch = _hat_praesentation(datei, e.id)
    return p


MASS_TYPEN = ("DIMENSIONAL_SIZE", "DIMENSIONAL_LOCATION", "ANGULAR_SIZE", "ANGULAR_LOCATION",
              "DIRECTED_DIMENSIONAL_LOCATION", "DIMENSIONAL_LOCATION_WITH_PATH",
              "DIMENSIONAL_SIZE_WITH_PATH")


def lies_masse(modell: StepModell) -> list[Pmi]:
    return [_lies_mass_step(modell, e) for e in modell.datei.of_types_by_id(MASS_TYPEN)]
