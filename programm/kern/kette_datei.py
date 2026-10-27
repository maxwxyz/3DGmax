"""Toleranzkette als eigene Datei (.3dgkette, JSON) zum Weiterarbeiten in einer spaeteren Sitzung (ohne Qt).

Inhalt: Format und Version, Modelldatei (Pfad und Name, damit die Flaechen wieder passen), Glieder, Cp der Kette,
Anforderung, Temperaturen und Werkstoffe je Bauteil. Das Projekt (.3dgmax) speichert die Kette ebenfalls.
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
             "temperaturen": k.temperaturen, "werkstoffe": k.werkstoffe, "glieder": [asdict(g) for g in k.glieder]}
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
    return pfad


def lade(pfad: str) -> KettenDatei:
    with open(pfad, encoding="utf-8") as f:
        d = json.load(f)
    if d.get("format") != FORMAT:
        raise ValueError("keine 3DGmax-Kettendatei")
    felder = set(Glied.__dataclass_fields__)
    glieder = [Glied(**{**{k: v for k, v in g.items() if k in felder}, "flaechen": tuple(g.get("flaechen", ())),
                       "messwerte": tuple(g.get("messwerte", ()))})
               for g in d.get("glieder", [])]
    modell = d.get("modell", "")
    if modell and not os.path.isabs(modell):
        modell = os.path.join(os.path.dirname(os.path.abspath(pfad)), modell)
    if modell and not os.path.isfile(modell):  # Datei verschoben: neben der Kette suchen
        neben = os.path.join(os.path.dirname(os.path.abspath(pfad)), d.get("modell_name", ""))
        modell = neben if os.path.isfile(neben) else modell
    return KettenDatei(glieder, d.get("cp", 1.0), tuple(d["anforderung"]) if d.get("anforderung") else None,
                       tuple(d["temperaturen"]) if d.get("temperaturen") else None, d.get("werkstoffe", {}), modell,
                       d.get("name", ""))
