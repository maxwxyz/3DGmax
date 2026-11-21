"""Einen geschlossenen Kegelstumpf aus der Laengsansicht rekonstruieren."""

from dataclasses import dataclass, replace
import re

import numpy as np

from ..i18n import tr
from .axialbohrung import tintenlaeufe
from .drehzeichnung import Sitzkontur, _groessen, _mass, _massstab
from .plattenbohrung import kegelwinkelmass
from .zeichnungskoerper import _gemeinsamer_kreis, schreibe_bemassten_koerper


@dataclass(frozen=True)
class Kegelkontur(Sitzkontur):
    enddurchmesser: float


def _flanke(seite, achse, x, laenge):
    reihe = np.arange(len(seite))[:,None]
    oben = np.argmax(seite,axis=0)
    ende = np.argmax((~seite) & (reihe > oben),axis=0)
    breite = ende-oben
    stift = np.median(breite)
    if min(breite) < 1 or np.max(abs(breite-stift)) > 2:
        return None
    if (seite & (reihe >= ende) & (reihe < achse-stift/2-1)).any():
        return None
    radius = achse-(oben+ende-1)/2
    steigung,anfang = np.polyfit(x,radius,1)
    if np.max(abs(radius-(anfang+steigung*x))) > 1.:
        return None
    return (anfang,anfang+steigung*laenge),stift


def kegelkontur(bild, box, senkrecht=False):
    h,w = bild.shape[:2]
    l,t,r,b = np.rint(np.clip(box,0,1)*[w,h,w,h]).astype(int)
    tinte = bild[t:b,l:r,:3].min(axis=2) < 245
    if senkrecht:
        tinte = tinte.T
    if tinte.size == 0 or not tinte.any() or tinte[0].any() or tinte[-1].any():
        return None
    # Die geschlossenen Stirnkanten sind die beiden hohen, vollstaendig gefuellten Spaltenbaender.
    oben = np.argmax(tinte,axis=0)
    unten = len(tinte)-1-np.argmax(tinte[::-1],axis=0)
    anzahl = tinte.sum(axis=0)
    enden = tintenlaeufe((anzahl == unten-oben+1) & (anzahl >= 8))
    if len(enden) != 2 or enden[0,0] < 1 or enden[1,1] >= tinte.shape[1]:
        return None
    links,rechts = enden.mean(axis=1)-.5
    x = np.arange(enden[0,1],enden[1,0])
    if len(x) < 8:
        return None
    # Obere und untere Flanke separat verfolgen. Innen sind nur Striche auf der Mittelachse erlaubt.
    innen = tinte[:,enden[0,1]:enden[1,0]]
    if (anzahl[x] < 2).any():
        return None
    mitte = (oben[x]+unten[x])/2
    if np.ptp(mitte) > 1.5:
        return None
    achse = np.median(mitte)
    flanken = [_flanke(seite,zentrum,x-links,rechts-links)
               for seite,zentrum in ((innen,achse),(innen[::-1],len(tinte)-1-achse))]
    if any(f is None for f in flanken):
        return None
    radius,stifte = zip(*flanken,strict=True)
    if np.max(np.ptp(radius,axis=0)) > 1.5:
        return None
    a,e = np.mean(radius,axis=0)
    stift = max(stifte)
    if abs(a-e) <= stift+1 or min(a,e) <= 2*stift:
        return None
    # Stirnstriche muessen tatsaechlich bis zu beiden projizierten Flanken reichen.
    for (lo,hi),rad in zip(enden,(a,e),strict=True):
        if hi-lo > stift+2 or abs(oben[lo:hi].min()-(achse-rad)) > stift+1 or abs(unten[lo:hi].max()-(achse+rad)) > stift+1:
            return None
    ausserhalb = np.arange(tinte.shape[1])
    ausserhalb = (ausserhalb < enden[0,0]) | (ausserhalb >= enden[-1,1])
    if tinte[np.abs(np.arange(len(tinte))-achse) > stift/2+1][:,ausserhalb].any():
        return None
    rad = max(a,e)
    rechteck = (achse-rad,links,achse+rad,rechts) if senkrecht else (links,achse-rad,rechts,achse+rad)
    box = tuple((np.asarray(rechteck)+[l,t,l,t])/[w,h,w,h])
    return Kegelkontur(box,rechts-links,2*a,2*e)


def _winkel_passt(text, winkel, soll):
    if winkel is None:
        return False
    oben,unten = winkel.grenzen()
    if oben is not None and unten is not None:
        return unten-1e-7 <= soll <= oben+1e-7
    # Ein Nennwinkel ohne Abmasse kann auf die gedruckten Nachkommastellen gerundet sein.
    zahl = re.fullmatch(r"\s*(\d+)(?:[,.](\d+))?\s*°\s*",text)
    rundung = .5*10**-len(zahl[2] or "") if zahl else 0.
    return abs(soll-winkel.nennwert) <= rundung+1e-7


def kegelmasse(kontur, masse, endtext, winkeltext, faktor):
    laenge,anfang = masse[0]
    ende = _mass(endtext,faktor,"Size_Diameter")
    if ende is None:
        raise ValueError(tr("Den zweiten Stirndurchmesser mit Ø angeben."))
    klein,gross = sorted((anfang,ende),key=lambda p:p.nennwert)
    if min(_groessen(gross)) <= max(_groessen(klein)):
        raise ValueError(tr("Die Grenzmaße müssen den Unterschied der beiden Stirndurchmesser erhalten."))
    _massstab([kontur],masse,[(kontur.enddurchmesser,ende.nennwert)])
    winkel = None
    if winkeltext.strip():
        winkel = kegelwinkelmass(winkeltext)
        soll = np.rad2deg(2*np.arctan((gross.nennwert-klein.nennwert)/(2*laenge.nennwert)))
        if not _winkel_passt(winkeltext,winkel,soll):
            raise ValueError(tr("Der eingeschlossene Kegelwinkel muss zu Länge und beiden Stirndurchmessern passen."))
    return ende,winkel


def schreibe_kegel(ziel, masse, ende, winkel):
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCone
    from OCC.Core.GeomAbs import GeomAbs_Cone, GeomAbs_Plane
    from OCC.Core.gp import gp_Ax2,gp_Dir,gp_Pnt
    laenge,anfang = masse[0]
    achse = gp_Ax2(gp_Pnt(),gp_Dir(1,0,0))
    form = BRepPrimAPI_MakeCone(achse,anfang.nennwert/2,ende.nennwert/2,laenge.nennwert).Shape()

    def ziele(modell):
        ebenen = []
        kegel = set()
        for i,f in enumerate(modell.flaechen):
            s = BRepAdaptor_Surface(f)
            if s.GetType() == GeomAbs_Plane:
                ebenen.append((s.Plane().Location().X(),i))
            elif s.GetType() == GeomAbs_Cone:
                kegel.add(i)
        ebenen.sort()
        merkmale = [(laenge,{i for _,i in ebenen})]
        for (_,i),dm in zip(ebenen,(anfang,ende),strict=True):
            rand = _gemeinsamer_kreis(modell,{i},kegel)
            merkmale.append((replace(dm,massziel_step=rand),kegel))
        if winkel:
            merkmale.append((winkel,kegel))
        return [replace(p,flaechen=f,nummer=n,step_id=-n,quelle="eigen") for n,(p,f) in enumerate(merkmale,1)]
    return schreibe_bemassten_koerper(ziel,form,ziele)
