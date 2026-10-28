"""Toleranzkette als eigene Datei (.3dgkette, JSON) zum Weiterarbeiten in einer spaeteren Sitzung (ohne Qt).

Inhalt: Format und Version, Modelldatei (Pfad und Name, damit die Flaechen wieder passen), Glieder, Cp der Kette,
Anforderung, Temperaturen und Werkstoffe je Bauteil, gemerkte Planspiel-Szenarien, manuelle Freigabe (geprueft,
Name, Datum, Kommentar). Das Projekt (.3dgmax) speichert
die Kette ebenfalls (ohne Szenarien).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field

from .toleranzkette import Glied

ENDUNG = ".3dgkette"
FORMAT = "3dgmax-kette"
VERSION = 1


@dataclass
class KettenDatei:
    glieder: list[Glied]
    cp: float = 1.0
    anforderung: tuple[float, float] | None = None
    temperaturen: tuple[float, float] | None = None  # °C, None: ohne Waermeausdehnung
    werkstoffe: dict = field(default_factory=dict)  # Bauteil -> {"name", "alpha" (1e-6/K), "t1", "t2" (°C, optional)}
    modell: str = ""  # Pfad der Modelldatei beim Speichern
    name: str = ""
    szenarien: dict = field(default_factory=dict)  # Name -> (Cp, Glieder) gemerkter Planspiele
    freigabe: dict = field(default_factory=dict)  # {"geprueft": bool, "name", "datum", "kommentar"}

    def alpha(self) -> dict:
        return {t: w["alpha"] for t, w in self.werkstoffe.items() if w.get("alpha")}

    def je_teil(self, fall: int) -> dict:
        """Eigene Temperaturen der Bauteile im Fall 0 (erste) bzw. 1 (zweite Grenztemperatur)."""
        schluessel = ("t1", "t2")[fall]
        return {t: w[schluessel] for t, w in self.werkstoffe.items() if w.get(schluessel) is not None}


def speichere(pfad: str, k: KettenDatei) -> str:
    if not pfad.endswith(ENDUNG):
        pfad += ENDUNG
    daten = {"format": FORMAT, "version": VERSION, "name": k.name, "modell": k.modell,
             "modell_name": os.path.basename(k.modell), "cp": k.cp, "anforderung": k.anforderung,
             "temperaturen": k.temperaturen, "werkstoffe": k.werkstoffe, "glieder": [asdict(g) for g in k.glieder],
             "szenarien": {n: {"cp": cp, "glieder": [asdict(g) for g in gl]} for n, (cp, gl) in k.szenarien.items()},
             "freigabe": k.freigabe}
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
    return pfad


def lade(pfad: str) -> KettenDatei:
    with open(pfad, encoding="utf-8") as f:
        d = json.load(f)
    if d.get("format") != FORMAT:
        raise ValueError("keine 3DGmax-Kettendatei")
    glieder = _glieder(d.get("glieder", []))
    modell = d.get("modell", "")
    if modell and not os.path.isabs(modell):
        modell = os.path.join(os.path.dirname(os.path.abspath(pfad)), modell)
    if modell and not os.path.isfile(modell):  # Datei verschoben: neben der Kette suchen
        neben = os.path.join(os.path.dirname(os.path.abspath(pfad)), d.get("modell_name", ""))
        modell = neben if os.path.isfile(neben) else modell
    return KettenDatei(glieder, d.get("cp", 1.0), tuple(d["anforderung"]) if d.get("anforderung") else None,
                       tuple(d["temperaturen"]) if d.get("temperaturen") else None, d.get("werkstoffe", {}), modell,
                       d.get("name", ""), {n: (x.get("cp", 1.0), _glieder(x.get("glieder", [])))
                                           for n, x in d.get("szenarien", {}).items()},
                       d.get("freigabe") or {})


def _glieder(liste: list) -> list[Glied]:
    felder = set(Glied.__dataclass_fields__)
    return [Glied(**{**{k: v for k, v in g.items() if k in felder}, "flaechen": tuple(g.get("flaechen", ())),
                     "messwerte": tuple(g.get("messwerte", ()))}) for g in liste]


# 2D- und 3D-Ketten (kern.kette2d / kern.kette3d) als eigene Dateien
ENDUNG_2D, ENDUNG_3D = ".3dgkette2d", ".3dgkette3d"
FORMAT_2D, FORMAT_3D = "3dgmax-kette2d", "3dgmax-kette3d"


def speichere_raum(pfad: str, kette) -> str:
    """2D- oder 3D-Kette speichern (Endung nach Art der Kette)."""
    from . import kette2d, kette3d
    zwei = isinstance(kette, kette2d.Kette2D)
    endung, fmt = (ENDUNG_2D, FORMAT_2D) if zwei else (ENDUNG_3D, FORMAT_3D)
    if not pfad.endswith(endung):
        pfad += endung
    daten = {"format": fmt, "version": 1, "kette": (kette2d if zwei else kette3d).als_dict(kette)}
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
    return pfad


def lade_raum(pfad: str):
    """2D- oder 3D-Kette laden (Art aus dem Format der Datei)."""
    from . import kette2d, kette3d
    with open(pfad, encoding="utf-8") as f:
        d = json.load(f)
    if d.get("format") == FORMAT_2D:
        return kette2d.von_dict(d["kette"])
    if d.get("format") == FORMAT_3D:
        return kette3d.von_dict(d["kette"])
    raise ValueError("keine 3DGmax-2D/3D-Kettendatei")

