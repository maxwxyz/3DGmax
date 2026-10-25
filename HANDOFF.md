# Übergabe (Stand 2026-10-25)

Branch: `main`. Noch kein Code – nur Plan.

## Fertig
- Recherche ähnlicher Programme und Bibliotheken, Plan in `PLAN.md` (Markt, Technik, Formate, Architektur, Schritte,
  Risiken, offene Entscheidungen).
- Geprüft: `cadquery-ocp` 8.0.1.1.0 (OCCT 8.0.1) als pip-Wheel für Python 3.14 auf macOS/Windows/Linux;
  `pythonocc-core` 8.0.1.2 nur über conda-forge.

## Offen / nächster Schritt
- Nutzer bestätigt Entscheidungen aus `PLAN.md` Abschnitt 7.
- Dann Schritt 1 (Machbarkeit, ohne Oberfläche): `.venv` mit OCP, NIST-PMI-Modelle laden, PMI und Ansichten
  auflisten, Abgleich mit NIST STEP File Analyzer, Mini-Versuch OCCT-Viewer im Qt-Fenster, JT/U3D anlesen.
  Ergebnis in `docs/Machbarkeit.md`.
