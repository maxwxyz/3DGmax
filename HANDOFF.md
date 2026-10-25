# Übergabe (Stand 2026-10-25)

Branch: `main` (Schritt 1 Machbarkeit fertig). Ergebnis: `docs/Machbarkeit.md`, Zahlen: `docs/Machbarkeit_Tabelle.md`.

## Umgebung
```bash
pixi install                 # Python 3.14, pythonocc-core 8.0.1, PySide6 6.12 (pixi.toml)
pixi run test                # Kern-Tests mit NIST-Modellen (tests/daten)
pixi run machbarkeit         # Auswertung aller NIST-Dateien in daten/nist (nicht im Repo)
pixi run python werkzeuge/viewer_versuch.py tests/daten/nist_ftc_10_asme1_ap242-e2.stp
```
NIST-Dateien komplett: https://www.nist.gov/document/nist-pmi-step-files → entpacken nach `daten/nist/`.

## Fertig
- `programm/kern/p21.py` eigener STEP-Leser (Entitätsgraph), `laden.py` (XCAF + Flächenindex + #ID-Zuordnung),
  `pmi.py` (Datenmodell, Text mit Symbolen), `pmi_step.py` (Maße/Toleranzen aus Datei), `pmi_lesen.py` (Liste,
  Bezüge, XCAF-Gegenprüfung), `ansichten.py` (Saved Views).
- Entscheidung: pythonocc statt OCP, Semantik aus eigener STEP-Auswertung (Begründung in docs/Machbarkeit.md).

## Offen / nächster Schritt (Schritt 2 Viewer)
- Nutzer: Beispiel-JT und 3D-PDF liefern; eigene anonymisierte STEP-Modelle.
- Schritt 2: Hauptfenster (Baum, Navigation, Darstellungsarten, hell/dunkel), grafische PMI anzeigen, Hinweise,
  Bezugsstellen, Hilfsgeometrie trennen, `tr()`/Übersetzung, Einführung, F1-Anleitung, Tests offscreen.
- Viewer-Bildschirmfoto: `QWidget.grab()` erfasst OpenGL nicht → für Doku `View.Dump` nutzen.
