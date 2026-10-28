"""Bearbeitete PMI-Werte verlustfrei in eine Kopie der STEP-Datei schreiben (PLAN §8.28)."""

from tests.conftest import pfad


def _aendere(p, **werte):
    p.original = {k: getattr(p, k) for k in werte}
    for k, v in werte.items():
        setattr(p, k, v)
    p.bearbeitet = True


def test_werte_schreiben_nur_geaenderte(tmp_path):
    from programm.kern import step_schreiben as sw
    from programm.ui.lader import lade_alles
    quelle = pfad("nist_ftc_10_asme1_ap242-e2.stp")
    a = lade_alles(quelle)
    m = next(p for p in a.pmi if p.art == "mass" and p.oben is not None and not p.grenzmass)
    t = next(p for p in a.pmi if p.art == "toleranz" and p.wert)
    nenn, wert = m.nennwert, t.wert
    _aendere(m, nennwert=nenn + 1, oben=0.3, unten=-0.05)
    _aendere(t, wert=wert * 2, material="M" if t.material != "M" else "")
    ziel = str(tmp_path / "neu.stp")
    b = sw.schreibe(quelle, ziel, a.pmi)
    assert sorted(b.geschrieben) == sorted([(m.nummer, "nennwert"), (m.nummer, "oben"), (m.nummer, "unten"),
                                            (t.nummer, "wert")])
    assert [(n, f) for n, f, _ in b.uebersprungen] == [(t.nummer, "material")]
    neu = {p.step_id: p for p in lade_alles(ziel).pmi}
    assert abs(neu[m.step_id].nennwert - (nenn + 1)) < 1e-9 and neu[m.step_id].oben == 0.3
    assert neu[m.step_id].unten == -0.05 and abs(neu[t.step_id].wert - 2 * wert) < 1e-9
    alt = {p.step_id: p.wert_text() for p in lade_alles(quelle).pmi}
    assert len(neu) == len(alt)
    assert all(neu[k].wert_text() == v for k, v in alt.items() if k not in (m.step_id, t.step_id))
    # ausser den Zahlen bleibt die Datei Zeichen fuer Zeichen gleich
    q, z = open(quelle, encoding="utf-8").read(), open(ziel, encoding="utf-8").read()
    assert abs(len(q) - len(z)) < 40 and q.splitlines()[:20] == z.splitlines()[:20]


def test_real_und_ohne_entsprechung(tmp_path):
    from programm.kern import step_schreiben as sw
    from programm.ui.lader import lade_alles
    assert sw._real(2.0) == "2." and sw._real(0.15) == "0.15" and "E" in sw._real(1e-20).upper()
    quelle = pfad("nist_ftc_10_asme1_ap242-e2.stp")
    a = lade_alles(quelle)
    m = next(p for p in a.pmi if p.art == "mass" and p.oben is None and not p.grenzmass and p.nennwert)
    _aendere(m, oben=0.1)
    b = sw.schreibe(quelle, str(tmp_path / "x.stp"), a.pmi)
    assert not b.geschrieben and b.uebersprungen[0][:2] == (m.nummer, "oben")
