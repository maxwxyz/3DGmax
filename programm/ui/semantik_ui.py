"""Dialog "Semantisch machen": nur grafische PMI pruefen und als eigene PMI mit Semantik uebernehmen (Reparieren).

Nicht modal: waehrend der Dialog offen ist, lassen sich im Modell Flaechen waehlen und uebernehmen.
"""

from __future__ import annotations

import math
import re
from dataclasses import replace

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern.pmi import BEZUG, MASS, MERKMAL, TOL_SYMBOL, TOLERANZ, Pmi

MASS_TYPEN = ("Size_Diameter", "Size_Radius", "Size_Thickness", "Size_Angular", "Location_LinearDistance",
              "Location_Angular", "Size_SphericalDiameter", "Size_SphericalRadius")
ARTEN = ((TOLERANZ, "Toleranz"), (MASS, "Maß"), (BEZUG, "Bezug"))


def _zahl(text: str) -> float | None:
    t = text.replace(",", ".").strip()
    try:
        zahl = float(t)
        return zahl if math.isfinite(zahl) else None
    except ValueError:
        return None


class SemantikDialog(QtWidgets.QDialog):
    """Art, Werte und Flaechen einer nur grafischen PMI; Startwerte aus pmi_reparieren.vorschlag."""

    def __init__(self, vorschlag, auswahl, zeigen, parent=None, *, position=0, anzahl=0, step=True, geometriewert=None):
        super().__init__(parent)
        self.v, self.auswahl, self.zeigen = vorschlag, auswahl, zeigen
        self.bereichspruefung = None
        self.geometriewert = geometriewert
        self.flaechen = set(vorschlag.flaechen)
        self.projektionsflaechen = list(vorschlag.projektionsflaechen)
        self.projektionsflaechen_oben = set()
        self.setWindowTitle(tr("Grafische PMI prüfen ({} von {})").format(position, anzahl)
                            if anzahl else tr("Semantisch machen"))
        lay = QtWidgets.QFormLayout(self)
        info = QtWidgets.QLabel(tr("Grafik „{}“: Prüfen Sie Art, Werte und zugeordnete Flächen.").format(
            vorschlag.nur_grafik_text) + " " + (tr("Die geprüfte PMI kann im Projekt und zusammen mit der "
            "Originalgrafik in einer STEP-Kopie gespeichert werden.") if step else tr("Die geprüfte PMI wird "
            "beim Speichern des Projekts mit der Originalgrafik verknüpft.")))
        info.setWordWrap(True)
        info.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        info.setObjectName("leise")
        lay.addRow(info)
        self.hinweiswahl = None
        if hinweis := getattr(vorschlag, "freier_hinweis", None):
            nr, wortlaut = hinweis
            self.hinweiswahl = QtWidgets.QCheckBox(tr("Hinweis aus Grafik #{} für beide Zeilen übernehmen").format(nr))
            lay.addRow(self.hinweiswahl)
            lay.addRow(QtWidgets.QLabel(wortlaut))
        if vorschlag.beschreibung:
            zusatz = QtWidgets.QLabel(vorschlag.beschreibung)
            zusatz.setTextFormat(QtCore.Qt.TextFormat.PlainText)
            zusatz.setWordWrap(True)
            lay.addRow(tr("Geltungshinweis für beide Zeilen"), zusatz)
        if vorschlag.bereichsgrenzen:
            grenzen = " ↔ ".join(tr("{} (Kante #{})").format(name, k) for name, k in vorschlag.bereichsgrenzen)
            lay.addRow(tr("Begrenzter Profilbereich"), QtWidgets.QLabel(grenzen))
        validierung = getattr(vorschlag, "validierungstexte", ())
        if validierung:
            herkunft = (tr("Mehrere STEP-Validierungstexte sind dieser Grafik zugeordnet. Werte an der Grafik prüfen.")
                        if len(validierung) > 1 else tr("Der Text stammt aus der STEP-Validierungseigenschaft dieser Grafik."))
            if vorschlag.rahmensymbolquelle == "grafik":
                herkunft += " " + tr("Das Rahmensymbol wurde aus dem ersten gezeichneten Fach gelesen.")
            elif vorschlag.rahmensymbolquelle == "name":
                herkunft += " " + tr("Das Rahmensymbol ergibt sich aus dem Namen „{}“.").format(vorschlag.merkmalsname)
            if getattr(vorschlag, "ocr_text", "") and vorschlag.wert is None:
                herkunft = tr("Grafik und STEP-Validierung stimmen nicht überein. Beide Rahmenzeilen prüfen. Dateitext: {}").format(
                    " / ".join(validierung))
            if kurztext := getattr(vorschlag, "kurzer_geltungshinweis", ""):
                herkunft = tr("Im STEP-Validierungstext steht „{}“. Beim Übernehmen gilt der vollständige "
                              "Geltungshinweis aus der Grafik.").format(kurztext)
            label = QtWidgets.QLabel(herkunft)
            label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            lay.addRow(label)
        elif getattr(vorschlag, "ocr_text", ""):
            lay.addRow(QtWidgets.QLabel(tr("Der Textvorschlag stammt aus der automatischen Schrifterkennung.")))
        self.geometriehinweis = QtWidgets.QLabel(tr("Das vorgeschlagene Nennmaß stammt aus der Modellgeometrie."))
        lay.addRow(self.geometriehinweis)
        self.geometriehinweis.setVisible(getattr(vorschlag, "nennwert_aus_geometrie", False))
        self.art = QtWidgets.QComboBox()
        for k, text in ARTEN:
            self.art.addItem(tr(text), k)
        self.art.setCurrentIndex(max(self.art.findData(vorschlag.art), 0))
        self.typ = QtWidgets.QComboBox()
        lay.addRow(tr("Art"), self.art)
        lay.addRow(tr("Merkmal"), self.typ)
        self.felder: dict[str, QtWidgets.QWidget] = {}
        self._zeilen(lay)
        self._masswahl(lay)
        self.flaechen_text = QtWidgets.QLabel()
        uebernehmen = QtWidgets.QPushButton(tr("Auswahl übernehmen"))
        uebernehmen.setToolTip(tr("Die im Modell gewählten Flächen statt des Vorschlags verwenden"))
        uebernehmen.setEnabled(not vorschlag.profilteil_ids)
        uebernehmen.clicked.connect(self._auswahl_uebernehmen)
        zeile = QtWidgets.QHBoxLayout()
        zeile.addWidget(self.flaechen_text, 1)
        zeile.addWidget(uebernehmen)
        lay.addRow(tr("Flächen"), zeile)
        knoepfe = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        knoepfe.accepted.connect(self._pruefen)
        knoepfe.rejected.connect(self.reject)
        if anzahl:
            knoepfe.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText(tr("Übernehmen"))
            knoepfe.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel).setText(tr("Beenden"))
            knoepfe.addButton(tr("Überspringen"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole).clicked.connect(
                lambda: self.done(2))
        lay.addRow(knoepfe)
        self.art.currentIndexChanged.connect(self._art_gewechselt)
        self._art_gewechselt()
        if vorschlag.profilteil_ids:
            self.art.setEnabled(False)
            self.typ.setEnabled(False)
        self.typ.currentIndexChanged.connect(self._geometriewert_aktualisieren)
        self.felder["nennwert"].textEdited.connect(self.geometriehinweis.hide)
        self._flaechen_gesetzt()

    def _zeilen(self, lay):
        v = self.v

        def zahl(name, text, wert):
            f = QtWidgets.QLineEdit("" if wert is None else str(wert))
            lay.addRow(text, f)
            self.felder[name] = f

        zahl("nennwert", tr("Nennmaß"), v.nennwert)
        self.felder["grenzmass"] = QtWidgets.QCheckBox(tr("Grenzmaße eingeben"))
        self.felder["grenzmass"].setChecked(v.grenzmass)
        lay.addRow("", self.felder["grenzmass"])
        zahl("oben", tr("Oberes Abmaß"), v.oben)
        zahl("unten", tr("Unteres Abmaß"), v.unten)
        self.felder["passung"] = QtWidgets.QLineEdit(v.passung)
        self.felder["passung"].setToolTip(tr("Toleranzklasse nach ISO 286, z. B. H7 (statt der Abmaße)"))
        lay.addRow(tr("Toleranzklasse"), self.felder["passung"])
        zahl("wert", tr("Toleranzwert"), v.wert)
        form = self.felder["zonenform"] = QtWidgets.QComboBox()
        form.addItem(tr("ohne"), "")
        form.addItem(tr("Durchmesserzone ⌀"), "Diameter")
        form.addItem(tr("Kugeldurchmesserzone S⌀"), "SphericalDiameter")
        formen = [s for s in ("Diameter", "SphericalDiameter") if s in v.modifikatoren or v.zone == s]
        form.setCurrentIndex(form.findData(formen[0]) if len(formen) == 1 else (-1 if formen else 0))
        lay.addRow(tr("Zonenform"), form)
        if v.hat_einheitskreis():
            zahl("einheitsdurchmesser", tr("Durchmesser der Einheitsfläche (mm)"), v.einheitsdurchmesser)
        if v.einheitsrechteck_text():
            zahl("einheitslaenge", tr("Länge der Einheitsfläche (mm)"), v.einheitslaenge)
            zahl("einheitsbreite", tr("Breite der Einheitsfläche (mm)"), v.einheitsbreite)
        zahl("maximum_toleranz", tr("Höchstwert der Toleranz (MAX)"), v.maximum_toleranz)
        self.felder["material"] = QtWidgets.QComboBox()
        for k, text in (("", "ohne"), ("M", "Maximum-Material Ⓜ"), ("L", "Minimum-Material Ⓛ")):
            self.felder["material"].addItem(tr(text), k)
        self.felder["material"].setCurrentIndex(max(self.felder["material"].findData(v.material), 0))
        lay.addRow(tr("Materialbedingung"), self.felder["material"])
        if v.zone == "Projected":
            zahl("zonen_wert", tr("Projektionshöhe (mm)"), v.zonen_wert)
            zahl("projektionsversatz", tr("Projektionsversatz (mm)"), v.projektionsversatz)
            self.projektionsknopf = QtWidgets.QPushButton()
            self.projektionsknopf.clicked.connect(self._projektionsende_waehlen)
            self.felder["projektionsende"] = self.projektionsknopf
            self._projektionsende_text()
            lay.addRow(tr("Austrittsfläche"), self.projektionsknopf)
        self.felder["bezuege"] = QtWidgets.QLineEdit(" ".join(b.text() for b in sorted(v.bezuege, key=lambda b: b.stelle)))
        self.felder["bezuege"].setToolTip(tr("Bezugsbuchstaben in der Reihenfolge primär, sekundär, tertiär, z. B. A B C"))
        lay.addRow(tr("Bezüge"), self.felder["bezuege"])
        self.felder["name"] = QtWidgets.QLineEdit(v.name if v.art == BEZUG else "")
        self.felder["name"].setToolTip(tr("Bezugsbuchstabe, wie er in der Grafik steht"))
        lay.addRow(tr("Buchstabe"), self.felder["name"])
        self._lay = lay
        self.felder["grenzmass"].toggled.connect(self._massbeschriftung)
        self._massbeschriftung()

    def _masswahl(self, lay):
        self.massknoepfe = {}
        self.masslesart = None
        wahl = getattr(self.v, "masswahl", ())
        if not wahl:
            return
        hinweis = (tr("Originalgrafik und STEP-Validierungstext weichen voneinander ab. Werte prüfen und eine Quelle wählen oder von Hand eingeben.")
                   if len(wahl) > 1 else tr("Der Bindestrich ist mehrdeutig. Beide Zahlen können nach Prüfung als Grenzmaße übernommen werden."))
        label = QtWidgets.QLabel(hinweis)
        label.setWordWrap(True)
        lay.addRow(label)
        titel = {"grafik": tr("Originalgrafik"), "datei": tr("STEP-Validierungstext"), "grenzen": tr("Grenzmaße")}
        for quelle, text, daten in wahl:
            knopf = QtWidgets.QPushButton(tr("Als Grenzmaße übernehmen") if daten.get("grenzmass") else tr("Werte übernehmen"))
            knopf.clicked.connect(lambda _=False, t=text, d=daten: self._masswerte_setzen(t, d))
            zeile = QtWidgets.QHBoxLayout()
            wort = QtWidgets.QLabel(text)
            wort.setTextFormat(QtCore.Qt.TextFormat.PlainText)
            zeile.addWidget(wort, 1)
            zeile.addWidget(knopf)
            lay.addRow(titel[quelle], zeile)
            self.massknoepfe[quelle] = knopf

    def _masswerte_setzen(self, text, daten):
        self.masslesart = (text, daten)
        self.art.setCurrentIndex(self.art.findData(MASS))
        self.typ.setCurrentIndex(self.typ.findData(daten["typ"]))
        self.felder["grenzmass"].setChecked(daten.get("grenzmass", False))
        for k in ("nennwert", "oben", "unten"):
            self.felder[k].setText(str(daten[k]) if k in daten else "")
        self.felder["passung"].setText(daten.get("passung", ""))

    def _massbeschriftung(self):
        grenze = self.felder["grenzmass"].isChecked()
        self._lay.labelForField(self.felder["oben"]).setText(tr("Höchstmaß") if grenze else tr("Oberes Abmaß"))
        self._lay.labelForField(self.felder["unten"]).setText(tr("Mindestmaß") if grenze else tr("Unteres Abmaß"))

    def _art_gewechselt(self):
        art = self.art.currentData()
        typen = {TOLERANZ: list(TOL_SYMBOL), MASS: list(MASS_TYPEN), BEZUG: ["Datum"]}[art]
        alt = self.typ.currentData() or self.v.typ
        self.typ.clear()
        for t in typen:
            self.typ.addItem(f"{TOL_SYMBOL.get(t, '')} {tr(MERKMAL.get(t, t))}".strip(), t)
        self.typ.setCurrentIndex(0 if art == BEZUG and alt != "DatumTarget" else self.typ.findData(alt))
        sichtbar = {MASS: {"nennwert", "oben", "unten", "grenzmass", "passung"},
                    TOLERANZ: {"wert", "zonenform", "maximum_toleranz", "material", "bezuege", "zonen_wert", "projektionsversatz",
                               "projektionsende", "einheitslaenge", "einheitsbreite", "einheitsdurchmesser"}, BEZUG: {"name"}}[art]
        for name, f in self.felder.items():
            self._lay.setRowVisible(f, name in sichtbar)

    def _auswahl_uebernehmen(self):
        neu = self.auswahl()
        if neu:
            geaendert = self.flaechen != set(neu)
            self.flaechen = set(neu)
            if geaendert:
                self._geometriewert_aktualisieren()
            self._flaechen_gesetzt()
        else:
            QtWidgets.QMessageBox.information(self, tr("Semantisch machen"), tr("Bitte Flächen der Quelldatei wählen"))

    def _geometriewert_aktualisieren(self):
        if not getattr(self.v, "nennwert_aus_geometrie", False):
            return
        wert = (self.geometriewert(self.typ.currentData(), self.flaechen)
                if self.art.currentData() == MASS and self.typ.currentData() and self.geometriewert else None)
        self.felder["nennwert"].setText(str(wert) if wert is not None else "")
        self.geometriehinweis.setVisible(wert is not None)

    def _flaechen_gesetzt(self):
        self.flaechen_text.setText(tr("{} gewählt").format(len(self.flaechen)) if self.flaechen else
                                   tr("keine – Flächen im Modell wählen und übernehmen"))
        if self.v.profilteil_ids:
            teile = ", ".join(f"#{nr}" for nr in self.v.profilteil_ids)
            self.flaechen_text.setText(tr("Teilflächen {} · ganze Flächen {}").format(teile, len(self.flaechen)))
        self.zeigen(self.flaechen)

    def _projektionsende_text(self):
        text = (tr("Fläche {} · Auswahl übernehmen").format(self.projektionsflaechen[0])
                if len(self.projektionsflaechen) == 1 else tr("Austrittsfläche aus Auswahl übernehmen"))
        self.projektionsknopf.setText(text)

    def _projektionsende_waehlen(self):
        auswahl = self.auswahl()
        if len(auswahl) != 1 or auswahl & self.flaechen:
            QtWidgets.QMessageBox.information(self, tr("Semantisch machen"),
                                              tr("Eine eigene Austrittsfläche für die Projektion wählen"))
            return
        self.projektionsflaechen = list(auswahl)
        self._projektionsende_text()
        self.zeigen(auswahl)

    def fehler(self) -> str:
        art = self.art.currentData()
        if not self.flaechen and not self.v.profilteil_ids:
            return tr("Bitte Flächen wählen")
        if self.bereichspruefung and art == TOLERANZ and not self.bereichspruefung(self.flaechen):
            return tr("Die Bereichsgrenzen passen nicht zu den gewählten Flächen.")
        if self.flaechen & self.projektionsflaechen_oben:
            return tr("Eine eigene Austrittsfläche für die Projektion wählen")
        if self.typ.currentIndex() < 0:
            return tr("Bitte das Merkmal wählen")
        if art == MASS:
            n = _zahl(self.felder["nennwert"].text())
            if n is None or n < 0:
                return tr("Bitte das Nennmaß angeben")
            if self.typ.currentData().startswith("Location_") and len(self.flaechen) != 2:
                return tr("Für ein Lagemaß zwei Flächen wählen")
            oben, unten = (self.felder[k].text().strip() for k in ("oben", "unten"))
            if oben or unten or self.felder["grenzmass"].isChecked():
                o, u = _zahl(oben), _zahl(unten)
                if o is None or u is None or u > o:
                    return tr("Bitte beide Grenzen in aufsteigender Reihenfolge angeben")
            klasse = self.felder["passung"].text().strip()
            if klasse and (oben or unten or not re.fullmatch(r"[A-Za-z]+\d+", klasse)):
                return tr("Bitte eine Toleranzklasse oder zwei Grenzwerte angeben")
        if art == TOLERANZ:
            wert = _zahl(self.felder["wert"].text())
            if wert is None or wert < 0:
                return tr("Bitte den Toleranzwert angeben")
            if "einheitsdurchmesser" in self.felder and (_zahl(self.felder["einheitsdurchmesser"].text()) or 0) <= 0:
                return tr("Für die kreisförmige Einheitsfläche einen positiven Durchmesser angeben")
            if "einheitslaenge" in self.felder and any(
                    (_zahl(self.felder[k].text()) or 0) <= 0 for k in ("einheitslaenge", "einheitsbreite")):
                return tr("Für die rechteckige Einheitsfläche zwei positive Seitenlängen angeben")
            if self.felder["zonenform"].currentIndex() < 0:
                return tr("Bitte die Zonenform wählen")
            text = self.felder["maximum_toleranz"].text().strip()
            if text or "Maximum_Tolerance" in self.v.modifikatoren:
                maximum = _zahl(text)
                if maximum is None or maximum <= wert or self.felder["material"].currentData() not in ("M", "L"):
                    return tr("Höchstwert der geometrischen Toleranz nicht gültig")
            if self._bezuege() is None:
                return tr("Bitte bis zu drei gültige Bezugsangaben eingeben")
            if "projektionsende" in self.felder:
                h = _zahl(self.felder["zonen_wert"].text())
                offset = _zahl(self.felder["projektionsversatz"].text())
                if h is None or h <= 0 or offset is None or offset < 0:
                    return tr("Positive Projektionshöhe und nichtnegativen Versatz angeben")
                if len(self.projektionsflaechen) != 1 or self.projektionsflaechen[0] in self.flaechen:
                    return tr("Eine eigene Austrittsfläche für die Projektion wählen")
        if art == BEZUG and not re.fullmatch(r"[A-Z]{1,2}", self.felder["name"].text().strip()):
            return tr("Bitte den Bezugsbuchstaben angeben")
        return ""

    def _bezuege(self):
        from ..kern.pmi_ableiten import bezugsreferenz
        alt = {b.text(): b for b in self.v.bezuege}
        neu = []
        for k, text in enumerate(self.felder["bezuege"].text().strip().upper().split(), 1):
            ref = replace(alt[text], stelle=k) if text in alt else bezugsreferenz(text, k)
            if ref is None or k > 3:
                return None
            neu.append(ref)
        return neu

    def _pruefen(self):
        text = self.fehler()
        if text:
            QtWidgets.QMessageBox.information(self, tr("Semantisch machen"), text)
            return
        self.accept()

    def pmi(self):
        """Die gepruefte PMI (art, typ, Werte, Flaechen; Verweis auf den Callout bleibt)."""
        p = replace(self.v) if self.v.art == self.art.currentData() else Pmi(self.art.currentData(),
                callout=self.v.callout, nur_grafik_text=self.v.nur_grafik_text)
        if self.hinweiswahl and self.hinweiswahl.isChecked():
            p.beschreibung = self.v.freier_hinweis[1]
        if self.v.profilteil_ids:
            p.profilausschnitte = self.v.profilausschnitte
        f = self.felder
        p.art, p.typ, p.flaechen = self.art.currentData(), self.typ.currentData(), set(self.flaechen)
        if p.art == MASS:
            if self.masslesart:
                p.nur_grafik_text, daten = self.masslesart
                if p.typ == daten["typ"]:
                    p.modifikatoren = list(daten.get("modifikatoren", ()))
            p.nennwert, p.oben, p.unten = (_zahl(f[k].text()) for k in ("nennwert", "oben", "unten"))
            p.passung, p.grenzmass = f["passung"].text().strip(), f["grenzmass"].isChecked()
        elif p.art == TOLERANZ:
            p.wert, p.material = _zahl(f["wert"].text()), f["material"].currentData()
            form = f["zonenform"].currentData()
            p.modifikatoren = [m for m in p.modifikatoren if m not in ("Diameter", "SphericalDiameter", "Maximum_Tolerance")]
            if form:
                p.modifikatoren.append(form)
            if p.zone in ("Diameter", "SphericalDiameter"):
                p.zone = ""
            if "einheitslaenge" in f:
                p.einheitslaenge, p.einheitsbreite = (_zahl(f[k].text()) for k in ("einheitslaenge", "einheitsbreite"))
            if "einheitsdurchmesser" in f:
                p.einheitsdurchmesser = _zahl(f["einheitsdurchmesser"].text())
            p.maximum_toleranz = _zahl(f["maximum_toleranz"].text())
            p.bezuege = self._bezuege()
            if "projektionsende" in f:
                p.zonen_wert = _zahl(f["zonen_wert"].text())
                p.projektionsversatz = _zahl(f["projektionsversatz"].text())
                p.projektionsflaechen = self.projektionsflaechen.copy()
        else:
            p.name = f["name"].text().strip()
        return p


def kandidaten(erg, auswahl=None):
    """Pruefbare Originalgrafiken der ersten Datei in der Reihenfolge der PMI-Liste."""
    from ..kern.pmi_reparieren import reparierbar
    from ..kern.zusammenfuegen import pmi_der_ersten_datei
    if erg is None:
        return []
    ids = None if auswahl is None else {id(p) for p in auswahl}
    return [p for p in pmi_der_ersten_datei(erg) if (ids is None or id(p) in ids) and reparierbar(p, erg.grafik)]


def semantisch_machen(fenster, auswahl=None):
    """Jeden Callout einzeln pruefen. Der Durchlauf ist an genau ein geladenes Ergebnis gebunden."""
    from ..kern import pmi_reparieren
    from ..kern.laden import ENDUNGEN_STEP, ENDUNGEN_STEPZ
    aktiv = getattr(fenster, "_semantik_dialog", None)
    if aktiv is not None:
        aktiv.raise_()
        aktiv.activateWindow()
        return aktiv
    erg = fenster.erg
    einzeln = isinstance(auswahl, Pmi)
    liste = fenster.pmi.reparierbare_pmi([auswahl] if einzeln else auswahl)
    if not liste:
        return None
    limit = min((z.erste_flaeche for z in erg.zusaetze), default=len(erg.modell.flaechen))
    uebernommen = 0
    uebersprungen = 0

    def flaechen():
        indices = {erg.modell.flaechen_index(f) for f in fenster.ansicht.auswahl3d}
        return indices if all(i is not None and 0 <= i < limit for i in indices) else set()

    def weiter(k, folge=None, erste=None):
        nonlocal uebersprungen
        while k < len(liste) and not kandidaten(erg, [liste[k]]):
            uebersprungen += 1
            k += 1
        if k == len(liste):
            bilanz()
            return None
        p = liste[k]
        fenster.pmi.waehle(lambda q: q is p)
        fenster.ansicht.zeige_pmi({p.step_id})
        if not fenster.ansicht.grafik_an or fenster.ansicht.grafik_nur_auswahl:
            fenster.ansicht.setze_grafik(True, False, False)
        fenster.ansicht.richte_normal_aus(set(), None, {p.step_id})
        if folge is None:
            v = pmi_reparieren.vorschlag(p, erg.grafik[p.step_id], erg.modell)
            if any(i >= limit or i < 0 for i in v.flaechen):
                v.flaechen = set()
                if v.nennwert_aus_geometrie:
                    v.nennwert = None
            from ..kern.pmi_zwischenbereich import ergaenze
            ergaenze(v, erg.grafik[p.step_id], erg.modell, erg.grafik)
            v.projektionsflaechen = [i for i in v.projektionsflaechen if 0 <= i < limit]
            paar = pmi_reparieren.verbundvorschlaege(v, erg.grafik[p.step_id], erg.modell, erg.grafik)
            if paar:
                v, folge = paar
        else:
            v = folge
        if hinweis := getattr(v, "freier_hinweis", None):
            fenster.ansicht.zeige_pmi({p.step_id, hinweis[0]})
        if grenzgrafiken := getattr(v, "grenzgrafiken", None):
            fenster.ansicht.zeige_pmi({p.step_id, *grenzgrafiken})
        if v.profilteil_ids:
            p.profilausschnitte = v.profilausschnitte
            fenster.ansicht.ergaenze_grafik({}, [p])
        d = SemantikDialog(v, flaechen, fenster.ansicht.hebe_flaechen, fenster, position=k+1,
                           anzahl=0 if einzeln else len(liste), step=erg.pfad.lower().endswith(ENDUNGEN_STEP + ENDUNGEN_STEPZ),
                           geometriewert=lambda typ, indices: pmi_reparieren.geometrie_nennmass(typ, indices, erg.modell))
        if v.bereichsgrenzen:
            from ..kern.pmi_zwischenbereich import begrenzter_verband
            kanten = [kante for _, kante in v.bereichsgrenzen]
            d.bereichspruefung = lambda indices: begrenzter_verband(
                erg.modell.datei, {erg.modell.flaeche_zu_step.get(i) for i in indices} | set(v.profilteil_ids), kanten)
        if folge is not None:
            if erste is not None:
                d.projektionsflaechen_oben = set(erste.projektionsflaechen)
            d.art.setEnabled(False)
            d.typ.setEnabled(erste is None)
            if erste is None:
                box = d.findChild(QtWidgets.QDialogButtonBox)
                box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText(tr("Untere Zeile prüfen"))
            d.setWindowTitle(tr("Verbundrahmen prüfen · Zeile {} von 2").format(2 if erste else 1))
            erklaerung = (tr("Beide Toleranzzeilen werden mit den hier gewählten Flächen übernommen.") if erste
                          else tr("Nach der oberen Zeile folgt die Prüfung der unteren. Abbrechen verwirft beide Zeilen."))
            hinweis = QtWidgets.QLabel(erklaerung)
            hinweis.setWordWrap(True)
            d.layout().insertRow(0, hinweis)
        def fertig(code):
            nonlocal uebernommen, uebersprungen
            if fenster._semantik_dialog is not d:
                return
            fenster._semantik_dialog = None
            d.deleteLater()
            if fenster.erg is not erg:
                return
            if code == QtWidgets.QDialog.DialogCode.Accepted and not d.fehler() and kandidaten(erg, [p]):
                geprueft = d.pmi()
                if folge is not None and erste is None:
                    folge.flaechen = set(geprueft.flaechen)
                    folge.typ = geprueft.typ
                    folge.freier_hinweis = None
                    folge.beschreibung = geprueft.beschreibung
                    weiter(k, folge, geprueft)
                    return
                if erste is not None:
                    erste.flaechen = set(geprueft.flaechen)
                    erste.step_id, geprueft.step_id = -1, -2
                    erste.folgetoleranzen = [geprueft.step_id]
                fenster.fuege_pmi_hinzu([erste, geprueft] if erste is not None else [geprueft])
                uebernommen += 1
            elif code == 2:
                uebersprungen += 1
            else:
                bilanz()
                return
            weiter(k + 1)
        fenster._semantik_dialog = d
        d.finished.connect(fertig)
        d.show()
        return d

    def bilanz():
        fenster._grafik_umschalten()
        fenster.pmi._filtern()
        fenster.statusBar().showMessage(tr("Grafische PMI: {} übernommen, {} übersprungen, {} offen.").format(
            uebernommen, uebersprungen, len(liste) - uebernommen - uebersprungen), 8000)
    return weiter(0)
