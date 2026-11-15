# Absetzen: Topf mit kleinem Restwinkel (Zahn-Kerben-Spiel) senkrecht absenken -> findet die Lippe in die Nut?
BAUGRUPPE = True
NO_REPORT = True
TEST = False
exec(open("/mnt/raid1/3d_print/tools/freecad/plant_pot/plant_pot.py").read())
rm = (CAM_R + CAM_RI) / 2
a_n = math.degrees((TOOTH_W / 2 + CAM_NOTCH_CL) / rm); a_t = math.degrees((TOOTH_W / 2) / rm)
print("Kerbenspiel Zahn: +-%.2f° (Zahn %.2f°, Kerbe %.2f°)" % (a_n - a_t, a_t, a_n))
def rest(ang, hi=8.0):
    lo = 0.0
    for _ in range(20):
        mid = (lo + hi) / 2
        p = pot_collide.copy(); p.rotate(V(0, 0, 0), V(0, 0, 1), ang); p.translate(V(0, 0, mid))
        if p.common(reservoir).Volume > 1e-4: lo = mid
        else: hi = mid
    return hi
for a in (0.0, 0.05, 0.1, a_n - a_t, 0.2):
    print("  verdreht %.2f° -> liegt %.2f mm über aufgesetzt" % (a, rest(a)))
