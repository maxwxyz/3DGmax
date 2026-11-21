"""Schraubenmasse aus STEP-Hinweisen und Pruefung gegen eine bekannte Schraubnut."""

import math

import numpy as np
import pytest

from programm.kern import plausibilitaet as pl
from tests.test_verzahnung_sonder import _referenz


def test_schraubenmasse_als_tabellenfelder():
    assert pl.verzahnung_angaben("Gangzahl = 2; Axialteilung = 8 mm; Vorschub je Umdrehung = 16 mm") == {
        "gaenge": 2, "axialteilung": 8., "vorschub": 16.}
    assert pl.verzahnung_angaben('axial pitch = .25 in lead = 1 1/2" per turn') == pytest.approx({
        "axialteilung": 6.35, "vorschub": 38.1})
    assert pl.verzahnung_angaben("Schraube: Ganghöhe 0,7 cm, Axialteilung 3500 µm") == {
        "vorschub": 7., "axialteilung": 3.5}
    for text in ("lead = 3 mm", "lead angle = 14°", "axial pitch 7 mm/min", "axial pitch 1/0 in",
                 "axial pitch 7 ± 1 mm", "axial pitch 7 mm/rev", "worm lead 14"):
        assert pl.verzahnung_angaben(text) == {}


def test_steigung_und_axialteilung_mit_eigenem_step_kontext(tmp_path, fenster):
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.Interface import Interface_Static
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from programm.kern.laden import lade_modell
    from programm.kern.pmi_darstellung import Praesentation
    from programm.kern.praesentation import Grafik
    from programm.kern.step_schreiben import _Anhang

    pfad = tmp_path / "Schnecke.stp"
    schreiber = STEPControl_Writer()
    form = _referenz(2, 5.2, 2.1, 28., -2 * math.pi / 14., lagen=80, kerbe=True)
    schema = Interface_Static.CVal("write.step.schema")
    try:
        assert Interface_Static.SetCVal("write.step.schema", "AP242DIS")
        assert schreiber.Transfer(form, STEPControl_AsIs) == IFSelect_RetDone
        assert schreiber.Write(str(pfad)) == IFSelect_RetDone
    finally:
        Interface_Static.SetCVal("write.step.schema", schema)
    modell = lade_modell(str(pfad))
    a = _Anhang(modell.datei, modell)
    fl = {0}
    assert a.waehle(fl) is None
    mm = a.kontext
    wert = a.neu(f"LENGTH_MEASURE_WITH_UNIT(LENGTH_MEASURE(25.4),#{a.einheit_laenge})")
    zoll = a.neu(f"(CONVERSION_BASED_UNIT('inch',#{wert}) LENGTH_UNIT() NAMED_UNIT(*))")
    inch = a.neu(f"(GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNIT_ASSIGNED_CONTEXT((#{zoll})) "
                 "REPRESENTATION_CONTEXT('',''))")
    g = Praesentation(a, modell)
    # Die Einheit des Zeichnungsmodells ist von der Geometrie (mm) unabhaengig.
    for kontext, text in [(mm, "Axialteilung 7"), (inch, "worm lead .55118"),
                          (inch, "Axialteilung 8 mm; Vorschub je Umdrehung 16 mm"),
                          (inch, "worm lead 1/2"), (mm, "axial pitch 7 mm/min"),
                          (mm, "axial pitch 7; lead .55118 in")]:
        a.kontext = kontext
        grafik = Grafik(0, name=text, linien=[np.array([[0., 0., 0.], [1., 1., 0.]])])
        assert g.callout(grafik, a.aspekt(fl), fl)
    # Letzte Beschriftung hat zwei Definitionskontexte: nur die explizite Zollangabe ist auswertbar.
    _, aspekt, callout = g.dmia[-1]
    g.dmia.append((inch, aspekt, callout))
    g.abschliessen()
    text = pfad.read_text()
    pos = text.rindex("ENDSEC;")
    pfad.write_text(text[:pos] + "\n".join(a.zeilen) + "\n" + text[pos:])
    fenster.lade(str(pfad), warten=True)
    befunde = [b for b in fenster.pruefe_pmi().befunde if b.kategorie == "geometrie"]
    assert len(fenster.erg.pmi) == 6
    assert [(b.nummern, b.stufe, b.flaechen) for b in befunde] == [
        ([3], "Warnung", fl), ([3], "Warnung", fl), ([4], "Warnung", fl), ([5], "Hinweis", fl),
        ([6], "Hinweis", fl)]
    assert "8 mm" in befunde[0].text and "16 mm" in befunde[1].text
    assert "12.7 mm" in befunde[2].text and "1/2" in befunde[2].text
    assert "mm/min" in befunde[3].text
