#!/usr/bin/env python3
"""Sichtbare Facetten in STL-Dateien finden (Joe 15.11.2026: Facetten an den Rundungen des ersten Square-Pot-Drucks).

Eine zu grob vernetzte Rundung besteht aus langen, flachen Streifen. Zwischen zwei Nachbarfacetten liegt dann ein
Knick von einigen Grad. Gezählt werden Knickkanten mit KNICK_MIN..KNICK_MAX Grad und mindestens MIN_LEN mm Länge.
Echte Kanten (Fasen 45°, Ecken 90°) liegen außerhalb des Bands, kurze Knicke (polygonale Kurvenbahnen) unter MIN_LEN.

Referenz: Square Pot 100er, Topf mit LinearDeflection 0,05 / AngularDeflection 0,2 -> 13-14 m (sichtbar gedruckt);
mit 0,005 / 0,05 -> 0 mm.

Nutzung:
  python3 stl_facetten.py teil.stl [weitere.stl] [--max 100]     (Exit 1, wenn eine Datei über --max mm liegt)
  im FreeCAD-Skript: from stl_facetten import knickkanten; mm, n, amax = knickkanten(punkte, dreiecke)
Ohne numpy (läuft mit jedem Python 3).
"""
import math, struct, sys

KNICK_MIN, KNICK_MAX, MIN_LEN = 2.5, 15.0, 3.0


def knickkanten(pts, tris, lo=KNICK_MIN, hi=KNICK_MAX, min_len=MIN_LEN):
    """pts: Liste (x, y, z); tris: Liste (i, j, k). Rückgabe (Länge mm, Anzahl, größter Knick °) der Facettenkanten."""
    normals = []
    for i, j, k in tris:
        a, b, c = pts[i], pts[j], pts[k]
        u = (b[0] - a[0], b[1] - a[1], b[2] - a[2]); v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        l = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1e-30
        normals.append((n[0] / l, n[1] / l, n[2] / l))
    edges = {}
    for f, (i, j, k) in enumerate(tris):
        for e in ((i, j), (j, k), (k, i)):
            edges.setdefault((min(e), max(e)), []).append(f)
    total, count, amax = 0.0, 0, 0.0
    for (i, j), fs in edges.items():
        if len(fs) != 2:
            continue
        n1, n2 = normals[fs[0]], normals[fs[1]]
        d = max(-1.0, min(1.0, n1[0] * n2[0] + n1[1] * n2[1] + n1[2] * n2[2]))
        ang = math.degrees(math.acos(d))
        if lo < ang < hi:
            p, q = pts[i], pts[j]
            L = math.sqrt((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2)
            if L >= min_len:
                total += L; count += 1; amax = max(amax, ang)
    return total, count, amax


def lade_stl(fn):
    """Binär- oder ASCII-STL -> (Punkte, Dreiecke) mit zusammengeführten Eckpunkten."""
    data = open(fn, "rb").read()
    verts = []
    n = struct.unpack("<I", data[80:84])[0] if len(data) >= 84 else 0
    if len(data) == 84 + 50 * n:
        for t in range(n):
            o = 84 + 50 * t + 12
            v = struct.unpack("<9f", data[o:o + 36])
            verts += [v[0:3], v[3:6], v[6:9]]
    else:
        for line in data.decode("ascii", "replace").splitlines():
            s = line.split()
            if len(s) == 4 and s[0] == "vertex":
                verts.append(tuple(float(x) for x in s[1:]))
    index, pts, flat = {}, [], []
    for v in verts:
        key = (round(v[0], 5), round(v[1], 5), round(v[2], 5))
        if key not in index:
            index[key] = len(pts); pts.append(key)
        flat.append(index[key])
    return pts, [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("stl", nargs="+")
    ap.add_argument("--max", type=float, default=100.0, help="Grenze mm Knickkanten je Datei (Standard 100)")
    a = ap.parse_args(argv)
    bad = 0
    for fn in a.stl:
        mm, n, amax = knickkanten(*lade_stl(fn))
        ok = mm <= a.max
        bad += not ok
        print("%-4s %s: %.0f mm sichtbare Facettenkanten (%d Kanten, größter Knick %.1f°)" % ("ok" if ok else "ZU GROB", fn, mm, n, amax))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
