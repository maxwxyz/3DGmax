# 3DGmax – Plan

3D PMI viewer and comparison tool for Model Based Definition (MBD). This document records the market overview,
technical decisions (with what was verified by experiment), architecture, steps with acceptance criteria and risks.
Feature status: **[docs/Roadmap.md](docs/Roadmap.md)**. UI/UX principles: **[docs/UIUX.md](docs/UIUX.md)**.
Feasibility results: **[docs/Feasibility.md](docs/Feasibility.md)**.

Markers: **[verified]** = checked ourselves (package index, vendor page, experiment), **[knowledge]** = from domain
knowledge, not yet confirmed by experiment, **[open]** = still to be clarified.

---

## 1. Similar applications (research)

| Application | What it does | Relevance |
|---|---|---|
| **Kisters 3DViewStation** (commercial) | Reads PMI from CATIA, Creo, NX, JT, STEP; saved PMI views; **since v2024.0 revision comparison with PMI changes (colored)**, quick and exact [verified] | Closest competitor, similar scope. Benchmark for usability. |
| **Kubotek K-Compare** (commercial) | Revision comparison of parts/assemblies, result tree with face highlighting, reads AP242 PMI [verified]; semantic PMI diff not clearly documented | Model for result tree and face coloring. |
| **CoreTechnologie 3D_Evolution** (commercial) | Converts and **compares PMI original ↔ converted**, checks whether PMI is semantic or graphical only [verified] | Original/converted rather than two revisions; we adopt the "semantic or graphical only" flag per PMI. |
| **TransMagic MagicCheck** (commercial) | Geometry comparison with color map by tolerance, point list with values [verified, sources 2012/13] | Model for deviation color map + point browser. |
| **Capvidia MBDVidia / CompareVidia** (commercial) | MBD validation, QIF generation, model comparison [knowledge] | Reference for the QIF path. |
| **CATIA Compare Products** (commercial) | Visual (fast) and geometric (accurate) comparison, added/removed material as 3D map, adjustable accuracy [verified] | Model for exact vs. approximate comparison display. |
| **NIST STEP File Analyzer and Viewer** (free) | Shows graphical PMI, analyzes **semantic PMI** against CAx-IF recommended practices [verified] | **Our reference**: what we read from NIST models is checked against its report. |
| **ODA Open STEP Viewer** (free, closed source) | AP242 ed.3, measuring, clash, PMI display [verified] | Cross-check for display questions. |
| **Siemens JT2Go** (free) | View JT with PMI [knowledge]; comparison only in paid Teamcenter Visualization | Cross-check for JT. |

**Conclusion:** free viewers show PMI, but **none compares two revisions semantically** and guides through a review
with a report. Commercially, essentially only 3DViewStation does. That is where 3DGmax adds value: semantic PMI
comparison + review walk-through + report, like ZGmax does for 2D drawings.

## 2. Technical decisions

### 2.1 Language and UI – confirmed
**Python 3.14 + PySide6** as in ZGmax: same toolchain (offscreen tests, PyInstaller, `tr()`, handoff), reusable parts
(review walk-through, report with SHA-256, changelog/version, manual with menu reference).

### 2.2 Geometry kernel – **pythonocc-core via pixi** (changed after the step 1 experiment)
- First proposal was OCP (`cadquery-ocp`, pip wheels). Experiment: OCP 8.0.1 cannot look up STEP entities from
  Python (hash lookups fail) and lacks `TransferBRep` → no mapping STEP face ↔ OCCT face [verified].
- pythonocc-core 8.0.1.2 (conda-forge) maps all faces [verified]; environment via **pixi**, variant **without VTK**
  (`build = "novtk*"`), because the VTK variant pulls Qt from conda-forge and clashes with PySide6 DLLs on Windows.
- Licenses: OCCT LGPL 2.1 with exception, pythonocc LGPL 3, PySide6 LGPL 3, numpy/scipy BSD.

### 2.3 PMI: own STEP reader, OCCT for cross-checking [verified]
- OCCT/XCAF reads much semantic PMI, but: pythonocc does not wrap `XCAFDoc_GeomTolerance`; face links via
  `SET_REPRESENTATION_ITEM` are lost; some dimensions/fits are missing; one inch limit dimension is read wrongly.
- Therefore 3DGmax reads semantics, presentation (graphical PMI), saved views and colors from the STEP entity graph
  itself (`programm/kern/p21.py` and following). Result on all NIST AP242 models: 266/266 dimensions,
  362/362 tolerances, 114/114 datums.

### 2.4 Display – **OCCT viewer (AIS/V3d) in a Qt widget**
Exact B-rep picking, snapping, clip planes with capping, no VTK. Findings: logical points on macOS; faces with custom
color draw no boundaries (edges as separate layer); offscreen rendering crashes on macOS (tests use a placeholder view).

### 2.5 Other libraries
numpy, scipy (KD tree, ICP), pypdf (3D streams from PDF, BSD), lxml (QIF), pytest.

## 3. Formats – feasibility and effort

| Format | Approach | Geometry | PMI | Effort | Cost |
|---|---|---|---|---|---|
| STEP AP242 / AP214 / AP203 | OCCT + own entity reader | yes | semantic + graphical | done | 0 |
| IGES, STL, OBJ, glTF/GLB | OCCT readers (present in pythonocc) **[done]** | yes | – | small | 0 |
| 3MF | own reader (ZIP + XML) **[done]** | mesh | – | small | 0 |
| **QIF** | lxml, own B-rep builder (kern/qif.py) **[done: B-rep + semantic PMI; graphics and views in kern/qif_grafik.py]**; test files: NIST models from github.com/QualityInformationFramework/qif-community (licence not stated – kept local in daten/qif) | QIF B-rep | **semantic, clean** | medium | 0 |
| **JT** – mesh | own reader per ISO 14306 | mesh | – | large (weeks) | 0 |
| **JT** – TKJT (as used by FreeCAD) | TKJT by Open Cascade (2013–2015), maintained at github.com/mmaenz/TKJT (OCCT 7.7, compiled on Mac, untested); own Python binding | mesh, structure, attributes; PMI part present, scope [open] | [open] | medium–large | 0, but **GPL v2+** [verified] |
| **JT** – commercial SDK | Siemens JT Open Toolkit, Open Cascade JT SDK, CAD Exchanger, HOOPS Exchange | yes | yes | medium | quote only |
| **3D PDF U3D** | extract stream with pypdf, read U3D (ECMA-363) | mesh | views only | medium | 0 |
| **3D PDF PRC** | own reader (kern/prc.py) per the public ISO working draft N570, see §8.15 **[done: tessellation, markups, views]** | tessellation (B-rep open) | graphical markups (semantic open) | large | 0 |
| **STEPZ** | ZIP/gzip around a Part 21 file, unpack and load **[done]** | as STEP | as STEP | small | 0 |
| **STEP-XML** (ISO 10303-28) | own reader mapping the XML entity graph onto the Part 21 model (p21.py), then the STEP path | as STEP | as STEP | medium–large | 0 |

## 4. Architecture

```
programm/
  kern/                 no Qt, fully testable
    p21.py              STEP Part 21 entity graph reader
    laden.py            STEP -> XCAF document, face index, STEP #ID <-> face
    pmi.py              neutral PMI model + text rendering (symbols, frames)
    pmi_step.py         dimensions and tolerances from STEP
    pmi_lesen.py        PMI list, datums, datum targets, notes, XCAF cross-check
    ansichten.py        saved views (camera, window, PMI per view)
    praesentation.py    graphical PMI (polylines, triangles, placeholders, file color)
    baum.py, farben.py  assembly tree, face colors
    messen.py           distance, angle, radius, wall thickness, coordinates, snapping
    ausrichten.py       best fit (PCA start, ICP, point-to-plane), three point pairs
    vergleich_geo.py    face status (equal/changed/new/removed), exact B-rep distance with mesh preselection
    vergleich_pmi.py    semantic PMI diff (field by field, faces via face mapping)
    vergleich.py        orchestration, change list
    pruefung.py         review report with SHA-256
    pmi_bericht.py      PMI table (CSV), plausibility check, change export
  ui/                   PySide6: main window, 3D view, navigation (CATIA/classic), panels, measuring, comparison
tests/  packaging/  werkzeuge/  docs/
```

## 5. Steps with acceptance

| # | Content | Acceptance | Status |
|---|---|---|---|
| **1 Feasibility** | load NIST AP242, list PMI and views, cross-check, viewer experiment, JT/3D PDF assessment | `docs/Feasibility.md` | ✅ |
| **2 Viewer** | loading, tree, CAD navigation, display modes, light/dark, saved views, PMI list, PMI↔face, section, intro, translation, F1 manual | NIST FTC usable, views switch PMI correctly | ✅ |
| **3 Measure** | distance/angle/radius/wall thickness/coordinates with snapping, list, CSV | values match NIST dimensions | ✅ |
| **4 Compare** | alignment, face status, PMI diff, change list, review walk-through, report | modified NIST variants: all changes found, no false alarms | ✅ (extensions see §8.1) |
| **5 Output** | PDF per saved view, comparison report with images, PMI change table PDF/CSV, project container, folder comparison, views as drawings (HLR) | report understandable for a supplier | ⬜ next |
| **6 Formats** | QIF, IGES/STL/OBJ/glTF/3MF, 3D PDF | one test file per format | 🟡 (QIF incl. graphics/views, meshes, IGES, 3D PDF/PRC, STEPZ done; STEP-XML open) |
| **7 JT via TKJT** | build TKJT for OCCT 8, Python binding, load JT; build with/without TKJT (open source only on GitHub) | JT file like its STEP counterpart | ⬜ |
| later | multiple section planes, clipping box, section views from the model | section looks like in CAD | 🟡 (clipping box, up to three planes, contour export done; hatched section views open) |

Throughout: tests (core, offscreen UI, stress test, on-screen test), `--selbsttest`, changelog DE/EN via
`packaging/release.py`, HANDOFF.md, unfinished work on `wip/...`, push after each commit.

## 6. Risks

1. **Real exports differ from NIST** (CATIA/NX/Creo write PMI differently) – put own anonymized models into tests early.
2. **Face matching with heavy redesigns** (faces split/merged) – reported as *changed* via deviation, not mismatched.
3. **Large assemblies** – background tessellation, cache, levels of detail, tessellate instances once.
4. **JT with PMI** only via TKJT (GPL) or commercial SDK.

## 7. Decisions

- Geometry kernel: pythonocc via pixi (decided after experiment).
- Display: OCCT viewer.
- License: **GPL-3.0-or-later** – compatible with OCCT/pythonocc/PySide6 (LGPL) and TKJT (GPL v2+).
- JT: TKJT as optional build variant after STEP; GitHub builds open-source-only by default.

## 8. Extensions

### 8.1 Comparison
- Exact **and** approximate (fast) like CATIA Compare Products: added/removed material as volume, adjustable accuracy;
  deviation color map with scale and sign.
- Detect **moved** elements (face/feature rigidly offset) and moved PMI placement.
- **Done (2026-10-27):** rotated and mirrored elements (`vergleich._starr_gleich`: PCA start with all eight axis
  sign combinations, point-to-surface ICP that keeps handedness, confirmed by mesh distance both ways; reported as
  angle/axis or mirror plane, status "moved"); per-instance comparison (`vergleich_geo._instanzen`: every located
  face is sampled, results are folded onto the shared face index). Per-instance status colors in the 3D view done
  (`GeoErgebnis.instanzen_b`, key = face index + rounded location; `entfernt_a` holds removed located faces).
  Open: change list entries per instance.
- **Graphical PMI comparison** in addition to semantic: match annotations (position, shape), color moved/changed/
  new/removed in the 3D view.
- Assembly comparison; manual alignment by point pairs in the UI.
- Meshes: STL/OBJ vs. CAD, mesh vs. mesh, fit and compare 3D scans (best fit, datum/RPS based).

### 8.2 Saved views and search
- Thumbnails per view; targeted search (`datum:A`, `value:0.5`, `type:position`).

### 8.3 Build variants by license
- **Default (open source, LGPL libraries)** – distributable. **With TKJT (GPL v2+)** – adds JT reading; distribution
  under GPL-compatible terms with source (fits GPL-3.0-or-later). Switch in build scripts and workflow with step 7.

### 8.4 Make graphical PMI usable
- Searchable: render annotations offscreen, text recognition (OCR as in ZGmax), map text to the annotation.
- Convert to semantic PMI: evaluate recognized text + frame structure; mark result as "derived (check)", never as
  genuine semantics.

### 8.5 Tolerance zones (stage 1 done: offsets ±t/2, ⌀ zone cylinders, exaggeration; open: datum-oriented, UZ, projected)
- Generate envelope surfaces for roundness, cylindricity, coaxiality, position, surface/line profile etc. showing how far
  geometry may deviate from nominal – including datum reference frame, material condition, unequal zones (UZ),
  projected zones.

### 8.6 Annotating and commenting (done: comments on faces/PMI with markers, status, project, CSV/PDF)
- Comments/change proposals on faces, edges, PMI (list and model), on changed PMI and geometry in a comparison; stored
  in the project container, exported in reports.

### 8.7 Reports
- PDF per saved view: one page per view with view name, model name, date, visible PMI (image + list); plus comparison
  report and PMI change table (step 5).

### 8.8 Tolerance stack-up analysis (stage 1 done: 1D chain from PMI dimensions, worst case, RSS, Monte Carlo)
- Dimension chains built from the semantic PMI (select faces/PMI along a chain), worst case, statistical (RSS) and
  Monte Carlo; GD&T contributions (position, profile, datum shift with material condition); report with contributors.
- Related: bill of characteristics with balloon numbers for metrology/quality.

### 8.9 Test data
- NIST: FTC/STC/CTC (AP242); D2MI 827-9999-904 rev C (AP242 with PMI) ↔ 906 (same geometry, no PMI); FTC-06 ↔ STC-06
  (same part, simplified PMI, different position). Own variants: `werkzeuge/testmodelle.py`.
- **JT with PMI: no freely available files found** (NIST publishes STEP and native CAD only; JT2Go samples are under
  the Siemens license). Option: export JT of the NIST models from a CAD system.

### 8.10 Create and edit PMI (stage 1 done: advisor suggestions, own PMI in project; open: edit, STEP write-back)
- Edit existing PMI and create new PMI on existing models (semantic, linked to faces), write back to STEP AP242.
- **Tolerancing advisor:** contextual suggestions based on the selection (e.g. hole pattern → position with ⌀ zone and
  Ⓜ, planar datum face → flatness, mating cylinder → fit), checking consistency with the datum reference frame and
  the plausibility rules (§ PMI check).

### 8.11 Open CATIA V5/V6 files (CATPart, CATProduct) – feasibility only
- Native CATIA formats are proprietary and undocumented. No free, legally safe reader exists; reverse engineering
  could violate license terms. Legal options to evaluate: licensed SDKs that include CATIA readers (e.g. CAD Exchanger,
  HOOPS Exchange, Spatial 3D InterOp) with their costs and redistribution terms, or reading the lightweight
  representations CATIA exports (STEP AP242, JT, 3DXML). Decision only after cost/license review.

### 8.12 Essential viewer functions – gap analysis against common viewers
Compared with JT2Go, F3D, ODA/other STEP viewers, Kisters 3DViewStation, Teamcenter Visualization, Fusion and
Onshape [knowledge], 3DGmax was missing these everyday functions for engineers (viewing, measuring, reading PMI).
UI rule: no extra panels – information appears where the eye already is (status bar, tooltip, context menu).

**Now (implemented next):**
1. **Selection info / quick measure** in the status bar (right), live for the current selection, items can be
   switched off by right-click:
   - one edge: length; line → length; closed circle → ⌀, circumference; arc → R, angle, arc length
   - one face: type and area; cylinder → ⌀ (closed) or R (open) and axis; cone → half angle; sphere → ⌀;
     torus → radii
   - one vertex: coordinates
   - two elements: minimum distance; planes → angle (parallel planes: distance); cylinders/axes → axis distance
     and angle; point–plane/point–axis distance
   - selected PMI: kind, characteristic, value, limits (upper/lower), datums
2. **Model properties** (dialog, also for selected parts): volume, surface area, mass with adjustable density,
   center of gravity, overall size (bounding box L × W × H), counts (solids, faces), file header (schema,
   originating system, author, organization, date), length unit.
3. Visual polish: anti-aliasing, sans-serif labels (measurements, generated PMI texts), subtler view cube
   (transparent, opaque on hover, closed corners).

**Next:**
4. Camera: perspective/orthographic, previous/next camera (view undo), smooth transitions.
5. Hide selected in 3D, tree search/filter; 3D PMI follows the list filter (type, search).
6. Datum reference frame display for a selected tolerance (datum features highlighted A/B/C in color).
7. Bill of characteristics with balloon numbers (export, PDF) – see §8.7.
8. Exploded view and parts list (BOM with properties) for assemblies.
9. Analyses: draft angle, curvature, wall thickness map (color maps like the deviation map).
10. Limits from ISO 286 tolerance classes (exact tables).

### 8.13 ASME Y14.5 vs. ISO GPS – what depends on the standard
STEP AP242 uses the same semantic entities for both systems; the file rarely states which one applies (sometimes in
notes, e.g. "ISO 8015", "ASME Y14.5-2009"). Reading, listing, comparing and the deviation map are standard-neutral.
Standard-dependent are [knowledge]:
- **Size and form:** ASME Rule #1 (envelope by default) vs. ISO 8015 independence principle (envelope only with Ⓔ);
  ISO 14405 size modifiers (LP, LS, GG, GX, GN, CC …). Matters for tolerance zones (§8.5), stack-up (§8.8) and the
  advisor (§8.10).
- **Characteristics:** concentricity and symmetry were removed in ASME Y14.5-2018 but remain in ISO 1101; ISO zone
  modifiers (UZ, CZ, SZ, ACS, LE, NC, OZ) vs. ASME (U for unequal profile, "all around/all over").
- **Plausibility rules:** some rules differ (e.g. concentricity → ASME 2018 warns, ISO ok); rules get a standard flag.
- **Terms and symbols in the UI:** ISO terms (Flächenform, Lauf …) vs. ASME terms (profile of a surface, runout).
- **General tolerances:** ISO 2768 / ISO 22081 vs. title block tolerances – only as notes in STEP.
Plan: detect the standard from notes/modifiers, otherwise a per-model setting (ISO GPS / ASME, default from settings);
show it in model properties; standard-specific rules and terms switch with it.
Test data: the NIST test cases are ASME based (Y14.5-1994/2009); no free ISO GPS AP242 set is known. Options: own
ISO variants of the NIST models (built in a CAD system and exported), CAx-IF test models (members only), vendor samples.

### 8.14 Feedback round (done: column auto-fit, About/macOS roles, fixed pivot with cross, standard detection, bill of characteristics)
- Columns shown via the header menu are too narrow: fit them to their content automatically when shown.
- About dialog: drop the author line, the copyright is enough. On macOS the About entry belongs in the application
  menu (Qt `QAction.MenuRole.AboutRole`, likewise Preferences/Quit), not in Help.
- Rotation center set with the middle mouse button must stay where it is while zooming and panning (today zoom/pan
  move it unpredictably). Show it as a small line cross like CATIA while it is set.
- In progress when paused: standard detection ASME/ISO (fallback **ISO GPS**; NIST files carry hints such as
  "ASME Y14.5M-1994 APPLIES" in notes, some only "asme1" in names) and bill of characteristics with balloon numbers
  (numbering, table column, CSV/PDF, balloons in 3D via AIS_TextLabel subtitle style at the callout position).

### 8.15 PRC and 3D PDF (requested; B-rep preferred, mesh as fallback)
- Test data found: the NIST STC 06–10 PDFs (nist-stc-pmi-v4.zip) each contain a PRC stream (`/Subtype /PRC`, e.g.
  STC_06: 4.4 MB, PRC version 7095) [verified: extracted with pypdf].
- No free PRC reader exists (Asymptote only writes PRC; HOOPS Exchange is commercial). Own reader per the published
  PRC specification (Adobe PRC Format Specification / ISO 14739-1):
  1. Extract PRC (and U3D) streams from 3D PDFs; PRC file structure, sections, zlib, bit reader, schema.
  2. Product tree and tessellation (`PRC_TYPE_TESS_3D`, also the highly compressed tessellation) → mesh display.
  3. Markups (PMI): tessellated leaders/texts as graphical PMI, views; semantic markups where present.
  4. Exact B-rep (NURBS, analytic surfaces, topology) → OCCT faces, so measuring and comparison use exact geometry.
- Effort: large (several weeks). Order: 1–2 first (mesh view of 3D PDFs), then 3, then 4.
- **Done (2026-10-27, stages 1–3 partly):** `kern/prc_bits.py` (bit reader, double coding verified against vectors
  from the Asymptote writer), `kern/prc_tabelle.py` (frequent-double/exponent table), `kern/prc.py` (file structure,
  schema interpreter, globals, tree with part definitions, product occurrences, markups, annotations, views,
  tessellation: TESS_3D faces, wires, markup codes with matrix blocks). All five NIST STC PDFs load (5–7 s each);
  STC-07 surface area matches the FTC-07 STEP within 0.15 %. Markups become graphical PMI (notes in the list),
  views carry camera and visible markups. Findings: the ISO draft has wrong type numbers (TESS = 170, not 230;
  MISC numbering as in Asymptote); MarkupLinkedItem has an extra bit before the optional product occurrence
  reference; the annotation plane (PRC_TYPE_SURF_Plane) carries 6 undocumented bits before the parameterization –
  the reader searches for the default parameterization like the Asymptote reader does; schema token 39 with one
  argument appears before the first block (not in the draft). NIST STC markup texts are stroked glyphs, not strings.
- **Edges done (2026-10-27):** TESS_3D wire indices per face (start_wire, sizes_wire with IsNotDrawn 0x4000 and
  IsClosing 0x8000, draft §7.8.6) become `StepModell.netz_kanten` (face index → polylines); the 3D view draws them in
  its edge layer as polygon wires (edges with only a Poly_Polygon3D are not drawn by OCCT). Display only – not
  selectable or measurable. The 19 polywires of STC-06 (RI_PolyWire) are sketch/construction lines, kept hidden.
- Open: highly compressed tessellation (PRC_TYPE_TESS_3D_Compressed, described in the draft §7.8.9), exact B-rep
  (geometry section; the NIST files have none), semantic PMI (may sit in user data), U3D streams.
- Specification status [verified 2026-10-26]: the Adobe "PRC Format Specification" (Acrobat 9 SDK) is only partly
  available as an archived HTML copy (web.archive.org, livedocs.adobe.com/.../PRC_Format_Specification/); the pages for
  the bit-level writing (WriteBits, unsigned integers, the double encoding table) and the compressed tessellation were
  not archived. Options: buy ISO 14739-1:2014, or use the LGPL PRC writer in Asymptote (prc/ directory) as a reference
  for the encodings – LGPL code may be used in this GPL project with attribution. Extracted test streams
  (STC_06–10.prc, PRC version 7095) are in daten/prc (local only). The Asymptote code covers writing (bit stream,
  unsigned/signed integers, the frequent-double table) but not reading the highly compressed tessellation that CAD
  exporters use; plan: port the bit/double decoding first, then probe which representation the NIST files carry.

### 8.16 Generate graphical PMI from semantic PMI (requested)
Files with semantic PMI but no presentation (or QIF/STEP from systems that drop the graphics) should still show and
print annotations. Today 3DGmax writes generated texts only into the placeholders the file provides. Plan:
1. Placement: annotation plane from the saved view (or the face normal), anchor at the toleranced feature (face
   centroid / axis end), text outside the model silhouette, avoid overlaps (simple greedy layout).
2. Content: dimension text (nominal, deviations, fit), feature control frame (symbol, zone, value, modifiers,
   datums) and datum feature symbols drawn as vector graphics (frames, triangles), leaders to the feature.
3. Use in 3D view, drawings (§ HLR export) and reports; mark as "generated" (different color) so it is never
   mistaken for the author's presentation.
- **Stage 2 done (2026-10-27):** `kern/pmi_erzeugen.py` – annotation plane from the saved view that shows the PMI,
  otherwise the principal model plane matching the face normal / axis (normal oriented to the iso viewer so text
  is not mirrored); frames with compartments (symbol, value with ⌀/Ⓜ/Ⓟ, datums), datum triangle + box, dimension
  text with a reference line; one text placeholder per compartment (`Platzhalter.text`); greedy placement outside
  the model box without overlapping other frames (3D boxes); menu switch "Show generated PMI display".
  Open (stage 3): dimension lines with arrows/extension lines, overlap check in the projected view, text glyphs as
  vectors for DXF.

### 8.17 More open formats (requested)
- STEPZ (`.stpz`, `.stepz`, `.stp.gz`): ZIP or gzip around a Part 21 file – unpack to a temporary file, load as STEP
  **[done]**.
- STEP-XML (ISO 10303-28, `.stpx`/`.stpxz`): XML representation of the same entity graph; plan: map the XML onto
  `p21.P21Datei` so the PMI, view and color readers work unchanged; geometry via OCCT after writing a temporary
  Part 21 file (OCCT has no Part 28 reader) [open: verify which AP242 XML schema variants exist in practice].
- Research 2026-10-27: "STEP AP242 XML" (.stpx) is the Business Object Model (ISO/TS 10303-3001, AP242 ed. 1) or
  the Domain Model (ISO 10303-4442, later editions) – mainly product structure/PDM with references to external
  geometry files, not a second encoding of the Part 21 geometry and PMI. XSDs: MBx-IF "XSD Schemas"; no free
  sample files found yet. Plan: read the assembly structure and follow external references to Part 21 files;
  needs sample files (MBx-IF test cases or a CAD export) before implementing.
- Others to review: JT (step 7), 3MF/glTF with PMI extensions, IFC (not CAD PMI) – decide by demand.

### 8.18 PMI available as semantics or graphics only (requested)
- Semantic-only PMI: shown as generated graphics in the view (stage 2 done, §8.16), switch in the View menu.
- Graphical-only PMI: evaluate them in the table – kind from the source (PRC markup type: dimension, GD&T, datum,
  note; STEP callout names), values from text where the file has strings (STEP placeholders, PRC text entities) and
  OCR for stroked text later (§8.4). Mark as "derived (check)", never as genuine semantics.
  **Done (2026-10-27):** `kern/pmi_ableiten.py` – text parser (frame symbol, ⌀/Ⓜ/Ⓛ, value, datums; limit, ±, +/-
  deviations, radius, angle; single datum letter) and PRC markup kind/name rules (NX stores datum symbols as GD&T);
  applied in `pmi_lesen.ergaenze_hinweise`; `quelle="abgeleitet"`, list shows "≈" and a tooltip. NIST STC PRC
  texts are strokes → kind only; QIF texts → full values. Open: OCR for stroked text.

### 8.19 QIF graphics and views (done 2026-10-27)
- `kern/qif_grafik.py`: PMIDisplay → Grafik in the annotation plane (AnnotationView normal + direction, plane origin
  and optional direction; 2D values scaled by the file unit). Texts with `{SYMBOL}` tokens mapped to Unicode and
  `{BR}` line breaks, rectangular/circular frames, leaders (plain, extended, double-headed, circular) with filled
  arrow/dot heads, witness lines, free polylines and triangle areas. Graphical-only notes keep their QIF id.
- SavedView → Ansicht: camera quaternion stored as w x y z, matrix rows are the camera axes (view = row 3,
  up = row 2) – verified against the saved view of the same NIST model in STEP; height × ratio as window.
- Test files: NIST QIF models from github.com/QualityInformationFramework/qif-community, downloaded in tests
  (`tests/conftest.testdatei`), never committed.

