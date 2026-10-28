"""Einheitlicher Aufbau der Werkzeug-Panels (UI-Plan Stufe 3): oben ein Satz zum Zweck, dann Eingaben, ein
Hauptknopf (objectName "primaer"), die Ergebnistabelle (leere Tabelle mit Hinweis, tabellen.leer_hinweis) und unten
Nebenbefehle und Export."""

from __future__ import annotations

from PySide6 import QtWidgets


def zweck_zeile(text: str) -> QtWidgets.QLabel:
    """Ein Satz oben im Panel: wofuer es da ist (leise, umbrechend)."""
    zeile = QtWidgets.QLabel(text)
    zeile.setWordWrap(True)
    zeile.setObjectName("leise")
    zeile.setProperty("zweck", True)
    return zeile
