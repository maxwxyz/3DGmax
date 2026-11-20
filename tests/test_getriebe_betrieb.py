"""Betriebsdrehzahlen bei festem Steg, gekoppelten Planetensaetzen und offenem Kegeldifferential."""

import math

import numpy as np
import pytest

from programm.kern import verzahnung as vz
from programm.kern.getriebe_betrieb import Betriebsmodell
from programm.kern.verzahnung_sonder import Sonderprofil
from tests.test_getriebezug import _rad


def _planetensatz(name, z, axial=0.):
    # Modul 1, Planet ebenso gross wie die Sonne, Hohlrad mit dreifacher Zaehnezahl.
    ring = _rad(f"{name} Ring", 3*z, 0., axial)
    ring.innen = True
    ring.da, ring.df = ring.d - 2., ring.d + 2.5
    return [_rad(f"{name} Sonne", z, 0., axial), ring,
            _rad(f"{name} Planet A", z, z, axial), _rad(f"{name} Planet B", z, -z, axial)]


def _wellen(betrieb, vorgaben, kupplungen=()):
    daten = betrieb.auswerten(vorgaben, kupplungen)
    assert daten["einheit"] == "1/min"
    return {w["id"]: w for w in daten["wellen"]}


@pytest.mark.parametrize("fest,abtrieb,soll", [(1, 2, 300.), (2, 1, -400.)])
def test_planeten_und_sternbetrieb(fest, abtrieb, soll):
    # Sonnenrad 1200/min. Ring fest -> Steg 300/min. Steg fest -> Ring -400/min.
    raeder = _planetensatz("A", 18)
    betrieb = Betriebsmodell(raeder, vz.paare(raeder)).betrieb()
    satz, = betrieb.saetze
    assert satz["art"] == "planet" and len(satz["umlaufraeder"]) == 2
    wellen = satz["wellen"]
    w = _wellen(betrieb, {wellen[0]: 1200., wellen[fest]: 0.})
    assert all(x["status"] == "bestimmt" for x in w.values())
    assert w[wellen[abtrieb]]["drehzahl"] == pytest.approx(soll)
    frei = _wellen(betrieb, {wellen[0]: 1200.})
    assert frei[wellen[0]]["drehzahl"] == pytest.approx(1200.)
    for i in wellen[1:]:
        assert frei[i]["status"] == "frei" and frei[i]["drehzahl"] is None


def test_gekuppelte_stufen_und_lokaler_widerspruch():
    raeder = _planetensatz("A", 18) + _planetensatz("B", 20, 12.)
    raeder += [_rad("Nebenritzel", 16, 150.), _rad("Nebenrad", 32, 174.)]
    modell = Betriebsmodell(raeder, vz.paare(raeder))
    betrieb = modell.betrieb()
    erster, zweiter = betrieb.saetze
    sa, ra, ca = erster["wellen"]
    sb, rb, cb = zweiter["wellen"]
    ritzel, rad = modell.welle[8], modell.welle[9]
    vorgaben = {sa: 1600., ra: 0., rb: 0., ritzel: 600.}
    w = _wellen(betrieb, vorgaben)
    assert w[ca]["drehzahl"] == pytest.approx(400.) and w[sb]["status"] == w[cb]["status"] == "frei"
    kupplung = [(ca, sb)]
    w = _wellen(betrieb, vorgaben, kupplung)
    assert w[sb]["drehzahl"] == pytest.approx(400.) and w[cb]["drehzahl"] == pytest.approx(100.)
    with pytest.raises(ValueError):
        betrieb.auswerten(vorgaben, [(ca, ritzel)])
    w = _wellen(betrieb, {**vorgaben, cb: 99.}, kupplung)
    for i in (sa, ra, ca, sb, rb, cb):
        assert w[i]["status"] == "widerspruch" and w[i]["drehzahl"] is None
    assert w[rad]["status"] == "bestimmt" and w[rad]["drehzahl"] == pytest.approx(-300.)


def test_mehrstufige_stirnradkette_mit_gemeinsamer_welle():
    # 16:32 und 12:36, zwei Aussenverzahnungen; Abtrieb dreht mit 1/6 der Eingangsdrehzahl.
    raeder = [_rad("Eingang", 16, 0.), _rad("Zwischenrad", 32, 24.),
              _rad("Zwischenritzel", 12, 24., 10.), _rad("Abtrieb", 36, 48., 10.)]
    modell = Betriebsmodell(raeder, vz.paare(raeder))
    assert modell.welle[1] == modell.welle[2]
    w = _wellen(modell.betrieb(), {modell.welle[0]: 1800.})
    assert w[modell.welle[1]]["drehzahl"] == pytest.approx(-900.)
    assert w[modell.welle[3]]["drehzahl"] == pytest.approx(300.)


def test_gleichhaendige_aussenraeder_bilden_keinen_planetensatz():
    raeder = _planetensatz("A", 18)
    faktor = 1. / math.cos(math.radians(15.))
    for r in raeder:
        r.hand, r.beta = "rechts", 15.
        r.punkt *= faktor
        r.d *= faktor
        r.db *= faktor
    kandidaten = vz.paare(raeder)
    assert len(kandidaten) == 4
    assert not Betriebsmodell(raeder, kandidaten).betrieb().saetze


def test_umlaufrad_erzeugt_keine_festachsige_nebenstufe():
    raeder = _planetensatz("A", 18) + [_rad("Nachbar", 18, 36.)]
    paare = vz.paare(raeder)
    assert any(p.a is raeder[2] and p.b is raeder[4] for p in paare)
    modell = Betriebsmodell(raeder, paare)
    betrieb = modell.betrieb()
    assert len(betrieb.saetze) == 1
    assert modell.welle[2] not in betrieb.ports and modell.welle[4] not in betrieb.ports


def test_drehsinn_bezogen_auf_fast_gegengerichtete_darstellungsachsen():
    # Die physisch nahezu parallelen Achsen liegen beiderseits der Betragsgleichheit von X und Y.
    a = np.array([1.00001, -1., 0.])
    b = np.array([1., -1.00001, 0.])
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    ritzel, rad = _rad("Ritzel", 16, 0.), _rad("Rad", 32, 0.)
    ritzel.richtung, rad.richtung = a, b
    rad.punkt[2] = 24.
    raeder = [ritzel, rad]
    betrieb = Betriebsmodell(raeder, vz.paare(raeder)).betrieb()
    assert betrieb.positive_achse(0) @ betrieb.positive_achse(1) < -.99999
    w = _wellen(betrieb, {0: 600.})
    # Gegenlauf als reale Winkelgeschwindigkeit erfordert hier gleiches numerisches Vorzeichen.
    assert w[1]["drehzahl"] == pytest.approx(300.)

    raeder = _planetensatz("A", 18)
    for r in raeder:
        r.richtung = b if r.innen else a
        r.punkt = np.array([0., 0., r.punkt[0]])
    betrieb = Betriebsmodell(raeder, vz.paare(raeder)).betrieb()
    sonne, ring, steg = betrieb.saetze[0]["wellen"]
    stern = _wellen(betrieb, {sonne: 1200., steg: 0.})
    assert stern[ring]["drehzahl"] == pytest.approx(400.)
    starr = _wellen(betrieb, {sonne: 1200.}, [(sonne, ring)])
    assert starr[ring]["drehzahl"] == pytest.approx(-1200.)
    assert starr[steg]["drehzahl"] == pytest.approx(1200.)


@pytest.mark.parametrize("endung", ["step", "stl"])
def test_kegeldifferential_aus_datei(tmp_path, endung):
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.TopoDS import TopoDS_Compound
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from programm.kern.laden import lade_modell
    from tests.test_verzahnung_sonder import _referenz

    paket = TopoDS_Compound()
    bauer = BRep_Builder()
    bauer.MakeCompound(paket)
    # Zwei Seitenraeder auf +/-Z und ein Ausgleichskegel auf +X; alle Teilkegel haben denselben Scheitel.
    for z, steigung, winkel in ((24, 2., 0.), (24, 2., math.pi), (12, .5, math.pi/2)):
        delta = math.atan(steigung)
        form = _referenz(z, 18 * math.sin(delta) + .9, 1.8, 7 * math.cos(delta), 0.,
                         kegel=steigung, lagen=3)
        lage = gp_Trsf()
        lage.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(0, 1, 0)), winkel)
        start = 18 * math.cos(delta)
        lage.SetTranslationPart(gp_Vec(start * math.sin(winkel), 0., start * math.cos(winkel)))
        bauer.Add(paket, form.Moved(TopLoc_Location(lage)))
    pfad = str(tmp_path / f"differential.{endung}")
    if endung == "step":
        from OCC.Core.IFSelect import IFSelect_RetDone
        from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
        writer = STEPControl_Writer()
        assert writer.Transfer(paket, STEPControl_AsIs) == IFSelect_RetDone
        assert writer.Write(pfad) == IFSelect_RetDone
    else:
        from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
        from OCC.Core.StlAPI import StlAPI_Writer
        BRepMesh_IncrementalMesh(paket, .001)
        assert StlAPI_Writer().Write(paket, pfad)
    raeder = list(vz.erkenne_koerper(lade_modell(pfad).form, "Differential", steckprofile=True, sonderprofile=True))
    assert sorted(v.z for v in raeder) == [12, 24, 24]
    betrieb = Betriebsmodell(raeder, vz.paare(raeder)).betrieb()
    satz, = betrieb.saetze
    assert satz["art"] == "kegel" and [raeder[i].z for i in satz["raeder"]] == [24, 24]
    assert [raeder[i].z for i in satz["umlaufraeder"]] == [12]
    links, rechts, korb = satz["wellen"]
    assert _wellen(betrieb, {korb: 500., links: 0.})[rechts]["drehzahl"] == pytest.approx(1000.)
    assert _wellen(betrieb, {rechts: 420., links: -180.})[korb]["drehzahl"] == pytest.approx(120.)

    # Eine 16:32-Aussenradstufe treibt den Korb. Explizite Kupplung auf der gemeinsamen Z-Achse.
    raeder += [_rad("Antrieb", 16, 24., 50.), _rad("Korbzahnrad", 32, 0., 50.)]
    modell = Betriebsmodell(raeder, vz.paare(raeder))
    betrieb = modell.betrieb()
    links, rechts, korb = betrieb.saetze[0]["wellen"]
    antrieb, korbrad = modell.welle[3], modell.welle[4]
    w = _wellen(betrieb, {antrieb: 2000., links: 0.}, [(korbrad, korb)])
    assert w[korb]["drehzahl"] == pytest.approx(-1000.) and w[rechts]["drehzahl"] == pytest.approx(-2000.)


def test_symmetrisches_kegelkreuz_braucht_traegerachse():
    # Identische 45-Grad-Kegel in allen vier Richtungen, beide Gegenpaare sind als Seitenraeder moeglich.
    raeder = []
    for i, n in enumerate(([1., 0, 0], [-1., 0, 0], [0, 0, 1.], [0, 0, -1.])):
        n = np.array(n)
        raeder.append(Sonderprofil(str(i), "konisch", 16, n * 12., n, 4., (13., 17.), (11., 15.), 0.))
    modell = Betriebsmodell(raeder, [])
    gruppe, = modell.differentiale
    assert {frozenset((s.a, s.b)) for s in gruppe} == {frozenset((0, 1)), frozenset((2, 3))}
    assert not modell.betrieb().saetze
    for ungueltig in (-1, len(gruppe)):
        with pytest.raises(ValueError):
            modell.betrieb({0: ungueltig})
    for index, variante in enumerate(gruppe):
        betrieb = modell.betrieb({0: index})
        satz, = betrieb.saetze
        assert set(satz["raeder"]) == {variante.a, variante.b}
        assert set(satz["umlaufraeder"]) == set(range(4)) - set(satz["raeder"])
        a, b, steg = satz["wellen"]
        assert _wellen(betrieb, {a: 250., steg: 0.})[b]["drehzahl"] == pytest.approx(-250.)


def test_langsamer_abtrieb_bleibt_frei_bis_zur_vorgabe():
    from programm.kern.getriebe_betrieb import _loesen
    # Dreizehn Stufen 10:1. Auch ein sehr langsamer freier Abtrieb darf nicht als fest gelten.
    stufen = [({i: 16, i + 1: 160}, 0.) for i in range(13)]
    frei, konflikt = _loesen(14, stufen)
    assert frei == [None] * 14 and not konflikt
    drehzahlen, konflikt = _loesen(14, stufen + [({0: 1}, 1000.)])
    assert not konflikt and drehzahlen[-1] == pytest.approx(-1e-10, abs=1e-20)
