"""Projektionsursprung, Hoehe, Versatz und Toleranzdeckel ueber die normalen STEP-Pfade."""

from dataclasses import replace
import math
import re

import pytest
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.GProp import GProp_GProps

from programm.kern import step_schreiben, toleranzzone, vergleich_pmi
from programm.ui.lader import lade_alles
from tests.conftest import pfad


@pytest.fixture(scope="module")
def zollmodell():
    quelle = pfad("nist_ftc_07_asme1_ap242-e2.stp")
    geladen = lade_alles(quelle)
    p = next(p for p in geladen.pmi if p.zone == "Projected" and len(p.flaechen) == 2)
    assert len(p.projektionsflaechen) == 1
    assert p.zonen_wert == pytest.approx(10.795)
    return quelle, geladen, p


def test_ap242_projektion_in_zoll_mit_versatz_und_maximum(zollmodell, tmp_path):
    quelle, geladen, p = zollmodell
    neu = replace(p, quelle="eigen", nummer=900, step_id=-900, name="Pruefung", wert=.2, material="M",
                  modifikatoren=["Diameter"], maximum_toleranz=.45, zonen_wert=8., projektionsversatz=2.)
    ziel = str(tmp_path / "projektion.stp")
    bericht = step_schreiben.schreibe(quelle, ziel, [neu], geladen.modell)
    assert bericht.neu == [900] and not bericht.uebersprungen
    kontrolle = lade_alles(ziel)
    t = next(p for p in kontrolle.pmi if p.name == neu.name and p.art == "toleranz")
    assert (t.wert, t.zonen_wert, t.projektionsversatz, t.maximum_toleranz) == pytest.approx((.2, 8., 2., .45))
    assert t.material == "M" and t.projektionsflaechen == p.projektionsflaechen
    zone = toleranzzone.zone(t, kontrolle.modell, alle_pmi=kontrolle.pmi)
    props = GProp_GProps()
    brepgprop.VolumeProperties(zone.formen[zone.rollen.index(toleranzzone.ZONE)], props)
    # Austrittsflaeche y = 12,7 mm; Beginn bei 14,7 mm, Ende bei 22,7 mm.
    assert props.CentreOfMass().Y() == pytest.approx(18.7)
    assert props.Mass() == pytest.approx(math.pi * .1**2 * 8.)
    t.bearbeitet, t.original, t.wert = True, {"wert": t.wert}, .5
    bericht = step_schreiben.schreibe(ziel, str(tmp_path / "bearbeitet.stp"), [t])
    assert not bericht.geschrieben and bericht.uebersprungen[0][1] == "wert"


def test_fehlende_projektionsangabe_wird_nicht_als_normale_zone_geschrieben(zollmodell, tmp_path):
    quelle, geladen, p = zollmodell
    neu = replace(p, quelle="eigen", nummer=900, step_id=-900, projektionsflaechen=[])
    bericht = step_schreiben.schreibe(quelle, str(tmp_path / "fehlend.stp"), [neu], geladen.modell)
    assert not bericht.neu and bericht.uebersprungen[0][0] == 900
    assert toleranzzone.zone(neu, geladen.modell) is None


def test_projektion_mit_unbekannter_laengeneinheit(zollmodell, tmp_path):
    from pathlib import Path
    quelle, _, p = zollmodell
    text = Path(quelle).read_text()
    mass = re.search(r"PROJECTED_ZONE_DEFINITION\(#[0-9]+,\(\),#[0-9]+,#([0-9]+)\)", text).group(1)
    # Eine Referenz auf die Dateiidentitaet liefert keine Laengeneinheit.
    text, anzahl = re.subn(rf"(#{mass}=LENGTH_MEASURE_WITH_UNIT\(LENGTH_MEASURE\([^)]+\),)#\d+", r"\g<1>#1", text)
    assert anzahl == 1
    ziel = tmp_path / "einheit.stp"
    ziel.write_text(text)
    t = next(t for t in lade_alles(str(ziel)).pmi if t.step_id == p.step_id)
    assert t.zone == "Projected" and t.zonen_wert is None


def test_materialbedingung_in_aelterer_step_darstellung(tmp_path):
    from pathlib import Path
    quelle = Path(pfad("nist_ftc_10_asme1_ap242-e2.stp"))
    text = quelle.read_text()
    mod = "GEOMETRIC_TOLERANCE_WITH_MODIFIERS((.MAXIMUM_MATERIAL_REQUIREMENT.))"
    assert mod in text
    quelle_alt = tmp_path / "alter_modifikator.stp"
    quelle_alt.write_text(text.replace(mod, "MODIFIED_GEOMETRIC_TOLERANCE(.MAXIMUM_MATERIAL_CONDITION.)"))
    t = next(p for p in lade_alles(str(quelle_alt)).pmi if p.material == "M")
    t.bearbeitet, t.original, t.material = True, {"material": "M"}, "L"
    ziel = str(tmp_path / "wechsel.stp")
    bericht = step_schreiben.schreibe(str(quelle_alt), ziel, [t])
    assert (t.nummer, "material") in bericht.geschrieben
    assert next(p for p in lade_alles(ziel).pmi if p.step_id == t.step_id).material == "L"


def test_vergleich_unterscheidet_die_austrittsseite(zollmodell):
    _, _, p = zollmodell
    andere = replace(p, projektionsflaechen=[999])
    vergleich, = vergleich_pmi.vergleiche_pmi([p], [andere])
    assert vergleich.status == vergleich_pmi.GEAENDERT
    assert {feld for feld, _, _ in vergleich.felder} == {"projektionsflaechen"}


def test_projektionsursprung_und_gewindeachsen_im_hinzugefuegten_teil(zollmodell):
    from programm.kern.zusammenfuegen import fuege_hinzu
    _, basis, _ = zollmodell
    zusatz = lade_alles(pfad("nist_ftc_10_asme1_ap242-e2.stp"))
    p = next(t for t in zusatz.pmi if t.zone == "Projected" and not t.flaechen)
    ursprung, = p.projektionsflaechen
    vereinigt = fuege_hinzu(basis, zusatz, (15., 100., 20.))
    assert p.projektionsflaechen == [ursprung + len(basis.modell.flaechen)]
    z = toleranzzone.zone(p, vereinigt.modell)
    for rolle, form in zip(z.rollen, z.formen, strict=True):
        if rolle == toleranzzone.BONUS:
            props = GProp_GProps()
            brepgprop.VolumeProperties(form, props)
            assert props.CentreOfMass().Y() == pytest.approx(100. + 27. + 3.2 / 2)
    assert z.rollen.count(toleranzzone.BONUS) == 2
