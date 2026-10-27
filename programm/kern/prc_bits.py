"""Bitstrom-Leser fuer PRC (ISO 14739-1 / Adobe PRC Format Specification).

PRC-Daten sind bitweise kodiert (hoechstwertiges Bit eines Bytes zuerst):
- Bit: ein Bit; Zeichen: 8 Bit.
- Vorzeichenlose Ganzzahl: Folge aus (1-Bit, 8-Bit-Byte), abgeschlossen durch ein 0-Bit, niederwertiges Byte zuerst.
- Ganzzahl: wie oben, danach Vorzeichenerweiterung auf 32 Bit.
- Double: Huffman-Code fuer haeufige Werte bzw. Exponenten, Vorzeichen, Mantisse mit Byte-Wiederholungen.
- Zeichenkette: Bit "nicht leer", Laenge, Zeichen.

Die Bit- und Double-Kodierung folgt dem LGPL-PRC-Code von Asymptote (prc/PRCbitStream.cc, prc/PRCTools/bitData.cc,
github.com/vectorgraphics/asymptote, LGPL 3; Leser von Orest Shardt, Double-Leser von Michail Vidiassov).
"""

from __future__ import annotations

import struct

from .prc_tabelle import DOUBLES, EXPONENTEN


class PrcFehler(Exception):
    pass


def _code_tabelle():
    """{(Bitanzahl, Bits): (ist_double, oberes Wort, unteres Wort)}."""
    tab = {(n, b): (True, hi, lo) for n, b, hi, lo in DOUBLES}
    for e, (n, b) in enumerate(EXPONENTEN):
        tab[(n, b)] = (False, 0x7FF80000 if e == 0x7FF else e << 20, 0)
    return tab


_CODES = _code_tabelle()
_LAENGEN = sorted({n for n, _ in _CODES})


class BitLeser:
    """Liest PRC-Grundtypen aus einem Bytepuffer."""

    def __init__(self, daten: bytes):
        self.daten = bytes(daten) + b"\0" * 16
        self.laenge = len(daten) * 8
        self.pos = 0
        self.name = ""  # aktueller Name (PRC "same name as current")

    def ende(self) -> bool:
        return self.pos >= self.laenge

    def bits(self, n: int) -> int:
        """n Bits (n <= 57) als Ganzzahl, erstes Bit hoechstwertig."""
        if self.pos + n > self.laenge:
            raise PrcFehler("Ende der Daten")
        b = self.pos >> 3
        wert = int.from_bytes(self.daten[b:b + 8], "big")
        wert = (wert >> (64 - (self.pos & 7) - n)) & ((1 << n) - 1)
        self.pos += n
        return wert

    def bit(self) -> bool:
        if self.pos >= self.laenge:
            raise PrcFehler("Ende der Daten")
        w = (self.daten[self.pos >> 3] >> (7 - (self.pos & 7))) & 1
        self.pos += 1
        return bool(w)

    def zeichen(self) -> int:
        return self.bits(8)

    def uint(self) -> int:
        wert, k = 0, 0
        while self.bit():
            wert |= self.bits(8) << (8 * k)
            k += 1
            if k > 8:
                raise PrcFehler("Ungueltige Ganzzahl")
        return wert

    def int(self) -> int:
        wert, k = 0, 0
        while self.bit():
            wert |= self.bits(8) << (8 * k)
            k += 1
            if k > 4:
                raise PrcFehler("Ungueltige Ganzzahl")
        if k and wert & (1 << (8 * k - 1)):
            wert -= 1 << (8 * k)
        return wert

    def text(self) -> str:
        if not self.bit():
            return ""
        n = self.uint()
        if n > (self.laenge - self.pos) // 8:
            raise PrcFehler("Zeichenkette zu lang")
        roh = bytes(self.bits(8) for _ in range(n))
        return roh.decode("utf-8", "replace")

    def double(self) -> float:
        code, n = 0, 0
        for laenge in _LAENGEN:
            code = (code << (laenge - n)) | self.bits(laenge - n)
            n = laenge
            treffer = _CODES.get((n, code))
            if treffer is not None:
                break
        else:
            raise PrcFehler("Ungueltiger Double-Code")
        ist_double, hi, lo = treffer
        if ist_double and n == 2 and code == 1:
            return 0.0
        negativ = self.bit()
        if not ist_double and self.bit():
            hi, lo = self._mantisse(hi)
        if negativ:
            hi |= 0x80000000
        return struct.unpack("<d", struct.pack("<II", lo, hi))[0]

    def _mantisse(self, hi: int) -> tuple[int, int]:
        """Mantisse: 4 obere Bits, dann Bytes 5..0 (je neu, Wiederholung oder Rest auffuellen)."""
        by = [0] * 8  # little endian, by[7] hoechstwertig
        by[7], by[6] = hi >> 24, (hi >> 16) & 0xFF
        by[6] |= self.bits(4)
        i = 5
        while i >= 0:
            if self.bit():
                by[i] = self.bits(8)
                i -= 1
                continue
            versatz = self.bits(3)
            if versatz == 0:
                by[0:i + 1] = [by[i + 1]] * (i + 1)
                break
            if versatz == 6:
                by[1:i + 1] = [by[i + 1]] * i
                by[0] = self.bits(8)
                break
            if i + versatz > 7:
                raise PrcFehler("Ungueltiger Double-Verweis")
            by[i] = by[i + versatz]
            i -= 1
        wert = int.from_bytes(bytes(by), "little")
        return wert >> 32, wert & 0xFFFFFFFF

    def uid(self) -> tuple:
        return tuple(self.uint() for _ in range(4))
