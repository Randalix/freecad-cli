# Gießstellung: Topf gerade aus der Nut heben, um GIESS_WINKEL drehen; Auflagehöhe je Drehwinkel (Weg) und Rast-Lage.
# Für jeden Winkel: tiefste Lage ohne Durchdringung (Bisektion). Kontaktstellen und Gießöffnung in der Endlage.
BAUGRUPPE = True
NO_REPORT = True
TEST = False
exec(open("/mnt/raid1/3d_print/tools/freecad/plant_pot/plant_pot.py").read())
ang_end = globals().get("GIESS_WINKEL", CAM_TURN if LIFT else 45.0)
def placed(ang, dz):
    p = pot_collide.copy(); p.rotate(V(0, 0, 0), V(0, 0, 1), ang); p.translate(V(0, 0, dz)); return p
def rest(ang, hi=15.0):
    lo = 0.0
    for _ in range(22):
        mid = (lo + hi) / 2
        if placed(ang, mid).common(reservoir).Volume > 1e-4: lo = mid
        else: hi = mid
    return hi
print("Aufgesetzt: Überschneidung Topf/Reservoir %.4f mm3" % pot.common(reservoir).Volume)
print("Weg (Drehwinkel -> Auflagehöhe über aufgesetzt):")
for a in [1, 5, 15, 30, 43, ang_end]:
    print("  %5.1f° -> %.2f mm" % (a, rest(a)))
dz = rest(ang_end)
pg = placed(ang_end, dz)
p2 = pg.copy(); p2.translate(V(0, 0, -0.05))
contact = reservoir.common(p2)
print("Gießstellung %g°: Topf liegt %.2f mm über der Einbaulage auf" % (ang_end, dz))
print("Auflage: %d Kontaktstellen" % len(contact.Solids))
for s_ in contact.Solids:
    c = s_.BoundBox.Center; print("  Kontakt bei (%.1f, %.1f, %.2f), r = %.1f" % (c.x, c.y, c.z, math.hypot(c.x, c.y)))
outline = Part.Face(rr(0, 0)); outline.rotate(V(0, 0, 0), V(0, 0, 1), ang_end)
open_area = Part.Face(rr(LIP_OUT, 0)).cut(outline)
print("Gießöffnung (Ecken innerhalb der Lippe): %d Flächen, gesamt %.0f mm²; Spalt Topfunterseite -> Lippe %.2f mm" % (
    len(open_area.Faces), open_area.Area, dz - LIP_H))
cad.material("Topf", "pla_schwarz"); cad.material("Reservoir", "pla_schwarz")
cad.report(Topf=pg, Reservoir=reservoir)
