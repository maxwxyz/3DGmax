"""Logo packaging/logo.svg erzeugen: Wuerfel (3D-Modell) mit oranger Flaeche (PMI) und einem Masspfeil parallel zur
unteren Vorderkante - bewusst ohne Kleinteile, Wuerfel und Pfeil als Gruppe mittig im Keyline-Quadrat.

Aufruf: pixi run python werkzeuge/logo.py && pixi run python packaging/make_icon.py
"""

from __future__ import annotations

import math
import os

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYLINE = 320  # Inhalt in px (Kachel 480 px, je 80 px Rand)
ABSTAND, HALB, SPITZE, BREITE = 54, 60, 38, 30  # Pfeil: Abstand zur Kante, halbe Schaftlaenge, Spitze, Spitzenbreite
WUERFEL = [(256, 104), (392, 183), (392, 339), (256, 418), (120, 339), (120, 183)]


def svg() -> str:
    a, b = (256, 418), (392, 339)  # untere Vorderkante der orangen Flaeche
    lang = math.dist(a, b)
    d = ((b[0] - a[0]) / lang, (b[1] - a[1]) / lang)
    n = (-d[1], d[0]) if d[0] > 0 else (d[1], -d[0])  # Normale nach unten rechts
    if n[1] < 0:
        n = (-n[0], -n[1])
    m = ((a[0] + b[0]) / 2 + n[0] * ABSTAND, (a[1] + b[1]) / 2 + n[1] * ABSTAND)

    def pt(s, q=0.0):
        return m[0] + d[0] * s + n[0] * q, m[1] + d[1] * s + n[1] * q
    l0, l1 = pt(-HALB), pt(HALB)
    k1 = [pt(-(HALB + SPITZE)), pt(-HALB, BREITE), pt(-HALB, -BREITE)]
    k2 = [pt(HALB + SPITZE), pt(HALB, BREITE), pt(HALB, -BREITE)]
    pts, r = WUERFEL + k1 + k2, 8
    x0, x1 = min(x for x, _ in pts) - r, max(x for x, _ in pts) + r
    y0, y1 = min(y for _, y in pts) - r, max(y for _, y in pts) + r
    k = KEYLINE / max(x1 - x0, y1 - y0)
    tx, ty = 256 - k * (x0 + x1) / 2, 256 - k * (y0 + y1) / 2

    def p(q):
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in q)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <!-- 3DGmax: erzeugt von werkzeuge/logo.py (Wuerfel, orange PMI-Flaeche, Masspfeil; mittig im Keyline-Quadrat) -->
  <defs>
    <linearGradient id="hg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#2f6fe4"/>
      <stop offset="1" stop-color="#1b43a0"/>
    </linearGradient>
  </defs>
  <rect x="16" y="16" width="480" height="480" rx="108" fill="url(#hg)"/>
  <g transform="translate({tx:.2f} {ty:.2f}) scale({k:.4f})">
    <polygon points="256,104 392,183 256,262 120,183" fill="#f2f6ff"/>
    <polygon points="120,183 256,262 256,418 120,339" fill="#a9c0f2"/>
    <polygon points="256,262 392,183 392,339 256,418" fill="#ff8a1f"/>
    <path d="M256 104 L392 183 L392 339 L256 418 L120 339 L120 183 Z M120 183 L256 262 L392 183 M256 262 L256 418"
          fill="none" stroke="#0e2a6b" stroke-width="14" stroke-linejoin="round" stroke-linecap="round"/>
    <g fill="#ffffff" stroke="#ffffff" stroke-linecap="round" stroke-linejoin="round">
      <line x1="{l0[0]:.1f}" y1="{l0[1]:.1f}" x2="{l1[0]:.1f}" y2="{l1[1]:.1f}" stroke-width="18"/>
      <polygon points="{p(k1)}" stroke-width="8"/>
      <polygon points="{p(k2)}" stroke-width="8"/>
    </g>
  </g>
</svg>
'''


if __name__ == "__main__":
    ziel = os.path.join(WURZEL, "packaging", "logo.svg")
    with open(ziel, "w", encoding="utf-8") as f:
        f.write(svg())
    print(ziel)
