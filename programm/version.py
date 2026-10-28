"""Programmversion aus der Aenderungshistorie.

Quelle ist CHANGELOG.json: "unreleased" sammelt die Eintraege seit der letzten Version (deutsch und englisch),
"releases" die veroeffentlichten Versionen (neueste zuerst).
"""

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
