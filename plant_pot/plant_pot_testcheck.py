# Bajonett-Testpaar wie das Vollmodell prüfen: aufgesetzt, Weg 1..45°, Absetzen mit Restwinkel, seitlich verschieben
NO_REPORT = True
exec(open("/mnt/raid1/3d_print/tools/freecad/plant_pot/plant_pot.py").read())
R, Pt = t_bj_res_asm, t_bj_pot_asm
def rest(ang, hi=12.0, dx=0.0):
    lo = 0.0
    for _ in range(20):
        mid = (lo + hi) / 2
        p = Pt.copy(); p.rotate(V(0, 0, 0), V(0, 0, 1), ang); p.translate(V(dx, 0, mid))
        if p.common(R).Volume > 1e-4: lo = mid
        else: hi = mid
    return hi
print("Testpaar aufgesetzt: Überschneidung %.4f mm3" % Pt.common(R).Volume)
for a in (1, 15, 30, 45): print("  Drehung %4.1f° -> %.2f mm" % (a, rest(a)))
for a in (0.1, 0.15): print("  Absetzen verdreht %.2f° -> %.2f mm" % (a, rest(a)))
p = Pt.copy(); p.translate(V(0.05, 0, 0)); print("  seitlich 0,05 mm -> Überschneidung %.2f mm3 (muss > 0)" % p.common(R).Volume)
