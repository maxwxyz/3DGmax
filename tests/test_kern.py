"""Kernfunktionen an NIST-Modellen: Laden, Flaechenzuordnung, PMI, Ansichten."""

import pytest

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
    assert text.splitlines()[0].startswith("Pos;Sachnummer;Benennung;Werkstoff;Anzahl") and len(text.splitlines()) == 5


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
    for name, netz in (("igs", False), ("stl", True), ("obj", True), ("gltf", True), ("glb", True), ("3mf", True),
                       ("ply", True), ("_ascii.ply", True)):
        m = lade_modell(pfad(f"formate/baugruppe{name}" if name.startswith("_") else f"formate/baugruppe.{name}"))
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


def test_qif_brep_und_pmi(qif_ctc01):
    """QIF 3.0 der NIST-Testfaelle (lokal unter daten/qif oder beim Test geladen, nicht im Repo)."""
    q = qif_ctc01
    from programm.kern.eigenschaften import berechne
    from programm.ui.lader import lade_alles
    e = lade_alles(q)
    w = berechne(e.modell.form)
    assert len(e.modell.flaechen) == 117 and abs(w.volumen - 14644823.3) < 5  # wie die STEP-Datei
    arten = [p.art for p in e.pmi]
    assert arten.count("toleranz") == 6 and arten.count("bezug") == 3 and arten.count("mass") >= 7
    pos = next(p for p in e.pmi if p.typ == "Position")
    assert pos.wert == 0.75 and pos.bezug_text() == "A|B|C" and pos.flaechen
    assert e.norm.art == "asme" and "QIF" in e.norm.grund
    # Grafische PMI (PMIDisplaySet) und gespeicherte Ansicht (ViewSet) wie in der STEP-Datei
    aus_datei = [g for g in e.grafik.values() if not g.erzeugt]
    assert len(aus_datei) == 23 and all(g.pmi_ids and g.ebene is not None for g in aus_datei)
    assert not [g for g in e.grafik.values() if g.erzeugt]  # alles hat eine Darstellung aus der Datei
    pos_grafik = next(g for g in aus_datei if pos.step_id in g.pmi_ids)
    assert [ph.text for ph in pos_grafik.platzhalter][:3] == ["⌖", "0.750", "A"]
    assert [a.name for a in e.ansichten] == ["MBD_0"] and len(e.ansichten[0].pmi_nummern) == 23
    import numpy as np
    from programm.kern.ansichten import lies_ansichten
    from programm.kern.laden import lade_step
    from tests.conftest import pfad
    step = lies_ansichten(lade_step(pfad("nist_ctc_01_asme1_ap242-e1.stp")))[0]
    assert np.allclose(e.ansichten[0].richtung, step.richtung, atol=1e-6)
    assert np.allclose(e.ansichten[0].oben, step.oben, atol=1e-6)


def test_zeichnung_hlr_svg_dxf(ctc01):
    from programm.kern import zeichnung as z
    vorne = z.projiziere(ctc01.form, (0, 1, 0), (0, 0, 1), "vorne")
    assert vorne.linien[z.SICHTBAR] and vorne.linien[z.VERDECKT]
    lo, hi = vorne.grenzen()
    assert abs((hi[0] - lo[0]) - 800) < 0.5 and abs((hi[1] - lo[1]) - 150) < 0.5  # Breite x Hoehe der Platte
    iso = z.blatt(ctc01.form, "iso")
    asme = z.blatt(ctc01.form, "asme")
    oben_iso = next(a for a in iso if a.name == "oben")
    oben_asme = next(a for a in asme if a.name == "oben")
    assert oben_iso.versatz[1] < 0 < oben_asme.versatz[1]  # Methode 1: Draufsicht unten, Methode 3: oben
    assert {a.name for a in iso} == {"vorne", "oben", "links", "iso"}
    assert {a.name for a in asme} == {"vorne", "oben", "rechts", "iso"}
    svg = z.als_svg(iso, "CTC-01")
    assert svg.startswith("<svg") and "stroke-dasharray" in svg
    dxf = z.als_dxf(iso)
    assert "LINE" in dxf and "VERDECKT" in dxf and dxf.rstrip().endswith("EOF")


def test_grafische_pmi_aus_semantik(ctc01):
    import numpy as np
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    from programm.kern import pmi_erzeugen
    from programm.kern.pmi_lesen import lies_pmi
    pmi = lies_pmi(ctc01)
    neu = pmi_erzeugen.ergaenze(pmi, {}, ctc01)  # so tun, als haette die Datei keine Darstellung
    mit_flaechen = [p for p in pmi if p.step_id and p.flaechen and p.art != "hinweis"]
    assert len(neu) == len(mit_flaechen) and all(g.erzeugt and g.linien and g.platzhalter for g in neu.values())
    # Stufe 2: Schreibebene, Text je Feld in der Ebene, Toleranzrahmen mit Feldern (Symbol, Wert, Bezuege)
    nach_id = {p.step_id: p for p in pmi}
    for g in neu.values():
        p = nach_id[next(iter(g.pmi_ids))]
        assert g.ebene is not None and all(ph.text and np.linalg.norm(ph.x) > 0.99 for ph in g.platzhalter)
        if p.art == "toleranz":
            assert len(g.platzhalter) == 2 + len(p.bezuege)
        if p.art == "bezug":
            assert g.dreiecke  # Bezugsdreieck
    # Rahmen ueberdecken sich nicht und liegen ausserhalb des Modellquaders
    box = Bnd_Box()
    brepbndlib.Add(ctc01.form, box)
    lo, hi = np.array(box.Get()[:3]), np.array(box.Get()[3:])
    rechtecke = []
    for g in neu.values():
        ecken = np.vstack([np.vstack([ph.ursprung, ph.ursprung + ph.x * ph.breite + ph.y * ph.hoehe])
                           for ph in g.platzhalter])
        rechtecke.append((ecken.min(axis=0), ecken.max(axis=0)))
        assert not (np.all(ecken.min(axis=0) < hi) and np.all(ecken.max(axis=0) > lo))
    for i, (a0, a1) in enumerate(rechtecke):
        for b0, b1 in rechtecke[i + 1:]:
            assert not (np.all(a0 < b1) and np.all(b0 < a1))
    assert pmi_erzeugen.ergaenze(pmi, neu, ctc01) == {}  # schon dargestellt: nichts Neues


def test_grafische_pmi_ebene_aus_ansicht():
    import numpy as np
    from programm.kern import pmi_erzeugen
    from programm.kern.ansichten import Ansicht
    a = Ansicht("A", 1, richtung=(0.0, 0.0, -1.0), oben=(0.0, 1.0, 0.0))
    x, y, n = pmi_erzeugen.ansicht_ebene(a)
    assert np.allclose(x, (1, 0, 0)) and np.allclose(y, (0, 1, 0)) and np.allclose(n, (0, 0, 1))
    # Seitenflaeche: Ebene XZ, oben = +Z, Normale zum Betrachter der Isoansicht (-Y), Text nicht gespiegelt
    x, y, n = pmi_erzeugen.modell_ebene((0.1, 0.9, 0.0))
    assert np.allclose(n, (0, -1, 0)) and np.allclose(y, (0, 0, 1)) and np.allclose(x, (1, 0, 0))


def test_toleranzzonen(ctc01):
    from programm.kern import toleranzzone as tz
    from programm.kern.pmi import TOLERANZ, Pmi
    from programm.kern.pmi_lesen import lies_pmi
    pmi = lies_pmi(ctc01)
    eben = next(p for p in pmi if p.typ == "Flatness")
    z = tz.zone(eben, ctc01, 2.0)
    assert z.art == "flaechen" and len(z.formen) == 2 * len(eben.flaechen) and z.faktor == 10.0 and z.breite == 0.2
    assert tz.zone(eben, ctc01).faktor == 1.0
    # Durchmesserzone an einer Bohrung: Zonenzylinder und die beiden Huellen der Flaeche (Mass + Lage)
    loch = next(p for p in pmi if p.typ == "Size_Diameter" and p.flaechen and p.grenzen()[0] is not None)
    hoechst, mindest = loch.grenzen()
    pos = Pmi(TOLERANZ, "Position", wert=0.1, modifikatoren=["Diameter"], flaechen=set(loch.flaechen))
    z = tz.zone(pos, ctc01, alle_pmi=pmi)
    assert z.art == "zylinder" and z.rollen.count(tz.ZONE) >= 1 and z.rollen.count(tz.HUELLE) >= 2
    assert f"⌀{mindest - 0.1:.4g}" in z.hinweise[-1] and f"⌀{hoechst + 0.1:.4g}" in z.hinweise[-1]
    # Masstoleranz: Huellen bei Hoechst- und Mindestmass
    z = tz.zone(loch, ctc01)
    assert z.art == "mass" and len(z.formen) == 2 * len(loch.flaechen)
    assert tz.zone(Pmi("mass", "Location_LinearDistance", nennwert=5, oben=0.1, unten=-0.1, flaechen={1}),
                   ctc01) is None


def test_toleranzzonen_unsymmetrisch(ctc01):
    """UZ: ISO verschiebt die Zonenmitte, ASME (U) gibt den Anteil ausserhalb des Materials an."""
    from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
    from programm.kern import toleranzzone as tz
    from programm.kern.pmi import TOLERANZ, Pmi
    eben = next(i for i, f in enumerate(ctc01.flaechen) if tz._achse([f]) is None)
    f = ctc01.flaechen[eben]
    for norm, erwartet in (("iso", (0.2, 0.0)), ("asme", (0.1, 0.1))):
        p = Pmi(TOLERANZ, "ProfileOfSurface", wert=0.2, modifikatoren=["UZ 0.1"], flaechen={eben}, norm=norm)
        assert tz.unsymmetrisch(p) == 0.1
        aussen, innen = tz._grenzen_aussen_innen(p, 0.2)
        assert (round(aussen, 6), round(-innen, 6)) == erwartet
        z = tz.zone(p, ctc01)
        assert len(z.formen) == 2 and z.hinweise
        abstaende = sorted(round(BRepExtrema_DistShapeShape(f, x).Value(), 6) for x in z.formen)
        assert abstaende == sorted(erwartet)


def test_toleranzzonen_material_projiziert_muster(ftc10, ftc07):
    from programm.kern import toleranzzone as tz
    from programm.kern.pmi_lesen import lies_pmi
    pmi = lies_pmi(ftc10)
    # Lochmuster mit M: je Bohrung Zone, Bonuszone und zwei Huellen; Huelle innen = virtuelle Grenze (MMC - t)
    m = next(p for p in pmi if p.material == "M" and p.wert and len(p.flaechen) > 2)
    z = tz.zone(m, ftc10, alle_pmi=pmi)
    n = len(tz._achsen([ftc10.flaechen[i] for i in m.flaechen]))
    assert n > 1 and z.rollen.count(tz.ZONE) == n and z.rollen.count(tz.BONUS) == n and z.hinweise[0]
    # Nulltoleranz mit M/L: die Zone besteht nur aus dem Bonus
    null = next(p for p in pmi if p.material and p.wert == 0 and p.flaechen)
    z = tz.zone(null, ftc10, alle_pmi=pmi)
    assert tz.ZONE not in z.rollen and tz.BONUS in z.rollen
    assert len(tz.zonen([null], ftc10, 1.0, pmi)) == 1
    # projizierte Zone liegt ausserhalb des Elements (ausserhalb des Materials)
    pmi7 = lies_pmi(ftc07)
    proj = next(p for p in pmi7 if p.zone == "Projected" and p.flaechen)
    z = tz.zone(proj, ftc07, alle_pmi=pmi7)
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.BRepGProp import brepgprop
    g = GProp_GProps()
    brepgprop.VolumeProperties(z.formen[0], g)
    mitte = g.CentreOfMass()
    assert not tz._im_material(ftc07, (mitte.X(), mitte.Y(), mitte.Z()))
    # alle Zonen gemeinsam: eine Ueberhoehung
    alle = tz.zonen(pmi, ftc10, 1.0, pmi)
    assert len(alle) > 30 and len({round(z.faktor, 6) for _, z in alle}) == 1


def test_toleranzzonen_mittelebene_kugel(ftc10):
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeSphere
    from OCC.Core.gp import gp_Pnt
    from programm.kern import toleranzzone as tz
    from programm.kern.laden import StepModell, _alle_flaechen
    from programm.kern.pmi import MASS, TOLERANZ, Pmi
    from programm.kern.pmi_lesen import lies_pmi
    pmi = lies_pmi(ftc10)
    # Symmetrie an einer Nut: Zone der abgeleiteten Mittelebene (zwei ebene Rechtecke, Abstand t)
    sym = next(p for p in pmi if p.typ == "Symmetry" and p.flaechen)
    z = tz.zone(sym, ftc10, alle_pmi=pmi)
    assert z.art == "mittelebene" and len(z.formen) == 2
    from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
    assert abs(BRepExtrema_DistShapeShape(*z.formen).Value() - sym.wert) < 1e-6
    # Richtungstoleranz an zwei Ebenen ohne Mass darauf: jede Flaeche einzeln (Flaechenzone, Richtung frei)
    senk = next(p for p in pmi if p.typ == "Perpendicularity" and not p.modifikatoren and len(p.flaechen) > 2)
    z = tz.zone(senk, ftc10, alle_pmi=pmi)
    assert z.art == "flaechen" and any("Richtungszone" in h or "orientation" in h.lower() for h in z.hinweise)
    # Kugelzone S⌀ um den Mittelpunkt einer Kugel, mit Raum der Kugelflaeche aus dem Kugelmass
    kugel = BRepPrimAPI_MakeSphere(gp_Pnt(1, 2, 3), 10.0).Shape()
    m = StepModell("k.stp", None, None, kugel, _alle_flaechen(kugel))
    m._baue_index()
    alle = [Pmi(MASS, "Size_SphericalDiameter", nennwert=20.0, oben=0.1, unten=-0.1, flaechen={0})]
    pos = Pmi(TOLERANZ, "Position", wert=0.4, modifikatoren=["SphericalDiameter"], flaechen={0})
    z = tz.zone(pos, m, alle_pmi=alle)
    assert z.art == "kugel" and z.rollen == [tz.ZONE, tz.HUELLE, tz.HUELLE]
    assert "19.5" in z.hinweise[-1] and "20.5" in z.hinweise[-1]


def test_toleranzzonen_bezugssystem(ftc10):
    """Bezugsverschiebung bei Ⓜ am Bezug, Koaxialitaet und Lauf um die Bezugsachse, Hierarchie Form < Richtung < Lage."""
    import copy
    import numpy as np
    from programm.kern import toleranzzone as tz
    from programm.kern.pmi import TOLERANZ, BezugsRef, Pmi
    from programm.kern.pmi_lesen import lies_pmi
    pmi = lies_pmi(ftc10)
    bezug_b = next(p for p in pmi if p.art == "bezug" and p.name == "B")  # Bohrung ⌀6 ±0.15
    pos = copy.deepcopy(next(p for p in pmi if p.typ == "Position" and "Diameter" in p.modifikatoren
                             and not p.material and p.bezuege and len(p.flaechen) == 2))
    pos.bezuege = [BezugsRef("A", 1), BezugsRef("B", 2, ["MaximumMaterialRequirement"]), BezugsRef("C", 3)]
    assert tz.bezugsverschiebung(pos, pmi) == [("B", "M", pytest.approx(0.3))]
    z = tz.zone(pos, ftc10, alle_pmi=pmi)
    assert tz.VERSCHIEBUNG in z.rollen and any("⌀0.3" in h for h in z.hinweise)
    # Koaxialitaet: Zylinder auf der Bezugsachse B (auch wenn das Element woanders liegt)
    achse_b = tz.bezugsachse(Pmi(TOLERANZ, "Coaxiality", bezuege=[BezugsRef("B", 1)]), ftc10, pmi)
    assert achse_b is not None and achse_b[4] == "B"
    koax = Pmi(TOLERANZ, "Coaxiality", wert=0.1, modifikatoren=["Diameter"], bezuege=[BezugsRef("B", 1)],
               flaechen=set(bezug_b.flaechen))
    z = tz.zone(koax, ftc10, alle_pmi=pmi)
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.BRepGProp import brepgprop
    g = GProp_GProps()
    brepgprop.VolumeProperties(z.formen[0], g)
    c = g.CentreOfMass()
    q = np.array([c.X(), c.Y(), c.Z()]) - achse_b[0]
    assert np.linalg.norm(q - achse_b[1] * (q @ achse_b[1])) < 1e-6 and any("Bezugsachse B" in h for h in z.hinweise)
    lauf = Pmi(TOLERANZ, "CircularRunout", wert=0.05, bezuege=[BezugsRef("B", 1)], flaechen=set(bezug_b.flaechen))
    z = tz.zone(lauf, ftc10, alle_pmi=pmi)
    assert z.art == "lauf" and len(z.formen) == 2 * len(bezug_b.flaechen)
    # Hierarchie: Geradheit liegt in der Profilzone derselben Flaeche; groessere Formtoleranz = Widerspruch
    gerade = next(p for p in pmi if p.typ == "Straightness")
    z = tz.zone(gerade, ftc10, alle_pmi=pmi)
    assert tz.HUELLE in z.rollen and any("PMI" in h for h in z.hinweise)
    zu_gross = copy.deepcopy(gerade)
    zu_gross.wert = 5.0
    assert any("5" in h and ("Widerspruch" in h or "contradiction" in h.lower())
               for h in tz.zone(zu_gross, ftc10, alle_pmi=pmi).hinweise)


def test_plausibilitaet(ctc01, ftc10):
    """Widersprueche und unvollstaendige Angaben (PLAN §8.22)."""
    import copy
    from programm.kern import plausibilitaet as pl, pmi_bericht
    from programm.kern.pmi import BezugsRef
    from programm.ui.lader import lade_alles
    pmi = lies_pmi(ftc10)
    # Hierarchie: Geradheit groesser als die Profiltoleranz derselben Flaeche
    gerade = copy.deepcopy(next(p for p in pmi if p.typ == "Straightness"))
    gerade.wert, gerade.nummer = 5.0, 999
    befunde = pl.hierarchie(pmi + [gerade], ftc10)
    assert any(999 in b.nummern and b.kategorie == "widerspruch" for b in befunde)
    assert pl.hierarchie(pmi, ftc10) == []
    # Werte: unsymmetrische Zone groesser als t, vertauschte Abmasse, unbekannte Passung
    profil = copy.deepcopy(next(p for p in pmi if p.typ == "ProfileOfSurface"))
    profil.modifikatoren = [f"UZ {profil.wert * 2}"]
    mass = copy.deepcopy(next(p for p in pmi if p.art == "mass" and p.oben is not None and not p.grenzmass))
    mass.oben, mass.unten = -0.1, 0.1
    passung = copy.deepcopy(mass)
    passung.passung, passung.oben, passung.unten = "Q99", None, None
    befunde = pl.werte([profil, mass, passung], ftc10)
    assert len(befunde) == 3 and {b.kategorie for b in befunde} == {"wert"} and "Q99" in befunde[-1].text
    # Bezugssystem: Sekundaerbezug parallel zum Primaerbezug
    pos = copy.deepcopy(next(p for p in pmi if p.typ == "Position" and p.bezuege))
    ebenen = [p.name for p in pmi if p.art == "bezug" and p.typ == "Datum" and p.name in ("A", "H")]
    pos.bezuege = [BezugsRef("A", 1), BezugsRef("A", 2)]
    assert any(b.kategorie == "bezug" and "A" in b.text for b in pl.bezugssystem(pmi + [pos], ftc10)) and ebenen
    # Geometrie: Nennmass passt nicht zur Bohrung (Variante mit Ø21)
    geo = lade_alles(pfad("varianten/ctc01_geo.stp"))
    befunde = pmi_bericht.pruefe(geo.pmi, geo.ansichten, geo.modell)
    assert any(b.kategorie == "geometrie" and "21" in b.text for b in befunde)
    assert not any(b.kategorie == "geometrie" for b in pmi_bericht.pruefe(lies_pmi(ctc01), None, ctc01))
    # Vollstaendigkeit: nicht tolerierte Flaechen als Flaechenmenge (ohne PMI-Nummer)
    frei = next(b for b in befunde if b.kategorie == "unvollstaendig")
    assert frei.flaechen and not frei.nummern
    assert not any(b.kategorie == "widerspruch" for b in pmi_bericht.pruefe(pmi, None, ftc10))


def test_allgemeintoleranzen(ctc01):
    from programm.kern import toleranzzone as tz
    from programm.kern.pmi import Pmi
    from programm.kern.pmi_lesen import lies_pmi
    assert tz.iso2768_laenge("m", 25) == 0.2 and tz.iso2768_laenge("f", 150) == 0.2
    assert tz.iso2768_laenge("v", 2) is None and tz.iso2768_ebenheit("K", 50) == 0.2
    a = tz.allgemein_aus_hinweisen([Pmi("hinweis", nur_grafik_text="TOLERANCES ISO 2768-mK")])
    assert (a.laenge, a.form, a.profil) == ("m", "K", None) and a.text() == "ISO 2768-mK"
    a = tz.allgemein_aus_hinweisen([Pmi("hinweis", nur_grafik_text="ISO 22081 - 0.5 A B C")])
    assert a.profil == 0.5
    assert tz.allgemein_aus_hinweisen([Pmi("hinweis", nur_grafik_text="DEBURR")]) is None
    pmi = lies_pmi(ctc01)
    z = tz.allgemein_zone(ctc01, pmi, tz.Allgemein("m", "K"))
    belegt = {i for p in pmi if p.art in ("mass", "toleranz") for i in p.flaechen}
    assert z.art == "allgemein" and set(z.rollen) == {tz.ALLGEMEIN}
    assert 0 < len(z.formen) <= 2 * (len(ctc01.flaechen) - len(belegt))
    z = tz.allgemein_zone(ctc01, pmi, tz.Allgemein(profil=0.5))
    frei = len(ctc01.flaechen) - len(belegt)
    assert z.breite == 0.5 and 0.9 * 2 * frei <= len(z.formen) <= 2 * frei  # Versatz an Kegelspitzen entfaellt


def test_toleranzkette():
    from programm.kern import toleranzkette as tk
    from programm.kern.pmi import MASS, Pmi
    a = tk.glied_von_pmi(Pmi(MASS, "Location_LinearDistance", nennwert=50.0, oben=0.1, unten=-0.1, nummer=1), +1)
    b = tk.glied_von_pmi(Pmi(MASS, "Location_LinearDistance", nennwert=20.0, oben=0.05, unten=-0.05, nummer=2), -1)
    c = tk.glied_von_pmi(Pmi(MASS, "Size_Diameter", nennwert=10.0, passung="h7", nummer=3), -1)  # 0/-0.015
    e = tk.berechne([a, b, c])
    assert abs(e.nenn - 20.0) < 1e-12
    assert abs(e.wc_max - (50.1 - 19.95 - 9.985)) < 1e-9 and abs(e.wc_min - (49.9 - 20.05 - 10.0)) < 1e-9
    assert abs(e.rss - (0.1 ** 2 + 0.05 ** 2 + 0.0075 ** 2) ** 0.5) < 1e-9
    assert e.mc_min > e.wc_min and e.mc_max < e.wc_max and abs(e.mc_mittel - e.mitte) < 1e-3
    assert tk.glied_von_pmi(Pmi("toleranz", "Flatness", wert=0.1)) is None
    assert "Worst Case max" in tk.als_csv([a, b, c], e)
    # Cp und Verteilung je Glied, Anteile
    a.cp, b.verteilung = 2.0, "gleich"
    e2 = tk.berechne([a, b, c])
    s = [0.2 / 12, 0.1 / (2 * 3 ** 0.5), 0.015 / 6]
    assert abs(e2.rss - 3 * sum(x * x for x in s) ** 0.5) < 1e-9
    assert abs(sum(e2.anteile) - 1) < 1e-9 and e2.anteile[1] == max(e2.anteile)
    assert e2.wc_min == e.wc_min and e2.mc_min > e2.wc_min


def test_toleranzkette_aus_flaechen():
    """FTC-10: Glieder aus Flaechen, Richtung aus der Geometrie, PMI auch bei Mustern, sonst ISO 2768."""
    from programm.kern import toleranzkette as tk
    from programm.ui.lader import lade_alles
    erg = lade_alles(pfad("nist_ftc_10_asme1_ap242-e2.stp"))
    g, r, h = tk.kette_aus_flaechen(erg.modell, [181, 187, 183, 185], erg.pmi, "m", lagetoleranzen=False)
    assert [x.pmi_nummer for x in g] == [6, 0, 5] and [x.quelle for x in g] == ["pmi", "allgemein", "pmi"]
    assert [x.richtung for x in g] == [1, -1, 1] and abs(abs(r[0]) - 1) < 1e-9 and not h
    e = tk.berechne(g)
    assert abs(e.nenn - 10.0) < 1e-9 and abs(e.wc_max - e.wc_min - 1.2) < 1e-9  # 3 x +-0.2 (ISO 2768-m 6..30: +-0.2)
    mit, _, _ = tk.kette_aus_flaechen(erg.modell, [181, 187, 183, 185], erg.pmi, "m")
    lage = [x for x in mit if x.quelle == "lage"]  # Position 1 an 181/187, Symmetrie 0.5 an 183/185
    assert [(x.pmi_nummer, x.mindest, x.hoechst) for x in lage] == [(34, -0.5, 0.5), (36, -0.25, 0.25)]
    muster, _, _ = tk.kette_aus_flaechen(erg.modell, [189, 134], erg.pmi, lagetoleranzen=False)
    assert [x.pmi_nummer for x in muster] == [8] and abs(muster[0].toleranz - 0.4) < 1e-9
    ohne, _, h = tk.kette_aus_flaechen(erg.modell, [181, 187, 183], erg.pmi, lagetoleranzen=False)
    assert ohne[-1].quelle == "ohne" and h
    assert tk.kette_aus_flaechen(erg.modell, [181], erg.pmi)[0] == []


def test_tolerierungsberater_regeln(ctc01):
    from programm.kern import pmi_vorschlag as pv
    from programm.kern.messen import art_von
    from programm.kern.pmi_lesen import lies_pmi
    pmi = lies_pmi(ctc01)
    loch = next(p for p in pmi if p.typ == "Size_Diameter" and p.flaechen)
    v = pv.vorschlaege(sorted(loch.flaechen), ctc01, pmi)
    assert [x.pmi.typ for x in v] == ["Size_Diameter", "Position"]
    assert abs(v[0].pmi.nennwert - loch.nennwert) < 1e-6 and v[1].pmi.bezug_text() == "A|B|C"
    eben = [i for i, f in enumerate(ctc01.flaechen) if art_von(f) == "Ebene"]
    assert pv.vorschlaege(eben[:1], ctc01, pmi)[0].pmi.typ == "Flatness"
    zwei = pv.vorschlaege(eben[:2], ctc01, pmi)
    assert zwei and zwei[0].pmi.typ in ("Perpendicularity", "Parallelism", "Location_LinearDistance",
                                       "Size_Thickness", "Location_Angular")
    assert all(g in pv.GRUENDE for x in v + zwei for g in [x.grund])


def test_iso14405_modifikatoren_im_text():
    from programm.kern.pmi import MASS, Pmi
    p = Pmi(MASS, "Size_Diameter", nennwert=10.0, oben=0.1, unten=-0.1, modifikatoren=["TwoPointSize", "AnyCrossSection"])
    assert p.wert_text() == "⌀10 ±0.1 LP ACS"
    q = Pmi(MASS, "Size_Thickness", nennwert=8.0, passung="h7", modifikatoren=["Square", "Envelope"])
    assert q.wert_text() == "□8 h7 Ⓔ" and "Hüllbedingung" in q.huelle_text() or q.typ == "Size_Thickness"


def test_sachnummern_aus_step_produkten():
    from programm.kern import p21, stueckliste as sl
    d = p21.lese_text("ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\n#1=PRODUCT('4711-01','Deckel','',(#2));\n"
                      "#3=PRODUCT('Grundplatte','Grundplatte','',(#2));\nENDSEC;\nEND-ISO-10303-21;\n")
    assert sl.sachnummern(d) == {"Deckel": "4711-01"}
    liste = sl.ergaenze_sachnummern([sl.Position(1, "Deckel", 1, 1.0, 1.0)], d)
    assert liste[0].sachnummer == "4711-01" and sl.zeilen(liste, 7.85)[0][1] == "4711-01"


def test_pruefregeln_mit_geometrie(ctc01):
    from programm.kern import pmi_bericht as pb
    from programm.kern.messen import art_von
    from programm.kern.pmi import MASS, TOLERANZ, BEZUG, BezugsRef, Pmi
    zyl = {i for i, f in enumerate(ctc01.flaechen) if art_von(f) == "Zylinder"}
    eben = [i for i, f in enumerate(ctc01.flaechen) if art_von(f) == "Ebene"]
    liste = [Pmi(TOLERANZ, "Position", wert=0.1, flaechen={min(zyl)}, nummer=1),
             Pmi(TOLERANZ, "Flatness", wert=0.05, material="M", flaechen={eben[0]}, nummer=2),
             Pmi(BEZUG, "Datum", "A", flaechen={eben[0]}, nummer=3),
             Pmi(TOLERANZ, "Perpendicularity", wert=0.1, flaechen={eben[1]}, nummer=4,
                 bezuege=[BezugsRef("A", 1, ["MaximumMaterialRequirement"])]),
             Pmi(MASS, "Size_Diameter", nennwert=10.0, passung="H7", flaechen={min(zyl)}, nummer=5, norm="iso")]
    texte = {b.text for b in pb.pruefe(liste, None, ctc01)}
    assert any("⌀-Zone" in t for t in texte) and any("Ⓜ/Ⓛ an einer Fläche" in t for t in texte)
    assert any("Bezug A ist eine Ebene" in t for t in texte) and any("ISO 8015" in t for t in texte)
    liste[4].norm = "asme"
    assert not any("ISO 8015" in b.text for b in pb.pruefe(liste, None, ctc01))


def test_stepz_zip_und_gzip(tmp_path):
    """STEPZ: ZIP mit einer Part-21-Datei oder gzip; geladen wie STEP, Pfad bleibt die Originaldatei."""
    import gzip
    import zipfile
    from programm.kern.laden import lade_modell
    quelle = pfad("nist_ftc_07_asme1_ap242-e2.stp")
    daten = open(quelle, "rb").read()
    z = tmp_path / "teil.stpz"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as a:
        a.writestr("teil.stp", daten)
    g = tmp_path / "teil.stp.gz"
    g.write_bytes(gzip.compress(daten))
    for p in (z, g):
        m = lade_modell(str(p))
        assert m.pfad == str(p) and len(m.flaechen) > 100 and m.datei is not None


def test_pmi_aus_grafik_ableiten():
    """Nur grafische PMI: Art und Werte aus Text bzw. Markup-Art, gekennzeichnet als abgeleitet."""
    from programm.kern.pmi_ableiten import aus_markup, aus_text
    t = aus_text(["⌖", "⌀0.750Ⓜ", "A", "B", "C"])
    assert t["typ"] == "Position" and t["wert"] == 0.75 and t["material"] == "M" and "Diameter" in t["modifikatoren"]
    assert [b.name for b in t["bezuege"]] == ["A", "B", "C"]
    assert aus_text(["A"]) == {"art": "bezug", "typ": "Datum", "name": "A"}
    m = aus_text(["⌀35.20", "34.80"])
    assert m["typ"] == "Size_Diameter" and m["grenzmass"] and (m["oben"], m["unten"]) == (35.2, 34.8)
    m = aus_text(["⌀20", "+0.05", "-0.10"])
    assert (m["nennwert"], m["oben"], m["unten"]) == (20.0, 0.05, -0.1)
    assert aus_text(["R.125 ±.020"])["typ"] == "Size_Radius" and aus_text(["NOTES"]) is None
    assert aus_markup("Gdt", 0, "Datum Feature Symbol D (24)") == {"art": "bezug", "typ": "Datum", "name": "D"}
    assert aus_markup("Dimension", 11, "Diameter Dimension (3)")["typ"] == "Size_Diameter"


def test_qif_nur_grafik_in_tabelle(qif_ctc01, tmp_path):
    """QIF ohne Semantik (nur PMIDisplaySet): Toleranzen, Masse und Bezuege aus den Texten abgeleitet."""
    from lxml import etree
    from programm.ui.lader import lade_alles
    w = etree.parse(qif_ctc01)
    ns = "{http://qifstandards.org/xsd/qif3}"
    for tag in ("Characteristics", "DatumDefinitions", "DatumReferenceFrames"):
        for e in list(w.iter(ns + tag)):
            e.getparent().remove(e)
    ziel = tmp_path / "nur_grafik.qif"
    w.write(str(ziel))
    e = lade_alles(str(ziel))
    abgeleitet = [p for p in e.pmi if p.quelle == "abgeleitet"]
    assert all(not p.semantisch and p.grafisch for p in abgeleitet)
    arten = [p.art for p in abgeleitet]
    assert arten.count("toleranz") == 6 and arten.count("bezug") == 3 and arten.count("mass") == 8
    pos = [p for p in abgeleitet if p.typ == "Position"]
    assert pos and all(p.wert == 0.75 and p.bezug_text() == "A|B|C" for p in pos)


def test_schnittansicht_aus_step():
    """CAMERA_MODEL_D3_MULTI_CLIPPING: Ebene und Vereinigung -> Gruppen (UND ueber Gruppen, ODER in der Gruppe)."""
    from programm.kern.ansichten import lies_ansichten
    from programm.kern.laden import lade_modell
    m = lade_modell(pfad("varianten/ctc01_schnittansicht.stp"))
    a = next(a for a in lies_ansichten(m) if a.name == "MBD_0")
    assert a.schnitt == [[((0.0, -125.0, 0.0), (0.0, 1.0, 0.0))],
                         [((30.0, 0.0, 0.0), (-1.0, 0.0, 0.0)), ((0.0, 0.0, -25.0), (0.0, 0.0, 1.0))]]
    assert a.pmi_ids  # Kamera und PMI der Ansicht weiterhin gelesen
    ohne = lade_modell(pfad("nist_ctc_01_asme1_ap242-e1.stp"))
    assert all(not x.schnitt for x in lies_ansichten(ohne))


def test_kollision_freier_bereich():
    """Block gleitet auf dem Boden (Kontakt, keine Kollision) bis an die Wand bei x = 25: frei -30 ... +15."""
    import numpy as np
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.gp import gp_Pnt
    from programm.kern import kollision as ko, verbindung as vb
    block = ko.Teil(1, "Block", BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 10, 10, 10).Shape())
    wand = ko.Teil(2, "Wand", BRepPrimAPI_MakeBox(gp_Pnt(25, 0, 0), 5, 10, 10).Shape())
    boden = ko.Teil(3, "Boden", BRepPrimAPI_MakeBox(gp_Pnt(-20, 0, -5), 60, 10, 5).Shape())
    z = np.array([0, 0, 0, 1, 0, 0.0])
    unten, oben, befunde = ko.freier_bereich(block, [wand, boden], lambda w: vb.bewegung(z, w), 30)
    assert unten == -30 and abs(oben - 15) < 30 / 24 / 2 ** 6 + 1e-9
    assert len(befunde) == 1 and befunde[0].b.nummer == 2 and befunde[0].bewegung.startswith("+15")
    # schon in der Ausgangslage durchdrungen: zaehlt nicht als Grenze
    drin = ko.Teil(4, "Stift", BRepPrimAPI_MakeBox(gp_Pnt(4, 4, -2), 2, 2, 14).Shape())
    unten, oben, _ = ko.freier_bereich(block, [drin, boden], lambda w: vb.bewegung(z, w), 10, schritte=5)
    assert (unten, oben) == (-10, 10)


def test_kollision_kontakt_band():
    """Testbaugruppe: Schrauben durchdringen den Deckel, Spalt 0,3 mm zur Grundplatte, Deckel liegt auf."""
    from programm.kern import kollision as ko
    from programm.ui.lader import lade_alles
    erg = lade_alles(pfad("baugruppe.stp"))
    teile = [ko.Teil(k.nummer, k.name, k.form) for k in erg.baum.blaetter() if not k.hilfsgeometrie]
    b = ko.pruefe(teile, e=ko.Einstellung(mindest=1.0))
    arten = [x.art for x in b]
    assert arten == [ko.KOLLISION] * 4 + [ko.ZU_NAH] * 4 + [ko.KONTAKT]
    assert all(abs(x.volumen - 163.3628) < 0.01 and x.durchdringung is not None for x in b[:4])
    assert all(abs(x.abstand - 0.3) < 1e-6 and len(x.punkte) == 2 for x in b[4:8])
    assert {b[8].a.name, b[8].b.name} == {"Grundplatte", "Deckel"}
    platte = [t for t in teile if t.name == "Grundplatte"]
    gegen = ko.pruefe(platte, [t for t in teile if t.name != "Grundplatte"],
                      ko.Einstellung(hoechst=4.0, kontakte_melden=False))
    assert [(x.art, x.b.name) for x in gegen] == [(ko.ZU_WEIT, "Winkel")] and abs(gegen[0].abstand - 5.0) < 1e-6
    assert "Kollision" in ko.als_csv(b) or "Clash" in ko.als_csv(b)


def test_zusammenbau_fangen_freiheitsgrade():
    """Schraube: Kopf auf den Deckel (eben, 1 mm nach oben), Schaft koaxial zur Bohrung -> nur Drehung frei."""
    import numpy as np
    from programm.kern import verbindung as vb
    from programm.ui.lader import lade_alles
    erg = lade_alles(pfad("baugruppe.stp"))
    knoten = {k.nummer: k for k in erg.baum.blaetter()}
    f = lambda t, i: vb.flaeche_im_teil(knoten[t].form, i, erg.modell)  # noqa: E731
    b = vb.Baugruppe()
    assert isinstance(b.verbinde(4, f(4, 18), 18, 4, f(4, 19), 19), str)  # gleiches Teil
    assert vb.Baugruppe().verbinde(4, f(4, 18), 18, 2, f(2, 6), 6).art == vb.LANGLOCH  # Ebene gegen Zylinder
    v = b.verbinde(4, f(4, 18), 18, 3, f(3, 15), 15)
    assert v.art == vb.EBEN and np.allclose(b.lage(4)[:3, 3], [0, 0, 1]) and len(b.freiheitsgrade(4)) == 3
    v2 = b.verbinde(4, f(4, 19), 19, 2, f(2, 6), 6)
    basis = b.freiheitsgrade(4)
    assert v2.art == vb.KOAXIAL and len(basis) == 1 and not b.verletzt()
    assert vb.beschreibe(basis)[0].startswith(("Drehung", "rotation"))
    # Wiggle-Bewegung dreht um die Schraubenachse (15, 15): der Achspunkt bleibt
    m = vb.bewegung(basis[0], 30.0)
    assert np.allclose(m[:3, :3] @ [15, 15, 0] + m[:3, 3], [15, 15, 0], atol=1e-9)
    # Laden aus dem gespeicherten Zustand
    b2 = vb.Baugruppe()
    b2.lade(b.als_dict(), f)
    assert [x.nummer for x in b2.verbindungen] == [1, 2] and np.allclose(b2.lage(4), b.lage(4))
    # Toleranzen: Durchgangsloch 6.6 / Schaft 6 mit ISO 2768-m -> Spiel (6.8 - 5.9) / 2 = 0.45
    for x in b.verbindungen:
        vb.toleranz_aus_pmi(b, x, erg.modell, erg.pmi, "m")
    assert abs(b.verbindungen[1].toleranz - 0.45) < 1e-9 and b.verbindungen[1].eingriff
    b.setze_toleranz(1, 0.02, 0.001, "manuell")
    weg, frei = b.streuung(4, np.array([[15, 15, 30.0]]), np.array([15, 15, 5.0]))
    assert frei == 1 and 0.45 < weg[0] < 0.5 and abs(weg[0] - weg[1]) < 1e-6 and 0.02 < weg[2] < 0.05
    lagen = b.grenzlagen(4, np.array([15, 15, 5.0]))
    assert lagen and max(abs(x[3:]).max() for x in lagen) <= 0.45 + 1e-6
    assert np.allclose(vb.bewegung_klein(np.r_[0, 0, 0.1, 0, 0, 0], 1.0, np.array([15, 15, 0]))[:3, 3] @ [1, 0, 0]
                       + 15 * np.cos(0.1) - 15 * np.sin(0.1), 15, atol=1e-9)
    # Versatz: Kopf 2 mm ueber dem Deckel
    b3 = vb.Baugruppe()
    b3.verbinde(5, f(5, 18), 18, 3, f(3, 15), 15, versatz=2.0)
    assert np.allclose(b3.lage(5)[:3, 3], [0, 0, 3])


def test_toleranzzonen_laengen_und_winkelmasse(ctc01):
    """Laengenmass zwischen Ebenen (FTC-10) und Winkelmass (CTC-01): zwei Zonenflaechen an der zweiten Seite."""
    import numpy as np
    from programm.kern import toleranzzone as tz
    from programm.kern.pmi_lesen import lies_pmi
    from programm.ui.lader import lade_alles
    pmi = lies_pmi(ctc01)
    winkel = next(p for p in pmi if p.typ == "Location_Angular")
    z = tz.zone(winkel, ctc01, 0.0, pmi)
    assert z is not None and len(z.formen) == 2 and z.art == "mass"
    ftc = lade_alles(pfad("nist_ftc_10_asme1_ap242-e2.stp"))
    laenge = next(p for p in ftc.pmi if p.nummer == 6)  # 15 +-0.2 zwischen 181 und 187
    z = tz.zone(laenge, ftc.modell, 0.0, ftc.pmi)
    assert z is not None and len(z.formen) == 2 and abs(z.breite - 0.4) < 1e-9
    # Lage der zwei Zonenebenen entlang x: 0.4 auseinander, symmetrisch um die Nennlage der zweiten Seite
    from programm.kern.toleranzkette import _ebene_oder_achse
    xs = sorted(float(_ebene_oder_achse(f)[1][0]) for f in z.formen)
    assert abs(xs[1] - xs[0] - 0.4) < 1e-6
    assert tz.zone(next(p for p in ftc.pmi if p.nummer == 16), ftc.modell, 0.0, ftc.pmi) is None  # eine Flaeche


def test_toleranzkette_bonus_kante_cpk():
    """Bonus bei Ⓜ (⌀1Ⓜ mit ⌀10 ±0.25 -> ±0.75), Nulltoleranz Ⓛ, Kante als Kettenende, Mittenversatz und
    Anforderung an das Schlussmass (Cp, Cpk, Anteil ausserhalb)."""
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer
    from programm.kern import toleranzkette as tk
    from programm.ui.lader import lade_alles
    erg = lade_alles(pfad("nist_ftc_10_asme1_ap242-e2.stp"))
    m = erg.modell

    def kette_zur_achse(nr):
        p = next(q for q in erg.pmi if q.nummer == nr)
        zyl = sorted(p.flaechen)[0]
        achse = tk._element(m.flaechen[zyl])[2]
        ebene = next(i for i, f in enumerate(m.flaechen)
                     if (g := tk._element(f)) and g[0] == "ebene" and abs(g[2] @ achse) < 1e-6)
        g, _, _ = tk.kette_aus_flaechen(m, [ebene, zyl], erg.pmi, "m")
        return next(x for x in g if x.pmi_nummer == nr)
    bonus = kette_zur_achse(52)
    assert abs(bonus.hoechst - 0.75) < 1e-9 and abs(bonus.mindest + 0.75) < 1e-9
    null_l = kette_zur_achse(53)  # ⌀0Ⓛ mit ⌀3.5 ±0.2: nur Bonus 0.4 -> ±0.2
    assert abs(null_l.toleranz - 0.4) < 1e-9
    ex = TopExp_Explorer(m.flaechen[183], TopAbs_EDGE)
    kanten = []
    while ex.More():
        kanten.append(ex.Current())
        ex.Next()
    kante = next(k for k in kanten if tk._element(k)[0] == "kante" and abs(tk._element(k)[2][0]) < 1e-6)
    g, _, _ = tk.kette_aus_flaechen(m, [181, kante], erg.pmi, "m")
    assert g[0].quelle == "allgemein" and abs(g[0].nenn - 5.0) < 1e-6 and g[0].flaechen == (181,)
    glieder, _, _ = tk.kette_aus_flaechen(m, [181, 187, 183, 185], erg.pmi, "m", lagetoleranzen=False)
    e = tk.berechne(glieder, anforderung=(9.0, 11.0))
    assert abs(e.cp - e.cpk) < 1e-9 and e.cp > 1.5 and e.ausserhalb < 1e-4
    glieder[0].versatz = 0.1
    e2 = tk.berechne(glieder, anforderung=(9.0, 11.0))
    assert abs(e2.mitte - 10.1) < 1e-9 and e2.cpk < e.cpk and abs(glieder[0].cpk() - 0.5) < 1e-9
    assert "Cpk" in tk.als_csv(glieder, e2)
