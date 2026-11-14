#!/usr/bin/env python3
"""Selbsttest des Renderers: Silhouette im Bild (Bildkoordinaten -> Modell-mm) gegen die bekannte BBox der STL.
  python3 cad_selftest.py [stl ...]   Abweichung muss < 1 mm sein (Phase R, Lineal-Koordinaten). Ohne DISPLAY ausfuehren."""
import os, struct, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cad_render as cr

DEF = ["/mnt/raid1/3d_print/kotbeutel_bin/gridfinity_bin.stl", "/mnt/raid1/3d_print/tuecher_bin/gridfinity_tuecher.stl",
       "/mnt/raid1/3d_print/kotbeutel_bin/gridfinity_nase_serie.stl", "/mnt/raid1/3d_print/tempo_bin/gridfinity_tempo.stl"]
AX = {"front": ((0, 1), (2, 1)), "right": ((1, 1), (2, 1)), "top": ((0, 1), (1, 1))}  # (Achse, Vorzeichen) waagerecht/senkrecht

def bbox(p):
    b = open(p, "rb").read()
    if b[:5] == b"solid" and b"facet" in b[:400]:
        import re
        v = [tuple(map(float, m)) for m in re.findall(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", b)]
    else:
        n = struct.unpack("<I", b[80:84])[0]; v = []
        for i in range(n):
            o = 84 + i * 50 + 12; f = struct.unpack("<9f", b[o:o + 36]); v += [f[0:3], f[3:6], f[6:9]]
    return [min(p[i] for p in v) for i in range(3)], [max(p[i] for p in v) for i in range(3)]

worst = 0.0
for stl in (sys.argv[1:] or DEF):
    lo, hi = bbox(stl)
    for view, ((ha, hs), (va, vs)) in AX.items():
        job = {"models": [{"path": stl}], "out": "/tmp/claude-1000/cad_selftest.png", "views": [cr.view_from_args(view, px=700)], "ruler": False}
        res = cr.run_job(job)
        if not res["ok"]:
            print("FEHLER", stl, view, res.get("error")); sys.exit(3)
        v = res["views"][0]; s = v["silhouette"]
        err = max(abs(s[0] - lo[ha]), abs(s[1] - hi[ha]), abs(s[2] - lo[va]), abs(s[3] - hi[va]))
        worst = max(worst, err)
        print("%-28s %-6s Silhouette h %.2f..%.2f (BBox %.2f..%.2f)  v %.2f..%.2f (BBox %.2f..%.2f)  max.Abw. %.2f mm  %.1fs" % (
            os.path.basename(stl), view, s[0], s[1], lo[ha], hi[ha], s[2], s[3], lo[va], hi[va], err, res["seconds"]))
print("WORST %.3f mm -> %s" % (worst, "OK" if worst < 1.0 else "ZU GROSS"))
sys.exit(0 if worst < 1.0 else 1)
