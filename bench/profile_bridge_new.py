"""Zeit/Rundenzahl/Punkte von _bridge_span je Cluster (nach P4-Aenderung; nutzt info-Argument)."""
import time, cadgeom, numpy as np, os
sc = cadgeom.get_scene({})
nz = sc.N[:, 2]; incl = np.degrees(np.arccos(np.clip(-nz, -1, 1)))
crit = (nz < -1e-6) & (sc.C[:, 2] - sc.zmin >= 0.3) & (incl < 44) & (sc.area > 0) & (incl < 5)
sel = np.nonzero(crit)[0]; lab = cadgeom._tri_clusters(sc.F, len(sc.P), sel)
rec = []
for c in np.unique(lab):
    idx = sel[lab == c]
    if sc.area[idx].sum() < 4: continue
    inf = {}; t0 = time.process_time(); t1 = time.time(); r = cadgeom._bridge_span(sc, idx, inf)
    rec.append((time.process_time() - t0, time.time() - t1, float(sc.area[idx].sum()), len(idx), r, inf))
rec.sort(key=lambda x: -x[0])
print("load", os.getloadavg()[0], "Summe CPU %.2fs, Wand %.2fs, Cluster %d" % (sum(x[0] for x in rec), sum(x[1] for x in rec), len(rec)))
for x in rec[:6]:
    print("cpu %.2fs wall %.2fs  %9.0f mm2 %3d Dr  Spannweite %.2f  %s" % x)
