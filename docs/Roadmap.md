# 3DGmax – Roadmap

✅ done · 🟡 partial · ⬜ planned · 💡 idea/later (scope to be defined)

## Viewing
| Feature | Status |
|---|---|
| Load STEP AP242/AP214/AP203 (background, cancel, drag and drop, recent files) | ✅ |
| Assembly tree: show/hide, isolate, transparent, auxiliary geometry | ✅ |
| Navigation CATIA style (default) and classic, trackpad, standard views, pivot/view center | ✅ |
| Display shaded/with edges/wireframe, light/dark, custom background colors | ✅ |
| Saved views: camera, window, PMI per view, browse (◀ ▶), search | ✅ |
| Thumbnails per saved view | ⬜ |
| Section X/Y/Z, at selected face/edge, from view direction, slider | ✅ |
| Multiple section planes, clipping box, section views from the model, section contour as view | ⬜ |
| 3D selection of faces/edges (multiple), context menu, zoom to selection, align normal | ✅ |
| Large assemblies: tessellation cache, levels of detail | ⬜ |

## PMI
| Feature | Status |
|---|---|
| Semantic PMI: dimensions, geometric tolerances, datums, datum targets, notes | ✅ |
| Graphical PMI from the file, placeholder texts generated from semantics | ✅ |
| PMI ↔ face in both directions, select datums / tolerances using a datum | ✅ |
| List with name, views, search, filter, context menu; count in current view | ✅ |
| PMI color: high contrast / from file / custom | ✅ |
| PMI export CSV (values, datums, face IDs, views) | ✅ |
| Plausibility check (unused/missing datums, without face/view, duplicates, rules) | ✅ |
| Targeted search (`datum:A`, `value:0.5`, `type:position`) | ⬜ |
| Surface texture (roughness), weld symbols | ⬜ |
| Make graphical PMI searchable (OCR on rendered annotations) | 💡 |
| Convert graphical PMI into semantic PMI | 💡 |
| Show tolerance zones as envelope surfaces (incl. datums, unequal zones) | 💡 |
| Tolerance stack-up analysis (dimension chains, worst case, RSS, Monte Carlo) | 💡 |
| Bill of characteristics with balloon numbers | 💡 |

## Measuring
| Feature | Status |
|---|---|
| Distance, angle, radius/Ø, wall thickness, coordinates; snapping; list, CSV, copy | ✅ |
| Save measurement as view, measurements in reports | ⬜ |

## Comparison
| Feature | Status |
|---|---|
| Alignment: same position, best fit (ICP), three point pairs (core) | 🟡 (point pairs without UI) |
| Geometry: equal/changed/new/removed per face, exact (B-rep) with mesh preselection | ✅ |
| Semantic PMI comparison (field by field, datums, faces), "geometry under PMI changed" | ✅ |
| Change list, review walk-through, comment, review report with SHA-256 | ✅ |
| Export changes (CSV) | ✅ |
| Deviation color map (scale, tolerance limit, sign) | ⬜ |
| Display like CATIA Compare Products: added/removed volume, visual (fast) and exact | ⬜ |
| Detect moved elements and moved PMI | ⬜ |
| Graphical PMI comparison (moved, changed, new, removed) | ⬜ |
| Assembly comparison | ⬜ |
| Meshes: STL/OBJ vs. CAD, mesh vs. mesh, fit and compare 3D scans | ⬜ |

## Reports and exchange
| Feature | Status |
|---|---|
| PDF: one page per saved view with view name, model name, PMI | ✅ |
| PDF comparison report (overview, change list, image per change) | ✅ |
| PMI change table PDF for suppliers/production | ✅ |
| Project container (ZIP with models, review status, comments, measurements) | ✅ |
| Folder comparison | ✅ |
| Export views as drawings (HLR) PDF/SVG/DXF | ⬜ |
| Annotate: comments/change proposals on faces, PMI (list and model), changed geometry | ⬜ |

## Formats
| Format | Status |
|---|---|
| STEP AP242/AP214/AP203 | ✅ |
| QIF | ⬜ |
| IGES, STL, OBJ, glTF/GLB, 3MF | ⬜ |
| JT via TKJT (GPL v2+), build with/without TKJT | ⬜ (step 7) |
| 3D PDF (U3D/PRC) | ⬜ (sample files missing) |

## Operation
| Feature | Status |
|---|---|
| German/English UI, F1 manual with generated menu reference, introduction, what's new | ✅ |
| Portable apps Windows/macOS/Linux, GitHub workflow with/without tests, self-test | 🟡 (macOS verified locally) |
| Release script: bump version, keep changelog DE/EN | ✅ |
| Tests: core, offscreen UI, stress test, on-screen test | ✅ |
