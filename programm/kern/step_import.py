"""Nativer STEP-Import ohne Python-Sperre. Der normale pythonocc-Reader behaelt die Transferdaten."""

import ctypes
from functools import lru_cache
from pathlib import Path
import sys

from ..i18n import tr

_Meldung = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int)


@lru_cache(maxsize=1)
def bibliothek():
    ordner = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2] / "build/step"
    endung = {"darwin": "dylib", "win32": "dll"}.get(sys.platform, "so")
    pfad = ordner / f"dg_step.{endung}"
    if not pfad.exists():
        return None
    lib = ctypes.CDLL(str(pfad))
    lib.dg_step_lesen.argtypes = (ctypes.c_void_p, ctypes.c_char_p)
    lib.dg_step_uebertragen.argtypes = (ctypes.c_void_p, ctypes.c_void_p, _Meldung)
    return lib


def uebertrage(reader, doc, pfad, fortschritt):
    from OCC.Core.IFSelect import IFSelect_RetDone
    from .laden import LadeFehler

    lib = bibliothek()
    fehler = []
    def anzeigen(prozent):
        if fehler:
            return 0
        try:
            fortschritt(tr("STEP-Geometrie übertragen … {} %").format(prozent))
            return 1
        except BaseException as exc:
            # Keine Python-Ausnahme ueber die C-Grenze weiterreichen.
            fehler.append(exc)
            return 0
    ok = lib.dg_step_lesen(int(reader.this), pfad.encode("utf-8")) if lib else reader.ReadFile(pfad) == IFSelect_RetDone
    if not ok:
        raise LadeFehler(f"STEP-Datei nicht lesbar: {pfad}")
    if fortschritt:
        fortschritt(tr("STEP-Geometrie übertragen … {} %").format(0))
    if lib:
        label = doc.Main()
        ok = lib.dg_step_uebertragen(int(reader.this), int(label.this), _Meldung(anzeigen) if fortschritt else _Meldung())
    else:
        ok = reader.Transfer(doc)
    if fehler:
        raise fehler[0]
    if not ok:
        raise LadeFehler(f"Uebertragung fehlgeschlagen: {pfad}")
