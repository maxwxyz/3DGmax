# 3DGmax – Plan (Stand 2026-10-25)

3D-PMI-Viewer und -Vergleich für Model Based Definition. Dieses Dokument ist der Plan vor dem ersten Code: Marktüberblick,
Technikentscheidung (mit dem, was noch per Versuch zu beweisen ist), Architektur, Schritte mit Abnahmekriterien, Risiken.

Kennzeichnung: **[geprüft]** = selbst nachgesehen (Paketindex, Herstellerseite), **[Wissen]** = aus meinem Fachwissen,
noch nicht mit einem Versuch bestätigt, **[offen]** = muss in Schritt 1 per Versuch geklärt werden.

---

## 1. Ähnliche Programme (Recherche)

| Programm | Was es kann | Bezug zu uns |
|---|---|---|
| **Kisters 3DViewStation** (kommerziell) | Liest PMI aus CATIA, Creo, NX, JT, STEP; gespeicherte PMI-Ansichten; **seit v2024.0 Revisionsvergleich mit PMI-Änderungen (eingefärbt)**, schnell und exakt [geprüft] | Nächster Wettbewerber, Funktionsumfang ähnlich unserem Ziel. Messlatte für Bedienung. |
| **Kubotek K-Compare** (kommerziell) | Revisionsvergleich von Teilen/Baugruppen, Ergebnisbaum mit Flächen-Hervorhebung, liest AP242-PMI [geprüft]; semantischer PMI-Diff nicht eindeutig belegt | Vorbild für Ergebnisbaum und Flächen-Einfärbung. |
| **CoreTechnologie 3D_Evolution** (kommerziell) | Konvertiert und **vergleicht PMI Original ↔ Konvertat**, prüft ob PMI semantisch (auswertbar) oder nur grafisch ist [geprüft] | Vergleich Original/Konvertat statt zwei Stände; die Prüfung „semantisch oder nur Grafik“ übernehmen wir als Hinweis je PMI. |
| **TransMagic MagicCheck** (kommerziell) | Geometrievergleich mit Farbkarte nach Toleranz, Punktliste mit Zahlenwerten [geprüft, Quellen 2012/13] | Vorbild für Abweichungsfarbkarte + Punktbrowser. |
| **Capvidia MBDVidia / CompareVidia** (kommerziell) | MBD-Prüfung, QIF-Erzeugung, Modellvergleich [Wissen, nicht bestätigt] | Referenz für QIF-Weg. |
| **NIST STEP File Analyzer and Viewer** (frei, öffentlich) | Zeigt grafische PMI, analysiert **semantische PMI** gegen die CAx-IF-Empfehlungen, Tabelle aller Entitäten [geprüft] | **Unser Prüfmaßstab**: Was wir aus den NIST-Modellen lesen, gleichen wir mit dessen Bericht ab. |
| **ODA Open STEP Viewer** (frei, nicht quelloffen) | AP242 ed.3, Messen, Kollision, PMI-Anzeige [geprüft] | Gegenprobe bei Darstellungsfragen. |
| **Siemens JT2Go** (frei) | JT mit PMI ansehen [Wissen]; Vergleich nur in der kostenpflichtigen Teamcenter-Visualisierung | Gegenprobe für JT. |
| **Open Cascade CAD Assistant** (frei) | OCCT-basierter Viewer für STEP/IGES/glTF u. a. [Wissen] | Zeigt, was OCCT in der Praxis leistet. |

**Fazit Markt:** Freie Viewer zeigen PMI, aber **keiner vergleicht zwei Stände semantisch** und führt durch eine
Prüfung mit Protokoll. Kommerziell kann das im Wesentlichen nur 3DViewStation. Der Mehrwert von 3DGmax liegt genau dort:
semantischer PMI-Vergleich + Prüfrundgang + Bericht, wie ZGmax für 2D.

## 2. Technikentscheidung

### 2.1 Sprache und Oberfläche – bestätigt
**Python 3.14 + PySide6** wie ZGmax. Gründe: gleiche Werkzeugkette (Tests offscreen, PyInstaller, `tr()`, HANDOFF),
Teile übertragbar (Prüfrundgang, Protokoll mit SHA-256, Changelog/Version, Anleitung mit Menüreferenz, Container).

### 2.2 Geometriekern – **pythonocc-core über pixi** (nach Versuch in Schritt 1 geändert, siehe docs/Machbarkeit.md)

Ursprünglicher Vorschlag (verworfen):
- **OCCT 8.0.1** ist aktuell. `cadquery-ocp` 8.0.1.1.0 gibt es als **pip-Wheel für Python 3.14 auf macOS (arm64/x86),
  Windows und Linux**, je ca. 50–70 MB [geprüft]. Damit passt es in eine normale `.venv` wie bei ZGmax.
- `pythonocc-core` 8.0.1.2 gibt es nur über conda-forge [geprüft] → zusätzliche Umgebung (pixi/conda), PyInstaller
  aufwendiger. Vorteil wäre nur der fertige Qt-Viewer, den wir selbst in ca. 200 Zeilen bauen.
- Variante `cadquery-ocp-novtk` ohne VTK [geprüft] → kleinere App, wenn wir den OCCT-Viewer nehmen (s. u.).
- Lizenzen: OCCT LGPL 2.1 mit Ausnahme, OCP Apache 2.0, PySide6 LGPL 3, numpy/scipy BSD – alles dynamisch gebunden,
  im Über-Fenster aufführen.

### 2.3 Was OCCT für PMI liefert [Wissen → in Schritt 1 beweisen]
- `STEPCAFControl_Reader` mit `SetGDTMode`, `SetViewMode`, `SetNameMode`, `SetColorMode`, `SetLayerMode` liest
  in ein XCAF-Dokument:
  - **Semantische PMI** über `XCAFDoc_DimTolTool`: Maße (`XCAFDoc_Dimension` → `XCAFDimTolObjects_DimensionObject`:
    Typ, Nennwert, Ober-/Unterabmaß, Passungsklasse, Modifikatoren), Form- und Lagetoleranzen
    (`XCAFDoc_GeomTolerance`: Typ, Wert, Zone, Modifikatoren, Bezugssystem), Bezüge (`XCAFDoc_Datum`) und die
    **zugeordneten Flächen/Kanten** (Verweise auf Teilformen).
  - **Grafische PMI** (Polylinien/Text der Annotation) als Präsentationsform je Objekt.
  - **Gespeicherte Ansichten** über `XCAFDoc_ViewTool` (Kamera, Schnittebenen, verknüpfte PMI und Formen).
- Bekannte Lücke aus dem OCCT-Forum: bei manchen Creo-Exporten kamen Maße mit Wert 0 an [geprüft, Forum]. Deshalb
  braucht es einen **eigenen Ergänzungsleser**: Wo OCCT nichts liefert, lesen wir die STEP-Entitäten direkt
  (`Interface_EntityIterator`/`StepData` aus OCCT oder ein schlanker Textparser der Part-21-Datei) und gleichen gegen
  den NIST-Analyzer ab.
- Oberflächenangaben (Rauheit) und Hinweistexte: in AP242 möglich, in XCAF nur teilweise abgebildet → [offen].

### 2.4 Darstellung – **OCCT-Viewer (AIS/V3d) im Qt-Widget**, nicht VTK
| Kriterium | OCCT AIS/V3d | VTK |
|---|---|---|
| Picking Fläche/Kante/Ecke der B-Rep | eingebaut (`AIS_Shape` Auswahlmodi) | nur Dreiecke → Rückabbildung selbst bauen |
| PMI-Darstellung | `PrsDim`/XCAF-Präsentation direkt | alles selbst zeichnen |
| Schnittebenen mit Kappen | `Graphic3d_ClipPlane` mit Capping | vorhanden |
| Fang (Kante, Mitte, Fläche) | über Teilformen exakt | nur Netz |
| Paketgröße | ohne VTK kleiner | +100 MB |
| Qt-Einbindung | über `winId()` + `Cocoa_Window`/`WNT_Window`/`Xw_Window`, wie CQ-editor [Wissen] | `QVTKRenderWindowInteractor` fertig |

Risiko: Einbindung auf macOS (Retina, Metal/OpenGL-Kontext) und offscreen-Tests → Schritt 1 enthält einen Mini-Versuch
„Würfel im Qt-Fenster anzeigen und anklicken“. Fallback: Offscreen-Rendering von OCCT in ein QImage (langsamer).

### 2.5 Weitere Bibliotheken
numpy, scipy (KD-Baum, Bestpassung/ICP, Zuordnung per Hungarian), lxml (QIF), reportlab oder QPdfWriter (Berichte –
wie in ZGmax), pypdf (3D-Streams aus PDF, BSD; PyMuPDF wäre AGPL), pytest + pytest-qt.

## 3. Formate – Machbarkeit und Aufwand

| Format | Weg | Geometrie | PMI | Aufwand | Kosten |
|---|---|---|---|---|---|
| STEP AP242 / AP214 / AP203 | OCCT STEPCAFControl | ja | semantisch + grafisch (zu prüfen) | Kern | 0 € |
| IGES, STL, OBJ, glTF/GLB | OCCT (IGESCAFControl, RWStl, RWObj, RWGltf) | ja | – | klein | 0 € |
| 3MF | eigener Leser (ZIP + XML) oder lib3mf (BSD) | Netz | – | klein | 0 € |
| **QIF** | lxml + Klassen aus den offiziellen XSD (qifstandards.org, QualityInformationFramework auf GitHub) | QIF-eigene B-Rep oder Verweis auf STEP | **semantisch, sehr sauber** (Characteristics, Datums, Messwerte) | mittel | 0 € |
| **JT** – Netz | eigener Leser nach ISO 14306 (LSG, Tri-Strip, zlib/LZMA) | Netz | – | groß (Wochen), Versionen 8–10 | 0 € |
| **JT** – TKJT (wie FreeCAD) | TKJT von Open Cascade (2013–2015), gepflegt in github.com/mmaenz/TKJT (OCCT 7.7, Mac kompiliert, ungetestet); Python-Anbindung selbst bauen (pybind11) | Netz, Baugruppe, Attribute; PMI-Teil vorhanden (`JtElement_MetaData_PMIManager`), Umfang offen | [offen] | mittel–groß (OCCT-8-Anpassung, 3 Plattformen) | 0 €, aber **GPL v2+** [geprüft, Kopf der Quelldateien] |
| **JT** – mit PMI | Siemens JT Open Toolkit (Mitgliedschaft, kein Listenpreis), Open Cascade JT SDK (kommerziell, Angebot), CAD Exchanger SDK (nur Angebot; ältere Liste 6.000–100.000 $/Jahr laut Wettbewerber), HOOPS Exchange (Angebot) | ja | ja | mittel (C++-Anbindung) | **4- bis 5-stellig pro Jahr** |
| **3D-PDF U3D** | 3D-Stream mit pypdf herauslösen, U3D (ECMA-363, öffentlich) selbst lesen | Netz | nur Ansichten | mittel | 0 € |
| **3D-PDF PRC** | PRC (ISO 14739) – kein brauchbarer freier Leser gefunden (Asymptote schreibt nur) | aufwendig | – | groß | sonst SDK (ODA PRC, HOOPS) |

**Empfehlung:** STEP vollständig, QIF als zweiter semantischer Weg (Schritt 6), JT zunächst nur Netz-Machbarkeit an einer
Testdatei; JT-PMI erst nach Angebotsvergleich – Entscheidung liegt bei dir. 3D-PDF: U3D-Netz anzeigen, PRC zurückstellen.

## 4. Architektur

```
programm/
  kern/            ohne Qt, voll testbar
    laden.py       Formate -> Modell (XCAF-Dokument + eigene Datenklassen), Hintergrund, Abbrechen
    modell.py      Baugruppe, Teile, Flächen-IDs, Farben, Ebenen
    pmi.py         PMI-Datenklassen (Mass, Formtoleranz, Bezug, Oberflaeche, Hinweis) + Text-Darstellung
    pmi_step.py    PMI aus XCAF lesen, Ergaenzung aus STEP-Entitaeten
    ansichten.py   gespeicherte Ansichten
    tessel.py      Tessellierung, Cache (Datei-Hash + Feinheit), Detailstufen
    messen.py      Abstand, Winkel, Radius, Wandstaerke, Fang
    ausrichten.py  Bestpassung (ICP) und Drei-Punkt-Ausrichtung
    vergleich_geo.py   Flaechenzuordnung, neu/entfernt/geaendert/gleich, Abweichungskarte
    vergleich_pmi.py   semantischer PMI-Diff
    pruefung.py    Aenderungsliste, Status, Protokoll mit SHA-256 (aus ZGmax uebernommen)
    bericht.py, projekt.py (.3dgmax = ZIP), ordnervergleich.py
  ui/              PySide6: Hauptfenster, Viewer-Widget, Baum, PMI-Liste, Messen, Vergleich, Pruefen
tests/  packaging/  docs/
```

**Kernidee Vergleich:**
1. *Ausrichten*: Schwerpunkt/Hauptachsen als Startwert, dann ICP auf Abtastpunkten; von Hand über 3 Punktpaare.
2. *Flächenzuordnung*: persistente IDs, wenn das Modell welche trägt (AP242 hat dafür keinen Pflichtmechanismus – meist
   nicht vorhanden); sonst Signatur je Fläche (Flächentyp, Parameter wie Radius/Achse/Normale, Fläche, Schwerpunkt,
   Hüllquader) → Kostenmatrix → Zuordnung. Gleiche Signatur = *gleich*, zugeordnet aber abweichend = *geändert*, Rest
   *neu*/*entfernt*.
3. *Abweichungskarte*: Punkte auf Netz A, Abstand zur exakten Fläche B (OCCT-Projektion, beschleunigt mit KD-Baum
   über Netz B), Farbskala mit Toleranzgrenze.
4. *PMI-Diff*: PMI auf ein neutrales Schema bringen (Typ, Nennwert, Abmaße, Zone, Modifikatoren, Bezugssystem,
   zugeordnete Flächen **übersetzt über die Flächenzuordnung**). Zuordnung alt↔neu über Typ + Flächen + Wertnähe;
   Ergebnis je PMI *neu/entfallen/geändert (Feld für Feld)/gleich*. Das ist die eigentliche Neuheit.

## 5. Schritte mit Abnahme

| # | Inhalt | Abnahme (du prüfst) |
|---|---|---|
| **1 Machbarkeit** ✅ (ohne Oberfläche) | `.venv` mit OCP 8.0.1; NIST-Modelle (CTC/FTC/STC, AP242) laden; Skript gibt PMI-Tabelle (Typ, Wert, Toleranz, Bezüge, Anzahl Flächen, semantisch/grafisch) und Ansichten aus; Abgleich mit NIST-Analyzer; Mini-Versuch OCCT-Viewer im Qt-Fenster mit Klick auf Fläche; JT-Netz und U3D an je einer Testdatei anlesen | Übersicht `docs/Machbarkeit.md` mit Tabellen, Abdeckungsquote je Modell, Bildschirmfoto; Entscheidung JT/PDF |
| **2 Viewer** ✅ | Laden (Drag-and-drop, Zuletzt), Baum, Navigation wie CAD (Maus/Trackpad, Standardansichten, Drehpunkt), Darstellungsarten, hell/dunkel, gespeicherte Ansichten, PMI-Liste mit Filter, Hervorhebung PMI↔Fläche, Schnitt; Einführung, `tr()`, F1-Anleitung | NIST-FTC flüssig bedienbar, Ansichten schalten PMI korrekt |
| **3 Messen** ✅ | Abstand/Winkel/Radius/Wandstärke/Koordinaten mit Fang, Liste, CSV | Messwerte gegen bekannte NIST-Maße |
| **4 Vergleich** | Ausrichten, Flächenzuordnung, Farbkarte, PMI-Diff, Änderungsliste, Prüfen starten, Prüfung abschließen | Zwei absichtlich geänderte Stände eines NIST-Modells (Wert, Toleranz, Bezug, Fläche geändert) – alle Änderungen gefunden, keine Falschmeldungen |
| **5 Ausgaben** | PDF-Bericht mit Bildern, PMI-Änderungstabelle PDF/CSV, Zwischenablage, Projekt-Container, Ordnervergleich, **Ansichten als Zeichnung** (verdeckte Kanten mit OCCT-HLR, PMI-Projektion → PDF/SVG/DXF), Vergleich exportieren | Bericht für einen Lieferanten verständlich |
| **6 Formate** | QIF, IGES/STL/OBJ/glTF/3MF, JT/3D-PDF je nach Entscheidung | Je Format eine Testdatei in den Tests |
| **7 JT über TKJT** (nach STEP) | TKJT für OCCT 8 bauen, Python-Anbindung, JT laden (Netz, Struktur, dann PMI); Bau mit/ohne TKJT (siehe 8.3) | NIST- bzw. eigene JT-Datei wie STEP-Gegenstück |
| **später: Schnittansichten** | Mehrere Schnittebenen/Clipping-Boxen, Schnittansichten aus dem Modell (AP242 Clipping in Saved Views), Schnittkontur hervorheben und als Ansicht speichern/exportieren | Schnitt aus der Datei sieht aus wie im CAD |

Durchgängig: Tests ab Schritt 1 (Kern mit NIST-Dateien, Oberfläche offscreen, Stresstest), `--selbsttest`,
Changelog DE/EN, HANDOFF.md, unfertiges auf `wip/...`, nach jedem Commit Push.

## 6. Risiken

1. **PMI-Vollständigkeit in OCCT** (größtes Risiko) – Gegenmaßnahme: Ergänzungsleser + Abgleich mit NIST-Analyzer
   in Schritt 1, bevor Oberfläche entsteht.
2. **Echte Exporte weichen von NIST ab** (CATIA/NX/Creo schreiben PMI unterschiedlich) – deine anonymisierten Modelle
   so früh wie möglich in die Tests.
3. **Qt + OCCT-Viewer auf macOS/offscreen** – Mini-Versuch in Schritt 1, Fallback Offscreen-Bild.
4. **Flächenzuordnung bei starken Umbauten** (Flächen geteilt/vereinigt) – als *geändert* mit Abweichungskarte melden
   statt falsch zuzuordnen.
5. **Große Baugruppen** – Tessellierung im Hintergrund, Cache, Detailstufen, Instanzen nur einmal tessellieren.
6. **JT-PMI nur mit Lizenz** – Kosten vor Bau vorlegen.

## 7. Entscheidungen, die bei dir liegen

- ~~Geometriekern OCP über pip~~ → **pythonocc über pixi** (Versuch: OCP kann STEP-Flächen nicht zuordnen).
- Darstellung **OCCT-Viewer** (empfohlen) statt VTK.
- JT: nur Netz frei, PMI nur mit Angebot – erst nach Schritt 1.
- Projektname/Programmname „3DGmax“, Dateiendung `.3dgmax`?

## 8. Ergänzungen (2026-10-26)

### 8.1 Ansichten (Captures) durchklicken
- Gespeicherte Ansichten mit Kamera **und** den jeweils eingeblendeten Annotationen zeigen; vor/zurück durchklicken
  (Tasten, Knöpfe), Ansicht als Vorschaubild in der Liste. Teilweise erledigt: Kamera (Ort, Richtung, Ausschnitt)
  und PMI-Filter je Ansicht; offen: Vor/Zurück-Knöpfe, Vorschaubilder, Schnittebenen der Ansicht.

### 8.2 Suche
- PMI-Suche nach Name, Maß/Wert, Bezug (vorhanden: Freitext über Wert, Bezüge, Name, Typ); ausbauen zu gezielter
  Suche (z. B. `bezug:A`, `wert:0.5`, `typ:position`).
- Suche nach Ansichten/Captures (Name, enthaltene PMI) in der Ansichtsliste.

### 8.3 Bau-Varianten nach Lizenz
- **Standard (Open Source, LGPL-Bibliotheken):** OCCT, pythonocc, Qt/PySide6 – die App darf weitergegeben werden.
- **Mit TKJT (GPL v2+):** zusätzlich JT-Lesen. Eine weitergegebene App müsste dann unter einer GPL-kompatiblen Lizenz
  mit Quelltext stehen; für reine interne Nutzung keine Pflichten. Bau-Skripte und GitHub-Workflow erhalten dafür
  einen Schalter (Standard: ohne TKJT). Wird mit Schritt 7 umgesetzt, damit es keinen Schalter ohne Funktion gibt.
- Entschieden (2026-10-26): 3DGmax steht unter **GPL-3.0-or-later** – verträglich mit OCCT/pythonocc/PySide6 (LGPL)
  und TKJT (GPL v2+), auch bei Weitergabe einer App mit TKJT.
