"""Separat getrimmte STEP-Profilbereiche mit eigener Berandung und Innenloch."""

import gzip
import re

import pytest
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCC.Core.BRepCheck import BRepCheck_Analyzer
from OCC.Core.BRepTools import breptools
from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCC.Core.TopoDS import topods

from programm.kern import p21, step_schreiben, toleranzzone
from programm.kern.pmi import Pmi
from programm.kern.profilteilflaeche import _inhalt
from programm.ui.lader import lade_alles
from tests.conftest import pfad


def _flaeche_als_step(form, pfad):
    writer = STEPControl_Writer()
    writer.Transfer(form, STEPControl_AsIs)
    writer.Write(str(pfad))
    text = pfad.read_text(encoding="ascii")
    datei = p21.lese_text(text)
    face, = datei.of_type("ADVANCED_FACE")
    zeilen = {int(m[1]): m[0] for m in re.finditer(r"#(\d+)\s*=[^;]+;", text)}
    # Nur den getrimmten Bereich mit seinen Kurven und Flaechen uebernehmen.
    offen, verweise = [face.id], {}
    while offen:
        nr = offen.pop()
        if nr not in verweise:
            zeile = zeilen[nr]
            verweise[nr] = re.sub(r"#(\d+)", lambda m: f"#{110000 + int(m[1])}", zeile)
            offen.extend(map(int, re.findall(r"#(\d+)", zeile.split("=", 1)[1])))
    kanten = sorted(step_schreiben.randkanten(datei, face.id))
    return face.id + 110000, [kanten[0]+110000, kanten[2]+110000], "\n".join(verweise.values())


@pytest.fixture(scope="module")
def bereiche(tmp_path_factory):
    ordner = tmp_path_factory.mktemp("teilbereich")
    quelle = ordner / "CTC01.stp"
    with gzip.open(pfad("nist_ctc_01_asme1_ap203.stp.gz"), "rb") as f:
        quelle.write_bytes(f.read())
    eingang = lade_alles(str(quelle))
    m = eingang.modell
    ziel = ordner / "Ganz.step"
    p = Pmi("toleranz", "ProfileOfSurface", wert=1.25, quelle="eigen", callout=3422,
            flaechen={m.step_zu_flaeche[n] for n in (553, 554)}, bereichsgrenzen=[["A", 2023], ["B", 2025]])
    assert step_schreiben.schreibe(str(quelle), str(ziel), [p], m).repariert
    vorlage = ziel.read_text(encoding="ascii")
    out = {"Ganz": ziel}
    for name, nr, uv in (("Innenloch", 553, (10., 30., 20., 70.)), ("Rand", 553, (40., 65., 20., 70.)),
                         ("Zylinder", 554, (5., 6., 15., 45.))):
        basis = BRep_Tool.Surface(m.form_von_step(nr))
        mf = BRepBuilderAPI_MakeFace(basis, *uv, 1e-7)
        if name == "Innenloch":
            loch = BRepBuilderAPI_MakeFace(basis, 15., 25., 30., 40., 1e-7).Face()
            mf.Add(topods.Wire(breptools.OuterWire(loch).Reversed()))
        assert BRepCheck_Analyzer(mf.Face()).IsValid()
        f, kanten, zusatz = _flaeche_als_step(mf.Face(), ordner / "Geometrie.step")
        text = vorlage.replace("CONNECTED_FACE_SET('',(#553,#554))", f"CONNECTED_FACE_SET('',(#{f}))")
        assert text != vorlage
        rep = re.search(r"#(\d+)=SHAPE_REPRESENTATION\('',\(#\d+\),#17160\);", text[text.index("CONNECTED_FACE_SET"):])[1]
        for alt, neu in zip((2023, 2025), kanten):
            text, n = re.subn(rf"(GEOMETRIC_ITEM_SPECIFIC_USAGE\('','',#\d+,)#148,#{alt}\);",
                              rf"\g<1>#{rep},#{neu});", text)
            assert n == 1
        pos = text.rindex("ENDSEC;")
        out[name] = ordner / (name + ".step")
        out[name].write_text(text[:pos] + zusatz + "\n" + text[pos:], encoding="ascii")
    return out


def _profil(e):
    p, = [p for p in e.pmi if p.bereichsgrenzen]
    return p


@pytest.mark.parametrize("name,nr", [("Innenloch", 553), ("Zylinder", 554)])
def test_echte_berandung_und_versatz(bereiche, name, nr):
    from OCC.Core.TopAbs import TopAbs_WIRE
    from OCC.Core.TopExp import TopExp_Explorer
    from tests.test_step_ap242 import _occt
    e = lade_alles(str(bereiche[name]))
    p = _profil(e)
    m = e.modell
    (idx, teil), = p.profilausschnitte.values()
    assert not p.flaechen and p.traegerflaechen() == {idx} and idx == m.step_zu_flaeche[nr]
    assert len(m.flaechen) == 139 and m._reader.ChangeReader().NbShapes() == 1
    assert m.flaechen_index(teil) is None and _inhalt(teil) < _inhalt(m.flaechen[idx])
    assert _occt(bereiche[name])[1:] == _occt(bereiche["Ganz"])[1:]
    z = toleranzzone.zone(p, m)
    assert z.breite == 1.25 and z.quellen_je_form() == [{idx}, {idx}]
    if name == "Innenloch":
        for f in [teil, *z.formen]:
            assert _inhalt(f) == pytest.approx(900.)
            ex = TopExp_Explorer(f, TopAbs_WIRE)
            anzahl = 0
            while ex.More():
                anzahl += 1
                ex.Next()
            assert anzahl == 2
    else:
        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
        radius = BRepAdaptor_Surface(teil).Cylinder().Radius()
        assert _inhalt(teil) == pytest.approx(radius * 30.)
        assert sorted(_inhalt(f) for f in z.formen) == pytest.approx([(radius-.625)*30., (radius+.625)*30.])


def test_teilweise_ausserhalb_bleibt_offen(bereiche):
    e = lade_alles(str(bereiche["Rand"]))
    p = _profil(e)
    assert not p.traegerflaechen() and toleranzzone.zone(p, e.modell) is None


def test_teilbereich_in_hinzugefuegter_datei(bereiche):
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from programm.kern.zusammenfuegen import fuege_hinzu
    haupt = lade_alles(str(bereiche["Ganz"]))
    zusatz = lade_alles(str(bereiche["Innenloch"]))
    p = _profil(zusatz)
    nr, (idx, teil) = next(iter(p.profilausschnitte.items()))
    original = GProp_GProps()
    brepgprop.SurfaceProperties(teil, original)
    grenzen = [k for _, k in p.bereichsgrenzen]
    lage = (25., -33., 70.)
    neu = fuege_hinzu(haupt, zusatz, lage)
    verschoben = GProp_GProps()
    offset = neu.zusaetze[0].id_versatz
    basis, form = p.profilausschnitte[nr + offset]
    brepgprop.SurfaceProperties(form, verschoben)
    assert basis == idx + len(haupt.modell.flaechen)
    assert [k for _, k in p.bereichsgrenzen] == [k + offset for k in grenzen]
    mitte = original.CentreOfMass().Coord()
    assert verschoben.CentreOfMass().Coord() == pytest.approx([x + y for x, y in zip(mitte, lage)])
    assert toleranzzone.zone(p, neu.modell).quellen_je_form() == [{basis}, {basis}]


def test_auswahl_zeigt_nur_den_getrimmten_bereich(fenster, bereiche, tmp_path):
    f = fenster
    f.lade(str(bereiche["Innenloch"]), warten=True)
    p = _profil(f.erg)
    f.pmi.waehle(lambda q: q.step_id == p.step_id)
    a = f.ansicht
    assert not a.hervor and a.pmi_ids_hervor == {p.step_id}
    assert a.szene.profilbereiche[p.step_id] == p.profilausschnitte
    f.aktionen["toleranzzone"].trigger()
    assert [_inhalt(form) for form in a.zone_formen] == pytest.approx([900., 900.])
    if getattr(a, "_bereit", False):
        (nr, ais), = a._profil_ais
        assert a.d.Context.IsDisplayed(ais) and _inhalt(ais.Shape()) == pytest.approx(900.)
    traeger, = p.traegerflaechen()
    blatt = f._flaechen_besitzer(list(f.erg.baum.blaetter()))[traeger]
    a.knoten_sichtbar({blatt.nummer}, False)
    assert not a.zone_formen
    if getattr(a, "_bereit", False):
        assert not a.d.Context.IsDisplayed(ais)
    a.knoten_sichtbar({blatt.nummer}, True)
    assert [_inhalt(form) for form in a.zone_formen] == pytest.approx([900., 900.])
    if getattr(a, "_bereit", False):
        assert a.d.Context.IsDisplayed(ais)
    f.pmi.waehle(lambda q: False)
    assert not a.pmi_ids_hervor and not getattr(a, "_profil_ais", ())
    f.bearbeite_pmi(p, {"wert": .8})
    projekt = f.speichere_projekt(str(tmp_path / "Ausschnitt.3dgmax"))
    f.oeffne_projekt(projekt, warten=True)
    geladen = _profil(f.erg)
    assert geladen.wert == .8 and geladen.profilausschnitte.keys() == p.profilausschnitte.keys()
    kopie = f.speichere_step_pmi(str(tmp_path / "Bearbeitet.step"), melden=False)
    e = lade_alles(kopie)
    q = _profil(e)
    assert q.wert == .8 and q.bereichsgrenzen == p.bereichsgrenzen
    assert q.profilausschnitte.keys() == p.profilausschnitte.keys()
    assert _inhalt(next(iter(q.profilausschnitte.values()))[1]) == pytest.approx(900.)
    assert q.step_id in e.grafik[3422].pmi_ids
    from programm.kern import pmi_bericht
    zeile, = pmi_bericht.tabelle([q], [], e.modell)
    assert zeile["Flächen"] == 1 and zeile["Flächen (STEP-#ID)"] == f"#{next(iter(q.profilausschnitte))}"
    assert all(b.text != "Keine Fläche zugeordnet" for b in pmi_bericht.pruefe([q], modell=e.modell))
    assert not a.hervor


def _grafischer_bereich(bereiche, ordner, schrift):
    from dataclasses import replace
    from tests.test_profilbereich import _als_strichschrift, _fuellsatz
    quelle = pfad("nist_ctc_01_asme1_ap203.stp.gz")
    e = lade_alles(quelle)
    with gzip.open(quelle, "rt", encoding="ascii") as f:
        text = f.read()
    verschiebung = {3425: [10, 0, 0], 3412: [-70, -50, 0]}
    if schrift == "fuellung":
        grafiken = dict(e.grafik)
        for nr, lage in verschiebung.items():
            g = grafiken[nr]
            grafiken[nr] = replace(g, linien=[l + lage for l in g.linien])
        text = _fuellsatz(text, grafiken)
    else:
        from programm.kern.step_ap242 import aus_ap203
        # Die topologische Flaechenmenge als Ziel der GISU gehoert zum AP242-Select.
        text = _als_strichschrift(aus_ap203(text, e.modell.datei), e.grafik)
        temp = ordner / "Strich.step"
        temp.write_text(text, encoding="ascii")
        grafiken = lade_alles(str(temp)).grafik
        zeilen = []
        nr = 150000
        for cid, satz in ((3425, 4143), (3412, 4130)):
            refs = []
            for zug in grafiken[cid].linien:
                punkte = []
                for xyz in zug + verschiebung[cid]:
                    zeilen.append(f"#{nr}=CARTESIAN_POINT('',({','.join(f'{a:.10f}' for a in xyz)}));")
                    punkte.append(f"#{nr}")
                    nr += 1
                zeilen.append(f"#{nr}=POLYLINE('',({','.join(punkte)}));")
                refs.append(f"#{nr}")
                nr += 1
            text, n = re.subn(rf"(#{satz}=GEOMETRIC_CURVE_SET\('[^']*',)\([^;]+;",
                              rf"\g<1>({','.join(refs)}));", text)
            assert n == 1
        pos = text.rindex("ENDSEC;")
        text = text[:pos] + "\n".join(zeilen) + "\n" + text[pos:]
    teile = re.findall(r"#11\d{4}\s*=[^;]+;", bereiche["Innenloch"].read_text())
    zusatz = ["#130000=CONNECTED_FACE_SET('',(#110017));", "#130001=SHAPE_REPRESENTATION('',(#130000),#17160);",
              "#130002=GEOMETRIC_ITEM_SPECIFIC_USAGE('','PMI',#189,#130001,#130000);"]
    text, n = re.subn(r"#(119|120|121)=GEOMETRIC_ITEM_SPECIFIC_USAGE\([^;]+;", "", text)
    assert n == 3
    for nr, kante in ((128, 110021), (129, 110021), (90, 110060), (91, 110060)):
        text, n = re.subn(rf"(#{nr}=GEOMETRIC_ITEM_SPECIFIC_USAGE\('','PMI',#\d+,)#148,#\d+\);",
                          rf"\g<1>#130001,#{kante});", text)
        assert n == 1
    pos = text.rindex("ENDSEC;")
    pf = ordner / "Nur Grafik.step"
    pf.write_text(text[:pos] + "\n".join(teile + zusatz) + "\n" + text[pos:], encoding="ascii")
    return pf


@pytest.mark.parametrize("schrift", ["fuellung", "strich"])
def test_teilbereich_aus_grafik(fenster, bereiche, tmp_path, schrift):
    import numpy as np
    from tests.test_step_ap242 import _occt
    from programm.kern.pmi_freier_hinweis import _ansichten
    pf = _grafischer_bereich(bereiche, tmp_path, schrift)
    fenster.lade(str(pf), warten=True)
    e = fenster.erg
    grenzen = [["A", 110021], ["B", 110060]]
    for nr in (3417, 3427, 3414, 3422):
        original = next(p for p in e.pmi if p.step_id == nr)
        fenster._pmi_befehl("semantisch", original)
        dialog = fenster._semantik_dialog
        assert not dialog.fehler()
        if nr == 3422:
            assert dialog.v.wert == 1.25 and dialog.v.bereichsgrenzen == grenzen
            assert dialog.v.profilteil_ids == [110017] and not dialog.flaechen
            assert len(dialog.v.traegerflaechen()) == 1
            assert "#110017" in dialog.flaechen_text.text()
            if getattr(fenster.ansicht, "_bereit", False):
                (_, ais), = fenster.ansicht._profil_ais
                assert fenster.ansicht.d.Context.IsDisplayed(ais) and _inhalt(ais.Shape()) == pytest.approx(900.)
        dialog._pruefen()
    projekt = fenster.speichere_projekt(str(tmp_path / "Geprueft.3dgmax"))
    fenster.oeffne_projekt(projekt, warten=True)
    p = _profil(fenster.erg)
    assert p.profilteil_ids == [110017] and p.profilausschnitte.keys() == {110017}
    assert not p.flaechen and fenster.ansicht.szene.profilbereiche[p.step_id] == p.profilausschnitte
    r = fenster.erg.modell._reader.ChangeReader()
    anzahl = r.StepModel().NbEntities()
    assert anzahl > 0
    assert r.StepModel().IdentLabel(r.StepModel().Value(r.WS().NumberFromLabel("#110017"))) == 110017
    ausgabe = fenster.speichere_step_pmi(str(tmp_path / "Semantik und Grafik.step"), melden=False)
    assert not fenster._step_bericht.uebersprungen and r.StepModel().NbEntities() == anzahl
    bezuege = [b for b in fenster.erg.pmi if b.quelle == "eigen" and b.art == "bezug"]
    fenster.lade(ausgabe, warten=True)
    neu = fenster.erg
    q = _profil(neu)
    fenster.pmi.waehle(lambda p: p is q)
    assert q.grenzgrafiken == [3425, 3412]
    assert fenster.ansicht.pmi_ids_hervor == {q.step_id, 3425, 3412}
    assert q.typ == "ProfileOfSurface" and q.wert == 1.25 and q.bereichsgrenzen == grenzen
    from programm.kern.merkmalstext import aspekte_am_callout
    datei = neu.modell.datei
    for rolle, cid in (("start feature", 3425), ("end feature", 3412)):
        rel, = [e for e in datei.of_type("SHAPE_ASPECT_RELATIONSHIP") if e.args()[0] == rolle]
        assert rel.args()[3].id in aspekte_am_callout(datei, cid)
    assert [b.name for b in q.bezuege] == ["A", "B", "C"]
    assert not q.flaechen and q.profilausschnitte.keys() == {110017}
    assert [_inhalt(f) for f in toleranzzone.zone(q, neu.modell).formen] == pytest.approx([900., 900.])
    assert _occt(ausgabe)[1:] == _occt(pf)[1:] and q.step_id in neu.grafik[3422].pmi_ids
    for nr in (3422, 3425, 3412):
        g, h = e.grafik[nr], neu.grafik[nr]
        assert bool(h.dreiecke) == (schrift == "fuellung") and bool(h.linien) == (schrift == "strich")
        for a, b in zip(g.linien, h.linien, strict=True):
            np.testing.assert_array_equal(a, b)
        for (a, b), (c, d) in zip(g.dreiecke, h.dreiecke, strict=True):
            np.testing.assert_array_equal(a, c)
            np.testing.assert_array_equal(b, d)
        assert _ansichten(e.modell.datei, nr) == _ansichten(neu.modell.datei, nr)
    if schrift == "fuellung":
        from dataclasses import replace
        for falsch in (replace(p, grenzgrafiken=list(reversed(p.grenzgrafiken))),
                       replace(p, flaechen=p.traegerflaechen()), replace(p, profilteil_ids=[553])):
            ziel = tmp_path / "Unpassender Bereich.step"
            bericht = step_schreiben.schreibe(str(pf), str(ziel), [*bezuege, falsch], e.modell)
            assert p.nummer not in bericht.repariert and len(bericht.uebersprungen) == 1
            assert not any(q.bereichsgrenzen for q in lade_alles(str(ziel)).pmi)

def test_teilbereich_braucht_beide_randpfeile(bereiche, tmp_path):
    from programm.kern import pmi_reparieren, pmi_zwischenbereich
    pf = _grafischer_bereich(bereiche, tmp_path, "fuellung")
    text = pf.read_text()
    # Der gezeichnete B-Pfeil zeigt auf die urspruengliche Aussenkante, die Zuordnung jetzt in das Loch.
    for nr in (90, 91):
        text, n = re.subn(rf"(#{nr}=GEOMETRIC_ITEM_SPECIFIC_USAGE[^;]+,)#110060", r"\g<1>#110092", text)
        assert n == 1
    pf.write_text(text)
    e = lade_alles(str(pf))
    original = next(p for p in e.pmi if p.step_id == 3422)
    g = e.grafik[original.step_id]
    v = pmi_reparieren.vorschlag(original, g, e.modell)
    pmi_zwischenbereich.ergaenze(v, g, e.modell, e.grafik)
    assert not v.profilteil_ids and not v.bereichsgrenzen and v.wert is None
