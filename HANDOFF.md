# Übergabe (Stand 2026-10-26)

Branch: `main` (keine weiteren Branches). Version 0.1 + viele unveröffentlichte Einträge in `programm/CHANGELOG.json`
(Version erhöhen nur mit `pixi run python packaging/release.py minor --git`, dann `git push --follow-tags`).
**Pause – wartet auf Eingabe des Nutzers.**

## Abgleich Plan / Roadmap
| Schritt (PLAN.md §5) | Stand |
|---|---|
| 1 Machbarkeit | ✅ |
| 2 Viewer | ✅ (offen: Vorschaubilder je Ansicht, Cache/Detailstufen für große Baugruppen) |
| 3 Messen | ✅ |
| 4 Vergleich | ✅ Kern + Oberfläche (offen: Abweichungsfarbkarte mit Skala, Punktpaare in der Oberfläche, verschoben-Erkennung, grafischer PMI-Vergleich, Baugruppen, Mesh/Scan) |
| 5 Ausgaben | ⬜ als Nächstes: PDF je Ansicht, Vergleichsbericht, PMI-Änderungstabelle, Projekt-Container, Ordnervergleich |
| 6 Formate | ⬜ |
| 7 JT über TKJT | ⬜ (keine freien JT-Testdateien mit PMI gefunden) |
Details je Funktion: `docs/Roadmap.md`; Zukunftsthemen: PLAN.md §8–9 (Toleranzzonen, Annotieren, grafische PMI/OCR, FMK).

## Umgebung und Befehle
```bash
pixi install                      # Python 3.14, pythonocc-core 8.0.1 (ohne VTK), PySide6 6.12, PyInstaller
pixi run start                    # App starten
pixi run test                     # 56 Tests offscreen (~60 s); CI: pixi run test-ci
DG_BILDSCHIRM=1 pixi run python -m pytest -q tests/test_bildschirm.py   # echte 3D-Ansicht (Mac)
pixi run python werkzeuge/testmodelle.py          # Varianten von CTC-01 (tests/daten/varianten)
pixi run python werkzeuge/bildschirmfotos.py docs/bilder --thema hell|dunkel
packaging/build_mac.sh [--ohne-tests]             # lokal geprüft: Tests, Bau, Selbsttest, 3D-Bild
```

## GitHub-Bau
Workflow „Apps bauen“ ist korrigiert (Cache, VTK/Qt-DLL-Konflikt Windows, Zeitlimits). **Läufe werden von GitHub
nicht gestartet (Zahlung/Ausgabenlimit des Kontos).** Nach Klärung: `gh workflow run "Apps bauen" -f plattform=alle -f tests=true`.

## Testdaten
- NIST AP242 (daten/nist, nicht im Repo), Auswahl in tests/daten; D2MI 904 rev C ↔ 906 (daten/nist_d2mi).
- NIST CAD-Archive (native CAD, Zeichnungen) in daten/nist_cad_dl – keine JT/3D-PDF enthalten.

## Erkenntnisse (nicht offensichtlich)
- OCCT-Viewer auf dem Mac in logischen Punkten; Flächen mit eigener Farbe ohne Ränder → Kanten als eigene Ebene.
- `ctx.MainSelector()` in pythonocc unbrauchbar → Punkt unter der Maus per Sichtstrahl.
- Saved Views: Kamera blickt entlang +z der Platzierung. pythonocc ohne VTK (`build = "novtk*"`).
- Vergleich: Netzabstand nur Vorauswahl; Werte nahe/über Toleranz exakt gegen B-Rep. Feinpassung Punkt-zu-Ebene-ICP.
- Offscreen-Rendering stürzt auf macOS ab → Tests mit Platzhalter, echter 3D-Test separat.
