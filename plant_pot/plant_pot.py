# Pflanztopf mit Wasser-Reservoir — parametrisch (Breite/Tiefe/Höhe frei), Form nach Houdini j::cubepot_copy::2.4.
# Fuge v2 (Joe 14.11.2026: "optisch ein Stück"): statt Konus-Stopfen sitzt der Topf mit flachem Boden
# (erste Schicht, kantenscharf) auf der flachen Randfläche des Reservoirs (Deckschicht). Eine Lippe am
# Reservoir greift in eine Ringnut im Topfboden und zentriert; Nutdecke 45° spitz -> keine Brücke, keine Stützen.
# Konus-Version (Houdini-Nachbau): v001/v002 modell/plant_pot.py.
# Einbaulage: Reservoir z 0..SPLIT, Topf z SPLIT..HEIGHT. Druck: beide aufrecht, Topf mit Boden auf z=0.
import Part, math
from FreeCAD import Vector as V, Matrix

# --- Parameter (mm) ---------------------------------------------------------
# Jeder Parameter lässt sich von außen setzen, ohne die Datei zu ändern:
#   cad run -c 'SIZE_X=150; HEIGHT=120; exec(open("/mnt/raid1/3d_print/tools/freecad/plant_pot/plant_pot.py").read())'
_g = globals()
def P(name, default):
    return _g[name] if name in _g else default

SIZE_X     = P("SIZE_X", 180.0)   # Breite außen
SIZE_Y     = P("SIZE_Y", SIZE_X)  # Tiefe außen (Standard: quadratisch)
HEIGHT     = P("HEIGHT", 140.0)   # Gesamthöhe Baugruppe
DEPTH      = P("DEPTH", 0.75)     # Anteil Topf an der Höhe -> Fuge bei HEIGHT*(1-DEPTH) (wie Houdini)
RES_HEIGHT = P("RES_HEIGHT", None)  # Reservoirhöhe fest vorgeben (None = HEIGHT*(1-DEPTH))
BEVEL      = P("BEVEL", 20.0)     # Radius senkrechte Ecken und Bodenrundung außen
BOTTOM_DROP = P("BOTTOM_DROP", BEVEL / 6)  # Bodenrundung wird so weit unter z=0 abgeschnitten (Auflage breiter)
BOTTOM_45  = P("BOTTOM_45", True) # Bodenrundung unten bis zur 45°-Tangente als Fase auffüllen (kein flacher Überhang)
# Schale (Joe 14.11.: Wandstärke überall gleich, Radien innen/außen konzentrisch)
WALL       = P("WALL", 5.3)       # Wand und Böden von Topf und Reservoir; min = POT_SKIN + Nut + 1,6 (= 5,3)
HOLE_SP    = P("HOLE_SP", 30.0)   # Raster Drainagelöcher
HOLE_R     = P("HOLE_R", 2.5)     # Radius Drainageloch
# Fuge
FIT        = P("FIT", 0.25)       # Spiel an den senkrechten Nutflanken (berühren nicht; Deckellippe P1S, Joe 13.11.)
POT_SKIN   = P("POT_SKIN", 1.6)   # Außenhaut des Topfs neben der Nut (gap-frei 1,6)
LIP_T      = P("LIP_T", 1.6)      # Lippendicke (gap-frei 1,6)
LIP_H      = P("LIP_H", 3.0)      # Lippenhöhe über der Fuge: 0,8 Fase + 2,2 Führung (11 Schichten), mehr zentriert nicht besser
LIP_CH     = P("LIP_CH", 1.0)     # 45°-Zentrierschräge außen an der Lippe (einzige Kontaktfläche der Nut)
FLANK_CLEAR = P("FLANK_CLEAR", 0.0)  # Spiel an der 45°-Schräge (waagerecht); 0 = setzt zugleich mit den Flachseiten auf (wie Gridfinity-Fuß FOOT_PLAY 0,00).
                                     # Bestimmung per Ring-Serie (TEST_FLANKS), Druck macht Nuten enger und Lippen breiter
GROOVE_TOP = P("GROOVE_TOP", 0.4) # Luft über der Lippe in der Nut
SEAM_CH    = P("SEAM_CH", 0.0)    # Fase an beiden Fugenkanten außen (Joe 14.11.: keine Fase, Kante scharf -> Elefantenfuß im Slicer kompensieren)
# Schnurkanal (Aufhängung) je Ecke: Torus, senkrechte Achse, in x gestreckt
CORD_INSET = P("CORD_INSET", 5.05)  # Mitte so weit innerhalb der Außenkante (x und y)
CORD_R     = P("CORD_R", 4.0)     # Ringradius
CORD_SX    = P("CORD_SX", 1.3)    # Streckung in x
CORD_TUBE  = P("CORD_TUBE", 1.6)  # Rohrradius
CORD_DZ    = P("CORD_DZ", 10.0)   # Kanal so weit unter der Fuge
CORD_BOSS  = P("CORD_BOSS", 2.1)  # Rand der Boss-Ellipse um den Kanal; ergibt >= 1,6 Wand zum Wasser (Joe 16.11.: nur wasserdicht, kaum Druck), Verdickung nur innen in der Reservoir-Ecke, unten 45°
CORD_ROOF  = P("CORD_ROOF", 60.0)  # Joe 16.11. (Gießwasser spritzt von der flachen Oberseite zurück): Verdickung oben als Dach, so steil (Grad, 0 = flach)
POUR_FUNNEL = P("POUR_FUNNEL", True)  # Joe 16.11. (Gießöffnung maximal): innere Oberkante des Reservoirs in den Ecken 45° abgeschrägt,
                                      # in Flucht mit der Innenflanke der Lippe -> alles innerhalb des Lippenkamms läuft ins Wasser
POUR_FLAT_MAX = P("POUR_FLAT_MAX", 45.0)  # Regel: unter der Gießöffnung keine Fläche flacher als das (Grad) über der Füllmarke
MIN_WATER_WALL = P("MIN_WATER_WALL", 1.6)  # Mindestwand zwischen Wasserraum und Außenluft (Kanal, Ecken)
# Joe 16.11. (Etsy: geriffelte Töpfe beliebt, "der Pot bleibt flach, es geht nur um die Riffel"): senkrechte Riffel außen,
# auf die glatte Hülle aufgesetzt (Wand 5,3 bleibt überall, Innenleben unverändert), laufen über die Fuge durch
RIFFEL       = P("RIFFEL", True)
RIFFEL_PITCH = P("RIFFEL_PITCH", 3.2)   # Abstand der Riffel (mm, entlang des Umfangs; Anzahl auf Vielfaches von 4 gerundet)
RIFFEL_DEPTH = P("RIFFEL_DEPTH", 1.0)   # Höhe Kamm über Tal (mm); Kosinusprofil, Außenmaß wächst um 2x DEPTH
RIFFEL_RAMP  = P("RIFFEL_RAMP", 8.0)    # unten in der Bodenrundung so lang einblenden (mm Höhe) -> Überhang bleibt < 45°
# Hub-Bajonett (Joe 14.11.): Topf gerade aus der Nut heben, 45° drehen -> Rampen heben ihn weiter, rastet stabil ein
LIFT       = P("LIFT", True)
# Joe 15.11.: "erst heben, dann drehen" ist nicht intuitiv -> Lippe als flaches Trapez (45° beidseitig) und V-Kerben:
# Drehen allein hebt den Topf (45°-Flanken gleiten hoch), kein senkrechter Hub mehr nötig.
LIP_V      = P("LIP_V", True)
LIP_TOP    = P("LIP_TOP", 0.4)    # Lippe oben flach (V-Lippe); Höhe = (Basis - LIP_TOP) / 2
LIP_CI     = P("LIP_CI", 0.2)     # V-Lippe: waagerechte Luft an der Innenflanke (Außenflanke: FLANK_CLEAR, zentriert)
STL_LIN    = P("STL_LIN", 0.005)  # STL-Sehnenfehler mm (R20: 1,3° pro Facette, Sehne 0,45 mm)
STL_FACET_MAX = P("STL_FACET_MAX", 100.0)  # Regel: höchstens so viel mm sichtbare Facettenkanten je STL (v015: Topf 14 m, v016: 0)
STL_ANG    = P("STL_ANG", 0.05)   # STL-Winkel rad (2,9°); 0,02 machte das Reservoir 43 MB (Schnurkanal-Tori)
CAM_R      = P("CAM_R", None)     # Außenradius des Kurvenrings (groß = stabile Auflage auf 45°); None = min(60, halbe Innenbreite - 5)
CAM_T      = P("CAM_T", 1.6)      # Wand des Kurvenrings im Reservoir (gap-frei mit 2 Wandlinien; 2,4 bräuchte 3)
CAM_CL     = P("CAM_CL", 0.4)     # radiale Luft Ring <-> Kanal im Topf
CAM_TEETH  = P("CAM_TEETH", 4)    # Zähne im Topf (bei 0/90/180/270°, mittig über den Seiten)
TOOTH_R    = P("TOOTH_R", 3.0)    # Joe 15.11. (Drehen ruckelt über die Layerstufen der Rampe): Zahnspitze rund, gleitet über die
                                  # Stufenkanten statt hineinzufallen (Rest-Holpern ~ Stufenlänge² / 8R). 0 = spitzes 45°-V
FUZZY      = P("FUZZY", False)    # Fuzzy-Skin-Bereiche in die slicer_*.json schreiben (Joe 16.11.: kann weg)
FEIN_TOPF  = P("FEIN_TOPF", False)  # Joe 16.11.: 0,1-mm-Schichten unten am Topf sieht man an der Außenwand (Schichthöhe gilt je Schicht fürs ganze Teil).
                                    # Aus: am Topf gleitet auf der Rampe immer dieselbe Stelle der runden Zahnspitze, die Stufen der Rampe (Reservoir, fein) zählen
TOOTH_W    = P("TOOTH_W", None)   # Zahnbreite (tangential), Unterseite 45°-V mit runder Spitze (None = 6 bei rundem Zahn, sonst 4)
CAM_ZT     = P("CAM_ZT", 0.5)     # Zahnspitze über der Fuge (Topf aufgesetzt)
CAM_C      = P("CAM_C", 0.3)      # Luft Zahn <-> Kerbengrund im aufgesetzten Zustand (Topf liegt auf Fuge, nicht auf Zähnen)
CAM_L1     = P("CAM_L1", None)    # gerader Hub bis die Lippe frei ist (None = LIP_H + 0,3)
CAM_H2     = P("CAM_H2", 4.0)     # zusätzlicher Hub durch die 45°-Drehung
CAM_DET    = P("CAM_DET", 0.5)    # Tiefe der Rastmulde (45°-V) am Rampenende
CAM_TURN   = P("CAM_TURN", 45.0)  # Drehwinkel bis zur Rast
CAM_NOTCH_CL = P("CAM_NOTCH_CL", 0.15)  # tangentiale Luft Zahn <-> Kerbe je Seite (eng: richtet die Drehung vor dem Einfädeln der Lippe aus)
CAM_FUNNEL = P("CAM_FUNNEL", 1.0)  # 45°-Trichter oben an der Kerbe
CAM_COVER  = P("CAM_COVER", 1.2)   # Material über dem Kanaldach bis zur Topf-Bodenfläche (Topf muss nicht dicht sein)
POT_FLOOR  = P("POT_FLOOR", None)  # Topfboden (None = WALL, oder dicker, wenn das Bajonett Platz braucht; innen glatt, kein Wulst)
CAM_WIN    = P("CAM_WIN", (8.0, 5.0))  # Wasserfenster unten im Ring (Breite, Höhe bis Dachansatz)
# Dochtkorb (Joe 14.11.: Selbstbewässerung über Erdsäule in der Mitte statt Fäden)
WICK       = P("WICK", True)
WICK_R     = P("WICK_R", None)    # Korb außen oben (None = 30, bei kleinen Töpfen kleiner) (Öffnung im Topfboden = WICK_R + WICK_FIT)
WICK_RB    = P("WICK_RB", None)   # Korb außen unten (None = WICK_R - 4)
WICK_T     = P("WICK_T", 1.6)     # Korbwand / -boden (gap-frei)
WICK_FIT   = P("WICK_FIT", 0.3)   # radiale Luft Korb <-> Öffnung
WICK_COLLAR = P("WICK_COLLAR", 3.0)  # 45°-Kegelkragen oben (Senkung im Topfboden), bündig mit der Bodenfläche
WICK_GAP   = P("WICK_GAP", 3.0)   # Korbboden über Reservoirboden (aufgesetzt)
WICK_SLOTS = P("WICK_SLOTS", 24)  # senkrechte Schlitze im Korbteil unter dem Topfboden
WICK_SLOT_W = P("WICK_SLOT_W", 2.0)
FILL_DZ    = P("FILL_DZ", 10.0)   # Füllmarke so weit unter der Fuge (Luftspalt unter dem Topfboden)
FILL_MARK  = P("FILL_MARK", (10.0, 1.0, 0.6, 30.0))  # Kerbe: Länge, Höhe, Tiefe, Abstand Mitte von der Außenecke (entlang der Seite)
TEST       = P("TEST", True)      # Fugen-Testringe (volle Kontur, flach) mit ausgeben
TEST_FLANKS = P("TEST_FLANKS", (0.0, 0.05, 0.1))  # FLANK_CLEAR-Serie für die Topf-Testringe
TEST_POT_H = P("TEST_POT_H", 6.0)  # Höhe Topf-Testring (Nut + Dach + Rest)
TEST_RES_H = P("TEST_RES_H", 4.0)  # Reservoir-Testring: so viel Wand unter der Fuge (+ Lippe)
BODEN_PROBE = P("BODEN_PROBE", 12.0)  # Joe 15.11. (Linie außen auf Bodenhöhe): Topf-Unterteil bis Bodenoberkante + so viel Wand als Probe-STL (0 = aus)
NAME       = P("NAME", None)      # Dateiname-Zusatz; None = <Breite>x<Tiefe>x<Höhe>

HX, HY = SIZE_X / 2, SIZE_Y / 2
TOOTH_W = (6.0 if TOOTH_R else 4.0) if TOOTH_W is None else TOOTH_W
assert TOOTH_W / 2 >= TOOTH_R * math.sin(math.radians(45)) - 1e-9, "TOOTH_W zu schmal für TOOTH_R"
SPLIT = RES_HEIGHT if RES_HEIGHT is not None else HEIGHT * (1 - DEPTH)
LIP_IN = POT_SKIN + FIT                 # Lippe beginnt so weit innerhalb der Außenwand (= Breite der Auflagefläche)
LIP_OUT = LIP_IN + LIP_T                # Lippe innen
if LIP_V:   # Nut = V zwischen Außenhaut POT_SKIN und Innenhaut 1,6; Lippe = Trapez darin
    G_O, G_I = POT_SKIN, WALL - 1.6     # Nutflanken an der Fuge (Einzug)
    LIP_IN, LIP_OUT = G_O + FLANK_CLEAR, G_I - LIP_CI
    LIP_T = LIP_OUT - LIP_IN
    LIP_H = LIP_CH = (LIP_T - LIP_TOP) / 2
CORD_Z = SPLIT - CORD_DZ
CAM_L1 = LIP_H + 0.3 if CAM_L1 is None else CAM_L1
CAM_R = min(60.0, min(HX, HY) - 2 * WALL - 2.5 - CAM_CL) if CAM_R is None else CAM_R   # skaliert mit der Topfgröße (Grenze: Assert Kanal)
CAM_RI = CAM_R - CAM_T                   # Innenradius Kurvenring
CH_RI, CH_RO = CAM_RI - CAM_CL, CAM_R + CAM_CL   # Ringkanal im Topf
NAME = NAME or "%gx%gx%g" % (SIZE_X, SIZE_Y, HEIGHT)
if WICK_R is None:   # Dochtkorb so groß wie möglich, max 30, innerhalb des Ringkanals
    WICK_R = min(30.0, (CH_RI - 1.6 - WICK_FIT - WICK_COLLAR - 1.0) if LIFT else 30.0)
WICK_RB = WICK_R - 4.0 if WICK_RB is None else WICK_RB
assert SPLIT >= BEVEL - BOTTOM_DROP, "Fuge liegt in der Bodenrundung (Reservoir höher machen)"
assert SPLIT - WALL > 5, "Reservoir zu flach"
assert not (LIFT and WICK) or CH_RI - 1.6 >= WICK_R + WICK_FIT + WICK_COLLAR + 1.0 - 1e-6, "Dochtkorb kollidiert mit dem Ringkanal (WICK_R kleiner)"
assert WALL < BEVEL, "WALL muss kleiner als BEVEL sein (konzentrische Innenradien)"
if LIP_V:
    assert LIP_H >= 0.5, "V-Lippe zu niedrig (%.2f mm, WALL zu dünn)" % LIP_H
else:
    assert WALL >= LIP_OUT + FIT + 1.6 - 1e-6, "WALL zu dünn für die Nut (Innenhaut < 1,6)"
    assert LIP_T - LIP_CH >= 0.4, "Lippe oben zu schmal (LIP_T - LIP_CH < 0,4)"
    assert LIP_H > LIP_CH + 0.6, "Lippe zu niedrig für die Schräge"


def rr(inset, z, r=None):
    """Gerundetes Rechteck: Außenkontur um inset nach innen versetzt, Eckradius r (Standard BEVEL-inset), Höhe z."""
    r = BEVEL - inset if r is None else r
    cx, cy = HX - inset - r, HY - inset - r
    sq = Part.makePlane(2 * cx, 2 * cy, V(-cx, -cy, z))
    return sq.makeOffset2D(r, join=0).OuterWire


def prism(wire, z0, z1):
    f = Part.Face(wire)
    f.translate(V(0, 0, z0 - wire.BoundBox.ZMin))
    return f.extrude(V(0, 0, z1 - z0))


def loft(*wires):
    return Part.makeLoft(list(wires), True, True)


def slab(z0, z1):
    return Part.makeBox(SIZE_X + 20, SIZE_Y + 20, z1 - z0, V(-HX - 10, -HY - 10, z0))


def band(i0, i1, z0, z1):
    """Ring zwischen Einzug i0 (außen) und i1 (innen), senkrecht."""
    return prism(rr(i0, 0), z0, z1).cut(prism(rr(i1, 0), z0 - 1, z1 + 1))


# --- Grundkörper: Kernquader + 3D-Offset BEVEL (runde Ecken, Kugel-Ecken unten) ---
core_z0 = -BOTTOM_DROP + BEVEL
cx, cy = HX - BEVEL, HY - BEVEL
core = Part.makeBox(2 * cx, 2 * cy, HEIGHT + BEVEL - core_z0, V(-cx, -cy, core_z0))
base = core.makeOffsetShape(BEVEL, 1e-3, join=0)
inner = core.makeOffsetShape(BEVEL - WALL, 1e-3, join=0)   # Innenfläche: gleiche Kernform, Radien = Außen - WALL

# --- Topf (Einbaulage z SPLIT..HEIGHT) -----------------------------------------
pot = base.common(slab(SPLIT, HEIGHT))
if SEAM_CH > 0:
    pot = pot.common(loft(rr(SEAM_CH, SPLIT), rr(0, SPLIT + SEAM_CH)).fuse(prism(rr(0, 0), SPLIT + SEAM_CH, HEIGHT + 1)))
if LIFT:
    _h_t = SPLIT + CAM_ZT + CAM_L1 + CAM_H2
    _need = (_h_t + 0.4 + (CH_RO - CH_RI) / 2 + CAM_COVER) - SPLIT
    POT_FLOOR = max(WALL, _need) if POT_FLOOR is None else POT_FLOOR
    assert POT_FLOOR >= _need - 1e-6, "POT_FLOOR zu dünn für das Bajonett (%.2f nötig)" % _need
else:
    POT_FLOOR = WALL if POT_FLOOR is None else POT_FLOOR
cav = inner.common(slab(SPLIT + POT_FLOOR, HEIGHT + 1))
def make_groove(fc):
    """Ringnut im Topfboden. Außenflanke: senkrecht mit FIT Spiel, oben 45° = Lippenschräge + fc (Zentrierung);
    Innenflanke senkrecht mit FIT Spiel; Dach 45° (keine Brücke).
    LIP_V: V-Nut, beide Flanken 45° ab der Fuge (Außenflanke um fc weiter außen als die Lippe), Scheitel 90°."""
    if LIP_V:
        o, i, H = LIP_IN - fc, G_I, 3.0
        A = loft(rr(o - 1, SPLIT - 1), rr(o + H, SPLIT + H))      # innerhalb der Außenflanke
        B = loft(rr(i + 1, SPLIT - 1), rr(i - H, SPLIT + H))      # innerhalb der Innenflanke
        za = SPLIT + (i - o) / 2
        return A.cut(B).common(slab(SPLIT - 1, za + 1)).removeSplitter(), za
    g0, g1 = LIP_IN - FIT, LIP_OUT + FIT
    zf0 = SPLIT + LIP_H - LIP_CH                   # Beginn der Lippenschräge
    z1 = zf0 - FIT + fc                            # dort trifft die 45°-Flanke die senkrechte Außenwand der Nut
    zt = SPLIT + LIP_H + GROOVE_TOP                # Innenflanke senkrecht bis über die Lippe
    za = (g1 - g0 + z1 + zt) / 2                   # Scheitel: Außenflanke (45° nach innen) trifft Dach (45° nach außen)
    ia = g0 + (za - z1)
    outer = prism(rr(g0, 0), SPLIT - 1, z1).fuse(loft(rr(g0, z1), rr(ia - 0.05, za)))
    innr = prism(rr(g1, 0), SPLIT - 2, zt).fuse(loft(rr(g1, zt), rr(ia + 0.05, za)))
    return outer.cut(innr).removeSplitter(), za

HOLE_MARGIN = HOLE_R + 2.0   # Lochmitte mindestens so weit von der Innenwand (auch in den Ecken)
nx = int((HX - WALL - HOLE_MARGIN) // HOLE_SP)
ny = int((HY - WALL - HOLE_MARGIN) // HOLE_SP)

def _in_floor(x, y):
    ex, ey = max(abs(x) - (HX - BEVEL), 0), max(abs(y) - (HY - BEVEL), 0)   # Abstand über die Eckmitte hinaus
    return math.hypot(ex, ey) <= BEVEL - WALL - HOLE_MARGIN

holes = [Part.makeCylinder(HOLE_R, POT_FLOOR + 2, V(i * HOLE_SP, j * HOLE_SP, SPLIT - 1))
         for i in range(-nx, nx + 1) for j in range(-ny, ny + 1) if _in_floor(i * HOLE_SP, j * HOLE_SP)]
if LIFT:   # Löcher, die den Ringkanal treffen würden, weglassen
    holes = [h for h in holes if not ((CH_RI - 1.2) < math.hypot(h.BoundBox.Center.x, h.BoundBox.Center.y) + HOLE_R
                                      and math.hypot(h.BoundBox.Center.x, h.BoundBox.Center.y) - HOLE_R < (CH_RO + 1.2))]
if WICK:   # Löcher in der Korböffnung samt Senkung weglassen (die Öffnung ersetzt sie)
    holes = [h for h in holes if math.hypot(h.BoundBox.Center.x, h.BoundBox.Center.y) - HOLE_R > WICK_R + WICK_COLLAR + 1]
pot_body = pot.cut(cav).cut(Part.makeCompound(holes))    # ohne Nut (für Testringe)
groove, groove_top = make_groove(FLANK_CLEAR)
pot = pot_body.cut(groove).removeSplitter()

# --- Riffel außen (senkrecht, folgen unten der Bodenrundung) -------------------
RIFFEL_N = 0
def riffel_wire(inset, z, amp):
    """Kontur rr(inset) mit Riffeln nach außen: je Riffel ein Kreisbogen (Tal -> Kamm -> Tal, Täler 0,05 in der Wand),
    analytische Flächen statt BSpline (BSpline-Variante: fuse 860 s, ungültig). Parametrisierung nach Umfangsanteil,
    damit jede Riffel in allen Höhen dieselbe Nummer behält (senkrecht; in der Bodenrundung laufen sie leicht zusammen)."""
    r = BEVEL - inset
    cx, cy = HX - BEVEL, HY - BEVEL
    segs = [("l", (cx + r, 0), (0, 1), cy), ("a", (cx, cy), 0.0, r * math.pi / 2), ("l", (cx, cy + r), (-1, 0), 2 * cx),
            ("a", (-cx, cy), 90.0, r * math.pi / 2), ("l", (-cx - r, cy), (0, -1), 2 * cy), ("a", (-cx, -cy), 180.0, r * math.pi / 2),
            ("l", (-cx, -cy - r), (1, 0), 2 * cx), ("a", (cx, -cy), 270.0, r * math.pi / 2), ("l", (cx + r, -cy), (0, 1), cy)]
    L = sum(sg[3] for sg in segs)
    def pt(t, f):
        s = L * (t % 1.0)
        for kind, p0, d, ln in segs:
            if s <= ln + 1e-9:
                break
            s -= ln
        if kind == "l":
            x, y = p0[0] + d[0] * s, p0[1] + d[1] * s; nx_, ny_ = d[1], -d[0]
        else:
            a = math.radians(d) + s / r; nx_, ny_ = math.cos(a), math.sin(a); x, y = p0[0] + r * nx_, p0[1] + r * ny_
        return V(x + nx_ * f, y + ny_ * f, z)
    N = RIFFEL_N
    vs = [pt(i / N, -0.05) for i in range(N)]
    edges = [Part.Arc(vs[i], pt((i + 0.5) / N, max(amp, 0.02)), vs[(i + 1) % N]).toShape() for i in range(N)]
    return Part.Wire(edges)

ribs = None
if RIFFEL:
    _L0 = 4 * (HX - BEVEL) + 4 * (HY - BEVEL) + 2 * math.pi * BEVEL
    RIFFEL_N = max(4, int(round(_L0 / RIFFEL_PITCH / 4)) * 4)
    _zt = core_z0 - BEVEL * math.cos(math.radians(45))      # Ende der 45°-Fase unten
    _z0 = max(_zt, 0.0) + 2.0                                # Start: Bodenrundung hier < 45° (Rippenanstieg kommt dazu)
    def _ins(z):   # Einzug der Kugel-Bodenrundung in Höhe z
        u = core_z0 - z
        return BEVEL - math.sqrt(max(BEVEL ** 2 - u * u, 0.0)) if u > 0 else 0.0
    _zs = [_z0 + k * (core_z0 - _z0) / max(1, int(math.ceil(core_z0 - _z0))) for k in range(int(math.ceil(core_z0 - _z0)) + 1)]
    _secs = [riffel_wire(_ins(z), z, RIFFEL_DEPTH * min(1.0, (z - _z0) / RIFFEL_RAMP)) for z in _zs]
    _top = riffel_wire(0.0, HEIGHT, RIFFEL_DEPTH)
    # Rampe bis core_z0 nicht ganz eingeblendet? dann im geraden Teil fertig einblenden
    if core_z0 - _z0 < RIFFEL_RAMP:
        _zr = _z0 + RIFFEL_RAMP
        ribs = Part.makeLoft(_secs + [riffel_wire(0.0, _zr, RIFFEL_DEPTH)], True, False).fuse(prism(_top, _zr, HEIGHT))
    else:
        ribs = Part.makeLoft(_secs, True, False).fuse(prism(_top, core_z0, HEIGHT))
    # nur als Haut: innen 1 mm unter der glatten Außenfläche abschneiden (innerhalb POT_SKIN, Nut/Löcher/Kanäle bleiben frei)
    ribs = ribs.cut(core.makeOffsetShape(BEVEL - 1.0, 1e-3, join=0)).removeSplitter()
    pot = pot.fuse(ribs.common(slab(SPLIT, HEIGHT))).removeSplitter()
    print("Riffel: %d Stück, Abstand %.2f mm, Tiefe %.1f mm, ab z %.1f, Außenmaß %.1f x %.1f" % (
        RIFFEL_N, _L0 / RIFFEL_N, RIFFEL_DEPTH, _z0, SIZE_X + 2 * RIFFEL_DEPTH, SIZE_Y + 2 * RIFFEL_DEPTH))

# --- Reservoir (z 0..SPLIT, Lippe bis SPLIT+LIP_H) ----------------------------
res = base.common(slab(0, SPLIT))
if BOTTOM_45:
    zt = core_z0 - BEVEL * math.cos(math.radians(45))   # Höhe der 45°-Tangente
    it = BEVEL * (1 - math.sin(math.radians(45)))       # Einzug dort
    if zt > 0:
        res = res.fuse(loft(rr(it + zt, 0), rr(it, zt)))
if SEAM_CH > 0:
    res = res.common(prism(rr(0, 0), -1, SPLIT - SEAM_CH).fuse(loft(rr(0, SPLIT - SEAM_CH), rr(SEAM_CH, SPLIT))))
if LIP_V:   # Trapez: beide Flanken 45° ab der Fuge
    lip = loft(rr(LIP_IN - 1, SPLIT - 1), rr(LIP_IN + LIP_H + 1, SPLIT + LIP_H + 1)).cut(
        loft(rr(LIP_OUT + 1, SPLIT - 1), rr(LIP_OUT - LIP_H - 1, SPLIT + LIP_H + 1))).common(slab(SPLIT - 0.5, SPLIT + LIP_H))
else:
    lip = band(LIP_IN, LIP_OUT, SPLIT - 0.5, SPLIT + LIP_H - LIP_CH).fuse(
        loft(rr(LIP_IN, SPLIT + LIP_H - LIP_CH), rr(LIP_IN + LIP_CH, SPLIT + LIP_H)).cut(
            prism(rr(LIP_OUT, 0), SPLIT + LIP_H - LIP_CH - 1, SPLIT + LIP_H + 1)))
res_cav = inner.common(slab(WALL, SPLIT + LIP_H + 1))
# Schnurkanal: Torus; Verdickung (Boss) nur dort, wo er in den Wasserraum ragen würde, Unterseite 45° (druckbar)
m = Matrix(); m.scale(CORD_SX, 1, 1)
# Boss = enge Ellipse um den gestreckten Kanal: Halbachsen = Kanal-Außenmaß + CORD_BOSS (Streckung nur auf den Ring, nicht auf die Wand)
rb = CORD_R + CORD_TUBE + CORD_BOSS                 # Halbachse y
bsx = (CORD_R * CORD_SX + CORD_TUBE + CORD_BOSS) / rb   # Streckung des Boss in x
hb = CORD_TUBE + CORD_BOSS                          # halbe Boss-Höhe
tor = Part.makeTorus(CORD_R, CORD_TUBE).transformGeometry(m)
mb = Matrix(); mb.scale(bsx, 1, 1)
boss0 = Part.makeCylinder(rb, 2 * hb, V(0, 0, -hb)).fuse(
    Part.makeCone(0, rb, rb * bsx, V(0, 0, -hb - rb * bsx))).transformGeometry(mb)  # Kegelhöhe x Streckung -> nach Streckung >= 45°
if CORD_ROOF:   # Dach: Kegel, nach der Streckung in x mindestens CORD_ROOF steil (in y steiler)
    boss0 = boss0.fuse(Part.makeCone(rb, 0, rb * bsx * math.tan(math.radians(CORD_ROOF)), V(0, 0, hb)).transformGeometry(mb))
cords, bosses = [], []
for sx in (-1, 1):
    for sy in (-1, 1):
        d = V(sx * (HX - CORD_INSET), sy * (HY - CORD_INSET), CORD_Z)
        t = tor.copy(); t.translate(d); cords.append(t)
        b = boss0.copy(); b.translate(d); bosses.append(b)
cords = Part.makeCompound(cords)
bosses = Part.makeCompound(bosses).common(res).common(slab(WALL, SPLIT))
reservoir = res.fuse(lip).removeSplitter().cut(res_cav).fuse(bosses).removeSplitter()
if ribs is not None:   # vor dem Schnurkanal, damit die Kanalöffnungen in den Ecken frei durch die Riffel gehen
    reservoir = reservoir.fuse(ribs.common(slab(-1, SPLIT))).removeSplitter()
reservoir = reservoir.cut(cords).removeSplitter()
pour_open = None
if POUR_FUNNEL or POUR_FLAT_MAX:   # Gießöffnung = innerhalb des Lippenkamms, außerhalb des um CAM_TURN gedrehten Topfs
    _ol = Part.Face(rr(0, 0)); _ol.rotate(V(0, 0, 0), V(0, 0, 1), CAM_TURN if LIFT else 45.0)
    pour_open = Part.Face(rr(LIP_IN + LIP_H + LIP_TOP if LIP_V else LIP_OUT, 0)).cut(_ol)
if POUR_FUNNEL:
    assert LIP_V, "POUR_FUNNEL setzt die V-Lippe voraus (Trichter in Flucht mit der Innenflanke)"
    d_f = WALL - LIP_OUT + 6.0   # tief genug: der flache Boden des Schneidkörpers darf die Verdickung nicht treffen
    funnel = loft(rr(LIP_OUT + d_f, SPLIT - d_f), rr(LIP_OUT, SPLIT))     # 45°, Verlängerung der Lippen-Innenflanke
    _ol3 = prism(_ol.OuterWire, SPLIT - d_f - 1, SPLIT + 1)
    funnel = funnel.cut(_ol3)
    reservoir = reservoir.cut(funnel).removeSplitter()
cav_real = res_cav.cut(bosses)
cord_wall = min(t.distToShape(cav_real)[0] for t in cords.Solids)
assert cord_wall >= MIN_WATER_WALL - 0.05, "Schnurkanal zu nah am Wasserraum (%.2f mm, CORD_BOSS erhöhen)" % cord_wall

# --- Hub-Bajonett ---------------------------------------------------------------
def revolve_profile(pts):
    """Polygon (r, z) um die Z-Achse drehen."""
    w = Part.makePolygon([V(r, 0, z) for r, z in pts] + [V(pts[0][0], 0, pts[0][1])])
    return Part.Face(w).revolve(V(0, 0, 0), V(0, 0, 1), 360)

def cam_profile():
    """Kurvenbahn als Liste (Winkel°, Höhe) über 360°, Zähne bei 0/90/..: Kerbe, senkrechte Wand, Rampe, Rast-V."""
    rm = (CAM_R + CAM_RI) / 2
    zt = SPLIT + CAM_ZT
    a_n = math.degrees((TOOTH_W / 2 + CAM_NOTCH_CL) / rm)   # halbe Kerbenbreite (eng)
    a_f = math.degrees(CAM_FUNNEL / rm)                     # Trichter oben
    a_d = math.degrees(CAM_DET / rm)                     # halbe Breite der Rastmulde (45°-V)
    a_l = math.degrees((TOOTH_W / 2 + 1.0) / rm)         # halbe Rastplateau-Breite
    h_n, h_s, h_t = zt - CAM_C, zt + CAM_L1 - 0.1, zt + CAM_L1 + CAM_H2
    period = 360.0 / CAM_TEETH
    half = period / 2
    assert CAM_TURN <= half, "CAM_TURN größer als halbe Zahnteilung"
    turn = CAM_TURN
    # eine Seite von 0 bis half (Rast bei turn; bei turn == half symmetrisch)
    if LIP_V and TOOTH_R:   # Kerbe = Zahnkontur + CAM_C (Bogen R+CAM_C, dann 45°), Rastmulde 90°-V, in die der runde Zahn CAM_DET tief fällt
        R = TOOTH_R + CAM_C; zc_ = zt + TOOTH_R
        arc = [(R * math.sin(math.radians(b)), zc_ - R * math.cos(math.radians(b))) for b in range(0, 46, 5)]
        x45, z45 = arc[-1]
        assert h_s > z45 + 0.05, "Kerbe: 45°-Flanke zu kurz (CAM_L1 größer oder TOOTH_R kleiner)"
        d_v = CAM_DET + TOOTH_R * (math.sqrt(2) - 1)       # V-Tiefe, damit die runde Spitze CAM_DET tief einsinkt
        a_d = math.degrees(d_v / rm)
        assert a_d < a_l, "Rastmulde breiter als das Plateau"
        seg = [(math.degrees(x / rm), z) for x, z in arc] + [(math.degrees((x45 + h_s - z45) / rm), h_s),
               (turn - a_l, h_t), (turn - a_d, h_t), (turn, h_t - d_v)]
    elif LIP_V:   # V-Kerbe 45° (parallel zur Zahn-Unterseite, CAM_C Luft): Drehen hebt sofort
        a_v = math.degrees((h_s - h_n) / rm)
        seg = [(0, h_n), (a_v, h_s), (turn - a_l, h_t), (turn - a_d, h_t), (turn, h_t - CAM_DET)]
    else:
        seg = [(0, h_n), (a_n, h_n), (a_n, h_s - CAM_FUNNEL), (a_n + a_f, h_s), (turn - a_l, h_t), (turn - a_d, h_t), (turn, h_t - CAM_DET)]
    if turn < half:
        seg += [(turn + a_d, h_t), (half, h_t)]
    left = [(-a, h) for a, h in reversed(seg[1:])]
    one = left + seg                                     # -half .. +half (Mitte = Zahn)
    pts = []
    for k in range(CAM_TEETH):
        for a, h in one:
            pts.append((a + k * period, h))
    # Dubletten an den Periodengrenzen entfernen, feine Unterteilung auf schrägen Stücken
    out = []
    for a, h in pts:
        if out and abs(a - out[-1][0]) < 1e-9 and abs(h - out[-1][1]) < 1e-9:
            continue
        if out and a - out[-1][0] > 2.0:
            a0, h0 = out[-1]; n = int(math.ceil((a - a0) / 2.0))
            for i in range(1, n):
                out.append((a0 + (a - a0) * i / n, h0 + (h - h0) * i / n))
        out.append((a, h))
    if abs(out[-1][0] - out[0][0] - 360) < 1e-9 and abs(out[-1][1] - out[0][1]) < 1e-9:
        out.pop()
    return out, (h_n, h_s, h_t)

def cam_ring(z_bot):
    """Kurvenring als Solid aus Viereck-/Dreiecksflächen (Oberkante = Kurvenbahn)."""
    prof, _ = cam_profile()
    n = len(prof)
    P_ = lambda r, a, z: V(r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), z)
    faces = []
    def poly(*pp):
        pp = [p for i, p in enumerate(pp) if (p - pp[i - 1]).Length > 1e-7]
        if len(pp) >= 3:
            faces.append(Part.Face(Part.makePolygon(list(pp) + [pp[0]])))
    for i in range(n):
        a1, h1 = prof[i]; a2, h2 = prof[(i + 1) % n]
        if i == n - 1: a2 += 360
        ri, ro = CAM_RI, CAM_R
        # Oberseite (verdrehtes Viereck -> zwei Dreiecke)
        poly(P_(ri, a1, h1), P_(ro, a1, h1), P_(ro, a2, h2))
        poly(P_(ri, a1, h1), P_(ro, a2, h2), P_(ri, a2, h2))
        if abs(a2 - a1) > 1e-9:
            poly(P_(ro, a1, z_bot), P_(ro, a2, z_bot), P_(ro, a2, h2), P_(ro, a1, h1))
            poly(P_(ri, a1, z_bot), P_(ri, a1, h1), P_(ri, a2, h2), P_(ri, a2, z_bot))
            poly(P_(ri, a1, z_bot), P_(ri, a2, z_bot), P_(ro, a2, z_bot), P_(ro, a1, z_bot))
    shell = Part.Shell(faces)
    sol = Part.Solid(shell)
    if sol.Volume < 0: sol.reverse()
    return sol

def regel_drehweg():
    """Sicherheitsregel (Joe 15.11.: Drehen ohne vorheriges Anheben). Jeder Abschnitt der Kurvenbahn, den ein Zahn
    beim Drehen hochgleitet, höchstens 45° steil (am Ringmittel); senkrechte Stücke = man muss heben."""
    if not LIFT:
        return
    assert LIP_V, "REGEL Drehweg: Lippe mit senkrechten Flanken blockiert das Drehen (LIP_V=True)"
    rm = (CAM_R + CAM_RI) / 2
    prof, _ = cam_profile()
    for (a1, h1), (a2, h2) in zip(prof, prof[1:]):
        arc = math.radians(a2 - a1) * rm
        steil = abs(h2 - h1) / arc if arc > 1e-9 else float("inf")
        assert steil <= 1.0 + 1e-6, "REGEL Drehweg: Kurvenbahn bei %.1f° steiler als 45° (%.2f) -> Topf muss angehoben werden" % (a1, steil)

def _sdf(x, y):
    """Vorzeichenbehafteter Abstand zur Außenkontur (gerundetes Rechteck, Radius BEVEL); Einzüge = Niveaulinien (konzentrisch)."""
    qx, qy = abs(x) - (HX - BEVEL), abs(y) - (HY - BEVEL)
    return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - BEVEL

def _kontur(inset, n_arc=24, step=1.0):
    """Punkte auf der Kontur mit Einzug inset (Seiten in step-mm-Schritten, Ecken mit n_arc Punkten)."""
    cx, cy, rho = HX - BEVEL, HY - BEVEL, BEVEL - inset
    pts = []
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        for k in range(n_arc + 1):
            al = math.radians(90 * k / n_arc)
            pts.append((sx * (cx + rho * math.cos(al)), sy * (cy + rho * math.sin(al))))
    for t in [i * step for i in range(-int(cx / step), int(cx / step) + 1)]:
        pts += [(t, HY - inset), (t, -(HY - inset))]
    for t in [i * step for i in range(-int(cy / step), int(cy / step) + 1)]:
        pts += [(HX - inset, t), (-(HX - inset), t)]
    return pts

def drehweg(theta):
    """Schnelle Rechnung (ms statt Minuten Booleans): Hub des Topfs über der Einbaulage bei Drehung theta° (Topf gegen
    Reservoir). Zähne: Kurvenbahn minus Zahnkontur am Ringmittel. Lippe: wie weit sich ihre Flanken beim Drehen in die
    45°-Nutflanken schieben (begrenzt auf die Lippenhöhe). Rückgabe (Hub, Zähne, Lippe)."""
    rm = (CAM_R + CAM_RI) / 2
    prof, _ = cam_profile()
    angs = [a for a, _h in prof] + [prof[0][0] + 360]; hs = [h for _a, h in prof] + [prof[0][1]]
    def cam(a):
        a = (a - angs[0]) % 360 + angs[0]
        for i in range(len(angs) - 1):
            if angs[i] <= a <= angs[i + 1]:
                f = (a - angs[i]) / (angs[i + 1] - angs[i]) if angs[i + 1] > angs[i] else 0
                return hs[i] + f * (hs[i + 1] - hs[i])
        return hs[-1]
    tz = SPLIT + CAM_ZT; s45 = math.sin(math.radians(45))
    def tooth(x):
        if TOOTH_R and abs(x) <= TOOTH_R * s45:
            return tz + TOOTH_R - math.sqrt(TOOTH_R ** 2 - x * x)
        if TOOTH_R:
            return tz + TOOTH_R * (1 - s45) + (abs(x) - TOOTH_R * s45)
        return tz + abs(x)
    n = 200
    l_t = max(cam(theta + math.degrees(x / rm)) - tooth(x) for x in [-TOOTH_W / 2 + TOOTH_W * i / n for i in range(n + 1)])
    c, s_ = math.cos(math.radians(-theta)), math.sin(math.radians(-theta))
    d_out = d_in = 0.0
    for ins in (LIP_IN, LIP_IN + LIP_H):
        for x, y in _kontur(ins):
            d = _sdf(c * x - s_ * y, s_ * x + c * y) - _sdf(x, y)
            d_out, d_in = max(d_out, d), max(d_in, -d)
    l_l = min(max(d_out - FLANK_CLEAR, d_in - LIP_CI, 0.0), LIP_H)
    return max(l_t, l_l, 0.0), l_t, l_l

if LIFT:
    regel_drehweg()
    _, (h_n, h_s, h_t) = cam_profile()
    assert CH_RO + WALL < min(HX, HY) - WALL - 2, "Kurvenring zu groß für den Topf"
    # Reservoir: Kurvenring auf dem Boden, unten Wasserfenster (Dach 45°)
    ring = cam_ring(WALL - 0.5)
    ww, wh = CAM_WIN
    wins = []
    for k in range(CAM_TEETH):
        a = (k + 0.5) * 360.0 / CAM_TEETH
        prof = [(-ww / 2, WALL - 1), (ww / 2, WALL - 1), (ww / 2, WALL + wh), (0, WALL + wh + ww / 2), (-ww / 2, WALL + wh)]
        f = Part.Face(Part.makePolygon([V(CAM_RI - 1, t, z) for t, z in prof] + [V(CAM_RI - 1, prof[0][0], prof[0][1])]))
        w_ = f.extrude(V(CAM_T + 2, 0, 0)); w_.rotate(V(0, 0, 0), V(0, 0, 1), a); wins.append(w_)
    ring = ring.cut(Part.makeCompound(wins))
    reservoir = reservoir.fuse(ring).removeSplitter()
    cav_real = cav_real.cut(ring)
    # Topf: Ringkanal (Dach 45°), Wulst drumherum mit WALL (konzentrisch), Zähne mit 45°-V unten
    zc = h_t + 0.4                                   # Kanaldecke (senkrechter Teil) über dem höchsten Rampenpunkt
    rmid = (CH_RI + CH_RO) / 2; rh = (CH_RO - CH_RI) / 2
    chan_prof = [(CH_RI, SPLIT - 1), (CH_RO, SPLIT - 1), (CH_RO, zc), (rmid, zc + rh), (CH_RI, zc)]
    channel = revolve_profile(chan_prof)
    teeth = []
    tz = SPLIT + CAM_ZT
    for k in range(CAM_TEETH):
        a = k * 360.0 / CAM_TEETH
        if TOOTH_R:   # runde Spitze (Bogen ±45°), dann 45°-Flanken bis zur Zahnbreite
            r_, s45 = TOOTH_R, math.sin(math.radians(45))
            z_f = tz + r_ * (1 - s45) + (TOOTH_W / 2 - r_ * s45)
            arcp = [(r_ * math.sin(math.radians(b)), tz + r_ - r_ * math.cos(math.radians(b))) for b in range(-45, 46, 5)]
            prof = [(-TOOTH_W / 2, z_f)] + arcp + [(TOOTH_W / 2, z_f), (TOOTH_W / 2, zc + rh + 1), (-TOOTH_W / 2, zc + rh + 1)]
        else:
            prof = [(-TOOTH_W / 2, tz + TOOTH_W / 2), (0, tz), (TOOTH_W / 2, tz + TOOTH_W / 2), (TOOTH_W / 2, zc + rh + 1), (-TOOTH_W / 2, zc + rh + 1)]
        f = Part.Face(Part.makePolygon([V(CH_RI - 1, t, z) for t, z in prof] + [V(CH_RI - 1, prof[0][0], prof[0][1])]))
        t_ = f.extrude(V(CH_RO - CH_RI + 2, 0, 0)); t_.rotate(V(0, 0, 0), V(0, 0, 1), a); teeth.append(t_)
    teeth = Part.makeCompound(teeth).common(channel)
    pot = pot.cut(channel).fuse(teeth).removeSplitter()
    _fein_topf = max(groove_top, tz + TOOTH_W / 2 + 0.5 if not TOOTH_R else z_f) - SPLIT + 0.2
    _fein_res = max(SPLIT + LIP_H, h_t) + 0.2
    _w = [0, 0.5, 1, 2, 3, 5, 10, 20, 30, 40, CAM_TURN - 1, CAM_TURN]
    print("Drehweg (schnell gerechnet): " + ", ".join("%g°->%.2f" % (a_, drehweg(a_)[0]) for a_ in _w))
    print("Hub-Bajonett: Ring r %.1f..%.1f, gerader Hub %.2f, Drehhub %.2f, Rast %.2f tief -> Gießstellung ca. %.2f mm über Fuge; "
          "Topfboden %.1f mm (innen glatt), %d Drainagelöcher" % (CAM_RI, CAM_R, CAM_L1, CAM_H2, CAM_DET, CAM_L1 + CAM_H2 - CAM_DET, POT_FLOOR, len(holes)))

# --- Dochtkorb (separates Teil, hängt im Topfboden) --------------------------
basket = basket_seated = None
if WICK:
    zb0 = WALL + WICK_GAP                       # Korbboden (aufgesetzt)
    ztop = SPLIT + POT_FLOOR                    # Bodenfläche Topf innen = Oberkante Korb
    zc0 = ztop - WICK_COLLAR                    # Kragenbeginn
    assert WICK_R + WICK_COLLAR + 2 < (CH_RI if LIFT else HX - WALL), "Dochtkorb zu groß (trifft Bajonett-Kanal)"
    assert zc0 > SPLIT + 1, "Topfboden zu dünn für den Kragen"
    # Topf: Durchgang + 45°-Senkung
    hole_prof = [(0, SPLIT - 1), (WICK_R + WICK_FIT, SPLIT - 1), (WICK_R + WICK_FIT, zc0), (WICK_R + WICK_FIT + WICK_COLLAR + 0.5, ztop + 0.5), (0, ztop + 0.5)]
    pot = pot.cut(revolve_profile(hole_prof)).removeSplitter()
    # Korb: außen konisch bis zum Kragen, Kragen 45° bis zur Bodenfläche; innen um WICK_T versetzt
    rz = lambda z: WICK_RB + (WICK_R - WICK_RB) * (z - zb0) / (zc0 - zb0)    # Außenradius Körper
    outer_prof = [(0, zb0), (WICK_RB, zb0), (WICK_R, zc0), (WICK_R + WICK_COLLAR, ztop), (0, ztop)]
    t = WICK_T
    inner_prof = [(0, zb0 + t), (rz(zb0 + t) - t, zb0 + t), (WICK_R - t, zc0), (WICK_R + WICK_COLLAR - t * (2 ** 0.5 - 1) - t, ztop + 1), (0, ztop + 1)]
    basket = revolve_profile(outer_prof).cut(revolve_profile(inner_prof))
    # Schlitze: senkrecht im Teil unter dem Topfboden (Dach 45°), dazu Schlitze im Korbboden
    sz0, sz1 = zb0 + t + 1.0, SPLIT - 1.5
    slots = []
    for k in range(WICK_SLOTS):
        a = 360.0 * k / WICK_SLOTS
        prof = [(-WICK_SLOT_W / 2, sz0), (WICK_SLOT_W / 2, sz0), (WICK_SLOT_W / 2, sz1), (0, sz1 + WICK_SLOT_W / 2), (-WICK_SLOT_W / 2, sz1)]
        f = Part.Face(Part.makePolygon([V(WICK_RB - 3, q, z) for q, z in prof] + [V(WICK_RB - 3, prof[0][0], prof[0][1])]))
        sl = f.extrude(V(WICK_R - WICK_RB + 6, 0, 0)); sl.rotate(V(0, 0, 0), V(0, 0, 1), a); slots.append(sl)
    for off in (-12, -6, 0, 6, 12):
        L = 2 * math.sqrt(max(0, (WICK_RB - t - 2) ** 2 - off ** 2))
        if L > 4:
            slots.append(Part.makeBox(WICK_SLOT_W, L, t + 2, V(off - WICK_SLOT_W / 2, -L / 2, zb0 - 1)))
    basket = basket.cut(Part.makeCompound(slots)).removeSplitter()
    basket_seated = basket.copy()
    basket.translate(V(0, 0, -zb0))             # Drucklage: Boden auf z=0, Kragen oben
    # Füllmarke: kurze Kerben innen an den Seiten nahe den Ecken (durch die Gießöffnungen sichtbar)
    mL, mH, mD, mA = FILL_MARK
    zf = SPLIT - FILL_DZ
    marks = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            # an der x-Seite (Wand y = sy*HY) und an der y-Seite (Wand x = sx*HX)
            # Kerbe reicht mD in die Wand hinein und 1 mm in den Wasserraum (sauberer Schnitt)
            cxm = sx * (HX - mA)
            y0 = (HY - WALL - 1) if sy > 0 else (-HY + WALL - mD)
            marks.append(Part.makeBox(mL, mD + 1, mH, V(cxm - mL / 2, y0, zf)))
            cym = sy * (HY - mA)
            x0 = (HX - WALL - 1) if sx > 0 else (-HX + WALL - mD)
            marks.append(Part.makeBox(mD + 1, mL, mH, V(x0, cym - mL / 2, zf)))
    reservoir = reservoir.cut(Part.makeCompound(marks)).removeSplitter()
    cord_wall = min(t_.distToShape(cav_real.fuse(Part.makeCompound(marks)))[0] for t_ in cords.Solids)
    assert cord_wall >= MIN_WATER_WALL - 0.05, "Füllmarke schwächt den Schnurkanal (%.2f mm)" % cord_wall
pot_collide = Part.makeCompound([pot, basket_seated]) if basket_seated is not None else pot


def regel_giessen():
    """REGEL Gießöffnung (Joe 16.11.): unter der Öffnung in Gießstellung keine Fläche flacher als POUR_FLAT_MAX
    zwischen Füllmarke und Fuge (flache Flächen dort lassen Gießwasser zurückspritzen)."""
    import MeshPart
    msh = MeshPart.meshFromShape(Shape=reservoir.common(slab(SPLIT - FILL_DZ + 0.05, SPLIT + LIP_H + 1)),
                                 LinearDeflection=0.1, AngularDeflection=0.1)
    cz, bad, flat = math.cos(math.radians(POUR_FLAT_MAX - 2.0)), 0.0, []   # 2° Toleranz: Netzfacetten auf 45°-Kegeln (Lippe, Trichter) liegen bei 44,4°
    for f in msh.Facets:
        n = f.Normal
        if n.z <= cz: continue
        c = [sum(p[i] for p in f.Points) / 3 for i in range(3)]
        if c[2] < SPLIT - FILL_DZ + 0.1: continue   # Schnittfläche des Prüfbereichs
        if pour_open.isInside(V(c[0], c[1], 0), 0.01, True):
            bad += f.Area; flat.append(c)
    print("Regel Gießöffnung: %.0f mm² Öffnung je Ecke, %.1f mm² Fläche flacher als %g° darunter (Füllmarke bis Fuge)" % (
        pour_open.Area / max(len(pour_open.Faces), 1), bad, POUR_FLAT_MAX))
    if flat:
        c = max(flat, key=lambda q: q[2])
        print("  höchste flache Stelle bei (%.1f, %.1f, %.2f)" % tuple(c))
    assert bad < 1.0, "REGEL Gießöffnung: %.1f mm² flache Fläche unter der Gießöffnung (Wasser spritzt zurück)" % bad
if POUR_FLAT_MAX:
    regel_giessen()

# --- Fugen-Testringe: volle Kontur, flach (Zentrierung lässt sich nur am ganzen Umfang prüfen) -------
if TEST:
    ring_in = lambda z0, z1: prism(rr(WALL + 0.01, 0), z0, z1)   # Innenraum weg, nur Wandring
    t_res = reservoir.common(slab(SPLIT - TEST_RES_H, SPLIT + LIP_H + 1)).cut(ring_in(SPLIT - TEST_RES_H - 1, SPLIT + LIP_H + 2)).removeSplitter()
    t_res.translate(V(0, 0, -(SPLIT - TEST_RES_H)))
    t_pots = []
    for fc in TEST_FLANKS:
        g, _ = make_groove(fc)
        tp = pot_body.common(slab(SPLIT, SPLIT + TEST_POT_H)).cut(ring_in(SPLIT - 1, SPLIT + TEST_POT_H + 1)).cut(g).removeSplitter()
        tp.translate(V(0, 0, -SPLIT)); t_pots.append((fc, tp))
    t_bj_res = t_bj_pot = None
    if LIFT:
        # Bajonett-Testpaar: prüft Fuge + Kurvenring zusammen (Zentrierung, Drehen, Rast, Zurücksetzen).
        # Reservoir: oberste TEST_RES_H mm der Außenwand mit Lippe + Kurvenring, 4 flache Speichen (1,2 mm).
        # Topf: ganzer Boden (POT_FLOOR) nur als Außenring (Nut) + Kanalring (Zähne, Dach), 4 Speichen.
        zr0 = SPLIT - TEST_RES_H
        ann = lambda r0, r1, z0, z1: Part.makeCylinder(r1, z1 - z0, V(0, 0, z0)).cut(Part.makeCylinder(r0, z1 - z0 + 2, V(0, 0, z0 - 1)))
        sp = lambda r0, r1, z0, h: Part.makeCompound([
            (lambda b: (b.rotate(V(0, 0, 0), V(0, 0, 1), 90 * k), b)[1])(Part.makeBox(r1 - r0, 8.0, h, V(r0, -4.0, z0))) for k in range(4)])
        res_keep = prism(rr(0, 0), zr0 - 1, SPLIT + 20).cut(ring_in(zr0 - 2, SPLIT + 21)).fuse(
            ann(CAM_RI - 0.01, CAM_R + 0.01, zr0 - 1, SPLIT + 20))
        spokes_res = sp(CAM_RI + 0.5, HX - WALL + 0.5, zr0, 1.2)       # neues Material (liegt im Wasserraum)
        t_bj_res_asm = reservoir.common(slab(zr0, SPLIT + 20)).common(res_keep).fuse(spokes_res).removeSplitter()
        pot_keep = prism(rr(0, 0), SPLIT - 1, SPLIT + POT_FLOOR + 1).cut(ring_in(SPLIT - 2, SPLIT + POT_FLOOR + 2)).fuse(
            ann(CH_RI - 1.6, CH_RO + 1.6, SPLIT - 1, SPLIT + POT_FLOOR + 1)).fuse(sp(CH_RO + 1.0, HX - WALL + 1.0, SPLIT - 1, 1.2 + 1))
        t_bj_pot_asm = pot.common(slab(SPLIT, SPLIT + POT_FLOOR)).common(pot_keep).removeSplitter()
        t_bj_res = t_bj_res_asm.copy(); t_bj_res.translate(V(0, 0, -zr0))
        t_bj_pot = t_bj_pot_asm.copy(); t_bj_pot.translate(V(0, 0, -SPLIT))

# --- Ausgabe ----------------------------------------------------------------
pot_print = pot.copy(); pot_print.translate(V(0, 0, -SPLIT))
res_side = reservoir.copy(); res_side.translate(V(SIZE_X + 20, 0, 0))
cad.material("Topf", "pla_schwarz"); cad.material("Reservoir", "pla_schwarz")
if globals().get("NO_REPORT"):   # aufrufendes Skript meldet selbst (z. B. plant_pot_giessen.py)
    pass
elif globals().get("BAUGRUPPE"):   # Einbaulage (plant_pot_baugruppe.py): Fuge/Schnurkanal prüfen
    named = dict(Topf=pot, Reservoir=reservoir)
    if basket_seated is not None:
        named["Dochtkorb"] = basket_seated; cad.material("Dochtkorb", "pla_schwarz")
    cad.report(**named)
    cad.focus("Fuge", (HX - 5, 0, SPLIT + 3), 14, view="front")
    cad.focus("Schnurkanal", (HX - CORD_INSET, HY - CORD_INSET, CORD_Z), 24, view="iso")
elif globals().get("NUR_TEST"):
    named = {"TestReservoir": t_res}
    if t_bj_res is not None:
        named = {"BajonettReservoir": t_bj_res}
        q = t_bj_pot.copy(); q.translate(V(0, -(SIZE_Y + 10), 0)); named["BajonettTopf"] = q
    for k, (fc, tp) in enumerate(t_pots):
        q = tp.copy(); q.translate(V((k + 1) * (SIZE_X + 10), 0, 0)); named["TestTopf_%02d" % round(fc * 100)] = q
    for n_ in named: cad.material(n_, "pla_schwarz")
    cad.report(**named)
else:
    named = dict(Topf=pot_print, Reservoir=res_side)
    if basket is not None:
        bk = basket.copy(); bk.translate(V(0, -(SIZE_Y / 2 + 50), 0)); named["Dochtkorb"] = bk; cad.material("Dochtkorb", "pla_schwarz")
    cad.report(**named)

water = cav_real.common(slab(WALL, SPLIT)).Volume / 1000
if WICK:
    water_fill = cav_real.common(slab(WALL, SPLIT - FILL_DZ)).cut(revolve_profile(outer_prof)).Volume / 1000
    print("Dochtkorb: Ø %.0f/%.0f, Länge %.1f, taucht aufgesetzt %.1f mm ein (bis Füllmarke); Wasser bis Füllmarke %.0f ml, Luftspalt %.0f mm" % (
        2 * WICK_R, 2 * WICK_RB, ztop - zb0, (SPLIT - FILL_DZ) - zb0, water_fill, FILL_DZ))
print("Größe %s: Topf %g x %g x %g, Reservoir %g x %g x %g (+ Lippe %g) mm" % (
    NAME, SIZE_X, SIZE_Y, HEIGHT - SPLIT, SIZE_X, SIZE_Y, SPLIT, LIP_H))
print("Wasserraum bis Fuge %.0f ml, Löcher %d, Wand %.2f (Auflage %.2f, Lippe %.2f), Nut %.2f breit, "
      "Wand Schnurkanal->Wasser min %.2f mm" % (water, len(holes), WALL, LIP_IN, LIP_T, LIP_T + 2 * FIT, cord_wall))
out = cad.outdir("modell")
if out:
    import MeshPart
    def regel_facetten(msh, fn):
        """Sicherheitsregel (Joe 15.11.: Facetten an den Rundungen sichtbar) -> tools/freecad/stl_facetten.py."""
        import sys
        sys.path.insert(0, "/mnt/raid1/3d_print/tools/freecad")
        from stl_facetten import knickkanten
        pts, tris = msh.Topology
        mm, n_, amax = knickkanten([(q.x, q.y, q.z) for q in pts], tris)
        print("Regel Facetten %s: %.0f mm sichtbare Knickkanten (Grenze %g)" % (fn, mm, STL_FACET_MAX))
        assert mm <= STL_FACET_MAX, "REGEL Facetten: %s hat %.0f mm Knickkanten 2,5-15° (max %.1f°) -> STL_LIN/STL_ANG feiner" % (fn, mm, amax)
    def stl(shape, fn):
        # fein (Joe 15.11.: Facetten an den Rundungen sichtbar bei 0,05/0,2 = 8° pro Facette an R20)
        msh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=STL_LIN, AngularDeflection=STL_ANG)
        regel_facetten(msh, fn)
        msh.write(out + "/" + fn)
    stl(pot_print, "pot_%s.stl" % NAME)
    if BODEN_PROBE:
        stl(pot_print.common(slab(-1, POT_FLOOR + BODEN_PROBE)).removeSplitter(), "probe_boden_%s.stl" % NAME)
    stl(reservoir, "reservoir_%s.stl" % NAME)
    if basket is not None:
        stl(basket, "dochtkorb_%s.stl" % NAME)
    if TEST:
        stl(t_res, "testring_reservoir_%s.stl" % NAME)
        if t_bj_res is not None:
            stl(t_bj_res, "testring_bajonett_reservoir_%s.stl" % NAME)
            stl(t_bj_pot, "testring_bajonett_topf_flanke%02d_%s.stl" % (round(FLANK_CLEAR * 100), NAME))
        for fc, tp in t_pots:
            stl(tp, "testring_topf_flanke%02d_%s.stl" % (round(fc * 100), NAME))
    import json
    json.dump(dict(  # Höhen in Druckkoordinaten (Teil liegt auf z=0) für die Slicer-Modifier
        name=NAME, topf_hoehe=round(HEIGHT - SPLIT, 2), reservoir_hoehe=round(SPLIT + LIP_H, 2),
        topf_boden_oben=round(POT_FLOOR, 2), reservoir_boden_oben=round(WALL, 2), wand=WALL,
        kurvenring_r=round(CAM_R, 2) if LIFT else None,
        # Joe 15.11.: feine Schichten nur dort, wo beim Drehen etwas gleitet (Lippe/Nut, Zähne, Kurvenring) -> kleinere Layerstufen
        fein_schichthoehe=0.1 if LIFT else None,
        fein_topf=[0.0, round(_fein_topf, 2)] if LIFT and FEIN_TOPF else None,           # Druckhöhe Topf: V-Nut + Zahnspitzen
        fein_reservoir=[round(SPLIT, 2), round(_fein_res, 2)] if LIFT else None,   # Druckhöhe Reservoir: Lippe + Kurvenbahn
        # Joe 16.11.: leichtes Fuzzy Skin auf der Außenwand. Nur die sichtbare Außenhaut (Druckhöhe): Topf ganz, Reservoir bis zur Fuge;
        # darüber am Reservoir nur Lippe (Zentrierflanke) und Kurvenring (Spiel 0,4) -> glatt. Dochtkorb glatt (Spiel 0,3 in der Öffnung).
        fuge_reservoir=round(SPLIT, 2),
        # Joe 16.11. (später): "das fuzzy skin kann weg" -> Standard aus (FUZZY=True schreibt die Bereiche wieder)
        fuzzy_topf=[0.0, round(HEIGHT - SPLIT, 2)] if FUZZY else None, fuzzy_reservoir=[0.0, round(SPLIT, 2)] if FUZZY else None, fuzzy_dochtkorb=None,
        hinweis="Innenboden-Oberkante: darunter Lightning, darüber Grid (Joe, 15.11.); Naht back"),
        open(out + "/slicer_%s.json" % NAME, "w"), indent=1, ensure_ascii=False)
    print("STL: %s/{pot,reservoir%s}_%s.stl" % (out, ",testring_*" if TEST else "", NAME))
