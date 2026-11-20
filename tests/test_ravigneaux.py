"""Ravigneaux mit zwei Sonnen und zwei wiederholten Lang-/Kurzplanetenpaaren."""

from collections import Counter
import math

import pytest

from programm.kern import verzahnung as vz
from programm.kern import verzahnung_daten as vd
from programm.kern.getriebe_betrieb import Betriebsmodell


def _lagen():
    # Modul 1. Die drei Achsabstaende folgen separat aus den Teilkreisradien:
    # (32+14)/2 = (60-14)/2 = 23; (16+12)/2 = 14; (14+12)/2 = 13.
    beta = math.acos((23**2 + 14**2 - 13**2) / (2 * 23 * 14))
    x, y = 14 * math.cos(beta), 14 * math.sin(beta)
    alpha = math.atan2(y, x - 23)
    # Die Zahnmitte des einen Aussenrads trifft auf eine Luecke des Gegenrads.
    phase_kurz = alpha + math.pi - (math.pi - 14 * alpha) / 12
    phase_sonne = beta - (math.pi - 12 * (beta + math.pi - phase_kurz)) / 16
    return [
        ("Sonne lang", 32, 0., 0., 0., 5., math.pi / 32),
        ("Sonne kurz", 16, 0., 0., 11., 5., phase_sonne),
        ("Ring", 60, 0., 0., 0., 5., math.pi / 60),
        ("Lang A", 14, 23., 0., 0., 16., 0.),
        ("Kurz A", 12, x, y, 11., 5., phase_kurz),
        ("Lang B", 14, -23., 0., 0., 16., math.pi),
        ("Kurz B", 12, -x, -y, 11., 5., phase_kurz + math.pi),
    ]


def _radliste():
    from tests.test_getriebezug import _rad
    raeder = []
    for name, z, x, y, axial, breite, _ in _lagen():
        r = _rad(name, z, x, axial + breite / 2, y)
        r.b = breite
        if name == "Ring":
            r.innen = True
            r.da, r.df = r.d - 2., r.d + 2.5
        raeder.append(r)
    return raeder


@pytest.fixture(scope="module")
def baugruppe():
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.TopoDS import TopoDS_Compound
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from werkzeuge.zahnrad import zahnrad

    form = TopoDS_Compound()
    bauer = BRep_Builder()
    bauer.MakeCompound(form)
    bauteile = {}
    for name, z, x, y, axial, breite, phase in _lagen():
        if z not in bauteile:
            bauteile[z] = zahnrad(z, 1., breite, innen=name == "Ring")
        lage = gp_Trsf()
        lage.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(0, 0, 1)), phase)
        lage.SetTranslationPart(gp_Vec(x, y, axial))
        bauer.Add(form, bauteile[z].Moved(TopLoc_Location(lage)))
    return form


def _gepruefte_paare(raeder):
    return [p for p in vz.paare(raeder) if vd.eingriff_moeglich(p)]


def _eingriffe(paare):
    return Counter(tuple(sorted((p.a.z, p.b.z))) for p in paare)


def _drehzahlen(betrieb, vorgaben):
    return {w["id"]: w for w in betrieb.auswerten(vorgaben, [])["wellen"]}


@pytest.mark.parametrize("endung", ["step", "stl"])
def test_vierwellenbetrieb_aus_vollstaendiger_baugruppe(tmp_path, baugruppe, endung):
    from programm.kern.laden import lade_modell
    pfad = str(tmp_path / f"ravigneaux.{endung}")
    if endung == "step":
        from OCC.Core.IFSelect import IFSelect_RetDone
        from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
        writer = STEPControl_Writer()
        assert writer.Transfer(baugruppe, STEPControl_AsIs) == IFSelect_RetDone
        assert writer.Write(pfad) == IFSelect_RetDone
    else:
        from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
        from OCC.Core.StlAPI import StlAPI_Writer
        BRepMesh_IncrementalMesh(baugruppe, .002, False, .05, True)
        writer = StlAPI_Writer()
        writer.SetASCIIMode(False)
        assert writer.Write(baugruppe, pfad)
    raeder = list(vz.erkenne_koerper(lade_modell(pfad).form, "Ravigneaux", steckprofile=True, sonderprofile=True))
    assert sorted(v.z for v in raeder) == [12, 12, 14, 14, 16, 32, 60]
    paare = _gepruefte_paare(raeder)
    assert _eingriffe(paare) == {(14, 60): 2, (14, 32): 2, (12, 16): 2, (12, 14): 2}
    # Das Langrad reicht ueber beide Ebenen; jedes Paar hat genau 5 mm axiale Ueberdeckung.
    abstand = {(14, 60): 23., (14, 32): 23., (12, 16): 14., (12, 14): 13.}
    for p in paare:
        assert p.abstand == pytest.approx(abstand[tuple(sorted((p.a.z, p.b.z)))], abs=.005)
        unten = max(r.punkt[2] - r.b/2 for r in (p.a, p.b))
        oben = min(r.punkt[2] + r.b/2 for r in (p.a, p.b))
        assert oben - unten == pytest.approx(5., abs=.005)
    satz, = vd.ravigneauxsaetze(raeder, paare)
    assert (raeder[satz.sonne_lang].z, raeder[satz.sonne_kurz].z, raeder[satz.hohlrad].z) == (32, 16, 60)
    assert not vd.planetensaetze(raeder, paare)
    for lang, kurz in zip(satz.langplaneten, satz.kurzplaneten, strict=True):
        a, b = raeder[lang], raeder[kurz]
        assert a.z == 14 and b.z == 12
        assert math.dist(a.punkt[:2], b.punkt[:2]) == pytest.approx(13., abs=.005)
    betrieb = Betriebsmodell(raeder, paare).betrieb()
    gruppe, = betrieb.saetze
    assert gruppe["art"] == "ravigneaux" and len(gruppe["umlaufraeder"]) == 4
    sl, sk, ring, steg = gruppe["wellen"]
    assert set(betrieb.ports) == {sl, sk, ring, steg}
    # Gegenlauf am ersten, Gleichlauf am zweiten Sonnenrad, jeweils relativ zum Traeger:
    # 32(nL-nC) = -60(nR-nC); 16(nK-nC) = +60(nR-nC).
    w = _drehzahlen(betrieb, {steg: 0., sl: 900.})
    assert w[ring]["drehzahl"] == pytest.approx(-480.) and w[sk]["drehzahl"] == pytest.approx(-1800.)
    w = _drehzahlen(betrieb, {ring: 0., sl: 690.})
    assert w[steg]["drehzahl"] == pytest.approx(240.) and w[sk]["drehzahl"] == pytest.approx(-660.)
    w = _drehzahlen(betrieb, {sl: 900.})
    assert all(w[i]["status"] == "frei" and w[i]["drehzahl"] is None for i in (sk, ring, steg))
    w = _drehzahlen(betrieb, {sl: 900., ring: 0., steg: 0.})
    assert all(x["status"] == "widerspruch" for x in w.values())


@pytest.mark.parametrize("fehler", ["getrennte_achsen", "kein_axialer_eingriff", "fehlender_zweiter_zweig",
                                    "gleicher_langplanet"])
def test_aehnliche_anordnung_ohne_ravigneaux(fehler):
    raeder = _radliste()
    if fehler == "getrennte_achsen":
        raeder[1].punkt[1] += .25  # Paar-Kandidaten bleiben erhalten, aber die zweite Sonne ist exzentrisch.
    elif fehler == "kein_axialer_eingriff":
        raeder[1].punkt[2] += 15.
    elif fehler == "fehlender_zweiter_zweig":
        raeder[6].punkt[:2] = [0., -14.]  # Kurz B greift nur in die zweite Sonne ein.
    else:
        # Alle vier Eingriffsarten kommen je zweimal vor, aber beide Kurzplaneten greifen in Lang A.
        raeder[6].punkt[0] = raeder[4].punkt[0]
    paare = _gepruefte_paare(raeder)
    eingriffe = _eingriffe(paare)
    assert eingriffe[(14, 32)] == eingriffe[(14, 60)] == 2
    assert eingriffe[(12, 16)] == (0 if fehler == "kein_axialer_eingriff" else 2)
    assert eingriffe[(12, 14)] == (1 if fehler == "fehlender_zweiter_zweig" else 2)
    assert not vd.ravigneauxsaetze(raeder, paare)
    assert all(s["art"] != "ravigneaux" for s in Betriebsmodell(raeder, paare).betrieb().saetze)


@pytest.mark.parametrize("zusatzrad", ["kurz", "lang"])
def test_zusaetzlicher_eingriff_zwischen_planeten_blockiert_den_freien_satz(zusatzrad):
    raeder = _radliste()
    beta = math.atan2(raeder[4].punkt[1], raeder[4].punkt[0])
    if zusatzrad == "kurz":
        # Kurzplaneten auf Sehne 12 ihres Bolzenkreises; Langplaneten liegen jeweils aussen daneben.
        abstand = 2 * math.asin(12 / (2 * 14))
        winkel = (-beta, 0., abstand + beta, abstand)
    else:
        # Langplaneten auf Sehne 14; die beiden Kurzplaneten sind weit voneinander entfernt.
        abstand = 2 * math.asin(14 / (2 * 23))
        winkel = (0., -beta, abstand, abstand + beta)
    for rad, radius, phi in zip(raeder[3:], (23, 14, 23, 14), winkel, strict=True):
        rad.punkt[:2] = [radius * math.cos(phi), radius * math.sin(phi)]
    paare = _gepruefte_paare(raeder)
    menge = {(14, 60): 2, (14, 32): 2, (12, 16): 2, (12, 14): 2}
    z = 12 if zusatzrad == "kurz" else 14
    menge[z, z] = 1
    assert _eingriffe(paare) == menge
    assert not vd.ravigneauxsaetze(raeder, paare)
    if zusatzrad == "lang":
        # Die zusaetzliche Lang-Lang-Kante blockiert auch den scheinbar einfachen Sonne-Lang/Ring-Teilsatz.
        assert not vd.planetensaetze(raeder, paare)


def test_kurz_und_langplanet_auf_demselben_koerper():
    raeder = _radliste()
    raeder[3].koerper_id = raeder[4].koerper_id = object()
    assert not vd.ravigneauxsaetze(raeder, _gepruefte_paare(raeder))


def test_zwei_getrennte_kurzsonnen_sind_keine_eindeutige_vierwellenanordnung():
    from dataclasses import replace

    raeder = _radliste()
    # Zwei getrennte Zahnkraenze im Kurzplanetenband: beide koaxial und beide mit beiden Kurzplaneten im Eingriff.
    sonne = raeder[1]
    sonne.punkt[2], sonne.b = 12., 2.
    raeder.append(replace(sonne, teil="Weitere Kurzsonne", punkt=sonne.punkt + [0., 0., 3.]))
    paare = _gepruefte_paare(raeder)
    assert _eingriffe(paare) == {(14, 60): 2, (14, 32): 2, (12, 16): 4, (12, 14): 2}
    assert not vd.ravigneauxsaetze(raeder, paare)
