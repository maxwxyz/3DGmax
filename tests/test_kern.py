"""Kernfunktionen an NIST-Modellen: Laden, Flaechenzuordnung, PMI, Ansichten."""

from programm.kern import p21
from programm.kern.ansichten import lies_ansichten
from programm.kern.pmi import BEZUG, MASS, TOLERANZ
from programm.kern.pmi_lesen import lies_pmi, lies_pmi_xcaf
from tests.conftest import pfad


def _art(liste, art):
    return [p for p in liste if p.art == art]


def test_p21_liest_komplexe_entitaeten():
    d = p21.lese(pfad("nist_ctc_01_asme1_ap242-e1.stp"))
    assert d.schema.startswith("AP242")
    e = d.entities[21]
    assert e.is_a("GEOMETRIC_TOLERANCE") and e.is_a("POSITION_TOLERANCE")
    assert e.args("GEOMETRIC_TOLERANCE")[0] == "Position.1"


def test_p21_dekodiert_sonderzeichen():
    assert p21._dekodiere("\\X2\\00E4\\X0\\") == "ä"
    assert p21._dekodiere("a\\X\\E4b") == "aäb"


def test_alle_flaechen_zugeordnet(ctc01, ftc10):
    for m in (ctc01, ftc10):
        assert len(m.flaechen) == len(m.datei.of_type("ADVANCED_FACE"))
        assert len(m.step_zu_flaeche) == len(m.flaechen)


def test_ctc01_masse(ctc01):
    masse = _art(lies_pmi(ctc01), MASS)
    texte = [p.wert_text() for p in masse]
    assert len(masse) == 12
    assert "⌀35 0/-0.2" in texte
    assert "⌀20 +0.05/-0.1" in texte
    assert "60° ±0.5" in texte
    assert "⌀34.8–35.2" in texte
    assert all(p.flaechen for p in masse)


def test_ctc01_toleranzen_und_bezuege(ctc01):
    liste = lies_pmi(ctc01)
    tol = {p.wert_text() for p in _art(liste, TOLERANZ)}
    assert "⌖ | 0.75 | A | B | C" in tol
    assert "⏥ | 0.2" in tol
    bez = {p.name: p for p in _art(liste, BEZUG)}
    assert set(bez) == {"A", "B", "C"}
    # B und C haengen in der Datei an SET_REPRESENTATION_ITEM (fehlt in OCCT)
    assert len(bez["B"].flaechen) == 2 and len(bez["C"].flaechen) == 2


def test_ftc10_modifikatoren(ftc10):
    tol = [p.wert_text() for p in _art(lies_pmi(ftc10), TOLERANZ)]
    assert len(tol) == 40
    assert "⌖ | ⌀1Ⓜ | A | B | C" in tol
    assert "⌖ | ⌀0.8 Ⓟ3.2 | D | E | B" in tol
    assert "⌖ | ⌀0.8 | D | E-F-G" in tol
    masse = [p.wert_text() for p in _art(lies_pmi(ftc10), MASS)]
    assert "⌀3.5 G6" in masse


def test_ftc07_zoll_grenzmass(ftc07):
    """Datei in Zoll; Mindestmass 0.012 in (OCCT liest hier faelschlich den Nennwert)."""
    radien = [p for p in _art(lies_pmi(ftc07), MASS) if p.typ == "Size_Radius" and p.grenzmass]
    assert any(abs(p.unten - 0.3048) < 1e-6 and abs(p.oben - 0.5588) < 1e-6 for p in radien)


def test_eigene_masse_umfassen_occt(ctc01, ftc10):
    """Jedes von OCCT gelesene Mass mit Wert ist auch im eigenen Leser."""
    for m in (ctc01, ftc10):
        eigen = {(round(p.nennwert, 4)) for p in _art(lies_pmi(m), MASS) if p.nennwert is not None}
        for p in lies_pmi_xcaf(m):
            if p.art == MASS and p.nennwert is not None and p.typ != "CommonLabel":
                assert round(p.nennwert, 4) in eigen


def test_ansichten(ftc10):
    pmi = lies_pmi(ftc10)
    ans = lies_ansichten(ftc10, pmi)
    assert len(ans) == 18
    mit_pmi = [a for a in ans if a.pmi_nummern]
    assert len(mit_pmi) >= 5
    for a in ans:
        assert abs(sum(c * c for c in a.richtung) - 1) < 1e-6


def test_hinweise_und_bezugsstellen(ftc10):
    from programm.kern.ansichten import _laengen_skala
    from programm.kern.pmi_lesen import ergaenze_hinweise
    from programm.kern.praesentation import lies_grafik
    pmi = lies_pmi(ftc10)
    stellen = [p.name for p in pmi if p.typ == "DatumTarget"]
    assert stellen == ["K1", "K2", "L1", "L2"]
    pmi = ergaenze_hinweise(pmi, lies_grafik(ftc10.datei, _laengen_skala(ftc10.datei)))
    hinweise = [p for p in pmi if p.art == "hinweis"]
    assert len(hinweise) == 9 and all(not p.semantisch for p in hinweise)
    assert [p.nummer for p in pmi] == list(range(1, len(pmi) + 1))


def test_ansicht_blickrichtung_lesbar(ftc10):
    """Kamera blickt entlang +z der Platzierung (sonst ist die Schrift der Annotationen gespiegelt)."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    box = Bnd_Box()
    brepbndlib.Add(ftc10.flaechen[0], box)
    for f in ftc10.flaechen:
        brepbndlib.Add(f, box)
    x0, y0, z0, x1, y1, z1 = box.Get()
    mitte = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    for a in lies_ansichten(ftc10):
        if a.pmi_ids:
            assert a.breite > 0 and a.abstand > 0
            zum_modell = [m - o for m, o in zip(mitte, a.ort)]
            assert sum(r * z for r, z in zip(a.richtung, zum_modell)) > 0, a.name  # Kamera blickt aufs Modell


def test_release_versionssprung():
    import importlib.util
    import os
    from tests.conftest import WURZEL
    spec = importlib.util.spec_from_file_location("release", os.path.join(WURZEL, "packaging", "release.py"))
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    assert release.naechste("0.1", "minor") == "0.2"
    assert release.naechste("0.9", "major") == "1.0"
    assert release.naechste("1.2", "patch") == "1.2.1"
    text = release.markdown({"releases": [{"version": "0.2", "date": "2026-10-26", "de": ["A"], "en": ["B"]}]}, "de")
    assert "## 0.2 (2026-10-26)" in text and "- A" in text


def test_normerkennung_asme_iso_rueckfall(ctc01, ftc10):
    from programm.kern import norm
    from tests.conftest import pfad
    assert norm.erkenne(ftc10.pfad).art == norm.ASME and "Y14" in norm.erkenne(ftc10.pfad).grund
    assert norm.erkenne(ctc01.pfad).art == norm.ASME  # nur Dateiname "asme1"
    n = norm.erkenne(pfad("varianten/ctc01_geo.stp"))
    assert n.art == norm.ISO and not n.erkannt  # kein Hinweis: ISO GPS
    assert norm.erkenne("x.stp", text="#1=DOCUMENT('ISO 1101','Geometric Tolerancing Standard','',#2);").art == norm.ISO
    assert norm.erkenne("teil_asme.stp", text="NOTE('ISO 8015 APPLIES')").art == norm.ISO  # Text schlaegt Dateiname


def test_norm_begriffe_huelle_und_regel():
    from programm.kern import pmi_bericht
    from programm.kern.pmi import MASS, TOLERANZ, Pmi
    t = Pmi(TOLERANZ, "ProfileOfSurface", wert=0.2)
    assert t.merkmal() == "Flächenform"
    t.norm = "asme"
    assert t.merkmal() == "Flächenprofil"
    d = Pmi(MASS, "Size_Diameter", nennwert=10.0, oben=0.1, unten=0.0)
    assert "ISO 8015" in d.huelle_text()
    d.norm = "asme"
    assert "Rule #1" in d.huelle_text()
    k = Pmi(TOLERANZ, "Concentricity", wert=0.1, nummer=1, norm="asme")
    assert any("2018" in b.text for b in pmi_bericht.pruefe([k]))
    k.norm = "iso"
    assert not any("2018" in b.text for b in pmi_bericht.pruefe([k]))


def test_merkmalsliste_ballone(ctc01):
    from programm.kern import merkmale
    from programm.kern.ansichten import _laengen_skala
    from programm.kern.pmi_lesen import lies_pmi
    from programm.kern.praesentation import lies_grafik
    pmi = lies_pmi(ctc01)
    liste = merkmale.liste(pmi)
    assert liste and all(m.pmi.art in ("mass", "toleranz") for m in liste)
    assert [m.ballon for m in liste] == list(range(1, len(liste) + 1))
    assert not any(p.art == "bezug" for p in (m.pmi for m in liste))
    text = merkmale.als_csv(liste)
    assert text.splitlines()[0].startswith("Ballon;Nr;Merkmal") and len(text.splitlines()) == len(liste) + 1
    grafik = lies_grafik(ctc01.datei, _laengen_skala(ctc01.datei))
    orte = [merkmale.anker(m.pmi, grafik) for m in liste]
    assert sum(o is not None for o in orte) >= len(liste) * 0.8
    tol = next(m for m in liste if m.pmi.art == "toleranz" and m.pmi.wert)
    assert tol.grenzen() == (tol.pmi.wert, 0.0)


def test_stueckliste_baugruppe():
    from programm.kern import stueckliste as sl
    from programm.ui.lader import lade_alles
    from tests.conftest import pfad
    e = lade_alles(pfad("baugruppe.stp"))
    liste = sl.positionen(e.baum)
    namen = {p.name: p for p in liste}
    assert set(namen) == {"Grundplatte", "Deckel", "Schraube M6x25", "Winkel"}
    assert namen["Schraube M6x25"].anzahl == 4 and len(namen["Schraube M6x25"].nummern) == 4
    assert namen["Winkel"].baugruppen == ["Halter"]
    assert abs(namen["Deckel"].volumen - 100 * 60 * 4) < 1e-6
    text = sl.als_csv(liste, 7.85)
    assert text.splitlines()[0].startswith("Pos;Benennung;Anzahl") and len(text.splitlines()) == 5


def test_analysen_entformung_kruemmung_wandstaerke():
    import math
    import numpy as np
    from programm.kern import analyse as an
    from programm.ui.lader import lade_alles
    from tests.conftest import pfad
    e = lade_alles(pfad("baugruppe.stp"))
    deckel = next(k.form for k in e.baum.blaetter() if k.name == "Deckel")
    # Quader 100 x 60 x 4: Deckflaeche +90°, Boden -90°, Seiten 0° (zu wenig Schraege)
    w = an.berechne(an.ENTFORMUNG, [deckel], (0, 0, 1)).alle()
    assert np.isclose(w.max(), 90) and np.isclose(w.min(), -90) and np.any(np.abs(w) < 1e-6)
    sk = an.skala_entformung(1.0)
    assert sk.farbe(0.0) == (0.90, 0.20, 0.20) and sk.farbe(45.0) != sk.farbe(-45.0)
    d = an.berechne(an.WANDSTAERKE, [deckel]).alle()
    f = d[np.isfinite(d)]
    assert len(f) and np.isclose(np.percentile(f, 10), 4.0, atol=1e-3)  # Dicke 4 mm
    schraube = next(k.form for k in e.baum.blaetter() if k.name.startswith("Schraube"))
    r = an.berechne(an.KRUEMMUNG, [schraube]).alle()
    endlich = r[np.isfinite(r)]
    assert np.any(np.isclose(endlich, 3.0)) and np.any(np.isinf(r))  # Schaft R3, Stirnflaechen eben
    assert an.skala_kruemmung().wert_text(math.inf) == "eben"


def test_iso286_grenzabmasse():
    from programm.kern import iso286
    from programm.kern.pmi import MASS, Pmi
    bekannt = {  # (Klasse, Nennmass): (oben, unten) in um
        ("H7", 2): (10, 0), ("g6", 2): (-2, -8), ("K7", 2): (0, -10), ("N7", 2): (-4, -14), ("P7", 2): (-6, -16),
        ("s6", 2): (20, 14), ("r6", 2): (16, 10), ("H7", 25): (21, 0), ("g6", 25): (-7, -20), ("f7", 25): (-20, -41),
        ("k6", 25): (15, 2), ("n6", 25): (28, 15), ("p6", 25): (35, 22), ("K7", 25): (6, -15), ("M7", 25): (0, -21),
        ("N7", 25): (-7, -28), ("P7", 25): (-14, -35), ("JS9", 25): (26, -26), ("G6", 3.5): (12, 4),
        ("H7", 450): (63, 0), ("g6", 450): (-20, -60), ("M7", 450): (0, -63), ("K7", 450): (18, -45),
        ("s6", 480): (292, 252), ("M6", 300): (-9, -41), ("H11", 4): (75, 0), ("c11", 25): (-110, -240),
    }
    for (klasse, d), soll in bekannt.items():
        assert iso286.abmasse_um(klasse, d) == soll, (klasse, d, iso286.abmasse_um(klasse, d))
    assert iso286.abmasse_um("H7", 600) is None and iso286.abmasse_um("Hx", 10) is None
    assert iso286.abmasse_um("H7/g6", 10) is None
    p = Pmi(MASS, "Size_Diameter", nennwert=20.0, passung="H7")
    assert p.grenzen() == (20.021, 20.0)


def test_formate_laden_und_netze():
    import numpy as np
    from programm.kern import abweichung, analyse, schnellinfo
    from programm.kern.baum import lies_baum
    from programm.kern.eigenschaften import berechne
    from programm.kern.laden import ist_netz, lade_modell
    from tests.conftest import pfad
    groesse = (120.0, 105.0, 37.0)  # Test-Baugruppe; Winkel liegt in der Unterbaugruppe bei y = 85..105
    for name, netz in (("igs", False), ("stl", True), ("obj", True), ("gltf", True), ("glb", True), ("3mf", True)):
        m = lade_modell(pfad(f"formate/baugruppe.{name}"))
        assert ist_netz(m) == netz, name
        assert np.allclose(berechne(m.form).groesse, groesse, atol=0.05), (name, berechne(m.form).groesse)
    winkel = next(k for k in lies_baum(lade_modell(pfad("baugruppe.stp"))).blaetter() if k.name == "Winkel")
    assert np.allclose(berechne(winkel.form).kleinst, (45, 85, 0))  # Lage der Unterbaugruppe beachtet
    stl = lade_modell(pfad("formate/baugruppe.stl"))
    info = dict(schnellinfo.info(stl.flaechen))
    assert info["art"] == "Netz" and any("mm²" in t for _, t in schnellinfo.info(stl.flaechen))
    w = analyse.berechne(analyse.ENTFORMUNG, [stl.form]).alle()
    assert np.isfinite(w).any()
    cad = lade_modell(pfad("nist_ctc_01_asme1_ap242-e1.stp"))
    k = abweichung.berechne(stl, lade_modell(pfad("formate/baugruppe.stl")))  # Netz gegen Netz: kein Absturz
    assert np.nanmax(np.abs(k.alle())) < 0.01
    assert cad.flaechen
