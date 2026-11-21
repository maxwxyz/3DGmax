"""Profilrahmen mit zwei gezeichneten Endmarken und expliziten B-Rep-Kanten."""

import gzip
import re
from dataclasses import replace

import numpy as np
import pytest

from programm.kern import pmi_reparieren, pmi_zwischenbereich as bereich
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_hilfsmassschrift import _fuellgrafik, _mit_fuellsatz


def _fuellsatz(text, grafiken):
    g = grafiken[3422]
    gruppen = ((2,), (4, 5), (7,), (8,), (9,), (10,), (12, 13), (15, 16, 17),
               (19,), (23, 24), (25,), (26, 27, 28))
    netze = _fuellgrafik(g, gruppen, striche=(0, 1, 3, 6, 11, 14, 18, 20, 21, 22))
    text = _mit_fuellsatz(text, netze, 3422, 3455, "fcf")
    for nr, stil in ((3425, 3461), (3412, 3435)):
        note = grafiken[nr]
        netze = _fuellgrafik(note, ((2,), tuple(range(3, len(note.linien)))), striche=(0, 1))
        text = _mit_fuellsatz(text, netze, nr, stil, "note")
    return text


def _ohne_ebenen(text):
    for ebene, callout in ((3225, 3412), (3235, 3422), (3238, 3425)):
        text, n = re.subn(rf"#{ebene}\s*=\s*ANNOTATION_PLANE\([^;]+;", "", text)
        assert n == 1
        text, n = re.subn(rf"#{ebene}\b", f"#{callout}", text)
        assert n == 1
    return text


def _als_strichschrift(text, grafiken):
    """Eigenstaendige Linien fuer beide Randbuchstaben und die vier offenen Pfeilarme."""
    zeichen = {"A": [[(0,0), (.49,1), (1,0)], [(.18,.38), (.82,.38)]],
               "B": [[(0,0), (0,1), (.65,1), (.97,.84), (.94,.64), (.62,.50), (0,.50)],
                     [(.62,.50), (1,.32), (.96,.13), (.70,0), (0,0)]],
               "↔": [[(0,.5), (1,.5)], [(.19,1), (0,.5), (.19,0)], [(.81,1), (1,.5), (.81,0)]]}
    neu = []
    nr = 90000
    for callout, satz, quelle, behalten, zeile in (
            (3422, 4140, 3980, 23, ((23, "A"), (25, "↔"), (26, "B"))),
            (3425, 4143, 4053, 3, ((3, "A"),)), (3412, 4130, 3823, 3, ((3, "B"),))):
        g = grafiken[callout]
        o, x, y, _ = g.ebene
        refs = [f"#{k}" for k in range(quelle, quelle+behalten)]
        for i, buchstabe in zeile:
            box = (g.linien[i]-o) @ np.column_stack((x, y))
            for zug in zeichen[buchstabe]:
                ids = []
                for u, v in box.min(axis=0)+np.asarray(zug)*np.ptp(box, axis=0):
                    coords = ",".join(f"{a:.10f}" for a in o+u*x+v*y)
                    neu.append(f"#{nr}=CARTESIAN_POINT('',({coords}));")
                    ids.append(f"#{nr}")
                    nr += 1
                neu.append(f"#{nr}=POLYLINE('',({','.join(ids)}));")
                refs.append(f"#{nr}")
                nr += 1
        text, n = re.subn(rf"(#{satz}=GEOMETRIC_CURVE_SET\('[^']*',)\([^;]+;",
                          rf"\g<1>({','.join(refs)}));", text)
        assert n == 1
    pos = text.rindex("ENDSEC;")
    return text[:pos] + "\n".join(neu) + "\n" + text[pos:]


@pytest.mark.parametrize("schrift,ebene", [("kontur", True), ("fuellung", True), ("kontur", False),
                                         ("fuellung", False), ("strich", False), ("flaechenmenge", True)])
def test_profilbereich_mit_originalgrafiken(schrift, ebene, fenster, tmp_path):
    quelle = pfad("nist_ctc_01_asme1_ap203.stp.gz")
    with gzip.open(quelle, "rt", encoding="ascii") as f:
        text = f.read()
    gefuellt = schrift in ("fuellung", "flaechenmenge")
    if gefuellt:
        text = _fuellsatz(text, lade_alles(quelle).grafik)
    elif schrift == "strich":
        text = _als_strichschrift(text, lade_alles(quelle).grafik)
    if schrift == "flaechenmenge":
        # Eine Zuordnung zur separaten Bereichsdarstellung ersetzt die drei direkten Nutzungen.
        text, anzahl = re.subn(r"#(?:119|120|121)=GEOMETRIC_ITEM_SPECIFIC_USAGE\([^;]+;", "", text)
        assert anzahl == 3
        pos = text.rindex("ENDSEC;")
        text = (text[:pos] + "#100001=CONNECTED_FACE_SET('',(#554,#553));\n"
                "#100002=SHAPE_REPRESENTATION('',(#100001),#17160);\n"
                "#100003=GEOMETRIC_ITEM_SPECIFIC_USAGE('','PMI',#189,#100002,#100001);\n" + text[pos:])
    if not ebene:
        text = _ohne_ebenen(text)
    eingang = tmp_path / "Profilbereich.stp"
    eingang.write_text(text, encoding="ascii")
    fenster.lade(str(eingang), warten=True)
    erg = fenster.erg
    from programm.kern.pmi_freier_hinweis import _ansichten
    from tests.test_step_ap242 import _occt
    for nr, name in ((3417, "A"), (3427, "B"), (3414, "C"), (3422, "")):
        original = next(p for p in erg.pmi if p.step_id == nr)
        fenster._pmi_befehl("semantisch", original)
        d = fenster._semantik_dialog
        if name:
            assert d.v.art == "bezug" and d.v.name == name
        else:
            assert bool(erg.grafik[nr].dreiecke) == gefuellt
            assert bool(erg.grafik[nr].linien) != gefuellt
            assert d.v.bereichsgrenzen == [["A", 2023], ["B", 2025]]
            assert d.v.grenzgrafiken == [3425, 3412]
            assert [b.text() for b in d.v.bezuege] == ["A", "B", "C"]
            ziel = d.flaechen
            d.flaechen = {erg.modell.step_zu_flaeche[553]}
            assert d.fehler()
            d.flaechen = ziel
        assert not d.fehler()
        d._pruefen()
    ausgang = fenster.speichere_step_pmi(str(tmp_path / "Profilbereich mit Originalgrafik.stp"), melden=False)
    neu = lade_alles(ausgang)
    typen, fehler, _ = _occt(ausgang)
    assert fehler == _occt(eingang)[1] and "StepRepr_BetweenShapeAspect" in typen.values()
    p, = [p for p in neu.pmi if p.semantisch and p.art == "toleranz"]
    assert (p.typ, p.wert, p.bereichsgrenzen) == ("ProfileOfSurface", 1.25, [["A", 2023], ["B", 2025]])
    assert [b.text() for b in p.bezuege] == ["A", "B", "C"]
    assert {neu.modell.flaeche_zu_step[i] for i in p.flaechen} == {553, 554}
    assert "A ↔ B" in p.wert_text() and p.step_id in neu.grafik[3422].pmi_ids
    for nr in (3422, 3425, 3412):
        vorher, nachher = erg.grafik[nr], neu.grafik[nr]
        assert (vorher.ebene is not None) == (nachher.ebene is not None) == ebene
        assert bool(vorher.dreiecke) == gefuellt and bool(vorher.linien) != gefuellt
        for l, n in zip(vorher.linien, nachher.linien, strict=True):
            np.testing.assert_array_equal(l, n)
        for (p1, t1), (p2, t2) in zip(vorher.dreiecke, nachher.dreiecke, strict=True):
            np.testing.assert_array_equal(p1, p2)
            np.testing.assert_array_equal(t1, t2)
        ansichten = _ansichten(erg.modell.datei, nr)
        assert ansichten and _ansichten(neu.modell.datei, nr) == ansichten


def test_fehlende_oder_verschobene_grenzmarke(app):
    erg = lade_alles(pfad("nist_ctc_01_asme1_ap203.stp.gz"))
    original = next(p for p in erg.pmi if p.step_id == 3422)
    g = erg.grafik[3422]
    grafiken = dict(erg.grafik)
    note = grafiken.pop(3425)
    for ersatz in (None, replace(note, linien=[l+np.array([7., 8., 9.]) for l in note.linien])):
        if ersatz is not None:
            grafiken[3425] = ersatz
        v = pmi_reparieren.vorschlag(original, g, erg.modell)
        bereich.ergaenze(v, g, erg.modell, grafiken)
        assert not v.bereichsgrenzen and v.wert is None
    for fl, k in (([553, 554], [2023, 2024]), ([553, 554], [2023, 2023]), ([553, 554, 611], [2023, 2025])):
        assert not bereich.begrenzter_verband(erg.modell.datei, fl, k)

    ohne_pfeil = replace(g, linien=[l for i, l in enumerate(g.linien) if i != 25])
    assert bereich._bereichstext(ohne_pfeil) is None
    extra = replace(g, linien=[*g.linien, g.linien[25]+80*g.ebene[2]])
    assert bereich._bereichstext(extra) is None


def test_bereich_in_gedrehter_lage_und_mehrere_marken(app):
    from OCC.Core.gp import gp_Trsf
    from OCC.Core.TopLoc import TopLoc_Location
    from scipy.spatial.transform import Rotation
    erg = lade_alles(pfad("nist_ctc_01_asme1_ap203.stp.gz"))
    drehung = Rotation.from_rotvec([.8, -1.1, .4])
    versatz = np.array([45., -10., 91.])
    trsf = gp_Trsf()
    trsf.SetValues(*np.column_stack([drehung.as_matrix(), versatz]).ravel())

    def gedreht(g):
        return replace(g, ebene=None, linien=[drehung.apply(l) + versatz for l in g.linien])

    g = erg.grafik[3422]
    text, _, grenzen = bereich._bereichstext(gedreht(g))
    assert (text, grenzen) == ("⌓ 1.25 A B C", ("A", "B"))
    for nr, k, erwartet in ((3425, 2023, "A"), (3412, 2025, "B")):
        kante = erg.modell.form_von_step(k).Moved(TopLoc_Location(trsf))
        assert bereich._endzeichen(gedreht(erg.grafik[nr]), kante) == erwartet
    zweite = g.linien[2] + 3*g.ebene[3]
    assert bereich._bereichstext(gedreht(replace(g, linien=[*g.linien, zweite]))) is None
    schief = zweite.copy()
    schief[0] += g.ebene[3]
    assert bereich._bereichstext(gedreht(replace(g, linien=[*g.linien, schief]))) is None


def test_offene_pfeile_brauchen_schaft_und_vier_arme():
    from programm.kern.pmi_strichschrift import _bild
    arme = [np.array([[0,5], [40,5]]), np.array([[8,10], [0,5], [8,0]]),
            np.array([[32,10], [40,5], [32,0]])]

    def gelesen(zuege):
        return bereich._doppelpfeil(_bild([(p, False) for p in zuege], (0, 0, 40, 10), 5))

    assert gelesen(arme)
    assert not gelesen(arme[:2]) and not gelesen(arme[1:])
    assert not gelesen([*arme[:2], arme[-1][:2]])
    assert not gelesen([*arme, np.array([[21,0], [21,10]])])


def test_ziffer_acht_als_endmarke_ist_keine_b_grenze(app):
    erg = lade_alles(pfad("nist_ctc_01_asme1_ap203.stp.gz"))
    g = erg.grafik[3412]
    o, x, y, _ = g.ebene
    box = (g.linien[3]-o) @ np.column_stack((x, y))
    umriss = np.array([[.23,.52], [0,.70], [.04,.88], [.22,1], [.75,1], [.98,.86],
                       [1,.68], [.75,.51], [.23,.52], [.02,.35], [.01,.16], [.24,0],
                       [.75,0], [1,.16], [.98,.34], [.75,.51]])
    u, v = (box.min(axis=0) + umriss*np.ptp(box, axis=0)).T
    acht = replace(g, ebene=None, linien=[*g.linien[:3], o+u[:, None]*x+v[:, None]*y])
    assert bereich._endzeichen(acht, erg.modell.form_von_step(2025)) not in ("A", "B")
