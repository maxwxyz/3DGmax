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
- **Stage 2 (requested 2026-10-27):** derive the possible deviations from every geometric tolerance where it makes
  technical sense, and show them as zone geometry:
  - Coaxiality / concentricity / position with ⌀: zone cylinder (⌀ t) around the datum axis or the true position for
    the derived axis; in addition the space the feature surface may occupy (inner and outer envelope cylinders from
    size tolerance plus zone), so one sees where axis *and* surface can lie.
  - Profile of a surface / line: two offset surfaces ±t/2; unequal zone (ISO `UZ`, ASME Ⓤ) shifts the pair by the
    given offset; with datums the zone is fixed in location to the datum system, without datums only form.
  - Orientation (parallelism, perpendicularity, angularity): two planes / a cylinder oriented to the datum, free in
    location; runout (circular, total): zone around the datum axis.
  - Modifiers: Ⓜ/Ⓛ – zone at MMC and at LMC (bonus tolerance) and the virtual condition envelope; Ⓟ projected zone
    extended beyond the face by the projected length; Ⓔ envelope = maximum material boundary; Ⓕ, CZ/SZ, ACS/ALS
    as far as the zone geometry changes.
  - Size tolerances: maximum and minimum material envelopes (offsets to the limits).
  - Scope: the selected PMI, all PMI on the selected faces, or all PMI of the model at once (with a legend and per
    characteristic colors); optional exaggeration factor as today.
  - General tolerances as an option: ISO 2768-1 (f/m/c/v) and -2 (H/K/L), ISO 22081 general geometrical
    specification (profile tolerance to the datum system) – user picks the class (or it is read from the title
    block note), applied to faces without an explicit tolerance; shown in a distinct color and marked "general".
  - Reused by §8.20 (each zone bounds the small displacement torsor of its feature).
  - **Done (2026-10-27):** `kern/toleranzzone.py` – axes grouped per feature (patterns), zone cylinder, bonus zone
    with Ⓜ/Ⓛ (also zero tolerance at MMC/LMC), envelopes of the surface from size limits plus tolerance (virtual
    condition), projected zone placed on the open end (solid classifier), unequal zones, size envelopes, general
    tolerances ISO 2768-1/-2 and ISO 22081 (`Allgemein`, detected from notes), common exaggeration for "all"
    (median width). UI: View › "Show tolerance zone(s)", "Show all tolerance zones", "General tolerances …"; the
    part turns translucent while zones are shown. Interpretation of the STEP `unequally_disposed_geometric_tolerance`
    displacement is taken per standard (ISO: shift of the zone centre; ASME Ⓤ: amount outside the material) –
    **not verified against a sample file** (no test file with UZ). Also done: zone of the derived median plane
    (two opposed planes; symmetry and position always, orientation/straightness only on a feature of size = a
    dimension on exactly these faces), spherical zone for S⌀, hints for what the geometry does not show
    (orientation zone floating, form zone free, per cross-section, per unit length), context menus.
    Also done: coaxiality/concentricity and runout around the datum axis (`bezugsachse`), datum shift with Ⓜ/Ⓛ on
    a datum as an extra envelope (size tolerance of the datum feature; its own geometric tolerance ignored),
    hierarchy form < orientation < location (the higher-level zone on the same faces shown as envelope, with a
    contradiction hint when the lower one is not smaller).
    Open: line profile and circular runout per section (shown as surface band), ACS/ALS, CZ/SZ, tolerances on
    edges/points, datum shift including the datum's own position tolerance (virtual condition).

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
- 3D analysis of assemblies with materials, temperature and wiggle: see §8.20.
- Done 2026-10-27: process capability Cp adjustable for the chain (σ = T / (6·Cp)), angular dimensions excluded
  from length chains, chain cleared when another model is loaded.
- Requested 2026-10-27 for full stack-up functionality:
  - Cp/Cpk and distribution (normal, uniform, shifted mean) per link, not only per chain.
  - Build the chain from a 3D selection: faces, edges and derived axes/median planes picked in order along the
    chain; the direction from the geometry; values from the PMI on those features; features without PMI take the
    general tolerances (ISO 2768 / ISO 22081, §8.5) and are marked as such; missing values reported.
  - Accumulated (cumulative) chains across several parts of an assembly (links from different parts plus the
    mating conditions between them), see §8.20.
- Done 2026-10-27 (stage 2a): `kette_aus_flaechen` – faces in chain order (planes perpendicular to, cylinder/cone
  axes across the direction of the first planar face), sign from the position, PMI matched by positions at both ends
  and nominal (patterns included), else ISO 2768-1 from the chosen or file general tolerance, else "no tolerance";
  per link distribution (normal/uniform) and Cp, variance share per link; UI "From 3D selection", row highlights its
  faces. Open: edges and derived median planes as chain ends, GD&T contributors from the zone logic (position,
  profile, datum shift with Ⓜ/Ⓛ), Cpk / shifted means, PDF report, chains across assembly parts.

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

### 8.20 3D tolerance analysis of assemblies (requested 2026-10-27; reference: 3DCS)
Request: build assemblies, set up functional dimension chains ("Funktionsmaßketten", FMK – assumed meaning) from the
PMI, recognize or assign materials, take temperatures and thermal expansion into account, compute stack-ups, and
move parts within their tolerances (1:1 and exaggerated) in worst case or per tolerance / chain ("wiggle") to find
and judge errors in chains.

Research (2026-10-27, vendor statements and literature, not verified by experiment):
- 3DCS Variation Analyst (DCS, commercial, CAD-integrated): model = *moves* (how parts are located in the assembly,
  locators preferably on the GD&T datum features), *tolerances* (taken from the PMI), *measures* (gaps, flush,
  distances). Analyses: Monte Carlo (Cp, Cpk, Ppk, % out of spec, recommended GD&T value), High-Low-Median
  sensitivity (contribution from the tolerance range) and GeoFactor (geometric amplification of each tolerance);
  "contributor analysis" ranks the drivers. Sources: 3dcs.com, "What's new in 3DCS 7700", reseller listings.
- Methods in the literature: tolerance chart / 1D chains, vector loops (assembly constraints as closed loops),
  small displacement torsors (SDT) and the unified Jacobian-torsor model, combined with Monte Carlo; a comparison
  of methods on the same open-loop assembly gave noticeably different results – choose and document the method.
  No usable open-source implementation was found.
- Statistics: worst case (arithmetic) vs. statistical (RSS / error propagation; means at nominal and symmetric
  distributions are assumptions); DIN 7186 (statistical tolerancing) is withdrawn, process capability per the
  ISO 22514 / DIN ISO 21747 family. Non-linear and multi-dimensional chains need sampling instead of linear sums.
- Thermal expansion: ΔL = α · L · ΔT relative to the ISO 1 reference temperature of 20 °C; for parts of different
  materials the difference of the expansions enters the chain (deterministic shift per operating temperature).

Plan (each stage usable on its own; builds on §8.5 zones and the 1D chain of §8.8):
1. **Assembly model:** use STEP assemblies as loaded; additionally assemble parts in the project (place a part,
   mate datum features: plane–plane, pin–hole, pin–slot, 3-2-1 locating), stored in the project container.
   Placing snaps: drag a part, its face/axis/point snaps to the picked feature of the other part (coincident,
   coaxial, offset), the snaps accumulate into the mates of the part; the open DOF are shown (§8.21 stage 6).
2. **Materials:** read STEP material/density properties where present, otherwise assign from a small library
   (E-modulus, α, density; user extensible); temperature per part or per case (assembly, operation, min/max).
3. **Chains:** 1D chains as today but picked in the model (faces/PMI along the chain, direction from the geometry);
   then 3D: each toleranced feature gets a torsor bounded by its tolerance zone (form, orientation, location,
   size, datum shift with Ⓜ/Ⓛ), mates propagate the deviations, measures are distances/gaps/angles between
   features; thermal expansion and general tolerances (§8.5) as further contributors.
4. **Analysis:** worst case (extremes of the linearized torsor model, checked by sampling), RSS, Monte Carlo with
   distributions (normal, uniform, shifted mean, Cpk), result Cp/Cpk/% out of spec, contributor ranking (range
   and sensitivity), recommended tolerance changes.
5. **Wiggle:** move the parts within their tolerance freedom – per tolerance, per chain or the worst-case
   combination – 1:1 or exaggerated by a factor, animated, with gaps/interferences highlighted; slider per
   contributor.
6. **Report:** chain, contributors, histograms, worst-case configuration images (PDF/CSV), stored in the project.
- Effort: large (months for 3D); order: zones (§8.5 stage 2) → picked 1D chains with temperature → 3D torsor model
  and Monte Carlo → wiggle → assembly mating UI.

### 8.21 Clash, clearance band and intersection analysis; degrees of freedom (requested 2026-10-27)
Request (from public feature requests of an open-source CAD project, generalized): check assemblies or a selection of
parts for intersections, for distances outside a band (minimum/maximum clearance), also while parts move within
their joints/limits, and visualize the open degrees of freedom by wiggling the assembly. Part/version comparison and
scan-vs-CAD comparison from the same requests already exist (Comparison in docs/Roadmap.md: per-face status,
deviation color map, added/removed volume like CATIA Compare Products, meshes/PLY vs. CAD).

Research to do first: how CATIA (Clash/Distance and Band Analysis), NX (Clearance Analysis) and other viewers report
results (clash / contact / clearance categories, penetration depth, result list with ignore/approve state,
re-run after changes); which tolerance for "contact" vs. "clash" is useful for faceted data.

Building blocks verified in pythonocc-core 8.0.1 (2026-10-27, two boxes overlapping by 1 mm, a third 0.5 mm away):
`BRepExtrema_ShapeProximity` on meshed shapes finds overlapping face pairs (fast preselection, 5 pairs),
`BRepAlgoAPI_Common` gives the exact intersection volume (100 mm³), `BRepExtrema_DistShapeShape` the minimum
distance with points (0.5 mm). For meshes (PRC, STL) a triangle–triangle test on the existing mesh tools.

Plan:
1. **Selection:** all parts, a selection, or group A against group B; part instances count separately.
2. **Clash / contact:** bounding-box and mesh-proximity preselection, then exact check per pair: clash
   (intersection volume > 0, with penetration depth and volume), contact (touching within a tolerance),
   clearance (distance below the minimum).
3. **Band analysis:** user gives minimum and/or maximum distance; report every pair outside the band (too close or
   too far, e.g. for gap/assembly space), with the points of minimum distance.
4. **Intersection analysis:** intersection curves and volumes shown in the 3D view (red solids/curves), the two
   parts highlighted, others dimmed; jump between results (like the change list), comment, accept/ignore,
   report (PDF/CSV) in the project.
5. **With motion:** for STEP kinematics (AP242 kinematic structures, where present) or joints defined in the project
   (§8.20 mating): sample the joint ranges (and tolerances from §8.20) and report the worst clearance / first clash
   per joint position; animate that position.
6. **Degrees of freedom:** derive the open DOF of each part from its mates/joints and wiggle the assembly in every
   open DOF (animation, slider per DOF) to see whether all joints were made; under-/over-constrained parts listed.
- Shares the assembly, mate and wiggle model with §8.20; stages 1–4 are independent of it and can come first.

### 8.22 Plausibility check of the specification (requested 2026-10-27)
Find contradictions and incomplete specifications in the PMI of a model, as an extension of Model › Check PMI
(`kern/pmi_bericht.pruefe`, today: undefined/unused datums, orientation/runout without datum, form tolerance with
datum, Ⓜ/Ⓛ without feature of size, runout without axis, duplicates, PMI without face or value, standard rules).
Planned rules (each finding with severity, the PMI involved, a short reason and the rule source ISO/ASME):
- **Hierarchy contradictions** on the same face: form > orientation > location (e.g. flatness 0.2 with parallelism
  0.1 on the same face; perpendicularity larger than the position tolerance of the same axis; profile of a surface
  without datum tighter than with datum is fine, the reverse is not).
- **Size vs. form**: form tolerance larger than the size tolerance under the envelope requirement (ASME Rule #1,
  ISO Ⓔ) – ineffective; Ⓔ and a separate form tolerance with the same value.
- **Completeness**: faces without any dimension, tolerance or general tolerance (not fully toleranced, shown in the
  model); feature of size without size dimension; position without basic dimensions (when the file carries them);
  missing general tolerance note; patterns with a count that does not match the faces.
- **Datum system**: datum feature without its own form tolerance; degrees of freedom left open by the datum
  reference frame for a location tolerance (e.g. position on a pattern with only a primary plane); datum order
  that cannot constrain (two parallel planes as primary and secondary); Ⓜ on a planar datum.
- **Over-determination**: two dimensions for the same distance with different values; closed dimension chains
  (loop of linear dimensions) – the closing dimension is redundant; size given twice (dimension and note).
- **Values**: zero or negative tolerances without Ⓜ/Ⓛ, unequal zone larger than the tolerance, projected zone on a
  non-hole, tolerance finer than the decimals of the nominal, deviations with swapped signs (upper < lower), fit class
  unknown to ISO 286.
- **Consistency with geometry**: dimension value differs from the measured model geometry (e.g. Ø20 on a Ø21 hole –
  needs the measuring functions), datum letters used on different features, PMI on hidden/auxiliary geometry.
- UI: the existing Check PMI dialog grouped by category, double-click selects PMI and faces, export to the PMI report;
  optional "incomplete faces" colouring in the model.
- **Stage 1 done (2026-10-27):** `kern/plausibilitaet.py` (rules hierarchie, mass_und_form, vollstaendigkeit,
  bezugssystem, ueberbestimmung, werte, geometrie) appended to `pmi_bericht.pruefe`; findings carry a category and
  faces; the Check PMI dialog shows the category and selects PMI or faces. On the NIST files it reports the
  untoleranced faces and one datum system that fixes only one direction; on `ctc01_geo.stp` it finds the Ø20 nominal
  on the Ø21 hole. Open: closed dimension chains, basic dimensions for position, pattern counts, datum targets,
  export of the findings, colouring of untoleranced faces.

### 8.23 Scan against PMI tolerances (done 2026-10-27, stage 1)
- `kern/scanpruefung.py`: best fit (`ausrichten.richte_aus`, candidate choice by inlier share first – fixes
  mirrored/rotated fits of nearly symmetric parts) plus fine alignment point-to-plane against the exact B-rep faces;
  every scan point assigned to the nearest CAD face (foot point inside the face boundary, signed distance exact).
- Per PMI: form tolerances and profile without datum as range, profile/location with datum within the (unequal)
  zone, axis tolerances and sizes via a least-squares cylinder per feature (axis offset, actual size, bonus with
  Ⓜ/Ⓛ), status OK / not OK / at the limit (measurement uncertainty 5 µm) / not evaluable.
- UI: Tools › Check scan against tolerances (background), colour map over the translucent CAD model, result list
  (selection selects the PMI and its zone), CSV.
- Test data (`werkzeuge/testmodelle.py`): `ctc01_scan.ply` (noise 5 µm, rotated/shifted), `ctc01_scan_fehler.ply`
  (chamfer, dent, waviness on the flatness face); results in `tests/test_vergleich.py`.
- Open: manual alignment for the scan check (point pairs like the comparison), alignment to the datum system
  (3-2-1 instead of best fit), evaluation of linear distances and angles, line profile/roundness per section, report
  PDF with pictures per non-conforming PMI, point clouds without triangles.

### 8.24 Demo projects (requested 2026-10-27; stage 1 done the same day)
Done: `kern/beispiele.py` (nine examples, files looked up in the built app under `programm/beispiele/` or in
`tests/daten`; the spec copies them, so the repository holds no duplicates), File › Examples, steps after loading
via `Hauptfenster.oeffne_beispiel`, `test_beispiele_oeffnen`. Analyses (draft, wall thickness) left out on request.
Open: examples as project files with review state and comments; manual screenshots from the examples.
Example projects in the repository (`beispiele/`, project containers `.3dgmax` plus the referenced public-domain or
self-generated models) that show one function each and open with File › Examples: PMI display and views, check
PMI and plausibility findings, tolerance zones incl. general tolerances, comparison of the CTC-01 variants with the
review state, scan against tolerances (both generated scans), 1D stack-up with Cp, analyses (draft, wall
thickness), sections and drawings, assembly comparison (`baugruppe*.stp`). Only files with a clear licence (NIST
public domain, own test models from `werkzeuge/testmodelle.py`); a test opens every example. Later the screenshots
of the manual are generated from these projects.

### 8.25 Saved views with section planes (requested 2026-10-27; STEP done the same day)
Done: `kern/ansichten._schnitt` reads PLANE / CLIPPING_UNION / CLIPPING_INTERSECTION into an intersection of unions
(CAx-IF PMI Rec. Pract. 4.0.4 §9.4.3: the side the normal points to stays visible; several entries directly at the
camera are taken as all cutting – the document does not say it explicitly); each union is one chained OCCT clip
plane group (OCCT also keeps the normal side), the groups cut together. Test file
`tests/daten/varianten/ctc01_schnittansicht.stp` (text edit of NIST CTC-01). Open: QIF/PRC clip planes, own views
storing the current section, hatching of the cut faces.
STEP AP242 saved views may carry clipping planes (`CAMERA_MODEL_D3_MULTI_CLIPPING` with planes or
`CAMERA_MODEL_D3_MULTI_CLIPPING_INTERSECTION` / `_UNION` combinations). Today the camera of such a view is read but
the planes are ignored. Plan: read the planes (and their combination) in `kern/ansichten.py`, apply them as section
planes with capping when the view is activated (union/intersection map to the existing multi-plane section),
remove them when another view is chosen; same for QIF and PRC views where the format carries clip planes. No public
sample with clipping planes is known – a test file is made by a text edit of a NIST file (licence-safe) and checked
against the CAx-IF recommended practice for saved views.

### 8.26 Several models side by side (asked 2026-10-27)
Recommendation: File › New window in the same process (each window with its own model, 3D view and panels; shared
settings and recent files), plus "open in new window" from the recent list and for dropped files with a modifier.
Optional linked cameras between two windows (same view direction and zoom), which also gives the planned linked
side-by-side comparison view. Separate processes work today (start the app twice), but macOS bundles route a second
file open to the running app, so a window inside the app is the portable solution. Memory grows with each model; a
test opens two windows and closes one without affecting the other.
