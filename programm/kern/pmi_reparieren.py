"""Nur grafisch vorhandene PMI semantisch machen ("Reparieren", PLAN §8.18/§8.28).

Eine Grafik ohne Semantik (Callout ohne Verknuepfung, in der Liste als Hinweis oder "aus der Grafik abgeleitet")
wird nach Pruefung durch den Anwender zu einer eigenen PMI mit Art, Werten und Flaechen. Sie behaelt die Grafik der
Datei (Pmi.callout): beim Schreiben (step_schreiben) wird nur die Semantik angehaengt und mit dem vorhandenen Callout
verknuepft - die Datei zeigt danach dieselbe Darstellung, jetzt mit Semantik.

Vorschlag:
- Art aus den abgeleiteten Feldern (Text der Grafik) oder aus dem Namen des Callouts (CATIA/NX: "Flatness.1",
  "Linear Size.3", "Simple Datum.2", "Position surfacic profile.1" ...); Werte nur, wo die Grafik Text liefert
  oder die Vektor-OCR sie erkennt.
- Flaechen: Enden der Linien und Ecken der Dreiecke (Pfeilspitzen, Bezugsdreieck), die auf einer Flaeche liegen.
"""

from __future__ import annotations

from copy import deepcopy
import re

import numpy as np

from .pmi import BEZUG, HINWEIS, MASS, TOLERANZ, Pmi
from .pmi_ableiten import LINEARMASS, grenzlesart

# Name des Callouts -> (Art, Typ); die erste passende Regel gilt (Reihenfolge beachten: "surfacic profile" vor
# "Position", "Total Runout" vor "Runout")
NAMEN = [
    (r"surfacic profile|surface profile|profile tolerance of any surface|profile of (a )?surface", TOLERANZ, "ProfileOfSurface"),
    (r"line profile|profile of (a )?line", TOLERANZ, "ProfileOfLine"),
    (r"total runout", TOLERANZ, "TotalRunout"),
    (r"runout", TOLERANZ, "CircularRunout"),
    (r"flatness", TOLERANZ, "Flatness"), (r"straightness", TOLERANZ, "Straightness"),
    (r"circularity|roundness", TOLERANZ, "CircularityOrRoundness"), (r"cylindricity", TOLERANZ, "Cylindricity"),
    (r"perpendicularity", TOLERANZ, "Perpendicularity"), (r"parallelism", TOLERANZ, "Parallelism"),
    (r"angularity", TOLERANZ, "Angularity"), (r"position", TOLERANZ, "Position"),
    (r"concentricity", TOLERANZ, "Concentricity"), (r"coaxiality", TOLERANZ, "Coaxiality"),
    (r"symmetry", TOLERANZ, "Symmetry"),
    (r"fcf|feature control frame", TOLERANZ, ""),
    (r"datum target", BEZUG, "DatumTarget"), (r"datum", BEZUG, "Datum"),
    (r"angular size", MASS, "Size_Angular"), (r"angular|angle", MASS, "Location_Angular"),
    (r"diameter", MASS, "Size_Diameter"), (r"radius", MASS, "Size_Radius"),
    (r"radial dimension", MASS, ""),
    (r"linear size|size", MASS, ""),  # Groesse: Art aus den Flaechen
    (r"distance|linear dimension|dimension", MASS, "Location_LinearDistance"),
]
FELDER = ("nennwert", "oben", "unten", "grenzmass", "passung", "wert", "zone", "zonen_wert", "material",
          "modifikatoren", "bezuege", "maximum_toleranz", "einheitslaenge", "einheitsbreite", "projektionsversatz", "projektionsflaechen")


def reparierbar(p, grafik: dict) -> bool:
    """Nur grafische PMI aus der Datei mit eigener Grafik (Callout)."""
    return (not p.semantisch and p.quelle != "eigen" and p.step_id != 0 and p.step_id in grafik
            and not grafik[p.step_id].erzeugt)


def aus_name(name: str, *, druckschrift=False) -> tuple[str, str] | None:
    """(Art, Typ) aus dem Namen eines Callouts; None, wenn nichts passt (z. B. "Text.1")."""
    # CAD-Systeme nennen auch Durchmesser und Radien schlicht "linear dimension".
    if druckschrift and re.fullmatch(r"(?:linear\s+)?dimension(?:\.\d+)?", (name or "").strip(), re.I):
        return MASS, ""
    for muster, art, typ in NAMEN:
        if re.search(rf"\b(?:{muster})\b", name or "", re.I):
            return art, typ
    return None


def _form(flaechen, modell) -> str:
    """Groessenmass nach den Flaechen: Zylinder -> Durchmesser, zwei Ebenen -> Dicke bzw. Abstand."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    fl = [modell.flaechen[i] for i in sorted(flaechen) if 0 <= i < len(modell.flaechen)]
    arten = [BRepAdaptor_Surface(f).GetType() for f in fl if BRep_Tool.Surface(f) is not None]
    if len(fl) == 1 and arten == [GeomAbs_Cylinder]:
        return "Size_Diameter"
    if arten == [GeomAbs_Plane, GeomAbs_Plane] and geometrie_nennmass("Size_Thickness", flaechen, modell) is not None:
        return "Size_Thickness"
    return ""


def geometrie_nennmass(typ, flaechen, modell):
    """Geometrischer Messwert in mm fuer eine eindeutige Auswahl (ohne Annahme zur Toleranz)."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder, GeomAbs_Sphere
    from .baugruppe_mass import ebene
    fl = [modell.flaechen[i] for i in sorted(flaechen) if 0 <= i < len(modell.flaechen)]
    if any(BRep_Tool.Surface(f) is None for f in fl):
        return None
    if len(fl) == 2 and typ in ("Size_Thickness", "Location_LinearDistance"):
        a, b = (ebene(f) for f in fl)
        if a is not None and b is not None and np.linalg.norm(np.cross(a[1], b[1])) < 1e-8:
            return float(abs((a[0] - b[0]) @ a[1]))
    if len(fl) == 1:
        sf = BRepAdaptor_Surface(fl[0])
        if sf.GetType() == GeomAbs_Cylinder and typ in ("Size_Radius", "Size_Diameter"):
            return sf.Cylinder().Radius() * (2 if typ == "Size_Diameter" else 1)
        if sf.GetType() == GeomAbs_Sphere and typ in ("Size_SphericalRadius", "Size_SphericalDiameter"):
            return sf.Sphere().Radius() * (2 if typ == "Size_SphericalDiameter" else 1)
    return None


def schriftvorschlag(g, bekannt, modell=None, flaechen=()):
    """Lesbare Angabe aus der Schrift, abgestimmt mit der bekannten Art des Callouts."""
    from .pmi import TOL_SYMBOL
    from .pmi_ableiten import aus_text
    from .pmi_strichschrift import lies_schrift

    if g.erzeugt:
        return "", {}
    art, typ = bekannt or (None, "")
    abstand = None
    linear = not bekannt or (art == MASS and typ in ("", "Size_Thickness", "Location_LinearDistance"))
    if linear and modell and len(flaechen) == 2:
        abstand = geometrie_nennmass("Location_LinearDistance", flaechen, modell)
    linearmass = abstand is not None and (not bekannt or g.ebene is None)
    text = lies_schrift(g, linearmass=linearmass)
    felder = aus_text([text], g.textfaktor) if text else None
    if not felder and text and (grenzen := grenzlesart(text, g.textfaktor, bekannt)):
        return text, {"art": MASS, "typ": grenzen["typ"]}
    if felder and felder["art"] == MASS and art == TOLERANZ and typ in TOL_SYMBOL:
        felder = aus_text([TOL_SYMBOL[typ], text], g.textfaktor)
    if not felder or (art and felder["art"] != art) or (not bekannt and text.isalpha()):
        return "", {}
    if felder["art"] == TOLERANZ and ("wert" not in felder or (typ and typ != felder["typ"])):
        return "", {}
    if felder["typ"] == "Location_LinearDistance":
        linear_gelesen = linearmass and LINEARMASS.fullmatch(text)
        if not bekannt and ("Hilfsmass" in felder.get("modifikatoren", ()) or linear_gelesen):
            # Eine isolierte Zahl kann eine Positionsnummer sein. Nur belegte Massflaechen verwenden.
            from .plausibilitaet import GEOMETRIE_TOLERANZ
            if abstand is None or abs(abstand - felder["nennwert"]) > GEOMETRIE_TOLERANZ:
                return text, {}
        elif art != MASS or typ in ("Size_Angular", "Location_Angular"):
            return "", {}
        felder["typ"] = typ or felder["typ"]
    return text, felder


def _druckschrift(g, bekannt, modell, flaechen):
    """Dateitext und Vektorschrift des Callouts fuer die Pruefung zusammenfuehren."""
    from .pmi_validierungstext import validierungsvorschlag
    from .zeichnungsabgleich import musteranzahl
    dateitexte, gelesen, ergaenzung = validierungsvorschlag(getattr(modell, "datei", None), g, bekannt)
    if len(dateitexte) > 1:
        return dateitexte, "", gelesen, ergaenzung, []
    dateitext = dateitexte[0] if dateitexte else ""
    grenzen = grenzlesart(dateitext, g.textfaktor, bekannt)
    if dateitext and not grenzen and gelesen.get("art") != MASS:
        return dateitexte, "", gelesen, ergaenzung, []

    wort, grafikwerte = schriftvorschlag(g, bekannt, modell, flaechen)
    grafikgrenzen = grenzlesart(wort, g.textfaktor, bekannt)
    original, dateiwerte = grafikgrenzen or grafikwerte, grenzen or gelesen
    wahl = []
    if not dateitext:
        gelesen, grenzen = grafikwerte, grafikgrenzen
    elif "nennwert" in original and (original != dateiwerte or musteranzahl(wort) != musteranzahl(dateitext)):
        wahl = [("grafik", wort, original), ("datei", dateitext, dateiwerte)]
        gelesen = {"art": MASS, "typ": original["typ"] if original["typ"] == dateiwerte["typ"] else ""}
    if grenzen and not wahl:
        wahl = [("grenzen", dateitext or wort, grenzen)]
        gelesen = {"art": MASS, "typ": grenzen["typ"]}
    return dateitexte, "" if dateitext else wort, gelesen, ergaenzung, wahl


def _verknuepfte_flaechen(p, g, modell):
    flaechen = {i for i in p.flaechen if 0 <= i < len(modell.flaechen)}
    if not flaechen and g is not None and getattr(modell, "datei", None) is not None:
        from .pmi_lesen import flaechen_von_aspekt
        for eid in g.pmi_ids:
            aspekt = modell.datei.get(eid)
            if aspekt is not None and (aspekt.is_a("SHAPE_ASPECT") or aspekt.is_a("DATUM_FEATURE")):
                flaechen.update(flaechen_von_aspekt(modell.datei, modell, eid))
    return flaechen


def vorschlag(p, g, modell) -> Pmi:
    """Eigene PMI als Startwert fuer die Pruefung: Art, Werte (soweit lesbar), Flaechen, Verweis auf den Callout."""
    name = p.name or (g.name if g else "")
    bekannt = (p.art, p.typ) if p.art != HINWEIS else aus_name(name)
    art, typ = bekannt or (TOLERANZ, "")
    texte = [ph.text for ph in g.platzhalter if ph.text] if g is not None else []
    flaechen = _verknuepfte_flaechen(p, g, modell)
    dateitexte, ocr, gelesen, ergaenzung, masswahl = (), "", {}, "", []
    if g and not texte and not g.erzeugt and not p.semantisch:
        schriftart = aus_name(name, druckschrift=True) if p.art == HINWEIS else bekannt
        dateitexte, ocr, gelesen, ergaenzung, masswahl = _druckschrift(g, schriftart, modell, flaechen)
        if gelesen:
            art = gelesen["art"]
            typ = gelesen["typ"] or (typ if schriftart != bekannt and not masswahl else "")
    neu = Pmi(art, typ=typ, norm=p.norm, name=p.name if art == BEZUG and re.fullmatch(r"[A-Z]{1,2}", p.name or "") else "")
    for k in ("name", *FELDER):
        if k in gelesen:
            setattr(neu, k, gelesen[k])
    neu.masswahl = masswahl
    neu.ocr_text = ocr
    neu.validierungstexte = dateitexte
    neu.rahmensymbolquelle = ergaenzung
    neu.merkmalsname = g.name if ergaenzung == "name" else ""
    for k in FELDER:
        if not masswahl and k not in gelesen and p.art == art and getattr(p, k, None) not in (None, "", []):
            setattr(neu, k, deepcopy(getattr(p, k)))
    neu.flaechen = flaechen
    if not neu.flaechen and g is not None:
        neu.flaechen = flaechen_vorschlag(g, modell)
    if art == MASS and not typ and not masswahl and re.search(r"\bsize\b", g.name if g else p.name, re.I):
        neu.typ = _form(neu.flaechen, modell)
    neu.nennwert_aus_geometrie = False
    if art == MASS and neu.nennwert is None and not masswahl:
        neu.nennwert = geometrie_nennmass(neu.typ, neu.flaechen, modell)
        neu.nennwert_aus_geometrie = neu.nennwert is not None
    neu.callout, neu.nur_grafik_text = p.step_id, "\n".join(texte or dateitexte) or ocr or p.nur_grafik_text or p.name
    return neu


def _punkte(g) -> np.ndarray:
    """Kandidaten fuer Beruehrpunkte: Enden der Linienzuege, Ecken gefuellter Dreiecke (Pfeile, Bezugsdreieck)."""
    enden = [q for linie in g.linien if len(linie) > 1 for q in (linie[0], linie[-1])]
    teile = [np.asarray(enden, dtype=float).reshape(-1, 3)]
    teile.extend(p for p, _ in g.dreiecke if len(p))
    return np.concatenate(teile)


class _Flaechenindex:
    """Modellgrenzen und Flaechenquader fuer alle Callouts desselben geladenen Modells."""
    def __init__(self, modell):
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        self.form, self.flaechen = modell.form, modell.flaechen
        self.boxen = np.full((len(self.flaechen), 6), np.nan)
        self.netze = {}
        for i, f in enumerate(self.flaechen):
            b = Bnd_Box()
            brepbndlib.Add(f, b)
            if not b.IsVoid():
                self.boxen[i] = b.Get()
        box = Bnd_Box()
        brepbndlib.Add(self.form, box)
        self.grenzen = np.array(box.Get()) if not box.IsVoid() else None


def flaechen_vorschlag(g, modell, max_punkte: int = 400) -> set[int]:
    """Nur eindeutige Flaechentreffer bei Pfeilspitzen oder Linienenden innerhalb der Modellgrenzen."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
    from OCC.Core.gp import gp_Pnt
    from .ausrichten import _punkt_dreieck, tesselliere
    pts = _punkte(g)
    if not len(pts) or not modell.flaechen:
        return set()
    index = getattr(modell, "_reparatur_index", None)
    if (index is None or index.form is not modell.form or index.flaechen is not modell.flaechen or
            len(index.boxen) != len(modell.flaechen)):
        index = modell._reparatur_index = _Flaechenindex(modell)
    if index.grenzen is None:
        return set()
    lo, hi = index.grenzen[:3], index.grenzen[3:]
    tol = 2e-3 * (float(np.linalg.norm(hi - lo)) or 1.0)
    pts = pts[np.all((pts >= lo - tol) & (pts <= hi + tol), axis=1)]
    # Duplikate von Pfeil- oder Schriftpunkten duerfen das Probenbudget nicht verbrauchen.
    _, erste = np.unique(np.round(pts, 7), axis=0, return_index=True)
    pts = pts[np.sort(erste)]
    if len(pts) > max_punkte:
        pts = pts[np.linspace(0, len(pts) - 1, max_punkte, dtype=int)]
    out = set()
    for q in pts:
        nah = np.flatnonzero(np.all((q >= index.boxen[:, :3] - tol) & (q <= index.boxen[:, 3:] + tol), axis=1))
        if not len(nah):
            continue
        v = BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float, q))).Vertex()
        abst = []
        for i in nah:
            f = modell.flaechen[i]
            if BRep_Tool.Surface(f) is None:
                if i not in index.netze:
                    p, tri = tesselliere([f])[0]
                    index.netze[i] = p[tri]
                tri = index.netze[i]
                if len(tri):
                    punkt = _punkt_dreieck(np.broadcast_to(q, tri[:, 0].shape), *tri.transpose(1, 0, 2))
                    abst.append((np.min(np.linalg.norm(punkt - q, axis=1)), int(i)))
            else:
                d = BRepExtrema_DistShapeShape(v, f)
                if d.IsDone() and d.NbSolution() > 0:
                    abst.append((d.Value(), int(i)))
        abst.sort()
        if abst and abst[0][0] < tol and (len(abst) == 1 or abst[1][0] - abst[0][0] > 1e-7):
            out.add(abst[0][1])
    return out


def verbundvorschlaege(v, g, modell, grafiken=None):
    """Zwei getrennt pruefbare Toleranzen mit gemeinsamem Symbol und gemeinsamer Zielflaechenauswahl."""
    from .pmi_ableiten import aus_text
    from .pmi_validierungstext import verbundtext_abgleich
    from .pmi_verbundschrift import lies_verbund_mit_lage
    if v.art != TOLERANZ or v.ocr_text or g.erzeugt or any(p.text for p in g.platzhalter):
        return ()
    gelesen, lage = lies_verbund_mit_lage(g)
    if not gelesen:
        return ()
    zeilen = gelesen[:2]
    zusatz = gelesen[2] if len(gelesen) == 3 else ""
    daten = [aus_text([z], g.textfaktor) for z in zeilen]
    if not all(d and d.get("wert") is not None and (not v.typ or d["typ"] == v.typ) for d in daten):
        return ()
    passt, kurztext = verbundtext_abgleich(getattr(modell, "datei", None), g, zeilen, daten, zusatz)
    hinweis = None
    if passt and not zusatz and grafiken:
        from .pmi_freier_hinweis import freier_hinweis
        hinweis = freier_hinweis(getattr(modell, "datei", None), g, grafiken, lage)
    vorschlaege = []
    for wort, felder in zip(zeilen, daten):
        neu = Pmi(**felder, norm=v.norm, callout=v.callout, flaechen=set(v.flaechen), nur_grafik_text=wort)
        neu.freier_hinweis = hinweis
        neu.beschreibung = zusatz
        neu.ocr_text = wort
        if not passt:
            neu.wert = None
        if kurztext or not passt:
            neu.kurzer_geltungshinweis = kurztext
            neu.validierungstexte = v.validierungstexte
            neu.rahmensymbolquelle = ""
            neu.merkmalsname = ""
        vorschlaege.append(neu)
    return tuple(vorschlaege)


def verbundpaare(pmis):
    """Eigene zweizeilige Rahmen anhand ihrer ausdruecklichen Verknuepfung gruppieren."""
    gruppen = {}
    for p in pmis:
        if p.callout:
            gruppen.setdefault(p.callout, []).append(p)
    paare = {}
    for cid, gruppe in gruppen.items():
        if len(gruppe) == 2:
            for a, b in (gruppe, gruppe[::-1]):
                if (a.art == b.art == TOLERANZ and a.typ == b.typ and a.step_id != b.step_id
                        and a.folgetoleranzen == [b.step_id] and not b.folgetoleranzen):
                    paare[cid] = a, b
    return paare
