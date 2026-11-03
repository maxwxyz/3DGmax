"""Export der erkannten Verzahnungen als REXS-Modell (JSON) - das offene Austauschformat der FVA fuer Getriebedaten
(Reusable Engineering EXchange Standard, www.rexs.info), das Auslegungs- und Nachrechenprogramme lesen. Nur Analyse:
geschrieben wird, was kern.verzahnung/verzahnung_daten aus der Geometrie bestimmt haben.

Komponenten, Attribute, Einheiten und Relationen nach dem REXS-Datenbankmodell 1.7 (enthalten in der freien
REXS-Bibliothek der FVA, github.com/fva-net/rexs-api-cpp, models/rexs_schema_1.7_en.xml); Dateiaufbau nach deren
JSON-Schema models/rexs-file.json (model: version, applicationId, applicationVersion, date, relations, components;
Attribut: id, unit und genau ein Wert, hier floating_point, integer oder enum).

Abbildung:
- gear_unit (model_name), je Welle (gleichachsige Raeder, verzahnung_daten.wellen) ein shaft mit assembly-Relationen
  zu seinen Raedern;
- je Rad cylindrical_gear bzw. ring_gear mit Zaehnezahl, Modulen, Schraegungswinkel (mit Vorzeichen: rechtssteigend
  positiv, wie ISO 21771), Durchmessern (Teil-, Kopf-, Fuss-, Grund-, Kopfform-, Fussformkreis), Breite, Zahnhoehe,
  Zahndicke und Lueckenweite, Zahnweite mit k, Mass ueber Kugeln mit Kugeldurchmesser (nur Aussenrad);
- je Rad zwei cylindrical_gear_flank (flank-Relation links/rechts) mit Normaleingriffswinkel, Stirneingriffswinkel und
  Profilverschiebungsfaktor; erkannte Korrekturen als tip_relief, profile_slope und helix_crowning, von beiden Flanken
  ueber reference-Relationen verwiesen (die Erkennung mittelt beide Flanken);
- je Radpaar cylindrical_stage (stage-Relation gear_1/gear_2) mit Achsabstand, Uebersetzung, Summe der
  Profilverschiebungen, Profil-, Sprung- und Gesamtueberdeckung, Normalflankenspiel (min = max, aus der Nennlage),
  dazu je Rad cylindrical_stage_gear_data (stage_gear_data-Relation) mit Kopfspiel, Betriebseingriffswinkel und
  spezifischem Gleiten am Fuss;
- je Planetensatz planetary_stage mit central_shaft (Welle der Sonne) und planet_shaft (Wellen der Planeten); der
  Steg ist aus der Verzahnung allein nicht bestimmbar und fehlt.
"""

from __future__ import annotations

import datetime
import math

from . import verzahnung_daten as vd
from .verzahnung import Paar, Verzahnung

VERSION = "1.7"
# Attribut -> Einheit laut REXS-Datenbank 1.7 (nur die hier geschriebenen)
EINHEIT = {
    "model_name": "none", "number_of_teeth": "none", "normal_module": "mm", "transverse_module": "mm",
    "helix_angle_reference_diameter": "deg", "helix_angle_base_circle": "deg", "face_width": "mm",
    "reference_circle_diameter": "mm", "tip_diameter": "mm", "root_diameter": "mm", "base_circle_diameter": "mm",
    "tip_form_diameter": "mm", "root_form_diameter": "mm", "tooth_depth": "mm",
    "normal_tooth_thickness_at_reference_diameter": "mm", "normal_space_width_at_reference_diameter": "mm",
    "number_of_teeth_for_span_measurement": "none", "span_measurement": "mm", "diameter_of_measuring_ball_or_pin": "mm",
    "size_over_balls": "mm", "normal_pressure_angle": "deg", "pressure_angle_in_the_transverse_section": "deg",
    "addendum_modification_coefficient": "none", "tip_relief_depth": "mm", "tip_relief_datum_diameter": "mm",
    "shape_of_relief": "none", "profile_slope": "mm", "helix_crowning_amount_datum_face": "mm",
    "helix_crowning_amount_non_datum_face": "mm", "shape_of_helix_crowning": "none", "center_distance": "mm",
    "gear_ratio": "none", "sum_of_addendum_modification_coefficients": "none", "radial_contact_ratio": "none",
    "overlap_contact_ratio": "none", "total_contact_ratio": "none", "minimum_normal_backlash": "mm",
    "maximum_normal_backlash": "mm", "tip_clearance": "mm", "operating_pressure_angle_in_the_transverse_section": "deg",
    "specific_sliding_at_root_diameter": "none",
}
ROLLEN = {"assembly": ("assembly", "part"), "flank": ("gear", "left", "right"), "reference": ("origin", "referenced"),
          "stage": ("stage", "gear_1", "gear_2"), "stage_gear_data": ("stage", "gear", "stage_gear_data"),
          "central_shaft": ("planetary_stage", "shaft"), "planet_shaft": ("planetary_stage", "shaft")}


def _attr(aid: str, wert) -> dict | None:
    """Attribut im REXS-JSON; None fuer fehlende, unendliche oder nicht bestimmte Werte."""
    if wert is None or (isinstance(wert, float) and (math.isnan(wert) or math.isinf(wert))):
        return None
    if isinstance(wert, str):
        return {"id": aid, "unit": EINHEIT[aid], "enum" if aid.startswith("shape") else "string": wert}
    if isinstance(wert, bool):
        return {"id": aid, "unit": EINHEIT[aid], "boolean": wert}
    if isinstance(wert, int):
        return {"id": aid, "unit": EINHEIT[aid], "integer": wert}
    return {"id": aid, "unit": EINHEIT[aid], "floating_point": round(float(wert), 6)}


class _Modell:
    def __init__(self):
        self.komponenten: list[dict] = []
        self.relationen: list[dict] = []

    def komponente(self, typ: str, name: str, werte: dict) -> int:
        nr = len(self.komponenten) + 1
        attribute = [a for k, w in werte.items() if (a := _attr(k, w)) is not None]
        self.komponenten.append({"id": nr, "type": typ, "name": name, "attributes": attribute})
        return nr

    def relation(self, typ: str, **refs: int):
        rollen = ROLLEN[typ]
        self.relationen.append({"id": len(self.relationen) + 1, "type": typ,
                                "refs": [{"id": refs[r], "role": r} for r in rollen if r in refs]})


def _rad(m: _Modell, v: Verzahnung) -> int:
    w = vd.stirnwerte(v)
    p = vd.profil(v)
    werte = {"number_of_teeth": int(v.z), "normal_module": v.mn or None, "transverse_module": w.get("mt"),
             "helix_angle_reference_diameter": (-v.beta if v.hand == "links" else v.beta) if v.mn else None,
             "helix_angle_base_circle": w.get("beta_b"), "face_width": v.b, "reference_circle_diameter": v.d or None,
             "tip_diameter": v.da, "root_diameter": v.df, "base_circle_diameter": v.db or None,
             "tooth_depth": w.get("h"), "normal_tooth_thickness_at_reference_diameter": w.get("sn"),
             "normal_space_width_at_reference_diameter": w.get("en")}
    if p is not None:
        werte.update({"tip_form_diameter": p.dfa, "root_form_diameter": p.dff})
    if not v.innen:
        werte.update({"number_of_teeth_for_span_measurement": int(v.k) if v.k else None,
                      "span_measurement": v.wk or None})
        k = vd.kugelmass(v)
        if k:
            werte.update({"diameter_of_measuring_ball_or_pin": k[0], "size_over_balls": k[1]})
    rad = m.komponente("ring_gear" if v.innen else "cylindrical_gear", v.teil, werte)
    flanke = {"normal_pressure_angle": v.alpha_n or None, "pressure_angle_in_the_transverse_section": w.get("alpha_t"),
              "addendum_modification_coefficient": v.x if v.mn else None}
    links = m.komponente("cylindrical_gear_flank", f"{v.teil} – links", flanke)
    rechts = m.komponente("cylindrical_gear_flank", f"{v.teil} – rechts", flanke)
    m.relation("flank", gear=rad, left=links, right=rechts)
    korrekturen = []
    if p is not None and p.ca:
        korrekturen.append(m.komponente("tip_relief", f"{v.teil} – Kopfrücknahme", {
            "tip_relief_depth": p.ca, "tip_relief_datum_diameter": p.dca, "shape_of_relief": "linear"}))
    if p is not None and abs(p.fh_alpha) > p.toleranz:
        korrekturen.append(m.komponente("profile_slope", f"{v.teil} – Profilwinkel", {"profile_slope": p.fh_alpha}))
    cb = vd.breitenballigkeit(v)
    if p is not None and cb is not None and abs(cb) > p.toleranz:
        korrekturen.append(m.komponente("helix_crowning", f"{v.teil} – Breitenballigkeit", {
            "helix_crowning_amount_datum_face": cb, "helix_crowning_amount_non_datum_face": cb,
            "shape_of_helix_crowning": "parabolic"}))
    for k in korrekturen:
        for f in (links, rechts):
            m.relation("reference", origin=f, referenced=k)
    return rad


def modell(liste: list[Verzahnung], paare: list[Paar], name: str = "3DGmax",
           programm_version: str = "") -> dict:
    """REXS-Modell (dict fuer json.dump) der Raeder, Paare, Wellen und Planetensaetze."""
    m = _Modell()
    m.komponente("gear_unit", name, {"model_name": name})
    ids = [_rad(m, v) for v in liste]
    for k, gruppe in enumerate(vd.wellen(liste), 1):
        welle = m.komponente("shaft", " + ".join(liste[i].teil for i in gruppe), {})
        for i in gruppe:
            m.relation("assembly", assembly=welle, part=ids[i])
    index = {id(v): i for i, v in enumerate(liste)}
    for p in paare:
        w = vd.paar_werte(p)
        stufe = m.komponente("cylindrical_stage", f"{p.a.teil} – {p.b.teil}", {
            "center_distance": p.abstand, "gear_ratio": w["u"], "sum_of_addendum_modification_coefficients": w["summe_x"],
            "radial_contact_ratio": p.eps_alpha, "overlap_contact_ratio": p.eps_beta,
            "total_contact_ratio": w["eps_gamma"], "minimum_normal_backlash": p.spiel,
            "maximum_normal_backlash": p.spiel})
        a, b = index[id(p.a)], index[id(p.b)]
        m.relation("stage", stage=stufe, gear_1=ids[a], gear_2=ids[b])
        klein_ist_a = w["klein"] == p.a.teil
        gleiten = w["gleiten"] or (None, None)
        for i, v in ((a, p.a), (b, p.b)):
            klein = (v is p.a) == klein_ist_a
            daten = m.komponente("cylindrical_stage_gear_data", f"{p.a.teil} – {p.b.teil}: {v.teil}", {
                "tip_clearance": w["c_klein"] if not klein else w["c_gross"],  # Kopf des anderen Rads am eigenen Fuss
                "operating_pressure_angle_in_the_transverse_section": p.alpha_wt,
                "specific_sliding_at_root_diameter": gleiten[0] if klein else gleiten[1]})
            m.relation("stage_gear_data", stage=stufe, gear=ids[i], stage_gear_data=daten)
    wellen = vd.wellen(liste)
    welle_von = {i: k for k, g in enumerate(wellen) for i in g}
    wellen_ids = [c["id"] for c in m.komponenten if c["type"] == "shaft"]
    for n, s in enumerate(vd.planetensaetze(liste, paare), 1):
        satz = m.komponente("planetary_stage", f"Planetensatz {n}", {})
        m.relation("central_shaft", planetary_stage=satz, shaft=wellen_ids[welle_von[s.sonne]])
        for i in s.planeten:
            m.relation("planet_shaft", planetary_stage=satz, shaft=wellen_ids[welle_von[i]])
    jetzt = datetime.datetime.now(datetime.timezone.utc).astimezone().replace(microsecond=0)
    datum = jetzt.strftime("%Y-%m-%dT%H:%M:%S") + jetzt.strftime("%z")[:3] + ":" + jetzt.strftime("%z")[3:]
    return {"model": {"version": VERSION, "applicationId": "3DGmax", "applicationVersion": programm_version or "0",
                      "date": datum, "applicationLanguage": "de", "relations": m.relationen,
                      "components": m.komponenten}}
