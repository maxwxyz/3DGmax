"""Bezugsbuchstaben der NIST CTC-02/03 mit Kontur, Strichschrift und Dreiecksfuellung."""

import gzip

import numpy as np
import pytest
from PySide6 import QtCore, QtGui

from programm.kern import pmi_strichschrift as schrift
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_hilfsmassschrift import _fuellgrafik, _mit_fuellsatz

BEZUEGE_03 = {3624: "C", 3628: "A", 3632: "B", 3635: "E", 3639: "F", 3643: "D"}
RAHMEN_03 = {3633: ("Position", 2.032, "DBC"), 3646: ("Position", .762, "DBC"),
             3647: ("Perpendicularity", .254, "E"), 3650: ("Position", 1.524, "DBC")}
BEZUEGE_02 = {8676: "F", 8683: "J", 8697: "G", 8704: "H", 8708: "D", 8715: "E"}
RAHMEN_02 = {8682: ("Perpendicularity", .05, "D"), 8690: ("Position", .05, "DE"),
             8691: ("ProfileOfSurface", .8, "GHJ"), 8698: ("ProfileOfSurface", .5, "DEF"),
             8685: ("ProfileOfSurface", .5, "DEⓂF"), 8702: ("ProfileOfSurface", .5, "DEFⓂ"),
             8705: ("ProfileOfSurface", .5, "DEⓂFⓂ")}


def _gefuellt(g):
    from dataclasses import replace
    pfade = schrift._pfade(g, g.ebene)
    o, x, y, _ = g.ebene
    # Die Originalkurven der schraegen Bezugszeichen sind um wenige Mikrometer windschief.
    planar = replace(g, linien=[o + p[:, :1]*x + p[:, 1:]*y for p, _ in pfade])
    linien = [i for i, (p, _) in enumerate(pfade) if len(p) == 2]
    ringe = {}
    for i, (p, _) in enumerate(pfade):
        if i not in linien:
            assert np.allclose(p[0], p[-1])
            ringe[i] = QtGui.QPolygonF([QtCore.QPointF(*punkt) for punkt in p])
    eltern = {i: [j for j, q in ringe.items() if j != i and
                  q.containsPoint(poly[0], QtCore.Qt.FillRule.OddEvenFill)] for i, poly in ringe.items()}
    gruppen = [[i, *(j for j, a in eltern.items() if i in a and len(a) == len(eltern[i])+1)]
               for i in ringe if len(eltern[i]) % 2 == 0]
    netze = _fuellgrafik(planar, gruppen, striche=linien)
    assert len(netze) == len(gruppen) + len(linien)
    return [(punkte/g.textfaktor, dreiecke) for punkte, dreiecke in netze]


def _strichbuchstaben(text, e, bezuege, rahmen):
    """Offene Mittellinien in die urspruenglichen Bezugsfelder der Zeichnung setzen."""
    import re
    zuege = {"D": [[(0,0), (0,1), (.44,1), (.80,.88), (1,.63), (1,.38), (.84,.13), (.45,0), (0,0)]],
             "E": [[(1,1), (0,1), (0,0), (1,0)], [(0,.52), (.87,.52)]],
             "F": [[(1,1), (0,1), (0,0)], [(0,.54), (.86,.54)]],
             "G": [[(.99,.84), (.78,1), (.3,1), (0,.77), (0,.21), (.25,0), (.78,0), (1,.18), (1,.46), (.55,.46)]],
             "H": [[(0,0), (0,1)], [(1,0), (1,1)], [(0,.5), (1,.5)]],
             "J": [[(1,1), (1,.26), (.83,.08), (.62,0), (.27,0), (.07,.1), (0,.28)]]}
    neue = []
    naechste = max(e.modell.datei.entities) + 1
    for cid in (*bezuege, *rahmen):
        zeichen = bezuege[cid] if cid in bezuege else "  " + rahmen[cid][2]
        if "Ⓜ" in zeichen:
            continue  # Die Originalrahmen mit eingekreisten Modifikatoren bleiben als Gegenprobe.
        g = e.grafik[cid]
        o, x, y, _ = g.ebene
        pfade = schrift._pfade(g, g.ebene)
        gruppe = e.modell.datei.get(e.modell.datei.get(cid).args()[2])
        refs = [r.id for r in gruppe.args()[1]]
        entfernt, neu = set(), []
        for z, (l, u, r, t) in zip(zeichen, schrift._zellen(pfade), strict=True):
            if z not in zuege:
                continue
            ind = [i for i, (p, _) in enumerate(pfade) if np.all(p.min(axis=0) > [l+.001, u+.001]) and
                   np.all(p.max(axis=0) < [r-.001, t-.001])]
            punkte = np.vstack([pfade[i][0] for i in ind])
            entfernt.update(refs[i] for i in ind)
            for zug in zuege[z]:
                ids = []
                for a, b in punkte.min(axis=0) + np.asarray(zug)*np.ptp(punkte, axis=0):
                    xyz = (o+a*x+b*y)/g.textfaktor
                    neue.append(f"#{naechste}=CARTESIAN_POINT('',({','.join(f'{v:.12f}' for v in xyz)}));")
                    ids.append(f"#{naechste}")
                    naechste += 1
                neue.append(f"#{naechste}=POLYLINE('',({','.join(ids)}));")
                neu.append(naechste)
                naechste += 1
        if entfernt:
            refs = [nr for nr in refs if nr not in entfernt] + neu
            text, n = re.subn(rf"(#{gruppe.id}=GEOMETRIC_CURVE_SET\('[^']*',)\([^;]+;",
                              r"\g<1>(" + ",".join(f"#{nr}" for nr in refs) + "));", text)
            assert n == 1
    pos = text.rindex("ENDSEC;")
    return text[:pos] + "\n".join(neue) + "\n" + text[pos:]


@pytest.mark.parametrize("schriftart", ["kontur", "fuellung", "strich"])
@pytest.mark.parametrize("modell", ["02", "03"])
def test_datum_und_rahmen_mit_originalgrafik(fenster, tmp_path, schriftart, modell):
    from programm.kern.pmi_freier_hinweis import _ansichten
    from tests.test_step_ap242 import _occt
    quelle = pfad(f"nist_ctc_{modell}_asme1_ap203.stp.gz")
    bezuege, rahmen = (BEZUEGE_03, RAHMEN_03) if modell == "03" else (BEZUEGE_02, RAHMEN_02)
    with gzip.open(quelle, "rt", encoding="ascii") as f:
        text = f.read()
    fuellung = schriftart == "fuellung"
    if schriftart == "strich":
        text = _strichbuchstaben(text, lade_alles(quelle), bezuege, rahmen)
    if fuellung:
        e = lade_alles(quelle)
        for nr in (*bezuege, *rahmen):
            stil = e.modell.datei.get(nr).args("ANNOTATION_OCCURRENCE")[1][0].id
            text = _mit_fuellsatz(text, _gefuellt(e.grafik[nr]), nr, stil, "datum" if nr in bezuege else "fcf")
    eingang = tmp_path / f"CTC{modell}.step"
    eingang.write_text(text, encoding="ascii")
    fenster.lade(str(eingang), warten=True)
    erg = fenster.erg
    if modell == "02":
        assert schrift.lies_schrift(erg.grafik[8680]) == "⟂ ⌀0.25 K"
    flaechen = {}
    for nr in (*bezuege, *rahmen):
        p = next(p for p in erg.pmi if p.step_id == nr)
        assert not p.semantisch
        fenster._pmi_befehl("semantisch", p)
        d = fenster._semantik_dialog
        assert not d.fehler(), (nr, d.fehler())
        if nr in bezuege:
            assert (d.v.art, d.v.name) == ("bezug", bezuege[nr])
        else:
            typ, wert, bez = rahmen[nr]
            assert d.v.typ == typ and d.v.wert == pytest.approx(wert)
            assert "".join(b.text() for b in d.v.bezuege) == bez
        flaechen[nr] = {erg.modell.flaeche_zu_step[i] for i in d.flaechen}
        assert flaechen[nr]
        d._pruefen()
    kopie = fenster.speichere_step_pmi(str(tmp_path / "Geprueft.step"), melden=False)
    assert kopie and not fenster._step_bericht.uebersprungen
    assert len(fenster._step_bericht.repariert) == len(bezuege) + len(rahmen)
    neu = lade_alles(kopie)
    assert _occt(eingang)[1:] == _occt(kopie)[1:]
    for nr in (*bezuege, *rahmen):
        a, b = erg.grafik[nr], neu.grafik[nr]
        p, = [p for p in neu.pmi if p.semantisch and p.step_id in b.pmi_ids]
        assert {neu.modell.flaeche_zu_step[i] for i in p.flaechen} == flaechen[nr]
        ansichten = _ansichten(erg.modell.datei, nr)
        assert ansichten and _ansichten(neu.modell.datei, nr) == ansichten
        if nr in bezuege:
            assert p.name == bezuege[nr]
        else:
            typ, wert, bez = rahmen[nr]
            assert p.typ == typ and p.wert == pytest.approx(wert) and "".join(b.text() for b in p.bezuege) == bez
            assert ("Diameter" in p.modifikatoren) == (nr in {3633, 3647, 3650, 8682, 8690})
        assert len(a.linien) == len(b.linien) and bool(a.linien) != fuellung
        assert len(a.dreiecke) == len(b.dreiecke) and bool(a.dreiecke) == fuellung
        for vor, nach in zip(a.linien, b.linien):
            np.testing.assert_array_equal(vor, nach)
        for (p1, t1), (p2, t2) in zip(a.dreiecke, b.dreiecke):
            np.testing.assert_array_equal(p1, p2)
            np.testing.assert_array_equal(t1, t2)
