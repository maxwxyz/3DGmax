"""Projektdatei .3dgmax: ZIP mit projekt.json und den eingebetteten Modellen (zum Verschicken).

projekt.json:
  format, programm, typ ("modell" | "vergleich"), modelle {"modell"} bzw. {"alt", "neu"} (Dateinamen im ZIP),
  vergleich {toleranz, suchweite, aenderungen [{nr, titel, pruefstatus, kommentar}]}, messungen [...],
  kette {cp, glieder [...]} (Toleranzkette, optional)
Beim Oeffnen werden die Modelle in einen temporaeren Ordner entpackt; der Vergleich wird neu gerechnet
(deterministisch) und Pruefstatus/Kommentare werden ueber Nummer und Titel wieder zugeordnet.
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from dataclasses import asdict

from ..i18n import tr
from .messen import Messung

ENDUNG = ".3dgmax"
FORMAT = 1


def _eindeutig(namen: list[str]) -> list[str]:
    out, gesehen = [], set()
    for n in namen:
        basis, endung = os.path.splitext(n)
        kandidat, i = n, 2
        while kandidat in gesehen:
            kandidat = f"{basis}_{i}{endung}"
            i += 1
        gesehen.add(kandidat)
        out.append(kandidat)
    return out


def speichere(pfad: str, modell_pfad: str | None = None, vergleich=None, messungen: list | None = None,
              version: str = "", ansichten: list | None = None, kommentare: list | None = None,
              eigene_pmi: list | None = None, pmi_aenderungen: list | None = None, kette: tuple | None = None) -> str:
    """Modell oder Vergleich mit Pruefstand und Messungen als .3dgmax speichern."""
    if not pfad.lower().endswith(ENDUNG):
        pfad += ENDUNG
    daten = {"format": FORMAT, "programm": f"3DGmax {version}".strip(), "messungen":
             [asdict(m) for m in (messungen or [])],
             "ansichten": [_ansicht_json(a) for a in (ansichten or []) if getattr(a, "eigen", False)],
             "kommentare": [asdict(k) for k in (kommentare or [])],
             "eigene_pmi": [_pmi_json(p) for p in (eigene_pmi or [])],
             "pmi_aenderungen": list(pmi_aenderungen or [])}
    if kette is not None and kette[1]:  # (Cp der Kette, Glieder) der Toleranzkette
        daten["kette"] = {"cp": kette[0], "glieder": [asdict(g) for g in kette[1]]}
    if vergleich is not None:
        quellen = [vergleich.alt.pfad, vergleich.neu.pfad]
        alt, neu = _eindeutig([os.path.basename(q) for q in quellen])
        daten.update({"typ": "vergleich", "modelle": {"alt": alt, "neu": neu},
                      "vergleich": {"toleranz": vergleich.toleranz, "suchweite": vergleich.suchweite,
                                    "aenderungen": [{"nr": a.nummer, "titel": a.titel, "pruefstatus": a.pruefstatus,
                                                     "kommentar": a.kommentar} for a in vergleich.aenderungen]}})
        dateien = {alt: quellen[0], neu: quellen[1]}
    else:
        name = os.path.basename(modell_pfad)
        daten.update({"typ": "modell", "modelle": {"modell": name}})
        dateien = {name: modell_pfad}
    with zipfile.ZipFile(pfad, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("projekt.json", json.dumps(daten, ensure_ascii=False, indent=1))
        for name, quelle in dateien.items():
            z.write(quelle, f"modelle/{name}")
    return pfad


def lade(pfad: str, ziel: str | None = None) -> dict:
    """Projekt lesen; Modelle werden entpackt, die Pfade stehen unter 'pfade'."""
    ziel = ziel or tempfile.mkdtemp(prefix="3dgmax_")
    with zipfile.ZipFile(pfad) as z:
        daten = json.loads(z.read("projekt.json").decode("utf-8"))
        if daten.get("format", 0) > FORMAT:
            raise ValueError(tr("Projekt stammt aus einer neueren Version von 3DGmax"))
        for name in z.namelist():
            if name.startswith("modelle/") and not name.endswith("/"):
                sicher = os.path.basename(name)  # keine Pfade aus dem ZIP uebernehmen
                with open(os.path.join(ziel, sicher), "wb") as f:
                    f.write(z.read(name))
    daten["pfade"] = {k: os.path.join(ziel, v) for k, v in daten["modelle"].items()}
    daten["messungen"] = [Messung(**m) for m in daten.get("messungen", [])]
    from .ansichten import Ansicht
    from .kommentare import von_dict
    daten["kommentare"] = [von_dict(k) for k in daten.get("kommentare", [])]
    daten["eigene_pmi"] = [_pmi_von(p) for p in daten.get("eigene_pmi", [])]
    if daten.get("kette"):
        from .toleranzkette import Glied
        daten["kette"]["glieder"] = [Glied(**{**g, "flaechen": tuple(g.get("flaechen", ()))})
                                     for g in daten["kette"]["glieder"]]
    daten["ansichten"] = [Ansicht(**{**a, "pmi_ids": set(a.get("pmi_ids", [])), "ort": tuple(a["ort"]),
                                     "richtung": tuple(a["richtung"]), "oben": tuple(a["oben"])})
                          for a in daten.get("ansichten", [])]
    return daten


def _pmi_json(p) -> dict:
    d = asdict(p)
    d["flaechen"] = sorted(d["flaechen"])
    return d


def _pmi_von(d: dict):
    from .pmi import BezugsRef, Pmi
    d = dict(d)
    d["flaechen"] = set(d.get("flaechen", []))
    d["bezuege"] = [BezugsRef(**b) for b in d.get("bezuege", [])]
    return Pmi(**d)


def _ansicht_json(a) -> dict:
    d = asdict(a)
    d["pmi_ids"] = sorted(d["pmi_ids"])
    return d


def uebernimm_pruefstand(vergleich, gespeichert: list[dict]) -> int:
    """Pruefstatus und Kommentare auf einen neu gerechneten Vergleich uebertragen; Anzahl der Treffer."""
    nach_schluessel = {(g["nr"], g["titel"]): g for g in gespeichert}
    nach_titel = {}
    for g in gespeichert:
        nach_titel.setdefault(g["titel"], []).append(g)
    treffer = 0
    for a in vergleich.aenderungen:
        g = nach_schluessel.get((a.nummer, a.titel)) or (nach_titel.get(a.titel) or [None])[0]
        if g is not None:
            a.pruefstatus, a.kommentar = g["pruefstatus"], g["kommentar"]
            treffer += 1
    return treffer
