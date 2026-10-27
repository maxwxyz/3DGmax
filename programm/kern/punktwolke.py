"""Punktwolken ohne Dreiecke lesen (Scanner-Export): XYZ/ASC/TXT/CSV/PTS und PLY nur mit Punkten (ohne Qt).

Text: je Zeile mindestens drei Zahlen (x y z, weitere Spalten wie Farbe oder Intensitaet werden ignoriert),
Trenner Leerzeichen, Tab, Komma oder Semikolon; Kopf- und Kommentarzeilen werden uebersprungen (PTS: erste Zeile
= Anzahl). Dezimalkomma bei Semikolon-Trennung wird erkannt.
"""

from __future__ import annotations

import os
import re

import numpy as np

ENDUNGEN = (".xyz", ".asc", ".txt", ".csv", ".pts")
_ZAHL = re.compile(r"[-+]?(?:\d+[.,]?\d*|[.,]\d+)(?:[eE][-+]?\d+)?")


def ist_punktwolke(pfad: str) -> bool:
    """Textformat oder PLY ohne Flaechen."""
    endung = os.path.splitext(pfad)[1].lower()
    if endung in ENDUNGEN:
        return True
    if endung == ".ply":
        with open(pfad, "rb") as f:
            kopf = f.read(4096).split(b"end_header")[0]
        return b"element face" not in kopf or re.search(rb"element face 0\b", kopf) is not None
    return False


def lies_punkte(pfad: str, hoechstens: int = 2_000_000) -> np.ndarray:
    """Punkte (n, 3); bei sehr grossen Dateien gleichmaessig ausgeduennt."""
    if pfad.lower().endswith(".ply"):
        from .laden import lies_ply
        p, _ = lies_ply(pfad)
    else:
        p = _lies_text(pfad)
    p = np.asarray(p, float)
    if len(p) < 3:
        raise ValueError(f"Keine Punkte gefunden: {os.path.basename(pfad)}")
    if len(p) > hoechstens:
        p = p[np.random.default_rng(1).choice(len(p), hoechstens, replace=False)]
    return p


def _lies_text(pfad: str) -> np.ndarray:
    werte = []
    with open(pfad, encoding="utf-8", errors="replace") as f:
        for zeile in f:
            zeile = zeile.strip()
            if not zeile or zeile[0] in "#/;%":
                continue
            semikolon = ";" in zeile
            teile = re.split(r"[;\t ]+" if semikolon else r"[,;\t ]+", zeile)
            zahlen = []
            for t in teile:
                if not _ZAHL.fullmatch(t):
                    break
                zahlen.append(float(t.replace(",", ".") if semikolon else t))
            if len(zahlen) >= 3:
                werte.append(zahlen[:3])
    return np.array(werte, float).reshape(-1, 3)
