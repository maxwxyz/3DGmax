"""QIF-Messergebnisse lesen, den Merkmalen zuordnen und bewerten."""

from tests.conftest import pfad


def _ergebnisse(werte: list[tuple[str, str, float]]) -> str:
    """Kleine QIF-Ergebnisdatei wie das Community-Beispiel: (Kennung, Messart, Wert) je Messung."""
    items, messungen = [], []
    for i, (kennung, art, wert) in enumerate(werte):
        items.append(f'<{art}CharacteristicItem id="{100 + i}"><Name>{kennung}</Name><CharacteristicDesignator>'
                     f'<Designator>{kennung}</Designator></CharacteristicDesignator>'
                     f'<CharacteristicNominalId>{900 + i}</CharacteristicNominalId></{art}CharacteristicItem>')
        messungen.append(f'<{art}CharacteristicMeasurement id="{200 + i}"><Status><CharacteristicStatusEnum>PASS'
                         f'</CharacteristicStatusEnum></Status><CharacteristicItemId>{100 + i}</CharacteristicItemId>'
                         f'<Value>{wert}</Value></{art}CharacteristicMeasurement>')
    return ('<?xml version="1.0" encoding="UTF-8"?><QIFDocument xmlns="http://qifstandards.org/xsd/qif3" '
            'versionQIF="3.0.0"><Characteristics><CharacteristicItems>' + "".join(items) +
            '</CharacteristicItems></Characteristics><Results><MeasurementResultsSet><MeasurementResults id="1">'
            '<InspectionStatus><InspectionStatusEnum>FAIL</InspectionStatusEnum></InspectionStatus>'
            '<MeasuredCharacteristics><CharacteristicMeasurements>' + "".join(messungen) +
            '</CharacteristicMeasurements></MeasuredCharacteristics></MeasurementResults></MeasurementResultsSet>'
            '</Results></QIFDocument>')


def test_community_beispiel():
    from programm.kern import qif_ergebnisse as qe
    werte, angaben = qe.lies(pfad("qif/QIF_Results_Sample.QIF"))
    assert len(werte) == 13 and angaben["status"] == "FAIL"
    durchmesser = [w for w in werte if w.art == "Diameter" and w.kennung == "6"]
    assert durchmesser[0].wert == 9.499476 and durchmesser[0].status == "FAIL"
    assert sum(1 for w in werte if w.kennung == "5") == 2  # Profil an zwei Punkten


def test_zuordnen_und_bewerten(tmp_path):
    from programm.kern import merkmale, qif_ergebnisse as qe
    from programm.ui.lader import lade_alles
    liste = merkmale.liste(lade_alles(pfad("nist_ctc_01_asme1_ap242-e1.stp")).pmi)
    mass = next(m for m in liste if m.pmi.art == "mass" and None not in m.grenzen())
    tol = next(m for m in liste if m.pmi.art == "toleranz" and m.pmi.wert)
    oben, unten = mass.grenzen()
    datei = tmp_path / "e.qif"
    datei.write_text(_ergebnisse([(str(mass.ballon), "Diameter", (oben + unten) / 2),
                                  (str(tol.ballon), "PointProfile", tol.pmi.wert * 0.4),
                                  (str(tol.ballon), "PointProfile", -tol.pmi.wert * 0.6),
                                  ("999", "Diameter", 1.0)]), encoding="utf-8")
    werte, _ = qe.lies(str(datei))
    je = qe.zuordnen(werte, liste)
    assert set(je) == {mass.ballon, tol.ballon} and len(je[tol.ballon]) == 2
    w, urteil = qe.massgebend(mass, je[mass.ballon])
    assert urteil == qe.GUT
    w, urteil = qe.massgebend(tol, je[tol.ballon])  # -0,6 t ausserhalb von +-t/2
    assert urteil == qe.SCHLECHT and w.wert < 0
    messung = {m.ballon: qe.massgebend(m, je[m.ballon]) for m in liste if m.ballon in je}
    zeilen = merkmale.zeilen(liste, None, messung)
    z = next(z for z in zeilen if z[0] == str(tol.ballon))
    assert z[10] and z[11] in ("nein", "no")


def test_messergebnisse_im_fenster(fenster_ctc01, tmp_path):
    from programm.kern import merkmale
    f = fenster_ctc01
    liste = merkmale.liste(f.erg.pmi)
    m = next(x for x in liste if x.pmi.art == "mass" and None not in x.grenzen())
    datei = tmp_path / "e.qif"
    datei.write_text(_ergebnisse([(str(m.ballon), "Diameter", m.grenzen()[0] + 1.0)]), encoding="utf-8")
    d = f.lies_messergebnisse(str(datei))
    assert d.tabelle.rowCount() == 1 and d.tabelle.item(0, 7).text() in ("n. i. O.", "not OK")
    d.tabelle.selectRow(0)
    csv = open(f.exportiere_merkmale(str(tmp_path / "m.csv")), encoding="utf-8-sig").read()
    assert f"{m.grenzen()[0] + 1.0:.4f}".rstrip("0").rstrip(".").replace(".", ",") in csv
    d.close()


def test_qif_ohne_geometrie_klare_meldung():
    import pytest
    from programm.kern.laden import LadeFehler
    from programm.ui.lader import lade_alles
    with pytest.raises(LadeFehler, match="Messergebnisse"):
        lade_alles(pfad("qif/QIF_Results_Sample.QIF"))
