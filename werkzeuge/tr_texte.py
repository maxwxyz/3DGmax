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
    from programm.ui import hilfe, panels
    out |= set(panels.ART_TEXT.values()) | set(panels.PmiPanel.SPALTEN)
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
