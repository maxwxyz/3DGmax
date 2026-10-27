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
| Thumbnails per saved view (HLR edge drawing with PMI, background) | ✅ |
| Section X/Y/Z, at selected face/edge, from view direction, slider | ✅ |
| Clipping box around the selection | ✅ |
| Multiple section planes (up to three, union or common region), section contour export SVG/DXF/PDF | ✅ |
| Section views from the model (hatched section in drawings) | ⬜ |
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
| Exploded view along axes, BOM with material property | ⬜ |
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
| ISO 286: letters a, b, j, t–zc, sizes above 500 mm, fits H7/g6 as pair | ⬜ |
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
| Tolerance zones: datum-oriented zones, unequal/offset zones (UZ), projected zones, material conditions | ⬜ |
| Tolerance stack-up 1D (dimension chain from PMI, worst case, RSS, Monte Carlo, CSV) | ✅ |
| Tolerance stack-up 3D (geometric tolerances, chain from the model, sensitivity) | 💡 |
| Bill of characteristics with balloon numbers (table column, 3D balloons, CSV, PDF) | ✅ |
| Datum reference frame display for a selected tolerance | ✅ |
| Create PMI with tolerancing advisor (stage 1: rules per selection, own PMI in project) | ✅ |
| Edit existing PMI (values, fit, material condition; saved in the project) | ✅ |
| Write PMI back to STEP AP242, advisor stage 2 (DRF consistency, fits from mating parts) | ⬜ |

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
| Geometry comparison per part instance (each instance sampled; status shown on the shared faces) | ✅ |
| Status colors per instance in the 3D view (instance key: face index + location), removed instances shown | ✅ |
| Change list entries per instance | ⬜ |
| Meshes: STL/OBJ/glTF/3MF vs. CAD and mesh vs. mesh (alignment, color map) | ✅ |
| PLY meshes from scanners | ✅ |
| Point clouds without triangles (PLY points, XYZ, E57) | ⬜ |

## Reports and exchange
| Feature | Status |
|---|---|
| PDF: one page per saved view with view name, model name, PMI | ✅ |
| PDF comparison report (overview, change list, image per change) | ✅ |
| PMI change table PDF for suppliers/production | ✅ |
| Project container (ZIP with models, review status, comments, measurements) | ✅ |
| Folder comparison | ✅ |
| Export views as drawings (HLR) PDF/SVG/DXF: standard views by projection method, current view, saved views with their PMI | ✅ |
| Drawings and view thumbnails for mesh models (face borders, silhouettes, hidden edges via depth buffer) | ✅ |
| Generate graphical PMI from semantic PMI – stage 1: leader + label, stacked, own color (3D, drawings) | ✅ |
| Generated PMI stage 2: annotation planes (saved view or model plane), frames/datum symbols as vector graphics, overlap-free layout outside the model, show/hide switch | ✅ |
| Generated PMI stage 3: dimension lines with arrows and extension lines, layout avoiding projected overlaps per view | ⬜ |
| Drawing: dimensions/frames as DXF dimension entities, sheet formats and scales | ⬜ |
| Annotate: comments/questions/change proposals on faces and PMI, markers, status, project, CSV/PDF | ✅ |

## Formats
| Format | Status |
|---|---|
| STEP AP242/AP214/AP203 | ✅ |
| QIF 3.0: exact B-rep and semantic PMI (validated against STEP for NIST CTC-01/FTC-06) | ✅ |
| QIF: graphical PMI (PMIDisplaySet: texts with symbols, frames, leaders, witness lines, polylines, areas) and saved views (camera, visible PMI) | ✅ |
| QIF: measurement results, measurement plan | ⬜ |
| IGES, STL, OBJ, glTF/GLB, 3MF, PLY (meshes: view, measure, analyze, compare against CAD) | ✅ |
| JT via TKJT (GPL v2+), build with/without TKJT | ⬜ (step 7) |
| 3D PDF / PRC stage 1–3: structure, schema, tessellation as colored mesh, markups as graphical PMI, saved views with camera (own reader, PLAN §8.15; NIST STC PDFs downloaded in tests) | ✅ |
| 3D PDF / PRC: model edges from the tessellation wire indices shown in the edge layer | ✅ |
| 3D PDF / PRC: highly compressed tessellation, exact B-rep, semantic PMI from markup user data; U3D | ⬜ |
| STEPZ (zipped or gzip STEP) | ✅ |
| STEP-XML (ISO 10303-28) and other open CAD formats | ⬜ |
| CATIA V5/V6 CATPart/CATProduct | 💡 (only via licensed SDK or CATIA exports; legal review first) |

## Operation
| Feature | Status |
|---|---|
| German/English UI, F1 manual with generated menu reference, introduction, what's new | ✅ |
| Portable apps Windows/macOS/Linux, GitHub workflow with/without tests, self-test | 🟡 (macOS verified locally) |
| Release script: bump version, keep changelog DE/EN | ✅ |
| Tests: core, offscreen UI, stress test, on-screen test | ✅ |
