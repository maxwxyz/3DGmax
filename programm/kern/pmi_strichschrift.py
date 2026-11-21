"""Vektor-OCR fuer ebene CAD-Beschriftungen. Auswertung erst beim Pruefen eines Callouts."""

from functools import lru_cache

import re

import numpy as np
from PySide6 import QtCore, QtGui
from scipy import ndimage

_WINKELZAHL = r"(?:\d+(?:[.,]\d+)?|[.,]\d+)"
_WINKELZEILE = re.compile(rf"{_WINKELZAHL}°(?:\s*±\s*{_WINKELZAHL}°?)?")
_HALBDREHUNG = str.maketrans("69", "96")


def _pfade(g, ebene):
    o, x, y, _ = ebene
    achsen = np.column_stack((x, y))
    pfade = [((l - o) @ achsen, False) for l in g.linien if len(l) >= 2]
    for p, t in g.dreiecke:
        if len(t):
            pfade.extend((dreieck, True) for dreieck in ((p - o) @ achsen)[t])
    return pfade if pfade and np.isfinite(np.vstack([p for p, _ in pfade])).all() else []


def _rahmen(pfade):
    """Geschlossene Rahmen aus waagerechten und senkrechten Strichen, inklusive geteilter Zellkanten."""
    senk, waag = [], []
    for p, voll in pfade:
        if voll or len(p) > 6:
            continue
        for a, b in zip(p, p[1:]):
            dx, dy = abs(b - a)
            if dx < 1e-6 * dy:
                senk.append((a[0], min(a[1], b[1]), max(a[1], b[1])))
            elif dy < 1e-6 * dx:
                waag.append((a[1], min(a[0], b[0]), max(a[0], b[0])))
    if len(senk) > 140 or len(waag) > 140:
        return []
    gruppen = {}
    for x, unten, oben in senk:
        gruppen.setdefault((round(unten, 5), round(oben, 5)), set()).add(round(x, 5))
    rahmen = []
    for (unten, oben), kanten in gruppen.items():
        h = oben - unten
        if h <= 0 or len(kanten) < 2:
            continue
        kanten = sorted(kanten)
        for a, b in zip(kanten, kanten[1:]):
            if not .4 * h < b - a < 30 * h:
                continue
            eps = h * .003
            if all(any(abs(y - yy) < eps and x1 <= a + eps and x2 >= b - eps
                       for y, x1, x2 in waag) for yy in (oben, unten)):
                rahmen.append((a, unten, b, oben))
    return sorted(rahmen)


def _bild(pfade, box, skala):
    """Binaerbild in Schreibrichtung, auch fuer getrennte Konturen und gefuellte Schrift."""
    x, y, r, t = box
    groesse = np.array([r - x, t - y]) * skala
    if not np.isfinite(groesse).all() or max(groesse) > 3195:
        return None
    w, h = np.ceil(groesse).astype(int) + 5
    if min(w, h) < 5 or w * h > 2_000_000:
        return None
    im = QtGui.QImage(int(w), int(h), QtGui.QImage.Format.Format_Grayscale8)
    im.fill(0)
    painter = QtGui.QPainter(im)
    pen = QtGui.QPen(QtCore.Qt.GlobalColor.white)
    for p, voll in pfade:
        painter.setPen(pen)
        poly = QtGui.QPolygonF([QtCore.QPointF((a-x)*skala+2, (t-b)*skala+2) for a, b in p])
        if voll:
            painter.setBrush(QtCore.Qt.GlobalColor.white)
            painter.drawPolygon(poly)
        else:
            painter.drawPolyline(poly)
    painter.end()
    return np.frombuffer(im.constBits(), np.uint8).reshape(h, im.bytesPerLine())[:, :w] > 0


def _gruppen(mask):
    """Zusammenhaengende belegte Spalten; Innenkonturen gehoeren zum Zeichen."""
    kanten = np.flatnonzero(np.diff(np.r_[False, mask.any(axis=0), False]))
    return [(int(l), int(r)) for l, r in kanten.reshape(-1, 2)]


def _merkmal(mask):
    yy, xx = np.nonzero(mask)
    h, w = np.ptp(yy) + 1, np.ptp(xx) + 1
    # Innenkonturen trennen z. B. Null, Acht und Durchmesserzeichen.
    voll = mask[yy.min():yy.max()+1, xx.min():xx.max()+1]
    rand = voll ^ ndimage.binary_erosion(voll, border_value=0)
    ys, xs = np.nonzero(rand)
    bitmap = np.zeros((32, 32), bool)
    faktor = 29 / max(1, max(w, h) - 1)
    bitmap[1 + np.rint(ys * faktor).astype(int), 1 + np.rint(xs * faktor).astype(int)] = True
    return bitmap


def _fachmaske(pfade, box, pixelhoehe=100):
    x, y, r, t = box
    h = t - y
    rand = .003 * h
    innen = [(p, voll) for p, voll in pfade if np.min(p[:, 0]) > x + rand and np.max(p[:, 0]) < r - rand
             and np.min(p[:, 1]) > y + rand and np.max(p[:, 1]) < t - rand]
    return _bild(innen, box, pixelhoehe / h) if innen and h > 0 else None


def _bildzeichen(mask):
    out = []
    for l, r in _gruppen(mask):
        teil = mask[:, l:r]
        ys = np.nonzero(teil)[0]
        out.append((_merkmal(teil), (l, int(ys.min()), r, int(ys.max())+1)))
    return out


# Einfache einlinige Ziffern im 6 x 9 Raster. Schraegstriche trennen die Linien.
_STRICHE = {
    "0": "20 40 61 67 48 28 07 01 20",
    "1": "02 30 38",
    "2": "02 11 20 40 61 63 08 68",
    "3": "00 60 34 54 65 67 58 18 07",
    "4": "58 50 05 65",
    "5": "60 10 04 34 55 66 57 48 18 07",
    "6": "60 30 12 04 07 18 48 67 65 54 24 05",
    "7": "00 60 28",
    "8": "20 40 61 63 44 24 03 01 20 / 24 44 65 67 48 28 07 05 24",
    "9": "61 50 20 01 03 14 44 63 66 48 18",
    "A": "08 30 68 / 15 55",
    "B": "08 00 40 61 63 44 04 / 44 65 67 48 08",
    "C": "61 50 20 01 07 18 48 67",
    "R": "08 00 40 61 63 44 04 / 34 68",
    "⟂": "30 38 / 08 68",
    "⏥": "23 73 57 07 23",
}


def _musterbilder(muster):
    import zlib
    return [(z, np.unpackbits(np.frombuffer(zlib.decompress(bytes.fromhex(bits)), np.uint8)).reshape(32, 32) > 0)
              for z, varianten in muster.items() for bits in varianten]


@lru_cache(maxsize=1)
def _vorlagen():
    from .pmi_schriftmuster import MUSTER
    muster = _musterbilder(MUSTER)
    for z, zug in _STRICHE.items():
        linien = []
        for pfad in zug.split("/"):
            p = np.array([(int(a), 8 - int(b)) for a, b in pfad.split()])
            linien.append((p, False))
        muster.append((z, _merkmal(_bild(linien, (0, 0, 8, 8), 8))))
    return [(z, b, ndimage.distance_transform_edt(~b)) for z, b in muster]


@lru_cache(maxsize=2)
def _breitvorlagen(rahmen=False):
    from .pmi_schriftmuster import BREITSCHRIFT, BREITE_RAHMENSCHRIFT
    muster = _musterbilder(BREITSCHRIFT)
    if rahmen:
        muster.extend(_musterbilder(BREITE_RAHMENSCHRIFT))
    return [(z, b, ndimage.distance_transform_edt(~b)) for z, b in muster]


# In dieser Schrift ist der Punkt ein kleines, geschlossenes Rechteck.
_INNENRAEUME = {z: n for n, gruppe in enumerate(("-+±X12357⟂∥CE", ".0469R⌓AD○", "8⌀BⓅ", "", "⌖Ⓜ")) for z in gruppe}


_Y, _X = np.ogrid[:32, :32]
_KREIS_INNEN = (_Y - 15.5)**2 + (_X - 15.5)**2 <= 9**2


def _lies_zeile(zeichen, vorlagen=None, innenraeume=None):
    if not 1 <= len(zeichen) <= 48:
        return ""
    oben = min(box[1] for _, box in zeichen)
    unten = max(box[3] for _, box in zeichen)
    hoehe = unten - oben
    ergebnis = ""
    for i, (bitmap, (l, y, r, u)) in enumerate(zeichen):
        h = (u - y) / hoehe
        dist = ndimage.distance_transform_edt(~bitmap)
        je_zeichen = {}
        for z, vorlage, abstand in (_vorlagen() if vorlagen is None else vorlagen):
            if z == "○":
                # Ein leerer Modifikator folgt der Zahl. Sein Aussenkreis ist breiter
                # als die Ziffern derselben Schrift; die Eins hat eine eigene Breite.
                if i != len(zeichen)-1 or not ergebnis[-1:].isdigit():
                    continue
                breiten = [b[2]-b[0] for c, (_, b) in zip(ergebnis, zeichen)
                           if c in "023456789⌀"]
                if breiten and r-l <= 1.1*np.median(breiten):
                    continue
            if (innenraeume is not None and innenraeume[i] != _INNENRAEUME[z]
                    and not (z == "Ⓟ" and innenraeume[i] == 3)):
                # Beim umkreisten M kann eine Beruehrung wegrastern. Dann muss jedes Pixel
                # beider Glyphen hoechstens einen Rasterpunkt von der Gegenglyphe liegen.
                if (z != "Ⓜ" or innenraeume[i] not in (1, 3)
                        or dist[vorlage].max() > 1 or abstand[bitmap].max() > 1):
                    continue
            if z == "." and (h > .38 or u < unten - .23 * hoehe):
                continue
            if z == "°" and (h > .43 or y > oben + .27 * hoehe):
                continue
            if z == "-" and (h > .28 or abs((y+u-oben-unten)/2) > .23 * hoehe):
                continue
            if z not in ".°±-" and (h < .46 or not y < (oben + unten) / 2 < u):
                continue
            if z in "ⓂⒻⓁⓅ":
                # Der gemeinsame Aussenkreis sagt nichts ueber die Materialbedingung aus.
                innen = np.r_[dist[vorlage & _KREIS_INNEN], abstand[bitmap & _KREIS_INNEN]]
                if not innen.size or np.quantile(innen, .9) > 1.7:
                    continue
            fehler = (dist[vorlage].mean() + abstand[bitmap].mean()) / 2
            je_zeichen[z] = min(je_zeichen.get(z, np.inf), fehler)
        sortiert = sorted(je_zeichen, key=je_zeichen.get)
        if not sortiert or je_zeichen[sortiert[0]] > 1.05:
            return ""
        if len(sortiert) > 1 and je_zeichen[sortiert[1]] - je_zeichen[sortiert[0]] < .16:
            return ""
        ergebnis += sortiert[0]
    return ergebnis


def _gesamtbild(pfade, skala):
    punkte = np.vstack([p for p, _ in pfade])
    box = (*punkte.min(axis=0), *punkte.max(axis=0))
    return _bild(pfade, box, skala), box


def _einzelrahmen(pfade, zellen):
    """Eine zusammenhaengende Zellreihe ohne weitere Beschriftung daneben."""
    links, unten, _, oben = zellen[0]
    rechts = zellen[-1][2]
    if any(a[2] != b[0] or a[1::2] != b[1::2] for a, b in zip(zellen, zellen[1:])):
        return False
    skala = 80 / (oben - unten)
    mask, box = _gesamtbild(pfade, skala)
    if mask is None:
        return False
    # Zusatzangaben ausserhalb des Rahmens muessen ebenfalls gelesen werden.
    labels, _ = ndimage.label(mask, np.ones((3, 3)))
    x1, x2 = (round((x - box[0]) * skala) + 2 for x in (links, rechts))
    y1, y2 = (round((box[3] - y) * skala) + 2 for y in (oben, unten))
    rahmenlabels = np.unique(labels[max(0, y1-2):y2+3, max(0, x1-2):x2+3])
    ausserhalb = np.setdiff1d(np.unique(labels), rahmenlabels)
    if len(ausserhalb):
        # AP203 erlaubt eine kurze Luecke zwischen Zellkante und Fuehrungslinie.
        if len(ausserhalb) != 1:
            return False
        y, x = np.nonzero(labels == ausserhalb[0])
        mitte = (y1 + y2) / 2
        enden = ((x1, mitte), (x2, mitte))
        if (np.ptp(x) < 80 or min(np.min(np.hypot(x-a, y-b)) for a, b in enden) > 32
                or len(x) / ((np.ptp(x)+1)*(np.ptp(y)+1)) > .15):
            return False
    return True


def _rahmenwort(teile):
    from .pmi_ableiten import gueltige_rahmenzellen
    if len(teile) == 1:
        return f"[{teile[0]}]" if teile[0].isalpha() else ""
    return " ".join(teile) if gueltige_rahmenzellen(teile) else ""


def _rahmentext(pfade, zellen, masken=None):
    if not _einzelrahmen(pfade, zellen):
        return ""
    if masken is None:
        masken = [_fachmaske(pfade, z) for z in zellen]
    if any(m is None for m in masken):
        return ""
    normal = _rahmenwort([_normale_zeile(m) for m in masken])
    breit = _rahmenwort([_breite_zeile(m, rahmen=True) for m in masken])
    if breit and normal and breit != normal:
        return ""
    return breit or normal


def _normale_zeile(mask):
    zeichen = _bildzeichen(mask)
    wort = _lies_zeile(zeichen)
    for z, (_, (l, t, r, b)) in zip(wort, zeichen):
        if z == "°":
            glyph = mask[t:b, l:r]
            mitte = ((b-t)//2, (r-l)//2)
            if glyph[mitte] or not ndimage.binary_fill_holes(glyph)[mitte]:
                return ""  # Auch zwei gezeichnete Kreisraender umschliessen eine freie Mitte.
    return wort


def _breite_zeile(mask, rahmen=False):
    zeichen = _bildzeichen(mask)
    innen = [ndimage.label(~np.pad(mask[t:b, l:r], 1))[1] - 1 for _, (l, t, r, b) in zeichen]
    return _lies_zeile(zeichen, _breitvorlagen(rahmen), innen)


def _gestapelt(mask, lesen=_normale_zeile):
    """Gemeinsamer Vorsatz links, zwei getrennte Zahlenzeilen rechts."""
    zahl = r"(?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+)"
    gruppen = _gruppen(mask)
    if not 2 <= len(gruppen) <= 48:
        return ""
    for _, trennung in gruppen[:-1]:
        rechts = mask[:, trennung:]
        zeilen = _gruppen(rechts.T)
        if len(zeilen) != 2:
            continue
        (a, b), (c, d) = zeilen
        h = max(b-a, d-c)
        if min(b-a, d-c) < .65*h or not .1*h < c-b < 1.8*h:
            continue
        links = mask[:, :trennung]
        ly, lx = np.nonzero(links)
        rx = np.flatnonzero(rechts.any(axis=0))
        mitte = (ly.min() + ly.max()) / 2
        if not (a+b)/2 < mitte < (c+d)/2 or rx.min() + trennung - lx.max() > 3*h:
            continue
        vorsatz = lesen(links)
        oben, unten = (lesen(rechts[y:v]) for y, v in zeilen)
        if vorsatz in ("⌀", "R") and re.fullmatch(zahl, oben) and re.fullmatch(zahl, unten):
            if float(oben.replace(",", ".")) >= float(unten.replace(",", ".")):
                return f"{vorsatz}{oben}\n{unten}"
        abmass = rf"(?:[+-]{zahl}|0(?:[.,]0+)?)"
        if re.fullmatch(rf"(?:(?:[1-9][0-9]*X)?[⌀R])?{zahl}", vorsatz) and all(re.fullmatch(abmass, t) for t in (oben, unten)):
            return f"{vorsatz} {oben}\n{unten}"
    return ""


def _masszeile(mask):
    normal = _normale_zeile(mask) or _gestapelt(mask)
    breit = _breite_zeile(mask) or _gestapelt(mask, _breite_zeile)
    if not re.match(r"^(?:[1-9][0-9]*X)?[⌀R][0-9.]", breit):
        return normal
    return breit if not normal or breit == normal else ""


def _klammerzeile(labels, objekte):
    """Schrift zwischen zwei grossen, abgesetzten Masslinien mitsamt Pfeilkopf lesen."""
    if len(objekte) < 5:
        return ""
    def groesse(box):
        return max(s.stop - s.start for s in box)
    reihe = sorted(enumerate(objekte, 1), key=lambda eintrag: groesse(eintrag[1]))
    schrift, linien = reihe[:-2], reihe[-2:]
    if groesse(linien[0][1]) <= 3.5 * max(groesse(box) for _, box in schrift):
        return ""
    for nr, box in linien:
        maske = labels[box] == nr
        # Masslinie und Hilfslinie belegen je eine fast durchgehende Zeile bzw. Spalte.
        if maske.mean() >= .12 or min(maske.mean(0).max(), maske.mean(1).max()) < .85:
            return ""
    bereich = tuple(slice(min(b[i].start for _, b in schrift), max(b[i].stop for _, b in schrift)) for i in (0, 1))
    for i, s in enumerate(bereich):
        links, rechts = sorted((b[i] for _, b in linien), key=lambda rand: rand.start)
        if links.stop <= s.start and s.stop <= rechts.start:
            wort = _normale_zeile(labels[bereich] > 0)
            return wort if wort.startswith("(") and wort.endswith(")") else ""
    return ""


def _freitext(pfade):
    punkte = np.vstack([p for p, _ in pfade])
    spannweite = np.ptp(punkte, axis=0)
    if min(spannweite) <= 0:
        return ""
    # Erst die gesamte Grafik rastern. Lange Masslinien samt verbundener Pfeilspitze abtrennen.
    skala = min(720 / spannweite[1], 2000 / spannweite[0])
    mask, box = _gesamtbild(pfade, skala)
    if mask is None:
        return ""
    labels, anzahl = ndimage.label(mask, np.ones((3, 3)))
    if not 1 <= anzahl <= 120:
        return ""
    objekte = ndimage.find_objects(labels)
    hoehen = [y.stop-y.start for y, x in objekte if y.stop-y.start >= 4]
    if not hoehen:
        return ""
    fuehrungen = []
    typisch = np.percentile(hoehen, 65)
    for i, (y, x) in enumerate(objekte, 1):
        if max(x.stop-x.start, y.stop-y.start) > 3.5 * typisch:
            # Nur eindeutig angeschlossene, lange Fuehrungslinien mit geringem Flaechenanteil.
            teil = labels[y, x] == i
            if teil.mean() < .12:
                mask[y, x] &= ~teil
                fuehrungen.append(i-1)
    if not mask.any():
        return ""
    wort = _masszeile(mask)
    if not wort:
        wort = _klammerzeile(labels, objekte)
    if not wort and not any(voll for _, voll in pfade):
        from .pmi_hinweislinie import winkelbeschriftung
        schrift = winkelbeschriftung(pfade, box, skala, labels, objekte)
        if schrift:
            punkte = np.vstack([p for p, _ in schrift])
            dx, dy = np.ptp(punkte, axis=0)
            if min(dx, dy) > 0:
                ausschnitt, _ = _gesamtbild(schrift, min(720/dy, 2000/dx))
                winkel = _normale_zeile(ausschnitt) if ausschnitt is not None else ""
                if _WINKELZEILE.fullmatch(winkel):
                    return winkel
    if wort or len(fuehrungen) != 1:
        return wort
    from .pmi_hinweislinie import zielbogen
    bogen = zielbogen(pfade, box, skala, labels, objekte, fuehrungen[0], typisch)
    if bogen is None:
        return ""
    y, x = objekte[bogen]
    mask[y, x] &= labels[y, x] != bogen+1
    wort = _masszeile(mask)
    return wort if re.match(r"^(?:[1-9][0-9]*X)?[⌀R][0-9.]", wort) else ""


def _rechteckfaecher(mask, mindestbreite):
    labels, _ = ndimage.label(~mask)
    faecher = []
    for y, x in ndimage.find_objects(labels):
        l, r, t, b = x.start, x.stop, y.start, y.stop
        h = b - t
        if not (l and t and r < mask.shape[1] and b < mask.shape[0]
                and h >= 12 and mindestbreite*h < r-l < 30*h):
            continue
        if min(mask[t-1, x].mean(), mask[b, x].mean(), mask[y, l-1].mean(), mask[y, r].mean()) < .98:
            continue
        faecher.append((l, t, r, b))
    return faecher


def _fuellrahmen(pfade):
    """Gerade geschlossene Fachraender aus der Fuellung, auch ohne einzelne Kantenstriche."""
    punkte = np.vstack([p for p, _ in pfade])
    dx, dy = np.ptp(punkte, axis=0)
    if min(dx, dy) <= 0:
        return []
    skala = min(480 / dy, 1800 / dx)
    mask, box = _gesamtbild(pfade, skala)
    if mask is None:
        return []
    faecher = _rechteckfaecher(mask, .4)
    if not faecher:
        return []
    # Eine einzige Reihe mit gemeinsamen Stegen. Mehrzeilige Rahmen brauchen eigene Semantik.
    h = max(b-t for _, t, _, b in faecher)
    reihe = sorted(z for z in faecher if z[3] - z[1] > .85*h)
    t, b = reihe[0][1::2]
    if (len(reihe) > 6 or any(abs(y-t) > 2 or abs(u-b) > 2 for _, y, _, u in reihe)
            or any(not 0 < z[0]-a[2] <= max(3, .12*h) for a, z in zip(reihe, reihe[1:]))):
        return []
    if not any(mask[y:u,l:r].any() for l, y, r, u in reihe):
        return []
    kanten = [reihe[0][0]-1, *((a[2]+z[0]-1)/2 for a, z in zip(reihe, reihe[1:])), reihe[-1][2]]
    xx = [box[0]+(x-2)/skala for x in kanten]
    unten, oben = box[3]-(b-2)/skala, box[3]-(t-3)/skala
    return [(l, unten, r, oben) for l, r in zip(xx, xx[1:])]


def _zellen(pfade):
    rahmen = _rahmen(pfade)
    if not rahmen:
        return _fuellrahmen(pfade) if any(voll for _, voll in pfade) else []
    h = max(b[3] - b[1] for b in rahmen)
    return [b for b in rahmen if b[3] - b[1] > .85 * h]


def _netzrandrichtungen(dreiecke):
    """Gemeinsame Diagonalen im Dreiecksnetz liefern keine Richtung des Buchstabens oder Rahmens."""
    for punkte, netz in dreiecke:
        if not len(netz):
            continue
        koordinaten, index = np.unique(punkte, axis=0, return_inverse=True)
        t = index.reshape(-1)[netz]
        paare = np.concatenate((t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]))
        kanten, anzahl = np.unique(np.sort(paare, axis=1), axis=0, return_counts=True)
        rand = kanten[anzahl == 1]
        if len(rand):
            yield koordinaten[rand[:, 1]] - koordinaten[rand[:, 0]]


def _haeufige_schriftkanten(g, x, y):
    """Wiederkehrende Glyphenkanten liefern Achsen auch bei langen schraegen Masshilfslinien."""
    kanten = [np.diff(l, axis=0) for l in g.linien if len(l) >= 2]
    kanten.extend(_netzrandrichtungen(g.dreiecke))
    if not kanten:
        return
    kanten = np.vstack(kanten)
    kanten = kanten[np.linalg.norm(kanten, axis=1) > 1e-7]
    winkel = np.rad2deg(np.arctan2(kanten @ y, kanten @ x)) % 90
    klassen = np.rint(winkel).astype(int) % 90
    anzahl = np.bincount(klassen, minlength=90)
    for k in np.argsort(anzahl)[-3:][::-1]:
        if anzahl[k] < 4:
            break
        delta = (winkel[klassen == k] - k + 45) % 90 - 45
        a = np.deg2rad(k + np.median(delta))
        yield np.cos(a) * x + np.sin(a) * y


def _rahmenrichtungen(g):
    """Moegliche Schreibachsen aus der Ebene und den laengsten geraden Kanten."""
    kanten = [np.diff(l, axis=0) for l in g.linien if 2 <= len(l) <= 6]
    if len(kanten) < 2:
        # Kurze Massangaben koennen fast vollstaendig aus zwei langen Schriftzuegen bestehen.
        kanten = [np.diff(l, axis=0) for l in g.linien if len(l) >= 2]
    if not kanten:
        kanten = list(_netzrandrichtungen(g.dreiecke))
    if not kanten:
        return
    punkte = np.vstack([*g.linien, *(p for p, _ in g.dreiecke)])
    if not np.isfinite(punkte).all():
        return
    o = punkte.mean(axis=0)
    lokal = punkte - o
    werte, achsen = np.linalg.eigh(lokal.T @ lokal)
    if werte[1] <= werte[2] * 1e-10 or abs(werte[0]) > werte[1] * 1e-9:
        return
    z = achsen[:, 0]
    kanten = np.vstack(kanten)
    laengen = np.linalg.norm(kanten, axis=1)
    versucht = []
    for i in np.argsort(laengen)[-14:][::-1]:
        v = kanten[i] - z * (kanten[i] @ z)
        laenge = np.linalg.norm(v)
        if laenge <= 1e-10:
            continue
        x = v / laenge
        y = np.cross(z, x)
        if any(max(abs(x @ achse), abs(y @ achse)) > .999999 for achse in versucht):
            continue
        versucht.append(x)
        yield o, x, y, z
        yield o, y, x, -z


def _schriftachsen(pfade):
    """Mehrere nahezu waagerechte und senkrechte Zeichenstriche stuetzen die Leseachse."""
    kanten = np.abs(np.vstack([np.diff(p, axis=0) for p, _ in pfade]))
    kanten = kanten[kanten.max(axis=1) > 1e-7]
    anzahl = max(1, .015 * len(kanten))
    # Zwei Grad Spiel fuer facettierte Glyphen und leicht schraege Anschlusslinien.
    dx, dy = kanten.T
    return min(np.count_nonzero(dx < .035*dy), np.count_nonzero(dy < .035*dx)) >= anzahl


def _mass_ohne_ebene(g, richtungen, ergebnis=""):
    from .pmi_ableiten import aus_text, grenzlesart
    for ebene in richtungen:
        pfade = _pfade(g, ebene)
        for spiegelung in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            wort = _freitext([(p * spiegelung, voll) for p, voll in pfade])
            geklammert = wort.startswith("(") and wort.endswith(")")
            if not (geklammert or re.match(r"^(?:[1-9][0-9]*X)?[⌀R][0-9.]", wort) or _WINKELZEILE.match(wort)):
                continue
            daten = aus_text([wort], g.textfaktor) or grenzlesart(wort, g.textfaktor)
            if daten and (daten["typ"] in ("Size_Diameter", "Size_Radius", "Size_Angular")
                          or "Hilfsmass" in daten.get("modifikatoren", ())):
                # Bei (66) kann die Gegenrichtung auch (99) sein, selbst wenn die zweite Lesung scheitert.
                if (m := re.fullmatch(r"\(([01689]+)\)", wort)) and m[1][::-1].translate(_HALBDREHUNG) != m[1]:
                    return None
                if ergebnis and ergebnis != wort:
                    return None
                ergebnis = wort
    return ergebnis


def _weitere_massrichtungen(g, ebenen):
    """Glyphenachsen fuer ungeloeste Angaben, Winkel und geklammerte Hilfsmasse."""
    o, x, y, z = ebenen[0]
    for v in _haeufige_schriftkanten(g, x, y):
        if any(abs(v @ e[1]) > .999999 for e in ebenen):
            continue
        quer = np.cross(z, v)
        for ebene in ((o, v, quer, z), (o, quer, v, -z)):
            pfade = _pfade(g, ebene)
            if _schriftachsen(pfade) and not _zellen(pfade):
                yield ebene


def _ohne_schreibebene(g):
    """Alle lesbaren Orientierungen muessen denselben Rahmen bzw. dasselbe Mass ergeben."""
    from .pmi_ableiten import aus_text

    ergebnis = ""
    massrichtungen = []
    hat_rahmen = False
    ebenen = list(_rahmenrichtungen(g))
    for ebene in ebenen:
        pfade = _pfade(g, ebene)
        zellen = _zellen(pfade)
        if pfade and len(zellen) <= 6 and _schriftachsen(pfade):
            if any(m is not None and m.any() for m in (_fachmaske(pfade, z) for z in zellen)):
                if 2 <= len(zellen) <= 6 and _einzelrahmen(pfade, zellen):
                    hat_rahmen = True
            else:
                massrichtungen.append(ebene)
        if not 2 <= len(zellen) <= 6:
            continue
        for x, y in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            achsen = np.array([x, y])
            ausgerichtet = [(p * achsen, voll) for p, voll in pfade]
            boxen = sorted((min(x*l, x*r), min(y*b, y*t), max(x*l, x*r), max(y*b, y*t))
                           for l, b, r, t in zellen)
            text = _rahmentext(ausgerichtet, boxen)
            if text and "wert" in (aus_text([text], g.textfaktor) or {}):
                if ergebnis and ergebnis != text:
                    return ""
                ergebnis = text
    if ergebnis or hat_rahmen or not ebenen:
        return ergebnis
    mass = _mass_ohne_ebene(g, massrichtungen)
    if mass is None or (mass and "°" not in mass and not mass.startswith("(")):
        return mass or ""
    return _mass_ohne_ebene(g, _weitere_massrichtungen(g, ebenen), mass) or ""


def _lesbar(g):
    return (len(g.linien) + len(g.dreiecke) <= 1200
            and sum(map(len, g.linien)) + sum(len(p) + len(t) for p, t in g.dreiecke) <= 40000)


def lies_rahmensymbol(g, fachzahl):
    """Erstes Symbol einer einzelnen Rahmenzeile zur Ergaenzung des STEP-Validierungstexts."""
    from .pmi_ableiten import SYMBOL_ZU_TYP
    if g.ebene is None or not _lesbar(g) or not 2 <= fachzahl <= 5:
        return ""
    pfade = _pfade(g, g.ebene)
    zellen = _zellen(pfade) if pfade else []
    if len(zellen) != fachzahl or not _einzelrahmen(pfade, zellen):
        return ""
    maske = _fachmaske(pfade, zellen[0])
    if maske is None:
        return ""
    lesarten = {_normale_zeile(maske), _breite_zeile(maske, rahmen=True)}
    lesarten.discard("")
    if len(lesarten) == 1:
        zeichen = lesarten.pop()
        return zeichen if zeichen in SYMBOL_ZU_TYP else ""
    return ""


def lies_schrift(g):
    """Vollstaendig erkannte Rahmen oder einzelne Schriftzeile, sonst leer."""
    if not _lesbar(g):
        return ""
    if g.ebene is None:
        return _ohne_schreibebene(g)
    pfade = _pfade(g, g.ebene)
    if not pfade:
        return ""
    zellen = _zellen(pfade)
    if len(zellen) > 6:
        return ""
    masken = [_fachmaske(pfade, b) for b in zellen]
    if any(m is not None and m.any() for m in masken):
        return _rahmentext(pfade, zellen, masken)
    return _freitext(pfade)
