"""Geaenderte PMI-Werte verlustfrei in eine Kopie der STEP-Datei schreiben (PLAN §8.28, Stufe 1, ohne Qt).

Der Rueckweg ueber OCCT (XCAF lesen, AP242 schreiben) verliert Teile der semantischen PMI (Versuch an NIST FTC-10:
81 -> 69 PMI, Bezugsstellen fehlen). Deshalb bleibt die Originaldatei Zeichen fuer Zeichen erhalten; ersetzt wird nur
die Zahl der Mess-Entitaet, die ein bearbeiteter Wert in der Datei hat:
- Toleranzwert: Betrag der GEOMETRIC_TOLERANCE (magnitude),
- Nennmass, Grenzmasse: MEASURE_REPRESENTATION_ITEM 'nominal value' / 'upper limit' / 'lower limit' der
  DIMENSIONAL_CHARACTERISTIC_REPRESENTATION,
- Abmasse: TOLERANCE_VALUE (unteres, oberes) der PLUS_MINUS_TOLERANCE,
in der Einheit der Datei. Nicht geschrieben (im Bericht): Passung, Materialbedingung, Werte ohne Entsprechung in der
Datei (z. B. ein neu angegebenes Abmass), Mess-Entitaeten, die mehrere PMI teilen, und eigene PMI.
Die grafische Darstellung (Polylinien) zeigt weiter die alten Werte - der Bericht nennt die betroffenen PMI.

Stufe 2 (anhaengen): eigene PMI als neue Entitaeten vor dem Ende des DATA-Abschnitts, nach der CAx-IF-Praxis wie in
den NIST-Dateien: SHAPE_ASPECT mit GEOMETRIC_ITEM_SPECIFIC_USAGE je Flaeche; Toleranz einfach (FLATNESS_TOLERANCE(..))
oder komplex mit GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE (DATUM_SYSTEM, DATUM_REFERENCE_COMPARTMENT) und
GEOMETRIC_TOLERANCE_WITH_MODIFIERS (Materialbedingung), Durchmesserzone als TOLERANCE_ZONE; Masse als DIMENSIONAL_SIZE
bzw. DIMENSIONAL_LOCATION mit SHAPE_DIMENSION_REPRESENTATION ('nominal value') und PLUS_MINUS_TOLERANCE
(TOLERANCE_VALUE oder LIMITS_AND_FITS); Bezuege als DATUM_FEATURE, DATUM und SHAPE_ASPECT_RELATIONSHIP. Nur
Einzelteile und Baugruppen (Produktform, Darstellung und Einheiten je Teil aus den Flaechen der PMI; alle Flaechen
einer PMI in einem Teil); Lagemasse ohne genau zwei Flaechen werden gemeldet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..i18n import tr
from . import p21
from .p21 import Ref

ZAHLEN_FELDER = ("nennwert", "oben", "unten", "wert")
MASS_ART = r"(?:POSITIVE_)?(?:LENGTH|PLANE_ANGLE)_MEASURE|RATIO_MEASURE|PARAMETER_VALUE"


@dataclass
class Bericht:
    geschrieben: list[tuple[int, str]] = field(default_factory=list)  # (PMI-Nummer, Feld)
    uebersprungen: list[tuple[int, str, str]] = field(default_factory=list)  # (Nummer, Feld, Grund)
    grafik_veraltet: list[int] = field(default_factory=list)  # PMI mit Darstellung der alten Werte
    neu: list[int] = field(default_factory=list)  # eigene PMI, als neue Entitaeten angehaengt


def _messwert(datei, ref) -> int | None:
    return ref.id if isinstance(ref, Ref) and datei.get(ref) is not None else None


def ziele(datei: p21.P21Datei, p) -> dict[str, int]:
    """Feld -> Id der Mess-Entitaet, die den Wert der PMI in der Datei traegt."""
    out: dict[str, int] = {}
    e = datei.entities.get(p.step_id)
    if e is None:
        return out
    if p.art == "toleranz":
        grund = e.args("GEOMETRIC_TOLERANCE") if e.is_a("GEOMETRIC_TOLERANCE") else e.args()
        if len(grund) >= 3 and _messwert(datei, grund[2]):
            out["wert"] = grund[2].id
        return out
    if p.art != "mass":
        return out
    namen = {"nominal value": "nennwert", "upper limit": "oben", "lower limit": "unten"}
    for rid in datei.referrers().get(p.step_id, []):
        r = datei.entities[rid]
        if r.is_a("DIMENSIONAL_CHARACTERISTIC_REPRESENTATION"):
            darst = datei.get(r.args()[1])
            items = list(darst.args(next(iter(darst.parts)))[1] or []) if darst is not None else []
            while items:
                it = items.pop()
                ie = datei.get(it)
                if ie is None:
                    continue
                if ie.is_a("COMPOUND_REPRESENTATION_ITEM"):
                    teil = ie.args("COMPOUND_REPRESENTATION_ITEM")[0]
                    items += list(getattr(teil, "args", [teil])[0] or [])
                    continue
                name = ie.args("REPRESENTATION_ITEM")[0] if ie.is_a("REPRESENTATION_ITEM") else ""
                feld = namen.get(name or "nominal value")
                if feld == "nennwert" or (feld and p.grenzmass):
                    out.setdefault(feld, it.id)
        elif r.is_a("PLUS_MINUS_TOLERANCE") and not p.grenzmass:
            bereich = datei.get(r.args("PLUS_MINUS_TOLERANCE")[0])
            if bereich is not None and bereich.is_a("TOLERANCE_VALUE"):
                unten, oben = bereich.args("TOLERANCE_VALUE")[:2]
                for feld, ref in (("unten", unten), ("oben", oben)):
                    if _messwert(datei, ref):
                        out[feld] = ref.id
    return out


def _faktor(datei, mess_id: int) -> float:
    """Dateiwert * Faktor = Wert in 3DGmax (mm bzw. Grad)."""
    from .pmi_step import einheit_mm, messwert_roh
    _, einheit = messwert_roh(datei, Ref(mess_id))
    e = datei.get(einheit) if isinstance(einheit, Ref) else None
    text = " ".join(datei.entities[mess_id].parts)
    if "PLANE_ANGLE" in text:
        return 57.29577951308232 if e is not None and e.is_a("SI_UNIT") else 1.0
    return einheit_mm(datei, einheit)


def _real(x: float) -> str:
    """REAL nach ISO 10303-21: immer mit Dezimalpunkt."""
    t = f"{x:.12g}"
    return t if ("." in t or "E" in t.upper()) else t + "."


def _anweisung(text: str, eid: int) -> tuple[int, int]:
    """Anfang und Ende (nach ';') der Anweisung #eid im Dateitext."""
    m = re.search(rf"(?<![\w#])#{eid}\s*=", text)
    if m is None:
        raise KeyError(eid)
    in_str = False
    for i in range(m.end(), len(text)):
        if text[i] == "'":
            in_str = not in_str
        elif text[i] == ";" and not in_str:
            return m.start(), i + 1
    raise KeyError(eid)


def _ersetze_zahl(text: str, eid: int, wert: float) -> str:
    a, b = _anweisung(text, eid)
    stueck = text[a:b]
    neu, n = re.subn(rf"((?:{MASS_ART})\s*\(\s*)[-+0-9.Ee]+(\s*\))", lambda m: m.group(1) + _real(wert) + m.group(2),
                     stueck, count=1)
    if n == 0:  # ohne Typangabe: MEASURE_WITH_UNIT(0.1,#5)
        neu, n = re.subn(r"(MEASURE_WITH_UNIT\s*\(\s*)[-+0-9.Ee]+", lambda m: m.group(1) + _real(wert), stueck,
                         count=1)
    if n == 0:
        raise ValueError(eid)
    return text[:a] + neu + text[b:]


class _Anhang:
    """Neue Entitaeten mit fortlaufenden Ids ab der hoechsten Id der Datei; Teil-Kontext (Produktform, Darstellung,
    Einheiten) je PMI aus ihren Flaechen - auch in Baugruppen."""

    def __init__(self, datei: p21.P21Datei, modell):
        self.datei, self.modell = datei, modell
        self.naechste = max(datei.entities) + 1
        self.zeilen: list[str] = []
        self.flaeche_zu_step = {i: eid for eid, i in getattr(modell, "step_zu_flaeche", {}).items()}
        self.pds = self.darst = self.kontext = self.einheit_laenge = self.einheit_winkel = None
        self.bezuege = {(e.args("DATUM")[2].id if isinstance(e.args("DATUM")[2], Ref) else None, e.args("DATUM")[4]):
                        e.id for e in datei.of_type("DATUM")}
        self._sdr = {e.args("SHAPE_DEFINITION_REPRESENTATION")[1].id: e.args("SHAPE_DEFINITION_REPRESENTATION")[0].id
                     for e in datei.of_type("SHAPE_DEFINITION_REPRESENTATION")
                     if all(isinstance(x, Ref) for x in e.args("SHAPE_DEFINITION_REPRESENTATION")[:2])}

    def neu(self, text: str) -> int:
        eid = self.naechste
        self.naechste += 1
        self.zeilen.append(f"#{eid}={text};")
        return eid

    def bezug(self, name: str) -> int | None:
        return self.bezuege.get((self.pds, name))

    def _pds_von(self, darst: int) -> int | None:
        """Produktform zur Darstellung: direkt ueber SHAPE_DEFINITION_REPRESENTATION oder ueber verknuepfte
        Darstellungen (SHAPE_REPRESENTATION_RELATIONSHIP)."""
        offen, gesehen = [darst], {darst}
        verweise = self.datei.referrers()
        while offen:
            x = offen.pop(0)
            if x in self._sdr and self.datei.entities[self._sdr[x]].is_a("PRODUCT_DEFINITION_SHAPE"):
                return self._sdr[x]
            for r in verweise.get(x, []):
                e = self.datei.entities[r]
                if e.is_a("SHAPE_REPRESENTATION_RELATIONSHIP") or e.is_a("REPRESENTATION_RELATIONSHIP"):
                    teil = "REPRESENTATION_RELATIONSHIP" if "REPRESENTATION_RELATIONSHIP" in e.parts else \
                        next(iter(e.parts))
                    for y in e.args(teil)[2:4]:
                        if isinstance(y, Ref) and y.id not in gesehen:
                            gesehen.add(y.id)
                            offen.append(y.id)
        return None

    def _einheiten(self, kontext: int):
        laenge = winkel = None
        e = self.datei.entities.get(kontext)
        if e is not None and e.is_a("GLOBAL_UNIT_ASSIGNED_CONTEXT"):
            for u in e.args("GLOBAL_UNIT_ASSIGNED_CONTEXT")[0] or []:
                ue = self.datei.get(u)
                if ue is not None and ue.is_a("LENGTH_UNIT"):
                    laenge = laenge or u.id
                elif ue is not None and ue.is_a("PLANE_ANGLE_UNIT"):
                    winkel = winkel or u.id
        return laenge, winkel

    def darstellung(self, flaeche_step: int) -> int | None:
        """Formdarstellung (REPRESENTATION), in der die Flaeche liegt: aufwaerts ueber die Verweise."""
        offen, gesehen = [flaeche_step], set()
        verweise = self.datei.referrers()
        while offen:
            x = offen.pop(0)
            for r in verweise.get(x, []):
                if r in gesehen:
                    continue
                gesehen.add(r)
                e = self.datei.entities[r]
                if e.is_a("SHAPE_REPRESENTATION") or e.is_a("ADVANCED_BREP_SHAPE_REPRESENTATION") or \
                        e.is_a("MANIFOLD_SURFACE_SHAPE_REPRESENTATION"):
                    return r
                if not (e.is_a("STYLED_ITEM") or e.is_a("GEOMETRIC_ITEM_SPECIFIC_USAGE")):
                    offen.append(r)
        return None

    def waehle(self, flaechen) -> str | None:
        """Teil-Kontext der Flaechen setzen; Fehlertext, wenn sie nicht in einem Teil mit Einheiten liegen."""
        stepf = [self.flaeche_zu_step.get(i) for i in sorted(flaechen)]
        if not stepf or None in stepf:
            return tr("Flächen ohne Entsprechung in der Datei")
        darst = {self.darstellung(f) for f in stepf}
        if len(darst) != 1 or None in darst:
            return tr("Flächen aus mehreren Teilen")
        self.darst = darst.pop()
        self.pds = self._pds_von(self.darst)
        rep = self.datei.entities[self.darst]
        teil = "REPRESENTATION" if "REPRESENTATION" in rep.parts else next(iter(rep.parts))
        args = rep.args(teil)
        kontext = args[2] if len(args) > 2 else None
        self.kontext = kontext.id if isinstance(kontext, Ref) else None
        self.einheit_laenge, self.einheit_winkel = self._einheiten(self.kontext) if self.kontext else (None, None)
        if self.pds is None or self.einheit_laenge is None:
            return tr("nur für Teile mit Produktform und Einheiten")
        self._stepf = stepf
        return None

    def aspekt(self, flaechen, art: str = "SHAPE_ASPECT") -> int | None:
        """Formaspekt der Flaechen im gewaehlten Teil (waehle vorher)."""
        stepf = [self.flaeche_zu_step.get(i) for i in sorted(flaechen)]
        if not stepf or None in stepf:
            return None
        sa = self.neu(f"{art}('','',#{self.pds},.T.)" if art == "SHAPE_ASPECT" else f"{art}('',$,#{self.pds},.T.)")
        for f in stepf:
            self.neu(f"GEOMETRIC_ITEM_SPECIFIC_USAGE('','',#{sa},#{self.darst},#{f})")
        return sa

    def winkel_dateiwert(self, grad: float) -> float:
        """Grad in die Winkeleinheit der Datei (SI: Radiant)."""
        e = self.datei.entities.get(self.einheit_winkel)
        return grad / 57.29577951308232 if e is not None and e.is_a("SI_UNIT") else grad

    def mass(self, wert: float, winkel: bool = False, art: str = "LENGTH_MEASURE") -> int:
        einheit = self.einheit_winkel if winkel else self.einheit_laenge
        wert = self.winkel_dateiwert(wert) if winkel else wert
        return self.neu(f"{'PLANE_ANGLE' if winkel else 'LENGTH'}_MEASURE_WITH_UNIT("
                        f"{'PLANE_ANGLE_MEASURE' if winkel else art}({_real(wert)}),#{einheit})")


GROESSE_NAME = {"Size_Diameter": "diameter", "Size_Radius": "radius", "Size_Thickness": "thickness",
                "Size_SphericalDiameter": "spherical diameter", "Size_SphericalRadius": "spherical radius"}


def _schreibe_bezug(a: _Anhang, p) -> str | None:
    fehler = a.waehle(p.flaechen)
    if fehler:
        return fehler
    if a.bezug(p.name) is not None:
        return tr("Bezug {} gibt es in der Datei schon").format(p.name)
    df = a.aspekt(p.flaechen, "DATUM_FEATURE")
    if df is None:
        return tr("Flächen ohne Entsprechung in der Datei")
    d = a.neu(f"DATUM('',$,#{a.pds},.F.,'{p.name}')")
    a.neu(f"SHAPE_ASPECT_RELATIONSHIP('',$,#{df},#{d})")
    a.bezuege[(a.pds, p.name)] = d
    return None


def _schreibe_toleranz(a: _Anhang, p) -> str | None:
    from .pmi_step import TOL_ARTEN
    entitaet = {v: k for k, v in TOL_ARTEN.items()}.get(p.typ)
    if entitaet is None or p.wert is None:
        return tr("Toleranzart nicht schreibbar")
    fehler = a.waehle(p.flaechen)
    if fehler:
        return fehler
    fehlend = [b.name for b in p.bezuege if a.bezug(b.name) is None]
    if fehlend:
        return tr("Bezug {} fehlt in der Datei").format(", ".join(fehlend))
    sa = a.aspekt(p.flaechen)
    if sa is None:
        return tr("Flächen ohne Entsprechung in der Datei")
    betrag = a.mass(p.wert)
    teile = {entitaet: "()"}
    if p.bezuege:
        abteile = [a.neu(f"DATUM_REFERENCE_COMPARTMENT('',$,#{a.pds},.F.,#{a.bezug(b.name)},$)")
                   for b in sorted(p.bezuege, key=lambda b: b.stelle)]
        system = a.neu(f"DATUM_SYSTEM('',$,#{a.pds},.F.,({','.join(f'#{x}' for x in abteile)}))")
        teile["GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE"] = f"((#{system}))"
    mods = {"M": "MAXIMUM_MATERIAL_REQUIREMENT", "L": "LEAST_MATERIAL_REQUIREMENT"}.get(p.material)
    if mods:
        teile["GEOMETRIC_TOLERANCE_WITH_MODIFIERS"] = f"((.{mods}.))"
    name = p.name or p.typ
    if len(teile) == 1:
        tol = a.neu(f"{entitaet}('{name}','',#{betrag},#{sa})")
    else:
        teile["GEOMETRIC_TOLERANCE"] = f"('{name}','',#{betrag},#{sa})"
        tol = a.neu("( " + " ".join(f"{k}{teile[k]}" for k in sorted(teile)) + " )")
    if "Diameter" in p.modifikatoren:
        form = a.neu("TOLERANCE_ZONE_FORM('cylindrical or circular')")
        a.neu(f"TOLERANCE_ZONE('',$,#{a.pds},.F.,(#{tol}),#{form})")
    return None


def _schreibe_mass(a: _Anhang, p) -> str | None:
    if p.nennwert is None:
        return tr("Maß ohne Wert")
    fehler = a.waehle(p.flaechen)
    if fehler:
        return fehler
    if p.typ in GROESSE_NAME:
        sa = a.aspekt(p.flaechen)
        if sa is None:
            return tr("Flächen ohne Entsprechung in der Datei")
        dim = a.neu(f"DIMENSIONAL_SIZE(#{sa},'{GROESSE_NAME[p.typ]}')")
    elif p.typ == "Size_Angular":
        if a.einheit_winkel is None:
            return tr("Keine Winkeleinheit in der Datei")
        sa = a.aspekt(p.flaechen)
        if sa is None:
            return tr("Flächen ohne Entsprechung in der Datei")
        dim = a.neu(f"ANGULAR_SIZE(#{sa},'',.EQUAL.)")
    elif p.typ in ("Location_LinearDistance", "Location_Angular") and len(p.flaechen) == 2:
        if p.typ == "Location_Angular" and a.einheit_winkel is None:
            return tr("Keine Winkeleinheit in der Datei")
        f1, f2 = sorted(p.flaechen)
        s1, s2 = a.aspekt({f1}), a.aspekt({f2})
        if s1 is None or s2 is None:
            return tr("Flächen ohne Entsprechung in der Datei")
        dim = a.neu(f"DIMENSIONAL_LOCATION('linear distance','',#{s1},#{s2})" if p.typ == "Location_LinearDistance"
                    else f"ANGULAR_LOCATION('angular location','',#{s1},#{s2},.EQUAL.)")
    else:
        return tr("Maßart nicht schreibbar")
    winkel = p.typ in ("Size_Angular", "Location_Angular")
    if winkel:
        wert = a.neu(f"( MEASURE_REPRESENTATION_ITEM() MEASURE_WITH_UNIT(PLANE_ANGLE_MEASURE("
                     f"{_real(a.winkel_dateiwert(abs(p.nennwert)))}),#{a.einheit_winkel}) PLANE_ANGLE_MEASURE_WITH_UNIT() "
                     f"REPRESENTATION_ITEM('nominal value') )")
    else:
        wert = a.neu(f"( LENGTH_MEASURE_WITH_UNIT() MEASURE_REPRESENTATION_ITEM() MEASURE_WITH_UNIT("
                     f"LENGTH_MEASURE({_real(abs(p.nennwert))}),#{a.einheit_laenge}) REPRESENTATION_ITEM('nominal value') )")
    darst = a.neu(f"SHAPE_DIMENSION_REPRESENTATION('',(#{wert}),#{a.kontext})")
    a.neu(f"DIMENSIONAL_CHARACTERISTIC_REPRESENTATION(#{dim},#{darst})")
    if p.oben is not None and p.unten is not None and not p.grenzmass:
        tv = a.neu(f"TOLERANCE_VALUE(#{a.mass(p.unten, winkel)},#{a.mass(p.oben, winkel)})")
        a.neu(f"PLUS_MINUS_TOLERANCE(#{tv},#{dim})")
    elif p.passung:
        import re as _re
        m = _re.match(r"([A-Za-z]+)(\d+)$", p.passung)
        if m:
            lf = a.neu(f"LIMITS_AND_FITS('{m.group(1)}','','{m.group(2)}','')")
            a.neu(f"PLUS_MINUS_TOLERANCE(#{lf},#{dim})")
    return None


def _haenge_an(text: str, datei, modell, pmi, bericht: Bericht) -> str:
    eigene = [p for p in pmi if p.quelle == "eigen" and p.art in ("mass", "toleranz", "bezug")]
    if not eigene:
        return text
    a = _Anhang(datei, modell)
    # Bezuege zuerst: Toleranzen verweisen auf sie
    for p in sorted(eigene, key=lambda p: p.art != "bezug"):
        vorher = (len(a.zeilen), a.naechste)
        schreiber = {"bezug": _schreibe_bezug, "toleranz": _schreibe_toleranz, "mass": _schreibe_mass}[p.art]
        grund = schreiber(a, p)
        if grund:
            del a.zeilen[vorher[0]:]  # halb geschriebene Entitaeten verwerfen
            a.naechste = vorher[1]
            bericht.uebersprungen.append((p.nummer, "neu", grund))
        else:
            bericht.neu.append(p.nummer)
    if not a.zeilen:
        return text
    ende = text.rfind("ENDSEC;", 0, text.find("END-ISO-10303-21"))
    return text[:ende] + "\n".join(a.zeilen) + "\n" + text[ende:]


def schreibe(quelle: str, ziel: str, pmi: list, modell=None) -> Bericht:
    """Kopie von 'quelle' mit den bearbeiteten Werten der PMI nach 'ziel'; mit modell auch die eigenen PMI."""
    with open(quelle, "rb") as f:
        roh = f.read()
    try:
        text, kodierung = roh.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        text, kodierung = roh.decode("latin-1"), "latin-1"
    datei = p21.lese_text(text)
    bericht = Bericht()
    verweise = datei.referrers()
    for p in pmi:
        if not p.bearbeitet or not p.original or p.quelle == "eigen":
            continue
        felder = ziele(datei, p)
        for feld, alt in p.original.items():
            neu = getattr(p, feld, None)
            if neu == alt:
                continue
            if feld not in ZAHLEN_FELDER:
                bericht.uebersprungen.append((p.nummer, feld, tr("nicht schreibbar")))
                continue
            eid = felder.get(feld)
            if eid is None or neu is None:
                bericht.uebersprungen.append((p.nummer, feld, tr("keine Entsprechung in der Datei")))
                continue
            if len(verweise.get(eid, [])) > 1:
                bericht.uebersprungen.append((p.nummer, feld, tr("Wert wird von mehreren PMI geteilt")))
                continue
            try:
                text = _ersetze_zahl(text, eid, float(neu) / _faktor(datei, eid))
            except (KeyError, ValueError):
                bericht.uebersprungen.append((p.nummer, feld, tr("Zahl nicht gefunden")))
                continue
            bericht.geschrieben.append((p.nummer, feld))
        if any(n == p.nummer for n, _ in bericht.geschrieben) and p.grafisch:
            bericht.grafik_veraltet.append(p.nummer)
    if modell is not None:
        text = _haenge_an(text, datei, modell, pmi, bericht)
    with open(ziel, "w", encoding=kodierung, newline="") as f:
        f.write(text)
    return bericht
