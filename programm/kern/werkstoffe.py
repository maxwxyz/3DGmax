"""Werkstoffe fuer die Waermeausdehnung (ohne Qt): kleine Bibliothek mit Ausdehnungskoeffizienten, Zuordnung eines
Werkstoffnamens (z. B. "S235", "EN AW-6082", "1.4301") per Stichwort und Werkstoffe je Produkt aus der STEP-Datei.

STEP: AP214/AP242 MATERIAL_DESIGNATION(Name, (Definitionen)) oder die XCAF-Form PROPERTY_DEFINITION('material
property', 'material name', Definition) mit PROPERTY_DEFINITION_REPRESENTATION auf eine REPRESENTATION mit
DESCRIPTIVE_REPRESENTATION_ITEM(Name, Beschreibung). Definition -> PRODUCT_DEFINITION(_SHAPE) -> Produktname.
Laengenaenderung: dL = alpha * L * (T - 20 °C), Bezugstemperatur 20 °C nach ISO 1.
"""

from __future__ import annotations

import re

REFERENZ = 20.0  # °C, ISO 1

# Name -> alpha in 1e-6/K (Richtwerte bei Raumtemperatur)
BIBLIOTHEK = {"Stahl": 11.5, "Nichtrostender Stahl": 16.0, "Gusseisen": 10.5, "Aluminium": 23.0, "Messing": 19.0,
              "Kupfer": 16.5, "Titan": 8.6, "PA6": 80.0, "POM": 110.0, "PEEK": 47.0}

# Name -> Dichte in g/cm3 (Richtwerte)
DICHTE = {"Stahl": 7.85, "Nichtrostender Stahl": 7.9, "Gusseisen": 7.2, "Aluminium": 2.7, "Messing": 8.5,
          "Kupfer": 8.96, "Titan": 4.5, "PA6": 1.14, "POM": 1.41, "PEEK": 1.32}

# Stichworte (Wortanfang, ohne Gross-/Kleinschreibung) -> Bibliotheksname; spezifische zuerst
STICHWORTE = (
    ("Nichtrostender Stahl", (r"1\.4[0-9]", "x[0-9]+cr", "edelstahl", "stainless", "inox", "v[24]a", "aisi 3")),
    ("Aluminium", ("alu", "almg", "alsi", "alcu", "alzn", "en aw", "6061", "6082", "7075", "5083")),
    ("Gusseisen", ("gg[0-9-]", "gjl", "gjs", "guss", "cast iron", "en-gj")),
    ("Messing", ("messing", "brass", "cuzn", "ms[0-9]")),
    ("Kupfer", ("kupfer", "copper", r"cu\b", "cu-etp")),
    ("Titan", ("titan", r"ti\b", "ti6al")),
    ("PA6", ("pa6", "pa 6", "polyamid", "nylon")),
    ("POM", ("pom", "acetal", "delrin")),
    ("PEEK", ("peek",)),
    ("Stahl", ("stahl", "federstahl", "steel", "c75", "c60", "s235", "s275", "s355", "c45", "c35", "42crmo", "16mncr", "100cr", "st37", "st52",
               r"1\.0[0-9]", r"1\.[1-8][0-9]")),
)


def bibliotheksname(werkstoff: str) -> str | None:
    """Bibliothekseintrag zu einem Werkstoffnamen oder None."""
    if not werkstoff:
        return None
    text = werkstoff.casefold()
    if werkstoff in BIBLIOTHEK:
        return werkstoff
    for name, muster in STICHWORTE:
        if any(re.search(r"(?<![a-z0-9])" + m, text) for m in muster):
            return name
    return None


def alpha_fuer(werkstoff: str) -> float | None:
    """Ausdehnungskoeffizient in 1e-6/K zu einem Werkstoffnamen (Bibliothek per Stichwort) oder None."""
    name = bibliotheksname(werkstoff)
    return BIBLIOTHEK[name] if name else None


def dichte_fuer(werkstoff: str) -> float | None:
    """Dichte in g/cm3 zu einem Werkstoffnamen (Bibliothek per Stichwort) oder None."""
    name = bibliotheksname(werkstoff)
    return DICHTE[name] if name else None


def laengenaenderung(alpha_e6: float, laenge: float, temperatur: float) -> float:
    """dL in mm fuer alpha (1e-6/K), Laenge (mm) und Temperatur (°C)."""
    return alpha_e6 * 1e-6 * laenge * (temperatur - REFERENZ)


def _produkt(datei, ref) -> str | None:
    """Produktname zu einer Definition (PRODUCT_DEFINITION, ..._SHAPE, ..._FORMATION)."""
    for _ in range(6):
        e = datei.get(ref)
        if e is None:
            return None
        if e.is_a("PRODUCT"):
            a = e.args("PRODUCT")
            return a[1] if len(a) > 1 and isinstance(a[1], str) else None
        if e.is_a("PRODUCT_DEFINITION_SHAPE"):
            ref = e.args("PRODUCT_DEFINITION_SHAPE")[2]
        elif e.is_a("PRODUCT_DEFINITION"):
            ref = e.args("PRODUCT_DEFINITION")[2]
        elif e.is_a("PRODUCT_DEFINITION_FORMATION") or e.is_a("PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE"):
            ref = e.args()[2]
        else:
            return None
    return None


def werkstoffe_aus_step(datei) -> dict[str, str]:
    """Produktname -> Werkstoffname aus einer STEP-Datei (leer ohne Datei oder ohne Angabe)."""
    out: dict[str, str] = {}
    if datei is None:
        return out
    for e in datei.of_type("MATERIAL_DESIGNATION"):
        a = e.args("MATERIAL_DESIGNATION")
        if len(a) >= 2 and isinstance(a[0], str):
            for d in a[1] if isinstance(a[1], (list, tuple)) else [a[1]]:
                p = _produkt(datei, d)
                if p:
                    out.setdefault(p, a[0])
    darstellung = {}
    for e in datei.of_type("PROPERTY_DEFINITION_REPRESENTATION"):
        a = e.args("PROPERTY_DEFINITION_REPRESENTATION")
        if len(a) >= 2:
            darstellung[getattr(a[0], "id", a[0])] = a[1]
    for e in datei.of_type("PROPERTY_DEFINITION"):
        a = e.args("PROPERTY_DEFINITION")
        if len(a) < 3 or a[0] != "material property" or a[1] != "material name" or e.id not in darstellung:
            continue
        rep = datei.get(darstellung[e.id])
        if rep is None:
            continue
        for item in rep.args()[1]:
            it = datei.get(item)
            if it is not None and it.is_a("DESCRIPTIVE_REPRESENTATION_ITEM"):
                p = _produkt(datei, a[2])
                if p:
                    out.setdefault(p, it.args("DESCRIPTIVE_REPRESENTATION_ITEM")[0])
    return out
