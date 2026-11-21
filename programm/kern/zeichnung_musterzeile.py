"""Durchmessermass mit eigener Hinweislinie ueber einem projizierten Rahmen."""
import re

import numpy as np
from scipy import ndimage

from .pmi_koplanarschrift import _konturzeile
from .pmi_strichschrift import _gruppen
from .zeichnungsabgleich import Blattangabe, lese_angabe


def _durchmesser(maske):
    # Der steigende Querstrich teilt den Ring in zwei diagonal gegenueberliegende Innenraeume.
    h, w = maske.shape
    if not .7 < w/h < 1.25:
        return False
    labels, n = ndimage.label(~np.pad(maske, 1))
    if n != 3:
        return False
    innen = labels[1:-1, 1:-1]
    mitten = []
    for i in (2, 3):
        punkte = np.argwhere(innen == i)
        if not .08 < len(punkte)/maske.size < .30:
            return False
        mitten.append((punkte.mean(axis=0)+.5) / [h, w])
    oben, unten = sorted(mitten, key=lambda v: v[0])
    if not (np.all((.22 < oben) & (oben < .44)) and np.all((.56 < unten) & (unten < .78))):
        return False
    y, x = (np.indices((h, w))+.5)/np.array([h, w])[:, None, None]-.5
    ring = abs(np.hypot(x,y)-.45) < .06
    strich = (abs(x+y) < .09) & (abs(x) < .44) & (abs(y) < .44)
    soll = ring | strich
    return np.count_nonzero(soll & maske) / np.count_nonzero(soll | maske) > .66


def _masswort(maske):
    from .zeichnungsblatt import _zeile
    gruppen = _gruppen(maske)
    if not 2 <= len(gruppen) <= 30:
        return ""
    text = ""
    h = len(maske)
    if any(l-rechts > .85*h for (_, rechts), (l, _) in zip(gruppen, gruppen[1:])):
        return ""
    for l, r in gruppen:
        teil = maske[:, l:r]
        y = np.nonzero(teil)[0]
        zeichen = teil[y.min():y.max()+1]
        if y.min() > .65*h and y.max() >= .82*h and .55 < (r-l)/len(zeichen) < 1.5 and zeichen.mean() > .6:
            text += "."
        elif (not text or text.endswith("X")) and _durchmesser(zeichen):
            text += "⌀"
        else:
            if y.min() > .25*h or y.max() < .73*h:
                return ""
            lesarten = {_zeile(zeichen), _konturzeile(zeichen)} - {""}
            if len(lesarten) != 1:
                return ""
            glyph = lesarten.pop()
            if len(glyph) != 1 or glyph not in "0123456789X±":
                return ""
            text += glyph
    zahl = r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)"
    if re.fullmatch(rf"(?:[1-9][0-9]{{0,3}}X)?⌀{zahl}(?:±{zahl})?", text) and lese_angabe(text, 1.):
        return text
    return ""


def _entzerrtes_mass(maske):
    """Gestauchte Schrift am Ring des gedruckten Durchmesserzeichens ausrichten."""
    for l, r in _gruppen(maske)[:6]:
        spalte = maske[:, l:r]
        y = np.flatnonzero(spalte.any(axis=1))
        glyph = spalte[y[0]:y[-1]+1]
        verh = (r-l)/len(glyph)
        if .7 < verh < .84 and _durchmesser(glyph):
            return _masswort(ndimage.zoom(maske, (1, .90/verh), order=0))
    return ""


def _messzeile(streifen, breite, hoehe, skala):
    fenster = np.array([-1.5, -1.6, breite+3, -.07])
    m = streifen._maske(fenster*hoehe, skala/hoehe, 185)
    gruppen = _gruppen(m)
    if not 3 <= len(gruppen) <= 32:
        return None
    # Die textseitige Gerade des Hinweises kann links oder rechts an die Masszeile anschliessen.
    funde = []
    for links in (False, True):
        anfang, ende = gruppen[0 if links else -1]
        if ende-anfang < .5*skala:
            continue
        rand = round(.20*skala)
        anschluss = m[:,ende-rand:ende] if links else m[:,anfang:anfang+rand]
        ys = np.flatnonzero(anschluss.any(axis=1))
        if not 0 < len(ys) < .09*skala or not anschluss.all(axis=1).any():
            continue
        schrift = gruppen[1:] if links else gruppen[:-1]
        # Angeschnittene fremde Geometrie jenseits einer breiten Luecke im Suchfenster.
        if len(schrift) > 2 and links:
            a,b = schrift[-1]
            if b == m.shape[1] and m[0,a:b].any() and a-schrift[-2][1] > 2*skala:
                schrift = schrift[:-1]
        elif len(schrift) > 2:
            a,b = schrift[0]
            if a == 0 and m[0,a:b].any() and schrift[1][0]-b > 2*skala:
                schrift = schrift[1:]
        l, r = schrift[0][0], schrift[-1][1]
        luecke = l-ende if links else anfang-r
        # Linksbuendiger, mittiger oder rechtsbuendiger Text ueber dem zugehoerigen Rahmen.
        ausrichtung = np.array([l,(l+r)/2,r])/skala + fenster[0] - [0,breite/2,breite]
        if not .06*skala < luecke < .85*skala or min(abs(ausrichtung)) > .65 or l == 0 or r == m.shape[1]:
            continue
        y = np.nonzero(m[:,l:r])[0]
        t, b = y.min(), y.max()+1
        if t == 0 or b == len(m) or not .27*skala < b-t < .9*skala or not t <= ys.mean() < b:
            continue
        maske = m[t:b,l:r]
        wort = _masswort(maske) or _entzerrtes_mass(maske)
        if wort:
            box = np.array([l,t,r,b])/skala + np.tile(fenster[:2],2)
            ende_xy = np.array([ende-1 if links else anfang, ys.mean()])/skala + fenster[:2]
            funde.append((wort, box, ende_xy))
    return funde[0] if len(funde) == 1 else None


def musterzeile(streifen, breite, hoehe):
    from .zeichnungsblatt import _box
    grob = _messzeile(streifen, breite, hoehe, 100)
    if not grob:
        return None
    fein = _messzeile(streifen, breite, hoehe, 140)
    if not fein or fein[0] != grob[0]:
        return None
    if not np.allclose(np.r_[grob[1], grob[2]], np.r_[fein[1], fein[2]], atol=.035, rtol=0):
        return None
    wort, box, ende = fein
    ecken = streifen.blattecken(box*hoehe)
    if ecken:
        ort = (streifen.ort + (ende*hoehe) @ streifen.achsen) / streifen.blattpixel
        return Blattangabe(streifen.blatt.nummer, _box(ecken), wort, zeilenecken=ecken, hinweisenden=(tuple(ort),))
