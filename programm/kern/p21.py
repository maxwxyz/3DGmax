"""Schlanker Leser fuer STEP-Dateien (ISO 10303-21) als Entitaetsgraph.

Dient zum Gegenpruefen und Ergaenzen dessen, was OCCT aus der Datei liest
(z. B. Zuordnung von PMI zu Flaechen ueber ITEM_IDENTIFIED_REPRESENTATION_USAGE).
Kein vollstaendiger Parser: Werte werden in Python-Typen zerlegt, Schema wird nicht geprueft.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# Verknuepfung Semantik -> Annotation (mit Platzhalter ab AP242 e2)
DMIA_PH = "DRAUGHTING_MODEL_ITEM_ASSOCIATION_WITH_PLACEHOLDER"


@dataclass
class Ref:
    """Verweis auf eine Entitaet (#123)."""
    id: int

    def __repr__(self):
        return f"#{self.id}"


@dataclass
class Enum:
    """Aufzaehlungswert (.T., .PARALLEL.)."""
    name: str


@dataclass
class Typed:
    """Getypter Wert, z. B. LENGTH_MEASURE(12.5)."""
    typ: str
    args: list


@dataclass
class Entity:
    id: int
    # Teiltypen; einfache Entitaet hat genau einen, komplexe mehrere
    parts: dict[str, list] = field(default_factory=dict)

    @property
    def typ(self) -> str:
        return next(iter(self.parts)) if len(self.parts) == 1 else "(" + " ".join(self.parts) + ")"

    def is_a(self, name: str) -> bool:
        return name in self.parts

    def args(self, name: str | None = None) -> list:
        if name is None:
            return next(iter(self.parts.values()))
        return self.parts[name]


@dataclass
class P21Datei:
    schema: str
    entities: dict[int, Entity]

    def of_type(self, name: str) -> list[Entity]:
        return [e for e in self.entities.values() if e.is_a(name)]

    def get(self, ref) -> Entity | None:
        if isinstance(ref, Ref):
            ref = ref.id
        return self.entities.get(ref)

    def referrers(self) -> dict[int, list[int]]:
        """Rueckverweise: Ziel-ID -> Liste der IDs, die darauf zeigen."""
        if getattr(self, "_rueck", None) is None:
            rueck: dict[int, list[int]] = {}
            for e in self.entities.values():
                for r in _refs_in(list(e.parts.values())):
                    rueck.setdefault(r, []).append(e.id)
            self._rueck = rueck
        return self._rueck


_TOKEN = re.compile(r"""
    (?P<str>'(?:[^']|'')*')
  | (?P<ref>\#\d+)
  | (?P<enum>\.[A-Z_0-9]+\.)
  | (?P<num>[-+]?(?:\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?))
  | (?P<kw>[A-Z_][A-Z_0-9]*)
  | (?P<sym>[(),$*])
""", re.VERBOSE)


def _tokenize(text: str):
    pos, n = 0, len(text)
    while pos < n:
        c = text[pos]
        if c in " \t\r\n":
            pos += 1
            continue
        m = _TOKEN.match(text, pos)
        if not m:
            raise ValueError(f"Unbekanntes Zeichen {c!r} bei {pos}")
        pos = m.end()
        yield m.lastgroup, m.group()


def _parse_list(toks, i):
    """Liest ab '(' bis zum passenden ')'; gibt (liste, naechster index) zurueck."""
    assert toks[i][1] == "("
    i += 1
    out = []
    while toks[i][1] != ")":
        val, i = _parse_value(toks, i)
        out.append(val)
        if toks[i][1] == ",":
            i += 1
    return out, i + 1


def _parse_value(toks, i):
    art, tok = toks[i]
    if art == "str":
        return _dekodiere(tok[1:-1].replace("''", "'")), i + 1
    if art == "ref":
        return Ref(int(tok[1:])), i + 1
    if art == "enum":
        return Enum(tok[1:-1]), i + 1
    if art == "num":
        return (float(tok) if any(c in tok for c in ".eE") else int(tok)), i + 1
    if art == "kw":
        args, j = _parse_list(toks, i + 1)
        return Typed(tok, args), j
    if tok == "(":
        return _parse_list(toks, i)
    if tok in "$*":
        return None, i + 1
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


def _refs_in(val):
    if isinstance(val, Ref):
        yield val.id
    elif isinstance(val, list):
        for v in val:
            yield from _refs_in(v)
    elif isinstance(val, Typed):
        yield from _refs_in(val.args)


def _statements(text: str):
    """Zerlegt den DATA-Abschnitt in Anweisungen, Semikolons in Texten bleiben erhalten."""
    out, buf, in_str = [], [], False
    for ch in text:
        if ch == "'":
            in_str = not in_str
        if ch == ";" and not in_str:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    return out


_KOPF = re.compile(r"^#(\d+)\s*=\s*(.*)$", re.S)


def lese(pfad: str) -> P21Datei:
    """Eigentlich ASCII mit \\X2\\-Kodierung; manche Programme (auch OCCT) schreiben Umlaute als UTF-8, aeltere als
    Latin-1. Ein Latin-1-Umlaut ist kein gueltiges UTF-8, daher zuerst UTF-8, sonst Latin-1."""
    with open(pfad, "rb") as f:
        roh = f.read()
    try:
        text = roh.decode("utf-8")
    except UnicodeDecodeError:
        text = roh.decode("latin-1")
    return lese_text(text)


def lese_text(text: str) -> P21Datei:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    schema = ""
    m = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']*)'", text)
    if m:
        schema = m.group(1)
    a = text.find("DATA;")
    b = text.rfind("ENDSEC;")
    entities: dict[int, Entity] = {}
    for st in _statements(text[a + 5:b]):
        m = _KOPF.match(st)
        if not m:
            continue
        eid, rumpf = int(m.group(1)), m.group(2).strip()
        toks = list(_tokenize(rumpf))
        ent = Entity(eid)
        if toks[0][1] == "(":
            # komplexe Entitaet: (A(..) B(..) ...)
            i = 1
            while toks[i][1] != ")":
                name = toks[i][1]
                args, i = _parse_list(toks, i + 1)
                ent.parts[name] = args
        else:
            args, _ = _parse_list(toks, 1)
            ent.parts[toks[0][1]] = args
        entities[eid] = ent
    return P21Datei(schema, entities)
