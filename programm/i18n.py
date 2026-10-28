"""Sprache der Oberflaeche: Deutsch oder Englisch.

tr("Text") liefert die Uebersetzung des deutschen Textes (oder ihn selbst). Texte mit Werten werden als
Vorlage uebersetzt: tr("Datei {} geladen").format(name). Die Sprache steht beim Programmstart fest:
  1. Umgebungsvariable DG_LANG (de/en), z. B. fuer Tests
  2. Einstellung "sprache" (Ansicht > Sprache), "auto" = wie das Betriebssystem
  3. Systemsprache: Deutsch -> de, alles andere -> en
Uebersetzungen: i18n_en.json (deutscher Text -> englischer Text).
"""

import json
import os
import sys

SPRACHEN = ("de", "en")
HIER = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ORG, APP = "3DGmax", "3DGmax"


def systemsprache() -> str:
    try:
        from PySide6.QtCore import QLocale
        return "de" if QLocale.system().language() == QLocale.Language.German else "en"
    except Exception:  # noqa: BLE001
        return "de" if os.environ.get("LANG", "").lower().startswith("de") else "en"


def einstellung() -> str:
    try:
        from PySide6.QtCore import QSettings
        v = QSettings(ORG, APP).value("sprache")
        return v if v in SPRACHEN else "auto"
    except Exception:  # noqa: BLE001
        return "auto"


def _erkenne() -> str:
    env = os.environ.get("DG_LANG", "")
    if env in SPRACHEN:
        return env
    s = einstellung()
    return s if s in SPRACHEN else systemsprache()


SPRACHE = _erkenne()
_EN: dict | None = None


_QT_UEBERSETZER = []  # Referenz halten, sonst raeumt Python den QTranslator weg


def qt_uebersetzung(app) -> bool:
    """Qt-eigene Texte (Knoepfe "Schließen", "Abbrechen", Dateidialoge) auf Deutsch: qtbase_de.qm aus der App (gebaut)
    oder aus der Qt-Installation. False, wenn Englisch eingestellt ist oder die Datei fehlt."""
    if SPRACHE != "de":
        return False
    if _QT_UEBERSETZER:  # schon geladen (App-Start oder Hauptfenster)
        return True
    from PySide6.QtCore import QLibraryInfo, QTranslator
    for ordner in (os.path.join(HIER, "translations"), QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        u = QTranslator(app)
        if u.load("qtbase_de", ordner):
            app.installTranslator(u)
            _QT_UEBERSETZER.append(u)
            return True
    return False


def uebersetzungen() -> dict:
    global _EN
    if _EN is None:
        try:
            with open(os.path.join(HIER, "i18n_en.json"), encoding="utf-8") as f:
                _EN = json.load(f)
        except (OSError, ValueError):
            _EN = {}
    return _EN


def tr(text: str) -> str:
    """Uebersetzung in die aktuelle Sprache (unbekannte Texte bleiben unveraendert)."""
    if SPRACHE == "de":
        return text
    return uebersetzungen().get(text, text)


def anleitung() -> str:
    """Dateiname der Anleitung in der aktuellen Sprache."""
    return "Manual.html" if SPRACHE == "en" else "Anleitung.html"
