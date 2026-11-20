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


def _schreibe(pfad, netze):
    if pfad.suffix == ".obj":
        start = 1
        with pfad.open("w") as f:
            f.write("o Getriebe\n")
            for p, ix in netze:
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
