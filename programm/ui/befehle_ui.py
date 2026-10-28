"""Befehlssuche (Strg/⌘+K): alle Menuebefehle nach Text, Menuepfad, Tastenkuerzel und dem Text in der anderen
Sprache durchsuchen; Enter fuehrt den Befehl aus. Gerade nicht verfuegbare Befehle stehen grau mit Hinweis."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import SPRACHE, tr, uebersetzungen


@dataclass
class Befehl:
    aktion: QtGui.QAction
    text: str
    pfad: str  # z. B. "Datei › Exportieren"
    suche: str  # kleingeschrieben: Text, Pfad, Kuerzel, andere Sprache


def _ohne_kuerzel(text: str) -> str:
    return text.replace("&&", "\0").replace("&", "").replace("\0", "&")


def _andere_sprache(text: str) -> str:
    """Englisch zum deutschen Text bzw. Deutsch zum englischen (Suche in beiden Sprachen)."""
    en = uebersetzungen()
    if SPRACHE == "de":
        return en.get(text, "")
    rueck = getattr(_andere_sprache, "_rueck", None)
    if rueck is None:
        rueck = _andere_sprache._rueck = {v: k for k, v in en.items()}
    return rueck.get(text, "")


def befehle(menueleiste: QtWidgets.QMenuBar) -> list[Befehl]:
    """Alle ausfuehrbaren Menueeintraege (ohne Untermenues selbst und Trenner)."""
    out: list[Befehl] = []

    def gehe(menue: QtWidgets.QMenu, pfad: list[str]):
        for a in menue.actions():
            if a.isSeparator() or not a.isVisible():
                continue
            text = _ohne_kuerzel(a.text())
            if a.menu() is not None:
                gehe(a.menu(), pfad + [text])
                continue
            if not text:
                continue
            kuerzel = a.shortcut().toString(QtGui.QKeySequence.SequenceFormat.NativeText)
            suche = " ".join((text, " ".join(pfad), kuerzel, _andere_sprache(text))).casefold()
            out.append(Befehl(a, text, " › ".join(pfad), suche))

    for a in menueleiste.actions():
        if a.menu() is not None:
            gehe(a.menu(), [_ohne_kuerzel(a.text())])
    return out


def treffer(liste: list[Befehl], anfrage: str) -> list[Befehl]:
    """Befehle, die alle Woerter der Anfrage enthalten; Textanfang vor Wortanfang vor Rest, verfuegbare zuerst."""
    woerter = anfrage.casefold().split()
    if not woerter:
        return list(liste)
    passend = [b for b in liste if all(w in b.suche for w in woerter)]

    def rang(b: Befehl):
        t = b.text.casefold()
        erstes = woerter[0]
        stufe = 0 if t.startswith(erstes) else 1 if any(x.startswith(erstes) for x in t.split()) else 2
        return (not b.aktion.isEnabled(), stufe, len(b.text))
    return sorted(passend, key=rang)


class BefehlsSuche(QtWidgets.QDialog):
    """Kleines Suchfenster oben in der Mitte des Hauptfensters."""

    def __init__(self, menueleiste: QtWidgets.QMenuBar, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Befehl suchen"))
        self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint)
        self.resize(560, 380)
        self.alle = befehle(menueleiste)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        self.eingabe = QtWidgets.QLineEdit()
        self.eingabe.setPlaceholderText(tr("Befehl suchen, z. B. Schnitt, Vergleich, Toleranzkette …"))
        self.eingabe.setToolTip(tr("Name einer Funktion tippen; ↑ ↓ wählen, Enter führt sie aus"))
        self.eingabe.setClearButtonEnabled(True)
        self.eingabe.textChanged.connect(self._fuelle)
        self.eingabe.installEventFilter(self)
        lay.addWidget(self.eingabe)
        self.liste = QtWidgets.QListWidget()
        self.liste.itemActivated.connect(lambda _it: self.ausfuehren())
        lay.addWidget(self.liste, 1)
        self.hinweis = QtWidgets.QLabel(tr("↑ ↓ wählen · Enter ausführen · Esc schließen"))
        self.hinweis.setObjectName("leise")
        lay.addWidget(self.hinweis)
        self._fuelle("")

    def _fuelle(self, anfrage: str):
        self.treffer = treffer(self.alle, anfrage)
        self.liste.clear()
        for b in self.treffer:
            kuerzel = b.aktion.shortcut().toString(QtGui.QKeySequence.SequenceFormat.NativeText)
            zeile = f"{b.text}    {b.pfad}" + (f"    {kuerzel}" if kuerzel else "")
            it = QtWidgets.QListWidgetItem(zeile)
            if not b.aktion.isEnabled():
                it.setForeground(QtGui.QBrush(QtGui.QColor("#9aa0aa")))
                it.setToolTip(tr("Gerade nicht verfügbar (z. B. erst ein Modell öffnen)"))
            elif b.aktion.isCheckable():
                it.setToolTip(tr("Schaltet um (jetzt: {})").format(tr("an") if b.aktion.isChecked() else tr("aus")))
            self.liste.addItem(it)
        if self.treffer:
            self.liste.setCurrentRow(0)

    def eventFilter(self, obj, ev):
        if obj is self.eingabe and ev.type() == QtCore.QEvent.Type.KeyPress:
            schritt = {QtCore.Qt.Key.Key_Down: 1, QtCore.Qt.Key.Key_Up: -1}.get(ev.key())
            if schritt and self.liste.count():
                self.liste.setCurrentRow(max(0, min(self.liste.count() - 1, self.liste.currentRow() + schritt)))
                return True
            if ev.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
                self.ausfuehren()
                return True
        return super().eventFilter(obj, ev)

    def ausfuehren(self) -> bool:
        """Gewaehlten Befehl ausfuehren (nach dem Schliessen, damit Dialoge des Befehls nicht ueberdeckt werden)."""
        z = self.liste.currentRow()
        if not 0 <= z < len(self.treffer) or not self.treffer[z].aktion.isEnabled():
            return False
        aktion = self.treffer[z].aktion
        self.accept()
        QtCore.QTimer.singleShot(0, aktion.trigger)
        return True
