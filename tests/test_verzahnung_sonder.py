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
        phi = winkel + (drehung(s) if callable(drehung) else drehung * s)
        linie = BRepBuilderAPI_MakePolygon()
        for x, y in zip(r * np.cos(phi), r * np.sin(phi)):
            linie.Add(gp_Pnt(x, y, s))
        linie.Close()
        loft.AddWire(linie.Wire())
    loft.Build()
    form = loft.Shape()
    assert BRepCheck_Analyzer(form).IsValid()
    return form


@pytest.mark.parametrize("rate", [0., .008, -.008])
def test_kegelprofil(rate):
    form = _referenz(14, 9., 1.7, 8., rate, kegel=.55, tiefenzuwachs=.06)
    v = vz.erkenne(form, "Testkegel", sonderprofile=True)
    assert v is not None and v.art == "konisch" and v.z == 14
    daten = v.als_dict()
    assert daten["kopfkegelwinkel"] == pytest.approx(math.degrees(math.atan(.55)), abs=.2)
    assert daten["fusskegelwinkel"] == pytest.approx(math.degrees(math.atan(.49)), abs=.2)
    assert abs(v.phase / v.breite) == pytest.approx(abs(rate), abs=.0004)
    assert daten["verzahnungsrichtung"] == ("gerade" if not rate else "links" if rate < 0 else "rechts")
    assert daten["spiralwinkel_mitte_grad"] == (None if rate else 0.)


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


@pytest.mark.parametrize("profil", ["kegel", "kehle", "schraube"])
def test_pmi_pruefung_unterscheidet_zaehne_und_gaenge(profil, tmp_path):
    from types import SimpleNamespace
    from programm.kern import plausibilitaet as pl
    from programm.kern.laden import lade_modell
    from programm.kern.pmi import Pmi
    from programm.kern.pmi_bericht import FEHLER, INFO
    if profil == "kegel":
        from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
        form = _referenz(14, 9., 1.7, 8., .008, kegel=.55, tiefenzuwachs=.06)
        pfad = str(tmp_path / "kegel.step")
        schreiber = STEPControl_Writer()
        schreiber.Transfer(form, STEPControl_AsIs)
        schreiber.Write(pfad)
        modell = lade_modell(pfad)
        hinweise = ["z = 14", "teeth = 15", "Gangzahl = 14", "Normalmodul = 2"]
    elif profil == "kehle":
        r2 = 18 * 14 / (4 * math.pi)
        form = _referenz(18, r2 + .9, 1.8, 8., 14 / (2 * math.pi * 4.2 * r2), lagen=17, kehle=.075)
        modell = SimpleNamespace(form=form)
        hinweise = ["z = 18", "teeth = 19", "Gangzahl = 18", "Normalmodul = 2"]
    else:
        from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
        from OCC.Core.StlAPI import StlAPI_Writer
        form = _referenz(2, 5.2, 2.1, 28., 2 * math.pi / 14, lagen=80, kerbe=True)
        pfad = str(tmp_path / "schraube.stl")
        BRepMesh_IncrementalMesh(form, .001)
        assert StlAPI_Writer().Write(form, pfad)
        modell = lade_modell(pfad)
        hinweise = ["number of starts = 2", "Gangzahl = 3", "teeth = 2", "Normalmodul = 2"]
    notizen = [Pmi("hinweis", nur_grafik_text=text, nummer=i) for i, text in enumerate(hinweise, 1)]
    befunde = pl.verzahnung(notizen, modell)
    assert [(b.nummern, b.stufe) for b in befunde] == [([2], FEHLER), ([3], INFO), ([4], INFO)]
    assert "Geometrie " + hinweise[0].split()[-1] in befunde[0].text
    assert pl.verzahnung_angaben("Gangzahl = 1,5") == {}
    text = "worm lead 14; Axialteilung 0.7 cm" if profil == "schraube" else "worm lead 14 mm"
    b, = pl.verzahnung([Pmi("hinweis", name=text, nummer=5)], modell)
    assert b.nummern == [5] and b.stufe == INFO
    assert ("Einheit" if profil == "schraube" else "Profil") in b.text


@pytest.mark.parametrize("format_", ["step", "stl"])
def test_kegelstufe_aus_schnittachsen_und_zahnband(tmp_path, app, format_):
    import json
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Trsf, gp_Vec
    from programm.kern.laden import lade_modell
    from programm.kern import verzahnung_daten as vd
    from programm.kern.verzahnung_sonder import kegelpaar_kandidaten
    from programm.ui.verzahnung_ui import VerzahnungFenster

    def rad(z, delta, quer):
        innen, breite = (20., 6.) if quer else (18., 7.)
        start = innen * math.cos(delta)
        # Logarithmische Spirale mit konstant 28 Grad auf dem abgewickelten Teilkegel.
        faktor = (-1 if quer else 1) * math.tan(math.radians(28)) / math.sin(delta)
        form = _referenz(z, innen * math.sin(delta) + .9, 1.8, breite * math.cos(delta),
                        lambda s: faktor * math.log1p(s / start), kegel=math.tan(delta), lagen=17)
        t = gp_Trsf()
        if quer:
            t.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(0, 1, 0)), math.pi / 2)
        t.SetTranslationPart(gp_Vec(start, 0, 0) if quer else gp_Vec(0, 0, start))
        form = form.Moved(TopLoc_Location(t))
        pfad = str(tmp_path / f"kegel{z}.{format_}")
        if format_ == "step":
            schreiber = STEPControl_Writer()
            schreiber.Transfer(form, STEPControl_AsIs)
            schreiber.Write(pfad)
        else:
            from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
            from OCC.Core.StlAPI import StlAPI_Writer
            BRepMesh_IncrementalMesh(form, .001)
            assert StlAPI_Writer().Write(form, pfad)
        return vz.erkenne(lade_modell(pfad).form, str(z), steckprofile=True, sonderprofile=True)

    a = rad(12, math.atan(.5), False)
    b = rad(24, math.atan(2.), True)
    paare = kegelpaar_kandidaten([a, b])
    assert len(paare) == 1
    p = paare[0]
    assert p.achswinkel == pytest.approx(90., abs=.01)
    assert p.teil_a == pytest.approx(26.56505, abs=.01)
    assert p.gemeinsame_breite == pytest.approx(5., abs=.002)
    for band, innen, aussen, delta, z in zip(p.baender, [18., 20.], [25., 26.], [math.atan(.5), math.atan(2.)], [12, 24]):
        assert band.innen == pytest.approx(innen, abs=.002)
        assert band.aussen == pytest.approx(aussen, abs=.002)
        assert band.modul_aussen == pytest.approx(2 * aussen * math.sin(delta) / z, abs=.0002)
        assert band.modul_mitte == pytest.approx((innen + aussen) * math.sin(delta) / z, abs=.0002)
        assert band.spiralwinkel == pytest.approx(28., abs=.25)
        assert band.hand == ("rechts" if z == 12 else "links")
    daten = vd.datenblatt([a, b], [])
    assert daten["kegelpaar_kandidaten"][0]["z2_durch_z1"] == 2 and not daten["zahnraeder"]
    assert any(b["thema"] == "Teilkegel" for b in daten["auslegungsbefunde"])
    w = VerzahnungFenster([a, b], str(tmp_path / "kegel"))
    assert w.paar_tabelle.columnCount() == 1 and not w.rexs.isEnabled()
    export = json.loads(open(w.speichere("json", str(tmp_path / "werte.json"))).read())
    from pypdf import PdfReader
    pdf_text = " ".join(seite.extract_text() for seite in PdfReader(w.speichere("pdf", str(tmp_path / "paar.pdf"))).pages)
    assert "Gemeinsame Zahnbreite" in pdf_text and "5.0000" in pdf_text
    assert "Spiralwinkel" in pdf_text and "Verzahnungsrichtung" in pdf_text
    assert export["kegelpaar_kandidaten"][0]["teilkegelbaender"][0]["spiralwinkel_mitte_grad"] == pytest.approx(28, abs=.25)
    assert export["kegelpaar_kandidaten"][0]["teilkegelbaender"][0]["b_durch_re"] == pytest.approx(7/25, abs=.0002)
    assert "5.0000" in vd.als_csv([a, b], [])
    assert "Mögliches äußeres Kegelradpaar" in vd.als_csv([a, b], [])
    assert "rechts / links" in vd.als_csv([a, b], [])
    w.close()
    from dataclasses import replace
    ohne_rand, = kegelpaar_kandidaten([replace(a, bandgrenzen=None), b])
    assert ohne_rand.baender[0] is None and ohne_rand.baender[1] is not None
    assert ohne_rand.als_dict()["gemeinsame_zahnbreite"] is None
    gespiegelt = replace(b.spur, achssinn=-b.spur.achssinn)
    assert not kegelpaar_kandidaten([a, replace(b, spur=gespiegelt, zahnrichtung=a.zahnrichtung)])
    b.punkt[1] += 1.   # windschiefe Achsen
    assert not kegelpaar_kandidaten([a, b])


def test_offener_kegelmantel_belegt_keine_zahnbreite():
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from programm.kern.ausrichten import tesselliere
    from programm.kern.laden import _alle_flaechen
    form = _referenz(14, 9., 1.7, 8., 0., kegel=.55)
    BRepMesh_IncrementalMesh(form, .001)
    dreiecke = np.vstack([p[ix] for p, ix in tesselliere(_alle_flaechen(form)) if len(ix)])
    # Nur das breite Ende oeffnen. Die Zahnkonturen im Inneren bleiben vollstaendig.
    offen = dreiecke[~np.all(np.isclose(dreiecke[:, :, 2], 8.), axis=1)]
    rad, = vz._aus_schnitten(None, "Kegel", np.zeros(3), np.array([0., 0., 1.]), offen, False, True)
    assert rad.art == "konisch" and rad.bandgrenzen is None


def test_spiralwinkel_an_den_teilkreisflanken_und_in_bandmitte():
    from programm.kern.kegel_zahnspur import Kegelspur
    z, delta, spitze = 14, math.radians(30), -15.
    stationen = np.linspace(.3, 8.7, 12)
    mitte = 4.5
    r_m = (mitte - spitze) * math.tan(delta)
    rate = math.tan(math.radians(23)) / (r_m * math.cos(delta))
    th = np.linspace(-np.pi, np.pi, 8192, endpoint=False)
    profil = np.cos(z * th)
    radien, phasen = [], []
    for s in stationen:
        x = s - mitte
        # Die Spur dreht sich an den Bandenden schneller. Kopf und Fuss wandern zudem
        # gegenueber den Flanken am Teilkreis: die Phase des Gesamtprofils ist kein Ersatz.
        phi = rate * x + .012 * np.sign(x) * max(abs(x) - 2., 0.)**2
        azimut = th + phi + .012 * x * profil**2
        r = (s - spitze) * math.tan(delta) + np.interp(th, azimut, profil, period=2*np.pi)
        radien.append(r)
        phasen.append(np.angle(np.fft.rfft(r)[z]))
    spur = Kegelspur(stationen, radien, -np.unwrap(phasen) / z, 1, z)
    assert spur.spiralwinkel(spitze, delta, mitte) == pytest.approx(23., abs=.05)
    # Ein fehlender Zahn am Teilkreis verhindert die Zuordnung der beiden Flanken.
    radien[5][:1000] = radien[5].min()
    assert spur.spiralwinkel(spitze, delta, mitte) is None


def test_zahnrichtung_unabhaengig_vom_sinn_der_schnittachse():
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from programm.kern.ausrichten import tesselliere
    from programm.kern.laden import _alle_flaechen
    form = _referenz(14, 9., 1.7, 8., -.035, kegel=.55, lagen=12)
    BRepMesh_IncrementalMesh(form, .001)
    dreiecke = np.vstack([p[ix] for p, ix in tesselliere(_alle_flaechen(form)) if len(ix)])
    for achse in (1., -1.):
        rad, = vz._aus_schnitten(None, "Kegel", np.zeros(3), np.array([0., 0., achse]), dreiecke, False, True)
        assert rad.zahnrichtung == "links"
        assert rad.richtung[2] == 1.


def test_kegelspur_mit_mehr_als_halber_teilung_zwischen_zwei_grobschnitten():
    form = _referenz(24, 10., 1.6, 8., .24, kegel=.45, lagen=35)
    rad = vz.erkenne(form, "Steiles Ritzel", sonderprofile=True)
    assert rad.art == "konisch" and rad.z == 24 and rad.zahnrichtung == "rechts"
    assert rad.phase / rad.breite == pytest.approx(.24, abs=.001)


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
