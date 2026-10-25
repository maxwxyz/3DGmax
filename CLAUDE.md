# 3DGmax – Hinweise für Claude

3D-PMI-Viewer und -Vergleich (Model Based Definition). Geplante Technik: Python 3.14, PySide6, OCCT über OCP.
**Vor jeder Arbeit `HANDOFF.md` und `PLAN.md` lesen.** Schwesterprojekt: ZGmax (`../Zeichnungsvergleich`).

## Regeln
- Nutzer schreibt Deutsch; Antworten auf Deutsch. Fähigkeiten von Bibliotheken nicht erfinden – per Versuch prüfen.
- Kommentare/Docstrings im Code deutsch ohne Umlaute (ae, oe, ue), kurze Funktionen, keine toten Knöpfe.
- Oberfläche deutsch, alle Texte über `tr()`, Übersetzung Englisch in einer Datei.
- Tests vor jedem Commit grün. Commits enden mit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  **Nach jedem Commit pushen** (`origin` = github.com/maxwxyz/3DGmax, privat).
- Am Ende jeder Antwort `HANDOFF.md` aktualisieren; Unfertiges auf einem Branch `wip/...`, nicht auf `main`.
