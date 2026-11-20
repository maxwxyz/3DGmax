"""PDF-Blatt in Leselage, mit Fundstellen aus Schrift und gezeichneten Toleranzrahmen."""

from functools import lru_cache
import zlib

import numpy as np
from scipy import ndimage

from . import pmi_strichschrift as schrift
from .pmi import MASS, TOL_SYMBOL
from .zeichnungsabgleich import Blattangabe, lese_angabe


@lru_cache(maxsize=1)
def _vorlagen():
    from .zeichnung_schriftmuster import MUSTER
    vorlagen = list(schrift._vorlagen())
    for z, varianten in MUSTER.items():
        for bits in varianten:
            bild = np.unpackbits(np.frombuffer(zlib.decompress(bytes.fromhex(bits)), np.uint8)).reshape(32, 32) > 0
            vorlagen.append((z, bild, ndimage.distance_transform_edt(~bild)))
    return vorlagen


def _zellen(mask):
    # Das umschlossene Weiss beruehrt die vier durchlaufenden Raender einer Rahmenzelle.
    labels, _ = ndimage.label(~mask)
    zellen = []
    for y, x in ndimage.find_objects(labels):
        l, r, t, b = x.start, x.stop, y.start, y.stop
        if min(b-t, r-l) < 5 or min(b-t, r-l) > 90 or max(b-t, r-l) > 1080:
            continue
        if l == 0 or t == 0 or r >= mask.shape[1] or b >= mask.shape[0]:
            continue
        if min(mask[t-1, x].mean(), mask[b, x].mean(), mask[y, l-1].mean(), mask[y, r].mean()) > .88:
            zellen.append((l, t, r, b))
    return zellen


def _zellgruppen(rechtecke):
    # Nur Faecher mit passender Groesse in der jeweiligen Leserichtung.
    zellen = [(l,t,r,b) for l,t,r,b in rechtecke if 7 <= b-t <= 90 and 5 <= r-l <= 12*(b-t)]
    nach_anfang = {}
    for l, t, r, b in zellen:
        nach_anfang.setdefault((l, t), []).append((l, t, r, b))
    verbraucht = set()
    for zelle in sorted(zellen):
        if zelle in verbraucht:
            continue
        gruppe = [zelle]
        while True:
            l, t, r, b = gruppe[-1]
            nachbarn = [z for x in range(r, r+5) for y in range(t-2, t+3)
                        for z in nach_anfang.get((x, y), ()) if abs(z[3]-b) <= 2 and z not in verbraucht]
            if len(nachbarn) != 1:
                break
            gruppe.extend(nachbarn)
            verbraucht.update(nachbarn)
        yield gruppe


def _mehrzeilig(gruppen, lies_zelle):
    # Zwei verbundene Zeilen koennen Segmente derselben Spezifikation sein.
    unten = {}
    verbunden = set()
    for i, gruppe in enumerate(gruppen):
        unten.setdefault(gruppe[0][3], []).append(i)
    for i, gruppe in enumerate(gruppen):
        l, t = gruppe[0][:2]
        for y in range(t-4, t+1):
            for j in unten.get(y, ()):
                andere = gruppen[j]
                if (max(len(gruppe), len(andere)) >= 2
                        and any(abs(a[0]-b[0]) <= 2 for a in gruppe[:2] for b in andere[:2])
                        and min(gruppe[-1][2], andere[-1][2]) > l+4):
                    zeichen = {lies_zelle(gruppe[0]), lies_zelle(andere[0])}
                    if len(zeichen) == 2 and zeichen.issubset(TOL_SYMBOL.values()):
                        continue
                    verbunden.update((i, j))
    return verbunden


def _gedreht(z, k, w, h):
    l, t, r, b = z
    return (z, (t, w-r, b, w-l), (w-r, h-b, w-l, h-t), (h-b, l, h-t, r))[k]


def _box(punkte):
    x, y = np.array(punkte).T
    return float(x.min()), float(y.min()), float(x.max()), float(y.max())


def _zeile(mask):
    zeichen = schrift._bildzeichen(mask)
    if not zeichen:
        return ""
    unten = max(box[3] for _, box in zeichen)
    hoehe = unten - min(box[1] for _, box in zeichen)
    punkt = next(bits for z, bits, _ in _vorlagen() if z == ".")
    for i, (_, (l, t, r, b)) in enumerate(zeichen):
        if (b-t < .34 * hoehe and b >= unten - .20 * hoehe and .6 <= (r-l)/(b-t) <= 1.4
                and mask[t:b, l:r].mean() > .55):
            zeichen[i] = punkt, (l, t, r, b)
    return schrift._lies_zeile(zeichen, _vorlagen())


class Zeichnungsblatt:
    def __init__(self, doc, nummer):
        self.nummer = nummer
        self.seite = doc[nummer]
        self.breite, self.hoehe = self.seite.get_size()
        self.bitmap = self.seite.render(scale=1900 / max(self.breite, self.hoehe), rev_byteorder=True)
        self.bild = self.bitmap.to_numpy()
        self.text = self.seite.get_textpage()
        self.koordinaten = self.bitmap.get_posconv(self.seite)
        self.textbereiche = list(self._textzeilen())

    def _textzeilen(self):
        from pypdfium2 import raw
        h, w = self.bild.shape[:2]
        raster = np.array([w, h, w, h])
        buchstaben, punkte = [], []
        letzte_box = None
        anzahl = self.text.count_chars()
        for i in range(anzahl + 1):
            z = chr(raw.FPDFText_GetUnicode(self.text, i)) if i < anzahl else "\n"
            box = None
            if not z.isspace():
                l, b, r, t = self.text.get_charbox(i)
                box = _box([self.koordinaten.to_bitmap(l, b), self.koordinaten.to_bitmap(r, t)])
            getrennt = z in "\r\n"
            if box and letzte_box:
                l, t, r, b = letzte_box
                x, y, x2, y2 = box
                abstand = max(l-x2, x-r, t-y2, y-b)
                getrennt = abstand > 2 * max(r-l, b-t, x2-x, y2-y, 1)
            if getrennt and punkte:
                yield tuple(np.clip(_box(punkte) / raster, 0., 1.)), "".join(buchstaben).strip()
                buchstaben, punkte, letzte_box = [], [], None
            if box:
                punkte.extend([box[:2], box[2:]])
                letzte_box = box
            if z not in "\r\n":
                buchstaben.append(z)

    def schliesse(self):
        self.text.close()
        self.bitmap.close()
        self.seite.close()

    def _pdftext(self, box):
        l, t, r, b = box
        return "\n".join(text for (x, y, x2, y2), text in self.textbereiche
                         if l <= x and t <= y and x2 <= r and y2 <= b)

    def ausschnitt(self, box, max_breite, max_hoehe, grau=False):
        l, t, r, b = box
        dx, dy = (r - l) * self.breite, (b - t) * self.hoehe
        if min(dx, dy) <= 0:
            return None
        skala = min(max_hoehe / dy, max_breite / dx, 100000 / max(self.breite, self.hoehe))
        if min(dx, dy) * skala < 2:
            return None
        crop = (l * self.breite, (1-b) * self.hoehe, (1-r) * self.breite, t * self.hoehe)
        return self.seite.render(scale=skala, crop=crop, grayscale=grau, rev_byteorder=not grau)

    def _mask(self, box, drehung, hoehe):
        ziel = (hoehe, 1600) if drehung % 2 else (1600, hoehe)
        bitmap = self.ausschnitt(box, *ziel, grau=True)
        if bitmap is None:
            return None
        try:
            mask = bitmap.to_numpy().reshape(bitmap.height, bitmap.width) < 185
            return np.rot90(mask, drehung)
        finally:
            bitmap.close()

    def lies(self, box, rahmenfach=False, drehung=0):
        text = self._pdftext(box)
        if text:
            return text
        for hoehe in ((72, 60) if rahmenfach else (72,)):
            wort = self._bildtext(box, rahmenfach, drehung, hoehe)
            if wort:
                return wort
        return ""

    def _bildtext(self, box, rahmenfach, drehung, hoehe):
        mask = self._mask(box, drehung, hoehe)
        if mask is None or not mask.any():
            return ""
        if rahmenfach:
            # Beim Vergroessern kann eine duenne Zellwand wieder in den Innenausschnitt fallen.
            rand = max(1, round(mask.shape[0] * .07))
            def wand(bild):
                voll = np.flatnonzero(bild[:rand].mean(axis=1) > .85)
                return int(voll[-1]) + 2 if len(voll) else 1
            h, w = mask.shape
            mask = mask[wand(mask):h-wand(mask[::-1]), wand(mask.T):w-wand(mask.T[::-1])]
        if not mask.size:
            return ""
        return _zeile(mask) or schrift._gestapelt(mask)

    def _rahmen(self, zellen, drehung, w, h):
        raster = np.array([w, h, w, h])
        original = {_gedreht(z, drehung, w, h): z for z in zellen}
        gruppen = list(_zellgruppen(original))

        @lru_cache(maxsize=None)
        def lies_zelle(zelle):
            return self.lies(tuple(original[zelle] / raster), rahmenfach=True, drehung=drehung)

        verbunden = _mehrzeilig(gruppen, lies_zelle)
        for i, gruppe in enumerate(gruppen):
            if len(gruppe) > 6 or (len(gruppe) == 1 and (drehung or i in verbunden)):
                continue
            punkte = [original[z][:2] for z in gruppe] + [original[z][2:] for z in gruppe]
            box = tuple(_box(punkte) / raster)
            if any(l < box[0] and box[2] < r and t < box[1] and box[3] < b
                   for (l, t, r, b), _ in self.textbereiche):
                continue
            text = lies_zelle(gruppe[0])
            grundmass = False
            if len(gruppe) > 1:
                if text not in TOL_SYMBOL.values():
                    continue
                text = " | ".join([text] + [lies_zelle(z) or "?" for z in gruppe[1:]])
                if i in verbunden:
                    text += " | …"
            elif len(text) == 1 and text in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                text = f"[{text}]"
            else:
                p = lese_angabe(text, 1.)
                if p is None or p.art != MASS:
                    continue
                grundmass = True
            yield Blattangabe(self.nummer, box, text, grundmass)

    def fundstellen(self):
        h, w = self.bild.shape[:2]
        zellen = _zellen(self.bild.min(axis=2) < 195)
        rahmen, einzeln = {}, []
        for k in range(4):
            for a in self._rahmen(zellen, k, w, h):
                if "|" not in a.text:
                    einzeln.append(a)
                elif a.box in rahmen and rahmen[a.box].text != a.text:
                    rahmen[a.box].text = "?"  # Mehrere moegliche Leserichtungen.
                else:
                    rahmen[a.box] = a

        def innerhalb(box):
            x, y = (box[0]+box[2])/2, (box[1]+box[3])/2
            return any(l <= x <= r and t <= y <= b for l, t, r, b in rahmen)

        for a in einzeln:
            if not innerhalb(a.box):
                rahmen[a.box] = a
        for box, text in self.textbereiche:
            if not innerhalb(box) and lese_angabe(text, 1.) is not None:
                rahmen[box] = Blattangabe(self.nummer, box, text)
        return sorted(rahmen.values(), key=lambda a: (a.box[1], a.box[0]))
