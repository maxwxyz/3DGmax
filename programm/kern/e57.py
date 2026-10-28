"""Punktwolken aus E57 (ASTM E2807) lesen, ohne Fremdbibliothek (ohne Qt).

Aufbau: 48 Byte Kopf (Signatur "ASTM-E57", Versionen, Laenge, Lage und Laenge des XML-Teils, Seitengroesse), alles
in Seiten zu 1024 Byte, davon 4 Byte CRC am Seitenende (physische Lage) - gelesen wird logisch ohne die CRC.
Im XML je Scan (data3D/vectorChild): Pose (Quaternion w x y z, Verschiebung) und die Punkte als CompressedVector mit
Prototyp der Felder (Float einfach/doppelt, Integer, ScaledInteger mit min/max/scale/offset). Die Binaersektion:
Kopf (Id 1, Laenge, Lage der Datenpakete), dann Datenpakete (Typ 1) mit je einem Bytestrom je Feld in
Prototyp-Reihenfolge; Index- (0) und Leerpakete (2) werden uebersprungen. Ganzzahlen sind bitgepackt (LSB zuerst,
Bitzahl aus max - min), ScaledInteger = (roh + min) * scale + offset. Kartesisch (cartesianX/Y/Z) oder sphaerisch
(sphericalRange/Azimuth/Elevation); ungueltige Punkte (cartesianInvalidState/sphericalInvalidState = 2) fallen weg.
Laengen in Metern laut Norm, Ergebnis in mm. Bilder (images2D) werden nicht gelesen.
"""

from __future__ import annotations

import math
import struct

import numpy as np
from lxml import etree

SEITE, CRC = 1024, 4
NUTZ = SEITE - CRC


class _Datei:
    def __init__(self, pfad: str):
        with open(pfad, "rb") as f:
            self.roh = f.read()
        if self.roh[:8] != b"ASTM-E57":
            raise ValueError("keine E57-Datei")
        _maj, _min, _laenge, self.xml_lage, self.xml_laenge, seite = struct.unpack("<IIQQQQ", self.roh[8:48])
        if seite != SEITE:
            raise ValueError(f"E57: Seitengroesse {seite} nicht unterstuetzt")

    def lies(self, physisch: int, anzahl: int) -> bytes:
        """anzahl logische Bytes ab der physischen Lage (CRC am Seitenende uebersprungen)."""
        out = bytearray()
        while len(out) < anzahl:
            in_seite = physisch % SEITE
            if in_seite >= NUTZ:  # in der CRC: zur naechsten Seite
                physisch += SEITE - in_seite
                continue
            stueck = min(NUTZ - in_seite, anzahl - len(out))
            out += self.roh[physisch:physisch + stueck]
            if physisch + stueck > len(self.roh):
                raise ValueError("E57: Datei zu kurz")
            physisch += stueck
            if physisch % SEITE == NUTZ:
                physisch += CRC
        return bytes(out)

    def weiter(self, physisch: int, logisch: int) -> int:
        """Physische Lage nach logisch Bytes ab physisch."""
        seite, rest = divmod(physisch, SEITE)
        lin = seite * NUTZ + rest + logisch
        s, r = divmod(lin, NUTZ)
        return s * SEITE + r


def _feld(e) -> dict:
    a = e.attrib
    art = a.get("type")
    if art == "Float":
        return {"art": "float", "bytes": 4 if a.get("precision") == "single" else 8}
    lo, hi = int(a.get("minimum", "0")), int(a.get("maximum", "0"))
    bits = max(0, math.ceil(math.log2(hi - lo + 1))) if hi > lo else 0
    return {"art": art, "min": lo, "bits": bits, "scale": float(a.get("scale", "1")),
            "offset": float(a.get("offset", "0"))}


def _werte(f: dict, daten: bytes, n: int) -> np.ndarray:
    if f["art"] == "float":
        return np.frombuffer(daten, "<f8" if f["bytes"] == 8 else "<f4", count=n).astype(float)
    if f["bits"] == 0:
        roh = np.zeros(n)
    else:
        b = f["bits"]
        bits = np.unpackbits(np.frombuffer(daten, np.uint8), bitorder="little")[:n * b].reshape(n, b)
        roh = bits.astype(np.int64) @ (np.int64(1) << np.arange(b, dtype=np.int64))
    wert = (roh + f["min"]).astype(float)
    return wert * f["scale"] + f["offset"] if f["art"] == "ScaledInteger" else wert


def _punkte(d: _Datei, cv, namen: list[str], felder: list[dict]) -> dict[str, np.ndarray]:
    n = int(cv.get("recordCount"))
    lage = int(cv.get("fileOffset"))
    kopf = d.lies(lage, 32)
    if kopf[0] != 1:
        raise ValueError("E57: unerwarteter Sektionskopf")
    _laenge, daten_lage, _index = struct.unpack("<QQQ", kopf[8:32])
    stroeme = [bytearray() for _ in felder]
    noetig = [n * f["bytes"] if f["art"] == "float" else math.ceil(n * f["bits"] / 8) for f in felder]
    p = daten_lage
    while any(len(s) < k for s, k in zip(stroeme, noetig)):
        h = d.lies(p, 6)
        typ, _flags, laenge_m1, anzahl = h[0], h[1], *struct.unpack("<HH", h[2:6])
        laenge = laenge_m1 + 1
        if typ == 1:
            paket = d.lies(p, laenge)
            groessen = struct.unpack(f"<{anzahl}H", paket[6:6 + 2 * anzahl])
            k = 6 + 2 * anzahl
            for i, g in enumerate(groessen):
                if i < len(stroeme):
                    stroeme[i] += paket[k:k + g]
                k += g
        elif typ not in (0, 2):
            raise ValueError(f"E57: unbekannter Pakettyp {typ}")
        p = d.weiter(p, laenge)
    return {name: _werte(f, bytes(s), n) for name, f, s in zip(namen, felder, stroeme)}


def _pose(scan, ns):
    r, t = np.eye(3), np.zeros(3)
    q = scan.find(f"{ns}pose/{ns}rotation")
    if q is not None:
        w, x, y, z = (float(q.findtext(f"{ns}{k}") or v) for k, v in (("w", 1), ("x", 0), ("y", 0), ("z", 0)))
        r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    v = scan.find(f"{ns}pose/{ns}translation")
    if v is not None:
        t = np.array([float(v.findtext(f"{ns}{k}") or 0) for k in "xyz"])
    return r, t


def lies(pfad: str) -> np.ndarray:
    """Alle gueltigen Punkte aller Scans in Weltlage (Pose angewandt), mm, Form (n, 3)."""
    d = _Datei(pfad)
    wurzel = etree.fromstring(d.lies(d.xml_lage, d.xml_laenge))
    ns = "{" + wurzel.nsmap[None] + "}" if None in wurzel.nsmap else ""
    teile = []
    for scan in wurzel.iterfind(f"{ns}data3D/{ns}vectorChild"):
        cv = scan.find(f"{ns}points")
        proto = cv.find(f"{ns}prototype") if cv is not None else None
        if proto is None or not int(cv.get("recordCount", "0")):
            continue
        namen = [etree.QName(e).localname for e in proto]
        felder = [_feld(e) for e in proto]
        w = _punkte(d, cv, namen, felder)
        if {"cartesianX", "cartesianY", "cartesianZ"} <= set(w):
            p = np.column_stack([w["cartesianX"], w["cartesianY"], w["cartesianZ"]])
            gut = w.get("cartesianInvalidState", np.zeros(len(p))) != 2
        elif {"sphericalRange", "sphericalAzimuth", "sphericalElevation"} <= set(w):
            r, az, el = w["sphericalRange"], w["sphericalAzimuth"], w["sphericalElevation"]
            p = np.column_stack([r * np.cos(el) * np.cos(az), r * np.cos(el) * np.sin(az), r * np.sin(el)])
            gut = w.get("sphericalInvalidState", np.zeros(len(p))) != 2
        else:
            continue
        rot, t = _pose(scan, ns)
        teile.append(p[gut] @ rot.T + t)
    if not teile:
        raise ValueError("E57: keine Punkte")
    return np.vstack(teile) * 1000.0
