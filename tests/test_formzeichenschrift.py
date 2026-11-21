"""Grafische Form- und Lauftoleranzen aus dem zollbasierten NIST CTC-05."""

import gzip
import re
from dataclasses import replace

import numpy as np
import pytest

from programm.kern import pmi_strichschrift as schrift
from programm.kern.pmi_freier_hinweis import _ansichten
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_bezugsbuchstaben import _gefuellt
from tests.test_hilfsmassschrift import _mit_fuellsatz
from tests.test_step_ap242 import _occt


# Sollwerte des semantischen CTC-05 AP242, Zielflaechen im grafischen AP203.
RAHMEN = {3170: ("Straightness", .127, "", 549), 3173: ("CircularityOrRoundness", .0508, "", 550),
          3175: ("CircularRunout", .635, "A-B", 484), 3176: ("TotalRunout", .381, "B", 486),
          3181: ("CircularRunout", .889, "A-B", 489), 3182: ("CircularRunout", .635, "A-B", 485),
          3183: ("Concentricity", .762, "A", 488), 3188: ("TotalRunout", .0508, "A", 515)}


def _mittelstriche(typ):
    phi = np.linspace(0, 2*np.pi, 65)
    kreis = np.column_stack((np.cos(phi), np.sin(phi)))
    if typ == "Straightness":
        return [np.array([(0,.5), (1,.5)])]
    if typ in ("CircularityOrRoundness", "Concentricity"):
        radien = [.5, .31] if typ == "Concentricity" else [.5]
        return [.5+r*kreis for r in radien]
    pfeil = [np.array([(0,0), (1,1)]), np.array([(.47,.77), (1,1), (.77,.47)])]
    if typ == "CircularRunout":
        return pfeil
    return [p/[1.66,1] for p in [*pfeil, *[p+[.66,0] for p in pfeil], np.array([(0,0),(.66,0)])]]


def _strichzeichen(text, e, nr, typ):
    g, d = e.grafik[nr], e.modell.datei
    o, x, y, _ = g.ebene
    pfade = schrift._pfade(g, g.ebene)
    l, b, r, t = schrift._zellen(pfade)[0]
    innen = [i for i, (a, _) in enumerate(pfade) if np.all(a.min(axis=0)>[l+.001,b+.001])
             and np.all(a.max(axis=0)<[r-.001,t-.001])]
    punkte = np.vstack([pfade[i][0] for i in innen])
    gruppe = d.get(d.get(nr).args()[2])
    refs = [str(ref) for i, ref in enumerate(gruppe.args()[1]) if i not in innen]
    n = 100*nr
    neu = []
    for zug in _mittelstriche(typ):
        ids = []
        for u,v in punkte.min(axis=0) + zug*np.ptp(punkte, axis=0):
            xyz = ",".join(f"{a:.10f}" for a in (o+u*x+v*y)/g.textfaktor)
            neu.append(f"#{n}=CARTESIAN_POINT('',({xyz}));")
            ids.append(f"#{n}")
            n += 1
        neu.append(f"#{n}=POLYLINE('',({','.join(ids)}));")
        refs.append(f"#{n}")
        n += 1
    text, anzahl = re.subn(rf"(#{gruppe.id}=GEOMETRIC_CURVE_SET\('[^']*',)\([^;]+;", r"\g<1>(" + ",".join(refs) + "));", text)
    assert anzahl == 1
    pos = text.rindex("ENDSEC;")
    return text[:pos] + "\n".join(neu) + "\n" + text[pos:]


def _fuellung_mit_zieltiefe(g):
    """Die axiale Lage der Originalmarke und beide Enden des raeumlichen Schaftes erhalten."""
    netze = _gefuellt(g)
    o, x, y, n = g.ebene
    geraden = [p for p in g.linien if len(p) == 2]
    tief = [p for p in g.linien if len(p) > 2 and min(abs((p-o)@n)) > .001]
    for i, (punkte, _) in enumerate(netze):
        xy = (punkte*g.textfaktor-o) @ np.column_stack((x,y))
        if i < len(geraden):
            ende = geraden[i]
            ab = (ende-o) @ np.column_stack((x,y))
            v = ab[1]-ab[0]
            t = np.clip((xy-ab[0]) @ v/(v@v), 0, 1)
            tiefe = (ende-o) @ n
            punkte += (tiefe[0] + t*np.diff(tiefe)[0])[:,None]*n/g.textfaktor
        else:
            for marke in tief:
                uv = (marke-o) @ np.column_stack((x,y))
                if np.all(xy >= uv.min(axis=0)-.001) and np.all(xy <= uv.max(axis=0)+.001):
                    punkte += np.mean((marke-o) @ n)*n/g.textfaktor
    return netze


@pytest.mark.parametrize("art", ["kontur", "strich", "fuellung"])
def test_ctc05_formzeichen_bis_step(fenster, tmp_path, art):
    quelle = pfad("nist_ctc_05_asme1_ap203.stp.gz")
    e = lade_alles(quelle)
    with gzip.open(quelle, "rt", encoding="ascii") as f:
        text = f.read()
    for nr, (typ, _, _, _) in RAHMEN.items():
        if art == "strich":
            text = _strichzeichen(text, e, nr, typ)
        if art == "fuellung":
            stil = e.modell.datei.get(nr).args("ANNOTATION_OCCURRENCE")[1][0].id
            text = _mit_fuellsatz(text, _fuellung_mit_zieltiefe(e.grafik[nr]), nr, stil, "fcf")
        if art != "kontur":
            ebene, = [p.id for p in e.modell.datei.of_type("ANNOTATION_PLANE")
                      if any(ref.id == nr for ref in p.args()[-1])]
            text, anzahl = re.subn(rf"#{ebene}=ANNOTATION_PLANE\([^;]+;", "", text)
            assert anzahl == 1
            text, anzahl = re.subn(rf"#{ebene}\b", f"#{nr}", text)
            assert anzahl == 1
    quelle = tmp_path / "Nur Grafik.step"
    quelle.write_text(text, encoding="ascii")
    fenster.lade(str(quelle), warten=True)
    quelle_erg = fenster.erg
    for nr in (3168, 3179, *RAHMEN):
        p = next(p for p in quelle_erg.pmi if p.step_id == nr)
        assert not p.semantisch
        fenster._pmi_befehl("semantisch", p)
        dialog = fenster._semantik_dialog
        assert not dialog.fehler(), (nr, dialog.fehler())
        if nr in RAHMEN:
            typ, wert, bezug, face = RAHMEN[nr]
            assert dialog.v.typ == typ and dialog.v.wert == pytest.approx(wert)
            assert dialog.v.bezug_text() == bezug
            assert {quelle_erg.modell.flaeche_zu_step[i] for i in dialog.flaechen} == {face}
        dialog._pruefen()
    projekt = fenster.speichere_projekt(str(tmp_path / "Kontrolle.3dgmax"))
    fenster.oeffne_projekt(projekt, warten=True)
    ziel = fenster.speichere_step_pmi(str(tmp_path / "Geprueft.step"), melden=False)
    assert ziel and not fenster._step_bericht.uebersprungen
    neu = lade_alles(ziel)
    assert _occt(quelle)[1:] == _occt(ziel)[1:]
    for nr, (typ, wert, bezug, face) in RAHMEN.items():
        a, b = quelle_erg.grafik[nr], neu.grafik[nr]
        p, = [p for p in neu.pmi if p.semantisch and p.step_id in b.pmi_ids]
        assert (p.typ, p.bezug_text()) == (typ, bezug) and p.wert == pytest.approx(wert)
        assert {neu.modell.flaeche_zu_step[i] for i in p.flaechen} == {face}
        assert ("Diameter" in p.modifikatoren) == (typ == "Concentricity")
        assert _ansichten(quelle_erg.modell.datei,nr) == _ansichten(neu.modell.datei,nr)
        assert (a.ebene is None) == (art != "kontur")
        assert bool(a.linien) != (art == "fuellung") and bool(a.dreiecke) == (art == "fuellung")
        for v,w in zip(a.linien, b.linien, strict=True):
            np.testing.assert_array_equal(v,w)
        for (v,t),(w,u) in zip(a.dreiecke,b.dreiecke,strict=True):
            np.testing.assert_array_equal(v,w)
            np.testing.assert_array_equal(t,u)


def test_unvollstaendige_formzeichen_bleiben_offen():
    from programm.kern.pmi_formzeichen import formzeichen
    y, x = np.mgrid[-52:53, -67:68]
    r = np.hypot(x, y)
    aussen = abs(r-35) < 1.1
    innen = abs(r-21) < 1.1
    assert formzeichen(aussen) == "○"
    assert formzeichen(aussen | innen) == "◎"
    for falsch in (aussen & ((abs(y)>2) | (x<0)), aussen | (innen & (x>0)),
                   aussen | ((abs(x-y)<1.5) & (r<37)), r<35,
                   (abs(y)==2) & (abs(x)<44)):
        assert not formzeichen(falsch)


def test_raumlinie_braucht_zusammenhaengenden_schaft_und_ziel():
    e = lade_alles(pfad("nist_ctc_05_asme1_ap203.stp.gz"))
    g = e.grafik[3181]
    assert schrift.lies_schrift(replace(g, ebene=None)) == "↗ .035 A-B"
    for falsch in ([g.linien[0], *g.linien[2:]], [*g.linien[:2], g.linien[2]+3*g.ebene[3], *g.linien[3:]],
                   [*g.linien, g.linien[2]+2*g.ebene[1]]):
        assert not schrift.lies_schrift(replace(g, ebene=None, linien=falsch))


def test_linienprofil_halbbogen_braucht_offene_fuesse():
    from programm.kern import pmi_strichschrift as schrift
    from programm.kern.pmi_formzeichen import formzeichen
    g = lade_alles(pfad("nist_ctc_02_asme1_ap203.stp.gz")).grafik[8712]
    phi = np.linspace(0, np.pi, 61)
    bogen = np.column_stack((np.cos(phi), np.sin(phi)))
    pfade = schrift._pfade(g, g.ebene)
    fach = schrift._zellen(pfade)[0]
    o, x, y, _ = g.ebene
    ort = np.array([(fach[0]+fach[2])/2, (fach[1]+fach[3])/2])
    r = .48*(fach[3]-fach[1])
    def glyph(zug):
        return o + (ort[0]+r*zug[:,0,None])*x + (ort[1]+r*(zug[:,1,None]-.5))*y
    innen = [i for i,(a,_) in enumerate(pfade) if np.all(a.min(axis=0)>fach[:2])
             and np.all(a.max(axis=0)<fach[2:])]
    assert innen
    linien = [v for i,v in enumerate(g.linien) if i not in innen]
    for ebenen in (None, g.ebene):
        bild = replace(g, linien=linien+[glyph(bogen)], ebene=ebenen)
        assert schrift.lies_schrift(bild) == "⌒ 0.25 A B C"
    for zuege in ([bogen[11:]], [bogen[:25], bogen[35:]], [bogen, bogen[[0,-1]]],
                  [bogen*[1,-1]], [bogen*[1,.56]]):
        p = [(zug, False) for zug in zuege]
        mask = schrift._bild(p, (-1.3,-.5,1.3,1.5), 65)
        assert formzeichen(mask) != "⌒"
