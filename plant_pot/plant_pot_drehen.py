# Gegenprobe zum schnellen Drehweg (drehweg() in plant_pot.py, läuft bei jedem Bau mit): echte Booleans an wenigen
# Winkeln, tiefste Lage ohne Durchdringung. Langsam (Minuten); nur nach Änderungen an Lippe, Nut, Zähnen oder Kurvenbahn.
# Volle Winkelliste: WINKEL = [...] vor dem exec setzen.
BAUGRUPPE = True
NO_REPORT = True
TEST = False
exec(open("/mnt/raid1/3d_print/tools/freecad/plant_pot/plant_pot.py").read())
rm = (CAM_R + CAM_RI) / 2
# nur der Fugenbereich zählt (Dochtkorb ist rund, Drehen ändert an ihm nichts) -> Booleans viel schneller
pot_c = pot.common(slab(SPLIT - 2, SPLIT + POT_FLOOR + 2))
res_c = reservoir.common(slab(SPLIT - 8, SPLIT + 20))
def rest(ang, hi=12.0):
    lo = 0.0
    for _ in range(15):
        mid = (lo + hi) / 2
        p = pot_c.copy(); p.rotate(V(0, 0, 0), V(0, 0, 1), ang); p.translate(V(0, 0, mid))
        if p.common(res_c).Volume > 1e-4: lo = mid
        else: hi = mid
    return hi
print("Lippe: Basis %.2f, Höhe %.2f, oben %.2f; Kurvenring rm %.1f" % (LIP_T, LIP_H, LIP_TOP, rm))
angs = globals().get("WINKEL") or [0, 1, 3, 10, 30, CAM_TURN - 1, CAM_TURN]
prev = None; worst = 0
for a in angs:
    z = rest(a)
    s = ""
    if prev is not None:
        arc = math.radians(a - prev[0]) * rm
        k = (z - prev[1]) / arc
        worst = max(worst, k)
        s = "  Steigung %.2f (45° = 1,00)" % k
    print("  %5.2f° -> %.2f mm (schnell gerechnet %.2f)%s" % (a, z, drehweg(a)[0], s))
    prev = (a, z)
print("steilster Abschnitt: %.2f (über 1 = Topf muss angehoben werden / klemmt)" % worst)
