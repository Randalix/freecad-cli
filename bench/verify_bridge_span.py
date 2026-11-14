"""Genauigkeit von cadgeom._bridge_span an Formen mit bekannter Loesung (Aufruf: cad run bench/verify_bridge_span.py).
Sollwert = 2 x Radius des groessten Inkreises; Toleranz laut Doku: <= max(0,4 mm, 1,33 x L_fin) zu klein, nie mehr als 0,1 mm zu gross."""
import math, time, numpy as np, cadgeom

class S: pass

def scene(P, F):
    sc = S(); sc.P = np.array(P, float); sc.F = np.array(F, int)
    T = sc.P[sc.F]; sc.area = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2
    return sc

def rect(w, h):
    return scene([[0, 0, 5], [w, 0, 5], [w, h, 5], [0, h, 5]], [[0, 2, 1], [0, 3, 2]]), min(w, h)

def lshape(L, w):   # Arme der Laenge L, Breite w
    P = [[0, 0], [L, 0], [L, w], [w, w], [w, L], [0, L]]
    F = [[0, 1, 2], [0, 2, 3], [0, 3, 4], [0, 4, 5]]
    return scene([[x, y, 5] for x, y in P], F), 2 * (math.sqrt(2) * w / (1 + math.sqrt(2)))

def ring(R, r, n=96):
    P = [[R * math.cos(2 * math.pi * i / n), R * math.sin(2 * math.pi * i / n), 5] for i in range(n)] + \
        [[r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), 5] for i in range(n)]
    F = []
    for i in range(n):
        j = (i + 1) % n
        F += [[i, j, n + j], [i, n + j, n + i]]
    # Inkreis des Rings: Mittelpunkt auf Radius (R_eff + r)/2, R_eff = Apothem Aussenpolygon
    ap = R * math.cos(math.pi / n)
    return scene(P, F), (ap - r)

def sliver(w, h):
    return rect(w, h)

cases = [("Rechteck 14 x 30", rect(14, 30)), ("Rechteck 6 x 800 (Splitter)", rect(6, 800)), ("Rechteck 1000 x 520", rect(1000, 520)),
         ("Quadrat 2400 x 2400", rect(2400, 2400)), ("L-Form Arme 400, Breite 40", lshape(400, 40)), ("Ring R 100 / r 40", ring(100, 40)),
         ("Rechteck 4 x 4", rect(4, 4))]
worst_low, worst_high = 0.0, 0.0
for name, (sc, exact) in cases:
    info = {}; t = time.time(); v = cadgeom._bridge_span(sc, np.arange(len(sc.F)), info); dt = time.time() - t
    err = v - exact
    worst_low = min(worst_low, err); worst_high = max(worst_high, err)
    print("%-30s soll %8.2f  ist %8.2f  Abw. %+6.2f mm (%+.2f %%)  %.3fs  L_fin %.2f Runden %d" % (name, exact, v, err, 100 * err / exact, dt, info["final_L"], info["rounds"]))
ok = worst_high <= 0.1 and worst_low >= -1.5
print("groesste Unterschaetzung %.2f mm, groesste Ueberschaetzung %.2f mm -> %s" % (-worst_low, worst_high, "OK" if ok else "ZU UNGENAU"))
