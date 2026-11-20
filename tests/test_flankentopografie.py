import csv
import io
import math

import numpy as np
import pytest

from programm.kern import flankentopografie, verzahnung, verzahnung_daten


@pytest.mark.parametrize("endung", ["step", "stl"])
def test_einzelner_zahnversatz_im_importierten_rad(tmp_path, endung, app):
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from OCC.Core.StlAPI import StlAPI_Writer
    from OCC.Core.gp import gp_Vec
    from programm.kern.laden import lade_modell
    from werkzeuge import zahnrad

    z = 24
    kontur = zahnrad.stirnschnitt(z, 2., flanke=32)
    am_zahn = np.abs(np.arctan2(kontur[:, 1], kontur[:, 0])) < math.pi / z
    winkel = .06 / (z * math.cos(math.radians(20)))
    c, s = math.cos(winkel), math.sin(winkel)
    kontur[am_zahn] = kontur[am_zahn] @ np.array([[c, s], [-s, c]])
    stirn = BRepBuilderAPI_MakeFace(zahnrad._draht(kontur, 0.)).Face()
    form = BRepPrimAPI_MakePrism(stirn, gp_Vec(0, 0, 10)).Shape()
    pfad = str(tmp_path / f"versatz.{endung}")
    if endung == "stl":
        BRepMesh_IncrementalMesh(form, .01, False, .5, False)
        assert StlAPI_Writer().Write(form, pfad)
    else:
        writer = STEPControl_Writer()
        writer.Transfer(form, STEPControl_AsIs)
        writer.Write(pfad)
    modell = lade_modell(pfad)
    rad, = verzahnung.erkenne_koerper(modell.form, "Versatz")
    daten = verzahnung_daten.datenblatt([rad], [])["zahnraeder"][0]["mikrogeometrie"]
    raster = daten["flankenkarte_stirnschnitt"]
    j = int(np.argmin(np.abs(np.array(raster["radius_mm"]) - rad.d / 2)))
    for seite in ("links", "rechts"):
        assert daten["spannweite_teilkreis_mm"][seite] == pytest.approx(.06, abs=.003)
        np.testing.assert_allclose(np.array(raster[f"spannweite_{seite}_mm"])[:, j], .06, atol=.003)
        assert np.max(np.abs(np.array(raster[f"{seite}_mm"])[:, j])) < .005
    zeilen = list(csv.reader(io.StringIO(verzahnung_daten.als_csv([rad], [])), delimiter=";"))
    for name in ("Linke Flanke", "Rechte Flanke"):
        i = zeilen.index(["Versatz", name, "Spannweite zwischen den Zähnen (mm)"])
        assert float(zeilen[i+2][j+1]) == pytest.approx(.06, abs=.003)
    if endung == "step":
        from pypdf import PdfReader
        from programm.ui.verzahnung_ui import VerzahnungFenster
        fenster = VerzahnungFenster([rad], "")
        bericht = fenster.speichere("pdf", str(tmp_path / "rad.pdf"))
        text = " ".join(seite.extract_text() for seite in PdfReader(bericht).pages)
        assert "Flankenstreuung links" in text and "Flankenstreuung rechts" in text
        fenster.close()


@pytest.mark.parametrize("innen", [False, True])
def test_flankenstreuung_ueber_winkelnaht_und_unvollstaendige_teilung(innen):
    z = 64
    teilung = 2 * np.pi / z
    t = np.linspace(-np.pi, np.pi, 32768, endpoint=False)
    # Ein Zahn liegt ueber der Naht des Winkelrasters.
    mitten = -np.pi + np.arange(z) * teilung

    def kontur(zentren):
        profil = np.full_like(t, -1.)
        for mitte in zentren:
            d = np.abs((t - mitte + np.pi) % (2 * np.pi) - np.pi)
            profil = np.maximum(profil, 1 - 12 * d / teilung)
        return 10 - profil if innen else 10 + profil

    _, streuung = flankentopografie._flankenwinkel(kontur(mitten + .42 * teilung), 10., z, innen)
    np.testing.assert_allclose(streuung, 0., atol=1e-13)
    mitten[2] = mitten[3] + .3 * teilung
    assert flankentopografie._flankenwinkel(kontur(mitten), 10., z, innen) is None
