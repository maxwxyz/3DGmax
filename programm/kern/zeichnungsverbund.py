"""Schraeg projizierte Verbundrahmen anhand von PDF-Schrift lokalisieren und im Druckbild lesen."""

from dataclasses import dataclass
import re

import numpy as np

from scipy.spatial import cKDTree

from .pmi import TOL_SYMBOL
from .pmi_ableiten import SIMULTANHINWEIS, gueltige_rahmenwerte
from .schriftstreifen import Schriftstreifen
from .zeichnungsabgleich import Blattangabe


@dataclass(eq=False)
class _Schriftort:
    text: str
    ort: np.ndarray
    richtung: np.ndarray
    em: float
    ecken: np.ndarray


def _schriftorte(blatt):
    from pypdfium2 import PdfiumError, raw
    h, w = blatt.bild.shape[:2]
    ursprung = np.array(blatt.koordinaten.to_page(0, 0))
    raster = np.linalg.inv(np.array([(blatt.koordinaten.to_page(w, 0)-ursprung)/w,
                                     (blatt.koordinaten.to_page(0, h)-ursprung)/h]))
    for obj in blatt.seite.get_objects(filter=[raw.FPDF_PAGEOBJ_TEXT], textpage=blatt.text):
        try:
            text = obj.extract().strip()
            if not text:
                continue
            ecken = np.asarray(obj.get_quad_points())
        except PdfiumError:
            continue
        matrix = obj.get_matrix()
        eltern = obj.container
        while eltern is not None:
            m = eltern.get_matrix()
            ecken = np.array([m.on_point(*p) for p in ecken])
            matrix = matrix.multiply(m)
            eltern = eltern.container
        a, b, c, d, x, y = matrix.get()
        achse = np.array([a, b]) @ raster
        em = obj.get_font_size() * np.linalg.norm(np.array([c, d]) @ raster)
        if em > 0 and np.linalg.norm(achse) > 0:
            yield _Schriftort(text, ([x, y]-ursprung) @ raster, achse/np.linalg.norm(achse),
                              em, (ecken-ursprung) @ raster)


def _zeilenpaar(mask, oben, unten):
    from .zeichnungsblatt import _zellen, _zeile
    zellen = _zellen(mask)

    def reihe(ort, oberkante):
        # Der Textursprung liegt knapp vor der ersten Ziffer, aber innerhalb der Wertzelle.
        x, y = ort
        aktuell = [z for z in zellen if z[0] <= x <= z[2] and z[1] <= y <= z[3]]
        if len(aktuell) != 1:
            return []
        while True:
            _, t, r, b = aktuell[-1]
            nachbar = [z for z in zellen if 0 <= z[0]-r <= 5 and abs(z[1]-t) <= 2 and abs(z[3]-b) <= 2]
            if not nachbar:
                # Weiterlaufende Rahmenkante bedeutet ein beschaedigtes oder abgeschnittenes Fach.
                rand = t-1 if oberkante else b
                if mask[rand-1:rand+2,r+4:r+10].any():
                    return []
                return aktuell
            if len(aktuell) >= 4 or len(nachbar) != 1:
                return []
            aktuell.extend(nachbar)

    erste, zweite = reihe(oben, True), reihe(unten, False)
    if not erste or not zweite:
        return None
    l, t, _, b = erste[0]
    l2, t2, _, b2 = zweite[0]
    if abs(l-l2) > 2 or not 0 <= t2-b <= 5:
        return None
    links = [z for z in zellen if 0 <= l-z[2] <= 5 and abs(z[1]-t) <= 2 and abs(z[3]-b2) <= 2]
    if len(links) != 1:
        return None

    def lies(z):
        x, y, r, u = z
        return _zeile(mask[y+1:u-1, x+1:r-1])

    symbol = lies(links[0])
    werte = [[lies(z) for z in reihe] for reihe in (erste, zweite)]
    if symbol not in TOL_SYMBOL.values() or not all(map(gueltige_rahmenwerte, werte)):
        return None
    return (links[0][0], t, max(erste[-1][2], zweite[-1][2]), b2), l, symbol, werte


def _fund(blatt, hinweis, oben, unten, orte):
    from .zeichnungsblatt import _box
    delta = unten.ort-oben.ort
    hoehe = np.linalg.norm(delta)
    if not .75*oben.em < hoehe < 2.8*oben.em:
        return None
    quer = delta/hoehe
    # Stark gestauchte oder vertauschte Achsen ergeben keine lesbare Projektion.
    u, v = oben.richtung
    if u*quer[1]-v*quer[0] < .45:
        return None
    streifen = Schriftstreifen(blatt, oben.ort, oben.richtung, quer)
    def lokal(p):
        return (p-oben.ort) @ streifen.basis.T / hoehe
    x, y = lokal(hinweis.ort)
    if not -3 <= x <= 1 or not 1.4 <= y <= 3.4:
        return None
    fenster = np.array([-3., -1.4, 13., 3.8])
    for faktor in (52., 60., 48.):
        mask = streifen._maske(fenster*hoehe, faktor/hoehe, 215)
        start = -fenster[:2]*faktor
        gelesen = _zeilenpaar(mask, start, start + [0, faktor])
        if gelesen is not None:
            break
    else:
        return None
    box, wertanfang, symbol, werte = gelesen
    if [z[0] for z in werte] != [oben.text, unten.text]:
        return None
    l, t, r, b = np.array(box)/faktor + np.tile(fenster[:2], 2)
    if min(abs(x-l), abs(x-(wertanfang/faktor+fenster[0]))) > .5 or not .2 < y-b < 1.85:
        return None
    zusatz = [hinweis]
    for ort in orte:
        xx, yy = lokal(ort.ort)
        if b+.1 < yy < y-.25 and l-.25 < xx < r and ort.richtung @ oben.richtung > .998:
            if abs(xx-x) > .35 or SIMULTANHINWEIS.fullmatch(ort.text):
                return None
            zusatz.append(ort)
    if len(zusatz) > 2 or (len(zusatz) == 1 and y-b > 1.1):
        return None
    rahmen = streifen.blattecken(np.array([l,t,r,b])*hoehe)
    if rahmen is None:
        return None
    ecken = np.concatenate([lokal(o.ecken) for o in zusatz])
    ecken = streifen.blattecken((np.array([min(l,ecken[:,0].min()), t, max(r,ecken[:,0].max()),
                                           max(b,ecken[:,1].max())])+[-.04,-.04,.04,.04])*hoehe)
    if ecken is None:
        return None
    text = "\n".join([" | ".join([symbol,*z]) for z in werte] + [o.text for o in reversed(zusatz)])
    return Blattangabe(blatt.nummer, _box(ecken), text, zeilenecken=ecken, rahmenbox=_box(rahmen), verbundrahmen=True)


def verbundrahmen(blatt):
    if not any("SIM" in t for _, t in blatt.textbereiche):
        return
    orte = list(_schriftorte(blatt))
    zahlen = [ort for ort in orte if re.fullmatch(r"(?:\d+[.,]?\d*|[.,]\d+)", ort.text)]
    if not zahlen:
        return
    index = cKDTree([z.ort for z in zahlen])
    kandidaten = []
    for hinweis in orte:
        if not SIMULTANHINWEIS.fullmatch(hinweis.text) or min(abs(hinweis.richtung)) < .08:
            continue
        nachbarn = index.query_ball_point(hinweis.ort, 7*hinweis.em)
        werte = [zahlen[i] for i in nachbarn if zahlen[i].richtung @ hinweis.richtung > .998]
        for oben in werte:
            for unten in werte:
                fund = _fund(blatt, hinweis, oben, unten, orte)
                if fund:
                    kandidaten.append((hinweis, oben, unten, fund))
    for hinweis, oben, unten, fund in kandidaten:
        if sum(h is hinweis or o is oben or u is unten for h,o,u,_ in kandidaten) == 1:
            yield fund
