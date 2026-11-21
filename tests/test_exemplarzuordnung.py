import numpy as np
import pytest

from programm.kern import vergleich_baugruppe as vb


def _teile(punkte):
    return [vb.Teil(i, "Rad", 1., 2., np.asarray(p, dtype=float)) for i,p in enumerate(punkte)]


def _referenz(a, b):
    kanten = sorted((np.linalg.norm(x.mitte-y.mitte), i, j) for i,x in enumerate(a) for j,y in enumerate(b))
    belegt_a, belegt_b, paare = set(), set(), []
    for abstand,i,j in kanten:
        if i not in belegt_a and j not in belegt_b:
            paare.append((abstand, i, j))
            belegt_a.add(i)
            belegt_b.add(j)
    return paare


def test_exemplarzuordnung_wie_sortierte_distanzpaare():
    rng = np.random.default_rng(1023)
    for _ in range(40):
        # Kollisionen, gleiche Abstaende und unterschiedlich grosse Gruppen beiderseits.
        a,b = [_teile(rng.integers(-2, 3, (rng.integers(12,26),3))) for _ in range(2)]
        assert vb._paare(a,b,list(range(len(a))),list(range(len(b)))) == _referenz(a,b)


@pytest.mark.parametrize("verschiebung", [0., np.nextafter(1., 0.), 1., np.nextafter(1., 2.)])
def test_umbenennungen_in_dateireihenfolge_mit_toleranz(monkeypatch, verschiebung):
    from dataclasses import replace
    alt = _teile([(0,0,0), (20,0,0), (40,0,0)])
    neu = _teile([(verschiebung,0,0), (0,0,0), (20,0,0), (60,0,0)])
    neu = [replace(n,name="Ritzel", volumen=5. if i == 2 else n.volumen) for i,n in enumerate(neu)]
    monkeypatch.setattr(vb, "teile", lambda teile, matrix=None: teile)
    ergebnis = vb.vergleiche(alt,neu,toleranz=1.)
    gewinner = 0 if verschiebung <= 1. else 1
    assert [(p.status,p.alt.knoten if p.alt else None,p.neu.knoten if p.neu else None) for p in ergebnis] == [
        (vb.UMBENANNT,0,gewinner), (vb.ENTFERNT,1,None), (vb.ENTFERNT,2,None),
        (vb.NEU,None,1-gewinner), (vb.NEU,None,2), (vb.NEU,None,3)]


def test_gleichstand_bei_gleicher_lage_und_geaenderter_geometrie(monkeypatch):
    from dataclasses import replace
    alt = _teile([(2,0,0), (2,0,0), (1,0,0), (4,0,0)])
    neu = _teile([(3,0,0), (2,0,0), (2,0,0), (0,0,0)])
    neu[2] = replace(neu[2], volumen=2.)
    monkeypatch.setattr(vb, "teile", lambda teile, matrix=None: teile)
    ergebnis = vb.vergleiche(alt,neu)
    assert [(p.status,p.alt.knoten,p.neu.knoten) for p in ergebnis] == [
        (vb.GEAENDERT,1,2), (vb.VERSCHOBEN,2,3), (vb.VERSCHOBEN,3,0)]


def test_halbe_rasterteilung_und_knapp_unterschiedliche_abstaende():
    a = _teile([(float(i),0.,0.) for i in range(60)])
    x = np.arange(60.)+.5
    for richtung in (np.inf,-np.inf):
        x[7::8] = np.nextafter(x[7::8],richtung)
        b = _teile([(v,0.,0.) for v in x[::-1]])
        assert vb._paare(a,b,list(range(len(a))),list(range(len(b)))) == _referenz(a,b)
