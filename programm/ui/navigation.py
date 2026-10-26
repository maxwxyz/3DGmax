"""Maussteuerung der Kamera als Zustandsautomat (ohne Qt-Abhaengigkeit testbar).

Eingabe: Ereignisse (druecken/bewegen/loslassen/doppelklick) mit Knopf, gedrueckten Knoepfen und Umschalttasten.
Ausgabe: Befehle als Tupel, die die 3D-Ansicht ausfuehrt:
  ("drehen", dx, dy), ("schieben", dx, dy), ("zoomen", faktor, x, y), ("klick", x, y),
  ("zentrieren", x, y), ("drehpunkt", x, y), ("hover", x, y), ("kontext", x, y)

CATIA (Standard):
  Mitteltaste ziehen: verschieben
  Mitteltaste halten + linke oder rechte Taste halten, ziehen: drehen
  Mitteltaste halten, links/rechts einmal klicken, weiter ziehen (hoch/runter): zoomen
  Mitteltaste klicken: Punkt in die Bildmitte; linke Taste klicken: waehlen; rechte Taste klicken: Kontextmenue
Klassisch:
  Linke Taste ziehen: drehen; Mitte/rechts oder Umschalt+links ziehen: verschieben
  Doppelklick: Drehpunkt; linke Taste klicken: waehlen
Fuer beide: Mausrad zoomt an der Mausposition (Trackpad behandelt die 3D-Ansicht).
"""

from __future__ import annotations

LINKS, MITTE, RECHTS = 1, 4, 2  # wie Qt.MouseButton
UMSCHALT = 0x02000000  # Qt.ShiftModifier
MODI = ("catia", "klassisch")
SCHWELLE = 4  # Pixel bis eine Bewegung als Ziehen gilt


class Navigation:
    def __init__(self, modus: str = "catia"):
        self.modus = modus if modus in MODI else "catia"
        self._zuruecksetzen()

    def _zuruecksetzen(self):
        self.letzte = None  # (x, y)
        self.start = None
        self.gezogen = False
        self.knopf = 0  # erster gedrueckter Knopf
        self.zoom_modus = False  # CATIA: Mitte + Klick links/rechts
        self.klick_waehrend_mitte = False
        self.bewegt_seit_klick = False

    # --- Ereignisse ---

    def druecken(self, knopf: int, knoepfe: int, umschalt: int, x: int, y: int) -> list:
        if self.start is None:
            self.start = (x, y)
            self.knopf = knopf
            self.gezogen = False
        if self.modus == "catia" and knoepfe & MITTE and knopf in (LINKS, RECHTS):
            self.klick_waehrend_mitte = True
            self.bewegt_seit_klick = False
        self.letzte = (x, y)
        return []

    def bewegen(self, knoepfe: int, umschalt: int, x: int, y: int) -> list:
        if not knoepfe or self.letzte is None:
            return [("hover", x, y)]
        lx, ly = self.letzte
        self.letzte = (x, y)
        if abs(x - self.start[0]) + abs(y - self.start[1]) > SCHWELLE:
            self.gezogen = True
        if not self.gezogen:
            return []
        dx, dy = x - lx, y - ly
        if self.klick_waehrend_mitte:
            self.bewegt_seit_klick = True
        return self._catia(knoepfe, dx, dy, x, y) if self.modus == "catia" else \
            self._klassisch(knoepfe, umschalt, dx, dy)

    def _catia(self, knoepfe, dx, dy, x, y):
        if not knoepfe & MITTE:
            return []  # linke Taste allein ziehen: (Rahmenauswahl spaeter)
        if knoepfe & (LINKS | RECHTS):
            return [("drehen", dx, dy)]
        if self.zoom_modus:
            return [("zoomen", 1.0 + 0.006 * -dy, *self.start)] if dy else []
        return [("schieben", dx, dy)]

    def _klassisch(self, knoepfe, umschalt, dx, dy):
        if knoepfe & (MITTE | RECHTS) or (knoepfe & LINKS and umschalt & UMSCHALT):
            return [("schieben", dx, dy)]
        if knoepfe & LINKS:
            return [("drehen", dx, dy)]
        return []

    def loslassen(self, knopf: int, knoepfe: int, x: int, y: int) -> list:
        out = []
        if self.modus == "catia":
            if knopf in (LINKS, RECHTS) and knoepfe & MITTE:
                # Klick links/rechts bei gehaltener Mitte ohne Bewegung -> ab jetzt zoomen
                if self.klick_waehrend_mitte and not self.bewegt_seit_klick:
                    self.zoom_modus = True
                self.klick_waehrend_mitte = False
                return out
            if knopf == MITTE and not self.gezogen and not self.zoom_modus and self.knopf == MITTE:
                out.append(("zentrieren", x, y))
            elif knopf == LINKS and not self.gezogen and self.knopf == LINKS:
                out.append(("klick", x, y))
            elif knopf == RECHTS and not self.gezogen and self.knopf == RECHTS:
                out.append(("kontext", x, y))
        elif knopf == LINKS and not self.gezogen:
            out.append(("klick", x, y))
        elif knopf == RECHTS and not self.gezogen:
            out.append(("kontext", x, y))
        if not knoepfe:
            self._zuruecksetzen()
        return out

    def doppelklick(self, knopf: int, x: int, y: int) -> list:
        if self.modus == "klassisch" or knopf == LINKS:
            return [("drehpunkt", x, y)]
        return []

    def rad(self, schritte: float, x: int, y: int) -> list:
        return [("zoomen", 1.2 ** schritte, x, y)] if schritte else []
