"""Version erhoehen: 'unreleased' aus programm/CHANGELOG.json wird zur neuen Version (mit Datum);
CHANGELOG.md (englisch, fuer GitHub) und CHANGELOG_DE.md (deutsch) werden neu geschrieben.

Aufruf: pixi run python packaging/release.py minor|patch|major [--git]
--git: Commit und Tag v<version> anlegen (Push danach von Hand bzw. durch den Workflow).
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PFAD = os.path.join(WURZEL, "programm", "CHANGELOG.json")


def naechste(version: str, art: str) -> str:
    teile = [int(x) for x in version.split(".")] + [0, 0]
    major, minor, patch = teile[:3]
    if art == "major":
        return f"{major + 1}.0"
    if art == "minor":
        return f"{major}.{minor + 1}"
    return f"{major}.{minor}.{patch + 1}"


def markdown(daten: dict, sprache: str) -> str:
    kopf = "# Änderungshistorie" if sprache == "de" else "# Changelog"
    zeilen = [kopf, ""]
    for r in daten["releases"]:
        zeilen.append(f"## {r['version']} ({r.get('date', '')})")
        zeilen += [f"- {t}" for t in r.get(sprache, [])]
        zeilen.append("")
    return "\n".join(zeilen)


def main(argv):
    art = argv[1] if len(argv) > 1 else "minor"
    with open(PFAD, encoding="utf-8") as f:
        daten = json.load(f)
    offen = daten.get("unreleased", {"de": [], "en": []})
    if not offen.get("de"):
        sys.exit("Keine Einträge unter 'unreleased' – nichts zu veröffentlichen.")
    if len(offen["de"]) != len(offen.get("en", [])):
        sys.exit("Deutsche und englische Einträge sind unterschiedlich viele.")
    alt = daten["releases"][0]["version"] if daten["releases"] else "0.0"
    neu = naechste(alt, art)
    daten["releases"].insert(0, {"version": neu, "date": datetime.date.today().isoformat(),
                                 "de": offen["de"], "en": offen["en"]})
    daten["unreleased"] = {"de": [], "en": []}
    with open(PFAD, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
    for name, sprache in (("CHANGELOG.md", "en"), ("CHANGELOG_DE.md", "de")):
        with open(os.path.join(WURZEL, name), "w", encoding="utf-8") as f:
            f.write(markdown(daten, sprache))
    print(f"Version {alt} -> {neu}")
    if "--git" in argv:
        subprocess.run(["git", "add", PFAD, "CHANGELOG.md", "CHANGELOG_DE.md"], cwd=WURZEL, check=True)
        subprocess.run(["git", "commit", "-m", f"Version {neu}\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"],
                       cwd=WURZEL, check=True)
        subprocess.run(["git", "tag", f"v{neu}"], cwd=WURZEL, check=True)


if __name__ == "__main__":
    main(sys.argv)
