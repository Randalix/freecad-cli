"""Gridfinity-Behaelter 3x6 Halter fuer Tempo-Taschentuchbox (115 x 225 mm) (FreeCAD Part API), Front-Aussparung zur Entnahme.

Headless:  freecad -c gridfinity_bin.py   (im GUI: exec(open(...).read()))
Ausgabe:   gridfinity_tempo.stl, gridfinity_tempo.FCStd
"""
import math
import FreeCAD as App
import Part

try:
    import Mesh
except ImportError:
    Mesh = None

OUT_DIR = "/mnt/raid1/3d_print/tempo_bin"

# Projektstruktur (14.11.2026): mit `cad projekt tempo_bin` und `cad version "<Label>"` landen die Modelle in
# <Version>/modell (cad.outdir), sonst wie bisher in OUT_DIR. Alte Dateinamen in OUT_DIR sind seit der Migration
# Symlinks in Versionen: _ziel() ersetzt den Symlink statt durch ihn in die Version zu schreiben.
try:
    OUT_DIR = cad.outdir("modell", projekt="tempo_bin", fallback=OUT_DIR)
except NameError:      # ohne cad-Worker (freecad -c)
    pass


def _ziel(p):
    import os
    if os.path.islink(p):
        os.unlink(p)
        print("[cad] Hinweis: Symlink %s ersetzt (die Version, auf die er zeigte, bleibt unveraendert)" % p)
    else:
        try:
            import cadprojekt
            w = cadprojekt.check_write(p)
            if w:
                print("[cad] Hinweis: " + w)
        except ImportError:
            pass
    return p

# ---- Parameter -------------------------------------------------------------
GRID = 42.0            # Rastermass
NX, NY = 3, 6          # 3x6 -> aussen 124.5 x 249.5, innen 121.7 x 246.7 (Box 115 x 225)
CLEAR = 0.5            # Gesamtspiel (Aussenmass = 84 - 0.5 = 83.5, Gridfinity-ueblich)
H_TOTAL = 40.0         # Gesamthoehe ohne Deckel
FOOT_H = 4.4           # Gridfinity Boden (Fuesse)
WALL = 1.4             # Wandstaerke
R_IN = 3.2             # Innenradius der Kavitaet
FLOOR = 1.2            # Bodenstaerke ueber den Fuessen
OPEN_W = 50.0          # Entnahme-Aussparung Breite (Radius = Breite/2)
OPEN_H = 28.0          # Aussparung Tiefe von Oberkante
LID_T = 2.0            # Deckelplatte
LID_LIP = 5.0          # Deckel-Fuehrungslippe
LID_FIT = 0.25         # Spiel Lippe zur Wand
LIP_WALL = 1.2         # Wandstaerke der (flexenden) Lippe
SNAP_W = 20.0          # Breite der Schnapp-Nase
SNAP_OUT = 0.5         # Nase steht so weit ueber die Lippe (0.3 ueber das Spiel = Haltekraft)
SNAP_GROOVE = 0.4      # Nut-Tiefe in der Behaelterwand (ab Innenflaeche)
SNAP_Z0 = 1.2          # Nase beginnt so hoch ueber Lippen-Unterkante
SNAP_H = 2.4           # Nasenhoehe (45-Grad-Rampen an Ober-/Unterseite)
SLIT = 1.0             # Schlitzbreite neben den Nasen
SNAP_SIDES = (0, 180, 90)   # Drehwinkel um Z: +X, -X, +Y (Front -Y bleibt frei)

W = GRID * NX - CLEAR
D = GRID * NY - CLEAR
R_OUT = R_IN + WALL


def rrect_wire(cx, cy, w, d, r, z):
    """Wire eines Rechtecks mit abgerundeten Ecken auf Hoehe z."""
    r = max(r, 0.01)
    x0, x1 = cx - w / 2, cx + w / 2
    y0, y1 = cy - d / 2, cy + d / 2
    V = App.Vector
    c = math.sqrt(0.5)
    e = []
    e.append(Part.LineSegment(V(x0 + r, y0, z), V(x1 - r, y0, z)))
    e.append(Part.Arc(V(x1 - r, y0, z), V(x1 - r + r * c, y0 + r - r * c, z), V(x1, y0 + r, z)))
    e.append(Part.LineSegment(V(x1, y0 + r, z), V(x1, y1 - r, z)))
    e.append(Part.Arc(V(x1, y1 - r, z), V(x1 - r + r * c, y1 - r + r * c, z), V(x1 - r, y1, z)))
    e.append(Part.LineSegment(V(x1 - r, y1, z), V(x0 + r, y1, z)))
    e.append(Part.Arc(V(x0 + r, y1, z), V(x0 + r - r * c, y1 - r + r * c, z), V(x0, y1 - r, z)))
    e.append(Part.LineSegment(V(x0, y1 - r, z), V(x0, y0 + r, z)))
    e.append(Part.Arc(V(x0, y0 + r, z), V(x0 + r - r * c, y0 + r - r * c, z), V(x0 + r, y0, z)))
    return Part.Wire([x.toShape() for x in e])


def rrect_prism(cx, cy, w, d, r, z0, h):
    return Part.Face(rrect_wire(cx, cy, w, d, r, z0)).extrude(App.Vector(0, 0, h))


def foot(cx, cy):
    """Gridfinity-Fuss (4.4 mm): 0.8 Fase / 1.8 senkrecht / 1.8 Fase, aussen 41.5."""
    cell = GRID - CLEAR
    s0 = cell - 2 * 2.6          # Unterkante
    s1 = cell - 2 * 1.8          # nach erster Fase
    s2 = cell                    # oben
    r0, r1, r2 = 0.8, 1.6, 3.75
    z = [0.0, 0.8, 2.6, 4.4]
    parts = []
    # Fase 1
    parts.append(Part.makeLoft([rrect_wire(cx, cy, s0, s0, r0, z[0]),
                                rrect_wire(cx, cy, s1 - 0.0, s1 - 0.0, r1, z[1])], True))
    # senkrecht
    parts.append(rrect_prism(cx, cy, s1, s1, r1, z[1], z[2] - z[1]))
    # Fase 2 (Aufweitung auf volle Zelle)
    parts.append(Part.makeLoft([rrect_wire(cx, cy, s1, s1, r1, z[2]),
                                rrect_wire(cx, cy, s2, s2, r2, z[3])], True))
    f = parts[0]
    for p in parts[1:]:
        f = f.fuse(p)
    return f



def build_bin():
    # Ein Fuss, dann kopieren/verschieben und in EINEM Schritt vereinigen (statt 3 Fuses je Zelle)
    base_foot = foot(0, 0)
    feet = []
    for i in range(NX):
        for j in range(NY):
            f = base_foot.copy()
            f.translate(App.Vector((i - (NX - 1) / 2) * GRID, (j - (NY - 1) / 2) * GRID, 0))
            feet.append(f)
    solid = feet[0].multiFuse(feet[1:]) if len(feet) > 1 else feet[0]
    solid = solid.fuse(rrect_prism(0, 0, W, D, R_OUT, FOOT_H, H_TOTAL - FOOT_H))
    z_floor = FOOT_H + FLOOR
    solid = solid.cut(rrect_prism(0, 0, W - 2 * WALL, D - 2 * WALL, R_IN, z_floor, H_TOTAL - z_floor + 1))
    # Front-Aussparung (-Y): U-Form mit runder Unterkante, Tiefe OPEN_H von oben
    V = App.Vector
    r = OPEN_W / 2
    zc = H_TOTAL - OPEN_H + r
    y0 = -D / 2 - 1.0
    cyl = Part.makeCylinder(r, WALL + 2.0, V(0, y0, zc), V(0, 1, 0))
    box = Part.makeBox(OPEN_W, WALL + 2.0, H_TOTAL + 1 - zc, V(-r, y0, zc))
    solid = solid.cut(cyl.fuse(box))
    return solid.removeSplitter()


import MeshPart
doc = App.newDocument("GridfinityTempo")
shape = build_bin()
obj = doc.addObject("Part::Feature", "Tempo")
obj.Shape = shape
doc.recompute()
mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.05, AngularDeflection=math.radians(10))
mesh.write(_ziel(OUT_DIR + "/gridfinity_tempo.stl"))
doc.saveAs(_ziel(OUT_DIR + "/gridfinity_tempo.FCStd"))
print("TEMPO valid=%s volume=%.0f mm3 bbox=%s inner=%.1f" % (shape.isValid(), shape.Volume, shape.BoundBox, W - 2 * WALL))
