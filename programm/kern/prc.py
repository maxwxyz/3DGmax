"""PRC-Leser (Product Representation Compact, ISO 14739-1) fuer 3D-PDF und .prc-Dateien.

Umfang (Stufe 1-2 laut PLAN §8.15):
- PRC-Stroeme aus 3D-PDFs holen (pypdf), Dateikopf, Dateistrukturen, zlib-Sektionen.
- Schema (Zusatzdaten neuerer Versionen) auswerten und ueberspringen.
- Globals (Farben, Stile, Koordinatensysteme), Baum (Teile, Produktvorkommen, Markups, Ansichten),
  Tessellation (Flaechennetze, Drahtkanten, Markup-Grafik).
Exakte B-Rep (Geometriesektion) und die hochkomprimierte Tessellation werden noch nicht gelesen.

Grundlage ist der oeffentliche ISO-Arbeitsentwurf ISO/TC171/SC2 N570 (PRC Format Version 8137); die
Typnummern folgen dem LGPL-PRC-Code von Asymptote (prc/include/prc/PRC.h), der an realen Dateien geprueft ist.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field

import numpy as np

from .prc_bits import BitLeser, PrcFehler

VERSION = 8137  # Version des umgesetzten Entwurfs: Schema-Bloecke bis hierhin kennt der Leser selbst

# Typnummern (PRC.h)
CRV, SURF, TOPO, TESS, MISC, RI, ASM, MKP, GRAPH, MATH = 10, 75, 140, 170, 200, 230, 300, 500, 700, 900
ROOT_BASIS, ROOT_GRAFIK = 1, 2
TESS_3D, TESS_3D_KOMPRIMIERT, TESS_FLAECHE, TESS_DRAHT, TESS_MARKUP = TESS + 2, TESS + 3, TESS + 4, TESS + 5, TESS + 6
MISC_ATTRIBUT, MISC_KARTESISCH, MISC_REFERENZ, MISC_VERKNUEPFUNG = MISC + 1, MISC + 2, MISC + 3, MISC + 4
MISC_REF_BASIS, MISC_REF_TOPO, MISC_ALLGEMEIN = MISC + 5, MISC + 6, MISC + 7
RI_BREP, RI_KURVE, RI_RICHTUNG, RI_EBENE, RI_PUNKTE = RI + 2, RI + 3, RI + 4, RI + 5, RI + 6
RI_POLYBREP, RI_POLYDRAHT, RI_MENGE, RI_KOORD = RI + 7, RI + 8, RI + 9, RI + 10
ASM_MODELL, ASM_STRUKTUR, ASM_GLOBALS, ASM_BAUM, ASM_TESS = ASM + 1, ASM + 2, ASM + 3, ASM + 4, ASM + 5
ASM_GEOMETRIE, ASM_EXTRA, ASM_VORKOMMEN, ASM_TEIL, ASM_FILTER = ASM + 6, ASM + 7, ASM + 10, ASM + 11, ASM + 20
MKP_ANSICHT, MKP_MARKUP, MKP_LEADER, MKP_ITEM, MKP_SET, MKP_REF = MKP + 1, MKP + 2, MKP + 3, MKP + 4, MKP + 5, MKP + 6
GRAPH_STIL, GRAPH_MATERIAL, GRAPH_BILD = GRAPH + 1, GRAPH + 2, GRAPH + 3
GRAPH_TEX_ANW, GRAPH_TEX_DEF, GRAPH_TEX_TRAFO = GRAPH + 11, GRAPH + 12, GRAPH + 13
GRAPH_LINIENMUSTER, GRAPH_PUNKTMUSTER, GRAPH_SCHRAFFUR, GRAPH_FUELLUNG, GRAPH_VBILD = (GRAPH + 21, GRAPH + 23,
                                                                                      GRAPH + 24, GRAPH + 25,
                                                                                      GRAPH + 26)
GRAPH_LICHT = (GRAPH + 31, GRAPH + 32, GRAPH + 33, GRAPH + 34)
GRAPH_SZENE, GRAPH_KAMERA = GRAPH + 41, GRAPH + 42
SURF_EBENE = SURF + 11

# Markup-Arten (KEPRCMarkupType)
MARKUP_ARTEN = {1: "Text", 2: "Dimension", 3: "Arrow", 4: "Balloon", 5: "CircleCenter", 6: "Coordinate",
                7: "Datum", 8: "Fastener", 9: "Gdt", 10: "Locator", 11: "MeasurementPoint", 12: "Roughness",
                13: "Welding", 15: "Table", 16: "Other"}

# Kennungen in Markup-Codes
_IST_MATRIX, _IST_EXTRA, _ANZAHL_MASKE = 0x08000000, 0x04000000, 0xFFFFF


def _extra_typ(code: int) -> int:
    return (code & 0x3E00000) >> 21


# --- Datenmodell ---

@dataclass
class Netz:
    """Dreiecksnetz einer Tessellationsflaeche (lokale Koordinaten der Tessellation)."""
    punkte: np.ndarray  # (n, 3)
    dreiecke: np.ndarray  # (m, 3) Punktindizes
    stil: int = -1  # Index in Globals.stile (-1: vom Besitzer)


@dataclass
class Tessellation:
    art: int
    netze: list[Netz] = field(default_factory=list)
    linien: list[np.ndarray] = field(default_factory=list)  # Drahtkanten / Markup-Linien je (n, 3)
    dreiecke: list[np.ndarray] = field(default_factory=list)  # Markup-Flaechen je (m*3, 3)
    texte: list[tuple] = field(default_factory=list)  # (Text, Ursprung, x, y, Breite, Hoehe)
    farbe: int = -1  # Markup: zuletzt gesetzte Farbe (Index in Globals.farben)


@dataclass
class Darstellung:
    """Representation Item mit Tessellation (Flaechenmodell oder Draht)."""
    art: int
    name: str
    tess: int
    koord: int = -1  # Index in Globals.koordinatensysteme
    stil: int = -1
    sichtbar: bool = True
    kinder: list = field(default_factory=list)  # RI_Set


@dataclass
class Markup:
    eid: int
    name: str
    art: int
    unterart: int
    tess: int
    stil: int = -1


@dataclass
class PrcAnsicht:
    name: str
    eid: int
    annotationen: list[int] = field(default_factory=list)  # eindeutige IDs von Markups/Annotationen
    kamera: dict | None = None
    standard: bool = False


@dataclass
class Teil:
    name: str
    darstellungen: list[Darstellung] = field(default_factory=list)
    markups: list[Markup] = field(default_factory=list)
    ansichten: list[PrcAnsicht] = field(default_factory=list)
    stil: int = -1


@dataclass
class Vorkommen:
    name: str
    teil: int  # Index des Teils (-1: keins)
    prototyp: int
    soehne: list[int]
    lage: np.ndarray  # 4x4
    markups: list[Markup] = field(default_factory=list)
    ansichten: list[PrcAnsicht] = field(default_factory=list)
    einheit: float = 1.0
    einheit_cad: bool = False
    unterdrueckt: bool = False


@dataclass
class Globals:
    farben: list[tuple] = field(default_factory=list)
    stile: list[dict] = field(default_factory=list)
    materialien: list[dict] = field(default_factory=list)
    koordinatensysteme: list[np.ndarray] = field(default_factory=list)
    schriften: list[str] = field(default_factory=list)


@dataclass
class Dateistruktur:
    version_lesen: int
    version_autor: int
    schema: dict[int, list[int]]
    globals: Globals
    teile: list[Teil]
    vorkommen: list[Vorkommen]
    wurzel: int
    tessellationen: list[Tessellation]
    annotationen: dict[int, list[int]] = field(default_factory=dict)

    def markups_von(self, ids) -> set[int]:
        """Alle Markup-IDs unter den gegebenen Annotations- oder Markup-IDs."""
        out, offen = set(), list(ids)
        while offen:
            i = offen.pop()
            if i in out:
                continue
            out.add(i)
            offen += self.annotationen.get(i, [])
        return out


@dataclass
class PrcModell:
    strukturen: list[Dateistruktur]
    einheit: float = 1.0  # mm je Einheit laut ModelFile
    einheit_cad: bool = False
    wurzeln: list[tuple[int, int]] = field(default_factory=list)  # (Struktur, Vorkommen)


# --- PDF ---

def prc_aus_pdf(pfad: str) -> list[bytes]:
    """Alle PRC-Stroeme der 3D-Annotationen einer PDF (Reihenfolge der Seiten)."""
    import pypdf
    out = []
    for seite in pypdf.PdfReader(pfad).pages:
        for a in seite.get("/Annots") or []:
            a = a.get_object()
            if a.get("/Subtype") != "/3D":
                continue
            dd = a["/3DD"].get_object()
            if "/Subtype" not in dd and "/3DD" in dd:  # 3D-Referenzverzeichnis
                dd = dd["/3DD"].get_object()
            if str(dd.get("/Subtype", "")) == "/PRC":
                out.append(dd.get_data())
    return out


# --- Schema ---

class _Schema:
    """Interpreter fuer die Schema-Tokens (Entwurf Kap. 9): liest und verwirft Zusatzdaten."""

    def __init__(self, leser: BitLeser, typen: dict[int, list[int]]):
        self.b = leser
        self.typen = typen

    def anwenden(self, typ: int):
        tok = self.typen.get(typ)
        if tok:
            self._block(tok, 0, {}, [0], True)

    def _block(self, tok, i, werte, schleife, aktiv):
        """Eine Anweisung ab i ausfuehren (aktiv) oder nur ueberlesen; (Wert, naechstes i)."""
        t = tok[i]
        b = self.b
        lesen = {0: b.bit, 1: b.double, 2: b.zeichen, 3: b.uint, 4: b.int, 5: b.text}
        if t in lesen:
            return (lesen[t]() if aktiv else 0), i + 1
        if t in (7, 8, 9, 10, 11):
            n = {7: 2, 8: 3, 9: 2, 10: 4, 11: 6}[t]
            if aktiv:
                for _ in range(n):
                    b.double()
            return 0, i + 1
        if t == 6:  # Vatertyp: dessen Zusatzdaten
            if aktiv:
                self.anwenden(tok[i + 1])
            return 0, i + 2
        if t in (12, 13, 14):
            if aktiv:
                raise PrcFehler(f"Schema: Objektverweis {t} nicht unterstuetzt")
            return 0, i + (2 if t == 12 else 1)
        if t == 15:  # For: Anzahl, Rumpf
            n, j = self._block(tok, i + 1, werte, schleife, aktiv)
            return self._schleife(tok, j, werte, n if aktiv else 0, aktiv)
        if t == 16:  # SimpleFor: Anzahl aus der Datei
            n = b.uint() if aktiv else 0
            return self._schleife(tok, i + 1, werte, n, aktiv)
        if t == 17:  # If [Else]
            bed, j = self._block(tok, i + 1, werte, schleife, aktiv)
            _, j = self._block(tok, j, werte, schleife, aktiv and bool(bed))
            if j < len(tok) and tok[j] == 18:
                _, j = self._block(tok, j + 1, werte, schleife, aktiv and not bed)
            return 0, j
        if t in (19, 20):  # Block, versionierter Block
            j = i + (2 if t == 20 else 1)
            aktiv = aktiv and (t == 19 or tok[i + 1] > VERSION)
            eigene = dict(werte)
            while tok[j] != 21:
                _, j = self._block(tok, j, eigene, schleife, aktiv)
            return 0, j + 1
        if t == 22:
            werte[tok[i + 1]] = 0
            return 0, i + 2
        if t in (23, 24):
            w, j = self._block(tok, i + 2, werte, schleife, aktiv)
            werte[tok[i + 1]] = w
            return 0, j
        if t == 25:
            return werte.get(tok[i + 1], 0), i + 2
        if t == 26:
            return tok[i + 1], i + 2
        if t == 27:
            return schleife[-1], i + 1
        if t == 28:
            return 1, i + 1
        if 29 <= t <= 38:
            a, j = self._block(tok, i + 1, werte, schleife, aktiv)
            c, j = self._block(tok, j, werte, schleife, aktiv)
            ops = {29: lambda x, y: x * y, 30: lambda x, y: x // y if y else 0, 31: lambda x, y: x + y,
                   32: lambda x, y: x - y, 33: lambda x, y: x < y, 34: lambda x, y: x <= y,
                   35: lambda x, y: x > y, 36: lambda x, y: x >= y, 37: lambda x, y: x == y,
                   38: lambda x, y: x != y}
            return ops[t](a, c), j
        if t == 39:  # in neueren Schemas vor dem ersten Block; ein Argument, ohne Daten
            return 0, i + 2
        raise PrcFehler(f"Unbekanntes Schema-Token {t}")

    def _schleife(self, tok, i, werte, n, aktiv):
        j = i
        if not aktiv or n == 0:
            _, j = self._block(tok, i, werte, [0], False)
            return 0, j
        for k in range(n):
            _, j = self._block(tok, i, werte, [k], True)
        return 0, j


# --- Leser fuer eine Sektion ---

class _Sektion:
    """Liest Entitaeten aus einer dekomprimierten Sektion; aktueller Name/Grafik wie in Kap. 5.4."""

    def __init__(self, daten: bytes, schema: dict[int, list[int]]):
        self.b = BitLeser(daten)
        self.schema = _Schema(self.b, schema)
        self.name = ""
        self.grafik = (-1, -1, 1)  # Ebene, Stil, Verhalten
        self.annotationen: dict[int, list[int]] = {}  # Annotations-ID -> enthaltene IDs

    # Grundbausteine

    def typ(self, erwartet: int | None = None) -> int:
        t = self.b.uint()
        if erwartet is not None and t != erwartet:
            raise PrcFehler(f"Typ {erwartet} erwartet, {t} gelesen (Bit {self.b.pos})")
        return t

    def vektor(self, n=3) -> np.ndarray:
        return np.array([self.b.double() for _ in range(n)])

    def attribute(self):
        for _ in range(self.b.uint()):
            self.typ(MISC_ATTRIBUT)
            self._titel()
            for _ in range(self.b.uint()):
                self._titel()
                art = self.b.uint()
                {1: self.b.int, 2: self.b.double, 3: self.b.uint, 4: self.b.text}.get(art, lambda: None)()

    def _titel(self):
        return self.b.uint() if self.b.bit() else self.b.text()

    def name_lesen(self) -> str:
        if not self.b.bit():
            self.name = self.b.text()
        return self.name

    def basis(self, referenzierbar: bool) -> tuple[str, int]:
        """ContentPRCBase: (Name, eindeutige ID)."""
        self.attribute()
        name = self.name_lesen()
        eid = 0
        if referenzierbar:
            self.b.uint()
            self.b.uint()
            eid = self.b.uint()
        return name, eid

    def basis_grafik(self, referenzierbar=True) -> tuple[str, int, tuple]:
        name, eid = self.basis(referenzierbar)
        if not self.b.bit():
            ebene = self.b.uint() - 1
            stil = self.b.uint() - 1
            verhalten = self.b.zeichen() | (self.b.zeichen() << 8)
            self.grafik = (ebene, stil, verhalten)
        self.schema.anwenden(ROOT_GRAFIK)
        return name, eid, self.grafik

    def nutzerdaten(self):
        n = self.b.uint()
        if n > self.b.laenge - self.b.pos:
            raise PrcFehler("Nutzerdaten laenger als die Sektion")
        self.b.pos += n

    def ende(self, typ: int):
        """Zusatzdaten laut Schema, dann Nutzerdaten."""
        self.schema.anwenden(typ)
        self.nutzerdaten()

    def eindeutige_id(self) -> tuple:
        return self.b.uid()

    # Transformationen

    def kartesisch(self) -> np.ndarray:
        """Transformation (Kap. 7.4.11) als 4x4-Matrix."""
        b = self.b
        art = b.zeichen()
        m = np.eye(4)
        if art & 0x01:
            m[:3, 3] = self.vektor()
        if art & 0x20:
            m[:3, 0], m[:3, 1], m[:3, 2] = self.vektor(), self.vektor(), self.vektor()
        elif art & 0x02:
            x, y = self.vektor(), self.vektor()
            z = np.cross(y, x) if art & 0x04 else np.cross(x, y)
            m[:3, 0], m[:3, 1], m[:3, 2] = x, y, z
        if art & 0x10:
            m[:3, :3] = m[:3, :3] * self.vektor()
        if art & 0x08:
            m[:3, :3] *= b.double()
        if art & 0x40:
            m[3, :] = self.vektor(4)
        return m

    def transformation_objekt(self) -> np.ndarray:
        t = self.typ()
        if t == MISC_KARTESISCH:
            m = self.kartesisch()
        elif t == MISC_ALLGEMEIN:
            m = np.array([self.b.double() for _ in range(16)]).reshape(4, 4).T
        else:
            raise PrcFehler(f"Unbekannte Transformation {t}")
        self.schema.anwenden(t)
        return m

    def transformation_geometrie(self) -> np.ndarray:
        if not self.b.bit():
            return np.eye(4)
        return self.kartesisch()

    # Verweise

    def referenz_basis(self) -> int:
        """ReferenceOnPRCBase ohne Typkennung davor: eindeutige ID (Fremdstruktur: 0)."""
        self.b.uint()  # Zieltyp
        gleich = self.b.bit()
        if not gleich:
            self.eindeutige_id()
        eid = self.b.uint()
        return eid if gleich else 0

    def referenz_daten(self):
        t = self.typ()
        if t == MISC_REF_TOPO:
            self.b.uint()
            if self.b.bit():
                if not self.b.bit():
                    self.eindeutige_id()
                self.b.uint()
                self.b.uint()
                for _ in range(self.b.uint()):
                    self.b.uint()
        elif t == MISC_REF_BASIS:
            self.referenz_basis()
        else:
            raise PrcFehler(f"Unbekannter Verweis {t}")

    def inhalt_referenz(self):
        self.basis_grafik()
        self.b.uint()  # lokales Koordinatensystem + 1
        if self.b.bit():
            self.referenz_daten()

    def entitaets_referenz(self):
        self.typ(MISC_REFERENZ)
        self.inhalt_referenz()
        self.ende(MISC_REFERENZ)

    def eindeutige_ids(self) -> list[int]:
        out = []
        for _ in range(self.b.uint()):
            self.typ(MISC_REF_BASIS)
            out.append(self.referenz_basis())
        return out

    # Grafik in Globals

    def bild(self):
        self.typ(GRAPH_BILD)
        self.basis(False)
        self.b.int()
        for _ in range(3):
            self.b.uint()
        self.schema.anwenden(GRAPH_BILD)

    def stil(self) -> dict:
        self.typ(GRAPH_STIL)
        self.basis(True)
        b = self.b
        breite = b.double()
        b.bit()
        b.uint()
        ist_material = b.bit()
        idx = b.uint() - 1
        transparenz = b.zeichen() if b.bit() else 255
        for _ in range(3):  # Zusatzparameter (Rendering u. a.)
            if b.bit():
                b.zeichen()
        self.schema.anwenden(GRAPH_STIL)
        return {"breite": breite, "material": ist_material, "index": idx, "alpha": transparenz}

    def material(self) -> dict:
        t = self.typ()
        if t != GRAPH_MATERIAL:
            raise PrcFehler(f"Material-Typ {t} (Texturen) nicht unterstuetzt")
        self.basis(True)
        idx = [self.b.uint() - 1 for _ in range(4)]
        werte = [self.b.double() for _ in range(5)]
        self.schema.anwenden(t)
        return {"umgebung": idx[0], "diffus": idx[1], "alpha": werte[2]}

    def linienmuster(self):
        self.typ(GRAPH_LINIENMUSTER)
        self.basis(True)
        for _ in range(self.b.uint()):
            self.b.double()
        self.b.double()
        self.b.bit()
        self.schema.anwenden(GRAPH_LINIENMUSTER)

    def fuellmuster(self):
        t = self.typ()
        self.basis(True)
        b = self.b
        b.uint()
        if t == GRAPH_PUNKTMUSTER:
            b.double()
            b.bit()
            b.int()
        elif t == GRAPH_SCHRAFFUR:
            for _ in range(b.uint()):
                for _ in range(5):
                    b.double()
                b.uint()
        elif t == GRAPH_FUELLUNG:
            b.bit()
            b.uint()
        elif t == GRAPH_VBILD:
            b.double()
            b.double()
            self.typ(TESS_MARKUP)
            _markup_tess(self)
        else:
            raise PrcFehler(f"Unbekanntes Fuellmuster {t}")
        self.schema.anwenden(t)

    def koordinatensystem(self) -> np.ndarray:
        self.typ(RI_KOORD)
        self.basis_grafik()
        self.b.uint()
        self.b.uint()
        m = self.transformation_objekt()
        self.ende(RI_KOORD)
        return m

    # Szene und Ansichten

    def kamera(self) -> dict:
        self.typ(GRAPH_KAMERA)
        self.basis(True)
        b = self.b
        ortho = b.bit()
        ort, ziel, oben = self.vektor(), self.vektor(), self.vektor()
        fx, fy = b.double(), b.double()
        verh, nah, fern, zoom = b.double(), b.double(), b.double(), b.double()
        self.schema.anwenden(GRAPH_KAMERA)
        return {"ortho": ortho, "ort": ort, "ziel": ziel, "oben": oben, "fx": fx, "fy": fy,
                "verhaeltnis": verh, "nah": nah, "fern": fern, "zoom": zoom}

    def licht(self):
        t = self.typ()
        if t not in GRAPH_LICHT:
            raise PrcFehler(f"Unbekanntes Licht {t}")
        self.basis(True)
        for _ in range(4):
            self.b.uint()
        if t == GRAPH_LICHT[1]:
            self.vektor()
            self.vektor()
        elif t == GRAPH_LICHT[2]:
            self.vektor()
            self.b.double()
        elif t == GRAPH_LICHT[3]:
            self.vektor()
            self.vektor()
            self.vektor()
            self.b.double()
            self.b.double()
        self.schema.anwenden(t)

    def ebene(self) -> np.ndarray:
        """PRC_TYPE_SURF_Plane (Typkennung schon gelesen): Lage der Ebene als 4x4.

        Reale Dateien weichen vom Entwurf ab (zusaetzliche Bits vor der Parametrisierung, auch der
        Asymptote-Leser findet sie nicht). Wie dort wird bis zur Standard-Parametrisierung
        [-12345, 12345]^2, Koeffizienten (1, 1, 0, 0) gesucht.
        """
        b = self.b
        start = b.pos
        m = np.eye(4)
        if b.bit():  # BaseGeometry
            self.attribute()
            self.name_lesen()
            b.uint()
        b.uint()  # Fortsetzungsart
        if b.bit():
            b.pos -= 1
            m = self.transformation_geometrie()
        such = b.pos
        for versatz in range(64):
            b.pos = such + versatz
            try:
                werte = [b.double() for _ in range(8)]
            except (PrcFehler, IndexError):
                continue
            if werte == [-12345.0, -12345.0, 12345.0, 12345.0, 1.0, 1.0, 0.0, 0.0]:
                self.schema.anwenden(SURF_EBENE)
                return m
        raise PrcFehler(f"Ebene ab Bit {start} nicht lesbar")

    def szene(self) -> dict | None:
        self.typ(GRAPH_SZENE)
        self.basis(True)
        b = self.b
        b.bit()
        for _ in range(b.uint()):
            self.licht()
        kamera = self.kamera() if b.bit() else None
        if b.bit():
            self.vektor()
        for _ in range(b.uint()):
            self.typ(SURF_EBENE)
            self.ebene()
        b.uint()
        b.uint()
        for _ in range(b.uint()):
            b.uint()
            b.uint()
        b.bit()
        self.schema.anwenden(GRAPH_SZENE)
        return kamera

    def filter(self):
        self.typ(ASM_FILTER)
        self.basis(True)
        b = self.b
        b.bit()
        for _ in range(b.uint()):
            b.uint()
        b.bit()
        for _ in range(b.uint()):
            self.entitaets_referenz()
        self.ende(ASM_FILTER)

    def ansicht(self) -> PrcAnsicht:
        self.typ(MKP_ANSICHT)
        name, eid, _ = self.basis_grafik()
        a = PrcAnsicht(name, eid, self.eindeutige_ids())
        t = self.typ()
        if t == SURF_EBENE:
            self.ebene()
        elif t != 0:
            raise PrcFehler(f"Annotationsebene: Typ {t}")
        if self.b.bit():
            a.kamera = self.szene()
        self.b.bit()
        a.standard = self.b.bit()
        self.b.bit()
        self.eindeutige_ids()
        for _ in range(self.b.uint()):
            self.filter()
        self.ende(MKP_ANSICHT)
        return a

    # Markups

    def verknuepfung(self):
        self.typ(MISC_VERKNUEPFUNG)
        self.inhalt_referenz()
        if self.b.bit():  # Verweis auf das Produktvorkommen (ContentExtendedEntityReference)
            self.referenz_daten()
        for _ in range(4):
            self.b.bit()
        self.ende(MISC_VERKNUEPFUNG)

    def leader(self):
        self.typ(MKP_LEADER)
        self.basis_grafik()
        self.eindeutige_ids()
        self.eindeutige_ids()
        self.b.uint()
        self.ende(MKP_LEADER)

    def markup(self) -> Markup:
        self.typ(MKP_MARKUP)
        name, eid, grafik = self.basis_grafik()
        art, unter = self.b.uint(), self.b.uint()
        self.eindeutige_ids()
        self.eindeutige_ids()
        tess = self.b.uint() - 1
        self.ende(MKP_MARKUP)
        return Markup(eid, name, art, unter, tess, grafik[1])

    def annotation(self) -> int:
        """Annotation (Item, Set, Referenz); merkt sich die enthaltenen IDs in self.annotationen."""
        t = self.typ()
        _, eid, _ = self.basis_grafik()
        ziele = []
        if t == MKP_ITEM:
            self.typ(MISC_REF_BASIS)
            ziele.append(self.referenz_basis())
        elif t == MKP_SET:
            ziele = [self.annotation() for _ in range(self.b.uint())]
        elif t == MKP_REF:
            ziele = self.eindeutige_ids()
        else:
            raise PrcFehler(f"Unbekannte Annotation {t}")
        self.ende(t)
        self.annotationen[eid] = ziele
        return eid

    def markup_daten(self) -> list[Markup]:
        b = self.b
        for _ in range(b.uint()):
            self.verknuepfung()
        for _ in range(b.uint()):
            self.leader()
        out = [self.markup() for _ in range(b.uint())]
        for _ in range(b.uint()):
            self.annotation()
        return out

    # Darstellungen

    def darstellung(self) -> Darstellung | None:
        t = self.typ()
        name, eid, grafik = self.basis_grafik()
        koord, tess = self.b.uint() - 1, self.b.uint() - 1
        d = Darstellung(t, name, tess, koord, grafik[1], bool(grafik[2] & 1))
        b = self.b
        if t in (RI_BREP, RI_KURVE, RI_EBENE):
            if b.bit():
                b.uint()
                b.uint()
            if t == RI_BREP:
                b.bit()
        elif t == RI_RICHTUNG:
            if b.bit():
                self.vektor()
            self.vektor()
        elif t == RI_PUNKTE:
            for _ in range(b.uint()):
                self.vektor()
        elif t == RI_POLYBREP:
            b.bit()
        elif t == RI_MENGE:
            d.kinder = [self.darstellung() for _ in range(b.uint())]
        elif t == RI_KOORD:
            self.transformation_objekt()
        elif t != RI_POLYDRAHT:
            raise PrcFehler(f"Unbekanntes Representation Item {t}")
        self.ende(t)
        return d

    def teil(self) -> Teil:
        self.typ(ASM_TEIL)
        name, _, grafik = self.basis_grafik()
        self.vektor()
        self.vektor()
        t = Teil(name, stil=grafik[1])
        t.darstellungen = [self.darstellung() for _ in range(self.b.uint())]
        t.markups = self.markup_daten()
        t.ansichten = [self.ansicht() for _ in range(self.b.uint())]
        self.ende(ASM_TEIL)
        return t

    def vorkommen(self) -> Vorkommen:
        self.typ(ASM_VORKOMMEN)
        name, _, _ = self.basis_grafik()
        b = self.b
        teil = b.uint() - 1
        proto = b.uint() - 1
        if proto >= 0 and not b.bit():
            self.eindeutige_id()
        extern = b.uint() - 1
        if extern >= 0 and not b.bit():
            self.eindeutige_id()
        soehne = [b.uint() for _ in range(b.uint())]
        verhalten = b.zeichen()
        einheit_cad = b.bit()
        einheit = b.double()
        b.zeichen()
        b.int()
        lage = self.transformation_objekt() if b.bit() else np.eye(4)
        for _ in range(b.uint()):
            self.entitaets_referenz()
        v = Vorkommen(name, teil, proto, soehne, lage, einheit=einheit, einheit_cad=einheit_cad,
                      unterdrueckt=bool(verhalten & 1))
        v.markups = self.markup_daten()
        v.ansichten = [self.ansicht() for _ in range(b.uint())]
        if b.bit():
            self.filter()
        for _ in range(b.uint()):
            self.filter()
        for _ in range(b.uint()):
            self.szene()
        self.ende(ASM_VORKOMMEN)
        return v


# --- Sektionen ---

def _schema_lesen(s: _Sektion) -> dict[int, list[int]]:
    out = {}
    for _ in range(s.b.uint()):
        typ = s.b.uint()
        out[typ] = [s.b.uint() for _ in range(s.b.uint())]
    return out


def _globals(s: _Sektion) -> Globals:
    b = s.b
    s.typ(ASM_GLOBALS)
    s.basis(False)
    for _ in range(b.uint()):
        s.eindeutige_id()
    g = Globals()
    b.double()
    b.double()
    b.text()
    for _ in range(b.uint()):
        g.schriften.append(b.text())
        b.uint()
        for _ in range(b.uint()):
            b.uint()
            b.zeichen()
    g.farben = [(b.double(), b.double(), b.double()) for _ in range(b.uint())]
    for _ in range(b.uint()):
        s.bild()
    if b.uint():
        raise PrcFehler("Texturdefinitionen werden nicht unterstuetzt")
    g.materialien = [s.material() for _ in range(b.uint())]
    for _ in range(b.uint()):
        s.linienmuster()
    g.stile = [s.stil() for _ in range(b.uint())]
    for _ in range(b.uint()):
        s.fuellmuster()
    g.koordinatensysteme = [s.koordinatensystem() for _ in range(b.uint())]
    s.ende(ASM_GLOBALS)
    return g


def _baum(s: _Sektion) -> tuple[list[Teil], list[Vorkommen], int]:
    s.typ(ASM_BAUM)
    s.basis(False)
    teile = [s.teil() for _ in range(s.b.uint())]
    vorkommen = [s.vorkommen() for _ in range(s.b.uint())]
    s.typ(ASM_STRUKTUR)
    s.basis(False)
    s.b.uint()  # naechster freier Index
    wurzel = s.b.uint() - 1
    s.schema.anwenden(ASM_STRUKTUR)
    return teile, vorkommen, wurzel


def _basis_tess(s: _Sektion) -> np.ndarray:
    s.b.bit()
    n = s.b.uint()
    return np.array([s.b.double() for _ in range(n)])


def _vertex_farben(s: _Sektion, n: int):
    b = s.b
    rgba = b.bit()
    b.bit()
    if b.bit():
        raise PrcFehler("Optimierte Vertexfarben nicht unterstuetzt")
    k = 4 if rgba else 3
    for i in range(n):
        if i == 0 or not b.bit():
            for _ in range(k):
                b.zeichen()


def _dreiecke_aus_flaeche(ti: np.ndarray, start: int, art: int, groessen: list[int], textur: int) -> tuple:
    """Punktindizes (je 3) aus dem Index-Array einer Tessellationsflaeche; (Dreiecke, naechster Start)."""
    out, pos, g = [], start, 0
    norm_einzeln = 0x40000000
    for bit in range(16):
        flag = 1 << bit
        if not art & flag:
            continue
        if flag in (0x0001, 0x0010, 0x0100, 0x1000):
            raise PrcFehler(f"Tessellationsart {flag:#x} nicht unterstuetzt")
        t = textur if flag >= 0x0200 else 0
        if flag in (0x0002, 0x0200):  # Dreiecke: (n, [t], p) x3
            n = groessen[g]
            g += 1
            schritt = 2 + t
            for _ in range(n):
                out.append([ti[pos + schritt * k + 1 + t] for k in range(3)])
                pos += 3 * schritt
        elif flag in (0x0020, 0x2000):  # ein Normale je Dreieck: n, ([t], p) x3
            n = groessen[g]
            g += 1
            for _ in range(n):
                pos += 1
                out.append([ti[pos + (1 + t) * k + t] for k in range(3)])
                pos += 3 * (1 + t)
        else:  # Faecher und Streifen: Anzahl, dann Punktzahl je Element
            n = groessen[g]
            g += 1
            for _ in range(n):
                anz = groessen[g]
                g += 1
                einzeln = bool(anz & norm_einzeln) and flag in (0x0040, 0x0080, 0x4000, 0x8000)
                anz &= ~norm_einzeln
                pkt = []
                if einzeln:
                    pos += 1
                    for _ in range(anz):
                        pkt.append(ti[pos + t])
                        pos += 1 + t
                else:
                    for _ in range(anz):
                        pkt.append(ti[pos + 1 + t])
                        pos += 2 + t
                if flag in (0x0004, 0x0040, 0x0400, 0x4000):
                    out += [[pkt[0], pkt[k], pkt[k + 1]] for k in range(1, anz - 1)]
                else:
                    out += [[pkt[k], pkt[k + 1], pkt[k + 2]] if k % 2 == 0 else [pkt[k + 1], pkt[k], pkt[k + 2]]
                            for k in range(anz - 2)]
    return out, pos


def _tess_3d(s: _Sektion) -> Tessellation:
    b = s.b
    koord = _basis_tess(s)
    b.bit()
    b.bit()
    if b.bit():  # Normalen neu berechnen
        b.zeichen()
        b.double()
    for _ in range(b.uint()):
        b.double()
    draht = [b.uint() for _ in range(b.uint())]
    ti = [b.uint() for _ in range(b.uint())]
    flaechen = []
    for _ in range(b.uint()):
        s.typ(TESS_FLAECHE)
        attr = [b.uint() - 1 for _ in range(b.uint())]
        b.uint()
        for _ in range(b.uint()):
            b.uint()
        art = b.uint()
        start = b.uint()
        groessen = [b.uint() for _ in range(b.uint())]
        textur = b.uint()
        if b.bit():
            _vertex_farben(s, 3 * sum(groessen))
        if attr:
            b.uint()
        flaechen.append((attr, art, start, groessen, textur))
    for _ in range(b.uint()):
        b.double()
    punkte = koord.reshape(-1, 3)
    t = Tessellation(TESS_3D)
    for attr, art, start, groessen, textur in flaechen:
        dreiecke, _ = _dreiecke_aus_flaeche(ti, start, art, groessen, textur)
        if dreiecke:
            idx = np.asarray(dreiecke, dtype=np.int64) // 3
            benutzt, neu = np.unique(idx, return_inverse=True)
            t.netze.append(Netz(punkte[benutzt], neu.reshape(-1, 3), attr[0] if attr else -1))
    del draht
    return t


def _tess_draht(s: _Sektion) -> Tessellation:
    b = s.b
    pkt = _basis_tess(s).reshape(-1, 3)
    idx = [b.int() for _ in range(b.uint())]
    if b.bit():
        _vertex_farben(s, len(pkt))
    t = Tessellation(TESS_DRAHT)
    if not idx:
        t.linien.append(pkt)
        return t
    i = 0
    while i < len(idx):
        kopf = idx[i] & 0xFFFFFFFF
        n = kopf & 0x0FFFFFFF
        teil = [p // 3 for p in idx[i + 1:i + 1 + n]]
        i += 1 + n
        if kopf & 0x10000000 and teil:
            teil.append(teil[0])
        if kopf & 0x20000000 and t.linien and teil:
            t.linien[-1] = np.vstack([t.linien[-1], pkt[teil]])
        elif len(teil) > 1:
            t.linien.append(pkt[teil])
    return t


def _markup_tess(s: _Sektion) -> Tessellation:
    b = s.b
    werte = _basis_tess(s)
    codes = [b.uint() for _ in range(b.uint())]
    texte = [b.text() for _ in range(b.uint())]
    b.text()
    b.zeichen()
    return _markup_grafik(codes, werte, texte)


def _markup_grafik(codes: list[int], werte: np.ndarray, texte: list[str]) -> Tessellation:
    """Markup-Codes (Kap. 7.8.8) in Linien, Flaechen und Texte umsetzen (Matrixbloecke werden angewandt)."""
    t = Tessellation(TESS_MARKUP)
    stapel = [np.eye(4)]
    enden = []  # (Code-Position, an der der Block endet)
    ci, wi = 0, 0
    schrift = -1

    def trafo(p):
        m = stapel[-1]
        return p @ m[:3, :3].T + m[:3, 3]

    while ci + 1 < len(codes):
        kopf, nd = codes[ci], codes[ci + 1]
        inner = kopf & _ANZAHL_MASKE
        innen = codes[ci + 2:ci + 2 + (0 if (kopf & _IST_MATRIX or _extra_typ(kopf) in (6, 7, 8)) else inner)]
        d = werte[wi:wi + nd]
        if kopf & _IST_MATRIX:
            if inner:
                m = d[:16].reshape(4, 4).T
                stapel.append(stapel[-1] @ m)
                wi += 16
            elif len(stapel) > 1:
                stapel.pop()
            ci += 2
            continue
        if kopf & _IST_EXTRA:
            art = _extra_typ(kopf)
            if art in (6, 7, 8):  # Bloecke (Billboard, 2D, feste Groesse): Ursprung als Verschiebung
                if inner:
                    m = np.eye(4)
                    m[:3, 3] = d[:3]
                    stapel.append(stapel[-1] @ m)
                    wi += 3
                elif len(stapel) > 1:
                    stapel.pop()
                ci += 2
                continue
            if art == 2 and nd:
                t.dreiecke.append(trafo(d.reshape(-1, 3)))
            elif art == 3 and nd:
                q = d.reshape(-1, 4, 3)
                t.dreiecke.append(trafo(q[:, [0, 1, 2, 0, 2, 3]].reshape(-1, 3)))
            elif art == 16 and nd:
                p = trafo(d.reshape(-1, 3))
                t.linien.append(np.vstack([p, p[:1]]))
            elif art == 11 and innen:
                t.farbe = innen[0]
            elif art == 13 and innen:
                schrift = innen[0]
            elif art == 14 and innen and innen[0] < len(texte):
                m = stapel[-1]
                breite, hoehe = (float(d[0]), float(d[1])) if nd >= 2 else (0.0, 0.0)
                t.texte.append((texte[innen[0]], m[:3, 3].copy(), m[:3, 0].copy(), m[:3, 1].copy(), breite,
                                hoehe, schrift))
        elif nd >= 6:  # Linienzug
            t.linien.append(trafo(d.reshape(-1, 3)))
        ci += 2 + len(innen)
        wi += nd
    return t


def _tessellation(s: _Sektion) -> list[Tessellation]:
    s.typ(ASM_TESS)
    s.basis(False)
    out = []
    for _ in range(s.b.uint()):
        t = s.typ()
        if t == TESS_3D:
            out.append(_tess_3d(s))
        elif t == TESS_DRAHT:
            out.append(_tess_draht(s))
        elif t == TESS_MARKUP:
            out.append(_markup_tess(s))
        elif t == TESS_3D_KOMPRIMIERT:
            raise PrcFehler("Hochkomprimierte Tessellation wird noch nicht unterstuetzt")
        else:
            raise PrcFehler(f"Unbekannte Tessellation {t}")
    return out


# --- Datei ---

def _entpacken(daten: bytes, start: int) -> bytes:
    try:
        return zlib.decompressobj().decompress(daten[start:])
    except zlib.error as e:
        raise PrcFehler(f"Sektion bei Byte {start} nicht lesbar: {e}") from e


def lies_prc(daten: bytes) -> PrcModell:
    if daten[:3] != b"PRC":
        raise PrcFehler("Keine PRC-Daten")
    p = 3 + 8 + 32
    (n,) = struct.unpack_from("<I", daten, p)
    p += 4
    beschreibungen = []
    for _ in range(n):
        p += 20
        (k,) = struct.unpack_from("<I", daten, p)
        p += 4
        beschreibungen.append(struct.unpack_from(f"<{k}I", daten, p))
        p += 4 * k
    (modell_start,) = struct.unpack_from("<I", daten, p)
    strukturen = [_struktur(daten, offs) for offs in beschreibungen]
    modell = PrcModell(strukturen)
    _modelldatei(modell, _entpacken(daten, modell_start), len(strukturen))
    return modell


def _struktur(daten: bytes, offs) -> Dateistruktur:
    if len(offs) < 6:
        raise PrcFehler("Dateistruktur mit zu wenigen Sektionen")
    kopf = offs[0]
    v_lesen, v_autor = struct.unpack_from("<II", daten, kopf + 3)
    g = _Sektion(_entpacken(daten, offs[1]), {})
    schema = _schema_lesen(g)
    g.schema.typen = schema
    glob = _globals(g)
    baum = _Sektion(_entpacken(daten, offs[2]), schema)
    teile, vorkommen, wurzel = _baum(baum)
    tess = _tessellation(_Sektion(_entpacken(daten, offs[3]), schema))
    return Dateistruktur(v_lesen, v_autor, schema, glob, teile, vorkommen, wurzel, tess, baum.annotationen)


def _modelldatei(modell: PrcModell, daten: bytes, n: int):
    s = _Sektion(daten, {})
    s.schema.typen = _schema_lesen(s)
    s.typ(ASM_MODELL)
    s.basis(False)
    modell.einheit_cad = s.b.bit()
    modell.einheit = s.b.double() or 1.0
    for _ in range(s.b.uint()):
        s.eindeutige_id()
        idx = s.b.uint() - 1
        s.b.bit()
        modell.wurzeln.append((0, idx))
    del n


def lies_datei(pfad: str) -> PrcModell:
    """PRC aus .prc oder 3D-PDF (erster PRC-Strom) lesen."""
    if pfad.lower().endswith(".pdf"):
        stroeme = prc_aus_pdf(pfad)
        if not stroeme:
            raise PrcFehler(f"Kein PRC-Inhalt in der PDF: {pfad}")
        return lies_prc(stroeme[0])
    with open(pfad, "rb") as f:
        return lies_prc(f.read())


# --- Auswertung fuer 3DGmax (ohne OCCT) ---

@dataclass
class Koerper:
    """Flaechenmodell eines Representation Items in mm (Weltlage)."""
    name: str
    flaechen: list[tuple[np.ndarray, np.ndarray, tuple | None]]  # (Punkte, Dreiecke, Farbe)
    hilfsgeometrie: bool = False


@dataclass
class MarkupGrafik:
    eid: int
    name: str
    art: str
    linien: list[np.ndarray]
    dreiecke: list[np.ndarray]
    farbe: tuple | None


def einheit_mm(modell: PrcModell) -> float:
    """Erste gueltige Einheit: ModelFile, sonst Produktvorkommen (Kap. 5.6)."""
    if modell.einheit_cad:
        return modell.einheit
    for st in modell.strukturen:
        for v in st.vorkommen:
            if v.einheit_cad:
                return v.einheit
    return modell.einheit


def stilfarbe(g: Globals, stil: int) -> tuple | None:
    if not 0 <= stil < len(g.stile):
        return None
    s = g.stile[stil]
    idx = s["index"]
    if s["material"]:
        if not 0 <= idx < len(g.materialien):
            return None
        idx = g.materialien[idx]["diffus"]
    # Farbindizes zeigen auf das Double-Feld (r, g, b je Farbe)
    k = idx // 3 if idx >= 0 else -1
    return g.farben[k] if 0 <= k < len(g.farben) else None


def stil_transparent(g: Globals, stil: int) -> bool:
    return 0 <= stil < len(g.stile) and g.stile[stil]["alpha"] < 255


def _vorkommen_lagen(st: Dateistruktur):
    """(Vorkommen, Weltmatrix) fuer alle Vorkommen unter der Wurzel; Prototypen werden aufgeloest."""
    out = []

    def besuche(i, m, tiefe):
        if not 0 <= i < len(st.vorkommen) or tiefe > 32:
            return
        v = st.vorkommen[i]
        if v.unterdrueckt:
            return
        m = m @ v.lage
        out.append((v, m))
        soehne = v.soehne
        if not soehne and v.teil < 0 and 0 <= v.prototyp < len(st.vorkommen):
            proto = st.vorkommen[v.prototyp]
            soehne = proto.soehne
            if proto.teil >= 0:
                out[-1] = (Vorkommen(v.name, proto.teil, -1, [], v.lage, v.markups, v.ansichten), m)
        for s in soehne:
            besuche(s, m, tiefe + 1)

    wurzel = st.wurzel if 0 <= st.wurzel < len(st.vorkommen) else len(st.vorkommen) - 1
    besuche(wurzel, np.eye(4), 0)
    return out


def _darstellungen(liste):
    for d in liste:
        yield d
        yield from _darstellungen(d.kinder)


def koerper(modell: PrcModell) -> list[Koerper]:
    """Alle Flaechenmodelle (BrepModel/PolyBrepModel mit Tessellation) in Weltlage und mm."""
    f = einheit_mm(modell)
    skala = np.diag([f, f, f, 1.0])
    out = []
    for st in modell.strukturen:
        g = st.globals
        for v, m in _vorkommen_lagen(st):
            if not 0 <= v.teil < len(st.teile):
                continue
            teil = st.teile[v.teil]
            for d in _darstellungen(teil.darstellungen):
                if d.art not in (RI_BREP, RI_POLYBREP) or not 0 <= d.tess < len(st.tessellationen):
                    continue
                t = st.tessellationen[d.tess]
                if t.art != TESS_3D or not t.netze:
                    continue
                lokal = g.koordinatensysteme[d.koord] if 0 <= d.koord < len(g.koordinatensysteme) else np.eye(4)
                welt = skala @ m @ lokal
                stil = d.stil if d.stil >= 0 else teil.stil
                flaechen = []
                for n in t.netze:
                    p = n.punkte @ welt[:3, :3].T + welt[:3, 3]
                    flaechen.append((p, n.dreiecke, stilfarbe(g, n.stil if n.stil >= 0 else stil)))
                name = d.name or teil.name or v.name or "PRC"
                out.append(Koerper(name, flaechen, stil_transparent(g, stil) or not d.sichtbar))
    return out


def markup_grafik(modell: PrcModell) -> list[MarkupGrafik]:
    f = einheit_mm(modell)
    skala = np.diag([f, f, f, 1.0])
    out = []
    for st in modell.strukturen:
        g = st.globals
        for v, m in _vorkommen_lagen(st):
            markups = list(v.markups)
            if 0 <= v.teil < len(st.teile):
                markups += st.teile[v.teil].markups
            welt = skala @ m
            for k in markups:
                if not 0 <= k.tess < len(st.tessellationen):
                    continue
                t = st.tessellationen[k.tess]
                if t.art != TESS_MARKUP:
                    continue
                tr = lambda p: p @ welt[:3, :3].T + welt[:3, 3]  # noqa: E731
                farbe = stilfarbe(g, k.stil)
                if t.farbe >= 0:
                    j = t.farbe // 3
                    farbe = g.farben[j] if 0 <= j < len(g.farben) else farbe
                out.append(MarkupGrafik(k.eid, k.name, MARKUP_ARTEN.get(k.art, "Other"),
                                        [tr(l) for l in t.linien], [tr(d) for d in t.dreiecke], farbe))
    return out


def ansichten(modell: PrcModell) -> list[dict]:
    """Gespeicherte Ansichten: Name, Kamera (mm), sichtbare Markup-IDs."""
    f = einheit_mm(modell)
    out = []
    for st in modell.strukturen:
        for v, m in _vorkommen_lagen(st):
            liste = list(v.ansichten)
            if 0 <= v.teil < len(st.teile):
                liste += st.teile[v.teil].ansichten
            for a in liste:
                k = a.kamera
                eintrag = {"name": a.name, "eid": a.eid, "markups": st.markups_von(a.annotationen),
                           "standard": a.standard, "kamera": None}
                if k is not None:
                    ort = (m[:3, :3] @ k["ort"] + m[:3, 3]) * f
                    ziel = (m[:3, :3] @ k["ziel"] + m[:3, 3]) * f
                    oben = m[:3, :3] @ k["oben"]
                    eintrag["kamera"] = {"ort": ort, "ziel": ziel, "oben": oben, "ortho": k["ortho"],
                                         "breite": abs(k["fx"]) * f, "hoehe": abs(k["fy"]) * f}
                out.append(eintrag)
    return out
