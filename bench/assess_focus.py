"""Verdeckungs-Auswertung je cad.focus-Kachel (nach `cad run <skript>` des Couch-Modells): cad run bench/assess_focus.py"""
import time, cadgeom
sc = cadgeom.get_scene({})
P = cadgeom.VIS_PRESETS
for f in sc.focus:
    v = f["view"]; az, el = (P[v] if isinstance(v, str) else v)
    t = time.time()
    r = cadgeom.assess_focus(sc, {"name": f["name"], "center": f["center"], "size": f["size"], "dir": [az, el]})
    print("%-26s %-6s Ziele %s | verdeckt %s | flach %.2f | problem %s | Alternative %s | %.2fs" % (
        f["name"], v, r.get("targets"), r.get("hidden"), r.get("flat", -1), r.get("problem"), r.get("alternative"), time.time() - t))
