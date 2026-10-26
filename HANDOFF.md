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
| 5 Output | ✅ PDF per view, comparison PDF, PMI change PDF, bill of characteristics, measurement report, drawings (HLR), project container, folder comparison |
| 6 Formats | 🟡 IGES, STL, OBJ, glTF/GLB, 3MF, QIF (B-rep + semantic PMI) done; open: PRC/3D PDF (§8.15), QIF graphics/views |
| 7 JT via TKJT | ⬜ (no free JT test files with PMI found) |
Details: `docs/Roadmap.md`; future topics: PLAN.md §8 (tolerance zones, annotating, graphical PMI/OCR, tolerance stack-up,
PMI editing, CATIA files).

Last session: deviation color map, quick measure, model properties, PLAN §8.12 items done: camera back/forward
(Alt+←/→, history in OcctAnsicht._verlauf, recorded 450 ms after the camera rests), perspective (P), hide selection
(H) synced with the tree, tree search, 3D PMI follows the list filter, datum reference frame colors/labels, draggable
column widths. PLAN §8.13: ASME vs ISO GPS (no free ISO test files known).
**Not visually checked** (screen was locked): view cube look, MSAA, DRF colors/labels, legend – screenshot first.
Last session (continued): PLAN §8.14 done – auto-fit of shown columns, About without author line and macOS menu
roles (About/Preferences/Quit), fixed pivot on middle click with a pixel-constant cross shown only while
orbiting/panning, DRF labels white on colored box; standard detection (kern/norm.py: DOCUMENT 'Geometric Tolerancing
Standard' > text hints > ISO 14405/ASME modifiers > file name; fallback ISO GPS; override per file under
Model › Standard; Pmi.norm drives terms, ASME-2018 rule, envelope note); bill of characteristics (kern/merkmale.py,
balloon column, 3D balloons with B, CSV and PDF export).
Visual checks were done with View.Dump (screen locked); the cube look on a real screen is still unchecked.
Then: exploded view (OcctAnsicht.setze_explosion: radial offsets via SetLocalTransformation, PMI hidden, measuring
blocked; fit includes local transforms), parts list (kern/stueckliste.py, ui/stueckliste_ui.py; groups by base name +
TShape), analyses (kern/analyse.py: draft, curvature radius, wall thickness by ray; ui/analyse_ui.py dock; generic
color map via abweichung.Skala). Test assembly: werkzeuge/baugruppe.py -> tests/daten/baugruppe.stp.
Then ISO 286 (kern/iso286.py): IT table and fundamental deviations up to 500 mm, hole rules (mirror, delta, M6
250–315 exception); cross-checked against the MIT-licensed isofits tables (1334 equal, 6 differ = errors in that
data, inconsistent with its own IT values); Pmi.abmasse() falls back to the class.
Then step 6 formats: kern/laden.lade_modell (IGES via XCAF, STL/OBJ/glTF/GLB via OCCT mesh readers, own 3MF
reader), mesh faces have no surface (guards in messen, schnellinfo, abweichung, vergleich_geo, analyse, ausrichten,
ray picking `_netz_treffer`); test files from werkzeuge/formate.py (tests/daten/formate). Fixed nested assembly
placement in kern/baum.py.
Then QIF (kern/qif.py): own B-rep builder (surfaces/curves -> OCCT, ShapeFix_Wire connects loop edges, sewing with
Modified() to keep the QIF face ids), semantic PMI (characteristics, datums, DRF), units per value (linearUnit).
Test files: NIST QIF from qif-community (licence not stated) only local in daten/qif; test skips without them.
Validated: CTC-01 and FTC-06 volume/size identical to STEP; FTC-08/09 QIF are other model revisions (scaled).
Then: targeted PMI search, own views + measurement report PDF, drawings (kern/zeichnung.py: HLRBRep exact, standard
sheet by projection method, SVG/DXF own writers, PDF via QSvgRenderer on A3 with title block; PMI graphics projected,
placeholder texts as SVG/DXF text).
Next: PRC/3D PDF reader (PLAN §8.15, NIST STC PDFs contain PRC), generated graphical PMI (§8.16), QIF graphical PMI
and views, JT via TKJT
(step 7; free JT file without PMI: daten/nist_cad_dl/nist-cad-models-mtc-assembly.zip -> NX/NIST mtc crada assembly.jt).

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
