"""Einzelrad und zwei Stufen durch den echten STL-/OBJ-Import samt Analyse-Worker."""

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from programm.kern import verzahnung as vz
from programm.kern import verzahnung_daten as vd
from programm.kern.laden import lade_modell
from programm.ui.verzahnung_ui import VerzahnungLader


def _radnetz(z, x=0., axial=0., beta=0., flanke=12):
    from werkzeuge.zahnrad import stirnschnitt
    q = stirnschnitt(z, 2., beta=beta, flanke=flanke)
    n = len(q)
    rate = np.tan(np.radians(beta)) * np.cos(np.radians(beta)) / z
    ringe = []
    lagen = np.linspace(0, 6, 5 if beta else 2)
    for s in lagen:
        phi = s * rate
        xy = q @ np.array([[np.cos(phi), np.sin(phi)], [-np.sin(phi), np.cos(phi)]])
        ringe.append(np.c_[xy, np.full(n, s)])
    p = np.vstack([*ringe, [0, 0, 0], [0, 0, 6]]) + [x, 0, axial]
    i, j = np.arange(n), np.roll(np.arange(n), -1)
    ix = [np.c_[j, i, np.full(n, len(p) - 2)], np.c_[i+n*(len(lagen)-1), j+n*(len(lagen)-1), np.full(n, len(p)-1)]]
    for k in range(len(lagen) - 1):
        ix.extend([np.c_[i, j, j+n] + k*n, np.c_[i, j+n, i+n] + k*n])
    rot = Rotation.from_rotvec([.31, -.42, .18])
    return rot.apply(p) + [26, -45, 32], np.vstack(ix)


def _schreibe(pfad, netze, *, getrennt=False):
    if pfad.suffix == ".obj":
        start = 1
        with pfad.open("w") as f:
            f.write("o Getriebe\n")
            for i, (p, ix) in enumerate(netze):
                if i and getrennt:
                    f.write(f"o Rad{i+1}\n")
                np.savetxt(f, p, fmt="v %.10f %.10f %.10f")
                np.savetxt(f, ix + start, fmt="f %d %d %d")
                start += len(p)
    else:
        daten = np.vstack([p[ix] for p, ix in netze])
        dt = np.dtype([("normal", "<f4", (3,)), ("punkte", "<f4", (3, 3)), ("attribut", "<u2")])
        facetten = np.zeros(len(daten), dtype=dt)
        facetten["punkte"] = daten
        with pfad.open("wb") as f:
            f.write(bytes(80))
            f.write(len(daten).to_bytes(4, "little"))
            f.write(facetten.tobytes())
    return lade_modell(str(pfad))


@pytest.mark.parametrize("endung", ["stl", "obj"])
def test_einzelrad_aus_netzdatei(tmp_path, endung):
    from programm.kern.laden import ist_netz
    modell = _schreibe(tmp_path / f"schraeg.{endung}", [_radnetz(17, beta=15.)])
    assert ist_netz(modell)
    rad = vz.erkenne(modell.form, "schräg")
    assert rad.z == 17 and rad.teil == "schräg"
    assert rad.beta == pytest.approx(15, abs=.12)
    assert rad.mn == pytest.approx(2, abs=.01)
    assert rad.hand == "rechts" and any("Dreiecksflächen" in h for h in rad.hinweise)
    assert rad.kopffase is None and rad.fussradius is None


@pytest.mark.parametrize("endung", ["stl", "obj"])
def test_zwei_stufen_aus_einem_netzobjekt(tmp_path, endung, app):
    modell = _schreibe(tmp_path / f"stufen.{endung}", [
        _radnetz(14), _radnetz(20, 34), _radnetz(16, 34, 10), _radnetz(24, 74, 10)])
    worker = VerzahnungLader([("Getriebe", modell.form)])
    listen = []
    worker.fertig.connect(listen.append)
    worker.run()
    raeder = listen[0]
    assert sorted(v.z for v in raeder) == [14, 16, 20, 24]
    assert len({v.teil for v in raeder}) == 4
    paare = vz.paare(raeder)
    assert {tuple(sorted([p.a.z, p.b.z])) for p in paare} == {(14, 20), (16, 24)}
    assert sorted(p.abstand for p in paare) == pytest.approx([34., 40.], abs=.01)
    daten = vd.datenblatt(raeder, paare)
    assert len(daten["stufen"]) == 2 and len(daten["wellen"]) == 3


def test_aufloesung_des_importierten_netzes(tmp_path):
    # Unterabgetastete Evolvente nicht identifizieren. Bei mehr Facetten sinkt der tatsaechliche Fitfehler.
    werte = []
    for flanke in (2, 6, 12):
        modell = _schreibe(tmp_path / f"stirnrad{flanke}.stl", [_radnetz(17, flanke=flanke)])
        raeder = list(vz.erkenne_koerper(modell.form, "STL", steckprofile=True, sonderprofile=True))
        if flanke == 2:
            assert not raeder
        else:
            v, = raeder
            assert v.z == 17 and v.mn == pytest.approx(2, abs=.004)
            werte.append(v.fit_fehler)
    assert werte[1] < werte[0] / 2


def test_stufen_eines_step_baumblatts(tmp_path):
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.TopoDS import TopoDS_Compound
    from OCC.Core.gp import gp_Trsf, gp_Vec
    from werkzeuge.zahnrad import zahnrad

    comp = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(comp)
    for z, x, s in [(14, 0, 0), (20, 34, 0), (16, 34, 10), (24, 74, 10)]:
        trsf = gp_Trsf()
        trsf.SetTranslation(gp_Vec(x, 0, s))
        builder.Add(comp, zahnrad(z, 2., 6.).Moved(TopLoc_Location(trsf)))
    pfad = tmp_path / "radgruppe.step"
    writer = STEPControl_Writer()
    writer.Transfer(comp, STEPControl_AsIs)
    writer.Write(str(pfad))
    raeder = list(vz.erkenne_koerper(lade_modell(str(pfad)).form, "Gruppe"))
    assert sorted(v.z for v in raeder) == [14, 16, 20, 24]
    paare = vz.paare(raeder)
    assert len(vd.stufen(raeder, paare, [])[0]) == 2


def test_planetengetriebe_mit_stirnradvorstufe_aus_einem_stl(tmp_path):
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.StlAPI import StlAPI_Writer
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.TopoDS import TopoDS_Compound
    from OCC.Core.gp import gp_Trsf, gp_Vec
    from programm.kern.getriebe_betrieb import Betriebsmodell
    from werkzeuge.zahnrad import zahnrad

    bau, koerper = BRep_Builder(), TopoDS_Compound()
    bau.MakeCompound(koerper)

    def dazu(form, x=0., y=0., h=0.):
        pos = gp_Trsf()
        pos.SetTranslation(gp_Vec(x, y, h))
        bau.Add(koerper, form.Moved(TopLoc_Location(pos)))

    klein = zahnrad(18, 1.5, 6.)
    dazu(klein)
    dazu(zahnrad(54, 1.5, 6., innen=True))
    for winkel in np.radians([0, 120, 240]):
        dazu(klein, 27 * np.cos(winkel), 27 * np.sin(winkel))
    dazu(zahnrad(24, 1.5, 6.), h=12.)
    dazu(zahnrad(12, 1.5, 6.), x=27., h=12.)
    pfad = str(tmp_path / "Umlaufgetriebe.stl")
    BRepMesh_IncrementalMesh(koerper, .005)
    assert StlAPI_Writer().Write(koerper, pfad)

    raeder = list(vz.erkenne_koerper(lade_modell(pfad).form, "Getriebe", steckprofile=True, sonderprofile=True))
    assert sorted(v.z for v in raeder) == [12, 18, 18, 18, 18, 24, 54]
    modell = Betriebsmodell(raeder, vz.paare(raeder))
    betrieb = modell.betrieb()
    satz, = betrieb.saetze
    sonne, ring, steg = satz["wellen"]
    assert len(satz["umlaufraeder"]) == 3
    an, ab = (modell.welle[next(i for i, v in enumerate(raeder) if v.z == z)] for z in [12, 24])
    assert len(modell.gruppen[an]) == 1
    for fest, ziel, soll in [(ring, steg, -150.), (steg, ring, 200.)]:
        ergebnis = betrieb.auswerten({an: 1200., fest: 0.}, [(ab, sonne)])
        drehzahlen = {w["id"]: w["drehzahl"] for w in ergebnis["wellen"]}
        assert drehzahlen[sonne] == pytest.approx(-600.)
        assert drehzahlen[ziel] == pytest.approx(soll)


@pytest.mark.parametrize("getrennt", [False, True])
def test_getriebehinweis_an_obj_quellflaechen(tmp_path, getrennt):
    from programm.kern.plausibilitaet import verzahnung
    from programm.kern.pmi import Pmi
    from programm.kern.pmi_bericht import FEHLER, INFO
    modell = _schreibe(tmp_path / "paar.obj", [_radnetz(14), _radnetz(20, 34)], getrennt=getrennt)
    letzte = len(modell.flaechen)-1
    notizen = [Pmi("hinweis", nummer=1, name="z = 15", flaechen={0}),
               Pmi("hinweis", nummer=2, name="z = 19", flaechen={letzte})]
    a, b = verzahnung(notizen, modell)
    assert (a.nummern, b.nummern, a.flaechen, b.flaechen) == ([1], [2], {0}, {letzte})
    if getrennt:
        assert letzte == 1 and a.stufe == b.stufe == FEHLER
        assert "14" in a.text.split(",")[-1] and "20" in b.text.split(",")[-1]
    else:
        assert letzte == 0 and a.stufe == b.stufe == INFO


def test_gemeinsame_netzflaeche_mit_kleinem_nebenkoerper(tmp_path):
    from programm.kern.plausibilitaet import verzahnung
    from programm.kern.pmi import Pmi
    from programm.kern.pmi_bericht import INFO
    platte = np.array([[50., 50., 0.], [52., 50., 0.], [52., 52., 0.]])
    modell = _schreibe(tmp_path / "RadUndPlatte.stl", [_radnetz(14), (platte, np.array([[0, 1, 2]]))])
    hinweis = Pmi("hinweis", nummer=1, name="z = 15", flaechen={0})
    b, = verzahnung([hinweis], modell)
    assert b.stufe == INFO and b.flaechen == {0}
