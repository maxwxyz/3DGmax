"""Projizierte Toleranzrahmen mit gezeichnetem Geltungshinweis im PDF."""

from ctypes import c_int

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from .pmi_koplanarschrift import _konturzeile
from .pmi_rahmenzusatz import lies_hinweiszeile
from .pmi_strichschrift import _gruppen
from .schriftstreifen import Schriftstreifen
from .zeichnungsabgleich import Blattangabe, lese_angabe
from .zeichnungsansicht import _teilpfade


def _rahmenkanten(blatt):
    from pypdfium2 import raw
    h, w = blatt.bild.shape[:2]
    ks = blatt.koordinaten
    o = np.array(ks.to_page(0, 0))
    zur_ansicht = np.linalg.inv(np.array([(ks.to_page(w, 0)-o)/w, (ks.to_page(0, h)-o)/h]))
    rahmen, stege = [], []
    for obj in blatt.seite.get_objects(filter=[raw.FPDF_PAGEOBJ_PATH]):
        if not 2 <= raw.FPDFPath_CountSegments(obj) <= 8:
            continue
        fuellung, strich = c_int(), c_int()
        if not raw.FPDFPath_GetDrawMode(obj, fuellung, strich) or not strich.value or raw.FPDFPageObj_GetDashCount(obj):
            continue
        matrix = obj.get_matrix()
        eltern = obj.container
        while eltern is not None:
            matrix = matrix.multiply(eltern.get_matrix())
            eltern = eltern.container
        a,b,c,d,x,y = matrix.get()
        basis = np.array([[a,b],[c,d]]) @ zur_ansicht
        ort = (np.array([x,y])-o) @ zur_ansicht
        for pfad in _teilpfade(obj):
            p = np.asarray(pfad) @ basis + ort
            if len(p) == 2 and 4 <= np.linalg.norm(p[1]-p[0]) <= min(w, h)/2:
                stege.append(p)
            elif 5 <= len(p) <= 6 and np.max(np.abs(p[4:]-p[0])) < .5:
                if np.linalg.norm(p[0]+p[2]-p[1]-p[3]) <= .65:
                    rahmen.append(p[:4])
    return rahmen, np.array(stege)


def _leselagen(blatt):
    rahmen, stege = _rahmenkanten(blatt)
    if not len(stege):
        return
    mitten = cKDTree(stege.mean(axis=1))
    for ecken in rahmen:
        for i in range(4):
            o = ecken[i]
            rechts = ecken[(i+1)%4]-o
            quer = ecken[(i-1)%4]-o
            if rechts[0]*quer[1]-rechts[1]*quer[0] < 0:
                rechts, quer = quer, rechts
            laenge, hoehe = np.linalg.norm(rechts), np.linalg.norm(quer)
            if not (4 <= hoehe <= min(blatt.bild.shape[:2])/2 and 1.45*hoehe < laenge < 12*hoehe):
                continue
            achsen = np.array([rechts/laenge, quer/hoehe])
            if np.linalg.det(achsen) < .45:
                continue
            # Der Steg muss vom oberen bis zum unteren Rahmenstrich reichen.
            nachbarn = mitten.query_ball_point(o+(rechts+quer)/2, .5*laenge)
            if not nachbarn:
                continue
            lokal = (stege[nachbarn]-o) @ np.linalg.inv(achsen)
            for steg in lokal:
                x,y = steg.T
                if (abs(x[0]-x[1]) < .65 and .4*hoehe < x.mean() < laenge-.4*hoehe
                        and abs(min(y)) < .65 and abs(max(y)-hoehe) < .65):
                    yield Schriftstreifen(blatt, o, *achsen), laenge/hoehe, hoehe
                    break


def _ohne_bezugszeichen(maske, rahmen, zellen, h):
    """Nur ein grafisch an den Profilrahmen angeschlossenes Bezugszeichen ausnehmen."""
    from .zeichnungsblatt import _zeile
    l, t, _, b = rahmen
    maske = maske.copy()
    for x,y,rechts,unten in zellen:
        if (l-.2*h < x < l+.3*h and b+.12*h < y < b+1.8*h and
                .45*h < rechts-x < 1.4*h and .7*h < unten-y < 1.3*h):
            buchstabe = _zeile(maske[y+2:unten-2,x+2:rechts-2])
            if len(buchstabe) == 1 and "A" <= buchstabe <= "Z":
                # Nur den tatsaechlich an den Rahmen angeschlossenen Schaft und Kasten entfernen.
                labels, _ = ndimage.label(maske, np.ones((3,3)))
                label = labels[t-1,l]
                if label and np.any(labels[y-2:y,x:rechts] == label):
                    # Am benachbarten Text keine verbundenen Pixel loeschen.
                    rand = round(.06*h)
                    kasten = np.s_[b:unten+rand, max(0,x-rand):rechts+rand]
                    maske[kasten] &= labels[kasten] != label
                    maske[y:unten,x:rechts] = False
    return maske


def _schriftblock(maske, rahmen, zellen, h):
    maske = _ohne_bezugszeichen(maske, rahmen, zellen, h)
    l, _, _, b = rahmen
    start = int(b+.07*h)
    links = max(0, round(l-.1*h))
    feld = maske[start:,links:]
    # Ein weit entfernter Blattrand oder Text gehoert nicht zum Rahmen.
    spalten = _gruppen(feld)
    if not spalten or spalten[0][0] > 2*h:
        return None
    ende = spalten[0][1]
    for a,z in spalten[1:]:
        if a-ende > 1.4*h:
            break
        ende = z
    feld = feld[:,:ende]
    zeilen = _gruppen(feld.T)
    if not 1 <= len(zeilen) <= 2:
        return None
    texte, anfaenge = [], []
    for a,z in zeilen:
        zeile = feld[a:z]
        if not .27*h <= z-a <= .85*h:
            return None
        gruppen = _gruppen(zeile)
        if gruppen[0][0] < 1 or len(gruppen) > 20:
            return None
        anfaenge.append(gruppen[0][0])
        lesarten = {lies_hinweiszeile(zeile, anzahl=True, null_pruefen=True), _konturzeile(zeile)} - {None, ""}
        if len(lesarten) != 1:
            return None
        texte.append(lesarten.pop())
    if max(anfaenge)-min(anfaenge) > .35*h or zeilen[0][0] > .9*h:
        return None
    return texte, links+ende, start+zeilen[-1][1]


def _faecher(m, skala, breite, rand):
    from .zeichnungsblatt import _zellen
    zellen = _zellen(m, max_kurz=1.4*skala)
    reihe = sorted(z for z in zellen if abs(z[1]-rand*skala) < .06*skala
                   and abs(z[3]-(1+rand)*skala) < .06*skala
                   and (rand-.06)*skala < z[0] and z[2] < (rand+breite+.06)*skala)
    if not 2 <= len(reihe) <= 5 or any(abs(a[2]-b[0]) > .08*skala for a,b in zip(reihe, reihe[1:])):
        return None
    if abs(reihe[0][0]-rand*skala) > .06*skala or abs(reihe[-1][2]-(rand+breite)*skala) > .06*skala:
        return None
    return zellen, reihe


def _lesung(streifen, breite, hoehe):
    from .zeichnungsblatt import _box, _zeile
    rand = .22
    # Erst die Rahmenfaecher pruefen, dann nur bei lesbarem Rahmen den groesseren Hinweisbereich rendern.
    fenster = np.array([-rand,-rand,breite+rand,1+rand])
    m = streifen._maske(fenster*hoehe, 75/hoehe, 210)
    paar = _faecher(m, 75, breite, rand)
    if not paar:
        return None
    texte = [_zeile(m[t+2:b-2,l+2:r-2]) for l,t,r,b in paar[1]]
    kopf = " | ".join(texte)
    if texte[0] not in ("⌓", "⌖"):
        return None
    skala = 140
    fenster[2:] = [max(15., breite+1), 3.9]
    m = streifen._maske(fenster*hoehe, skala/hoehe, 185)
    paar = _faecher(m, skala, breite, rand)
    if not paar:
        return None
    zellen, reihe = paar
    fein = [_zeile(m[t+2:b-2,l+2:r-2]) for l,t,r,b in reihe]
    if fein[0] != texte[0]:
        return None
    rahmen = streifen.blattecken(np.array([0,0,breite,1])*hoehe)
    if not rahmen:
        return None
    mass = None
    if texte[0] == "⌖":
        from .zeichnung_musterzeile import musterzeile
        mass = musterzeile(streifen, breite, hoehe)
    rahmenbox = (*reihe[0][:2], reihe[-1][2], reihe[0][3])
    fund = _schriftblock(m, rahmenbox, zellen, skala) if fein == texte and lese_angabe(kopf, 1.) else None
    angabe = None
    if fund:
        zeilen, r, u = fund
        text = "\n".join([kopf, *zeilen])
        box = np.array([0,0,max(breite,r/skala-rand),u/skala-rand])
        ecken = streifen.blattecken(box*hoehe)
        if ecken and lese_angabe(text, 1.) is not None:
            angabe = Blattangabe(streifen.blatt.nummer, _box(ecken), text, rahmenbox=_box(rahmen), zeilenecken=ecken)
    if angabe or mass:
        return angabe, rahmen, mass


def rahmen_mit_hinweis(blatt):
    from .zeichnungsblatt import _box
    funde = {}
    for streifen, breite, hoehe in _leselagen(blatt):
        if fund := _lesung(streifen, breite, hoehe):
            angabe, rahmen, mass = fund
            schluessel = (angabe.text if angabe else "", mass.text if mass else "")
            funde.setdefault(_box(rahmen), {})[schluessel] = fund
    for lesarten in funde.values():
        if len(lesarten) == 1:
            yield next(iter(lesarten.values()))
