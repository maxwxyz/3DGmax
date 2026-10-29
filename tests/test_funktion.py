"""Von der Funktion zur Tolerierung: Rollen je Flaeche -> Bezugssystem 3-2-1 -> PMI-Vorschlaege (kern.funktion)."""

from types import SimpleNamespace

import pytest

from programm.kern import funktion as fu
from programm.kern.pmi import BEZUG, MASS, TOLERANZ


@pytest.fixture(scope="module")
def teil():
    """Platte 100 x 60 x 20 mit Zentrierbohrung Ø20 (Mitte) und Stiftloch Ø6 (versetzt), beide durch."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    form = BRepPrimAPI_MakeBox(100, 60, 20).Shape()
    for x, y, r in ((50, 30, 10), (85, 30, 3)):
        form = BRepAlgoAPI_Cut(form, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, -1), gp_Dir(0, 0, 1)), r, 22)
                               .Shape()).Shape()
    flaechen, ex = [], TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        flaechen.append(topods.Face(ex.Current()))
        ex.Next()
    return SimpleNamespace(flaechen=flaechen)


def _finde(teil, art, **bed):
    for i, f in enumerate(teil.flaechen):
        g = fu._geometrie(f)
        if g and g["art"] == art and all(abs(float(bed[k](g)) ) < 1e-6 for k in bed):
            return i
    raise AssertionError(art)


def test_bezugssystem_und_tolerierung(teil):
    unten = _finde(teil, "ebene", z=lambda g: g["punkt"][2] if abs(g["richtung"][2]) > 0.9 else 1,
                   n=lambda g: g["richtung"][2] + 1)
    oben = _finde(teil, "ebene", z=lambda g: g["punkt"][2] - 20 if abs(g["richtung"][2]) > 0.9 else 1)
    links = _finde(teil, "ebene", x=lambda g: g["punkt"][0] if abs(g["richtung"][0]) > 0.9 else 1)
    bohrung = _finde(teil, "zylinder", d=lambda g: g["groesse"] - 20)
    stift = _finde(teil, "zylinder", d=lambda g: g["groesse"] - 6)
    rollen = {unten: "auflage", bohrung: "zentrierung", stift: "verdrehsicherung", oben: "dichtung", links: "frei"}
    s = fu.bezugssystem(teil, rollen)
    assert [(b.buchstabe, b.flaeche, b.element) for b in s.bezuege] == \
        [("A", unten, "ebene"), ("B", bohrung, "achse"), ("C", stift, "achse")] and s.offen == 0
    v = fu.tolerierung(teil, rollen, s)
    typen = {(p.pmi.art, p.pmi.typ, tuple(sorted(p.pmi.flaechen))) for p in v}
    assert (BEZUG, "Datum", (unten,)) in typen and (TOLERANZ, "Flatness", (unten,)) in typen
    passung = {p.pmi.passung for p in v if p.pmi.art == MASS}
    assert passung == {"H7"}  # beide Bohrungen: Bohrungsbasis H7
    stift_pos = next(p.pmi for p in v if p.pmi.typ == "Position" and stift in p.pmi.flaechen)
    assert stift_pos.material == "M" and [b.name for b in stift_pos.bezuege] == ["A", "B"]
    senkrecht = next(p.pmi for p in v if p.pmi.typ == "Perpendicularity" and bohrung in p.pmi.flaechen)
    assert [b.name for b in senkrecht.bezuege] == ["A"] and 0 < senkrecht.wert < 0.1
    assert not any(links in p.pmi.flaechen for p in v)  # Freiflaeche: Allgemeintoleranz
    nur_achse = fu.bezugssystem(teil, {bohrung: "zentrierung"})
    assert nur_achse.bezuege[0].freiheitsgrade == 4 and nur_achse.offen == 2 and nur_achse.hinweise


def test_element_aus_halbschalen_und_eigene_werte():
    """Bohrung aus zwei Halbschalen = ein Element (Inhalt beider, PMI an beiden Flaechen); von Hand gesetzte
    Toleranz und Passung ersetzen die Startwerte."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.ShapeUpgrade import ShapeUpgrade_ShapeDivideClosed
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    form = BRepAlgoAPI_Cut(BRepPrimAPI_MakeBox(60, 40, 20).Shape(), BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(30, 20, -1), gp_Dir(0, 0, 1)), 10, 22).Shape()).Shape()
    teilen = ShapeUpgrade_ShapeDivideClosed(form)
    teilen.SetNbSplitPoints(1)
    teilen.Perform()
    flaechen, ex = [], TopExp_Explorer(teilen.Result(), TopAbs_FACE)
    while ex.More():
        flaechen.append(topods.Face(ex.Current()))
        ex.Next()
    t = SimpleNamespace(flaechen=flaechen)
    halbe = [i for i, f in enumerate(flaechen) if (g := fu._geometrie(f)) and g["art"] == "zylinder"]
    unten = _finde(t, "ebene", z=lambda g: g["punkt"][2] if abs(g["richtung"][2]) > 0.9 else 1,
                   n=lambda g: g["richtung"][2] + 1)
    oben = _finde(t, "ebene", z=lambda g: g["punkt"][2] - 20 if abs(g["richtung"][2]) > 0.9 else 1)
    assert len(halbe) == 2 and fu.ein_element(t, halbe) and not fu.ein_element(t, [halbe[0], unten])
    assert not fu.ein_element(t, [unten, oben])  # parallel, aber nicht in einer Ebene
    gruppen = {halbe[0]: tuple(halbe)}
    g1, g2 = fu._geometrie(flaechen[halbe[0]]), fu._geo(t, halbe[0], gruppen)
    assert abs(g2["inhalt"] - 2 * g1["inhalt"]) < 1e-6 and g2["groesse"] == 20
    rollen = {unten: "auflage", halbe[0]: "zentrierung"}
    s = fu.bezugssystem(t, rollen, gruppen)
    assert [b.flaeche for b in s.bezuege] == [unten, halbe[0]]
    v = fu.tolerierung(t, rollen, s, gruppen)
    assert {p.flaechen == set(halbe) for p in (x.pmi for x in v) if halbe[0] in p.flaechen} == {True}
    start = fu.startwerte(t, halbe[0], "zentrierung", gruppen)
    assert start["passung"] == "H7" and start["lage"] > 0
    v = fu.tolerierung(t, rollen, s, gruppen, {halbe[0]: {"toleranz": 0.05, "passung": "H8"}})
    eigene = [x.pmi for x in v if halbe[0] in x.pmi.flaechen]
    assert {p.wert for p in eigene if p.art == TOLERANZ} == {0.05}
    assert [p.passung for p in eigene if p.art == MASS] == ["H8"]
    assert all(x.pmi.wert != 0.05 for x in v if unten in x.pmi.flaechen and x.pmi.art == TOLERANZ)


def test_erzeugte_pmi_liegen_nicht_uebereinander():
    """Alle Vorschlaege der Funktion auf FTC-10 als PMI erzeugt: im isometrischen Gesamtbild ueberlappt kein Rahmen
    einen anderen (vorher nur je Schreibebene geprueft - Rahmen verschiedener Ebenen lagen uebereinander)."""
    import numpy as np
    from programm.kern import pmi_erzeugen as pe
    from programm.ui.lader import lade_alles
    from tests.conftest import pfad
    m = lade_alles(pfad("nist_ftc_10_asme1_ap242-e2.stp")).modell
    geo = {i: g for i in range(len(m.flaechen)) if (g := fu._geometrie(m.flaechen[i])) is not None}
    ebenen = sorted((i for i in geo if geo[i]["art"] == "ebene"), key=lambda i: -geo[i]["inhalt"])
    boh = sorted((i for i in geo if geo[i]["art"] == "zylinder" and geo[i]["bohrung"]), key=lambda i: -geo[i]["groesse"])
    rollen = {ebenen[0]: "auflage", boh[0]: "zentrierung", boh[1]: "verdrehsicherung", ebenen[1]: "dichtung",
              ebenen[2]: "anschlag", boh[2]: "presssitz"}
    pmi = [v.pmi for v in fu.tolerierung(m, rollen)]
    for k, p in enumerate(pmi, 1):
        p.step_id, p.nummer = -2000 - k, k
    neu = pe.ergaenze(pmi, {}, m, [])

    def bild(g):
        pts = np.vstack([np.array(li) for li in g.linien[1:]] +
                        [np.array([ph.ursprung, ph.ursprung + ph.x * ph.breite + ph.y * ph.hoehe]) for ph in g.platzhalter])
        q = pts @ pe.ISO_BILD
        return q.min(0), q.max(0)
    b = [bild(g) for g in neu.values()]
    assert len(b) > 8
    assert not [(i, j) for i in range(len(b)) for j in range(i + 1, len(b))
                if np.all(b[i][0] < b[j][1]) and np.all(b[j][0] < b[i][1])]


def test_bezuege_von_hand(teil):
    """Bezuege in der Tabelle von Hand festlegen: Reihenfolge und Elemente folgen der Vorgabe, die Tolerierung
    bezieht sich darauf."""
    unten = _finde(teil, "ebene", z=lambda g: g["punkt"][2] if abs(g["richtung"][2]) > 0.9 else 1,
                   n=lambda g: g["richtung"][2] + 1)
    bohrung = _finde(teil, "zylinder", d=lambda g: g["groesse"] - 20)
    stift = _finde(teil, "zylinder", d=lambda g: g["groesse"] - 6)
    rollen = {unten: "auflage", bohrung: "zentrierung", stift: "verdrehsicherung"}
    auto = fu.bezugssystem(teil, rollen)
    assert [b.flaeche for b in auto.bezuege] == [unten, bohrung, stift]
    s = fu.bezugssystem(teil, rollen, vorgabe={stift: "B", unten: "A"})  # Stift statt Bohrung als B, kein C
    assert [(b.buchstabe, b.flaeche) for b in s.bezuege] == [("A", unten), ("B", stift)] and s.offen == 1
    assert s.hinweise and all(b.grund == "Von Hand als Bezug festgelegt" for b in s.bezuege)
    v = fu.tolerierung(teil, rollen, s)
    assert {p.name for p in (x.pmi for x in v) if p.art == BEZUG} == {"A", "B"}


def test_bezug_vorschau_freiheitsgrade(teil):
    """Vorschau des Bezugssystems: A Ebene sperrt 3, B Achse senkrecht dazu 2, C Stift 1 - nichts offen; nur die
    Achse: 4 gesperrt, offen Verschieben entlang und Drehen um die Achse."""
    from programm.kern import bezug_vorschau as bv
    unten = _finde(teil, "ebene", z=lambda g: g["punkt"][2] if abs(g["richtung"][2]) > 0.9 else 1,
                   n=lambda g: g["richtung"][2] + 1)
    bohrung = _finde(teil, "zylinder", d=lambda g: g["groesse"] - 20)
    stift = _finde(teil, "zylinder", d=lambda g: g["groesse"] - 6)
    rollen = {unten: "auflage", bohrung: "zentrierung", stift: "verdrehsicherung"}
    v = bv.vorschau(teil, fu.bezugssystem(teil, rollen))
    assert v.gesperrt == {"A": 3, "B": 2, "C": 1} and not v.offen
    nur = bv.vorschau(teil, fu.bezugssystem(teil, {bohrung: "zentrierung"}))
    achse = fu._geo(teil, bohrung)["richtung"]
    assert nur.gesperrt == {"A": 4} and sorted(b.art for b in nur.offen) == ["drehung", "verschiebung"]
    assert all(abs(abs(float(b.richtung @ achse)) - 1) < 1e-6 for b in nur.offen)


@pytest.fixture(scope="module")
def welle():
    """Getriebewelle des Beispiels (werkzeuge/welle.py) mit den Rollen aus kern.beispiele."""
    from programm.kern import beispiele
    from programm.ui.lader import lade_alles
    from tests.conftest import pfad
    erg = lade_alles(pfad(beispiele.WELLE))
    return SimpleNamespace(erg=erg, modell=erg.modell, rollen=dict(beispiele.welle_rollen(erg.modell)))


def test_welle_generator_und_rollen(welle):
    """Der Generator erzeugt die mitgelieferte Welle (gueltiger Koerper, gleiche Flaechen); alle Rollen des Beispiels
    finden ihre Flaeche."""
    from programm.kern import beispiele
    from werkzeuge import welle as gen  # Wurzel steht im Suchpfad (conftest)
    form = gen.welle()
    neu = SimpleNamespace(flaechen=[f for f in _flaechen(form)])
    assert len(neu.flaechen) == len(welle.modell.flaechen)
    assert sorted(beispiele.welle_rollen(neu)) == sorted(welle.rollen.items())
    assert len(welle.rollen) == len(beispiele.WELLE_ROLLEN)
    assert sorted(welle.rollen.values()).count("lagersitz") == 2


def _flaechen(form):
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        yield topods.Face(ex.Current())
        ex.Next()


def _rolle(welle, rolle, **bed):
    """Erstes Element der Rolle, dessen Geometrie die Bedingungen erfuellt (z. B. d=30)."""
    for i, r in sorted(welle.rollen.items()):
        g = fu._geo(welle.modell, i)
        if r == rolle and all(abs(g[{"d": "groesse"}.get(k, k)] - v) < 1e-6 for k, v in bed.items()):
            return i
    raise AssertionError(rolle)


def test_welle_gemeinsame_bezugsachse(welle):
    """Zwei koaxiale Lagersitze -> gemeinsame Bezugsachse A-B (A links, B rechts), die Lagerschulter des Festlagers
    (groesster Anschlag) wird C; offen bleibt nur die Drehung um die Achse."""
    from programm.kern import bezug_vorschau as bv
    m, rollen = welle.modell, welle.rollen
    lager = sorted((i for i, r in rollen.items() if r == "lagersitz"), key=lambda i: fu._geo(m, i)["mitte"][0])
    s = fu.bezugssystem(m, rollen)
    assert [(b.buchstabe, b.flaeche, b.element, b.gemeinsam) for b in s.bezuege[:2]] == \
        [("A", lager[0], "achse", "A-B"), ("B", lager[1], "achse", "A-B")]
    c = s.bezuege[2]
    assert c.buchstabe == "C" and c.element == "ebene" and abs(fu._geo(m, c.flaeche)["mitte"][0] - 70) < 1e-6
    assert [(r.name, r.stelle) for r in s.drf()] == [("A-B", 1), ("C", 2)] and s.offen == 1
    v = bv.vorschau(m, s)
    assert v.gesperrt == {"A": 4, "B": 0, "C": 1} and [b.art for b in v.offen] == ["drehung"]
    # von Hand: A und B auf die Lagersitze -> ebenfalls gemeinsame Achse
    hand = fu.bezugssystem(m, rollen, vorgabe={lager[1]: "B", lager[0]: "A"})
    assert [b.gemeinsam for b in hand.bezuege] == ["A-B", "A-B"] and hand.offen == 2
    # nur ein Lagersitz: einfache Bezugsachse A
    einer = fu.bezugssystem(m, {lager[0]: "lagersitz"})
    assert [(b.buchstabe, b.gemeinsam, b.freiheitsgrade) for b in einer.bezuege] == [("A", "", 4)]


def test_welle_tolerierung(welle):
    """Vorschlaege an der Welle: Lagersitze k6 mit Zylinderform IT5/2 und Rundlauf zu A-B, Lagerschulter Planlauf
    IT5, Dichtsitz h11 mit Rauheitshinweis, Nabensitze k6 mit Rundlauf, Passfedernut N9 mit Symmetrie, Ringnut
    h12/H13 mit Lage der tragenden Flanke zu C."""
    from programm.kern import iso286
    m, rollen = welle.modell, welle.rollen
    v = fu.tolerierung(m, rollen)
    pmi = [x.pmi for x in v]

    def an(i, typ):
        return [p for p in pmi if p.typ == typ and i in p.flaechen]
    lager = _rolle(welle, "lagersitz", d=30.0)
    assert [p.passung for p in an(lager, "Size_Diameter")] == ["k6"]
    assert an(lager, "Cylindricity")[0].wert == round(iso286.it(5, 30) / 2000, 4)
    lauf = an(lager, "CircularRunout")[0]
    assert [b.name for b in lauf.bezuege] == ["A-B"] and lauf.wert == iso286.it(5, 30) / 1000
    schulter = next(i for i, r in rollen.items() if r == "anschlag" and abs(fu._geo(m, i)["mitte"][0] - 70) < 1e-6)
    plan = an(schulter, "TotalRunout")[0]
    assert [b.name for b in plan.bezuege] == ["A-B"] and plan.wert < 0.02
    nabe_schulter = next(i for i, r in rollen.items() if r == "anschlag" and abs(fu._geo(m, i)["mitte"][0] - 78) < 1e-6)
    assert an(nabe_schulter, "TotalRunout")[0].wert > plan.wert  # kein Lager daneben: Anschlag IT8
    dicht = _rolle(welle, "dichtsitz")
    assert [p.passung for p in an(dicht, "Size_Diameter")] == ["h11"] and an(dicht, "CircularRunout")
    assert "drallfrei" in an(dicht, "Note")[0].nur_grafik_text
    for d in (20.0, 36.0):
        nabe = _rolle(welle, "nabensitz", d=d)
        assert [p.passung for p in an(nabe, "Size_Diameter")] == ["k6"] and an(nabe, "CircularRunout")
    nuten = sorted((i for i, r in rollen.items() if r == "passfedernut"), key=lambda i: fu._geo(m, i)["mitte"][0])
    for i, b in zip(nuten, (6.0, 10.0)):
        nut = fu.passfedernut(m, i)
        assert nut and not nut["nabe"] and abs(nut["breite"] - b) < 1e-6
        waende = set(nut["waende"])
        breite = next(p for p in pmi if p.typ == "Size_Thickness" and p.flaechen == waende)
        sym = next(p for p in pmi if p.typ == "Symmetry" and p.flaechen == waende)
        assert breite.passung == "N9" and abs(breite.nennwert - b) < 1e-6 and [x.name for x in sym.bezuege] == ["A-B"]
    ring = _rolle(welle, "sicherungsringnut")
    assert [p.passung for p in an(ring, "Size_Diameter")] == ["h12"]
    nut = fu.ringnut(m, ring)
    assert abs(nut["breite"] - 1.6) < 1e-6
    assert next(p for p in pmi if p.typ == "Size_Thickness" and p.flaechen == set(nut["flanken"])).passung == "H13"
    lage = next(p for p in pmi if p.typ == "Location_LinearDistance")
    assert abs(lage.nennwert - 16) < 1e-6 and lage.unten == 0 and lage.oben > 0 and schulter in lage.flaechen
    assert {p.name for p in pmi if p.art == BEZUG} == {"A", "B", "C"}
    # eigene Werte: Passung der Passfedernut (Breite) und Toleranz des Lagersitzes
    w = fu.tolerierung(m, rollen, werte={nuten[0]: {"passung": "P9"}, lager: {"toleranz": 0.005}})
    assert next(x.pmi for x in w if x.pmi.typ == "Size_Thickness" and x.pmi.flaechen == set(
        fu.passfedernut(m, nuten[0])["waende"])).passung == "P9"
    assert {x.pmi.wert for x in w if lager in x.pmi.flaechen and x.pmi.art == TOLERANZ} == {0.005}
    assert fu.startwerte(m, nuten[0], "passfedernut")["passung"] == "N9"
    assert fu.startwerte(m, schulter, "anschlag", rollen=rollen)["lage"] == plan.wert


def test_welle_zonen_und_step(welle, tmp_path):
    """Gemeinsamer Bezug A-B: Laufzone um die Achse beider Lagersitze, Schreiben als COMMON_DATUM_LIST und wieder
    gelesen als "A-B"; Callouts der Vorschlaege in der Ebene durch die Achse, ueber bzw. unter der Welle."""
    import numpy as np
    from programm.kern import pmi_erzeugen as pe, step_schreiben as sw, toleranzzone as tz
    from programm.ui.lader import lade_alles
    from tests.conftest import pfad
    m, rollen = welle.modell, welle.rollen
    pmi = [x.pmi for x in fu.tolerierung(m, rollen)]
    for k, p in enumerate(pmi, 1):
        p.quelle, p.nummer, p.step_id = "eigen", k, -3000 - k
    dicht = _rolle(welle, "dichtsitz")
    lauf = next(p for p in pmi if p.typ == "CircularRunout" and dicht in p.flaechen)
    achse = tz.bezugsachse(lauf, m, pmi)
    assert achse is not None and achse[4] == "A-B" and achse[2] > 70  # ueber beide Lagersitze
    assert tz.zone(lauf, m, 0.01, pmi) is not None
    neu = pe.ergaenze(pmi, {}, m, [])
    for g in neu.values():
        if any(fu._geometrie(m.flaechen[i])["art"] == "zylinder" for p in pmi if p.step_id in g.pmi_ids
               for i in p.flaechen) and g.platzhalter:
            assert abs(abs(float(g.ebene[3] @ np.array([0, 1.0, 0]))) - 1) < 1e-9  # Ebene XZ durch die Achse
    ziel = str(tmp_path / "welle.stp")
    b = sw.schreibe(pfad("getriebewelle.stp"), ziel, pmi, m)
    geschrieben = {p.nummer for p in pmi if p.art in (TOLERANZ, BEZUG)} - {n for n, _, _ in b.uebersprungen}
    assert lauf.nummer in geschrieben, b.uebersprungen
    gelesen = [p for p in lade_alles(ziel).pmi if p.typ == "CircularRunout"]
    assert gelesen and all([x.name for x in p.bezuege] == ["A-B"] for p in gelesen)
