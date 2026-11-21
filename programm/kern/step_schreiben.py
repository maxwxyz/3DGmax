"""Geaenderte PMI-Werte verlustfrei in eine Kopie der STEP-Datei schreiben (PLAN §8.28, Stufe 1, ohne Qt).

Der Rueckweg ueber OCCT (XCAF lesen, AP242 schreiben) verliert Teile der semantischen PMI (Versuch an NIST FTC-10:
81 -> 69 PMI, Bezugsstellen fehlen). Deshalb bleibt die Originaldatei Zeichen fuer Zeichen erhalten; ersetzt wird nur
die Zahl der Mess-Entitaet, die ein bearbeiteter Wert in der Datei hat:
- Toleranzwert: Betrag der GEOMETRIC_TOLERANCE (magnitude),
- Nennmass, Grenzmasse: MEASURE_REPRESENTATION_ITEM 'nominal value' / 'upper limit' / 'lower limit' der
  DIMENSIONAL_CHARACTERISTIC_REPRESENTATION,
- Abmasse: TOLERANCE_VALUE (unteres, oberes) der PLUS_MINUS_TOLERANCE,
in der Einheit der Datei. Nicht geschrieben (im Bericht): Passung, Materialbedingung, Werte ohne Entsprechung in der
Datei (z. B. ein neu angegebenes Abmass), Mess-Entitaeten, die mehrere PMI teilen, und eigene PMI. Toleranzklasse
(vorhandene LIMITS_AND_FITS) und Materialbedingung (GEOMETRIC_TOLERANCE_WITH_MODIFIERS, einfache Entitaet wird in
die komplexe Form umgeschrieben) werden ersetzt.
Die grafische Darstellung (Polylinien) zeigt weiter die alten Werte - der Bericht nennt die betroffenen PMI.

Stufe 2 (anhaengen): eigene PMI als neue Entitaeten vor dem Ende des DATA-Abschnitts, nach der CAx-IF-Praxis wie in
den NIST-Dateien: SHAPE_ASPECT mit GEOMETRIC_ITEM_SPECIFIC_USAGE je Flaeche; Toleranz einfach (FLATNESS_TOLERANCE(..))
oder komplex mit GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE (DATUM_SYSTEM, DATUM_REFERENCE_COMPARTMENT) und
GEOMETRIC_TOLERANCE_WITH_MODIFIERS (Materialbedingung), Durchmesserzone als TOLERANCE_ZONE; Masse als DIMENSIONAL_SIZE
bzw. DIMENSIONAL_LOCATION mit SHAPE_DIMENSION_REPRESENTATION ('nominal value') und PLUS_MINUS_TOLERANCE
(TOLERANCE_VALUE oder LIMITS_AND_FITS); Bezuege als DATUM_FEATURE, DATUM und SHAPE_ASPECT_RELATIONSHIP. Nur
Einzelteile und Baugruppen (Produktform, Darstellung und Einheiten je Teil aus den Flaechen der PMI; alle Flaechen
einer PMI in einem Teil); Lagemasse ohne genau zwei Flaechen werden gemeldet.

Stufe 3: zu jeder geschriebenen eigenen PMI ihre Darstellung (Rahmen, Linien, Pfeile, Texte als Glyphen) als
tessellierte AP242-Praesentation, verknuepft mit der Semantik (kern.pmi_darstellung).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from ..i18n import tr
from . import p21
from .p21 import Ref

ZAHLEN_FELDER = ("nennwert", "oben", "unten", "wert")
MATERIAL_ENUM = {"M": "MAXIMUM_MATERIAL_REQUIREMENT", "L": "LEAST_MATERIAL_REQUIREMENT"}
MASS_ART = r"(?:POSITIVE_)?(?:LENGTH|PLANE_ANGLE)_MEASURE|RATIO_MEASURE|PARAMETER_VALUE"


@dataclass
class Bericht:
    geschrieben: list[tuple[int, str]] = field(default_factory=list)  # (PMI-Nummer, Feld)
    uebersprungen: list[tuple[int, str, str]] = field(default_factory=list)  # (Nummer, Feld, Grund)
    grafik_veraltet: list[int] = field(default_factory=list)  # PMI mit Darstellung der alten Werte
    neu: list[int] = field(default_factory=list)  # eigene PMI, als neue Entitaeten angehaengt
    dargestellt: list[int] = field(default_factory=list)  # eigene PMI mit geschriebener Darstellung (Callout)
    repariert: list[int] = field(default_factory=list)  # nur grafische PMI, jetzt mit Semantik am vorhandenen Callout
    ap242_kopie: bool = False  # Quelldaten fuer diese Kopie von AP203 auf AP242 uebertragen


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
    from .pmi_step import mass_item_name, mass_items, messwert_roh
    namen = {"nominal value": "nennwert", "upper limit": "oben", "lower limit": "unten"}
    for rid in datei.referrers().get(p.step_id, []):
        r = datei.entities[rid]
        if r.is_a("DIMENSIONAL_CHARACTERISTIC_REPRESENTATION"):
            darst = datei.get(r.args()[1])
            if darst is None:
                continue
            for ie in mass_items(datei, darst):
                if messwert_roh(datei, Ref(ie.id))[0] is None:
                    continue
                name = mass_item_name(ie)
                feld = namen.get(name or "nominal value")
                if feld == "nennwert" or (feld and p.grenzmass):
                    out.setdefault(feld, ie.id)
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
    from .pmi_step import einheit_mm, ist_winkelmass, messwert_roh
    _, einheit = messwert_roh(datei, Ref(mess_id))
    e = datei.get(einheit) if isinstance(einheit, Ref) else None
    if ist_winkelmass(datei.entities[mess_id]):
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


def randkanten(datei, flaeche):
    """EDGE_CURVE-Ids aller Raender einer ADVANCED_FACE."""
    face = datei.entities[flaeche]
    if not face.is_a("ADVANCED_FACE"):
        return set()
    kanten = set()
    for rand in face.args("ADVANCED_FACE")[1]:
        schleife = datei.get(datei.get(rand).args()[1])
        if schleife.is_a("EDGE_LOOP"):
            kanten.update(datei.get(ref).args("ORIENTED_EDGE")[3].id for ref in schleife.args("EDGE_LOOP")[1])
    return kanten


def randpunkte(datei, kanten):
    return {ref.id for k in kanten for ref in datei.entities[k].args("EDGE_CURVE")[1:3]}


def _enthaelt_massziel(datei, flaeche, ziel):
    kanten = randkanten(datei, flaeche)
    return ziel in kanten or ziel in randpunkte(datei, kanten)


class _Anhang:
    """Neue Entitaeten mit fortlaufenden Ids ab der hoechsten Id der Datei; Teil-Kontext (Produktform, Darstellung,
    Einheiten) je PMI aus ihren Flaechen - auch in Baugruppen."""

    def __init__(self, datei: p21.P21Datei, modell):
        self.datei, self.modell = datei, modell
        self.naechste = max(datei.entities) + 1
        self.zeilen: list[str] = []
        self.flaeche_zu_step = modell.flaeche_zu_step
        self.pds = self.darst = self.kontext = self.einheit_laenge = self.einheit_winkel = None
        self.semantik = None  # Entitaet der zuletzt geschriebenen PMI (Ziel der Darstellung)
        self.bezuege = {(e.args("DATUM")[2].id if isinstance(e.args("DATUM")[2], Ref) else None, e.args("DATUM")[4]):
                        e.id for e in datei.of_type("DATUM")}
        self._sdr = {}
        for e in datei.of_type("SHAPE_DEFINITION_REPRESENTATION"):
            pds, rep = e.args("SHAPE_DEFINITION_REPRESENTATION")[:2]
            form = datei.get(pds) if isinstance(pds, Ref) else None
            if isinstance(rep, Ref) and form is not None and form.is_a("PRODUCT_DEFINITION_SHAPE"):
                self._sdr.setdefault(rep.id, set()).add(pds.id)

    def neu(self, text: str) -> int:
        eid = self.naechste
        self.naechste += 1
        self.zeilen.append(f"#{eid}={text};")
        return eid

    def bezug(self, name: str) -> int | None:
        return self.bezuege.get((self.pds, name))

    def _produktformen(self, darst: int) -> set[int]:
        """Produktform zur Darstellung: direkt ueber SHAPE_DEFINITION_REPRESENTATION oder ueber verknuepfte
        Darstellungen (SHAPE_REPRESENTATION_RELATIONSHIP)."""
        offen, gesehen, produktformen = [darst], {darst}, set()
        verweise = self.datei.referrers()
        while offen:
            x = offen.pop()
            produktformen.update(self._sdr.get(x, ()))
            for r in verweise.get(x, []):
                e = self.datei.entities[r]
                if e.is_a("REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION"):
                    continue  # keine Teilgrenze in eine Verwendungsinstanz ueberschreiten
                if e.is_a("SHAPE_REPRESENTATION_RELATIONSHIP") or e.is_a("REPRESENTATION_RELATIONSHIP"):
                    teil = "REPRESENTATION_RELATIONSHIP" if "REPRESENTATION_RELATIONSHIP" in e.parts else \
                        next(iter(e.parts))
                    for y in e.args(teil)[2:4]:
                        if isinstance(y, Ref) and y.id not in gesehen:
                            gesehen.add(y.id)
                            offen.append(y.id)
        return produktformen

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
        """Formdarstellung (REPRESENTATION), in der die Flaeche liegt."""
        from .laden import NETZFLAECHEN
        from .praesentation import darstellung_der_flaeche, eindeutige_netzdarstellung, netz_darstellungen
        if self.datei.entities[flaeche_step].parts.keys() & NETZFLAECHEN:
            treffer = netz_darstellungen(self.datei, flaeche_step)
            paare = {(r, p) for r in treffer for p in self._produktformen(r)}
            if len({p for r, p in paare}) != 1:
                return None
            return eindeutige_netzdarstellung(self.datei, {r for r, p in paare})
        return darstellung_der_flaeche(self.datei, flaeche_step)

    def waehle(self, flaechen) -> str | None:
        """Teil-Kontext der Flaechen setzen; Fehlertext, wenn sie nicht in einem Teil mit Einheiten liegen."""
        stepf = [self.flaeche_zu_step.get(i) for i in sorted(flaechen)]
        if not stepf or None in stepf:
            return tr("Flächen ohne Entsprechung in der Datei")
        darst = {self.darstellung(f) for f in stepf}
        if len(darst) != 1 or None in darst:
            return tr("Flächen aus mehreren Teilen")
        self.darst = darst.pop()
        formen = self._produktformen(self.darst)
        self.pds = next(iter(formen)) if len(formen) == 1 else None
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

    def aspekt(self, flaechen, art: str = "SHAPE_ASPECT", *, ziel=None) -> int | None:
        """Formaspekt der Flaechen im gewaehlten Teil (waehle vorher)."""
        stepf = [self.flaeche_zu_step.get(i) for i in sorted(flaechen)]
        if not stepf or None in stepf:
            return None
        if ziel is not None:
            if not any(_enthaelt_massziel(self.datei, f, ziel) for f in stepf):
                return None
            stepf = [ziel]
        sa = self.neu(f"{art}('','',#{self.pds},.T.)" if art == "SHAPE_ASPECT" else f"{art}('',$,#{self.pds},.T.)")
        for f in stepf:
            self.neu(f"GEOMETRIC_ITEM_SPECIFIC_USAGE('','',#{sa},#{self.darst},#{f})")
        return sa

    def bereichsaspekt(self, flaechen_step):
        """Bereichsflaechen als eigene Darstellung im Kontext des Bauteils schreiben."""
        refs = ",".join(f"#{f}" for f in sorted(flaechen_step))
        menge = self.neu(f"CONNECTED_FACE_SET('',({refs}))")
        bereich = self.neu(f"SHAPE_REPRESENTATION('',(#{menge}),#{self.kontext})")
        teil = self.neu(f"SHAPE_ASPECT('','',#{self.pds},.T.)")
        self.neu(f"GEOMETRIC_ITEM_SPECIFIC_USAGE('','',#{teil},#{bereich},#{menge})")
        aspekt = self.neu(f"BETWEEN_SHAPE_ASPECT('',$,#{self.pds},.T.)")
        self.neu(f"SHAPE_ASPECT_RELATIONSHIP('','',#{aspekt},#{teil})")
        return aspekt, bereich

    def verbundaspekt(self, flaechen):
        sa = self.neu(f"COMPOSITE_SHAPE_ASPECT('','DIMENSION',#{self.pds},.F.)")
        for f in sorted(flaechen):
            teil = self.aspekt({f})
            self.neu(f"SHAPE_ASPECT_RELATIONSHIP('','',#{sa},#{teil})")
        return sa

    def symmetriemitte(self, ursprung):
        mitte = self.neu(f"CENTRE_OF_SYMMETRY('','',#{self.pds},.F.)")
        self.neu(f"SHAPE_ASPECT_DERIVING_RELATIONSHIP('','',#{mitte},#{ursprung})")
        return mitte

    def winkel_dateiwert(self, grad: float) -> float:
        """Grad in die Winkeleinheit der Datei (SI: Radiant)."""
        e = self.datei.entities.get(self.einheit_winkel)
        return grad / 57.29577951308232 if e is not None and e.is_a("SI_UNIT") else grad

    def mass(self, wert: float, winkel: bool = False, art: str = "LENGTH_MEASURE") -> int:
        einheit = self.einheit_winkel if winkel else self.einheit_laenge
        wert = self.winkel_dateiwert(wert) if winkel else self.laengen_dateiwert(wert)
        return self.neu(f"{'PLANE_ANGLE' if winkel else 'LENGTH'}_MEASURE_WITH_UNIT("
                        f"{'PLANE_ANGLE_MEASURE' if winkel else art}({_real(wert)}),#{einheit})")

    def laengen_dateiwert(self, mm: float) -> float:
        from .pmi_step import einheit_mm
        return mm / einheit_mm(self.datei, Ref(self.einheit_laenge))


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
    name = p.name.replace("'", "''")
    d = a.neu(f"DATUM('',$,#{a.pds},.F.,'{name}')")
    a.neu(f"SHAPE_ASPECT_RELATIONSHIP('',$,#{df},#{d})")
    a.bezuege[(a.pds, p.name)] = d
    a.semantik = df  # wie in den NIST-Dateien: Darstellung am Bezugsmerkmal
    return None


def _bezug_mods(mods) -> str:
    from .pmi_step import BEZUG_MODS
    if not mods:
        return "$"
    enums = {name: key for key, name in BEZUG_MODS.items()}
    return "(" + ",".join(f"SIMPLE_DATUM_REFERENCE_MODIFIER(.{enums[m]}.)" for m in mods) + ")"


def _bezug_basis(a: _Anhang, b) -> str:
    """Basis eines Abteils im Bezugssystem: der Bezug oder bei 'A-B' eine Liste gemeinsamer Bezugselemente."""
    teile = b.name.split("-")
    if len(teile) == 1:
        return f"#{a.bezug(b.name)}"
    elemente = []
    for n in teile:
        mods = _bezug_mods(b.element_modifikatoren.get(n, ()))
        elemente.append(a.neu(f"DATUM_REFERENCE_ELEMENT('',$,#{a.pds},.F.,#{a.bezug(n)},{mods})"))
    return "COMMON_DATUM_LIST((" + ",".join(f"#{e}" for e in elemente) + "))"


def _schreibe_toleranz(a: _Anhang, p, aspekt=None) -> str | None:
    from .pmi_step import BEZUG_MODS, TOL_ARTEN, TOL_MODS
    entitaet = {v: k for k, v in TOL_ARTEN.items()}.get(p.typ)
    if entitaet is None or p.wert is None:
        return tr("Toleranzart nicht schreibbar")
    flaechen = set(p.flaechen)
    if p.profilteil_ids:
        from .profilteilflaeche import grafikbereich
        bereich = grafikbereich(a.modell, p.callout) if p.callout else None
        if (not bereich or p.typ != "ProfileOfSurface" or not p.bereichsgrenzen or
                bereich[0] != flaechen or set(p.profilteil_ids) != bereich[1].keys()):
            return tr("Die Bereichsgrenzen passen nicht zu den gewählten Flächen.")
        flaechen.update(idx for idx, _ in bereich[1].values())
    if p.zone == "Projected":
        if (len(p.projektionsflaechen) != 1 or p.zonen_wert is None or not math.isfinite(p.zonen_wert)
                or p.zonen_wert <= 0 or p.projektionsversatz is None or not math.isfinite(p.projektionsversatz)):
            return tr("Projektionsursprung, Länge oder Versatz nicht eindeutig")
        flaechen.update(p.projektionsflaechen)
    rechteck = (p.einheitslaenge, p.einheitsbreite)
    if ((any(v is not None for v in rechteck) or "RECTANGULAR" in p.modifikatoren) and
            any(v is None or not math.isfinite(v) or v <= 0 for v in rechteck)):
        return tr("Für die rechteckige Einheitsfläche zwei positive Seitenlängen angeben")
    if ("Maximum_Tolerance" in p.modifikatoren or p.maximum_toleranz is not None and
            (p.material not in ("M", "L") or not math.isfinite(p.maximum_toleranz) or p.maximum_toleranz <= p.wert)):
        return tr("Höchstwert der geometrischen Toleranz nicht gültig")
    fehler = a.waehle(flaechen)
    if fehler:
        return fehler
    fehlend = [n for b in p.bezuege for n in b.name.split("-") if a.bezug(n) is None]
    if fehlend:
        return tr("Bezug {} fehlt in der Datei").format(", ".join(fehlend))
    for b in p.bezuege:
        if b.element_modifikatoren and ("-" not in b.name or b.element_modifikatoren.keys() - set(b.name.split("-"))):
            return tr("Bezugsmodifikator nicht schreibbar")
        gruppen = [b.modifikatoren, *b.element_modifikatoren.values()]
        if any(m not in BEZUG_MODS.values() for gruppe in gruppen for m in gruppe):
            return tr("Bezugsmodifikator nicht schreibbar")
    if p.bereichsgrenzen is None:
        return tr("Zuordnung der Grenzkanten offen")
    if p.bereichsgrenzen:
        from .pmi_zwischenbereich import begrenzter_verband, endmarken_in_datei
        from .pmi_darstellung import verknuepfe_im_modell
        grenzen = p.bereichsgrenzen
        fl = {a.flaeche_zu_step.get(i) for i in p.flaechen} | set(p.profilteil_ids)
        if (aspekt is not None or len(grenzen) != 2 or
                not all(isinstance(g, (tuple, list)) and len(g) == 2 and isinstance(g[1], int)
                        and isinstance(g[0], str) and re.fullmatch("[A-Z]", g[0]) for g in grenzen)
                or grenzen[0][0] == grenzen[1][0] or not begrenzter_verband(a.datei, fl, [g[1] for g in grenzen])):
            return tr("Die Bereichsgrenzen passen nicht zu den gewählten Flächen.")
        marken = endmarken_in_datei(a.datei, p) if p.grenzgrafiken else []
        if marken is None:
            return tr("Die Bereichsgrenzen passen nicht zu den gewählten Flächen.")
        sa, gebiet = a.bereichsaspekt(fl)
        teilkanten = {k for f in p.profilteil_ids for k in randkanten(a.datei, f)}
        for i, ((name, kante), rolle) in enumerate(zip(grenzen, ("start feature", "end feature"))):
            grenze = a.neu(f"SHAPE_ASPECT('{name}','',#{a.pds},.T.)")
            rep = gebiet if kante in teilkanten else a.darst
            a.neu(f"GEOMETRIC_ITEM_SPECIFIC_USAGE('','',#{grenze},#{rep},#{kante})")
            a.neu(f"SHAPE_ASPECT_RELATIONSHIP('{rolle}','',#{sa},#{grenze})")
            if marken:
                modell, callout = marken[i]
                verknuepfe_im_modell(a, modell, grenze, callout)
    else:
        sa = a.aspekt(p.flaechen) if aspekt is None else aspekt
    if sa is None:
        return tr("Flächen ohne Entsprechung in der Datei")
    betrag = a.mass(p.wert)
    teile = {entitaet: "()"}
    if p.bezuege:
        abteile = [a.neu(f"DATUM_REFERENCE_COMPARTMENT('',$,#{a.pds},.F.,{_bezug_basis(a, b)},{_bezug_mods(b.modifikatoren)})")
                   for b in sorted(p.bezuege, key=lambda b: b.stelle)]
        system = a.neu(f"DATUM_SYSTEM('',$,#{a.pds},.F.,({','.join(f'#{x}' for x in abteile)}))")
        teile["GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE"] = f"((#{system}))"
    mods = [enum for enum, name in TOL_MODS.items() if name in p.modifikatoren and enum not in MATERIAL_ENUM.values()]
    if p.material in MATERIAL_ENUM:
        mods.append(MATERIAL_ENUM[p.material])
    if mods:
        teile["GEOMETRIC_TOLERANCE_WITH_MODIFIERS"] = "((" + ",".join(f".{m}." for m in mods) + "))"
    if p.einheitslaenge is not None:
        teile["GEOMETRIC_TOLERANCE_WITH_DEFINED_UNIT"] = f"(#{a.mass(p.einheitslaenge)})"
        teile["GEOMETRIC_TOLERANCE_WITH_DEFINED_AREA_UNIT"] = f"(.RECTANGULAR.,#{a.mass(p.einheitsbreite)})"
    if p.maximum_toleranz is not None:
        teile["GEOMETRIC_TOLERANCE_WITH_MAXIMUM_TOLERANCE"] = f"(#{a.mass(p.maximum_toleranz)})"
    name = (p.name or p.typ).replace("'", "''")
    beschreibung = p.beschreibung.replace("'", "''")
    if len(teile) == 1:
        tol = a.neu(f"{entitaet}('{name}','{beschreibung}',#{betrag},#{sa})")
    else:
        teile["GEOMETRIC_TOLERANCE"] = f"('{name}','{beschreibung}',#{betrag},#{sa})"
        tol = a.neu("( " + " ".join(f"{k}{teile[k]}" for k in sorted(teile)) + " )")
    zonenform = ("spherical" if "SphericalDiameter" in p.modifikatoren else
                 "cylindrical or circular" if "Diameter" in p.modifikatoren else "")
    if zonenform or p.zone == "Projected":
        form = a.neu(f"TOLERANCE_ZONE_FORM('{zonenform}')")
        zone = a.neu(f"TOLERANCE_ZONE('',$,#{a.pds},.F.,(#{tol}),#{form})")
        if p.zone == "Projected":
            ende = a.aspekt(p.projektionsflaechen)
            args = f"#{zone},(),#{ende},#{a.mass(p.zonen_wert)}"
            if p.projektionsversatz:
                a.neu(f"PROJECTED_ZONE_DEFINITION_WITH_OFFSET({args},#{a.mass(p.projektionsversatz)})")
            else:
                a.neu(f"PROJECTED_ZONE_DEFINITION({args})")
    a.semantik = tol
    return None


def _passungsfelder(passung):
    klasse = re.fullmatch(r"([A-Za-z]+)([0-9]+)", passung)
    if klasse is None:
        return None
    lage, grad = klasse.groups()
    art = "hole" if lage[0].isupper() else "shaft"
    return f"'{lage}','{art}','{grad}'"


def _schreibe_mass(a: _Anhang, p) -> str | None:
    from .pmi_step import MASS_TYP1, MASS_TYP2
    if p.nennwert is None:
        return tr("Maß ohne Wert")
    if p.grenzmass and (p.unten is None or p.oben is None or p.unten > p.oben):
        return tr("Grenzmaße unvollständig oder vertauscht")
    mods = set(p.modifikatoren)
    erlaubt = {*MASS_TYP1.values(), *MASS_TYP2.values(), "Envelope", "E"}
    if mods - erlaubt or len(mods.intersection(MASS_TYP1.values())) > 1:
        return tr("Maßmodifikatoren nicht schreibbar oder widersprüchlich")
    fehler = a.waehle(p.flaechen)
    if fehler:
        return fehler
    if p.typ in GROESSE_NAME:
        if p.massziel_step is None and len(p.flaechen) > 1:
            # Einzelne Formaspekte im Verbund erhalten alle Massziele auch in XCAF.
            sa = a.verbundaspekt(p.flaechen)
        else:
            sa = a.aspekt(p.flaechen, ziel=p.massziel_step)
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
    elif p.typ == "Location_LinearDistance_FromOuterToCenter" and p.mittenbezug is not None:
        from .plausibilitaet import ebene_zur_mittenebene
        if ebene_zur_mittenebene(p,a.modell) is None:
            return tr("Maßart nicht schreibbar")
        ursprung = a.aspekt({p.mittenbezug})
        mitte = a.symmetriemitte(a.verbundaspekt(p.flaechen-{p.mittenbezug}))
        dim = a.neu(f"DIMENSIONAL_LOCATION('linear distance outer centre','',#{ursprung},#{mitte})")
    elif p.typ in ("Location_LinearDistance", "Location_LinearDistance_FromOuterToCenter", "Location_LinearDistance_FromOuterToOuter", "Location_Angular") and len(p.flaechen) == 2:
        if p.typ == "Location_Angular" and a.einheit_winkel is None:
            return tr("Keine Winkeleinheit in der Datei")
        f1, f2 = sorted(p.flaechen)
        name = "linear distance"
        if p.typ == "Location_LinearDistance_FromOuterToCenter":
            from .plausibilitaet import ebene_zur_achse
            paar = ebene_zur_achse([a.modell.flaechen[i] for i in (f1, f2)])
            if paar is None:
                return tr("Maßart nicht schreibbar")
            if paar[0] == 1:
                f1, f2 = f2, f1
            name = "linear distance outer centre"
        elif p.typ == "Location_LinearDistance_FromOuterToOuter":
            name = "linear distance outer outer"
        if p.massziel_step is not None:
            wand = [i for i in (f1,f2) if _enthaelt_massziel(a.datei, a.flaeche_zu_step[i], p.massziel_step)]
            if len(wand) != 1 or p.typ != "Location_LinearDistance":
                return tr("Flächen ohne Entsprechung in der Datei")
            f2, = wand
            f1, = p.flaechen-{f2}
        s1, s2 = a.aspekt({f1}), a.aspekt({f2}, ziel=p.massziel_step)
        if s1 is None or s2 is None:
            return tr("Flächen ohne Entsprechung in der Datei")
        if p.mittenabstand:
            if p.typ != "Location_LinearDistance" or p.massziel_step is not None:
                return tr("Maßart nicht schreibbar")
            s1, s2 = a.symmetriemitte(s1), a.symmetriemitte(s2)
        dim = a.neu(f"DIMENSIONAL_LOCATION('{name}','',#{s1},#{s2})" if p.typ != "Location_Angular"
                    else f"ANGULAR_LOCATION('angular location','',#{s1},#{s2},.EQUAL.)")
    else:
        return tr("Maßart nicht schreibbar")
    winkel = p.typ in ("Size_Angular", "Location_Angular")
    masse = [("nominal value", abs(p.nennwert))]
    if p.grenzmass:
        # XCAF uebernimmt das Nennmass sonst je nach Reihenfolge als untere Grenze.
        masse.extend([("lower limit", p.unten), ("upper limit", p.oben)])
    items = []
    for name, mass in masse:
        if winkel:
            item = a.neu(f"( MEASURE_REPRESENTATION_ITEM() MEASURE_WITH_UNIT(PLANE_ANGLE_MEASURE("
                         f"{_real(a.winkel_dateiwert(mass))}),#{a.einheit_winkel}) PLANE_ANGLE_MEASURE_WITH_UNIT() "
                         f"REPRESENTATION_ITEM('{name}') )")
        else:
            item = a.neu(f"( LENGTH_MEASURE_WITH_UNIT() MEASURE_REPRESENTATION_ITEM() MEASURE_WITH_UNIT("
                         f"LENGTH_MEASURE({_real(a.laengen_dateiwert(mass))}),#{a.einheit_laenge}) "
                         f"REPRESENTATION_ITEM('{name}') )")
        items.append(f"#{item}")
    for name, mod in MASS_TYP1.items():
        if mod in mods:
            item = a.neu(f"DESCRIPTIVE_REPRESENTATION_ITEM('dimensional note','{name}')")
            items.append(f"#{item}")
    gruppe = []
    for name, mod in MASS_TYP2.items():
        if mod in mods:
            item = a.neu(f"DESCRIPTIVE_REPRESENTATION_ITEM('dimensional note','{name}')")
            gruppe.append(f"#{item}")
    if gruppe:
        item = a.neu(f"COMPOUND_REPRESENTATION_ITEM('modifiers',LIST_REPRESENTATION_ITEM(({','.join(gruppe)})))")
        items.append(f"#{item}")
    name = "envelope requirement" if mods.intersection({"Envelope", "E"}) else ""
    darst = a.neu(f"SHAPE_DIMENSION_REPRESENTATION('{name}',({','.join(items)}),#{a.kontext})")
    a.neu(f"DIMENSIONAL_CHARACTERISTIC_REPRESENTATION(#{dim},#{darst})")
    if p.oben is not None and p.unten is not None and not p.grenzmass:
        tv = a.neu(f"TOLERANCE_VALUE(#{a.mass(p.unten, winkel)},#{a.mass(p.oben, winkel)})")
        a.neu(f"PLUS_MINUS_TOLERANCE(#{tv},#{dim})")
    elif p.passung:
        felder = _passungsfelder(p.passung)
        if felder is None:
            return tr("Toleranzklasse nicht schreibbar")
        lf = a.neu(f"LIMITS_AND_FITS({felder},'')")
        a.neu(f"PLUS_MINUS_TOLERANCE(#{lf},#{dim})")
    a.semantik = dim
    return None


def _grafiken(eigene, modell, grafik) -> dict:
    """PMI-Id -> Grafik der eigenen PMI: die der Ansicht (grafik), sonst neu erzeugt wie in der Ansicht."""
    out = {}
    for g in (grafik or {}).values():
        for i in g.pmi_ids:
            out.setdefault(i, g)
    offen = [p for p in eigene if p.step_id not in out and not p.callout]
    if offen and getattr(modell, "form", None) is not None:
        from .pmi_erzeugen import ergaenze
        try:
            for g in ergaenze(offen, {}, modell).values():
                for i in g.pmi_ids:
                    out.setdefault(i, g)
        except Exception:  # noqa: BLE001 - ohne Grafik bleibt die Semantik geschrieben
            pass
    return out


def _schreibe_verbund(a, paar):
    oben, unten = paar
    if oben.flaechen != unten.flaechen or any(set(p.projektionsflaechen) & p.flaechen for p in paar):
        return tr("Die Zeilen des Verbundrahmens brauchen gemeinsame Zielflächen."), []
    fehler = a.waehle(oben.flaechen)
    if fehler:
        return fehler, []
    aspekt = a.aspekt(oben.flaechen)
    if aspekt is None:
        return tr("Flächen ohne Entsprechung in der Datei"), []
    ids = []
    for zeile in paar:
        grund = _schreibe_toleranz(a, zeile, aspekt)
        if grund:
            return grund, []
        ids.append(a.semantik)
    a.neu(f"GEOMETRIC_TOLERANCE_RELATIONSHIP('composite','',#{ids[0]},#{ids[1]})")
    return None, ids


def _haenge_an(text: str, datei, modell, pmi, bericht: Bericht, grafik=None, schrift=None) -> str:
    from .pmi_darstellung import Praesentation
    from .pmi_reparieren import verbundpaare
    from .praesentation import eigenstaendige_annotation
    eigene = [p for p in pmi if p.quelle == "eigen" and p.art in ("mass", "toleranz", "bezug")]
    if not eigene:
        return text
    a = _Anhang(datei, modell)
    darst, grafiken = Praesentation(a, modell, schrift), _grafiken(eigene, modell, grafik)
    belegt = _semantische_callouts(datei) if any(p.callout for p in eigene) else set()
    paare = verbundpaare(eigene)
    unvollstaendig = {p.callout for p in eigene if p.folgetoleranzen and p.callout not in paare}
    # Bezuege zuerst: Toleranzen verweisen auf sie
    for p in sorted(eigene, key=lambda p: p.art != "bezug"):
        paar = paare.get(p.callout)
        if paar and p is paar[1]:
            continue
        gruppe = paar or (p,)
        if p.callout in unvollstaendig:
            bericht.uebersprungen.append((p.nummer, "neu", tr("Verknüpfung im Verbundrahmen unvollständig")))
            continue
        if p.callout:
            grafikziel = datei.entities.get(p.callout)
            if grafikziel is None or not (grafikziel.is_a("DRAUGHTING_CALLOUT") or
                                          eigenstaendige_annotation(datei, grafikziel)):
                bericht.uebersprungen.extend((q.nummer, "neu", tr("Originalgrafik in der STEP-Datei fehlt")) for q in gruppe)
                continue
            if p.callout in belegt:
                bericht.uebersprungen.extend((q.nummer, "neu", tr("Originalgrafik bereits mit Semantik verknüpft")) for q in gruppe)
                continue
        vorher = (len(a.zeilen), a.naechste)
        schreiber = {"bezug": _schreibe_bezug, "toleranz": _schreibe_toleranz, "mass": _schreibe_mass}[p.art]
        if paar:
            grund, semantiken = _schreibe_verbund(a, paar)
        else:
            grund = schreiber(a, p)
            semantiken = [a.semantik]
        if grund:
            del a.zeilen[vorher[0]:]  # halb geschriebene Entitaeten verwerfen
            a.naechste = vorher[1]
            bericht.uebersprungen.extend((q.nummer, "neu", grund) for q in gruppe)
            continue
        bericht.neu.extend(q.nummer for q in gruppe)
        if p.callout:
            for eid in semantiken:
                darst.verknuepfe(p.callout, eid)
            belegt.add(p.callout)
            bericht.repariert.extend(q.nummer for q in gruppe)
        elif darst.callout(grafiken.get(p.step_id), a.semantik, p.flaechen):
            bericht.dargestellt.append(p.nummer)
    darst.abschliessen()
    if not a.zeilen:
        return text
    ende = text.rfind("ENDSEC;", 0, text.find("END-ISO-10303-21"))
    return text[:ende] + "\n".join(a.zeilen) + "\n" + text[ende:]


def _semantische_callouts(datei) -> set[int]:
    """Bereits an Mass, Toleranz oder Bezug gebundene Grafik. Ein reiner Formaspekt erlaubt die Reparatur."""
    from .pmi_step import MASS_TYPEN, TOL_ARTEN
    typen = {"DATUM", "DATUM_FEATURE", "DATUM_TARGET", "PLACED_DATUM_TARGET_FEATURE",
             "GEOMETRIC_TOLERANCE", *MASS_TYPEN, *TOL_ARTEN}
    out = set()
    for link in datei.of_types_by_id(("DRAUGHTING_MODEL_ITEM_ASSOCIATION", p21.DMIA_PH)):
        args = link.args()
        if len(args) >= 5 and isinstance(args[2], Ref) and isinstance(args[4], Ref):
            ziel = datei.get(args[2])
            if ziel is not None and typen.intersection(ziel.parts):
                out.add(args[4].id)
    return out


def _passung_id(datei, p) -> int | None:
    for rid in datei.referrers().get(p.step_id, []):
        r = datei.entities[rid]
        if r.is_a("PLUS_MINUS_TOLERANCE"):
            b = r.args("PLUS_MINUS_TOLERANCE")[0]
            if isinstance(b, Ref) and datei.entities.get(b.id) is not None and datei.entities[b.id].is_a("LIMITS_AND_FITS"):
                return b.id
    return None


def _schreibe_passung(text: str, datei, p) -> str | None:
    """Toleranzklasse in einer vorhandenen LIMITS_AND_FITS ersetzen; None, wenn die Datei keine hat."""
    eid = _passung_id(datei, p)
    felder = _passungsfelder(p.passung or "")
    if eid is None or felder is None:
        return None
    a, b = _anweisung(text, eid)
    # Quellenangabe im vierten Feld mitsamt originaler STEP-Zeichencodierung erhalten.
    feld = r"(?:'(?:[^']|'')*'|\$)\s*,\s*"
    neu, anzahl = re.subn(rf"(LIMITS_AND_FITS\s*\(\s*)(?:{feld}){{3}}",
                          lambda m: m[1]+felder+",", text[a:b], count=1, flags=re.I)
    return text[:a]+neu+text[b:] if anzahl else None


def _schreibe_material(text: str, datei, p) -> str | None:
    """Materialbedingung einer Toleranz setzen: in GEOMETRIC_TOLERANCE_WITH_MODIFIERS ersetzen oder die einfache
    Entitaet in die komplexe Form mit Modifikatoren umschreiben; None, wenn das nicht geht."""
    import re as _re
    e = datei.entities.get(p.step_id)
    if e is None:
        return None
    a, b = _anweisung(text, p.step_id)
    stueck = text[a:b]
    neu_enum = MATERIAL_ENUM.get(p.material)
    if e.is_a("MODIFIED_GEOMETRIC_TOLERANCE") and not e.is_a("GEOMETRIC_TOLERANCE_WITH_MODIFIERS"):
        enum = {"M": "MAXIMUM_MATERIAL_CONDITION", "L": "LEAST_MATERIAL_CONDITION", "": "REGARDLESS_OF_FEATURE_SIZE"}
        if p.material not in enum:
            return None
        neu, n = _re.subn(r"(MODIFIED_GEOMETRIC_TOLERANCE\s*\(\s*)\.[A-Z_]+\.",
                          lambda m: m[1] + "." + enum[p.material] + ".", stueck, count=1)
        return text[:a] + neu + text[b:] if n else None
    if e.is_a("GEOMETRIC_TOLERANCE_WITH_MODIFIERS"):
        def ersetze(m):
            enums = [x for x in _re.findall(r"\.([A-Z_]+)\.", m.group(2)) if x not in MATERIAL_ENUM.values()]
            enums += [neu_enum] if neu_enum else []
            return m.group(1) + "(" + ",".join(f".{x}." for x in enums) + ")"
        neu = _re.sub(r"(GEOMETRIC_TOLERANCE_WITH_MODIFIERS\s*\(\s*)\(([^)]*)\)", ersetze, stueck, count=1)
        return text[:a] + neu + text[b:]
    if not neu_enum:
        return text  # nichts zu entfernen
    if len(e.parts) == 1:  # einfache Form: FOO_TOLERANCE('n','',#betrag,#aspekt[,(#system)])
        typ = next(iter(e.parts))
        m = _re.match(rf"#{p.step_id}\s*=\s*{typ}\s*\((.*)\)\s*;$", stueck, _re.S)
        if m is None:
            return None
        teile = _argumente(m.group(1))
        if len(teile) < 4:
            return None
        kompl = {"GEOMETRIC_TOLERANCE": "(" + ",".join(teile[:4]) + ")", typ: "()",
                 "GEOMETRIC_TOLERANCE_WITH_MODIFIERS": f"((.{neu_enum}.))"}
        if len(teile) > 4:
            kompl["GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE"] = "(" + teile[4] + ")"
        return text[:a] + f"#{p.step_id}=( " + " ".join(f"{k}{kompl[k]}" for k in sorted(kompl)) + " );" + text[b:]
    # komplex ohne Modifikatoren: Teil einfuegen (alphabetisch)
    m = _re.match(rf"(#{p.step_id}\s*=\s*\()(.*)(\)\s*;)$", stueck, _re.S)
    if m is None:
        return None
    teile = _re.findall(r"([A-Z_0-9]+)\s*(\((?:[^()']|'[^']*'|\((?:[^()']|'[^']*'|\([^()]*\))*\))*\))", m.group(2))
    if not teile:
        return None
    teile.append(("GEOMETRIC_TOLERANCE_WITH_MODIFIERS", f"((.{neu_enum}.))"))
    return text[:a] + m.group(1) + " " + " ".join(f"{k}{v}" for k, v in sorted(teile)) + " " + m.group(3) + text[b:]


def _argumente(inhalt: str) -> list[str]:
    """Argumente einer P21-Liste auf oberster Ebene (Klammern und Texte beachtet)."""
    out, tiefe, start, in_str = [], 0, 0, False
    for i, c in enumerate(inhalt):
        if c == "'":
            in_str = not in_str
        elif not in_str and c == "(":
            tiefe += 1
        elif not in_str and c == ")":
            tiefe -= 1
        elif not in_str and c == "," and tiefe == 0:
            out.append(inhalt[start:i].strip())
            start = i + 1
    out.append(inhalt[start:].strip())
    return out


def schreibe(quelle: str, ziel: str, pmi: list, modell=None, grafik: dict | None = None,
             schrift: str | None = None) -> Bericht:
    """Kopie von 'quelle' mit den bearbeiteten Werten der PMI nach 'ziel'; mit modell auch die eigenen PMI samt
    Darstellung (grafik: Grafiken der Ansicht, damit die Datei zeigt, was man sieht; sonst neu erzeugt)."""
    from .laden import ENDUNGEN_STEPZ, _entpacke_stepz
    if str(quelle).lower().endswith(ENDUNGEN_STEPZ):
        import tempfile
        with tempfile.TemporaryDirectory(prefix="3dgmax_stepz_") as ordner:
            return schreibe(_entpacke_stepz(quelle, ordner), ziel, pmi, modell, grafik, schrift)
    with open(quelle, "rb") as f:
        roh = f.read()
    try:
        text, kodierung = roh.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        text, kodierung = roh.decode("latin-1"), "latin-1"
    datei = p21.lese_text(text)
    bericht = Bericht()
    if modell is not None and any(p.quelle == "eigen" and p.callout for p in pmi) and not datei.schema.upper().startswith("AP242"):
        from .step_ap242 import aus_ap203
        text = aus_ap203(text, datei)
        datei = p21.lese_text(text)
        bericht.ap242_kopie = True
    verweise = datei.referrers()
    for p in pmi:
        if not p.bearbeitet or not p.original or p.quelle == "eigen":
            continue
        felder = ziele(datei, p)
        for feld, alt in p.original.items():
            neu = getattr(p, feld, None)
            if neu == alt:
                continue
            if feld in ("material", "wert") and (
                    "Maximum_Tolerance" in p.modifikatoren or p.maximum_toleranz is not None and
                    (p.material not in MATERIAL_ENUM or p.wert is None or p.wert >= p.maximum_toleranz)):
                bericht.uebersprungen.append((p.nummer, feld, tr("Höchstwert der geometrischen Toleranz nicht gültig")))
                continue
            if feld in ("passung", "material"):
                neu_text = (_schreibe_passung if feld == "passung" else _schreibe_material)(text, datei, p)
                if neu_text is None:
                    bericht.uebersprungen.append((p.nummer, feld, tr("nicht schreibbar")))
                else:
                    text = neu_text
                    bericht.geschrieben.append((p.nummer, feld))
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
        text = _haenge_an(text, datei, modell, pmi, bericht, grafik, schrift)
    with open(ziel, "w", encoding=kodierung, newline="") as f:
        f.write(text)
    return bericht
