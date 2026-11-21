"""Kugelruecken und ballige Bolzenbohrungen eines Kegelrads aus achsnormalen Schnitten."""

import numpy as np


def _ring(q):
    """Radius und Streuung einer Kontur, die die Radachse vollstaendig umschliesst."""
    winkel = np.sort(np.arctan2(q[:, 1], q[:, 0]))
    if np.diff(winkel, append=winkel[0] + 2 * np.pi).max() > .15:
        return None
    rho = np.hypot(*q.T)
    return float(np.median(rho)), float(np.ptp(rho))


def _kugelbogen(orte, radien, tol):
    """r² + x² ist auf einer achszentrierten Kugel linear in x."""
    u, rho = np.asarray(orte) - orte[0], np.asarray(radien)
    m, b = np.polyfit(u, rho**2 + u**2, 1)
    soll = b + m * u - u**2
    if np.any(soll <= 0) or np.any(np.diff(rho) >= 0):
        return None
    fehler = np.max(abs(np.sqrt(soll) - rho))
    gerade = np.polyval(np.polyfit(u, rho, 1), u)
    # Auch kurze Kugelabschnitte sind messbar, wenn die Kruemmung den Anpassfehler klar uebersteigt.
    if fehler > tol or np.max(abs(rho - gerade)) <= max(4 * fehler, .06 * tol):
        return None
    return float(np.sqrt(b + (.5 * m)**2))


def _kugel_facetten(netz, sinn, orte, radien, tol):
    """Gekappte Zahnkoepfe ohne glatten Ring: ein gemeinsamer Kugelmittelpunkt fuer die hinteren Facetten."""
    t = np.stack((netz.a, netz.b, netz.c), axis=1)
    x = sinn * t[:, :, 2]
    rho = np.hypot(t[:, :, 0], t[:, :, 1])
    auswahl = ((x.max(axis=1) >= orte[0] - 10*tol) & (np.ptp(x, axis=1) > 1e-5 * netz.r_max)
               & (rho.mean(axis=1) > .75 * min(radien)))
    t, x, rho = t[auswahl], x[auswahl], rho[auswahl]
    if len(t) < 12:
        return None
    # Zwei axial entfernte Eckpunkte bestimmen den Mittelpunkt auf der Achse.
    nr = np.arange(len(t))
    a, b = np.argmin(x, axis=1), np.argmax(x, axis=1)
    quadrat = rho**2 + x**2
    mitte = (quadrat[nr, b] - quadrat[nr, a]) / (2 * (x[nr, b] - x[nr, a]))
    dist = np.hypot(rho, x - mitte[:, None])
    radius = dist.mean(axis=1)
    genau = max(netz.r_max * 2e-5, tol * .02)
    gut = ((np.ptp(dist, axis=1) < genau) & (mitte < orte[0])
           & (abs(np.hypot(radien[0], orte[0] - mitte) - radius) < tol))
    if np.count_nonzero(gut) < 12:
        return None
    # Ein Kegelstumpf kann in einer einzelnen Facettenreihe ebenfalls auf einer Kugel liegen.
    # Mehrere Breitenkreise muessen zusammen eine gekruemmte Aussenflaeche rund um die Achse belegen.
    _, gruppe, zahl = np.unique(np.rint(mitte[gut] / (4 * genau)), return_inverse=True, return_counts=True)
    for k in np.argsort(zahl)[::-1][:4]:
        if zahl[k] < 6:
            break
        c = np.median(mitte[gut][gruppe == k])
        rad = np.median(radius[gut][gruppe == k])
        if np.max(abs(np.hypot(radien, orte - c) - rad)) > tol:
            continue
        auf = np.max(abs(np.hypot(rho, x-c) - rad), axis=1) < genau
        u, v = x[auf].ravel(), rho[auf].ravel()
        if len(u) < 36 or np.ptp(u) < .01 * rad:
            continue
        winkel = np.sort(np.arctan2(t[auf, :, 1], t[auf, :, 0]).ravel())
        if np.diff(winkel, append=winkel[0] + 2*np.pi).max() > np.pi/3:
            continue
        kugelfehler = np.max(abs(np.hypot(v, u-c) - rad))
        if np.max(abs(np.polyval(np.polyfit(u, v, 1), u) - v)) > max(4 * kugelfehler, .3 * genau):
            return float(rad)
    return None


def kalotte(netz, s, r):
    """Bereich mit ganzen Zaehnen und Radius der ausseren Kalotte, auch hinter einem intakten Zahnband."""
    sinn = 1 if r[-1, 1] > r[0, 1] else -1
    x, radien = sinn * s[::sinn], r[::sinn]
    m, start = np.polyfit(x[:5] - x[0], radien[:5], 1)
    hoehe = np.mean(radien[:5, 0] - radien[:5, 1])
    tol = .05 * hoehe
    if min(m) <= 0 or min(m) * (x[4] - x[0]) < .25 * hoehe:
        return None, None
    fehler = radien - (start + np.outer(x - x[0], m))
    if np.abs(fehler[:, 1]).max() > tol or np.any(fehler[:, 0] > tol):
        return None, None
    beschnitten = np.flatnonzero(fehler[:, 0] < -tol)
    if len(beschnitten) and (beschnitten[0] < 5 or len(beschnitten) != len(x) - beschnitten[0]):
        return None, None
    ende = max((sinn * p[:, 2]).max() for p in (netz.a, netz.b, netz.c))
    orte, aussen = list(x[beschnitten]), list(radien[beschnitten, 0])
    for pos in np.linspace(x[-1], ende, 16)[1:-1]:
        konturen = netz.konturen(sinn * pos)
        if not konturen:
            break
        q = max(konturen, key=lambda k: np.hypot(*k.T).max())
        ring = _ring(q)
        if ring is None or ring[1] > tol:
            if len(orte) == len(beschnitten):
                continue
            break
        orte.append(pos)
        aussen.append(ring[0])
    ganz = int(beschnitten[0]) if len(beschnitten) else len(x)
    bereich = (slice(0, ganz) if sinn > 0 else slice(-ganz, None)) if len(beschnitten) else None
    for n in range(len(orte), len(beschnitten) + 4, -1):
        radius = _kugelbogen(orte[:n], aussen[:n], tol)
        if radius is not None:
            return bereich, radius
    if len(beschnitten):
        radius = _kugel_facetten(netz, sinn, x[beschnitten], radien[beschnitten, 0], tol)
        if radius is not None:
            return bereich, radius
    return None, None


def kegelband(s, r):
    """Unbeschnittene Zahnkoepfe zwischen Stirnfase und Ruecksitz anhand des durchlaufenden Fusskegels."""
    h = np.median(r[:, 0] - r[:, 1])
    tol = .05 * h
    if h <= 0 or len(s) < 7:
        return None
    x = s - s[0]
    fuss = np.polyfit(x, r[:, 1], 1)
    if np.max(abs(r[:, 1] - np.polyval(fuss, x))) > tol:
        return None
    # Laengstes gemeinsam getragenes Intervall, mindestens die Haelfte der Messbreite.
    for n in range(len(s) - 1, max(4, len(s) // 2 - 1), -1):
        for i in range(len(s) - n + 1):
            bereich = slice(i, i+n)
            xx = x[bereich]
            if np.ptp(xx) < .5 * np.ptp(x):
                continue
            kopf = np.polyfit(xx, r[bereich, 0], 1)
            if kopf[0] * fuss[0] <= 0 or min(abs(kopf[0]), abs(fuss[0])) * np.ptp(xx) < max(.4*h, .02*r.mean()):
                continue
            rest = r[:, 0] - np.polyval(kopf, x)
            if np.max(abs(rest[bereich])) < tol and rest.max() < tol and rest.min() < -2*tol:
                return bereich
    return None


def _bohrprofil(netz, sinn):
    lo = min((sinn * p[:, 2]).min() for p in (netz.a, netz.b, netz.c))
    hi = max((sinn * p[:, 2]).max() for p in (netz.a, netz.b, netz.c))

    def messe(x):
        konturen = netz.konturen(sinn * x)
        if len(konturen) < 2:
            return None
        innen, aussen = sorted(konturen, key=lambda q: np.hypot(*q.T).max())[:2]
        ring = _ring(innen)
        if ring is None or ring[1] > .01 * ring[0] or np.hypot(*aussen.T).min() <= ring[0] + ring[1]:
            return None
        return ring

    axial = np.linspace(lo, hi, 33)[1:-1]
    ringe = []
    for pos in axial:
        ring = messe(pos)
        if ring is None:
            return None
        ringe.append(ring)
    return axial, np.array(ringe).T, messe, hi


def _sitzstufen(x, r, rauschen, messe, ende):
    """Ueber einen sprunghaften Durchmesserwechsel in eine zylindrische hintere Senkung messen."""
    kanten = []
    for i in np.flatnonzero(np.diff(r) > max(8 * rauschen, .003 * np.max(r))):
        if i+2 >= len(r) or abs(r[i+2]-r[i+1]) > 3*rauschen:
            continue
        links, rechts = r[i:i+2]
        # Bei leicht geneigter Netzachse durchschneidet die Ebene kurz beide Waende.
        # Beide Raender getrennt eingrenzen, auch wenn dort kein einzelner Ring messbar ist.
        def grenze(a, b, ref):
            for _ in range(14):
                m = .5 * (a+b)
                ring = messe(m)
                if ring and abs(ring[0]-ref) <= .12*(rechts-links):
                    a = m
                else:
                    b = m
            return a
        a = grenze(x[i], x[i+1], links)
        b = grenze(x[i+1], x[i], rechts)
        if b-a < .015 * (x[i+1]-x[i]):
            kanten.append((i + 1, .5 * (a+b)))
    stufen = []
    for k, (i, start) in enumerate(kanten):
        j, stop = kanten[k+1] if k+1 < len(kanten) else (len(r), ende)
        segment = r[i:j]
        if len(segment) < 2 or np.ptp(segment) > 3 * rauschen:
            continue
        dm = 2 * float(np.median(segment))
        stufen.append({"durchmesser_mm": dm, "laenge_mm": float(stop-start)})
    return stufen, (kanten[0][0] if stufen and kanten else len(r))


def bohrungsmerkmale(netz, sinn):
    daten = _bohrprofil(netz, sinn)
    if daten is None:
        return None, []
    axial, (r, streuung), messe, ende = daten
    rauschen = max(np.median(streuung), .00015 * r.mean())
    stufen, bis = _sitzstufen(axial, r, rauschen, messe, ende)
    profil = _balligkeit(axial[:bis], r[:bis], rauschen)
    return profil, stufen


def bolzenbohrung(netz):
    return bohrungsmerkmale(netz, 1)[0]


def _balligkeit(axial, r, rauschen):
    if len(r) < 9:
        return None
    if np.ptp(r) <= 4 * rauschen:
        return None
    # Kurze Einlauffasen an den Muendungen duerfen ausserhalb des tragenden Bogens liegen.
    for rand in range(9):
        for links in range(max(0, rand - 4), min(4, rand) + 1):
            bereich = slice(links, len(r) - rand + links)
            if len(r[bereich]) < 9:
                continue
            profil = _bohrungsbogen(axial[bereich], r[bereich], rauschen)
            if profil is not None:
                return profil
    return None


def _bohrungsbogen(axial, r, rauschen):
    x, y = axial - axial.mean(), r - r.mean()
    # (x - xc)² + (y - yc)² = R², in zentrierten Koordinaten.
    xc, yc, c = np.linalg.lstsq(np.column_stack([2*x, 2*y, np.ones(len(x))]), x*x + y*y, rcond=None)[0]
    radius = np.sqrt(max(0., c + xc*xc + yc*yc))
    innen_eng = yc > 0
    scheitel = r.mean() + yc + (-radius if innen_eng else radius)
    if radius <= 0 or not x[2] < xc < x[-3] or scheitel <= 0:
        return None
    soll2 = radius**2 - (x - xc)**2
    if np.any(soll2 <= 0):
        return None
    soll = r.mean() + yc + (-1 if innen_eng else 1) * np.sqrt(soll2)
    hub = min(abs(r[0] - scheitel), abs(r[-1] - scheitel))
    fehler = np.max(abs(r - soll))
    if hub <= max(10 * fehler, 4 * rauschen):
        return None
    # Eine Doppelkonus-Bohrung hat beidseits einen geraden Verlauf.
    for seite in (x < xc, x > xc):
        gerade = np.polyval(np.polyfit(x[seite], r[seite], 1), x[seite])
        if np.max(abs(gerade - r[seite])) <= max(2 * fehler, .35 * rauschen):
            return None
    return {"profil": "mittig_eng" if innen_eng else "mittig_weit", "balligkeitsradius": float(radius),
            "scheiteldurchmesser": float(2 * scheitel)}
