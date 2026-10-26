"""Alle tr("...")-Texte im Programm finden (fuer Uebersetzung und Test).

Aufruf: pixi run python werkzeuge/tr_texte.py   -> listet fehlende englische Texte
"""

from __future__ import annotations

import ast
import json
import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROGRAMM = os.path.join(WURZEL, "programm")


def tr_texte() -> set[str]:
    out = set()
    for ordner, _, dateien in os.walk(PROGRAMM):
        for d in dateien:
            if not d.endswith(".py"):
                continue
            baum = ast.parse(open(os.path.join(ordner, d), encoding="utf-8").read())
            for k in ast.walk(baum):
                if isinstance(k, ast.Call) and getattr(k.func, "id", "") == "tr" and k.args \
                        and isinstance(k.args[0], ast.Constant) and isinstance(k.args[0].value, str):
                    out.add(k.args[0].value)
    # Texte, die ueber Tabellen laufen (tr(variable))
    from programm.kern.pmi import BEZUG, HINWEIS, MASS, TOLERANZ  # noqa: F401
    from programm.ui import einstellungen, hilfe, messwerkzeug, panels, vergleich_ui
    from programm.ui import berichte, ordnervergleich_ui
    out |= set(ordnervergleich_ui.STATUS_TEXT.values())
    from programm.ui import vergleich_ui as vu
    out |= set(vu.AusrichtPanel.ART_TEXT.values()) | {"Ausrichtung nicht eindeutig – weitere Elemente wählen"}
    out |= {t for t, _ in berichte.PMI_SPALTEN + berichte.AENDERUNG_SPALTEN + berichte.MESS_SPALTEN} | {"Status", "Alt", "Neu"}
    from programm.kern import pmi_bericht, pruefung
    out |= {pmi_bericht.FEHLER, pmi_bericht.WARNUNG, pmi_bericht.INFO} | set(pmi_bericht.CSV_SPALTEN)
    out |= set(pmi_bericht.ART_TEXT.values()) | set(pmi_bericht.KATEGORIE.values()) | set(pmi_bericht.STATUS.values())
    from programm.kern import vergleich as kv, vergleich_pmi as kvp
    out |= set(kv.GEO_TITEL.values()) | set(kv.PMI_TITEL.values()) | set(kvp.FELD_TEXT.values())
    for tabelle in (vergleich_ui.STATUS_TEXT, vergleich_ui.PRUEF_TEXT, vergleich_ui.KATEGORIE_TEXT):
        out |= set(tabelle.values())
    out |= set(pruefung.ERGEBNISSE) | {"Ausrichten …", "Geometrie vergleichen …", "PMI vergleichen …",
                                       "gleiche Lage", "Bestpassung", "Punktpaare",
                                       "Geometrie geändert", "Geometrie neu", "Geometrie entfernt"}
    out |= set(messwerkzeug.ART_TEXT.values())
    from programm.kern import messen
    out |= set(messen.WOERTER)
    import re
    quelle = open(messen.__file__, encoding="utf-8").read()
    out |= set(re.findall(r'raise ValueError\("([^"]+)"\)', quelle))
    for schritte in messwerkzeug.HINWEIS.values():
        out |= set(schritte)
    for name, text in einstellungen.STEUERUNG_TEXT.values():
        out |= {name, text}
    out |= set(panels.ART_TEXT.values()) | set(panels.PmiPanel.SPALTEN)
    from programm.kern import pmi as kp
    out |= set(kp.MERKMAL.values()) | set(kp.MATERIAL.values()) | {"Abstand"} | set(kp.MERKMAL_ASME.values())
    out |= {"Hüllbedingung gilt (ASME Rule #1)", "Hüllbedingung Ⓔ", "Unabhängigkeitsprinzip (ISO 8015) – Form nicht begrenzt"}
    from programm.kern import merkmale as km
    out |= set(km.SPALTEN)
    from programm.kern import stueckliste as ks
    out |= set(ks.SPALTEN) | {"Abweichung"}
    from programm.ui import analyse_ui
    out |= {t for _, t in analyse_ui.ARTEN} | set(analyse_ui.HINWEIS.values()) | {"Blickrichtung (zum Betrachter)"}
    from programm.kern import schnellinfo
    out |= set(schnellinfo.GRUPPEN.values())
    for t, x in hilfe.SCHRITTE:
        out |= {t, x}
    return out


def fehlende() -> list[str]:
    with open(os.path.join(PROGRAMM, "i18n_en.json"), encoding="utf-8") as f:
        en = json.load(f)
    return sorted(t for t in tr_texte() if t not in en)


if __name__ == "__main__":
    sys.path.insert(0, WURZEL)
    print(json.dumps(sorted(tr_texte()), ensure_ascii=False, indent=0))
