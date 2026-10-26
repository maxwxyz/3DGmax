# 3DGmax

View, measure and compare 3D models with PMI (dimensions, geometric tolerances, datums) from STEP AP242 – for
Model Based Definition without 2D drawings. 3DGmax reads PMI **semantically** (as evaluable values, not just as a
picture) and compares two revisions of a model in geometry **and** PMI, with a guided review and a review report.

![3DGmax comparing two revisions](docs/bilder/vergleich_hell.png)

## Features
- STEP AP242/AP214/AP203 with semantic and graphical PMI, saved views, assembly tree
- CATIA-style navigation (classic optional), section planes, display modes, light/dark theme
- PMI list with search and filters, PMI ↔ face highlighting, plausibility check, CSV export
- Measuring: distance, angle, radius/Ø, wall thickness, coordinates with snapping
- Comparison: automatic alignment (best fit), geometry status per face, semantic PMI diff, change list with review
  walk-through and report with SHA-256 checksum
- User interface in German and English

Status and plans: [docs/Roadmap.md](docs/Roadmap.md) · [PLAN.md](PLAN.md)

## Run from source
Requires [pixi](https://pixi.sh).
```bash
pixi install
pixi run start          # application
pixi run test           # tests (offscreen)
```

## Build portable apps
`packaging/build_mac.sh`, `packaging/build_linux.sh`, `packaging\build_windows.bat` (each accepts `--ohne-tests`
to skip tests), or on GitHub: *Actions › Apps bauen*.

## License
© 2026 Max Wilfinger. GNU General Public License v3 or later (GPL-3.0-or-later), see [LICENSE](LICENSE).
Libraries used (Open CASCADE Technology, pythonocc-core, Qt/PySide6 under LGPL and others) are listed in
*Help › About 3DGmax*. Test models: NIST MBE PMI Validation and Conformance Testing (public domain).
