"""Wortlaut am Zielformelement und Wortlaut der beiden Toleranzen getrennt pruefen."""

from dataclasses import replace
from types import SimpleNamespace

from programm.kern.blattverbund import Verbundindex, pruefe_rahmen
from programm.kern.merkmalstext import Merkmalstext
from programm.kern.p21 import Entity, P21Datei, Ref
from programm.kern.pmi_step import lies_toleranzen
from programm.kern.zeichnungsabgleich import Blattangabe


def test_originale_semantische_textquelle_ftc07(ftc07):
    modelle = lies_toleranzen(ftc07)
    index = Verbundindex(modelle, ftc07)
    a = Blattangabe(2,(0,0,1,1), "⌓ | .070 | A | B | C\n⌓ | .015 | A\n4 COPLANAR SURFACES\nSIM REQT",
                    verbundrahmen=True, modell=index.quellen[14614], unten=index.quellen[14623])
    bericht = pruefe_rahmen(a, 25.4, index)
    (quelle, status), = bericht.merkmalstexte
    assert (quelle.aspekt, quelle.eigenschaft, quelle.darstellung, quelle.grafiken) == (13858,16453,16454,(16461,))
    assert quelle.zeilen == ("4 COPLANAR SURFACES","SIM REQT") and status == "gleich"
    assert bericht.wortlaut == "geaendert" and bericht.gruppe_offen
    assert not a.modell.beschreibung and not a.unten.beschreibung
    # Dieselben Zahlen und Bezuege reichen fuer einen anderen Zielaspekt nicht.
    assert not index.merkmalstexte(index.quellen[15076], index.quellen[15085])
    assert not index.merkmalstexte(a.modell, index.quellen[15085])


def test_kein_text_aus_validierung_oder_fremder_eigenschaft(ftc07):
    modelle = lies_toleranzen(ftc07)
    def suche(teil, teile):
        d = P21Datei(ftc07.datei.schema, {**ftc07.datei.entities, teil:Entity(teil,teile)})
        index = Verbundindex(modelle, SimpleNamespace(datei=d))
        return index.merkmalstexte(index.quellen[14614], index.quellen[14623])
    assert not suche(16453, {"PROPERTY_DEFINITION":["pmi validation property", "", Ref(13858)]})
    assert not suche(16453, {"PROPERTY_DEFINITION":["semantic text", "", Ref(15072)]})
    quelle, = suche(16454, {"REPRESENTATION":["", [Ref(16452), Ref(999999)], Ref(8)]})
    assert not quelle.vollstaendig and quelle.vergleich(["SIM REQT"]) == "offen"
    quelle, = suche(16470, {"DRAUGHTING_MODEL_ITEM_ASSOCIATION":["","",Ref(13858),Ref(13679),Ref(16461)]})
    assert quelle.grafiken == () and quelle.zeilen == ("4 COPLANAR SURFACES", "SIM REQT")


def test_reihenfolge_der_repraesentationsitems_bleibt_unbestimmt():
    q = Merkmalstext(1,2,3,(),("SIM REQT", "4 COPLANAR SURFACES"), True)
    assert q.vergleich(["4 COPLANAR SURFACES", "SIM REQT"]) == "gleich"
    assert q.vergleich(["4 COPLANAR SURFACES", "SIM REQT 2"]) == "geaendert"
    assert q.vergleich(["4 COPLANAR SURFACES"]) == "geaendert"
    assert replace(q, zeilen=("4 COPLANAR","SURFACES")).vergleich(["4 COPLANAR SURFACES"]) == "offen"
    assert replace(q, zeilen=("4 COPLANAR SURFACES",)).vergleich(["4 COPLANAR","SURFACES"]) == "gleich"
    assert replace(q, zeilen=("4 COPLANAR\nSURFACES",)).vergleich(["SURFACES", "4 COPLANAR"]) == "geaendert"
