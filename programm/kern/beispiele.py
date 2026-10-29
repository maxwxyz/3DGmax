"""Beispiele (Datei › Beispiele): je eine Funktion an freien Testdaten zeigen (ohne Qt).

Die Dateien liegen in der gebauten App unter programm/beispiele/ (packaging/3dgmax.spec kopiert sie), im
Quellbaum in tests/daten bzw. tests/daten/varianten – das Repository enthaelt keine Kopien. Die Schritte nach dem
Oeffnen fuehrt das Hauptfenster aus (Hauptfenster.oeffne_beispiel).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

CTC01 = "nist_ctc_01_asme1_ap242-e1.stp"
FTC10 = "nist_ftc_10_asme1_ap242-e2.stp"
WELLE = "getriebewelle.stp"  # werkzeuge/welle.py
# Funktion der Flaechen der Getriebewelle: (Rolle, Art, x der Flaechenmitte, Durchmesser bzw. Normale)
WELLE_ROLLEN = (("lagersitz", "zylinder", 62.0, 30.0), ("lagersitz", "zylinder", 126.5, 30.0),
                ("anschlag", "ebene", 70.0, (1, 0, 0)), ("anschlag", "ebene", 78.0, (1, 0, 0)),
                ("anschlag", "ebene", 118.0, (1, 0, 0)), ("sicherungsringnut", "zylinder", 53.2, 28.6),
                ("dichtsitz", "zylinder", 44.75, 25.0), ("nabensitz", "zylinder", 18.5, 20.0),
                ("nabensitz", "zylinder", 98.0, 36.0), ("passfedernut", "ebene", 18.0, (0, 0, 1)),
                ("passfedernut", "ebene", 98.0, (0, 0, 1)))


@dataclass(frozen=True)
class Beispiel:
    name: str
    titel: str  # deutsch, Anzeige ueber tr()
    text: str  # Erklaerung in der Statuszeile, ueber tr()
    dateien: tuple[str, ...]


BEISPIELE = (
    Beispiel("pmi", "PMI und gespeicherte Ansichten",
             "NIST CTC-01: PMI-Liste, grafische PMI und die gespeicherte Ansicht MBD_0", (CTC01,)),
    Beispiel("pruefen", "PMI prüfen und Plausibilität",
             "NIST FTC-10: Befunde zu Bezügen, Vollständigkeit und Widersprüchen – Doppelklick wählt PMI bzw. Flächen",
             (FTC10,)),
    Beispiel("funktion", "Funktion → Tolerierung",
             "Getriebewelle: zwei Lagersitze (gemeinsame Bezugsachse A-B), Schultern, Dichtsitz, Nabensitze mit "
             "Passfedernut und Sicherungsringnut sind zugeordnet; Rollen, Bezüge, Passungen und Toleranzen in der "
             "Tabelle ändern, dann „Tolerierung vorschlagen …“", (WELLE,)),
    Beispiel("messen", "Messen",
             "NIST CTC-01: Messen ist an (Abstand) – zwei Elemente im Modell anklicken; Winkel, Radius, Wandstärke "
             "und Koordinaten in der Leiste Messen", (CTC01,)),
    Beispiel("analyse", "Analyse: Entformungsschräge",
             "NIST FTC-10: Entformung in +Z mit 1° Mindestschräge – grün genug Schräge, rot zu wenig; in der Leiste "
             "Analyse auch Krümmung und Wandstärke", (FTC10,)),
    Beispiel("merkmale", "Merkmalsliste mit Ballonnummern",
             "NIST FTC-10: jedes Merkmal (Maß, Form- und Lagetoleranz) mit Nummer im Modell und in der PMI-Liste; "
             "Datei › Export: Merkmalsliste als CSV oder PDF", (FTC10,)),
    Beispiel("kette2d", "2D-Toleranzkette (Hebel)",
             "Vorlage Hebel mit Lagerabstand: Längen und Winkel mit Abmaßen, Schlussgröße linear und nichtlinear – "
             "ohne Modell, alles in der Leiste änderbar", ()),
    Beispiel("kette3d", "3D-Kette aus einer Baugruppen-Messgröße",
             "Testbaugruppe: Bündigkeit der Schraubenköpfe als 3D-Kette – je Teil auf dem Verbindungsweg ein Glied "
             "mit seinen Spielräumen, im Modell gezeigt", ("baugruppe.stp",)),
    Beispiel("zonen", "Toleranzzonen mit Allgemeintoleranzen",
             "NIST FTC-10: alle Toleranzzonen (gelb), Bonus bei Ⓜ/Ⓛ (magenta), Allgemeintoleranzen ISO 2768-mK "
             "(violett)", (FTC10,)),
    Beispiel("schnittansicht", "Schnittansicht aus der Datei",
             "Ansicht mit Schnittebenen aus STEP AP242 (Ebene durch die Bohrung, Stufenschnitt)",
             ("ctc01_schnittansicht.stp",)),
    Beispiel("vergleich", "Vergleich: Geometrie und PMI geändert",
             "Bohrung Ø25 um 15 mm versetzt (ihr Maß folgt), eine Bohrung entfallen, Fase 3 mm; Position 0,75 → 0,5, "
             "Bezüge A|B|C → A|C|B, Rechtwinkligkeit entfallen, Position neu – Änderungsliste mit Prüfrundgang, "
             "Farbkarte, Material + / −", (CTC01, "ctc01_geo_pmi_deutlich.stp")),
    Beispiel("scan", "Scan gegen Toleranzen",
             "Erzeugter Scan mit Fase, Delle und Welligkeit: ausgerichtet, je PMI bewertet, Farbkarte über dem Modell",
             (CTC01, "ctc01_scan_fehler.ply")),
    Beispiel("kette", "Toleranzkette (1D)",
             "NIST FTC-10: Längenmaße als Kettenglieder (Richtung je Glied umkehrbar), Worst Case, statistisch mit "
             "Cp 1,33, Monte Carlo", (FTC10,)),
    Beispiel("kette_getriebe", "Toleranzkette Getriebewelle mit Wärmeausdehnung",
             "Axialspiel zwischen Lager und Sicherungsring: Kette aus Datei, Richtungen aus dem Schlussmaß, "
             "Werkstoffe aus der STEP-Datei, −20 °C und 100 °C (Alu-Hülse), Anforderung 0,05 … 1,1 mm",
             ("getriebe.3dgkette", "getriebe.stp")),
    Beispiel("zusammenbau", "Zusammenbau und Wiggle",
             "Schraube: Kopf auf den Deckel gefangen, Schaft koaxial zur Bohrung – offen bleibt die Drehung um die "
             "Achse, der Wiggle zeigt sie", ("baugruppe.stp",)),
    Beispiel("variation", "Baugruppenvariation: Spalt und Bündigkeit",
             "Deckel auf Grundplatte, zwei Schrauben mit Spiel: Kopfüberstand und Bündigkeit der Köpfe als Worst Case "
             "und Monte Carlo, Beitragende je Verbindung", ("baugruppe.stp",)),
    Beispiel("kollision", "Kollisionen und Abstände",
             "Testbaugruppe: Schrauben durchdringen den Deckel (rot), Spalt 0,3 mm unter dem Mindestabstand 1 mm, "
             "Deckel liegt auf (Kontakt)", ("baugruppe.stp",)),
    Beispiel("baugruppe", "Baugruppenvergleich",
             "Zwei Stände einer Baugruppe: Teile verschoben, geändert, hinzugekommen", ("baugruppe.stp",
                                                                                           "baugruppe_b.stp")),
)


def welle_rollen(modell) -> list[tuple[int, str]]:
    """Beispiel Funktion -> Tolerierung: (Flaeche, Rolle) der Getriebewelle nach WELLE_ROLLEN."""
    import numpy as np
    from . import funktion as fu
    out = []
    for i, f in enumerate(modell.flaechen):
        g = fu._geometrie(f)
        if g is None:
            continue
        for rolle, art, x, kennung in WELLE_ROLLEN:
            if g["art"] != art or abs(g["mitte"][0] - x) > 0.6:
                continue
            if art == "zylinder" and abs(g["groesse"] - kennung) < 0.01 or \
                    art == "ebene" and abs(abs(float(g["richtung"] @ np.array(kennung))) - 1) < 1e-6:
                out.append((i, rolle))
    return out


def ordner() -> list[str]:
    """Suchorte: gebaute App, dann der Quellbaum (tests/daten)."""
    hier = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    basis = getattr(sys, "_MEIPASS", None)
    out = [os.path.join(basis, "programm", "beispiele")] if basis else []
    wurzel = os.path.dirname(hier)
    return out + [os.path.join(hier, "beispiele"), os.path.join(wurzel, "tests", "daten"),
                  os.path.join(wurzel, "tests", "daten", "varianten")]


def datei(name: str) -> str | None:
    return next((p for o in ordner() for p in [os.path.join(o, name)] if os.path.isfile(p)), None)


def dateien(b: Beispiel) -> list[str] | None:
    """Pfade aller Dateien des Beispiels oder None, wenn eine fehlt."""
    pfade = [datei(n) for n in b.dateien]
    return None if None in pfade else pfade


def finde(name: str) -> Beispiel:
    return next(b for b in BEISPIELE if b.name == name)


def alle_dateien() -> set[str]:
    """Fuer den App-Bau: alle benoetigten Dateien (Namen)."""
    return {n for b in BEISPIELE for n in b.dateien}
