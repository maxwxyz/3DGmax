# 3DGmax – Roadmap (Stand 2026-10-26)

✅ umgesetzt · 🟡 teilweise · ⬜ geplant · 💡 Idee/später (Umfang klären)

## Ansehen
| Funktion | Stand |
|---|---|
| STEP AP242/AP214/AP203 laden (Hintergrund, Abbrechen, Drag-and-drop, Zuletzt verwendet) | ✅ |
| Baugruppenbaum: ein-/ausblenden, isolieren, transparent, Hilfsgeometrie | ✅ |
| Navigation CATIA (Standard) und klassisch, Trackpad, Standardansichten, Drehpunkt/Bildmitte | ✅ |
| Darstellung schattiert/mit Kanten/Draht, hell/dunkel, eigene Hintergrundfarben | ✅ |
| Gespeicherte Ansichten: Kamera, Ausschnitt, PMI je Ansicht, durchklicken (◀ ▶), Suche | ✅ |
| Vorschaubilder je Ansicht in der Liste | ⬜ |
| Schnitt X/Y/Z, an gewählter Fläche/Kante, aus Blickrichtung, Regler | ✅ |
| Mehrere Schnittebenen, Clipping-Box, Schnittansichten aus dem Modell, Schnittkontur als Ansicht | ⬜ |
| 3D-Auswahl Flächen/Kanten (mehrfach), Kontextmenü, auf Auswahl zoomen, normal ausrichten | ✅ |
| Große Baugruppen: Tessellierungs-Cache, Detailstufen | ⬜ |

## PMI
| Funktion | Stand |
|---|---|
| Semantische PMI: Maße, Form-/Lagetoleranzen, Bezüge, Bezugsstellen, Hinweise | ✅ |
| Grafische PMI aus der Datei, Platzhaltertexte aus der Semantik | ✅ |
| PMI ↔ Fläche in beide Richtungen, Bezüge/Toleranzen mit Bezug wählen | ✅ |
| Liste mit Name, Ansichten, Suche, Filter, Kontextmenü; Anzahl in aktueller Ansicht | ✅ |
| PMI-Farbe kontrastreich / aus Datei / eigene | ✅ |
| PMI-Export CSV (Werte, Bezüge, Flächen-IDs, Ansichten) | ✅ |
| Plausibilitätsprüfung (unbenutzte/fehlende Bezüge, ohne Fläche/Ansicht, Doppelte, Regeln) | ✅ |
| Gezielte Suche (`bezug:A`, `wert:0.5`, `typ:position`) | ⬜ |
| Oberflächenangaben (Rauheit), Schweißzeichen | ⬜ |
| Grafische PMI durchsuchbar machen (Texterkennung/OCR auf gerenderten Annotationen) | 💡 |
| Grafische PMI in semantische PMI umwandeln (Text + Rahmenstruktur auswerten) | 💡 |
| Toleranzzonen darstellen: Hüllflächen für Rundheit, Koaxialität, Profil, Position … inkl. Bezüge, unsymmetrische Zonen | 💡 |
| FMK (Umfang mit Nutzer klären: Funktionsmaßkonzept/Messkonzept) | 💡 |

## Messen
| Funktion | Stand |
|---|---|
| Abstand, Winkel, Radius/Ø, Wandstärke, Koordinaten; Fang; Liste, CSV, Kopieren | ✅ |
| Messung als Ansicht speichern, Messungen im Bericht | ⬜ |

## Vergleich
| Funktion | Stand |
|---|---|
| Ausrichten: gleiche Lage, Bestpassung (ICP), drei Punktpaare (Kern) | 🟡 (Punktpaare ohne Oberfläche) |
| Geometrie: gleich/geändert/neu/entfernt je Fläche, exakt (B-Rep) mit Netz-Vorauswahl | ✅ |
| Semantischer PMI-Vergleich (Feld für Feld, Bezüge, Flächen), „Geometrie unter PMI geändert“ | ✅ |
| Änderungsliste, Prüfrundgang, Kommentar, Prüfprotokoll mit SHA-256 | ✅ |
| Änderungen exportieren (CSV) | ✅ |
| Abweichungsfarbkarte (Punkt- bzw. Netzfärbung mit Skala, Toleranzgrenze, Vorzeichen) | ⬜ |
| Anzeige wie CATIA „Compare Products“: hinzugefügt/entfernt als Volumen, visuell (schnell) und genau | ⬜ |
| Verschobene Elemente erkennen (Feature/Fläche starr versetzt), PMI verschoben (Platzierung) | ⬜ |
| Grafischer PMI-Vergleich (Annotation verschoben, geändert, neu, entfernt) | ⬜ |
| Baugruppen vergleichen (Teile zuordnen, Lageänderungen) | ⬜ |
| Mesh: STL/OBJ gegen CAD, Mesh gegen Mesh, 3D-Scan einpassen (Bestpassung, RPS/Bezüge) und vergleichen | ⬜ |

## Berichte und Austausch
| Funktion | Stand |
|---|---|
| PDF: je gespeicherter Ansicht eine Seite mit Ansichtsname, Modellname, PMI | ⬜ |
| PDF-Vergleichsbericht (Übersicht, Änderungsliste, Bild je Änderung) | ⬜ |
| PMI-Änderungstabelle PDF für Lieferanten/Fertigung | ⬜ |
| Projektdatei (ZIP mit Modellen, Prüfstatus, Kommentaren) | ⬜ |
| Ordnervergleich | ⬜ |
| Ansichten als Zeichnung (HLR) exportieren (PDF/SVG/DXF) | ⬜ |
| Annotieren: Kommentare/Änderungsvorschläge an Flächen, PMI (Liste und Modell), geänderter Geometrie | ⬜ |

## Formate
| Format | Stand |
|---|---|
| STEP AP242/AP214/AP203 | ✅ |
| QIF | ⬜ |
| IGES, STL, OBJ, glTF/GLB, 3MF | ⬜ (Leser vorhanden bzw. klein) |
| JT über TKJT (GPL v2+), Bau mit/ohne TKJT | ⬜ (Schritt 7) |
| 3D-PDF (U3D/PRC) | ⬜ (Beispieldateien fehlen) |

## Betrieb
| Funktion | Stand |
|---|---|
| Deutsch/Englisch, Anleitung F1 mit automatischer Menüreferenz, Einführung, Was ist neu | ✅ |
| Portable Apps Windows/macOS/Linux, GitHub-Workflow mit/ohne Tests, Selbsttest | 🟡 (macOS lokal geprüft, GitHub blockiert durch Abrechnung) |
| Release-Skript: Version erhöhen, Changelog DE/EN mitführen | ✅ |
| Tests: Kern, Oberfläche offscreen, Stresstest, Bildschirmtest | ✅ |
