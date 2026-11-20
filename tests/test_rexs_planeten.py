"""REXS 1.7: Zentralwellen, Planetenwellen und Eingriffe einer Stufe bleiben getrennt."""

import pytest

from programm.kern import rexs, verzahnung as vz
from tests.test_getriebe_betrieb import _planetensatz
from tests.test_getriebezug import _rad


def test_wellen_und_stufenzugehoerigkeit_im_rexs_planetensatz():
    raeder = _planetensatz("P", 18)
    raeder += [_rad("Antrieb", 12, 18., 20.), _rad("Gegenrad", 24, 36., 20.),
               _rad("Fremdrad", 18, 18., y=18.)]
    paare = vz.paare(raeder)
    assert any(raeder[6] is p.b and raeder[2] is p.a for p in paare)
    daten = rexs.modell(raeder, paare)["model"]
    teile = {c["id"]: c for c in daten["components"]}
    relationen = [(r["type"], {ref["role"]: ref["id"] for ref in r["refs"]}) for r in daten["relations"]]
    getriebe, = [i for i, v in teile.items() if v["type"] == "gear_unit"]
    satz, = [i for i, v in teile.items() if v["type"] == "planetary_stage"]
    assert ("assembly", {"assembly": getriebe, "part": satz}) in relationen
    welle = {teile[r["part"]]["name"]: r["assembly"] for typ, r in relationen
             if typ == "assembly" and teile[r["assembly"]]["type"] == "shaft"}
    assert len(set(welle.values())) == len(raeder)
    for rolle, namen in (("central_shaft", ["P Sonne", "P Ring"]), ("planet_shaft", ["P Planet A", "P Planet B"])):
        refs = [r for typ, r in relationen if typ == rolle]
        assert len(refs) == len(namen)
        assert {r["planetary_stage"] for r in refs} == {satz}
        assert {r["shaft"] for r in refs} == {welle[n] for n in namen}
    eingriffe = {r["stage"]: {teile[r["gear_1"]]["name"], teile[r["gear_2"]]["name"]}
                 for typ, r in relationen if typ == "stage"}
    assert len(eingriffe) == 5
    assert not any("Fremdrad" in e for e in eingriffe.values())
    for stufe, paar in eingriffe.items():
        eltern = [r["assembly"] for typ, r in relationen if typ == "assembly" and r["part"] == stufe]
        assert eltern == ([getriebe] if paar == {"Antrieb", "Gegenrad"} else [satz])


@pytest.mark.parametrize("fehler", ["ueberdeckung", "hand"])
def test_unmoeglicher_eingriff_wird_nicht_als_rexs_stufe_exportiert(fehler):
    a, b = _rad("Ritzel", 16, 0.), _rad("Rad", 32, 24.)
    p, = vz.paare([a, b])
    if fehler == "ueberdeckung":
        p.eps_alpha = 0.
    else:
        a.hand = b.hand = "rechts"
        a.beta = b.beta = 15.
    daten = rexs.modell([a, b], [p])["model"]
    assert not any(c["type"] in ("planetary_stage", "cylindrical_stage", "cylindrical_stage_gear_data")
                   for c in daten["components"])
    assert sum(c["type"] == "cylindrical_gear" for c in daten["components"]) == 2
