"""Stufenplaneten mit zwei starr verbundenen Zahnbaendern am selben Bolzen."""

from fractions import Fraction
import math

import pytest

from programm.kern import verzahnung as vz
from programm.kern import verzahnung_daten as vd
from programm.kern.getriebe_betrieb import Betriebsmodell


@pytest.fixture(scope="module")
def bauteile():
    from tests.test_verzahnung_zahnbaender import _stufenwelle
    from werkzeuge.zahnrad import zahnrad

    # Modul 1,5 mm. Beide Paarungen haben Achsabstand 24 mm:
    # (18 + 14) * m/2 auf der Sonnenseite, (52 - 20) * m/2 auf der Ringseite.
    return (zahnrad(18, 1.5, 5.), zahnrad(52, 1.5, 5., innen=True),
            _stufenwelle([(14, 2., 5.), (20, 24., 5.)]))


def _datei(pfad, bauteile, geteilt=False):
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.TopoDS import TopoDS_Compound
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from programm.kern.laden import lade_modell

    sonne, ring, planet = bauteile
    if geteilt:
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
        luecke = BRepPrimAPI_MakeBox(gp_Pnt(-20, -20, 14), gp_Pnt(20, 20, 15)).Shape()
        planet = BRepAlgoAPI_Cut(planet, luecke).Shape()
    paket = TopoDS_Compound()
    bauer = BRep_Builder()
    bauer.MakeCompound(paket)
    for form, x, z, phase in ((sonne, 0., 2., math.pi/18), (ring, 0., 24., math.pi/52),
                              (planet, -24., 0., 0.), (planet, 24., 0., 0.)):
        lage = gp_Trsf()
        lage.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(0, 0, 1)), phase)
        lage.SetTranslationPart(gp_Vec(x, 0., z))
        bauer.Add(paket, form.Moved(TopLoc_Location(lage)))
    if pfad.suffix == ".step":
        from OCC.Core.IFSelect import IFSelect_RetDone
        from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
        writer = STEPControl_Writer()
        assert writer.Transfer(paket, STEPControl_AsIs) == IFSelect_RetDone
        assert writer.Write(str(pfad)) == IFSelect_RetDone
    else:
        from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
        from OCC.Core.StlAPI import StlAPI_Writer
        BRepMesh_IncrementalMesh(paket, .002, False, .05, True)
        writer = StlAPI_Writer()
        writer.SetASCIIMode(False)
        assert writer.Write(paket, str(pfad))
    form = lade_modell(str(pfad)).form
    raeder = list(vz.erkenne_koerper(form, "Stufenplaneten", steckprofile=True, sonderprofile=True))
    assert sorted(v.z for v in raeder) == [14, 14, 18, 20, 20, 52]
    return raeder


@pytest.mark.parametrize("endung", ["step", "stl"])
def test_stufenplanet_aus_einteiligen_doppelraedern(tmp_path, bauteile, endung):
    raeder = _datei(tmp_path / f"stufensatz.{endung}", bauteile)
    paare = vz.paare(raeder)
    satz, = vd.planetensaetze(raeder, paare)
    assert satz.gestuft and (satz.z_sonne, satz.z_planet, satz.z_planet_ring, satz.z_hohlrad) == (18, 14, 20, 52)
    assert len(satz.planeten) == len(satz.planeten_ring) == 2
    assert set(satz.umlaufraeder) == {*satz.planeten, *satz.planeten_ring}
    for i, j in zip(satz.planeten, satz.planeten_ring):
        assert (raeder[i].z, raeder[j].z) == (14, 20)
        assert raeder[i].koerper_id is not None and raeder[i].koerper_id is raeder[j].koerper_id
    assert raeder[satz.planeten[0]].koerper_id is not raeder[satz.planeten[1]].koerper_id
    a, b = satz.koeffizienten
    assert Fraction(b, a) == Fraction(52 * 14, 18 * 20)
    betrieb = Betriebsmodell(raeder, paare).betrieb()
    gruppe, = betrieb.saetze
    assert gruppe["art"] == "stufenplanet"
    sonne, ring, steg = gruppe["wellen"]
    assert set(betrieb.ports) == {sonne, ring, steg}
    # Unabhaengige Sollwerte mit zwei Zahnkontakten: 45 (nS-nC) + 91 (nR-nC) = 0.
    for eingang, fest, ausgang, soll in ((1360., ring, steg, 450.), (910., steg, ring, -450.)):
        auswertung = betrieb.auswerten({sonne: eingang, fest: 0.}, [])
        w = next(w for w in auswertung["wellen"] if w["id"] == ausgang)
        assert w["status"] == "bestimmt" and w["drehzahl"] == pytest.approx(soll)


def test_getrennte_koerper_auf_denselben_planetenachsen(tmp_path, bauteile):
    raeder = _datei(tmp_path / "geteilte_planeten.stl", bauteile, geteilt=True)
    paare = vz.paare(raeder)
    assert len([p for p in paare if vd.eingriff_moeglich(p)]) == 4
    assert not vd.planetensaetze(raeder, paare)
    assert not Betriebsmodell(raeder, paare).betrieb().saetze


def _radliste(fehler=None):
    from tests.test_getriebezug import _rad

    sonne, ring = _rad("Sonne", 18, 0.), _rad("Ring", 52, 0., 12.)
    ring.innen = True
    ring.da, ring.df = ring.d - 2., ring.d + 2.5
    raeder = [sonne, ring]
    for k, seite in enumerate((1, -1)):
        # Zweiter Pfad: 16/18 statt 14/20, beide Zahnkontakte jeweils im Nennachsabstand.
        p1, p2 = (16, 18) if k and fehler == "standuebersetzung" else (14, 20)
        x = seite * (18 + p1) / 2
        ringlage = 30. if k and fehler == "fehlender_eingriff" else 12.
        name = f"Planet {k + 1}"
        a, b = _rad(name + " [1/2]", p1, x), _rad(name + " [2/2]", p2, x, ringlage)
        a.koerper = b.koerper = name
        a.koerper_id = b.koerper_id = object()
        raeder.extend((a, b))
    return raeder


def test_planetenbaender_bleiben_ihrem_koerper_zugeordnet():
    original = _radliste()
    # Gleiche Bezeichnungen wie bei einer mehrfach eingesetzten Baugruppenkomponente.
    for rad in original[2:]:
        rad.koerper = "Doppelrad"
    raeder = [original[i] for i in (1, 5, 2, 0, 4, 3)]
    satz, = vd.planetensaetze(raeder, list(reversed(vz.paare(raeder))))
    paare = [(raeder[i], raeder[j]) for i, j in zip(satz.planeten, satz.planeten_ring, strict=True)]
    assert len(paare) == 2
    assert all(a.z == 14 and b.z == 20 and a.koerper_id is b.koerper_id for a, b in paare)


@pytest.mark.parametrize("fehler", ["standuebersetzung", "fehlender_eingriff"])
def test_stufenplanet_verlangt_zwei_konsistente_eingriffspfade(fehler):
    raeder = _radliste(fehler)
    paare = [p for p in vz.paare(raeder) if vd.eingriff_moeglich(p)]
    assert len(paare) == (4 if fehler == "standuebersetzung" else 3)
    assert not vd.planetensaetze(raeder, paare)
