"""Freistehende grafische Hinweise unter zweizeiligen STEP-Toleranzrahmen."""

import numpy as np

from . import pmi_strichschrift as schrift
from .ansichten import KAMERA_TYPEN, _items, darstellungskontext
from .merkmalstext import texte_am_aspekt
from .p21 import DMIA_PH, Ref
from .pmi_ableiten import KOPLANARHINWEIS
from .pmi_rahmenzusatz import lies_hinweiszeile
from .pmi_validierungstext import _validierungswerte
from .pmi_verbundschrift import _verbundzellen, rahmenanker


def _ansichten(datei, nr):
    rueck = datei.referrers()
    ebenen = {i for i in rueck.get(nr, ()) if datei.get(i).is_a("ANNOTATION_PLANE")
              and Ref(nr) in _ebenenitems(datei.get(i))}
    quellen = {nr, *ebenen}
    eltern = {i for r in quellen for i in rueck.get(r, ())}
    return {i for i in eltern if datei.get(i).is_a("DRAUGHTING_MODEL")
            and any(r.id in quellen for r in _items(datei, datei.get(i)) if isinstance(r, Ref))
            and any((e := datei.get(r)) and any(e.is_a(t) for t in KAMERA_TYPEN)
                    for r in _items(datei, datei.get(i)) if isinstance(r, Ref))}


def _ebenenitems(e):
    a = e.args("ANNOTATION_PLANE")
    return a[-1] if a and isinstance(a[-1], list) else ()


def _mitglieder(datei, ansichten):
    for i in ansichten:
        for r in _items(datei, datei.get(i)):
            e = datei.get(r) if isinstance(r, Ref) else None
            if e and e.is_a("DRAUGHTING_CALLOUT"):
                yield e.id
            elif e and e.is_a("ANNOTATION_PLANE"):
                for s in _ebenenitems(e):
                    if isinstance(s, Ref):
                        yield s.id


def _aspekte(datei, nr):
    ziel = set()
    for i in datei.referrers().get(nr, ()):
        e = datei.get(i)
        a = e.parts.get("DRAUGHTING_MODEL_ITEM_ASSOCIATION", e.parts.get(DMIA_PH, ()))
        if len(a) < 5 or a[4] != Ref(nr) or not isinstance(a[2], Ref):
            continue
        ent = datei.get(a[2])
        if ent and any(t.endswith("SHAPE_ASPECT") or t in ("DATUM_FEATURE", "DATUM_TARGET") for t in ent.parts):
            ziel.add(ent.id)
    return ziel


def _in_ebene(g, ebene):
    teile = [*g.linien, *(p for p, _ in g.dreiecke)]
    return bool(teile) and all(np.all(np.abs((p-ebene[0]) @ ebene[3]) < .001) for p in teile)


def _pfade(g, ebene):
    if g.erzeugt or g.platzhalter or not schrift._lesbar(g):
        return []
    if g.ebene is not None and not np.allclose(g.ebene[1:3], ebene[1:3], atol=1e-5):
        return []
    return schrift._pfade(g, ebene) if _in_ebene(g, ebene) else []


def _anker(pfade):
    dx, dy = np.ptp(np.vstack([p for p, _ in pfade]), axis=0)
    if min(dx, dy) <= 0:
        return None
    k = min(500/dy, 1800/dx)
    m, box = schrift._gesamtbild(pfade, k)
    if m is None:
        return None
    zellen = _verbundzellen(schrift._rechteckfaecher(m, .32), m, nur_anordnung=True)
    if zellen:
        return rahmenanker(zellen, box, k)
    return None


def _passt(anker, box):
    x, y, h = anker
    l, b, _, t = box
    return abs(l-x) < .35*h and .10*h < y-t < .85*h and .4*h < t-b < 2.4*h


def _zeilen(pfade, box):
    bild, _ = schrift._gesamtbild(pfade, 136/(box[3]-box[1]))
    if bild is None:
        return ()
    bereiche = schrift._gruppen(bild.T)
    if not 1 <= len(bereiche) <= 3:
        return ()
    texte = []
    for oben, unten in bereiche:
        zeile = bild[oben:unten]
        if not 1 <= len(schrift._gruppen(zeile)) <= 40:
            return ()
        text = lies_hinweiszeile(zeile, anzahl=not texte)
        if not text:
            return ()
        texte.append(text)
    wortlaut = " ".join(texte)
    return tuple(texte) if KOPLANARHINWEIS.fullmatch(wortlaut) else ()


def freier_hinweis(datei, rahmen, grafiken, lage):
    """Eindeutige Zuordnung nach Ansicht, Schreibebene und Lage unter dem ersten Wertfach."""
    if datei is None or lage is None:
        return None
    ansichten = _ansichten(datei, rahmen.callout_id)
    kontexte = {darstellungskontext(datei.get(i)) for i in ansichten}
    if len(kontexte) != 1 or None in kontexte:
        return None
    kontext = kontexte.pop()
    if rahmen.kontext not in (kontext, None):
        return None
    andere = (set(_mitglieder(datei, ansichten)) & grafiken.keys()) - {rahmen.callout_id}
    if not andere:
        return None
    ebene, anker = lage
    if not _in_ebene(rahmen, ebene):
        return None
    nachbarn, kandidaten = {}, []
    ziel = _aspekte(datei, rahmen.callout_id)
    for nr in andere:
        g = grafiken[nr]
        if g.kontext not in (kontext, None):
            continue
        pfade = _pfade(g, ebene)
        if not pfade:
            continue
        punkte = np.vstack([p for p, _ in pfade])
        box = (*punkte.min(axis=0), *punkte.max(axis=0))
        nachbarn[nr] = pfade, box
        if _passt(anker, box):
            kandidaten.append((nr, box))
    if len(kandidaten) != 1:
        return None
    nr, box = kandidaten[0]
    if _ansichten(datei, nr) != ansichten:
        return None
    notenziel = _aspekte(datei, nr)
    if ziel and notenziel and ziel != notenziel:
        return None
    pfade, _ = nachbarn.pop(nr)
    zeilen = _zeilen(pfade, box)
    if not zeilen:
        return None
    for pfade, (_, _, _, oben) in nachbarn.values():
        if oben > box[3] and (a := _anker(pfade)) and _passt(a, box):
            return None
    wortlaut = " ".join(zeilen)
    for wert in _validierungswerte(datei, nr):
        teile = wert.split(r"\n")
        if teile[0] != "TXT" or " ".join(" ".join(teile[1:]).split()) != wortlaut:
            return None
    for aspekt in notenziel:
        for quelle in texte_am_aspekt(datei, aspekt):
            if nr in quelle.grafiken and quelle.vergleich(zeilen) != "gleich":
                return None
    return nr, wortlaut
