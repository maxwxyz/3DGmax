# Handoff

## Current state, 2026-11-21

### Solid truncated cones from PDF drawings

- Checked PLAN §§8.35–8.37 and docs/Roadmap.md. File → Shaft from 2D drawing also recognizes
  a solid truncated cone. The two independently fitted flanks must be straight and symmetric,
  and both end segments must reach them. The length and both end diameters must fit one scale.
  Size limits must preserve the taper direction. The optional included angle is checked against
  the geometrical angle, using its explicit limits or the precision of a printed nominal.
- Verified two PDF → review dialog → STEP round trips in opposite taper directions and sheet
  orientations (Ø28 and Ø16 over 30 mm). The native reader returned four graphical and semantic
  characteristics. XCAF returned their diameter fits, edge target counts, length end faces and
  angle tolerance. Verified the specific circular edges and graphical leader tips for the two fits,
  both length planes, cone angle and solid volume. Unmarked angles are optional. Additional
  strokes, broken ends or flanks, a bowed profile, conflicting angle, scale and fits were
  rejected in tests. All 28 affected tests and 45 native macOS tests passed; all 2577 UI
  strings have English translations. Mixed cylindrical/tapered shafts remain open.
- For §8.35 oblique hole views, an isolated vector PDF experiment projected four coplanar
  circular rims with two in-plane rotations and a 0.5 minor/major axis ratio. The PDF printer
  emitted each stroke as a pair of filled-path boundaries. The recovered centre lines had a
  ratio of 0.50008. Undoing the foreshortening matched all four distinct centres and radii to
  their original pattern. Production work needs complete printed paths, ambiguity and depth
  checks, and ellipse-aware review, leader targeting and export. Whole-drawing equivalence
  remains open. QIF is the final implementation item.

### Bores entering from both shaft ends

- Checked PLAN §§8.35–8.37 and docs/Roadmap.md. The longitudinal view can contain
  cylindrical bores from both ends of the same shaft. Two flat floors bound a material web.
  A shared through core requires both printed walls across the whole intervening length.
  The review table identifies the entry end of each diameter and depth. Optional end views
  are checked separately. Each side retains its own fits, shoulders and entry reference.
- Four PDF-to-STEP tests covered both drawing orientations, solid and dashed walls, identical
  and different entry diameters, a shared through core and two blind cores. Both STEP readers
  recovered the individual fits, depth limits and their target faces. Checked the depth graphics
  and removed volume. Missing floors, overlapping depth limits and disappearing shoulders
  block export. All 39 affected tests and 42 native macOS tests passed. All 2565 UI strings
  have English entries.
- For the outer-taper item, an isolated solid with Ø20 and Ø12 seats joined by an 8 mm taper
  round-tripped in both axial directions. Its included angle was 53.1301024° and its volume
  6542.890300 mm³. Both STEP readers recovered the angle on the cone, the seat fits and the
  12 mm and 20 mm stations from the end plane to the corresponding circular edges. The
  graphical leader tips reached those circles. Drawing recognition and review of external
  tapers, opposed drill points, fillets and whole-drawing comparison remain open. QIF stays last.

### Conical drill points in shaft drawings

- Checked PLAN §§8.16, 8.28 and 8.35–8.37 against docs/Roadmap.md. File → Shaft from 2D drawing
  now recognizes a simple or stepped axial blind bore with a conical point. Fit both printed flanks
  independently and check their strokes from cylinder to apex. The diameter, angle, cylinder end
  and apex must fit the same drawing scale. Pick or enter the included angle and explicitly select
  the depth to the cylinder end or to the apex. The median longitudinal selection time on a
  1900 × 1140 pixel sheet with a dashed 118° point was 14.3 ms over seven local runs.
- The tolerance check evaluates the cone radius where it reaches each outside seat, minimum
  remaining cylinder length behind the last shoulder, and material beyond the deepest apex. A cone
  may extend into a narrower seat when its radius has already reduced sufficiently. Conflicting
  angle or depth limits keep export unavailable. Broken, asymmetric, doubled or truncated flank
  drawings stayed unresolved in regression tests.
- Verified four drawing-to-STEP round trips with 90° and 118° points, both shaft ends, both depth
  conventions, simple and stepped cores and horizontal and vertical PDFs. Both STEP readers returned
  the angle and its limits on the cone. The depth targets the entry plane and the circle at full
  diameter or the apex vertex. Checked the graphical arrow endpoint, depth limits and cut volume.
  All 31 affected tests and 36 native macOS tests (eight screen tests and 28 shaft tests) passed.
  All 2553 UI strings have English entries.
- For the next §8.36 item, an isolated probe put Ø10 H7 × 6 and Ø10 H8 × 8 mm counterbores at
  opposite ends of a 30 mm shaft. A shared Ø6 core or two separate blind Ø6 cores round-tripped
  with their individual face assignments, tolerances and reference ends. The volumes were
  4253.716453 and 4451.636790 mm³ respectively. A PDF probe distinguished two separate Ø10 wall
  intervals and a continuous or divided Ø6 interval. Drawing review still needs both entry
  directions, verified connecting shoulders and a retained core or residual wall at the drawing
  limits. Outer tapers and fillets, datum transfer and whole-drawing comparison remain open.
  QIF stays last.

### Single-entry stepped axial bores in shaft drawings

- Checked PLAN §§8.16, 8.28, 8.35–8.37 and docs/Roadmap.md. File → Shaft from 2D drawing now
  follows successive coaxial wall pairs from either entry end. The printed annular shoulder must
  connect each pair to the next on both sides. Continuous and dashed walls, horizontal and vertical
  longitudinal views, a through core and a flat-bottom core are supported. The review table starts
  at the entry face. Each diameter and each depth from that face can be selected on another sheet.
  All dimensions must fit a single longitudinal scale. Optional entry-view rings are checked at
  their own scale. The tolerance limits must preserve the internal shoulders and remaining material.
- PDF-to-STEP tests covered two and three cylindrical stages, including a bore shoulder coplanar
  with an outside shoulder. Both STEP readers recovered every bore fit on its own cylinder and every
  depth with the shared entry plane and its respective internal shoulder or floor. Confirmed the
  graphic depth spans and the volume for all four PDF round trips. Negative cases covered a broken
  wall, a missing shoulder flank, a sloped step, an unclosed rear face, an inconsistent end view,
  a depth on a through core and limits at which shoulders disappear. Reselecting the outline
  clears the previous bore table. All 25 affected tests and 30 native macOS tests (eight screen
  tests and 22 shaft tests) passed. All 2549 UI strings have English entries.
- For the next §8.36 package, a local shaft probe added a 118° point to an Ø6 H8 core beneath
  a 6 mm deep Ø10 counterbore. Both STEP readers recovered the angle on the cone. For the 14 mm
  depth the entry plane and cylinder-end circle or apex vertex round-tripped from both directions.
  The corresponding reconstructed volumes were 5091.240721 and 5142.207522 mm³. A second PDF probe
  fitted each point flank separately in both orientations of entry, recovering 90° from continuous
  strokes and 117.63–117.68° from dashed 118° strokes. Production recognition, review of the depth
  convention and tolerance-limit checks for the cone remain open. Opposed counterbores, outer
  tapers and fillets, datum transfer and whole-drawing comparison also remain open. QIF stays last.

### Flat-bottom axial blind bores in dimensioned shaft drawings

- Checked PLAN §§8.16, 8.28, 8.35–8.37 and docs/Roadmap.md. The shaft dialog recognises paired
  bore walls from one end to a flat axial floor. Entry is labelled left/right or top/bottom in the
  selected longitudinal view. Select or enter the diameter and depth from the entry plane. A through
  callout, a conflicting depth, or an end view from the opposite side prevents export.
- The bore limits must leave a wall in every seat reached at maximum depth and minimum section
  lengths, plus material behind the floor. A blind Ø14 H7 × 10 mm bore fits inside an Ø20 × 12 mm
  land followed by an Ø12 land. Increasing its depth tolerance into the thinner land blocks export.
  Both continuous and dashed wall lines are supported. Partial floors, conical tips, open rear ends
  and opposed incomplete wall pairs remain unresolved.
- For left and right entries, native and XCAF STEP reloads recovered the two outside lengths, both
  outside diameters, the bore fit and the toleranced bore depth. The depth references the planes
  adjacent to the inner cylinder even when a shoulder shares the floor coordinate. The graphical
  depth spans the corresponding X coordinates. Reloaded volume matches the two outside cylinders
  minus the blind hole, and the drawing comparison matches the printed depth. Checked horizontal
  and vertical PDFs and a separate dimension sheet. All 20 affected tests, eight native macOS screen
  tests and 15 native shaft tests passed. All 2538 UI strings have English entries.
- A probe for the next §8.36 package put an Ø10 H7 counterbore 6 mm deep over an Ø6 H8 core from
  either end. With a through core the volume is 4655.840313 mm³, with a 14 mm flat-bottom core it
  is 5108.229655 mm³. Both readers recovered the two cylinder targets and each entered depth from
  the common entry face to its own floor. A separate four-view PDF probe found both wall pairs and
  their respective axial spans. Integration still needs connected step-edge evidence, review of
  each diameter and depth, and clearance checks per step. Conical shaft drill points, tapers,
  fillets, datum transfer and whole-drawing comparison also remain open. QIF stays last.

### Reconstruct a straight axial through bore in a stepped shaft

- Checked PLAN §§8.16, 8.28 and 8.35–8.37 against docs/Roadmap.md. File → Shaft from 2D drawing
  now handles solid and hollow shafts. A pair of symmetric continuous or dashed bore walls must
  span the full longitudinal view. When hidden lines are omitted, select the concentric vector
  rings of an end view and supply the printed through diameter, e.g. Ø8 H7 THRU ALL. Views may
  use separate sheets and scales. A selected end view must agree with the contour even when
  longitudinal evidence is already present. Hidden shoulders between larger seats cannot serve as end-view rings. The bore must leave material in each seat at the
  entered size limits. A fit outside the supported tables requires explicit limits. Incomplete bore traces and partial end edges keep the selection unresolved.
- Tested two PDF routes to the same two-seat shaft (Ø20 × 12 and Ø12 h6 × 18 mm). The exported
  Ø8 H7 bore reduces the volume to 4297.698750 mm³. Both the native and XCAF STEP readers
  recover the fit on the inner cylinder bounded by the 0 and 30 mm planes. Verified five semantic
  and graphical dimensions and the leader endpoint. The regressions also cover interrupted walls,
  a hollow section with open end faces, wrong or incomplete end rings, vertical orientation,
  conflicting tolerances and preserving an existing target when the bore reaches the outside wall.
  All 139 affected tests passed. The complete headless suite passed 745 with eight screen tests
  skipped. The native macOS run passed all eight screen tests and all eight shaft tests. The
  final menu/manual and translation checks passed; all 2527 UI strings have English translations.
- For the next §8.36 item, an isolated OCCT probe added flat-bottom axial blind bores from either
  end. Both STEP readers recovered Ø8 H7 and a toleranced depth between entry plane and floor.
  With 14 mm depth, the graphic spans X = 0–14 or 16–30 mm, and the volume is 5101.946469 mm³.
  When the floor shares its X coordinate with the outside shoulder, adjacency distinguishes the two
  planes. A second round trip checked all six dimensions together and preserved the external seat
  lengths independently of the hole depth. A rendered PDF probe distinguished full floors from
  interrupted walls ending mid-seat, with both continuous and dashed wall strokes.
  Where a shoulder coincides with a candidate floor the drawing also needs an explicit depth.
  A 10 mm blind Ø14 H7 bore in the 12 mm long Ø20 seat also round-tripped from either side,
  despite the remote Ø12 seat. Check blind-bore clearance only along its possible penetration
  at the drawing limits. Through-bore clearance still applies along the whole shaft.
  Blind-bore review and production export, tapers, fillets, datum transfer and whole-drawing
  comparison remain open. QIF stays last.

### Solid turned shafts from dimensioned longitudinal PDF views

- Checked PLAN §§8.16, 8.28 and 8.35–8.37 and docs/Roadmap.md. File → Solid shaft from 2D
  drawing is available without a loaded model. Select a horizontal or vertical longitudinal
  outline. Each reviewed section needs a length and a diameter, with known units. A printed
  centerline and visible shoulder edges are supported. The remaining ink, common centerline,
  continuous outline, section widths and shoulder stations must agree with the same geometry
  and scale. The median selection time on the 1900 × 1140 pixel probe sheet was 16 ms over five
  runs. The plate and shaft dialogs share PDF lifetime, page switching and atomic STEP export.
- Ran the menu command on a two-sheet PDF with Ø20, Ø12 h6 and Ø20 seats of lengths 12, 18
  and 8 mm. The two Ø20 seats have different diameter tolerances. Both STEP readers recovered
  the six dimensions at their respective cylinders and end/shoulder planes. Checked the graphical
  diameter leader tips and length spans and the volume π × (20 × 100 + 18 × 36) mm³. The drawing
  comparison matched the first Ø20 and flagged its changed tolerance when assigned to the last
  seat instead. Additional cases covered vertical orientation, explicit inch units, missing units,
  incompatible limits, cropped and broken outlines, extra internal edges and asymmetric profiles.
- The original fit writer put the full class in the form-variance field and left the grade empty.
  XCAF lost a newly authored h6 in this representation. Separate form-variance and grade fields
  preserve h6 for a new shaft seat and H7 for an edited NIST dimension. Existing source files
  with combined notation remain readable. The complete headless suite passed 740 tests and skipped
  the eight screen tests. The native macOS run passed those eight and all three shaft tests. The
  focused plate, shaft and STEP writer run passed all 34 tests.
- For the next §8.36 stage, a local hollow-shaft probe added an Ø8 H7 straight bore through
  two lands of Ø20 × 12 and Ø12 × 18 mm. Its cylinder was adjacent to both end planes. Both
  STEP readers recovered all five dimensions and the volume was 4297.698750 mm³. A separate
  PDF end view yielded two concentric vector rings with radius ratio 0.400000. A two-sheet
  hidden-line probe for a 30 mm shaft distinguished paired wall strokes along the full length
  from traces ending at 14 mm. Both were correctly rejected by the current solid-shaft dialog.
  Integration still needs evidence of a through bore from the drawing, inner-diameter review and checks
  against the smallest outside diameter. Tapers, fillets, datum transfer and whole-drawing
  comparison remain open. QIF stays last.

### Reconstruct obround slots from their end-axis spacing

- Checked PLAN §§8.16, 8.28 and 8.35–8.37 and docs/Roadmap.md. The PDF picker and pocket table
  accept spacing between the end axes in either orientation. Width plus spacing fixes the geometry.
  An explicitly entered overall length is checked against the other dimensions and exported as a
  separate characteristic. Limit-only dimensions can use a compatible nominal inside the printed
  range. The slot keeps the drawing limits. A calculated overall length adds no extra PMI.
- Verified a 16 × 6 mm blind slot specified by a 10 ±0.1 mm spacing and a vertical through slot
  whose drawing supplied overall length, width and a 9.98–10.08 mm spacing. The STEP uses two
  CENTRE_OF_SYMMETRY aspects derived from the respective end faces. Reloads confirmed both pairs
  of faces and the printed limits. The native reader retains the 10 mm nominal fixed by the other
  dimensions. XCAF's value for the asymmetric interval is its midpoint, 10.03 mm. The actual
  axes and graphical dimension lines are 10 mm apart. The model comparison detects a change in
  the targets from derived centers to the original faces even if the numerical values agree.
  All 209 affected tests, 83 drawing/STEP tests and eight macOS screen tests passed. The final
  reconstruction run passed all 24 tests, including incompatible ranges.
- The next §8.36 package is turned parts. A local OCCT probe revolved an axial profile with
  Ø20 × 12 mm and Ø12 × 18 mm lands. Native and XCAF STEP reloads returned four face-linked
  dimensions, each diameter on its own cylinder and each length between its end or shoulder planes.
  The volume was 5805.663224 mm³. A separate rendered PDF probe included three cylindrical lands
  with lengths 12, 18 and 8 mm and diameters 20, 12 and 20 mm. Column envelopes reproduced
  these six dimensions to within 0.11 mm, including both equal-diameter lands. Pen width affected
  the transition pixels. Centerline extraction, rejection of ambiguous outlines and connection
  to the user-facing workflow remain open. Inclined slots, datum transfer
  and whole-drawing comparison are also open. QIF stays last.

### Obround slots dimensioned by their overall length

- Checked PLAN §§8.16, 8.28 and 8.35–8.37 and docs/Roadmap.md. The plate dialog accepts a
  closed horizontal or vertical obround vector outline matching the printed top view. Overall
  X and Y dimensions locate the tangent walls and the two end centers relative to the reviewed
  midpoint. Length and width limits must keep the ends distinct. The short dimension determines
  the end diameter. Both a through cut and a flat-bottom slot are supported.
- Built a 60 × 40 × 8 mm plate from a PDF with two 16 × 6 mm slots. One ran along X and ended at
  4 mm depth, the other passed through along Y. Volume agreed with removal of (60 + 9π) × 12 mm³.
  Native STEP and OCCT/XCAF reloads preserved all eight dimensions, including the two outer-to-outer
  locations on their respective half cylinders. Verified nominal span, separate deviations, straight
  side walls, floor, and graphical dimension line endpoints along both axes. The geometry check
  detected a deliberately substituted 10 mm nominal. All 59 affected tests, 82 drawing/STEP
  tests and eight macOS screen tests passed.
- Slot center spacing is the next §8.36 drawing case. In a local experiment, a 10 mm linear
  dimension referencing two CENTRE_OF_SYMMETRY aspects, each related to its end wall by
  SHAPE_ASPECT_DERIVING_RELATIONSHIP, recovered both face references in the native reader and
  XCAF for both slots. Capturing the drawing convention, writing the derived targets, preserving
  tolerance and drawing the center-to-center dimension still need integration. Inclined slots,
  turned parts and whole-drawing comparison also remain open. QIF stays last.

### Four equal corner fillets in reconstructed pockets and through openings

- Checked PLAN §§8.16, 8.28, 8.35–8.37 and docs/Roadmap.md. A closed vector contour can define
  four equal quarter-circle corners when it agrees with the top-view ink. The drawing can supply
  the common radius as R3 or 4× R3 with limits or deviations. Its limits must leave four straight
  walls. Contact checks use the rounded outline, including clearance around a bore near a corner.
- Reconstructed a blind pocket and a through opening of the same size and radius with distinct
  tolerances on a plate with a through hole. Verified the volume, the 13 graphical and semantic
  dimensions, and face identity through both the native reader and OCCT/XCAF. With one shape aspect
  and four geometric usages XCAF recovered only one corner. A composite shape aspect referencing
  four individual face aspects preserves the entire group in both readers.
- All 48 affected tests, 74 drawing comparison/reconstruction tests, eight STEP writer/translation
  tests and eight macOS screen tests passed. Obround slots, unequal corner radii, turned parts,
  automatic cross-view association and datum transfer remain open. For the next slot stage, a
  local OCCT probe extruded two straight edges and two semicircles. A 16 × 6 × 4 mm tool yielded
  two R3 half-cylinder faces and the expected volume of 353.097335529 mm³. QIF stays last.

### Reconstruct drill points with both drawing depth conventions

- Checked PLAN §§8.16, 8.28, 8.35–8.37 and docs/Roadmap.md. A blind bore accepts an explicit
  included point angle and a depth to either the cylindrical end or the apex. The PDF picker and
  the table support both. The first depth references the top plane and the cylinder’s lower
  circular edge. The second references the top plane and the cone’s apex vertex. The angle is
  a separate angular size on the cone. Checks use diameter, angle, depth and plate thickness
  limits, including the remaining cylindrical segment under a countersink.
- Verified a two-bore PDF with Ø4 holes and 118 ±1° and 90 ±2° point angles. One bore also has a
  120° countersink. Under both depth conventions the native STEP reader and OCCT/XCAF recover
  the depth references, the point angles and their tolerances. Independent volume and cone
  endpoint checks confirm the amount removed. For a 5 mm total depth the apex and the graphical
  depth arrow both land at (42, 20, 3) mm on an 8 mm plate. All 202 affected tests, 71 drawing
  comparison/reconstruction tests and eight macOS screen tests passed. The final dialog run
  passed all 18 reconstruction tests.
- Remaining §8.36 work includes rounded pockets, turned parts, cross-view association and datum
  transfer. A local PDF probe of a 60 × 40 rectangle with 8-unit corner radii exposes two nested
  38-point contours for the pen stroke. Their measured radii bracket the centerline radius.
  Filleting four vertical tool edges with OCCT also produced the expected volume for a
  60 × 40 × 3 mm pocket with R8 corners. Rounded-pocket reconstruction still needs an integrated implementation. QIF stays last.

### Reconstruct conical seats and dimension their entry circle

- Checked PLAN §§8.16, 8.28, 8.35–8.37 and docs/Roadmap.md. The outermost concentric ring can be
  confirmed as a countersink from the plate top. The included angle with its deviations or limits
  and the two diameters determine the taper. The deepest permitted taper must leave an inner
  cylindrical segment. An outer ring alone does not determine whether the seat is conical.
- The angular size references the actual cone. The entry diameter uses the EDGE_CURVE shared
  by the cone and the top face. Its graphical arrow ends on this same circle. Two equal Ø12 entries
  at different centers, with 90 ±1° and 120 ±2° angles, were checked through the PDF dialog,
  STEP export, native import and OCCT/XCAF. One was above a through bore and the other above
  a stepped blind bore. Actual material removal matched the two frustum volumes.
- All 200 affected tests, 69 drawing comparison/reconstruction tests and eight macOS screen tests passed. Drill points,
  turned parts, rounded pockets and automatic cross-view association remain open. QIF stays last.

### Generated dimension and tolerance leaders on tessellated STEP faces

- Checked PLAN §§8.16, 8.22, 8.35–8.37 and docs/Roadmap.md. A face can contain only triangles.
  The geometric nominal checks now skip missing analytic planes or cylinders, including mixed
  plane/mesh pairs. Generated leaders use the nearest point across the located triangles and
  analytic faces in the selection. Mesh arrays are reused while placing annotations.
- On the NIST FTC-08 AP242 tessellated example, all 273 faces have no analytic surface. Added a
  dimension referencing two mesh faces, exported and reopened it. The new semantic record and
  its stored presentation were both present. An independent barycentric check put the arrow tip
  on an actual referenced triangle. A mixed planar B-rep and translated triangle also gave the
  expected closest points in the triangle interior, on its boundary and on the analytic face.
- All 41 affected tests and eight local macOS on-screen tests passed. The next drawing work
  includes conical seats and drill points, rounded pockets, turned parts and cross-view
  association. Whole-drawing completeness remains open. QIF stays last.

### Reconstruct cylindrical stepped bores from the top view

- Checked PLAN §§8.35–8.37 and docs/Roadmap.md. Concentric vector rings with distinct ink contours
  share their innermost row’s reviewed X and Y. The reviewer selects a through or flat-bottom core
  and confirms a cylindrical step from the top for each larger ring. All depths are measured from
  the top surface. Step diameter and depth ranges must stay separated.
- On a 60 × 40 × 8 mm plate, one through bore had two shoulders and one blind bore had one shoulder.
  The native STEP reader and OCCT/XCAF recovered all five cylinder positions, diameters and axial
  extents, both equal-depth shoulders with their distinct tolerances, and the blind floor. Volume
  agreed with the nominal cuts. The PDF dialog test exercises picking the outer depth, changing
  end conditions and rejecting overlapping limits. Separate near-radius and eccentric profiles
  exercise the distinction between two steps and interfering bores.
- All 20 affected tests and 68 combined drawing comparison/reconstruction tests passed. Conical
  seats, drill points, rounded pockets, turned parts and automatic cross-view association remain
  open under §8.36. Whole-drawing completeness remains open under §8.35. QIF is last.

### Rectangular through openings alongside pockets and bores

- Checked PLAN §§8.35–8.37 and docs/Roadmap.md. Each rectangular interior contour can be a
  flat-bottom pocket with a reviewed depth or an explicitly selected through opening. Switching
  to through clears the depth and its PDF selection. Switching back requires a new depth.
- A through opening has four connected walls shared by the top and bottom plate faces. STEP
  links width and height to the respective opposite walls. Both the native and OCCT/XCAF readers
  recovered each wall pair for two identical, aligned openings. The mixed case includes one
  through opening, one blind pocket and a drilled hole on the same plate. Solid volume and the
  absence of a depth dimension on the through opening were checked. All 18 affected tests and the 66-test drawing comparison and reconstruction run passed.
- Next §8.36 candidates are stepped bores and rounded pocket profiles. The reviewer still supplies
  the end condition from the drawing. Automatic cross-view association and whole-drawing
  completeness remain open. QIF stays last.

### Hole-center dimensions in reconstructed plates

- Checked PLAN §§8.35–8.37 and docs/Roadmap.md. The PDF plate dialog accepts bilateral deviations
  and limits for X and Y from the lower left. Each exported distance references the corresponding
  zero-coordinate plane first and the individual bore wall second. Dimension lines run from that
  plane to the axis in the top view. Plate edges must clear the entire diameter and location range.
- Reopened a two-hole AP242 export in the native reader and OCCT/XCAF. Both retained the four
  location dimensions on the correct bore and plate face, including X = 20 ±0.1 mm and Y limits
  of 27.9–28.1 mm. The regression also checks the STEP aspect order and the graphical dimension
  line lengths at the top surface. The affected suite passed 45 tests.
- Pocket center references, through and rounded pockets, stepped holes, turned parts and automatic
  cross-view association remain open in §8.36. Drawing-wide completeness is open in §8.35. QIF is last.

### Reconstruct rectangular pockets and their dimensions

- Checked PLAN §§8.35–8.37 and docs/Roadmap.md. A selected rectangular plate can contain closed
  rectangular pockets alongside cylindrical holes. Each profile must be separate and closed.
  The table lists estimates and accepts the drawing center, two side dimensions and flat-bottom
  depth. All four projected edges must agree. Boundary contact, overlapping cuts and open
  contours prevent export. Clicking inside a pocket or on a bore rim selects the matching row.
- Verified through the PDF dialog on two equal 12 × 8 mm pockets at different X positions with
  depth 3 ±0.1 mm, both with and without a through hole. Reload checks the cut volume, graphical
  and semantic values and both pairs of opposite walls. Independent XCAF inspection checks the
  depth reference at each distinct floor. The affected suite passed 44 tests and the combined
  drawing/reconstruction/translation run passed 65.
- Under §8.36 center-location PMI, stepped bores, rounded profiles, turned parts and cross-view
  association still need implementation. Under §8.35, section and non-circular feature matching
  and whole-drawing completeness remain open. QIF is last.

### Reconstruct flat-bottom blind holes with depth PMI

- Checked PLAN §§8.35–8.37 and docs/Roadmap.md. Each printed ring now has an explicit end
  condition. Through and top-entry flat-bottom holes can share a plate. A blind hole requires
  a depth from the drawing, including any limits or deviations. The depth range must leave
  material at the minimum plate thickness. New view selections clear previous end choices.
- After the STEP geometry is read back, the cylinder's edge neighbours identify its planar
  bottom and entry face. The exporter attaches the depth to those faces and the diameter to
  the bore wall. Tested on a three-hole drawing with one through hole and two Ø8 blind holes
  of depth 4 mm at different centers, with ±0.1 and ±0.2 mm depth deviations. The solid volume,
  all eight graphical and semantic records, both bottom centers and both tolerances survived
  reload. OCCT/XCAF independently read both depth records on the correct pairs of faces.
- All 13 affected tests and 62 combined drawing/reconstruction/translation tests passed.
  Next in §8.36: checked pocket outlines and their depth or stepped bores. Drawings with drill
  points, center-location PMI and automatic view interpretation remain open. QIF stays last.

### Reconstruct confirmed through holes in a plate

- Checked PLAN §§8.35–8.37 and docs/Roadmap.md. The plate dialog matches separate closed ink
  components to circular vector paths inside the top outline. Residual lines, cropped profiles
  and overlapping holes prevent reconstruction. Each row shows estimated X/Y/diameter separately
  from the drawing values. The user enters those values or picks the annotations on the PDF and
  confirms through depth. The cut uses all tools together, and the export associates the diameter
  with the actual cylindrical wall. X/Y specify the modeled location.
- A portable 60 × 40 × 8 mm PDF defines Ø10 ±0.05 and Ø8 H7 holes at (20,16) and (48,28) mm.
  STEP reload gives a volume of 18169.55761 mm³, five displayed and semantic dimensions, both
  cylinder centers and the expected tolerance and fit. OCCT/XCAF independently read both diameters
  on their walls. Other tests cover mismatched or missing coordinates, a repeated quantity pasted
  into an individual diameter, extra ink, intersecting bores, units and reselection.
- Selected PDF crops can contain a native text row separated into single-glyph fragments by PDFium.
  The crop reader now rejoins horizontally aligned fragments with consistent spacing. All 23
  affected tests passed. The final reconstruction, drawing and translation run passed 61 tests.
  An earlier run with a failing assertion also aborted
  during subsequent Qt preview setup; it did not recur on the corrected runs.
- Next in §8.36: explicitly dimensioned blind bores and the bottom face/depth PMI. Counterbores,
  pockets, separate X/Y PMI and automatic cross-view interpretation also remain. Whole-drawing
  verification in §8.35 is still open. QIF remains last.

### Reconstruct a dimensioned rectangular plate from a drawing

- Checked PLAN §§8.35–8.37 and docs/Roadmap.md. File → Plate from 2D drawing is available
  without a model. Select the plain top contour, pick the dimensions on the PDF or enter them, and
  optionally select a front contour from a different sheet or scale. The dialog requires a positive
  width, height and thickness in known units and checks both view proportions. An invalid optional
  view must be corrected or removed. Interior marks and open or cropped contours block reconstruction.
- The export uses a local OCCT AP242 writer configuration. It attaches three dimensions and their
  graphical presentations to the corresponding opposite faces. The destination is replaced only
  after all three have been written. A 60 × 40 × 8 mm PDF round trip checks the volume, measured
  face distances, all three semantic associations and the 60 ±0.1 mm width in both 3DGmax and XCAF.
  Exporting the nominal first also preserves the two limits in OCCT's independent reader. Tested
  with a 1.50–1.52 inch width and a 0.125 ±0.002 inch thickness. All 156 affected tests passed.
  The full suite run passed 713 tests with eight skipped. The affected run includes the additional
  export-failure and inch-limit regressions added after collection of the full suite.
- Next in §8.36: through-holes in the top outline. Local experiments identified the two printed
  rings of a 60 × 40 mm plate and checked their supplied centers and diameters against the view.
  A separate OCCT cut/STEP experiment retained the volume and five face-linked dimensions (three
  outer dimensions and two diameters). The shipped dialog currently accepts plain plates.
  Pockets, turned profiles and GD&T transfer remain open. QIF stays last.

### Read standalone graphical diameters in all four sheet orientations

- Checked PLAN §8.35 and docs/Roadmap.md. The selected view is searched for free horizontal and
  vertical leader ends. The local strip and ray are expressed in the reading direction, then the
  crop is mapped back to sheet coordinates. Both reading directions share one render at each
  resolution. A diameter still needs a consistent full-row reading and an arrow to a printed ring.
- The original D2MI 904 sheet 3 rotated by 90 degrees produced the same callout, STEP #103256
  and open numerical finding as the upright drawing. The portable PDF covers all four rotations,
  removal and re-registration, and rejection of an unknown suffix both horizontally and vertically.
  All 53 focused drawing tests and 55 affected tests passed.
- Arbitrarily angled standalone rows, sections and non-circular targets remain in §8.35.
  The next reconstruction milestone in §8.36 is a dimensioned prismatic plate from a selected
  orthographic view, with explicit depth and checks on the recovered geometry. QIF remains last.

### Match symmetric hole patterns as a group

- Checked PLAN §8.35 and docs/Roadmap.md. Where every equally good registration permutes the
  same complete set of bore walls, a repeated diameter can match a grouped model dimension.
  The review draws dashed rings for these holes and identifies the group association in CSV.
  Individual targets and alternative sets of walls remain unresolved.
- Verified in the drawing dialog on the original D2MI 904 sheet 3. The callout with four
  0.215–0.225 inch diameters matches STEP #103256 on eight half-cylinder faces. The model gives
  5.461 mm as the upper and 5.715 mm as the lower limit, so the numerical verdict stays open.
  A portable solid/PDF test also covers equal and changed values, registering the view twice,
  and CSV export. All 49 focused drawing tests and 42 affected tests passed.
- Next in §8.35: recover standalone diameter rows at rotated leader ends. Sections, oblique
  projections and whole-drawing scope remain open. §8.36 reconstruction precedes QIF in §8.37.

### Discover standalone graphical diameter rows around a selected hole pattern

- Checked PLAN §8.35 and docs/Roadmap.md. The registration worker follows free horizontal leader
  ends to printed circles inside the selection, independently of whether a STEP face can be matched.
  Only the adjacent row is rendered for OCR. A complete diameter reading must recur at two
  resolutions and competing readings stay open. Existing labels and frame cells take precedence.
  Reselecting the view neither duplicates findings nor restores a finding the user removed.
- In the review dialog, selecting the symmetric hole pattern on D2MI 904 sheet 3 recovered the
  standalone 4X diameter with 0.215–0.225 inch limits. The row is in the list and its crop is
  visible. The individual STEP faces remain ambiguous under reflection. A portable public-domain
  raster crop of this callout exercises the normal dialog on a separate, asymmetric PDF fixture.
  The test also adds an unknown graphical suffix to verify that the partial row stays out of the list.
- All 51 affected tests passed and 47 focused drawing and translation tests passed. Still open are
  group-level associations invariant under symmetry, inclined or stacked free rows, sections,
  non-circular targets and whole-drawing verification. §8.36 reconstruction precedes QIF in §8.37.

### Follow branched drawing leaders to a hole pattern

- Checked PLAN §8.35 and docs/Roadmap.md. A printed quantity can identify two or more distinct
  registered holes through its arrow branches, including a junction in the middle of a shaft and a
  dimension line drawn as a single crossbar with arrowheads at both ends. Unconnected crossings,
  open or cyclic paths, two arrows to the same hole, an unregistered tip or a quantity mismatch
  do not produce a complete group.
- In constructed vector PDFs the dialog selected two specified holes despite a third printed circle
  of the same diameter and matched a three-hole callout with nested branches. Nine regression cases
  exercised the review dialog. D2MI 904 retained its 14 registered rings and the separate diameter
  and position targets. The automatically discovered repeated callout in the local D2MI drawing
  collection has a single representative arrow. The branch tests therefore use constructed PDFs.
- All 35 affected tests passed; the focused drawing and translation run passed 45 tests. Further
  work includes finding unframed graphical annotations beyond the recognized rows, sections and
  non-circular targets in §8.35. Reconstruction remains in §8.36 and QIF stays last in §8.37.

### Compare a repeated drawing callout with separate STEP dimensions

- Checked PLAN §8.35 and docs/Roadmap.md. In individual-PMI mode each selected hole has a model
  record, an open decision or an explicitly confirmed drawing-only finding. Only dimensions whose
  faces belong to that hole are offered. Changing the active hole highlights its circle and model
  PMI. Multiple candidates on a hole need a choice. Removed model records reopen their findings.
- The CSV emits one row per reviewed hole with its source ID, sheet coordinates, local finding and
  whole-pattern finding. A group with an unresolved hole stays open. A partly missing or changed
  pattern is marked changed. Verification used a newly written and reimported AP242 solid with
  separate 4.0 and 4.1 mm model dimensions against a PDF calling for two 4.0 mm holes. It identified
  the correct hole in each case. The dialog test also removes and restores a record, confirms a
  missing dimension, checks competing dimensions on one hole and reviews a second sheet region.
- All 28 affected tests passed and the focused drawing and translation run passed 36 tests.
  Compound leaders, sections, non-circular targets and whole-drawing verification remain open.
  Reconstruction follows in §8.36 and QIF stays last in §8.37.

### Verify repeated diameter callouts against a grouped model dimension

- Checked PLAN §8.35 and docs/Roadmap.md. Native and supported plotted diameter rows retain their
  quantity. A leader or a manual click identifies the first hole. The selected view supplies the
  other same-radius circles, including unmatched rings when counting potential targets. Extra
  circles require explicit selection with Shift-click. Equal values require the selected model PMI
  to cover exactly the marked holes. The PDF view highlights them and the CSV keeps each coordinate.
- In the review dialog, D2MI 904 sheet 2 independently identified the plotted 2X diameter above the
  least-material position frame. Its printed limits are 0.370 and 0.380 inch. The leader and the
  second ring identify both holes of STEP dimension #38471. Its tolerance entity #38491 supplies
  +0.005 inch as the lower deviation and −0.005 as the upper. The app preserves the source order
  and reports an open value check. The adjacent position control remains separate.
- Confirmed the dialog and CSV with equal and changed values, a missing or extra model face and an
  additional unmatched printed circle. Registering a second view preserved the first reviewed pattern.
  All 39 affected tests passed. The focused drawing and
  translation run passed 35 tests. Still open are repeated callouts encoded as separate model
  characteristics per hole, compound leaders, sections and whole-drawing verification. Reconstruction
  remains in §8.36 and QIF stays last in §8.37.

### Register auxiliary views along inclined hole axes

- Checked PLAN §8.35 against docs/Roadmap.md. The model now groups analytic cylinders by their
  common axis direction and projects their circular rims into the perpendicular plane. Complete
  angular coverage and depth remain separate checks. Complementary STEP arcs can have slightly
  different fitted centers. Their cylinder’s axis supplies a stable projected center and radius.
- D2MI 904 sheet 2 now matches 14 printed rings. The four additional rings are the 3.175 mm and
  4.7625 mm steps on the holes at (63.5, 63.1952) and (60.325, 6.35) mm. Tilting the real STEP
  faces about an oblique axis preserved all 14 associations, including the split face pairs.
  Rotating the PDF sheet by 28 degrees independently preserved them too. The plotted leader still
  identified the position control on the inner diameter. Two identical groups on differently
  inclined planes stayed open. All 24 affected tests, 32 focused drawing cases and the translation
  completeness test passed.
- Still open in §8.35 are elliptical projections, sections, non-circular targets, repeated-hole
  callouts and whole-drawing verification. §8.36 covers reconstruction and §8.37 keeps QIF last.

### Register a principal view at any angle on the sheet

- Checked PLAN §8.35 and docs/Roadmap.md. Two separated circle centers give candidate scales and
  rotations. The fit checks the remaining centers and radii, including reflected views. Competing
  fits retain only their shared face associations. Distances are processed in bounded blocks.
- A second PDF made by rotating the entire NIST D2MI 904 sheet by 28 degrees matched the same ten
  sets of STEP faces. The selected rectangle contained 19 circles after rotation and 18 before it.
  Generated PDFs exercised rotated and mirrored views through the dialog. Tests also cover rounded
  coordinates, an extra circle, a second equally plausible pattern and threefold symmetry.
  All 21 affected tests and all 31 focused drawing cases passed.
- The projection direction is still a principal axis of the model. Views along inclined bore axes,
  sections, non-circular targets, repeated-hole callouts and whole-drawing verification remain open.
  Drawing reconstruction follows in §8.36 and QIF stays last in §8.37.

### Follow plotted leaders from a diameter row shared with a control frame

- Checked PLAN §8.35 and docs/Roadmap.md. A triangular arrowhead may be filled, outlined in a single
  path, or assembled from separately plotted segments. Its contour must close. A hatch inside the
  triangle is allowed. A branch leaving the triangle or a quantity prefix such as 2X prevents an
  automatic association via the diameter row above a frame.
- In the review dialog, D2MI 904 sheet 2 registered ten circles and automatically associated the
  0.005 inch position control with maximum material and A|B|C to the cylinder at (63.5, 63.1952) mm.
  The STEP reports the same control on both half-cylinder faces. Several other controls carry the
  same printed value. The repeated-hole callout and the separate counterbore frame stayed open.
  All 30 affected tests and 28 focused drawing cases passed.
- Multiple-hole leaders, sections, non-circular targets and whole-drawing verification remain open.
  Reconstruction is §8.36 and QIF remains last in §8.37.

### Register hole patterns and follow leaders on PDF drawings

- Checked PLAN §8.35 against docs/Roadmap.md. The review registers a selected principal view
  against the exact cylindrical boundaries of a single part. A straight or bent unbranched leader
  with a filled triangular arrowhead can identify the model PMI even when a different feature has
  the exact printed value. The reviewer can select the target ring directly and confirm it in the CSV.
- On sheet 2 of D2MI 904 the selected main view returned ten matched circles. The hole at sheet
  pixel (384.35, 296.65) maps to both half-cylinder faces at model (6.35, 25.4) mm, radius
  2.38125 mm. This initial stage required manual target selection on the reference sheet. Constructed PDF/solid pairs
  separately verify automatic leader tracing, changed values, branching, rotation, symmetry,
  separate blind holes at the same projected location, and cancellation on a page change. A conflict
  with an earlier approved value-only match reopens the finding. All 15 affected tests and all 22
  drawing comparison and registration cases passed.
- Next in §8.35 are compound leaders, oblique views, sections and non-circular features. Raster-only
  annotations can still be read and reviewed. Feature registration currently requires vector circles.
  Whole-drawing completeness and §8.36 reconstruction remain open, with QIF last.

### Inclined dimension text in a selected drawing region

- Checked PLAN §8.35 and docs/Roadmap.md. Dragging a region around a single graphical dimension
  now also tries a fitted baseline and both reading directions. A transcription needs the same result
  at multiple angles. Conflicting readings stay open. The drawing retains the original region.
- A raster dimension from D2MI 904 read .005 inch (0.127 mm) in PDFs at 25°, 55°, 135° and 224°.
  A standalone leader and two stacked labels did not produce a single dimension. Automatic discovery
  of oblique unframed annotations and leader registration remain open. CSV uses a format-neutral
  source ID so a QIF characteristic identifier can be traced correctly. A second experiment with
  the 2.016 inch callout recovered all four rotated values. All 19 affected tests passed.

### Review model PMI against a drawing PDF

- Checked PLAN §8.35 against docs/Roadmap.md. File → Compare PMI with 2D drawing opens a separate
  review window. The sheet keeps each annotation’s location, and the model view remains interactive.
  Confirm a model association after checking the view and leader. Repeated detail views can refer to
  the same PMI. Ambiguous candidates, unsupported annotations and missing units remain open.
- A real D2MI 904 drawing and STEP pair agree on a 2.016 inch basic dimension (51.2064 mm) and on
  0.005 inch flatness and position controls (0.127 mm). The position test includes least material
  and the ordered datum system A, B, C. A raster crop exercises the path without a PDF text layer
  even when the local NIST archive is unavailable. The same crop is verified at 0°, 90°, 180° and
  270° with its original datum order and sheet location.
- Automatic leader/feature registration, inclined annotations, composites and whole-drawing
  completeness are still open in §8.35. Reconstruction remains in §8.36 and QIF is last in §8.37.
- Checked a frozen macOS PDFium executable against sheet 2 of the same source. It read the three-page
  document and rendered the selected sheet. A complete macOS app build contains the PDFium dynamic
  library and dependency license files. Its self-test loaded 117 faces and 23 PMI. All 12 sheets in
  the six local D2MI engineering drawings rendered and returned sheet-relative annotation regions.
- All 146 affected tests passed. The full offscreen suite passed 667 tests and skipped the eight
  display tests. All eight also passed separately on the macOS display. The 21 graphical PMI
  conversion and STEP round-trip tests passed separately.

### Different position diameters and floating orientation zones along one axis

- Checked PLAN §8.20 and docs/Roadmap.md. All supported controls on one rigid cylindrical feature in
  one datum frame retain their own native or projected interval. The shared actual size determines
  each control’s effective diameter independently, including opposite material conditions and separate
  caps. The intervals survive the 3D chain JSON round trip with reproducible Monte Carlo results.
- For Ø0.2 at stations 20–30 mm and Ø0.1 at 35–45 mm the total range at zero is 0.44 mm. A floating
  Ø0.05 orientation zone on the native 0–20 mm cylinder with Ø0.2 position at 20–30 mm gives 0.30 mm.
  An analytic test requires three active circles and independent radial and tilting loads. A short
  intermediate interval checks numerical conditioning. Across 200 generated interval sets the largest
  difference from an independent four-variable SLSQP optimisation was under 0.00000004 in model units.
  All 50 cases selected by the affected-test runner passed. The focused projected-zone, material and
  feature-variation suites passed all 52 cases.

- For the next PLAN §8.35 package, the local NIST archive contains the CTC-01 model specification
  and six D2MI engineering drawings. Rendered CTC-01 shows the same 25 ±0.15 diameter callout and
  position frames as the model. Its PDF text layer contains only the caption and revision information.
  The six D2MI PDFs likewise return plotting metadata as text. A drawing comparison needs the visible
  vector annotations or their rendered image to cover these reference files.

### Simultaneous projected position zones on a rigid axis

- Checked PLAN §8.20 and docs/Roadmap.md. Equal-diameter position controls with the same datum frame,
  material condition and maximum geometric tolerance share the two outermost constrained stations.
  Checked nested and separated projections, projections from opposite ends, and a projection together
  with the physical cylinder. Reversing PMI order or rotating the assembly preserves the bounds.
- Two Ø0.2 mm intervals at 20–30 and 35–45 mm yield a 0.52 mm total range at station zero in the
  measurement and exported 3D chain. With a common MMC bonus capped at Ø0.4 mm the range is 1.04 mm.
  All 23 affected tests passed. Different effective widths or floating orientation controls on different
  intervals remain open.

### Tooth-to-tooth variation in the cylindrical gear analysis

- Checked PLAN §8.27 and docs/Roadmap.md. Each flank map cell now includes the peak-to-peak deviation
  of the individual tooth positions relative to equal angular spacing, expressed on the fitted base
  circle. The gear table and PDF give the largest pitch-circle range over the evaluable sections.
  CSV and JSON contain the ranges over the measured radius and width. A missing angular sector and
  duplicate crossing invalidate the cell even if the total crossing count looks correct.
- A single tooth of a generated 24-tooth gear was rotated by the equivalent of 0.060 mm on the base
  circle. The STEP and STL round trips recovered 0.060 mm within 0.003 mm on both flanks. Periodic
  angle crossings, CSV values and the PDF summary are covered. All 14 affected tests passed.
  The result describes variation in the supplied geometry. Production grades and load response remain open.

### Analysis mesh quality on previously displayed models

- The 42.85 MB STEP assembly supplied 28,800 triangles across 14,400 faces. Drawing 8,000 surface samples
  took a median 11.3 ms across five runs versus 156.2 ms at the preceding revision. All point coordinates
  and face indices matched exactly. These timings cover sampling after extraction, excluding loading and
  the remainder of the comparison. An additional regression spans empty faces, zero-area triangles and a
  processing block boundary.

- Checked PLAN §§6 and 8.1 against docs/Roadmap.md. Comparison, deviation mapping and scan inspection now
  reuse refined meshes for the lifetime of the loaded model. A 12 mm sphere displayed with 58 triangles
  yielded 11,936 analysis triangles at the 0.01 mm setting. The largest radial error measured at their
  centroids was 0.00761 mm. On the development Mac, extraction took 29 ms initially and a median of
  0.041 ms over ten subsequent calls on this single face.
- Tests cover simultaneous requests on two instances, curved trims on a planar cap, and a face supplied
  only as triangles. NIST CTC-01 against its changed variant reported 111 unchanged, four changed, two new
  and four removed faces. All 56 affected cases passed. Persistent disk caching and interactive display
  levels remain open.

### Tolerance frames without a supplied writing plane

- Checked PLAN §§8.4, 8.15 and 8.18 and docs/Roadmap.md. Planar multi-cell frames can establish their own axes.
  The reader rejects conflicting interpretations and nonplanar annotations. Eight NIST STC-06 PRC tolerances
  match the separate semantic AP242 reference, including Ø0.381 mm with E, A and B and Ø0.635 mm at maximum
  material with A, B and C. The PRC review is stored in the project. Combined native STEP export remains
  available for STEP inputs.
- NIST FTC-08's flatness frame reads 0.762 mm in free state. The independent AP242 reference specifies the
  same modifier. The inner letter distinguishes it from maximum material and the cell boundary prevents a
  damaged or unknown modifier in the value cell from being interpreted as a datum. The retained modifier and
  face association were checked after native STEP export. All 62 affected cases passed for the inferred frames
  and compartment checks.
- Across the preceding search/stacked-dimension change, the full suite passed 639 cases off screen, with
  eight display cases separately exercised on screen. The affected selection passed 239 cases. The real-window
  selection passed all eleven cases, including cancelling a graphical search during a model change.
- A separate experiment for the large-assembly tessellation item in the Roadmap found that requesting 0.01 mm
  from an already coarse-meshed 12 mm sphere still returned 58 triangles with 1.755 mm deflection. Explicit
  OCCT remeshing produced 11,936 triangles with 0.00761 mm deflection. Carry this comparison accuracy case into
  the next package, including mesh-only faces and reuse of finer triangulations.

### Search graphical lettering before semantic review

- Native text also stays searchable under its original wording. The PRC parser previously retained text codes
  internally but dropped them when assembling renderable markups. A rotated, locally scaled inch part with
  the literal ⌀0.5 ±0.01 now displays a text rectangle and proposes 12.7 ±0.254 mm. STC-06 exercises the
  existing real-file path. The positioned literal uses a constructed PRC markup-code sequence.

- The PMI list starts recognising graphical entries on the first content search. It retains temporary results
  across queries, cancels pending recognition when the search is cleared, and drops the index on model switch.
  This adds no OCR to ordinary file loading. A search for value 0.75 and datum C in the original graphical
  AP203e2 model returns the two position frames. The diameter string also finds its source callout directly.
- Recognition runs in a cancellable worker using snapshots of the graphical annotations. A stale result cannot
  populate a newly loaded model. Search and review share the same recognition rules.
- Checked PLAN §§8.4 and 8.18 and docs/Roadmap.md. Stacked deviations and absolute limits now survive review and
  STEP reimport (including zero on either side), while degree signs and parentheses retain the meaning of angular
  and reference dimensions. A lone letter on an unframed note stays a note. Composite controls and additional
  glyph sets remain open.

### Planar lettering in the graphical PMI conversion dialog

- Checked PLAN §§8.4, 8.18 and 8.28 against docs/Roadmap.md. OCR runs when a graphical entry is reviewed.
  It reads projected curve strokes and rasterises triangle interiors directly. A reference test removes every
  curve and the original feature semantics from the flatness callout in NIST CTC-01. The dialog proposes 0.2
  from the filled digits, and the exported characteristic reopens on the selected face with every source entity intact.
- An independent single-stroke drawing on an oblique plane reads 27. The AP203e2 reference supplies a 25 mm
  diameter with ±0.15 deviations and a position frame with A, B and C. A profile with an additional indication
  outside its frame is left for manual review. Unknown letterforms, stacked deviations, freeform notes and
  composite frames required review at that stage. All 23 affected regression tests passed. The later search and
  stacked-dimension changes are recorded above.

### Graphical PMI to semantic PMI and native STEP export

- The Tools command reviews a complete source model. The PMI list can start the same review on a selection.
  The reviewer confirms each characteristic and its faces while looking at the original annotation.
  STEP text literals and QIF text supply machine-readable values. PRC markup types and names can suggest a kind.
  Clear geometric size proposals are identified as measurements. Stroked lettering still needs human reading.
- The writer appends a confirmed characteristic to the original callout, preserves absolute limits, and
  reports missing or occupied callouts before appending any entities. Removing a repair restores its source entry.
  PRC and QIF conversions are project data. Native STEP is the verified combined interchange format.
- A reference test removes all semantic PMI from NIST CTC-01, drives the review from the Tools menu and saves
  a STEP copy. Using the reference for the review, all eight measured dimensions, six tolerances and three
  datums match on reimport. All original STEP entities and all 23 callouts in MBD_0 survive. OCCT also reads
  the new associations. A separate text-literal example derives the value directly from the STEP presentation.
  Packed STEP inputs (ZIP and gzip) and Part 21 files use the same writer and export a plain STEP copy.
- Two original graphical-only NIST models are included as compressed regression fixtures. CTC-01 AP203e2
  supplies 21 curve annotations and 19 explicit face associations. Its radial dimension on face #605 was
  confirmed as a diameter and reopened as 20 mm in an AP242 Edition 3 copy. The supported AP203e2
  mapping was also tried on CTC-03 and CTC-05. Other protocol identifiers and unmapped structures are reported.
  The NIST source files have pre-existing OCCT warnings about annotation-plane fill styles.
- FTC-08 exposes 273 tessellated faces through the OCCT transfer map. Confirming one flatness tolerance on
  face #7581 leaves the other 59 annotations graphical and preserves all four views on STEP reimport.
- Checked PLAN §§8.18 and 8.28 against docs/Roadmap.md. Stroked-text OCR remains open. The drawing comparison,
  drawing reconstruction and QIF work retain their order at the end of the plan.
- Verification covered all 638 collected cases on the Mac. The full off-screen run passed 621 and deferred its
  eight display tests, which passed on screen. All nine separately collected AP203 conversion cases passed.
  The affected-test run passed 308 cases. Two menu-to-export workflows also passed in a real Cocoa window.

### Bevel tooth traces and material-dependent or projected feature tolerances

- The tooth centreline is measured from the two flank intersections at successive cross-sections.
  With a compatible mate, a supported pitch cone and confirmed tooth-band ends, the local tangent
  at mid-face gives the mean spiral angle. The 12/24-tooth reference with a specified angle of 28°
  gave 28.009° right-hand and 28.006° left-hand on the B-rep. STEP and STL tests cover both members
  and both hands. An individual gear can establish hand and, for a confirmed straight trace, 0°.
  Numerical angles for single spiral gears with unknown pitch cones remain unresolved.
- For measured rigid bores and pins, one actual size drives both the material bonus and the surface
  displacement. Worst case respects a geometric tolerance cap and Monte Carlo samples inside the
  corresponding zone. The exported 3D chain keeps this dependence when reopened. For a 6 ±0.2 mm
  pin with diametral position 0.2 mm at maximum material, the positive surface point can move
  −0.4 to +0.2 mm. Reversing to a bore gives −0.2 to +0.4 mm.
- Projected intervals use the PMI exit face, height and offset. The original FTC-07 STEP file
  specifies 10.795 mm from the exit at Y=12.700 mm. The assembly solver checks the shared edge.
  Separate controls check projection from the opposite end, lever arms, and combined position and
  orientation tolerances. The displayed construction threads in FTC-10 use their stated exit plane.
  A millimetre-to-inch STEP round trip preserves the zone, location, material limit and tolerance cap.
- Checked PLAN §§8.20, 8.27 and 8.27a and the Roadmap. Material-boundary datum simulators, deformable
  features, simultaneous controls on different projection intervals and manufacturing-system
  identification still require further work. Drawing comparison, drawing reconstruction and QIF
  retain their order under §§8.35–8.37.
- All 192 affected tests and all eight on-screen checks passed. A separate overlapping run of the
  nine gear, tolerance and STEP integration test modules passed all 105 cases.

### Worm stage speeds and common datums in assembly variation

- The operating point resolves rotation about each displayed shaft axis from the worm hand,
  contact side, number of starts and wheel tooth count. Both STEP and STL imports of a generated
  left-hand pair gave −100 rpm at the 18-tooth wheel for +900 rpm at the two-start worm.
  A downstream 16:32 spur pair reverses and halves the wheel speed. The UI and CSV, JSON and PDF
  report the result. The equations assume engagement. Backdrivability under load is unknown.
- Assembly variation treats A-B as one reference. Each coaxial bearing seat contributes its
  centre displacement to the fitted axis. Coplanar pads facing the same way contribute to an
  area-weighted plane. The model propagates each member's displacement to the measurement
  location, including points beyond the supporting seats. A STEP write/read test uses the example
  gearbox shaft. The assembly measurement, contributor ranking and exported 3D chain agree with
  the analytic interpolation and extrapolation results.
- The AP242 reader and writer retain simple modifiers on individual datum reference elements.
  In the NIST FTC-10 file, E, F and G each carry their own maximum material modifier. Such
  conditions need an additional physical datum model and leave the requirement verdict open.
- Checked PLAN §§8.20, 8.27 and 8.37 and the Roadmap. Further work includes
  component-specific friction and locking characteristics. Drawing comparison precedes
  reconstruction from drawings, with remaining QIF work last.
- All 264 affected tests passed. The overlapping 86-test mechanics and STEP integration selection
  and the English UI translation check also passed.

### Ravigneaux gearsets and limited-slip differentials

- PLAN §8.27 and the Roadmap now cover a Ravigneaux set with two independent suns, a ring and a
  common carrier. A generated seven-gear assembly gave the same eight meshes through both STEP
  and STL. With the carrier held and the large sun at 900 rpm, the ring turns at −480 rpm and
  the small sun at −1,800 rpm. The operating point and REXS export preserve the shared carrier
  kinematics and mesh membership, respectively.
- A rotated six-gear STL exercises parallel-axis helical differential recognition. It requires
  two separate, opposite-hand coaxial side gears and two complete three-mesh pinion chains.
  Symmetric bevel and helical differentials expose four operating assumptions in the dialog,
  CSV, JSON and PDF. A rigid lock enforces equal speeds. Open, TBR and plate-clutch models
  report the permissible output torques for steady driving. At 200 Nm carrier input and 40 Nm
  side-to-side clutch capacity, the slower output can receive 100–140 Nm and the faster one
  60–100 Nm in forward drive. Their sum is constrained to 200 Nm.
- Checked PLAN and the Roadmap. Manufacturer-specific friction, engagement transients and overrun
  behaviour remain open. These changes were tested on generated assemblies. Drawing comparison
  (§8.35), reconstruction (§8.36) and QIF (§8.37, last) retain their order.
- Verification passed for all 57 affected tests, all 56 tests in the eight gearbox integration
  modules (overlapping selection), and English UI translation coverage.

### Stepped planetary gearsets

- PLAN §8.27 now covers one-piece planets with two tooth bands. Recognition matches each band to
  its sun or ring mesh using the identity of the imported body, including repeated component names.
  Two distinct pin axes and consistent tooth counts are required. The calculated speeds assume both
  meshes engage. Relative tooth phase and assembly feasibility remain unresolved.
- The operating point combines these sets with other stages. The power-flow table, JSON, CSV and PDF use
  the compound ratio. REXS attaches the sun-side and ring-side mesh to their corresponding gear bands
  on the same planet shaft. Tip clearances also retain their gear assignment when the order is reversed
  or two gear names match.
- A generated 18/14/20/52-tooth assembly produced the same results after STEP and STL import. With the
  ring fixed, 1,360 rpm at the sun gave 450 rpm at the carrier. With the carrier fixed, 910 rpm at
  the sun gave −450 rpm at the ring. The UI export test couples the carrier to a second stage and
  recovers 112.5 rpm. Splitting each planet into two loose bodies preserves the four candidate meshes
  and removes the compound-set assignment. All 35 affected tests passed.

### Multistage gearbox reverse engineering

- The **Operating point** tab under **Tools › Analyse gearbox** combines fixed cylindrical and
  external bevel stages, simple planetary sets and symmetric open bevel differentials. The user can
  set signed speeds, hold shafts stationary, choose the carrier axis of an ambiguous cross and
  connect coaxial shafts. For reverted trains with independent coaxial input and output shafts,
  the user can separate ordinary coaxial gears and couple the intended intermediate wheels.
  Recognised planetary and differential members keep separate ports. Orbiting pinions cannot create
  spurious fixed-axis stages, including on the axis line of an axially displaced spur gear.
- Speeds are solved per connected component using exact rational elimination of tooth-count relations
  and user inputs. Free members remain undetermined even after thirteen 10:1 reductions. Inconsistent
  inputs affect their own connected train. Reference axes, constraints, selected topology and speeds
  are available in the dialog and its CSV, JSON and PDF reports.
- A complete STL assembly with a 12:24 spur stage driving an 18:54 planetary set gives −600 rpm
  at the sun for 1,200 rpm input. Holding the ring gives −150 rpm at the carrier. Holding the carrier
  gives +200 rpm at the ring. In a synthetic three-bevel differential, STEP and STL independently
  give +1,000 rpm at the second side gear with the first held and the carrier at +500 rpm. Tests also
  cover two cascaded planetary sets, a symmetric four-gear cross and opposite signed axis conventions.
- Corrected the REXS planetary stage hierarchy. Both central shafts, each planet shaft and their
  actual meshes have separate roles. Confirmed tooth bands on one physical body keep a shared
  identity even when other coaxial wheels are assigned to independent shafts.
- Verification: all 67 affected tests passed. The operating-point PDF was also rendered and
  inspected. Manufacturer reference gearboxes were unavailable for this round.

### Bevel gear pair measurements

- Continued gearbox reverse engineering in PLAN §8.27a. The pair data sheet now gives each
  gear's outer and mean transverse module, outer cone distance, face width on the pitch cone and
  width ratio. Its shared face width uses the overlap of the bands measured from the common apex.
- The existing interior transverse sections identify the cone. Full-width measurements additionally
  require the tooth contour near each end and flat end facets around the circumference. An open
  mesh or an unconfirmed end leaves that gear's full-band values and the overlap unresolved.
- Verified through STEP and STL import with synthetic 12- and 24-tooth gears covering cone
  distances 18–25 and 20–26 mm. The 5 mm shared width and both sets of modules reach the results
  dialog and the exports. The open-end mesh control retains conical-tooth recognition.
- Checked PLAN and `docs/Roadmap.md` against the implementation. Spiral angle and hand at the pitch
  surface remain open, as does independent evidence for the manufacturing system. Drawing comparison
  (§8.35), reconstruction (§8.36) and the final QIF stage (§8.37) keep their order.

### Earlier results from the same day

- Reviewed the normal STEP import and viewer/comparison paths. The main bottleneck was a linear
  OCCT label lookup for each face. The importer indexes transferred entities once. Part 21
  parsing indexes entity types and respects STEP strings across comments and statement boundaries.
  In the viewer, shared edges are drawn once and disabled thumbnails do no background work.
  Exact comparison prunes by B-rep lower bounds and reuses placed triangulations.
- Mac benchmarks against 295603f: a generated 6.91 MB STEP with 400 solids, 2,400 faces and
  141,220 entities loaded in 1.58 s (previously 32.94 s). First display of the loaded model on
  the same screen took 0.339 s (previously 0.376 s). CTC-01 vs. its changed variant took
  2.17–2.26 s (previously 6.50 s). The face mappings, statuses and B-side deviations matched
  the baseline checksum. The PMI-rich NIST FTC-09 file (6.11 MB, 64 PMI, 23 views) loaded in
  1.48 s (previously 2.03 s). The STEP face, colour, PMI and view associations checked on CTC-01,
  its variant and FTC-09 also matched. A second generated STEP (42.85 MB, 2,400 solids, 14,400
  faces, 847,220 entities) loaded with every face assigned in 11.86 s on the revised path.
- Fixed bootloader splash shutdown. PyInstaller 6.22.3 removes the connection variable when it
  imports its splash module. The application reuses the connected module. With its actual RPC
  implementation and a simulated socket the main-window path sent EOT and closed the connection.
  A packaged interactive Windows startup still needs a visual check.
- Integrated the earlier 1D/3D chain wiggle work. The 1D example follows four real faces. The 3D
  chain can animate closure limits or individual links and carries the moving assembly instance.
  Mating feature origins can lie far from the solid, and standalone templates have no model frame.
  One-sided planar stops, measured-feature displacements and ranked datum frames now contribute to
  assembly variation. The ranking, chain and report identify incomplete inputs. Combined
  position/orientation zones on a cylindrical feature use an exact support bound for arbitrarily
  directed sensitivities at its two ends. Remaining analytical limits include deformable form, common
  multi-feature datums and projected or material-modified zones on measured features. Monte Carlo independently samples the projected feature contributions.
- Gear analysis covers involute, parallel-sided and serrated shaft/hub profiles, repeated straight
  tooth tip chamfers and cylindrical root fillets, plus conditional bevel and worm pairs. Known
  parameterised shapes and STEP round trips check these branches. No manufacturer reference was
  available. Cutting system, production fit and contact under load require independent evidence.
  Cylindrical pairs require axial overlap, also used for the overlap contact ratio. Left and
  right tooth-averaged flank maps export to CSV, JSON and PDF. PDF reports include sourced findings.
- Gearbox reverse engineering has separate selection and whole-model commands. On the STL and OBJ
  tests it recovers 14:20 and 16:24 stages on three shafts from one mesh object, and the inclined standalone
  17-tooth helical gear. A stepped shaft with two axial tooth bands is measured per band, including
  a 0.7 mm band found between the original sampling planes and tooth counts changing at a shoulder.
  A general gear note on such a shaft remains unassigned. Stage ratios can use a chosen reference shaft. Checked reversed reference,
  mixed spur/bevel stages, independent trains, branches and inconsistent cycles. Coaxial wheels imply a
  rigid link unless the planetary calculation supplies a separate operating case.
- Replacing a load, comparison, gear analysis or view preview now discards stale Qt signals and project actions.
  Finished loader threads release their models. Windows can close during a native read and application
  exit joins remaining workers.
- Generated PMI frames account for file annotations and projected overlaps in every shared saved
  orthographic view. Perspective placement and leader crossings remain open.

### Verification

`pixi run test` completed with 458 passing in 704 seconds. The eight display-dependent cases
skipped in that run all passed on the physical Mac display (60 seconds). The English translation
inventory is complete. The gear PDF was rendered and inspected, including the numerical data sheet,
left/right flank maps and sourced findings. Windows bootloader IPC was checked separately as above.

### Plan and roadmap check

PLAN §§6, 8.1, 8.16, 8.20, 8.27/8.27a and 8.33 and the corresponding rows in
`docs/Roadmap.md` reflect the implemented scope. The UI plan still awaits its user study.
The new drawing comparison (§8.35) and reconstruction of geometry with dimensioned PMI (§8.36)
remain planned, in that order. Remaining QIF work is the last milestone (§8.37). Other open
items include large-assembly levels of detail and persistent mesh caching, STEP-XML, JT PMI/B-rep,
advanced PRC/U3D, editable drawing dimensions in DXF and AP242 mechanism fixtures.

## Historical handoff, 2026-10-28
All work on `main`, pushed; no other branches. Version 0.2 released (tag v0.2). Full suite last green on
the Mac (200 tests incl. the new ones, ~11 min); `pixi run test-schnell` skips the six `langsam` tests.

Side session 2026-10-29 (branch `claude/ansicht-kontrast-3e4797`, merged into main): user reports
"PMI im Dark Mode nicht lesbar" and "Legende für Toleranzzonen". Root cause: OCCT shows the background gradient
gamma-encoded while unlit PMI keep their value – the dark scheme's 3D background appeared mid grey (#7b818b), where no
colour reaches 4.5:1 on both ends. Dark 3D background now really dark; PMI colours per scheme in `ui/thema.py`
(`pmi`, `pmi_erzeugt`, `pmi_vorschau`, `pmi_hervor`, helpers `kontrast`/`lesbar`/`hintergrund_3d`), ≥ 4.5:1 against
both ends as given and encoded (test `tests/test_kontrast.py`); own background: scheme colours made readable; own PMI
colour kept, settings warn. Zone legend bottom left (`AnsichtBasis.zonen_legende`, `OcctAnsicht._baue_zonen_legende`;
test `test_zonen_legende_nur_gezeigte_rollen`, on screen in `test_navigation_und_klick`). Zones now survive a scene
rebuild (theme switch). Checked on screen (Retina) light/dark with the shaft and FTC-10 zone examples. Seen, not fixed:
the Funktion panel's datum preview stays when another example is opened; own background colours appear lighter than
picked (gamma); `View.Dump` renders at logical size on Retina (use `bild_qimage` for checks). PLAN/Roadmap: Roadmap row
added (✅), UI_UX_Plan note; no PLAN item affected.

Side session 2026-10-29 (branch `claude/tabellen-maus-338d20`, merged into main): user reports on
table mouse behaviour (UI_UX_Plan stage 2 note, Roadmap ✅, PLAN §8.30). (1) Hovering over cells with drop-downs or
number fields selected the row. Cause found by experiment: Qt makes the cell of a cell widget current and selects the
row whenever the widget gets focus – without a click too (wheel/MouseFocusReason without button, window change, code)
and when an open click-editor (`EIN_KLICK`, CurrentChanged) closes because focus moved into a cell widget (its
FocusOut). `ui/radsperre.py` (app-wide filter) now delivers those FocusIn/FocusOut events with the selection model's
signals blocked and restores selection and current cell; left/right click and Tab still select. (2) Middle mouse
button autoscroll like a browser: new `ui/autorollen.py`, installed by `radsperre.installieren` (no change to
`hauptfenster.py`); item views, QScrollArea, text views; anchor marker child of the scroll area, override cursor,
dead zone 10 px, speed 0.08 px/tick per px, units converted via pageStep/viewport (per-item tables); release after
dragging ends, short click sticky until next click/Esc, wheel ends; not over WA_PaintOnScreen (OCCT viewer) or in
popups; over the frozen first column the table scrolls. Tests `test_ueberfahren_von_zellfeldern_waehlt_keine_zeile`,
`test_mittlere_taste_rollt_wie_im_browser` (function, chain, 2D chain tables). Not checked with a real mouse on screen
(synthetic events only; real cursor moves could not be generated from a script) – user should try it.

Side session 2026-10-29 (branch `claude/laden-vergleich-a08067`, merged into main): two user
reports. (1) Loading another file kept old data: new `Hauptfenster._modellzustand_zuruecksetzen` (called from
`zeige_ergebnis` whenever a different result is shown, and from `schliesse_modell`) clears function → tolerancing
(`setze_modell`, preview), 1D chain (`lade_datei(KettenDatei([]))`: links, requirement, materials, temperatures,
approval, scenarios), 2D/3D chains, measurements, quick measure, comments, collision, assembly, zones, helper lines,
datum colours, sections, balloons, focus, selection, inspector. Projects/chain files restore afterwards; "Add model"
passes `zuruecksetzen=False`, re-alignment keeps it (same new-state object); guided flow stays. (2) Comparison
display: `_vergleich_anzeigen` is a function of (mode, highlight switch), colour map/material follow
`_aenderungen_sichtbar`; `ansicht3d`: colour-only rebuilds keep the camera (`_baue_szene(kamera=False)`, also on
`setze_thema`), pending camera for a not yet started view (`_kamera_offen`), `setze_kamera_daten` stops a running
flight, `showEvent` refits the depth range. PLAN §8.31 notes, Roadmap ✅. Tests `test_neues_modell_leert_werkzeuge`,
`test_vergleichsanzeige_nach_modus_und_haken` (offscreen), `test_vergleichsmodi_kamera_und_darstellung` (on screen,
`DG_BILDER=<dir>` saves a screenshot per step). Not reproduced literally: the "semi-transparent New" – likely the
colour map shown in New after switching (now hidden without the switch) or a stale depth range after the hidden view
was rebuilt (now refitted on show); user should re-check with the example.

Side session 2026-10-29 (branch `claude/ketten-wiggle-7d70d7`, integrated 2026-11-20): user reports
"3D chains: building, display and wiggle not clean" and "1D chain of the example cannot be wiggled". New
`kern/kette3d_anzeige.py` (lines + wiggle of 3D chains: worst case of the closing quantity or link by link, 1:1 /
×10 / ×100 / automatic, real value at the function point, assembly parts move with their link via `Glied3D.teil`);
`ui/kette3d_ui.py` in three columns with ▶/⏸, art and exaggeration combos, view fitted only when switched on or for a
new chain; `Hauptfenster._kette3d_teile` moves parts (`setze_teil_lagen`). Bug fixes: example 3D chain invisible
(`OcctAnsicht._baue_szene_inhalt` now re-shows `hilfslinien`; base `zeige()` clears them for another model);
"＋ Aus Zusammenbau" on rotated chain ends / chains with a base (`kette3d.ausrichtung`). 1D:
`schluss_wiggle.schluss_oder_grund` walks the links along their faces – it fixed the gearbox example moving the
wrong faces (19/22 → 18/23); play button disabled with the reason as tooltip (`ToleranzketteFenster.wiggle_grund`,
`pruefe_wiggle`). Example "kette" is now a 4-face chain on FTC-10 (`beispiele.KETTE_FLAECHEN`, 55 ± 0.7) with chain
picture and running wiggle. Tests: `test_kette3d` (2 new), `test_gui` (`test_beispiel_kette_wiggelt`,
`test_3d_kette_wiggle`, wiggle test extended), screen test `test_3d_kette_sichtbar_und_wiggle`. PLAN §8.33 note,
Roadmap ✅. Open: assembly link origins are the mating feature point (a plane's location point, possibly far from the
part) – correct for the analysis but rotations swing the part in the wiggle; templates are drawn at the world origin
inside a loaded model (no relation to it).


Side session 2026-10-29 (branch `claude/beispiel-welle-abdfe0`, merged into main `db2cd0d`): user request –
the example "Funktion → Tolerierung" now uses a generated gearbox shaft instead of NIST FTC-10 (PLAN §8.33 note,
Roadmap ✅). Generator `werkzeuge/welle.py` → `tests/daten/getriebewelle.stp` (bundled via `beispiele.alle_dateien`),
roles in `kern/beispiele.WELLE_ROLLEN`/`welle_rollen`. `kern/funktion.py`: new roles lagersitz, dichtsitz, nabensitz,
passfedernut, sicherungsringnut; common datum A-B (`BezugVorschlag.gemeinsam`, `Bezugssystem.drf()`); runout/axial
runout/symmetry on turned parts (`_drehteil`, `_passfedernut`, `_ringnut`, context `_Kontext`). "A-B" now resolves in
`toleranzzone`, `plausibilitaet`, `pmi_vorschlag` and is written to STEP as COMMON_DATUM_LIST (`step_schreiben`).
`pmi_erzeugen`: on long turned parts annotations on axial elements lie in the axial plane above/below the part.
Main window: `_beispiel_funktion` (roles from kern.beispiele, front view fitted incl. callouts –
`ansicht.standard(name, pmi_ids)`). Open: the DIN 471/472 groove-diameter classes by size are start values (h10/h11/h12
rule not checked against the standard text); keyway widths are edge-on in the front view (visible from the top).

Side session 2026-10-29 (branch `claude/vergleich-beispiel-b688ce`, merged into main): File ›
Examples has ONE comparison example `vergleich` ("Vergleich: Geometrie und PMI geändert", opens with the colour map,
`Hauptfenster._beispiel_farbkarte` waits for the map with `warten`) instead of `vergleich_pmi`/`vergleich_geo`.
New variant `tests/daten/varianten/ctc01_geo_pmi_deutlich.stp` from `werkzeuge/testmodelle.py` (`deutlich`,
reproducible): OCCT geometry (hole Ø25 at (160, 45) moved +15 mm in X as two half shells like the original, hole Ø25
at (−160, −45) filled topologically – OCCT's Defeaturing would unify all split holes –, 3 mm chamfer at the hole at
(160, −45)), the new B-rep spliced into the original file (`form_einsetzen`: faces/edges matched by sample points,
references re-pointed, removed geometry with its styles dropped, cone angles converted rad → degree); PMI: Position.1
0.75 → 0.5, Position.2 own datum system A|C|B, Perpendicularity.1 removed with its presentation (`pmi_entfernen`),
new Position ⌀0.4 Ⓜ A|B|C on the moved hole via `step_schreiben`. The old small variants stay for the tests.
Core fixes found with it (`kern/vergleich.py`, `kern/vergleich_geo.py`): pure translation detected regardless of the
order of equal faces (`_paare`; before: "rotated 139°"), moved faces beyond the search radius get a face mapping so
their PMI become "PMI verschoben"; sampling: ≥ 5 points per face (`_mindestens`, chamfer cones had none), projected
mesh points outside the face boundary pulled onto the face (spurious 0.037 mm at a Ø35 hole edge). Test
`test_deutliche_aenderung_geometrie_und_pmi`. Checked in the app (screenshots): change list 7 PMI + 4 geometry rows,
material +/− and review walk fine. Open/follow-up: the colour map shows the filled hole only as a small spot (planar
faces refined to diag/40 only, colours per vertex) – a finer refinement where the deviation changes would help.

Side session 2026-10-28 (branch `claude/pmi-darstellung-8f2b0b`, merged into main after UI
work): plan item 6 done – own PMI written to STEP carry their presentation (PLAN §8.28 stage 3,
`kern/pmi_darstellung.py`; reader places part presentation at the instance in assemblies, `praesentation.in_teillage`
called from `ui/lader.py`). `step_schreiben.schreibe(..., grafik=self.erg.grafik)` from the main window would write
exactly the graphic shown in the view (today it regenerates it; layout can differ when other generated PMI exist).
Open: check the file in CATIA (user); own PMI are not added to saved views. Test: `tests/test_step_schreiben.py`.
Then (user request): "Make semantic …" for graphical-only PMI (§8.18 repair) on the same branch – touches
`ui/hauptfenster.py` minimally (`_pmi_befehl` "semantisch", `fuege_pmi_hinzu` replaces the note and keeps the file
graphic) and `ui/panels.py` (context menu entry); tests `test_nur_grafische_pmi_reparieren`, `test_semantisch_machen`.

Side session 2026-10-28 (branch `claude/bezugsverschiebung-39e50e`, merged into main): evening item c
done – datum shift / Ⓜ/Ⓛ bonus in assembly connections (PLAN §8.20 note, Roadmap ✅). `Verbindung.bonus` +
`bonus_quelle` set by `toleranz_aus_pmi` (`_bonus_aus_pmi`: Ⓜ/Ⓛ location tolerances on both faces grow by the
feature's size tolerance, datums with Ⓜ/Ⓛ via `toleranzzone.bezugsverschiebung`); `Baugruppe.zeilen(..., bonus=True)`
includes it by default, `Baugruppe.mc_bonus` draws it; `baugruppe_mass.Analyse` keeps it as its own contributor
(`Beitrag.bonus`, `beitrag_art`) in the table and PDF. No change to `ui/hauptfenster.py`. Test
`test_bonus_und_bezugsverschiebung_in_verbindung` (⌀10 H8, position ⌀0.1 Ⓜ, bolt ⌀9.9). The example
`baugruppe.stp` has no PMI, so its numbers are unchanged. Not checked on screen.

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
- Generated PMI stage 3 (dimension lines, leader arrows) and PMI texts as glyph faces in model space (on the Mac GPU
  AIS_TextLabel draws in screen pixels) – `ed32ec1`; first display much faster (scene built once, previews after the
  view is ready; FTC-10 19 s → 1.5 s) – `f2633bb`. Full suite green after these.
- **JT 10 (§8.32):** build switched to the fork wwmayer/TKJT (JT 10 reading, base of FreeCAD's JT 10 import) plus own
  fixes `packaging/jt/tkjt_jt10.patch` (Move-to-Front codec, unsigned probability values, Lag1 for binary
  coordinates, mesh decoder without crash + coarser LOD fallback in jt2glb), checked against the public prostep JT
  format description; NIST MTC JT 10.5 loads end-to-end (46 276 triangles, correct on screen). Build needs
  `liblzma-devel` (pixi dev). App bundle with DG_MIT_JT=1 not rebuilt yet (liblzma should be collected as a
  dependency of jt2glb – check at the next local build).
- **Stack-up (§8.33):** "Kette im 3D" (whole chain as arrows with dimension/tolerance labels, colours per kind,
  what-if overlay), chain window with splitter, histogram beside the result table, interactive histogram (share at the
  mouse, draggable requirement limits); checked on screen. Plan for the next stages in PLAN §8.33 (purpose of
  functional chains, 1D gaps, 2D/3D research, function → ISO GPS guide, cost-optimal tolerances).
- **Stack-up results:** histogram follows the applicable method (✓; row click switches, overlay of all), traffic
  light for the requirement (window + PDF), manual approval with name/date/comment (`.3dgkette` + PDF); results pane
  gets the height it needs (no overlap); Qt's own buttons German in every window (translator also loaded by the main
  window, so scripts/tests show "Schließen" too). Checked on screen.
- **Released v0.2** (2026-10-28, `packaging/release.py minor --git`, tag pushed) after the full suite was green
  (281 passed, 3 skipped) – commit `eef4130` holds JT 10, stack-up UI, cost allocation, function → GPS, 2D chains.
- **User decisions 2026-10-28:** all proposals accepted – chain plan order as in §8.33, traffic light thresholds
  (Cpk 1.33, 0.27 %), version 0.2, Alt+1…6, directions from the closing dimension; one rendering pipeline for all
  views (done: fixed-function for every view); UI stage 2 still only after the user's review of the UI/UX plan.
- **§8.33 stage 1 done:** cost-optimal allocation with process table (`kern/fertigung.py`), column "Fertigung".
  §8.33 stages 2/3 done: `kern/funktion.py` + window "Funktion → Tolerierung" (roles → datum system 3-2-1 →
  GPS proposal with fits → own PMI → STEP). Stage 4 done: 2D vector loop window (`kern/kette2d.py`, `ui/kette2d_ui.py`). Stage 5 done (by hand): 3D chain window
  (`kern/kette3d.py`, `ui/kette3d_ui.py`). Open: 2D/3D chains from the model/assembly, storing them in files/project.
- **Fix 2026-10-28 (user report, Windows multi-monitor):** 3D picking and the view cube were offset when Qt's logical
  coordinates differ from OCCT window pixels (Windows/Linux use physical pixels; mixed DPI, UI size ≠ 100 %).
  `OcctAnsicht._px` now scales by OCCT window size / widget size (`_occt_faktor`), the cube pick uses the OCCT width,
  the context menu converts back; screen test with QT_SCALE_FACTOR 1.25. Not checked on a real Windows machine.
- **UI:** combo boxes got a visible arrow (theme `pfeil_symbol`, the QSS border had removed Qt's arrow); editable
  chain cells tinted + one-click editing; pivot moves with panning, rotation about the view centre without a set pivot
  (screen test updated); histogram overlay of all methods by default.
- **User reports 2026-10-28 fixed:** colour reading crashed on CATIA complex STYLED_ITEM instances (`farben._stil_ziel`,
  reproduced with the old code); JT in GitHub builds (workflow option, `packaging/jt/bauen.py`, Windows via MSVC – first
  CI run must confirm); CATIA roll ring (`OcctAnsicht._rolle`, screen test); scan hide keeps the tab
  (`scan_verwerfen` for a full reset); arrow when walking the chain. Circle hint for the roll ring → UI stage 2.
- **Fix:** PMI glyph texts drawn unlit (`_unbeleuchtet`) – with the fixed-function pipeline they shone white.
- 2D/3D chains in files/project, CZ hint, scan line profile per section – done (see §8.34).
- **Remaining tolerance zones done (§8.34):** line profile, ACS, CZ/SZ, edges/points, thread axes with Ⓟ, whole part.
- **Tooltips:** rule from the user – every non-obvious control gets a tooltip. `werkzeuge/tooltips.py` lists controls
  without one (main window, docks, all dialogs constructible with the main window as parent);
  `tests/test_gui.py::test_tooltips_vollstaendig` keeps it at zero. Stack-up: tooltips per method/column, spread
  sparkline per link.
- Not done for lack of a verifiable source or test data (kept open in the roadmap): ISO 286 b/t–zc/>500 mm (isofits
  has none of them), surface texture/weld symbols (no sample file), large-assembly LOD (no large model; 3.7 MB STEP
  loads in 2.4 s).

- **Evening order 2026-10-28 ("1–4, then the new UI, then 5–8"):**
  - Item 1 done: assembly variation with thermal expansion at an operating temperature (α from STEP materials,
    dialog "Werkstoffe …"), traffic light per measure, measures at a clicked point ("am Klickpunkt": point to plane /
    point to axis), all in the PDF. Datum shift stays open.
  - Item 2 done (assembly part): "Als 3D-Kette" turns an assembly measure into a 3D chain (one link per part on the
    connection path, LP limits per component); on the example it matches the assembly analysis exactly. Found and
    fixed on the way: 2D/3D → 1D hand-over lost the nominal of untoleranced components (worst case centred wrongly).
  - Windows JT build fixed (MSVC `link.exe` next to `cl.exe` instead of GNU `link`, response file); run 40669857102
    green; Linux/macOS with JT green in run 40669274020.
  - User reports fixed: splash with old logo and jump (launcher image now regenerated and kept until the main window,
    progress text in it); contrast setting reached only the main view → now all views of all windows, filled PMI
    drawn unlit. Side-panel resizing: analysis + fix entered in `docs/UI_UX_Plan.md` stage 2 (not done yet).
  - Later the same evening (user reports, all fixed with tests): JT on Windows (no console window – closing it
    killed the converter; drag & drop of .jt – the main window had its own extension list without JT; clearer error
    text without TKJT "skipping element" notes), zones of half shells (envelopes followed the full axis), editable
    function table (role, fit, tolerance, swap faces, multi-face features), shrinkable chain window (flow layout
    `ui/fluss.py`), assembly measure shown in 3D (only the instance concerned is highlighted – `hebe_flaechen` got an
    instance restriction), section contour edges (`kern/schnitt.kontur_anzeige` from the display mesh, 0.1 s instead
    of 15 s with the exact section), view cube/left click after a lost mouse release (stale gesture state reset),
    docks in scroll areas (window min width 1624 → 805 px), 3D handle cleared on loading another file, wiggle
    button icon-only. Not reproducible here: the thin blue stripe while loading on Windows (asked for a screenshot).
  - Committed `c12604d`. Then: changes tab only with an active comparison (hint + "Zwei Stände vergleichen …"),
    item 3 done (`kern/schluss_wiggle.py`, play/pause in the chain window), item 4 done (median plane ends, joint
    links across parts from assembly connections).
  - Next: UI stage 2 (`docs/UI_UX_Plan.md` incl. all additions of 2026-10-28), then items 5–8.
  - Added to the plan (user, 2026-10-28): live 3D preview of the function → tolerancing proposal (PLAN §8.33,
    Roadmap ⬜); fits well with UI stage 2 (the function window becomes a panel).
  - Fixed: deleting own PMI left their callouts in 3D (view and `erg` share the graphics dict; the view is now
    cleared first); Del/Backspace in the PMI list deletes selected own PMI.
  - Added to the plan (user, 2026-10-28, after UI stage 2): materials in hand-built 1D/2D/3D chains – chain default
    plus per-link override (PLAN §8.33, Roadmap ⬜).
  - Added to UI stage 2 (user, 2026-10-28): CATIA roll band further out, continuous blend into the trackball
    (rounded arcball) while dragging – `docs/UI_UX_Plan.md`.
- Help › "Was ist neu" and the first-start introduction wizard removed (user request 2026-10-28): actions `neu`,
  `einfuehrung`, `Hauptfenster.erster_start` (only showed those two), `hilfe.Einfuehrung`/`SCHRITTE`/`zeige_neu`,
  `version.aenderungen_html`, their translations; settings keys `einfuehrung_gesehen`/`version_gesehen` no longer
  read. CHANGELOG files and the release script stay. Merged into main (`08bd2dc`).

- **Side session (branch `claude/modell-hinzufuegen-f74208`, merged into main):** "Add model"
  (File menu and assembly panel, `kern/zusammenfuegen.py`): further files become parts of the current model (own top
  node, faces/PMI/views remapped, placed next to the model, stored in the project as `zusaetze`). Tests:
  `test_kern.py::test_modell_hinzufuegen_zusammenfuegen`, `test_gui.py::test_modell_hinzufuegen_verbinden_projekt`;
  checked on screen (both models side by side). Limits in PLAN §8.20.
- Same branch, plan item 5: dragging parts in 3D with live snapping (`kern/einrasten.py`, CATIA navigation: left
  drag on a part in the assembly; classic: Alt + left), also at the 3D handle; on-screen test
  `test_bildschirm.py::test_teil_ziehen_einrasten`. STEP kinematics researched (PLAN §8.20): OCCT 8.0.1 parses
  `StepKinematics_*` but does not transfer them, no public sample file – nothing imported; needs a CAD-exported
  AP242 file with a mechanism.
  - UI stage 2 done (`a76d128`, `c17c7b9`, `27bd1e2`): workspaces with panel sets, tool windows as bottom panels,
    one toolbar row (File dropdown left, measure toggle in the measure panel, section/explosion in the structure
    panel), CATIA roll circle with smooth blend, view cube rebuild per screen, selection order (earlier ×0.78),
    editable cells tinted, wheel never changes unfocused fields (`ui/radsperre.py`), smooth panel resizing (fast
    polygonal HLR previews, p90 1088 → 13 ms), comparison always with both trees. Then `eefae08` (example
    function → tolerancing, manual datums), `64e2430` (scan check as a comparison: target/actual modes, side by side,
    review walk with status/comment in CSV/PDF).
  - UI stage 3 done: inspector panel (`ui/inspektor.py`), guided flows "Scan prüfen"/"Spalt messen"
    (`ui/fuehrung.py`, Help › Guided and start page), unified panels (empty-table hints `tabellen.leer_hinweis`, one
    primary button per panel). Tests `test_inspektor`, `test_gefuehrte_ablaeufe`, `test_einheitliches_panel_layout`.
  - Parallel sessions (own worktree branches, merge only after the user says so): item 6 presentation for written
    PMI + "make semantic"; "Modell hinzufügen" then item 5 (live snapping, STEP kinematics); removal of "Was ist neu"
    and the first-start introduction (touches the Help-menu loop in `hauptfenster.py`, which now also lists
    `gefuehrt_scan`/`gefuehrt_spalt`).

- **Side session (branch `claude/kette-lesbar-213437`):** stack-up tables readable (user report "Spaltenbreiten und
  Zellen in der Toleranzrechnung nicht lesbar"). Cause: `ResizeToContents` measures only item text, not cell widgets,
  and the stretched name column wrapped. New `tabellen.spalten_anpassen` (header, text ≤ ~48 chars with elide+tooltip,
  cell widget size hints, row height, numbers right-aligned, per-pixel scrolling, hand-dragged widths kept),
  `zahlen_rechts`, `zeilen_hoehe`, `inhalt_breite`; used in 1D chain (links, results, scenarios, materials dialog),
  2D segment table, 3D editor. Test `test_gui.py::test_kettentabellen_lesbar`; on-screen screenshots at 90/100/150 %
  and as wide/low panel compared before/after. Other panels (assembly, function, collisions) could adopt the helper.
  Extended on request (user reports via the main session): material fields cut off (size hints taken before the
  stylesheet was polished, editable combos sized too small → `_feld_groesse`), 3D editor overlay (18 new spin boxes
  per selection lay over the old ones + cell selection drawn behind → fields built once, NoSelection/NoFocus), and
  one control height in the whole UI (`thema.bedien_hoehe`, spin boxes/tool buttons/menu arrows styled, form label
  proxy style, `werkzeuge/hoehen.py`, `test_bedienelemente_gleich_hoch`). Merged origin/main (materials) first.
  Screenshots before/after (100/150 %) in the session scratchpad, not in the repo.

**Deferred questions for the user** (do not block on them):
- UI/UX stage 2 (workspaces) changes the layout a lot – implement only after you have read `docs/UI_UX_Plan.md`?
- JT: JT 10.5 (NIST) now works; a JT 8/9 file and a JT with colours/PMI from CATIA/NX would still be good tests.
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
- (Checked 2026-10-28 on the Mac: AIS_TextLabel in an annotation plane draws in screen pixels → now glyph faces in
  model space.)
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
| 7 JT via TKJT | ✅ JT 10 via fork + own patch, builds on macOS/Linux/Windows (GitHub workflow option "jt") – was ⬜ (free JT without PMI: `NIST mtc crada assembly.jt` in daten/nist_cad_dl/nist-cad-models-mtc-assembly.zip) |
Details: `docs/Roadmap.md`; future topics: PLAN.md §8 (8.5 tolerance zones, 8.6 annotating, 8.8 stack-up,
8.10 PMI editing/advisor, 8.11 CATIA, 8.15 PRC/3D PDF, 8.16 generated PMI, 8.17 open formats, 8.18 PMI as semantics or
graphics only, 8.19 QIF graphics, 8.20 3D tolerance analysis,
8.21 clash/band/intersection analysis, 8.22 plausibility check, 8.23 scan against PMI tolerances).

## Historical priority list (October 2026)
0. Evening order 2026-10-28 – items 1–7, UI stages 1–3 and the follow-up list are done and in main:
   materials in hand-built chains (`a4bda25`), live 3D preview for function → tolerancing and the unified panel order
   (`7692a6a`), datum shift in the assembly variation (merge `e5ac96e`), readable chain tables and one control height
   in the whole UI (merge `56da1be`). Full suite 336 passed + 6 on-screen tests green on `56da1be`; a local build
   (`packaging/build_mac.sh --ohne-tests`) was made for the user's review of UI stage 3.
   UI stage 3 accepted by the user on screen (2026-10-28). Acceptance test with users (≥ 80 %) not run.
   2026-10-29: user fixes (view cube hover lower left on Retina, multi-selection order lost after the PMI list
   re-highlight, measured elements shown as selection, compact buttons, larger tab ✕, fitted columns, wheel guard,
   frozen first column); CI fixed (test windows were never deleted → setStyleSheet repolished all of them, Windows ran
   into the 300 s timeout; slots on deleted windows; Windows font widths; JT fake converter as .cmd) – full suite now
   ~9 min instead of ~40. Plan items done: traffic light/approval for 2D/3D chains and assembly measures (`0136119`),
   chains from the model (`17a857e`), sliding contacts in 2D chains (`9238077`). GitHub build run 40826336669 started.
   A session card "Erzeugte PMI: Überlappung je gespeicherter Ansicht" waits for the user to start it.
   Later on 2026-10-29: measured-face tolerances in the assembly variation (`400a251`, first part of "automatically
   from the model"), "An Bezügen" connect at datum features (`49b8c3d`), advisor stage 2 (`82919f2`), sliding
   contacts in 3D chains (`3bc5419`). All chain/assembly roadmap items of the order are done (open in §8.20: full
   feature torsors inside a part, one-sided contact). Windows CI: `test_toleranzkette_fenster_verkleinerbar` gives
   715 px on the Windows runner (macOS/Linux fine); the test now prints the widest children – read them from the
   next Windows run and fix that widget.
   Later on 2026-10-29: GitHub builds green on all platforms (run 40833502869). Examples merged without a test run
   after the merge (user's choice): gearbox shaft for function → tolerancing (`db2cd0d`), one comparison example with
   clear geometry and PMI changes (`bc91a17`). Bevel gears dropped (user: no generator, gears = analysis only).
   Paused by the user, to resume later: functional-chain open items (branch `claude/fmk-offen-804965`, no code yet,
   plan in the shared note `fmk-offen.md`) and spline recognition (branch `claude/passverzahnung-a24808`, empty WIP
   commit with the plan, note `passverzahnung.md`). QIF Plans export waits for the user's OK to download the QIF 3
   XSDs; the cylindrical gear data sheet waits for the user's decision (gears paused for now).
   2026-11-03: user reports fixed and merged – readable PMI in both schemes + zone legend, tables (hover never selects,
   middle-button autoscroll), state reset on loading + stable comparison display (camera kept). User order: fix the
   reported issues first, 2D/3D chains at the very end. The finished branch `claude/ketten-wiggle-7d70d7` (3D chain
   wiggle, clean 3D chain display, 1D wiggle of the example finds the closing faces; full suite green there) stays
   unmerged until the user calls for the chain topic.
   2026-11-03: gear data sheet for cylindrical gears done (`f7babef`, `kern/verzahnung_daten.py`, see PLAN §8.27
   note; test-data helper got an optional tip relief, analysis only). Open in gears: tip chamfer vs. relief, root
   fillet radius, topological modifications, mapping to the input fields of specific gear tools; splines paused.
   Next, in this order: formats (QIF Plans export – waits for the OK to download the QIF 3 XSDs, STEP-XML, PRC
   compressed tessellation/B-rep, PMI from JT), performance/gears (gear data sheet, PLAN §8.27; analysis only, no
   generators), item 8 DXF dimension entities, the user checks (CATIA reading of written STEP with own
   PMI/presentation, screenshot of the blue stripe while loading on Windows, an AP242 file with a mechanism); paused:
   functional-chain open items (note `fmk-offen.md`), spline recognition (note `passverzahnung.md`); at the very end:
   2D/3D chains (merge `claude/ketten-wiggle-7d70d7`, then further 2D/3D chain work).
   2026-11-03 later: REXS 1.7 export (`8eed44c`, `kern/rexs.py`, valid against the FVA JSON schema) and gear design
   findings for cylindrical stages and planetary sets (`80c1c90`, `kern/verzahnung_auslegung.py`, PLAN §8.27a, table
   "Auslegungsbefunde", CSV/JSON). User report "Schrägungswinkel nicht sauber erkannt" fixed in the same commit:
   phase tracked from the middle (`_drehung`), toothed threshold per pitch; also a phase wrap at ±π (internal spur
   gear) found by the tests. Probe z 15–100, β 8–35°, b ≤ 120 mm: all within 0.01°; all gear tests incl. the slow one
   green. Spline session `claude/steckverzahnung-32bc37` resumed and paused again by the user the same evening; its
   finished part merged into main (`ba33fe9`): test-data helpers for spline shafts/hubs in `werkzeuge/zahnrad.py`
   (involute DIN 5480/ISO 4156 style with flat or full-radius root, straight-sided ISO 14, serration; checked: valid
   solids, plausible volumes). Recognition (`kern/passverzahnung.py`), pairing male/female and findings not started;
   the branch stays for resuming (design notes in the session's shared note `steckverzahnung.md`). Bevel gears
   (analysis only) wait for test geometry from the user.
   2026-11-04: user report – the stack-up strip needed vertical scrolling to reach the table's scroll bar. Not the
   histogram but the result table with the traffic light above it set the height. Wide strip now: hint only as table
   tooltip, button row below the links, traffic light across the full width, compact result rows, closing dimension
   text under the histogram; minimum height 595 → 360 px (offscreen). Tall layout unchanged in order.
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
5. At the very end: item 8 (DXF dimension entities for drawings), then the open user checks listed in item 0.

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
