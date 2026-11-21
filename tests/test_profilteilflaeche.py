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
