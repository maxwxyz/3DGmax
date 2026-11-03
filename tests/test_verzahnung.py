"""Verzahnung aus der Geometrie (PLAN §8.27) an selbst erzeugten Evolventenraedern mit bekannten Sollwerten."""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "werkzeuge"))


@pytest.mark.parametrize("z, mn, b, beta, x, innen", [
    (23, 2.0, 20.0, 0.0, 0.0, False),
    (23, 2.0, 20.0, 15.0, 0.2, False),
    (31, 1.25, 10.0, -20.0, -0.1, False),
    (40, 1.5, 12.0, 0.0, 0.0, True),
    (12, 4.0, 30.0, 0.0, 0.3, False),
])
def test_stirnrad_erkennen(z, mn, b, beta, x, innen):
    import zahnrad
    from programm.kern import verzahnung as vz
    v = vz.erkenne(zahnrad.zahnrad(z, mn, b, 20.0, beta, x, innen), "Rad")
    assert v is not None and v.z == z and v.innen == innen and v.alpha_n == 20.0
    assert abs(v.mn - mn) < 1e-3 * mn and abs(v.b - b) < 0.01 and abs(v.x - x) < 0.02
    assert abs(v.beta - abs(beta)) < 0.02 and v.hand == ("" if not beta else "rechts" if beta > 0 else "links")
    d = z * mn / math.cos(math.radians(beta))
    assert abs(v.d - d) < 0.05 and not v.hinweise
    at = math.atan(math.tan(math.radians(20.0)) / math.cos(math.radians(beta)))
    assert abs(v.db - d * math.cos(at)) < 0.03
    ha = mn * (1.0 + x) if not innen else -mn * (1.0 - x)
    assert abs(v.da - (d + 2 * ha)) < 0.02
    if not innen:  # Zahnweite nach ISO 21771 mit den Sollwerten
        wk = mn * math.cos(math.radians(20)) * ((v.k - 0.5) * math.pi + z * (math.tan(at) - at)) + \
            2 * x * mn * math.sin(math.radians(20))
        assert abs(v.wk - wk) < 0.03


def test_kein_zahnrad_und_export(tmp_path):
    import json
    import zahnrad
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from programm.kern import verzahnung as vz
    assert vz.erkenne(BRepPrimAPI_MakeBox(10, 20, 30).Shape()) is None
    assert vz.erkenne(BRepPrimAPI_MakeCylinder(10, 5).Shape()) is None
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCC.Core.gp import gp_Pnt, gp_Vec
    poly = BRepBuilderAPI_MakePolygon()
    for i in range(6):  # Sechskant: periodisch, aber keine Verzahnung
        poly.Add(gp_Pnt(10 * math.cos(i * math.pi / 3), 10 * math.sin(i * math.pi / 3), 0))
    poly.Close()
    assert vz.erkenne(BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(poly.Wire()).Face(), gp_Vec(0, 0, 8)).Shape()) is None
    v = vz.erkenne(zahnrad.zahnrad(17, 3.0, 15.0), "z17")
    csv = vz.als_csv([v])
    assert "z17" in csv and "17" in csv.splitlines()[2]
    d = json.loads(json.dumps(v.als_dict()))
    assert d["z"] == 17 and abs(d["mn"] - 3.0) < 0.01


def test_radpaare():
    """Zwei Raeder im Achsabstand (mit Profilverschiebung) und ein Ritzel im Hohlrad: Achsabstand, Ueberdeckung,
    Flankenspiel aus dem Achsabstand; Raeder mit anderem Modul paaren nicht."""
    import zahnrad
    from OCC.Core.gp import gp_Trsf, gp_Vec
    from OCC.Core.TopLoc import TopLoc_Location
    from programm.kern import verzahnung as vz

    def an(form, x):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(x, 0, 0))
        return form.Moved(TopLoc_Location(t))
    z1, z2, mn, x1, x2 = 17, 29, 2.0, 0.3, 0.1
    at = math.radians(20.0)
    inv_wt = math.tan(at) - at + 2 * math.tan(at) * (x1 + x2) / (z1 + z2)
    lo, hi = 0.1, 1.0
    for _ in range(80):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if math.tan(m) - m < inv_wt else (lo, m)
    a_soll = (z1 + z2) * mn / 2 * math.cos(at) / math.cos(lo)
    abstand = a_soll + 0.1  # 0,1 mm groesser: Normalflankenspiel 2 * 0,1 * sin 20
    r1 = vz.erkenne(zahnrad.zahnrad(z1, mn, 10.0, x=x1), "Ritzel")
    r2 = vz.erkenne(an(zahnrad.zahnrad(z2, mn, 10.0, x=x2), abstand), "Rad")
    r3 = vz.erkenne(an(zahnrad.zahnrad(20, 3.0, 10.0), -40.0), "anderes Modul")
    p = vz.paare([r1, r2, r3])
    assert len(p) == 1 and {p[0].a.teil, p[0].b.teil} == {"Ritzel", "Rad"}
    p = p[0]
    assert abs(p.abstand - abstand) < 1e-6 and abs(p.abstand_soll - a_soll) < 0.02
    assert abs(p.spiel - 2 * 0.1 * math.sin(at)) < 0.015 and 1.2 < p.eps_alpha < 1.8 and p.eps_beta == 0
    # Ritzel im Hohlrad (ohne Profilverschiebung): a = (d2 - d1) / 2
    hohl = vz.erkenne(zahnrad.zahnrad(40, 1.5, 12.0, innen=True), "Hohlrad")
    ritzel = vz.erkenne(an(zahnrad.zahnrad(16, 1.5, 12.0), 18.0), "Ritzel")
    p = vz.paare([ritzel, hohl])
    assert len(p) == 1 and p[0].a.teil == "Hohlrad" and abs(p[0].abstand_soll - 18.0) < 0.03
    assert abs(p[0].spiel) < 0.02 and p[0].eps_alpha > 1.3


def test_verzahnung_gegen_hinweis():
    from types import SimpleNamespace
    import zahnrad
    from programm.kern import plausibilitaet as pl
    from programm.kern.pmi import Pmi
    assert pl.verzahnung_angaben("Zähnezahl z = 23; Normalmodul mn = 2,0; αn = 20°; β = 15°") == \
        {"z": 23.0, "mn": 2.0, "alpha_n": 20.0, "beta": 15.0}
    assert pl.verzahnung_angaben("Allgemeintoleranz ISO 2768-mK, 12 mm") == {}
    modell = SimpleNamespace(form=zahnrad.zahnrad(23, 2.0, 20.0, beta=15.0, x=0.2), flaechen=[])
    gut = Pmi("hinweis", nur_grafik_text="z = 23  mn = 2  alpha n = 20  beta = 15  x = +0.2", nummer=1)
    assert pl.verzahnung([gut], modell) == []
    falsch = Pmi("hinweis", nur_grafik_text="number of teeth: 24, module 2.5", nummer=2)
    befunde = pl.verzahnung([falsch], modell)
    assert len(befunde) == 2 and befunde[0].stufe == "Fehler" and "24" in befunde[0].text
    assert pl.verzahnung([Pmi("hinweis", nur_grafik_text="DEBURR", nummer=3)], modell) == []


@pytest.mark.parametrize("innen", [False, True])
def test_zahnwelle_30_grad(innen):
    """Zahnwelle/-nabe mit 30 Grad und flacher Zahnhoehe (Kopf 0,5 m, Fuss 0,6 m) wird als Wellenverbindung erkannt."""
    import zahnrad
    from programm.kern import verzahnung as vz
    v = vz.erkenne(zahnrad.zahnrad(24, 1.25, 15.0, 30.0, innen=innen, kopf=0.5, fuss=0.6), "Welle")
    assert v is not None and v.welle and v.z == 24 and v.alpha_n == 30.0 and abs(v.mn - 1.25) < 2e-3
    assert "4156" in v.zeilen()[0][1]
    assert vz.erkenne(zahnrad.zahnrad(24, 1.25, 15.0, 20.0, kopf=0.5, fuss=0.6)) is None  # 20 Grad und flach: nicht


def _an(form, x, y=0.0, z=0.0):
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.gp import gp_Trsf, gp_Vec
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(x, y, z))
    return BRepBuilderAPI_Transform(form, t, True).Shape()


def test_datenblatt_rad_und_mikrogeometrie():
    """Abgeleitete Werte nach ISO 21771, Formkreise aus der Zahndicke ueber dem Radius, Kopfruecknahme an Testdaten
    mit bekannter Ruecknahme (0,02 mm ab 60 % der Waelzlaenge); reine Evolvente: keine Korrektur."""
    import zahnrad
    from programm.kern import verzahnung as vz, verzahnung_daten as vd
    rein = vz.erkenne(zahnrad.zahnrad(23, 2.0, 20.0), "rein")
    w = vd.stirnwerte(rein)
    assert abs(w["sn"] - math.pi) < 0.02 and abs(w["ha_stern"] - 1.0) < 0.01 and abs(w["hf_stern"] - 1.25) < 0.01
    dm, md = vd.kugelmass(rein)
    assert dm == 3.5 and rein.da < md < rein.da + dm
    p = vd.profil(rein)
    assert not p.ca and abs(p.dff - max(rein.db, rein.df)) < 0.15 and abs(p.dfa - rein.da) < 0.15
    assert abs(p.fh_alpha) <= p.toleranz and vd.breitenballigkeit(rein) is not None
    assert any(n.startswith("Kopfrücknahme") or n.startswith("Tip relief") for n, *_ in vd.mikro_zeilen(rein))
    mit = vz.erkenne(zahnrad.zahnrad(23, 2.0, 20.0, ruecknahme=(0.02, 0.6)), "Rücknahme")
    p = vd.profil(mit)
    rb = 23 * 2.0 * math.cos(math.radians(20.0)) / 2
    beginn = 2 * math.hypot(rb, 0.6 * math.sqrt(25.0 ** 2 - rb ** 2))
    assert abs(p.ca - 0.02) < 0.003 and abs(p.dca - beginn) < 0.3
    innen = vd.profil(vz.erkenne(zahnrad.zahnrad(40, 1.5, 12.0, innen=True), "Hohlrad"))
    assert not innen.ca


def test_datenblatt_paar_stufen_planeten(tmp_path):
    """Paar: Uebersetzung, Kopfspiel 0,25 m, Spiele; zwei Stufen ueber eine gemeinsame Welle: Gesamtuebersetzung
    und Drehrichtung; Planetensatz 18/18/54 mit drei Planeten; CSV und JSON enthalten alles."""
    import json
    import numpy as np
    import zahnrad
    from programm.kern import verzahnung as vz, verzahnung_daten as vd
    r1 = vz.erkenne(zahnrad.zahnrad(17, 2.0, 10.0), "Ritzel 1")
    r2 = vz.erkenne(_an(zahnrad.zahnrad(51, 2.0, 10.0), 68.0), "Rad 1")
    r3 = vz.erkenne(_an(zahnrad.zahnrad(20, 2.0, 10.0), 68.0, 0, 15.0), "Ritzel 2")
    r4 = vz.erkenne(_an(zahnrad.zahnrad(40, 2.0, 10.0), 128.0, 0, 15.0), "Rad 2")
    liste = [r1, r2, r3, r4]
    paare = vz.paare(liste)
    w = vd.paar_werte(paare[0])
    assert abs(w["u"] - 3) < 1e-9 and abs(w["c_klein"] - 0.5) < 0.03 and abs(w["c_gross"] - 0.5) < 0.03
    assert w["gegenlaeufig"] and w["gleiten"][0] < w["gleiten"][1] < 0  # Ritzelfuss gleitet am staerksten
    st, ziel = vd.stufen(liste, paare, [])
    assert [round(s.u, 6) for s in st] == [3.0, 2.0]
    assert sorted((round(i, 6), r) for i, r in ziel.values()) == [(1.0, 1), (3.0, -1), (6.0, 1)]
    mn = 1.5
    a = 18 * mn
    planeten = [vz.erkenne(_an(zahnrad.zahnrad(18, mn, 12.0), a * math.cos(t), a * math.sin(t)), f"Planet {k}")
                for k, t in enumerate(np.radians([0, 120, 240]), 1)]
    satz_liste = [vz.erkenne(zahnrad.zahnrad(18, mn, 12.0), "Sonne"),
                  vz.erkenne(zahnrad.zahnrad(54, mn, 12.0, innen=True), "Hohlrad")] + planeten
    saetze = vd.planetensaetze(satz_liste, vz.paare(satz_liste))
    assert len(saetze) == 1 and (saetze[0].z_sonne, saetze[0].z_planet, saetze[0].z_hohlrad) == (18, 18, 54)
    texte = dict(saetze[0].zeilen(satz_liste))
    assert len(saetze[0].planeten) == 3 and not saetze[0].hinweise
    assert any("120.0°" in t for t in texte.values())
    csv = vd.als_csv(liste, paare)
    daten = json.loads(json.dumps(vd.datenblatt(liste, paare)))
    assert "Kugel" in csv or "balls" in csv
    assert len(daten["stufen"]) == 2 and daten["zahnraeder"][0]["mikrogeometrie"]["dFf"] > 0


def test_verzahnungsfenster_datenblatt(tmp_path):
    """Fenster: Datenblatt je Rad (gemessen, abgeleitet, Mikrogeometrie), Paare und Getriebe; JSON Version 2."""
    import json
    import zahnrad
    from PySide6 import QtWidgets
    from programm.kern import verzahnung as vz
    from programm.ui.verzahnung_ui import VerzahnungFenster
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    liste = [vz.erkenne(zahnrad.zahnrad(17, 2.0, 10.0), "Ritzel"),
             vz.erkenne(_an(zahnrad.zahnrad(51, 2.0, 10.0), 68.0), "Rad")]
    f = VerzahnungFenster(liste, str(tmp_path / "g"))
    namen = [f.tabelle.verticalHeaderItem(r).text() for r in range(f.tabelle.rowCount())]
    assert any("Kugeln" in n or "balls" in n for n in namen) and any("dFf" in n for n in namen)
    assert f.paar_tabelle.rowCount() > 6 and f.getriebe_tabelle.rowCount() >= 1
    pfad = f.speichere("json", str(tmp_path / "g.json"))
    d = json.load(open(pfad, encoding="utf-8"))
    assert d["version"] == 2 and d["paare"] and d["zahnraeder"][0]["kugelmass"]["DM"] == 3.5
    r = json.load(open(f.speichere("rexs", str(tmp_path / "g.rexsj")), encoding="utf-8"))
    assert r["model"]["applicationId"] == "3DGmax" and f.rexs.toolTip()


def test_rexs_export(tmp_path):
    """REXS-Modell (FVA, Version 1.7) aus erkannten Raedern: Pflichtfelder der Datei, eindeutige Ids, Relationen
    nur mit vorhandenen Komponenten und den Rollen ihres Typs, Einheiten laut Datenbank; Werte eines bekannten Rads,
    Hohlrad als ring_gear, Kopfruecknahme als tip_relief an beiden Flanken. (Gegen das Datenbankmodell und das
    JSON-Schema der FVA einmal vollstaendig geprueft - siehe kern/rexs.py; hier die Regeln, die davon abhaengen.)"""
    import zahnrad
    from programm.kern import rexs, verzahnung as vz
    liste = [vz.erkenne(zahnrad.zahnrad(17, 2.0, 10.0, ruecknahme=(0.02, 0.6)), "Ritzel"),
             vz.erkenne(_an(zahnrad.zahnrad(51, 2.0, 10.0), 68.0), "Rad"),
             vz.erkenne(_an(zahnrad.zahnrad(40, 1.5, 12.0, innen=True), 0, 200), "Hohlrad")]
    d = rexs.modell(liste, vz.paare(liste), "Test", "1.0")["model"]
    assert {"version", "applicationId", "applicationVersion", "date", "relations", "components"} <= set(d)
    assert d["version"] == "1.7" and len(d["date"]) == 25 and d["date"][-3] == ":"
    typ = {c["id"]: c["type"] for c in d["components"]}
    assert len(typ) == len(d["components"]) and len({r["id"] for r in d["relations"]}) == len(d["relations"])
    for r in d["relations"]:
        assert all(x["id"] in typ for x in r["refs"]) and [x["role"] for x in r["refs"]] == list(rexs.ROLLEN[r["type"]])
    for c in d["components"]:
        for a in c["attributes"]:
            assert a["unit"] == rexs.EINHEIT[a["id"]] and len(a) == 3
    werte = lambda c: {a["id"]: next(v for k, v in a.items() if k not in ("id", "unit")) for a in c["attributes"]}  # noqa
    ritzel = werte(next(c for c in d["components"] if c["name"] == "Ritzel"))
    assert ritzel["number_of_teeth"] == 17 and abs(ritzel["normal_module"] - 2.0) < 0.005
    assert abs(ritzel["tip_diameter"] - 38.0) < 0.05 and "size_over_balls" in ritzel
    assert any(c["type"] == "ring_gear" and c["name"] == "Hohlrad" for c in d["components"])
    relief = next(c for c in d["components"] if c["type"] == "tip_relief")
    assert abs(werte(relief)["tip_relief_depth"] - 0.02) < 0.004
    assert sum(r["type"] == "reference" and r["refs"][1]["id"] == relief["id"] for r in d["relations"]) == 2
    stufe = werte(next(c for c in d["components"] if c["type"] == "cylindrical_stage"))
    assert abs(stufe["gear_ratio"] - 3.0) < 1e-9 and abs(stufe["center_distance"] - 68.0) < 1e-6
