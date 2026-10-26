# UI/UX-Grundsätze für 3DGmax (Stand 2026-10-26)

Zielgruppen: Konstrukteure, SE-/BE-Teamleiter, Montage, Messraum, Qualität, Produktion – erfahren und gelegentlich,
jünger und älter. Leitbild: **ruhig und übersichtlich wie ZGmax, aber leistungsfähig** („einfach anfangen, tief
gehen können“).

## Was andere Programme vormachen (Recherche)
- **Kisters 3DViewStation:** PMI-Ansichten aus der CAD-Datei, Revisionsvergleich mit eingefärbten PMI-Änderungen;
  ausdrücklich ohne CAD-Kenntnisse bedienbar ([Kisters MBD/PMI](https://viewer.kisters.de/en/im-looking-for/mbd-pmi-visualization.html)).
- **Capvidia (MBD für Lieferanten, browserbasiert):** Zoom, Schnitt und **PMI-Filter** als Kern der Werkstatt-
  Bedienung, auch auf Tablet/Kiosk; **Sprung vom Merkmal in der Liste zur Annotation am Modell**
  ([Business Wire 2025](https://www.businesswire.com/news/home/20250818272813/en/Capvidia-brings-MBD-for-Suppliers-with-browser-based-3D-human-viewable-models-linked-to-QIFSTEP)).
- **Creo View (Design Check, View State Compare):** Annotationen und Geometrie **markieren/abhaken** mit Prüfer, Zeit,
  Historie; Vergleich hebt Annotationsänderungen hervor.
- **Onshape (MBD):** Werkstatt braucht das aktuelle annotierte Modell **ohne CAD-Lizenz** und **filtert sich die
  benötigten Daten selbst** statt starrer Ansichten ([Onshape Blog](https://www.onshape.com/es/blog/model-based-definition-mbd-cloud-cad-fixes-broken-promise)).
- **CATIA Compare Products:** visueller (schneller) und geometrischer (genauer) Vergleich, Ergebnis als
  hinzugefügt/entfernt mit einstellbarer Genauigkeit; xCompare zeigt zusätzlich Maß-/Toleranzänderungen
  ([Technia](https://www.technia.com/?p=4393), [pycatia PartComps](https://pycatia.readthedocs.io/en/latest/api/pycatia/smt_interfaces/part_comps.html)).

## Grundsätze (gelten für jede neue Funktion)
1. **Eine Hauptaufgabe je Bildschirm.** Startseite: öffnen/vergleichen. Danach Modell im Mittelpunkt, Leisten nur
   bei Bedarf (Messen, Änderungen erscheinen, wenn benutzt).
2. **Alles beschriftet, keine Rätselsymbole.** Text in der Werkzeugleiste, Tooltips mit Kurzerklärung und Taste.
3. **Navigation geht immer** – auch im Mess- oder Prüfmodus; Esc beendet jedes Werkzeug.
4. **Liste ↔ Modell immer verbunden:** Klick in einer Liste hebt im Modell hervor und umgekehrt; „Auf Auswahl
   zoomen“ (Z) und „Normal ausrichten“ (N) funktionieren für alles Gewählte.
5. **Geführte Abläufe für Gelegenheitsnutzer:** „Prüfen starten“ führt Schritt für Schritt, ◀ ▶ blättert
   Ansichten/Änderungen, klare Zählerstände („3 von 12 offen“).
6. **Gut lesbar für alle Altersgruppen:** Kontrast hell/dunkel, PMI-Farbe automatisch kontrastreich, ausreichend
   große Schrift; nichts nur über Farbe kodieren (Status zusätzlich als Text).
7. **Keine toten Knöpfe:** Was gerade nicht geht, ist ausgegraut und sagt im Tooltip warum.
8. **Fortgeschrittenes erreichbar, aber nicht im Weg:** Rechtsklick-Menüs, Tastenkürzel, Einstellungen-Dialog.
9. **Werkstatt-tauglich (Montage, Produktion):** große Klickflächen, Bedienung mit Maus, Trackpad und später Touch;
   Ansichten und Merkmale ohne CAD-Wissen auffindbar.
10. **Ehrliche Ergebnisse:** Abweichungen, Unsicherheiten und Grenzen offen anzeigen (z. B. „nur grafisch“).

## Offene UI-Aufgaben aus der Recherche
- Vorschaubilder in der Ansichtsliste; Touch-Gesten; „Modus für die Werkstatt“ (vereinfachte Leiste).
- Merkmalsliste (Bill of Characteristics) mit Ballon-Nummern für Messraum/Qualität.
- Markieren/Abhaken einzelner PMI (wie Design Check) auch ohne Vergleich.
- Gebrauchstauglichkeit mit echten Nutzern prüfen (je Zielgruppe 2–3 Personen, typische Aufgaben, Zeit/Fehler).
