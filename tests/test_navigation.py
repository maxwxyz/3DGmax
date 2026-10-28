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


def test_liegen_gebliebener_zustand_stoert_nicht():
    """Ging das Loslassen verloren (ausserhalb losgelassen, Fensterwechsel, Menue), beginnt der naechste Druck mit
    nur einem Knopf eine neue Geste: ein Linksklick bleibt ein Klick (sonst reagierten Auswahl und Wuerfel nicht)."""
    for modus in ("catia", "klassisch"):
        n = Navigation(modus)
        n.druecken(MITTE, MITTE, 0, 100, 100)
        _ziehe(n, MITTE)  # ... und das Loslassen kommt nie an
        n.druecken(LINKS, LINKS, 0, 300, 300)
        assert n.start == (300, 300) and n.loslassen(LINKS, 0, 300, 300) == [("klick", 300, 300)]


def test_roll_anteil_weich():
    """Mitte Trackball, aussen rollen, dazwischen stetig und monoton (kein Sprung); der Bereich ist ein Kreis mit der
    halben kleineren Fensterseite (in jeder Richtung derselbe Abstand)."""
    from programm.ui.navigation import ROLL_AUSSEN, ROLL_INNEN, roll_anteil
    w, h = 1200, 800
    assert roll_anteil(600, 400, w, h) == 0.0 and roll_anteil(0, 0, w, h) == 1.0
    assert roll_anteil(600 + ROLL_INNEN * 400, 400, w, h) == 0.0 == roll_anteil(600, 400 - ROLL_INNEN * 400, w, h)
    assert roll_anteil(600 + ROLL_AUSSEN * 400, 400, w, h) == 1.0 == roll_anteil(600, 400 + ROLL_AUSSEN * 400, w, h)
    werte = [roll_anteil(600 + k * 4, 400, w, h) for k in range(101)]
    assert all(b >= a for a, b in zip(werte, werte[1:])) and max(b - a for a, b in zip(werte, werte[1:])) < 0.1
