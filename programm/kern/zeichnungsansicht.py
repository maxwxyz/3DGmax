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
        return spitze, basis
    return None


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
    def __init__(self, blatt):
        import ctypes as ct
        from pypdfium2 import raw
        h, w = blatt.bild.shape[:2]
        self.groesse = np.array([w, h])
        mask = blatt.bild.min(axis=2) < 245
        ks = blatt.koordinaten
        o = np.array(ks.to_page(0, 0))
        basis = np.array([(ks.to_page(w, 0)-o)/w, (ks.to_page(0, h)-o)/h])
        zur_ansicht = np.linalg.inv(basis)
        kreise, linien, pfeile = {}, [], []
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
            ringraender = []
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
                elif strich.value and 2 <= len(p) <= 4 and np.linalg.norm(p[0]-p[-1]) >= 3:
                    for start, ende in zip(p, p[1:]):
                        if np.linalg.norm(start-ende) >= 3 and _sichtbar(mask, np.linspace(start, ende, 9)):
                            linien.append((start, ende))
                elif fuellung.value and not strich.value:
                    balken = _duenner_balken(p)
                    if balken is not None and _sichtbar(mask, np.linspace(*balken, 9)):
                        linien.append(balken)
                if fuellung.value and 3 <= len(p) <= 5:
                    pfeil = _pfeil(p)
                    if pfeil is not None and _sichtbar(mask, [p.mean(axis=0)]):
                        pfeile.append(pfeil)
            if len(ringraender) == 2:
                (k, sinn), (j, sinn2) = ringraender
                if (math.hypot(k.x-j.x, k.y-j.y) < .15 and abs(k.r-j.r) < min(4., .18*k.r)
                        and (sinn != sinn2 or fuellung.value == raw.FPDF_FILLMODE_ALTERNATE)):
                    ring = Blattkreis((k.x+j.x)/2, (k.y+j.y)/2, (k.r+j.r)/2)
                    kreise[tuple(round(v, 1) for v in (ring.x, ring.y, ring.r))] = ring
        self.kreise = list(kreise.values())
        self.linien = np.array(linien).reshape(-1,2,2)
        self.enden = cKDTree(self.linien.reshape(-1,2))
        self.pfeile = pfeile

    def im_bereich(self, box):
        l, t, r, b = (np.array(box).reshape(2,2) * self.groesse).ravel()
        return [k for k in self.kreise if l <= k.x-k.r and k.x+k.r <= r and t <= k.y-k.r and k.y+k.r <= b]

    def hinweisziel(self, box, kreise):
        """Ein einzelner unverzweigter Linienzug vom Beschriftungsrand zur gefuellten Pfeilspitze."""
        if not self.pfeile or not kreise:
            return None
        (l,t), (r,b) = np.array(box).reshape(2,2) * self.groesse
        seiten = ((l,(t+b)/2), (r,(t+b)/2), ((l+r)/2,t), ((l+r)/2,b))
        starts = []
        for ort, aussen in zip(seiten, ((-1,0),(1,0),(0,-1),(0,1))):
            for index in self.enden.query_ball_point(ort, 2.8):
                i, k = divmod(index, 2)
                weg = self.linien[i,1-k] - self.linien[i,k]
                if weg @ aussen > .25*np.linalg.norm(weg):
                    starts.append(index)
        if len(starts) != 1:
            return None
        index, benutzt = starts[0], set()
        while index//2 not in benutzt and len(benutzt) < 4:
            i, k = divmod(index, 2)
            benutzt.add(i)
            start, ende = self.linien[i, [k, 1-k]]
            laenge = np.linalg.norm(ende-start)
            richtung = (ende-start) / laenge
            kandidaten = self.enden.query_ball_point((start+ende)/2, laenge/2+1.5)
            for j in kandidaten:
                if j//2 in benutzt:
                    continue
                v = self.linien[j//2, j%2] - start
                dist = v @ richtung
                if 1.5 < dist < laenge-1.5 and np.linalg.norm(v-dist*richtung) < 1.5:
                    return None
            spitzen = [s for s, basis in self.pfeile if
                       min(np.linalg.norm(ende-s), np.linalg.norm(ende-basis)) < 2
                       and richtung @ (s-basis) > .94*np.linalg.norm(s-basis)]
            if spitzen:
                if len(spitzen) != 1:
                    return None
                x,y = spitzen[0]
                # Auch unbekannte oder konzentrische Nachbarkreise koennen das Hinweisziel sein.
                alle = [a for a in self.kreise if abs(math.hypot(a.x-x, a.y-y)-a.r) < 1.6]
                if len(alle) == 1:
                    return next((a for a in kreise if (a.x,a.y,a.r) == (alle[0].x,alle[0].y,alle[0].r)), None)
                return None
            nachbarn = [j for j in self.enden.query_ball_point(ende, 1.5) if j//2 not in benutzt]
            if len(nachbarn) != 1:
                return None
            index = nachbarn[0]
        return None


def modellkreise(modell, pruefe=lambda: None):
    """Kreisraender aus zusammengehoerenden Zylindermantelflaechen, getrennt je Hauptansicht."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.GeomAbs import GeomAbs_Circle
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    from .pmi_vorschlag import _flaeche_info
    boegen = defaultdict(list)
    for i, f in enumerate(modell.flaechen):
        if i % 32 == 0:
            pruefe()
        info = _flaeche_info(f)
        if not info or info[0] != "zylinder":
            continue
        achse = np.abs(info[1]["achse"])
        k = int(np.argmax(achse))
        if np.linalg.norm(np.delete(achse, k)) > 1e-6:
            continue
        u, v = (k+1) % 3, (k+2) % 3
        ex = TopExp_Explorer(f, TopAbs_EDGE)
        while ex.More():
            kurve = BRepAdaptor_Curve(topods.Edge(ex.Current()))
            ex.Next()
            if kurve.GetType() != GeomAbs_Circle:
                continue
            kreis = kurve.Circle()
            normal = kreis.Axis().Direction().Coord()[k]
            if abs(normal) < 1 - 1e-9 or not math.isclose(kreis.Radius(), info[1]["r"], abs_tol=1e-6):
                continue
            mitte = kreis.Location().Coord()
            start, ende = kurve.FirstParameter(), kurve.LastParameter()
            punkt = kurve.Value(start if normal > 0 else ende).Coord()
            phi = math.atan2(punkt[v]-mitte[v], punkt[u]-mitte[u]) % math.tau
            schluessel = (k, *(round(mitte[j], 6) for j in (u, v, k)), round(kreis.Radius(), 6))
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


def _passungen(m, z, pruefe):
    # Mit einem Kreispaar sind Massstab und Verschiebung festgelegt. Die uebrigen Kreise pruefen die Lage.
    block = max(1, 8192 // len(z))
    for xy in (m[:, :2], m[:, 1::-1]):
        for vorzeichen in ((1,1), (1,-1), (-1,1), (-1,-1)):
            p = xy * vorzeichen
            baum = cKDTree(np.column_stack((p, m[:, 2])))
            gesehen = set()
            for anker in z:
                relativ = z[:, :2] - anker[:2]
                grob = 1.5 + .015 * np.linalg.norm(relativ, axis=1)
                for i in range(0, len(m), block):
                    pruefe()
                    radien = m[i:i+block, 2]
                    s = anker[2] / radien
                    orte = np.empty((len(s), len(z), 3))
                    orte[:, :, :2] = relativ / s[:, None, None] + p[i:i+block, None, :]
                    orte[:, :, 2] = z[:, 2] / s[:, None]
                    dist, ids = baum.query(orte)
                    nah = dist*s[:, None] <= grob
                    for j in np.flatnonzero(nah.sum(axis=1) >= 3):
                        ziel = np.flatnonzero(nah[j])
                        quelle = ids[j, ziel]
                        schluessel = tuple(zip(ziel.tolist(), quelle.tolist()))
                        if schluessel in gesehen:
                            continue
                        if len(gesehen)*len(z) > 32768:
                            gesehen.clear()  # Nur ein Rechencache, keine Begrenzung der geprueften Hypothesen.
                        gesehen.add(schluessel)
                        a, b = p[quelle], z[ziel, :2]
                        am, bm = a.mean(axis=0), b.mean(axis=0)
                        a0 = a - am
                        if not np.any(a0):
                            continue
                        faktor = np.sum(a0*(b-bm)) / np.sum(a0*a0)
                        if faktor <= 0:
                            continue
                        modell = np.column_stack(((z[:, :2]-bm)/faktor + am, z[:, 2]/faktor))
                        abstand, index = baum.query(modell, k=2)
                        eindeutig = (abstand[:, 0]*faktor <= .75) & (abstand[:, 1]*faktor > .75)
                        ziel = np.flatnonzero(eindeutig)
                        quelle = index[ziel, 0]
                        if len(ziel) < 3 or len(set(quelle)) != len(ziel):
                            continue
                        mitten = []
                        for ort in z[ziel, :2]:
                            if all(np.linalg.norm(ort-q) > 1.5 for q in mitten):
                                mitten.append(ort)
                        if len(mitten) < 3:
                            continue
                        streuung = np.linalg.svd(mitten-np.mean(mitten, axis=0), compute_uv=False)
                        if streuung[1] > max(2., .01*streuung[0]):
                            yield (len(mitten), len(ziel)), zip(quelle, ziel)


def zuordnen(kreise, ansichten, pruefe=lambda: None):
    """Nur Zuordnungen behalten, die alle gleich gut passenden Hauptansichten gemeinsam haben."""
    if len(kreise) < 3:
        return []
    def daten(zeilen):
        return np.array([(k.x, k.y, k.r) for k in zeilen])
    z = daten(kreise)
    beste, sicher = (0, 0), {}
    for gruppe in ansichten:
        if len(gruppe) < 3:
            continue
        for rang, treffer in _passungen(daten(gruppe), z, pruefe):
            if rang < beste:
                continue
            neu = {j: gruppe[i].flaechen for i,j in treffer}
            if rang == beste:
                sicher = {j: ids for j, ids in sicher.items() if ids == neu.get(j)}
            else:
                beste, sicher = rang, neu
    return [Blattkreis(kreise[j].x, kreise[j].y, kreise[j].r, ids) for j, ids in sorted(sicher.items()) if ids]
