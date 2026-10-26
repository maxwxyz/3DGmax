# UI/UX principles for 3DGmax

Target users: designers, engineering team leads, assembly, metrology lab, quality, production – frequent and
occasional users, younger and older. Guiding idea: **calm and clear like ZGmax, yet powerful** ("easy to start,
deep when needed").

## What other applications show (research)
- **Kisters 3DViewStation:** PMI views from the CAD file, revision comparison with colored PMI changes; usable
  without CAD knowledge ([Kisters MBD/PMI](https://viewer.kisters.de/en/im-looking-for/mbd-pmi-visualization.html)).
- **Capvidia (browser-based MBD for suppliers):** zoom, section and **PMI filters** as the core of shop-floor use,
  also on tablet/kiosk; **jump from the characteristic in the list to the annotation on the model**
  ([Business Wire 2025](https://www.businesswire.com/news/home/20250818272813/en/Capvidia-brings-MBD-for-Suppliers-with-browser-based-3D-human-viewable-models-linked-to-QIFSTEP)).
- **Creo View (Design Check, View State Compare):** **tag/check** annotations and geometry with inspector, time,
  history; comparison highlights annotation changes.
- **Onshape (MBD):** the shop floor needs the current annotated model **without a CAD license** and **filters the
  data it needs** instead of static views ([Onshape blog](https://www.onshape.com/es/blog/model-based-definition-mbd-cloud-cad-fixes-broken-promise)).
- **CATIA Compare Products:** visual (fast) and geometric (accurate) comparison, result as added/removed with
  adjustable accuracy; xCompare also shows dimension/tolerance changes
  ([Technia](https://www.technia.com/?p=4393), [pycatia PartComps](https://pycatia.readthedocs.io/en/latest/api/pycatia/smt_interfaces/part_comps.html)).

## Principles (apply to every new feature)
1. **One main task per screen.** Start page: open/compare. Then the model in the center; panels only when needed.
2. **Everything labeled, no puzzle icons.** Text in the toolbar, tooltips with short explanation and shortcut.
3. **Navigation always works** – also while measuring or reviewing; Esc ends every tool.
4. **List ↔ model always linked:** a click in a list highlights in the model and vice versa; zoom to selection (Z)
   and align normal (N) work for everything selected.
5. **Guided workflows for occasional users:** "Start review" steps through, ◀ ▶ browses views/changes, clear
   counters ("3 of 12 open").
6. **Readable for all ages:** contrast in light and dark, PMI color automatically high-contrast, sufficient font size;
   never encode by color alone (status also as text).
7. **No dead buttons:** what is not possible right now is greyed out and the tooltip says why.
8. **Advanced features reachable but not in the way:** context menus, shortcuts, settings dialog.
9. **Shop-floor ready:** large click targets, mouse, trackpad and later touch; views and characteristics findable
   without CAD knowledge.
10. **Honest results:** show deviations, uncertainties and limits openly (e.g. "graphical only").

## Open UI tasks from the research
- Thumbnails in the view list; touch gestures; simplified "shop-floor mode" toolbar.
- Bill of characteristics with balloon numbers for metrology and quality.
- Tag/check individual PMI (like Design Check) also outside a comparison.
- Usability test with real users (2–3 people per target group, typical tasks, time/errors).
