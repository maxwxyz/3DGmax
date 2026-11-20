"""Gekoppelte Schraegdifferentialritzel aus einer montierten Netzdatei und Gegenproben."""

import math

import pytest
from scipy.spatial.transform import Rotation

from programm.kern import verzahnung as vz
from programm.kern import verzahnung_daten as vd
from programm.kern.getriebe_betrieb import Betriebsmodell
from tests.test_verzahnung_mesh import _radnetz, _schreibe


@pytest.fixture(scope="module")
def schraegraeder(tmp_path_factory):
    # Zwei koaxiale 24er Seitenraeder. Je Zweig zwei 12er Ritzel, gegeneinander axial versetzt.
    netze = [_radnetz(24, axial=0., beta=12.), _radnetz(24, axial=8., beta=-12.)]
    lage = Rotation.from_rotvec([.31, -.42, .18])
    radius = 36 / math.cos(math.radians(12))
    halbwinkel = math.asin(1/3)
    for achse in (0., math.pi):
        for phi, axial, beta in ((achse - halbwinkel, 1.75, -12.), (achse + halbwinkel, 6.25, 12.)):
            punkte, ind = _radnetz(12, axial=axial, beta=beta)
            netze.append((punkte + lage.apply([radius * math.cos(phi), radius * math.sin(phi), 0]), ind))
    modell = _schreibe(tmp_path_factory.mktemp("Differential") / "Schraegdifferential.stl", netze)
    return list(vz.erkenne_koerper(modell.form, "Differential", steckprofile=True, sonderprofile=True))


def test_schraegraddifferential_aus_stl(schraegraeder):
    raeder = schraegraeder
    assert sorted(v.z for v in raeder) == [12, 12, 12, 12, 24, 24]
    paare = vz.paare(raeder)
    assert len([p for p in paare if vd.eingriff_moeglich(p)]) == 6
    betrieb = Betriebsmodell(raeder, paare).betrieb()
    satz, = betrieb.saetze
    assert satz["art"] == "schraegraddifferential"
    a, b, steg = satz["wellen"]
    assert set(betrieb.ports) == {a, b, steg}
    ergebnis = betrieb.auswerten({a: 60., steg: 120.}, [])
    assert next(w["drehzahl"] for w in ergebnis["wellen"] if w["id"] == b) == pytest.approx(180.)
    daten = vd.datenblatt(raeder, paare)
    assert len(daten["differentialgruppen"]) == 1 and not daten["kraftfluss"]["zuege"]
    assert not daten["stufen"]


def test_schraegraddifferential_braucht_zwei_vollstaendige_ritzelpaare(schraegraeder):
    paare = vz.paare(schraegraeder)
    kanten = [p for p in paare if p.a.z == p.b.z == 12 and vd.eingriff_moeglich(p)]
    assert len(kanten) == 2
    ohne_eingriff = [p for p in paare if p is not kanten[0]]
    assert not Betriebsmodell(schraegraeder, ohne_eingriff).differentiale


def test_drehfest_verbundene_ritzel_sind_keine_freien_ausgleichsraeder(schraegraeder, monkeypatch):
    paare = vz.paare(schraegraeder)
    paar = next(p for p in paare if p.a.z == p.b.z == 12 and vd.eingriff_moeglich(p))
    koerper = object()
    monkeypatch.setattr(paar.a, "koerper_id", koerper)
    monkeypatch.setattr(paar.b, "koerper_id", koerper)
    assert not Betriebsmodell(schraegraeder, paare).differentiale


def test_sperrmodell_und_rexs_am_importierten_schraegraddifferential(schraegraeder):
    from programm.kern.differentialsperre import Sperrvorgabe
    from programm.kern import rexs

    paare = vz.paare(schraegraeder)
    betrieb = Betriebsmodell(schraegraeder, paare).betrieb()
    a, b, steg = betrieb.saetze[0]["wellen"]
    gesperrt = betrieb.auswerten({steg: 120.}, [], sperren={steg: Sperrvorgabe("gesperrt")})
    assert all(w["drehzahl"] == 120 for w in gesperrt["wellen"])
    teil = betrieb.auswerten({a: 60., b: 180.}, [], sperren={steg: Sperrvorgabe("tbr", 400., 3.)})
    assert teil["differentialsperren"][0]["seitenmomente_a_b"] == [[200., 300.], [100., 200.]]
    daten = rexs.modell(schraegraeder, paare)["model"]
    rollen = [r["type"] for r in daten["relations"]]
    assert rollen.count("central_shaft") == 2 and rollen.count("planet_shaft") == 4 and rollen.count("stage") == 6
