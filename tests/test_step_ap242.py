"""AP203e2-Kurven-PMI nach AP242e3: Geometrie, Verwaltungsdaten und Kameras bleiben verknuepft."""

import gzip

import numpy as np
import pytest
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.GProp import GProp_GProps
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.STEPControl import STEPControl_Reader

from programm.kern import p21, step_ap242
from programm.kern.praesentation import lies_grafik
from tests.conftest import pfad


@pytest.fixture(scope="module")
def quelle():
    with gzip.open(pfad("nist_ctc_01_asme1_ap203.stp.gz"), "rt", encoding="ascii") as f:
        return f.read()


def _occt(pfad):
    r = STEPControl_Reader()
    assert r.ReadFile(str(pfad)) == IFSelect_RetDone
    m = r.StepModel()
    typen, beanstandungen = {}, []
    for j in range(1, m.NbEntities() + 1):
        e = m.Value(j)
        nr = m.IdentLabel(e)
        typen[nr] = e.DynamicType().Name()
        c = m.Check(j, True)
        beanstandungen.extend((nr, c.CFail(k)) for k in range(1, c.NbFails() + 1))
    assert r.TransferRoots() == 1
    volumen = GProp_GProps()
    brepgprop.VolumeProperties(r.OneShape(), volumen)
    return typen, beanstandungen, volumen.Mass()


def test_original_ctc01_in_ap242_mit_kurven_und_verwaltungsdaten(quelle, tmp_path):
    d = p21.lese_text(quelle)
    konvertiert = step_ap242.aus_ap203(quelle, d)
    neu = p21.lese_text(konvertiert)
    assert neu.schema == step_ap242.SCHEMA and d.entities.keys() == neu.entities.keys()
    geaendert = {e.id for e in d.of_types_by_id(("APPLICATION_CONTEXT", "APPLICATION_PROTOCOL_DEFINITION", "ANNOTATION_OCCURRENCE"))}
    assert all(neu.get(i) == e for i, e in d.entities.items() if i not in geaendert)
    assert neu.get(3410).args("STYLED_ITEM") == d.get(3410).args()[1:]
    alt_g, neu_g = lies_grafik(d), lies_grafik(neu)
    assert alt_g.keys() == neu_g.keys() and len(alt_g) == 21
    for k, g in alt_g.items():
        g2 = neu_g[k]
        assert (g.name, g.farbe, g.pmi_ids) == (g2.name, g2.farbe, g2.pmi_ids)
        assert len(g.linien) == len(g2.linien) and g.linien
        assert all(np.array_equal(a, b) for a, b in zip(g.linien, g2.linien))
    alt, ziel = tmp_path / "ursprung.stp", tmp_path / "uebertragen.stp"
    alt.write_text(quelle, encoding="ascii")
    ziel.write_text(konvertiert, encoding="ascii")
    typen, fehler, volumen = _occt(alt)
    typen_neu, fehler_neu, volumen_neu = _occt(ziel)
    assert volumen > 0 and volumen_neu == pytest.approx(volumen) and fehler_neu == fehler
    assert typen.keys() == typen_neu.keys()
    assert all(typen_neu[k] == "StepVisual_AnnotationCurveOccurrenceAndGeomReprItem" for k in alt_g)
    assert all(typen_neu[k] == t for k, t in typen.items() if k not in alt_g)


@pytest.mark.parametrize("suchen,ersatz", [
    ("{ 1 0 10303 403 3 1 4}", "{ 1 0 10303 403 2 1 2}"),
    ("#3410=ANNOTATION_OCCURRENCE(", "#3410=SOME_ANNOTATION("),
    ("'radial dimension',(#3431),#4128", "'radial dimension',(#3431),#3431"),
    ("#3410=ANNOTATION_OCCURRENCE(", "#3410=COLOUR();\n#3410=ANNOTATION_OCCURRENCE("),
    ("END-ISO-10303-21;", "DATA;ENDSEC;END-ISO-10303-21;"),
])
def test_ungeklaerte_abbildung_liefert_keine_ap242_kopie(quelle, suchen, ersatz):
    text = quelle.replace(suchen, ersatz, 1)
    assert text != quelle
    with pytest.raises(ValueError):
        step_ap242.aus_ap203(text, p21.lese_text(text))


def test_textliteral_und_kommentar_sind_keine_step_anweisungen(quelle):
    name = "radial ''dimension''; #2=COLOUR();"
    alt = quelle.replace("'radial dimension'", "'" + name + "'", 1)
    alt = alt.replace("#3410=ANNOTATION_OCCURRENCE", "/* #3432=COLOUR(); */ #3410=ANNOTATION_OCCURRENCE", 1)
    text = step_ap242.aus_ap203(alt, p21.lese_text(alt))
    assert "/* #3432=COLOUR(); */ #3410=" in text
    assert p21.lese_text(text).get(3410).args("REPRESENTATION_ITEM") == [name.replace("''", "'")]


@pytest.mark.parametrize(("modell", "anzahl"), [("03", 29), ("05", 22)])
def test_nist_zoll_und_rationale_flaechen(modell, anzahl):
    from pathlib import Path
    from programm.kern.pmi_step import einheit_mm
    ordner = Path(__file__).resolve().parents[1] / "daten/nist/NIST-PMI-STEP-Files/AP203 with PMI"
    pfad = ordner / f"nist_ctc_{modell}_asme1_ap203.stp"
    if not pfad.is_file():
        pytest.skip("Optionales NIST-Referenzmodell fehlt")
    quelle = pfad.read_text(encoding="ascii")
    alt = p21.lese_text(quelle)
    neu = p21.lese_text(step_ap242.aus_ap203(quelle, alt))
    assert len(neu.of_type("ANNOTATION_CURVE_OCCURRENCE")) == anzahl
    einheiten = [e for e in neu.of_type("CONVERSION_BASED_UNIT") if e.is_a("LENGTH_UNIT")]
    assert einheiten and all(einheit_mm(neu, p21.Ref(e.id)) == pytest.approx(25.4) for e in einheiten)
    if modell == "05":
        rational = neu.of_type("RATIONAL_B_SPLINE_SURFACE")
        assert rational and all(e == alt.get(e.id) for e in rational)
