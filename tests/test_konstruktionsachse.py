"""Projizierte Gewindeachsen am FTC-10, Auswahl im Zusammenbau und gespeicherte Kette."""

import copy
import json

import numpy as np
import pytest
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.gp import gp_Ax1, gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from scipy.spatial.transform import Rotation

from programm.kern import baugruppe_mass as bm, kette3d, konstruktionsachse as ka, verbindung as vb
from programm.kern.pmi import BezugsRef, Pmi
from programm.ui.lader import lade_alles
from tests.conftest import pfad


@pytest.fixture(scope="module")
def ftc():
    return lade_alles(pfad("nist_ftc_10_asme1_ap242-e2.stp"))


def test_konstruktionskreis_nur_mit_angeschlossenen_mantellinien():
    kreis = BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(), gp_Dir(0, 0, 1)), 2.)).Edge()
    def linie(x, z0, z1):
        return BRepBuilderAPI_MakeEdge(gp_Pnt(x, 0., z0), gp_Pnt(x, 0., z1)).Edge()
    formen = [kreis, linie(2., -3., 2.), linie(2., 2., 7.), linie(2., 15., 18.), linie(2.1, -4., 10.)]
    for reihe in (formen, list(reversed(formen))):
        (o, d, laenge, r), = ka.kreisachsen(reihe, vollkreis=True)
        np.testing.assert_allclose(o, [0, 0, -3])
        assert (laenge, r) == pytest.approx((10., 2.))
    assert list(ka.kreisachsen([*formen, linie(-2., -4., 2.)], vollkreis=True)) == []
    offen = BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(), gp_Dir(0, 0, 1)), 2.), 0., 2.).Edge()
    assert list(ka.kreisachsen([offen, *formen[1:]], vollkreis=True)) == []


def test_ftc10_beide_gewinde_in_bewegter_wiederholter_instanz(ftc):
    basis = ftc.modell.flaechen
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(0, 0, 1)), .5)
    t.SetTranslationPart(gp_Vec(77, 34, -9))
    ort = TopLoc_Location(t)
    lage = np.eye(4)
    lage[:3, :3] = Rotation.from_rotvec([.5, -.1, .3]).as_matrix()
    lage[:3, 3] = [21., -10., 19.]
    def wand(i):
        return basis[i].Moved(ort)
    for i, x, z in ((238, 31.9, -30.), (239, 31.9, -30.), (240, 35.1, -20.), (241, 35.1, -20.)):
        quelle, merkmal, fehler = ka.projektionsziel(ftc.pmi, wand(i), basis[i], wand, lage)
        assert not fehler and quelle.step_id == 19580
        _, mitte, d, laenge = merkmal
        erwartet = gp_Pnt(x, 28.6, z).Transformed(t).Coord()
        np.testing.assert_allclose(mitte, lage[:3,:3] @ erwartet + lage[:3,3])
        np.testing.assert_allclose(d, lage[:3,:3] @ gp_Dir(0,1,0).Transformed(t).Coord(), atol=1e-12)
        assert laenge == pytest.approx(3.2)
    assert ka.projektionsziel(ftc.pmi, wand(242), basis[242], wand, lage)[2]
    fremd = lambda i: basis[i] if i == 10 else wand(i)
    assert ka.projektionsziel(ftc.pmi, wand(238), basis[238], fremd, lage)[2]


def test_projizierte_gewindeachse_bei_klickort_und_in_kette(ftc):
    formen = ftc.modell.flaechen
    original = next(p for p in ftc.pmi if p.step_id == 19580)
    p = copy.copy(original)
    p.bezuege = [BezugsRef("R")]
    bezug = Pmi("bezug", "Datum", name="R", flaechen={5})
    bg = vb.Baugruppe()
    lookup = lambda teil, i: formen[i]
    a = bm.Analyse(bg, [p, bezug], lookup, formen.__getitem__)
    # Eine definierte starre Bezugsebene isoliert den lokalen Anteil der Konstruktion.
    for y, breite in ((28.6, .8), (17., 5.8)):
        m = bm.Messgroesse(1, 1, 10, 1, 238, bm.PUNKT_ACHSE, punkt=[35.9, y, -30.],
                           konstruktions_pmi=19580, soll_min=0., soll_max=8.)
        e = a.berechne(m, formen[10], formen[238], proben=300)
        assert not e.hinweise and bm.bewertung(e, m)[0] == "gruen"
        assert (e.nenn, e.wc_min, e.wc_max) == pytest.approx((4., 4.-breite/2, 4.+breite/2))
        assert e.wc_min < e.mc_min < e.mc_max < e.wc_max
        k = a.als_kette3d(m, formen[10], formen[238])
        k = kette3d.von_dict(json.loads(json.dumps(kette3d.als_dict(k))))
        assert not k.hinweise and kette3d.schlussgroesse(k) == pytest.approx(4.)
        g, = [g for g in k.glieder if "#19580" in g.name]
        assert g.werte["z"].oben - g.werte["z"].unten == pytest.approx(breite)
    for pmi in ([], [p, p, bezug], [original, bezug]):
        analyse = bm.Analyse(bg, pmi, lookup, formen.__getitem__)
        assert analyse.berechne(m, formen[10], formen[238]).hinweise
    zusatz = copy.copy(p)
    zusatz.zone = "Diameter"
    assert ka.projektionsziel([p, zusatz], formen[238], formen[238], formen.__getitem__, np.eye(4))[2]
    p.material = "M"
    assert a.berechne(m, formen[10], formen[238]).hinweise
    # Nach einer Lageaenderung kann der Messpunkt genau auf die Achse fallen.
    m.punkt = [31.9, 20., -30.]
    e = a.berechne(m, formen[10], formen[238])
    assert e.nenn == pytest.approx(0.) and e.hinweise and not bm.bewertung(e, m)[0]
    k = a.als_kette3d(m, formen[10], formen[238])
    assert k.hinweise == e.hinweise and kette3d.schlussgroesse(k) == pytest.approx(0.)


def test_gewinde_im_zusammenbau_auswaehlen_und_projekt_laden(fenster, tmp_path):
    f = fenster
    f.lade(pfad("nist_ctc_01_asme1_ap242-e1.stp"), warten=True)
    f.modell_hinzufuegen(pfad("nist_ftc_10_asme1_ap242-e2.stp"), warten=True)
    z = f.zusammenbau
    zusatz, = f.erg.zusaetze
    modell = f.erg.modell
    ia = next(i for i in range(zusatz.erste_flaeche) if bm.ebene(modell.flaechen[i]) is not None)
    ib = zusatz.erste_flaeche + 238
    def auswahl(idx):
        for k in f.erg.baum.blaetter():
            form = vb.flaeche_im_teil(k.form, idx, modell)
            if form is not None:
                return form, k.nummer
        pytest.fail(f"Flaeche {idx} ohne Instanz")
    (fa, ta), (fb, tb) = auswahl(ia), auswahl(ib)
    f.ansicht.setze_auswahl([fa, fb], [ta, tb])
    punkt, _ = bm.ebene(fa)
    f.ansicht.klickpunkte[ta, ia] = tuple(punkt)
    z.am_punkt.setChecked(True)
    z.konstruktionsachse.setChecked(True)
    z.mass_knopf.click()
    m, = f.baugruppe.masse
    assert m.konstruktions_pmi == zusatz.id_versatz + 19580
    ergebnis = f.messgroessen_ergebnisse()[m.nummer]
    assert any(f"#{m.konstruktions_pmi}" in b.text and b.flaeche == ib for b in ergebnis.beitraege)
    assert "Konstruktionsachse" in z.masse.item(0, 1).text()
    assert ergebnis.hinweise  # Mehrteiliger Originalbezug und weitere Toleranzrahmen.
    kfenster = f.messgroesse_als_kette3d(m.nummer)
    assert kfenster.kette.hinweise == ergebnis.hinweise
    assert any(f"#{m.konstruktions_pmi}" in g.name for g in kfenster.kette.glieder)
    kfenster.close()
    pf = f.speichere_projekt(str(tmp_path / "Gewinde.3dgmax"))
    f.oeffne_projekt(pf, warten=True)
    wieder, = f.baugruppe.masse
    assert wieder == m
    neu = f.messgroessen_ergebnisse()[wieder.nummer]
    assert neu.hinweise == ergebnis.hinweise
    assert (neu.nenn, neu.wc_min, neu.wc_max) == pytest.approx((ergebnis.nenn, ergebnis.wc_min, ergebnis.wc_max))
