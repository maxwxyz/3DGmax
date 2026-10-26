# 3DGmax

3D-Modelle mit PMI (Maße, Toleranzen, Bezüge) aus STEP AP242 ansehen, messen und – in Arbeit – zwei Stände
semantisch vergleichen. Python 3.14, PySide6, Open CASCADE (pythonocc-core).

```bash
pixi install
pixi run start          # App
pixi run test           # Tests
```

Bauen: `packaging/build_mac.sh`, `build_linux.sh`, `build_windows.bat` (jeweils `--ohne-tests` möglich) oder auf
GitHub „Actions › Apps bauen“.

© 2026 Max Wilfinger. Lizenz: GNU General Public License v3 oder später (GPL-3.0-or-later), siehe `LICENSE`.
Verwendete Bibliotheken (OCCT, pythonocc, Qt/PySide6 unter LGPL u. a.) siehe „Hilfe › Über 3DGmax“.
Testmodelle: NIST MBE PMI Validation and Conformance Testing (gemeinfrei).
