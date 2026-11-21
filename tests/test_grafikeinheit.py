"""Einheiten von Zeichenmodellen getrennt von der Einheit der Geometrie auswerten."""

from types import SimpleNamespace

import pytest

from programm.kern import p21
from programm.kern.ansichten import lies_ansichten
from programm.kern.praesentation import lies_grafik


def test_grafik_und_kamera_der_originalen_zolldatei(app):
    from programm.ui.lader import lade_alles
    from tests.conftest import pfad
    erg = lade_alles(pfad("nist_ftc_07_asme1_ap242-e2.stp"))
    g = erg.grafik[16200]
    assert g.textfaktor == 25.4 and g.ebene[0] == pytest.approx((-91.44,0.,0.))
    assert g.grenzen()[1] == pytest.approx((-91.44,44.5219582,133.2154816))
    kamera = next(a for a in erg.ansichten if a.step_id == 16577)
    assert kamera.breite == pytest.approx(17.4855982*25.4)
    assert kamera.abstand == pytest.approx(36.4163905*25.4)
    assert kamera.ort[0] == pytest.approx(-703.9650879)


def test_getrennte_kontexte_fuer_schrift_ebenen_und_kamera():
    from programm.kern.pmi_ableiten import aus_text
    d = p21.lese_text("""DATA;
#1=(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.));
#2=LENGTH_MEASURE_WITH_UNIT(LENGTH_MEASURE(25.4),#1);
#3=(CONVERSION_BASED_UNIT('inch',#2) LENGTH_UNIT() NAMED_UNIT(*));
#4=(GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNIT_ASSIGNED_CONTEXT((#1)) REPRESENTATION_CONTEXT('',''));
#5=(GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNIT_ASSIGNED_CONTEXT((#3)) REPRESENTATION_CONTEXT('',''));
#6=CARTESIAN_POINT('',(2.,3.,4.));
#7=AXIS2_PLACEMENT_3D('',#6,$,$);
#8=PLANAR_EXTENT('',2.,1.);
#9=TEXT_LITERAL_WITH_EXTENT('','R2',#7,'center',.RIGHT.,$,#8);
#10=ANNOTATION_TEXT_OCCURRENCE('',(),#9);
#11=DRAUGHTING_CALLOUT('a',(#10));
#12=DRAUGHTING_CALLOUT('b',(#10));
#13=DRAUGHTING_CALLOUT('c',(#10));
#14=PLANE('',#7);
#15=ANNOTATION_PLANE('',(),#14,(#12));
#16=PLANAR_BOX('',10.,8.,#7);
#17=VIEW_VOLUME(.PARALLEL.,#6,12.,0.,.F.,0.,.F.,.F.,#16);
#18=CAMERA_MODEL_D3('mm',#7,#17);
#19=CAMERA_MODEL_D3('inch',#7,#17);
#20=DRAUGHTING_MODEL('',(#11,#13,#18,#22),#4);
#21=DRAUGHTING_MODEL('',(#15,#13,#19),#5);
#22=DRAUGHTING_CALLOUT('d',(#10));
#23=DRAUGHTING_MODEL_ITEM_ASSOCIATION('','',#24,#21,#22);
#24=SHAPE_ASPECT('','',$,.F.);
ENDSEC;""")
    grafiken = lies_grafik(d)
    for nr, faktor in ((11,1.),(12,25.4),(22,25.4)):
        g = grafiken[nr]
        ph, = g.platzhalter
        assert g.textfaktor == faktor and ph.ursprung == pytest.approx((2*faktor,3*faktor,4*faktor))
        assert (ph.breite,ph.hoehe) == pytest.approx((2*faktor,faktor))
        assert aus_text([ph.text],g.textfaktor)["nennwert"] == pytest.approx(2*faktor)
    g = grafiken[13]
    assert g.textfaktor is None and aus_text([g.platzhalter[0].text],g.textfaktor) is None
    assert aus_text(["R2 mm"],g.textfaktor)["nennwert"] == 2.
    assert grafiken[22].kontext == 5 and grafiken[22].pmi_ids == {24}
    ansichten = lies_ansichten(SimpleNamespace(datei=d))
    assert {a.name for a in ansichten} == {"inch","mm"}
    for a in ansichten:
        faktor = {"inch":25.4,"mm":1.}[a.name]
        assert a.ort == pytest.approx((2*faktor,3*faktor,4*faktor))
        assert (a.breite,a.hoehe,a.abstand) == pytest.approx((10*faktor,8*faktor,12*faktor))
        assert a.richtung == (0.,0.,1.)
