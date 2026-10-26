# Übergabe (Stand 2026-10-26)

Branch: `main`. Schritt 1 (Machbarkeit) und Schritt 2 (Viewer) fertig. Version 0.1 (+ unveröffentlichte Einträge in
`programm/CHANGELOG.json`).

## Umgebung und Befehle
```bash
pixi install                      # Python 3.14, pythonocc-core 8.0.1, PySide6 6.12, PyInstaller
pixi run start                    # App starten (optional Datei dahinter: pixi run start datei.stp)
pixi run test                     # alle Tests offscreen (Kern, Oberfläche, Stresstest), ~7 s
DG_BILDSCHIRM=1 pixi run python -m pytest -q tests/test_bildschirm.py   # echte 3D-Ansicht (Mac mit Bildschirm)
pixi run selbsttest
pixi run python werkzeuge/bildschirmfotos.py docs/bilder --thema hell   # Doku-Bilder (DG_LANG=en für englisch)
pixi run python werkzeuge/tr_texte.py   # alle tr()-Texte; Test prüft, dass i18n_en.json vollständig ist
packaging/build_mac.sh [--ohne-tests]    # bzw. build_linux.sh / build_windows.bat → dist/
```
GitHub: Actions → „Apps bauen“ (Plattform wählbar, Tests an/aus). Nutzt pixi (`prefix-dev/setup-pixi`).

## Aufbau
- `programm/kern/`: `p21.py` (STEP-Graph), `laden.py`, `pmi*.py`, `ansichten.py`, `praesentation.py` (grafische PMI),
  `baum.py`, `farben.py` (Farben aus STEP – pythonocc-Bindung für XCAF-Farben unbrauchbar).
- `programm/ui/`: `hauptfenster.py`, `ansicht3d.py` (OCCT-Viewer + eigene Navigation; `PlatzhalterAnsicht` offscreen),
  `panels.py`, `lader.py` (Hintergrund), `hilfe.py` (Anleitung mit automatischer Menüreferenz), `thema.py`.
- Einstellungen: QSettings „3DGmax“; Tests/Skripte setzen `DG_EINSTELLUNGEN=<ini>` (echte nie berühren).

## Erkenntnisse (nicht offensichtlich)
- OCCT-Viewer auf dem Mac rechnet in logischen Punkten (keine Retina-Skalierung der Mauskoordinaten).
- Flächen mit eigener Farbe (`AIS_ColoredShape.SetCustomColor`) zeichnen keine Ränder → Kanten als eigene AIS-Ebene.
- Offscreen-Rendering von OCCT stürzt auf macOS ab → Tests nutzen den Platzhalter, echter 3D-Test separat.
- Gebaute App braucht OCCT-Ressourcen (`occt_resources`, gesetzt in `packaging/start_3dgmax.py`). Größe: 492 MB
  (.app), 145 MB (ZIP) – verkleinern möglich (nur benötigte OCC.Core-Module).

## Offen / nächster Schritt
- Schritt 3: Messen (Abstand, Winkel, Radius, Wandstärke, Koordinaten, Fang, Liste, CSV).
- Viewer-Feinschliff: App-Symbol fehlt; „Ganzes Modell zeigen“ bezieht die PMI-Grafik mit ein (Modell wirkt klein);
  gespeicherte Ansicht stellt nur Richtung ein, nicht Ausschnitt/Zoom der Datei; Hinweise (Notes) und
  Bezugsstellen als eigene Listeneinträge; GitHub-Bau noch nicht erfolgreich durchgelaufen (siehe unten).
- Nutzer: JT-, 3D-PDF- und eigene STEP-Beispiele liefern.

## GitHub-Bau (Stand 2026-10-26)
- Lauf 1: Fehler in der Workflow-Einstellung (setup-pixi: Cache ohne Installation) → behoben.
- Lauf 2: Windows-Tests scheiterten (`DLL load failed while importing QtCore`): pythonocc-Variante mit VTK zog Qt aus
  conda-forge nach → behoben durch `build = "novtk*"` in pixi.toml (alle Plattformen), pytest-qt entfernt.
- Lauf 3 (40296935931): **nicht gestartet – GitHub-Ausgabenlimit/Zahlung des Kontos**. Nach Klärung unter
  „Billing & plans“: Actions → „Apps bauen“ erneut starten (`gh workflow run "Apps bauen" -f plattform=alle -f tests=true`).
- Lokal gebaut und geprüft: macOS-arm64 (`packaging/build_mac.sh`, Selbsttest und `--bild` aus der .app OK).
