"""Vergleich zweier Staende: Ausrichten, Geometrie, PMI, Aenderungsliste (nummeriert, mit Pruefstatus)."""

from __future__ import annotations

from ..i18n import tr

from dataclasses import dataclass, field

from . import ausrichten, vergleich_geo, vergleich_pmi
from .vergleich_geo import ENTFERNT, GEAENDERT, GLEICH, NEU

GEOMETRIE, PMI, BAUGRUPPE = "geometrie", "pmi", "baugruppe"
PRUEF_STATUS = ("offen", "geprueft", "abgelehnt")


@dataclass
class Aenderung:
    nummer: int
    kategorie: str  # geometrie | pmi
    status: str  # neu, entfernt/entfallen, geaendert, geometrie
    titel: str
    beschreibung: str = ""
    flaechen_neu: set[int] = field(default_factory=set)  # Flaechenindizes im neuen Stand
    flaechen_alt: set[int] = field(default_factory=set)  # im alten Stand
    pmi_alt: object = None
    pmi_neu: object = None
    pruefstatus: str = "offen"
    kommentar: str = ""
    spalten: tuple = ()  # (Merkmal, alt, neu, Delta, Tendenz) fuer die Aenderungstabelle; leer: aus den PMI


SPALTEN = ("Merkmal", "Alt", "Neu", "Δ", "Tendenz")


def _breite(p) -> float | None:
    """Toleranzbreite einer PMI: Mass Hoechst- minus Mindestmass, Form/Lage der Toleranzwert."""
    if p is None:
        return None
    if p.art == "mass":
        h, m = p.grenzen()
        return None if h is None or m is None else h - m
    return float(p.wert) if p.art == "toleranz" and p.wert is not None else None


def _zahl_aus(text: str) -> float | None:
    try:
        return float(str(text).replace(",", ".").replace("±", "").split()[0])
    except (ValueError, IndexError):
        return None


def pmi_spalten(alt, neu, felder) -> tuple:
    """Spalten einer PMI-Aenderung: geaenderte Felder alt/neu, Delta bei einem Zahlenfeld, Tendenz der Toleranz."""
    from .vergleich_pmi import FELD_TEXT
    if alt is None or neu is None:
        return ("", "–" if alt is None else alt.wert_text(), "–" if neu is None else neu.wert_text(), "", "")
    felder = [f for f in felder if f[0] != "geometrie"]
    if not felder:
        return ("", "", "", "", "")
    merkmal = ", ".join(tr(FELD_TEXT.get(f, f)) for f, _, _ in felder)
    a, n = " · ".join(str(x) for _, x, _ in felder), " · ".join(str(x) for _, _, x in felder)
    delta = ""
    if len(felder) == 1:
        za, zn = _zahl_aus(felder[0][1]), _zahl_aus(felder[0][2])
        if za is not None and zn is not None:
            delta = f"{zn - za:+.4g}"
    ba, bn = _breite(alt), _breite(neu)
    tendenz = ""
    if ba is not None and bn is not None and abs(ba - bn) > 1e-9:
        tendenz = tr("enger") if bn < ba else tr("weiter")
    return (merkmal, a, n, delta, tendenz)


def spalten(a: Aenderung) -> tuple:
    return a.spalten or pmi_spalten(a.pmi_alt, a.pmi_neu, [])


@dataclass
class Vergleich:
    alt: object  # lader.Ergebnis
    neu: object
    ausrichtung: ausrichten.Ausrichtung
    geo: vergleich_geo.GeoErgebnis
    pmi: list
    aenderungen: list[Aenderung]
    toleranz: float
    suchweite: float

    def zaehler(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for a in self.aenderungen:
            out[a.pruefstatus] = out.get(a.pruefstatus, 0) + 1
        return out


def _gruppen(flaechen: set[int], nachbarn: dict[int, set[int]]) -> list[set[int]]:
    """Zusammenhaengende Bereiche (Flaechen mit gemeinsamer Kante)."""
    rest, out = set(flaechen), []
    while rest:
        start = rest.pop()
        gruppe, stapel = {start}, [start]
        while stapel:
            for n in nachbarn.get(stapel.pop(), ()):
                if n in rest:
                    rest.discard(n)
                    gruppe.add(n)
                    stapel.append(n)
        out.append(gruppe)
    return sorted(out, key=lambda g: min(g))


VERSCHOBEN = "verschoben"
GEDREHT, GESPIEGELT = "gedreht", "gespiegelt"  # Titel; der Status bleibt VERSCHOBEN (gleiche Form, andere Lage)
GEO_TITEL = {GEAENDERT: "Geometrie geändert", NEU: "Geometrie neu", ENTFERNT: "Geometrie entfernt",
             VERSCHOBEN: "Geometrie verschoben", GEDREHT: "Geometrie gedreht", GESPIEGELT: "Geometrie gespiegelt"}
GRAFIK = "grafik"
PMI_TITEL = {"geaendert": "PMI geändert", "neu": "PMI neu", "entfallen": "PMI entfallen",
             "geometrie": "Geometrie unter PMI geändert", "verschoben": "PMI verschoben",
             GRAFIK: "PMI-Darstellung geändert"}


def _geo_aenderungen(geo, nachbarn_neu, nachbarn_alt) -> list[Aenderung]:
    out = []
    for status in (GEAENDERT, NEU):
        menge = {f for f, s in geo.status_b.items() if s == status}
        for g in _gruppen(menge, nachbarn_neu):
            alt = {geo.zuordnung[f] for f in g if f in geo.zuordnung}
            abw = max(geo.max_abw_b.get(f, 0.0) for f in g)
            werte = (tr("größte Abweichung"), "", "", f"{abw:.3f} mm", "") if status == GEAENDERT else \
                (tr("Flächen"), "–", str(len(g)), "", "")
            out.append(Aenderung(0, GEOMETRIE, status, tr(GEO_TITEL[status]),
                                 tr("{} Fläche(n), größte Abweichung {:.3f} mm").format(len(g), abw), g, alt,
                                 spalten=werte))
    weg = {f for f, s in geo.status_a.items() if s == ENTFERNT}
    for g in _gruppen(weg, nachbarn_alt):
        out.append(Aenderung(0, GEOMETRIE, ENTFERNT, tr(GEO_TITEL[ENTFERNT]), tr("{} Fläche(n)").format(len(g)),
                             set(), g, spalten=(tr("Flächen"), str(len(g)), "–", "", "")))
    return out


def _kennwerte(flaechen) -> list[tuple]:
    """(Flaechentyp, Inhalt, Schwerpunkt) je Flaeche, sortiert nach Typ und Inhalt."""
    import numpy as np
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    out = []
    for f in flaechen:
        g = GProp_GProps()
        brepgprop.SurfaceProperties(f, g)
        c = g.CentreOfMass()
        typ = BRepAdaptor_Surface(f, True).GetType() if BRep_Tool.Surface(f) is not None else -1
        out.append((int(typ), abs(g.Mass()), np.array([c.X(), c.Y(), c.Z()])))
    return sorted(out, key=lambda k: (k[0], k[1]))


def _verschiebungen(aenderungen, alt, neu, ausrichtung, toleranz: float) -> list[Aenderung]:
    """Paare aus 'neu' und 'entfernt' mit gleicher Form in anderer Lage -> 'verschoben' (auch gedreht/gespiegelt).

    Zuerst reiner Versatz (alle Schwerpunkte gleich verschoben), sonst starre Lage ueber die Netzpunkte
    (Drehung oder Spiegelung), bestaetigt durch den Abstand der abgebildeten Flaechen zu den alten in beide
    Richtungen.
    """
    import numpy as np
    neue = [a for a in aenderungen if a.kategorie == GEOMETRIE and a.status == NEU]
    weg = [a for a in aenderungen if a.kategorie == GEOMETRIE and a.status == ENTFERNT]
    if not neue or not weg:
        return aenderungen
    m = ausrichtung.matrix
    kenn_weg = {id(a): _kennwerte([alt.modell.flaechen[i] for i in sorted(a.flaechen_alt)]) for a in weg}
    genutzt, ersetzt, dazu = set(), set(), []
    for a in neue:
        kn = _kennwerte([neu.modell.flaechen[i] for i in sorted(a.flaechen_neu)])
        kn = [(t, f, c @ m[:3, :3].T + m[:3, 3]) for t, f, c in kn]  # ins System des alten Stands
        for b in weg:
            kw = kenn_weg[id(b)]
            if id(b) in genutzt or len(kw) != len(kn):
                continue
            if any(t1 != t2 or abs(f1 - f2) > 1e-3 * max(f1, 1.0) for (t1, f1, _), (t2, f2, _) in zip(kn, kw)):
                continue
            versatz = [c1 - c2 for (_, _, c1), (_, _, c2) in zip(kn, kw)]
            d = np.mean(versatz, axis=0)
            if np.linalg.norm(d) > toleranz and max(np.linalg.norm(v - d) for v in versatz) <= max(10 * toleranz, 1e-3):
                titel = tr(GEO_TITEL[VERSCHOBEN])
                text = tr("{} Fläche(n) um dX {:+.3f}  dY {:+.3f}  dZ {:+.3f} mm ({:.3f} mm)").format(
                    len(a.flaechen_neu), d[0], d[1], d[2], float(np.linalg.norm(d)))
            else:
                lage = _starr_gleich([neu.modell.flaechen[i] for i in sorted(a.flaechen_neu)],
                                     [alt.modell.flaechen[i] for i in sorted(b.flaechen_alt)], m, toleranz)
                if lage is None:
                    continue
                art, beschreibung = beschreibe_lage(*lage)
                titel = tr(GEO_TITEL[art])
                text = tr("{} Fläche(n) {}; Schwerpunkt dX {:+.3f}  dY {:+.3f}  dZ {:+.3f} mm").format(
                    len(a.flaechen_neu), beschreibung, d[0], d[1], d[2])
            genutzt.add(id(b))
            ersetzt |= {id(a), id(b)}
            dazu.append(Aenderung(0, GEOMETRIE, VERSCHOBEN, titel, text, set(a.flaechen_neu), set(b.flaechen_alt),
                                  spalten=(tr("Lage"), "", "", f"{float(np.linalg.norm(d)):.3f} mm", "")))
            break
    return [a for a in aenderungen if id(a) not in ersetzt] + dazu


def _starr_gleich(flaechen_neu, flaechen_alt, m, toleranz: float):
    """(R, t) alt -> neu, wenn die neuen Flaechen (im alten System) durch Drehung/Spiegelung auf den alten liegen."""
    import numpy as np
    from .ausrichten import NetzAbstand, abtasten
    netz_neu = _gruppen_netz(flaechen_neu, m)
    netz_alt = _gruppen_netz(flaechen_alt)
    p_neu, _ = abtasten(netz_neu, 600)
    p_alt, _ = abtasten(netz_alt, 600, zufall=2)
    if len(p_neu) < 3 or len(p_alt) < 3:
        return None
    grenze = max(5 * toleranz, 3 * _feinheit(flaechen_alt))
    ziel_alt = NetzAbstand(netz_alt)
    for r, t, _ in starre_lagen(p_neu, p_alt):
        r, t = _nachfuehren(p_neu, ziel_alt, r, t)
        if np.allclose(r, np.eye(3), atol=1e-6):
            continue  # reiner Versatz wurde vorher geprueft
        abgebildet = [(p @ r.T + t if len(p) else p, dr) for p, dr in netz_neu]
        d1, _, _ = ziel_alt.abfrage(p_neu @ r.T + t)
        if float(np.max(d1)) > grenze:
            continue
        d2, _, _ = NetzAbstand(abgebildet).abfrage(p_alt)
        if float(np.max(d2)) <= grenze:
            return r.T, -(t @ r)  # Lage alt -> neu
    return None


def _nachfuehren(punkte, ziel, r, t, schritte: int = 60):
    """ICP Punkt zu Flaeche: naechste Punkte auf dem Zielnetz, Kabsch mit gleicher Haendigkeit wie r."""
    import numpy as np
    spiegel = np.linalg.det(r) < 0
    for _ in range(schritte):
        _, q, _ = ziel.abfrage(punkte @ r.T + t)
        ma, mq = punkte.mean(axis=0), q.mean(axis=0)
        u, _, vt = np.linalg.svd((punkte - ma).T @ (q - mq))
        s = np.linalg.det(vt.T @ u.T)
        r = vt.T @ np.diag([1.0, 1.0, -s if spiegel else s]) @ u.T
        t = mq - ma @ r.T
    return r, t


def _gruppen_netz(flaechen, m=None):
    """Netz einer Flaechengruppe, wahlweise mit 4x4-Matrix abgebildet."""
    from .ausrichten import tesselliere
    netze = tesselliere(flaechen, _feinheit(flaechen))
    if m is not None:
        netze = [(p @ m[:3, :3].T + m[:3, 3] if len(p) else p, t) for p, t in netze]
    return netze


def _feinheit(flaechen) -> float:
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    import numpy as np
    box = Bnd_Box()
    for f in flaechen:
        brepbndlib.Add(f, box)
    x0, y0, z0, x1, y1, z1 = box.Get()
    return min(max(float(np.linalg.norm([x1 - x0, y1 - y0, z1 - z0])) * 2e-3, 0.005), 0.2)


def starre_lagen(punkte_neu, punkte_alt, iterationen: int = 25) -> list[tuple]:
    """Kandidaten fuer die starre Abbildung (Drehung oder Spiegelung + Versatz) von 'punkte_neu' auf 'punkte_alt'.

    Ohne Punktzuordnung: Schwerpunkte und Hauptachsen (PCA) vorausrichten, alle acht Vorzeichenkombinationen der
    Achsen (vier Drehungen, vier Spiegelungen) mit naechsten Nachbarn nachfuehren (ICP mit Kabsch, Haendigkeit
    bleibt). Ergebnis: [(R, t, groesster Restabstand)] aufsteigend nach Rest, alt ~ neu @ R.T + t; det(R) < 0:
    gespiegelt. Symmetrische Formen liefern mehrere gute Kandidaten; der Aufrufer prueft gegen die Flaechen.
    """
    import itertools

    import numpy as np
    from scipy.spatial import cKDTree
    a, b = np.asarray(punkte_neu, float), np.asarray(punkte_alt, float)
    if len(a) < 3 or len(b) < 3:
        return []
    ca, cb = a.mean(axis=0), b.mean(axis=0)
    _, _, va = np.linalg.svd(a - ca, full_matrices=False)
    _, _, vb = np.linalg.svd(b - cb, full_matrices=False)
    baum = cKDTree(b)
    out = []
    for vz in itertools.product((1.0, -1.0), repeat=3):
        r = vb.T @ np.diag(vz) @ va
        t = cb - ca @ r.T
        spiegel = np.linalg.det(r) < 0
        for _ in range(iterationen):
            _, j = baum.query(a @ r.T + t)
            q = b[j]
            ma, mq = a.mean(axis=0), q.mean(axis=0)
            u, _, vt = np.linalg.svd((a - ma).T @ (q - mq))
            s = np.linalg.det(vt.T @ u.T)
            r = vt.T @ np.diag([1.0, 1.0, -s if spiegel else s]) @ u.T
            t = mq - ma @ r.T
        d, _ = baum.query(a @ r.T + t)
        out.append((r, t, float(d.max())))
    return sorted(out, key=lambda k: k[2])


def beschreibe_lage(r, t) -> tuple[str, str]:
    """(Art, Text) einer starren Abbildung: 'gedreht' (Winkel, Achse) oder 'gespiegelt' (Ebenennormale)."""
    import numpy as np
    if np.linalg.det(r) < 0:
        w, v = np.linalg.eig(r)
        k = int(np.argmin(np.abs(w + 1)))
        n = np.real(v[:, k])
        n = n / np.linalg.norm(n)
        if n[np.argmax(np.abs(n))] < 0:
            n = -n
        abstand = float(t @ n) / 2
        return "gespiegelt", tr("gespiegelt an Ebene mit Normale ({:+.3f}, {:+.3f}, {:+.3f}) bei {:.3f} mm").format(
            n[0], n[1], n[2], abstand)
    winkel = float(np.degrees(np.arccos(np.clip((np.trace(r) - 1) / 2, -1.0, 1.0))))
    achse = np.array([r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1]])
    achse = achse / (np.linalg.norm(achse) or 1.0)
    if achse[np.argmax(np.abs(achse))] < 0:
        achse, winkel = -achse, -winkel
    return "gedreht", tr("gedreht um {:+.2f}° um Achse ({:+.3f}, {:+.3f}, {:+.3f})").format(
        winkel, achse[0], achse[1], achse[2])


BG_TITEL = {"neu": "Teil neu", "entfernt": "Teil entfernt", "verschoben": "Teil verschoben",
            "geaendert": "Teil geändert", "umbenannt": "Teil umbenannt"}


def _flaechen_von(modell, knoten) -> set[int]:
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    out, ex = set(), TopExp_Explorer(knoten.form, TopAbs_FACE)
    while ex.More():
        i = modell.flaechen_index(ex.Current())
        if i is not None:
            out.add(i)
        ex.Next()
    return out


def _baugruppen_aenderungen(alt, neu, ausrichtung, toleranz) -> list[Aenderung]:
    """Teile neu/entfernt/verschoben/geaendert/umbenannt, wenn einer der Staende mehrere Teile hat."""
    import numpy as np
    from . import vergleich_baugruppe as vb
    anzahl = lambda e: sum(1 for k in e.baum.blaetter() if not k.hilfsgeometrie)  # noqa: E731
    if getattr(alt, "baum", None) is None or getattr(neu, "baum", None) is None or max(anzahl(alt), anzahl(neu)) < 2:
        return []
    out = []
    for x in vb.vergleiche(alt.baum, neu.baum, ausrichtung.matrix, toleranz):
        teile = []
        if x.versatz is not None and x.status in (vb.VERSCHOBEN, vb.GEAENDERT):
            d = x.versatz
            teile.append(tr("Lage dX {:+.3f}  dY {:+.3f}  dZ {:+.3f} mm").format(*d))
        if x.status == vb.GEAENDERT:
            teile.append(tr("Volumen {:.1f} → {:.1f} mm³").format(x.alt.volumen, x.neu.volumen))
        if x.status == vb.GEAENDERT:
            werte = (tr("Volumen"), f"{x.alt.volumen:.1f}", f"{x.neu.volumen:.1f}",
                     f"{x.neu.volumen - x.alt.volumen:+.1f} mm³", "")
        elif x.versatz is not None and x.status == vb.VERSCHOBEN:
            werte = (tr("Lage"), "", "", f"{float(np.linalg.norm(x.versatz)):.3f} mm", "")
        else:
            werte = (tr("Teil"), x.alt.name if x.alt else "–", x.neu.name if x.neu else "–", "", "")
        out.append(Aenderung(0, BAUGRUPPE, x.status, f"{tr(BG_TITEL[x.status])}: {x.name}", " · ".join(teile),
                             _flaechen_von(neu.modell, x.neu.knoten) if x.neu else set(),
                             _flaechen_von(alt.modell, x.alt.knoten) if x.alt else set(), spalten=werte))
    return out


def _grafik_punkte(grafik: dict, step_id: int):
    import numpy as np
    pts = [np.asarray(l, float) for g in grafik.values() if step_id in g.pmi_ids and not g.erzeugt for l in g.linien]
    pts += [np.asarray(p, float) for g in grafik.values() if step_id in g.pmi_ids and not g.erzeugt
            for p, _ in g.dreiecke]
    return np.vstack(pts) if pts else None


def _grafik_aenderungen(liste, alt, neu, ausrichtung, toleranz) -> list[Aenderung]:
    """Semantisch gleiche PMI, deren Darstellung verschoben oder in der Form geaendert ist."""
    import numpy as np
    ga, gn = getattr(alt, "grafik", None) or {}, getattr(neu, "grafik", None) or {}
    if not ga or not gn:
        return []
    m = ausrichtung.matrix
    out = []
    for x in liste:
        if x.status != vergleich_pmi.GLEICH or x.alt is None or x.neu is None:
            continue
        pa, pn = _grafik_punkte(ga, x.alt.step_id), _grafik_punkte(gn, x.neu.step_id)
        if pa is None or pn is None:
            continue
        pn = pn @ m[:3, :3].T + m[:3, 3]
        versatz = pn.mean(axis=0) - pa.mean(axis=0)
        groesse_a, groesse_n = np.ptp(pa, axis=0), np.ptp(pn, axis=0)
        grenze = max(10 * toleranz, 0.05)
        if np.linalg.norm(groesse_n - groesse_a) > grenze or len(pa) != len(pn):
            text = tr("Darstellung geändert (Größe {:.1f} → {:.1f} mm)").format(float(np.linalg.norm(groesse_a)),
                                                                             float(np.linalg.norm(groesse_n)))
        elif np.linalg.norm(versatz) > grenze:
            text = tr("Beschriftung verschoben um dX {:+.2f}  dY {:+.2f}  dZ {:+.2f} mm").format(*versatz)
        else:
            continue
        out.append(Aenderung(0, PMI, GRAFIK, f"{tr(PMI_TITEL[GRAFIK])}: {x.neu.wert_text()}", text,
                             set(x.neu.flaechen), set(x.alt.flaechen), x.alt, x.neu,
                             spalten=(tr("Darstellung"), "", "", f"{float(np.linalg.norm(versatz)):.2f} mm", "")))
    return out


def _pmi_aenderungen(liste) -> list[Aenderung]:
    out = []
    for x in liste:
        if x.status == vergleich_pmi.GLEICH:
            continue
        p = x.neu or x.alt
        art = {"mass": "Maß", "toleranz": "Toleranz", "bezug": "Bezug", "hinweis": "Hinweis"}.get(p.art, p.art)
        out.append(Aenderung(0, PMI, x.status, f"{tr(PMI_TITEL[x.status])}: {tr(art)} {p.wert_text()}", x.text(),
                             set(x.neu.flaechen) if x.neu else set(), set(x.alt.flaechen) if x.alt else set(),
                             x.alt, x.neu, spalten=pmi_spalten(x.alt, x.neu, x.felder)))
    return out


def vergleiche(alt, neu, toleranz: float = 0.01, suchweite: float = 2.0, ausrichtung=None,
               fortschritt=lambda text: None) -> Vergleich:
    """alt, neu: Ergebnisse von ui.lader.lade_alles (Modell, PMI, ...)."""
    if ausrichtung is None:
        fortschritt(tr("Ausrichten …"))
        ausrichtung = ausrichten.richte_aus(alt.modell.flaechen, neu.modell.flaechen, toleranz)
    fortschritt(tr("Geometrie vergleichen …"))
    geo = vergleich_geo.vergleiche(alt.modell, neu.modell, ausrichtung, toleranz, suchweite=suchweite)
    fortschritt(tr("PMI vergleichen …"))
    pmi = vergleich_pmi.vergleiche_pmi(alt.pmi, neu.pmi, geo.zuordnung, zuordnung_ab=geo.zuordnung_ab,
                                       geo_status=geo.status_b)
    nachbarn_neu = vergleich_geo._nachbarn(neu.modell.flaechen, neu.modell.flaechen_index)
    nachbarn_alt = vergleich_geo._nachbarn(alt.modell.flaechen, alt.modell.flaechen_index)
    geo_liste = _verschiebungen(_geo_aenderungen(geo, nachbarn_neu, nachbarn_alt), alt, neu, ausrichtung, toleranz)
    pmi_liste = _pmi_aenderungen(pmi)
    # PMI, deren Flaechen nur verschoben wurden: "PMI verschoben" statt "Geometrie unter PMI geaendert"
    for a in pmi_liste:
        for g in geo_liste:
            if a.status == "geometrie" and g.status == VERSCHOBEN and a.flaechen_neu and a.flaechen_neu <= g.flaechen_neu:
                a.status = VERSCHOBEN
                a.titel = f"{tr('PMI verschoben')}: {a.titel.split(': ', 1)[-1]}"
                a.beschreibung = g.beschreibung
                break
    pmi_liste += _grafik_aenderungen(pmi, alt, neu, ausrichtung, toleranz)
    aenderungen = _baugruppen_aenderungen(alt, neu, ausrichtung, toleranz) + pmi_liste + geo_liste
    for i, a in enumerate(aenderungen, 1):
        a.nummer = i
    return Vergleich(alt, neu, ausrichtung, geo, pmi, aenderungen, toleranz, suchweite)


def ist_gleich(v: Vergleich) -> bool:
    return not v.aenderungen and all(s == GLEICH for s in v.geo.status_b.values())
