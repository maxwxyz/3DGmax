"""Schlanker Leser fuer STEP-Dateien (ISO 10303-21) als Entitaetsgraph.

Dient zum Gegenpruefen und Ergaenzen dessen, was OCCT aus der Datei liest
(z. B. Zuordnung von PMI zu Flaechen ueber ITEM_IDENTIFIED_REPRESENTATION_USAGE).
Kein vollstaendiger Parser: Werte werden in Python-Typen zerlegt, Schema wird nicht geprueft.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cached_property, lru_cache
from threading import Lock


# Verknuepfung Semantik -> Annotation (mit Platzhalter ab AP242 e2)
DMIA_PH = "DRAUGHTING_MODEL_ITEM_ASSOCIATION_WITH_PLACEHOLDER"


@dataclass(slots=True)
class Ref:
    """Verweis auf eine Entitaet (#123)."""
    id: int

    def __repr__(self):
        return f"#{self.id}"


@dataclass(slots=True)
class Enum:
    """Aufzaehlungswert (.T., .PARALLEL.)."""
    name: str


@dataclass(slots=True)
class Typed:
    """Getypter Wert, z. B. LENGTH_MEASURE(12.5)."""
    typ: str
    args: list


@dataclass(slots=True)
class Entity:
    id: int
    # Teiltypen; einfache Entitaet hat genau einen, komplexe mehrere
    parts: dict[str, list] = field(default_factory=dict)

    def typen(self):
        return self.parts.keys()

    def sammle_verweise(self, rueck):
        for args in self.parts.values():
            _sammle_verweise(args, self.id, rueck)

    @property
    def typ(self) -> str:
        return next(iter(self.parts)) if len(self.parts) == 1 else "(" + " ".join(self.parts) + ")"

    def is_a(self, name: str) -> bool:
        return name in self.parts

    def args(self, name: str | None = None) -> list:
        if name is None:
            return next(iter(self.parts.values()))
        return self.parts[name]


# Diese einfachen Geometrieentitaeten wurden beim Modellimport bereits von OCCT gelesen.
_GEOMETRIE = frozenset("""
    CARTESIAN_POINT DIRECTION VECTOR LINE CIRCLE ELLIPSE AXIS1_PLACEMENT AXIS2_PLACEMENT_2D AXIS2_PLACEMENT_3D
    VERTEX_POINT ORIENTED_EDGE EDGE_CURVE EDGE_LOOP FACE_BOUND FACE_OUTER_BOUND ADVANCED_FACE FACE_SURFACE
    PCURVE SURFACE_CURVE SEAM_CURVE DEFINITIONAL_REPRESENTATION CLOSED_SHELL OPEN_SHELL MANIFOLD_SOLID_BREP
    PLANE CYLINDRICAL_SURFACE CONICAL_SURFACE SPHERICAL_SURFACE TOROIDAL_SURFACE
    B_SPLINE_CURVE_WITH_KNOTS B_SPLINE_SURFACE_WITH_KNOTS CARTESIAN_POINT_LIST_2D CARTESIAN_POINT_LIST_3D
    COORDINATES_LIST TESSELLATED_CURVE_SET TRIANGULATED_FACE TRIANGULATED_SURFACE_SET
""".split())
_GEOMETRIE_KOPF = re.compile(r"([A-Z][A-Z_0-9]*)\s*\(")
_VERWEIS_ODER_TEXT = re.compile(r"'(?:[^']++|'')*'|#(\d+)")
_GEOMETRIE_SPERRE = Lock()


class _Geometrie(Entity):
    """Der Typ und die Originalargumente reichen, bis jemand die STEP-Geometrie tatsaechlich auswertet."""
    __slots__ = ("_name", "_inhalt")

    def __init__(self, eid, name, rumpf):
        self.id, self._name, self._inhalt = eid, name, rumpf

    @property
    def parts(self):
        if isinstance(self._inhalt, str):
            with _GEOMETRIE_SPERRE:
                if isinstance(self._inhalt, str):
                    werte, _ = _parse_list(_tokenize(self._inhalt), 1)
                    self._inhalt = {self._name: werte}
        return self._inhalt

    @parts.setter
    def parts(self, wert):
        self._inhalt = wert

    def typen(self):
        return (self._name,) if isinstance(self._inhalt, str) else self._inhalt.keys()

    @property
    def typ(self):
        return self._name if isinstance(self._inhalt, str) else super().typ

    def is_a(self, name):
        return self._name == name if isinstance(self._inhalt, str) else name in self._inhalt

    def sammle_verweise(self, rueck):
        roh = self._inhalt
        if isinstance(roh, str):
            if "#" in roh:
                for m in _VERWEIS_ODER_TEXT.finditer(roh):
                    if m[1] is not None:
                        rueck.setdefault(int(m[1]), []).append(self.id)
        else:
            super().sammle_verweise(rueck)

    def __eq__(self, andere):
        if isinstance(andere, Entity):
            return self.id == andere.id and self.parts == andere.parts
        return NotImplemented


@dataclass
class P21Datei:
    schema: str
    entities: dict[int, Entity]

    @cached_property
    def _nach_typ(self) -> dict[str, list[Entity]]:
        index = {}
        for e in self.entities.values():
            for name in e.typen():
                index.setdefault(name, []).append(e)
        return index

    def of_type(self, name: str) -> list[Entity]:
        return list(self._nach_typ.get(name, ()))

    def of_types_by_id(self, namen) -> list[Entity]:
        """Mehrere Teiltypen in ID-Reihenfolge, auch komplexe Entitaeten nur einmal."""
        treffer = {e.id: e for name in namen for e in self._nach_typ.get(name, ())}
        return [treffer[i] for i in sorted(treffer)]

    def get(self, ref) -> Entity | None:
        if isinstance(ref, Ref):
            ref = ref.id
        return self.entities.get(ref)

    def referrers(self) -> dict[int, list[int]]:
        """Rueckverweise: Ziel-ID -> Liste der IDs, die darauf zeigen."""
        if getattr(self, "_rueck", None) is None:
            rueck: dict[int, list[int]] = {}
            for e in self.entities.values():
                e.sammle_verweise(rueck)
            self._rueck = rueck
        return self._rueck


_ZAHL = r"[-+]?(?:\d++(?:\.\d*+)?|\.\d++)(?:[eE][-+]?\d++)?"
_TOKEN = re.compile(rf"""
    ( '(?:[^']++|'')*' | \#\d+ | \.[A-Z_0-9]+\.
    | {_ZAHL}
    | [A-Z_][A-Z_0-9]* | [(),$*] )
  | [^\x20\t\r\n]
""", re.VERBOSE)


def _tokenize(text: str) -> list[str]:
    # Die Fanggruppe ist bei unbekannten Zeichen leer. Nur im Fehlerfall die genaue Position suchen.
    tokens = _TOKEN.findall(text)
    if "" in tokens:
        fehler = next(m for m in _TOKEN.finditer(text) if m[1] is None)
        raise ValueError(f"Unbekanntes Zeichen {fehler[0]!r} bei {fehler.start()}")
    return tokens


def _parse_list(toks, i):
    """Liest ab '(' bis zum passenden ')'; gibt (liste, naechster index) zurueck."""
    assert toks[i] == "("
    i += 1
    out = []
    while toks[i] != ")":
        val, i = _parse_value(toks, i)
        out.append(val)
        if toks[i] == ",":
            i += 1
    return out, i + 1


def _parse_value(toks, i):
    tok = toks[i]
    anfang = tok[0]
    if anfang == "#":
        return Ref(int(tok[1:])), i + 1
    if anfang == "'":
        return _dekodiere(tok[1:-1].replace("''", "'")), i + 1
    if anfang == "." and tok.endswith("."):
        return Enum(tok[1:-1]), i + 1
    if anfang.isdecimal() or anfang in "+-.":
        return (float(tok) if "." in tok or "E" in tok or "e" in tok else int(tok)), i + 1
    if tok == "(":
        return _parse_list(toks, i)
    if tok in "$*":
        return None, i + 1
    if anfang.isupper() or anfang == "_":
        args, j = _parse_list(toks, i + 1)
        return Typed(tok, args), j
    raise ValueError(f"Unerwartet: {tok}")


_X2 = re.compile(r"\\X2\\((?:[0-9A-F]{4})+)\\X0\\")
_X = re.compile(r"\\X\\([0-9A-F]{2})")


def _dekodiere(s: str) -> str:
    """STEP-Zeichenkodierung (\\X2\\...\\X0\\, \\X\\..) in Unicode umwandeln."""
    if "\\" not in s:
        return s
    s = _X2.sub(lambda m: "".join(chr(int(m.group(1)[k:k + 4], 16))
                                  for k in range(0, len(m.group(1)), 4)), s)
    return _X.sub(lambda m: chr(int(m.group(1), 16)), s)


def _sammle_verweise(werte, quelle, rueck):
    for wert in werte:
        if isinstance(wert, Ref):
            rueck.setdefault(wert.id, []).append(quelle)
        elif isinstance(wert, list):
            _sammle_verweise(wert, quelle, rueck)
        elif isinstance(wert, Typed):
            _sammle_verweise(wert.args, quelle, rueck)


_TRENNER = re.compile(r"'(?:[^']++|'')*'|/\*.*?\*/|;", re.S)


def _statements(text: str):
    """Liefert je eine Anweisung; Texte koennen Semikolons und Kommentarzeichen enthalten."""
    start = 0
    while (ende := text.find(";", start)) >= 0:
        st = text[start:ende]
        if "/*" in st or st.count("'") % 2:
            # Das erste Semikolon kann in einem Text oder Kommentar liegen.
            teile = []
            for m in _TRENNER.finditer(text, start):
                zeichen = text[m.start()]
                if zeichen == "/":
                    teile.append(text[start:m.start()])
                    start = m.end()
                elif zeichen == ";":
                    ende = m.start()
                    teile.append(text[start:ende])
                    st = " ".join(teile)
                    break
            else:
                return
        yield st.strip()
        start = ende + 1


_KOPF = re.compile(r"^#(\d+)\s*=\s*(.*)$", re.S)
_VEKTOR = re.compile(rf"(CARTESIAN_POINT|DIRECTION)\('',\(({_ZAHL}(?:,{_ZAHL}){{1,2}})\)\)")
_VERWEISFOLGE = re.compile(r"([A-Z_][A-Z_0-9]*)\('',#([0-9]+)(?:,#([0-9]+)(?:,#([0-9]+))?)?\)")


@lru_cache(maxsize=2048)
def _koordinaten(text):
    """Wiederholte Zahlenfolgen teilen nur unveraenderliche Zahlen, keine Argumentlisten."""
    return tuple(float(z) if "." in z or "E" in z or "e" in z else int(z) for z in text.split(","))


def dateitext(pfad: str) -> str:
    """Eigentlich ASCII mit \\X2\\-Kodierung; manche Programme (auch OCCT) schreiben Umlaute als UTF-8, aeltere als
    Latin-1. Ein Latin-1-Umlaut ist kein gueltiges UTF-8, daher zuerst UTF-8, sonst Latin-1."""
    with open(pfad, "rb") as f:
        roh = f.read()
    try:
        return roh.decode("utf-8")
    except UnicodeDecodeError:
        return roh.decode("latin-1")


def lese(pfad: str) -> P21Datei:
    return lese_text(dateitext(pfad))


def lese_text(text: str, *, geometrie_spaeter: bool = False, abbruch=None) -> P21Datei:
    schema = ""
    in_daten = False
    typnamen = {}
    entities: dict[int, Entity] = {}
    for nr, st in enumerate(_statements(text)):
        if abbruch is not None and nr % 4096 == 0 and abbruch():
            raise InterruptedError("STEP-Import abgebrochen")
        if not in_daten:
            m = re.match(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']*)'", st)
            if m and not schema:
                schema = m.group(1)
            in_daten = st == "DATA" or re.match(r"DATA\s*\(", st) is not None
            continue
        if st == "ENDSEC":
            in_daten = False
            continue
        m = _KOPF.match(st)
        if not m:
            continue
        eid, rumpf = int(m.group(1)), m.group(2).strip()
        if geometrie_spaeter and (kopf := _GEOMETRIE_KOPF.match(rumpf)) and kopf[1] in _GEOMETRIE:
            name = kopf[1]
            entities[eid] = _Geometrie(eid, typnamen.setdefault(name, name), rumpf)
            continue
        # Im Cache bleiben nur kurze Zahlenfolgen in der ueblichen Schreibweise.
        if len(rumpf) <= 160 and (m := _VEKTOR.fullmatch(rumpf)):
            name, zahlen = m.groups()
            entities[eid] = Entity(eid, {typnamen.setdefault(name, name): ["", list(_koordinaten(zahlen))]})
            continue
        if m := _VERWEISFOLGE.fullmatch(rumpf):
            name, *nummern = m.groups()
            args = ["", *(Ref(int(n)) for n in nummern if n is not None)]
            entities[eid] = Entity(eid, {typnamen.setdefault(name, name): args})
            continue
        toks = _tokenize(rumpf)
        ent = Entity(eid)
        if toks[0] == "(":
            # komplexe Entitaet: (A(..) B(..) ...)
            i = 1
            while toks[i] != ")":
                name = toks[i]
                args, i = _parse_list(toks, i + 1)
                ent.parts[typnamen.setdefault(name, name)] = args
        else:
            args, _ = _parse_list(toks, 1)
            name = toks[0]
            ent.parts[typnamen.setdefault(name, name)] = args
        entities[eid] = ent
    return P21Datei(schema, entities)
