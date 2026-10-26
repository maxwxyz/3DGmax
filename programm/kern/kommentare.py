"""Kommentare und Aenderungsvorschlaege an Flaechen, PMI oder Stellen im Modell (ohne Qt).

Ein Kommentar haengt an einem Ort (Punkt im Modell, fuer die Markierung) und optional an Flaechen und PMI-Nummern.
Gespeichert im Projekt (.3dgmax), exportiert als CSV und in Berichten.
"""

from __future__ import annotations

import csv
import datetime
import getpass
import io
from dataclasses import asdict, dataclass, field

from ..i18n import tr

ART = {"kommentar": "Kommentar", "vorschlag": "Änderungsvorschlag", "frage": "Frage"}
STATUS = {"offen": "offen", "erledigt": "erledigt"}


@dataclass
class Kommentar:
    nummer: int
    text: str
    ort: tuple[float, float, float]
    art: str = "kommentar"
    status: str = "offen"
    autor: str = ""
    datum: str = ""
    flaechen: list[int] = field(default_factory=list)
    pmi: list[int] = field(default_factory=list)  # PMI-Nummern

    @staticmethod
    def neu(nummer: int, text: str, ort, art: str = "kommentar", flaechen=(), pmi=()) -> "Kommentar":
        try:
            autor = getpass.getuser()
        except Exception:  # noqa: BLE001 - ohne Benutzername weiter
            autor = ""
        return Kommentar(nummer, text, tuple(float(x) for x in ort), art, "offen", autor,
                         datetime.datetime.now().isoformat(timespec="minutes"), sorted(flaechen), sorted(pmi))


def als_dict(k: Kommentar) -> dict:
    return asdict(k)


def von_dict(d: dict) -> Kommentar:
    d = dict(d)
    d["ort"] = tuple(d.get("ort", (0.0, 0.0, 0.0)))
    return Kommentar(**d)


SPALTEN = ("Nr", "Art", "Status", "Text", "Autor", "Datum", "PMI", "Flächen", "Ort (mm)")


def zeilen(liste: list[Kommentar]) -> list[list[str]]:
    return [[str(k.nummer), tr(ART.get(k.art, k.art)), tr(STATUS.get(k.status, k.status)), k.text, k.autor, k.datum,
             ", ".join(str(n) for n in k.pmi), str(len(k.flaechen)), "{:.2f}, {:.2f}, {:.2f}".format(*k.ort)]
            for k in liste]


def als_csv(liste: list[Kommentar]) -> str:
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";")
    w.writerow([tr(s) for s in SPALTEN])
    w.writerows(zeilen(liste))
    return puffer.getvalue()
