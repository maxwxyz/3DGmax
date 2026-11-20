"""Zwei verbundene Baender je Bolzen im REXS-Modell und der Auslegungsanalyse eines Stufenplanetensatzes."""

from programm.kern import rexs, verzahnung as vz, verzahnung_auslegung as va
from tests.test_getriebezug import _rad


def _stufenraeder():
    # Modul 1: a = (16+20)/2 = (48-12)/2. Axial getrennte Stirnradpaare, zwei gegenueberliegende Bolzen.
    ring = _rad("Hohlrad", 48, 0, 10)
    ring.innen = True
    ring.da, ring.df = ring.d - 2., ring.d + 2.5
    raeder = [_rad("Sonne", 16, 0), ring]
    for n, x in [("A", 18.), ("B", -18.)]:
        links, rechts = _rad(f"P{n}1", 20, x), _rad(f"P{n}2", 12, x, 10)
        links.koerper_id = rechts.koerper_id = object()
        raeder.extend([links, rechts])
    return raeder


def test_rexs_stufenplanet_auf_gemeinsamer_welle():
    raeder = _stufenraeder()
    # Eine geometrisch passende ortsfeste Stirnradpaarung mit dem umlaufenden zweiten Band darf nicht erscheinen.
    raeder.append(_rad("Fremd", 20, 18., 10., y=16.))
    paare = vz.paare(raeder)
    assert any({p.a.teil, p.b.teil} == {"PA2", "Fremd"} for p in paare)
    daten = rexs.modell(raeder, paare)["model"]
    teile = {c["id"]: c for c in daten["components"]}
    refs = [(r["type"], {ref["role"]: ref["id"] for ref in r["refs"]}) for r in daten["relations"]]
    satz, = [i for i, c in teile.items() if c["type"] == "planetary_stage"]
    zentralwellen = [d["shaft"] for typ, d in refs if typ == "central_shaft" and d["planetary_stage"] == satz]
    planetenwellen = [d["shaft"] for typ, d in refs if typ == "planet_shaft" and d["planetary_stage"] == satz]
    assert len(zentralwellen) == len(planetenwellen) == 2 and set(zentralwellen).isdisjoint(planetenwellen)
    teile_auf_wellen = {frozenset(teile[d["part"]]["name"] for typ, d in refs
                                 if typ == "assembly" and d["assembly"] == welle) for welle in planetenwellen}
    assert teile_auf_wellen == {frozenset(["PA1", "PA2"]), frozenset(["PB1", "PB2"])}
    stufen = {d["stage"]: frozenset([teile[d["gear_1"]]["name"], teile[d["gear_2"]]["name"]])
              for typ, d in refs if typ == "stage"}
    eltern = [d["part"] for typ, d in refs if typ == "assembly" and d["assembly"] == satz]
    assert set(eltern) == set(stufen) and len(stufen) == 4
    assert set(stufen.values()) == {frozenset([a, b]) for a, b in [
        ("Sonne", "PA1"), ("Sonne", "PB1"), ("Hohlrad", "PA2"), ("Hohlrad", "PB2")]}


def test_stufenplanet_auslegung_nutzt_beide_zahnzahlen():
    raeder = _stufenraeder()
    befunde = va.getriebe_befunde(raeder, vz.paare(raeder))
    nach_thema = {b.thema: b for b in befunde}
    assert nach_thema["Übersetzung"].wert == "i = 6"
    assert nach_thema["Zähnezahlen"].wert == "16 / 20 / 12 / 48"
    assert nach_thema["Planetenzahl"].wert == "2"
    assert "Phasenlage der Planeten" not in nach_thema and "Montagebedingung" not in " ".join(
        b.einordnung for b in befunde)


def test_stufendaten_nach_rad_geordnet_auch_bei_gleichem_namen():
    # Am groesseren Rad ist die radiale Kopfkuerzung absichtlich groesser; beide Spiele unterscheiden sich.
    gross = _rad("Rad", 32, 0.)
    klein = _rad("Rad", 16, 24.)
    gross.da -= .4
    paar, = vz.paare([gross, klein])
    daten = rexs.modell([gross, klein], [paar])["model"]
    teile = {c["id"]: c for c in daten["components"]}
    wert = {}
    for r in daten["relations"]:
        if r["type"] != "stage_gear_data":
            continue
        refs = {v["role"]: v["id"] for v in r["refs"]}
        z = next(a["integer"] for a in teile[refs["gear"]]["attributes"] if a["id"] == "number_of_teeth")
        wert[z] = next(a["floating_point"] for a in teile[refs["stage_gear_data"]]["attributes"]
                       if a["id"] == "tip_clearance")
    assert wert[32] == round(paar.abstand - gross.df / 2 - klein.da / 2, 6)
    assert wert[16] == round(paar.abstand - klein.df / 2 - gross.da / 2, 6)
