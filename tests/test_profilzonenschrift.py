"""Ungleich verteilte Profilzonen aus grafischen CTC-02-Rahmen mit explizitem Materialbezug."""

import gzip
import re
from dataclasses import replace

import numpy as np
import pytest

from programm.kern import p21, pmi_strichschrift as schrift
from programm.kern.pmi import Pmi
from programm.kern.pmi_ableiten import aus_text
from programm.kern.pmi_freier_hinweis import _ansichten
from programm.kern.pmi_reparieren import vorschlag
from programm.kern.toleranzzone import _grenzen_aussen_innen
from programm.ui.lader import lade_alles
from tests.conftest import pfad
from tests.test_bezugsbuchstaben import _gefuellt
from tests.test_hilfsmassschrift import _mit_fuellsatz
from tests.test_step_ap242 import _occt


# Callout, urspruengliche Semantik, zugehoeriger Formaspekt und Zielflaeche im AP242.
PROFILE = {1196: (56, 1596, 2518), 1197: (57, 1597, 2677), 1201: (58, 1603, 2604)}


def _ohne_profile(quelle):
    with gzip.open(quelle, "rt", encoding="ascii") as f:
        text = f.read()
    datei = p21.lese_text(text)
    # Nur die drei Toleranzen und ihre Validierungsdaten entfernen. Ihre originalen
    # Zeichnungslinks zeigen danach direkt auf den Formaspekt. Alle Bezugsstellen bleiben.
    aspekte = {nr: aspekt for nr, aspekt, _ in PROFILE.values()}
    weg, ersatz = set(aspekte), {}
    offen = list(weg)
    while offen:
        nr = offen.pop()
        for i in datei.referrers().get(nr, ()):
            e = datei.get(i)
            if e.is_a("DRAUGHTING_MODEL_ITEM_ASSOCIATION") or e.is_a(p21.DMIA_PH):
                ersatz[i] = nr
            elif i not in weg:
                weg.add(i)
                offen.append(i)
    for i in weg:
        text, n = re.subn(rf"(?m)^#{i}=[^;]+;", "", text)
        assert n == 1
    for i, nr in ersatz.items():
        text, n = re.subn(rf"(?m)(^#{i}=[^;]+?)#{nr},", rf"\g<1>#{aspekte[nr]},", text)
        assert n == 1
    return text


def _dreiecke(g):
    netze = list(g.dreiecke)
    for linie in g.linien:
        for a, b in zip(linie, linie[1:]):
            quer = np.cross(g.ebene[3], b-a)
            if np.linalg.norm(quer) > 1e-9:
                quer *= .07 / np.linalg.norm(quer)
                netze.append((np.array([a-quer, b-quer, b+quer, a+quer]), [[0,1,2], [0,2,3]]))
    return [(p/g.textfaktor, t) for p,t in netze]


@pytest.mark.parametrize("fuellung", [False, True])
def test_drei_profilanteile_bis_step(fenster, tmp_path, fuellung):
    quelle = pfad("nist_ctc_02_asme1_ap242-e2.stp.gz")
    ref = lade_alles(quelle)
    text = _ohne_profile(quelle)
    if fuellung:
        for nr in PROFILE:
            g = ref.grafik[nr]
            occ = ref.modell.datei.get(ref.modell.datei.get(nr).args()[1][0])
            stil = occ.args()[1][0].id
            text = _mit_fuellsatz(text, _dreiecke(g), nr, stil, g.name)
    eingang = tmp_path / "Profile.step"
    eingang.write_text(text, encoding="ascii")
    fenster.lade(str(eingang), warten=True)
    e = fenster.erg
    assert set(e.modell.datei.referrers()) <= e.modell.datei.entities.keys()
    for nr, (sem, _, face) in PROFILE.items():
        p = next(p for p in e.pmi if not p.semantisch and p.step_id == nr)
        soll = next(q for q in ref.pmi if q.step_id == sem)
        fenster._pmi_befehl("semantisch", p)
        d = fenster._semantik_dialog
        assert not d.fehler(), (nr, d.fehler())
        assert (d.v.typ, d.v.wert, d.v.bezug_text()) == (soll.typ, soll.wert, soll.bezug_text())
        assert d.v.modifikatoren == soll.modifikatoren and d.v.profilzonenart == "asme"
        assert {e.modell.flaeche_zu_step[i] for i in d.flaechen} == {face}
        u = soll.profilversatz()
        assert float(d.felder["profilversatz"].text()) == u
        for falsch in ("", "-1", "NaN"):
            d.felder["profilversatz"].setText(falsch)
            assert d.fehler()
        d.felder["profilversatz"].setText("0,75")
        assert not d.fehler() and d.pmi().profilversatz() == .75
        d.felder["profilversatz"].setText(str(u))
        d._pruefen()
    projekt = fenster.speichere_projekt(str(tmp_path / "Profile.3dgmax"))
    fenster.oeffne_projekt(projekt, warten=True)
    ziel = fenster.speichere_step_pmi(str(tmp_path / "Geprueft.step"), melden=False)
    assert ziel and not fenster._step_bericht.uebersprungen
    neu = lade_alles(ziel)
    typen, diagnosen, volumen = _occt(ziel)
    _, bisher, sollvolumen = _occt(eingang)
    assert volumen == sollvolumen
    # OCCT behandelt bereits das originale kombinierte Zeichenmodell #1208 als unbekannt.
    # Nur seine drei neuen Praesentationslinks duerfen denselben Lesefehler wiederholen.
    zusatz = set(diagnosen) - set(bisher)
    assert set(bisher) <= set(diagnosen) and len(zusatz) <= 3
    for i, meldung in zusatz:
        link = neu.modell.datei.get(i)
        assert link.is_a("DRAUGHTING_MODEL_ITEM_ASSOCIATION")
        assert link.args()[3].id == 1208 and link.args()[4].id in PROFILE
        assert any(msg == meldung and e.modell.datei.get(j).is_a("DRAUGHTING_MODEL_ITEM_ASSOCIATION")
                   and e.modell.datei.get(j).args()[3].id == 1208 for j, msg in bisher)
    for nr, (sem, _, face) in PROFILE.items():
        a, b = e.grafik[nr], neu.grafik[nr]
        p, = [p for p in neu.pmi if p.semantisch and p.step_id in b.pmi_ids]
        soll = next(q for q in ref.pmi if q.step_id == sem)
        assert (p.typ, p.wert, p.bezug_text()) == ("ProfileOfSurface", 2.5, "A|B|C")
        assert p.modifikatoren == soll.modifikatoren and p.profilzonenart == "asme"
        assert "UneqDisGeoTol" in typen[p.step_id]
        assert _grenzen_aussen_innen(p, p.wert) == (soll.profilversatz(), soll.profilversatz()-2.5)
        assert {neu.modell.flaeche_zu_step[i] for i in p.flaechen} == {face}
        assert _ansichten(e.modell.datei,nr) == _ansichten(neu.modell.datei,nr) != []
        assert bool(a.linien) != fuellung and a.dreiecke
        for v, w in zip(a.linien,b.linien,strict=True):
            np.testing.assert_array_equal(v,w)
        for (v,t),(w,u) in zip(a.dreiecke,b.dreiecke,strict=True):
            np.testing.assert_array_equal(v,w)
            np.testing.assert_array_equal(t,u)


def test_ap203_anteile_aus_konturen_und_fuellung():
    e = lade_alles(pfad("nist_ctc_02_asme1_ap203.stp.gz"))
    # Die Referenz lokalisiert B2 an dieser Stelle. Das einzelne gelesene B reicht nicht.
    b2 = next(p for p in e.pmi if p.step_id == 8674)
    v = vorschlag(b2, e.grafik[8674], e.modell)
    assert v.typ == "DatumTarget" and not v.name
    for nr, u in ((8688,2.5), (8694,.5), (8714,0.)):
        g = e.grafik[nr]
        p = next(p for p in e.pmi if p.step_id == nr)
        fuellung = [(v*g.textfaktor,t) for v,t in _gefuellt(g)]
        for bild in (g, replace(g, linien=[], dreiecke=fuellung, ebene=None)):
            v = vorschlag(replace(p,norm="iso"), bild, e.modell)
            assert v.wert == 2.5 and v.profilversatz() == u and v.bezug_text() == "A|B|C"
            assert _grenzen_aussen_innen(v,2.5) == (u,u-2.5)


def test_u_braucht_profil_und_vollstaendige_zweite_zahl():
    p = Pmi(**aus_text(["⌒ .1Ⓤ.025 A"],25.4))
    assert p.profilversatz() == pytest.approx(.635) and p.wert == pytest.approx(2.54)
    for s in ("⏥ .1Ⓤ0", "⌓ .1Ⓤ", "⌓ .1Ⓤ-.2 A", "⌓ .1Ⓤ0.2.5", "⌓ .1Ⓤ0Ⓛ A"):
        assert "wert" not in (aus_text([s]) or {})


def _bezugsfelder_aus_nachbarrahmen(text, e):
    # Die drei Bezugsfelder des grafischen Modells erhalten die echten G/H/J-Glyphen
    # aus #8691. Die zugehoerigen grafischen Bezugsmerkmale existieren im selben Teil.
    d = e.modell.datei
    g = e.grafik[8694]
    o, x, y, _ = g.ebene
    gruppe = d.get(d.get(8694).args()[2])
    refs = [ref.id for ref in gruppe.args()[1]]
    nr = max(d.entities)+1
    alte_refs, neue_refs, elemente = set(), [], []
    def innen(n, feld):
        grafik = e.grafik[n]
        pf = schrift._pfade(grafik, grafik.ebene)
        l,b,r,t = schrift._zellen(pf)[feld]
        return np.array([(l+r)/2, (b+t)/2]), [(j,p) for j,(p,_) in enumerate(pf)
                if np.all(p.min(axis=0) > [l+.001,b+.001]) and np.all(p.max(axis=0) < [r-.001,t-.001])]
    for fach in (2,3,4):
        ziel, alt = innen(8694, fach)
        quelle, neu = innen(8691, fach)
        alte_refs.update(refs[j] for j,_ in alt)
        for _, pfad_2d in neu:
            ids = []
            for u,v in pfad_2d + ziel - quelle:
                xyz = ",".join(f"{a:.10f}" for a in (o+u*x+v*y)/g.textfaktor)
                elemente.append(f"#{nr}=CARTESIAN_POINT('',({xyz}));")
                ids.append(f"#{nr}")
                nr += 1
            elemente.append(f"#{nr}=POLYLINE('',({','.join(ids)}));")
            neue_refs.append(nr)
            nr += 1
    refs = [j for j in refs if j not in alte_refs] + neue_refs
    text, n = re.subn(rf"(#{gruppe.id}=GEOMETRIC_CURVE_SET\('[^']*',)\([^;]+;",
                       r"\g<1>(" + ",".join(f"#{i}" for i in refs) + "));", text)
    assert n == 1
    pos = text.rindex("ENDSEC;")
    return text[:pos] + "\n".join(elemente) + "\n" + text[pos:]


@pytest.mark.parametrize("fuellung", [False, True])
def test_grafisches_gesamtmodell_mit_gezeichneten_bezuegen(fenster, tmp_path, fuellung):
    quelle = pfad("nist_ctc_02_asme1_ap203.stp.gz")
    e = lade_alles(quelle)
    with gzip.open(quelle, "rt", encoding="ascii") as f:
        text = _bezugsfelder_aus_nachbarrahmen(f.read(), e)
    eingang = tmp_path / "Nur Grafik.step"
    eingang.write_text(text, encoding="ascii")
    if fuellung:
        g = lade_alles(str(eingang)).grafik[8694]
        text = _mit_fuellsatz(text, _gefuellt(g), 8694,
                             e.modell.datei.get(8694).args("ANNOTATION_OCCURRENCE")[1][0].id, "fcf")
        eingang.write_text(text, encoding="ascii")
    fenster.lade(str(eingang), warten=True)
    erg = fenster.erg
    assert not any(p.semantisch for p in erg.pmi)
    for nr in (8697, 8704, 8683, 8694):
        p = next(p for p in erg.pmi if p.step_id == nr)
        fenster._pmi_befehl("semantisch", p)
        d = fenster._semantik_dialog
        assert not d.fehler(), (nr, d.fehler())
        if nr == 8694:
            assert d.v.bezug_text() == "G|H|J" and d.v.profilversatz() == .5
            assert d.v.profilzonensymbol == "Ⓤ"
        d._pruefen()
    ziel = fenster.speichere_step_pmi(str(tmp_path / "Ausgabe.step"), melden=False)
    assert ziel and not fenster._step_bericht.uebersprungen
    assert _occt(eingang)[1:] == _occt(ziel)[1:]
    neu = lade_alles(ziel)
    a, b = erg.grafik[8694], neu.grafik[8694]
    p, = [q for q in neu.pmi if q.semantisch and q.step_id in b.pmi_ids]
    assert _grenzen_aussen_innen(p,p.wert) == (.5,-2.) and p.bezug_text() == "G|H|J"
    assert bool(a.linien) != fuellung and bool(a.dreiecke) == fuellung
    for v, w in zip(a.linien,b.linien,strict=True):
        np.testing.assert_array_equal(v,w)
    for (v,t),(w,u) in zip(a.dreiecke,b.dreiecke,strict=True):
        np.testing.assert_array_equal(v,w)
        np.testing.assert_array_equal(t,u)


def test_zeichnung_und_revision_unterscheiden_mitte_von_aussengrenze():
    from programm.kern import zeichnungsabgleich as za
    from programm.kern.vergleich_pmi import vergleiche_pmi
    blatt = za.lese_angabe("⌓ | 2.5Ⓤ0.5 | A", 1.)
    asme = replace(blatt, norm="asme", profilzonenart="")
    iso = replace(blatt, norm="iso", profilzonenart="")
    assert not za.unterschiede(blatt,asme)
    assert za.unterschiede(blatt,iso) == ["profilzonensymbol"]
    assert "Ⓤ" in asme.wert_text() and "UZ" in iso.wert_text()
    from programm.kern.pmi_erzeugen import felder
    assert felder(asme) == ["⌓", "2.5 Ⓤ 0.5", "A"]
    eintrag, = vergleiche_pmi([asme],[iso])
    assert ("profilzonensymbol","Ⓤ","UZ") in eintrag.felder


def test_einliniges_u_mit_rundung_und_beiden_schenkeln():
    winkel = np.linspace(0, 2*np.pi, 97)
    kreis = .5 + .49*np.column_stack((np.cos(winkel), np.sin(winkel)))
    bogen = np.linspace(np.pi, 2*np.pi, 25)
    u = np.vstack(([.34,.75], np.column_stack((.50+.16*np.cos(bogen),.38+.13*np.sin(bogen))), [.66,.75]))
    def lies(aussen, innen):
        teile = [(aussen, False), (innen, False)]
        mask = schrift._bild(teile,(0,0,1,1),76)
        return schrift._lies_zeile(schrift._bildzeichen(mask))
    assert lies(kreis,u) == "Ⓤ"
    for aussen, innen in ((kreis[:78],u), (kreis,u[1:]), (kreis,u[:-1]), (kreis,1-u),
                          (kreis,np.array([(.34,.75),(.5,.25),(.66,.75)]))):
        assert lies(aussen,innen) != "Ⓤ"


def test_gerichteter_versatz_in_zolldatei_und_ungueltige_eingaben(tmp_path):
    from programm.kern.step_schreiben import schreibe
    quelle = pfad("nist_ftc_07_asme1_ap242-e2.stp")
    e = lade_alles(quelle)
    basis = next(p for p in e.pmi if p.typ == "ProfileOfSurface" and p.flaechen)
    profil = Pmi("toleranz", "ProfileOfSurface", name="Profilzone", quelle="eigen", wert=2.54,
                 flaechen=basis.flaechen, nummer=900, step_id=-900)
    ziel = str(tmp_path / "Zone.step")
    for art, u in (("iso", -.635), ("asme", .635)):
        p = replace(profil, profilzonenart=art, modifikatoren=[f"UZ {u}"])
        assert schreibe(quelle, ziel, [p], e.modell).neu == [900]
        neu = lade_alles(ziel)
        q, = [p for p in neu.pmi if p.name == "Profilzone"]
        assert q.profilzonenart == art and q.profilversatz() == pytest.approx(u)
        aussen = u if art == "asme" else u+1.27
        assert _grenzen_aussen_innen(q,q.wert) == pytest.approx((aussen,aussen-2.54))
    for typ, mods in (("Position", ["UZ 1"]), ("ProfileOfSurface", ["UZ"]),
                      ("ProfileOfSurface", ["UZ nan"]), ("ProfileOfSurface", ["UZ -1"]),
                      ("ProfileOfSurface", ["UZ 1","UZ 0"])):
        p = replace(profil, typ=typ, modifikatoren=mods, profilzonenart="asme")
        bericht = schreibe(quelle, ziel, [p], e.modell)
        assert not bericht.neu and [nr for nr, _, _ in bericht.uebersprungen] == [900]
