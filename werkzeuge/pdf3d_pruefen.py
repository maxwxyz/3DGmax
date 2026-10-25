"""3D-Inhalte einer PDF auflisten und herausloesen (U3D/PRC), ohne sie auszuwerten.

Aufruf: pixi run python -I werkzeuge/pdf3d_pruefen.py datei.pdf [zielordner]
"""

from __future__ import annotations

import os
import sys

import pypdf


def streams_3d(pfad: str) -> list[tuple[int, str, bytes]]:
    """(Seite, Untertyp U3D/PRC, Rohdaten) je 3D-Annotation."""
    out = []
    for nr, seite in enumerate(pypdf.PdfReader(pfad).pages, 1):
        for a in seite.get("/Annots") or []:
            a = a.get_object()
            if a.get("/Subtype") != "/3D":
                continue
            dd = a["/3DD"].get_object()
            if "/Subtype" not in dd and "/3DD" in dd:  # 3D-Referenzverzeichnis
                dd = dd["/3DD"].get_object()
            out.append((nr, str(dd.get("/Subtype", "?")).lstrip("/"), dd.get_data()))
    return out


def main(argv):
    ziel = argv[2] if len(argv) > 2 else None
    for nr, art, daten in streams_3d(argv[1]):
        kopf = daten[:4]
        print(f"Seite {nr}: {art}, {len(daten)} Byte, Kopf {kopf!r}")
        if ziel:
            os.makedirs(ziel, exist_ok=True)
            with open(os.path.join(ziel, f"seite{nr}.{art.lower()}"), "wb") as f:
                f.write(daten)


if __name__ == "__main__":
    main(sys.argv)
