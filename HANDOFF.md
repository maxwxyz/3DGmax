# Handoff (2026-10-26)

Branch: `main` (no other branches). Version 0.1 plus many unreleased entries in `programm/CHANGELOG.json`
(bump only via `pixi run python packaging/release.py minor --git`, then `git push --follow-tags`).

## Check against plan / roadmap
| Step (PLAN.md §5) | Status |
|---|---|
| 1 Feasibility | ✅ |
| 2 Viewer | ✅ incl. view cube, quick measure, model properties (open: PLAN §8.12 items 4–10, thumbnails, LOD) |
| 3 Measure | ✅ |
| 4 Compare | ✅ incl. manual alignment, deviation color map (open: moved detection, graphical PMI compare, assemblies, meshes) |
| 5 Output | ✅ PDF per view, comparison PDF, PMI change PDF, project container, folder comparison (open: views as drawings HLR) |
| 6 Formats | ⬜ **next**: QIF, IGES/STL/OBJ/glTF/3MF |
| 7 JT via TKJT | ⬜ (no free JT test files with PMI found) |
Details: `docs/Roadmap.md`; future topics: PLAN.md §8 (tolerance zones, annotating, graphical PMI/OCR, tolerance stack-up,
PMI editing, CATIA files).

Last session: deviation color map (kern/abweichung.py: signed, exact projection with trim check, legend via
AIS_ColorScale, value on click), PLAN §8.12 gap analysis vs common viewers, quick measure in the status bar
(kern/schnellinfo.py), model properties dialog (kern/eigenschaften.py, ui/eigenschaften_ui.py), window/dock/column
state saved on exit, MSAA, sans-serif labels, subtler view cube (hover opacity).
**Not visually checked** (screen was locked): new cube look and MSAA – check with a screenshot first.
Next per PLAN §8.12: camera perspective/undo, hide selected + tree search + 3D PMI follows filter, DRF display.

## Environment and commands
```bash
pixi install                      # Python 3.14, pythonocc-core 8.0.1 (no VTK), PySide6 6.11 (conda), PyInstaller
pixi run start                    # application
pixi run test                     # offscreen tests (~2 min); CI: pixi run test-ci
DG_BILDSCHIRM=1 pixi run python -m pytest -q tests/test_bildschirm.py   # real 3D view incl. view cube (Mac)
pixi run python werkzeuge/testmodelle.py          # CTC-01 variants (tests/daten/varianten)
pixi run python werkzeuge/tr_texte.py             # all tr() texts (completeness test uses it)
packaging/build_mac.sh [--ohne-tests]             # verified locally: tests, build, self-test, 3D image
```

## GitHub build
Workflow "Apps bauen" green on Windows/Linux/macOS (last checked run 40369306525). Repository is public.

## Test data
- NIST AP242 (daten/nist, not in repo), selection in tests/daten; D2MI 904 rev C ↔ 906 (daten/nist_d2mi).
- NIST CAD archives (native CAD, drawings) in daten/nist_cad_dl – no JT/3D PDF included.

## Findings (not obvious)
- OCCT viewer on macOS uses logical points; faces with custom color draw no boundaries → edges as own layer;
  the context default face boundaries are switched off (otherwise faint edges in shaded mode).
- `ctx.MainSelector()` unusable in pythonocc → point under the mouse via view ray.
- AIS_Triangulation only accepts display mode 0 (`ctx.Display(ais, 0, -1, False)`); vertex colors packed
  RGBA bytes as signed int32. AIS_ColorScale needs its own Prs3d_TextAspect (TextAspect() is None).
- View cube on macOS: drawn in device pixels but picked in logical points → size scaled by devicePixelRatio
  and pick coordinates mapped from the top-right corner (`_wuerfel_unter_maus`). `Font` enums not wrapped (no bold).
- View cube: `AIS_ViewCube`, owner via `AIS_ViewCubeOwner.DownCast(ctx.DetectedOwner()).MainOrientation()`;
  re-displayed after `RemoveAll` in `_baue_szene`, hidden for report images.
- Saved views: camera looks along +z of the placement. Annotation writing plane stored in `Grafik.ebene`
  (not every file has REPOSITIONED placements – then plane via SVD + snap to edge directions).
- Comparison: mesh distance is only a preselection; values near/above tolerance exact against the B-rep;
  fine alignment with point-to-plane ICP.
- Offscreen rendering crashes on macOS → tests use a placeholder view, real 3D test separate.
- Saved table column state key includes the column count (new columns invalidate old state).
