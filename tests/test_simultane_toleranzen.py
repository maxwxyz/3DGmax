"""Explizite Gleichzeitigkeit von Toleranzen in realen FTC-07-Modellkopien."""

from pathlib import Path

import pytest

from tests.conftest import pfad


def _kopie(ziel, paare, ersatz=None):
    text = Path(pfad("nist_ftc_07_asme1_ap242-e2.stp")).read_text(encoding="utf-8")
    pos = text.rindex("ENDSEC;")
    links = [f"#{20000+i}=GEOMETRIC_TOLERANCE_RELATIONSHIP('simultaneity','',#{a},#{b});"
             for i, (a, b) in enumerate(paare)]
    text = text[:pos]+"\n".join(links)+"\n"+text[pos:]
    if ersatz:
        import re
        text = re.sub(r"#(\d+)\b", lambda m: "#"+str(ersatz.get(int(m[1]), int(m[1]))), text)
    ziel.write_text(text, encoding="utf-8")
    return str(ziel)


@pytest.mark.parametrize("variante,geaendert", [
    ("umgekehrt", set()), ("andere_kette", set()), ("umnummeriert", set()), ("getrennt", {14472, 14614, 15076}),
    ("anderes_ziel", {14121, 14472, 14614, 15076}), ("bezugsbasis_offen", {14472, 14614, 15076, 15085})])
def test_simultane_paare_im_modellvergleich(tmp_path, variante, geaendert):
    from programm.ui.lader import lade_alles
    from programm.kern.vergleich_pmi import vergleiche_pmi, GEAENDERT

    ursprung = [(14614, 15076), (14614, 14472)]
    alt = lade_alles(_kopie(tmp_path/"A.stp", ursprung))
    paare = {"umgekehrt": [(15076,14614), (14472,14614)], "umnummeriert": ursprung,
             "andere_kette": [(14614,14472), (14472,15076)],
             "getrennt": [ursprung[1]], "anderes_ziel": [(14121,15076), ursprung[1]],
             "bezugsbasis_offen": [(14614,15085), ursprung[1]]}[variante]
    ersatz = {15076: 501, 501: 15076, 13915: 100002} if variante == "umnummeriert" else {}
    neu = lade_alles(_kopie(tmp_path/"B.stp", paare, ersatz))
    delta = [p for p in vergleiche_pmi(alt.pmi, neu.pmi) if p.status == GEAENDERT]
    assert {p.alt.step_id for p in delta} == geaendert
    assert all({f for f, _, _ in p.felder} <= {"simultan_mit", "simultan_offen"} for p in delta)
    if variante == "bezugsbasis_offen":
        index = {p.step_id:p for p in neu.pmi}
        assert index[14614].simultan_mit == [14472]
        assert index[14614].simultan_offen == [15085] and index[15085].simultan_offen == [14614]


def test_simultane_toleranzen_im_projekt_und_in_der_step_kopie(fenster, tmp_path):
    from programm.kern.zusammenfuegen import _pmi_umrechnen
    from programm.kern.zeichnungsabgleich import wertebefund
    from programm.ui.lader import lade_alles
    from tests.test_step_schreiben import _aendere
    from dataclasses import replace

    f = fenster
    quelle = _kopie(tmp_path/"Simultan.stp", [(14614,15076),(15076,14614),(15076,15076),(14614,14623),(15076,14121)])
    f.lade(quelle, warten=True)
    projekt = f.speichere_projekt(str(tmp_path/"Verknüpft"))
    f.lade(projekt, warten=True)
    alle = {p.step_id:p for p in f.erg.pmi}
    a, b = alle[14614], alle[15076]
    assert a.simultan_mit == [b.step_id] and b.simultan_mit == [14121, a.step_id]
    assert a.folgetoleranzen == [14623] and a.simultan_offen == [14623]
    assert all(not (p.simultan_mit or p.simultan_offen) for n,p in alle.items() if n not in (14121,14614,14623,15076))
    t = f.pmi.tabelle
    z = f.erg.pmi.index(a)
    tip = t.item(z, f.pmi.SPALTEN.index("Wert")).toolTip()
    assert f"Gleichzeitig geltende Toleranzen: {b.nummer}" in tip
    assert f"Gleichzeitige Anforderung mit ungeprüfter Bezugsbasis: {alle[14623].nummer}" in tip
    assert wertebefund(replace(a, simultan_mit=[], simultan_offen=[]), a) == "offen"
    from PySide6 import QtCore, QtTest, QtWidgets

    def gruppe_waehlen():
        menu = QtWidgets.QApplication.activePopupWidget()
        try:
            for aktion in menu.actions():
                if aktion.text() == "Gemeinsam geltende Toleranzen auswählen":
                    menu.setActiveAction(aktion)
                    QtTest.QTest.keyClick(menu, QtCore.Qt.Key.Key_Return)
                    break
        finally:
            menu.close()

    QtCore.QTimer.singleShot(50, gruppe_waehlen)
    f.pmi.waehle(lambda p: p is a)
    f.pmi._menue(t.visualItemRect(t.item(z, 0)).center())
    assert {p.step_id for p in f.pmi.gewaehlte()} == {14121,14614,15076}
    _aendere(a, wert=.813)
    ziel = f.speichere_step_pmi(str(tmp_path/"Kopie.stp"), melden=False)
    neu = lade_alles(ziel)
    geaendert = next(p for p in neu.pmi if p.step_id == a.step_id)
    assert geaendert.wert == pytest.approx(.813) and geaendert.simultan_mit == [15076]
    for nr in range(20000,20005):
        assert f.erg.modell.datei.get(nr) == neu.modell.datei.get(nr)
    _pmi_umrechnen([geaendert], 3, 100000, 20, None)
    assert geaendert.simultan_mit == [115076] and geaendert.simultan_offen == [114623]


def test_grafischer_sim_req_titel_allein_liefert_keine_partner(ftc07):
    from programm.kern.pmi_step import lies_toleranzen

    assert not any(p.simultan_mit or p.simultan_offen for p in lies_toleranzen(ftc07))


def test_vertauschte_gleiche_nennmasse_mit_verschiedenen_abmassen():
    from dataclasses import replace
    from programm.kern.vergleich_pmi import GLEICH, vergleiche_pmi
    from programm.ui.lader import lade_alles

    alt = [p for p in lade_alles(pfad("nist_ftc_07_asme1_ap242-e2.stp")).pmi if p.semantisch]
    a, b = [p for p in alt if p.step_id in (15607, 15653)]
    assert a.nennwert == b.nennwert and a.oben != b.oben and a.modifikatoren != b.modifikatoren
    neu = [replace(p, step_id=p.step_id+200000, folgetoleranzen=[n+200000 for n in p.folgetoleranzen])
           for p in reversed(alt)]
    delta = vergleiche_pmi(alt, neu)
    assert len(delta) == len(alt) and all(q.status == GLEICH for q in delta)


def test_wiederholte_bohrungen_vergleichen_ohne_quadratische_paarliste(monkeypatch):
    from dataclasses import replace
    from programm.kern import vergleich_pmi as vp
    from programm.kern.pmi import Pmi

    alt = [Pmi("mass", "Size_Diameter", nennwert=8., oben=.1, unten=-.1, flaechen={i}) for i in range(500)]
    neu = [replace(p, flaechen={1000+i}) for i, p in enumerate(alt)]
    neu[25].grenzmass = True
    aufrufe = 0
    punkte = vp._punkte
    def zaehle(*args):
        nonlocal aufrufe
        aufrufe += 1
        return punkte(*args)
    monkeypatch.setattr(vp, "_punkte", zaehle)
    delta = vp.vergleiche_pmi(alt, list(reversed(neu)), {1000+i:i for i in range(len(alt))})
    geaendert, = [p for p in delta if p.status != vp.GLEICH]
    assert geaendert.alt is alt[25] and geaendert.neu is neu[25]
    assert geaendert.felder == [("grenzmass", "Nein", "Ja")]
    assert aufrufe == len(alt)


@pytest.mark.parametrize("schwelle", [-1., 0., .5, .5001, 1., 2., 10.])
def test_index_enthaelt_alle_bewertbaren_kandidaten(schwelle):
    from dataclasses import replace
    from programm.kern import vergleich_pmi as vp
    from programm.kern.pmi import BezugsRef, Pmi

    alt = [Pmi("mass","D",nennwert=.125,flaechen={17}),
           Pmi("mass","D",nennwert=.125+1e-6,name="a"),
           Pmi("mass","D",nennwert=5.,name="b"), Pmi("mass","D",nennwert=float("nan")),
           Pmi("bezug","Datum"), Pmi("hinweis","",nur_grafik_text="Flansch 1"),
           Pmi("toleranz","Position",wert=None,bezuege=[BezugsRef("A")])]
    neu = [replace(p, flaechen={25} if p.flaechen else set()) for p in alt]
    neu.append(Pmi("hinweis","",nur_grafik_text="Flansch 2"))
    neu.append(Pmi("mass","D",nennwert=27.,flaechen={25}))
    merk = vp._paarmerkmale(neu, {25:17})
    kandidaten = set(vp._kandidaten(alt, neu, merk, schwelle, range(len(alt)), range(len(neu))))
    erwartet = {(i,j) for i,a in enumerate(alt) for j,b in enumerate(neu)
                if vp._punkte(a,b,merk[j].flaechen,a.bezug_text()==b.bezug_text()) >= schwelle}
    assert erwartet <= kandidaten


def test_simultane_alte_bezugsverweise_brauchen_gleiche_rangfolge():
    from programm.kern.p21 import lese_text, Ref
    from programm.kern.pmi_step import _bezugsbasis

    d = lese_text("""DATA;
#1=DATUM('','',#99,.F.,'A'); #2=DATUM('','',#99,.F.,'B');
#3=DATUM_REFERENCE(1,#1); #4=DATUM_REFERENCE(2,#2);
#5=DATUM_REFERENCE(1,#1); #6=DATUM_REFERENCE(1,#2);
ENDSEC;""")
    def basis(*ids):
        return _bezugsbasis(d, [Ref(n) for n in ids])
    assert basis(3, 4) == basis(4, 5) and basis(3, 4) != basis(3, 6)
    assert basis(3, 999) is None and basis() is None
