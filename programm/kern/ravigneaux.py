"""Ravigneaux-Satz mit drei Zentralraedern und zwei ineinandergreifenden Planetenfamilien."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..i18n import tr


@dataclass
class Ravigneaux:
    sonne_lang: int
    sonne_kurz: int
    hohlrad: int
    langplaneten: list[int]
    kurzplaneten: list[int]
    z_sonne_lang: int
    z_sonne_kurz: int
    z_hohlrad: int
    z_langplanet: int
    z_kurzplanet: int
    gekoppelte_zentralraeder: list[list[int]] = field(default_factory=list)

    @property
    def umlaufraeder(self):
        return [*self.langplaneten, *self.kurzplaneten]

    @property
    def zentralraeder(self):
        return [self.sonne_lang, self.sonne_kurz, self.hohlrad]

    def titel(self, n):
        return tr("Ravigneaux-Satz {}").format(n)

    @property
    def teile(self):
        return {self.sonne_lang, self.sonne_kurz, self.hohlrad, *self.umlaufraeder}

    @property
    def eingriffe(self):
        return [paar for lang, kurz in zip(self.langplaneten, self.kurzplaneten)
                for paar in ((self.sonne_lang, lang), (self.hohlrad, lang), (lang, kurz), (self.sonne_kurz, kurz))]

    @property
    def koeffizienten(self):
        """Vier Wellen, zwei unabhaengige Gleichungen im gleichen positiven Achssinn."""
        a, b, r = self.z_sonne_lang, self.z_sonne_kurz, self.z_hohlrad
        return ((a, 0, r, -(a + r)), (0, b, -r, r - b))

    def als_dict(self):
        return {"art": "ravigneaux", "sonne_lang": self.sonne_lang, "sonne_kurz": self.sonne_kurz,
                "hohlrad": self.hohlrad, "langplaneten": self.langplaneten, "kurzplaneten": self.kurzplaneten,
                "umlaufraeder": self.umlaufraeder, "eingriffe": self.eingriffe,
                "z_sonne_lang": self.z_sonne_lang, "z_sonne_kurz": self.z_sonne_kurz, "z_hohlrad": self.z_hohlrad,
                "z_langplanet": self.z_langplanet, "z_kurzplanet": self.z_kurzplanet,
                "rollen": ["sonne_lang", "sonne_kurz", "hohlrad", "steg"], "koeffizienten": self.koeffizienten,
                "drehfest_verbundene_zentralraeder": self.gekoppelte_zentralraeder,
                "anzahl_stege": 1, "montierbarkeit": "unbestimmt"}

    def zeilen(self, raeder):
        def name(i):
            return f"{raeder[i].teil} (z = {raeder[i].z})"
        a, b, r = self.z_sonne_lang, self.z_sonne_kurz, self.z_hohlrad
        zeilen = [(tr("Sonne am Langplaneten"), name(self.sonne_lang)),
                (tr("Sonne am Kurzplaneten"), name(self.sonne_kurz)), (tr("Hohlrad"), name(self.hohlrad)),
                (tr("Langplanet / Kurzplanet"), ", ".join(f"{name(lang)} / {name(kurz)}"
                                                         for lang, kurz in zip(self.langplaneten, self.kurzplaneten))),
                (tr("Langplanetenzweig"), f"{a} (nSL − nC) + {r} (nR − nC) = 0"),
                (tr("Kurzplanetenzweig"), f"{b} (nSK − nC) − {r} (nR − nC) = 0"),
                (tr("Drehzahlrollen"), tr("nSL, nSK: Sonnen, nR: Hohlrad, nC: gemeinsamer Steg")),
                (tr("Betriebsbedingung"), tr("Gemeinsamer Steg und gleichzeitiger Eingriff aller vier Paarungen vorausgesetzt."))]
        if self.gekoppelte_zentralraeder:
            teile = ", ".join(" + ".join(raeder[i].teil for i in g) for g in self.gekoppelte_zentralraeder)
            zeilen.append((tr("Drehfest verbundene Zentralräder"), teile))
        return zeilen


def erkenne(raeder, nachbarn, einfach):
    """Eindeutige Paare an verschiedenen Bolzen. Alle vier Eingriffe stammen aus der Paaranalyse."""
    from .verzahnung_daten import _gleiche_achse, _koerperkennung, _nur_satzkontakte
    out = []
    for grund in einfach:
        if grund.gestuft or len({raeder[i].z for i in grund.planeten}) != 1:
            continue
        lang_ids = set(grund.planeten)
        s, r = grund.sonne, grund.hohlrad
        varianten = []
        for sk, rad in enumerate(raeder):
            sl = raeder[s]
            if rad.innen or not 0 < rad.d < sl.d or not _gleiche_achse(raeder[r], rad):
                continue
            # Zwei axial getrennte Sonnen; der Langplanet greift an der groesseren Sonne und am Ring ein.
            abstand = abs((rad.punkt - sl.punkt) @ sl.richtung)
            if (sl.b + rad.b * abs(sl.richtung @ rad.richtung)) / 2 - abstand > 1e-5 * max(sl.b, rad.b):
                continue
            kurz = nachbarn.get(sk, set())
            if kurz & lang_ids:
                continue
            kurz_ids = []
            for lang in grund.planeten:
                kandidaten = (nachbarn[lang] & kurz) - {s, r, sk}
                if len(kandidaten) != 1:
                    break
                k = next(iter(kandidaten))
                if (raeder[k].innen or k in nachbarn[r] or k in nachbarn[s] or
                        any(_gleiche_achse(raeder[k], raeder[i]) for i in (*lang_ids, *kurz_ids))):
                    break
                kurz_ids.append(k)
            if len(kurz_ids) != len(grund.planeten) or len({raeder[i].z for i in kurz_ids}) != 1:
                continue
            satz = Ravigneaux(s, sk, r, grund.planeten, kurz_ids, raeder[s].z, rad.z, raeder[r].z,
                              grund.z_planet, raeder[kurz_ids[0]].z)
            if _nur_satzkontakte(satz, nachbarn):
                gruppen = {}
                for i in satz.zentralraeder:
                    gruppen.setdefault(_koerperkennung(raeder[i], i), []).append(i)
                planetenkoerper = {_koerperkennung(raeder[i], i) for i in satz.umlaufraeder}
                if len(planetenkoerper) != len(satz.umlaufraeder) or not planetenkoerper.isdisjoint(gruppen):
                    continue
                satz.gekoppelte_zentralraeder = [g for g in gruppen.values() if len(g) > 1]
                varianten.append(satz)
        if len(varianten) == 1:
            out.extend(varianten)
    # Alternative grosse Sonnen bzw. Ringe am selben Planetenpaar ergeben keine eindeutige Vierwellenzuordnung.
    kontakte = [{frozenset(paar) for paar in s.eingriffe} for s in out]
    return [s for i, s in enumerate(out) if all(i == j or k.isdisjoint(kontakte[i]) for j, k in enumerate(kontakte))]
