"""PDF-Blatt in Leselage, mit Fundstellen aus Schrift und gezeichneten Toleranzrahmen."""

from functools import cached_property, lru_cache
import zlib

import numpy as np
from scipy import ndimage

from . import pmi_strichschrift as schrift
from .pmi import MASS, TOL_SYMBOL
from .zeichnungsabgleich import Blattangabe, lese_angabe, musteranzahl


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


def _geneigte_angabe(mask):
    """Schreibachse einer frei markierten Masszahl suchen, beide Leserichtungen pruefen."""
    y, x = np.nonzero(mask)
    if len(x) < 20:
        return ""
    punkte = np.column_stack((x, y)).astype(float)
    punkte -= punkte.mean(axis=0)
    _, basis = np.linalg.eigh(punkte.T @ punkte)
    quer, laengs = basis.T
    if np.ptp(punkte @ laengs) < 1.8 * np.ptp(punkte @ quer):
        return ""
    grad = np.rad2deg(np.arctan2(laengs[1], laengs[0]))
    grad = (grad + 90) % 180 - 90
    # Waagerechte Beschriftungen sind bereits in der normalen Zeilenlesung behandelt.
    if abs(grad) < 5:
        return ""
    from scipy.spatial import ConvexHull, QhullError
    try:
        rand = punkte[ConvexHull(punkte).vertices]
    except QhullError:
        return ""
    winkel = grad + np.arange(-10, 10.1, .5)
    rad = np.deg2rad(winkel)
    hoehen = np.ptp(rand @ np.array([-np.sin(rad), np.cos(rad)]), axis=0)
    # In einer Zeile liegen die meisten Zeichen auf gemeinsamer Grundlinie.
    # Gleichwertige Lesarten (z. B. 66 / 99) koennen nur am Original geklaert werden.
    gelesen = {}
    for i in np.argsort(hoehen)[:10]:
        gedreht = ndimage.rotate(mask, winkel[i], order=0, prefilter=False)
        ys, xs = np.nonzero(gedreht)
        if not len(ys):
            continue
        zeile = gedreht[ys.min():ys.max()+1, xs.min():xs.max()+1]
        if zeile.shape[0] < 5 or zeile.shape[1] > 65 * zeile.shape[0]:
            continue
        for bild in (zeile, zeile[::-1, ::-1]):
            reduziert = ndimage.zoom(bild, 30 / bild.shape[0], order=0, prefilter=False)
            wort = _zeile(reduziert)
            if wort and lese_angabe(wort, 1.) is not None:
                gelesen.setdefault(wort, set()).add(i)
                if len(gelesen) > 1:
                    return ""
    return next((wort for wort, lagen in gelesen.items() if len(lagen) >= 2), "")


def _einzelzeichen_verbinden(zeilen, groesse):
    """PDFium kann jeden Buchstaben einer einzigen Masszeile als eigene Textzeile liefern."""
    h, w = groesse
    gruppe = []
    def abgeschlossen():
        boxen, teile = zip(*gruppe)
        box = (boxen[0][0], min(q[1] for q in boxen), boxen[-1][2], max(q[3] for q in boxen))
        return box, "".join(teile)

    for box, text in zeilen:
        if len(text) != 1:
            if gruppe:
                yield abgeschlossen()
                gruppe.clear()
            yield box, text
            continue
        leerzeichen = False
        if gruppe:
            letzte = gruppe[-1][0]
            abstand = (box[0]-letzte[2])*w
            hoehe = max(zeilenhoehe, (box[3]-box[1])*h)
            if not (-.12*hoehe <= abstand <= .85*hoehe and box[0] > letzte[0]
                    and abs(box[3]-basis)*h <= .32*hoehe):
                yield abgeschlossen()
                gruppe.clear()
            else:
                leerzeichen = abstand > .45*hoehe
        if not gruppe:
            zeilenhoehe, basis = (box[3]-box[1])*h, box[3]
        else:
            zeilenhoehe = hoehe
        gruppe.append((box, (" " if leerzeichen else "") + text))
    if gruppe:
        yield abgeschlossen()


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
        zeilen = ((q, text) for q, text in self.textbereiche
                  if l <= q[0] and t <= q[1] and q[2] <= r and q[3] <= b)
        return "\n".join(text for _, text in _einzelzeichen_verbinden(zeilen, self.bild.shape[:2]))

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

    def durchmesseranfang(self, box):
        """Die obere Zeile muss unmittelbar mit einem Durchmessersymbol und einer Zahl beginnen."""
        mask = self._mask(box, 0, 72)
        if mask is None:
            return False
        zeichen = schrift._bildzeichen(mask)
        if len(zeichen) < 2 or schrift._lies_zeile(zeichen[:1], _vorlagen()) != "⌀":
            return False
        for i in range(1, min(4, len(zeichen))):
            wort = schrift._lies_zeile(zeichen[i:i+1], _vorlagen())
            if wort.isdecimal():
                return True
            # Ein vorangestellter Dezimalpunkt liegt unter der Zeichenmitte.
            _, (_, y, _, u) = zeichen[i]
            _, (_, oben, _, unten) = zeichen[0]
            if y < (oben+unten)/2 or u-y > .36*(unten-oben):
                return False
        return False

    def lies(self, box, rahmenfach=False, drehung=0):
        text = self._pdftext(box)
        if text:
            return text
        for hoehe in ((72, 60) if rahmenfach else (72,)):
            wort = self._bildtext(box, rahmenfach, drehung, hoehe)
            if wort:
                return wort
        if not rahmenfach:
            bitmap = self.ausschnitt(box, 520, 520, grau=True)
            if bitmap is not None:
                try:
                    return _geneigte_angabe(bitmap.to_numpy().reshape(bitmap.height, bitmap.width) < 185)
                finally:
                    bitmap.close()
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

    def _schriftboxen(self, ort, sinn, achse):
        # Die Streifenhoehe variiert mit Blattmassstab und Schriftgrad. Schrift darf oben und
        # unten nicht angeschnitten sein. Von rechts kommende Hinweise in Leserichtung zurueckrechnen.
        bild = np.rot90(self.bild, achse)
        h, w = bild.shape[:2]
        if achse:
            ort = (ort[1], h-1-ort[0])
        x = int(np.ceil(ort[0]))+2 if sinn > 0 else int(np.floor(ort[0]))-2
        for halbe in (7, 9, 12, 16, 22, 30):
            y = round(ort[1])-halbe
            if y < 0 or y+2*halbe >= h:
                continue
            l, r = (x, min(w, x+38*halbe)) if sinn > 0 else (max(0, x-38*halbe), x)
            if not 0 <= l < r <= w:
                continue
            mask = bild[y:y+2*halbe+1, l:r].min(axis=2) < 245
            if sinn < 0:
                mask = mask[:, ::-1]
            gruppen = list(schrift._gruppen(mask))
            if not gruppen or not 1 <= gruppen[0][0] <= 1.5*halbe:
                continue
            von, bis = gruppen[0]
            for a,b in gruppen[1:]:
                if a-bis > 2.1*halbe:
                    break
                bis = b
            if bis == gruppen[0][1] or bis+2 >= mask.shape[1]:
                continue
            ys = np.nonzero(mask[:, von:bis])[0]
            oben, unten = ys.min(), ys.max()+1
            if oben < 1 or unten >= mask.shape[0] or unten-oben < 5:
                continue
            x1, x2 = (l+von, l+bis) if sinn > 0 else (r-bis, r-von)
            box = (max(0,x1-1)/w, (y+oben-1)/h, min(w,x2+1)/w, (y+unten+1)/h)
            yield _gedreht(box, -achse % 4, 1, 1)

    def freie_masszeile(self, ort, sinn, achse, belegt):
        boxen = list(self._schriftboxen(ort, sinn, achse))
        if not boxen:
            return None
        # Nur die vollstaendige Zeile lesen. Ein schmalerer Ausschnitt kann einen Zusatz verlieren.
        box = max(boxen, key=lambda q: q[achse+2]-q[achse])
        x, y = (box[0]+box[2])/2, (box[1]+box[3])/2
        if any(l <= x <= r and t <= y <= b for l,t,r,b in belegt):
            return None
        h, w = self.bild.shape[:2]
        if any(l <= x*w <= r and t <= y*h <= b for l,t,r,b in self.zellen):
            return None
        richtungen = ({}, {})
        for hoehe in (72, 60, 64):
            mask = self._mask(box, achse, hoehe)
            if mask is None or not mask.any():
                continue
            for lesarten, lage in zip(richtungen, (mask, mask[::-1, ::-1])):
                wort = _zeile(lage) or schrift._gestapelt(lage)
                if wort:
                    lesarten[wort] = lesarten.get(wort, 0)+1
        stimmen = {}
        for lesarten in richtungen:
            for wort, anzahl in lesarten.items():
                p = lese_angabe(wort, 1.)
                if p is not None and p.typ == "Size_Diameter":
                    stimmen[wort] = stimmen.get(wort, False) or (len(lesarten) == 1 and anzahl >= 2)
        if len(stimmen) == 1:
            wort, sicher = next(iter(stimmen.items()))
            if sicher:
                return Blattangabe(self.nummer, box, wort)
        return None

    def _muster_am_rahmen(self, rahmen):
        # Die Mengenangabe gehoert zur eigenen Durchmesserzeile ueber dem Rahmen.
        h, w = self.bild.shape[:2]
        raster = np.array([w, h, w, h])
        l, t, r, b = np.rint(rahmen.box*raster).astype(int)
        hoehe = b-t
        if r-l < 2*hoehe or hoehe < 5 or t < hoehe+2:
            return None
        x, y = max(0, l-2*hoehe), max(0, t-round(1.42*hoehe))
        streifen = self.bild[y:t-2, x:min(w, r+3*hoehe)].min(axis=2) < 185
        gruppen = list(schrift._gruppen(streifen))
        if len(gruppen) < 5:
            return None
        links, ende = gruppen[0]
        # Vor der Beschriftung muss ein waagerechtes Stueck der Hinweislinie liegen.
        stueck = max(3, round(.5*hoehe))
        if ende-links < stueck or abs(ende+x-l) > 1.6*hoehe:
            return None
        strich = streifen[:, ende-stueck:ende]
        if not strich.all(axis=1).any() or strich.any(axis=1).sum() > 3:
            return None
        links, rechts = gruppen[1][0], gruppen[-1][1]
        if rechts+2 >= streifen.shape[1] or links-ende < 2 or links-ende > hoehe:
            return None
        ys = np.nonzero(streifen[:, links:rechts])[0]
        box = tuple(np.clip(np.array([x+links-1, y+ys.min()-1, x+rechts+1, y+ys.max()+2])/raster, 0., 1.))
        texte = {self._bildtext(box, False, 0, aufloesung) for aufloesung in (72, 60)}
        texte.discard("")
        if len(texte) == 1:
            text = texte.pop()
            if musteranzahl(text) and lese_angabe(text, 1.) is not None:
                return Blattangabe(self.nummer, box, text)
        return None

    @cached_property
    def zellen(self):
        return _zellen(self.bild.min(axis=2) < 195)

    def fundstellen(self):
        h, w = self.bild.shape[:2]
        rahmen, einzeln = {}, []
        for k in range(4):
            for a in self._rahmen(self.zellen, k, w, h):
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
        for a in list(rahmen.values()):
            if "|" in a.text and (m := self._muster_am_rahmen(a)) is not None:
                if not any(musteranzahl(ortsangabe.text) and
                           m.box[0] <= (ortsangabe.box[0]+ortsangabe.box[2])/2 <= m.box[2] and
                           m.box[1] <= (ortsangabe.box[1]+ortsangabe.box[3])/2 <= m.box[3] for ortsangabe in rahmen.values()):
                    rahmen[m.box] = m
        return sorted(rahmen.values(), key=lambda a: (a.box[1], a.box[0]))
