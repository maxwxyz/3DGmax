"""Geneigte Masszeilen direkt in ihrer Leserichtung aus der PDF-Seite rendern."""

from ctypes import byref

import numpy as np

from . import pmi_strichschrift as schrift


def schriftumfang(mask, halbe):
    gruppen = list(schrift._gruppen(mask))
    if not gruppen or not 1 <= gruppen[0][0] <= 1.5*halbe:
        return None
    von,bis = gruppen[0]
    for a,b in gruppen[1:]:
        if a-bis > 2.1*halbe:
            break
        bis = b
    if bis == gruppen[0][1] or bis+2 >= mask.shape[1]:
        return None
    ys = np.flatnonzero(mask[:,von:bis].any(axis=1))
    oben,unten = ys[0],ys[-1]+1
    if oben < 1 or unten >= mask.shape[0] or unten-oben < 5:
        return None
    return von,oben,bis,unten


class Schriftstreifen:
    def __init__(self, blatt, ort, richtung, quer=None):
        self.blatt = blatt
        self.ort = np.asarray(ort)
        u,v = richtung
        self.achsen = np.array([[u,v], [-v,u] if quer is None else quer])
        self.basis = np.linalg.inv(self.achsen.T)
        h,w = blatt.bild.shape[:2]
        self.blattpixel = np.array([w,h])

    def _bitmap(self, fenster, faktor, grau):
        from pypdfium2 import PdfBitmap,raw
        links,oben,rechts,unten = fenster
        w,h = np.ceil(faktor*np.array([rechts-links,unten-oben])).astype(int)
        bitmap = PdfBitmap.new_native(w,h,raw.FPDFBitmap_Gray if grau else raw.FPDFBitmap_BGR,rev_byteorder=not grau)
        try:
            bitmap.fill_rect((255,255,255,255),0,0,w,h)
            matrix = self.basis * (self.blattpixel/[self.blatt.breite,self.blatt.hoehe])
            versatz = -self.basis @ self.ort - [links,oben]
            m = raw.FS_MATRIX(*(faktor*np.r_[matrix.T.ravel(),versatz]))
            clip = raw.FS_RECTF(0,0,w,h)
            flags = raw.FPDF_GRAYSCALE if grau else raw.FPDF_REVERSE_BYTE_ORDER
            raw.FPDF_RenderPageBitmapWithMatrix(bitmap,self.blatt.seite,byref(m),byref(clip),flags)
            return bitmap
        except BaseException:
            bitmap.close()
            raise

    def _maske(self, fenster, faktor, schwelle):
        bitmap = self._bitmap(fenster,faktor,True)
        try:
            return bitmap.to_numpy().reshape(bitmap.height,bitmap.width) < schwelle
        finally:
            bitmap.close()

    def umfang(self):
        # Einmal entlang des Hinweisstrichs abtasten, dann die moeglichen Schrifthoehen pruefen.
        maske = self._maske((2,-30,1142,31),1.,245)
        fenster = []
        for halbe in (7,9,12,16,22,30):
            teil = maske[30-halbe:31+halbe,:38*halbe]
            box = schriftumfang(teil,halbe)
            if box:
                l,t,r,b = box
                fenster.append((l+1,t-halbe-1,r+3,b-halbe+1))
        if not fenster:
            return None
        # Am weitesten sichtbares Zeilenende verwenden, auch bei abgesetztem Grenzmass.
        ende = max(f[2] for f in fenster)
        lang = np.array([f for f in fenster if f[2] >= ende-1])
        return (*lang[:,:2].min(axis=0),*lang[:,2:].max(axis=0))

    def blattecken(self, fenster):
        l,t,r,b = fenster
        ecken = (self.ort+np.array([(l,t),(r,t),(r,b),(l,b)]) @ self.achsen)/self.blattpixel
        if ecken.min() < 0 or ecken.max() > 1:
            return None
        return tuple(map(tuple,ecken))

    def lesemasken(self, fenster):
        l,t,r,b = fenster
        for hoehe in (72,60,64):
            yield self._maske(fenster,min(1600/(r-l),hoehe/(b-t)),185)


def zeilenvorschau(blatt, ecken, max_breite, max_hoehe):
    h,w = blatt.bild.shape[:2]
    a,b,_,d = np.asarray(ecken)*[w,h]
    laenge,hoehe = np.linalg.norm(b-a),np.linalg.norm(d-a)
    rand = .22*hoehe
    streifen = Schriftstreifen(blatt,a,(b-a)/laenge,(d-a)/hoehe)
    faktor = min(max_breite/(laenge+2*rand),max_hoehe/(hoehe+2*rand))
    return streifen._bitmap((-rand,-rand,laenge+rand,hoehe+rand),faktor,False)
