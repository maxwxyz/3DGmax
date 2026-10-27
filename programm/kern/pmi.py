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

# Merkmal (Art der Toleranz bzw. des Masses) nach ISO 1101 / ISO 14405; Anzeige ueber tr()
MERKMAL = {
    "Size_Diameter": "Durchmesser", "Size_Radius": "Radius", "Size_SphericalDiameter": "Kugeldurchmesser",
    "Size_SphericalRadius": "Kugelradius", "Size_Thickness": "Dicke", "Size_CurveLength": "Bogenlänge",
    "Size_Angular": "Winkel (Größe)", "Location_Angular": "Winkel (Lage)", "Location_Oriented": "Winkel (Lage)",
    "Location_LinearDistance": "Abstand", "Location_CurvedDistance": "Abstand auf Kurve",
    "Size_ToroidalMinorDiameter": "Torusdurchmesser", "Size_ToroidalMajorDiameter": "Torusdurchmesser",
    "Size_ToroidalMinorRadius": "Torusradius", "Size_ToroidalMajorRadius": "Torusradius",
    "Straightness": "Geradheit", "Flatness": "Ebenheit", "CircularityOrRoundness": "Rundheit",
    "Cylindricity": "Zylinderform", "ProfileOfLine": "Linienform", "ProfileOfSurface": "Flächenform",
    "Angularity": "Neigung", "Perpendicularity": "Rechtwinkligkeit", "Parallelism": "Parallelität",
    "Position": "Position", "Concentricity": "Konzentrizität", "Coaxiality": "Koaxialität",
    "Symmetry": "Symmetrie", "CircularRunout": "Lauf", "TotalRunout": "Gesamtlauf",
    "Datum": "Bezug", "DatumTarget": "Bezugsstelle",
}
MATERIAL = {"M": "Maximum-Material Ⓜ", "L": "Minimum-Material Ⓛ"}
# ASME-Begriffe, wo sie von ISO 1101 abweichen (Anzeige ueber tr())
MERKMAL_ASME = {"ProfileOfSurface": "Flächenprofil", "ProfileOfLine": "Linienprofil", "CircularRunout": "Rundlauf",
                "Cylindricity": "Zylindrizität", "Angularity": "Winkligkeit"}
# Groessenmodifikatoren nach ISO 14405-1 (und ASME-Pendants) fuer die Anzeige hinter dem Mass
GROESSEN_MOD = {
    "TwoPointSize": "LP", "LocalSizeDefinedBySphere": "LS", "LeastSquaresAssociationCriterion": "GG",
    "MaximumInscribedAssociation": "GX", "MinimumCircumscribedAssociation": "GN", "CircumferenceDiameter": "CC",
    "AreaDiameter": "CA", "VolumeDiameter": "CV", "MaximumSize": "SX", "MinimumSize": "SN", "AverageSize": "SA",
    "MedianSize": "SM", "MidRangeSize": "SD", "RangeOfSizes": "SR", "AnyCrossSection": "ACS",
    "SpecificFixedCrossSection": "SCS", "CommonTolerance": "CT", "FreeStateCondition": "Ⓕ",
    "StatisticalTolerance": "⟨ST⟩", "ControlledRadius": "CR", "ContinuousFeature": "⟨CF⟩", "Envelope": "Ⓔ",
}
VORSATZ_MOD = {"Square": "□"}
GROESSENMASSE = {"Size_Diameter", "Size_Radius", "Size_SphericalDiameter", "Size_SphericalRadius", "Size_Thickness"}


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
    norm: str = "iso"  # iso | asme (Begriffe, Regeln; siehe kern.norm)
    bearbeitet: bool = False  # Werte in 3DGmax geaendert
    original: dict | None = None  # Werte laut Datei vor der Bearbeitung

    # --- Darstellung ---

    def wert_text(self) -> str:
        if self.art == MASS:
            return self._mass_text()
        if self.art == TOLERANZ:
            # aus der Grafik abgeleitet ohne lesbaren Wert: Text der Grafik statt eines leeren Rahmens
            return self._rahmen_text() if self.wert is not None or not self.nur_grafik_text else self.nur_grafik_text
        if self.art == BEZUG:
            return f"[{self.name}]" if self.name else self.nur_grafik_text
        return self.nur_grafik_text or self.name

    def _mass_text(self) -> str:
        if self.nennwert is None:
            return self.nur_grafik_text or "(ohne Wert)"
        text = self._mass_kern()
        vorsatz = "".join(VORSATZ_MOD[m] for m in self.modifikatoren if m in VORSATZ_MOD)
        mods = " ".join(GROESSEN_MOD[m] for m in self.modifikatoren if m in GROESSEN_MOD)
        return f"{vorsatz}{text}" + (f" {mods}" if mods else "")

    def _mass_kern(self) -> str:
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

    def merkmal(self) -> str:
        """Merkmalsschluessel (deutsch, Anzeige ueber tr()) nach der Norm des Modells; unbekannte Typen unveraendert."""
        if self.norm == "asme" and self.typ in MERKMAL_ASME:
            return MERKMAL_ASME[self.typ]
        if self.typ in MERKMAL:
            return MERKMAL[self.typ]
        if self.typ.startswith("Location_LinearDistance"):
            return "Abstand"
        return self.typ

    def abmasse(self) -> tuple[float | None, float | None]:
        """Oberes und unteres Abmass (bei Grenzmassen aus dem Nennmass, bei Toleranzklasse nach ISO 286)."""
        if self.art == MASS and self.oben is None and self.unten is None:
            klasse = self.klassen_abmasse()
            return klasse if klasse is not None else (None, None)
        if self.art != MASS:
            return None, None
        if self.grenzmass:
            if self.nennwert is None:
                return None, None
            return (None if self.oben is None else self.oben - self.nennwert,
                    None if self.unten is None else self.unten - self.nennwert)
        return self.oben or 0.0, self.unten or 0.0

    def klassen_abmasse(self) -> tuple[float, float] | None:
        """Abmasse aus der Toleranzklasse (z. B. H7) nach ISO 286 in mm, falls Klasse und Nennmass passen."""
        if self.art != MASS or not self.passung or self.nennwert is None or "/" in self.passung \
                or self.typ in WINKEL_TYPEN:
            return None
        from .iso286 import grenzabmasse
        return grenzabmasse(self.passung, abs(self.nennwert))

    def grenzen(self) -> tuple[float | None, float | None]:
        """Hoechstmass und Mindestmass (ohne Passungstabelle: nur aus Abmassen bzw. Grenzmassen)."""
        if self.art != MASS:
            return None, None
        if self.grenzmass:
            return self.oben, self.unten
        o, u = self.abmasse()
        if self.nennwert is None or o is None:
            return None, None
        return self.nennwert + o, self.nennwert + u

    def masstoleranz(self) -> float | None:
        h, m = self.grenzen()
        return None if h is None or m is None else h - m

    def huelle_text(self) -> str:
        """Geltung der Huellbedingung fuer Groessenmasse: ASME Rule #1 vs. ISO 8015 (Unabhaengigkeit)."""
        if self.art != MASS or self.typ not in GROESSENMASSE:
            return ""
        if self.norm == "asme":
            return "Hüllbedingung gilt (ASME Rule #1)"
        if "Envelope" in self.modifikatoren or "E" in self.modifikatoren:
            return "Hüllbedingung Ⓔ"
        return "Unabhängigkeitsprinzip (ISO 8015) – Form nicht begrenzt"

    def zonen_text(self) -> str:
        teile = []
        if "Diameter" in self.modifikatoren or self.zone == "Diameter":
            teile.append("⌀")
        if self.zone == "Projected":
            teile.append("Ⓟ" + (f" {_zahl(self.zonen_wert)}" if self.zonen_wert else ""))
        elif self.zone and self.zone != "Diameter":
            teile.append(self.zone + (f" {_zahl(self.zonen_wert)}" if self.zonen_wert else ""))
        return " ".join(teile)

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
