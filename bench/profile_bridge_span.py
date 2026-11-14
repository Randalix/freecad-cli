import time, cadgeom
sc = cadgeom.get_scene({})
orig = cadgeom._bridge_span
rec = []
def w(sc_, idx):
    t = time.time(); r = orig(sc_, idx); rec.append((time.time() - t, float(sc_.area[idx].sum()), len(idx), r)); return r
cadgeom._bridge_span = w
t = time.time(); hs = cadgeom.find_overhangs(sc); tot = time.time() - t
cadgeom._bridge_span = orig
rec.sort(reverse=True)
print("find_overhangs gesamt %.1fs, Brueckencluster %d, Zeit in _bridge_span %.1fs" % (tot, len(rec), sum(r[0] for r in rec)))
for r in rec[:5]:
    print("  %.2fs  Flaeche %9.0f mm2  %4d Dreiecke  Spannweite %.1f" % r)
small = [r for r in rec if r[1] < 20000]
print("kleine Cluster (<20000 mm2): %d, zusammen %.2fs" % (len(small), sum(r[0] for r in small)))
