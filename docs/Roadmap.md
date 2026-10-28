# 3DGmax – Roadmap

✅ done · 🟡 partial · ⬜ planned · 💡 idea/later (scope to be defined)

## Viewing
| Feature | Status |
|---|---|
| Load STEP AP242/AP214/AP203 (background, cancel, drag and drop, recent files) | ✅ |
| Assembly tree: show/hide, isolate, transparent, auxiliary geometry | ✅ |
| Navigation CATIA style (default) and classic, trackpad, standard views, pivot/view center | ✅ |
| Pivot stays fixed during zoom/pan, shown as line cross while orbiting/panning | ✅ |
| Display shaded/with edges/wireframe, light/dark, custom background colors | ✅ |
| Saved views: camera, window, PMI per view, browse (◀ ▶), search | ✅ |
| Saved views with section planes (AP242 multi-clipping incl. union/intersection) – PLAN §8.25 | ✅ |
| Thumbnails per saved view (HLR edge drawing with PMI, background), small by default, large or off | ✅ |
| Section X/Y/Z, at selected face/edge, from view direction, slider | ✅ |
| Clipping box around the selection | ✅ |
| Focus mode: everything except the selection translucent (faces, PMI, tree parts) | ✅ |
| Multiple section planes (up to three, union or common region), section contour export SVG/DXF/PDF | ✅ |
| Section views from the model (hatched section in drawings) | ✅ |
| 3D selection of faces/edges (multiple), context menu, zoom to selection, align normal (upright: edges level, annotations readable), flip view | ✅ |
| View cube with axes (chamfered edges/corners, click aligns, drag rotates) | ✅ |
| Wireframe: click through to hidden edges | ✅ |
| Large assemblies: tessellation cache, levels of detail | ⬜ |
| Model properties: volume, area, mass (density), center of gravity, overall size, file header | ✅ |
| Anti-aliasing, sans-serif labels, subtle view cube; window/panel/column layout remembered | ✅ |
| Camera: perspective/orthographic, view back/forward | ✅ |
| Smooth camera transitions | ✅ |
| Hide selected in 3D, tree search; 3D PMI follows list filter | ✅ |
| Exploded view (slider), parts list (BOM) with quantity, volume, mass, CSV | ✅ |
| Exploded view by assembly levels (staged), BOM with part number | ✅ |
| BOM with material property (STEP) and material density | ✅ |
| Exploded view along axes (X/Y/Z) | ✅ |
| Analyses: draft angle, curvature radius, wall thickness map (value on click) | ✅ |

## PMI
| Feature | Status |
|---|---|
| Semantic PMI: dimensions, geometric tolerances, datums, datum targets, notes | ✅ |
| Graphical PMI from the file, placeholder texts generated from semantics | ✅ |
| PMI ↔ face in both directions, select datums / tolerances using a datum | ✅ |
| List with name, views, search, filter, context menu; count in current view | ✅ |
| Table columns: move, show/hide; ISO GPS columns (characteristic, nominal, deviations, limits, size tolerance, class, zone, material condition) | ✅ |
| Limits from ISO 286 tolerance classes (holes C–S, shafts c–s, IT1–IT18, up to 500 mm; cross-checked) | ✅ |
| ISO 286: letters a/A, j/J (j5–j7, J6–J8), fits as pair (H7/g6) with clearance and type | ✅ |
| ISO 286: letters b, t–zc, sizes above 500 mm (needs a verifiable free source) | ⬜ |
| Standard awareness ASME Y14.5 / ISO GPS (detect, fallback ISO, per-model override, terms, rule, envelope note) | ✅ |
| ISO 14405 modifier display | ✅ |
| Standard- and geometry-dependent check rules (stage 1) | ✅ |
| PMI color: high contrast / from file / custom | ✅ |
| PMI export CSV (values, datums, face IDs, views) | ✅ |
| Plausibility check (unused/missing datums, without face/view, duplicates, rules) | ✅ |
| Targeted search (`datum:A`, `value:0.5`, `type:position`, `view:`, `name:`, `no:`, `balloon:`) | ✅ |
| Surface texture (roughness), weld symbols | ⬜ |
| Make graphical PMI searchable (OCR on rendered annotations) | 💡 |
| Graphical-only PMI evaluated in the table (kind from PRC markup type/name, values/deviations/zone/Ⓜ/datums from text), marked as derived | ✅ |
| Graphical PMI with stroked text (PRC, STEP tessellated): values via OCR | 💡 |
| Semantic-only PMI: optional generated display in the view (see generated PMI stage 2) | ✅ |
| Show tolerance zones as envelope surfaces (offsets ±t/2, ⌀ zone cylinder, exaggeration) | ✅ |
| Tolerance zones stage 2: unequal zones (UZ/Ⓤ), projected zones, Ⓜ/Ⓛ bonus zone, space of the surface (size + location), size envelopes, patterns per feature | ✅ |
| Tolerance zones for the selected PMI, the selected faces or all PMI at once; general tolerances (ISO 2768-1/-2, ISO 22081) as a toggle, for the whole model or only at selected faces without PMI | ✅ |
| Zone of the derived median plane (slots/tabs), spherical zone (S⌀), context menus | ✅ |
| Tolerance zones in the datum system: coaxiality/runout around the datum axis, datum shift with Ⓜ/Ⓛ, form/orientation inside the higher-level zone | ✅ |
| Tolerance zones for linear dimensions between planes and angular dimensions | ✅ |
| Tolerance zones: line profile/roundness per section, ACS/ALS, CZ/SZ, tolerances on edges/points | ⬜ |
| Tolerance stack-up 1D (dimension chain from PMI, worst case, RSS, Monte Carlo, CSV) | ✅ |
| Stack-up 1D: Cp adjustable, angular dimensions excluded | ✅ |
| Stack-up: chain picked in 3D (planes, cylinder/cone axes) with direction from the geometry, PMI values (also patterns) and ISO 2768 for features without PMI; distribution and Cp per link; contribution share | ✅ |
| Stack-up: location tolerances of the end faces as links (position, symmetry, coaxiality, profile with datum, UZ), PDF report, chain in the project | ✅ |
| Stack-up 1D final: Ⓜ/Ⓛ bonus, datum shift, edges as chain ends, mean offset (Cpk), requirement with Cp/Cpk/share outside | ✅ |
| Stack-up stage 3: triangular/trapezoidal distributions by production type, applicable method in bold (≥ 4 effective contributors), what-if with comparison to actual, direction by double-click, result table, share bars, histogram, PDF | ✅ |
| Stack-up stage 3b: thermal expansion (materials from STEP/library, per-part temperatures), length ranges and adjusting member, directions from the closing dimension, walk chain, chain file .3dgkette, gearbox example | ✅ |
| Stack-up stage 4: modified RSS (Bender), mean-shift model, sensitivity factor per link, tolerance allocation (equal variance / proportional) | ✅ |
| Stack-up: distribution fitted from measured values (paste/CSV) | ✅ |
| Stack-up: several saved what-if scenarios with comparison | ✅ |
| Stack-up: correlated links (groups with ρ, covariances, rank-correlated Monte Carlo) | ✅ |
| Stack-up: folded normal and Rayleigh distributions (form/runout/position) | ✅ |
| Stack-up: more distributions (beta, DIN histogram) | 💡 |
| Stack-up: link shown as a line in 3D while walking the chain | ✅ |
| Stack-up: wiggle of the closing faces by the worst-case extremes | ⬜ |
| Stack-up: median planes as chain ends, chains across assembly parts | ⬜ |
| Assembly: connections plane/plane and coaxial with snapping, satisfied check, open DOF per part, DOF wiggle, in the project | ✅ |
| Assembly: point contact (sphere on plane), pin–slot (line on plane), ball joint | ✅ |
| Assembly: reverse a connection (180°, cylinder end for end) and swap parts | ✅ |
| Assembly: wiggle as play/pause button | ✅ |
| Fix: tolerance zones follow the assembled part position and appear at every instance | ✅ |
| All tolerance / general-tolerance zones only for visible parts | ✅ |
| UI/UX plan (`docs/UI_UX_Plan.md`); stage 1: command search Ctrl/⌘+K, task start page, menu cleanup | ✅ |
| UI scaling option (90–150 %, as in ZGmax) | ✅ |
| UI/UX stage 2: workspaces; stage 3: inspector and guided flows | ⬜ |
| Assembly: move the selected part only along its open DOF (numeric fields per DOF) | ✅ |
| Assembly: 3D dragger (gizmo with arrows and rings) for the same moves | ⬜ |
| Assembly: 3-2-1 template, dragging with live snapping, STEP kinematics | ⬜ |
| Tolerance stack-up 3D (geometric tolerances, chain from the model, sensitivity) – PLAN §8.20 | ⬜ |
| Assemblies built in the project (mates on datum features), materials and thermal expansion in chains | ⬜ |
| Wiggle within tolerances (assembly connections, extreme positions, 1:1 or exaggerated); worst-case position scatter per part | ✅ |
| Assembly variation: measures between parts (gap/flush), worst case and Monte Carlo over all connections, requirement with Cpk/share outside, contributor ranking, PDF, example | ✅ |
| Assembly variation: temperature, datum shift, chains across parts, measures on axes/points, histogram | ⬜ |
| Bill of characteristics with balloon numbers (table column, 3D balloons, CSV, PDF) | ✅ |
| Datum reference frame display for a selected tolerance | ✅ |
| Create PMI with tolerancing advisor (stage 1: rules per selection, own PMI in project) | ✅ |
| Edit existing PMI (values, fit, material condition; saved in the project) | ✅ |
| Write PMI back to STEP AP242 (dimensions/datums via OCCT, geometric tolerances via own P21 writer – PLAN §8.28), advisor stage 2 | ⬜ |

## Measuring
| Feature | Status |
|---|---|
| Distance, angle, radius/Ø, wall thickness, coordinates; snapping; list, CSV, copy | ✅ |
| Quick measure in the status bar for the selection (length, Ø/R, area, distances, axis distance, angle, PMI info) | ✅ |
| Own views (camera, PMI, measurements) in project and PDF; measurement report PDF | ✅ |

## Comparison
| Feature | Status |
|---|---|
| Alignment: same position, best fit (ICP), manual point pairs with snapping (UI) | ✅ |
| Geometry: equal/changed/new/removed per face, exact (B-rep) with mesh preselection | ✅ |
| Semantic PMI comparison (field by field incl. name, datums, faces), "geometry under PMI changed" | ✅ |
| Change list, review walk-through, comment, review report with SHA-256 | ✅ |
| Export changes (CSV) | ✅ |
| Deviation color map (scale, tolerance limit, sign, value on click) | ✅ |
| Display like CATIA Compare Products: added/removed volume (exact, Boolean) | ✅ |
| Detect moved elements (translation) and moved PMI | ✅ |
| Detect rotated/mirrored elements (angle and axis, mirror plane) | ✅ |
| Graphical PMI comparison: moved or reshaped presentation of equal PMI | ✅ |
| Graphical-only PMI (notes) matched and compared by text | ✅ |
| Assembly comparison (parts new/removed/moved/changed/renamed) | ✅ |
| Change table with characteristic, old, new, Δ, tendency (tighter/looser), also in PDF/CSV | ✅ |
| Comparison modes: comparison, old, new, overlay, side by side (coupled cameras), blink; tree follows the mode | ✅ |
| Comparison modes stage 2: tree with part status colours | ✅ |
| Comparison: both trees side by side in "Side by side" | ✅ |
| Geometry comparison per part instance (each instance sampled; status shown on the shared faces) | ✅ |
| Status colors per instance in the 3D view (instance key: face index + location), removed instances shown | ✅ |
| Change list entries per instance | ✅ |
| Meshes: STL/OBJ/glTF/3MF vs. CAD and mesh vs. mesh (alignment, color map) | ✅ |
| PLY meshes from scanners | ✅ |
| Scan against PMI tolerances: best fit + fine alignment, per-PMI evaluation (form, profile, location, axes, sizes, Ⓜ/Ⓛ bonus), colour map over CAD, CSV (PLAN §8.23) | ✅ |
| Scan check stage 2: 3-2-1 alignment to the datum system, inspection report PDF, linear/angular dimensions, point clouds (XYZ/ASC/CSV/PTS/PLY) | ✅ |
| Scan check: manual alignment by point pairs | ✅ |
| Scan check: ISO 5459 tangent datums, per-section evaluation, E57 | ⬜ |
| Plausibility check of the specification stage 1: hierarchy, size vs. form, completeness, datum system, contradicting dimensions, values, nominal vs. geometry (PLAN §8.22) | ✅ |
| Plausibility check stage 2: closed dimension chains | ✅ |
| Plausibility check: basic dimensions (with tolerance, location toleranced twice), patterns of different size, datum target counts | ✅ |
| Point clouds without triangles (PLY points, XYZ/ASC/CSV/PTS) | ✅ |
| Point clouds E57 | ⬜ |
| Linked side-by-side view of old and new state (synchronized cameras) | ✅ |
| Clash/contact/clearance analysis of assemblies or selections (PLAN §8.21 stages 1–3) | ✅ |
| Band analysis (min/max distance), intersection volumes, result list with status/comment, CSV | ✅ |
| Clash: intersection curves, penetration depth, PDF report, results in the project | ✅ |
| Clash: mesh parts (PRC/STL) and mixed pairs (approximate) | ✅ |
| Gear and spline analysis of existing files (z, mn, αn, β, b, x, Wk; pairs) as input for gear tools – PLAN §8.27 | ⬜ |
| Wiggle in the open degrees of freedom (kinematic) | ✅ |
| Clash check at the tolerance limit positions (assembly) | ✅ |
| Clash check over joint ranges (open DOF): free range per DOF up to the first collision | ✅ |

## Reports and exchange
| Feature | Status |
|---|---|
| PDF: one page per saved view with view name, model name, PMI (columns as visible in the PMI list) | ✅ |
| PDF comparison report (overview, change list, image per change) | ✅ |
| PMI change table PDF for suppliers/production | ✅ |
| Project container (ZIP with models, review status, comments, measurements) | ✅ |
| Folder comparison | ✅ |
| Export views as drawings (HLR) PDF/SVG/DXF: standard views by projection method, current view, saved views with their PMI | ✅ |
| Drawings and view thumbnails for mesh models (face borders, silhouettes, hidden edges via depth buffer) | ✅ |
| Generate graphical PMI from semantic PMI – stage 1: leader + label, stacked, own color (3D, drawings) | ✅ |
| Generated PMI stage 2: annotation planes (saved view or model plane), frames/datum symbols as vector graphics, overlap-free layout outside the model, show/hide switch | ✅ |
| Generated PMI stage 3: dimension lines with arrows and extension lines, layout avoiding projected overlaps per view | ⬜ |
| Drawing: sheet formats A4–A0 with frame, title block and standard scales | ✅ |
| Drawing: dimensions/frames as DXF dimension entities | ⬜ |
| Annotate: comments/questions/change proposals on faces and PMI, markers, status, project, CSV/PDF | ✅ |

## Formats
| Format | Status |
|---|---|
| STEP AP242/AP214/AP203 | ✅ |
| QIF 3.0: exact B-rep and semantic PMI (validated against STEP for NIST CTC-01/FTC-06) | ✅ |
| QIF: graphical PMI (PMIDisplaySet: texts with symbols, frames, leaders, witness lines, polylines, areas) and saved views (camera, visible PMI) | ✅ |
| QIF: measurement results, measurement plan | ⬜ |
| IGES, STL, OBJ, glTF/GLB, 3MF, PLY (meshes: view, measure, analyze, compare against CAD) | ✅ |
| JT 8/9 via TKJT converter jt2glb (mesh, structure, names, colours), build variant DG_MIT_JT=1; JT 10 detected and reported | 🟡 (step 7; end-to-end test needs a JT 9 file) |
| JT 10, PMI from JT, JT B-rep (XT) | ⬜ |
| 3D PDF / PRC stage 1–3: structure, schema, tessellation as colored mesh, markups as graphical PMI, saved views with camera (own reader, PLAN §8.15; NIST STC PDFs downloaded in tests) | ✅ |
| 3D PDF / PRC: model edges from the tessellation wire indices shown in the edge layer | ✅ |
| 3D PDF / PRC: highly compressed tessellation, exact B-rep, semantic PMI from markup user data; U3D | ⬜ |
| STEPZ (zipped or gzip STEP) | ✅ |
| STEP-XML (ISO 10303-28) and other open CAD formats | ⬜ |
| CATIA V5/V6 CATPart/CATProduct | 💡 (only via licensed SDK or CATIA exports; legal review first) |

## Operation
| Feature | Status |
|---|---|
| Manual DE/EN with generated screenshots (packaging/doc_screenshots.py), opened in the browser | ✅ |
| German/English UI, F1 manual with generated menu reference, introduction, what's new | ✅ |
| Portable apps Windows/macOS/Linux, GitHub workflow with/without tests, self-test | ✅ (all three verified by the user) |
| Start screen before the main window (PyInstaller splash on Windows/Linux, Qt splash) | ✅ |
| Release script: bump version, keep changelog DE/EN | ✅ |
| Tests: core, offscreen UI, stress test, on-screen test | ✅ |
| Examples for the main functions (File › Examples, free test data, no copies in the repository) – PLAN §8.24 | ✅ |
| Several models side by side: File › New window, open in new window, linked cameras – PLAN §8.26 | ✅ |
| Wireframe with high-contrast edges (setting, default on); calmer, more legible view cube | ✅ |
| Status-bar progress with Cancel for all background jobs (load, compare, analysis, colour map, material, scan) | ✅ |
| Closable tabs of stacked side panels; smooth side-panel resizing (batched 3D buffer resize) | ✅ |
