# Handoff

## Current state, 2026-11-21

### Compare projected reference dimensions and retain both witness lines

- Checked PLAN §8.35 and the graphical STEP repair in §8.4 against
  docs/Roadmap.md. CTC-03 Rev C sheet 1 reads “(.750)” between opposed
  inward-pointing arrows. Both arrow shafts and both parallel witness lines
  are visible. The same reader handles ordinary linear dimensions. Tests
  distinguish a missing parenthesis, extra ink above the baseline and a
  number that can be read as 66 or 99. Only a unique value confirmed at two
  resolutions becomes a proposal.
- AP242 #97 and the reopened AP203 #3630 export agree on 19.05 mm, the
  reference designation and the two planar slot faces. The dialog reports a
  missing reference designation as changed. On the partial export containing
  only bore sizes, confirming “Only in drawing” exports that finding. Tested
  both before and after registering the seven-bore view. Selecting a dimension
  highlights the extension lines and the CSV records both segments.
- The seven-bore fit admits two projections with a maximum residual of
  0.17 pixels. On both source models the nearest projected edges of the two
  linked slot faces are at least 6.45 pixels from the corresponding drawn
  witness ends (rounded to two decimals). The numeric result does not
  establish that these endpoints are registered to faces.
- All 173 affected tests and 201 drawing/oblique regression checks passed.
  Native Cocoa runs passed 25 recognition/review cases plus four comparison
  and registration cases. Surveyed 30 local NIST sheets. The signed app
  passed its self-test and rendered the reviewed STEP. Keep the single
  main application at `dist/3DGmax.app`.
- Next in §8.4: CTC-03 AP203 #3625 prints “(1.5)” on a callout named
  “linear dimension”. The current distance suggestion has just one face
  and cannot be confirmed. Two extension lines start at opposite points
  of bore #545, 38.1 mm apart and tangent in the annotation plane. Its
  repeated supplementary edge #2053 is a 0.75 inch circle. Independent
  AP242 #269 identifies a diameter on two half-cylinder faces, radius
  19.05 mm, and has no nominal value representation. Recover the printed
  reference diameter from letters and verified tangency, then check project
  and STEP export with the original presentation. QIF stays last.

### Compare the repeated thickness on the CTC-03 drawing

- Checked PLAN §8.35 and §8.4 against docs/Roadmap.md. Sheet 1 of CTC-03 Rev C
  has no PDF text at the thickness callout. Two parallel witness lines, the
  arrow and the origin circle establish its projected writing axes. The row
  reads “4X .82 ±.06” at both verification resolutions. Tests cover changed
  count and tolerance, missing end marks, missing shafts and additional ink.
- Verified the PDF against independent AP242 #270 and against the reopened
  export of graphical AP203 #3634. After explicit confirmation the dialog and
  CSV show matching values and four separate coplanar pads; the model PMI
  also references their common base. An extra or missing pad changes the
  count finding. Without model geometry the quantity remains open. Individual
  2D pad positions have not been registered. Of 30 local NIST PDF sheets,
  one matched this arrow-and-circle layout with a counted linear dimension.
- All 166 affected tests, 186 drawing and thickness regression checks and six
  native Cocoa checks passed. The signed build passed its self-test and
  rendered the reviewed export. The only local main app is `dist/3DGmax.app`.
- Next: CTC-03 sheet 1 has a separate “(.750)” reference dimension between
  two inward-pointing arrows. The AP203 repair reads #3630 as a reference
  distance on faces #537 and #539; AP242 #97 gives 19.05 mm. Rectifying the
  two measured witness directions recovered the parentheses and all digits
  at three raster resolutions in a probe. Connect this layout to the normal
  drawing review and CSV export. QIF stays last.

### Recover a repeated thickness from graphical STEP

- Checked PLAN §8.4 and §8.35 against docs/Roadmap.md. CTC-03 AP203 #3634
  prints 4X .82 ±.06 inch. The callout references one plane and four separate
  coplanar pads. Its two additional edge targets belong to these faces. The
  review recovers 20.828 ±1.524 mm and checks the quantity, both witness
  levels and the end marks before proposing a thickness. All five surface
  normals point the same way in this model.
- Tested original outlines, single strokes and filled triangles, with and
  without annotation axes. The review, project reload and STEP export retain
  the numeric limits, five face references, original graphic and view. The
  separate AP242 #270 agrees. The four pads in the reference lie 0.00254 mm
  higher than in AP203. The measured AP203 separation is 20.83054 mm.
- All 22 affected tests and eight native Cocoa checks passed. Native OCCT
  recovered the dimension with the same model volume and diagnostics as the
  input. The signed app passed its self-test and rendered the triangle-only
  export. The local main build is solely at `dist/3DGmax.app`.
- Next in §8.35: read the counted linear dimension on CTC-03 sheet 1 and
  compare it with the reviewed thickness. The existing drawing quantity
  comparison covers bores and radii. QIF stays last.

### Distinguish equal drawing dimensions by their projected bore walls

- Checked PLAN §8.4 and oblique registration against docs/Roadmap.md. CTC-03
  sheet 1 draws ten bore rims as closed, nonuniform polygonal approximations.
  Their pen is 1.73 page pixels wide. The reader checks the fitted ellipse
  against the segments, the printed width and local contrast around the rim.
  Open back edges, regular polygons in the fallback, insufficient line width,
  solid areas and partial overpainting have negative controls.
- Shift-drag collects rectangles in one view; the last ordinary drag registers
  the complete set of rims in their union. Overlap counts once. Tested
  cancellation, a hole in the gap, actual mouse events and a single rectangle.
  Selecting the mounting and tab bores together on CTC-03 registers seven
  bore walls. The two Ø.438 callouts reach different cylinders via their
  leaders and select AP242 #264 and #263. The 4X Ø.625 pattern covers #265.
  Checked the same workflow after reviewing AP203 #3638, #3640, #3641,
  #3649 and reopening the export. The confirmed inspection CSV keeps the
  individual model IDs and the two different ellipse locations.
- Five of seven CTC-03 dimension leaders reach a drawn ellipse. The separate
  2X Ø.438 pattern still has only one verified target. The Ø2.00 and Ø1.500
  centres miss the seven-bore projection by at least 9.7 and 9.6 pixels
  respectively, versus at most 0.12 pixels on the seven matching centres.
  This was measured against both AP203 and AP242. Their values compare
  independently; these two locations need separate review.
- Passed 65 affected tests, 103 drawing regression checks and 11 native Cocoa
  checks. Surveyed 42 sheets, finding 154 additional ellipse candidates.
  The signed app rendered the graphical-to-semantic export and passed its
  self-test. Keep one main app in `dist/3DGmax.app`.
- Next in §8.4: AP203 #3634 prints 4X .82 ±.06 inch on a linear dimension.
  Independent AP242 #270 is Size_Thickness, nominal 20.828 mm with limits
  19.304 and 22.352 mm. The AP203 callout resolves to plane #481 and four
  coplanar pads #557, #558, #563 and #566. Their measured separation
  (20.83054 mm) differs from the rounded printed nominal. Preserve the
  printed precision and verify the four targets before proposing the size.
  QIF stays last.

### Compare individual bore sizes on projected drawings

- Checked PLAN §8.4 and the oblique-view registration work against
  docs/Roadmap.md. NIST CTC-03 Rev C sheet 1 yields all seven printed bore
  dimensions with seven distinct vector leader starts. The app reads left-,
  centre- and right-aligned text, including compressed lettering next to a
  diameter symbol. Overlapping native PDF text and graphical readings are
  reconciled. Conflicting values at the same location stay open.
- The two Ø.438 ±.005 inch single bores and the 2X pattern each have their
  own finding. Three AP242 dimensions share these limits. The dialog leaves
  both singles unassigned without geometry evidence. Checked Ø2.00 ±.01
  against #267 and again after graphical #3629 was reviewed, exported to STEP
  and reopened. Both comparisons reach the confirmed equal result in CSV.
- Across 42 reference sheets the inventory increased from 153 to 169, with
  no previous row lost. Inspected all 16 additional readings against the PDF.
  Fifteen have matching numeric limits in the model. FTC-06 sheet 1 actually
  prints 2X Ø.562 ±.008 inch, while AP242 #271 stores .5625 ±.008 inch.
  The nominal and both limits differ by 0.0127 mm. Comparing printed values
  does not establish that the underlying physical bore changed.
- Passed 49 affected tests, 84 regression cases and 31 native Cocoa tests.
  The signed app rendered the reviewed export and passed its self-test.
  Keep one main app in `dist/3DGmax.app`.
- Next: geometric assignment of the CTC-03 projected bores. The current
  vector reader reports four rings on sheet 1 and cannot follow the seven
  leaders to a confirmed bore. The central rim is a closed 23-point stroked
  vector path. Its fitted major and minor radii are 56.72 and 32.73 pixels,
  but the largest normalised chord-midpoint error is 0.025. Compare chord
  error to the actual printed line width and local contrast; check holes,
  nearby partial back rims and intentionally polygonal contours separately.
  The independent graphical CTC-03 #3634 linear pattern is still open.
  QIF stays last.

### Recover the toleranced central bore beside a long bent leader

- Checked PLAN §8.4 against docs/Roadmap.md. NIST CTC-03 AP203 #3629
  now proposes Ø2.00 ±.01 inch. When the full graphic is unreadable, verify
  the separate leader and read all remaining lettering at two resolutions.
  A changed printed deviation changes the proposal on the same cylinder.
- Reviewed the original outlines, single strokes and a triangle-only copy
  through the native review dialog, project reload and AP242 export. All
  three retain their original graphic, view and target #544. The independent
  semantic #267 covers the same cylinder in two halves with limits 50.546
  and 51.054 mm. OCCT reports the same diagnostics and solid volume before
  and after export. Also tested with the writing plane removed.
- Passed 30 affected tests and four native Cocoa checks. Compared 194 review
  candidates across six graphical STEP models, with #3629 the only change.
  The signed build passed its self-test and rendered the reopened export.
  Local main has a single app at `dist/3DGmax.app` and no `main-*` build
  directories. The two existing versioned release ZIPs are retained.
- Next in §8.4: projected drawing dimensions with no pattern count. A local
  reading experiment on CTC-03 sheet 1 finds Ø.438 ±.005 and Ø1.500 ±.005
  inch. AP242 has three semantic candidates with the first size (#263,
  #264, #266) and one with the second (#268). Resolve assignment separately
  from text recognition. The experiment still misses Ø2.00 ±.01. CTC-03
  graphical #3634 has a separate counted linear dimension. QIF stays last.

### Compare projected mounting positions and counted diameters on the drawing

- Checked PLAN §8.4 against docs/Roadmap.md. CTC-03 Rev C sheet 1 now reads
  the five position compartments and both caption lines. The original AP242
  #41 differs only in its empty description. The CSV field comparison names
  that difference. All three previously exported graphical variants agree
  after reopening. Also tested the full UI workflow from AP203 by reviewing
  D/B/C, the position and its separate diameter, exporting AP242, reopening
  the file and confirming the drawing comparison through the file menu.
- The dimension above the frame has its own drawing coordinates and leader.
  “4X Ø.625 ±.005” matches the numeric limits of AP242 #265. The app reads
  the quantity, diameter, nominal value and deviations from the dimension
  itself, including when the attached position value is unreadable.
  A count stays open until the drawing holes have been associated with the
  model faces. Coincident PDF text and graphics produce one measurement.
- Verified five printed quantities and sizes in CTC-02 sheet 1, CTC-03
  sheet 1, FTC-09 sheets 1 and 4, and FTC-10 sheet 5. Each FTC-09 value
  occurs on three semantic dimensions, so equal values alone cannot assign
  the feature. The 42-sheet inventory grew from 147 to 153 findings. All six
  additions were verified against the real drawing and STEP.
- Passed 149 affected tests, 60 comparison regression cases and 20 native
  Cocoa checks. The signed local app rendered the reviewed export and
  passed its self-test. Keep the single main app at `dist/3DGmax.app`.
- Next in §8.4, CTC-03 AP203 radial dimension #3629 prints Ø2.00 ±.01 inch.
  Target #544 has radius 25.4 mm. AP242 #267 gives 50.546 and 51.054 mm
  limits on the two cylinder halves. The current reader removes the leader
  but gets no full value at 720 pixels per callout height. The same original
  contours read correctly at 900 and 1100 pixels. Verify a bounded retry
  with original curves, single strokes, fills and damaged controls. #3634
  shows a separate counted linear dimension. QIF stays last.

### Switch mounting positions from graphical STEP

- Rechecked PLAN §8.4 and docs/Roadmap.md. Reviewed NIST CTC-03 AP203 #3627
  from its original contours, a full single-stroke frame and caption, and a
  single set of filled triangles. The same reading works without a writing
  plane. Its printed diameter tolerance of .05 inch converts to 1.27 mm at
  maximum material relative to D/B/C. Both lines of “SWITCH MOUNTING LOCATIONS”
  become the tolerance description. Missing letters, incomplete strokes inside
  the modifier and contradictory validation text are covered.
- Reopened the four independently reviewed PMI (three datums and the position)
  from the project and the exported AP242. View #3388 and the source graphics
  survive in all three representations. AP203 #546–549 are four full cylinders.
  The independent AP242 #41 uses eight half cylinders. Their axes, radii,
  axial limits and complete circumferential coverage match in pairs. OCCT
  accepted the modified tolerance with datum references and preserved volume.
- All thirteen graphical CTC-03 tolerance frames now yield values. The 194-callout
  inventory found just the two known coplanar profiles and this mounting-position
  caption. Adding a single-stroke circled M left the original 194 readings stable.
  Passed 42 affected tests, 25 coplanar/material/composite regression cases and
  four native Cocoa cases. The signed main app passed its self-test and rendered
  the reopened triangle-only STEP. Keep one app at `dist/3DGmax.app`.
- Next in §8.4, bring this position control into drawing comparison. CTC-03 Rev C
  sheet 1 shows “4X Ø.625 ±.005” above the frame as a separate size dimension.
  An experiment on the real PDF yielded all five position compartments at 75, 100
  and 140 pixels per frame height, and both caption lines at 140. The current UI
  omits this projected position frame. Compare its wording explicitly, including
  the original semantic reference’s empty description. QIF stays last.

### Tightly spaced coplanar lettering and the canonical main app

- Verified PLAN §8.4 against docs/Roadmap.md. CTC-03 AP203 #3636 reads
  “⌓ .01” and “2 COPLANAR SURFACES”. Letter widths overlap in L/A and F/A.
  Grouping complete contours with their counters, or filled triangles by shared
  edges, retains the individual glyphs. No installed font is needed at runtime.
  The single-stroke number reader also recognises the leading 2.
- Reviewed and exported original outlines, a single-stroke caption and a single
  triangle set without outlines. Reopening each project and AP242 export
  preserved both faces (#492 and #502), view #3388, the callout geometry and
  the datum-free 0.254 mm surface profile. OCCT retained solid volume. All
  three reopened exports agreed with CTC-03 Rev C sheet 1 and AP242 #35.
  The 194-candidate audit with and without writing planes found only the two
  known coplanar captions. The affected suite passed 20 tests. Nine focused
  tests also passed on native Cocoa.
- Keep one signed main app at `dist/3DGmax.app`. Verified its self-test and a
  native rendering of the exported STEP. No `main-*` build directories remain.
  The two historical release ZIP files are separate from the main build.
- Twelve of thirteen CTC-03 AP203 tolerance frames yield a value. Next in
  §8.4 is #3627. Its original presentation shows a position control with
  Ø.05 at maximum material, D/B/C and “SWITCH MOUNTING / LOCATIONS”. AP242
  #41 supplies an independent comparison for value, modifiers and datums.
  Check the four source mounting features against split AP242 cylinder faces
  and retain the printed description through review and export. QIF stays last.

### Compare single-row coplanar drawing controls with STEP

- Checked PLAN §8.4 and docs/Roadmap.md. The NIST CTC-02 Rev C PDF shows
  “4 COPLANAR / SURFACES” on sheet 3. Its profile frame and lettering are
  projected vector paths with an adjacent boxed datum G. The comparison reads
  the closed frame, verifies each compartment at two resolutions and checks the
  complete caption in the local reading direction. Axis-aligned PDF text also
  supports a wrapped count. A datum in its own frame compartment remains part
  of the tolerance.
- The STEP association selected in the dialog supplies the target faces. CTC-02
  AP242 #53 controls four separate planar patches at 0.1 mm. CTC-03 Rev C sheet 1
  reads “2 COPLANAR / SURFACES” at .01 inch. Its AP242 #35 has two separate
  coplanar patches and a 0.254 mm tolerance. Both give equal results through
  the file menu, selection dialog and CSV. STEP may express this scope through
  the target faces alone. An explicit conflicting description still differs.
- A different count, a parallel offset and a cylinder all produce a difference.
  Unverified geometry and uncertain assembly occurrences remain open. Reopened
  STEP exports of CTC-02 from graphical contours, single strokes and pure fills
  also agreed with the actual PDF. An inventory of 42 local NIST and D2MI PDF
  sheets added only the two independently verified controls to the 145 existing
  findings.
- The final affected suite passed 129 tests. All ten focused cases also passed
  using native Cocoa. The signed local bundle passed its self-test and rendered
  the reviewed STEP. Keep one current main app in dist.
- Next in §8.4, recover the corresponding CTC-03 AP203 callout #3636. Its frame
  alone reads “⌓ .01” and its two linked faces pass the coplanarity check. Its
  caption fits on one line in a different font. Adjacent L/A and F/A glyphs
  overlap in the horizontal projection. Rasterising at higher resolution alone
  still leaves ambiguous letters. Isolating contours by full bounding-box
  containment and enclosed counters gave the right 17 characters against both
  independently rendered Tahoma and Verdana samples. Tahoma separated each
  character from its nearest alternative by at least 0.80 on the symmetric
  distance score. Retain word spacing and verify triangle-only and single-stroke
  sources, controls and negative cases before integrating. QIF remains last.

### Single-row coplanar profile and the local main build

- Checked PLAN §8.4 and docs/Roadmap.md. AP203 CTC-02 #8709 gives a 0.1 mm
  surface profile followed by “4 COPLANAR SURFACES”. Review and export check
  faces #1127, #1198, #1187 and #1132. The duplicate source link to #1187 counts
  once. All four patch centres match the independent semantic AP242 control #53
  within 0.0001 mm. The scope stays on the same single control through project
  reopen and STEP export. Its saved view #8309 and original presentation survive.
- Covered contour letters, single strokes and filled triangles, both with and
  without writing axes. Different printed counts and the distinction between
  O and 0 are checked. Missing letters, incomplete links, wrong selections and
  displaced notes are rejected. Conflicting STEP validation leaves the numeric
  value open for review. Of 194 graphical callouts in six NIST models, only
  #8709 matched this additional layout in either orientation test.
- A complete pass through the review dialog on the graphical CTC-02 source
  wrote 44 confirmed annotations, including all 22 tolerance frames, seven
  dimensions, six datums and nine datum targets. The two other callouts #8696
  and #8701 retained all their original curves. Native OCCT reread the individual
  contour, stroke and filled exports with the original volume and diagnostics.
- The final affected run passed 386 tests and five dedicated native Cocoa
  cases passed. All 2,857 UI strings have English entries. The signed bundle
  passed its self-test and rendered the complete 44-annotation export. OCCT
  reported the same diagnostics and volume as for the source.
- Main uses a single signed arm64 app at `dist/3DGmax.app`. Removed the old
  temporary main build for 77f1b70 and the binaries and caches from twelve more
  superseded staging directories, accounting for 29.1 GB in the latter twelve
  by directory size. Compared their source files with main history. Kept the
  nonmatching handoff and plan snapshots and the two versioned release ZIPs.
- The drawing comparison still needs a geometry check for a coplanar note under
  a single row. Its current parser leaves “⌓ | 0.1” followed by “4 COPLANAR /
  SURFACES” open. The existing two-row comparison already checks the count,
  coplanarity and disjoint faces. QIF remains last.

### Circular datum target K1 and the line-profile control in graphical CTC-02

- Checked PLAN §8.4 and docs/Roadmap.md. The divided circle in AP203 #8713 reads
  Ø85 over K1. Its leader projects onto the material of planar annular face #1158.
  Two complete concentric trims, with radii 20 and 60 mm, give the centre
  (0, 812, −140) mm. The oriented normal is +Y. The AP242 reference #110 independently
  confirms centre, normal, diameter, identifier and circular target type.
- Review shows the centre inferred from the trim, the normal and the diameter.
  Export revalidates the source graphic, face and parameters. AP242 stores the
  target diameter with its unit, its oriented local placement and supporting face.
  Verified the wholly graphical model, true single-stroke lettering and filled
  triangles with the original graphics after project reload. Native OCCT reads
  each export with the same diagnostics and volume as its input. Its dependent
  perpendicularity #8680 retains the printed 0.25 mm relative to K. The separate
  AP242 edition uses 0.254 mm. Tested inch units and aligned revision comparisons of
  position, diameter and orientation.
- The open semicircle of #8712 now yields a 0.25 mm line-profile tolerance with
  A/B/C, matching AP242 control #83. Verified outlines, a single-stroke arc,
  triangle fills and missing writing axes. Reviewing the eight point targets
  enables export of this control as well as the three unequal surface profiles.
- The remaining AP203 CTC-02 frame #8709 in §8.4 carries a 0.1 mm surface
  profile and a two-line scope note “4 COPLANAR SURFACES”. The two FCF cells
  already read correctly on their own. Validate the separate scope and the actual
  four faces before emitting semantics. AP203 aspects #274–278 link to distinct
  faces #1127, #1198, #1187 and #1132 in the plane Z = 40 mm, with #1187 linked
  twice. AP242 callout #1207 refers to control #53. The existing freestanding-note
  recognizer rejects this font in both contour and filled form. An isolated
  glyph comparison using independently rendered sans-serif letters and digits
  read both lines in both representations. Validate count changes, lookalikes,
  missing glyphs and spacing before integrating this reading.
- The open-arc recognizer changed only #8712 in a comparison of 194 graphic
  callouts in six models, with and without supplied writing axes.
  The full suite passed 1164 tests and skipped eight. The final affected run
  passed 422 tests. The focused form and target run passed 15 cases, and all
  nine native Cocoa target tests passed. The signed arm64 build passed its
  self-test and rendered both exported models. QIF stays last. Local main uses
  one app in dist.

### Point target datums from the graphical CTC-02 source

- Checked PLAN §8.4 and docs/Roadmap.md. Original AP203 annotations for A1–A3,
  B1–B4 and C1 now round-trip through graphical review, project reopen and STEP
  export. The cross must be attached to the divided balloon by a leader, its full
  identifier must be readable, and the cross must touch the source face within
  0.001 mm. All eight points lie within 0.05 mm of the separate AP242 reference.
- Verified original outlines, a single-stroke A1 and filled glyphs without contours
  or writing axes. STEP stores the target number, point in the part's length unit,
  supporting face and parent datum. Exporting a partial review retains individual
  confirmed targets and reports missing siblings by identifier on dependent frames.
  Reopening the partial STEP and confirming B2 completes all three A/B/C profiles.
  Native OCCT reads the outputs with the same diagnostics and volume as the input.
  The inch variant verifies the physical contact position after export and readback.
- The complete suite passed (1163 passed, 8 skipped). All 448 affected tests passed.
  Four dedicated target cases passed, and the
  three native Cocoa review/export cases passed. The signed arm64 app passed its
  self-test and rendered the exported triangle-only STEP model.
- Local main keeps one app at `dist/3DGmax.app`. The previous 21 `dist/main-*`
  folders and 13 temporary packaging outputs from integrated main revisions have
  been removed. The two versioned release ZIPs in dist are retained.
- Next in §8.4: circular area target K1. Its upper compartment reads Ø85. The
  leader tip is 8.51 mm off the source face and is unsuitable as the target centre.
  Face #1158 has concentric circular trims of radius 20 and 60 mm whose centre
  matches the independent semantic reference (0, 812, −140) mm. Establish the
  supported circular region and its orientation before proposing it. QIF stays last.

### Recover graphical unequally disposed profile tolerances

- Checked PLAN §8.4 and docs/Roadmap.md. CTC-02 AP203 frames #8688, #8694 and #8714
  have 2.5 mm surface profile tolerances with outer boundary distances of 2.5, 0.5
  and 0 mm. All three match the independent AP242 controls #58, #57 and #56. The
  review distinguishes ASME Ⓤ from the ISO zone-centre displacement even if the
  source and its exported copy have neutral filenames.
- Tested contours, an independently drawn single-stroke U, pure triangle fills and
  reading without stored writing axes. Only the three CTC-02 readings changed
  in the six-model, 194-callout comparison. Review, project reopen and STEP export
  preserve target faces, datum order, graphics and saved views. The displacement
  is a LENGTH_MEASURE_WITH_UNIT on UNEQUALLY_DISPOSED_GEOMETRIC_TOLERANCE. A
  MEASURE_QUALIFICATION records the convention locally. Verified signed ISO offsets,
  ASME boundary distances and inch-to-mm conversion on readback.
- The AP242 test removes the three original semantic controls and keeps the real
  datum targets. OCCT reads the new tolerances and their displacement without an
  error. Its existing limitation with the compound draughting model #1208 also
  applies to the three new presentation links. A separate wholly graphical model
  variant uses the existing G/H/J datum graphics from the neighbouring CTC-02 frame.
  It round-trips with the same OCCT diagnostics and volume as its input.
- All 460 affected cases passed. The separate graphical regression set passed 68 cases,
  followed by 22 checks for the datum-target safeguard and nine native Cocoa tests. The
  signed arm64 build passed its self-test and rendered the exported triangle-only variant.
  Local main builds still use the single app in dist.
- Next in §8.4: recover the point datum targets needed by the unmodified AP203
  A/B/C frames. The AP242 reference locates A1/A2/A3, B1/B2/B3/B4 and C1. The
  cross positions are within 0.05 mm of the reference anchors. #8674 corresponds
  to B2. Its partial reading “B” now leaves the target unresolved. #8713 is a
  separate circular datum target K1 with 85 mm diameter. Validate the contact
  points, individual target numbers and full datum sets before use. QIF stays last.

### Read least-material requirements in graphical CTC-02 frames

- Checked PLAN §8.4 against docs/Roadmap.md. The six circled-L frames match the values,
  types, material conditions and ordered datum references of semantic CTC-02. Three profile
  frames mark H, J or both. Two position controls and one perpendicularity control mark
  the toleranced feature. Tested the original contours, separately drawn single strokes
  and pure triangle fills, including recognition without a writing plane.
- Five reviewed controls round-trip through the project and semantic STEP with the correct
  faces, saved views and original graphics. The remaining 1 mm position control is read
  with A/B/C. Export keeps it graphical and reports the missing semantic datums when only
  G/H/J were reviewed. CTC-02 contains graphical datum targets for A, B and C.
- Rounded compartment endpoints previously obscured #8707 (1.5 mm position at maximum
  material, to A/B/C). Adjacent datum references stay separate after projection.
  A damaged separator must leave the frame unresolved.
- Across 194 graphical callouts the six circled-L frames and #8707 were the only changed
  readings, with and without saved writing axes. All 29 affected tests, 77 related
  regression cases and five native Cocoa checks passed. The signed arm64 build passed
  its self-test and rendered the exported triangle-only callouts.
- Next in §8.4: the three unequally disposed profile controls in CTC-02 (#8688, #8694
  and #8714). Their 2.5 mm profile values accompany offsets of 2.5, 0.5 and 0 mm,
  respectively (semantic controls #58, #57 and #56). Check how the exporter writes
  UNEQUALLY_DISPOSED_GEOMETRIC_TOLERANCE before enabling semantic review. Reconstruction of datum-target sets is also open. QIF remains last.

### Recover CTC-05 form and runout controls from their graphical STEP presentation

- Checked PLAN §8.4 against docs/Roadmap.md. In CTC-05 AP203 the eight previously unread
  controls now recover their characteristics, inch values, datum compartments and original
  target faces. The NIST semantic AP242 reference independently confirms all eight values
  and types. For example, three circular runouts reference the common datum A-B with
  values 0.889, 0.635 and 0.635 mm. The two total runouts are 0.0508 mm to A and
  0.381 mm to B. The concentricity control retains its diameter zone.
- Verified native contours, separately drawn centreline characteristic symbols, and
  triangle-only callouts. The latter two variants omit the writing planes. Two leaders
  traverse depth to separate parallel target planes. Review, project reload and AP242 export
  preserve all eight controls, original graphic coordinates/connectivity and saved views.
  OCCT diagnostics and volume match the input. Across 194 callouts in six models, only the
  eight CTC-05 readings changed, with either supplied or removed writing planes.
- All 31 affected tests passed, plus 43 related regression tests. Native Cocoa passed the
  five checks in the new module, including the three end-to-end review/export variants.
  The signed arm64 build passed its self-test and rendered the semantic copy with the
  original fills. Local main builds use the single canonical app in dist.
- Next graphical gap in §8.4 is the circled L. CTC-02 reference controls #59, #60 and
  #67 distinguish least-material modifiers on J, H, and both datum features. Graphic
  frames #8678, #8699 and #8711 recover the value but leave the modified cells unread.
  The same glyph remains unread in three value cells (#8686, #8687 and #8717).
  Verify feature and datum modifiers separately against the reference. QIF stays last.

### Recognise crown gears and splined wheel bores, and compare trimmed profile regions

- Checked PLAN §§8.4 and 8.27 against docs/Roadmap.md. The recognition command now
  keeps inner and outer transverse-section contours on a single body. Verified a
  23-tooth spur gear with a 24-tooth involute spline and a 14-tooth bevel gear with a
  six-groove parallel-sided bore in both STEP and STL. The data sheet has two columns.
  Selecting either column identifies the same occurrence. JSON retains both profiles.
- Verified crown gear candidates on independent 15- and 32-tooth models from
  [FreeCAD Gears](https://github.com/looooo/freecad.gears/blob/master/freecad/gears/crowngear.py)
  in STEP and STL. The committed 15-tooth test file uses module 1 mm, a 15-tooth
  pinion, 20° pressure angle, 2 mm radial face width, 5 mm stock thickness, and four
  generating profiles. Tested an additional STEP solid combining this face gear with
  a six-groove hub. Both profiles were recovered. A flat dog clutch remains a negative
  control. The tooth form needs sufficient radial and angular sampling. Pair contact,
  transmission ratio for an identified crown stage, and tooth strength remain open.
- Revision comparison measures the areas unique to each trimmed face set after
  alignment. A translated hole leaves 30 mm² unique to each revision and closing the
  hole adds 100 mm². Renumbering is equivalent. A cylindrical patch can be split at
  the seam or overlap a second trim. Its covered area stays equal after a rigid change
  of coordinates. An unresolved patch is reported as such.
- All 159 affected tests and three native Cocoa selection/display tests passed.
  Local ad-hoc-signed arm64 test build at `dist/3DGmax.app`. Its self-test passed.
  It rendered the combined crown gear with the native Cocoa/OpenGL viewer. The user's
  original differential pinion is represented only by screenshots. QIF stays last.
- Keep one local main build at `dist/3DGmax.app`. Historical references below to
  `dist/main-*` describe disposable build and test output. Once changes are on
  main, discard those directories. Stage future builds outside dist and replace the
  canonical app after verification. Versioned release archives are separate.

### Recover flatness per circular unit area in FTC-07

- Checked PLAN §8.4 and docs/Roadmap.md. The FTC-07 callout #14269 reads
  “.01 / ⌀1.00”. Original strokes and filled triangles, including fills without
  a writing plane, supply 0.254 mm flatness on circles of diameter 25.4 mm.
  Without semantic associations or validation text the review also proposes the
  correct face #10770. Its STEP reference is flatness #14257. The area diameter
  stays independent of the tolerance zone shape and is editable in the dialog.
- Verified project reload and AP242 export with the source graphics. The output
  uses CIRCULAR with an omitted second size, just as in the reference. The scan
  report leaves local evaluation open. The revision and drawing comparisons
  report a change from 25.4 to 12.7 mm independently. In a before/after reading
  of 194 callouts across FTC-07 and CTC-01 to CTC-05, only #14269 changed. The
  property text on the independently authored drawing also confirms both values.
  All 448 affected tests passed, as did 17 native Cocoa checks. The three graphic
  variants were additionally checked on Cocoa with OCCT link diagnostics.
- The product volume and OCCT diagnostics on the circular control's graphic link
  match the NIST reference. The installed OCCT reader treats the complex tolerance
  and tessellated draughting model as undefined entities. 3DGmax resolves both.
  The signed app at `dist/3DGmax.app` passed its self-test and rendered the
  exported file. The macOS ZIP and before/after examples are in `dist/main-einheitskreis/`.
- Next is revision comparison of trimmed profile interiors. A new experiment with
  a 60 mm² cylindrical patch crossing its seam found that a single multi-argument
  OCCT cut returned a negative area for an equivalent two-piece trim. Overlapping
  tools also produced a false 10 mm² remnant. Subtracting each tool in succession
  from each source face in both directions gave zero for the seam split and
  overlaps. A 1 mm axial shift left 6 mm² on each side and a 0.1 rad angular
  shift left 10 mm² on each side. These checks are experiments. Integration with
  face and edge correspondence, alignment, and the comparison report remains open.
  QIF stays last.

### Preserve both sides of a rectangular unit-area flatness control

- Checked PLAN §8.4 and docs/Roadmap.md. In NIST CTC-03 graphical callout #3623,
  the value reads “.005 / .25 X .25”. In millimetres this requires 0.127 flatness
  on a 6.35 × 6.35 rectangle. The reference AP242 file encodes both dimensions
  on its flatness tolerance #37. The review dialog, project and STEP reader/writer
  now retain both. The drawing and revision comparisons distinguish a changed width.
- Reopened the NIST outlines, independent single strokes, and triangle fills with
  their writing plane removed. The latter two actually draw .20 for the second
  side. Both reopened with a width of 5.08 mm, on original face #479 with matching
  graphics, saved views and solid volume. A closed hourglass remains unreadable as
  X. Round leaders ending at the near rim still recover the FTC-08 free-state frame.
- OCCT 8 treats the complex rectangular unit-area tolerance as an undefined entity
  in both the independent NIST reference and our export. On export this causes one
  reader diagnostic on the presentation link. The 3DGmax reader resolves the link
  and both dimensions. The scan report leaves local flatness open pending a check
  over moving rectangles.
- All 442 affected tests passed. Eight rectangular unit-area checks and thirteen
  gear/selection export checks also passed on native Cocoa. Selecting a face of the
  exported reconstruction in the main window identified the single nine-tooth pinion.
  The installed Apple Silicon build at `dist/3DGmax.app` passed the bundled self-test
  and rendered the rectangular example and the reopened pinion. Before/after STEP files and the
  ZIP are in `dist/main-einheitsflaeche/`. The nine-tooth differential reconstruction
  remains at `dist/main-ausgleichsrad/Ausgleichsrad-mit-Bund.step`.
- Next graphical case in §8.4 is FTC-07 #14269. The semantic reference #14257
  and its validation property #14260 specify 0.254 mm flatness per circle of
  diameter 25.4 mm. The graphical reader finds both cells and accepts the frame
  outline, but neither font recogniser decodes the cells. The semantic reader
  retains only a generic unit length. Comparison of independently
  trimmed regions also remains open. QIF stays last.

### Convert frames with a detached round-ended leader

- Checked PLAN §8.4 and docs/Roadmap.md. CTC-03 callouts #3631 and #3651 have a
  horizontal gap of about 0.69 frame heights before the first leader segment. Check
  the approach, bend, second segment and circular endpoint. The shaft may reach
  the near rim as in FTC-08 or the centre as in CTC-03. The same circle attached at the bend prevents the
  plain frame proposal in the tests, including a leader touching the frame.
- The two profiles read 1.524 and 0.762 mm with A/B/C on source faces #479 and
  #481. The angularity control #3644 reads 1.016 mm to A on #479. The inch-based
  file matches the NIST semantic reference in values and datum order. Its equivalent
  support faces have matching surface areas and centres to within the differences
  between the two NIST revisions. Across 141 graphical callouts in CTC-01 to CTC-05,
  the one other changed reading was CTC-05 #3184, perpendicularity 0.254 mm to D,
  also present in its semantic reference.
- Checked original polylines, independently drawn single-stroke letters and angularity
  symbol, triangle-only graphics, and triangle-only frames exported without writing
  planes. Reflecting the reading axes can move the inner border of a rasterised cell
  by one pixel. Re-measure it in reading direction before evaluating the lettering.
  Reopened STEP retained exact graphic coordinates, view membership, face IDs,
  values, datums, volume and the OCCT diagnostic list of the input.
- All 33 affected tests, 32 additional profile/lettering checks, and eight native
  Cocoa cases passed. The signed local app is at `dist/3DGmax.app`. The package
  and before/after CTC-03 STEP files are in `dist/main-profilrahmen/`.
- Next graphical case is CTC-03 #3623. Its complete value field reads
  “.005 / .25 X .25”. The reference AP242 #37 has RECTANGULAR,
  GEOMETRIC_TOLERANCE_WITH_DEFINED_UNIT(#233) and a second length #234, both
  6.35 mm. Current OCR lacks the slash and X in this font. The semantic reader
  currently exposes only the first side as a modifier. Retain both lengths in
  review, project, STEP and comparison, and test unequal sides. Revision comparison
  of independently trimmed regions remains open. QIF is last.

### Recognise a face-toothed pinion blending into an inner collar

- Checked PLAN §8.27 and docs/Roadmap.md. Raising the inner edge of the nine-tooth
  reconstruction by 3 or 4 mm with a rounded transition toward the teeth reproduced
  another missed recognition. The whole radial band no longer followed a cone.
  The fit now tries consecutive inner cutoffs, keeping at least two thirds of the
  periodic band and four measurement circles. For a shortened band, tip and root
  must continue sloping in the same direction across its outer half.
- A repositioned mesh and a selected B-spline solid loaded from STEP both returned
  nine teeth. A smooth blank and flat dog clutches with and without the same 4 mm
  collar did not receive this classification. The tree extract reopened as a
  nine-tooth candidate, with radii 10.10–15.70 mm and measured inclination 25.71°.
  These are measurements of the reconstruction. Only screenshots of the original
  pinion are available, so the original topology remains unverified.
- Rechecked File › Export and the tree context menu with multiple occurrences,
  assembly placement, colour and mesh export. Thirteen affected tests passed, plus
  thirteen gear and export tests on native Cocoa. The signed Apple Silicon app at
  the normal local path `dist/3DGmax.app` passed its self-test and rendered the
  exported pinion. Its ZIP and `Ausgleichsrad-mit-Bund.step` are in
  `dist/main-ausgleichsrad/`. The previous October build is retained there.
- The graphical PMI review and scoped comparison cases below remain next in §8.4.
  QIF remains the final item.

### Distinguish graphical datum letters on NIST CTC-02 and CTC-03

- Checked PLAN §8.4 and docs/Roadmap.md. Three CTC-03 position controls read B/B/C
  before the fix. Their original glyphs and the semantic reference give D/B/C.
  CTC-02 profiles now retain G/H/J and all four D/E/F combinations with maximum
  material on E, F, both or neither. Its perpendicularity frame #8680 reads K.
- Both models were tested through the review dialog and STEP export in three versions:
  the NIST contours, independently drawn single-line datum letters and triangulated
  copies. The regression compares values, units, diameter modifiers, ordered datums,
  face IDs, original graphic coordinates, view membership, OCCT volume and diagnostics.
  The XCAF reader accepts the older CTC-02 AP203e2 signature, its non-rational spline
  surfaces and styled ellipses. The converter continues checking each entity signature.
  [MBx-IF EXPRESS schemas](https://www.mbx-if.org/home/mbx/resources/express-schemas/)
- Surveyed 141 graphical callouts across CTC-01 through CTC-05. All 15 focused schema
  and conversion cases and all 48 affected tests passed.
- Next graphical cases are CTC-03 #3631 and #3651, whose printed frames have detached
  marks, and #3623 with a unit-area flatness qualifier. Comparison of independently
  trimmed regions also remains open. QIF stays last.

### Convert graphical profiles on separately trimmed STEP faces

- Checked the implementation against PLAN §8.4 and docs/Roadmap.md. The review uses
  the explicit face set on the callout and checks the two graphical leaders against
  the transferred edges of that set. The chosen area appears in the scene and in the
  dialog. Confirmed records persist the supplementary STEP face numbers in the project.
  Reopening the project resolves those numbers against the source callout and recovers
  the trims. STEP writes the supplementary faces and relates their boundary edges to
  the area representation.
- Fixed the previous supplemental reader's ownership of the STEP entity table.
  Releasing a secondary OCCT session with the same StepData_StepModel erased all 17,310
  entries in the live product reader in the triangle-only reproduction. Each secondary
  session now owns its entity table and retains the original transfer order, entities,
  header and length unit. Its release preserves the product transfer and labels.
- The planar example contains 900 mm² of material inside a 20 × 50 mm patch with a
  10 × 10 mm hole. The 1.25 mm frame, the A/B/C datum order, both boundary edges, the
  original graphics and their saved views survived project reload and STEP export.
  Both original endpoint drawings are explicitly linked to their named start and end
  features in the STEP copy. Selecting the reopened profile highlights both labels and
  the trimmed region. A wrong association pointing to the hole edge instead
  of the drawn leader tip yields no scope proposal. Tests exercise both triangle-only
  graphics and single-stroke endpoints and arrow.
- The affected run passed 469 tests and the full run passed 1,105, with eight native
  screen checks skipped in each. All 16 focused and screen checks passed separately on Cocoa.
- Reproduced the next revision-comparison case on this export. The original 900 mm²
  patch, the same file with all STEP identifiers renumbered, a patch without the hole
  (1,000 mm²), and a patch with its 10 mm hole translated by 3 mm currently all yield
  unresolved endpoints. The latter two 900 mm² regions share only 870 mm². Compare the
  aligned region coverage on the matched supports, together with the oriented boundary
  edges. QIF remains the final item.

### Read and display separately trimmed surface-profile patches

- Checked PLAN §8.4 and docs/Roadmap.md. A supplemental face in the bounded profile's
  CONNECTED_FACE_SET now has its own STEP transfer session. The reader tests the patch's
  full area for overlap with each candidate product face, checks the product definition
  and representation context, and keeps a result only for a unique support. This also
  works when the patch has a separately defined geometric surface. Product topology and
  root count are unchanged. Partial overlap leaves the association unresolved.
- The PMI selection draws the actual trimmed region on its part. Zone offsets preserve
  boundary wires and holes. The report uses the STEP face number of the patch. Regression
  files cover a 20 × 50 mm planar patch with a 10 × 10 mm hole (900 mm²) and a
  cylindrical sector. Editing 1.25 mm to 0.8 mm and reopening the exported STEP keeps the
  patch, its boundary labels and its original callout. A rectangle crossing the edge of
  its support is a negative control. The signed local package and STEP examples are
  in `dist/main-pmi-teilflaechen/`.
- The edited 0.8 mm tolerance and the hole also survived a project save and reopen.
  A native rendering check compared pixels on the material, inside the hole and beside
  the trim. Only the material took the selection colour. The affected run passed 506 tests
  with eight screen tests skipped. A separate native run passed all eight screen tests
  and four profile checks. The final five profile tests cover project reload and a
  translated model added to a second document. The full run passed 1,101 tests with
  the eight native screen tests skipped.
- Selected the 459-face reconstructed pinion in the tree and exported it again using this
  build's source. Both the input and the reopened selection reported nine face teeth and
  459 faces. The resulting `Ausgleichsrad-9Z.step` is next to the signed app. Testing the
  original pictured part still requires its STEP geometry.
- Next §8.4 graphical review case: a triangle-only copy of CTC-01 has a profile frame
  and A/B leaders on two opposite edges of the 900 mm² perforated patch. A trial moved
  the original A and B callout graphics by (10, 0, 0) and (-70, -50, 0) mm respectively,
  then associated them with the patch edges. The raster reader recovered the 1.25 mm
  A/B/C frame. Both letters and arrow contacts passed when given the supplementary
  edges. Direct STEP transfer of those edges alone failed. Transferring their parent
  face and reading its transfer binders supplied the correct edges. The normal review
  still has no scoped proposal for this input. Preserve the patch reference, end edges
  and original graphics through project storage and STEP confirmation. Revision comparison
  of patch interiors is also open. QIF remains last.

### Use grouped model faces for scoped profile tolerances

- Checked PLAN §8.4 and docs/Roadmap.md against CAx-IF PMI v4.1 §6.4.3, Figure 34.
  A CONNECTED_FACE_SET can identify the restricted area through a related shape aspect
  and a separate shape representation. The reader now resolves its members to original
  model faces and excludes start/end features from the area. An empty group or a member
  without a model-face correspondence leaves the area unresolved.
- Graphical review of the triangle-only CTC-01 frame with this association recovered its
  1.25 mm tolerance, A/B/C datums, A/B boundary edges and original saved-view callouts.
  While testing export, the search for a face's representation reached the separate
  area before its product. The writer now finds the product first and emits the area
  as a distinct connected face set with its own representation in the part context.
- Verified that the old direct associations and the grouped form compare equal, that
  removing a member changes the comparison, and that a face used as an endpoint does
  not enlarge the toleranced region. OCCT read one solid with the same volume and no
  additional diagnostics.
- Further §8.4 case: a separate ADVANCED_FACE trimmed to a 20 × 50 mm rectangle
  inside the plane of CTC-01 face #553 is readable by OCCT but absent from the product
  transfer. The 139 product faces and the volume are unchanged. This area remains
  unresolved. Recover and validate its own trimming before highlighting or comparing it.
  The reproduction used the grouped example and a new bounds wire on plane #3344.
  A separate probe explicitly transferred that patch with STEPControl_Reader.TransferOne.
  Its surface area was 1,000 mm², all inside the 5,000 mm² product face. This adds a
  second shape to the reader, so the patch must stay outside the product's display shape
  and face index. QIF remains last.
- Rechecked the screenshot case with a second reconstructed pinion, now with 459
  individually trimmed faces, a crowned bore and a stepped back. The gear command
  found nine face teeth both in the source and after structure-tree STEP extraction.
  The original user STEP is still unavailable. The extracted example, grouped graphical
  and reviewed PMI examples and signed local app are in `dist/main-pmi-flaechenmenge/`.
- The complete offscreen run passed 1,095 tests, with eight screen tests skipped.
  All 28 native macOS checks passed, including those eight. The affected run passed
  123 tests, including the additional grouped-versus-direct and invalid-member
  regressions. The packaged app passed its self-test and ZIP verification.

### Compare the ordered boundary edges of scoped profile tolerances

- Checked PLAN §8.4 and docs/Roadmap.md. A removed A ↔ B restriction or swapped endpoint
  edges previously compared equal when the profile value and datums stayed the same.
  The semantic comparison now includes the ordered endpoint labels and matched edges.
  Spatial candidates come from the edges on the supporting face occurrences after model
  alignment. OCCT checks that common edge intervals cover both trimmed curves. Coincident
  candidates can be distinguished by their matched supporting faces. Ambiguity or missing
  geometry is reported for review. An imported BETWEEN_SHAPE_ASPECT with unresolvable
  endpoints remains recognizable as a bounded tolerance.
- Tests used separately imported STEP revisions with an added or removed restriction,
  swapped edges, reused numbers for changed geometry and a completely renumbered copy.
  The change table, review navigation and CSV carry the old and new extents. Further
  controls covered rigid assembly placement, independent numbering of duplicate frames,
  opposite semicircles, a full circle with a shifted seam and ambiguous coincident edges.
- All 394 affected tests passed, plus eleven checks on native macOS. The signed package
  passed its bundled self-test and ZIP integrity check. The separately distributed STEPs
  produced one semantic change for swapped edges and no changes for complete renumbering.
  Build and comparison examples are in `dist/main-profilvergleich/`.
- Remaining §8.4 case: profile extents that cut through the interior of a B-rep face.
  The converter currently requires distinct original boundary edges of a connected set of
  faces. A probe replaced the two direct face usages with a single usage referencing
  CONNECTED_FACE_SET (#553, #554). OCCT recognized the set with the same diagnostics as
  the input. The current PMI reader retained both endpoints but returned an empty face set.
  Test this restricted-area representation before tackling trimmed subfaces. See
  [CAx-IF PMI v4.1 §6.4.3](https://www.mbx-if.org/home/wp-content/uploads/2024/06/rec_pracs_pmi_v41.pdf#page=45).
  QIF stays last.

### Recover bounded surface profiles without annotation planes

- Checked PLAN §8.4 and docs/Roadmap.md. Removing all three annotation planes from the
  CTC-01 AP203 profile frame and its boundary notes prevented a proposal. The source
  contains a small round mark parallel to the main frame but at a different depth.
  Within-path edge directions now supply the plane normal, and the main lettering plane
  supplies candidate reading axes. Reprojecting the original geometry validates the mark
  separately. Endpoint lettering can have its own rotation and plane.
- The graphical review and STEP round trip passed for original contour glyphs, pure triangle
  fill and independently drawn A/B lettering with an open four-arm double arrow. In each
  case the profile remained 1.25 mm against A/B/C on faces #553 and #554, bounded by edges
  #2023 and #2025. The original three callouts, their saved view and absence of stored
  writing planes survived. OCCT recognized the semantic entity. A real digit 8, an incomplete
  arrow, and marks at conflicting depths were checked separately. Seven additional rigid
  rotations of the filled frame gave the same reading.
- All 12 affected tests and all nine native macOS profile tests passed. The signed app passed
  its packaged self-test. The build and the before/after STEP files for the triangle-only
  and single-stroke examples are in `dist/main-pmi-ohne-ebenen/`.
- Next comparison case: removing the restriction from an imported profile, or exchanging the
  two boundary edges while retaining the labels, currently yields `gleich` in the semantic
  comparison. Match the ordered ends after geometry alignment, independently of local STEP
  numbers. Include a renumbered but geometrically identical revision as a control. Handling
  scopes requiring new trimmed surfaces remains open. QIF stays last.

### Convert a graphical surface profile bounded by two named edges

- Checked PLAN §8.4 and docs/Roadmap.md. CTC-01 AP203 #3422 contains a 1.25 mm
  surface-profile frame against A/B/C. Its caption A ↔ B uses two independent lettered
  leaders in the same saved view. Their arrowheads touch original edges #2023 and #2025.
  Those are exterior edges of the connected faces #553 and #554. The same letters A and B
  in the datum compartments still refer to the actual datum features.
- Confirming the three datums and then the profile in the review dialog writes a
  BETWEEN_SHAPE_ASPECT with explicit start and end feature relationships. Reimport
  preserved the value, ordered datums, edges, faces and saved view. The original curves
  and, separately, the triangle coordinates and indices for all three callouts matched.
  OCCT recognized the typed STEP entity and reported the same legacy style diagnostics
  as for the input. Missing or displaced end markers, a shared interior edge, a disconnected
  selection and an unreadable scope caption all prevent the scoped proposal.
- The final affected test run passed all 362 cases. All three profile tests passed
  separately with native Cocoa windows. The signed package passed its built-in STEP
  self-test and the distribution ZIP passed its integrity check.
- Rechecked the user’s selection workflow. The available nine-tooth differential pinion
  example was recognized through the gear command both before structure-tree STEP export
  and after reopening the extracted part. All ten gear and selection-export tests passed.
  The user’s original part is still represented only by the supplied screenshots.
- Local macOS package and triangle-only before/after examples are in
  `dist/main-pmi-profilbereich/`. The extent is verified on whole faces with an explicit
  writing plane. Next §8.4 case: review a bounded profile without stored writing axes.
  Check both the orientation of the lettering and the detached round leader mark before
  offering geometry. Scope comparisons across revisions with renumbered edges, and
  extents that need trimmed subfaces, are also open. QIF stays last.

### Review diameter limits attached to a generic STEP dimension

- Checked PLAN §8.4 and docs/Roadmap.md. Original CTC-01 AP203 callout #3413 is named
  “linear dimension”. Its curves read “⌀34.8-35.2” and its associated cylinder (#611)
  measures 35 mm. The conversion dialog previously offered no limit values. It now uses
  the printed diameter sign to identify a possible size dimension. The reviewer chooses
  the two limits. The original graphic is also searchable before conversion.
- In the AP203 original and a triangle-only AP242 variant without a writing plane, both
  STEP readers recovered a 35 mm diameter and absolute limits of 34.8 and 35.2 mm on
  face #611. The original presentation coordinates and saved view survived export.
  A separate validation property with limits of 34.7 and 35.3 mm produced two distinct
  review choices. Each choice retained its own values after reimport. An explicit distance
  or radius type still prevents a conflicting diameter range from being offered.
- All 71 affected tests passed, as did six native macOS tests. The reproducible local
  package and before/after triangle-only STEP files are in `dist/main-pmi-grenzmass/`.
- Next §8.4 case: CTC-01 AP203 #3422 contains a surface-profile frame reading 1.25
  against A/B/C. Under the frame two separately readable letters A and B flank a closed
  double-headed arrow. The full annotation currently yields no proposal. Evaluate this
  scope indication together with the separately drawn endpoint notes #3425 and #3412.
  QIF remains last.

### Recover nominal and toleranced linear dimensions from graphical STEP

- Checked PLAN §8.4 and docs/Roadmap.md. Removing the parentheses and writing plane from
  CTC-01 AP203 callout #3418 produced a legible 85 mm nominal length with an empty OCR result.
  Use the lettering between the two dimension and extension lines. For an anonymous number,
  confirm the drawing unit and distance between the two explicitly linked planar faces.
  A number alone, a missing extension line, conflicting spacing or an ambiguous 66/99
  orientation do not supply a semantic proposal for an anonymous callout.
- Review, export and reimport recovered 85 mm from contour lettering, independent
  single-line digits and triangle-only lettering. A further pair of constructed inputs
  preserved 85 ±1 mm in strokes and pure fill. Both STEP readers returned the nominal,
  deviations and faces #568 and #572. The source polyline coordinates or triangle arrays,
  original view membership and distinction from the auxiliary dimension (85) were checked.
  All 72 affected tests and 11 native macOS checks passed. The signed app passed its
  packaged self-test and the distributed example pair passed a separate geometry and PMI reimport.
- Local Apple Silicon package and before/after STEP examples: `dist/main-pmi-linearmass/`.
  Next §8.4 case: original CTC-01 AP203 callout #3413 reads “⌀34.8-35.2” from its curves.
  Its generic “linear dimension” name currently suppresses the limit choice in the dialog.
  Check the drawn diameter, target cylinder and both limits through STEP. QIF remains last.

### Rounded face teeth on a differential pinion and structure-tree export

- The three user screenshots show nine broad teeth on the face of the pinion. The original
  STEP was unavailable. A constructed closed B-spline solid with nine rounded face teeth, a
  pin bore and a stepped back reproduces a missed detection. Fixed-order mass integration
  displaced its centre by 5.56 mm and picked a transverse axis. Adaptive integration recovers
  the rotation axis. Concentric axial height measurements on the tooth face recover the nine
  repetitions from the reimported STEP through the normal selection and analysis commands.
  The result is a bevel gear candidate. The reported surface inclination is a measurement of
  the tooth band. A nominal pitch cone and manufacturing dimensions still require other data.
- Rotated seven-, nine- and eleven-tooth meshes exercise the same detection. Smooth and
  flat dog-clutch controls reject the face-tooth classification. The signed Apple Silicon
  build, ZIP and approximate nine-tooth STEP example are in `dist/main-baumauszug/`.
- The structure tree and File › Export now write a selected part, multiple occurrences or a
  complete branch in assembly coordinates. STEP AP242 preserves the selected geometry,
  hierarchy, part names and face colours. This geometry extract omits PMI and saved views.
  Binary STL also accepts mesh parts. Round trips cover a moved occurrence, a repeated part,
  overlapping selections, sRGB face colour and an imported mesh.
- All 185 affected tests passed. The full suite passed 1,061 tests and skipped eight display
  tests, which all passed separately on Cocoa. Four native feature tests and the additional
  face-colour round trip passed. Reimporting the STEP selection extract of the example also
  recovered all nine teeth. The packaged app passed its self-test and rendered the example.
- Checked the implementation against PLAN §8.27 and docs/Roadmap.md. Verification on the
  user's original pinion remains open. QIF remains the final roadmap item.

### Differential pinion with a separate collared thrust washer

- The new two-part assembly reproduces the reported configuration: a rear spherical surface,
  an annular recess, a stepped bore, a separate spherical thrust washer and a projecting collar.
  Its ten-tooth pinion with trimmed toe and heel returned an empty result on main 12fb63d.
  The new fit checks the continuous root cone and the intact central tooth band. The inner
  profile distinguishes cylindrical steps from a crowned pin bore and the outer spherical back.
- Selecting the first counterbore face in the positioned STEP assembly returns the pinion. The
  gearbox command finds the same gear and the collar on the separate occurrence. Diameter and
  overlap agree with the reference (10.2 mm counterbore, 10.16 mm collar and 2.58 mm overlap).
  The second counterbore is 16 mm. CAD and STL controls exclude the washer as a gear. Additional
  generated variants recovered 8, 9, 11, 13 and 16 teeth. The user's model was unavailable.
- Checked PLAN §8.27 and the shipped Roadmap entry. The reusable example is in
  dist/main-kragensitz with the signed and self-tested Apple Silicon app and ZIP.

### Preliminary shaft, bearing, gear and joint sizing

- Checked PLAN §§8.38–8.39 against docs/Roadmap.md and kept QIF last. The gearbox report now
  includes cylindrical B-rep seats, source occurrences, candidate mating parts, diametral
  difference, overlap and selection. A smaller through bore and an adjoining wider flange on the
  mating component provide additional evidence for a sleeve or thrust-washer collar at a bevel
  gear counterbore. This identification is a candidate. The installed bearing type and actual
  fit require independent data.
- Tools › Size machine element starts without a model. Adopt supported gear-pair parameters
  or seat dimensions, supply operating conditions, save and reopen calculations, and transfer
  resultant tooth forces into a simply supported shaft. Modules cover nominal spur loads,
  static shaft torsion and bending, projected bushing pressure/speed, basic rolling-bearing life
  and cylindrical friction/interference joints. Shaft and bushing STEP round-trips retain their
  diameter and length dimensions as graphical and semantic PMI. Complete tooth strength
  ratings and parametric gear-pair assemblies with PMI are still open.
- Three native GUI tests passed, including selection of the pin bore in a STEP assembly,
  standalone sizing and tooth-force transfer. The packaged app rendered the new STEP assembly.
  The exported two-page PDF contains the counterbore dimensions and the collar candidate.
  All 178 affected tests passed. The full run passed 1,052 tests with 8 native display tests skipped.

### Selected bevel pinion with short spherical back and crowned pin bore

- Reproduced an empty gear list on main 3fe6d18 with a constructed 12-tooth pinion, rear
  sphere R15, circular bore crown R18 and bore diameter 8 mm at its mid-length extremum.
  The short back had a sphere-fit residual under 0.001 mm, yet its deviation from a straight
  line was smaller than the tooth-height-based rejection threshold.
- Checked PLAN §8.27 and docs/Roadmap.md. Back classification now uses the measured error and
  corroborates clipped tooth tips against spherical facets if the back ends before full circular
  sections can be measured. A through bore needs a closed inner contour and evidence of crown
  curvature on both sides. CSV, JSON and the data sheet expose the two radii independently.
- Regression controls select the actual bore face in a STEP assembly or the mesh occurrence in
  its structure tree. They include both crown directions and an interrupted spherical back.
  Negative controls cover straight and stepped bores, double cones, blind bores and a conical
  back. Six runs of the selection command in a native macOS window found exactly the selected
  gear. The generated STEP control returned back radius 15.004 mm, bore profile radius 17.994 mm
  and bore crown diameter 8.001 mm. The user's source model was unavailable. QIF stays last.

### Spherical-backed bevel gears and drivetrain reverse engineering

- Reproduced the reported classification failure with a generated 14-tooth bevel gear, a
  spherical back and a through bore. The back clips the tooth tips at the large end while
  the roots still follow their cone. Recognition now measures the intact section after
  checking the clipped tips and circular sections against a coaxial sphere. A straight
  chamfer or cylindrical shoulder does not provide that evidence.
- Rotated and translated STEP and STL controls recover 14 teeth and the expected tip and root
  cone angles. In a generated STEP assembly, two 28-tooth side gears and a 14-tooth pinion
  yield two 2:1 mesh candidates and the symmetric differential speed equation. When inspected
  as an isolated two-wheel stage the stage and overall ratios are both 2. The user's original
  model was unavailable for verification. The local main build in dist/main-kalottendifferenzial
  includes the signed Apple Silicon app, ZIP and generated 14/28/28-tooth STEP example.
  Opening the example in the packaged app rendered it successfully. The gear-train command
  selected its power-flow tab and its JSON contained both gear pairs and the speed equation.
  With carrier speed 80 rpm, specifying one side at 80 or 60 rpm gave the other side at 80 or
  100 rpm respectively. All 33 affected tests and the overlapping 46-case drivetrain run passed.
  The preceding selection changes passed the full 1,013-test headless run and eight native
  display tests. The subsequent thumbnail regression also passed.
- Checked PLAN §§8.27, 8.38 and 8.39 against docs/Roadmap.md. The planned system scope covers
  final drives, electric machines, engines, suspension and mechanism motion. QIF stays last.

### Reuse the model projection in saved views

- Checked the large-STEP work in PLAN §6 against the saved-view entry in docs/Roadmap.md.
  The preview worker computes visible edges once per exact pair of camera direction and up vector.
  Each view gets new PMI overlays and its original list position. Only the current orientation
  needs geometry in memory.
- The FTC-07 and FTC-10 reference files produced byte-identical SVG output for every saved view.
  FTC-07 needed ten projections for 16 thumbnails and FTC-10 needed twelve for 18 thumbnails.
  A regression test checks rotated cameras, differing PMI, original list indices and cancellation.
  The first projection of a complex model can still delay interaction. QIF stays last.

### Machine-element design scope and component selection

- Checked PLAN §8.38 against the planned section in docs/Roadmap.md. Forward sizing, verification
  and generation of geometry with PMI cover machine elements in general. The first planned
  end-to-end example is a cylindrical gear pair. Shared materials, units and load cases also
  serve bearing and shaft/hub modules. Each method needs its own validation. QIF remains last.
- Updated PLAN §8.27 and the shipped gear-recognition entry in docs/Roadmap.md. Wheel recognition
  follows selected component occurrences in the tree or viewport. Without selection it checks
  all physical components. Gearbox analysis still uses the visible assembly for power flow.
  Wheel and pair selections resolve to their source occurrences, including repeated parts.
- The user confirmed that the preceding large STEP import change improved opening their model.
  The filled-PMI display change passed 1,012 headless tests (eight display-only skips).
- Native macOS checks exercised selection on repeated screw occurrences. The packaged
  Apple Silicon app passed its self-test (117 faces, 23 PMI) and rendered the 111.55 MB STEP.
- Next §6 performance lead: the 18-copy FTC-09 input contains 414 saved views with only nine
  distinct (direction, up) pairs. The original FTC-07 has 16 views with ten distinct orientations.
  Investigate reusing projected geometry while applying the PMI of each view separately.

### Accelerate first display of filled PMI in large STEP files

- Checked PLAN §6 against the large-model viewing section of docs/Roadmap.md.
  The 111.55 MB AP242 stress case contains 18 independently numbered FTC-09
  models and 1,152 PMI. Per-triangle and per-node Python calls took over six
  profiled seconds. The view now passes vertices and triangles to OCCT in bulk.
  The same constructor serves imported meshes and coloured comparison maps.
- In three runs per version on the 111.55 MB case, median normal opening on the
  Mac fell from 16.49 to 9.22 s against 77f1b70. The maximum gap between UI
  timer callbacks fell from a median 7.03 to 2.24 s. With the same import code,
  profiling first display attributed 6.26 s to building 1,116 graphical callouts
  before batching and 0.29 s afterwards.
- Tested non-contiguous inputs, coordinates at double precision, triangle
  orientation, empty triangle lists and invalid indices. Rendering the original
  FTC-09 at a fixed camera before and after the change produced identical pixels.
- Next §6: investigate rendering the saved-view thumbnails of large shaded models
  without a long hidden-line calculation during opening. The user's own file
  and Windows performance remain unverified. QIF stays last.

### Prioritise large STEP files that appear to hang on opening

- Checked PLAN §6 and docs/Roadmap.md. Normal asynchronous file opening in a native macOS
  window reproduced a pause of almost four seconds on the 42.85 MB, 2,400-part assembly.
  Packaged apps now run OCCT reading and XCAF transfer outside the interpreter lock.
  A progress callback supports cancellation during transfer. Competing loads queue before
  allocating their indices. At 30 MB and above, a worker indexes Part 21 concurrently.
  Ordinary source imports also use this path after compiling packaging/step/bauen.py.
- Across three alternating runs per version, normal opening fell from 7.94 to 5.76 s,
  peak RSS from 1,789 to 1,566 MiB and the longest UI callback interval from 3.75 to
  1.64 s. The original local main build was 77f1b70. On a 37.06 MB aggregate of six
  NIST FTC-09 files, the native window opened 978 faces, 384 PMI and 138 saved views
  in 4.09 s. The reporting user's own file was unavailable.
- Compared the type index, every argument and all reverse references against the eager
  reader for 564,941 entities across 53 source files. Also exercised an interrupted
  native transfer, immediate retry, the source-only fallback and AP242 conversion.
- Cancelling the 42.85 MB import using the button at 3% and immediately opening
  CTC-01 displayed just the new model with all 117 faces and 23 PMI. The packaged
  executable also rendered a 111.55 MB aggregate (18 FTC-09 copies). Its normal
  opening took 13.21 s, with a 6.51 s pause on the first scene. Profiling found
  1.39 million individual triangle setter calls for the filled annotation graphics.
- Next §6: first display still takes the main thread for about 1.6 s on 2,400 parts.
  Check larger curved parts, scene construction and thumbnails on complex saved views.
  Verify Windows packaging and timing on Windows. QIF stays last.

### Resolve a single STEP datum with several faces

- Checked PLAN §8.20 and docs/Roadmap.md. The three coplanar pads of FTC-10 D
  resolve to one area-weighted datum plane. B and E each resolve to a connected
  cylindrical datum, including the small difference in E's axial trim limits.
  Model #19580 with these three datums at nominal evaluates to 3.6–4.4 mm at
  the same 4 mm radial measuring point on either core wall. The original file
  retains the local Ø0.8 contribution and reports open lower-level controls.
- In the two-pad test, the individual contributions are 0.1 mm each. Missing
  pads, duplicate STEP definitions, overlapping faces, a foreign cylindrical
  wall and one half with its own control leave the assessment open. The assembly
  measure and exported 3D chain give the same diagnostics, including after moving
  and rotating the part. All 74 focused regressions and 20 affected tests passed.
- Next §8.20: apply the joint axial extent consistently when a native position
  tolerance controls the entire split cylinder. An isolated Ø0.2 control on E
  referencing B is currently rejected because E's two trim lengths differ by
  0.000063 mm. A direct 4 mm measurement normal to plane #5 with a synthetic
  reference to that plane yields 0.26478594 or 0.26478553 mm width when just
  one half is controlled at y = 28.6 mm. Assigning the same source to both
  halves currently yields an incomplete verdict. Check the whole-span result
  separately from the support supplied by the lower-level datum frame. Distinct frames, multi-hole controls and material
  contact need separate checks. QIF remains last.

### Local macOS main build for testing

- Built the committed source of main at 77f1b70 for Apple Silicon, with the local
  JT converter. The ad-hoc signed app and verified ZIP are under dist/main-77f1b70/.
  The bundled self-test read 117 faces, 23 PMI and one saved view. A native Cocoa
  window rendered NIST FTC-10 from the packaged executable. All 57 selected tests
  for graphical PMI and projected tolerances passed from the same source snapshot.
  The packaged executable also rendered the 2,400-part, 42.85 MB STEP in 13.58 s
  from process launch through image export, including the 1.5 s capture delay.
- Checked PLAN §§8.3, 8.20 and docs/Roadmap.md. This is a local build of version 0.2.
  The construction-axis changes described below were in progress when it was built.

### Measure a projected STEP construction axis in the assembly

- Checked PLAN §8.20 against the assembly variation section of docs/Roadmap.md. In
  the Measures tab, choose a point on A, the associated core wall on B, and the
  construction-axis option. The selected occurrence, bore wall and STEP control
  identify the axis when the project is reopened. The nominal radial distance,
  source ID, projected tolerance contribution and open constraints carry through
  to the 3D chain. A project previously lost all measures if it had no assembly
  connections or poses. The normal project save now covers that case.
- FTC-10 #19580 defines two 10 mm construction axes around 12 mm core holes.
  Both half walls identified the correct axis, also after rotating and translating
  an occurrence and applying a second assembly pose. The projection was 3.2 mm high
  and centred at y = 28.6 mm. The isolated Ø0.8 control with a fully supporting
  radial datum gave a 0.8 mm range there and 5.8 mm at y = 17 mm. Sampling stayed
  within the limits. The original D/E/B frame retains its local contribution and
  reports the unresolved datum. A coincident point has no radial measurement direction.
- The native macOS run passed the project/chain round trip, three construction
  geometry checks and all eight display tests. The round trip used a second STEP
  file added to the first one, preserving occurrence, PMI ID and both limit values.
  The full suite passed 994 tests with eight display tests skipped there. The
  affected suite passed all 162 tests.
- Next §8.20: resolve the nominal geometry of a datum with several representation
  faces. FTC-10 D has three coplanar pads facing the same way. B and E each have two
  cylindrical wall patches. E's UV limits differ by 0.000063 mm at their trimmed
  ends. Preserve the distinction between one named feature and separate datums with
  the same letter. Check the influence of lower-level controls independently. QIF
  remains last.

### Resolve projected zone origins across split cylinder walls

- Checked PLAN §8.20 against docs/Roadmap.md. On a cylinder fused from two
  half shells, either half cap defines the same 10 mm projection for both
  walls. A point at z = 5 mm measured against the axis gives a 3.6–4.4 mm
  worst-case interval. Adding a coincident but disconnected cap now suppresses
  the in-spec verdict, records the reason in the 3D chain and omits the invalid
  zone. Source order has no effect.
- A two-axis pattern with exit faces at different heights and on opposite sides
  produced zone centres at (0, 0, 25) and (12, 0, 0) mm. Both source orders
  gave the same geometry. All 32 projection and STEP regressions and the 52 affected
  tests for the final projection changes passed.
- Next §8.20: NIST FTC-10 control #19580 uses two construction axes, each 10 mm
  long, with a 3.2 mm projection at y = 27 mm and no associated model faces in
  the tolerance record. Each axis coincides with two connected halves of a 12 mm
  core bore plus a conical drill point. Investigate selecting the construction
  axis as the measured feature, keeping thread and core-bore sizes distinct.
  Check the explicit exit, thread depth, repeated occurrences and independent
  movement of the two holes. QIF remains last.

### Compare worm and bevel hands with their PMI notes

- Checked PLAN §§8.22 and 8.27 against docs/Roadmap.md. Explicit German and English
  fields accept right, left, RH and LH. A bevel trace can also be straight. The
  gear report keeps the exact source wording and face association for a conflict.
  A hand for a different profile or an explicit alternative remains unresolved.
- Reopened a two-start left-hand AP242 screw with eight graphical callouts. The
  14 mm lead, 7 mm axial pitch and left hand agreed. The right-hand note produced
  a warning on its face and “LH/RH” remained open. The check also distinguished the
  matching and opposite hands on a right-hand STEP bevel gear and an STL screw.
  Six targeted tests passed. The macOS screen, graphical PMI and screw-dialog run
  passed all 19 cases. The manuals and English translation cover the new fields.
- Next §8.20: with a split cylinder wall, an origin on just one half cap can be
  missed when the other wall is selected. Conversely, adding a geometrically
  coincident cap from a different body to a valid cap can produce an in-spec
  verdict. Check the origin across the connected wall, the display and the
  3D chain. QIF remains last.

### Read repeated STEP geometry and build the PMI reverse index faster

- Checked PLAN §6 against the viewing section of docs/Roadmap.md. The reader decodes
  common two- and three-component point or direction tuples and short geometry references
  directly. It caches only immutable numeric values. References, coordinates and argument
  lists remain separately editable per entity. Quoted semicolons and comments still use
  the string-aware scanner. The reverse index collects links directly from nested arguments.
- Compared every entity and argument, the type index, and the reverse index including its
  key order and repeated source IDs on 55 local STEP inputs (594,731 entities). All matched
  the previous reader. On NIST FTC-09 the loaded PMI values, linked faces, drawing geometry
  and saved-view membership also matched, including 64 PMI and 23 views.
- Four alternating full loads per version in fresh processes on the Mac measured
  6.794 to 6.468 s for the 42.85 MB assembly and 0.712 to 0.682 s for FTC-09 against
  revision 19f4171. These timings include OCCT transfer and PMI extraction up to display.
- In four alternating index builds, the 42.85 MB assembly with 991,221 references took
  0.271 s versus 0.501 s with a collection before each build. FTC-07 took 8.93 ms versus
  15.88 ms. These timings cover index construction only. In the full working-tree regression run
  988 tests passed and the eight display tests were skipped. A separate run of all
  eight display tests and eleven PMI and gear cases passed with the macOS window server.
- Next §§8.22 and 8.27: check explicit worm and spiral hands in PMI against the measured
  tooth trace. The two-start reference has a 14 mm left-hand lead. Keep shaft rotation,
  ambiguous notes and a note about the wrong kind of profile distinct. QIF remains last.

### Accelerate occurrence matching in assembly revision comparisons

- Checked PLAN §6 against the comparison section of docs/Roadmap.md. The matcher
  groups parts by base name, consumes coincident centres in file order and uses
  spatial searches for moved occurrences and renames. Mutually closest pairs
  preserve the previous greedy ordering. A row shifted by half its spacing can
  resolve equal minimum distances together. Mass properties no longer compute a
  bounding box or count topology for each compared occurrence.
- Two generated AP242 revisions were reopened, each with 640 instances of one pin.
  The occurrence stage took 0.453 s before and 0.122 s after (three alternating
  runs, median). Both returned the same twenty 1 mm moves, IDs, order and vectors.
  For the matching step on equivalent centres the traced Python allocation peak
  fell from 49.71 to 0.66 MiB. The 2,400 differently named parts of the 42.85 MB
  reference took 0.928 s versus 0.668 s. These component timings exclude import
  and surface comparison. Findings also matched on 1,500 generated groups with
  ties, geometry changes, renames and unequal counts. All 19 affected tests, 36
  comparison regressions and the native macOS assembly-dialog check passed.
- Next §6: opening the same 847,220-entity STEP attributed 5.25 s of a profiled
  load to Part 21 reading. Of 242,403 point and direction statements, 180,374
  use just 64 distinct argument strings. Instrumenting Entity.args during a
  normal load recorded no calls for those two types. Optimise repeated geometry
  records and measure total opening time. Check mutable arguments, reference
  graphs, malformed input, annotations and export against the existing reader.
  QIF remains last.

### Read bore arcs printed as filled strips

- Checked PLAN §§8.35–8.36 against docs/Roadmap.md. The print contour provides
  two opposing edges and two short caps. Their centreline joins the same rim
  registration as a stroked arc. Both edges need visible paper beside them.
  Filled disks, broad sectors, duplicate quarters and overpainted gaps stayed
  unresolved. Qt PDF output verified flat, square and round caps on a rotated
  ellipse with a minor-to-major axis ratio of 0.24.
- In the comparison dialog the filled circular and elliptical rims identified the
  changed bore and its CSV result. The plate dialog rebuilt two bores from filled
  semicircles with the measured volume, diameter tolerance and H7 fit on the correct
  walls after STEP reimport. All 30 affected tests, 13 native macOS checks and 87
  additional drawing comparison and reconstruction cases passed.
- Next §6: the occurrence comparison builds every pair of distances between parts
  with the same base name. On this Mac, comparing a 640-occurrence subset of the
  42.85 MB STEP to itself, with numbered occurrence names on both sides, took a
  median of 0.477 s including properties. It generated 409,600 candidate pairs for
  640 exact position matches. Preserve the existing distance and input-order ties,
  alignment and rename findings while reducing this cost. QIF remains last.

### Register and reconstruct bore rims drawn as separate PDF arcs

- Checked PLAN §§8.35 and 8.36 against docs/Roadmap.md. Stroked arcs may appear
  in any order or direction. Each endpoint needs one partner and the resulting
  loop must fit a circular or elliptical rim. The rendered outline is checked at
  pixel spacing. Missing arcs, competing branches, clipped or dashed strokes,
  retraced semicircles and a twelve-sided polygon stayed unresolved.
- The drawing dialog matched four split bore rims in an axial view and on a
  rotated oblique sheet. Selecting the leader on the Ø4.1 drawing selected the
  Ø4.0 bore wall and exported the difference to CSV. The plate dialog rebuilt two
  through bores from semicircles. Both STEP readers recovered the diameters, wall
  associations, bilateral tolerance and H7 fit. The solid volume matched the two
  subtracted holes and all nine semantic dimensions retained their graphics.
- The 22 affected tests, five native macOS tests and 87 additional drawing
  comparison and reconstruction cases passed. All eleven sheets of NIST D2MI
  904–908 kept their previous ring counts, including small elliptical rims. The
  controls for split arcs are generated PDFs.
- Next §§8.35–8.36: Qt's PDF printer can emit each quarter as a closed, thin
  filled strip. Four such quarters form a visible circle but currently yield
  zero registered rims. The same four quarters emitted as ordinary strokes yield
  one. Test strip centre lines, including their cap geometry. QIF remains last.

### Follow open drawing arrows to their model bore walls

- Checked PLAN §8.35 against docs/Roadmap.md. Two free, symmetric arrow wings can
  identify a bore when their common tip meets the centred leader shaft on one
  registered rim. PDF inputs tested include a polyline, separate strokes and a
  thin filled outline emitted by the Qt PDF printer in a mirrored oblique view.
- In the four-hole drawing, the printed Ø4.1 points to a model Ø4.0. The dialog
  selects that wall even with a competing PMI of Ø4.1 elsewhere. Confirmation
  and CSV retain the difference and the correct circular or elliptical target.
  Branched quantity leaders can use open heads on each target. Missing wings,
  crossed tips, dangling branches and off-centre or reversed shafts stay unresolved.
  The 74 affected tests and 33 additional native macOS checks passed.
- Next §8.35: a PDF probe draws three complete, identical 13-point-radius rims.
  The one-path circle registers. When two semicircle paths or four quarter-circle
  paths meet on the page, neither registers yet. Check unambiguous closed chains
  and reject partial or branching paths. QIF remains last.

### Recover parenthesised reference dimensions without a writing plane

- Checked PLAN §8.4 against docs/Roadmap.md. CTC-01 AP203 #3418 was opened with its
  plane removed. A second, anonymous AP242 variant contains only filled triangles,
  including the holes in the eight. Both proposed “(85)” as an auxiliary linear
  dimension on faces #568 and #572. The anonymous proposal requires the two
  explicitly linked planes to agree with the printed value in its drawing unit.
- Review and STEP export preserved the source graphics and saved-view association.
  Both readers recovered 85 mm and the same two face IDs. The 3DGmax reader also
  recovered the auxiliary qualifier. A half-turn ambiguity such as (66)/(99)
  leaves the text unresolved without a writing direction. All 33 affected tests,
  four native macOS checks and 64 additional graphical PMI regression cases passed.
- Next §8.35: a generated PDF of the four-hole test part currently misses the wall
  at the tip of a centred open arrow, both as a single polyline and as two separate
  wings on a rotated sheet. The closed-arrow and dangling-branch controls passed.
  QIF remains last.

### Recover unframed angles from strokes and solid lettering

- Checked PLAN §8.4 against docs/Roadmap.md. The OCR reader checks the closed centre
  of a raised degree sign, including the double outlines in CTC-01 AP203. If the long
  edges of a planar callout do not explain its lettering, recurrent glyph edges can
  supply the writing axes. Two long non-parallel witness lines with closed arrowheads
  can be separated from sparse stroked text before reading it at higher resolution.
- CTC-01 AP242 callout #618 was reopened without semantics, validation text, placeholders,
  a name, a positioning transform or a writing plane. The original mixed source and the
  triangle-only variant recovered 60° ±0.5°. An independent stroke-only 60° preserved
  the absence of deviations. The reviewer selected the angular location and the two
  source faces. Both STEP readers recovered those faces and values. All source entities
  survived the export, and MBD_0 displayed the new semantic dimension. A rotated
  stroke-only control with an open degree ring stayed unresolved. The 25 affected
  tests, four native macOS tests and a 64-case graphical STEP regression run passed.
  Extra glyph axes are checked on demand. In a three-run median, routine no-plane
  diameter #607 took 232 ms (previously 235 ms) and flatness #611 took 21 ms in both versions.
- Next §8.4: CTC-01 AP203 callout #3418 is a parenthesised reference dimension. With
  its stored plane the same strokes read “(85)”; removing the plane currently leaves
  the proposal empty. The orientation search yielded only “(85)”. Verify the auxiliary
  modifier, the length unit and both target faces through STEP review and reimport.
  QIF remains last.

### Compare screw axial pitch and lead in PMI notes

- Verified PLAN §§8.22 and 8.27 against docs/Roadmap.md. The geometry check uses the
  two distinct measurements from the screw sections. Lengths with explicit metric
  or inch units take precedence. A unitless value can use its own STEP drawing context.
  Conflicting contexts, unsupported units or qualifiers, and a missing measurement
  on a wheel remain visible for review. The warning threshold is 0.7% of the nominal.
- Opened a generated left-handed, two-start AP242 screw with six face-linked notes
  in the application. The 7 mm axial pitch and 14 mm lead were recovered. Wrong values
  in one note produced two warnings. A half-inch lead in an inch context was reported
  as 12.7 mm. Conflicting mm/inch contexts left the bare pitch open, while the explicit
  inch lead in the same note was checked. The mesh control has no implicit text unit.
  All 57 affected tests passed.
- Next §8.4: original NIST CTC-01 AP242 callout #618 reads “60°±0.5°” with its
  writing plane. Removing the plane leaves the same strokes unread. Verify angular
  lettering, including a triangle-only source, from review through STEP reimport.
  QIF remains last.

### Check wheel teeth and screw starts in PMI notes

- Checked PLAN §§8.22 and 8.27 against docs/Roadmap.md. The PMI checker now uses the
  conical, throated and screw profiles from the gear analysis. A tooth-count note
  is checked on wheels and an explicit number of starts on a screw. Each discrepancy
  identifies its source. A parameter without a matching measurement stays open.
- A generated 14-tooth bevel gear was reopened from STEP, a two-start screw from STL.
  Together with an 18-tooth throated wheel these controls distinguish correct values,
  wrong counts and requests for a measurement unavailable on that profile. The 40
  affected tests passed, as did a separate run of 18 mesh, band and note controls
  and the three updated special-profile tests with the file imports.
- Next §§8.22 and 8.27: compare explicitly labelled axial pitch and lead with the screw
  profile. The reference has a 14 mm lead and 7 mm axial pitch. A note with two starts,
  8 mm axial pitch and 16 mm lead currently returns only the start count. Include unit
  handling and retain the wheel/screw distinction. QIF remains last.

### Match each gear note to its own wheel or toothed band

- Checked PLAN §§8.22 and 8.27 against docs/Roadmap.md. The plausibility check keeps
  every distinct stated value and note number. Explicit STEP callout-to-feature links
  resolve to the model faces. Disconnected mesh bodies retain their source faces.
  On one stepped shaft, the axial interval and measured root/tip radii distinguish
  a flank of one band from the neighbouring band. Shared prototype faces, links across
  bands and mesh faces covering multiple components stay open.
- Verified using a generated AP242 solid with 14 and 21 teeth and five independent
  annotations. Opening it in the native macOS app and double-clicking a finding
  selected the source note and highlighted its linked faces. Reversing conflicting
  notes on a 23-tooth gear reports the same source. Tests cover separate and common OBJ
  face records, a small separate triangle sharing an STL face with a gear, repeated
  B-rep occurrences and an unrelated housing face. A connected OBJ shaft with one
  source face per selected flank identified both bands and left the shared remainder
  unresolved. The 53 affected tests and the additional connected-OBJ test passed.
- Next §§8.22 and 8.27: the regular gear analysis recognises a generated right-handed
  14-tooth bevel gear with 0.55 tip taper and 0.008 radians of tooth rotation per mm.
  On the same geometry, the PMI checker warns that no involute gear is recognisable
  for both “z = 14” and “z = 15”. Check known tooth counts on conical and throated
  gears against notes, distinguish worm starts from wheel teeth, and indicate which
  parameters need a mating gear or independent specification. QIF remains last.

### Recover unframed graphical diameter and radius dimensions without a stored writing plane

- Checked PLAN §8.4 against docs/Roadmap.md. A planar size callout can supply candidate axes
  from strokes or triangle edges, checked against the lettering. Only a complete diameter or
  radius reading agreed across the legible orientations proceeds to review. The dimension
  parser and the review dialog share the interpretation of two values separated by a hyphen;
  the reviewer still chooses whether these are limits.
- Removed the writing planes from all twelve FTC-07 size callouts. All twelve match their
  stroked reference strings. Four CTC-01 rows retain stacked deviations or absolute limits.
  Tested the native review and STEP round trip for FTC-07 quantities, symmetric and stacked
  deviations, a diameter with a detached target arc, and the radius range R.022-.012. The
  cases include stroke-only and triangle-only files. Both readers recovered the semantic
  dimensions and target faces, and the original STEP presentation entities were preserved.
  A separate anonymous solid-font Helvetica R2 and a sparse stroked R2 passed without a
  writing plane, positioning metadata, validation strings or text placeholders. A rotated
  3D callout is readable and a noncoplanar perturbation is rejected. The 61 affected
  tests and nine focused native macOS tests passed.
- Next §§8.22 and 8.27: check gear annotations against their source and target bands. A
  23-tooth control with independent notes #1 “z = 23”, #2 “z = 24” and #3 “deburr”
  gave zero findings in file order. Reversing the order found the discrepancy but cited
  all three notes. The checker concatenates every note and takes the first value per
  parameter. Preserve each note's identity and geometry association; keep ambiguous
  annotations on multistage or repeated gears explicitly open. QIF remains last.

### Update individual assembly parts and revision colours in the viewer

- Checked PLAN §§6 and 8.1 against docs/Roadmap.md. Tree visibility updates changed occurrences,
  their edge presentations and their picking modes. Transparency changes touch the visible
  affected parts. The face index already built by the viewer supplies the visible tolerance-zone
  targets, including model faces shared by several occurrences.
- Same-alignment revision colour changes update the affected presentations and removed-face
  overlay. A realignment rebuilds the scene. The highlight checkbox also clears occurrence
  overrides. The regression test previously retained new/changed colours after selecting
  the new revision and clearing the checkbox on the example assembly.
- Native macOS benchmark on the 42.85 MB / 2,400-part STEP, in milliseconds including redraw:
  single-part visibility 41.83 → 25.02, transparency 38.33 → 17.14 (ten toggles each);
  comparison highlighting with one changed face 640.73 → 34.05 (six toggles). With one
  box hidden, the same 14,394 tolerance-zone face indices took 62.20 → 9.86 ms to retrieve.
  The full suite passed 927 tests; the eight screen tests skipped offscreen also passed on native macOS.
- Next §8.4: without a writing plane, all twelve unframed FTC-07 linear size annotations
  previously returned empty OCR text. Test the three diameter formats and the radius range
  in original strokes and pure triangle fill, plus an independently rendered filled font.
  QIF remains last.

### Retain the two pocket-center dimensions from the drawing

- Checked PLAN §8.36 against docs/Roadmap.md. A rectangular pocket, rounded pocket or
  axis-aligned obround now retains the reviewed X and Y coordinates, deviations and limits.
  Each STEP location references the plate side and the median plane of the corresponding
  two pocket walls or semicircular ends. Separate face aspects in a composite preserve
  both target walls in the native XCAF reader. The drawn dimension uses the projected
  witness on the plate side and the midpoint of those specific walls.
- Two equal pockets, blind and through, were tested with different X and equal Y.
  Both STEP readers recovered the original dimensions, limits and three distinct faces.
  Changing the reference role yields a comparison finding. Tested edge clearance and a
  coordinate interval overlapping a second pocket or a counterbore. 322 affected tests
  and 28 native macOS drawing-reconstruction tests passed.
- Next, large assembly interaction (§6): on the 42.85 MB STEP with 2,400 solids the native
  viewer took 41.83 ms to toggle one part and 38.33 ms to toggle its transparency (medians
  including redraw). Each action refreshed every part and selection mode. QIF remains last.

### Reconstruct and dimension opposed drill points from a shaft drawing

- Checked PLAN §8.36 against docs/Roadmap.md. A clear material gap lets the reader evaluate
  each entry side independently. Two cones with different angles or one cone and one flat
  floor are supported. Each terminal table row has its own included angle and depth reference.
  The drawing scale checks both the full-diameter length and the apex position. The limiting
  axial reaches include angle and diameter tolerances when depth ends at the full diameter.
- Checked horizontal and vertical PDFs, simple and stepped cores, with solid and dashed walls.
  Two Ø6 cores from opposite sides retain different fits, angle targets and depth origins. The
  native review and both STEP readers verified the axial depths and cone association. The
  graphical witness, circular edge, apex location, cone angle and actual solid volume were
  measured after export. A missing flank or tolerance intervals exhausting the central material
  block the result. 49 affected tests and 28 native macOS tests passed.
- Next §8.36: preserve approved pocket-center coordinates as graphical and semantic PMI. A
  60 × 40 × 8 plate with a 12 × 8 pocket at (15, 16), depth 3, currently reloads with six
  dimensions (60, 40, 8, 12, 8, 3). The entered X and Y are missing. The same normal input
  with X = 15 ±0.1 is rejected before export. Verify the distance from the left or bottom
  plate face to the derived median plane of the associated pocket walls and the original
  coordinate limits, including equal-sized pockets at different locations. QIF remains last.

### Review the second detached FTC-07 surface count

- Checked PLAN §8.4 against docs/Roadmap.md. MBD_B's separate #16374 wraps “4 COPLANAR
  SURFACES” across two lines under #14143. The matching window now uses the width of both
  value cells and row height. The previous MBD_C case, out-of-plane text, displaced text and
  competing annotations remain covered. Both reference frames passed as original strokes and
  as pure triangle fills without writing planes, feature links, semantic PMI or validation
  text. Both readers recovered the two expected values, the accepted caption, target faces
  and the original saved view. 15 affected and 5 native macOS tests passed.
- Next §8.36: opposed blind bores with drill points in a dimensioned shaft drawing. A local PDF
  probe used the existing outside contour (12 mm × Ø20, 18 mm × Ø12), a Ø6 hole 9 mm deep
  from the left and a Ø4 hole 8 mm deep from the right. Two flat floors returned both seats
  and a Gegenbohrungen record. Replacing only the floors with symmetric 90-degree drill
  points returned zero seats and no bore record. Single-ended cones already support
  cylinder-end versus apex dimensions. Extend detection, per-side angle and depth checks,
  projection and semantic STEP targets; verify material between the two deepest tips. QIF
  remains last.

### Compare a combined coplanar and simultaneous caption

- Checked PLAN §§8.4 and 8.35 against docs/Roadmap.md. A composite caption with a surface count
  and SIM REQT retains both meanings when STEP stores the description on one line. Group review
  now reports missing explicit model partners for either row, including when the reviewer marked
  it as independent on the sheet. Split and single-line drawing captions preserve the face-count
  check and numbered group suggestions. An arbitrary sentence containing SIM REQT does not
  establish a group caption.
- Checked numbered and unnumbered variants with FTC-07 nominal faces, contradictory wording,
  pending memberships and the existing saved-view conversion. 21 focused and 56 affected tests passed.
- Next graphical reference: MBD_B contains #14143 and the detached #16374. Its text is “4 COPLANAR”
  followed by “SURFACES”, with no simultaneous requirement. Both rows of profile tolerance and
  all caption letters already read individually. The source caption starts 0.414 row heights
  inside the first value cell; the previous matching window stops at 0.35. Test this layout,
  competing notes and the graphical-only exports without adding a group. QIF remains last.

### Review detached 3D lettering with its composite frame

- Checked PLAN §§8.4 and 8.35 against docs/Roadmap.md. FTC-07 annotation #16461 now supplies
  “4 COPLANAR SURFACES SIM REQT” directly from its lettering. Captions must align below the first
  value cell in the same saved view and plane. A second owner or caption, conflicting explicit
  targets, or contradictory source text withholds the proposal. Selecting the optional checkbox
  on the upper row includes the note on both controls. Skipping it keeps the descriptions empty.
- The graphical-only fixture strips target links, semantic PMI and validation text. Both original
  strokes and solid triangles without any writing planes on either annotation passed review,
  export and reload. The original STEP entities, MBD_C, target faces and composite relationship
  survive. Open CASCADE independently read both descriptions. The lettering creates no simultaneity
  relationship. 20 lettering regressions and 11 native macOS tests passed.
- Next §8.35: reviewing one independent drawing row against the newly exported combined caption
  can report matching group membership despite the model requesting SIM REQT with no explicit
  partner. Reproduced an incorrect “gleich” on both FTC-07 rows. Keep wording, target-face
  geometry and the group membership finding distinct. QIF remains last.

### Find separately stored semantic text on the STEP target feature

- Checked PLAN §§8.4 and 8.35 against docs/Roadmap.md. Both tolerances of the four-face
  FTC-07 frame reference shape aspect #13858. The dialog and CSV now show that semantic text
  property #16453, representation #16454 and annotation #16461 supply exactly the two printed
  lines “4 COPLANAR SURFACES” and “SIM REQT”. The two tolerance descriptions remain empty.
  Their difference from the caption and the independent simultaneous-group finding are preserved.
  The other pair has no such property on its target.
- Only properties explicitly named semantic text on the shared feature are considered. Redirected
  properties and validation properties do not contribute. A partial representation is unresolved.
  STEP representation items form a set. The comparison preserves each item's word order and
  keeps ambiguous line breaks between items open. The native dialog, exported source references
  and original file evidence were checked. 71 affected tests and 23 native macOS tests passed.
- Next §8.4: read the same detached caption from actual lettering when the semantic text is
  absent. A local probe rasterised the original #16461 strokes on their writing plane. The
  current wide-font templates gave “? CO?LANAR SURFACES” and “SIM REQT”. The leading 4 and P
  are the reproducible missing shapes. Verify stroke and pure-fill variants, then use source
  associations and the writing plane to present the detached note for review with its frame.
  QIF remains last.

### Compare simultaneous partners per row of a drawing composite frame

- Checked PLAN §§8.4 and 8.35 against docs/Roadmap.md. In the drawing dialog each row has its
  own partner review. Confirmed sets may include individual controls or rows from other frames
  and sheets. Numbered captions suggest the same printed row position. Review before all sheets
  have been opened stays provisional. Editing a single row clears its membership; changing the
  shared scope or removing the frame clears both.
- A two-sheet PDF and an FTC-07 STEP variant with only the upper link produced a matching
  upper group (#14614, #15076) and a different lower group (#14623, #15085 on the drawing).
  Both groups' member regions, mapped IDs, expected IDs and findings are in the CSV. Checked a
  model with both explicit links and one with a link across unverified datum systems. When the
  model only names SIM REQT with no explicit partners, membership remains unresolved.
- Verification: 88 affected tests passed, 30 passed with native macOS Qt, and the English
  translation inventory is complete. QIF remains last.
- Next §8.4/§8.35 case: FTC-07 stores the words omitted from #14614 and #14623 in a separate
  callout. #16461 (Text.8) and frame #14636 share the MBD_C writing plane and shape aspect
  #13858. Its semantic text property #16453 contains “4 COPLANAR SURFACES” and “SIM REQT”.
  The other frame #15098 is in MBD_D. Its embedded scope is already legible. The standalone
  lettering reader currently returns no text for #16461. Distinguish evidence linked to the
  target feature from an explicit tolerance description or a confirmed relationship.

### Check the printed number of coplanar target surfaces

- Checked PLAN §8.35 against docs/Roadmap.md. The right frame on FTC-07 sheet 3 names four coplanar
  surfaces. Both assigned STEP tolerances #14614 and #14623 cover faces 3, 265, 266 and 267. Open CASCADE
  confirms four separate patches in one nominal plane. Selecting the other pair (#15076 and #15085)
  still matches both numeric rows but reports one target face instead of four in the preview.
- The geometric result appears separately from the STEP descriptions in the review and CSV.
  Rotated normals, plane offsets, opposite normals, a placed planar Bézier face, intersecting
  bounding boxes with disjoint faces, touching patches, curved faces and missing geometry have
  regression coverage. Reused face prototypes with several placements need occurrence selection.
  Unknown additional scope wording stays open even when the printed and model descriptions agree.
- Verification: 69 affected tests passed, and 31 tests passed with native macOS Qt. For the next
  §8.35 case, independent STEP links added to an FTC-07 copy yielded two confirmed simultaneous
  groups: #14614 with #15076 against A/B/C, and #14623 with #15085 against A. Compare the selected
  drawing partners per row. A link on the upper row alone cannot prove the lower row's membership.
  QIF remains the final package.

### Compare the two drawing rows with the directed STEP pair

- Checked PLAN §8.35 against docs/Roadmap.md. Open FTC-07 sheet 3, choose inches and assign
  the upper and lower semantic controls. The left frame maps to #15076 and #15085; the right
  frame maps to #14614 and #14623. Both pairs match in individual values, datums, directed link
  and common model faces. All four semantic tolerance descriptions are empty. The drawing
  scope wording differs, and simultaneous group membership is a separate open finding.
- The review and CSV distinguish row values from a missing, reversed or extra composite link.
  Both source IDs and model values are exported. Removing a selected lower tolerance from the
  open model invalidates that assignment. Tests include reading modified STEP files with the
  link removed, reversed or redirected while all printed and model tolerances stay the same.
- Verification: 84 affected tests passed, 23 tests passed with native macOS Qt, and all UI
  strings have English translations. QIF remains last. For the next geometric check, Open CASCADE
  placed all four faces of #14614 on the same plane, with at least 137.248 mm between any two.
  Face 8 of #15076 lies on a different parallel plane. Both pairs have identical nominal PMI.

### Oblique composite controls on FTC-07 drawing sheet 3

- Checked PLAN §8.35 against docs/Roadmap.md. Sheet 3 shows two surface-profile frames with
  a shared symbol cell. PDFium returns one scope caption in the same text run as an adjacent
  value. The drawing reader uses native text origins to locate each frame, rectifies its two
  axes, then reads the actual printed cells. Both frames contain .070 against A/B/C over .015
  against A. Both say SIM REQT. Only the right-hand frame says 4 COPLANAR SURFACES.
- Verified both rectified previews visually against the sheet. A synthetic inclined PDF tests
  a numbered caption, split symbol cell, unsupported wording and competing captions. The File
  menu and CSV preserve the transcription, order and four drawing corners. The compound finding
  stays open for review. No simultaneous partnership is inferred.
- 62 affected tests passed. Twelve tests passed with the native macOS window. The next comparison
  case is grounded in the unmodified STEP: upper #14614 links to #14623 on four faces and
  #15076 links to #15085 on one. Both upper values are 1.778 mm and reference A/B/C. The printed
  and STEP scope wording, the ordered relationship and the selected target need separate evidence.
  QIF remains the final work package.

### Numbered scope notes in graphical 3D composite frames

- Checked PLAN §§8.4, 8.18 and 8.35 against docs/Roadmap.md. Confirmed FTC-07 #15098 failed
  to read after placing its own digit 1 to the right of SIM REQT. The scope reader now checks
  a digit suffix against the wide CAD glyphs. The rounded zero and octagonal O are compared
  using their mean and maximum distance from the source ink. Tests use original glyphs from
  FTC-07 for all ten digits. Lookalikes 1I, 1O and 1Q, a leading zero and a damaged 1 stay
  unresolved in both strokes and pure triangle fills.
- A graphical-only FTC-07 variant with SIM REQT 10 was reviewed and exported three ways:
  strokes, triangle-only lettering and triangles with the writing plane removed. Reimport
  retains both printed tolerance rows, original geometry entities, the common target faces,
  the MBD_D view, the composite relationship and the group number in both semantic descriptions. Open CASCADE
  independently read both descriptions from the plane-free export. A validation note with no
  number is reported as shorter; one naming group 1 conflicts with the drawn group 10.
- Numbered wording on a single control preserves the identifier. Explicit partner membership
  remains a separate review. The drawing recogniser currently suggests group numbers from native
  PDF text or reviewed transcriptions. Automatic recognition of the same note from pure drawing
  graphics is still open. In the local NIST FTC-07 reference PDF, sheet 3 exposes two tilted
  “SIM REQT” strings in PDFium text; one includes an adjacent .070 A B C row in the same text
  box. The automatic sheet reader currently returns neither as an attached scope note.
- Verification: 36 affected tests passed, followed by 68 tests covering graphical repair,
  composite frames and drawing groups. Twelve passed with native macOS Qt. QIF remains last.

### Simultaneous tolerance groups across PDF sheets

- Checked PLAN §§8.4 and 8.35 against docs/Roadmap.md. The drawing review can compare a
  user-confirmed set of sheet regions with an explicit STEP group. Numbered native PDF captions
  suggest other matching rows. Unnumbered captions require the reviewer to select the partners.
  An early review stays open until confirmed with all sheets available. Revising the transcription
  or removing a member clears the previous group. Editing a model assignment recalculates it.
- Tested the File menu with a generated two-sheet PDF. Each sheet has a surface-profile tolerance
  of .070 inch against A/B/C. A modified NIST FTC-07 links actual controls #14614 and #15076.
  Both rows matched. Adding #14472 to the STEP group changed the two group findings while all
  printed values remained the same. The CSV identifies both PDF regions, mapped STEP IDs, expected
  IDs and the membership finding independently of the values.
- Tests also cover repeated group numbers in separately confirmed views, duplicate or unresolved
  assignments, extra drawing-only members and unverified model datum systems. Bare simultaneous
  wording in a STEP description does not establish membership. The whole-drawing verdict is open.
- The next lettering case is a numbered group suffix drawn as strokes or pure triangle fill on
  a 3D control frame. On FTC-07 #15098 the original seven letters and both tolerance rows read
  correctly. Moving that frame's own digit 1 (curves 10 and 11) after the T with a shift of
  +24.65 and -13.21 mm along its writing axes produced an empty OCR result. This gives a
  reproducible next case. The 2D number proposal currently reads native or reviewed PDF text.
- All 82 affected tests passed, as did 24 tests with native macOS Qt. All 2,630 interface
  strings have English translations. QIF remains last.

### Part 21 loading and filtering annotations in the 3D viewer

- Checked PLAN §§6, 8.4 and 8.13 against the Viewing section in docs/Roadmap.md. Compared the
  new lexer against the previous reader on all 53 local plain STEP files. All 564,941 entities,
  subtype lists, typed arguments, numbers and references matched. The 847,220-entity synthetic
  assembly took 2.30 s to parse from text (previously 3.21 s, medians of three).
- The normal loader now keeps a small summary of the standard declarations from the decoded
  STEP text. Plain, ZIP and gzip FTC-07 all report ASME Y14.5M-1994 and set it on each PMI.
  A CTC-01 variant with a declaration at byte 61,213,817 opens with ASME Y14.5-2018, 117 faces
  and 23 PMI. The standalone comparison with the immediately preceding loader took 6.88 s versus
  7.77 s for the 42.85 MB benchmark, with the same 14,400 faces. Comparing both import changes
  together against commit 01420db in alternating fresh Python processes gave medians of
  11.43 s before and 7.61 s after (three runs each, warm filesystem, test suite running).
- Native macOS profiling showed that a PMI filter change reactivated assembly picking for
  every part. Filter, highlight and contrast now update just the annotations whose appearance
  changed. Replacing a graphic under the same callout ID removes the old AIS objects. The native
  check exercises hide, highlight, replace and hide again without reactivating geometry selection.
- In 12 alternating filter updates on FTC-07 the median fell from 29.6 to 24.9 ms, with the
  same 30 and 53 visible annotation objects. In the 2,400-part assembly without annotations it
  fell from 42.1 to 0.014 ms. Both timings include the Qt event pass on this Mac.
- For the first native scene build, the number of OCCT Display calls fell from 12,001 to 7,201.
  Single profiled runs took 1.87 s and 1.93 s. Initial AIS presentation is still the largest
  cost and these figures do not establish a first-frame speedup.
- Verification: 862 tests passed in the full suite. All eight screen tests skipped in the
  offscreen run passed on native macOS. All 2,610 interface strings have English translations.
- Persistent tessellation caching, viewer levels of detail and cross-row simultaneous groups in
  drawings remain open. QIF stays last.

### Large STEP loading and standard detection

- Checked PLAN §8.13 against the Viewing section in docs/Roadmap.md. Candidate detection for
  ISO, ASME, ANSI and DOCUMENT now uses overlapping 256 KiB character blocks. The complete
  expression is evaluated in the original text, including mixed case and multiline references.
- The detected standard, explanation and fallback flag matched the previous implementation on
  all 60 local STEP and QIF test files. Regression cases cover overlapping prefixes, Unicode
  case equivalents, block boundaries, repeated notes and the precedence of declared standards.
  All 80 affected tests passed.
- On the 42.85 MB STEP assembly with 2,400 solids and 14,400 faces, three alternating runs of
  the original and revised loader gave medians of 9.77 s and 7.33 s respectively. Standards
  detection including file reading took 2.55 s and 0.16 s. Measurements used `lade_alles`
  with warm filesystem caches and exclude painting the first frame.
- The STEP loader still reopens the path for text detection. Packed STEP and declarations after
  the raw scanner's 60 MB limit need the already decoded Part 21 text. Part 21 tokenization is
  the next measured loading bottleneck. QIF extensions remain last.

### Explicit simultaneous STEP tolerances and PMI comparison

- Checked PLAN §§8.1, 8.4 and 8.35 against docs/Roadmap.md. A modified FTC-07 fixture links three
  actual upper tolerance rows that reference #13915. The PMI context menu selects all three,
  crossing two explicit links. A link to a lower row with another basis appears separately.
  The original FTC-07 file carries only the printed wording and still has no such partners.
  See the [CAx-IF PMI guidance, section 6.9.9](https://www.mbx-if.org/home/wp-content/uploads/2024/06/rec_pracs_pmi_v41.pdf).
- Verified endpoint reversal, alternative link chains for the same group, STEP renumbering,
  changed partners, project reopen, remapping as an
  additional part, and a STEP copy after changing a tolerance value. Linked controls keep the
  PDF row finding open when the numbers match and the cross-row membership has not been reviewed.
- Reversing the order of FTC-07 PMI exposed two false deviations between #15607 and #15653.
  Both diameters now keep their distinct bounds and modifiers. On the local Mac the median of
  three in-memory comparisons of 980 repeated FTC-07 records fell from 506 to 22 ms. For 1,200
  same-size bores with separate face IDs it fell from 1,137 to 7 ms. The measurements cover
  semantic matching; file parsing, tessellation and display are separate operations.
- Verification: 310 affected tests passed. Another 47 passed with native macOS Qt, including
  context-menu selection. The translation check found all 2,610 keys.
- The next loading benchmark uses a 42,849,317-byte STEP with 2,400 solids and 14,400 faces.
  Profiling attributed 9.71 s to Part 21 parsing and 2.54 s to standards detection. These
  instrumented figures identify expensive stages; compare uninstrumented times for changes.
  Explicit multi-row membership on drawings is still open. QIF remains last.

### Scope notes on graphical composite frames

- Checked PLAN §§8.4, 8.18 and 8.28 against docs/Roadmap.md. The FTC-07 frame #15050 has a
  two-branch leader with two filled endpoints. Two lines of plotted lettering say “INNER AND
  OUTER WALL OF ENTIRE GROOVE”. The validation property #15064 drops the final three words.
  The reviewer sees its abbreviated wording alongside the complete graphical note. The numeric
  values agree and remain prefilled. Accepting uses the full graphical wording on both rows.
- #15098 has a single leader and the plotted note “SIM REQT”. The lettering is checked glyph
  by glyph, including spaces and complete lines. Both tolerances carry the complete note in
  GEOMETRIC_TOLERANCE.description. The model comparison includes that description. The text
  alone does not identify the membership of a simultaneous group of other controls.
- PLAN §8.35 also compares known scope wording on individual PDF rows. A two-sheet PDF
  with the same tolerance value and different groove-wall notes returns one equal and one
  changed finding. Both wordings survive CSV export. The NIST D2MI-904 description
  “Geometric tolerance for feature” is a general CAD label. It does not occur on the drawing.
  An unclassified model description remains unresolved in the drawing comparison.
- Verified all six frames in the same STEP export, including twelve tolerance rows and four
  reviewed datums. Original strokes and generated triangle-only versions both passed. For
  the two scope-bearing frames the triangle variant also passed with their planes removed,
  after saving and reopening the project. Open CASCADE's independent STEP entity reader
  returned the full descriptions on all four affected rows. The affected suite passed 263
  tests, the follow-up selection passed 142, and the combined native macOS run passed 24.
  All 2606 interface strings have English translations.
- For an explicit membership test, FTC-07 upper rows #14614 and #15076 reference the very same
  datum system #13915. The fixture has no explicit simultaneity link between them. A test copy
  can add one to verify the distinction between the text and explicit STEP membership.
  CAx-IF describes the legacy relationship name `simultaneity` and recommends against generating
  it. See [PMI Recommended Practices v4.1](https://www.mbx-if.org/home/wp-content/uploads/2024/06/rec_pracs_pmi_v41.pdf).
  Other lettering and explicit membership across controls remain open. QIF stays last.

### Semantic STEP composite frame relationships

- Checked PLAN §§8.1, 8.4 and 8.18 against docs/Roadmap.md. Imported composite tolerances
  retain the directed relationship between their rows. Hovering over the value in either PMI
  row identifies its linked rows by list number. Loading the model as an additional part
  remaps the referenced IDs together with the source tolerance.
- Compared the original FTC-07 file against copies with renumbered tolerances, a removed
  relationship, reversed roles and a different subordinate tolerance. The latter three cases
  report a relationship change with the individual numerical tolerances unchanged. Matching
  also covers repeated identical two-row frames reordered across revisions.
- Graphical-only #14498 has one symbol cell spanning two rows. Each row is separately editable
  and both are adopted together. Cancelling either row restores the original state. A conflict
  with the callout's own validation string clears both suggested tolerance values.
- Tested the FTC-07 position frame in four graphical-only versions: original strokes with and
  without validation text, and triangle-only variants with and without a writing plane. The project round trip
  retains the pair. STEP reimport confirms both diameters (1.524 and 0.381 mm), their A/B/C and A
  datums, the common shape aspect, directed link, original entities and MBD_B view membership.
  A missing datum on the second row causes both rows to be skipped. Removing either reviewed
  row restores one graphical callout. An additional mark outside the row cells prevents a proposal.
- Surface-profile pairs #14143 and #14636 were also checked from review to STEP reimport
  with strokes and triangle-only fills. Each bent leader terminates in a filled or hatched dot.
  The complete leader must account for the outside ink. The graphic of #15050 carries the
  note “INNER AND OUTER WALL OF ENTIRE GROOVE”, while #15098 adds “SIM REQT”. Both stay open.
  In #15064 the STEP validation string omits “OF ENTIRE GROOVE”. The full scope can only
  be recovered from the presentation or supplied explicitly during review.
- #14735 contains .06 and .02 inch position controls, both at maximum material against E/B/C.
  The E template comes from a separate datum callout. When a raster contact breaks within the
  circled M, both complete glyphs must still match within one normalised pixel. An empty outer
  ring or an altered inner letter stays open. Both stroke and triangle-only STEP round trips
  retained the modifiers on both rows. The remaining two FTC-07 composite controls have scope
  or simultaneity notes; preserve those when extending the review. QIF remains last.
- The full run passed 829 tests with eight display tests skipped. The affected run passed
  344 tests. On the final OCR code, 101 graphical STEP, composite, PRC and validation tests
  passed; a further filled-glyph regression verified both an empty and a damaged modifier.
  The native macOS run passed all 23 selected display and composite tests.

### Graphical diameter with detached target arc

- Checked PLAN §§8.4, 8.18 and 8.28 and docs/Roadmap.md. FTC-07 #15146 includes a separate
  30-vertex circular arc near the leader. Its fitted radius is about 6.3497 mm. The tip lies on
  that circle within 0.0001 mm and the shaft points along the radius. This describes the plot;
  the printed nominal diameter is read independently. The reader excludes this component only
  for a complete diameter or radius row and checks both arrow flanks.
- All twelve original FTC-07 “Linear Size” callouts were transcribed from the strokes alone.
  The graphic-only STEP round trips for #15146, #15669 and #15807 were repeated with original
  strokes and triangle-only fills. The .250-inch nominal and +.003/−.000-inch deviations from
  #15146 were reimported against the same two model faces. All original entities were retained.
  Straight, displaced, text-adjacent and additional marks, and an arrow missing its head, remain open.
  All 40 affected tests, 36 native macOS graphical STEP repair tests and 50 PRC/validation tests passed.
- Next §8.4: complex control frames still need their full row structure and semantic links.
  On FTC-07 #14498, the position symbol spans both rows. The upper value is diameter .060
  inch against A/B/C, the lower is diameter .015 against A. Original STEP links #14472 and
  #14483 with GEOMETRIC_TOLERANCE_RELATIONSHIP('composite',…) and associates both with this
  callout. Repaired composite export must preserve this order and relationship. QIF remains last.

### Unframed filled wide diameter dimensions

- Checked PLAN §§8.4, 8.18 and 8.28 against docs/Roadmap.md. Wide-font rows are now checked
  for filled meshes as well as strokes. The same rules require the complete dimension prefix,
  number and each stacked deviation. Conflicting font interpretations stay open.
- Converted three FTC-07 graphical callouts to triangle-only representations, with semantics and
  validation text removed. The review read three diameters of .875 ±.010 inch and four of .281
  with +.006/−.001 inch. Reimport confirmed the millimetre values, reference faces, original STEP
  entities and text including the quantity. A dimension with a detached mark stayed unread.
  All 38 affected tests, 34 native macOS repair tests and 67 drawing/validation tests passed.
- On FTC-07 #15146 the detached mark is a 30-vertex curve close to the leader tip, away from
  the printed text. Any change that excludes it should verify its attachment or purpose and
  preserve free-standing suffixes. Other fonts and compound frames are open. QIF is last.

### Filled frames without a STEP annotation plane

- Checked PLAN §§8.4, 8.18 and 8.28 against docs/Roadmap.md. Filled frames now recover
  writing axes from mesh boundaries. Shared triangle diagonals are excluded even when
  the same point has separate indices. All readable orientations must give the same control.
- Removed the annotation planes as well as all semantic PMI and validation strings from the
  triangle-only FTC-07 test. Both complete position controls were confirmed, exported and
  reimported with their original graphics, faces, datums, material or projected height.
  A compound frame remains open. An arbitrarily rotated triangle mesh is also checked
  against the projected frame, with a nonplanar variant as a negative control. All 37 affected
  tests and the three native macOS frame round trips passed.
- Next §8.4 work includes compound frames and unframed wide filled dimension strings.
  QIF remains last.

### Complete stroke and triangle-only tolerance frames

- Checked PLAN §§8.4, 8.18 and 8.28 and docs/Roadmap.md. Single-row wide CAD frames are
  decoded as one font family. A circled P and a circled M must match the interior lettering.
  Entirely filled graphics can supply the cell borders from closed rectangular spaces in the
  annotation plane. No edges or text entities are required.
- Removed semantics and validation strings from the FTC-07 STEP reference. The review read
  the projected position as diameter .020 inch and height .425 inch against A/B, and the other
  position as diameter .040 inch at maximum material against A/B/C. Tested both the original
  strokes and a separately triangulated version of both frames with zero line geometry.
  Reopening each exported STEP confirmed the original entities, ordered datums, target faces,
  material modifier and reviewed projection end face. A composite position frame stayed open.
  All 37 affected tests, 37 native repair/projection tests and 103 drawing, validation and PRC
  tests passed. All 2592 interface strings have English translations.
- Further §8.4 work includes triangle-only frames that lack a stored writing plane, additional
  fonts and multi-row control frames. QIF remains the final implementation phase.

### Wide CAD stroke dimensions and conflicting presentation values

- Checked PLAN §§8.4, 8.18, 8.28 and docs/Roadmap.md. A separate set of wide stroke glyphs
  is applied to an entire dimension row, including its quantity and upper/lower deviations.
  Original connected white regions distinguish open digits from 0/4/6/8/9. Ordinary and wide
  interpretations must agree if both are legible. Filled glyphs keep their existing classifier.
- From the vectors alone, FTC-07 yielded eleven of its twelve “Linear Size” callouts. Five
  callouts other than those used for templates exercised symmetric and stacked deviations,
  including four times diameter .250 with +.003/−.001. One annotation with a detached mark
  still needs review. No file text or semantic data is required to read these rows.
- On #15405 the actual lower deviation is plotted as −.001 inch; validation text #15416 gives
  −.000. The review leaves the numeric fields empty, displays both sources and permits explicit
  selection or entry. “R.022-.012” retains its printed hyphen until the reviewer chooses its
  interpretation. Three graphical-only STEP round trips (with and without validation strings)
  preserved all the source entities and verified both choices for the lower deviation. The radius
  round trip retained limits of 0.3048 and 0.5588 mm on the reference faces. All 37 affected
  tests, 29 native macOS repair tests and 75 drawing/validation regressions passed. All 2592 UI
  strings have English translations.
- Next §8.4: extend the same independent stroke reading to FTC-07's complete control frames.
  #14558 and #14795 contain a position symbol, a diameter zone with maximum material and A/B/C.
  The frame and many first symbols are already isolated correctly, while the value and datum
  cells need glyphs for circled modifiers and the wide datum letters. #13999 includes a projected
  height. Check the source cells and export without the validation property. QIF remains last.

### Graphical STEP validation text in semantic review

- Checked PLAN §§8.4, 8.18, 8.28 and the implementation order against docs/Roadmap.md. The review
  reads a callout's “equivalent unicode string” on demand. It follows the exact graphical owner,
  its draughting model (direct or through its annotation plane), property and representation.
  Native positioned text still takes precedence. With a validation text the original plot remains
  visible and the dialog labels the source. Repeated identical strings agree. Different strings
  and unsupported qualifiers remain available for manual review.
- For a feature control frame with an empty first text cell, check an isolated plotted row for
  a recognised symbol with the correct cell count. A specific callout name can supply the type.
  The dialog explains which source supplied the symbol. A contradiction prevents the suggestion.
  On FTC-07 the review read five datum names, eleven dimensions and twelve single tolerance frames;
  six of the twelve supplied their symbol directly from the plotted geometry.
- In a derivative of FTC-07 stripped of all semantic characteristics, the actual dialog confirmed
  A/B/C, a position tolerance with maximum material, and two repeated diameters. One has stacked
  signed deviations. The other shows .438 inch versus the original semantic .4375. Reloading the
  saved STEP verified the printed 11.1252 mm, target faces, material, ordered datums, deviations
  and all original source entities. All 49 affected tests, 39 native dialog/STEP tests and 61
  drawing regression tests passed. All 2585 UI texts have English translations. Whole-drawing
  equivalence and general composite tolerances remain open. QIF stays last.
- Next §8.4: make wide CAD stroke digits legible without validation metadata. On original
  FTC-07 callout #16200 the leader component detaches cleanly, leaving ten glyphs. Its zeros
  and twos are wider than the existing templates. A local probe using measured glyphs read
  “R.022-.012” from the strokes alone. Other FTC-07 diameter rows still required more work.
  Cross-check other callouts and fonts before adding templates. The hyphen between two values
  can indicate different conventions; keep that interpretation visible to the reviewer.

### Inch and mixed-unit STEP presentation contexts

- Checked PLAN §§8.18, 8.25 and 8.28 against docs/Roadmap.md. The STEP presentation reader now
  uses the length unit assigned to the defining draughting model. Without a definition link it
  checks direct view and annotation-plane membership. Saved cameras use each view's own unit.
  Mixed contexts can still draw the geometry using the fallback scale, but an ambiguous unit
  does not supply a numeric length from unqualified printed text. Explicit text units still apply.
- Original NIST FTC-07 callout #16200 now has plane x = −91.44 mm and text factor 25.4. Its saved
  camera MBD_A has width 444.13419428 mm, as specified by a 17.4855982 inch planar box. A second
  fixture exercises mm and inch views in one file, the same literal in both, ambiguous membership
  and a defining link whose unit differs from a view that also shows the callout. All 153 affected
  tests and 34 native macOS tests passed, including the 3D screen checks.
- Next §8.18 evidence: FTC-07 has 102 “equivalent unicode string” records on graphical callouts
  and semantic characteristics. For example #15635 describes the graphical callout #15623 through
  CHARACTERIZED_ITEM_WITHIN_REPRESENTATION, whereas #15614 describes the semantic DIMENSIONAL_SIZE.
  When using such file text in review, follow the callout-specific property through its actual
  references, retain quantities and rich-text fields, keep unsupported syntax open and distinguish
  the source text from OCR. The verified property for #15623 reads “3X ⌀.875±.020” and parses
  to 22.225 ±0.508 mm. Callout #13706 has datum A. A local parsing probe recovered five datum
  names and eleven dimensions, including stacked signed deviations. The 21 graphical frame
  descriptions did not pass the strict complete-cell check. #16212 contains “R.022-.012” with
  an ambiguous hyphen.
  Whole-drawing equivalence is still open. QIF remains last.

### Graphical radius lettering and repeated radius dimensions

- Checked PLAN §§8.18, 8.35–8.37 and docs/Roadmap.md. Single strokes and filled letters use
  R glyphs from NIST FTC-07. Two graphical-only STEP derivatives exercise review, face selection,
  export and reload for an unnamed R2. Every source entity survives in both cases.
- Drawing comparison reads free R and CR rows on leaders. A repeated radius requires the correct
  model characteristic and coverage of all selected walls. A filled “2X CR2” versus a plain model
  radius reports a changed modifier. “2X B2” produces no radius finding. Existing datum frames
  still read B. Unsupported or ambiguous lettering can still require review, including the zero
  in one independently plotted “R2 ±0.1”. All 118 affected tests, 91 native macOS tests and
  the check of 2581 translations passed.
- Next, fix a verified presentation scale defect on the original FTC-07 STEP. The local
  draughting model #13679 references context #8 in inches. Loading reports text factor 1 and
  annotation plane x = −3.6 instead of −91.44 mm. Inspect the assigned representation context
  for graphics and saved views. Mixed-unit files need per-representation handling. QIF remains last.

### Inclined graphical diameter rows attached to drawing leaders

- Checked PLAN §§8.35–8.37 against docs/Roadmap.md. Selecting a hole pattern now follows free
  leader segments at arbitrary angles. A PDFium transformation renders just the strip alongside
  the text-side endpoint into reading orientation. Select the longest complete row over six strip
  heights and check it in both directions at three resolutions. Unknown suffixes and unfinished
  branches leave the finding open. Each detected row retains its original leader endpoint.
- The sheet highlights the oriented text footprint. The detail renders the original row upright
  and CSV carries its four sheet corners and the text-side leader endpoints. Repeating registration
  preserves reviewed text and manually removed findings. Tested 28°, −38° and 147° with the
  original D2MI raster “4X⌀.215-.225”, reversed text direction and PDF page rotations. Each
  accepted finding kept both limits and pointed to the intended model wall. Negative cases used
  an additional symbol and an open branch. On original D2MI 904 sheet 3, a local run over
  all 1664 line segments took 96 ms to find three candidate ends and 54 ms to read their strips.
  All 73 affected tests and 64 native macOS comparison tests passed. All 2581 UI strings translate.
- For the next §8.35 item, an isolated PDF probe drew “R2”, “2X R2” and “R2 ±0.1” as filled
  vector paths at 27°. The OCR confused the R with B or left the row unread. Neither the CAD
  glyph table nor the stroke-letter set contains R. Radius callouts require validated glyphs
  for both stroke and filled forms, an explicit radius type when comparing repeated features,
  and tests that preserve datum B. Section geometry and whole-drawing equivalence remain open.
  QIF stays last.

### Oblique orthographic hole views in drawing comparison

- Checked PLAN §§8.35–8.37 and docs/Roadmap.md. File → Compare PMI with 2D drawing can register
  complete vector ellipses in a hole pattern. It uses both semi-axes, the major-axis direction
  and the axial station of each complete circular STEP boundary. Scale, rotation, tilt sign
  and reflection must explain the entire selected oblique pattern. Shape ambiguity stays open.
  Where the same through-bore wall is visible at both ends, an otherwise unambiguous quantity
  dimension counts that bore once. Both existing axial-view matching and the reconstruction
  dialogs retain their circular-rim behaviour.
- Two generated PDF tests exercised fitted annular paths, same-size competing bores, a bent
  leader, clicks on the minor-axis rim and CSV export. The second drawing reflected the pattern
  and put the rims at different depths. The arrow selected the correct model PMI with the
  changed nominal. Tests also covered coaxial openings at distinct depths, coincident candidate
  walls, symmetric groups, inconsistent tilts, broken paths and projecting both rims of each bore.
  The original NIST D2MI 904 sheet 1 and STEP file registered eight ellipses at four centres.
  The four outer rims matched diameter #103256 (5.461 to 5.715 mm), with pairwise ambiguity
  between individual bore walls.
- In a seeded local experiment 120 six-hole patterns with varied depths, random rotations
  and perturbed drawing data recovered all six intended faces. For a dense synthetic model with
  320 equal-diameter holes (640 rims), vectorising the pose checks reduced one local run from
  9.5 to 1.8 s; one of eight selected rims remained ambiguous. This measures geometry matching
  only. All 58 affected tests and all 59 native comparison tests passed. The eight native
  macOS screen tests also passed. All 2579 UI strings have English entries.
- Next in §8.35, a PDF probe followed a sloping leader baseline and sampled an inclined
  copy of the real D2MI graphical callout at three resolutions. It recovered the entire
  “4X⌀.215-.225” row at 28°, −38° and 147°. At 147° a short strip reproducibly omitted
  the upper limit. Production discovery therefore needs the whole printed row, both reading
  directions, retained sheet coordinates and reconnection to the exact leader after review.
  Partial rims, section geometry, composite controls and whole-drawing equivalence remain open.
  QIF remains the final implementation item.

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
