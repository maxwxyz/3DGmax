# Handoff (2026-10-28, local Mac session, user away ~8 h – work continues autonomously)

## Current state
All work on `main`, pushed; no other branches. Version not bumped (user's approval needed). Full suite last green on
the Mac (200 tests incl. the new ones, ~11 min); `pixi run test-schnell` skips the six `langsam` tests.

Done in this local session (commit):
- Test strategy (§8.29): `langsam` marker, `test-schnell`, `test-betroffen -- --schnell` – `b5980b6`.
- macOS Finder double-click / "Open With" loads the file (QFileOpenEvent), all formats registered – `d623a92`.
- Assembly variation (§8.20 stage 4): gap/flush measures, worst case (LP) and Monte Carlo (weighted fit), contributors,
  requirement/Cpk, PDF, example; connections pin–slot, sphere–plane, ball joint – `34c7f1d`.
- UI/UX plan `docs/UI_UX_Plan.md` (§8.30) and stage 1 (command search Ctrl/⌘+K, task start page, menu cleanup);
  multi-selection highlight fix; all-zones only for visible parts – `34c7f1d`.
- Stack-up stage 3 (§8.8): distributions by production type, applicable method bold (n_eff ≥ 4), what-if, UX,
  research of the state of the art with sources – `2342bd6`.
- Change table with characteristic/old/new/Δ/tendency – `3d1658c`.
- Comparison view modes (§8.31) and stack-up stage 3b (thermal expansion, materials, per-part temperatures, length
  ranges, adjusting member, directions from the closing dimension, walk chain, `.3dgkette`, gearbox example),
  P21 UTF-8 reading – `4efc9df`.
- Step 7 JT via TKJT (§8.32): `packaging/jt/bauen.sh` + own converter `jt2glb`, `.jt` loading, app variant
  `DG_MIT_JT=1` (checked: bundled tool loads the bundled OCCT libraries); wiggle play/pause – `a102822`.
- Tolerance zones at every instance and at the assembled position – `f06ef40`.
- Assembly: reverse a connection (180°) and swap parts – `15d3147`.
- UI scaling option (View › Size of the interface) – `db74f81`.
- Comparison: tree shows part status – `2f3a518`; parts list with material and density – `5c91352`.
- Stack-up stage 4a (sensitivity factor, Bender, mean shift, tolerance allocation) – `6677df5`; link line in 3D while
  walking the chain – `4c1716b`.
- Assembly: move along open DOF (numeric) – `26e9369`; ISO 286 j/J, a/A, fit pairs – `5a2a691`; plausibility: closed
  dimension chains – `3c66888`; explosion along X/Y/Z – `dfd8bb8`; clashes: depth, curves, PDF, project – `643aa2e`;
  several windows with coupled cameras – `1c1068a`; scan check aligned by hand from point pairs ("By hand …") – `9b015a9`.
- Plausibility: basic dimensions with tolerance, location toleranced twice, pattern dimension on different sizes, datum
  target counts – `391bb1f`; clashes: free range of motion along open DOF up to the first collision – `277b113`.
- Stack-up: distribution from measured values (paste/CSV) – `3ce67f1`; several saved what-if scenarios with comparison
  (stored in `.3dgkette`, not in the project) – `76e8b6a`; correlated links (groups with ρ) – `c95fdb3`; folded normal
  and Rayleigh distributions – `6ea8727`.
- Comparison: change list per instance – `69e86d4`; both trees in "Side by side" – `8793c8f`.
- Clashes with mesh parts and mixed pairs (approximate, marked ≈) – `d102cce`.
- Drawing: hatched section views – `3b89458`; sheet formats A4–A0 with frame, title block, standard scale – `6e4850b`.
- Gear recognition (§8.27) stage 1 – `0c1a2ec`; gear pairs – `fb273a5` (test generator `werkzeuge/zahnrad.py`).
- Plausibility: gear data in notes vs geometry – `b9ad4aa`.
- Save STEP with edited PMI (§8.28): lossless value replacement – `aecf915`; own PMI appended as semantic AP242
  entities (single parts) – `e0a123d`, angular dimensions – `d56697f`. Full suite green before these (247 passed).
- QIF measurement results (assign by balloon, assess, into the characteristics list; official QIF sample under
  Boost licence in `tests/daten/qif/`) – `96c09f4`; ring zones per cross-section – `72b6699`; 3-2-1 template –
  `1eb9c93`; histogram in the assembly report – `542fc64`; axis measures – `7b273cd`; scan roundness/runout per
  cross-section – `dea17e8`; datums as contact per ISO 5459 – `2abb796`.
- E57 point clouds (own reader; libE57Format test data CC0 / Test Data License in `tests/daten/e57/`) – `2aef5db`;
  involute splines – `5f0b63f`; own PMI written in assemblies – `ecd7304`.
- Full suite green (266 passed) – after `ecd7304`. Then: fit class / Ⓜ/Ⓛ edits written to STEP – `74bd8de`;
  3D handle (AIS_Manipulator, only open DOF; on-screen test `tests/test_bildschirm.py::test_3d_griff_ziehen`) –
  `72a5647`; second OCCT view rendered black → fixed-function pipeline for further views – `af9b6f1`; Qt's own texts
  in German (qtbase_de.qm bundled) – `afec0af`.
- Screen was available this time: on-screen checks done for the 3D handle, side-by-side views (fixed), stack-up window
  with what-if bar and scenarios (looks fine). Local macOS build after `afec0af` OK (qtbase_de.qm bundled,
  `--selbsttest` OK).
- Not done for lack of a verifiable source or test data (kept open in the roadmap): ISO 286 b/t–zc/>500 mm (isofits
  has none of them), surface texture/weld symbols (no sample file), large-assembly LOD (no large model; 3.7 MB STEP
  loads in 2.4 s).

**Deferred questions for the user** (do not block on them):
- UI/UX stage 2 (workspaces) changes the layout a lot – implement only after you have read `docs/UI_UX_Plan.md`?
- JT: the only free JT file (NIST MTC) is JT 10.5, which TKJT cannot read (no free JT 10 spec). Could you export a
  JT 9 (e.g. CATIA → JT, or NX "JT 9.5") of a NIST model for an end-to-end test of `jt2glb` (units, structure,
  colours)? Until then the converter is verified to build/run and to reject JT 10; loading is tested with a stand-in.
- Version bump: many unreleased entries – release as 0.2 when you approve (`packaging/release.py minor --git`).
- Comparison modes: shortcuts Alt+1…6 chosen because 1–7 are the standard views – OK?
- Stack-up "Kraftrichtung": implemented as "directions from the closing dimension" (two faces) instead of a load
  direction, because a load direction alone does not give unambiguous signs – OK?

**Check in CATIA/NX please:** open a STEP written by File › Save STEP with edited PMI (edited values and own PMI
from the advisor) – OCCT and our reader read it; a commercial reader is the real test of the CAx-IF structure.

**Visual check on the real screen still open** (screen locked / no capture permission tonight):
- (Resolved 2026-10-28: the second OCCT view in the process rendered without shaders – black background, no
  lighting, unlabelled cube; also further windows. Further views now use the fixed-function pipeline; they look a bit
  lighter than the first view, visible when blinking – tell me if all views should use the same pipeline.)
- Stack-up window layout (result table, share bars, histogram, what-if bar), assembly "Measures" tab, start page,
  command search popup, comparison mode bar.
- Plus everything listed under "Next" item 1 below (from the cloud handoff).

## Previous cloud handoff (2026-10-27, kept for reference)
Cloud session 2026-10-27 (Linux, no screen, no `daten/`). All work is on `main`, pushed; no unfinished branch
(`claude/inspiring-wright-dqsu4q` only mirrors `main` and can be deleted). Version not bumped.

**Packages done (commit):**
1. PRC / 3D PDF reader – `b0c7d7d` (kern/prc.py, prc_bits.py, prc_tabelle.py; mesh with colors, markups as
   graphical PMI notes, saved views with camera; drawings and thumbnails of mesh models via an own projection
   with a depth buffer, because OCCT HLR crashes on surface-less faces).
2. Generated graphical PMI stage 2 – `4e39505` (annotation planes from the saved view or the model plane, frames
   with compartments, datum triangle and box, overlap-free layout, View › "Show generated PMI display").
3. Rotated/mirrored elements and per-instance comparison – `1c7fd8e`.
4. QIF graphical PMI and saved views – `b5774e8` (kern/qif_grafik.py).
5. Multiple section planes (up to three; union, or common region via chained clip planes) and section contour
   export SVG/DXF/PDF (kern/schnitt.py) – `978dc82`.

Extra on request: STEPZ (`6620f29`); start error log and message box for the portable app (`5ca02ef`, Windows
build run 28 green); smooth side panel resizing and a readable, opaque view cube with calm hover color (`9d94eb1`);
PMI text size and generated PMI placement after the Xvfb check (`a259428`); fix: the G / generated PMI switches
raised a TypeError in the 3D view (`1942fbd`); graphical-only PMI evaluated in the table (§8.18, `6108e44`,
kern/pmi_ableiten.py, marked "≈ derived"); PRC model edges from the tessellation wire indices (commit "PRC: model
edges from the tessellation wire indices"). PLAN §8.17 records the STEP AP242 XML research (structure/PDM model with
external geometry, no free samples – deferred). Then: per-instance status colors in comparison, tolerance zones
stage 2 (§8.5: patterns, Ⓜ/Ⓛ bonus, surface space, Ⓟ, UZ, size envelopes, general tolerances ISO 2768/22081,
scope selection/faces/all, median plane, spherical zone, context menus), focus mode (Shift+T), plans §8.20 (3D
tolerance analysis) and §8.21 (clash/band/intersection, DOF). Then: new manual DE/EN with generated screenshots
(`packaging/doc_screenshots.py` under Xvfb, `programm/doc_img/`, F1 opens it in the browser), scan against PMI
tolerances (§8.23, `kern/scanpruefung.py`, Tools menu), new test data (`werkzeuge/testmodelle.py`: PMI-only,
small-geometry and combined variants of CTC-01, two generated scans as PLY), more robust best fit for nearly
symmetric parts, plane zones with the real face boundary, small thumbnails, PDF PMI columns as in the list, lazy
scipy import (window set-up 0.6 → 0.2 s) and `--startzeit`. PLAN §8.22 records the requested plausibility check. Then:
plausibility check stage 1 (§8.22, `kern/plausibilitaet.py`, part of Model › Check PMI with a category column),
status-bar progress with Cancel for every background job (`ui/lader.py: Abbruch, melder` – the job stops at its
next progress report), closable tabs on stacked side panels, side-panel resize jank fixed (cause was
`V3d_View::MustBeResized` at ~50 ms, called twice per pixel by our filter and pythonocc's resizeEvent; now at most
every 250 ms plus once after dragging: 117 → 20 ms per step under Xvfb), general tolerances as a toggle
(View › Show general tolerances; also at selected faces without PMI with "Show tolerance zone"). Then: wireframe
contrast edges (setting), calmer view cube, stack-up Cp (RSS fix: ±3σ of the closing dimension), angles excluded,
chain cleared on model change, PMI list right-click selects the row first, section views from AP242 saved views
(§8.25, test file `ctc01_schnittansicht.stp`), start screen (PyInstaller + Qt splash), File › Examples (§8.24,
`kern/beispiele.py`). Plan additions: §8.8 per-link Cp and 3D-picked chains, §8.20 snapping assembly, §8.24–8.26. Then: stack-up from
the 3D selection (`kette_aus_flaechen`, per-link distribution/Cp, shares) and clash/contact/band analysis
(`kern/kollision.py`, `ui/kollision_ui.py`, dock "Clashes", example). Then: stack-up stage 2b (location tolerances of the end
faces, PDF report, chain in the project) and assembly connections with snapping, open DOF and DOF wiggle
(`kern/verbindung.py`, `ui/baugruppe_ui.py`, dock "Assembly", part positions in `ansicht3d.teil_lagen`). Last in the
cloud: scan check stage 2 (point clouds, 3-2-1 datum alignment, linear/angular dimensions, inspection PDF), tolerance
zones for linear and angular dimensions, 1D stack-up finalised (Ⓜ/Ⓛ bonus, datum shift, edges, mean offset/Cpk,
requirement with Cp/Cpk/share outside), STEP PMI writing research (PLAN §8.28: dimensions/datums work with AP242 set
after creating the writer; geometric tolerances need an own P21 writer), `werkzeuge/tests_betroffen.py` (PLAN §8.29). Then:
tolerances on the connections (clearance from geometry/PMI, editable), worst-case position scatter per part via
linear programs (scipy `linprog`, lazily imported), wiggle within the tolerances; plainer tab close buttons (SVG
written to `<temp>/3DGmax-symbole` by `ui/thema.py`) and a right-click menu on the tab bars to show hidden panels.
Semantic GD&T writing (corrected 2026-10-27, PLAN §8.28): dimensions and datums can be written with pythonocc once
the schema is set to AP242 after creating the writer (the old segfault came from AP214 mode); geometric tolerances
cannot (XCAFDoc_GeomTolerance is an empty class in pythonocc 8.0.1) – plan: own P21 post-processing for them – PMI test variants are therefore text edits of the
public-domain NIST STEP files.

**Visual check in the cloud:** Xvfb + Mesa are available (`xvfb-run -a -s "-screen 0 1600x1000x24" ...`, then
`View.Dump`), so real 3D renders were checked for PRC (model, markups, edges), QIF graphics, generated PMI, section
planes and the view cube, and `DG_BILDSCHIRM=1 pytest tests/test_bildschirm.py` ran under Xvfb.

**Still to check on the real screen (Mac):**
- Font and glyph appearance of AIS_TextLabel texts (Mesa uses other fonts), MSAA and line widths on a real GPU.
- Capping with chained section planes on thin parts.
- Contrast of the 1 px model edges on PRC files with grey face colors.
- Tolerance zones stage 2: colors/transparency of zone, bonus, surface space and general tolerances; "all zones" on
  large models (FTC-10: many profile zones overlap) – maybe needs filtering by characteristic.
- Portable apps: the user confirmed Windows, macOS and Linux builds work. New since then: start screen
  (PyInstaller splash from `packaging/startbild.png` on Windows/Linux before Python loads, then a Qt splash
  `programm.app.startbild`); verified with a local Linux build under Xvfb (splash at 0.3 s, window at ~1.5 s).
  Check on Windows (first start with Defender) and macOS (Qt splash only; Gatekeeper delay before it remains).

**Not verified without local data (`daten/`):** the five NIST STC PDFs were downloaded from nist.gov in the cloud
(all load); QIF tests download the NIST QIF from qif-community; NIST AP242 set, D2MI and MTC were not available.

**Findings:**
- PRC: the public ISO working draft N570 (docs.techsoft3d.com, SC2N570-PRC-WD.pdf) is the usable spec; some type
  numbers in it are wrong (TESS = 170, MISC numbering as in Asymptote). NIST STC files: authoring version 20225,
  schema token 39 (one argument) before the blocks, schema of type 2 applies right after the graphics of every
  PRCBaseWithGraphics, MarkupLinkedItem has an extra bit before the product occurrence reference, annotation planes
  carry 6 undocumented bits (the reader searches for the default parameterization like the Asymptote reader).
  Geometry section empty (no B-rep), tessellation is regular TESS_3D, unit inch. Markup text is stroked glyphs, not
  strings; semantic PMI may sit in the large user data block of the tessellation section.
- QIF camera quaternion is stored w x y z; matrix rows are the camera axes (checked against STEP MBD_0 of CTC-01).
- Rigid fits for rotated features must be checked against the surfaces: corner nodes of planar faces admit
  symmetric wrong fits; point-to-surface ICP plus mesh distance in both directions solves it.

**Next local steps (handoff 2026-10-27 evening: finish these, then start JT):**
1. `git pull`, `pixi install`; run the affected tests only (`pixi run test-betroffen -- --seit 696df83`) or the full
   suite once (`pixi run test`, ~25 min); delete branch `claude/inspiring-wright-dqsu4q` (local and GitHub).
2. Finish the test strategy (PLAN §8.29): measure durations (`pixi run python -m pytest -q --durations=40`), add the
   `langsam` marker in `tests/conftest.py` and `pixi run test-schnell`; speed up the slowest tests (session fixtures
   for loaded models/comparisons, smaller scan samples). A duration run was started in the cloud but stopped.
3. Assembly variation (PLAN §8.20 open, task "assembly measures"): measures between parts (gap/flush between two
   picked faces) with worst case (linear programs over all connections, as `Baugruppe.streuung`) and Monte Carlo
   (sample the clearances per connection), contributor ranking (share per connection), PDF; further connection types
   (point/line contact, pin–slot, 3-2-1 template); chains across parts from the connections.
4. UI/UX review and `docs/UI_UX_Plan.md` (PLAN §8.30): personas (CATIA designers, 3DCS users, metrology staff,
   laypeople/students), task walkthroughs, alternatives (workspaces, ribbon, inspector + command palette, wizards),
   recommendation and staged plan with usability test – then implement stage 1.
5. Visual check on the Mac of everything since the last local check (see "Still to check on the real screen" and the
   list in "Next" item 1).
6. Then step 7: JT via TKJT (GPL v2+, build option; free JT without PMI: `NIST mtc crada assembly.jt` in
   `daten/nist_cad_dl/nist-cad-models-mtc-assembly.zip`).

## Check against plan / roadmap
| Step (PLAN.md §5) | Status |
|---|---|
| 1 Feasibility | ✅ |
| 2 Viewer | ✅ incl. view cube, quick measure, model properties, camera history, perspective, exploded view (staged by assembly levels), section box, up to three section planes, thumbnails (open: LOD for large assemblies, explosion along axes, hatched section views) |
| 3 Measure | ✅ incl. analyses (draft, curvature, wall thickness), measurement report, tolerance zones, tolerance stack-up 1D, comments, create PMI with advisor |
| 4 Compare | ✅ incl. manual alignment, deviation color map, material + / −, moved geometry/PMI, assembly comparison, graphical PMI changes, graphical-only notes, rotated/mirrored elements, per-instance geometry and status colors (open: change list per instance) |
| 5 Output | ✅ PDF per view, comparison PDF, PMI change PDF, bill of characteristics, measurement report, drawings (HLR, PDF/SVG/DXF with PMI; meshes too), section contour SVG/DXF/PDF, generated PMI stage 2, project container (incl. own views), folder comparison |
| 6 Formats | 🟡 STEP, STEPZ, IGES, STL, OBJ, glTF/GLB, 3MF, PLY, QIF 3.0 (B-rep, semantic + graphical PMI, views), PRC/3D PDF (mesh with edges, markups, views; graphical-only PMI evaluated) done; open: STEP-XML, PRC B-rep/compressed tessellation, U3D, point clouds |
| 7 JT via TKJT | ⬜ (free JT without PMI: `NIST mtc crada assembly.jt` in daten/nist_cad_dl/nist-cad-models-mtc-assembly.zip) |
Details: `docs/Roadmap.md`; future topics: PLAN.md §8 (8.5 tolerance zones, 8.6 annotating, 8.8 stack-up,
8.10 PMI editing/advisor, 8.11 CATIA, 8.15 PRC/3D PDF, 8.16 generated PMI, 8.17 open formats, 8.18 PMI as semantics or
graphics only, 8.19 QIF graphics, 8.20 3D tolerance analysis,
8.21 clash/band/intersection analysis, 8.22 plausibility check, 8.23 scan against PMI tolerances).

## Next (in this order)
1. Visual check on the Mac (see "Visual check on the real screen still open" and: wireframe contrast edges, view cube,
   start screen, side-panel dragging, tab ✕ and right-click menu on tabs, File › Examples, stack-up window and PDF,
   clash dock, assembly dock, scan check with point cloud and 3-2-1 alignment, zones for linear/angular dimensions).
2. Step 7: JT via TKJT (GPL v2+ build option; free JT without PMI: `NIST mtc crada assembly.jt` in
   `daten/nist_cad_dl/nist-cad-models-mtc-assembly.zip`) – started next in this session.
3. Remaining plan items (assembly dock requests 2026-10-28: connection reversal, DOF dragger, wiggle play/pause, zones at
   the assembled position and per instance; UI/UX stage 1 item 4–5 (play/pause toggles, UI scaling), stage 2
   workspaces; comparison modes stage 2 (tree status colours); stack-up stage 4 and 3D arrows/wiggle; then the
   roadmap ⬜ items in order).
4. Later: own P21 writer for geometric tolerances (§8.28) or QIF export; clash rest; several windows (§8.26); scan rest;
   plausibility stage 2; gear analysis (§8.27); hatched section views; STEP-XML (§8.17); PRC compressed
   tessellation/B-rep.

## Environment and commands
```bash
pixi install                      # Python 3.14, pythonocc-core 8.0.1 (no VTK), PySide6 6.11 (conda), PyInstaller
pixi run start                    # application
pixi run test                     # offscreen tests (~3 min); CI: pixi run test-ci
DG_BILDSCHIRM=1 pixi run python -m pytest -q tests/test_bildschirm.py   # real 3D view (Mac)
pixi run python werkzeuge/testmodelle.py          # CTC-01 variants (tests/daten/varianten)
pixi run python werkzeuge/baugruppe.py            # test assembly A/B (tests/daten/baugruppe*.stp)
pixi run python werkzeuge/formate.py              # IGES/STL/OBJ/glTF/GLB/3MF from the test assembly
pixi run python werkzeuge/tr_texte.py             # all tr() texts (completeness test uses it)
packaging/build_mac.sh [--ohne-tests]             # tests, build, self-test, 3D image
```

## Test data
- In the repo: tests/daten (NIST CTC-01, FTC-07, FTC-10, variants, test assembly, formats).
- Local only (`daten/`, git-ignored): NIST AP242 set (daten/nist), D2MI 904/906 (daten/nist_d2mi), NIST CAD archives
  (daten/nist_cad_dl: STC v4 PDFs contain PRC streams; MTC assembly contains a JT), QIF 3.0 of six NIST models
  (daten/qif, from github.com/QualityInformationFramework/qif-community – licence not stated, therefore not in the repo;
  the QIF test skips without them).

Latest additions: PMI edit/delete (✎, project overrides `pmi_aenderungen`), smooth camera transitions
(`_mit_fahrt`), ISO 14405 modifiers in dimension text, color map over all instances, PLY reader, notes compared by
text, part numbers in the parts list, geometry/standard check rules (`pmi_bericht._norm_regeln`), exploded view staged by assembly levels (`kern/explosion.py`).

## Module map (new this session)
kern: norm (ASME/ISO), merkmale (bill of characteristics), iso286, abweichung (color map + Skala), analyse,
eigenschaften, schnellinfo, stueckliste, vergleich_volumen (material), vergleich_baugruppe, qif, zeichnung (HLR),
pmi_erzeugen (generated PMI), kommentare, toleranzzone, toleranzkette, pmi_vorschlag (tolerancing advisor).
ui: eigenschaften_ui, stueckliste_ui, analyse_ui, kommentar_ui, toleranzkette_ui, pmi_anlegen_ui;
laden.lade_modell dispatches formats.
Cloud 2026-10-27: kern prc, prc_bits, prc_tabelle (PRC/3D PDF), qif_grafik (QIF graphics/views), schnitt (section
contours); zeichnung.projiziere_netz (mesh drawings); vergleich.starre_lagen/_starr_gleich (rotated/mirrored);
vergleich_geo._instanzen (per instance); tests/test_prc.py, tests/conftest.testdatei (downloaded test files).

## Findings (not obvious)
- OCCT viewer on macOS uses logical points; 2D/transform-persistent objects (view cube, color scale, pivot cross)
  are drawn in device pixels → sizes scaled by devicePixelRatio, cube picking maps coordinates (`_wuerfel_unter_maus`).
- Faces with custom color draw no boundaries → edges as own layer; context default face boundaries switched off.
- `ctx.MainSelector()` unusable in pythonocc → point under the mouse via view ray; meshes via `_netz_treffer`.
- AIS_Triangulation only accepts display mode 0; vertex colors are RGBA bytes as signed int32.
  AIS_ColorScale needs its own Prs3d_TextAspect (TextAspect() is None). `Font` enums not wrapped.
- Mesh faces (STL/OBJ/glTF/3MF) have no surface: every BRepAdaptor_Surface/BRep_Tool.Surface use is guarded.
- Nested assemblies: child placement must be composed with the parent (kern/baum.py `lage`).
- Booleans need small tolerances: tests/daten/varianten/ctc01_geo.stp has 0.5 mm edge tolerances (text edit) →
  material comparison sees nothing there; real revision pairs (D2MI) work.
- Auto alignment keeps identity when ≥ 50 % of the points already coincide (otherwise best fit skews changed models).
- QIF: Segment13 uses a sub-domain of its start/end points; loops may be oriented against the surface → faces are
  rebuilt with reversed wires (`qif._gut`); face ids are kept through sewing via `Modified()`.
- GD&T glyphs: Helvetica has none → `ansicht3d.pmi_schrift()` picks a font with coverage (Apple Symbols on macOS).
- Offscreen rendering crashes on macOS → tests use a placeholder view, real 3D test separate.
- Saved table column state key includes the column count and a version suffix.

## Cloud session prompt (licence-safe work packages)
Copy into a new cloud session (Linux, no screen, no local `daten/`):

```text
You continue 3DGmax (github.com/maxwxyz/3DGmax, public, GPL). Read CLAUDE.md, HANDOFF.md, PLAN.md and docs/Roadmap.md
first and follow their rules (German UI via tr(), English repo docs and commits, German code comments without
umlauts, changelog DE/EN, tests green before every commit, push after every commit, update HANDOFF.md incl. plan and
roadmap check). Environment: `pixi install`, tests with `QT_QPA_PLATFORM=offscreen pixi run test`. There is no screen:
verify visuals with tests and SVG/PDF output only. Never mention employers or internal terms. Do not copy code from
other projects; implement from public specifications. Do not commit third-party test files without a clear licence –
download them at test time or skip the test when they are missing.

Work packages, in this order (each: implement, test, changelog, roadmap, commit, push):
1. PRC reader stage 1–2 (PLAN §8.15): extract PRC streams from 3D PDFs (pypdf), parse the PRC file structure, bit
   reader and sections, read the product tree and tessellations into mesh faces (kern/prc.py, laden.lade_modell for
   .prc and .pdf). The archived Adobe spec lacks the bit/double encoding pages (see PLAN §8.15): use ISO 14739-1 if
   available, otherwise the LGPL PRC writer of Asymptote as encoding reference (LGPL is GPL-compatible; credit it in
   the file header and README). Test data: NIST STC v4 PDFs from nist.gov (US government work, public domain)
   downloaded in a test fixture, skip if offline.
2. Generated graphical PMI stage 2 (PLAN §8.16, kern/pmi_erzeugen.py): annotation planes from saved views or face
   normals, feature control frames and datum symbols as vector line graphics (Grafik.linien), overlap-free layout;
   used in 3D, drawings (kern/zeichnung.py) and reports.
3. Comparison: rotated and mirrored element detection (kern/vergleich.py `_verschiebungen`), geometry comparison per
   part instance for assemblies (StepModell.flaechen deduplicates instances – add per-instance sampling).
4. QIF graphical PMI and saved views (kern/qif.py: PMIDisplaySet polylines/text, ViewSet cameras → Ansicht objects).
   QIF test files: download NIST QIF samples from github.com/QualityInformationFramework/qif-community at test time.
5. Multiple section planes (2–3 planes combined) and section contour export to DXF/SVG (kern/zeichnung.py).
Not for the cloud: JT/TKJT build (step 7), CATIA formats (licence review), visual UI polish (needs a screen).

Work on `main` (commit and push after every finished package; unfinished work on a `wip/...` branch). When you stop
(all packages done or usage almost used up), hand back to the local Mac session: rewrite the section
"Return handoff from the cloud" at the top of HANDOFF.md with: packages done (commit hashes), what is unfinished and
on which branch, what could not be verified without a screen or without local data (daten/), new findings, and the
recommended next local steps (always including a visual check on the real screen). Update the plan/roadmap check
table, then commit and push. Do not bump the version.
```

## After the cloud (local Mac)
1. `git pull`, read "Return handoff from the cloud", run `pixi install` and `pixi run test`.
2. Visual check on the real screen: view cube, MSAA, explosion levels, everything the cloud marked as unverified
   (generated PMI, section planes, QIF graphics).
3. Tests with local data (`daten/`: NIST AP242, D2MI, QIF, STC PDFs with PRC).
4. Then: step 7 JT via TKJT, local build `packaging/build_mac.sh`.
