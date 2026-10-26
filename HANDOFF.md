# Handoff (2026-10-26)

Branch: `main` (no other branches). Version 0.1 plus many unreleased entries in `programm/CHANGELOG.json`
(bump only via `pixi run python packaging/release.py minor --git`, then `git push --follow-tags`).
Tests: 111 offscreen + on-screen test green; GitHub workflow "Apps bauen" green on Windows/Linux/macOS.

## Check against plan / roadmap
| Step (PLAN.md §5) | Status |
|---|---|
| 1 Feasibility | ✅ |
| 2 Viewer | ✅ incl. view cube, quick measure, model properties, camera history, perspective, exploded view, section box, thumbnails (open: LOD for large assemblies, multiple section planes) |
| 3 Measure | ✅ incl. analyses (draft, curvature, wall thickness), measurement report, tolerance zones, tolerance stack-up 1D, comments, create PMI with advisor |
| 4 Compare | ✅ incl. manual alignment, deviation color map, material + / −, moved geometry/PMI, assembly comparison, graphical PMI changes (open: rotated elements, per-instance geometry, graphical-only notes) |
| 5 Output | ✅ PDF per view, comparison PDF, PMI change PDF, bill of characteristics, measurement report, drawings (HLR, PDF/SVG/DXF with PMI), project container (incl. own views), folder comparison |
| 6 Formats | 🟡 STEP, IGES, STL, OBJ, glTF/GLB, 3MF, PLY, QIF 3.0 (B-rep + semantic PMI) done; open: PRC/3D PDF (§8.15), QIF graphics/views, point clouds |
| 7 JT via TKJT | ⬜ (free JT without PMI: `NIST mtc crada assembly.jt` in daten/nist_cad_dl/nist-cad-models-mtc-assembly.zip) |
Details: `docs/Roadmap.md`; future topics: PLAN.md §8 (8.5 tolerance zones, 8.6 annotating, 8.8 stack-up,
8.10 PMI editing/advisor, 8.11 CATIA, 8.15 PRC/3D PDF, 8.16 generated PMI stage 2).

## Next (in this order)
1. PRC / 3D PDF reader (PLAN §8.15): extract PRC from PDF, structure + tessellation → mesh, then markups, then B-rep.
2. Generated graphical PMI stage 2 (PLAN §8.16): annotation planes, frames/datum symbols as vectors, better layout.
3. QIF: graphical PMI (PMIDisplaySet) and saved views (ViewSet).
4. Comparison: rotated/mirrored elements, geometry per part instance (StepModell.flaechen deduplicates instances).
5. Step 7 JT via TKJT (GPL v2+, build option).
**Not checked on a real screen** (screen was locked, checks via `View.Dump`): view cube look, MSAA – first thing
on the Mac.

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
text, part numbers in the parts list, geometry/standard check rules (`pmi_bericht._norm_regeln`).

## Module map (new this session)
kern: norm (ASME/ISO), merkmale (bill of characteristics), iso286, abweichung (color map + Skala), analyse,
eigenschaften, schnellinfo, stueckliste, vergleich_volumen (material), vergleich_baugruppe, qif, zeichnung (HLR),
pmi_erzeugen (generated PMI), kommentare, toleranzzone, toleranzkette, pmi_vorschlag (tolerancing advisor).
ui: eigenschaften_ui, stueckliste_ui, analyse_ui, kommentar_ui, toleranzkette_ui, pmi_anlegen_ui;
laden.lade_modell dispatches formats.

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
```
