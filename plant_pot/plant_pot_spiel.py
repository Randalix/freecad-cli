# Seitliches Spiel prüfen: aufgesetzten Topf (Flachseiten auf der Fuge) waagerecht verschieben -> stößt er an?
BAUGRUPPE = True
NO_REPORT = True
TEST = False
exec(open("/mnt/raid1/3d_print/tools/freecad/plant_pot/plant_pot.py").read())
import math
for d in (0.02, 0.05, 0.1, 0.25):
    for ang in (0, 45, 90):
        p = pot_collide.copy(); p.translate(V(d * math.cos(math.radians(ang)), d * math.sin(math.radians(ang)), 0))
        v = p.common(reservoir).Volume
        # wie weit müsste er hochsteigen, damit es frei ist?
        lo, hi = 0.0, 1.0
        for _ in range(20):
            mid = (lo + hi) / 2
            q = p.copy(); q.translate(V(0, 0, mid))
            if q.common(reservoir).Volume > 1e-4: lo = mid
            else: hi = mid
        print("Versatz %.2f mm Richtung %3d°: Überschneidung %.2f mm3 -> müsste %.3f mm angehoben werden" % (d, ang, v, hi))
