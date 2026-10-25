# Machbarkeit (Schritt 1) – Ergebnis, Stand 2026-10-25

Geprüft an den 17 öffentlichen NIST-AP242-Modellen (CTC 1–5, FTC 6–11, STC 6–10). Zahlen je Datei:
[Machbarkeit_Tabelle.md](Machbarkeit_Tabelle.md) (neu erzeugen mit `pixi run machbarkeit`).

## Kurzfassung

| Frage | Ergebnis |
|---|---|
| STEP AP242 laden (Geometrie) | ✅ alle 17 Dateien, 0,1–1,5 s je Datei (M5 Max), auch tessellierte Geometrie (FTC-08-tg) |
| Flächen eindeutig nummerieren, STEP-#ID ↔ Fläche | ✅ 100 % der Flächen zugeordnet |
| Maße (Typ, Nennwert, Abmaße, Grenzmaße, Passung, Basis-/Hilfsmaß) | ✅ 266/266, 98 % mit Wert (Rest hat in der Datei keinen Wert), 93 % mit Fläche |
| Form- und Lagetoleranzen (Symbol, Wert, ⌀-Zone, Ⓜ/Ⓛ, Ⓟ, Bezugssystem, Bezugsgruppen) | ✅ 362/362, 100 % mit Wert, 98 % mit Fläche |
| Bezüge A, B, C … mit Flächen | ✅ 114/114, 91 % mit Fläche (Rest: Bezugsstellen als Punkt/Linie) |
| Gespeicherte Ansichten mit Kamera und zugehörigen PMI | ✅ alle Ansichten, PMI je Ansicht über die STEP-Verknüpfung |
| PMI anklicken → Flächen hervorheben, Fläche anklicken → PMI | ✅ im Viewer-Versuch (Bild unten) |
| OCCT-Viewer in PySide6 | ✅ läuft (OpenGL, Retina) |
| JT | ❌ kein freier Leser in OCCT/pythonocc; siehe unten |
| 3D-PDF | ⏳ Prüfskript fertig, es fehlen Beispieldateien (NIST-PDFs sind reine 2D-Zeichnungen) |
| IGES, STL, OBJ, glTF/GLB | ✅ Leser in pythonocc vorhanden (noch nicht angebunden) |
| 3MF | eigener kleiner Leser nötig (ZIP + XML) |

![Viewer-Versuch: FTC-10, Position ⌀0,75 | A | B | C hervorgehoben](bilder/versuch_ftc10.png)

## Wichtigste Erkenntnisse

1. **Geometriekern: pythonocc-core statt OCP** (Änderung gegenüber dem Plan, per Versuch begründet).
   - In OCP 8.0.1 schlagen alle Nachschlagevorgänge über OCCT-Tabellen aus Python fehl (`Model.Contains(Model.Value(25))`
     ergibt False). Dazu fehlt das Paket `TransferBRep`. Damit lässt sich keine STEP-#ID einer Fläche zuordnen.
   - pythonocc-core 8.0.1.2 (conda-forge, über **pixi**) kann beides: 117/117 Flächen von CTC-01 zugeordnet.
   - Umgebung: `pixi install`, Python 3.14.9, PySide6 6.12 über PyPI; Windows, macOS (arm/Intel) und Linux.
2. **Semantische PMI liest 3DGmax selbst aus der STEP-Datei**, OCCT dient nur zur Gegenprüfung. Gründe:
   - pythonocc bindet `XCAFDoc_GeomTolerance` nicht ein → Toleranzrahmen über OCCT nicht lesbar.
   - OCCT verliert Flächenzuordnungen, wenn die Datei `SET_REPRESENTATION_ITEM` nutzt (CTC-01: Bezüge B und C).
   - OCCT übersieht Maße (STC-07: 7, FTC-08: 4, FTC-10: 3), lässt Passungen weg (FTC-10: ⌀3,5 G6) und liest bei
     FTC-07 (Zoll) ein Grenzmaß falsch (Nennwert statt Mindestmaß 0,012 in).
   - Eigener Leser: alle von OCCT gelesenen Maße sind auch enthalten (Test `test_eigene_masse_umfassen_occt`).
   - Jede PMI behält ihre STEP-#ID → sichere Zuordnung zu Ansichten, Grafik und später zum Vergleich.
3. **Grafische PMI** (Linien/Text der Annotationen) ist in allen NIST-Dateien vorhanden. Darstellung kommt in
   Schritt 2 (aus der Datei: Polylinien/tessellierte Annotationen).

## Formate

**JT (ISO 14306):** OCCT enthält keinen freien JT-Leser. Möglichkeiten:
| Weg | Inhalt | Kosten | Aufwand |
|---|---|---|---|
| Eigener Leser (Netz) | Tessellierung, Baugruppe, keine PMI | 0 € | groß (mehrere Wochen, JT 8–10 unterschiedlich) |
| Siemens JT Open Toolkit | alles inkl. PMI | Mitgliedschaft, Preis nur auf Anfrage | mittel (C++-Anbindung) |
| Open Cascade JT SDK | Netz, LOD, Struktur (PMI laut Website unklar) | Angebot | klein (passt zu OCCT) |
| CAD Exchanger SDK / HOOPS Exchange | alles inkl. PMI | Angebot (früher 6.000–100.000 $/Jahr laut Wettbewerber) | mittel |

Empfehlung: JT zurückstellen, bis Schritt 4 (Vergleich) steht. Dann Angebot Open Cascade JT SDK einholen.

**3D-PDF:** `werkzeuge/pdf3d_pruefen.py` findet 3D-Annotationen und löst U3D/PRC heraus. Für U3D (ECMA-363, öffentlich)
ist ein eigener Netzleser machbar (mittel). Für PRC (ISO 14739) gibt es keinen brauchbaren freien Leser. **Benötigt:**
1–2 echte 3D-PDFs aus eurer Umgebung.

**QIF:** in Schritt 6, Schema öffentlich (qifstandards.org), XML mit lxml.

## Offene Punkte aus Schritt 1
- Hinweise/Notizen ohne Maß (in OCCT „CommonLabel“) noch nicht in der Liste.
- Free-Shapes enthalten Hilfsgeometrie (Punkte/Linien der Annotationen) → im Viewer getrennt schalten.
- Bezugsstellen (Datum Targets) als eigene Einträge mit Punkt/Linie/Fläche.
- Toleranzen ohne Fläche (2 %): meist projizierte Zonen bzw. Muster → prüfen.
- Eigene Modelle (CATIA/NX/Creo-Exporte) durch die Auswertung schicken.
