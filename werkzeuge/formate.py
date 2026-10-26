"""Testdateien in weiteren Formaten aus der Test-Baugruppe erzeugen (IGES, STL, OBJ, glTF, GLB, 3MF).

Aufruf: pixi run python werkzeuge/formate.py   -> tests/daten/formate/
"""

from __future__ import annotations

import os
import sys
import zipfile

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
ZIEL = os.path.join(WURZEL, "tests", "daten", "formate")
QUELLE = os.path.join(WURZEL, "tests", "daten", "baugruppe.stp")


def _netz(form, feinheit=0.2):
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    BRepMesh_IncrementalMesh(form, feinheit, False, 0.3, True)


def erzeuge():
    from OCC.Core.IGESCAFControl import IGESCAFControl_Writer
    from OCC.Core.Message import Message_ProgressRange
    from OCC.Core.RWGltf import RWGltf_CafWriter
    from OCC.Core.RWObj import RWObj_CafWriter
    from OCC.Core.StlAPI import StlAPI_Writer
    from OCC.Core.TCollection import TCollection_AsciiString
    from OCC.Core.TColStd import TColStd_IndexedDataMapOfStringString
    from programm.kern.laden import lade_step
    os.makedirs(ZIEL, exist_ok=True)
    m = lade_step(QUELLE)
    _netz(m.form)
    w = IGESCAFControl_Writer()
    w.SetColorMode(True)
    w.SetNameMode(True)
    w.Transfer(m.doc)
    w.Write(os.path.join(ZIEL, "baugruppe.igs"))
    StlAPI_Writer().Write(m.form, os.path.join(ZIEL, "baugruppe.stl"))
    info = TColStd_IndexedDataMapOfStringString()
    obj = RWObj_CafWriter(TCollection_AsciiString(os.path.join(ZIEL, "baugruppe.obj")))
    obj.ChangeCoordinateSystemConverter().SetInputLengthUnit(0.001)
    obj.ChangeCoordinateSystemConverter().SetOutputLengthUnit(0.001)
    obj.Perform(m.doc, info, Message_ProgressRange())
    for name, binaer in (("baugruppe.gltf", False), ("baugruppe.glb", True)):
        g = RWGltf_CafWriter(TCollection_AsciiString(os.path.join(ZIEL, name)), binaer)
        g.ChangeCoordinateSystemConverter().SetInputLengthUnit(0.001)  # mm -> m (glTF)
        g.Perform(m.doc, info, Message_ProgressRange())
    _schreibe_3mf(m, os.path.join(ZIEL, "baugruppe.3mf"))
    return sorted(os.listdir(ZIEL))


def _schreibe_3mf(m, pfad):
    """Einfaches 3MF: ein Objekt je Teil (Netz in Modellkoordinaten), Einheit mm."""
    from programm.kern.ausrichten import tesselliere
    from programm.kern.baum import lies_baum
    teile = [k for k in lies_baum(m).blaetter() if not k.hilfsgeometrie]
    objekte, items = [], []
    for i, k in enumerate(teile, 1):
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Core.TopExp import TopExp_Explorer
        flaechen = []
        ex = TopExp_Explorer(k.form, TopAbs_FACE)
        while ex.More():
            flaechen.append(ex.Current())
            ex.Next()
        verts, tris, off = [], [], 0
        for pts, tri in tesselliere(flaechen, 0.2):
            verts += [f'<vertex x="{p[0]:.5f}" y="{p[1]:.5f}" z="{p[2]:.5f}"/>' for p in pts]
            tris += [f'<triangle v1="{a + off}" v2="{b + off}" v3="{c + off}"/>' for a, b, c in tri]
            off += len(pts)
        objekte.append(f'<object id="{i}" name="{k.name}" type="model"><mesh><vertices>{"".join(verts)}</vertices>'
                       f'<triangles>{"".join(tris)}</triangles></mesh></object>')
        items.append(f'<item objectid="{i}"/>')
    modell = ('<?xml version="1.0" encoding="UTF-8"?><model unit="millimeter" xml:lang="en-US" '
              'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
              f'<resources>{"".join(objekte)}</resources><build>{"".join(items)}</build></model>')
    typen = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/'
             'content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
             'relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-'
             '3dmodel+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/'
            '2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.'
            'com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(pfad, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", typen)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", modell)


if __name__ == "__main__":
    print(erzeuge())
