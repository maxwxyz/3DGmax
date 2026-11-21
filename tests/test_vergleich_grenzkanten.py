"""Grenzkanten im Revisionsvergleich, mit ausgetauschten lokalen STEP-Nummern."""

import gzip
import re
from dataclasses import replace
from math import pi

import numpy as np
import pytest

from programm.kern import pmi_bericht, step_schreiben, vergleich, vergleich_grenzkanten as kanten, vergleich_pmi
from programm.kern.ausrichten import Ausrichtung
from programm.kern.pmi import Pmi
from programm.ui.lader import lade_alles
from tests.conftest import pfad


@pytest.fixture(scope="module")
def staende(tmp_path_factory):
    ordner = tmp_path_factory.mktemp("profilvergleich")
    quelle = ordner / "Original.stp"
    with gzip.open(pfad("nist_ctc_01_asme1_ap203.stp.gz"), "rb") as f:
        quelle.write_bytes(f.read())
    e = lade_alles(str(quelle))
    p = Pmi("toleranz", "ProfileOfSurface", wert=1.25, quelle="eigen", callout=3422,
            flaechen={e.modell.step_zu_flaeche[n] for n in (553, 554)})
    ergebnisse = {}
    for name, grenzen in (("Begrenzt", [["A", 2023], ["B", 2025]]), ("Ohne", []),
                          ("Vertauscht", [["A", 2025], ["B", 2023]])):
        ziel = ordner / (name+".step")
        bericht = step_schreiben.schreibe(str(quelle), str(ziel), [replace(p, bereichsgrenzen=grenzen)], e.modell)
        assert len(bericht.repariert) == 1 and not bericht.uebersprungen
        ergebnisse[name] = lade_alles(str(ziel))
    text = (ordner/"Begrenzt.step").read_text(encoding="ascii")
    offen = ordner/"Offene-Grenze.step"
    offen.write_text(text.replace("'end feature'", "'other feature'"), encoding="ascii")
    ergebnisse["Offen"] = lade_alles(str(offen))
    ziel = ordner/"Umnummeriert.step"
    ziel.write_text(re.sub(r"#(\d+)", lambda m: f"#{int(m[1])+50000}", text), encoding="ascii")
    ergebnisse["Umnummeriert"] = lade_alles(str(ziel))
    text = (ordner/"Vertauscht.step").read_text(encoding="ascii")
    ziel = ordner/"Nummern-wiederverwendet.step"
    ziel.write_text(re.sub(r"#(2023|2025)\b", lambda m: "#2023" if m[1] == "2025" else "#2025", text),
                    encoding="ascii")
    ergebnisse["Wiederverwendet"] = lade_alles(str(ziel))
    return ergebnisse


@pytest.mark.parametrize("a,b,anzahl", [("Begrenzt", "Ohne", 1), ("Ohne", "Begrenzt", 1),
                                        ("Begrenzt", "Vertauscht", 1), ("Begrenzt", "Wiederverwendet", 1),
                                        ("Begrenzt", "Umnummeriert", 0)])
def test_echter_step_vergleich_und_bericht(staende, a, b, anzahl):
    v = vergleich.vergleiche(staende[a], staende[b])
    assert len(v.aenderungen) == anzahl and vergleich.ist_gleich(v) == (anzahl == 0)
    if anzahl:
        befund, = v.aenderungen
        assert befund.kategorie == "pmi" and befund.status == "geaendert"
        feld, alt, neu, delta, _ = vergleich.spalten(befund)
        assert feld == "Begrenzter Profilbereich" and not delta
        assert (alt == "–") == (a == "Ohne") and (neu == "–") == (b == "Ohne")
        if b == "Wiederverwendet":
            assert befund.pmi_alt.bereichsgrenzen == befund.pmi_neu.bereichsgrenzen
            assert neu.count("geometrisch geändert") == 2
        assert alt != neu and all(s in pmi_bericht.vergleich_csv(v) for s in (feld, alt, neu))
    else:
        p, = [p for p in v.pmi if p.alt and p.alt.bereichsgrenzen]
        assert [n for _, n in p.neu.bereichsgrenzen] == [52023, 52025] and not p.felder


def test_doppelte_rahmen_behalten_ihre_enden_bei_anderer_reihenfolge(staende):
    alt = next(p for p in staende["Begrenzt"].pmi if p.bereichsgrenzen)
    neu = next(p for p in staende["Umnummeriert"].pmi if p.bereichsgrenzen)
    def umkehren(p):
        return replace(p, bereichsgrenzen=[[n, k] for (n, _), (_, k) in zip(p.bereichsgrenzen,
                                                                            reversed(p.bereichsgrenzen))])
    ergebnis = vergleich_pmi.vergleiche_pmi([alt, umkehren(alt)], [umkehren(neu), neu],
                      kantenschluessel=({2023:2023, 2025:2025}, {52023:2023, 52025:2025}))
    assert len(ergebnis) == 2 and all(x.status == "gleich" for x in ergebnis)


def test_ausrichtung_und_ungeklaerte_uebertragung(staende, monkeypatch):
    from OCC.Core.TopLoc import TopLoc_Location
    from scipy.spatial.transform import Rotation
    alt, neu = staende["Begrenzt"], staende["Umnummeriert"]
    matrix = np.eye(4)
    matrix[:3,:3] = Rotation.from_rotvec([.7, -.4, 1.9]).as_matrix()
    matrix[:3,3] = [89., -72., 13.]
    ausrichtung = Ausrichtung(matrix, "punkte", 0., 1.)
    lage = TopLoc_Location(ausrichtung.gp_trsf().Inverted())
    monkeypatch.setattr(neu.modell, "flaechen", [f.Moved(lage) for f in neu.modell.flaechen])
    abbildung = {i:i for i in range(len(alt.modell.flaechen))}
    links, rechts = kanten.grenzschluessel(alt, neu, ausrichtung, .01, abbildung)
    assert links == {2023:2023, 2025:2025} and rechts == {52023:2023, 52025:2025}
    lies = neu.modell.form_von_step
    monkeypatch.setattr(neu.modell, "form_von_step", lambda nr: None if nr == 52023 else lies(nr))
    schluessel = kanten.grenzschluessel(alt, neu, ausrichtung, .01, abbildung)
    paare = vergleich_pmi.vergleiche_pmi(alt.pmi, neu.pmi, kantenschluessel=schluessel)
    p, = [p for p in paare if p.alt and p.alt.bereichsgrenzen]
    assert p.status == "ungeklaert" and p.felder[0][0] == "grenzen_offen"


def test_kurvenverlauf_und_naht():
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCC.Core.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt
    def bogen(start, ende, phase=0.):
        achse = gp_Ax2(gp_Pnt(), gp_Dir(0,0,1), gp_Dir(np.cos(phase),np.sin(phase),0))
        return BRepBuilderAPI_MakeEdge(gp_Circ(achse, 20), start, ende).Edge()

    assert kanten._deckung(bogen(0, 2*pi), bogen(0, 2*pi, .7), .01)
    assert not kanten._deckung(bogen(0, pi), bogen(pi, 2*pi), .01)
    assert not kanten._deckung(bogen(0, 2*pi), bogen(0, pi), .01)


def test_deckungsgleiche_grenzen_brauchen_eindeutigen_flaechenpartner(monkeypatch):
    from types import SimpleNamespace
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCC.Core.gp import gp_Pnt
    def strecke():
        return BRepBuilderAPI_MakeEdge(gp_Pnt(10,0,0), gp_Pnt(0,0,0)).Edge()
    p = Pmi("toleranz", bereichsgrenzen=[["A", 1], ["B", 2]])
    alt, neu = SimpleNamespace(pmi=[p]), SimpleNamespace(pmi=[p])
    def kanten_am_rand(e):
        return ({1:strecke(), 2:strecke()}, {1:{10}, 2:{11}}) if e is alt else ({3:strecke()}, {3:{20}})
    monkeypatch.setattr(kanten, "_kanten", kanten_am_rand)
    lage = Ausrichtung(np.eye(4), "gleich", 0., 1.)
    assert kanten.grenzschluessel(alt, neu, lage, .01, {})[1] == {3:None}
    assert kanten.grenzschluessel(alt, neu, lage, .01, {20:11})[1] == {3:2}


def test_aufgeklappter_befund_im_pruefrundgang(staende, fenster):
    fenster.starte_vergleich({"alt":staende["Begrenzt"].pfad, "neu":staende["Vertauscht"].pfad,
                              "toleranz":.01, "suchweite":2.}, warten=True)
    panel = fenster.aenderungen
    assert fenster.vergleich is not None and panel.tabelle.rowCount() == 1
    assert panel.tabelle.item(0,3).text() == "Begrenzter Profilbereich"
    assert panel.tabelle.item(0,4).text() == "A (Kante #2023) ↔ B (Kante #2025)"
    assert panel.tabelle.item(0,5).text() == "A (Kante #2025) ↔ B (Kante #2023)"
    panel.pruefen_starten()
    assert panel.gewaehlte().pmi_neu.bereichsgrenzen == [["A", 2025], ["B", 2023]]


def test_unaufgeloester_step_bereich_bleibt_pruefbar(staende):
    v = vergleich.vergleiche(staende["Begrenzt"], staende["Offen"])
    a, = v.aenderungen
    assert a.status == "ungeklaert" and a.pmi_neu.bereichsgrenzen is None
    assert "? ↔ ?" in a.pmi_neu.wert_text() and "Zuordnung der Grenzkanten offen" in pmi_bericht.vergleich_csv(v)
    p, = vergleich_pmi.vergleiche_pmi([a.pmi_neu], [replace(a.pmi_neu, bereichsgrenzen=[])])
    assert p.status == "geaendert" and p.felder == [("bereichsgrenzen", "? ↔ ?", "–")]
