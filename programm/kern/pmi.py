"""Neutrales PMI-Datenmodell (unabhaengig von OCCT) und lesbare Textform.

Dieses Modell ist die Grundlage fuer Liste, Hervorhebung und den semantischen Vergleich.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Arten
MASS = "mass"
TOLERANZ = "toleranz"
BEZUG = "bezug"
HINWEIS = "hinweis"

# Symbole fuer Form- und Lagetoleranzen (ISO 1101 / ASME Y14.5)
TOL_SYMBOL = {
    "Straightness": "⏤", "Flatness": "⏥", "CircularityOrRoundness": "○",
    "Cylindricity": "⌭", "ProfileOfLine": "⌒", "ProfileOfSurface": "⌓",
    "Angularity": "∠", "Perpendicularity": "⟂", "Parallelism": "∥",
    "Position": "⌖", "Concentricity": "◎", "Coaxiality": "◎",
    "Symmetry": "⌯", "CircularRunout": "↗", "TotalRunout": "⌰",
}
MAT_SYMBOL = {"M": "Ⓜ", "L": "Ⓛ"}
MASS_VORSATZ = {
    "Size_Diameter": "⌀", "Size_Radius": "R", "Size_SphericalDiameter": "S⌀",
    "Size_SphericalRadius": "SR", "Location_Angular": "", "Size_Angular": "",
}
WINKEL_TYPEN = {"Location_Angular", "Size_Angular"}


@dataclass
class BezugsRef:
    """Ein Eintrag im Bezugssystem eines Toleranzrahmens."""
    name: str
    stelle: int = 1  # 1 primaer, 2 sekundaer, 3 tertiaer
    modifikatoren: list[str] = field(default_factory=list)

    def text(self) -> str:
        mods = "".join(MAT_SYMBOL.get(m[0], "") if m in ("MaximumMaterialRequirement",
                                                          "LeastMaterialRequirement") else ""
                       for m in self.modifikatoren)
        return self.name + mods


@dataclass
class Pmi:
    art: str
    typ: str = ""  # z. B. Size_Diameter, Position, Datum
    name: str = ""  # Name aus der Datei
    nennwert: float | None = None
    oben: float | None = None  # Oberes Abmass (oder Hoechstmass bei Grenzmassen)
    unten: float | None = None
    grenzmass: bool = False  # oben/unten sind Grenzmasse statt Abmasse
    passung: str = ""  # z. B. H7
    wert: float | None = None  # Toleranzwert
    zone: str = ""  # Projected, Runout ...
    zonen_wert: float | None = None
    material: str = ""  # M, L
    modifikatoren: list[str] = field(default_factory=list)
    bezuege: list[BezugsRef] = field(default_factory=list)
    flaechen: set[int] = field(default_factory=set)
    kanten: int = 0  # Anzahl zugeordneter Nicht-Flaechen (Kanten, Punkte)
    semantisch: bool = True
    grafisch: bool = False
    nur_grafik_text: str = ""
    quelle: str = "xcaf"  # xcaf | step (Ergaenzung)
    dezimalen: int | None = None  # Nachkommastellen laut Datei
    step_id: int = 0  # Entitaet in der STEP-Datei (0 = unbekannt)
    nummer: int = 0  # laufende Nummer in der Liste

    # --- Darstellung ---

    def wert_text(self) -> str:
        if self.art == MASS:
            return self._mass_text()
        if self.art == TOLERANZ:
            return self._rahmen_text()
        if self.art == BEZUG:
            return f"[{self.name}]"
        return self.nur_grafik_text or self.name

    def _mass_text(self) -> str:
        if self.nennwert is None:
            return self.nur_grafik_text or "(ohne Wert)"
        einheit = "°" if self.typ in WINKEL_TYPEN else ""
        txt = f"{MASS_VORSATZ.get(self.typ, '')}{_zahl(self.nennwert)}{einheit}"
        if self.passung:
            return f"{txt} {self.passung}"
        if self.grenzmass and self.oben is not None and self.unten is not None:
            return f"{MASS_VORSATZ.get(self.typ, '')}{_zahl(self.unten)}–{_zahl(self.oben)}{einheit}"
        if self.oben is None and self.unten is None:
            return txt
        o, u = self.oben or 0.0, self.unten or 0.0
        if abs(o + u) < 1e-12 and o > 0:
            return f"{txt} ±{_zahl(o)}"
        return f"{txt} {_vz(o)}/{_vz(u)}"

    def _rahmen_text(self) -> str:
        teile = [TOL_SYMBOL.get(self.typ, self.typ)]
        zone = ""
        if "Diameter" in self.modifikatoren or self.zone == "Diameter":
            zone = "⌀"
        wert = f"{zone}{_zahl(self.wert)}" if self.wert is not None else "?"
        wert += MAT_SYMBOL.get(self.material, "")
        if self.zone == "Projected":
            wert += " Ⓟ" + (f"{_zahl(self.zonen_wert)}" if self.zonen_wert else "")
        teile.append(wert)
        for b in sorted(self.bezuege, key=lambda b: b.stelle):
            teile.append(b.text())
        return " | ".join(teile)

    def bezug_text(self) -> str:
        return "|".join(b.text() for b in sorted(self.bezuege, key=lambda b: b.stelle))

    def zeile(self) -> dict:
        """Eine Zeile fuer Tabellen/CSV."""
        return {
            "Nr": self.nummer, "Art": self.art, "Typ": self.typ, "Name": self.name,
            "Wert": self.wert_text(), "Bezuege": self.bezug_text(),
            "Flaechen": len(self.flaechen), "Semantisch": self.semantisch,
            "Grafisch": self.grafisch, "Quelle": self.quelle,
        }


def _zahl(x: float | None) -> str:
    if x is None:
        return "?"
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _vz(x: float) -> str:
    return ("+" if x >= 0 else "") + _zahl(x) if abs(x) > 1e-12 else "0"
