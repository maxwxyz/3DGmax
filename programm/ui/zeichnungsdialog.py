"""Gemeinsamer Blattwechsel und STEP-Export fuer die Rekonstruktion aus PDF."""

from pathlib import Path

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern.zeichnungsblatt import Zeichnungsblatt


class Koerperdialog(QtWidgets.QDialog):
    def __init__(self, doc, pfad, titel, parent):
        super().__init__(parent)
        self.doc, self.pfad, self.titel = doc, Path(pfad), titel
        self.blatt = None
        self.setWindowTitle(titel + " – " + self.pfad.name)

    def showEvent(self, e):
        super().showEvent(e)
        self.ansicht.einpassen()

    def _seite(self):
        from pypdfium2 import PdfiumError
        try:
            neu = Zeichnungsblatt(self.doc, self.seite.value()-1)
        except (PdfiumError, ValueError) as e:
            if self.blatt is None:
                raise
            with QtCore.QSignalBlocker(self.seite):
                self.seite.setValue(self.blatt.nummer+1)
            self.status.setText(str(e))
            return
        if self.blatt is not None:
            self.blatt.schliesse()
        self.blatt = neu
        self.ansicht.zeige(self.blatt.bild)
        self._markieren()
        self._pruefen()

    def _export(self):
        ziel, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("STEP mit Bemaßung speichern …"),
                                                        str(self.pfad.with_name(self.pfad.stem + ".stp")), "STEP (*.stp *.step)")
        if not ziel:
            return
        try:
            if Path(ziel).resolve() == self.pfad.resolve():
                raise ValueError(tr("Für das STEP-Modell eine eigene Zieldatei wählen."))
            anzahl = self._schreibe(ziel)
        except (OSError, ValueError, RuntimeError) as e:
            QtWidgets.QMessageBox.warning(self, self.titel, str(e))
            return
        self.status.setText(tr("STEP-Modell mit {} bemaßten Merkmalen unter {} gespeichert.").format(anzahl, ziel))


def oeffne_koerperzeichnung(fenster, dialogklasse):
    import pypdfium2 as pdf
    pfad, _ = QtWidgets.QFileDialog.getOpenFileName(fenster, tr("2D-Zeichnung öffnen"), "", "PDF (*.pdf)")
    if not pfad:
        return
    doc = None
    try:
        doc = pdf.PdfDocument(pfad)
        if not len(doc):
            raise ValueError(tr("Die Zeichnung enthält keine Seiten."))
        dialog = dialogklasse(doc, pfad, fenster)
    except (pdf.PdfiumError, OSError, ValueError) as e:
        if doc is not None:
            doc.close()
        QtWidgets.QMessageBox.warning(fenster, tr("2D-Zeichnung öffnen"), str(e))
        return

    def schliessen():
        dialog.blatt.schliesse()
        doc.close()

    dialog.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
    dialog.finished.connect(schliessen)
    dialog.show()
    return dialog
