"""Begrenzte AP203e2-zu-AP242e3-Abbildung fuer Modelle mit grafischer Kurven-PMI.

Geprueft gegen ISO/TS 10303-403 MIM LF 1.43 (N2635) und -442 MIM LF 1.152 (N10962).
Der Katalog enthaelt die in NIST CTC-01, -02, -03 und -05 belegten gemeinsamen Einzel- und Komplexsignaturen.
Keine allgemeine EXPRESS-Validierung. Unbekannte Konstrukte bleiben in der Quelldatei.
"""

from __future__ import annotations

import re

from ..i18n import tr
from . import p21

AP203 = "AP203_CONFIGURATION_CONTROLLED_3D_DESIGN_OF_MECHANICAL_PARTS_AND_ASSEMBLIES_MIM_LF"
AP242 = "AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF"
SCHEMA = AP242 + " { 1 0 10303 442 4 1 4 }"

# Einfache Instanzen: Anzahl der expliziten Attribute mit allen geerbten Attributen.
_GRUPPEN = {
    0: "COLOUR",
    1: """APPLICATION_CONTEXT APPROVAL_ROLE APPROVAL_STATUS DATE_TIME_ROLE DERIVED_UNIT
        DRAUGHTING_PRE_DEFINED_CURVE_FONT INVISIBILITY PERSON_AND_ORGANIZATION_ROLE
        PRESENTATION_STYLE_ASSIGNMENT SECURITY_CLASSIFICATION_LEVEL SURFACE_STYLE_FILL_AREA""",
    2: """APPROVAL APPROVAL_DATE_TIME CARTESIAN_POINT CC_DESIGN_APPROVAL CC_DESIGN_SECURITY_CLASSIFICATION
        CLOSED_SHELL DATE_AND_TIME DERIVED_UNIT_ELEMENT DIRECTION EDGE_LOOP FILL_AREA_STYLE FILL_AREA_STYLE_COLOUR
        GEOMETRIC_CURVE_SET MANIFOLD_SOLID_BREP NAME_ATTRIBUTE PERSON_AND_ORGANIZATION PLANE PLANE_ANGLE_MEASURE_WITH_UNIT
        POLYLINE PRODUCT_CATEGORY PROPERTY_DEFINITION_REPRESENTATION REPRESENTATION_MAP SHAPE_DEFINITION_REPRESENTATION
        SURFACE_SIDE_STYLE SURFACE_STYLE_USAGE VALUE_REPRESENTATION_ITEM VERTEX_LOOP VERTEX_POINT LENGTH_MEASURE_WITH_UNIT""",
    3: """ADVANCED_BREP_SHAPE_REPRESENTATION ANNOTATION_OCCURRENCE APPROVAL_PERSON_ORGANIZATION CALENDAR_DATE
        CAMERA_MODEL_D3 CC_DESIGN_DATE_AND_TIME_ASSIGNMENT CC_DESIGN_PERSON_AND_ORGANIZATION_ASSIGNMENT
        CIRCLE CONSTRUCTIVE_GEOMETRY_REPRESENTATION COORDINATED_UNIVERSAL_TIME_OFFSET CYLINDRICAL_SURFACE
        DESIGN_CONTEXT DRAUGHTING_MODEL FACE_BOUND FACE_OUTER_BOUND GEOMETRICALLY_BOUNDED_WIREFRAME_SHAPE_REPRESENTATION
        LINE MAPPED_ITEM MEASURE_REPRESENTATION_ITEM MECHANICAL_CONTEXT MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION
        ORGANIZATION PRESENTATION_LAYER_ASSIGNMENT PRODUCT_DEFINITION_SHAPE PRODUCT_RELATED_PRODUCT_CATEGORY
        PROPERTY_DEFINITION REPRESENTATION SECURITY_CLASSIFICATION SHAPE_REPRESENTATION STYLED_ITEM VECTOR SPHERICAL_SURFACE""",
    4: """ADVANCED_FACE ANNOTATION_PLANE APPLICATION_PROTOCOL_DEFINITION AXIS2_PLACEMENT_3D COLOUR_RGB
        CONICAL_SURFACE CONSTRUCTIVE_GEOMETRY_REPRESENTATION_RELATIONSHIP CURVE_STYLE ELLIPSE LOCAL_TIME PLANAR_BOX
        POINT_STYLE PRODUCT PRODUCT_DEFINITION PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE
        REPRESENTATION_RELATIONSHIP SHAPE_ASPECT SHAPE_REPRESENTATION_RELATIONSHIP UNCERTAINTY_MEASURE_WITH_UNIT TOROIDAL_SURFACE""",
    5: "DRAUGHTING_MODEL_ITEM_ASSOCIATION EDGE_CURVE GEOMETRIC_ITEM_SPECIFIC_USAGE ORIENTED_EDGE",
    6: "PERSON TRIMMED_CURVE",
    7: "DIMENSIONAL_EXPONENTS",
    9: "B_SPLINE_CURVE_WITH_KNOTS VIEW_VOLUME",
    13: "B_SPLINE_SURFACE_WITH_KNOTS",
}
_ANZAHL = {typ: n for n, typen in _GRUPPEN.items() for typ in typen.split()}
_KOMPLEX = {
    (("BOUNDED_SURFACE", 0), ("B_SPLINE_SURFACE", 7), ("B_SPLINE_SURFACE_WITH_KNOTS", 5),
     ("GEOMETRIC_REPRESENTATION_ITEM", 0), ("RATIONAL_B_SPLINE_SURFACE", 1), ("REPRESENTATION_ITEM", 1), ("SURFACE", 0)),
    (("CONVERSION_BASED_UNIT", 2), ("LENGTH_UNIT", 0), ("NAMED_UNIT", 1)),
    (("CONVERSION_BASED_UNIT", 2), ("NAMED_UNIT", 1), ("PLANE_ANGLE_UNIT", 0)),
    (("GEOMETRIC_REPRESENTATION_CONTEXT", 1), ("GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT", 1),
     ("GLOBAL_UNIT_ASSIGNED_CONTEXT", 1), ("REPRESENTATION_CONTEXT", 2)),
    (("LENGTH_UNIT", 0), ("NAMED_UNIT", 1), ("SI_UNIT", 2)),
    (("NAMED_UNIT", 1), ("PLANE_ANGLE_UNIT", 0), ("SI_UNIT", 2)),
    (("NAMED_UNIT", 1), ("SI_UNIT", 2), ("SOLID_ANGLE_UNIT", 0)),
}
# Engere bzw. neu gefasste SELECTs: nur die hier geprueften Zieltypen.
_ZIELE = {
    "STYLED_ITEM": {2: "CARTESIAN_POINT TRIMMED_CURVE AXIS2_PLACEMENT_3D MANIFOLD_SOLID_BREP CIRCLE ELLIPSE"},
    "ANNOTATION_PLANE": {2: "PLANE", 3: "ANNOTATION_OCCURRENCE"},
    "ANNOTATION_OCCURRENCE": {1: "PRESENTATION_STYLE_ASSIGNMENT", 2: "GEOMETRIC_CURVE_SET"},
    "DRAUGHTING_MODEL_ITEM_ASSOCIATION": {2: "SHAPE_ASPECT", 3: "DRAUGHTING_MODEL", 4: "ANNOTATION_OCCURRENCE"},
    "GEOMETRIC_ITEM_SPECIFIC_USAGE": {2: "SHAPE_ASPECT", 3: "ADVANCED_BREP_SHAPE_REPRESENTATION", 4: "ADVANCED_FACE EDGE_CURVE"},
    "SHAPE_DEFINITION_REPRESENTATION": {0: "PRODUCT_DEFINITION_SHAPE PROPERTY_DEFINITION", 1: "SHAPE_REPRESENTATION"},
    "APPLICATION_PROTOCOL_DEFINITION": {3: "APPLICATION_CONTEXT"},
}
_MENGEN = {("ANNOTATION_PLANE", 3), ("ANNOTATION_OCCURRENCE", 1)}
_GETYPT = {"PARAMETER_VALUE", "POSITIVE_LENGTH_MEASURE", "MARKER_TYPE", "COUNT_MEASURE",
           "VOLUME_MEASURE", "AREA_MEASURE", "LENGTH_MEASURE", "PLANE_ANGLE_MEASURE"}
_VORLAUF = re.compile(r"(?:\s+|/\*.*?\*/)*", re.S)
_LITERAL = r"'(?:[^']|'')*'"


def _unbekannt(e):
    return ValueError(tr("AP203e2-Abbildung für #{} ({}) nicht gesichert").format(e.id, e.typ))


def _argumente_ok(werte, datei):
    for v in werte:
        if isinstance(v, p21.Ref) and v.id not in datei.entities:
            return False
        if isinstance(v, p21.Typed) and (v.typ not in _GETYPT or not _argumente_ok(v.args, datei)):
            return False
        if isinstance(v, list) and not _argumente_ok(v, datei):
            return False
    return True


def _pruefe(datei):
    for e in datei.entities.values():
        if len(e.parts) > 1:
            if tuple((k, len(v)) for k, v in e.parts.items()) not in _KOMPLEX:
                raise _unbekannt(e)
        elif _ANZAHL.get(e.typ) != len(e.args()):
            raise _unbekannt(e)
        if not all(_argumente_ok(v, datei) for v in e.parts.values()):
            raise _unbekannt(e)
        for i, typen in _ZIELE.get(e.typ, {}).items():
            refs = e.args()[i]
            menge = (e.typ, i) in _MENGEN
            if isinstance(refs, list) != menge or menge and not refs:
                raise _unbekannt(e)
            for ref in refs if menge else [refs]:
                ziel = datei.get(ref) if isinstance(ref, p21.Ref) else None
                if ziel is None or ziel.typ not in typen.split():
                    raise _unbekannt(e)
        if e.typ == "SHAPE_DEFINITION_REPRESENTATION":
            bezug = datei.get(e.args()[0])
            if bezug.typ == "PROPERTY_DEFINITION":
                ref = bezug.args()[2]
                if not isinstance(ref, p21.Ref) or datei.get(ref).typ != "SHAPE_ASPECT":
                    raise _unbekannt(e)


def aus_ap203(text: str, datei: p21.P21Datei) -> str:
    """Uebertraegt den geprueften AP203e2-Teilumfang oder meldet die erste ungesicherte Stelle."""
    quelle = re.compile(AP203 + r"\s*\{\s*1\s+0\s+10303\s+403\s+(?:3\s+1\s+4|2\s+1\s+2)\s*\}")
    if not quelle.fullmatch(datei.schema):
        raise ValueError(tr("Dieses STEP-Schema wird nicht nach AP242 übertragen"))
    _pruefe(datei)
    protokolle = datei.of_type("APPLICATION_PROTOCOL_DEFINITION")
    if len(protokolle) != 1 or not datei.of_type("ANNOTATION_OCCURRENCE"):
        raise ValueError(tr("AP203e2-Anwendungsprotokoll oder Kurven-PMI nicht eindeutig"))
    prot = protokolle[0]
    status, name, jahr, ref = prot.args()
    if (status, name, jahr) != ("international standard", "config_control_design", 2010):
        raise _unbekannt(prot)
    kontext = datei.get(ref)
    beschreibung = kontext.args()[0]
    if not isinstance(beschreibung, str) or "".join(beschreibung.lower().split()) != (
            "configurationcontrolled3ddesignsofmechanicalpartsandassemblies"):
        raise _unbekannt(kontext)
    ersatz = {prot.id: f"APPLICATION_PROTOCOL_DEFINITION('international standard','{AP242.lower()}',2022,#{ref.id})",
              kontext.id: "APPLICATION_CONTEXT('managed model based 3d engineering')"}
    for e in datei.of_type("ANNOTATION_OCCURRENCE"):
        _, stile, ziel = e.args()
        if not isinstance(stile, list) or len(stile) != 1:
            raise _unbekannt(e)
        ersatz[e.id] = (f"(ANNOTATION_CURVE_OCCURRENCE() ANNOTATION_OCCURRENCE() GEOMETRIC_REPRESENTATION_ITEM() "
                        f"REPRESENTATION_ITEM({{name}}) STYLED_ITEM((#{stile[0].id}),#{ziel.id}))")
    teile, gesehen = [], set()
    start = 0
    h = iter(("ISO-10303-21", "HEADER", "FILE_DESCRIPTION", "FILE_NAME", "FILE_SCHEMA", "ENDSEC", "DATA"))
    erwartet = next(h)
    for m in p21._TRENNER.finditer(text):
        if text[m.start()] != ";":
            continue
        satz = text[start:m.start()]
        i = _VORLAUF.match(satz).end()
        inhalt = satz[i:]
        wort = re.match(r"[A-Z0-9_-]+", inhalt)
        if erwartet:
            if not wort or wort[0] != erwartet:
                raise ValueError(tr("STEP-Abschnitt nicht für die AP242-Übertragung geprüft"))
            erwartet = next(h, "") if erwartet != "END-ISO-10303-21" else "Dateiende"
        elif wort and wort[0] == "ENDSEC":
            erwartet = "END-ISO-10303-21"
        elif not inhalt.startswith("#"):
            raise ValueError(tr("STEP-Abschnitt nicht für die AP242-Übertragung geprüft"))
        if inhalt.startswith("FILE_SCHEMA"):
            if not re.fullmatch(r"FILE_SCHEMA\s*\(\s*\(\s*'" + quelle.pattern + r"'\s*\)\s*\)\s*", inhalt):
                raise ValueError(tr("Dieses STEP-Schema wird nicht nach AP242 übertragen"))
            satz = satz[:i] + f"FILE_SCHEMA(('{SCHEMA}'))"
        elif inhalt.startswith("#"):
            kopf = re.match(r"#(\d+)\s*=\s*", inhalt)
            if not kopf or (eid := int(kopf[1])) not in datei.entities or eid in gesehen:
                raise ValueError(tr("STEP-Instanz nicht eindeutig"))
            gesehen.add(eid)
            if eid in ersatz:
                neu = ersatz[eid]
                if eid not in (prot.id, kontext.id):
                    n = re.match(r"ANNOTATION_OCCURRENCE\s*\(\s*(" + _LITERAL + r")\s*,", inhalt[kopf.end():])
                    if not n:
                        raise _unbekannt(datei.entities[eid])
                    neu = neu.replace("{name}", n[1])
                satz = satz[:i + kopf.end()] + neu
        elif inhalt.strip() not in ("ISO-10303-21", "HEADER", "DATA", "ENDSEC", "END-ISO-10303-21") and not re.match(
                r"(?:FILE_DESCRIPTION|FILE_NAME)\s*\(", inhalt):
            raise ValueError(tr("STEP-Abschnitt nicht für die AP242-Übertragung geprüft"))
        teile.append(satz + ";")
        start = m.end()
    if erwartet != "Dateiende" or gesehen != datei.entities.keys() or text[start:].strip():
        raise ValueError(tr("STEP-Abschnitt nicht für die AP242-Übertragung geprüft"))
    return "".join(teile) + text[start:]
