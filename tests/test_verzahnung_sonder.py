"""Konische Zahnkoerper und Schraubnuten mit analytisch vorgegebenen Schnittprofilen."""

import math

import numpy as np
import pytest
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
from OCC.Core.BRepCheck import BRepCheck_Analyzer
from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCC.Core.gp import gp_Pnt

from programm.kern import verzahnung as vz


def _referenz(z, radius, tiefe, laenge, drehung, kegel=0.0, lagen=7, kerbe=False, tiefenzuwachs=0., kehle=0.):
    # Abschnitte mit definierter Zahnspur; gerade Kanten und Regelflaechen je Abschnitt.
    winkel = np.linspace(0, 2 * np.pi, max(8 * z, 48), endpoint=False)
    muster = np.cos(z * winkel)
    profil = (.5 - .5 * muster) ** 4 if kerbe else .5 - .5 * np.clip(1.5 * muster, -1, 1)
    loft = BRepOffsetAPI_ThruSections(True, True)
    loft.CheckCompatibility(False)
    for s in np.linspace(0, laenge, lagen):
        r = radius + kegel * s + kehle * (s - laenge / 2) ** 2 - (tiefe + tiefenzuwachs * s) * profil
        phi = winkel + drehung * s
        linie = BRepBuilderAPI_MakePolygon()
        for x, y in zip(r * np.cos(phi), r * np.sin(phi)):
            linie.Add(gp_Pnt(x, y, s))
        linie.Close()
        loft.AddWire(linie.Wire())
    loft.Build()
    form = loft.Shape()
    assert BRepCheck_Analyzer(form).IsValid()
    return form


@pytest.mark.parametrize("rate", [0., .008])
def test_kegelprofil(rate):
    form = _referenz(14, 9., 1.7, 8., rate, kegel=.55, tiefenzuwachs=.06)
    v = vz.erkenne(form, "Testkegel", sonderprofile=True)
    assert v is not None and v.art == "konisch" and v.z == 14
    daten = v.als_dict()
    assert daten["kopfkegelwinkel"] == pytest.approx(math.degrees(math.atan(.55)), abs=.2)
    assert daten["fusskegelwinkel"] == pytest.approx(math.degrees(math.atan(.49)), abs=.2)
    assert abs(v.phase / v.breite) == pytest.approx(abs(rate), abs=.0004)


@pytest.mark.parametrize("z,hand", [(2, 1), (3, -1), (1, 1), (4, -1)])
def test_schraubprofil(z, hand):
    rate = hand * 2 * math.pi / 14.
    form = _referenz(z, 5.2, 2.1, 28., rate, lagen=80, kerbe=True)
    v = vz.erkenne(form, "Testschraube", sonderprofile=True)
    assert v is not None and v.art == "schraube" and v.z == z
    d = v.als_dict()
    assert d["vorschub"] == pytest.approx(14., rel=.007)
    assert d["axialteilung"] == pytest.approx(14. / z, rel=.007)
    assert d["hand"] == ("rechts" if hand > 0 else "links")


def test_kegelstufe_aus_schnittachsen_und_zahnband(tmp_path, app):
    import json
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Trsf, gp_Vec
    from programm.kern.laden import lade_step
    from programm.kern import verzahnung_daten as vd
    from programm.kern.verzahnung_sonder import kegelpaar_kandidaten
    from programm.ui.verzahnung_ui import VerzahnungFenster

    def rad(z, delta, quer):
        start = 18 * math.cos(delta)
        form = _referenz(z, 18 * math.sin(delta) + .9, 1.8, 7 * math.cos(delta), 0., kegel=math.tan(delta))
        t = gp_Trsf()
        if quer:
            t.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(0, 1, 0)), math.pi / 2)
        t.SetTranslationPart(gp_Vec(start, 0, 0) if quer else gp_Vec(0, 0, start))
        form = form.Moved(TopLoc_Location(t))
        pfad = str(tmp_path / f"kegel{z}.stp")
        schreiber = STEPControl_Writer()
        schreiber.Transfer(form, STEPControl_AsIs)
        schreiber.Write(pfad)
        return vz.erkenne(lade_step(pfad).form, str(z), steckprofile=True, sonderprofile=True)

    a = rad(12, math.atan(.5), False)
    b = rad(24, math.atan(2.), True)
    paare = kegelpaar_kandidaten([a, b])
    assert len(paare) == 1
    p = paare[0]
    assert p.achswinkel == pytest.approx(90., abs=.01)
    assert p.teil_a == pytest.approx(26.56505, abs=.01)
    daten = vd.datenblatt([a, b], [])
    assert daten["kegelpaar_kandidaten"][0]["z2_durch_z1"] == 2 and not daten["zahnraeder"]
    assert any(b["thema"] == "Teilkegel" for b in daten["auslegungsbefunde"])
    w = VerzahnungFenster([a, b], str(tmp_path / "kegel"))
    assert w.paar_tabelle.columnCount() == 1 and not w.rexs.isEnabled()
    assert json.loads(open(w.speichere("json", str(tmp_path / "werte.json"))).read())["sonderprofile"]
    assert "Mögliches äußeres Kegelradpaar" in vd.als_csv([a, b], [])
    w.close()
    b.punkt[1] += 1.   # windschiefe Achsen
    assert not kegelpaar_kandidaten([a, b])


def test_gleichfoermige_und_ungerillte_teile_sind_keine_sonderprofile():
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCone
    from programm.kern.verzahnung_sonder import Sonderprofil
    glatt = BRepPrimAPI_MakeCone(8., 13., 8.).Shape()
    achsparallel = _referenz(2, 5., 2., 24., 0., kerbe=True)
    for f in (glatt, achsparallel):
        assert not isinstance(vz.erkenne(f, sonderprofile=True), Sonderprofil)


def test_tailliertes_schneckenrad_mit_passendem_und_versetztem_partner(app):
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Trsf, gp_Vec
    from OCC.Core.TopLoc import TopLoc_Location
    from programm.kern import verzahnung_daten as vd
    from programm.kern.verzahnung_sonder import Taillenrad, schneckenpaar_kandidaten
    from programm.ui.verzahnung_ui import VerzahnungFenster

    vorschub, gaenge, z = 14., 2, 18
    r1 = 4.2
    r2 = z * vorschub / (2 * math.pi * gaenge)
    laenge = 8.
    # Referenz mit bekannter Kehle bei L/2 und zur Axialteilung passender Zahnspur.
    rate = vorschub / (2 * math.pi * r1 * r2)
    form = _referenz(z, r2 + .9, 1.8, laenge, rate, lagen=17, kehle=.075)
    rad = vz.erkenne(form, "Rad", steckprofile=True, sonderprofile=True)
    assert isinstance(rad, Taillenrad)
    assert rad.punkt[2] == pytest.approx(laenge / 2, abs=.06)
    assert rad.kopf == pytest.approx(r2 + .9, abs=.04)
    form = _referenz(gaenge, 5.2, 2.1, 28., 2 * np.pi / vorschub, lagen=80, kerbe=True)
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(0, 1, 0)), math.pi / 2)
    t.SetTranslationPart(gp_Vec(-14., r1 + r2, laenge / 2))
    w = vz.erkenne(form.Moved(TopLoc_Location(t)), "Schraube", steckprofile=True, sonderprofile=True)
    p, = schneckenpaar_kandidaten([rad, w])
    assert p.achsabstand == pytest.approx(r1 + r2, abs=.03)
    assert p.als_dict()["zaehne_durch_gaenge"] == 9
    daten = vd.datenblatt([rad, w], [])
    assert daten["schneckenpaar_kandidaten"] == [p.als_dict()]
    assert any(b["thema"] == "Schneckenradpaar" for b in daten["auslegungsbefunde"])
    assert "Mögliches Schneckenradpaar" in vd.als_csv([rad, w], [])
    fenster = VerzahnungFenster([w, rad], "")
    assert fenster.paar_tabelle.columnCount() == 1
    fenster.close()
    rad.spursteigung *= -1
    assert not schneckenpaar_kandidaten([rad, w])  # unpassende Hand
    rad.spursteigung *= -1
    rad.punkt += 2 * rad.richtung
    assert not schneckenpaar_kandidaten([rad, w])  # gemeinsame Normale abseits der Kehle
