"""Kreismuster einer orthogonalen PDF-Ansicht den Zylinderflaechen eines Einzelteils zuordnen."""

from collections import defaultdict
from dataclasses import dataclass
import math

import numpy as np
from scipy.spatial import cKDTree


@dataclass(frozen=True)
class Blattkreis:
    x: float
    y: float
    r: float
    flaechen: frozenset = frozenset()
    tauschgruppe: frozenset = frozenset()

    @property
    def mitte(self):
        return self.x, self.y


def _kreis(punkte):
    # Eine volle Umdrehung in Pfadreihenfolge pruefen. Ellipsen und offene Boegen auslassen.
    p = np.array(punkte)
    if len(p) < 12 or not np.isfinite(p).all():
        return None
    mitte = (p.min(axis=0) + p.max(axis=0)) / 2
    d = p - mitte
    radien = np.linalg.norm(d, axis=1)
    r = float(radien.mean())
    if r < 2 or np.max(np.abs(radien - r)) > max(.05, .008 * r):
        return None
    phi = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
    schritte = np.diff(phi)
    if np.max(abs(schritte)) > .56 or abs(abs(phi[-1]-phi[0]) - 2*np.pi) > .12:
        return None
    if np.abs(schritte).sum() > 2*np.pi + .12:
        return None
    return Blattkreis(*map(float, mitte), r)


def _teilpfade(obj):
    import ctypes as ct
    from pypdfium2 import raw
    x, y = ct.c_float(), ct.c_float()
    punkte, kontrollen = [], []
    for i in range(raw.FPDFPath_CountSegments(obj)):
        seg = raw.FPDFPath_GetPathSegment(obj, i)
        if not raw.FPDFPathSegment_GetPoint(seg, x, y):
            return
        z = np.array((x.value, y.value))
        typ = raw.FPDFPathSegment_GetType(seg)
        if typ == raw.FPDF_SEGMENT_MOVETO:
            if punkte:
                yield punkte
            punkte, kontrollen = [z], []
        elif typ == raw.FPDF_SEGMENT_LINETO:
            punkte.append(z)
        elif typ == raw.FPDF_SEGMENT_BEZIERTO and punkte:
            kontrollen.append(z)
            if len(kontrollen) == 3:
                a, (b, c, d) = punkte[-1], kontrollen
                for t in np.arange(1, 9) / 8:
                    punkte.append((1-t)**3*a + 3*(1-t)**2*t*b + 3*(1-t)*t*t*c + t**3*d)
                kontrollen = []
        if raw.FPDFPathSegment_GetClose(seg) and punkte:
            punkte.append(punkte[0])
    if punkte:
        yield punkte


def _pfeil(p):
    while len(p) > 3 and np.linalg.norm(p[0]-p[-1]) < .1:
        p = p[:-1]
    if len(p) != 3:
        return None
    kanten = np.linalg.norm(p-np.roll(p, -1, axis=0), axis=1)
    i = int(kanten.argmin())
    basis = (p[i] + p[(i+1) % 3]) / 2
    spitze = p[(i+2) % 3]
    if (1 <= kanten[i] < .65 * kanten.max() and kanten.max() < 45
            and abs(kanten[(i+1) % 3]-kanten[(i+2) % 3]) < .4*kanten[i]):
        return spitze, basis, p
    return None


def _im_dreieck(linie, ecken):
    # Vorzeichenbehaftete Abstaende zu den drei Kanten, fuer beide Strichenden.
    kanten = np.roll(ecken, -1, axis=0) - ecken
    delta = linie[:, None, :] - ecken
    abstand = (kanten[:, 0]*delta[:, :, 1] - kanten[:, 1]*delta[:, :, 0]) / np.linalg.norm(kanten, axis=1)
    return (abstand >= -.6).all() or (abstand <= .6).all()


def _duenner_balken(p):
    # Manche PDF-Drucker geben einen geraden Strich als gefuelltes schmales Rechteck aus.
    if not 4 <= len(p) <= 12 or np.linalg.norm(p[0]-p[-1]) > .15:
        return None
    p = p[:-1]
    mitte = p.mean(axis=0)
    _, basis = np.linalg.eigh((p-mitte).T @ (p-mitte))
    ort = (p-mitte) @ basis
    unten, oben = ort.min(axis=0), ort.max(axis=0)
    breite, laenge = oben-unten
    if laenge < 3 or not .015 < breite < min(4., .12*laenge):
        return None
    x, y = ort.T
    inhalt = abs(x @ np.roll(y, 1) - y @ np.roll(x, 1)) / 2
    if inhalt < .8 * breite*laenge:
        return None
    return np.array([[(oben[0]+unten[0])/2, z] for z in (unten[1], oben[1])]) @ basis.T + mitte


def _sichtbar(mask, p):
    h, w = mask.shape
    x, y = np.rint(np.asarray(p)).astype(int).T
    if x.min() < 1 or y.min() < 1 or x.max() >= w-1 or y.max() >= h-1:
        return False
    return np.logical_or.reduce([mask[y+i,x+j] for i,j in ((0,0),(-1,0),(1,0),(0,-1),(0,1))]).mean() > .88


class Blattgeometrie:
    def __init__(self, blatt, *, mit_rundungen=False):
        import ctypes as ct
        from pypdfium2 import raw
        h, w = blatt.bild.shape[:2]
        self.groesse = np.array([w, h])
        mask = blatt.bild.min(axis=2) < 245
        ks = blatt.koordinaten
        o = np.array(ks.to_page(0, 0))
        basis = np.array([(ks.to_page(w, 0)-o)/w, (ks.to_page(0, h)-o)/h])
        zur_ansicht = np.linalg.inv(basis)
        kreise, linien, pfeile, konturen = {}, [], [], []
        self.rundungen = []
        if mit_rundungen:
            from .rundkontur import rundrechteck, druckrand
        for obj in blatt.seite.get_objects(filter=[raw.FPDF_PAGEOBJ_PATH]):
            fuellung, strich = ct.c_int(), ct.c_int()
            if not raw.FPDFPath_GetDrawMode(obj, fuellung, strich):
                continue
            matrix = obj.get_matrix()
            eltern = obj.container
            while eltern is not None:
                matrix = matrix.multiply(eltern.get_matrix())
                eltern = eltern.container
            a, b, c, d, ex, ey = matrix.get()
            abbildung = np.array([(a, b), (c, d)]) @ zur_ansicht
            verschiebung = (np.array([ex, ey]) - o) @ zur_ansicht
            ringraender, rundraender = [], []
            for pfad in _teilpfade(obj):
                p = np.asarray(pfad) @ abbildung + verschiebung
                if len(p) >= 12:
                    k = _kreis(p)
                    if k and _sichtbar(mask, p[::max(1, len(p)//36)]):
                        if strich.value:
                            kreise[tuple(round(v, 1) for v in (k.x, k.y, k.r))] = k
                        elif fuellung.value:
                            x, y = p.T
                            ringraender.append((k, np.sign(x @ np.roll(y, 1) - y @ np.roll(x, 1))))
                    elif mit_rundungen and (q := rundrechteck(p)) is not None and _sichtbar(mask, p):
                        if strich.value:
                            self.rundungen.append(q)
                        elif fuellung.value:
                            x, y = p.T
                            rundraender.append((q, np.sign(x @ np.roll(y,1)-y @ np.roll(x,1))))
                elif strich.value and 2 <= len(p) <= 4 and np.linalg.norm(p[0]-p[-1]) >= 3:
                    for start, ende in zip(p, p[1:]):
                        if np.linalg.norm(start-ende) >= 3 and _sichtbar(mask, np.linspace(start, ende, 9)):
                            linien.append((start, ende))
                elif fuellung.value and not strich.value:
                    balken = _duenner_balken(p)
                    if balken is not None and _sichtbar(mask, np.linspace(*balken, 9)):
                        linien.append(balken)
                if 3 <= len(p) <= 5:
                    pfeil = _pfeil(p)
                    if pfeil is not None:
                        if fuellung.value and _sichtbar(mask, [p.mean(axis=0)]):
                            pfeile.append(pfeil)
                        elif strich.value and _sichtbar(mask, p):
                            konturen.append((p[0], p[-1], pfeil))
            if rundraender:
                q = druckrand(rundraender, fuellung.value == raw.FPDF_FILLMODE_ALTERNATE)
                if q is not None:
                    self.rundungen.append(q)
            if len(ringraender) == 2:
                (k, sinn), (j, sinn2) = ringraender
                if (math.hypot(k.x-j.x, k.y-j.y) < .15 and abs(k.r-j.r) < min(4., .18*k.r)
                        and (sinn != sinn2 or fuellung.value == raw.FPDF_FILLMODE_ALTERNATE)):
                    ring = Blattkreis((k.x+j.x)/2, (k.y+j.y)/2, (k.r+j.r)/2)
                    kreise[tuple(round(v, 1) for v in (ring.x, ring.y, ring.r))] = ring
        self.kreise = list(kreise.values())
        self.linien = np.array(linien).reshape(-1,2,2)
        self.enden = cKDTree(self.linien.reshape(-1,2))
        # Bei geplotteten Pfeilen kann die dritte Dreiecksseite ein eigener Strich sein.
        for a, b, pfeil in konturen:
            nachbarn = self.enden.query_ball_point(a, .3)
            if np.linalg.norm(a-b) <= .3 or any(np.linalg.norm(self.linien[j//2,1-j%2]-b) <= .3 for j in nachbarn):
                pfeile.append(pfeil)
        laengen = np.linalg.norm(self.linien[:, 0]-self.linien[:, 1], axis=1)
        # Lange und kurze Linien getrennt indizieren, damit die Umgebungssuche lokal bleibt.
        self.schaftindex = []
        groessen = np.frexp(laengen)[1]
        for klasse in np.unique(groessen):
            ids = np.flatnonzero(groessen == klasse)
            self.schaftindex.append((cKDTree(self.linien[ids].mean(axis=1)), ids, laengen[ids].max()/2+1.5))
        # Auch drei einzeln geplottete Seiten bilden einen geschlossenen Pfeilkopf.
        for i in np.flatnonzero(laengen < .65 * 45):
            a, b = self.linien[i]
            links = self.enden.query_ball_point(a, .3)
            rechts = self.enden.query_ball_point(b, .3)
            if not (2 <= len(links) <= 12 and 2 <= len(rechts) <= 12):
                continue
            for j in links:
                if j//2 == i:
                    continue
                c = self.linien[j//2, 1-j%2]
                if not any(k//2 not in (i, j//2) and np.linalg.norm(self.linien[k//2, 1-k%2]-c) <= .3
                           for k in rechts):
                    continue
                kandidat = _pfeil(np.array([a, b, c]))
                if kandidat is not None and np.linalg.norm(kandidat[0]-c) < .3:
                    pfeile.append(kandidat)
        eindeutig = {tuple(np.round(np.concatenate(p[:2]), 1)): p for p in pfeile}
        self.pfeile = list(eindeutig.values())
        self.pfeilenden = cKDTree(np.array([eintrag[:2] for eintrag in self.pfeile]).reshape(-1,2))

    def im_bereich(self, box):
        l, t, r, b = (np.array(box).reshape(2,2) * self.groesse).ravel()
        return [k for k in self.kreise if l <= k.x-k.r and k.x+k.r <= r and t <= k.y-k.r and k.y+k.r <= b]

    def hinweisziel(self, box, kreise, durchmesseranfang=None, musterzeile=False):
        """Ein einzelner unverzweigter Linienzug vom Beschriftungsrand zur Dreiecksspitze."""
        if not self.pfeile or not kreise:
            return None
        starts = self._starts(box, durchmesseranfang, musterzeile)
        ziele = self._verfolge(starts, kreise, 1)
        return ziele[0] if ziele else None

    def hinweisgruppe(self, box, kreise, anzahl):
        """Ein gezeichnetes Pfeilende pro gedruckter Wiederholung."""
        if anzahl < 2 or anzahl > len(kreise) or not self.pfeile:
            return ()
        ziele = self._verfolge(self._starts(box, None, True), kreise, anzahl)
        if len(ziele) != anzahl or max(k.r for k in ziele)-min(k.r for k in ziele) > .75:
            return ()
        if any(math.hypot(k.x-q.x, k.y-q.y) < 1.5 for i,k in enumerate(ziele) for q in ziele[:i]):
            return ()
        return tuple(sorted(ziele, key=lambda k: (k.y, k.x)))

    def schriftenden(self, kreise, pruefe=lambda: None):
        """Freie Enden achsparalleler Hinweisstriche mit Pfeilziel im gewaehlten Bohrbild."""
        if not kreise or not self.pfeile:
            return []
        orte = []
        delta = self.linien[:, 1]-self.linien[:, 0]
        for achse in (0, 1):
            parallel = (abs(delta[:, 1-achse]) <= .55) & (abs(delta[:, achse]) >= 5)
            for nr, i in enumerate(np.flatnonzero(parallel)):
                if nr % 32 == 0:
                    pruefe()
                for k in (0, 1):
                    start, ende = self.linien[i, [k, 1-k]]
                    if len(self.enden.query_ball_point(start, 1.5)) == 1 and self._verfolge([2*i+k], kreise, len(kreise)):
                        orte.append((start, 1 if start[achse] > ende[achse] else -1, achse))
        return orte

    def _starts(self, box, durchmesseranfang, musterzeile):
        (l,t), (r,b) = np.array(box).reshape(2,2) * self.groesse
        seiten = ((l,(t+b)/2), (r,(t+b)/2), ((l+r)/2,t), ((l+r)/2,b))
        starts = []
        for ort, aussen in zip(seiten, ((-1,0),(1,0),(0,-1),(0,1))):
            for index in self.enden.query_ball_point(ort, 2.8):
                i, k = divmod(index, 2)
                weg = self.linien[i,1-k] - self.linien[i,k]
                if weg @ aussen > .25*np.linalg.norm(weg):
                    starts.append(index)
        if not starts and musterzeile:
            # Den Schriftabstand in Laengsrichtung der gedruckten Masszeile ueberbruecken.
            achse = int(b-t > r-l)
            haltepunkte = seiten[2:] if achse else seiten[:2]
            h = r-l if achse else b-t
            for ort, sinn in zip(haltepunkte, (-1, 1)):
                for j in self.enden.query_ball_point(ort, .85*h):
                    i, k = divmod(j, 2)
                    start, weiter = self.linien[i, [k, 1-k]]
                    weg = weiter-start
                    if (0 <= sinn*(start[achse]-ort[achse]) <= .8*h and abs(start[1-achse]-ort[1-achse]) <= .2*h
                            and sinn*weg[achse] >= .45*h and abs(weg[1-achse]) <= .5
                            and len(self.enden.query_ball_point(start, 1.5)) == 1):
                        starts.append(j)
        if not starts and durchmesseranfang is not None and r-l > 2*(b-t):
            starts = self._anschluss_am_mass(l, t, b-t, durchmesseranfang)
        return list(dict.fromkeys(starts))

    def _anschluss_am_mass(self, l, t, h, durchmesseranfang):
        # Der Pfeil kann an der Masszeile unmittelbar ueber dem Toleranzrahmen enden.
        starts = []
        for j in self.enden.query_ball_point((l, t-.6*h), 1.7*h):
            i, k = divmod(j, 2)
            endpunkt, weiter = self.linien[i, [k, 1-k]]
            x, y = endpunkt
            if not (l-1.6*h <= x <= l+.4*h and t-1.15*h <= y <= t-.25*h):
                continue
            if abs(weiter[1]-y) > .5 or x-weiter[0] < h*.45:
                continue
            if len(self.enden.query_ball_point(endpunkt, 1.5)) != 1:
                continue
            box = np.array([x+1, y-.49*h, x+3.6*h, min(t-1, y+.49*h)]).reshape(2,2)
            if durchmesseranfang(tuple(np.clip(box/self.groesse, 0., 1.).ravel())):
                starts.append(j)
        return starts

    def _schaefte_am_punkt(self, punkt):
        # Die ankommende Linie kann mitten auf einem durchgehenden Querstueck enden.
        for baum, ids, reichweite in self.schaftindex:
            for j in baum.query_ball_point(punkt, reichweite):
                i = ids[j]
                a, b = self.linien[i]
                weg = b-a
                laenge = np.linalg.norm(weg)
                dist = (punkt-a) @ weg / laenge
                if 1.5 < dist < laenge-1.5:
                    fuss = a + dist/laenge*weg
                    if np.linalg.norm(fuss-punkt) <= 1.5:
                        yield i, fuss

    def _linienende(self, index, kreise, abzweig):
        i, k = divmod(index, 2)
        start, ende = self.linien[i, [k, 1-k]]
        if abzweig is not None:
            start = abzweig
        laenge = np.linalg.norm(ende-start)
        richtung = (ende-start) / laenge
        nahe = {j//2 for j in self.pfeilenden.query_ball_point(ende, 2)}
        spitzen = []
        for j in nahe:
            s, basis, kontur = self.pfeile[j]
            if richtung @ (s-basis) > .94*np.linalg.norm(s-basis):
                spitzen.append((s, kontur))
        if len(spitzen) > 1:
            return None
        nachbarn = []
        for j in self.enden.query_ball_point((start+ende)/2, laenge/2+1.5):
            if j//2 == i:
                continue
            v = self.linien[j//2, j%2] - start
            dist = v @ richtung
            am_ende = np.linalg.norm(v-(ende-start)) <= 1.5
            auf_linie = 1.5 < dist < laenge-1.5 and np.linalg.norm(v-dist*richtung) < 1.5
            if am_ende or auf_linie:
                if spitzen and _im_dreieck(self.linien[j//2], spitzen[0][1]):
                    continue
                if spitzen and am_ende:
                    return None
                nachbarn.append((j, am_ende))
        quer = []
        if spitzen:
            x,y = spitzen[0][0]
            alle = [a for a in self.kreise if abs(math.hypot(a.x-x, a.y-y)-a.r) < 1.6]
            if len(alle) != 1:
                return None
            ziel = next((a for a in kreise if (a.x,a.y,a.r) == (alle[0].x,alle[0].y,alle[0].r)), None)
            if ziel is None:
                return None
        else:
            ziel = None
            # Ein seitlicher Ast darf ein offenes Ende der weiterlaufenden Linie nicht verdecken.
            quer = list(self._schaefte_am_punkt(ende))
            if not quer and not any(am_ende for _, am_ende in nachbarn):
                return None
        return ziel, [j for j, _ in nachbarn], quer

    def _verfolge(self, starts, kreise, anzahl):
        if not starts or len(starts) > anzahl:
            return ()
        offen = [(j, None) for j in starts]
        benutzt = {j//2 for j in starts}
        ziele = []
        while offen:
            index, abzweig = offen.pop()
            ergebnis = self._linienende(index, kreise, abzweig)
            if ergebnis is None:
                return ()
            ziel, nachbarn, quer = ergebnis
            if ziel is not None:
                if ziel in ziele:
                    return ()
                ziele.append(ziel)
            neu = [j//2 for j in nachbarn] + [i for i, _ in quer]
            if len(set(neu)) != len(neu) or benutzt.intersection(neu):
                return ()
            benutzt.update(neu)
            offen.extend((j, None) for j in nachbarn)
            for i, fuss in quer:
                offen.extend((2*i+k, fuss) for k in (0, 1))
            # Jeder offene Ast muss noch mindestens einen eigenen Pfeil erreichen.
            if len(ziele) + len(offen) > anzahl:
                return ()
        return tuple(ziele)


def _projektion(richtung, ebenen):
    # Positives und negatives Achsende bezeichnen dieselbe Ansicht. Bei gleich grossen
    # Komponenten dieselbe Bezugsachse waehlen, auch nach Rundung im STEP-Export.
    n = np.asarray(richtung)
    betrag = abs(n)
    k = int(np.flatnonzero(betrag >= betrag.max()-1e-9)[0])
    if n[k] < 0:
        n = -n
    schluessel = tuple(np.round(n, 9))
    if schluessel not in ebenen:
        u = np.eye(3)[(k+1) % 3]
        u -= (u @ n)*n
        u /= np.linalg.norm(u)
        ebenen[schluessel] = np.array([u, np.cross(n, u), n])
    return schluessel, ebenen[schluessel]


def modellkreise(modell, pruefe=lambda: None):
    """Kreisraender aus zusammengehoerenden Zylindermantelflaechen, getrennt nach Achsrichtung."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.GeomAbs import GeomAbs_Circle
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    from .pmi_vorschlag import _flaeche_info
    boegen = defaultdict(list)
    ebenen = {}
    for i, f in enumerate(modell.flaechen):
        if i % 32 == 0:
            pruefe()
        info = _flaeche_info(f)
        if not info or info[0] != "zylinder":
            continue
        richtung, basis = _projektion(info[1]["achse"], ebenen)
        zentrum = basis[:2] @ info[1]["punkt"]
        ex = TopExp_Explorer(f, TopAbs_EDGE)
        while ex.More():
            kante = topods.Edge(ex.Current())
            kurve = BRepAdaptor_Curve(kante)
            ex.Next()
            if kurve.GetType() != GeomAbs_Circle:
                continue
            kreis = kurve.Circle()
            normal = basis[2] @ kreis.Axis().Direction().Coord()
            if abs(normal) < 1 - 1e-9 or not math.isclose(kreis.Radius(), info[1]["r"], abs_tol=1e-6):
                continue
            mitte = np.array(kreis.Location().Coord())
            if np.linalg.norm(basis[:2] @ mitte - zentrum) > max(BRep_Tool.Tolerance(kante), 1e-5):
                continue
            start, ende = kurve.FirstParameter(), kurve.LastParameter()
            punkt = kurve.Value(start if normal > 0 else ende).Coord()
            x, y = basis[:2] @ (punkt-mitte)
            phi = math.atan2(y, x) % math.tau
            # Getrennt angepasste Halbkreise koennen leicht verschiedene Mittelpunkte
            # haben. Fuer ihre gemeinsame Projektion ist die Zylinderachse massgeblich.
            schluessel = (richtung, *np.round(zentrum, 6), round(basis[2] @ mitte, 6), round(info[1]["r"], 6))
            boegen[schluessel].append((phi, phi + ende-start, i))
    ansichten = defaultdict(lambda: defaultdict(list))
    for (k, x, y, _, r), teile in boegen.items():
        intervalle = [(max(0., a-s), min(math.tau, b-s)) for a,b,_ in teile for s in (0., math.tau) if b >= s]
        bis = 0.
        for a, b in sorted(intervalle):
            if a > bis + 1e-5:
                break
            bis = max(bis, b)
        if bis >= math.tau-1e-5:
            # Getrennte koaxiale Sackloecher sind in der Projektion deckungsgleich.
            komponenten = ansichten[k][x, y, r]
            wand = {i for _, _, i in teile}
            for andere in komponenten.copy():
                if wand & andere:
                    wand.update(andere)
                    komponenten.remove(andere)
            komponenten.append(wand)
    return [[Blattkreis(*ort, frozenset(wand[0]) if len(wand) == 1 else frozenset())
             for ort, wand in gruppe.items()] for gruppe in ansichten.values()]


def _modellpunkte(mitten, radien):
    return np.column_stack((mitten.real, mitten.imag, radien))


def _pruefe_passung(baum, modell, blatt, radien, ursprung, faktor, grob, cache):
    # Komplexer Faktor: gemeinsamer Massstab und beliebige Drehung in der Zeichenebene.
    ort = ursprung + blatt*faktor
    massstab = abs(faktor)
    abstand, ids = baum.query(_modellpunkte(ort, radien*massstab))
    ziel = np.flatnonzero(abstand <= grob*massstab)
    if len(ziel) < 3:
        return None
    quelle = ids[ziel]
    schluessel = tuple(zip(ziel.tolist(), quelle.tolist()))
    if schluessel in cache:
        return None
    if len(cache)*len(blatt) > 32768:
        cache.clear()
    cache.add(schluessel)
    a, b = blatt[ziel], modell[quelle]
    am, bm = a.mean(), b.mean()
    norm = np.vdot(a-am, a-am).real
    if norm < 1:
        return None
    faktor = np.vdot(a-am, b-bm) / norm
    massstab = abs(faktor)
    if massstab <= 0:
        return None
    punkte = _modellpunkte(bm + (blatt-am)*faktor, radien*massstab)
    abstand, ids = baum.query(punkte, k=2)
    eindeutig = (abstand[:, 0] <= .75*massstab) & (abstand[:, 1] > .75*massstab)
    ziel = np.flatnonzero(eindeutig)
    quelle = ids[ziel, 0]
    if len(ziel) < 3 or len(set(quelle)) != len(ziel):
        return None
    xy = np.column_stack((blatt[ziel].real, blatt[ziel].imag))
    zentren = cKDTree(xy)
    einzeln = np.ones(len(xy), dtype=bool)
    for i in np.flatnonzero(zentren.query(xy, k=2)[0][:, 1] <= 1.5):
        if einzeln[i]:
            einzeln[zentren.query_ball_point(xy[i], 1.5)] = False
            einzeln[i] = True
    xy = xy[einzeln]
    if len(xy) < 3:
        return None
    streuung = np.linalg.svd(xy-xy.mean(axis=0), compute_uv=False)
    if streuung[1] <= max(2., .01*streuung[0]):
        return None
    return (len(xy), len(ziel)), zip(quelle, ziel)


def _ankerfolge(blatt, pruefe):
    # Zuerst raeumlich verteilte Zentren verwenden, damit die Basislinien lang sind.
    folge = [int(np.argmax(abs(blatt-blatt.mean())))]
    abstand = abs(blatt-blatt[folge[0]])
    getrennt = [np.inf]
    while len(folge) < len(blatt):
        if len(folge) % 32 == 0:
            pruefe()
        abstand[folge[-1]] = -1.
        j = int(np.argmax(abstand))
        getrennt.append(min(getrennt[-1], abstand[j]))
        folge.append(j)
        np.minimum(abstand, abs(blatt-blatt[j]), out=abstand)
    return folge, getrennt


def _passungen(m, z, pruefe, minimum):
    modell = m[:, 0] + 1j*m[:, 1]
    blatt = z[:, 0] + 1j*z[:, 1]
    ebenen = (blatt, blatt.conj())
    baum = cKDTree(m)
    cache = [set(), set()]
    # Die erste Basislinie reicht quer durch die Ansicht. Eine vollstaendige Passung
    # muss dieses Paar enthalten, auch bei einer anderen Drehung oder Spiegelung.
    folge, getrennt = _ankerfolge(blatt, pruefe)
    min_basis = max(3., .15*getrennt[1])

    def paargrenze(anzahl):
        # Bei mindestens K passenden Zentren enthalten die ersten N-K+2 Ringe mindestens
        # zwei passende Zentren. Kurze Basislinien duerfen die Suche nicht beschraenken.
        n = min(len(blatt), len(blatt)-anzahl+2)
        return n if getrennt[n-1] >= min_basis else len(blatt)

    grenze = paargrenze(minimum)
    # Abstaende nur fuer einen Block von Modellzentren gleichzeitig im Speicher halten.
    block = max(1, 32768 // len(m))
    for anfang in range(0, len(m), block):
        pruefe()
        mit = modell[anfang:anfang+block]
        abstand = abs(mit[:, None]-modell)
        ri = m[anfang:anfang+block, 2, None]
        rk = m[:, 2]
        for pos, j in enumerate(folge[:-1]):
            if pos >= grenze-1:
                break
            for q in range(pos+1, grenze):
                if q >= grenze:
                    break
                zweiter = folge[q]
                pruefe()
                laenge = abs(blatt[zweiter]-blatt[j])
                if laenge < 3:
                    continue
                # Die Zentren duerfen je .75 Bildpunkte abweichen. Der daraus moegliche
                # Massstab muss auch beide gedruckten Radien innerhalb .75 Punkten treffen.
                passend = ((abstand > 0)
                           & (abs(laenge*ri - z[j, 2]*abstand) <= .75*abstand + 1.5*ri)
                           & (abs(laenge*rk - z[zweiter, 2]*abstand) <= .75*abstand + 1.5*rk))
                grob = 1.5 + 1.5*(abs(blatt-blatt[j]) + z[:, 2])/laenge
                for n, (ii, k) in enumerate(zip(*np.nonzero(passend))):
                    if n % 32 == 0:
                        pruefe()
                    i = anfang + ii
                    for spiegel, ebene in enumerate(ebenen):
                        faktor = (modell[k]-modell[i])/(ebene[zweiter]-ebene[j])
                        treffer = _pruefe_passung(baum, modell, ebene, z[:, 2], modell[i]-ebene[j]*faktor,
                                                  faktor, grob, cache[spiegel])
                        if treffer is not None:
                            minimum = max(minimum, treffer[0][0])
                            grenze = 2 if treffer[0][1] == len(z) else min(grenze, paargrenze(minimum))
                            yield treffer


def zuordnen(kreise, ansichten, pruefe=lambda: None, *, mit_gruppen=False):
    """Einzelziele und auf Wunsch unteilbare Gruppen aus allen besten Projektionen."""
    from scipy.cluster.hierarchy import DisjointSet
    if len(kreise) < 3:
        return []

    def daten(zeilen):
        return np.array([(k.x, k.y, k.r) for k in zeilen])

    z = daten(kreise)
    beste = (0, 0)
    verbunden = DisjointSet()
    immer = set()
    for gruppe in ansichten:
        if len(gruppe) < max(3, beste[0]):
            continue
        for rang, treffer in _passungen(daten(gruppe), z, pruefe, beste[0]):
            if rang < beste:
                continue
            paare = [(int(j), gruppe[i].flaechen) for i,j in treffer]
            # Auch bei geteilten Mantelflaechen muss jeder Kreis eine eigene Bohrung treffen.
            belegt, doppelt = set(), set()
            for _, wand in paare:
                if wand in belegt:
                    doppelt.add(wand)
                belegt.add(wand)
            sicher = {j for j, wand in paare if wand and wand not in doppelt}
            if rang > beste:
                beste, verbunden, immer = rang, DisjointSet(), sicher
            else:
                immer.intersection_update(sicher)
            for j, wand in paare:
                if wand:
                    verbunden.add(j)
                    verbunden.add(wand)
                    verbunden.merge(j, wand)
    zuordnung = {}
    for teil in verbunden.subsets():
        orte = {j for j in teil if isinstance(j, int)}
        waende = frozenset(teil-orte)
        if not orte <= immer or len(orte) != len(waende):
            continue
        if len(orte) == 1:
            zuordnung[orte.pop()] = (next(iter(waende)), frozenset())
        elif mit_gruppen and sum(map(len, waende)) == len(frozenset().union(*waende)):
            # Jede Passung bildet diese Blattmenge bijektiv auf dieselben Waende ab.
            for j in orte:
                zuordnung[j] = (frozenset(), waende)
    return [Blattkreis(kreise[j].x, kreise[j].y, kreise[j].r, *zuordnung[j]) for j in sorted(zuordnung)]


def muster_am_ziel(anker, anzahl, sichtbar, zugeordnet):
    """Das Mengenmass erfasst alle gleich grossen sichtbaren und zugeordneten Kreise."""
    if anker is None:
        return ()
    ringe = [k for k in sichtbar if abs(k.r-anker.r) <= .75]
    passend = tuple(k for k in zugeordnet if abs(k.r-anker.r) <= .75)
    if len(ringe) != anzahl or len(passend) != anzahl:
        return (anker,)
    if any(math.hypot(k.x-q.x, k.y-q.y) < 1.5 for i,k in enumerate(passend) for q in passend[:i]):
        return (anker,)
    return passend
