"""Modell hinzufuegen: weitere Dateien in das geladene Modell aufnehmen (ohne Qt).

Das Ergebnis verhaelt sich wie ein Modell aus einer Datei:
- Form: Compound aus bisheriger Form und der verschobenen neuen Form;
- Flaechen: neue Flaechen hinten angehaengt (Flaechenindex der neuen Datei + Versatz = Anzahl bisheriger Flaechen),
  Index ueber TShape wie bisher, die Lage der Flaeche enthaelt die Verschiebung;
- Struktur: neuer oberster Knoten mit dem Dateinamen, darunter die Teile der Datei mit eindeutigen Knotennummern;
- PMI, Grafik und Ansichten der neuen Datei bleiben erhalten: Flaechenindizes, STEP-#IDs (Versatz ID_VERSATZ je Datei,
  damit sie sich nicht mit der ersten Datei ueberschneiden) und laufende Nummern werden umgerechnet, Grafik und
  Ansichten mit verschoben.
Die bisherigen Objekte (Flaechen, Knoten, PMI) bleiben unveraendert, damit Verbindungen, Messungen und bearbeitete
PMI gueltig bleiben. Bezugsbuchstaben werden nicht umbenannt: gleiche Buchstaben zweier Dateien sind
nicht unterscheidbar (Bezugssysteme nur innerhalb einer Datei auswerten).
"""

from __future__ import annotations

import copy
import dataclasses
import os
from dataclasses import dataclass

import numpy as np

ID_VERSATZ = 100_000_000  # STEP-#IDs der k-ten hinzugefuegten Datei: + k * ID_VERSATZ


@dataclass
class Zusatz:
    pfad: str
    versatz: tuple  # Verschiebung (mm) gegenueber der Lage in der Datei
    knoten: int  # Nummer des obersten Knotens der Datei im Baum
    erste_flaeche: int  # Flaechenindex der ersten Flaeche dieser Datei
    flaechen: int  # Anzahl Flaechen
    id_versatz: int
    modell: object = None  # eigenes Modell der Datei (haelt das Dokument)


def zusaetze(erg) -> list[Zusatz]:
    return list(getattr(erg, "zusaetze", None) or [])


def _box(form):
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    b = Bnd_Box()
    brepbndlib.Add(form, b)
    return None if b.IsVoid() else np.array(b.Get(), float).reshape(2, 3)


def platz_daneben(form_bisher, form_neu) -> tuple:
    """Verschiebung, die die neue Form ohne Ueberlappung rechts (+X) neben die bisherige legt: Abstand 10 % der
    groesseren Ausdehnung (mind. 5 mm), in Y und Z mittig."""
    a, b = _box(form_bisher), _box(form_neu)
    if a is None or b is None:
        return (0.0, 0.0, 0.0)
    abstand = max(5.0, 0.1 * float(max((a[1] - a[0]).max(), (b[1] - b[0]).max())))
    mitte_a, mitte_b = (a[0] + a[1]) / 2, (b[0] + b[1]) / 2
    v = mitte_a - mitte_b
    v[0] = a[1][0] + abstand - b[0][0]
    return tuple(float(x) for x in v)


def _lage(versatz):
    from OCC.Core.gp import gp_Trsf, gp_Vec
    from OCC.Core.TopLoc import TopLoc_Location
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(*map(float, versatz)))
    return TopLoc_Location(t)


def _compound(formen):
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_Compound
    bb = BRep_Builder()
    comp = TopoDS_Compound()
    bb.MakeCompound(comp)
    for f in formen:
        bb.Add(comp, f)
    return comp


def _knoten_umrechnen(k, versatz_nr: int, lage):
    """Knoten (rekursiv) mit verschobener Form und Nummer + versatz_nr (Kopie)."""
    neu = dataclasses.replace(k, form=k.form.Moved(lage), nummer=k.nummer + versatz_nr,
                              kinder=[_knoten_umrechnen(c, versatz_nr, lage) for c in k.kinder])
    return neu


def _id(eid: int, versatz: int) -> int:
    return eid + versatz if eid else eid


def _grafik_umrechnen(g, id_versatz: int, v: np.ndarray):
    g = copy.deepcopy(g)
    g.callout_id = g.callout_id + id_versatz if g.callout_id > 0 else g.callout_id - id_versatz
    g.pmi_ids = {_id(i, id_versatz) for i in g.pmi_ids}
    g.linien = [np.asarray(x, float) + v for x in g.linien]
    g.dreiecke = [(np.asarray(p, float) + v, d) for p, d in g.dreiecke]
    g.hinweislinien = [np.asarray(x, float) + v for x in g.hinweislinien]
    for p in g.platzhalter:
        p.ursprung = np.asarray(p.ursprung, float) + v
    if g.ebene is not None:
        g.ebene = (np.asarray(g.ebene[0], float) + v, *g.ebene[1:])
    return g


def _pmi_umrechnen(pmi: list, flaechen_versatz: int, id_versatz: int, nummer_versatz: int):
    for p in pmi:
        p.flaechen = {i + flaechen_versatz for i in p.flaechen}
        p.step_id = _id(p.step_id, id_versatz)
        p.nummer += nummer_versatz
        if getattr(p, "callout", 0):  # Verweis auf die Grafik der Datei (falls vorhanden)
            p.callout = _id(p.callout, id_versatz)
    return pmi


def _ansichten_umrechnen(ansichten: list, name: str, id_versatz: int, nummer_versatz: int, v: np.ndarray):
    out = []
    for a in ansichten:
        a = copy.deepcopy(a)
        a.name = f"{name}: {a.name}"
        a.step_id = _id(a.step_id, id_versatz)
        a.ort = tuple(float(x) for x in np.asarray(a.ort, float) + v)
        a.pmi_ids = {_id(i, id_versatz) for i in a.pmi_ids}
        a.pmi_nummern = [n + nummer_versatz for n in a.pmi_nummern]
        out.append(a)
    return out


def fuege_hinzu(erg, neu, versatz=None):
    """Neues Ergebnis aus erg (bisheriges Modell, auch schon zusammengefuegt) und neu (frisch geladene Datei, wird
    dabei veraendert). versatz None: neben das bisherige Modell legen. Liefert eine Kopie von erg mit
    zusammengefuegtem Modell, Baum, PMI, Grafik, Farben, Ansichten und der Liste zusaetze."""
    from .baum import Knoten
    if versatz is None:
        versatz = platz_daneben(erg.modell.form, neu.modell.form)
    v = np.asarray(versatz, float)
    lage = _lage(v)
    alt = zusaetze(erg)
    id_versatz = (len(alt) + 1) * ID_VERSATZ
    n_flaechen = len(erg.modell.flaechen)
    nummer_versatz = max((k.nummer for k in erg.baum.alle()), default=0) + 1
    pmi_versatz = max((p.nummer for p in erg.pmi), default=0)
    name = os.path.basename(neu.pfad)

    modell = copy.copy(erg.modell)
    neue_flaechen = [f.Moved(lage) for f in neu.modell.flaechen]
    modell.flaechen = list(erg.modell.flaechen) + neue_flaechen
    modell.form = _compound([erg.modell.form, neu.modell.form.Moved(lage)])
    modell._baue_index()
    if len(modell._index) != len(modell.flaechen):  # gleiche TShape in beiden Dateien: nicht unterscheidbar
        raise ValueError(f"Flaechen doppelt: {name}")
    modell.netz_kanten = dict(erg.modell.netz_kanten)
    for i, linien in neu.modell.netz_kanten.items():
        modell.netz_kanten[i + n_flaechen] = [np.asarray(x, float) + v for x in linien]
    modell.ladezeit = erg.modell.ladezeit + neu.modell.ladezeit

    oben = Knoten(name, neu.modell.form.Moved(lage), baugruppe=True, nummer=nummer_versatz)
    oben.kinder = [_knoten_umrechnen(k, nummer_versatz, lage) for k in neu.baum.kinder]
    wurzel = dataclasses.replace(erg.baum, form=modell.form, kinder=list(erg.baum.kinder) + [oben])

    pmi = list(erg.pmi) + _pmi_umrechnen(list(neu.pmi), n_flaechen, id_versatz, pmi_versatz)
    grafik = dict(erg.grafik)
    for g in neu.grafik.values():
        g = _grafik_umrechnen(g, id_versatz, v)
        grafik[g.callout_id] = g
    farben = dict(erg.farben)
    farben.update({i + n_flaechen: c for i, c in neu.farben.items()})
    ansichten = list(erg.ansichten) + _ansichten_umrechnen(neu.ansichten, name, id_versatz, pmi_versatz, v)
    z = Zusatz(neu.pfad, tuple(float(x) for x in v), oben.nummer, n_flaechen, len(neue_flaechen), id_versatz,
               neu.modell)
    return dataclasses.replace(erg, modell=modell, baum=wurzel, pmi=pmi, grafik=grafik, farben=farben,
                               ansichten=ansichten, zusaetze=alt + [z])


def zusatz_von(erg, knoten_nummer: int) -> Zusatz | None:
    """Hinzugefuegte Datei, zu der ein Knoten gehoert (None: erste Datei)."""
    for z in zusaetze(erg):
        oben = next((k for k in erg.baum.kinder if k.nummer == z.knoten), None)
        if oben is not None and any(k.nummer == knoten_nummer for k in oben.alle()):
            return z
    return None


def pmi_der_ersten_datei(erg) -> list:
    """PMI ohne die der hinzugefuegten Dateien (z. B. zum Schreiben der ersten STEP-Datei)."""
    return [p for p in erg.pmi if p.step_id < ID_VERSATZ and not any(
        z.erste_flaeche <= i < z.erste_flaeche + z.flaechen for z in zusaetze(erg) for i in p.flaechen)]
