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
| **7 JT via TKJT** | build TKJT for OCCT 8, Python binding, load JT; build with/without TKJT (open source only on GitHub) | JT file like its STEP counterpart | ✅ JT 8–10 via TKJT fork wwmayer/TKJT + own JT 10 fixes; NIST JT 10.5 end-to-end |
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
  Change list entries per instance done (2026-10-28, `vergleich._je_instanz`: split when not all instances are
  affected, entry carries the leaf; "at all n instances" otherwise).
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
- Done 2026-10-27 (stage 2b): location tolerances of the first and last face as links (position, symmetry,
  coaxiality, profile with datum incl. UZ and material side; intermediate faces cancel out, so they get none),
  PDF report (picture with the chain faces, result, link table with shares), chain stored in the project.
  Open: Ⓜ/Ⓛ bonus and datum shift as (non-normal) contributors, Cpk / shifted means, edges and median planes as chain
  ends, chains across assembly parts (needs the mating model of §8.20).
- Done 2026-10-27 (1D finalised): Ⓜ/Ⓛ bonus widens the location link by the feature's size tolerance (worst case),
  zero tolerance at Ⓜ/Ⓛ allowed, datum with Ⓜ/Ⓛ as an own "datum shift" link (`toleranzzone.bezugsverschiebung`),
  straight/circular edges as chain ends, mean offset per link (Cpk = Cp·(1−|offset|/(T/2))), requirement on the
  closing dimension → Cp, Cpk and share outside (normal approximation and Monte Carlo); pattern matching of end
  features only within the same element type (axis/plane). Open: median planes of features of size as chain ends,
  chains across assembly parts (from the connections of §8.20), non-normal bonus distributions.
- State of the art (research 2026-10-28, sources below; "FMK" = Funktionsmaßkette):
  - **Methods:** arithmetic / worst case (always valid, conservative); statistical RSS (variances add, closing
    dimension ±3σ); modified RSS with an inflation factor (Bender 1962: ×1.5 for optimistic tolerance statements,
    in practice 1.4–1.7); mixed (some links worst case, others statistical); mean-shift models – mean shifts stacked
    arithmetically plus the reduced variation stacked statistically (Greenwood/Chase 1987, Scholz), or shifts stacked
    statistically; Six Sigma 1.5σ shift (conservative, not universal); Monte Carlo for any distribution and
    non-linear chains.
  - **Distributions per link** with inflation factor c (σ = c · T/2 / 3, Scholz Table 1): normal c = 1, uniform
    1.732, triangular 1.225, trapezoidal √(3(1+a²)/2) (a = flat part, 0 → triangle, 1 → uniform), half cosine 1.306,
    elliptical 1.5, symmetric beta 3/√(2a+1), DIN 7186 histogram density √3·√((1−p)(1+f)+f²). Choice by production
    type (Klein; HAW thesis 2024): one-off/prototype → uniform (only the limits are known), small batch → triangular
    (fixtures, aimed at mid), large series → normal (tolerance = ±3σ / Cp).
  - **When statistical is applicable:** the closing dimension is treated as normal by the central limit theorem –
    in practice from **four links** with arbitrary distributions (fewer if links are normal; two uniforms give a
    trapezoid); links must be independent (different parts/processes), processes stable and centred (otherwise mean
    shift / Cpk), and the quantity large enough that the 0.27 % risk means something. With few or dominated links
    the worst case is the honest result. Standards: DIN 7186-1 (statistical tolerancing, 1974) withdrawn without
    replacement; process capability per ISO 22514-2 / DIN ISO 21747; ASME Y14.5 has a statistical tolerance symbol.
  - **Contributors ("Beitragsleister"):** variance share per link (statistical), range share (worst case),
    sensitivity coefficient for non-linear chains (∂closing/∂link, not only ±1); Pareto chart; equalising the
    variances (links with tiny shares are made too precisely).
  - **Synthesis / allocation:** widening factor e = T0,arith / T0,stat; distribute the closing variance equally or
    by cost/process; inverse problem "which tolerance for a required Cpk".
  - **What-if:** commercial tools (e.g. CETOL: direct method, results update immediately; 3DCS: Monte Carlo, HLM
    sensitivity, GeoFactor) let users change tolerances and compare scenarios; results tied to Cp/Cpk/% out.
  - Sources: F. Scholz, "Tolerance Stack Analysis Methods" (Univ. of Washington / Boeing, faculty.washington.edu/
    fscholz); master thesis "Statistisches Toleranzdesign im Maschinenbau", HAW Hamburg 2024 (reposit.haw-hamburg.de,
    citing B. Klein 2017, F. Mannewitz 2016, Bosch booklet "Statistische Tolerierung"); Capra/Tolcap slides on
    Bender and the 1.5σ shift; Sigmetrix CETOL product pages; Walter et al. 2021 survey on statistical tolerance
    analysis in German industry.
- Requested 2026-10-28 (stage 3, implement now):
  1. Distributions per link: normal, uniform, **triangular, trapezoidal** (flat part a), labelled with the production
     type; σ and Monte Carlo sampling per distribution (trapezoid = sum of two uniforms).
  2. **Arithmetic always shown, the applicable method in bold** – statistical when there are at least four effective
     contributors (n_eff = (Σσ²)² / Σσ⁴, so one dominating link counts as one), otherwise arithmetic; the reason is
     shown ("5 effective contributors – statistical applicable") in the window and in the PDF/CSV.
  3. **What-if ("Planspiel"):** a switch makes the table editable (limits, nominal, tolerance, distribution, Cp,
     offset, direction) without touching the real chain; changed cells are marked; results "Ist | Planspiel | Δ" side
     by side; "Übernehmen" makes the scenario the chain, "Verwerfen" restores it; the PDF contains the comparison.
  4. Double-click on the direction cell reverses the link.
  5. UX (see below), CSV/PDF extended.
- Done 2026-10-28 (stage 4a): sensitivity factor per link (richtung × faktor in worst case, RSS, Monte Carlo, shares,
  n_eff, adjusting member), statistical method RSS / RSS × Bender factor / mean-shift model (shifts m·T/2 arithmetic +
  RSS of (1−m)·T/2 as ±3σ; m = 0 gives RSS, m = 1 worst case – both tested), tolerance allocation to a target range
  (equal variance per adjustable link or proportional, statistical or worst case, fixed links stay) into the what-if.
- Later (stage 4): modified RSS with factor (Bender) and mixed method as options; mean-shift model (worst case of
  shifts + RSS of variation) and Six Sigma shift; sensitivity coefficients per link (angles, cos factors,
  non-linear chains via Monte Carlo); correlation of links from the same part/process; tolerance allocation
  (equalise variances, widening factor, cost weights, "required Cpk → tolerances"); beta/cosine/DIN histogram
  distributions; distribution fitted from measured values (CSV import); several saved scenarios instead of one;
  ⟨ST⟩ statistical tolerance marks from the PMI as hint for the distribution.
- Requested 2026-10-28 (stage 3b, implement next):
  1. **Thermal expansion (optional):** two limit temperatures for the whole chain (e.g. −20 °C / +80 °C, reference
     20 °C per ISO 1); per link ΔL = α · L · (T − 20 °C) with α of the part; the closing dimension is computed at
     both limits (worst case and statistics shifted by the thermal term). α from the STEP material (if the file
     carries a material/property; otherwise a small material library: steel 11.5, stainless 16, aluminium 23,
     cast iron 10.5, brass 19, PA6 80, POM 110 ·10⁻⁶/K) or entered per part; links know their part via the PMI faces.
  2. **Save and load the chain** as an own file (`.3dgkette`, JSON: links, Cp, requirement, temperatures, materials,
     what-if; model path and face ids so that "show faces" works again) for later sessions, independent of the
     project container (which keeps storing it too).
  3. **Demo:** File › Examples "Toleranzkette (Getriebe)": a small generated gearbox-like assembly (shaft shoulder,
     gear, spacer, bearing, circlip groove and ring – the classic example of Klein/HAW thesis) as STEP with PMI plus
     a chain file; shipped in tests/daten (own geometry, no licence issue).
  4. **Springs and adjustable lengths:** a link type "length range" (e.g. a spring between min and max installed
     length, shims, adjustment screws): min/max instead of nominal ± tolerance, uniform distribution by default, can
     also be marked as the *adjusting member* (closing dimension is then solved for its required range instead).
  5. **Directions from a load direction:** with links from faces the sign already follows from the geometry. For a
     chain defined by PMI dimensions (no order), a "Kraftrichtung" (load/closing direction) picked in 3D lets the
     signs be set from the geometry of each dimension's two faces along that direction – unambiguous only for
     planar faces perpendicular to it; others stay and are marked. Plus a **validation animation**: each link is
     shown in turn as an arrow between its faces in the 3D view (+ green, − red), and a "wiggle" moves the faces of the
     closing dimension by the worst-case extremes (exaggerated) so the user sees whether the gap closes the right way.
- Done 2026-10-28 (stage 3b): thermal expansion at two limit temperatures with optional own temperature per part
  (`kern/werkstoffe.py`: library, keyword matching of material names, STEP materials via MATERIAL_DESIGNATION or
  the XCAF property form – checked by writing/reading a file with OCCT); length-range links and an adjusting member
  with its required worst-case range (`stellbereich`); chain file `.3dgkette` (`kern/kette_datei.py`), opened via File ›
  Open too (loads its model); gearbox demo `werkzeuge/getriebe.py` → `tests/daten/getriebe.stp/.3dgkette` and File ›
  Examples. Item 5 done differently: instead of a load direction the user picks the two faces of the closing dimension
  – a path search over the face positions sets order and signs (`richtungen_aus_schlussmass`, unambiguous where a
  load direction is not); "▶ Kette ablaufen" walks the links in the model. Open: arrows per link in 3D and a wiggle of
  the closing faces by the worst-case extremes. Finding: OCCT writes non-ASCII STEP strings as raw UTF-8 – the P21
  reader now tries UTF-8 before Latin-1.
- UX design (stage 3): one window in the order *purpose → inputs → links table → results → export*:
  - Top: one-line purpose and the buttons to add links (from PMI list, from 3D selection), "Lagetoleranzen",
    chain Cp; right aligned the "Planspiel" switch.
  - Links table: direction as "+"/"−" (double-click flips), distribution as combo with production type, Cp/form
    column that adapts (Cp for normal, a for trapezoid, "–" otherwise), share as a small bar with percent.
    In Planspiel the table gets a tinted background and changed cells are bold with the original as tooltip.
  - Results as a small table instead of running text: rows Arithmetic (worst case), Statistical (RSS ±3σ), Monte
    Carlo (99.73 %); columns min, max, ±/range; the applicable row bold with "✓ anwendbar" and the reason below; with
    requirement Cp/Cpk/ppm in extra columns. In Planspiel the columns are Ist, Planspiel, Δ.
  - A small histogram of the Monte Carlo samples with the worst-case limits and the requirement drawn as lines.
  - Bottom: CSV, PDF, close.

### 8.32 JT via TKJT (step 7, started 2026-10-28)
- Built: TKJT (github.com/mmaenz/TKJT, Open Cascade, GPL v2+) at commit 658f65a – the newer merge commit 2c15f87
  contains unresolved merge conflicts in 22 files – compiled with clang against OCCT 8.0.1 of the pixi environment by
  `packaging/jt/bauen.sh` (no cmake needed; no tbb: NO_JT_MULTITHREADING; zlib of the system; JtToTopoDS left out as
  it needs the Parasolid XT reader). Patch for OCCT 8 (`packaging/jt/tkjt_occt8.patch`): hasher call operators for
  Jt_GUID (NCollection_DataMap hasher API of OCCT 7.8+), MMgt_TShared → Standard_Transient.
- Own converter `packaging/jt/jt2glb.cxx`: LSG tree (partition, group, part, instance, range LOD → first level) to an
  XCAF assembly with names, placements and diffuse colours, the tri-strip LOD triangles to faces with triangulation,
  written as GLB by RWGltf_CafWriter; 3DGmax runs it as an external process and loads the GLB like glTF
  (`laden._lade_jt`, `jt_wandler`: DG_JT2GLB, bundled next to the app, extern/). App variant: `DG_MIT_JT=1` bundles it.
- **Limitation found:** the only free JT (NIST MTC assembly) is **JT 10.5**; TKJT reads JT 8/9 only (32-bit TOC
  offsets; JT 10 has 64-bit offsets and LZMA). The JT 10 file format reference is not freely available (ISO 14306:2012
  = JT 9.5), so a JT 10 extension would be reverse engineering – not done. JT 10 is detected from the header and
  reported clearly. No free JT 8/9 test file found (JT2Go samples are under the Siemens licence) → the converter is
  verified to build and to reject JT 10; the loading path is tested with a stand-in converter. Needs: a JT 9 export
  (e.g. from CATIA/NX) for an end-to-end test, unit check (mm vs m) against the STEP of the same model.
- **JT 10 (2026-10-28):** switched to the fork github.com/wwmayer/TKJT (commit 687cc51, JT 10 read support merged
  2026-05-22, base of FreeCAD's JT 10 import, already ported to OCCT 7.8+; only MMgt_TShared is replaced by sed).
  JT 10 segments use LZMA → `liblzma-devel` in the dev environment. With the NIST MTC assembly (JT 10.5) the fork
  still failed on every tri-strip LOD; own fixes in `packaging/jt/tkjt_jt10.patch`, checked against the public JT
  format description of prostep ivip (JTIAP V3, PSI 14):
  1. Move-to-Front pseudo-codec (CDP codec 5) was missing: two nested CDPs (window values, window offsets); offset
     -1 takes the next new value, otherwise the value at that window position moves to the front (window 16).
  2. Probability context: the Associated Value is stored with Min Value subtracted and was read as signed bit field
     (e.g. 11 became -5) → read unsigned.
  3. Binary vertex coordinates (quantization bits 0) pass the Lag1 predictor (spec: VecU32{Int32CDP, Lag1}); the fork
     skipped it → NaN/1e38 coordinates in all lossless LODs.
  4. Mesh decoder: when the valence symbols run out (one shape of the NIST file) decoding stops instead of crashing;
     jt2glb then takes the next coarser LOD.
  Result: all LODs give finite coordinates and unit normals; jt2glb writes 46 276 triangles in 0.2 s; the app shows
  the assembly correctly (checked on screen). Units: coordinates in mm (cover 152.4 = 6 in).
- 2026-10-28 (user report: JT not openable in the GitHub build): build script rewritten in Python
  (`packaging/jt/bauen.py`, clang++/g++ or MSVC cl/link with libraries looked up in the pixi environment), workflow
  input "jt" (default on) builds the converter (Windows: ilammy/msvc-dev-cmd) and bundles it (`DG_MIT_JT=1`);
  `jt2glb.exe` on Windows in spec and loader. Windows build not verified locally – check the first CI run.
- Open: PMI from JT (TKJT has a PMI manager element), JT B-rep (XT, needs Parasolid), the one shape whose finest LOD
  has inconsistent mesh symbols (coarser LOD used).

### 8.34 Remaining tolerance zones (requested 2026-10-28, done the same day)
- Line zones per section (`toleranzzone._linienzone`): ProfileOfLine, and LE (Line_Element) / ALS modifiers: the
  ±t/2 offset surfaces (with UZ) are cut by three planes – across the axis of cylinders/cones, through the axis
  (0°/60°/120°) for LE/ALS, otherwise across the largest extent – and a ruled band is built between the two section
  curves (`brepfill.Face`, curves re-oriented). The intersection-plane indicator of the file is not read yet.
- ACS (Any_Cross_Section) on axis tolerances: disks Ø t on the axis in three cross-sections instead of the cylinder.
- CZ (Common_Zone) on planar faces of one plane: one pair of planes ±t/2 over all faces; otherwise separate zones.
  SZ (Separate_Requirement): separate zones with a hint.
- Tolerances without faces: found in NIST data as (a) the whole part (aspect = PRODUCT_DEFINITION_SHAPE, e.g. FTC-10
  surface profile 1.5 A|B|C) → zone on all faces with a hint; (b) construction geometry (GEOMETRIC_CURVE_SET of a
  "Thread Cylinder": circle + trimmed lines, not transferred by OCCT) → edges rebuilt from the P21 data
  (`pmi_lesen._kurven_aus_datei`, PARAMETER_VALUE trims), axis from the circle, length from the parallel lines at the
  radius, one Ø t cylinder per thread and the projected zone Ⓟ on the side outside the material (FTC-10: 3 position
  tolerances × 2 threads); (c) curves/edges (CTC-05 straightness on a TRIMMED_CURVE) → tube Ø t; points → sphere.
  Shapes are kept as attribute `Pmi.teilformen` (not a dataclass field, so project files are unchanged).
- CZ on offset (non-coplanar) features and axis patterns: separate zones at their nominal places with the hint that
  they are theoretically exact to each other and aligned together (geometrically the same zones).
- Scan check: line profile per section (`scanpruefung._linien_auswertung`) – points split into slices across the
  section direction (LE: angular sectors around the axis = longitudinal sections); with datums all deviations in the
  zone, without datums range ≤ t; worst slice counts (test: taper 0.05 passes per cross-section, fails with LE).
- 2D/3D chains saved as .3dgkette2d/.3dgkette3d (`kette_datei.speichere_raum/lade_raum`) and in the project
  ("raumketten").
- Open: intersection-plane indicator – no sample file with it, and pythonocc does not wrap XCAFDoc_GeomTolerance,
  so it cannot be verified by experiment.

### 8.33 Functional dimension chains: view, purpose, 2D/3D, from function to ISO GPS (requested 2026-10-28)
Requests: show the chain with one click as arrows with dimensions and tolerances in the 3D view (geometric tolerances
and ranges in other colours, what-if as overlay); clean up the chain window (scrolling, histogram beside the result
table, interactive histogram); explain what a functional dimension chain (FMK) is for; list what 1D still lacks;
research, plan and build 2D/3D chains; a guide from a part's function to ISO GPS tolerancing with the cheapest
tolerances that still secure the function, and a "logic" in which faces and functions are defined the way designers
lay out parts.

**Done 2026-10-28:** "Kette im 3D" (`toleranzkette.kettenbild`): every link an arrow on its own lane outside the
model's bounding box, lanes stacked along the camera's up direction, tip to tail along the chain direction at the
positions of its faces (links without faces continue from the previous tip); dimensions green (+) / red (−), location
tolerances violet brackets over the zone width, length ranges orange, closing dimension blue with WC and RSS; labels
at the start of each arrow (midpoint labels of the lanes overlapped on screen); in the what-if, changed links also
in grey with the current value (overlay; side by side is left out – the overlay shows both at the same place).
Chain window: splitter between links and results, result table only as wide as its columns, histogram to its right;
histogram interactive (value and share below/above at the mouse, red requirement limits draggable → requirement
fields).

**Done 2026-10-28 (second request):** the histogram showed always Monte Carlo; now it shows the method marked ✓
(applicable: statistical with ≥ 4 effective contributors, otherwise worst case) – worst case as a band (no
distribution, every value possible), statistical as normal curve (mean, half width = 3σ of the chosen RSS variant),
Monte Carlo as histogram; a click on a result row switches, "overlay all" draws the three on one density scale;
the share at the mouse follows the shown method (none for worst case). Traffic light `toleranzkette.bewertung`:
green = applicable result inside the requirement (statistical also Cpk ≥ 1.33), yellow = inside but Cpk < 1.33, or
outside but ≤ 0.27 % of the Monte Carlo values outside, red otherwise; in the window and the PDF. Manual approval
("Kette i. O. / geprüft", name, date, comment) independent of the result, stored in `.3dgkette` and printed in the
PDF. Open: approval in the project file, traffic light for assembly measures and later 2D/3D chains (same function).

**Done 2026-10-28 – stage 1 (cost-optimal allocation):** `kern/fertigung.py` – processes with the finest economic
and the coarse IT grade and a relative cost factor (guide values from the usual process → IT grade charts, editable
per link: turning IT7–11, milling IT8–11, drilling IT10–13, reaming IT6–9, grinding IT5–7, honing/lapping IT4–6,
broaching IT6–8, die casting IT11–14, sand casting and forging IT14–16, sheet punching/bending IT10–13, laser
cutting IT12–14, injection moulding IT9–13, additive metal IT11–14, purchased part fixed); reciprocal cost model
cost = factor · T_coarse / T within [T_fine, T_coarse] (IT values from `iso286.it` at the nominal size).
`toleranzkette.verteile_kostenoptimal`: minimum total cost subject to the closing width (worst case: Σ k·T;
statistical: 6·sqrt(fixed variance + Σ (k·T/κ)²) with κ = T/σ of each link's distribution), bounds per link from its
process, SLSQP (scipy); fixed links, location tolerances, adjusting members, measured links and purchased parts stay;
infeasible targets set the finest tolerances and say so. Chain window: column "Fertigung" (process per link, tooltip
with the IT grade of the current tolerance), allocation option "Kostenoptimal nach Fertigungsverfahren", result
with cost before → after in the what-if and the PDF. Checked: die casting is driven to its finest grade under worst
case and relaxed statistically, turned parts widen, the ground ring gets its coarse limit.

**Done 2026-10-28 – stages 2 and 3 (function → datum system → ISO GPS proposal):** `kern/funktion.py`, window
Model › "Funktion → Tolerierung …". Roles per face: seat, centring (H7/h6), guide (H7/f7), press fit (H7/p6),
anti-rotation pin (H7/m6), sealing face, stop, free surface (preferred fits of the ISO hole-basis system). Datum
system 3-2-1: primary = largest planar seat (3 DOF), secondary = centring axis perpendicular to it (2 DOF) or a side
seat/stop perpendicular (2 DOF), tertiary = anti-rotation pin parallel to A / stop perpendicular to A and B (1 DOF);
without a planar seat the longest centring is the primary axis (4 DOF) and a stop along the axis the secondary;
open DOF are reported. Tolerances: datum features with a single preceding datum get an orientation tolerance
(perpendicularity), with two a position (pin with Ⓜ); other seats parallelism to A, other features position or
surface profile to A|B|C, seats and sealing faces flatness, sealing faces a roughness note, guides cylindricity,
cylinders the fit of their role (hole → H, shaft → the shaft letter); values = IT grade per role at the feature
size (starting values; the chain and the cost optimisation set the final ones). Proposals go through the existing
"PMI anlegen" dialog into own PMI and can be written to STEP AP242 (§8.28). Roles are stored in the project.
Checked on a generated plate (A seat, B bore Ø20 H7 ⟂ A, C pin Ø6 H7 position Ⓜ A|B) and on NIST FTC-10.
**Done 2026-10-28 (user request): editable function table.** Rows are features (`gruppen`: first face → all faces;
several faces on the same cylinder – axis and diameter – or in the same plane become one, e.g. two half shells),
role per combo box in the table, fit class and tolerance typed in (`werte`; empty/"auto" = start value from role and
IT grade, shown greyed), "Flächen aus Auswahl" swaps the faces of a feature keeping role and values; geometry of a
feature sums the area and spans all faces (`_geo`); stored in the project (old role-only format still read).
Found on the way: position/perpendicularity envelopes were full cylinders around the axis even for a half shell –
now offset copies of the actual faces (`_eine_achse`).

**Done 2026-10-28 (plan item 3): wiggle of the closing faces.** `kern/schluss_wiggle.py`: closing faces = first face
of the first and last face of the last link with faces (direction from the first link, oriented so the closing size
grows away from the start face); frames as a sine between worst-case minimum and maximum, magnified so the range is
about 1/20 of the model size; per frame value and assessment against the requirement. Display: copy of the end face
(unlit, Topmost so it stays visible inside material) with the value; play/pause icon in the chain window. Chains built
from PMI without faces in chain order report that the wiggle needs model faces (no guessing).

**Done 2026-10-28 (plan item 4): median planes and chains across parts.** `kette_aus_flaechen(mitte_anfang,
mitte_ende, fuegestelle)`: the first/last two selected faces form a median plane as chain end – link "½ × width" with
factor 0.5 on the width dimension (PMI between the two faces, else ISO 2768), position tolerances of that end are
not added (symmetry belongs to the feature); checked on FTC-10 slot 183/185: worst case 0.4 + 0.4 + 0.2 = 1.0. At a
change of part where the assembly has a connection between exactly these two faces, the transition becomes a link
"Fügestelle A / B" with nominal 0 and the connection's clearance (positions still from the file, i.e. the assembled
STEP position). Open: chains from the snapped assembly positions (moved parts) and connections between features
other than the selected faces.

**Planned (user question 2026-10-28): "make semantic / repair" for PMI.** Graphic → semantic: PMI that exist only
as graphics are already read and, where the graphics carry text (real strings, QIF texts, PRC markup type), type and
values are derived (`pmi_ableiten`, marked "abgeleitet – bitte prüfen"); a repair action takes a checked derived PMI
over as a real semantic own PMI (type, value, tolerance, datums, faces from the callout association or picked by hand)
that is written as AP242. Stroke-font texts (CATIA/NX draw text as polylines) carry no string – recognising the line
glyphs is a research item (fixed fonts). JT PMI are not read yet (the converter transfers geometry only).
Semantic → graphic: plan item 6 (presentation for written PMI, parallel session `pmi-darstellung`).

**Planned after UI stage 2 (requested 2026-10-28): materials in hand-built chains (1D, 2D, 3D).** Today a chain
built by hand (no model, or links typed in) has no material, so thermal expansion cannot use it. Clever default: a
chain-wide material (combo with the material library of `kern/werkstoffe`, default steel) plus an optional material
per link that overrides it (column "Werkstoff" in the 1D table, a field per segment/link in the 2D/3D editors; empty =
chain material, shown greyed like the "auto" start values). Links taken from a model keep the material read from STEP;
a link's material can still be changed. Stored in `.3dgkette`/`.3dgkette2d`/`.3dgkette3d` and the project; the
thermal case (two limit temperatures, per-part temperatures) then works for hand-built 2D/3D chains as for 1D
(lengths × α × ΔT on the length components; angles unchanged).

**Planned (requested 2026-10-28): preview of the proposal in 3D.** Before "PMI anlegen", show the proposed
tolerancing in the model. **Datum proposal first:** the proposed datum system (3-2-1) right after the roles are set –
datum features coloured A/B/C with datum flags (triangle + letter) at the faces, per datum the degrees of freedom it
locks (arrows/rings as in the DOF display of the assembly) and the DOF still open, with the reason from
`bezugssystem` as tooltip; changing a role or picking another face as A/B/C updates it live. Then each proposal as a
generated callout (stage 3 dimension lines/frames, marked as preview) at its face, the selected table row highlighted
in the model and vice versa. Live: changing a role, a grade or ticking proposals on/off updates the preview at once
(only the changed callouts are rebuilt); leaving the window or "Verwerfen" removes it, "PMI anlegen" turns the
preview into own PMI. Optional toggle "Toleranzzonen": the zones of the proposed tolerances (§8.5, computed from the
proposal before it becomes PMI – same colours as today, zone of the selected row highlighted), updated live with
grade changes; plus an overlap check of the preview callouts (plan item 7).

**Done 2026-10-28 – manual chains:** "＋ Glied" appends an own link (also without a model), name/nominal/limits
editable by double-click for own links (PMI links stay protected outside the what-if), "－ Entfernen" removes.
**Requested 2026-10-28 for stages 4/5:** 2D and 3D chains and their tolerances must also be buildable by hand,
guided with selection fields (link type, reference, tolerance type from lists instead of free text), good UI.

**Done 2026-10-28 – stage 4 (2D chain, by hand, guided):** `kern/kette2d.py` + window Model › "2D-Toleranzkette …".
Vector loop in a plane: segments with length and angle to the previous segment (first: to X), each with upper/lower
deviation and distribution (spin boxes and lists, templates "right angle 3-4-5" and "lever"); closing quantity from
a list: distance end–start, X or Y component of the closing vector, direction of the last segment. Direct
linearisation: sensitivities by central differences → 1D links with factor |dS/dp| and sign, plus a zero-tolerance
link for the linearisation remainder (S(nominal) − Σ dS/dp·p) so the 1D window reproduces the nominal; "In
Toleranzkette übernehmen" hands them over (requirement, traffic light, histogram, cost optimisation, report all
apply). Non-linear Monte Carlo (all lengths/angles sampled, loop evaluated exactly) shown beside the linear WC/RSS;
checked on the 3-4-5 triangle (sensitivities 0.6/0.8/−24·π/180, linear σ within 5 % of the non-linear one). Live
sketch of the loop with the closing vector. Open: storing 2D chains in a file/project, picking segments from the
model, kinematic adjustments (contact points that slide), stage 5 3D.

**Done 2026-10-28 – stage 5 (3D chain, by hand, guided):** `kern/kette3d.py` + window Model › "3D-Toleranzkette …".
Chain of positions: each link is translation X/Y/Z then rotation about X, Y, Z (degrees, intrinsic, applied after
its translation, i.e. it acts on the following links), each of the six components with deviations (= the small
displacement torsor of the link) and a distribution per link; a function point with direction sits in the last
link. Closing quantity from a list: X/Y/Z position of the point, distance to a target point, angle of the point
direction to a target direction. Same pipeline as 2D: central-difference sensitivities → 1D links with factors +
linearisation remainder → handover to the 1D window; non-linear Monte Carlo per sample. Guided UI: link list (rename
by double-click), 6 × 3 editor (nominal, upper, lower) with units, distribution list, templates "base with arm"
(tilt as lever) and "three stacked plates", "Im 3D zeigen" draws the link origins, axis crosses and the function
point in the model. A distance with nominal ≈ 0 is not differentiable (like a position deviation): sensitivities
vanish, the window warns and points to the non-linear result. Checked: tilt of the base ±0.05° on a 100 mm arm gives
−1.75 mm/° in Z, linear σ within 10 % of the non-linear one. Open: deriving 3D chains from the assembly connections
and the tolerance zones automatically (the assembly variation of §8.20 already covers gap/flush between parts),
storing 2D/3D chains in files and the project.
**Done 2026-10-28 (plan item 2):** `Analyse.als_kette3d` turns an assembly measure into a 3D chain – base glied
"Bezug" aligned to the reference plane/direction of B (closing size = Z), then one glied per moving part on the
connection path B → common mate → A (B side reversed), each the small displacement about the feature point of the
part's first connection with per-component limits from an LP over the clearances to its mates (mates nominal). At
that origin translation and tilt rows decouple: on the example assembly the linearised worst case equals the
assembly analysis exactly (head to lid ±0.03, heads flush ±0.06, lid to plate ±0.1); with the fixing point as origin
the box doubled the tilt lever (±0.24). `Kette3D.basis` places the chain in the model. Remaining: 2D chains and
chains picked directly from model faces without an assembly (stage 2a of 1D covers the 1D case).

**What a functional dimension chain is for** (answer for the user, background for the guide):
- Analysis: does the function (gap, overlap, preload, alignment) hold for the given part tolerances – worst case or
  with a defined risk (ppm)?
- Synthesis: which tolerances can be widened or must be tightened – contribution shares and sensitivities show the
  few links that matter; allocation distributes a target width; statistics allow wider part tolerances than worst
  case at a known risk. So yes: it is the tool to define and to reduce (or relax) single-part tolerances.
- Dimensioning: the chain shows which dimensions must be specified directly on each part (functional dimensions
  instead of accumulated chain dimensions) and which features become datums.

**1D – still missing:** cost-optimal allocation (cost-tolerance model per process, minimum cost subject to WC/RSS
≤ requirement); process capability table (achievable IT grade / Cp per process) to propose values; wiggle of the
closing faces; median planes as chain ends; chains across assembly parts directly from the assembly connections;
Ⓜ bonus treated statistically; form tolerances of contact faces as links; DIN histogram and beta distributions.

**2D/3D – research (literature, not verified by experiment):** vector loops with the direct linearization method
(Chase/Gao/Magleby, basis of CETOL): closed loops of vectors through the contacts, kinematic adjustments (contact
points slide), sensitivities from the Jacobian, then RSS/MC; small displacement torsors (Bourdet/Clément) and the
Jacobian-torsor model (Desrochers) for 3D zones; T-maps (Davidson/Shah) and deviation domains (Giordano) as exact
zone representations; point-based Monte Carlo with locators (3DCS). 3DGmax already has most building blocks: zones as
geometry (§8.5), assembly connections with rows in the small-motion space and the assembly-variation Monte Carlo
(§8.20 stage 4, linear, measures gap/flush).
Plan: (1) 2D vector loop in a section plane: links = vectors between features picked in a section (length and angle
from the geometry, tolerances from PMI), closing quantity length or angle, sensitivities by finite differences of the
loop closure, WC/RSS/MC – reuses the 1D window with an extra "sensitivity" column (already present as factor);
(2) 3D: each toleranced feature gets a torsor bounded by its zone (location/orientation/form, datum shift), the
connections propagate it (existing rows), a measure is a function of the part motions → linear sensitivities, MC with
the existing sampler; contributors per tolerance instead of per connection; (3) wiggle at the worst-case combination.

**From function to ISO GPS – guide and "function logic" (plan):**
1. Function roles per face (picked in 3D): contact/seat, centring/fit, guide, seal, stop, thread, free surface; the
   mating partner comes from the assembly connections.
2. Datum system proposal from the roles (ISO 5459): primary = largest planar seat (3 DOF), secondary = centring
   (2 DOF), tertiary = anti-rotation (1 DOF) – i.e. the 3-2-1 of the assembly.
3. Tolerance type per role (ISO 1101/5458/286): seat – flatness or profile; centring – size with fit (ISO 286 fit
   table by function: clearance/transition/press) plus position/coaxiality to the datums; guide – parallelism/
   straightness; seal – flatness plus surface texture; free surfaces – general tolerance ISO 22081/2768.
4. Values: from the functional requirement through the chains (1D/2D/3D) with cost-optimal allocation and the process
   capability table; plausibility check (§8.22) at the end.
5. Output as semantic PMI written to STEP AP242 (§8.28) – closes the loop to drawings and comparison.
Order: cost-optimal allocation + process table (1D) → function roles and datum proposal → tolerance proposal and
STEP output → 2D vector loop → 3D torsor chain.

### 8.31 Comparison view modes (requested 2026-10-28; as in ZGmax)
Today the comparison shows the new state with status colours and the removed faces of the old one, and the structure
tree shows only the new model. Modes as in ZGmax (Old, New, Comparison, Side by side, Overlay, Blink):
- **Comparison** (default, today's view): new state coloured by status, removed faces of the old state in red.
- **Old** / **New**: only one state; "Highlight changes" (on by default) colours changed/removed resp. changed/new
  faces and highlights changed PMI, off shows the plain model.
- **Overlay**: new state plus the old one transparent in another colour (like manual alignment, not pickable).
- **Side by side**: two 3D views (left old, right new) with **coupled cameras** (rotate, pan, zoom, standard views,
  cube) – both in the coordinate system of the old state, the new one aligned; a selected change highlights its faces
  in both.
- **Blink**: one view switches between old and new (0.3 / 0.6 / 1 / 2 s, ▶/⏸ pause, Space switches by hand) –
  cheap because the second view already exists with the same camera.
- **Structure tree** follows the mode (Old → old tree, otherwise new tree, title says which); stage 2: parts
  coloured by their assembly change status (new/removed/moved/changed), both trees side by side in "Side by side".
- UI: a mode bar above the 3D view while comparing (segmented buttons with the six modes, "Änderungen
  hervorheben", blink speed and ▶/⏸), shortcuts Alt+1 … Alt+6 (1–7 are the standard views), Space in Blink/Old/New.
- Implementation: a second full 3D view for the old state (own scene with PMI graphics and status colours of the old
  state), both in a splitter in the central area; the camera is coupled by a 50 ms check of eye/centre/up/scale
  (works for every camera change incl. the view cube); the second view is created at the first comparison.

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
  Stage 3 done 2026-10-28: distance/thickness dimensions as dimension line with extension lines and arrows outside
  the model, leaders end with an arrow at the nearest point of the face. On a real GPU AIS_TextLabel draws in screen
  pixels (Xvfb/Mesa did not show it): texts in an annotation plane are now glyph faces in model space
  (`Addons.text_to_brep`, `ansicht3d.text_flaechen`). Open: overlap check in the projected view, glyphs into DXF.

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
- Done 2026-10-27 (stage 1, kinematic part): `kern/verbindung.py` – connections plane on plane (with offset) and
  coaxial between part instances, snapping (smallest rotation, translation only along the constrained directions),
  check whether each connection is satisfied, open degrees of freedom as the null space of the small-motion
  constraints (plane: 3 rows, coaxial: 4 rows; mating parts fixed, parts never moved are reference parts), readable
  as translation along / rotation about; wiggle animates each open DOF; part positions shown in the 3D view together
  with explosion and comparison alignment, used by the clash check, stored in the project; dock "Assembly", example.
  Open: point/line contacts, pin–slot, 3-2-1 locating as a template, dragging a part with live snapping, STEP
  kinematics, then tolerances on the connections (stage 3) and the wiggle within tolerances (stage 5).
- Done 2026-10-27 (stages 3/5, linear): clearance per connection (planar ±h along the normal from location/profile
  tolerances of both faces, tilt ±k from all face tolerances over the face size; coaxial radial clearance from the
  diameters incl. size/general tolerances plus position, applied at the ends of the common length, octagon
  approximation of the circle, ≤8 %), editable; worst-case position scatter of each part's bounding-box corners
  by linear programs over all connections at once (restricted to the constrained directions); wiggle within the
  tolerances to the extreme positions, 1:1 or exaggerated.
- Done 2026-10-28 (stage 4, linear; `kern/baugruppe_mass.py`, tab "Measures" in the assembly dock): measures between
  parts – gap (facing parallel planes) and flush (same direction), distance of the face centroid to the reference plane,
  sensitivity c . (x_A - x_B) of the rigid relative motion; worst case by one linear program over all connections
  (motions restricted to the row space, a measure depending on free DOF is flagged "undetermined"); Monte Carlo:
  clearances sampled per connection (normal, clearance = 3σ, clipped; radial play as a point in the disc/ball),
  part motions as a weighted least-squares fit (weight 1/clearance – with over-constraint the tighter connection
  governs; checked: plain least squares let the 0.45 mm radial play leak into a 0.02 mm head contact); requirement
  with share outside and Cp/Cpk; contributors as high-low ranges (only this connection varies, others nominal) and MC
  variance shares; PDF; example. New connection types: pin–slot / line on plane (2 rows at the engagement ends),
  sphere on plane (1 row), ball joint (3 rows). Open: temperature, datum-shift effects, 3-2-1 template, chains
  across parts, measures on axes/points, histogram in the report, one-sided contact instead of symmetric play.
- Done 2026-10-28 (plan item 1 of the evening order): thermal expansion of the measures at one operating temperature
  (`Analyse.waermeverschiebung`: each part expands about its fixing point = centre of its connection features, the
  fixing point follows the mating part along the connection tree; α preset from STEP materials, editable per part),
  traffic light per measure (`bewertung`: green worst case incl. thermal shift within the target, yellow Monte Carlo
  ≤ 0.27 % outside, red otherwise), measures at a clicked point (`Messgroesse.punkt` in file position of part A;
  point to plane / point to axis for any face A), all in the PDF. Still open: datum shift, one-sided contact.
- Done 2026-10-28: clash check at the tolerance limit positions (each connected part at the extremes of its
  clearance, others nominal; only findings that do not exist nominally, worst case per pair). Finding: the symmetric
  ±h of a planar contact lets a lid sink into its seat and the octagon of the radial play (up to 8 % larger) lets a
  shaft penetrate the bore wall slightly – both point to the open item "one-sided contact instead of symmetric play". Directly connected pairs are therefore not reported at the limit
  positions (the connection defines their relative position); only other pairs are.
- Requested 2026-10-28 (next for the assembly dock):
  1. **Reverse a connection** (done 2026-10-28 as "Umkehren": the moved part turns 180° – cylinder/pin end for end
     about an axis across the engagement middle, on a plane about the normal – and "Teile tauschen": the other part
     moves; a plane-side flip would push the part into its mate, so it was not added). Original note: flip a planar connection (part on the other side of the mating plane, normals
     aligned instead of opposed – e.g. washer upside down), flip the axis direction of a coaxial/pin–slot connection
     (part turned end for end); button and context menu "Umkehren" in the connections table, the part is snapped
     again and the open DOF are recomputed; stored in the project.
  2. (Done 2026-10-28 numerically: one field per open DOF, `Baugruppe.bewege_frei`; the 3D gizmo below remains.)
     **Move the selected part with a dragger** while the "Verbindungen" tab is open: a small gizmo at the part
     (arrows for translation, rings for rotation, CATIA-compass-like) that offers **only the open degrees of freedom**
     of that part (null space of its connection rows, `Baugruppe.freiheitsgrade`) – a screw with head contact and
     coaxial shank shows only the ring about its axis, a part with one plane contact two arrows in the plane and the
     ring about the normal. Dragging projects the mouse motion onto the allowed directions, connections stay
     satisfied, positions are stored like snapping; Esc or the original position button resets. Implementation
     notes: AIS_Manipulator exists in OCCT (check it in pythonocc by experiment, otherwise own AIS arrows/rings with
     picking), restrict via its axis/mode flags or by projecting the delta onto the DOF basis each mouse move.
  3. **Wiggle as play/pause:** the checkable "Wiggle" button is not recognizable as a toggle – replace it with
     "▶ Wiggle" that becomes "⏸ Anhalten" while running (same for any other animation toggle).
  4. **Fix: tolerance zones follow the assembled position.** Zones (and general-tolerance zones, bonus zones) are
     drawn at the parts' original file position after snapping/wiggle – apply the part position
     (`ansicht3d.teil_lagen` of the part instance the PMI face belongs to, plus explosion and comparison transform)
     to the zone shapes, and redraw them when positions change. Same cause: part instances share face indices
     (`StepModell.flaechen` deduplicates), so zones of a part used four times appear at one instance only – draw
     them per visible instance. Done 2026-10-28: zones carry their source faces (`Zone.flaechen`, per form
     `quellen`), the display copies them to every visible instance of the owning part (the instance whose face equals
     the canonical face) and applies the assembly position; finding: ownership by bounding box fails for holes with a
     screw inside (the screw's box is smaller).

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
- Done 2026-10-27 (stages 1–3, most of 4): `kern/kollision.py` – pairs all/selected/selected against the rest,
  bounding-box preselection, exact minimum distance with points and intersection volume per pair; clash / contact
  (tolerance) / too close (minimum) / too far (maximum, only A against B); dock "Clashes" with status, comment, CSV,
  background job with cancel; selecting a finding shows the two parts opaque, the intersection red, the distance as a
  line with its value; example in File › Examples. The research on how CATIA/NX present results is still open (no
  vendor documentation read yet); categories follow the request text. Open: intersection curves and penetration
  depth, PDF report and storing results in the project, mesh parts (PRC/STL; triangle tests), stages 5–6.

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
- Done 2026-10-27 (stage 2): point clouds (kern/punktwolke.py: XYZ/ASC/TXT/CSV/PTS incl. decimal comma, PLY with
  points only; best fit on points, colour map as coloured points), alignment to the datum system (`richte_nach_bezug`:
  primary datum fitted in its DOF, secondary/tertiary only in the remaining null space, least squares per datum,
  points preselected near each datum), linear dimensions (two sides by position, best-fit planes or axes) and angular
  dimensions (angle between best-fit planes), inspection report PDF (header, overview, table, one page per NOK/limit
  PMI), exact projection only on PMI faces. Small faces may have too few scan nodes (≥ 6 needed) – reported as "not
  evaluable".
- Open: manual alignment for the scan check (point pairs), tangent/minimax datum contact per ISO 5459 instead of least
  squares, line profile/roundness per section, E57 point clouds.

### 8.24 Demo projects (requested 2026-10-27; stage 1 done the same day)
Done: `kern/beispiele.py` (eleven examples, files looked up in the built app under `programm/beispiele/` or in
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

### 8.27 Part analysis: gears and splines from existing files (requested 2026-10-27, later)
Goal: read the gear data of existing models (STEP B-rep, also meshes) as input for gear design and system analysis
tools (the user names MASTA as an example of a tool that needs these inputs), and check them against the PMI.
- Recognition: the gear axis from the tip/root cylinders (or cones), the teeth from the rotational pattern of the flank
  faces around the axis (number of teeth z = repetitions over 360°), internal or external toothing, spur/helical,
  later bevel, worm and splines (ISO 4156 / DIN 5480).
- Measured values: tip and root diameters da/df, face width b (axial extent of the flanks), helix angle β and hand from
  the twist of a flank along the axis, base diameter db from an involute fit of flank points in a transverse section,
  span measurement Wk over k teeth and dimension over balls/pins computed on the exact geometry.
- Derived values (ISO 21771 definitions): normal module mn, pressure angle αn, profile shift coefficient x (from Wk or
  the tooth thickness), lead; for a gear pair in an assembly the centre distance, contact ratio and backlash.
  Ambiguities (e.g. mn and αn from db alone) are resolved with the tip diameter and standard modules, and reported.
- Output: table per gear (values, how each was found, uncertainty), CSV/JSON for the import into gear tools, comparison
  with the PMI/notes (e.g. "z = 32, mn = 2" in a note) as part of the plausibility check (§8.22).
- Research first: which inputs gear/system tools expect (module, angles, profile shift, tolerances per ISO 1328,
  flank modifications) and which can be measured on nominal CAD data at all (modifications are often not modelled).
- Test data: self-generated involute gears (spur and helical, external and internal, with profile shift) built with
  OCCT, so the true values are known and the files are licence-free.
- Done 2026-10-28 (stage 1, `kern/verzahnung.py`, Tools › Recognise gears): axis from the principal inertia axis
  (cylinder axis preferred), transverse sections from one fine mesh of the part (fast also for faceted models and
  meshes), z from the dominant harmonic of r(θ) (≥ 90 % of the variation in its multiples, z ≥ 5), b by bisection
  of the toothed sections, β and hand from the phase drift of the tooth harmonic along the axis, db from an involute
  fit per flank side (points above the base circle only), mn/αn by the nearest ISO 54 module over the usual pressure
  angles, x from the tooth thickness (internal: space width) at d, Wk per ISO 21771; rejected when the flanks are not
  involute (fit > 3 % of the tooth height) or the tooth height is not 1.5–3 mn (hexagons, knurls). Test generator
  `werkzeuge/zahnrad.py`; on five test gears mn within 0.1 %, x within 0.01, β within 0.003°.
  Gear pairs done the same day (`verzahnung.paare`: parallel axes, same mn/αn/β, distance within 20 % of the
  reference; a without backlash from inv αwt, εα, εβ, normal backlash 2 Δa sin αn). Notes vs geometry done
  (`plausibilitaet.verzahnung`). Open: splines (ISO 4156), bevel/worm, tooth thickness tolerances.

### 8.28 Writing STEP AP242 with semantic PMI (research 2026-10-27, by experiment)
Findings (pythonocc-core 8.0.1.2 and OCP 8.0.1.1, both on OCCT 8.0.1; scripts were throw-away):
- The old note "writing new-style dimensions segfaults" was wrong in its cause: the writer crashed because the schema
  was still AP214 – `Interface_Static.SetCVal("write.step.schema", "AP242DIS")` only takes effect after a
  `STEPCAFControl_Writer` was created (before, the parameter does not exist and the call returns False).
- pythonocc with AP242: dimensions with tolerances (`XCAFDoc_Dimension` + `XCAFDimTolObjects_DimensionObject`) and
  datums (`XCAFDoc_Datum`) are written (DIMENSIONAL_SIZE, PLUS_MINUS_TOLERANCE, DATUM_FEATURE, DATUM,
  GEOMETRIC_ITEM_SPECIFIC_USAGE) and read back correctly by our reader (⌀10 +0.1/0 on the hole, datum A).
- pythonocc cannot write geometric tolerances: `XCAFDoc_GeomTolerance` is an empty class (no `Set`, no methods).
- OCP (CadQuery's bindings, Apache-2.0) wraps it: flatness was written and read back. OCP exists only for Python 3.13
  on conda-forge and brings its own OCCT copy (two OCCT builds in one process are not an option; a helper process
  would double the app size). OCP lacks `TDF_LabelSequence`, so datums cannot be linked to tolerances from it either.
  The lower deviation came back with the wrong sign (−0.1 → +0.1): the sign convention of `SetLowerTolValue` has to
  be checked before relying on it.
Plan (recommended): pythonocc XCAF for geometry, dimensions and datums; then our own P21 post-processing appends the
geometric tolerances (FLATNESS_TOLERANCE … POSITION_TOLERANCE, GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE, DATUM_SYSTEM,
DATUM_REFERENCE_COMPARTMENT, modifiers, values with units) to the SHAPE_ASPECTs/DATUMs OCCT wrote, following the
CAx-IF recommended practice for PMI; validated by reading back with our reader and with OCCT's XCAF reader. Use cases:
save own/edited PMI, semantic PMI derived from graphical-only PMI (after review), PMI edited in the advisor.
Alternatives: QIF export (own XML writer, also the exchange format for CMM software); ask pythonocc to wrap
`XCAFDoc_GeomTolerance` (upstream issue).
- Experiment 2026-10-28: the OCCT round trip (read with GD&T mode into XCAF, write AP242) is lossy – NIST FTC-10 81 → 69
  semantic PMI (datum targets gone, some diameters/positions merged), CTC-01 changes dimension types. So existing PMI
  must not go through XCAF.
- Done 2026-10-28 (stage 1, `kern/step_schreiben.py`, File › Save STEP with edited PMI): edited values are written by
  replacing only the numbers of their measure entities in the original text (tolerance magnitude, 'nominal value' /
  'upper limit' / 'lower limit', TOLERANCE_VALUE bounds; file units), the rest of the file stays byte-identical;
  report for fit class, material condition, values without counterpart, shared measure entities; hint that the
  polyline presentation still shows the old values.
- Done 2026-10-28 (stage 2): own PMI appended before the end of DATA like the NIST files (SHAPE_ASPECT + GISU per
  face, simple or complex tolerance entities with sorted parts, DATUM_SYSTEM/DATUM_REFERENCE_COMPARTMENT, modifiers,
  TOLERANCE_ZONE for ⌀, DIMENSIONAL_SIZE/LOCATION with SHAPE_DIMENSION_REPRESENTATION and PLUS_MINUS_TOLERANCE,
  DATUM_FEATURE + DATUM + SHAPE_ASPECT_RELATIONSHIP); read back by our reader and by OCCT XCAF (CTC-01: +1 dim,
  +2 tol, +1 datum); angular size/location added the same day. Assemblies done the same day (PDS, representation and units per
  part from the faces). Open: PMI across parts (assembly-level), presentation for written PMI. Fit class and material condition edits of
  existing PMI done (simple tolerance entities are rewritten in complex form with GEOMETRIC_TOLERANCE_WITH_MODIFIERS).

### 8.29 Test strategy: run only the affected tests (requested 2026-10-27)
The full suite takes ~25–28 min (180 tests, many load NIST models, compare, check scans or open the window). Rule
from now on (CLAUDE.md): before a commit run only the tests affected by the change; the full suite only before a
release, after changes to core modules and in CI.
- Done: `werkzeuge/tests_betroffen.py` / `pixi run test-betroffen` – changed files (git diff + untracked) →
  test functions whose source mentions the changed module, fixed mappings for broad modules (hauptfenster,
  ansicht3d, laden, p21, pmi_lesen, lader, thema) and for i18n/manual/changelog; changed test files run completely;
  `--seit <ref>` and `--zeigen`.
- Done 2026-10-28 (local): durations measured on the Mac (full suite 588 s, 182 tests): six tests over 30 s
  (`test_beispiele_modell` 60 s, `test_scan_gegen_toleranzen` 40 s, `test_scanpruefung_stufe2` 40 s,
  `test_toleranzkette_lage_pdf_projekt` 39 s, `test_scanpruefung_punktwolke_bezug_bericht` 37 s,
  `test_beispiele_vergleich_und_scan` 33 s, together ~250 s) carry `@pytest.mark.langsam` (registered in
  `pytest.ini`); `pixi run test-schnell` runs `-m "not langsam"`, `test-betroffen -- --schnell` skips them too;
  `test-ci` stays the full run in the GitHub workflow.
- Open: shorten the slowest tests (smaller scan samples, session fixtures for loaded models/comparisons).

### 8.30 UI/UX review and plan (requested 2026-10-27, to do locally)
Inventory 2026-10-27: 129 menu commands (File 41, View 49, Model 20, Tools 5, Window 10, Help 4), 10 side panels
(Structure, Saved views, PMI, Measure, Analysis, Comments, Changes, Scan check, Clashes, Assembly), one toolbar with
~12 entries. Functions are hard to find, the View menu is overloaded, panels compete for the same space.
Target users, none of them overwhelmed: experienced CATIA designers (expect CATIA navigation, tree, compass-like
cube, context menus), 3DCS users (expect a model/moves/tolerances/measures workflow and result tables), metrology
staff (expect alignment, characteristics, reports), laypeople and students (need guidance, plain words, examples).
Write `docs/UI_UX_Plan.md` (English) with:
1. Review of the current UI against these personas (task walkthroughs: open and read PMI, compare two states, check a
   scan, build a stack-up, assemble and wiggle), concrete problems with screenshots from `packaging/doc_screenshots.py`.
2. Alternatives with pros/cons and effort: (a) workspaces/task tabs at the top ("View · Check · Compare · Tolerances ·
   Assembly · Scan") that show only their panels and commands; (b) ribbon like CATIA/Office; (c) one context
   inspector panel plus a command palette (Ctrl/⌘+K) like modern design tools; (d) guided task wizards for beginners on
   top of (a). Progressive disclosure: simple/expert mode, defaults that work, advanced options folded.
3. Recommendation (expected: (a) + command palette + task start page with the examples; CATIA shortcuts kept),
   consistent panel layout (header with purpose, inputs, primary button, result table, export row), wording and
   icon rules, empty states that say what to do, keyboard map.
4. Staged implementation plan with measurable acceptance (time per task, clicks, first-use success with students),
   and a short usability test protocol for the local test.
- Done 2026-10-28: `docs/UI_UX_Plan.md` (inventory 125 commands / 10 panels, problems, personas and walkthroughs,
  options (a)–(d), recommendation workspaces + command palette + task start page, stages 1–3 with acceptance,
  test protocol); stage 1 implemented: command search Ctrl/⌘+K (`ui/befehle_ui.py`, German and English text, menu
  path, shortcut, disabled commands greyed), start page with open / compare / examples and the format list, menu
  cleanup. Open: play/pause toggles (stage 1 item 4), stage 2 workspaces, stage 3 inspector and guided flows, the
  usability test.

