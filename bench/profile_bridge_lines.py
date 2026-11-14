"""Zeit je Zeile in _bridge_span fuer den groessten Brueckencluster (Messskript, `cad run`)."""
import time, math, numpy as np, cadgeom
from scipy.spatial import cKDTree
sc = cadgeom.get_scene({})
nz = sc.N[:, 2]; zc = sc.C[:, 2]
incl = np.degrees(np.arccos(np.clip(-nz, -1, 1)))
crit = (nz < -1e-6) & (zc - sc.zmin >= 0.3) & (incl < 44) & (sc.area > 0) & (incl < 5)
sel = np.nonzero(crit)[0]
lab = cadgeom._tri_clusters(sc.F, len(sc.P), sel)
best = max((sel[lab == c] for c in np.unique(lab)), key=lambda i: sc.area[i].sum())
F = sc.F[best]; T = {}
t = time.time()
e = np.sort(np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]], axis=1); u, cnt = np.unique(e, axis=0, return_counts=True); bd = u[cnt == 1]
T["rand"] = time.time() - t; t = time.time()
area = float(sc.area[best].sum()); sp = max(0.5, math.sqrt(area / 150000.0))
pts, _ = cadgeom._sample_surface(sc.P, F, sp); T["sample"] = time.time() - t; t = time.time()
a, b = sc.P[bd[:, 0]], sc.P[bd[:, 1]]; ln = np.linalg.norm(b - a, axis=1); k = np.maximum(1, np.ceil(ln / (sp / 2)).astype(np.int64))
bpts = np.vstack([a[i] + (b[i] - a[i]) * (np.arange(k[i] + 1) / k[i])[:, None] for i in range(len(bd))]) if len(bd) < 4000 else np.vstack([a, b, (a + b) / 2])
T["randpunkte"] = time.time() - t; t = time.time()
tree = cKDTree(bpts); T["kdbau"] = time.time() - t; t = time.time()
d = tree.query(pts)[0]; T["query"] = time.time() - t
print("Cluster: %d Dreiecke, %.0f mm2, Randkanten %d, Punkte %d, Randpunkte %d, sp %.2f, Spannweite %.2f" % (len(best), area, len(bd), len(pts), len(bpts), sp, 2 * d.max()))
print("  ".join("%s %.2fs" % kv for kv in T.items()))
