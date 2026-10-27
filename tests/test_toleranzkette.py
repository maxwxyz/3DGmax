"""Toleranzkette: Verteilungen je Glied und Anwendbarkeit des statistischen Ergebnisses (ohne Qt)."""

import math

import numpy as np
import pytest

from programm.kern import toleranzkette as tk


@pytest.mark.parametrize("art", ["normal", "dreieck", "trapez", "gleich"])
def test_sigma_passt_zur_stichprobe(art):
    g = tk.Glied("x", 10.0, 10.1, 9.9, verteilung=art, form=0.4)
    werte = g.ziehe(np.random.default_rng(3), 400_000)
    assert abs(werte.std() - g.sigma()) < 0.01 * g.sigma() and abs(werte.mean() - 10.0) < 1e-3
    if art != "normal":  # begrenzte Verteilungen bleiben im Toleranzfeld
        assert werte.min() >= 9.9 - 1e-12 and werte.max() <= 10.1 + 1e-12


def test_trapez_grenzfaelle_und_faktoren():
    t = 0.2
    dreieck = tk.Glied("d", 0, t / 2, -t / 2, verteilung="dreieck").sigma()
    gleich = tk.Glied("g", 0, t / 2, -t / 2, verteilung="gleich").sigma()
    assert math.isclose(tk.Glied("a", 0, t / 2, -t / 2, verteilung="trapez", form=0.0).sigma(), dreieck)
    assert math.isclose(tk.Glied("b", 0, t / 2, -t / 2, verteilung="trapez", form=1.0).sigma(), gleich)
    # Verteilungsfaktoren c = 3 sigma / (T/2) nach Scholz: Dreieck 1,225, gleich 1,732
    assert abs(3 * dreieck / (t / 2) - 1.2247) < 1e-3 and abs(3 * gleich / (t / 2) - 1.7321) < 1e-3


def test_anwendbarkeit_nach_wirksamen_beitragsleistern():
    vier = [tk.Glied(str(i), 10, 10.1, 9.9) for i in range(4)]
    e = tk.berechne(vier)
    assert abs(e.n_eff - 4) < 1e-9 and e.statistisch and "statistisch" in tk.anwendbar_text(e)
    # ein dominierendes Glied und drei kleine: zaehlt kaum mehr als eines
    dominiert = [tk.Glied("gross", 10, 10.5, 9.5)] + [tk.Glied(str(i), 10, 10.01, 9.99) for i in range(3)]
    e = tk.berechne(dominiert)
    assert 1 <= e.n_eff < 1.1 and not e.statistisch and "arithmetisch" in tk.anwendbar_text(e)
    assert tk.berechne([]).n_eff == 0
    csv = tk.als_csv(dominiert, e)
    assert "arithmetisch" in csv and "Wirksame Beitragsleister" in csv


def test_monte_carlo_mit_gemischten_verteilungen():
    glieder = [tk.Glied("a", 20, 20.1, 19.9, verteilung="gleich"), tk.Glied("b", 5, 5.05, 4.95, -1, verteilung="dreieck"),
               tk.Glied("c", 8, 8.06, 7.94, verteilung="trapez", form=0.5), tk.Glied("d", 2, 2.03, 1.97)]
    e = tk.berechne(glieder)
    assert abs(e.nenn - 25) < 1e-9 and abs(e.mc_std - e.rss / 3) < 0.02 * e.rss / 3
    assert e.wc_min < e.mc_min < e.mc_max < e.wc_max and abs(sum(e.anteile) - 1) < 1e-9


def test_alte_projekte_ohne_form():
    g = tk.Glied(**{"name": "x", "nenn": 1.0, "hoechst": 1.1, "mindest": 0.9, "verteilung": "gleich"})
    assert g.form == 0.5


def test_werkstoffe_stichworte_und_step():
    from programm.kern import p21, werkstoffe as ws
    from tests.conftest import pfad
    assert ws.bibliotheksname("S235JR") == "Stahl" and ws.bibliotheksname("EN AW-6082 T6") == "Aluminium"
    assert ws.bibliotheksname("1.4301") == "Nichtrostender Stahl" and ws.bibliotheksname("CuZn39Pb3") == "Messing"
    assert ws.bibliotheksname("C75S Federstahl") == "Stahl" and ws.bibliotheksname("Holz") is None
    stoffe = ws.werkstoffe_aus_step(p21.lese(pfad("getriebe.stp")))
    assert stoffe == {"Welle": "42CrMo4", "Zahnrad": "16MnCr5", "Distanzhülse": "EN AW-6082", "Wälzlager": "100Cr6",
                      "Sicherungsring": "C75S Federstahl"}  # Umlaute: OCCT schreibt UTF-8
    assert abs(ws.laengenaenderung(23.0, 100.0, 120.0) - 0.23) < 1e-12


def test_getriebe_kette_temperatur_stellglied_datei(tmp_path):
    import copy
    from programm.kern import kette_datei
    from tests.conftest import pfad
    k = kette_datei.lade(pfad("getriebe.3dgkette"))
    assert k.modell.endswith("getriebe.stp") and len(k.glieder) == 6
    assert [g.richtung for g in k.glieder] == [-1, -1, -1, 1, 1, -1]  # aus dem Schlussmass erzeugt
    e = tk.berechne(k.glieder, anforderung=k.anforderung)
    assert abs(e.nenn - 0.4) < 1e-9 and abs(e.wc_min) < 1e-9 and abs(e.wc_max - 1.1) < 1e-9  # Lehrbuch: 0 ... 1,1
    heiss = tk.berechne(tk.thermisch(k.glieder, k.alpha(), 100.0))
    # Stahl wirkt ueber 106,5 + 1,3 - 51 - 12 - 1,2 = 43,6 mm, die Alu-Huelse (43,2 mm) dagegen: Spiel kleiner
    erwartet = (11.5 * 43.6 - 23.0 * 43.2) * 1e-6 * 80
    assert abs((heiss.nenn - e.nenn) - erwartet) < 1e-6
    kuehl = tk.berechne(tk.thermisch(k.glieder, k.alpha(), 100.0, {"Welle": 60.0}))  # Welle kuehler
    assert kuehl.nenn < heiss.nenn
    g = copy.deepcopy(k.glieder)
    g[-1].stellglied = True
    lo, hi = tk.stellbereich(g, (0.05, 1.1))
    assert lo <= hi and abs(hi - lo - (1.05 - (1.1 - 0.06))) < 1e-9
    feder = tk.bereich_glied("Feder", 8.0, 6.0, -1, True)
    assert feder.mindest == 6.0 and feder.hoechst == 8.0 and feder.verteilung == "gleich" and feder.quelle == "bereich"
    ziel = kette_datei.speichere(str(tmp_path / "x"), kette_datei.KettenDatei(g, 1.33, (0.05, 1.1), (-20.0, 100.0),
                                                                               k.werkstoffe, k.modell))
    k2 = kette_datei.lade(ziel)
    assert ziel.endswith(".3dgkette") and k2.cp == 1.33 and k2.temperaturen == (-20.0, 100.0)
    assert k2.glieder[-1].stellglied and k2.glieder[0].flaechen == k.glieder[0].flaechen and k2.alpha() == k.alpha()


def test_richtungen_aus_schlussmass_mit_falschen_vorzeichen():
    from programm.kern import kette_datei
    from programm.kern.laden import lade_modell
    from tests.conftest import pfad
    k = kette_datei.lade(pfad("getriebe.3dgkette"))
    m = lade_modell(pfad("getriebe.stp"))
    durcheinander = [k.glieder[i] for i in (3, 0, 5, 1, 4, 2)]
    for g in durcheinander:
        g.richtung = 1
    lager, ring = k.glieder[0].flaechen[0], k.glieder[-1].flaechen[0]
    # Flaechen des Schlussmasses: rechte Lagerflaeche und linke Ringflaeche (je die naeher am Spalt)
    from programm.kern.toleranzkette import _ebene_oder_achse
    x = lambda i: float(_ebene_oder_achse(m.flaechen[i])[1][0])  # noqa: E731
    lager = max(k.glieder[0].flaechen, key=x)
    ring = min(k.glieder[-1].flaechen, key=x)
    reihe, hinweise = tk.richtungen_aus_schlussmass(durcheinander, m, lager, ring)
    assert not hinweise and [g.name[:2] for g in reihe] == ["M3", "M2", "M1", "M4", "M5", "M6"]
    assert [g.richtung for g in reihe] == [-1, -1, -1, 1, 1, -1]
    assert abs(tk.berechne(reihe).nenn - 0.4) < 1e-9


def test_stueckliste_mit_werkstoff_und_dichte():
    from programm.kern import p21, stueckliste as sl
    from programm.kern.baum import lies_baum
    from programm.kern.laden import lade_modell
    from tests.conftest import pfad
    m = lade_modell(pfad("getriebe.stp"))
    liste = sl.ergaenze_sachnummern(sl.positionen(lies_baum(m)), p21.lese(pfad("getriebe.stp")))
    p = {x.name: x for x in liste}
    assert p["Distanzhülse"].werkstoff == "EN AW-6082" and p["Welle"].werkstoff == "42CrMo4"
    # Alu-Huelse mit 2,7 g/cm3, nicht mit der angegebenen Dichte 7,85
    assert abs(p["Distanzhülse"].masse(7.85) - p["Distanzhülse"].volumen * 2.7e-6) < 1e-12
    z = sl.zeilen(liste, 7.85)
    assert z[0][3] and sl.SPALTEN[3] == "Werkstoff" and ";" in sl.als_csv(liste, 7.85)


def test_empfindlichkeit_bender_mittenverschiebung():
    a = tk.Glied("a", 10, 10.1, 9.9)
    b = tk.Glied("b", 5, 5.1, 4.9, -1, faktor=2.0)  # Hebel 2:1
    e = tk.berechne([a, b])
    assert abs(e.nenn - 0.0) < 1e-12 and abs((e.wc_max - e.wc_min) - (0.2 + 2 * 0.2)) < 1e-12
    assert abs(e.rss - 3 * math.sqrt((0.2 / 6) ** 2 + (2 * 0.2 / 6) ** 2)) < 1e-12
    assert abs(e.bender - 1.5 * e.rss) < 1e-12
    halb_wc = (e.wc_max - e.wc_min) / 2
    assert abs(tk.berechne([a, b], verschiebung=0.0).verschiebung - e.rss) < 1e-12  # ohne Verschiebung: RSS
    assert abs(tk.berechne([a, b], verschiebung=1.0).verschiebung - halb_wc) < 1e-12  # ganz verschoben: Worst Case
    assert e.rss < e.verschiebung < halb_wc


def test_toleranzen_verteilen():
    glieder = [tk.Glied(str(i), 10, 10.05, 9.95) for i in range(4)] + [tk.Glied("Lager", 12, 12.05, 11.95, fest=True)]
    # statistisch, gleiche Varianz: Schlussmass +-3 sigma = Ziel, festes Glied unveraendert
    neu = tk.verteile_toleranzen(glieder, 0.4, "varianz", True)
    e = tk.berechne(neu)
    assert abs(2 * e.rss - 0.4) < 1e-9 and abs(neu[-1].toleranz - 0.1) < 1e-12
    assert len({round(g.toleranz, 9) for g in neu[:4]}) == 1 and abs(glieder[0].toleranz - 0.1) < 1e-12  # Original bleibt
    # arithmetisch, proportional
    neu = tk.verteile_toleranzen(glieder, 0.6, "proportional", False)
    e = tk.berechne(neu)
    assert abs((e.wc_max - e.wc_min) - 0.6) < 1e-9 and all(abs(g.mitte - 10) < 1e-12 for g in neu[:4])
    assert tk.verteile_toleranzen(glieder, 0.05, "varianz", False)[0].toleranz == glieder[0].toleranz  # zu eng


def test_iso286_j_a_und_passungen():
    from programm.kern import iso286 as iso
    assert iso.abmasse_um("j6", 25) == (9.0, -4.0) and iso.abmasse_um("J7", 25) == (12.0, -9.0)
    assert iso.abmasse_um("a11", 25) == (-300.0, -430.0) and iso.abmasse_um("A11", 25) == (430.0, 300.0)
    assert iso.abmasse_um("j9", 25) is None and iso.abmasse_um("j6", 2) is None and iso.abmasse_um("a11", 450) is None
    art, hoechst, mindest = iso.passung("H7/g6", 25)
    assert art == iso.SPIEL and abs(hoechst - 0.041) < 1e-12 and abs(mindest - 0.007) < 1e-12
    assert iso.passung("H7/k6", 25)[0] == iso.UEBERGANG and iso.passung("H7/s6", 25)[0] == iso.UEBERMASS
    assert iso.passung("g6/H7", 25) is None and iso.passung("H7", 25) is None


def test_plausibilitaet_geschlossene_masskette():
    from types import SimpleNamespace
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.gp import gp_Pnt
    from programm.kern import plausibilitaet as pl
    from programm.kern.pmi import MASS, Pmi
    from programm.kern.verbindung import merkmal
    flaechen = []
    for x0, x1 in ((0, 10), (10, 25)):  # zwei Quader: Ebenen bei x = 0, 10, 25
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Core.TopExp import TopExp_Explorer
        ex = TopExp_Explorer(BRepPrimAPI_MakeBox(gp_Pnt(x0, 0, 0), x1 - x0, 5, 5).Shape(), TopAbs_FACE)
        while ex.More():
            m = merkmal(ex.Current())
            if m and m[0] == "ebene" and abs(abs(m[2][0]) - 1) < 1e-9:
                flaechen.append((round(m[1][0], 6), ex.Current()))
            ex.Next()
    lage = {}
    for x, f in flaechen:
        lage.setdefault(x, len(lage))
    modell = SimpleNamespace(flaechen=[f for x, f in sorted({x: f for x, f in flaechen}.items())])
    idx = {x: i for i, x in enumerate(sorted({x for x, _ in flaechen}))}
    def mass(nr, a, b, tol=True):
        return Pmi(MASS, "Location_LinearDistance", "", nummer=nr, nennwert=abs(b - a), flaechen={idx[a], idx[b]},
                   oben=0.1 if tol else None, unten=-0.1 if tol else None)
    befunde = pl.geschlossene_ketten([mass(1, 0, 10), mass(2, 10, 25), mass(3, 0, 25)], modell)
    assert len(befunde) == 1 and sorted(befunde[0].nummern) == [1, 2, 3] and "Hilfsmaß" in befunde[0].text
    assert pl.geschlossene_ketten([mass(1, 0, 10), mass(2, 10, 25), mass(3, 0, 25, tol=False)], modell) == []
    assert pl.geschlossene_ketten([mass(1, 0, 10), mass(2, 10, 25)], modell) == []
