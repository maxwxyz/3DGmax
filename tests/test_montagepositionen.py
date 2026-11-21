"""Positionsrahmen mit gezeichneten Montageorten in CTC-03."""
from dataclasses import replace
import gzip
from pathlib import Path

import numpy as np
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Cylinder
import pytest

from programm.kern import pmi_strichschrift as schrift
from programm.kern.pmi_freier_hinweis import _ansichten
from programm.kern.pmi_koplanarschrift import rahmen_mit_hinweis
from programm.kern.pmi_reparieren import vorschlag
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_bezugsbuchstaben import _gefuellt
from tests.test_hilfsmassschrift import _mit_fuellsatz
from tests.test_kreisbezugsstelle import _ersetze_schrift
from tests.test_step_ap242 import _occt

QUELLE = "nist_ctc_03_asme1_ap203.stp.gz"
HINWEIS = "SWITCH MOUNTING LOCATIONS"
RAHMEN = "⌖ ⌀.05Ⓜ D B C"


def _mittellinien(g, zeilen):
    from programm.kern.pmi_rahmenzusatz import _ZUEGE
    o, x, y, _ = g.ebene
    linien = []
    for i, wort in enumerate(zeilen):
        pos = -228.
        for z in wort:
            if z == " ":
                pos += 5
                continue
            for zug in _ZUEGE[z]:
                linien.append(np.array([o+(pos+.52*u)*x+(-95-i*17-.62*v)*y for u, v in zug]))
            pos += 10 if z != "I" else 4
    return linien


def _strichrahmen(g):
    """Die neun Originalglyphen durch Mittellinien in ihren tatsaechlichen Zeichenboxen ersetzen."""
    phi = np.linspace(0,2*np.pi,73)
    ring = .5 + .5*np.column_stack((np.cos(phi),np.sin(phi)))
    striche = {
        "⌖": [.5+.62*(ring-.5), [(0,.5),(1,.5)], [(.5,0),(.5,1)]],
        "⌀": [ring*[.98,.72]+[.01,.14],[(.12,0),(.9,1)]],
        ".": [[(0,0),(1,0),(1,1),(0,1),(0,0)]],
        "0": [[(.33,0),(.66,0),(1,.13),(1,.87),(.66,1),(.33,1),(0,.87),(0,.13),(.33,0)]],
        "5": [[(1,1),(.15,1),(0,.51),(.52,.51),(.83,.39),(1,.26),(.86,.12),(.68,0),(.16,0),(0,.13)]],
        "Ⓜ": [ring,[(.29,.22),(.29,.78),(.5,.43),(.71,.78),(.71,.22)]],
        "D": [[(0,0),(0,1),(.44,1),(.8,.88),(1,.63),(1,.38),(.84,.13),(.45,0),(0,0)]],
        "B": [[(0,0),(0,1),(.65,1),(.94,.87),(.94,.66),(.69,.52),(0,.52)],[(.69,.52),(1,.38),(1,.16),(.69,0),(0,0)]],
        "C": [[(1,.86),(.78,1),(.28,1),(0,.81),(0,.2),(.25,0),(.78,0),(1,.14)]]}
    pfade = schrift._pfade(g, g.ebene)
    ergebnis = [g.linien[i] for i in (0,6,17,20,24,26,27,28)]
    o, x, y, _ = g.ebene
    for z, idx in zip("⌖⌀.05ⓂDBC",(1,7,10,11,13,14,18,21,25),strict=True):
        a = pfade[idx][0]
        for zug in striche[z]:
            uv = a.min(0)+np.array(zug)*np.ptp(a,axis=0)
            ergebnis.append(o+uv[:,:1]*x+uv[:,1:]*y)
    return ergebnis


def test_vollstaendiger_rahmen_und_hinweis(monkeypatch):
    from programm.kern import pmi_validierungstext
    e = lade_alles(pfad(QUELLE))
    g = e.grafik[3627]
    p = next(p for p in e.pmi if p.step_id == 3627)
    netz = replace(g, linien=[], dreiecke=[(a*g.textfaktor,t) for a,t in _gefuellt(g)])
    strich = replace(g, linien=_strichrahmen(g)+_mittellinien(g, ("SWITCH MOUNTING", "LOCATIONS")))
    for grafik in (g, netz, strich):
        for ebene in (g.ebene, None):
            assert rahmen_mit_hinweis(replace(grafik, ebene=ebene)) == (RAHMEN, HINWEIS)
    for linien in (g.linien[:-1], g.linien[:44], g.linien[:46]+g.linien[47:],
                   g.linien+[g.linien[-1]+15*g.ebene[1]], g.linien[:29]+_mittellinien(g, ("SWITCH M0UNTING", "LOCATIONS"))):
        assert not rahmen_mit_hinweis(replace(g, linien=linien))
    assert not rahmen_mit_hinweis(replace(g, linien=g.linien[:29]+[q+3*g.ebene[3] for q in g.linien[29:]]))
    # Beide Schenkel und die Spitze des M im geschlossenen Ring muessen lesbar sein.
    innen = strich.linien[17]
    for defekt in ([], innen[:-1], innen[1:], innen[[0,1,3,4]]):
        linien = strich.linien[:17]+([defekt] if len(defekt) else [])+strich.linien[18:]
        assert rahmen_mit_hinweis(replace(strich, linien=linien)) is None
    validierung = r"FCF\w⌖\w⌀.05Ⓜ\wD\wB\wC"
    for quelle, wert in ((validierung, 1.27), (validierung+r"\xTXT\w"+HINWEIS, 1.27),
                         (validierung+r"\xTXT\wPUMP MOUNTING LOCATIONS", None), (validierung.replace("Ⓜ",""), None)):
        monkeypatch.setattr(pmi_validierungstext, "_validierungswerte", lambda *a: {quelle})
        v = vorschlag(p, g, e.modell)
        assert v.wert == wert and v.beschreibung == HINWEIS


def _zylinder(modell, indices):
    gruppen = {}
    for i in indices:
        a = BRepAdaptor_Surface(modell.flaechen[i])
        assert a.GetType() == GeomAbs_Cylinder
        c = a.Cylinder()
        ort = tuple(np.round(c.Location().Coord(), 5))
        assert c.Radius() == pytest.approx(7.9375)
        assert c.Axis().Direction().Coord() == pytest.approx((0,0,-1))
        grenzen = tuple(np.round([a.FirstVParameter(), a.LastVParameter()], 5))
        gruppen.setdefault((ort, grenzen), []).append((a.FirstUParameter(), a.LastUParameter()))
    for boegen in gruppen.values():
        boegen.sort()
        assert boegen[0][0] == pytest.approx(0, abs=1e-7)
        assert boegen[-1][1] == pytest.approx(2*np.pi)
        assert all(v[1] == pytest.approx(n[0]) for v,n in zip(boegen, boegen[1:]))
    return set(gruppen)


@pytest.mark.parametrize("schrift", ["kontur", "strich", "fuellung"])
def test_montagebohrungen_projekt_und_step(fenster, tmp_path, schrift):
    e = lade_alles(pfad(QUELLE))
    g = e.grafik[3627]
    with gzip.open(pfad(QUELLE), "rt", encoding="ascii") as f:
        text = f.read()
    if schrift == "strich":
        text = _ersetze_schrift(text, e, g, 0, _strichrahmen(g)+_mittellinien(g, ("SWITCH MOUNTING", "LOCATIONS")))
    elif schrift == "fuellung":
        stil = e.modell.datei.get(3627).args()[1][0].id
        text = _mit_fuellsatz(text, _gefuellt(g), 3627, stil, g.name)
    eingang = tmp_path/"Montage.step"
    eingang.write_text(text, encoding="ascii")
    fenster.lade(str(eingang), warten=True)
    erg = fenster.erg
    grafik = erg.grafik[3627]
    for nr in (3643, 3632, 3624, 3627):
        fenster._pmi_befehl("semantisch", next(p for p in erg.pmi if p.step_id == nr))
        d = fenster._semantik_dialog
        assert not d.fehler()
        if nr == 3627:
            assert d.v.beschreibung == HINWEIS and d.v.ocr_text.splitlines() == [RAHMEN, HINWEIS]
        d._pruefen()
    projekt = fenster.speichere_projekt(str(tmp_path/"Montage.3dgmax"))
    fenster.oeffne_projekt(projekt, warten=True)
    q, = [p for p in fenster.erg.pmi if p.quelle == "eigen" and p.callout == 3627]
    assert q.beschreibung == HINWEIS
    ziel = fenster.speichere_step_pmi(str(tmp_path/"Geprueft.step"), melden=False)
    assert ziel and not fenster._step_bericht.uebersprungen
    neu = lade_alles(ziel)
    n = neu.grafik[3627]
    p, = [p for p in neu.pmi if p.semantisch and p.step_id in n.pmi_ids]
    assert p.typ == "Position" and p.wert == pytest.approx(1.27)
    assert [b.text() for b in p.bezuege] == ["D", "B", "C"]
    assert set(p.modifikatoren) == {"Diameter", "Maximum_Material_Requirement"}
    assert p.beschreibung == HINWEIS
    assert {neu.modell.flaeche_zu_step[i] for i in p.flaechen} == {546,547,548,549}
    bohrungen = _zylinder(neu.modell, p.flaechen)
    assert len(bohrungen) == 4
    referenz = Path(__file__).parents[1]/"daten/nist/NIST-PMI-STEP-Files/nist_ctc_03_asme1_ap242-e2.stp"
    if referenz.is_file():
        ref = lade_alles(str(referenz))
        r = next(q for q in ref.pmi if q.step_id == 41)
        assert r.typ == p.typ and r.wert == pytest.approx(p.wert) and r.bezuege == p.bezuege
        assert set(r.modifikatoren) == set(p.modifikatoren)
        assert len(r.flaechen) == 8 and _zylinder(ref.modell, r.flaechen) == bohrungen
    assert _ansichten(erg.modell.datei, 3627) == _ansichten(neu.modell.datei, 3627) != set()
    for a,b in zip(grafik.linien, n.linien, strict=True):
        np.testing.assert_array_equal(a,b)
    for (a,t),(b,u) in zip(grafik.dreiecke, n.dreiecke, strict=True):
        np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(t,u)
    typen, diagnosen, volumen = _occt(ziel)
    assert typen[p.step_id] == "StepDimTol_GeoTolAndGeoTolWthDatRefAndGeoTolWthMod"
    assert (diagnosen, volumen) == _occt(eingang)[1:]
