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
