"""JT ueber den externen TKJT-Konverter: Versionserkennung, Meldungen, Ladeweg mit einem Ersatz-Konverter."""

import os
import stat
import sys

import pytest

from programm.kern import laden
from tests.conftest import WURZEL, pfad


def _jt(tmp_path, version: str) -> str:
    p = tmp_path / "teil.jt"
    p.write_bytes(f"Version {version} JT".ljust(80).encode("latin-1") + b"\0" * 64)
    return str(p)


def test_version_und_meldungen(tmp_path, monkeypatch):
    assert laden.jt_version(_jt(tmp_path, "9.5")) == (9, 5)
    (tmp_path / "kein.jt").write_bytes(b"irgendwas")
    with pytest.raises(laden.LadeFehler, match="Keine JT|No JT"):
        laden.lade_modell(str(tmp_path / "kein.jt"))
    monkeypatch.setenv("DG_JT2GLB", "")
    monkeypatch.setattr(laden, "jt_wandler", lambda: None)
    with pytest.raises(laden.LadeFehler, match="TKJT"):
        laden.lade_modell(_jt(tmp_path, "9.5"))


def test_ladeweg_mit_ersatz_konverter(tmp_path, monkeypatch):
    """Der Konverter schreibt eine GLB; 3DGmax laedt sie wie glTF und behaelt den JT-Pfad."""
    glb = pfad(os.path.join("formate", "baugruppe.glb"))
    skript = tmp_path / "jt2glb"
    skript.write_text(f"#!{sys.executable}\nimport shutil, sys\nshutil.copy({glb!r}, sys.argv[2])\n")
    skript.chmod(skript.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("DG_JT2GLB", str(skript))
    jt = _jt(tmp_path, "9.5")
    m = laden.lade_modell(jt)
    assert m.pfad == jt and len(m.flaechen) > 0 and laden.ist_netz(m)


def test_nist_jt10_wird_geladen():
    """Freie NIST-Datei (lokal, daten/jt): JT 10.5 ueber den TKJT-Fork mit JT-10-Lesen (packaging/jt/bauen.sh)."""
    p = os.path.join(WURZEL, "daten", "jt", "NIST mtc crada assembly.jt")
    if not os.path.isfile(p):
        pytest.skip("NIST-JT nicht vorhanden (lokal unter daten/jt)")
    assert laden.jt_version(p) == (10, 5)
    if laden.jt_wandler() is None:
        pytest.skip("JT-Konverter nicht gebaut (packaging/jt/bauen.sh)")
    m = laden.lade_modell(p)
    assert m.pfad == p and laden.ist_netz(m) and len(m.flaechen) >= 8


def test_fehlermeldung_ohne_tkjt_hinweise(tmp_path, monkeypatch):
    """Bricht der Konverter ab, nennt die Meldung den Code und die letzten echten Zeilen - nicht die vielen Hinweise
    von TKJT auf uebersprungene, unbekannte Elementtypen."""
    skript = tmp_path / "jt2glb"
    hinweis = "JtReader: unknown object type GUID 98134716-0010-0818-19-98-08-00-09-83-5d-5a, skipping element"
    skript.write_text(f"#!{sys.executable}\nimport sys\nfor _ in range(50):\n    print({hinweis!r}, file=sys.stderr)\n"
                      "print('Segment 7 kaputt', file=sys.stderr)\nsys.exit(3)\n")
    skript.chmod(skript.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("DG_JT2GLB", str(skript))
    with pytest.raises(laden.LadeFehler) as e:
        laden.lade_modell(_jt(tmp_path, "9.5"))
    assert "3" in str(e.value) and "Segment 7 kaputt" in str(e.value) and "skipping" not in str(e.value)
    assert laden.jt_meldung(hinweis + "\n" + hinweis) == "–"


def test_jt_per_drag_and_drop():
    from programm.ui.hauptfenster import ablegbar
    assert ablegbar("C:/Daten/Teil.JT") and ablegbar("a.stp") and ablegbar("p.3dgmax") and not ablegbar("x.txt")
    assert all(ablegbar("a" + e) for e in laden.ENDUNGEN)
