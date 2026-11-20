"""PRC-Leser: Bitkodierung, Schema, Tessellation, Markups; NIST-STC-PDF (Download beim Test)."""

import os
import urllib.request
import zipfile

import numpy as np
import pytest

from programm.kern import prc
from programm.kern.prc_bits import BitLeser

# Double, dann UInt 12345, Int -77, String "abc" -- erzeugt mit dem PRC-Schreiber von Asymptote (LGPL)
VEKTOREN = [
    ('0', "673306cd81985898c0"),
    ('1', "04e660d9b0330b1318"),
    ('-1', "0ce660d9b0330b1318"),
    ('0.5', "eee9ccc1b36066162630"),
    ('3.1415926535897931', "db321fdd52892d8c4e660d9b0330b13180"),
    ('6.2831853071795862', "ad273306cd81985898c0"),
    ('0.001', "f4e660d9b0330b1318"),
    ('123.456', "c3ddd97c6b3fbebbce660d9b0330b13180"),
    ('-98765.432100000005', "ea1b6388e75bd3e1d862a73306cd81985898c0"),
    ('1.0000000000000001e+300', "ea4be97f24f31100bae7273306cd81985898c0"),
    ('2.2250738585072014e-308', "3474cc9ccc1b360661626300"),
    ('0.10000000000000001', "119ccb4d4e660d9b0330b13180"),
    ('25.399999999999999', "cb36609ccc1b360661626300"),
    ('1000', "efa9ccc1b36066162630"),
    ('9.9999999999999998e-13', "34711cbe67032df544673306cd81985898c0"),
    ('7', "bb90009ccc1b360661626300"),
    ('-0.001', "fce660d9b0330b1318"),
    ('42', "d2b0009ccc1b360661626300"),
    ('0.33333333333333331', "1ab5509ccc1b360661626300"),
    ('1.0000000000000002', "9a1006019ccc1b360661626300"),
    ('65536', "ea1b609ccc1b360661626300"),
    ('100', "c330009ccc1b360661626300"),
    ('12.5', "9330009ccc1b360661626300"),
    ('0.0070000000000000001', "ece6b21131937a6f33998366c0cc2c4c60"),
]


@pytest.mark.parametrize("wert,hexdaten", VEKTOREN)
def test_bitleser_vektoren(wert, hexdaten):
    b = BitLeser(bytes.fromhex(hexdaten))
    assert b.double() == float(wert)
    assert b.uint() == 12345
    assert b.int() == -77
    assert b.text() == "abc"


class _Schreiber:
    """Minimaler Bitschreiber fuer Testdaten (UInt, Bit)."""

    def __init__(self):
        self.bits = []

    def bit(self, w):
        self.bits.append(1 if w else 0)
        return self

    def uint(self, w):
        while w:
            self.bit(1)
            self.bits += [int(c) for c in f"{w & 0xFF:08b}"]
            w >>= 8
        return self.bit(0)

    def daten(self):
        b = self.bits + [0] * (-len(self.bits) % 8)
        return bytes(int("".join(map(str, b[i:i + 8])), 2) for i in range(0, len(b), 8))


def test_schema_liest_nur_neue_bloecke():
    # Block 7309 (<= Leserversion) wird uebersprungen, Block 15083 liest zwei UInts
    tokens = [19, 39, 1, 20, 7309, 0, 21, 20, 15083, 3, 3, 21, 21]
    s = _Schreiber().uint(5).uint(6).uint(99)
    b = BitLeser(s.daten())
    prc._Schema(b, {2: tokens}).anwenden(2)
    assert b.uint() == 99


def test_schema_bedingung_und_vatertyp():
    # If (1 == Integer) dann Zusatzdaten von Typ 802 (zwei UInts)
    typen = {2: [19, 39, 1, 20, 15083, 17, 37, 26, 1, 4, 6, 802, 21, 21],
             802: [19, 39, 1, 20, 15083, 3, 3, 21, 21]}
    b = BitLeser(_Schreiber().uint(1).uint(7).uint(8).uint(42).daten())
    prc._Schema(b, typen).anwenden(2)
    assert b.uint() == 42
    b = BitLeser(_Schreiber().uint(0).uint(42).daten())
    prc._Schema(b, typen).anwenden(2)
    assert b.uint() == 42


def test_dreiecke_aus_flaeche():
    # zwei Dreiecke (Normale, Punkt) x3, dann ein Faecher mit 4 Punkten, ein Streifen mit 4 Punkten
    ti = [0, 0, 0, 3, 0, 6] + [0, 3, 0, 6, 0, 9]
    ti += [0, 0, 0, 3, 0, 6, 0, 9]
    ti += [0, 0, 0, 3, 0, 6, 0, 9]
    tri, ende = prc._dreiecke_aus_flaeche(ti, 0, 0x2 | 0x4 | 0x8, [2, 1, 4, 1, 4], 0)
    assert ende == len(ti)
    assert tri[:2] == [[0, 3, 6], [3, 6, 9]]
    assert tri[2:4] == [[0, 3, 6], [0, 6, 9]]
    assert tri[4:] == [[0, 3, 6], [6, 3, 9]]


def test_flaechen_kanten():
    # zwei Kanten einer Schleife (die zweite schliesst sie), eine verdeckte Kante (zeichnet der Nachbar)
    draht = [99, 0, 3, 3, 6, 0, 9, 12]
    kanten = prc._flaechen_kanten(draht, 1, [2, 3 | 0x8000, 2 | 0x4000])
    assert [k.tolist() for k in kanten] == [[0, 1], [1, 2, 0]]


def test_markup_grafik_matrix_und_text():
    codes = [0x08000000 + 2, 16 + 6,  # Matrixblock mit zwei Elementen
             0, 6,  # Linienzug aus zwei Punkten
             0x04000000 | (14 << 21) | 1, 2, 0,  # Text 0, Breite/Hoehe
             0x08000000, 0,  # Blockende
             0x04000000 | (2 << 21), 9]  # ein Dreieck ausserhalb
    m = np.eye(4)
    m[:3, 3] = (10, 20, 30)
    werte = np.concatenate([m.T.ravel(), [0, 0, 0, 1, 0, 0], [5, 2], [0, 0, 0, 1, 0, 0, 0, 1, 0]])
    t = prc._markup_grafik(codes, werte, ["A"])
    assert np.allclose(t.linien[0], [[10, 20, 30], [11, 20, 30]])
    assert t.texte[0][0] == "A" and np.allclose(t.texte[0][1], (10, 20, 30))
    assert np.allclose(t.dreiecke[0][1], (1, 0, 0))


# --- NIST STC (US-Regierungswerk, gemeinfrei), wird beim Test geladen ---

NIST_URL = "https://www.nist.gov/document/nist-stc-pmi-v4"


@pytest.fixture(scope="session")
def stc06():
    ordner = os.environ.get("DG_TESTDATEN") or os.path.join(os.path.expanduser("~"), ".cache", "3dgmax")
    ziel = os.path.join(ordner, "STC_06.pdf")
    if not os.path.exists(ziel):
        os.makedirs(ordner, exist_ok=True)
        archiv = os.path.join(ordner, "nist-stc-pmi-v4.zip")
        try:
            if not os.path.exists(archiv):
                anfrage = urllib.request.Request(NIST_URL, headers={"User-Agent": "Mozilla/5.0 (3DGmax-Test)"})
                with urllib.request.urlopen(anfrage, timeout=120) as r, open(archiv + ".tmp", "wb") as f:
                    while block := r.read(1 << 20):
                        f.write(block)
                os.replace(archiv + ".tmp", archiv)
            with zipfile.ZipFile(archiv) as z:
                name = next(n for n in z.namelist() if n.endswith("STC_06.pdf"))
                with open(ziel, "wb") as f:
                    f.write(z.read(name))
        except Exception as e:  # noqa: BLE001 - ohne Netz ueberspringen
            pytest.skip(f"NIST-STC-Daten nicht verfuegbar: {e}")
    return ziel


def test_stc06_struktur(stc06):
    m = prc.lies_datei(stc06)
    st = m.strukturen[0]
    assert prc.einheit_mm(m) == pytest.approx(25.4)
    assert len(st.vorkommen) == 1 and st.vorkommen[0].name.startswith("nist_stc_06")
    koerper = [k for k in prc.koerper(m) if not k.hilfsgeometrie]
    assert len(koerper) == 1 and len(koerper[0].flaechen) == 144
    gr = prc.markup_grafik(m)
    assert len(gr) == 41
    assert {g.art for g in gr} >= {"Gdt", "Dimension"}
    namen = [a["name"] for a in prc.ansichten(m)]
    assert namen == ["MBD_A", "MBD_B", "MBD_C"]


def test_stc06_laden(stc06):
    from programm.ui.lader import lade_alles
    e = lade_alles(stc06)
    assert len(e.modell.flaechen) == 144
    assert len(e.farben) == 144
    # Randkanten aus den Drahtindizes der Tessellation (Netzflaechen haben sonst keine Kanten)
    assert len(e.modell.netz_kanten) == 144 and sum(map(len, e.modell.netz_kanten.values())) == 622
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer
    from programm.ui.ansicht3d import _kanten_von
    assert TopExp_Explorer(_kanten_von(e.modell.form, e.modell), TopAbs_EDGE).More()
    assert not TopExp_Explorer(e.modell.form, TopAbs_EDGE).More()
    assert len(e.pmi) == 41 and all(p.grafisch and not p.semantisch for p in e.pmi)
    arten = [p.art for p in e.pmi]  # aus den Markup-Arten abgeleitet (Texte sind nur Striche)
    assert arten.count("bezug") == 6 and arten.count("mass") == 13 and arten.count("toleranz") == 21
    assert {p.name for p in e.pmi if p.art == "bezug"} == set("ABCDEF")
    assert [a.name for a in e.ansichten] == ["MBD_A", "MBD_B", "MBD_C"]
    assert all(a.pmi_nummern for a in e.ansichten)
    # Markups liegen am Modell: die meisten Grafiken beruehren den (erweiterten) Modellquader
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    bb = Bnd_Box()
    brepbndlib.Add(e.modell.form, bb)
    lo, hi = np.array(bb.Get()[:3]) - 100, np.array(bb.Get()[3:]) + 100
    nah = [g for g in e.grafik.values() if g.grenzen() is not None
           and np.all(g.grenzen()[0] <= hi) and np.all(g.grenzen()[1] >= lo)]
    assert len(nah) >= 0.7 * len(e.grafik)


def test_stc06_im_fenster(fenster, stc06):
    fenster.lade(stc06, warten=True)
    assert fenster.erg is not None and len(fenster.erg.modell.flaechen) == 144
    assert fenster.pmi.tabelle.rowCount() == 41


def test_zeichnung_aus_netz():
    """Netzmodelle (STL, PRC) haben keine Kurven fuer HLR: eigene Projektion mit Tiefenpuffer."""
    import numpy as np
    from programm.kern import zeichnung
    # Wuerfel aus sechs Flaechen (je zwei Dreiecke): Flaechenraender, die Rueckkanten sind verdeckt
    p = np.array([[x, y, z] for x in (0, 10) for y in (0, 10) for z in (0, 10)], float)
    t = np.array([[0, 2, 3], [0, 3, 1], [4, 5, 7], [4, 7, 6], [0, 1, 5], [0, 5, 4],
                  [2, 6, 7], [2, 7, 3], [0, 4, 6], [0, 6, 2], [1, 3, 7], [1, 7, 5]])
    a = zeichnung.projiziere_netz([(p, t[i:i + 2]) for i in range(0, 12, 2)], (-1, -1, -1), (0, 0, 1))
    assert a.linien[zeichnung.SICHTBAR] and a.linien[zeichnung.VERDECKT]


def test_prc_textliteral_im_modell_und_semantikvorschlag():
    from programm.kern.pmi_lesen import ergaenze_hinweise
    from programm.kern.praesentation import prc_grafik

    lokal = np.eye(4)
    lokal[:3, 3] = (1., 2., 3.)
    # Der Textblock liegt in einer skalierenden Schreibmatrix innerhalb eines gedrehten Zoll-Teils.
    lokal[0, 0] = 1.5
    lokal[1, 1] = .5
    codes = [0x08000001, 18, 0x04000000 | (14 << 21) | 1, 2, 0, 0x08000000, 0]
    t = prc._markup_grafik(codes, np.r_[lokal.T.ravel(), 1.2, .1], ["⌀0.5 ±0.01"])
    teil = prc.Teil("A", markups=[prc.Markup(22, "Diameter.1", 2, 11, 0)])
    lage = np.array([[0., -1., 0., 4.], [1., 0., 0., 0.], [0., 0., 1., 1.], [0., 0., 0., 1.]])
    v = prc.Vorkommen("A.1", 0, -1, [], lage)
    st = prc.Dateistruktur(0, 0, {}, prc.Globals(), [teil], [v], 0, [t])
    modell = prc.PrcModell([st], einheit=25.4, einheit_cad=True)
    grafik = prc_grafik(modell)
    g = grafik[22]
    ph, = g.platzhalter
    assert not g.leer() and not g.linien and not g.dreiecke
    assert ph.text == "⌀0.5 ±0.01"
    np.testing.assert_allclose(ph.ursprung, np.array([2., 1., 4.]) * 25.4)
    np.testing.assert_allclose(ph.x, [0., 1., 0.])
    np.testing.assert_allclose(ph.y, [-1., 0., 0.])
    assert (ph.breite, ph.hoehe) == pytest.approx((1.8*25.4, .05*25.4))
    lo, hi = g.grenzen()
    np.testing.assert_allclose(lo, ph.ursprung + ph.y * ph.hoehe)
    np.testing.assert_allclose(hi, ph.ursprung + ph.x * ph.breite)
    p, = ergaenze_hinweise([], grafik)
    assert p.typ == "Size_Diameter" and not p.semantisch
    assert (p.nennwert, p.unten, p.oben) == pytest.approx((12.7, -.254, .254))


def test_stc06_ohne_schreibebene_an_unabhaengigen_massen(stc06):
    from programm.kern.pmi_reparieren import vorschlag
    from programm.ui.lader import lade_alles

    # Sollwerte aus den gleichnamigen Rahmen im semantischen NIST STC-06 AP242e3.
    erg = lade_alles(stc06)
    soll = {269: ("Position", .635, "M", ["A", "B", "C"]),
            271: ("Flatness", .254, "", []),
            274: ("Position", .381, "", ["C", "A", "B"]),
            275: ("ProfileOfSurface", .508, "", ["A", "B", "C"]),
            278: ("Position", .381, "", ["E", "A", "B"]),
            288: ("Flatness", .254, "", []),
            296: ("ProfileOfSurface", 1.016, "", ["A", "B", "C"]),
            299: ("Flatness", .254, "", [])}
    for nr, (typ, wert, material, bezuege) in soll.items():
        p = next(p for p in erg.pmi if p.step_id == nr)
        g = erg.grafik[nr]
        assert g.ebene is None and not g.platzhalter and not p.semantisch and p.wert is None
        neu = vorschlag(p, g, erg.modell)
        assert neu.ocr_text and neu.typ == typ and neu.wert == pytest.approx(wert)
        assert neu.material == material and [b.name for b in neu.bezuege] == bezuege
    p = next(p for p in erg.pmi if p.step_id == 298)
    assert not vorschlag(p, erg.grafik[298], erg.modell).ocr_text  # zusammengesetzter Profilrahmen


def test_ocr_schreibebene_gedrehter_rahmen_und_raeumliche_grafik():
    from dataclasses import replace
    from scipy.spatial.transform import Rotation
    from programm.kern.pmi_strichschrift import lies_schrift
    from programm.ui.lader import lade_alles
    from tests.conftest import pfad

    erg = lade_alles(pfad("nist_ctc_01_asme1_ap203.stp.gz"))
    g = erg.grafik[3415]
    d = Rotation.from_rotvec([.4, -.6, .8]).as_matrix()
    grafik = replace(g, ebene=None, linien=[p @ d.T + [315., -73., 104.] for p in g.linien])
    assert lies_schrift(grafik) == "⌖ 0.75 A B C"
    grafik.linien[0][0] += [10., 37., -43.]
    assert not lies_schrift(grafik)
