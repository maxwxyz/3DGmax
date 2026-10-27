"""Groesse der Oberflaeche (wie in ZGmax): Stufen und gespeicherter Wert; leicht, damit app.main ihn vor dem
Anlegen der QApplication lesen kann (QT_SCALE_FACTOR wirkt nur dann)."""

from __future__ import annotations

import os

SKALEN = (0.9, 1.0, 1.15, 1.3, 1.5)


def skalierung(ein) -> float:
    """Gespeicherte Groesse, auf die naechste Stufe gerundet."""
    try:
        v = float(ein.value("ui_skalierung", 1.0))
    except (TypeError, ValueError):
        v = 1.0
    return min(SKALEN, key=lambda s: abs(s - v))


def gespeicherte_skalierung() -> float:
    """Wert aus den Einstellungen (DG_EINSTELLUNGEN fuer Tests, sonst die echten)."""
    from PySide6 import QtCore
    from .. import i18n
    pfad = os.environ.get("DG_EINSTELLUNGEN")
    ein = QtCore.QSettings(pfad, QtCore.QSettings.Format.IniFormat) if pfad else QtCore.QSettings(i18n.ORG, i18n.APP)
    return skalierung(ein)
