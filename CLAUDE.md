# 3DGmax – Hinweise für Claude

3D-PMI-Viewer und -Vergleich (Model Based Definition). Technik: Python 3.14 (pixi), PySide6, OCCT über pythonocc-core; Semantik/Farben/Grafik aus eigenem STEP-Leser.
**Vor jeder Arbeit `HANDOFF.md` und `PLAN.md` lesen.** Schwesterprojekt: ZGmax (`../Zeichnungsvergleich`).

## Regeln
- Nutzer schreibt Deutsch; Antworten auf Deutsch. Fähigkeiten von Bibliotheken nicht erfinden – per Versuch prüfen.
- Kommentare/Docstrings im Code deutsch ohne Umlaute (ae, oe, ue), kurze Funktionen, keine toten Knöpfe.
- Oberfläche deutsch, alle Texte über `tr()`, Übersetzung Englisch in einer Datei.
- Tests vor jedem Commit grün. Commits enden mit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  **Nach jedem Commit pushen** (`origin` = github.com/maxwxyz/3DGmax, privat).
- Am Ende jeder Antwort `HANDOFF.md` aktualisieren – **mit Abgleich gegen PLAN.md und docs/Roadmap.md** (was ist
  fertig, was offen); Unfertiges auf einem Branch `wip/...`, nicht auf `main`.
- Nach Commit und Push **nicht mehr benötigte Branches löschen** (lokal und auf GitHub).
- Ist keine Aktion mehr offen: **Pause und auf Eingabe des Nutzers warten** (nicht von selbst weitermachen).
- Tests: `pixi run test` (offscreen). Neue `tr()`-Texte in `programm/i18n_en.json` eintragen (Test prüft das).
- Jede sichtbare Änderung in `programm/CHANGELOG.json` unter `unreleased` (de und en, gleiche Reihenfolge).
  **Version nur mit `packaging/release.py minor|patch|major --git` erhöhen** – das führt das Changelog mit
  (CHANGELOG.md/CHANGELOG_EN.md) und setzt den Tag; danach pushen (auch Tags).
- Roadmap `docs/Roadmap.md` (umgesetzt/geplant) bei jeder Funktion mitpflegen.
- Hilfsskripte setzen `DG_EINSTELLUNGEN=<tmp.ini>`; nie die echten Einstellungen ändern.
- Bauen: `packaging/build_*.sh|bat [--ohne-tests]`, GitHub-Workflow „Apps bauen“.
