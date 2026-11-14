import time, cadgeom, collections
sc = cadgeom.get_scene({})
out = []
for name in ["find_open_edges", "find_thin_walls", "find_overhangs", "find_gaps", "find_focus"]:
    t = time.time(); r = getattr(cadgeom, name)(sc); dt = time.time() - t
    kinds = collections.Counter(h["kind"] for h in r)
    out.append("%-18s %6.2fs  %3d Treffer  %s" % (name, dt, len(r), dict(kinds)))
print("Teile:", sc.ncomp, "Dreiecke:", sc.m)
print("\n".join(out))
