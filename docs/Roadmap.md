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
| Large assemblies: in-memory analysis mesh reuse across instances, comparisons and scan inspections, including refinement of coarse display meshes | ✅ |
| Batch surface sampling for alignment and comparison of assemblies with many small faces | ✅ |
| Large assemblies: persistent tessellation cache and viewer levels of detail | ⬜ |
| Indexed STEP geometry and PMI import, unique display edges, saved-view thumbnail generation only when enabled | ✅ |
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
| Find supported graphical PMI by recognised lettering, value, characteristic or datum before semantic review; recognition starts with a content search | ✅ |
| Preserve native PRC markup strings, positioned text rectangles and dimensions in model units; search original free-text notes | ✅ |
| Graphical-only PMI evaluated in the table (kind from PRC markup type/name, values/deviations/zone/Ⓜ/datums from text), marked as derived | ✅ |
| Make graphical-only PMI semantic (repair): kind from the callout name, faces from leader/arrow tips, checked in a dialog; STEP gets the semantics linked to the existing callout – PLAN §8.18 | ✅ |
| Review graphical PMI across the source model or a selection, read native STEP text literals, confirm or skip each entry, and export the reviewed dimensions, tolerances and datums alongside their original STEP graphics and saved views – PLAN §§8.18, 8.28 | ✅ |
| Convert supported AP203e2 curve annotations to AP242 Edition 3 and retain the original face references of native tessellated STEP PMI – checked on NIST CTC-01 and FTC-08 | ✅ |
| Read supported STEP dimension strings, datum letters and tolerance frames from single strokes, curves or filled triangle glyphs in the conversion dialog; export confirmed semantics with the original presentation | ✅ |
| Read stacked positive/negative deviations, unilateral deviations with zero, paired absolute limits, angles and parenthesised dimensions from supported graphical lettering | ✅ |
| Read planar tolerance frames without supplied writing axes, including original NIST 3D PDF/PRC; distinguish circled free-state and maximum-material symbols from their inner glyph | ✅ |
| Read additional lettering and composite frames from graphical PMI | 💡 |
| Semantic-only PMI: optional generated display in the view (see generated PMI stage 2) | ✅ |
| Show tolerance zones as envelope surfaces (offsets ±t/2, ⌀ zone cylinder, exaggeration) | ✅ |
| Tolerance zones stage 2: unequal zones (UZ/Ⓤ), projected zones, Ⓜ/Ⓛ bonus zone, space of the surface (size + location), size envelopes, patterns per feature | ✅ |
| Tolerance zones for the selected PMI, the selected faces or all PMI at once; general tolerances (ISO 2768-1/-2, ISO 22081) as a toggle, for the whole model or only at selected faces without PMI | ✅ |
| Zone of the derived median plane (slots/tabs), spherical zone (S⌀), context menus | ✅ |
| Tolerance zones in the datum system: coaxiality/runout around the datum axis, datum shift with Ⓜ/Ⓛ, form/orientation inside the higher-level zone | ✅ |
| Tolerance zones for linear dimensions between planes and angular dimensions | ✅ |
| Tolerance zones: roundness and circular runout per cross-section (ring zones) | ✅ |
| Tolerance zones: line profile per section (bands in three sections, longitudinal for LE), ACS (disks per cross-section), CZ (one common zone for coplanar faces) / SZ (hint), tolerances on edges/points (tube/sphere), on construction geometry (thread axes with projected zone Ⓟ outside the material), for the whole part ("all over") | ✅ |
| Tolerance zones: CZ for offset features and axis patterns (zones fixed to each other, hint) | ✅ |
| Tolerance zones: intersection-plane indicator for line profiles (no sample file; pythonocc lacks XCAFDoc_GeomTolerance) | ⬜ |
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
| Stack-up: whole chain in 3D with one click (arrows tip to tail on lanes, dimension and tolerance labels, location tolerances violet, ranges orange, closing dimension blue, what-if overlay in grey) | ✅ |
| Stack-up window: splitter, histogram beside the result table, interactive histogram (share at the mouse, draggable requirement limits) | ✅ |
| Stack-up: histogram per method (applicable ✓ by default, row click, overlay), traffic light for the requirement (window and PDF) | ✅ |
| Stack-up: manual approval "OK / checked" with name, date, comment (chain file, PDF) | ✅ |
| Stack-up: tooltips per method and column, distribution sparkline per link ("Spread") | ✅ |
| Tooltips for every non-obvious control, checked by a test (`werkzeuge/tooltips.py`) | ✅ |
| Stack-up: approval and traffic light also in the project file and for 2D/3D chains / assembly measures | ✅ |
| Stack-up: cost-optimal tolerance allocation with process capability table (PLAN §8.33) | ✅ |
| Function roles per face → datum system and ISO GPS tolerance proposal → STEP PMI (PLAN §8.33) | ✅ |
| Function → tolerancing: editable table (role, fit, tolerance by hand), swap faces, multi-face features (half shells) | ✅ |
| Function → tolerancing: datums by hand (A/B/C), example, generated PMI without overlap across writing planes | ✅ |
| Hand-built chains (1D/2D/3D): chain-wide material plus optional material per link, thermal expansion for 2D/3D (after UI stage 2) | ✅ |
| Function → tolerancing: live 3D preview of the proposed datum system (A/B/C flags, locked/open DOF) and of the tolerance proposal (callouts, row ↔ model highlight, zones optional) | ✅ |
| Function → tolerancing for shafts: gearbox shaft example (generated, licence-free), common datum axis A-B from two bearing seats, roles bearing seat / seal seat / hub seat / keyway / retaining ring groove, runout and symmetry proposals, annotations in the axial plane; common datums in zones and STEP | ✅ |
| Stack-up: build chains by hand without a model ("＋ Glied", editable cells) | ✅ |
| Stack-up tables readable: columns sized from header, text and cell widgets, numbers right-aligned (1D/2D/3D) | ✅ |
| Tables: hovering never selects a row (only click or keyboard); middle mouse button scrolls like a web browser in all tables, lists and panels | ✅ |
| One control height and frame style for all buttons, drop-downs, number and text fields in every window (theme), checked by a GUI test | ✅ |
| 2D vector-loop chains by hand with guided fields, sketch, linear (DLM) and non-linear Monte Carlo, handover to the 1D window (PLAN §8.33) | ✅ |
| 3D chains by hand: positions with six toleranced components, guided editor, templates, shown in the model, linear and non-linear, handover to the 1D window (PLAN §8.33) | ✅ |
| 2D/3D chains: save/open as .3dgkette2d/.3dgkette3d and in the project | ✅ |
| 2D/3D chains: pick from the model/assembly connections | ✅ |
| 2D chains: sliding contacts (kinematic adjustment, contact point slides – dependent variables solved by loop closure) | ✅ |
| 3D chains: sliding contacts (closure of position and orientation, six dependent variables) | ✅ |
| Stack-up: wiggle of the closing faces by the worst-case extremes | ✅ |
| Stack-up: closing faces found by walking the links along their faces; wiggle greyed out with the reason when they cannot be determined; 1D example as a real face chain | ✅ |
| 3D chains: wiggle (worst case of the closing quantity or link by link, 1:1 or exaggerated, function point with the real value, assembly parts move with their link); cleaner display in the model | ✅ |
| Stack-up: median planes as chain ends, chains across assembly parts | ✅ |
| Assembly: connections plane/plane and coaxial with snapping, satisfied check, open DOF per part, DOF wiggle, in the project | ✅ |
| Assembly: point contact (sphere on plane), pin–slot (line on plane), ball joint | ✅ |
| Assembly: reverse a connection (180°, cylinder end for end) and swap parts | ✅ |
| Assembly: wiggle as play/pause button | ✅ |
| Fix: tolerance zones follow the assembled part position and appear at every instance | ✅ |
| All tolerance / general-tolerance zones only for visible parts | ✅ |
| UI/UX plan (`docs/UI_UX_Plan.md`); stage 1: command search Ctrl/⌘+K, task start page, menu cleanup | ✅ |
| UI scaling option (90–150 %, as in ZGmax) | ✅ |
| UI/UX stage 2: workspaces; stage 3: inspector, guided flows and unified panels | ✅ |
| Assembly: move the selected part only along its open DOF (numeric fields per DOF) | ✅ |
| Assembly: 3D dragger (gizmo with arrows and rings) for the same moves | ✅ |
| Assembly: 3-2-1 template (six planes, one step) | ✅ |
| Assembly: add further files as parts ("Add model"; own tree node, placed next to the model, PMI kept, in the project) | ✅ |
| Assembly: drag a part in 3D in its open DOF with live snapping (plane/plane, coaxial), release connects; also at the 3D handle | ✅ |
| Assembly: STEP AP242 kinematics (joints, limits) as connections – researched, OCCT parses but does not transfer; needs a sample file | ⬜ |
| Tolerance stack-up 3D (geometric tolerances, chain from the model, sensitivity) – PLAN §8.20: by hand ✅ (§8.33), automatically from the model 🟡 (connections, measured planes and straight axes, common bearing axes and coplanar datum pads) | 🟡 |
| Assemblies built in the project (mates on datum features), materials and thermal expansion in chains | ✅ |
| Wiggle within tolerances (assembly connections, extreme positions, 1:1 or exaggerated); worst-case position scatter per part | ✅ |
| Assembly variation: measures between parts (gap/flush), worst case and Monte Carlo over all connections, requirement with Cpk/share outside, contributor ranking, PDF, example | ✅ |
| Assembly variation: histogram per measure in the report | ✅ |
| Assembly variation: measures on axes (axis to plane, axis distance) | ✅ |
| Assembly variation: temperature (materials from STEP), traffic light per measure, measures at a clicked point (point to plane/axis), in the PDF | ✅ |
| Assembly variation: datum shift (MMC/LMC bonus in connections) | ✅ |
| Assembly variation: one-sided planar stops in worst case and Monte Carlo, explicit per connection | ✅ |
| Assembly variation: measured planes and axes in their datum frame, lever arm at the measuring point, incomplete inputs indicated in the UI, PDF and chain | ✅ |
| Assembly variation: common datum axis from separate coaxial bearing seats, common plane from coplanar pads, individual member contributions | ✅ |
| Assembly variation: size-dependent Ⓜ/Ⓛ bonus on measured cylindrical features, coupled surface displacement, maximum geometric tolerance, projected axis zones with explicit start and offset | ✅ |
| Assembly variation: simultaneous position and orientation controls on different native and projected intervals of one rigid axis, including different diameters, offsets, material bonuses and caps | ✅ |
| Assembly variation: deformable form, other common datum geometries, material-boundary datum simulator contact and thread construction geometry | ⬜ |
| 3D chain from an assembly measure (one link per part on the connection path, clearance limits per component) | ✅ |
| Wiggle of the closing faces at the worst-case limits (exaggerated, coloured against the requirement) | ✅ |
| Chain from faces: median planes as chain ends, chains across parts with joint links from assembly connections | ✅ |
| Bill of characteristics with balloon numbers (table column, 3D balloons, CSV, PDF) | ✅ |
| Datum reference frame display for a selected tolerance | ✅ |
| Section: contour edges of the parts in the section plane (interactive, saved views, box), from the display mesh | ✅ |
| UI stage 2: workspaces (panel sets per task) | ✅ |
| UI stage 2: tool windows as panels (chain, 2D/3D chain, function) | ✅ |
| UI stage 2: CATIA roll band with rounded-arcball blend, view cube look and DPR, selection order, comparison state | ✅ |
| UI stage 2: one toolbar row, section/explosion in the structure panel, calm workspace switching, smooth panel resizing | ✅ |
| UI stage 2: scan check as comparison (mode bar target/actual, review walk) | ✅ |
| Create PMI with tolerancing advisor (stage 1: rules per selection, own PMI in project) | ✅ |
| Edit existing PMI (values, fit, material condition; saved in the project) | ✅ |
| Write edited PMI values back into a copy of the STEP file (lossless, own P21 editing) – PLAN §8.28 stage 1 | ✅ |
| Write own PMI to STEP AP242 as new P21 entities (datums, geometric tolerances, size/distance dimensions; single parts) | ✅ |
| Write own PMI in assemblies (context per part) | ✅ |
| Write PMI: presentation (graphics) for written own PMI – tessellated AP242 callouts linked to the semantics, read back by our reader and OCCT – PLAN §8.28 stage 3 | ✅ |
| Write PMI: advisor stage 2 (IT-grade start values, hole patterns, check against existing PMI) | ✅ |

## Measuring
| Feature | Status |
|---|---|
| Distance, angle, radius/Ø, wall thickness, coordinates; snapping; list, CSV, copy | ✅ |
| Quick measure in the status bar for the selection (length, Ø/R, area, distances, axis distance, angle, PMI info) | ✅ |
| Own views (camera, PMI, measurements) in project and PDF; measurement report PDF | ✅ |
| Loading another model clears all model-bound tool state (function → tolerancing, chains, measurements, comments, assembly, overlays); projects restore theirs | ✅ |

## Comparison
| Feature | Status |
|---|---|
| Alignment: same position, best fit (ICP), manual point pairs with snapping (UI) | ✅ |
| Geometry: equal/changed/new/removed per face, exact (B-rep) with mesh preselection | ✅ |
| Exact comparison acceleration: reject candidates by B-rep bounds and reuse the mesh of repeated instances | ✅ |
| Semantic PMI comparison (field by field incl. name, datums, faces), "geometry under PMI changed" | ✅ |
| Change list, review walk-through, comment, review report with SHA-256 | ✅ |
| Export changes (CSV) | ✅ |
| Deviation color map (scale, tolerance limit, sign, value on click) | ✅ |
| Display like CATIA Compare Products: added/removed volume (exact, Boolean) | ✅ |
| Detect moved elements (translation) and moved PMI | ✅ |
| Moved elements beyond the search radius: faces paired regardless of the order of equal faces (half shells), their PMI follow (“PMI moved”); sampling: at least five points per face, mesh points outside the face boundary pulled onto the face | ✅ |
| Detect rotated/mirrored elements (angle and axis, mirror plane) | ✅ |
| Graphical PMI comparison: moved or reshaped presentation of equal PMI | ✅ |
| Graphical-only PMI (notes) matched and compared by text | ✅ |
| Assembly comparison (parts new/removed/moved/changed/renamed) | ✅ |
| Change table with characteristic, old, new, Δ, tendency (tighter/looser), also in PDF/CSV | ✅ |
| Comparison modes: comparison, old, new, overlay, side by side (coupled cameras), blink; tree follows the mode | ✅ |
| Comparison modes stage 2: tree with part status colours | ✅ |
| Comparison modes: display is a function of mode and “Highlight changes” (colour map/material too), camera kept on every switch | ✅ |
| Comparison: both trees side by side in "Side by side" | ✅ |
| Geometry comparison per part instance (each instance sampled; status shown on the shared faces) | ✅ |
| Status colors per instance in the 3D view (instance key: face index + location), removed instances shown | ✅ |
| Change list entries per instance | ✅ |
| Meshes: STL/OBJ/glTF/3MF vs. CAD and mesh vs. mesh (alignment, color map) | ✅ |
| PLY meshes from scanners | ✅ |
| Scan against PMI tolerances: best fit + fine alignment, per-PMI evaluation (form, profile, location, axes, sizes, Ⓜ/Ⓛ bonus), colour map over CAD, CSV (PLAN §8.23) | ✅ |
| Scan check stage 2: 3-2-1 alignment to the datum system, inspection report PDF, linear/angular dimensions, point clouds (XYZ/ASC/CSV/PTS/PLY) | ✅ |
| Scan check: manual alignment by point pairs | ✅ |
| Scan check: per-section evaluation of roundness and circular runout | ✅ |
| Scan check: datums as contacting features (ISO 5459, constrained minimax) | ✅ |
| Scan check: line profile per section (cross sections; LE: longitudinal sections by angle) | ✅ |
| Plausibility check of the specification stage 1: hierarchy, size vs. form, completeness, datum system, contradicting dimensions, values, nominal vs. geometry (PLAN §8.22) | ✅ |
| Plausibility check stage 2: closed dimension chains | ✅ |
| Plausibility check: basic dimensions (with tolerance, location toleranced twice), patterns of different size, datum target counts | ✅ |
| Point clouds without triangles (PLY points, XYZ/ASC/CSV/PTS) | ✅ |
| Point clouds E57 (own reader, tested with libE57Format test data) | ✅ |
| Linked side-by-side view of old and new state (synchronized cameras) | ✅ |
| Clash/contact/clearance analysis of assemblies or selections (PLAN §8.21 stages 1–3) | ✅ |
| Band analysis (min/max distance), intersection volumes, result list with status/comment, CSV | ✅ |
| Clash: intersection curves, penetration depth, PDF report, results in the project | ✅ |
| Clash: mesh parts (PRC/STL) and mixed pairs (approximate) | ✅ |
| Gear analysis stage 1: cylindrical gears external/internal, spur/helical (z, da, df, b, β, db, mn, αn, x, Wk), CSV/JSON – PLAN §8.27 | ✅ |
| Gear pairs: centre distance, working pressure angle, contact ratios, backlash from the centre distance | ✅ |
| Gear data in notes checked against the geometry (plausibility) | ✅ |
| Gear analysis: involute splines (30°, ISO 4156 / DIN 5480) | ✅ |
| Gear analysis: full data sheet for cylindrical gears (ISO 21771 values, ball dimension, form diameters, tip relief, crowning, pair data, stages, planetary sets, CSV/JSON) | ✅ |
| Gear analysis: export as REXS model (FVA exchange format 1.7) for gear design and rating programs | ✅ |
| Gear design analysis (reverse engineering of design philosophies): cylindrical stages and planetary sets – PLAN §8.27a | ✅ |
| Shaft/hub splines and serrations, measured clearance and centring indications, conditional design findings – PLAN §8.27a | ✅ |
| Conical tooth geometry, tip/root cone angles and conditional pitch angles of a compatible pair, checked against known control geometry | ✅ |
| Bevel-pair dimensions from confirmed tooth-band ends: outer/mean transverse module, cone distance, face width, width ratio and shared width (STEP and STL controls) | ✅ |
| Bevel gears: tooth hand on an individual gear and mean spiral angle on the pitch cone of a compatible pair, tested with STEP and STL | ✅ |
| Bevel gears: manufacturing-system identification from independent evidence | ⬜ |
| Screw profiles: number of starts, lead, axial pitch and hand | ✅ |
| Throated wheel and candidate worm pair from screw and wheel geometry, axis position, hand and pitch | ✅ |
| Straight gears: repeated B-rep root fillet radius and radial tip chamfer height | ✅ |
| Manufacturing system and production fit or quality class from additional specification/inspection data | ⬜ |
| Fix: helix angle recognition for large angles, many teeth, wide gears | ✅ |
| Fix: tolerance stack-up strip lower (hint as tooltip, buttons below the links, compact results) | ✅ |
| Gear analysis: involute, parallel-sided and serrated shaft/hub profiles, measured tooth and space widths | ✅ |
| Gearbox reverse engineering for an individual gear, selected parts or all visible components, including disconnected wheels inside a single STL/OBJ mesh or CAD compound | ✅ |
| Stepped gears: distinguish axial tooth bands on a single solid or connected mesh, including tooth-count changes across a shoulder | ✅ |
| Multistage power flow with selectable reference shaft, branches, independent gear trains, cycle checks and mixed spur/bevel/worm stages | ✅ |
| Operating speeds and directions through worm stages and connected shafts, referred to the displayed positive shaft axes | ✅ |
| Operating speeds across coupled spur, bevel and simple planetary stages, reverted trains with separate coaxial input/output shafts, star operation with a fixed carrier, and symmetric open bevel differentials with selectable carrier axis | ✅ |
| Stepped planetary sets with two tooth bands on each one-piece planet: sun-side and ring-side mesh assignment, carrier ratio, operating speeds and REXS planet shafts | ✅ |
| Ravigneaux recognition and four-shaft operating speeds with a shared carrier, verified through STEP and STL | ✅ |
| Symmetric bevel and parallel-axis helical differentials: open, fully locked, clutch torque limit or torque bias ratio, operating-point conditions and torque bounds | ✅ |
| Component-specific friction, overrun and transient locking characteristics from independent data | ⬜ |
| Cylindrical gear pairs: actual axial engagement and overlap contact ratio | ✅ |
| Tooth-averaged left/right flank deviation maps, numeric CSV/JSON and illustrated gear PDF with sourced findings | ✅ |
| Tooth-to-tooth flank variation of cylindrical gears: peak-to-peak range per side at each sampled radius and section, pitch-circle summary in the gear table and PDF | ✅ |
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
| Generated PMI stage 3: dimension lines with arrows and extension lines (distance/thickness), leader arrows | ✅ |
| Generated PMI: projected frame and label overlap checks in shared orthographic views, including existing annotations | ✅ |
| Generated PMI: perspective placement and leader crossings | ⬜ |
| Drawing: sheet formats A4–A0 with frame, title block and standard scales | ✅ |
| Drawing: dimensions/frames as DXF dimension entities | ⬜ |
| Annotate: comments/questions/change proposals on faces and PMI, markers, status, project, CSV/PDF | ✅ |

## Formats
| Format | Status |
|---|---|
| STEP AP242/AP214/AP203 | ✅ |
| QIF 3.0: exact B-rep and semantic PMI (validated against STEP for NIST CTC-01/FTC-06) | ✅ |
| QIF: graphical PMI (PMIDisplaySet: texts with symbols, frames, leaders, witness lines, polylines, areas) and saved views (camera, visible PMI) | ✅ |
| QIF: measurement results read, assigned to the characteristics and assessed | ✅ |
| IGES, STL, OBJ, glTF/GLB, 3MF, PLY (meshes: view, measure, analyze, compare against CAD) | ✅ |
| JT 8–10 via TKJT converter jt2glb (mesh, structure, names, colours), build variant DG_MIT_JT=1; JT 10 via fork wwmayer/TKJT + own fixes (Move-to-Front, probability table, binary coordinates) | ✅ (NIST JT 10.5 end-to-end) |
| PMI from JT, JT B-rep (XT) | ⬜ |
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
| German/English UI, F1 manual with generated menu reference (introduction wizard and in-app "what's new" removed) | ✅ |
| Portable apps Windows/macOS/Linux, GitHub workflow with/without tests, self-test | ✅ (all three verified by the user) |
| Start screen closes when the main window opens, including after PyInstaller reads its Windows/Linux splash IPC variable | ✅ |
| Release script: bump version, keep changelog DE/EN | ✅ |
| Tests: core, offscreen UI, stress test, on-screen test | ✅ |
| Examples for the main functions (File › Examples, free test data, no copies in the repository) – PLAN §8.24 | ✅ |
| One comparison example with clear geometry and PMI changes (hole moved 15 mm, hole removed, chamfer; value, datum order, removed and new PMI) | ✅ |
| Several models side by side: File › New window, open in new window, linked cameras – PLAN §8.26 | ✅ |
| Wireframe with high-contrast edges (setting, default on); calmer, more legible view cube | ✅ |
| Readable PMI in both schemes (contrast ≥ 4.5:1 against the real 3D background, darker dark-scheme background, warning for a low-contrast own colour); legend of the shown tolerance zones in the 3D view | ✅ |
| Status-bar progress with Cancel for all background jobs (load, compare, analysis, colour map, material, scan) | ✅ |
| Closable tabs of stacked side panels; smooth side-panel resizing (batched 3D buffer resize) | ✅ |

## Drawing comparison and reconstruction

| Feature | Status |
|---|---|
| Compare model PMI with PDF drawing annotations, read inclined dimension text in selected regions and export reviewed matches, differences, one-sided and open findings with sheet and face references. Views along parallel hole axes can be rotated on the sheet or mirrored, including auxiliary views of inclined holes. They support hole-pattern registration, filled or outlined arrowheads, and a control frame sharing the diameter row’s leader. Repeated diameter dimensions support branching arrow leaders and retain their quantity, individual sheet locations and either a grouped dimension or individually reviewed model PMI per hole. Selecting a hole pattern also discovers unframed graphical diameter labels at horizontal leader ends. General view/leader registration and whole-drawing verification remain open – PLAN §8.35 | 🟡 |
| Generate a solid and dimensioned semantic PMI from orthographic drawing views and sections, resolve missing dimensions and verify by reprojection – PLAN §8.36 | ⬜ |

## Final implementation stage

| Feature | Status |
|---|---|
| Remaining QIF extensions, including QIF Plans measurement-plan export and schema validation – PLAN §8.37 | ⬜ |
