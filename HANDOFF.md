# Übergabe (Stand 2026-10-26)

Branch: `main`. Schritte 1 (Machbarkeit), 2 (Viewer) und 3 (Messen) fertig. **Pause nach Schritt 3** (Nutzerwunsch).
Version 0.1 + unveröffentlichte Einträge in `programm/CHANGELOG.json`.

## Umgebung und Befehle
```bash
pixi install                      # Python 3.14, pythonocc-core 8.0.1 (ohne VTK), PySide6 6.12, PyInstaller
pixi run start                    # App starten (Datei dahinter möglich)
pixi run test                     # alle Tests offscreen (~9 s); CI: pixi run test-ci (ausführlich, Zeitlimit)
DG_BILDSCHIRM=1 pixi run python -m pytest -q tests/test_bildschirm.py   # echte 3D-Ansicht (Mac mit Bildschirm)
pixi run selbsttest               # bzw. App mit --selbsttest; --bild out.png datei.stp speichert die 3D-Ansicht
pixi run python werkzeuge/bildschirmfotos.py docs/bilder --thema hell|dunkel
pixi run python packaging/make_icon.py   # Symbole aus packaging/logo.svg
packaging/build_mac.sh [--ohne-tests]    # bzw. build_linux.sh / build_windows.bat → dist/
```

## Aufbau
- `programm/kern/`: `p21.py` (STEP-Graph), `laden.py`, `pmi*.py` (Semantik, Hinweise, Bezugsstellen), `ansichten.py`,
  `praesentation.py` (grafische PMI inkl. Dateifarbe), `baum.py`, `farben.py`, `messen.py`.
- `programm/ui/`: `hauptfenster.py`, `ansicht3d.py` (OCCT-Viewer), `navigation.py` (CATIA/klassisch, testbar),
  `messwerkzeug.py`, `einstellungen.py`, `panels.py`, `lader.py`, `hilfe.py`, `thema.py`.

## Erkenntnisse (nicht offensichtlich)
- OCCT-Viewer auf dem Mac rechnet in logischen Punkten.
- Flächen mit eigener Farbe zeichnen keine Ränder → Kanten als eigene AIS-Ebene.
- `ctx.MainSelector()` ist in pythonocc nicht nutzbar → Punkt unter der Maus per Sichtstrahl (`_punkt_unter_maus`).
- Saved Views: Kamera blickt entlang **+z** der Platzierung (sonst Schrift gespiegelt), Fenster = PLANAR_BOX.
- pythonocc mit VTK zieht unter Windows/Linux Qt aus conda → DLL-Konflikt mit PySide6 → `build = "novtk*"`.
- Offscreen-Rendering stürzt auf macOS ab → Tests mit Platzhalter, echter 3D-Test separat.

## GitHub-Bau
- Workflow „Apps bauen“ (Plattform wählbar, Tests an/aus, Zeitlimit 60 min/Job, Tests mit 300 s je Test).
- Korrigiert: setup-pixi-Cache, VTK/Qt-DLL-Konflikt (Windows), Hänger abgesichert (modale Dialoge in Tests).
- **Läufe seit 26.10. nicht gestartet: GitHub-Konto (Zahlung/Ausgabenlimit) – Nutzer muss das klären.**
  Danach: `gh workflow run "Apps bauen" -f plattform=alle -f tests=true` und Ergebnis prüfen.
- Lokal gebaut und geprüft: macOS-arm64 (Selbsttest, 3D-Bild aus der .app, Symbol).

## Offen / nächster Schritt
- Schritt 4: Vergleich zweier Stände (Ausrichten, Flächenzuordnung, Farbkarte, PMI-Diff, Änderungsliste, Prüfen).
- Aus PLAN.md 8.1/8.2: Ansichten vor/zurück + Vorschaubilder, gezielte Suche (bezug:/wert:/typ:), Ansichtssuche.
- JT über TKJT (GPL v2+) als Bau-Variante – mit Schritt 7.
- Lizenz von 3DGmax festlegen (Vorschlag wie ZGmax: AGPL-3.0; verträglich mit TKJT).
- Nutzer: JT-, 3D-PDF- und eigene STEP-Beispiele liefern.
