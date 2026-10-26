# Handoff (2026-10-26)

Branch: `main` (no other branches). Version 0.1 plus many unreleased entries in `programm/CHANGELOG.json`
(bump only via `pixi run python packaging/release.py minor --git`, then `git push --follow-tags`).

## Check against plan / roadmap
| Step (PLAN.md §5) | Status |
|---|---|
| 1 Feasibility | ✅ |
| 2 Viewer | ✅ (open: view thumbnails, cache/levels of detail for large assemblies) |
| 3 Measure | ✅ |
| 4 Compare | ✅ core + UI (open: deviation color map, point pairs in UI, moved detection, graphical PMI compare, assemblies, meshes) |
| 5 Output | ⬜ **in progress next**: PDF per saved view, comparison report, PMI change table, project container, folder comparison |
| 6 Formats | ⬜ |
| 7 JT via TKJT | ⬜ (no free JT test files with PMI found) |
Details: `docs/Roadmap.md`; future topics: PLAN.md §8 (tolerance zones, annotating, graphical PMI/OCR, tolerance stack-up).

## Environment and commands
```bash
pixi install                      # Python 3.14, pythonocc-core 8.0.1 (no VTK), PySide6 6.12, PyInstaller
pixi run start                    # application
pixi run test                     # offscreen tests (~60 s); CI: pixi run test-ci
DG_BILDSCHIRM=1 pixi run python -m pytest -q tests/test_bildschirm.py   # real 3D view (Mac)
pixi run python werkzeuge/testmodelle.py          # CTC-01 variants (tests/daten/varianten)
pixi run python werkzeuge/bildschirmfotos.py docs/bilder --thema hell|dunkel
packaging/build_mac.sh [--ohne-tests]             # verified locally: tests, build, self-test, 3D image
```

## GitHub build
Workflow "Apps bauen" fixed (cache, VTK/Qt DLL clash on Windows, timeouts). Repository is public now.

## Test data
- NIST AP242 (daten/nist, not in repo), selection in tests/daten; D2MI 904 rev C ↔ 906 (daten/nist_d2mi).
- NIST CAD archives (native CAD, drawings) in daten/nist_cad_dl – no JT/3D PDF included.

## Findings (not obvious)
- OCCT viewer on macOS uses logical points; faces with custom color draw no boundaries → edges as own layer.
- `ctx.MainSelector()` unusable in pythonocc → point under the mouse via view ray.
- Saved views: camera looks along +z of the placement. pythonocc without VTK (`build = "novtk*"`).
- Comparison: mesh distance is only a preselection; values near/above tolerance exact against the B-rep;
  fine alignment with point-to-plane ICP.
- Offscreen rendering crashes on macOS → tests use a placeholder view, real 3D test separate.
