"""Gridfinity-Behaelter 2x2 fuer Kotbeutel (FreeCAD Part API).

Ausfuehren: cad run gridfinity_kotbeutel.py --report
Ausgabe:    gridfinity_bin.stl, gridfinity_lid.stl, gridfinity_fit_test.stl,
            gridfinity_fuss_test.stl, gridfinity_bin.FCStd

14.11.2026 (Entwurf, nicht gedruckt): Fuss nach Gridfinity-Profil mit definiertem Spiel
FOOT_PLAY statt vereinfachtem Fuss (der alte Fuss war in der Taille 0.1 mm/Seite breiter
als die Baseplate-Oeffnung und sass ca. 2 mm hoch auf den Fasen). Hoehe 12 Units = 84 mm,
mit Deckel 86 mm ueber Schubladenboden (Limit 90 mm). Wand 1.6, Nase 0.8, Nut abgeleitet.
"""
import math
import FreeCAD as App
import Part

try:
    import Mesh
except ImportError:
    Mesh = None

OUT_DIR = "/mnt/raid1/3d_print/kotbeutel_bin"

# Projektstruktur (14.11.2026): mit `cad projekt kotbeutel_bin` und `cad version "<Label>"` landen die Modelle in
# <Version>/modell (cad.outdir), sonst wie bisher in OUT_DIR. Alte Dateinamen in OUT_DIR sind seit der Migration
# Symlinks in Versionen: _ziel() ersetzt den Symlink statt durch ihn in die Version zu schreiben.
try:
    OUT_DIR = cad.outdir("modell", projekt="kotbeutel_bin", fallback=OUT_DIR)
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
NX = NY = 2            # 2x2
FOOT_PLAY = 0.30      # Spiel je Seite zur Baseplate-Oeffnung (Taille); Gridfinity-Standard 0.25
FOOT_BOT_EXTRA = 0.1   # zusaetzliches Spiel an der Fussunterkante (Elefantenfuss), wie Standard 0.8 vs 0.7
CLEAR = 2 * FOOT_PLAY  # Gesamtspiel je Zelle (Aussenmass = 84 - 0.6 = 83.4)
H_UNITS = 12           # Gridfinity-Hoehe in 7-mm-Units (Unterkante Fuss bis Oberkante Behaelter)
H_TOTAL = 7.0 * H_UNITS  # 84 mm; mit Deckelplatte 86 mm ueber Schubladenboden
H_LIMIT = 90.0         # absolute Obergrenze inkl. Deckel (Vorgabe); Schubladen-Innenhoehe ungemessen
FOOT_H = 4.75          # Gridfinity-Fusshoehe (Profil 0.8 / 1.8 / 2.15)
# Baseplate-Oeffnung (GridFlock/gridfinity-rebuilt, gemessen an seg_04.stl): halbe Breite / Radius
PLATE_BOT = (18.15, 1.15)   # z=0
PLATE_WAIST = (18.85, 1.85) # z=0.7..2.5
PLATE_TOP = (21.0, 4.0)     # z=4.65
PLATE_H = 4.65
WALL = 1.6             # Wandstaerke (1.4 -> 1.6, damit hinter der tieferen Nut >= 0.9 mm Wand bleibt)
R_IN = 3.2             # Innenradius der Kavitaet
FLOOR = 1.2            # Bodenstaerke ueber den Fuessen
OPEN_W = 40.0          # Frontoeffnung Breite
OPEN_H = 30.0          # Frontoeffnung Hoehe (von Oberkante)
LID_T = 2.0            # Deckelplatte
LID_LIP = 7.0          # Deckel-Fuehrungslippe
LID_FIT = 0.25         # Spiel Lippe zur Wand
LID_PRINT_FLIPPED = True  # Deckel mit Platte nach unten ausgeben (Druckausrichtung)
LIP_WALL = 1.6         # Wandstaerke der (flexenden) Lippe
GROOVE_CEIL = 1.5      # Nut-Decke steiler als 45 Grad (Druck ohne Support)
SNAP_W = 20.0          # Breite der Schnapp-Nase
SNAP_OUT = 0.8         # Nase ueber die Lippe (0.6 rastete zu schwach, 13.11.); Eingriff = SNAP_OUT - LID_FIT
SNAP_TIP_CLEAR = 0.1   # Spiel Nasenspitze zum Nutgrund
SNAP_GROOVE = SNAP_OUT - LID_FIT + SNAP_TIP_CLEAR   # Nut-Tiefe ab Wand-Innenflaeche (0.65)
EXPORT_SERIES = False  # Nasen-Serie nicht neu schreiben (gesliced Stand 13.11. bleibt gueltig)
SNAP_Z0 = 1.6          # Nase beginnt so hoch ueber Lippen-Unterkante
SNAP_H = 3.6           # Nasenhoehe (45-Grad-Rampen an Ober-/Unterseite)
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
    """Gridfinity-Fuss (4.75 mm, Profil 0.8 Fase / 1.8 senkrecht / 2.15 Fase) als Versatz der
    Baseplate-Oeffnung um FOOT_PLAY nach innen. Bei FOOT_PLAY=0.25 = Standard-Fuss
    (35.6 / 37.2 / 41.5). Der Behaelter steht auf dem Schubladenboden (Platte unten offen)."""
    p = FOOT_PLAY
    hw_w, r_w = PLATE_WAIST[0] - p, PLATE_WAIST[1] - p            # Taille: Spiel = p
    ch = 0.7 + FOOT_BOT_EXTRA                                     # untere Fase (Platte 0.7, Fuss 0.8)
    hw_b, r_b = hw_w - ch, max(r_w - ch, 0.3)                     # Unterkante (45 Grad)
    hw_t, r_t = hw_w + 2.15, PLATE_TOP[1] - p                     # Oberkante = Zelle - 2p
    z = [0.0, ch, ch + 1.8, FOOT_H]
    w = [rrect_wire(cx, cy, 2 * hw_b, 2 * hw_b, r_b, z[0]),
         rrect_wire(cx, cy, 2 * hw_w, 2 * hw_w, r_w, z[1]),
         rrect_wire(cx, cy, 2 * hw_w, 2 * hw_w, r_w, z[2]),
         rrect_wire(cx, cy, 2 * hw_t, 2 * hw_t, r_t, z[3])]
    return Part.makeLoft(w, True, True)   # ruled: gerade Fasen


def snap_profile(x_face, depth, z0, h, width, ceil=1.0):
    """Trapez (Nase/Nut) an der +X-Flaeche, in Y extrudiert.
    Unterflanke 45 Grad; Oberflanke (Nut-Decke) mit Steigung ceil*depth/depth,
    ceil=1 -> 45 Grad, ceil=1.5 -> ca. 56 Grad (steiler = besser druckbar, haelt besser)."""
    V = App.Vector
    r = min(depth, h / 2)
    r_hi = min(depth * ceil, h / 2)
    pts = [V(x_face, -width / 2, z0), V(x_face + depth, -width / 2, z0 + r),
           V(x_face + depth, -width / 2, z0 + h - r_hi), V(x_face, -width / 2, z0 + h)]
    f = Part.Face(Part.makePolygon(pts + [pts[0]]))
    return f.extrude(V(0, width, 0))


def rot(shape, deg):
    shape = shape.copy()
    shape.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), deg)
    return shape


def build_bin():
    # --- Fuesse -------------------------------------------------------------
    # Ein Fuss, dann kopieren/verschieben und in EINEM Schritt vereinigen (statt 3 Fuses je Zelle)
    base_foot = foot(0, 0)
    feet = []
    for i in range(NX):
        for j in range(NY):
            f = base_foot.copy()
            f.translate(App.Vector((i - (NX - 1) / 2) * GRID, (j - (NY - 1) / 2) * GRID, 0))
            feet.append(f)
    solid = feet[0].multiFuse(feet[1:]) if len(feet) > 1 else feet[0]

    # --- Koerper ------------------------------------------------------------
    body = rrect_prism(0, 0, W, D, R_OUT, FOOT_H, H_TOTAL - FOOT_H)
    solid = solid.fuse(body)

    # --- Kavitaet (oben offen) ---------------------------------------------
    z_floor = FOOT_H + FLOOR
    cav = rrect_prism(0, 0, W - 2 * WALL, D - 2 * WALL, R_IN, z_floor, H_TOTAL - z_floor + 1)
    solid = solid.cut(cav)

    # --- Nuten fuer die Deckel-Schnappnasen ---------------------------------
    # Nut oben/unten um SNAP_TIP_CLEAR hoeher als die Nase: sonst schneidet die 45-Grad-Oberflanke
    # der Nase die steilere Nut-Decke (gemessen 0.05 mm3 bei Nase 0.8 / Nut 0.65)
    gz0 = H_TOTAL - LID_LIP + SNAP_Z0 - SNAP_TIP_CLEAR
    x_in = W / 2 - WALL
    for ang in SNAP_SIDES:
        g = snap_profile(x_in - 0.01, SNAP_GROOVE + 0.01, gz0, SNAP_H + 2 * SNAP_TIP_CLEAR,
                         SNAP_W + 1.0, ceil=GROOVE_CEIL)
        solid = solid.cut(rot(g, ang))

    # --- Frontoeffnung: 45-Grad-Schraege, 40 breit x 30 hoch ----------------
    # Profil in YZ (Front bei -Y). Unterkante steigt nach innen unter 45 Grad.
    y_o = -D / 2 - 2.0
    z_b = H_TOTAL - OPEN_H
    V = App.Vector
    dz = (H_TOTAL + 1) - (z_b - 2.0)
    pts = [V(-OPEN_W / 2, y_o, z_b - 2.0),
           V(-OPEN_W / 2, y_o + dz, H_TOTAL + 1),
           V(-OPEN_W / 2, y_o, H_TOTAL + 1)]
    # Querschnitt (Dreieck, 45 Grad) in YZ, extrudiert ueber die X-Breite
    face = Part.Face(Part.makePolygon(pts + [pts[0]]))
    wedge = face.extrude(V(OPEN_W, 0, 0))
    solid = solid.cut(wedge)
    return solid.removeSplitter()


def build_lid():
    """Deckel mit Frontauschnitt; Platte + Lippe, flach auf z=0."""
    plate = rrect_prism(0, 0, W, D, R_OUT, LID_LIP, LID_T)
    lip_w = W - 2 * (WALL + LID_FIT)
    lip_d = D - 2 * (WALL + LID_FIT)
    r_lip = max(R_IN - LID_FIT, 0.5)
    lip = rrect_prism(0, 0, lip_w, lip_d, r_lip, 0, LID_LIP + 0.1)
    # Lippe aushoehlen -> duenne, federnde Wand (von unten offen)
    hollow = rrect_prism(0, 0, lip_w - 2 * LIP_WALL, lip_d - 2 * LIP_WALL,
                         max(r_lip - LIP_WALL, 0.5), -0.1, LID_LIP + 0.1 - 0.0)
    lip = lip.cut(hollow)
    lid = plate.fuse(lip)
    # Schnappnasen + Schlitze links/rechts/hinten
    for ang in SNAP_SIDES:
        n = snap_profile(lip_w / 2 - 0.01, SNAP_OUT + 0.01, SNAP_Z0, SNAP_H, SNAP_W)
        lid = lid.fuse(rot(n, ang))
        for sgn in (-1, 1):
            sl = Part.makeBox(LIP_WALL + 1.0, SLIT, LID_LIP + 0.2,
                              App.Vector(lip_w / 2 - LIP_WALL - 0.5,
                                         sgn * (SNAP_W / 2 + SLIT / 2) - SLIT / 2, -0.1))
            lid = lid.cut(rot(sl, ang))
    # Frontauschnitt: 40 breit, OPEN_H tief ab Frontkante
    cut = Part.makeBox(OPEN_W, OPEN_H, LID_T + LID_LIP + 2,
                       App.Vector(-OPEN_W / 2, -D / 2 - 1, -1))
    lid = lid.cut(cut)
    lid = lid.removeSplitter()
    if LID_PRINT_FLIPPED:
        # Druckfertig: Platte unten (z=0), Lippe zeigt nach oben -> keine Ueberhaenge
        lid.rotate(App.Vector(0, 0, 0), App.Vector(0, 1, 0), 180)
        lid.translate(App.Vector(0, 0, LID_T + LID_LIP))
    return lid


def export(shape, path, doc, name):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    doc.recompute()
    import MeshPart
    mesh = doc.addObject("Mesh::Feature", name + "_mesh")
    mesh.Mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.05,
                                      AngularDeflection=math.radians(10))
    mesh.Mesh.write(_ziel(path))
    doc.removeObject(mesh.Name)
    return obj


doc = App.newDocument("GridfinityBin")
bin_shape = build_bin()
b = export(bin_shape, OUT_DIR + "/gridfinity_bin.stl", doc, "Bin")
print("BIN valid=%s volume=%.0f mm3 bbox=%s" % (bin_shape.isValid(), bin_shape.Volume, bin_shape.BoundBox))

lid_shape = build_lid()
lid_shape.translate(App.Vector(W + 10, 0, 0))   # neben dem Behaelter
export(lid_shape, OUT_DIR + "/gridfinity_lid.stl", doc, "Lid")
print("LID valid=%s volume=%.0f mm3 bbox=%s" % (lid_shape.isValid(), lid_shape.Volume, lid_shape.BoundBox))

doc.recompute()
doc.saveAs(_ziel(OUT_DIR + "/gridfinity_bin.FCStd"))


# ---- Pruefkoerper (nur Messung, kein Export) -----------------------------------
def build_lid_mounted():
    """Deckel in Einbaulage auf dem Behaelter (Platte liegt auf dem Rand)."""
    global LID_PRINT_FLIPPED
    old = LID_PRINT_FLIPPED
    LID_PRINT_FLIPPED = False
    try:
        lid = build_lid()
    finally:
        LID_PRINT_FLIPPED = old
    lid.translate(App.Vector(0, 0, H_TOTAL - LID_LIP))
    return lid


def build_plate():
    """2x2-Ausschnitt der Baseplate (Profil wie GridFlock/gridfinity-rebuilt, unten offen)."""
    V = App.Vector
    cutters = []
    for i in range(NX):
        for j in range(NY):
            cx, cy = (i - (NX - 1) / 2) * GRID, (j - (NY - 1) / 2) * GRID
            (b, rb), (wa, rw), (t, rt) = PLATE_BOT, PLATE_WAIST, PLATE_TOP
            ws = [rrect_wire(cx, cy, 2 * b, 2 * b, rb, -1.0), rrect_wire(cx, cy, 2 * b, 2 * b, rb, 0.0),
                  rrect_wire(cx, cy, 2 * wa, 2 * wa, rw, 0.7), rrect_wire(cx, cy, 2 * wa, 2 * wa, rw, 2.5),
                  rrect_wire(cx, cy, 2 * t, 2 * t, rt, PLATE_H), rrect_wire(cx, cy, 2 * t, 2 * t, rt, PLATE_H + 3)]
            cutters.append(Part.makeLoft(ws, True, True))
    blk = Part.makeBox(GRID * NX + 8, GRID * NY + 8, PLATE_H, V(-(GRID * NX + 8) / 2, -(GRID * NY + 8) / 2, 0))
    return blk.cut(cutters[0].multiFuse(cutters[1:])).removeSplitter()


lid_mounted = build_lid_mounted()
plate = build_plate()
print("MASS Gesamthoehe inkl. Deckel = %.2f mm (Limit %.1f, Reserve %.2f)" % (
    lid_mounted.BoundBox.ZMax, H_LIMIT, H_LIMIT - lid_mounted.BoundBox.ZMax))
print("MASS Deckel auf Behaelter:"); fit_lid = None
try:
    fit_lid = cad.fit(lid_mounted, bin_shape)                       # 0 mm3 erwartet
    cad.fit(lid_mounted, bin_shape, move=(0, 0, -0.1))              # 0.1 tiefer -> Kontakt Platte/Rand
    print("MASS Fuss in Baseplate (Behaelter auf Schubladenboden):")
    cad.fit(bin_shape, plate)                                       # 0 mm3, Abstand = FOOT_PLAY
    for dx in (FOOT_PLAY - 0.05, FOOT_PLAY + 0.05):
        cad.fit(bin_shape, plate, move=(dx, 0, 0))                  # seitlich: Spiel ausnutzen
except NameError:      # ohne cad-Worker (freecad -c)
    pass
print("MASS Nase: Ueberstand %.2f, Lippenspiel %.2f, Eingriff %.2f, Nuttiefe %.2f, Restwand %.2f" % (
    SNAP_OUT, LID_FIT, SNAP_OUT - LID_FIT, SNAP_GROOVE, WALL - SNAP_GROOVE))


# ---- Teststueck: nur +X-Wand mit Nut + passendes Deckelstueck -----------------
def build_test():
    """Wandausschnitt (Nut) + Deckelausschnitt (Lippe/Nase) zum Probedruck der Passform."""
    V = App.Vector
    wall = build_bin().common(Part.makeBox(14, 40, 18, V(W / 2 - 14, -20, H_TOTAL - 18)))
    wall.translate(V(0, 0, -(H_TOTAL - 18)))           # flach auf z=0
    lx = -W / 2 if LID_PRINT_FLIPPED else W / 2 - 14
    lid = build_lid().common(Part.makeBox(14, 40, LID_T + LID_LIP, V(lx, -20, 0)))
    # Teile mit 8 mm Abstand nebeneinander (kurze Wege, weniger Faeden)
    lid.translate(V(wall.BoundBox.XMin - 8.0 - lid.BoundBox.XMax, 0, 0))
    return wall.fuse(lid)


test = build_test()
export(test, OUT_DIR + "/gridfinity_fit_test.stl", doc, "FitTest")
print("TEST valid=%s volume=%.0f mm3 bbox=%s" % (test.isValid(), test.Volume, test.BoundBox))


# ---- Fuss-Teststueck: nur die 4 Fuesse + Boden (Sitz im Raster pruefen, ca. 6 mm hoch) ----
FOOT_TEST_TOP = FOOT_H + FLOOR
foot_test = bin_shape.common(Part.makeBox(W + 2, D + 2, FOOT_TEST_TOP, App.Vector(-W / 2 - 1, -D / 2 - 1, 0)))
export(foot_test, OUT_DIR + "/gridfinity_fuss_test.stl", doc, "FootTest")
print("FUSSTEST valid=%s volume=%.0f mm3 bbox=%s" % (foot_test.isValid(), foot_test.Volume, foot_test.BoundBox))

try:
    lid_print = lid_shape.copy()
    lid_print.translate(App.Vector(-(W + 10), 0, 0))
    cad.report(Behaelter=bin_shape, Deckel=lid_print, Fusstest=foot_test, Platte=plate, DeckelMontiert=lid_mounted)
    cad.focus("Fuss_Taille", (W / 2 - 1.5, 0, 1.7), 6, view="front")
    cad.focus("Nut_X", (W / 2 - WALL, 0, H_TOTAL - LID_LIP + SNAP_Z0 + SNAP_H / 2), 8, view="front")
except NameError:
    pass


# ---- Nasen-Serie: 1 Wandstueck mit 3 Nuten + 3 Lippenstuecke ----------------------
SERIES_OUT = (0.8, 1.0, 1.2)     # Nasen-Ueberstand ueber die Lippe
SERIES_CLEAR = 0.1               # Spiel zwischen Nasenspitze und Nutgrund
SERIES_PIECE_W = 26.0            # Breite je Lippenstueck (Nase 20 + Schlitze + Rand)
SERIES_PITCH = 34.0              # Mittenabstand (8 mm Luecke)


def build_series():
    global SNAP_OUT
    V = App.Vector
    n = len(SERIES_OUT)
    z_top = 18.0
    gz0 = z_top - LID_LIP + SNAP_Z0
    # Wandstueck: Innenflaeche bei x=0, Wand zeigt nach +x, Nuten je Variante
    y_min = -(SNAP_W + 1.0) / 2
    y_max = (n - 1) * SERIES_PITCH + (SNAP_W + 1.0) / 2
    wall = Part.makeBox(WALL, y_max - y_min, z_top, V(0, y_min, 0))
    info = []
    for i, p in enumerate(SERIES_OUT):
        depth = p - LID_FIT + SERIES_CLEAR          # Nutgrund ab Wand-Innenflaeche
        g = snap_profile(-0.01, depth + 0.01, gz0, SNAP_H, SNAP_W + 1.0, ceil=GROOVE_CEIL)
        g.translate(V(0, i * SERIES_PITCH, 0))
        wall = wall.cut(g)
        info.append((p, round(depth, 2), round(WALL - depth, 2)))
    parts = [wall]
    xs = WALL + 8.0
    old = SNAP_OUT
    for i, p in enumerate(SERIES_OUT):
        SNAP_OUT = p
        lid = build_lid()
        lx = -W / 2 if LID_PRINT_FLIPPED else W / 2 - 14
        piece = lid.common(Part.makeBox(14, SERIES_PIECE_W, LID_T + LID_LIP + 0.1,
                                        V(lx, -SERIES_PIECE_W / 2, -0.05)))
        # Kerben 1/2/3 an der Plattenaussenkante (Anzahl = Variante)
        for k in range(i + 1):
            yk = (k - i / 2.0) * 4.0
            nb = Part.makeBox(1.2, 1.5, LID_T + 1, V(piece.BoundBox.XMin - 0.1, yk - 0.75, -0.5))
            piece = piece.cut(nb)
        piece.translate(V(xs - piece.BoundBox.XMin, i * SERIES_PITCH, 0))
        parts.append(piece)
    SNAP_OUT = old
    shape = parts[0]
    for q in parts[1:]:
        shape = shape.fuse(q)
    return shape, info


if EXPORT_SERIES:
    series, series_info = build_series()
    export(series, OUT_DIR + "/gridfinity_nase_serie.stl", doc, "NoseSeries")
    print("SERIE valid=%s bbox=%s  (Ueberstand, Nuttiefe, Restwand)=%s" % (series.isValid(), series.BoundBox, series_info))
