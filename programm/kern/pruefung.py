"""Pruefprotokoll eines Vergleichs mit Pruefsumme (SHA-256) – ausdruecklich keine qualifizierte Signatur."""

from __future__ import annotations

from ..i18n import tr

import datetime
import hashlib
import json
import os

ERGEBNISSE = ("freigegeben", "mit Auflagen", "nicht freigegeben")
_PRUEF = {"offen": "offen", "geprueft": "geprüft", "abgelehnt": "abgelehnt"}


def datei_hash(pfad: str) -> str:
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def protokoll(vergleich, pruefer: str, ergebnis: str, bemerkung: str = "", version: str = "") -> dict:
    daten = {
        "programm": f"3DGmax {version}".strip(),
        "zeitpunkt": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "pruefer": pruefer,
        "ergebnis": ergebnis,
        "bemerkung": bemerkung,
        "alt": {"datei": os.path.basename(vergleich.alt.pfad), "sha256": datei_hash(vergleich.alt.pfad)},
        "neu": {"datei": os.path.basename(vergleich.neu.pfad), "sha256": datei_hash(vergleich.neu.pfad)},
        "toleranz_mm": vergleich.toleranz,
        "suchweite_mm": vergleich.suchweite,
        "ausrichtung": {"methode": vergleich.ausrichtung.methode,
                        "matrix": [[round(x, 9) for x in z] for z in vergleich.ausrichtung.matrix.tolist()]},
        "aenderungen": [{"nr": a.nummer, "kategorie": a.kategorie, "status": a.status, "titel": a.titel,
                         "beschreibung": a.beschreibung, "pruefstatus": a.pruefstatus, "kommentar": a.kommentar}
                        for a in vergleich.aenderungen],
    }
    daten["pruefsumme_sha256"] = pruefsumme(daten)
    return daten


def pruefsumme(daten: dict) -> str:
    ohne = {k: v for k, v in daten.items() if k != "pruefsumme_sha256"}
    return hashlib.sha256(json.dumps(ohne, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def ist_unveraendert(daten: dict) -> bool:
    return daten.get("pruefsumme_sha256") == pruefsumme(daten)


def als_text(daten: dict) -> str:
    z = [f"{tr('Prüfprotokoll')} – {daten['programm']}", f"{tr('Zeitpunkt')}: {daten['zeitpunkt']}",
         f"{tr('Prüfer')}: {daten['pruefer']}", f"{tr('Ergebnis')}: {tr(daten['ergebnis'])}",
         f"{tr('Bemerkung')}: {daten['bemerkung']}", "",
         f"{tr('Alt')}: {daten['alt']['datei']}  SHA-256 {daten['alt']['sha256']}",
         f"{tr('Neu')}: {daten['neu']['datei']}  SHA-256 {daten['neu']['sha256']}",
         tr("Toleranz: {} mm, Suchweite: {} mm, Ausrichtung: {}").format(
             daten['toleranz_mm'], daten['suchweite_mm'], daten['ausrichtung']['methode']), "",
         f"{tr('Änderungen')}:"]
    for a in daten["aenderungen"]:
        z.append(f"  {a['nr']:3d}  [{tr(_PRUEF.get(a['pruefstatus'], a['pruefstatus']))}]  {a['titel']} – "
                 f"{a['beschreibung']}" + (f"  {tr('Kommentar')}: {a['kommentar']}" if a["kommentar"] else ""))
    z += ["", f"{tr('Prüfsumme')} (SHA-256): {daten['pruefsumme_sha256']}",
          tr("Hinweis: Prüfsumme zur Erkennung nachträglicher Änderungen, keine qualifizierte elektronische Signatur.")]
    return "\n".join(z)


def speichere(daten: dict, pfad_ohne_endung: str) -> tuple[str, str]:
    j, t = pfad_ohne_endung + ".json", pfad_ohne_endung + ".txt"
    with open(j, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
    with open(t, "w", encoding="utf-8") as f:
        f.write(als_text(daten))
    return j, t
