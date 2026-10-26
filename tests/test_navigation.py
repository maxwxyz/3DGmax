"""Kamerasteuerung (Zustandsautomat) fuer CATIA und klassisch."""

from programm.ui.navigation import LINKS, MITTE, RECHTS, UMSCHALT, Navigation


def _ziehe(nav, knoepfe, schritte=3, umschalt=0):
    out = []
    for i in range(1, schritte + 1):
        out += nav.bewegen(knoepfe, umschalt, 100 + 10 * i, 100 + 5 * i)
    return [b[0] for b in out]


def test_catia_mitte_ziehen_verschiebt():
    n = Navigation("catia")
    n.druecken(MITTE, MITTE, 0, 100, 100)
    assert set(_ziehe(n, MITTE)) == {"schieben"}
    assert n.loslassen(MITTE, 0, 130, 115) == []


def test_catia_mitte_plus_links_dreht():
    n = Navigation("catia")
    n.druecken(MITTE, MITTE, 0, 100, 100)
    n.druecken(LINKS, MITTE | LINKS, 0, 100, 100)
    assert set(_ziehe(n, MITTE | LINKS)) == {"drehen"}
    n.druecken(MITTE, MITTE, 0, 100, 100)
    n.druecken(RECHTS, MITTE | RECHTS, 0, 100, 100)
    assert set(_ziehe(n, MITTE | RECHTS)) == {"drehen"}


def test_catia_mitte_klick_links_dann_ziehen_zoomt():
    n = Navigation("catia")
    n.druecken(MITTE, MITTE, 0, 100, 100)
    n.druecken(LINKS, MITTE | LINKS, 0, 100, 100)
    n.loslassen(LINKS, MITTE, 100, 100)
    befehle = []
    for i in range(1, 4):
        befehle += n.bewegen(MITTE, 0, 100, 100 - 10 * i)
    assert befehle and all(b[0] == "zoomen" and b[1] > 1 for b in befehle)
    n.loslassen(MITTE, 0, 100, 70)
    n.druecken(MITTE, MITTE, 0, 100, 100)
    assert set(_ziehe(n, MITTE)) == {"schieben"}  # Zoom endet mit Loslassen der Mitte


def test_catia_klicks():
    n = Navigation("catia")
    n.druecken(MITTE, MITTE, 0, 50, 60)
    assert n.loslassen(MITTE, 0, 50, 60) == [("zentrieren", 50, 60)]
    n.druecken(LINKS, LINKS, 0, 10, 20)
    assert n.loslassen(LINKS, 0, 10, 20) == [("klick", 10, 20)]
    n.druecken(LINKS, LINKS, 0, 10, 20)
    assert _ziehe(n, LINKS) == []  # links allein ziehen bewegt nicht
    assert n.loslassen(LINKS, 0, 40, 35) == []


def test_klassisch():
    n = Navigation("klassisch")
    n.druecken(LINKS, LINKS, 0, 100, 100)
    assert set(_ziehe(n, LINKS)) == {"drehen"}
    n.loslassen(LINKS, 0, 130, 115)
    n.druecken(LINKS, LINKS, UMSCHALT, 100, 100)
    assert set(_ziehe(n, LINKS, umschalt=UMSCHALT)) == {"schieben"}
    n.loslassen(LINKS, 0, 130, 115)
    n.druecken(RECHTS, RECHTS, 0, 100, 100)
    assert set(_ziehe(n, RECHTS)) == {"schieben"}
    n.loslassen(RECHTS, 0, 130, 115)
    assert n.doppelklick(LINKS, 5, 6) == [("drehpunkt", 5, 6)]


def test_rad_und_unbekannter_modus():
    assert Navigation("xyz").modus == "catia"
    assert Navigation().rad(1, 3, 4)[0][0] == "zoomen"
    assert Navigation().rad(0, 3, 4) == []
