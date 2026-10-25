"""Machbarkeit Schritt 1: alle STEP-Dateien eines Ordners lesen und Abdeckung tabellieren.

Aufruf: pixi run python werkzeuge/machbarkeit.py [ordner] [--details datei.stp]
Schreibt docs/Machbarkeit_Tabelle.md.
"""

from __future__ import annotations

import collections
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from programm.kern.ansichten import lies_ansichten  # noqa: E402
from programm.kern.laden import lade_step  # noqa: E402
from programm.kern.pmi import BEZUG, MASS, TOLERANZ  # noqa: E402
from programm.kern.pmi_lesen import lies_pmi, lies_pmi_xcaf  # noqa: E402

STANDARD = "daten/nist/NIST-PMI-STEP-Files"
REFERENZ_TYPEN = {
    MASS: ("DIMENSIONAL_SIZE", "DIMENSIONAL_LOCATION", "ANGULAR_SIZE", "ANGULAR_LOCATION",
           "DIRECTED_DIMENSIONAL_LOCATION", "DIMENSIONAL_LOCATION_WITH_PATH", "DIMENSIONAL_SIZE_WITH_PATH"),
}


def referenz_zaehlung(datei) -> dict[str, int]:
    """Erwartete Anzahl je Art aus dem Entitaetsgraphen."""
    masse = sum(1 for e in datei.entities.values() if any(e.is_a(t) for t in REFERENZ_TYPEN[MASS]))
    tol_namen = ("GEOMETRIC_TOLERANCE", "FLATNESS_TOLERANCE", "PERPENDICULARITY_TOLERANCE",
                 "STRAIGHTNESS_TOLERANCE", "ROUNDNESS_TOLERANCE", "CYLINDRICITY_TOLERANCE",
                 "PARALLELISM_TOLERANCE", "ANGULARITY_TOLERANCE", "POSITION_TOLERANCE",
                 "SURFACE_PROFILE_TOLERANCE", "LINE_PROFILE_TOLERANCE", "SYMMETRY_TOLERANCE",
                 "CONCENTRICITY_TOLERANCE", "COAXIALITY_TOLERANCE", "CIRCULAR_RUNOUT_TOLERANCE",
                 "TOTAL_RUNOUT_TOLERANCE")
    tol = sum(1 for e in datei.entities.values() if any(e.is_a(t) for t in tol_namen))
    bez = len({e.args("DATUM")[4] for e in datei.of_type("DATUM")})
    kam = len(datei.of_type("CAMERA_MODEL_D3")) + len(datei.of_type("CAMERA_MODEL_D3_MULTI_CLIPPING"))
    return {MASS: masse, TOLERANZ: tol, BEZUG: bez, "ansichten": kam}


def _mass_schluessel(p):
    typ = {"Location_None": "Location_LinearDistance"}.get(p.typ, p.typ)
    r = lambda x: None if x is None else round(x, 4)  # noqa: E731
    return typ, r(p.nennwert), r(p.oben), r(p.unten), p.passung


def xcaf_abgleich(modell, eigene) -> tuple[int, int]:
    """(gleich, nur_xcaf): Masse als Mehrfachmenge von (Typ, Wert) vergleichen."""
    # CommonLabel = Hinweis ohne Mass, kein Vergleich
    xc = [p for p in lies_pmi_xcaf(modell) if p.art == MASS and p.semantisch and p.typ != "CommonLabel"]
    a = collections.Counter(_mass_schluessel(p) for p in xc)
    b = collections.Counter(_mass_schluessel(p) for p in eigene if p.art == MASS)
    gleich = sum((a & b).values())
    return gleich, sum(a.values()) - gleich


def auswerten(pfad: str) -> dict:
    m = lade_step(pfad)
    pmi = lies_pmi(m)
    ans = lies_ansichten(m, pmi)
    ref = referenz_zaehlung(m.datei)
    zeile = {"datei": os.path.basename(pfad), "zeit": m.ladezeit, "flaechen": len(m.flaechen),
             "zugeordnet": len(m.step_zu_flaeche), "ref": ref}
    for art in (MASS, TOLERANZ, BEZUG):
        liste = [p for p in pmi if p.art == art]
        mit_wert = [p for p in liste if (p.nennwert if art == MASS else p.wert) is not None] \
            if art != BEZUG else liste
        zeile[art] = (len(liste), len(mit_wert), sum(1 for p in liste if p.flaechen))
    zeile["xcaf"] = xcaf_abgleich(m, pmi)
    zeile["ansichten"] = (len(ans), sum(1 for a in ans if a.pmi_ids))
    zeile["pmi"] = pmi
    zeile["ans"] = ans
    return zeile


def tabelle(zeilen: list[dict]) -> str:
    kopf = ("| Datei | Laden s | Flächen (zugeordnet) | Maße gelesen/Datei, mit Wert, mit Fläche "
            "| Toleranzen gelesen/Datei, mit Wert, mit Fläche | Bezüge gelesen/Datei, mit Fläche "
            "| Maße = OCCT (abweichend) | Ansichten gelesen/Datei, mit PMI |\n"
            "|---|---|---|---|---|---|---|---|\n")
    out = [kopf]
    for z in zeilen:
        r = z["ref"]
        ma, to, be = z[MASS], z[TOLERANZ], z[BEZUG]
        out.append(
            f"| {z['datei'].replace('_asme1', '')} | {z['zeit']:.2f} | {z['flaechen']} ({z['zugeordnet']}) "
            f"| {ma[0]}/{r[MASS]}, {ma[1]}, {ma[2]} | {to[0]}/{r[TOLERANZ]}, {to[1]}, {to[2]} "
            f"| {be[0]}/{r[BEZUG]}, {be[2]} | {z['xcaf'][0]} ({z['xcaf'][1]}) "
            f"| {z['ansichten'][0]}/{r['ansichten']}, {z['ansichten'][1]} |\n")
    return "".join(out)


def summen(zeilen: list[dict]) -> str:
    s = collections.Counter()
    for z in zeilen:
        for art in (MASS, TOLERANZ, BEZUG):
            s[art + "_n"] += z[art][0]
            s[art + "_ref"] += z["ref"][art]
            s[art + "_wert"] += z[art][1]
            s[art + "_fl"] += z[art][2]
        s["xcaf_gleich"] += z["xcaf"][0]
        s["xcaf_ab"] += z["xcaf"][1]
    pz = lambda a, b: f"{100 * a / b:.0f} %" if b else "-"  # noqa: E731
    return (f"- Maße: {s['mass_n']} von {s['mass_ref']} gelesen, {pz(s['mass_wert'], s['mass_n'])} mit Wert, "
            f"{pz(s['mass_fl'], s['mass_n'])} mit Fläche; mit OCCT gleich: {s['xcaf_gleich']}, "
            f"abweichend: {s['xcaf_ab']}\n"
            f"- Toleranzen: {s['toleranz_n']} von {s['toleranz_ref']}, {pz(s['toleranz_wert'], s['toleranz_n'])} "
            f"mit Wert, {pz(s['toleranz_fl'], s['toleranz_n'])} mit Fläche\n"
            f"- Bezüge: {s['bezug_n']} von {s['bezug_ref']}, {pz(s['bezug_fl'], s['bezug_n'])} mit Fläche\n")


def details(z: dict) -> str:
    out = [f"\n### {z['datei']}\n\n| Nr | Art | Typ | Wert | Bezüge | Flächen | #ID |\n|---|---|---|---|---|---|---|\n"]
    for p in z["pmi"]:
        out.append(f"| {p.nummer} | {p.art} | {p.typ} | {p.wert_text().replace('|', '&#124;')} "
                   f"| {p.bezug_text().replace('|', '&#124;')} | {len(p.flaechen)} | {p.step_id} |\n")
    out.append("\n| Ansicht | Blickrichtung | PMI-Nummern |\n|---|---|---|\n")
    for a in z["ans"]:
        r = ", ".join(f"{c:.2f}" for c in a.richtung)
        out.append(f"| {a.name} | ({r}) | {', '.join(map(str, a.pmi_nummern)) or '–'} |\n")
    return "".join(out)


def main(argv):
    ordner = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else STANDARD
    det = argv[argv.index("--details") + 1] if "--details" in argv else "nist_ctc_01_asme1_ap242-e1.stp"
    dateien = sorted(glob.glob(os.path.join(ordner, "*.stp")) + glob.glob(os.path.join(ordner, "*.step")))
    zeilen = [auswerten(f) for f in dateien]
    text = ("# Machbarkeit – Tabelle (erzeugt von werkzeuge/machbarkeit.py)\n\n" + summen(zeilen) + "\n"
            + tabelle(zeilen))
    for z in zeilen:
        if z["datei"] == det:
            text += details(z)
    os.makedirs("docs", exist_ok=True)
    with open("docs/Machbarkeit_Tabelle.md", "w", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main(sys.argv)
