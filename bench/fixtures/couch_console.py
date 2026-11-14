"""Couch-Konsole (Konsolentisch hinter dem Sofa): Multiplex-Korpusse, Eichenplatte. Alle Masse in mm.

Ausfuehren:  cad run couch_console.py --report
Koordinaten: Ursprung = linke untere vordere Ecke der Eichenplatte (Boden z=0).
  X = Laenge (links -> rechts, vom Sofa aus gesehen), Y = Tiefe (0 = Sofaseite vorn, +Y -> Wand), Z = oben.
Layout: links/rechts je ein Korpus, an der AUSSENSEITE offen (Fachboeden, Laptop-Schlitz),
Vorder- und Rueckwand geschlossen. Mitte: durchgehende Rueckwand, Vorder-Zarge, Mittelstuetze.
"""
import os
import FreeCAD as App
import Part

OUT_DIR = "/mnt/raid1/3d_print/couch_console"
V = App.Vector

# ---- Hauptmasse -----------------------------------------------------------
L_TOTAL = 2400.0        # Plattenlaenge (Sofabreite 240 cm)
H_TOTAL = 750.0         # Oberkante Eichenplatte (75 cm)
PLATE_D = 220.0         # Plattentiefe (Schaetzwert, Richtwert 20-25 cm)
PLATE_T = 27.0          # Eichenplatte
OH_END = 15.0           # Plattenueberstand an den Enden (und Korpus beginnt dort)
OH_FRONT = 15.0         # Plattenueberstand vorn (Sofaseite)
WALL_Y = 230.0          # Lage der Wandflaeche (Y); Platte endet 10 mm davor
GAP_WALL = 35.0         # Abstand Rueckwand-Aussenseite zur Wand (Winkelstecker), 30-40
T18 = 18.0              # Multiplex
T12 = 12.0              # Multiplex duenn (Fachboeden, Trennwand)
NUT_T = 6.0             # Nuttiefe fuer Fachboeden in Vorder-/Rueckwand
# ---- abgeleitet -----------------------------------------------------------
Y_FRONT = OH_FRONT                  # Aussenflaeche Vorderwand
Y_BACK = WALL_Y - GAP_WALL          # Aussenflaeche Rueckwand
Y_IN0 = Y_FRONT + T18               # Innenflaeche vorn
Y_IN1 = Y_BACK - T18                # Innenflaeche hinten
IN_D = Y_IN1 - Y_IN0                # lichte Tiefe
Z_TOP = H_TOTAL - PLATE_T           # Oberkante Korpus
X0 = OH_END                         # Korpus links aussen (offen)
X1 = L_TOTAL - OH_END               # Korpus rechts aussen (offen)
# ---- Korpusse -------------------------------------------------------------
LAP_DEPTH = 380.0       # Laptop-Einschubtiefe (lichtes Mass Fach)  [Schaetzwert Laptop 360]
SLACK_X = 10.0          # Luft am Ende des Faches
FACH_X = LAP_DEPTH + SLACK_X        # lichte Fachlaenge (beide Korpusse)
BLOCK_L = FACH_X + T18              # Korpuslaenge inkl. Endwand
# links: Fachboeden
N_SHELF_L = 3
# rechts, von unten: Netzfach | Fachboden R1 | Laptop/Netzteil-Zone | Fachboden R2 | Ablagefach
BAY1_H = 200.0          # lichte Hoehe Fach Steckdosenleiste
LAP_H = 280.0           # lichte Hoehe Laptop-Schlitz (Laptop 250 hochkant)
LAP_T = 40.0            # lichte Dicke Laptop-Schlitz (Laptop 22)
CHAMF = 8.0             # Einfuehrschraege am Schlitz-Eingang
# ---- Steckdose / Kabel ----------------------------------------------------
SOCK_FROM_RIGHT = 150.0     # [Schaetzwert!] Abstand Dosenmitte vom rechten Plattenende; vor dem Bau nachmessen
SOCK_Z = 250.0              # Dosenmitte ueber Boden (bestaetigt)
SOCK_X = L_TOTAL - SOCK_FROM_RIGHT
PLUG_W, PLUG_D, PLUG_H = 50.0, 28.0, 60.0   # Winkelstecker-Platzhalter
SOCK_PROUD = 2.0            # Dose steht 2 mm vor der Wand (Unterputz, Abdeckrahmen)
STRIP_L, STRIP_W, STRIP_H = 300.0, 50.0, 35.0   # [Schaetzwert] Steckdosenleiste 4 Plaetze
STRIP_X1 = X1 - 15.0                # Leiste rechtsbuendig, 15 mm vom offenen Ende
STRIP_Y0 = 80.0
CUT_W, CUT_Z0, CUT_H = 60.0, 28.0, 60.0     # Ausschnitt Rueckwand an der Dose (Kabel abwaerts)
CORD_Z = 36.0               # Hoehe der Netzleitung (aus Leistenrueckseite)
CORD_D = 8.0                # Kabeldurchmesser (Pruefkoerper)
CLAMP_W, CLAMP_D, CLAMP_H = 50.0, 15.0, 12.0   # Zugentlastung (Leiste mit Kabelbinder)
PSU = (110.0, 60.0, 30.0)   # Netzteil-Platzhalter (x,y,z)
PSU_X0, PSU_Y0 = 2070.0, 90.0
SHAFT_W, SHAFT_D = 40.0, 20.0               # Kabelschacht (x, y)
SHAFT_X0 = X1 - BLOCK_L + T18               # an der Endwand (innen)
SHAFT_Y0 = Y_IN1 - SHAFT_D                  # hinten an der Rueckwand
HOLE_D = 60.0               # Kabeldurchlass Eichenplatte (Buerstentuelle)
HOLE_CX = SHAFT_X0 + SHAFT_W / 2
HOLE_CY = SHAFT_Y0 + SHAFT_D / 2 - 7.0
SLIT_Z0, SLIT_H = 240.0, 16.0   # Kabelschlitz Trennwand (USB-C zum Laptop)
SLIT_X0, SLIT_X1 = 2010.0, 2200.0
VENT_N, VENT_W, VENT_H, VENT_PITCH = 6, 5.0, 70.0, 28.0   # Lueftungsschlitze Rueckwand
VENT_X0, VENT_Z0 = PSU_X0 + 5.0, T18 + BAY1_H + T12 + 5.0   # hinter dem Netzteil
# ---- Testkoerper ------------------------------------------------------------
LAPTOP = (360.0, 22.0, 250.0)   # [Schaetzwert] 15,6 Zoll, hochkant

# ---------------------------------------------------------------------------
P = {}      # Name -> Shape
META = {}   # Name -> (Material, Dicke) ; nur Zuschnittteile


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def add(name, shape, mat=None):
    P[name] = shape
    if mat:
        META[name] = mat


def cut_all(shape, cutters):
    for c in cutters:
        shape = shape.cut(c)
    return shape


# Fachboden-Lagen (z0) je Korpus
bx_r0 = X1 - BLOCK_L           # rechter Korpus: Aussenkante innen
bx_l1 = X0 + BLOCK_L
r1_z0 = T18 + BAY1_H
r2_z0 = r1_z0 + T12 + LAP_H
shelves_r = {"Fachboden_R1": r1_z0, "Fachboden_R2": r2_z0}
shelves_l = {}
inner_h_l = Z_TOP - T18 - T18
pitch_h = (inner_h_l - N_SHELF_L * T12) / (N_SHELF_L + 1)
for i in range(N_SHELF_L):
    shelves_l["Fachboden_L%d" % (i + 1)] = T18 + pitch_h * (i + 1) + T12 * i

# Nuten (Quader in Vorder-/Rueckwand), bei Fachboeden
def nuten(xa, xb, shelves, front):
    out = []
    for z0 in shelves.values():
        if front:
            out.append(box(xa - 1, xb + 1, Y_IN0 - NUT_T, Y_IN0, z0, z0 + T12))
        else:
            out.append(box(xa - 1, xb + 1, Y_IN1, Y_IN1 + NUT_T, z0, z0 + T12))
    return out


def tri_prism(p0, p1, p2, z0, z1):
    """Dreiecksprisma (Punkte in XY), von z0 bis z1."""
    w = Part.makePolygon([V(p0[0], p0[1], z0), V(p1[0], p1[1], z0), V(p2[0], p2[1], z0), V(p0[0], p0[1], z0)])
    return Part.Face(w).extrude(V(0, 0, z1 - z0))


lap_z0 = r1_z0 + T12            # Oberkante Fachboden R1 = Auflage Laptop
lap_z1 = lap_z0 + LAP_H
Y_TW0 = Y_IN0 + LAP_T           # Trennwand Laptopfach: Flaeche zum Schlitz
Y_TW1 = Y_TW0 + T12

# --- Vorder-/Rueckwaende ---------------------------------------------------
add("Vorderwand_links", cut_all(box(X0, bx_l1, Y_FRONT, Y_IN0, 0, Z_TOP),
                               nuten(X0, bx_l1 - T18, shelves_l, True)), ("Multiplex", T18))
vr = box(bx_r0, X1, Y_FRONT, Y_IN0, 0, Z_TOP)
vr = cut_all(vr, nuten(bx_r0 + T18, X1, shelves_r, True))
vr = vr.cut(tri_prism((X1 - CHAMF, Y_IN0), (X1 + 0.01, Y_IN0), (X1 + 0.01, Y_IN0 - CHAMF), lap_z0, lap_z1))
add("Vorderwand_rechts", vr, ("Multiplex", T18))

rw = box(X0, X1, Y_IN1, Y_BACK, 0, Z_TOP)
rw = cut_all(rw, nuten(X0, bx_l1 - T18, shelves_l, False) + nuten(bx_r0 + T18, X1, shelves_r, False))
cuts = [box(SOCK_X - CUT_W / 2, SOCK_X + CUT_W / 2, Y_IN1 - 1, Y_BACK + 1, CUT_Z0, CUT_Z0 + CUT_H)]
for k in range(VENT_N):
    vx = VENT_X0 + k * VENT_PITCH
    cuts.append(box(vx, vx + VENT_W, Y_IN1 - 1, Y_BACK + 1, VENT_Z0, VENT_Z0 + VENT_H))
add("Rueckwand", cut_all(rw, cuts), ("Multiplex", T18))

# --- Boeden, Deckel, Endwaende ---------------------------------------------
add("Boden_links", box(X0, bx_l1, Y_IN0, Y_IN1, 0, T18), ("Multiplex", T18))
add("Boden_rechts", box(bx_r0, X1, Y_IN0, Y_IN1, 0, T18), ("Multiplex", T18))
shaft_cut = box(SHAFT_X0, SHAFT_X0 + SHAFT_W, SHAFT_Y0, SHAFT_Y0 + SHAFT_D, -1, H_TOTAL + 1)
add("Deckel_links", box(X0, bx_l1, Y_IN0, Y_IN1, Z_TOP - T18, Z_TOP), ("Multiplex", T18))
add("Deckel_rechts", box(bx_r0, X1, Y_IN0, Y_IN1, Z_TOP - T18, Z_TOP).cut(shaft_cut), ("Multiplex", T18))
add("Endwand_links", box(bx_l1 - T18, bx_l1, Y_IN0, Y_IN1, T18, Z_TOP - T18), ("Multiplex", T18))
add("Endwand_rechts", box(bx_r0, bx_r0 + T18, Y_IN0, Y_IN1, T18, Z_TOP - T18), ("Multiplex", T18))

# --- Fachboeden (in Nuten, Laenge = lichte Tiefe + 2 x Nut) -------------------
for nm, z0 in shelves_l.items():
    add(nm, box(X0, bx_l1 - T18, Y_IN0 - NUT_T, Y_IN1 + NUT_T, z0, z0 + T12), ("Multiplex", T12))
for nm, z0 in shelves_r.items():
    add(nm, box(bx_r0 + T18, X1, Y_IN0 - NUT_T, Y_IN1 + NUT_T, z0, z0 + T12).cut(shaft_cut), ("Multiplex", T12))

# --- Laptopfach-Trennwand (Kabelschlitz USB-C, Einfuehrschraege) ---------------
tw = box(bx_r0 + T18, X1, Y_TW0, Y_TW1, lap_z0, lap_z1)
tw = tw.cut(box(SLIT_X0, SLIT_X1, Y_TW0 - 1, Y_TW1 + 1, SLIT_Z0, SLIT_Z0 + SLIT_H))
tw = tw.cut(tri_prism((X1 - CHAMF, Y_TW0), (X1 + 0.01, Y_TW0), (X1 + 0.01, Y_TW0 + CHAMF), lap_z0 - 1, lap_z1 + 1))
add("Laptopfach_Trennwand", tw, ("Multiplex", T12))

# --- Mitte: Zarge vorn, Mittelstuetze ----------------------------------------
ZARGE_H = 100.0
add("Zarge_vorn", box(bx_l1, bx_r0, Y_FRONT, Y_IN0, Z_TOP - ZARGE_H, Z_TOP), ("Multiplex", T18))
xm = L_TOTAL / 2
add("Mittelstuetze", box(xm - T18 / 2, xm + T18 / 2, Y_IN0, Y_IN1, 0, Z_TOP), ("Multiplex", T18))

# --- Eichenplatte mit Kabeldurchlass ---------------------------------------------
plate = box(0, L_TOTAL, 0, PLATE_D, Z_TOP, H_TOTAL)
plate = plate.cut(Part.makeCylinder(HOLE_D / 2, PLATE_T + 2, V(HOLE_CX, HOLE_CY, Z_TOP - 1)))
add("Eichenplatte", plate, ("Eiche", PLATE_T))

# --- Platzhalter (kein Zuschnitt) -------------------------------------------------
add("Wand_Steckdose_Platzhalter", box(SOCK_X - 40, SOCK_X + 40, WALL_Y - SOCK_PROUD, WALL_Y, SOCK_Z - 40, SOCK_Z + 40))
add("Winkelstecker_Platzhalter", box(SOCK_X - PLUG_W / 2, SOCK_X + PLUG_W / 2, WALL_Y - SOCK_PROUD - PLUG_D,
                                     WALL_Y - SOCK_PROUD, SOCK_Z - PLUG_H / 2, SOCK_Z + PLUG_H / 2))
add("Steckdosenleiste_Platzhalter", box(STRIP_X1 - STRIP_L, STRIP_X1, STRIP_Y0, STRIP_Y0 + STRIP_W, T18, T18 + STRIP_H))
add("Zugentlastung_Leiste", box(SOCK_X - CLAMP_W / 2, SOCK_X + CLAMP_W / 2, 145, 145 + CLAMP_D, T18, T18 + CLAMP_H), ("Multiplex", T18))
add("Netzteil_Platzhalter", box(PSU_X0, PSU_X0 + PSU[0], PSU_Y0, PSU_Y0 + PSU[1], lap_z0, lap_z0 + PSU[2]))
LAP_Y0 = Y_IN0 + (LAP_T - LAPTOP[1]) / 2
LAP_X0 = bx_r0 + T18 + SLACK_X   # ganz eingeschoben
laptop = box(LAP_X0, LAP_X0 + LAPTOP[0], LAP_Y0, LAP_Y0 + LAPTOP[1], lap_z0, lap_z0 + LAPTOP[2])

# ---------------------------------------------------------------------------
# Kabelwege als Pruefkoerper (duerfen nichts beruehren)
def polyline(pts, d=CORD_D):
    out = []
    h = d / 2
    for a, b in zip(pts[:-1], pts[1:]):
        out.append(box(min(a[0], b[0]) - h, max(a[0], b[0]) + h, min(a[1], b[1]) - h, max(a[1], b[1]) + h,
                       min(a[2], b[2]) - h, max(a[2], b[2]) + h))
    return out

plug_cx = SOCK_X
netz = polyline([(plug_cx, WALL_Y - 25, SOCK_Z - PLUG_H / 2 - CORD_D / 2), (plug_cx, WALL_Y - 25, CORD_Z),
                 (plug_cx, Y_IN1 - 30, CORD_Z)])
usbc = polyline([(PSU_X0 + 40, PSU_Y0 - CORD_D / 2, lap_z0 + 14), (PSU_X0 + 40, LAP_Y0 + LAPTOP[1] + CORD_D / 2, lap_z0 + 14)])
sx, sy = SHAFT_X0 + SHAFT_W / 2, SHAFT_Y0 + SHAFT_D / 2
ac = polyline([(PSU_X0 - CORD_D / 2, 142, lap_z0 + 14), (sx, 142, lap_z0 + 14), (sx, sy, lap_z0 + 14), (sx, sy, 62),
               (sx + 85, sy, 62), (sx + 85, 105, 62), (sx + 85, 105, T18 + STRIP_H + CORD_D / 2)])
paths = {"Netzleitung": netz, "USBC_Laptop": usbc, "AC_Netzteil": ac}
shaft_probe = box(SHAFT_X0 + 0.5, SHAFT_X0 + SHAFT_W - 0.5, SHAFT_Y0 + 0.5, SHAFT_Y0 + SHAFT_D - 0.5, T18 + 2, Z_TOP + 2)
hole_probe = Part.makeCylinder(HOLE_D / 2 - 1, PLATE_T + 20, V(HOLE_CX, HOLE_CY, Z_TOP))

# ---------------------------------------------------------------------------
# Dokument + Export
doc = App.newDocument("couch_console")
for nm, sh in P.items():
    o = doc.addObject("Part::Feature", nm)
    o.Shape = sh
o = doc.addObject("Part::Feature", "Laptop_Platzhalter_360x22x250")
o.Shape = laptop
doc.recompute()
doc.saveAs(os.path.join(OUT_DIR, "couch_console.FCStd"))
try:
    Part.export([x for x in doc.Objects], os.path.join(OUT_DIR, "couch_console.step"))
except Exception as e:
    print("STEP-Export fehlgeschlagen:", e)

probes = {"Kabelweg_" + k: Part.makeCompound(v) for k, v in paths.items()}
probes["Kabelweg_Schacht"] = shaft_probe
probes["Kabelweg_Plattendurchlass"] = hole_probe
cad.report(**P, Laptop=laptop, **probes)

# ---- Fokus-Bereiche ---------------------------------------------------------
cad.focus("Laptopfach", (X1 - FACH_X / 2, Y_IN0 + LAP_T / 2, lap_z0 + 60), 450, view="top")
cad.focus("Schlitz_Eingang", (X1, Y_IN0 + 20, lap_z0 + 120), 80, view="top")
cad.focus("Plattendurchlass", (HOLE_CX, HOLE_CY, H_TOTAL), 100, view="top")
cad.focus("Kabelschacht", (sx, sy, Z_TOP - 40), 100, view="front")
cad.focus("Wanddose_Ausschnitt", (SOCK_X, Y_BACK, SOCK_Z - 100), 220, view="back")
cad.focus("Netzfach", (X1 - FACH_X / 2, Y_IN0 + IN_D / 2, T18 + BAY1_H / 2), 420, view="right")
cad.focus("Plattenueberstand_rechts", (L_TOTAL, PLATE_D / 2, Z_TOP), 120, view="front")
cad.focus("Auflager_Fachboden", (X0 + 100, Y_IN0, shelves_l["Fachboden_L1"]), 80, view="right")
cad.focus("Mittelstuetze", (xm, Y_IN0 + IN_D / 2, Z_TOP), 150, view="front")

# ---- Pruefungen (cad.fit) ------------------------------------------------------
print("=== Kollisionspruefung: alle Teile paarweise ===")
names = list(P.keys())
bad = []
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        a, b = P[names[i]], P[names[j]]
        if not a.BoundBox.intersect(b.BoundBox):
            continue
        v = a.common(b).Volume
        if v > 1e-3:
            bad.append((names[i], names[j], round(v, 2)))
print("Durchdringungen:", bad if bad else "keine")

print("=== Laptop: Einfuehren (Weg nach aussen +X) und Abstand ===")
allparts = Part.makeCompound([P[n] for n in names if not n.startswith("Eichen")])
allparts_all = Part.makeCompound(list(P.values()))
res = []
for dx in range(0, 421, 60):
    r = cad.fit(laptop, allparts_all, move=(dx, 0, 1.0))   # 1 mm angehoben (Auflage soll nicht als Kontakt zaehlen)
    res.append((dx, r["overlap_mm3"], r["min_distance_mm"]))
print("Laptop-Weg (dx, Ueberlappung, minAbstand):", res)
# Abstand je Teil im Endzustand
near = []
for n, s in P.items():
    d = laptop.distToShape(s)[0]
    if d < 30:
        near.append((n, round(d, 1)))
print("Abstand Winkelstecker-Rueckwand: %.1f mm" % P["Winkelstecker_Platzhalter"].distToShape(P["Rueckwand"])[0])
print("Laptop Endlage, Teile naeher als 30 mm:", sorted(near, key=lambda t: t[1]))

print("=== Kabelwege / Schacht / Durchlass frei? ===")
for nm, bxs in paths.items():
    tot = 0.0
    dmin = 1e9
    for bsh in bxs:
        for n, s in P.items():
            if n in ("Winkelstecker_Platzhalter", "Wand_Steckdose_Platzhalter", "Steckdosenleiste_Platzhalter", "Netzteil_Platzhalter") and nm != "":
                pass
            if bsh.BoundBox.intersect(s.BoundBox):
                tot += bsh.common(s).Volume
    print("[Kabel] %s Ueberlappung gesamt %.2f mm3" % (nm, tot))
for nm, pr in (("Schacht_40x20", shaft_probe), ("Plattendurchlass", hole_probe)):
    tot = sum(pr.common(s).Volume for s in P.values() if pr.BoundBox.intersect(s.BoundBox))
    print("[Kabel] %s Ueberlappung gesamt %.2f mm3" % (nm, tot))

# ---- Zuschnittliste ------------------------------------------------------------
def dims(s):
    bb = s.BoundBox
    d = sorted([bb.XLength, bb.YLength, bb.ZLength], reverse=True)
    return d[0], d[1], d[2]

rows = {}
for n, (mat, t) in META.items():
    l, w, th = dims(P[n])
    key = (mat, round(th), round(l), round(w))
    rows.setdefault(key, []).append(n)
SHEET = (2500.0, 1250.0)
KERF = 4.0

def pack(pieces):
    """Grobe Regalpackung (Streifen entlang 2500), keine Drehung; liefert Plattenzahl."""
    pieces = sorted(pieces, key=lambda p: (-p[1], -p[0]))  # (laenge, breite)
    sheets = []   # je Platte: Liste Streifen [breite, restlaenge]
    for l, w in pieces:
        placed = False
        for sh in sheets:
            for st in sh["strips"]:
                if st[0] >= w and st[1] >= l:
                    st[1] -= l + KERF
                    placed = True
                    break
            if placed:
                break
            rest = SHEET[1] - sum(s_[0] + KERF for s_ in sh["strips"])
            if rest >= w and SHEET[0] >= l:
                sh["strips"].append([w, SHEET[0] - l - KERF])
                placed = True
                break
        if not placed:
            sheets.append({"strips": [[w, SHEET[0] - l - KERF]]})
    return len(sheets)

lines = ["ZUSCHNITTLISTE Couch-Konsole (Masse in mm; Laenge x Breite; Dicke = Plattenstaerke)",
         "Parameter: L=%d, H=%d, Plattentiefe=%d, Wandabstand Rueckwand=%d. Abmasse = Umkantenquader; Ausschnitte/Nuten siehe Hinweise." % (L_TOTAL, H_TOTAL, PLATE_D, GAP_WALL),
         "", "%-4s %-10s %-5s %-12s %s" % ("Stk", "Material", "Dicke", "L x B", "Bauteile")]
mat_pieces = {}
for (mat, th, l, w), ns in sorted(rows.items(), key=lambda kv: (kv[0][0], -kv[0][1], -kv[0][2])):
    lines.append("%-4d %-10s %-5d %-12s %s" % (len(ns), mat, th, "%d x %d" % (l, w), ", ".join(ns)))
    mat_pieces.setdefault((mat, th), []).extend([(l, w)] * len(ns))
lines.append("")
lines.append("PLATTENBEDARF (grob, Regalpackung ohne Drehung, 4 mm Sage, Format %dx%d)" % SHEET)
for (mat, th), pcs in mat_pieces.items():
    if mat == "Multiplex":
        area = sum(l * w for l, w in pcs) / 1e6
        lines.append("  Multiplex %d mm: %d Platten 2500x1250 (Nettoflaeche %.2f m2, Platte 3.125 m2)" % (th, pack(pcs), area))
    else:
        lines.append("  Eiche %d mm: 1 Platte/Bohle %d x %d (Leimholz/Tischlerplatte, 220 mm Breite; Rohmass +10 mm Zugabe)" % (th, pcs[0][0], pcs[0][1]))
lines += ["", "HINWEISE",
          "- Fachboeden sind inkl. 2 x %d mm Nutzapfen gerechnet (Nut %d tief, %d breit in Vorder-/Rueckwand)." % (NUT_T, NUT_T, T12),
          "- Rueckwand: 1 Teil durchgehend 2370 mm (Format 2500 reicht); Ausschnitte: Dose %dx%d, %d Lueftungsschlitze." % (CUT_W, CUT_H, VENT_N),
          "- Boeden/Deckel/Endwaende: Duebel 8x40 oder Konfirmat-Schrauben durch Vorder-/Rueckwand.",
          "- Plattenbefestigung: Z-Laschen/Holzleisten von unten, Langloecher (Holz arbeitet quer).",
          "- Platte: Kabeldurchlass Ø%d bei X=%d, Y=%d." % (HOLE_D, HOLE_CX, HOLE_CY)]
open(os.path.join(OUT_DIR, "zuschnittliste.txt"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
