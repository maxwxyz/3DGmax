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


def test_verteilung_aus_messwerten(tmp_path):
    import numpy as np
    from programm.kern import kette_datei
    assert tk.messwerte_aus_text("10,01; 10,02 9,99") == [10.01, 10.02, 9.99]
    csv = "Nr;Soll;Ist\n1;10;10,012\n2;10;9,995\n3;10;10,004\n"
    assert tk.messwerte_aus_text(csv) == [10.012, 9.995, 10.004]  # letzte Spalte, Kopf entfaellt
    assert tk.messwerte_aus_text(csv, 1) == [1.0, 2.0, 3.0]
    rng = np.random.default_rng(1)
    werte = tuple(rng.normal(10.02, 0.01, 200))
    g = tk.Glied("a", 10, 10.1, 9.9, verteilung="messwerte", messwerte=werte)
    s = float(np.std(werte, ddof=1))
    assert g.gemessen and abs(g.sigma() - s) < 1e-12 and abs(g.wirk_versatz - (np.mean(werte) - 10)) < 1e-12
    assert abs(g.cpk() - (0.1 - abs(g.wirk_versatz)) / (3 * s)) < 1e-12
    e = tk.berechne([g] + [tk.Glied(n, 5, 5.05, 4.95) for n in "bcd"])
    assert abs(e.mitte - (25 + g.wirk_versatz)) < 1e-9 and abs(e.mc_mittel - e.mitte) < 0.005
    # zu wenige Werte: wie normal mit dem Cp der Kette
    assert tk.Glied("a", 10, 10.1, 9.9, verteilung="messwerte", messwerte=(10.0,)).sigma() - 0.2 / 6 < 1e-12
    # Verteilen laesst gemessene Glieder unveraendert
    neu = tk.verteile_toleranzen([g, tk.Glied("b", 5, 5.05, 4.95)], 0.1)
    assert (neu[0].hoechst, neu[0].mindest) == (10.1, 9.9)
    pfad = kette_datei.speichere(str(tmp_path / "m"), kette_datei.KettenDatei([g], 1.0))
    assert kette_datei.lade(pfad).glieder[0].messwerte == werte


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


def test_werkstoff_der_kette_und_je_glied():
    """Ketten von Hand: Vorgabe der ganzen Kette, Bauteil, eigener Werkstoff je Glied (in dieser Rangfolge); 2D/3D
    dehnen Laengen bzw. Verschiebungen, nicht Winkel; die linearisierte Uebernahme rechnet gleich."""
    from programm.kern import kette2d as k2, kette3d as k3
    from programm.kern.werkstoffe import laengenaenderung
    gl = [tk.Glied("a", 100, 100.1, 99.9), tk.Glied("b", 40, 40.1, 39.9, -1, teil="Deckel"),
          tk.Glied("c", 10, 10.1, 9.9, werkstoff="Aluminium"), tk.Glied("w", 5, 5.1, 4.9, waerme=False)]
    warm = tk.thermisch(gl, {tk.KETTE: 11.5, "Deckel": 16.0}, 70.0)
    assert [round(w.nenn - g.nenn, 6) for g, w in zip(gl, warm)] == \
        [round(laengenaenderung(a, g.nenn, 70.0), 6) for g, a in zip(gl, (11.5, 16.0, 23.0, 0.0))]
    k = k2.Kette2D([k2.Segment("Gestell", 80, 0.05, -0.05), k2.Segment("Hebel", 50, 0.1, -0.1, 120, 0.25, -0.25,
                                                                       werkstoff="Aluminium")], "x", "Stahl")
    k70 = k2.bei_temperatur(k, 70.0)
    assert k70.segmente[1].winkel == 120 and abs(k70.segmente[0].laenge - 80 - laengenaenderung(11.5, 80, 70)) < 1e-12
    linear = tk.berechne(tk.thermisch(k2.als_glieder(k), {}, 70.0)).nenn - tk.berechne(k2.als_glieder(k)).nenn
    assert abs(linear - (k2.schlussgroesse(k70) - k2.schlussgroesse(k))) < 1e-9
    assert k2.von_dict(k2.als_dict(k)).werkstoff == "Stahl"
    k3k = k3.Kette3D([k3.glied("Sockel", z=(20, 0.05, -0.05)), k3.glied("Arm", "Aluminium", x=(-100, 0.1, -0.1),
                                                                      rz=(90, 0.1, -0.1))], schluss="x",
                     werkstoff="Stahl", temperaturen=(-20.0, 70.0))
    k3w = k3.bei_temperatur(k3k, 70.0)
    assert k3w.glieder[1].werte["rz"].nenn == 90 and abs(k3.schlussgroesse(k3w) + 100 + 0.115) < 1e-9
    linear = tk.berechne(tk.thermisch(k3.als_glieder(k3k), {}, 70.0)).nenn - tk.berechne(k3.als_glieder(k3k)).nenn
    assert abs(linear - (k3.schlussgroesse(k3w) - k3.schlussgroesse(k3k))) < 1e-9
    zurueck = k3.von_dict(k3.als_dict(k3k))
    assert zurueck.glieder[1].werkstoff == "Aluminium" and zurueck.temperaturen == (-20.0, 70.0)


def test_raumkette_anforderung_ampel_freigabe():
    """2D/3D-Kette: Ampel aus dem linearen Verfahren mit dem nichtlinearen Anteil ausserhalb; Anforderung und
    Freigabe in Datei und Projekt."""
    from programm.kern import kette2d as k2, kette3d as k3
    k = k2.Kette2D([k2.Segment("a", 30, 0.1, -0.1), k2.Segment("b", 40, 0.1, -0.1, 90, 0.5, -0.5)], "abstand")
    e = tk.berechne(k2.als_glieder(k), anforderung=(49.0, 51.0))
    mc = k2.monte_carlo(k, 20_000)
    assert tk.bewertung_nichtlinear(e, (49.0, 51.0), mc)[0] == "gruen"
    assert tk.bewertung_nichtlinear(e, (49.95, 50.05), mc)[0] == "rot"
    assert tk.bewertung_nichtlinear(e, None, mc) == ("", "")
    k.anforderung, k.freigabe = (49.0, 51.0), {"geprueft": True, "name": "X", "datum": "2026-10-29", "kommentar": ""}
    z = k2.von_dict(k2.als_dict(k))
    assert z.anforderung == (49.0, 51.0) and z.freigabe["geprueft"]
    k3k = k3.Kette3D([k3.glied("a", z=(10, 0.1, -0.1))], anforderung=(9.5, 10.5), freigabe={"geprueft": True})
    assert k3.von_dict(k3.als_dict(k3k)).anforderung == (9.5, 10.5)


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


def test_glied_strecke_im_getriebe():
    from programm.kern import kette_datei
    from programm.kern.laden import lade_modell
    from tests.conftest import pfad
    k = kette_datei.lade(pfad("getriebe.3dgkette"))
    m = lade_modell(pfad("getriebe.stp"))
    start, ende = tk.glied_strecke(k.glieder[0], m)  # Waelzlager 12 mm, entlang X
    assert abs(abs(ende[0] - start[0]) - 12.0) < 1e-6 and abs(ende[1] - start[1]) < 1e-9
    assert tk.glied_strecke(tk.Glied("x", 1, 1, 1), m) is None


def test_plausibilitaet_theoretisch_muster_bezugsstellen():
    from types import SimpleNamespace
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from programm.kern import plausibilitaet as pl
    from programm.kern.pmi import BEZUG, MASS, TOLERANZ, BezugsRef, Pmi

    def flaechen(form):
        ex, out = TopExp_Explorer(form, TopAbs_FACE), []
        while ex.More():
            out.append(ex.Current())
            ex.Next()
        return out
    quader = flaechen(BRepPrimAPI_MakeBox(10, 10, 10).Shape())  # 0..5 Ebenen
    zyl = [flaechen(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, 0, 0), gp_Dir(0, 0, 1)), r, 5).Shape())[0]
           for x, r in ((20, 2), (30, 2), (40, 2.5))]
    modell = SimpleNamespace(flaechen=quader + zyl)  # Zylinder: 6, 7, 8
    a = Pmi(BEZUG, "Datum", "A", nummer=1, flaechen={0})
    pos = Pmi(TOLERANZ, "Position", wert=0.1, nummer=2, flaechen={6}, bezuege=[BezugsRef("A", 1)])
    lage = Pmi(MASS, "Location_LinearDistance", nennwert=20, oben=0.1, unten=-0.1, nummer=3, flaechen={0, 6})
    basis = Pmi(MASS, "Location_LinearDistance", nennwert=20, nummer=4, flaechen={0, 6}, modifikatoren=["Theoretisch"])
    falsch = Pmi(MASS, "Location_LinearDistance", nennwert=20, oben=0.1, unten=-0.1, nummer=5, flaechen={0, 6},
                 modifikatoren=["Theoretisch"])
    befunde = pl.theoretische_masse([a, pos, lage, basis, falsch], modell)
    assert [b.nummern for b in befunde] == [[2, 3], [5]]
    assert pl.theoretische_masse([a, pos, basis], modell) == []
    gleich = Pmi(MASS, "Size_Diameter", nennwert=4, oben=0.1, unten=0, nummer=6, flaechen={6, 7})
    verschieden = Pmi(MASS, "Size_Diameter", nennwert=4, oben=0.1, unten=0, nummer=7, flaechen={6, 7, 8})
    befunde = pl.muster([gleich, verschieden], modell)
    assert len(befunde) == 1 and befunde[0].nummern == [7] and "3" in befunde[0].text and "⌀5" in befunde[0].text
    # Bezugsstellen: Ebene A als Primaerbezug aus zwei Stellen, B ohne Verwendung
    stellen = [Pmi(BEZUG, "DatumTarget", n, nummer=10 + i, flaechen={0}) for i, n in enumerate(("A1", "A2", "B1"))]
    befunde = pl.bezugsstellen(stellen + [pos], modell)
    assert len(befunde) == 2 and "A" in befunde[0].text and "3" in befunde[0].text and "B1" in befunde[1].text
    pos.bezuege = [BezugsRef("B", 1), BezugsRef("A", 3)]
    befunde = pl.bezugsstellen(stellen + [pos], modell)  # B primaer aus einer Stelle, A tertiaer aus zwei genuegt
    assert len(befunde) == 1 and befunde[0].nummern == [12]


def test_korrelierte_glieder():
    import numpy as np
    a = [tk.Glied(n, 10, 10.1, 9.9, verteilung=v) for n, v in (("a", "normal"), ("b", "gleich"), ("c", "dreieck"),
                                                                   ("d", "normal"))]
    frei = tk.berechne(a)
    for g in a[:2]:
        g.gruppe, g.rho = "Teil 1", 1.0
    voll = tk.berechne(a)
    s = [g.sigma() for g in a]
    erwartet = 3 * np.sqrt((s[0] + s[1]) ** 2 + s[2] ** 2 + s[3] ** 2)
    assert abs(voll.rss - erwartet) < 1e-12 and voll.rss > frei.rss
    assert abs(voll.mc_std - voll.rss / 3) < 0.02 * voll.rss / 3  # Monte Carlo folgt der Korrelation
    assert voll.n_eff < frei.n_eff and abs(sum(voll.anteile) - 1) < 1e-12
    assert abs(voll.anteile[0] - s[0] * (s[0] + s[1]) / (voll.rss / 3) ** 2) < 1e-12
    # gegenlaeufige Richtung: Korrelation verkleinert die Streuung
    a[1].richtung = -1
    gegen = tk.berechne(a)
    assert gegen.rss < frei.rss
    # halbe Korrelation: rho_ij = Wurzel(rho_i rho_j)
    a[0].rho, a[1].rho, a[1].richtung = 0.25, 1.0, 1
    assert abs(tk.korrelation(a)[0, 1] - 0.5) < 1e-12 and tk.korrelation(a)[0, 2] == 0
    assert frei.rss < tk.berechne(a).rss < voll.rss


def test_betragsverteilungen():
    import numpy as np
    for art in ("betrag", "rayleigh"):
        g = tk.Glied("Ebenheit", 0, 0.05, 0.0, verteilung=art)
        x = g.ziehe(np.random.default_rng(3), 400_000)
        assert abs(np.mean(x <= 0.05) - 0.9973) < 0.001 and x.min() >= 0
        assert abs(x.mean() - (g.mitte + g.wirk_versatz)) < 2e-4 and abs(x.std() - g.sigma()) < 2e-4
        assert g.wirk_versatz < 0  # Mittelwert unter der Toleranzmitte
    e = tk.berechne([tk.Glied("a", 10, 10.1, 9.9), tk.Glied("Lauf", 0, 0.05, 0.0, -1, verteilung="betrag")])
    assert abs(e.mc_mittel - e.mitte) < 1e-3 and e.mitte > 10 - 0.025


def test_zusammenbau_321():
    """Quader auf eine Ecke aus drei Ebenen fangen: bestimmt, alle drei Verbindungen erfuellt, auch aus schiefer Lage."""
    import numpy as np
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from programm.kern import verbindung as vb

    def ebenen(form):
        out, ex = {}, TopExp_Explorer(form, TopAbs_FACE)
        while ex.More():
            m = vb.merkmal(ex.Current())
            out[tuple(np.round(m[2], 6)) + (round(float(m[1] @ m[2]), 6),)] = ex.Current()
            ex.Next()
        return out
    klotz = ebenen(BRepPrimAPI_MakeBox(10, 20, 30).Shape())
    winkel = ebenen(BRepPrimAPI_MakeBox(100, 100, 100).Shape())
    b = vb.Baugruppe()
    schief = vb.bewegung_klein(np.array([0.2, -0.1, 0.3, 40, 50, 60]))
    b.lagen[1] = schief
    teil = [(klotz[(0.0, 0.0, -1.0, 0.0)], 0), (klotz[(-1.0, 0.0, 0.0, 0.0)], 1), (klotz[(0.0, -1.0, 0.0, 0.0)], 2)]
    gegen = [(2, winkel[(0.0, 0.0, 1.0, 100.0)], 10), (2, winkel[(1.0, 0.0, 0.0, 100.0)], 11),
             (2, winkel[(0.0, 1.0, 0.0, 100.0)], 12)]
    out = b.verbinde_321(1, teil, gegen)
    assert len(out) == 3 and not b.verletzt() and len(b.freiheitsgrade(1)) == 0
    assert np.allclose(b.lage(1)[:3, 3], [100, 100, 100], atol=1e-6)  # Ecke des Klotzes auf der Ecke des Winkels
    assert "Ebenen" in b.verbinde_321(1, teil[:2] + teil[:1], gegen)  # zwei gleiche Richtungen


def test_kettenbild_im_getriebe():
    """Ein Klick zeigt die ganze Kette: Pfeile Spitze an Fuss auf eigenen Spuren, Farbe je Art, Schlussmass blau,
    im Planspiel geaenderte Glieder zusaetzlich grau mit dem Ist-Wert."""
    import copy
    from programm.kern import kette_datei
    from programm.kern.laden import lade_modell
    from tests.conftest import pfad
    k = kette_datei.lade(pfad("getriebe.3dgkette"))
    m = lade_modell(pfad("getriebe.stp"))
    linien = tk.kettenbild(k.glieder, m, "Spalt")
    texte = [li for li in linien if li[2]]
    assert len(texte) == len(k.glieder) + 1  # je Glied ein beschrifteter Pfeil, dazu das Schlussmass
    schluss = [li for li in linien if li[2] == "Spalt"][0]
    assert schluss[3] == tk.FARBEN["schluss"]
    summe = sum(g.richtung * g.faktor * g.nenn for g in k.glieder)
    assert abs(math.dist(schluss[0], schluss[1]) - abs(summe)) < 1e-6
    for g, li in zip(k.glieder, texte):  # Farbe nach Art, Text mit Abmass
        assert li[3] == tk.FARBEN[tk.glied_art(g)] and g.name in li[2]  # Name nennt das Mass schon
    plan = copy.deepcopy(k.glieder)
    plan[0].hoechst += 0.05
    grau = [li for li in tk.kettenbild(plan, m, ist=k.glieder) if li[3] == tk.FARBEN["ist"] and li[2]]
    assert len(grau) == 1 and grau[0][2].startswith("Ist")
    assert tk.abmass_text(tk.Glied("a", 10, 10.2, 9.9)) == "+0.2/−0.1"
    assert tk.abmass_text(tk.Glied("a", 10, 10.1, 9.9)) == "±0.1"


def test_bewertung_ampel_und_freigabe_in_datei(tmp_path):
    """Ampel nach dem anwendbaren Verfahren; manuelle Freigabe wird in der Kettendatei gespeichert."""
    from programm.kern import kette_datei
    glieder = [tk.Glied(f"g{i}", 10, 10.05, 9.95, 1 if i else -1) for i in range(6)]
    e = tk.berechne(glieder, anforderung=(39.0, 41.0))
    assert e.statistisch
    stufe, _ = tk.bewertung(e, (39.0, 41.0), (e.mitte - e.rss, e.mitte + e.rss))
    assert stufe == "gruen"
    e2 = tk.berechne(glieder, anforderung=(39.9, 40.1))
    assert tk.bewertung(e2, (39.9, 40.1), (e2.mitte - e2.rss, e2.mitte + e2.rss))[0] == "rot"
    assert tk.bewertung(e, None, (0, 1)) == ("", "")
    k = kette_datei.KettenDatei(glieder, freigabe={"geprueft": True, "name": "A", "datum": "2026-10-28",
                                                   "kommentar": "im Versuch nachgewiesen"})
    neu = kette_datei.lade(kette_datei.speichere(str(tmp_path / "k"), k))
    assert neu.freigabe["geprueft"] and neu.freigabe["kommentar"] == "im Versuch nachgewiesen"


def test_kostenoptimale_verteilung():
    """Billige grobe Verfahren bekommen weite, teure feine Verfahren enge Toleranzen; Ziel wird gehalten."""
    from programm.kern import fertigung as fe
    assert fe.it_grad(0.025, 40) == 7 and fe.it_grad(0.0001, 40) is None
    fein, grob = fe.grenzen("schleifen", 40)
    assert abs(fein - 0.011) < 1e-9 and abs(grob - 0.025) < 1e-9  # IT5 / IT7 bei 40 mm
    assert fe.kosten("drehen", 40, 0.1) < fe.kosten("drehen", 40, 0.04)
    glieder = [tk.Glied("Guss", 100, 100.5, 99.5, 1, verfahren="druckguss"),
               tk.Glied("Welle", 40, 40.05, 39.95, -1, verfahren="drehen"),
               tk.Glied("Buchse", 20, 20.05, 19.95, -1, verfahren="drehen"),
               tk.Glied("Ring", 10, 10.05, 9.95, -1, verfahren="schleifen"),
               tk.Glied("Lager", 18, 18.0, 17.88, -1, fest=True)]
    v = tk.verteile_kostenoptimal(glieder, ziel=0.6, statistisch=False)
    assert v.erreichbar and v.glieder[4].toleranz == glieder[4].toleranz  # festes Glied bleibt
    assert sum(g.toleranz * abs(g.faktor) for g in v.glieder) <= 0.6 + 1e-6
    for g in v.glieder[:4]:
        lo, hi = fe.grenzen(g.verfahren, g.nenn)
        assert lo - 1e-9 <= g.toleranz <= hi + 1e-9 and abs(g.mitte - glieder[v.glieder.index(g)].mitte) < 1e-9
    s = tk.verteile_kostenoptimal(glieder, ziel=0.6, statistisch=True)
    assert s.kosten_nachher <= v.kosten_nachher + 1e-9  # statistisch erlaubt weitere Toleranzen
    unmoeglich = tk.verteile_kostenoptimal(glieder, ziel=0.05, statistisch=False)
    assert not unmoeglich.erreichbar and unmoeglich.hinweise


def test_glied_pfeil_beim_ablaufen():
    """Ablaufen: Pfeil mit zwei Spitzenlinien am Ende in Wirkrichtung, Farbe nach Art."""
    from programm.kern import kette_datei
    from programm.kern.laden import lade_modell
    from tests.conftest import pfad
    k = kette_datei.lade(pfad("getriebe.3dgkette"))
    m = lade_modell(pfad("getriebe.stp"))
    g = k.glieder[0]  # Waelzlager, Richtung −
    linien = tk.glied_pfeil(g, m)
    assert len(linien) == 3 and linien[0][3] == tk.FARBEN["minus"] and linien[0][2]
    start, ende = np.array(linien[0][0]), np.array(linien[0][1])
    s = tk.glied_strecke(g, m)
    assert np.allclose(ende, s[0]) and np.allclose(start, s[1])  # − : Spitze am Anfang der Strecke
    assert all(np.allclose(li[0], ende) for li in linien[1:])  # Spitzenlinien gehen vom Pfeilende aus
    assert tk.glied_pfeil(tk.Glied("x", 1, 1, 1), m) == []
