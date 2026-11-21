"""Gedruckte Kreis- und Ellipsenraender in Blattkoordinaten."""

from dataclasses import dataclass, field, replace
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
    kurz: float = 0.  # Kleine Halbachse bei elliptischer Projektion
    winkel: float = 0.  # Grosse Halbachse im Uhrzeigersinn auf dem Blatt, Grad
    raender: tuple = field(default=(),compare=False,repr=False)  # Modell: Tiefe und Wand je Kreisrand

    @property
    def mitte(self):
        return self.x, self.y

    @property
    def form(self):
        return self.x,self.y,self.r,self.kurz,self.winkel

    def blattort(self, w, h):
        ort = (self.x/w,self.y/h,self.r/w)
        return (*ort,self.kurz/w,self.winkel) if self.kurz else ort

    def halbausdehnung(self):
        if not self.kurz:
            return self.r,self.r
        phi = math.radians(self.winkel)
        c,s = math.cos(phi),math.sin(phi)
        return math.hypot(self.r*c,self.kurz*s),math.hypot(self.r*s,self.kurz*c)

    def randabstand(self, x, y):
        dx,dy = x-self.x,y-self.y
        if not self.kurz:
            return abs(math.hypot(dx,dy)-self.r)
        phi = math.radians(self.winkel)
        c,s = math.cos(phi),math.sin(phi)
        u,v = abs(c*dx+s*dy),abs(c*dy-s*dx)
        # Im ersten Quadranten die Normale durch den angeklickten Punkt suchen.
        a,b = self.r,self.kurz
        lo,hi = 0.,math.pi/2
        for _ in range(20):
            t = (lo+hi)/2
            c,s = math.cos(t),math.sin(t)
            if (b*b-a*a)*c*s+a*u*s-b*v*c < 0:
                lo = t
            else:
                hi = t
        return math.hypot(a*c-u,b*s-v)


def geschlossene_bogenzuege(boegen):
    """Getrennt gezeichnete Boegen nur ueber eindeutige gemeinsame Endpunkte verbinden."""
    if len(boegen) < 2:
        return
    enden = np.array([p[[0, -1]] for p in boegen]).reshape(-1, 2)
    # Drei Nachbarn genuegen, auch bei vielen deckungsgleichen Pfaden.
    abstand, nachbarn = cKDTree(enden).query(enden, k=3, distance_upper_bound=.25)
    paar = np.isfinite(abstand[:, 1]) & ~np.isfinite(abstand[:, 2])
    partner = np.full(len(enden), -1)
    for i in np.flatnonzero(paar):
        a, b = nachbarn[i, :2]
        j = b if a == i else a
        if paar[j] and j//2 != i//2:
            partner[i] = j
    besucht = set()
    for i in range(len(boegen)):
        start = eingang = 2*i
        teile = []
        while eingang >= 0 and eingang//2 not in besucht:
            bogen, seite = divmod(eingang, 2)
            besucht.add(bogen)
            p = boegen[bogen]
            teile.append(p[::-1] if seite else p)
            eingang = partner[2*bogen + (1-seite)]
            if eingang == start:
                yield np.concatenate(teile)
                break


def ellipse(p):
    if len(p) < 12 or not np.isfinite(p).all() or np.linalg.norm(p[0]-p[-1]) > .25:
        return None
    ursprung = p.mean(axis=0)
    breite = np.ptp(p,axis=0).max()
    if breite < 4:
        return None
    x,y = ((p-ursprung)/breite).T
    form = np.column_stack((x*x,2*x*y,y*y,x,y))
    koeff,_,rang,_ = np.linalg.lstsq(form,np.ones(len(p)),rcond=None)
    if rang != 5:
        return None
    a,b,c,d,e = koeff
    matrix = np.array([[a,b],[b,c]])
    werte,basis = np.linalg.eigh(matrix)
    if min(werte) <= 0:
        return None
    zentrum = -.5*(basis @ ((basis.T @ [d,e])/werte))
    radien = breite*np.sqrt((1+zentrum @ matrix @ zentrum)/werte)
    gross,klein = radien
    if klein < 2 or klein/gross < .12 or gross-klein < max(.12,.015*gross):
        return None
    mitte = ursprung+breite*zentrum
    normiert = (p-mitte) @ basis/radien
    if np.max(abs(np.linalg.norm(normiert,axis=1)-1)) > .008:
        return None
    phi = np.unwrap(np.arctan2(normiert[:,1],normiert[:,0]))
    schritte = np.diff(phi)
    if max(abs(schritte)) > .56 or abs(abs(phi[-1]-phi[0])-math.tau) > .12 or sum(abs(schritte)) > math.tau+.12:
        return None
    winkel = math.degrees(math.atan2(*basis[::-1,0])) % 180
    return Blattkreis(*map(float,mitte),float(gross),kurz=float(klein),winkel=winkel)


def ringmitte(k, j):
    if math.dist(k.mitte,j.mitte) >= .15 or abs(k.r-j.r) >= min(4.,.18*k.r):
        return None
    if bool(k.kurz) != bool(j.kurz):
        return None
    winkel = 0.
    if k.kurz:
        d = (j.winkel-k.winkel+90)%180-90
        if abs(k.kurz-j.kurz) >= min(4.,.18*k.kurz) or (k.r-k.kurz)*abs(math.sin(math.radians(d))) > .25:
            return None
        if (k.r-j.r)*(k.kurz-j.kurz) <= 0:
            return None
        winkel = (k.winkel+d/2)%180
    return replace(k,x=(k.x+j.x)/2,y=(k.y+j.y)/2,r=(k.r+j.r)/2,kurz=(k.kurz+j.kurz)/2,winkel=winkel)
