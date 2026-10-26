"""Programmversion und Aenderungshistorie.

Quelle ist CHANGELOG.json: "unreleased" sammelt die Eintraege seit der letzten Version (deutsch und englisch),
"releases" die veroeffentlichten Versionen (neueste zuerst).
"""

import html
import json
import os
import sys

HIER = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(HIER, "CHANGELOG.json")


def changelog() -> dict:
    try:
        with open(CHANGELOG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"unreleased": {"de": [], "en": []}, "releases": []}


def _version() -> str:
    rel = changelog().get("releases") or []
    return rel[0]["version"] if rel else "0.0"


VERSION = _version()


def versions_schluessel(v) -> tuple:
    try:
        return tuple(int(x) for x in str(v).split("."))
    except ValueError:
        return (0,)


def datum(iso: str, sprache: str = "de") -> str:
    try:
        j, m, t = iso.split("-")
        return f"{int(t)}.{int(m)}.{j}" if sprache == "de" else iso
    except (AttributeError, ValueError):
        return iso or ""


def aenderungen_html(sprache: str = "de", seit=None, unveroeffentlicht: bool = True) -> str:
    """Aenderungshistorie als HTML ("Was ist neu"); seit = nur Versionen neuer als diese."""
    daten = changelog()
    kopf = {"de": ("Version {} vom {}", "In Arbeit (noch nicht veröffentlicht)"),
            "en": ("Version {} of {}", "In progress (not released yet)")}["en" if sprache == "en" else "de"]
    bloecke = []
    if unveroeffentlicht and daten.get("unreleased", {}).get(sprache):
        bloecke.append((kopf[1], daten["unreleased"][sprache]))
    for r in daten.get("releases", []):
        if seit is not None and versions_schluessel(r["version"]) <= versions_schluessel(seit):
            continue
        bloecke.append((kopf[0].format(r["version"], datum(r.get("date", ""), sprache)), r.get(sprache) or []))
    out = []
    for titel, punkte in bloecke:
        out.append(f"<h3>{html.escape(titel)}</h3><ul>")
        out += [f"<li>{html.escape(t)}</li>" for t in punkte]
        out.append("</ul>")
    return "\n".join(out)
