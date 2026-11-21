"""Auslegung, Flaechenbezug der Sitzmasse und Getriebebefunde bis zum Export."""

import json
import math

import pytest

from programm.kern.maschinenelemente import berechne


@pytest.mark.parametrize("art,eingaben,soll", [
    ("stirnrad", dict(z1=20, z2=60, m=2, alpha=20, t=100),
     (40, 120, 80, 3, 5000, 1819.851171)),
    ("lagerwelle", dict(d=20, span=100, x=25, quer=400, t=0), (300, 100, 7.5, 9.5492966, 9.5492966)),
    ("welle", dict(d=20, t=50, tau=80), (31.8309886, 14.7101367)),
    ("buchse", dict(d=20, l=15, f=3000, n=600, pzul=12), (10, .62831853, 6.2831853, 12.5)),
    ("reibsitz", dict(d=20, l=15, t=100, mu=.2, p=50), (53.0516477, 94.2477796)),
    ("kugellager", dict(c=12, peq=3, n=1000), (64, 1066.6666667)),
    ("pressverband", dict(d=20, l=15, da=40, ew=200000, nw=.3, en=200000, nn=.3, umin=16, umax=32,
                          mu=.2, t=100), (60, 120, 113.0973355, 14.147106)),
    ("rollenlager", dict(c=8, peq=1, n=1000), (1024, 17066.6666667)),
])
def test_referenz(art, eingaben, soll):
    assert tuple(berechne(art, eingaben).values()) == pytest.approx(soll)


@pytest.mark.parametrize("feld,wert", [("alpha", 90), ("z1", 3.5), ("t", -1), ("m", 0), ("z2", math.nan)])
def test_unmoegliche_eingaben(feld, wert):
    with pytest.raises(ValueError, match=feld):
        berechne("stirnrad", dict(dict(z1=20, z2=60, m=2, alpha=20, t=100), **{feld: wert}))


@pytest.mark.parametrize("bohrung", [None, 20.02])
def test_sitzteil_mit_pmi(tmp_path, bohrung):
    from programm.kern.maschinenelemente import schreibe_sitzteil
    from programm.kern.laden import lade_step
    from programm.kern.zylindersitze import erkenne
    pfad = tmp_path / "sitz.step"
    werte = [30., 15.] + ([bohrung] if bohrung else [])
    assert schreibe_sitzteil(pfad, 30., 15., bohrung) == len(werte)
    modell = lade_step(str(pfad))
    from programm.kern.pmi_lesen import lies_pmi
    assert sorted(p.nennwert for p in lies_pmi(modell) if p.semantisch and p.grafisch and p.flaechen) == sorted(werte)
    sitze = erkenne(modell.form, 7, "Teil")
    assert sorted(s.d_mm for s in sitze) == pytest.approx(sorted([30] + ([bohrung] if bohrung else [])))


def test_sitzpaare_bis_auslegung(app, tmp_path, monkeypatch):
    from PySide6 import QtWidgets
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    from programm.ui.verzahnung_ui import VerzahnungFenster, VerzahnungLader

    def zylinder(r, l, beginn, versatz=0):
        lage = gp_Ax2(gp_Pnt(5 + .6 * beginn, versatz, .8 * beginn), gp_Dir(.6, 0, .8))
        return BRepPrimAPI_MakeCylinder(lage, r, l).Shape()

    def ring(beginn, versatz=0):
        return BRepAlgoAPI_Cut(zylinder(16, 15, beginn, versatz), zylinder(10.01, 15, beginn, versatz)).Shape()

    teile = [("Zapfen", zylinder(10, 20, 0)), ("Ring", ring(12)), ("Ring", ring(20)), ("Ring", ring(10, 1))]
    lader = VerzahnungLader(teile, teilnummern=[11, 21, 22, 23], mit_sitzen=True)
    liste = []
    lader.fertig.connect(liste.append)
    lader.run()
    assert liste == [[]]
    p, = lader.sitzpaare
    assert p.ueberdeckung_mm == pytest.approx(8) and p.differenz_mm == pytest.approx(.02)
    f = VerzahnungFenster([], str(tmp_path / "getriebe"), getriebe=True, sitze=lader.sitze, sitzpaare=[p])
    assert f.csv.isEnabled() and f.pdf.isEnabled() and f.json.isEnabled()
    wahl = []
    f.teile_gewaehlt.connect(wahl.append)
    f.sitzseite.tabelle.selectRow(0)
    assert wahl[-1] == {11, 21}
    dialog = f.sitzseite._auslegen()
    assert dialog.daten is None
    for k, t in {"t": "50", "mu": "0,2", "p": "40"}.items():
        dialog.felder[k].setText(t)
    assert dialog.daten["eingaben"]["d"] == pytest.approx(20)
    assert dialog.daten["eingaben"]["l"] == pytest.approx(8)
    ziel = str(tmp_path / "auslegung.json")
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a: (ziel, ""))
    dialog._speichern()
    dialog.felder["l"].setText("25")
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a: (ziel, ""))
    dialog._oeffnen()
    assert dialog.daten["eingaben"]["l"] == pytest.approx(8)
    assert "Zapfen" in dialog.daten["modellquelle"]
    assert json.loads(open(f.speichere("json", str(tmp_path / "r.json"))).read())["wellen_und_sitze"]["sitzpaare"]
    assert "Zapfen" in open(f.speichere("csv", str(tmp_path / "r.csv"))).read()
    assert f.speichere("pdf", str(tmp_path / "r.pdf"))
    f.close()


def test_werkzeug_ohne_modell(fenster):
    from programm.ui.maschinenelemente_ui import AuslegungFenster
    a = fenster.aktionen["maschinenelement"]
    assert a.isEnabled()
    a.trigger()
    f, = fenster.findChildren(AuslegungFenster)
    assert f.isVisible() and f.wahl.count() >= 6


def test_radpaar_kraefte_bis_lagerreaktionen(app):
    from programm.ui.verzahnung_ui import VerzahnungFenster
    from tests.test_getriebezug import _rad
    a, b = _rad("Ritzel", 20, 0.), _rad("Rad", 60, 40.)
    f = VerzahnungFenster([a, b], "Modell", quellen={id(a): 3, id(b): 4})
    f.show()
    f.reiter.setCurrentWidget(f.paar_tabelle)
    f.paar_tabelle.selectColumn(0)
    assert f.paar_auslegen.isVisible()
    paar = f._paar_auslegen()
    assert {k: float(f.text()) for k, f in paar.breitenfelder.items()} == {"b1": a.b, "b2": b.b}
    paar.breitenfelder["b2"].setText("8")
    assert paar.messwerte["b2"] == b.b
    paar.felder["t"].setText("50")
    assert paar.daten["ergebnisse"]["ft"] == pytest.approx(5000)
    welle = paar._lagerwelle()
    for k, wert in {"d": "30", "span": "80", "x": "20"}.items():
        welle.felder[k].setText(wert)
    ergebnisse = welle.daten["ergebnisse"]
    assert ergebnisse["ra"] / ergebnisse["rb"] == pytest.approx(3)
    assert ergebnisse["ra"] + ergebnisse["rb"] == pytest.approx(5000 / math.cos(math.radians(20)))
    f.close()


def test_pressverband_ungueltige_geometrie_und_material():
    daten = dict(d=20, l=15, da=40, ew=200000, nw=.3, en=200000, nn=.3, umin=16, umax=32, mu=.2, t=100)
    for k, v in (("da", 20), ("umax", 14), ("nw", .5), ("nn", -1)):
        with pytest.raises(ValueError, match=k):
            berechne("pressverband", {**daten, k: v})
    assert berechne("pressverband", {**daten, "umin": 0})["t1"] == 0
