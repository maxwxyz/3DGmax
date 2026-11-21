"""Nur der am Callout hinterlegte Wortlaut gehoert zu dessen Pruefung."""

import pytest

from programm.kern.p21 import lese_text
from programm.kern.praesentation import Grafik
from programm.kern.pmi_validierungstext import validierungsvorschlag


def _quelle(wort, *, inhaber="#3", modell="#5", extras=""):
    return lese_text(r"""DATA;
#1=ANNOTATION_CURVE_OCCURRENCE('',(),$);
#3=DRAUGHTING_CALLOUT('A',(#1));
#4=DRAUGHTING_CALLOUT('B',(#1));
#5=DRAUGHTING_MODEL('',(#3),#99);
#6=DRAUGHTING_MODEL('',(#4),#99);
#7=CHARACTERIZED_ITEM_WITHIN_REPRESENTATION('','',INHABER,MODELL);
#8=PROPERTY_DEFINITION('pmi validation property','',#7);
#9=PROPERTY_DEFINITION_REPRESENTATION(#8,#10);
#10=REPRESENTATION('',(#11),#99);
#11=DESCRIPTIVE_REPRESENTATION_ITEM('equivalent unicode string','WORT');
EXTRAS
ENDSEC;""".replace("INHABER",inhaber).replace("MODELL",modell).replace("WORT",wort).replace("EXTRAS",extras))


def _lies(d, typ=None, faktor=25.4):
    return validierungsvorschlag(d, Grafik(3, textfaktor=faktor), typ)[:2]


@pytest.mark.parametrize("inhaber,modell", [("#4","#5"),("#3","#6"),("#99","#5")])
def test_fremde_grafik_und_fremdes_zeichenmodell_in_der_eigenschaft(inhaber,modell):
    assert _lies(_quelle(r"DIM\wR2",inhaber=inhaber,modell=modell)) == ((),{})


def test_zwei_quelltexte_duplikat_oder_widerspruch():
    extras = r"""#15=PROPERTY_DEFINITION_REPRESENTATION(#8,#16);
#16=REPRESENTATION('',(#17),#99);
#17=DESCRIPTIVE_REPRESENTATION_ITEM('equivalent unicode string','DIM\wR2');"""
    tex, felder = _lies(_quelle(r"DIM\\wR2",extras=extras))
    assert tex == ("R2",) and felder["nennwert"] == pytest.approx(50.8)
    assert _lies(_quelle(r"DIM\wR3",extras=extras)) == ((r"DIM\wR2",r"DIM\wR3"),{})


@pytest.mark.parametrize("text,bekannt", [
    (r"FCF\w\w.06\wA\wB",None), (r"FCF\w⌖\w.06\wA",("toleranz","Flatness")),
    (r"FCF\w\w.060\wA\wB\n.04\wA",("toleranz","Position")),
    (r"FCF\w⌖\w⌀.03Ⓜ\wA\wA\wD\wE",None),
    (r"DIM\wR.022-.012",None), (r"DIM\w0X ⌀2",None), (r"DIM\wR2\u+.2\n-.1\u unknown",None),
    (r"DIM\wR2",("mass","Size_Diameter")), (r"DTM\wA",("bezug","DatumTarget")),
])
def test_unsichere_felder_bleiben_zur_pruefung_lesbar(text,bekannt):
    zeilen, felder = _lies(_quelle(text),bekannt)
    assert len(zeilen) == 1 and zeilen[0] and not felder


def test_einheiten_und_rahmenzellen():
    zahlen = _lies(_quelle(r"DIM\w.2±.01"))[1]
    assert zahlen["typ"] == "" and zahlen["nennwert"] == pytest.approx(5.08)
    assert not _lies(_quelle(r"DIM\wR2"),faktor=None)[1]
    assert _lies(_quelle(r"DIM\wR2 mm"),faktor=None)[1]["nennwert"] == 2
    text, p = _lies(_quelle(r"FCF\w⊥\w⌀.015Ⓟ.425\wA"))
    assert text == ("⊥ | ⌀.015Ⓟ.425 | A",)
    assert p["typ"] == "Perpendicularity" and p["zone"] == "Projected"
    assert p["wert"] == pytest.approx(.381) and p["zonen_wert"] == pytest.approx(10.795)
    assert p["bezuege"][0].name == "A"
