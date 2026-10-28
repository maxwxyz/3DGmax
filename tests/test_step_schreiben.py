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
                                            (t.nummer, "wert"), (t.nummer, "material")])
    assert (t.nummer, "material") in b.geschrieben and not b.uebersprungen
    neu = {p.step_id: p for p in lade_alles(ziel).pmi}
    assert abs(neu[m.step_id].nennwert - (nenn + 1)) < 1e-9 and neu[m.step_id].oben == 0.3
    assert neu[m.step_id].unten == -0.05 and abs(neu[t.step_id].wert - 2 * wert) < 1e-9
    assert neu[t.step_id].material == t.material
    alt = {p.step_id: p.wert_text() for p in lade_alles(quelle).pmi}
    assert len(neu) == len(alt)
    assert all(neu[k].wert_text() == v for k, v in alt.items() if k not in (m.step_id, t.step_id))
    # ausser den Zahlen bleibt die Datei Zeichen fuer Zeichen gleich
    q, z = open(quelle, encoding="utf-8").read(), open(ziel, encoding="utf-8").read()
    assert abs(len(q) - len(z)) < 120 and q.splitlines()[:20] == z.splitlines()[:20]


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


def test_eigene_pmi_anhaengen(tmp_path):
    """Eigene PMI (Bezug, Ebenheit, Durchmesser, Position mit Bezug, Ⓜ und ⌀-Zone) als neue Entitaeten; unser Leser und
    der OCCT-Leser finden sie; Winkelmass und Baugruppe werden gemeldet."""
    from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
    from OCC.Core.TDF import TDF_LabelSequence
    from OCC.Core.TDocStd import TDocStd_Document
    from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool
    from programm.kern import step_schreiben as sw, toleranzzone as tz
    from programm.kern.pmi import BezugsRef, Pmi
    from programm.ui.lader import lade_alles
    quelle = pfad("nist_ctc_01_asme1_ap242-e1.stp")
    a = lade_alles(quelle)
    eben = next(i for i, f in enumerate(a.modell.flaechen) if not tz._achsen([f]))
    loch = next(i for i, f in enumerate(a.modell.flaechen) if tz._achsen([f]))
    d = 2 * tz._achsen([a.modell.flaechen[loch]])[0][3]
    neue = [Pmi("bezug", "Datum", "Q", flaechen={eben}), Pmi("toleranz", "Flatness", "", wert=0.02, flaechen={eben}),
            Pmi("mass", "Size_Diameter", "", nennwert=d, oben=0.1, unten=0.0, flaechen={loch}),
            Pmi("toleranz", "Position", "", wert=0.1, material="M", modifikatoren=["Diameter"],
                bezuege=[BezugsRef("Q", 1)], flaechen={loch}),
            Pmi("mass", "Size_Angular", "", nennwert=30, flaechen={eben}),
            Pmi("toleranz", "Parallelism", "", wert=0.1, bezuege=[BezugsRef("Z", 1)], flaechen={eben})]
    for i, p in enumerate(neue):
        p.quelle, p.nummer, p.step_id = "eigen", 900 + i, -1000 - i
    ziel = str(tmp_path / "eigen.stp")
    b = sw.schreibe(quelle, ziel, a.pmi + neue, a.modell)
    assert b.neu == [900, 901, 902, 903, 904] and [n for n, _, _ in b.uebersprungen] == [905]
    grenze = max(a.modell.datei.entities)
    neu = {(p.art, p.typ): p for p in lade_alles(ziel).pmi if p.step_id > grenze}
    assert set(neu) == {("bezug", "Datum"), ("toleranz", "Flatness"), ("mass", "Size_Diameter"),
                        ("toleranz", "Position"), ("mass", "Size_Angular")}
    assert abs(neu[("mass", "Size_Angular")].nennwert - 30) < 1e-9
    pos = neu[("toleranz", "Position")]
    assert pos.flaechen == {loch} and pos.material == "M" and "Diameter" in pos.modifikatoren
    assert [x.name for x in pos.bezuege] == ["Q"] and neu[("bezug", "Datum")].flaechen == {eben}
    assert abs(neu[("mass", "Size_Diameter")].nennwert - d) < 1e-9 and neu[("mass", "Size_Diameter")].oben == 0.1

    def xcaf(datei):
        doc = TDocStd_Document("MDTV-XCAF")
        r = STEPCAFControl_Reader()
        r.SetGDTMode(True)
        r.ReadFile(datei)
        r.Transfer(doc)
        dt = XCAFDoc_DocumentTool.DimTolTool(doc.Main())
        out = []
        for hole in (dt.GetDimensionLabels, dt.GetGeomToleranceLabels, dt.GetDatumLabels):
            s = TDF_LabelSequence()
            hole(s)
            out.append(s.Length())
        return out
    assert [n - v for n, v in zip(xcaf(ziel), xcaf(quelle))] == [2, 2, 1]
    # Baugruppe: Bezug und Toleranz am jeweiligen Teil; Flaechen aus zwei Teilen in einer PMI werden gemeldet
    g = lade_alles(pfad("getriebe.stp"))
    blaetter = {k.name: k for k in g.baum.blaetter()}

    def flaechen_von(name):
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Core.TopExp import TopExp_Explorer
        out, ex = [], TopExp_Explorer(blaetter[name].form, TopAbs_FACE)
        while ex.More():
            out.append(g.modell.flaechen_index(ex.Current()))
            ex.Next()
        return out
    hulse, rad = flaechen_von("Distanzhülse"), flaechen_von("Zahnrad")
    eigene = [Pmi("bezug", "Datum", "H", flaechen={hulse[0]}),
              Pmi("toleranz", "Parallelism", "", wert=0.02, bezuege=[BezugsRef("H", 1)], flaechen={hulse[1]}),
              Pmi("toleranz", "Flatness", "", wert=0.02, flaechen={rad[0]}),
              Pmi("toleranz", "Flatness", "", wert=0.02, flaechen={rad[0], hulse[0]}),
              Pmi("toleranz", "Parallelism", "", wert=0.02, bezuege=[BezugsRef("H", 1)], flaechen={rad[1]})]
    for i, p in enumerate(eigene):
        p.quelle, p.nummer, p.step_id = "eigen", 1 + i, -1 - i
    ziel_g = str(tmp_path / "g.stp")
    b = sw.schreibe(pfad("getriebe.stp"), ziel_g, eigene, g.modell)
    assert b.neu == [1, 2, 3] and [n for n, _, _ in b.uebersprungen] == [4, 5]  # zwei Teile; H gehoert zur Huelse
    neu = lade_alles(ziel_g).pmi
    par = next(p for p in neu if p.typ == "Parallelism")
    assert [x.name for x in par.bezuege] == ["H"] and par.flaechen == {hulse[1]}
    assert next(p for p in neu if p.typ == "Flatness").flaechen == {rad[0]}


def test_passung_und_materialbedingung(tmp_path):
    """Toleranzklasse in LIMITS_AND_FITS; Materialbedingung setzen (einfache Entitaet wird komplex), aendern, entfernen."""
    from programm.kern import step_schreiben as sw
    from programm.ui.lader import lade_alles
    quelle = pfad("nist_ftc_10_asme1_ap242-e2.stp")
    a = lade_alles(quelle)
    fit = next(p for p in a.pmi if p.art == "mass" and p.passung)
    senk = next(p for p in a.pmi if p.typ == "Perpendicularity" and not p.material)
    pos = next(p for p in a.pmi if p.typ == "Position" and p.material == "M")
    _aendere(fit, passung="H7")
    _aendere(senk, material="M")
    _aendere(pos, material="L")
    ziel = str(tmp_path / "f.stp")
    b = sw.schreibe(quelle, ziel, a.pmi)
    assert not b.uebersprungen and len(b.geschrieben) == 3
    neu = {p.step_id: p for p in lade_alles(ziel).pmi}
    assert neu[fit.step_id].passung == "H7"
    assert neu[senk.step_id].material == "M" and [x.name for x in neu[senk.step_id].bezuege] == \
        [x.name for x in senk.bezuege]
    assert neu[pos.step_id].material == "L"
    _aendere(pos, material="")
    b = sw.schreibe(ziel, str(tmp_path / "g.stp"), [pos])
    assert next(p for p in lade_alles(str(tmp_path / "g.stp")).pmi if p.step_id == pos.step_id).material == ""


def _occt_darstellungen(datei) -> tuple[list[str], list[str]]:
    """Namen der Darstellungen, die OCCT (XCAF, GD&T-Modus) an Masse und Bezuege haengt."""
    from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
    from OCC.Core.TDF import TDF_LabelSequence
    from OCC.Core.TDocStd import TDocStd_Document
    from OCC.Core.XCAFDoc import XCAFDoc_Datum, XCAFDoc_Dimension, XCAFDoc_DocumentTool
    doc = TDocStd_Document("MDTV-XCAF")
    r = STEPCAFControl_Reader()
    r.SetGDTMode(True)
    assert r.ReadFile(datei) == 1 and r.Transfer(doc)
    dt = XCAFDoc_DocumentTool.DimTolTool(doc.Main())
    out = []
    for hole, art in ((dt.GetDimensionLabels, XCAFDoc_Dimension), (dt.GetDatumLabels, XCAFDoc_Datum)):
        s = TDF_LabelSequence()
        hole(s)
        namen = []
        for i in range(1, s.Length() + 1):
            o = art.Set(s.Value(i)).GetObject()
            form, name = o.GetPresentation(), o.GetPresentationName()
            if form is not None and not form.IsNull():
                namen.append(name.ToCString() if name is not None else "")
        out.append(namen)
    return out[0], out[1]


def _pruefe_darstellung(a, eigene, ziel, grenze):
    """Jede eigene PMI kommt semantisch und mit Grafik aus der Datei zurueck, gleich der Grafik der Ansicht; die
    Hinweislinie endet auf der Flaeche."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
    from OCC.Core.gp import gp_Pnt
    from programm.kern import pmi_erzeugen
    from programm.ui.lader import lade_alles
    ansicht = pmi_erzeugen.ergaenze(eigene, {}, a.modell)
    e = lade_alles(ziel)
    neu = {(p.art, p.typ): p for p in e.pmi if p.step_id > grenze}
    assert len(neu) == len(eigene)
    for p in eigene:
        q = neu[(p.art, p.typ)]
        g = next(g for g in e.grafik.values() if q.step_id in g.pmi_ids)
        assert g.callout_id > grenze and g.fertig and not g.erzeugt and g.linien and g.dreiecke
        soll = next(x for x in ansicht.values() if p.step_id in x.pmi_ids)
        assert len(g.linien) > len(soll.linien)  # dazu die Umrisse der Textglyphen
        assert max(abs(x - y).max() for x, y in zip(soll.linien, g.linien)) < 1e-5
        if p.art != "bezug":  # Pfeilspitze der Hinweislinie auf der Flaeche
            d = BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float, g.linien[0][0]))).Vertex(),
                                           a.modell.flaechen[min(p.flaechen)])
            assert d.Value() < 1e-6
    return e


def test_eigene_pmi_mit_darstellung(tmp_path):
    """Eigene PMI werden mit Darstellung (tessellierte Callouts, Ebene, DRAUGHTING_MODEL, Verknuepfung) geschrieben:
    unser Leser liest Semantik und Grafik zurueck, OCCT haengt die Darstellung an Mass und Bezug; in der Baugruppe
    liegt die Grafik im Teil und kommt an der Lage der Instanz zurueck."""
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from programm.kern import step_schreiben as sw, toleranzzone as tz
    from programm.kern.pmi import BezugsRef, Pmi
    from programm.ui.lader import lade_alles
    quelle = pfad("nist_ctc_01_asme1_ap242-e1.stp")
    a = lade_alles(quelle)
    eben = next(i for i, f in enumerate(a.modell.flaechen) if not tz._achsen([f]))
    loch = next(i for i, f in enumerate(a.modell.flaechen) if tz._achsen([f]))
    d = 2 * tz._achsen([a.modell.flaechen[loch]])[0][3]
    eigene = [Pmi("bezug", "Datum", "Q", flaechen={eben}), Pmi("toleranz", "Flatness", "", wert=0.02, flaechen={eben}),
              Pmi("mass", "Size_Diameter", "", nennwert=d, oben=0.1, unten=0.0, flaechen={loch}),
              Pmi("toleranz", "Position", "", wert=0.1, modifikatoren=["Diameter"], bezuege=[BezugsRef("Q", 1)],
                  flaechen={loch})]  # OCCT legt Bezuege nur an Toleranzrahmen an
    for i, p in enumerate(eigene):
        p.quelle, p.nummer, p.step_id = "eigen", 900 + i, -1000 - i
    ziel = str(tmp_path / "d.stp")
    b = sw.schreibe(quelle, ziel, a.pmi + eigene, a.modell)
    assert b.neu == b.dargestellt == [900, 901, 902, 903]
    text = open(ziel, encoding="utf-8").read()
    assert text.count("DRAUGHTING_MODEL_ITEM_ASSOCIATION('PMI representation to presentation link'") == 23 + 4
    _pruefe_darstellung(a, eigene, ziel, max(a.modell.datei.entities))
    masse, bezuege = _occt_darstellungen(ziel)
    masse0, bezuege0 = _occt_darstellungen(quelle)
    assert len(masse) == len(masse0) + 1 and "Size_Diameter" in masse
    assert len(bezuege) == len(bezuege0) + 1 and "Q" in bezuege
    # Baugruppe: die Schraube liegt verschoben; Grafik im Teil geschrieben, an der Instanz gelesen
    g = lade_alles(pfad("baugruppe.stp"))
    schraube = next(k for k in g.baum.blaetter() if k.name.startswith("Schraube"))
    ex, fl = TopExp_Explorer(schraube.form, TopAbs_FACE), []
    while ex.More():
        fl.append(g.modell.flaechen_index(ex.Current()))
        ex.Next()
    assert not g.modell.flaechen[fl[0]].Location().IsIdentity()
    eben = next(i for i in fl if not tz._achsen([g.modell.flaechen[i]]))
    zyl = next(i for i in fl if tz._achsen([g.modell.flaechen[i]]))
    d = 2 * tz._achsen([g.modell.flaechen[zyl]])[0][3]
    eigene = [Pmi("bezug", "Datum", "H", flaechen={eben}),
              Pmi("mass", "Size_Diameter", "", nennwert=d, oben=0.1, unten=0.0, flaechen={zyl}),
              Pmi("toleranz", "Position", "", wert=0.1, modifikatoren=["Diameter"], bezuege=[BezugsRef("H", 1)],
                  flaechen={zyl})]
    for i, p in enumerate(eigene):
        p.quelle, p.nummer, p.step_id = "eigen", 1 + i, -1 - i
    ziel = str(tmp_path / "b.stp")
    assert sw.schreibe(pfad("baugruppe.stp"), ziel, eigene, g.modell).dargestellt == [1, 2, 3]
    _pruefe_darstellung(g, eigene, ziel, max(g.modell.datei.entities))
    assert _occt_darstellungen(ziel) == (["Size_Diameter"], ["H"])


def nur_grafisch_ctc01(ziel) -> str:
    """CTC-01 mit Ebenheit 'Flatness.1' nur als Grafik: Toleranz (#57) und ihre Verknuepfungen (#137, #138) fehlen."""
    import re
    text = open(pfad("nist_ctc_01_asme1_ap242-e1.stp"), encoding="utf-8").read()
    text = re.sub(r"^#(57|137|138)=.*;\n", "", text, flags=re.M)
    with open(ziel, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return str(ziel)


def test_nur_grafische_pmi_reparieren(tmp_path):
    """Nur grafische PMI semantisch machen: Art aus dem Callout-Namen, Flaechen aus der Hinweislinie (gleich der
    entfernten Semantik); geschrieben wird nur die Semantik, verknuepft mit dem vorhandenen Callout."""
    from programm.kern import pmi_erzeugen, pmi_reparieren as rep, step_schreiben as sw
    from programm.ui.lader import lade_alles
    quelle = nur_grafisch_ctc01(tmp_path / "grafisch.stp")
    a = lade_alles(quelle)
    p = next(p for p in a.pmi if p.name == "Flatness.1")
    assert not p.semantisch and rep.reparierbar(p, a.grafik) and p.step_id == 611
    assert rep.aus_name("Position surfacic profile.3") == ("toleranz", "ProfileOfSurface")
    assert rep.aus_name("Simple Datum.2") == ("bezug", "Datum") and rep.aus_name("Text.1") is None
    v = rep.vorschlag(p, a.grafik[611], a.modell)
    assert (v.art, v.typ, v.callout) == ("toleranz", "Flatness", 611)
    assert v.flaechen == {a.modell.step_zu_flaeche[861]}  # Flaeche der entfernten Semantik (GISU #245)
    v.wert, v.quelle, v.nummer, v.step_id = 0.1, "eigen", 99, -1
    assert pmi_erzeugen.ergaenze([v], a.grafik, a.modell) == {} and -1 in a.grafik[611].pmi_ids
    ziel = str(tmp_path / "repariert.stp")
    b = sw.schreibe(quelle, ziel, a.pmi + [v], a.modell)
    assert b.neu == b.repariert == [99] and not b.dargestellt
    text = open(ziel, encoding="utf-8").read()
    assert text.count("DRAUGHTING_CALLOUT(") == open(quelle, encoding="utf-8").read().count("DRAUGHTING_CALLOUT(")
    e = lade_alles(ziel)
    assert not any(q.name == "Flatness.1" and not q.semantisch for q in e.pmi)
    neu = next(q for q in e.pmi if q.typ == "Flatness" and q.step_id > max(a.modell.datei.entities))
    assert neu.flaechen == v.flaechen and neu.wert == 0.1 and neu.step_id in e.grafik[611].pmi_ids
    # OCCT: vorher eine reine Darstellung (DimensionPresentation), jetzt an der Toleranz (in pythonocc nicht lesbar)
    assert "Flatness.1" in _occt_darstellungen(quelle)[0] and "Flatness.1" not in _occt_darstellungen(ziel)[0]
