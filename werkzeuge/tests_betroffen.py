"""Nur die Tests ausfuehren, die von den geaenderten Dateien betroffen sind (statt der ganzen Suite).

    pixi run test-betroffen                 # Aenderungen im Arbeitsbaum gegen HEAD
    pixi run test-betroffen -- --seit main  # alle Aenderungen seit einem Stand
    pixi run test-betroffen -- --zeigen     # nur auflisten
    pixi run test-betroffen -- --schnell    # ohne langsame Tests (Markierung 'langsam', ueber 30 s)

Auswahl: je geaendertem Modul programm/**/name.py die Testfunktionen, deren Quelltext 'name' erwaehnt; Hauptfenster
und 3D-Ansicht betreffen alle Oberflaechentests; Uebersetzung und Anleitungen den Uebersetzungs- und Anleitungstest;
geaenderte Testdateien laufen ganz. Langsame Tests (Markierung 'langsam') laufen mit, wenn sie betroffen sind,
ausser mit --schnell.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(WURZEL, "tests")
# Module, die praktisch alle Tests einer Datei betreffen (Fixtures bauen das Fenster bzw. laden Modelle)
BREIT = {"hauptfenster": ["tests/test_gui.py"], "ansicht3d": ["tests/test_gui.py", "tests/test_bildschirm.py"],
         "laden": ["tests/test_kern.py", "tests/test_gui.py"], "p21": ["tests/test_kern.py"],
         "pmi_lesen": ["tests/test_kern.py"], "lader": ["tests/test_gui.py"], "thema": ["tests/test_gui.py"]}
FEST = {"programm/i18n_en.json": ["uebersetzung"], "programm/Anleitung.html": ["anleitung"],
        "programm/Manual.html": ["anleitung"], "programm/CHANGELOG.json": ["version"],
        "werkzeuge/tr_texte.py": ["uebersetzung"]}


def geaendert(seit: str | None) -> list[str]:
    def git(*args):
        return subprocess.run(["git", *args], cwd=WURZEL, capture_output=True, text=True).stdout.split()
    dateien = set(git("diff", "--name-only", seit or "HEAD"))
    dateien |= set(git("ls-files", "--others", "--exclude-standard"))
    return sorted(dateien)


def _testfunktionen():
    """(Datei, Name, Quelltext) aller Testfunktionen."""
    for datei in sorted(os.listdir(TESTS)):
        if not (datei.startswith("test_") and datei.endswith(".py")):
            continue
        text = open(os.path.join(TESTS, datei), encoding="utf-8").read()
        for k in ast.parse(text).body:
            if isinstance(k, ast.FunctionDef) and k.name.startswith("test_"):
                yield f"tests/{datei}", k.name, ast.get_source_segment(text, k) or ""


def auswahl(dateien: list[str]) -> list[str]:
    """pytest-Ziele (Dateien oder Datei::Test) zu den geaenderten Dateien."""
    ziele, namen, stichworte = set(), set(), set()
    for d in dateien:
        if d.startswith("tests/test_") and d.endswith(".py"):
            ziele.add(d)
        elif d in FEST:
            stichworte |= set(FEST[d])
        elif d.startswith("programm/") and d.endswith(".py"):
            name = os.path.splitext(os.path.basename(d))[0]
            if name in BREIT:
                ziele |= set(BREIT[name])
            elif name != "__init__":
                namen.add(name)
    for datei, test, quelle in _testfunktionen():
        if datei in ziele:
            continue
        if any(re.search(rf"\b{re.escape(n)}\b", quelle) for n in namen) or any(s in test for s in stichworte):
            ziele.add(f"{datei}::{test}")
    return sorted(ziele)


def main(argv: list[str]) -> int:
    seit = argv[argv.index("--seit") + 1] if "--seit" in argv else None
    dateien = geaendert(seit)
    ziele = auswahl(dateien)
    print(f"{len(dateien)} geänderte Dateien, {len(ziele)} Testziele", flush=True)
    for z in ziele:
        print("  ", z)
    if "--zeigen" in argv or not ziele:
        return 0
    auswahl_m = ["-m", "not langsam"] if "--schnell" in argv else []
    return subprocess.run([sys.executable, "-m", "pytest", "-q", *auswahl_m, *ziele], cwd=WURZEL).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
