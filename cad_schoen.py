#!/usr/bin/env python3
"""cad_schoen - Darstellungsstil "schoen" (fuer Menschen) und GLB-Export fuer `cad look --style schoen` / `--glb`.

Zwei Betriebsarten (wie cad_render.py):
  * normales Python (Client/Worker): Materialtabelle, Material aus Teilenamen, Explosions-Regeln (kein bpy noetig),
    run_job(job) startet  env -u LD_LIBRARY_PATH -u DISPLAY blender -b --python cad_schoen.py -- job.json
  * innerhalb von Blender: baut die Szene (Materialien je Bauteil, Perspektivkamera, Licht, optional Raum/Schnitt/Explosion),
    rendert (Cycles + Denoise oder EEVEE), legt Nummern/Legende per PIL darueber und schreibt optional ein GLB.

Koordinaten wie im Modell: Z oben, mm; 1 Blender-Einheit = 1 mm. GLB: Meter (Faktor 0,001), glTF Y-oben
(Blender/Modell (x, y, z) -> glTF (x, z, -y), vom Blender-Exporter), Teile = benannte Meshes (Knotenname = Teilename).
"""
import json, math, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_ROOT = os.environ.get("CAD_OUT", "/mnt/raid1/3d_print/cad_out")
TEX_DIR = os.path.join(OUT_ROOT, ".cache", "tex_v3")

# ---------------------------------------------------------------------------------------- Materialtabelle (ohne bpy)
MATERIALS = {
    # key: Anzeigename, Grundfarbe (sRGB 0..1, auch fuer Legende)
    "eiche": {"label": "Eiche (massiv)", "rgb": (0.66, 0.44, 0.22)},
    "multiplex": {"label": "Multiplex (Birke)", "rgb": (0.84, 0.70, 0.48)},
    "hartholz": {"label": "Hartholz", "rgb": (0.40, 0.24, 0.12)},
    "platzhalter": {"label": "Platzhalter (kein Möbelteil)", "rgb": (0.42, 0.58, 0.76)},
}
CABLE_RGB = (0.95, 0.45, 0.10)
ALIASES = {"eiche": "eiche", "multiplex": "multiplex", "birke": "multiplex", "sperrholz": "multiplex", "hartholz": "hartholz",
           "buche": "hartholz", "platzhalter": "platzhalter", "placeholder": "platzhalter"}


# Eigene Materialien: materials.json neben diesem Skript (Verwaltung: cad materials list|add|rm). Einmal angelegt, fuer alle Modelle nutzbar.
MATERIALS_FILE = os.path.join(HERE, "materials.json")
USER_MATERIALS = {}


def load_user_materials():
    USER_MATERIALS.clear()
    try:
        with open(MATERIALS_FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    for k, m in data.items():
        k = k.strip().lower()
        if k in ("eiche", "multiplex", "hartholz", "platzhalter"):
            continue
        USER_MATERIALS[k] = m
        MATERIALS[k] = {"label": m.get("label", k), "rgb": tuple(m["rgb"])}
        ALIASES[k] = k
        for al in m.get("aliases", []):
            ALIASES[str(al).strip().lower()] = k


def save_user_materials(data):
    with open(MATERIALS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    load_user_materials()


load_user_materials()


def norm_material(m):
    """'Eiche', 'multiplex', ... -> Schluessel; unbekannt -> ValueError."""
    k = ALIASES.get(str(m).strip().lower())
    if not k:
        raise ValueError("unbekanntes Material %r (eiche, multiplex, hartholz, platzhalter)" % (m,))
    return k


def default_material(name):
    """Fallback aus dem Teilenamen: Eiche -> eiche, *Platzhalter*/Kabelweg*/Laptop -> platzhalter, Rest -> multiplex."""
    n = str(name).lower()
    if "eiche" in n:
        return "eiche"
    for k, m in USER_MATERIALS.items():
        if m.get("match") and re.search(m["match"], n):
            return k
    if "platzhalter" in n or n.startswith("kabelweg") or n.startswith("laptop") or n.startswith("kabel"):
        return "platzhalter"
    if "hartholz" in n:
        return "hartholz"
    return "multiplex"


def is_cable(name):
    n = str(name).lower()
    return n.startswith("kabelweg") or n.startswith("kabel")


# Explosionsregeln: (Regex auf Teilenamen, (fx, fy, fz)); Verschiebung = (fx*dx, fy*dy, fz*dz). Reihenfolge = erste passende Regel.
# Montagerichtung: Platte nach oben, Rueckwand nach hinten (+Y, zur Wand), Zarge/Vorderwand nach vorn (-Y, Sofaseite),
# Fachboeden/Trennwand/Laptop seitlich aus dem offenen Ende, Kasten nach unten.
EXPLODE_RULES = [
    (r"^Eichenplatte", (0, 0, 1.55)),
    (r"^Fach_Oben_Rahmen", (0, 0, 0.85)),
    (r"^Fach_Oben_", (0, 0, -0.85)),
    (r"^Deckel", (0, 0, 0.40)),
    (r"^Boden", (0, 0, -0.40)),
    (r"^Mittelstuetze", (0, 0, 0.60)),
    (r"^(Vorderwand|Zarge)", (0, -1.0, 0)),
    (r"^Rueckwand", (0, 0.4, 0)),
    (r"^Wandklotz", (0, 2.2, 0)),
    (r"^Winkelstecker", (0, 3.9, 0)),
    (r"^Wand_Steckdose", (0, 4.7, 0)),
    (r"^Endwand_links", (0.55, 0, 0)),
    (r"^Endwand_rechts", (-0.55, 0, 0)),
    (r"^Fachboden_L", (-1.0, 0, 0)),
    (r"^Fachboden_R", (1.2, 0, 0)),
    (r"^Laptopfach_Trennwand", (1.7, 0, 0)),
    (r"^(Laptop)", (3.4, 0, 0)),
    (r"^(Netzteil|Steckdosenleiste|Zugentlastung)", (2.3, 0, 0)),
]
EXPLODE_AUTO = (300.0, 250.0, 300.0)


def explode_offsets(names, centers, model_center, spec):
    """Verschiebung je Teil (mm). spec = (dx,dy,dz) oder None (= auto). Teile ohne Regel: radial entlang der Achse mit der
    groessten Abweichung des Teilmittelpunkts vom Modellmittelpunkt."""
    d = EXPLODE_AUTO if not spec or spec == "auto" else tuple(float(x) for x in spec)
    out = {}
    for n, c in zip(names, centers):
        for pat, f in EXPLODE_RULES:
            if re.search(pat, n):
                out[n] = [f[0] * d[0], f[1] * d[1], f[2] * d[2]]
                break
        else:
            rel = [c[i] - model_center[i] for i in range(3)]
            ax = max(range(3), key=lambda i: abs(rel[i]))
            v = [0.0, 0.0, 0.0]
            v[ax] = math.copysign(0.8 * d[ax], rel[ax] or 1.0)
            out[n] = v
    return out


# ---------------------------------------------------------------------------------------- Client
def run_job(job, timeout=300):
    """Blender-Job (schoen/GLB) ausfuehren; gleiche Slot-/Umgebungslogik wie cad_render.run_job."""
    import cad_render as cr
    return cr.run_job(job, timeout=timeout, script=os.path.abspath(__file__))


# =========================================================================================== Blender-Teil
def _fnoise(np, W, H, su, sv, seed):
    """Periodisches, anisotropes Gauss-Rauschen (FFT): Korrelationslaenge su (u/x) und sv (v/y) in Pixeln, Mittel 0, Std 1."""
    rng = np.random.default_rng(seed)
    n = rng.standard_normal((H, W))
    F = np.fft.rfft2(n)
    fy = np.fft.fftfreq(H)[:, None]
    fx = np.fft.rfftfreq(W)[None, :]
    F *= np.exp(-2 * np.pi ** 2 * ((fx * su) ** 2 + (fy * sv) ** 2))
    r = np.fft.irfft2(F, s=(H, W))
    return (r - r.mean()) / (r.std() + 1e-9)


def _lerp(a, b, t):
    return a + (b - a) * t[..., None]


def make_textures(np, Image):
    """Prozedurale Holztexturen (kachelbar) einmalig erzeugen und als PNG ablegen. Rueckgabe: Name -> Pfad."""
    os.makedirs(TEX_DIR, exist_ok=True)
    spec = {
        "eiche": (2048, 1024), "hartholz": (1024, 512), "ply_face": (1024, 512), "ply_edge": (512, 256),
    }
    paths = {k: os.path.join(TEX_DIR, k + ".png") for k in spec}
    if all(os.path.exists(p) for p in paths.values()):
        return paths

    def save(name, rgb):
        img = Image.fromarray((np.clip(rgb, 0, 1) * 255 + 0.5).astype("uint8"), "RGB")
        tmp = paths[name] + ".%d.tmp" % os.getpid()
        img.save(tmp, format="PNG")
        os.replace(tmp, paths[name])

    def wood(W, H, seed, light, dark, rings, contrast, streak):
        yy = (np.arange(H)[:, None] / H) * np.ones((1, W))
        low = _fnoise(np, W, H, 260, 40, seed)
        ring_ph = yy * rings + 0.9 * low
        ring = 0.5 + 0.5 * np.cos(2 * np.pi * ring_ph)
        ring = ring ** 1.6
        pores = _fnoise(np, W, H, 40, 0.9, seed + 1)
        mott = _fnoise(np, W, H, 160, 120, seed + 2)
        v = 0.55 * contrast * (ring - 0.4) + streak * pores * 0.17 + 0.16 * mott
        t = np.clip(0.5 + v * 0.55, 0, 1)
        return _lerp(np.array(light), np.array(dark), t)

    save("eiche", wood(*spec["eiche"], 11, (0.74, 0.54, 0.31), (0.55, 0.35, 0.17), 130, 0.7, 1.0))
    save("hartholz", wood(*spec["hartholz"], 21, (0.46, 0.28, 0.14), (0.26, 0.14, 0.07), 24, 0.9, 1.0))
    save("ply_face", wood(*spec["ply_face"], 31, (0.88, 0.78, 0.62), (0.80, 0.68, 0.50), 6, 0.5, 0.6))
    # Sperrholz-Kante: v = Dicke; 4 Lagen je Kachel (1,5 mm je Lage); helle Lage / dunklere Lage / Leimfuge
    W, H = spec["ply_edge"]
    v = (np.arange(H)[:, None] / H) * np.ones((1, W))
    layer = np.floor(v * 4).astype(int)
    pos = (v * 4) % 1.0
    base = np.where((layer % 2 == 0)[..., None], np.array([0.89, 0.79, 0.62]), np.array([0.77, 0.63, 0.43]))
    glue = np.clip(1 - np.abs(pos - 0.0) * 14, 0, 1) + np.clip(1 - np.abs(pos - 1.0) * 14, 0, 1)
    base = base * (1 - 0.55 * glue[..., None]) + np.array([0.45, 0.30, 0.15]) * 0.55 * glue[..., None]
    base = base * (1 + 0.06 * _fnoise(np, W, H, 30, 2, 41)[..., None])
    save("ply_edge", base)
    return paths


def _srgb_to_lin(c):
    return [(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c]


def _box_mesh(bpy, bmesh, name, boxes, bevel=0.0):
    """Objekt aus Quadern [(x0,x1,y0,y1,z0,z1),...]; bevel = Fase (mm) als Modifier."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    for (x0, x1, y0, y1, z0, z1) in boxes:
        r = bmesh.ops.create_cube(bm, size=1.0)
        for v in r["verts"]:
            v.co.x = x0 if v.co.x < 0 else x1
            v.co.y = y0 if v.co.y < 0 else y1
            v.co.z = z0 if v.co.z < 0 else z1
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if bevel:
        m = ob.modifiers.new("Bevel", "BEVEL")
        m.width = bevel
        m.segments = 3
        m.limit_method = "ANGLE"
    return ob


WARN = []


def blender_main():
    import bpy
    job = json.load(open(sys.argv[sys.argv.index("--") + 1]))
    t0 = time.time()
    try:
        res = build_and_render(job, bpy)
        res["ok"] = True
    except Exception as e:
        import traceback
        res = {"ok": False, "error": "%s: %s" % (type(e).__name__, e), "trace": traceback.format_exc()}
    res["blender_seconds"] = round(time.time() - t0, 2)
    res["warnings"] = list(WARN)
    json.dump(res, open(job["legend_out"], "w"))


def _read_scene_objects(bpy, bmesh, np, parts):
    """STL-Teile laden, Punkte verschmelzen (fuer Boolean/Glattung), Objekt je Teil benennen."""
    imp = getattr(bpy.ops.wm, "stl_import", None) or bpy.ops.import_mesh.stl
    objs = {}
    for p in parts:
        before = set(bpy.data.objects)
        imp(filepath=p["path"])
        new = [o for o in bpy.data.objects if o not in before]
        if not new:
            raise RuntimeError("STL nicht lesbar: %s" % p["path"])
        o = new[0]
        o.name = p["name"]
        o.data.name = p["name"]
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        bm.to_mesh(o.data)
        bm.free()
        objs[p["name"]] = o
    return objs


def _verts_np(np, o):
    n = len(o.data.vertices)
    a = np.empty(n * 3)
    o.data.vertices.foreach_get("co", a)
    return a.reshape(n, 3) + np.array(o.location)


def _smooth_by_angle(bmesh, o, deg=32.0):
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    lim = math.radians(deg)
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) != 2 or e.calc_face_angle(0.0) > lim)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()


def _assign_uv_and_slots(np, o, kind, name):
    """UV (Maserung entlang der laengsten Achse; Sperrholz: Lagen an den Kanten) und Materialindex je Flaeche.
    kind: wood | ply. Rueckgabe: Dicken-Achse T."""
    me = o.data
    nv = len(me.vertices)
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(nv, 3)
    mn, mx = co.min(0), co.max(0)
    dims = mx - mn
    L, T = int(np.argmax(dims)), int(np.argmin(dims))
    nl = len(me.loops)
    vi = np.empty(nl, dtype=np.int32)
    me.loops.foreach_get("vertex_index", vi)
    npoly = len(me.polygons)
    ls = np.empty(npoly, dtype=np.int32)
    lt = np.empty(npoly, dtype=np.int32)
    nm = np.empty(npoly * 3)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    me.polygons.foreach_get("normal", nm)
    nm = nm.reshape(npoly, 3)
    pn = np.argmax(np.abs(nm), axis=1)
    loop_poly = np.repeat(np.arange(npoly), lt)
    ln = pn[loop_poly]
    other = np.array([[1, 2], [0, 2], [0, 1]])
    ua = np.where(ln == L, np.where(dims[other[ln][:, 0]] >= dims[other[ln][:, 1]], other[ln][:, 0], other[ln][:, 1]), L)
    va = 3 - ln - ua
    h = (sum(ord(c) * (i + 1) for i, c in enumerate(name)) % 997) / 997.0
    pts = co[vi]
    ar = np.arange(nl)
    u = pts[ar, ua] / 1200.0 + h
    v = pts[ar, va] / 600.0 + h * 0.7
    slot = np.zeros(npoly, dtype=np.int32)
    if kind == "ply":
        face = (pn == T) & (np.abs(nm[np.arange(npoly), T]) > 0.85)
        slot = np.where(face, 0, 1).astype(np.int32)
        edge_l = ~face[loop_poly]
        # Kante: u laengs der Kante (die Achse, die weder Flaechennormale noch Dicke ist), v = Dicke in 6-mm-Kacheln ab der Flaeche
        ue = 3 - ln - T
        ue = np.where(ln == T, ua, ue)
        u = np.where(edge_l, pts[ar, ue] / 600.0 + h, u)
        v = np.where(edge_l, (pts[ar, T] - mn[T]) / 6.0, v)
    uv = me.uv_layers.new(name="UVMap")
    flat = np.empty(nl * 2)
    flat[0::2] = u
    flat[1::2] = v
    uv.data.foreach_set("uv", flat)
    me.polygons.foreach_set("material_index", slot)
    me.update()
    return T


# ----------------------------------------------------------------------------------------- Materialien
class MatBook:
    def __init__(self, bpy, paths, cycles, simple=False):
        self.bpy, self.paths, self.cycles, self.simple = bpy, paths, cycles, simple
        self.cache = {}
        self.imgs = {}

    def img(self, key):
        if key not in self.imgs:
            im = self.bpy.data.images.load(self.paths[key])
            im.colorspace_settings.name = "sRGB"
            im.pack() if self.simple else None
            self.imgs[key] = im
        return self.imgs[key]

    def _new(self, name):
        m = self.bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        return m, nt, bsdf

    def _normal(self, nt, bsdf, rad=1.0, bump_from=None, strength=0.15):
        """Cycles: Fasen-Glanz (Bevel-Knoten) und leichte Poren (Bump); EEVEE/GLB: nichts."""
        if not self.cycles or self.simple:
            return
        last = None
        if bump_from is not None:
            b = nt.nodes.new("ShaderNodeBump")
            b.inputs["Strength"].default_value = strength
            b.inputs["Distance"].default_value = 0.5
            nt.links.new(bump_from, b.inputs["Height"])
            last = b.outputs["Normal"]
        bv = nt.nodes.new("ShaderNodeBevel")
        bv.samples = 4
        bv.inputs["Radius"].default_value = rad
        if last is not None:
            nt.links.new(last, bv.inputs["Normal"])
        nt.links.new(bv.outputs["Normal"], bsdf.inputs["Normal"])

    def textured(self, key, label, rough, tint=None, bump=True):
        mk = ("tex", key)
        if mk in self.cache:
            return self.cache[mk]
        m, nt, bsdf = self._new(label)
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = self.img(key)
        tex.interpolation = "Linear"
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = rough
        self._normal(nt, bsdf, 1.0, tex.outputs["Color"] if bump else None, 0.12)
        self.cache[mk] = m
        return m

    def solid(self, label, rgb, rough=0.5, metal=0.0, alpha=1.0, emit=0.0):
        mk = ("solid", label)
        if mk in self.cache:
            return self.cache[mk]
        m, nt, bsdf = self._new(label)
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
        if alpha < 1.0:
            bsdf.inputs["Alpha"].default_value = alpha
            for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
                try:
                    setattr(m, attr, val)
                except (AttributeError, TypeError):
                    pass
        self._normal(nt, bsdf, 0.8)
        self.cache[mk] = m
        return m

    def part_slots(self, key, name):
        """Materialliste (Slots) eines Teils nach Materialschluessel."""
        if key == "eiche":
            return [self.textured("eiche", "Eiche", 0.42)], "wood"
        if key == "hartholz":
            return [self.textured("hartholz", "Hartholz", 0.5)], "wood"
        if key == "multiplex":
            return [self.textured("ply_face", "Multiplex", 0.5, bump=False), self.textured("ply_edge", "Multiplex_Kante", 0.6, bump=False)], "ply"
        if key in USER_MATERIALS:
            m = USER_MATERIALS[key]
            return [self.solid(key, _srgb_to_lin(tuple(m["rgb"])), float(m.get("rough", 0.5)), metal=float(m.get("metal", 0.0)))], None
        if is_cable(name):
            if re.search(r"(Schacht|Plattendurchlass|Durchlass)", name):       # Freihalteraeume: durchscheinend
                return [self.solid("Freihalteraum", CABLE_RGB_LIN, 0.5, alpha=0.35)], None
            return [self.solid("Kabel", CABLE_RGB_LIN, 0.35, alpha=0.95)], None
        n = name.lower()
        if n.startswith("laptop"):
            return [self.solid("Platzhalter_Laptop", _srgb_to_lin((0.36, 0.42, 0.52)), 0.3, metal=0.6)], None
        if "netzteil" in n or "stecker" in n:
            return [self.solid("Platzhalter_Netz", _srgb_to_lin((0.25, 0.30, 0.38)), 0.35)], None
        return [self.solid("Platzhalter", _srgb_to_lin(MATERIALS["platzhalter"]["rgb"]), 0.4)], None

    def cap(self, key, name):
        base = {"eiche": (0.80, 0.55, 0.28), "hartholz": (0.52, 0.30, 0.14), "multiplex": (0.90, 0.68, 0.38)}.get(key) or tuple(min(1.0, v * 1.25 + 0.05) for v in USER_MATERIALS.get(key, {}).get("rgb", (0.45, 0.6, 0.72)))
        return self.solid("Schnitt_" + key, _srgb_to_lin(base), 0.7)


CABLE_RGB_LIN = _srgb_to_lin(CABLE_RGB)


# ----------------------------------------------------------------------------------------- Kamera
def _basis(az, el):
    """wie cadgeom._view_basis: e = vom Ziel zur Kamera, r rechts, u oben."""
    import numpy as np
    a, b = math.radians(az), math.radians(el)
    e = np.array([math.sin(a) * math.cos(b), -math.cos(a) * math.cos(b), math.sin(b)])
    up = np.array([0.0, math.copysign(1, el), 0.0]) if abs(el) >= 89.5 else np.array([0.0, 0.0, 1.0])
    r = np.cross(-e, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, -e)
    u /= np.linalg.norm(u)
    return e, r, u


def _project(np, P, C, e, r, u, tw, th):
    v = P - C
    depth = -(v @ e)
    return (v @ r) / depth / tw, (v @ u) / depth / th, depth


def frame_camera(np, pts, az, el, lens, aspect, margin=0.93, target=None, size=None, sensor=36.0):
    """Kameraposition (Perspektive) so, dass pts das Bild fuellen (margin) und zentriert sind (Objektivverschiebung).
    Mit target+size: Ausschnitt `size` mm breit um target, keine Verschiebung."""
    e, r, u = _basis(az, el)
    tw = (sensor / 2) / lens
    th = tw / aspect
    if target is not None:
        T = np.asarray(target, float)
        d = (size / 2) / tw
        return {"C": T + e * d, "T": T, "d": d, "shift": (0.0, 0.0), "c": (0.0, 0.0), "e": e, "r": r, "u": u, "tw": tw, "th": th}
    T = (pts.min(0) + pts.max(0)) / 2

    def ext(d):
        C = T + e * d
        x, y, dep = _project(np, pts, C, e, r, u, tw, th)
        ok = dep > 1e-3
        if not ok.all():
            return None
        return x.min(), x.max(), y.min(), y.max()

    lo, hi = 10.0, 1e6
    for _ in range(80):
        mid = math.sqrt(lo * hi)
        ex = ext(mid)
        fit = ex is not None and (ex[1] - ex[0]) / 2 <= margin and (ex[3] - ex[2]) / 2 <= margin
        if fit:
            hi = mid
        else:
            lo = mid
    d = hi
    ex = ext(d)
    cx, cy = (ex[0] + ex[1]) / 2, (ex[2] + ex[3]) / 2
    # positive Verschiebung schiebt das Sichtfeld nach rechts/oben -> Inhalt wandert nach links/unten
    return {"C": T + e * d, "T": T, "d": d, "shift": (cx / 2, cy / (2 * aspect)), "c": (cx, cy), "e": e, "r": r, "u": u, "tw": tw, "th": th}


# ----------------------------------------------------------------------------------------- Hauptprogramm (Blender)
def build_and_render(job, bpy):
    import numpy as np, bmesh, mathutils
    from PIL import Image, ImageDraw, ImageFont
    sys.path.insert(0, HERE)
    import cad_render as cr
    Vec = mathutils.Vector
    t_all = time.time()
    tim = {}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    parts = job["parts"]
    engine = job.get("engine", "cycles")
    cycles = engine == "cycles"
    paths = make_textures(np, Image)
    tim["textures"] = round(time.time() - t_all, 2)
    if job.get("no_render"):                      # nur GLB
        t_g = time.time()
        g = export_glb(job, bpy, np, bmesh, Image, paths, mathutils)
        g["seconds"] = round(time.time() - t_g, 2)
        return {"glb": g, "views": [], "time_detail": tim}
    sec = job.get("section")
    expl = job.get("explode")
    room = bool(job.get("room"))
    hide = set(job.get("hide") or [])

    objs = _read_scene_objects(bpy, bmesh, np, parts)
    mb = MatBook(bpy, paths, cycles)
    info = {}
    for p in parts:
        o = objs[p["name"]]
        key = p["mat"]
        slots, kind = mb.part_slots(key, p["name"])
        if kind:
            _assign_uv_and_slots(np, o, kind, p["name"])
        for m in slots:
            o.data.materials.append(m)
        if kind is None:
            _smooth_by_angle(bmesh, o, 32.0)
        else:
            _smooth_by_angle(bmesh, o, 32.0)
        info[p["name"]] = {"mat": key, "obj": o}
    # versteckte Teile (Kabelwege bei Explosion u. a.)
    for n in list(objs):
        if n in hide:
            bpy.data.objects.remove(objs[n], do_unlink=True)
            del objs[n]
            info.pop(n, None)

    # ---- Schnitt: Boolean gegen Quader der abgeschnittenen Seite, Schnittflaeche = Schnittmaterial
    sec_text = None
    if sec:
        ax, pos = "xyz".index(sec["axis"]), float(sec["pos"])
        sgn = {"x": 1, "y": -1, "z": 1}[sec["axis"]]       # x: behaelt x < pos; y: behaelt y > pos; z: behaelt z < pos
        big = 50000.0
        dg = bpy.context.evaluated_depsgraph_get()
        removed = []
        for n, o in list(objs.items()):
            v = _verts_np(np, o)
            lo, hi = v[:, ax].min(), v[:, ax].max()
            keep_all = (hi <= pos + 1e-6) if sgn > 0 else (lo >= pos - 1e-6)
            drop_all = (lo >= pos - 1e-6) if sgn > 0 else (hi <= pos + 1e-6)
            if keep_all:
                continue
            if drop_all:
                removed.append(n)
                continue
            b0 = [-big, big, -big, big, -big, big]
            if sgn > 0:
                b0[2 * ax], b0[2 * ax + 1] = pos, pos + big
            else:
                b0[2 * ax], b0[2 * ax + 1] = pos - big, pos
            cutter = _box_mesh(bpy, bmesh, "cutter", [tuple(b0)])
            cutter.data.materials.append(mb.cap(info[n]["mat"], n))
            bm_ = o.modifiers.new("cut", "BOOLEAN")
            bm_.operation = "DIFFERENCE"
            bm_.operand_type = "OBJECT"
            bm_.object = cutter
            bm_.solver = "EXACT"
            try:
                bm_.material_mode = "TRANSFER"
            except Exception:
                pass
            dg.update()
            ev = o.evaluated_get(dg)
            newme = bpy.data.meshes.new_from_object(ev)
            if len(newme.polygons) > 0:
                oldme = o.data
                o.modifiers.remove(bm_)
                o.data = newme
                bpy.data.meshes.remove(oldme)
                _smooth_by_angle(bmesh, o, 32.0)
            else:
                o.modifiers.remove(bm_)
                bpy.data.meshes.remove(newme)
                removed.append(n)
            bpy.data.objects.remove(cutter, do_unlink=True)
        for n in removed:
            bpy.data.objects.remove(objs[n], do_unlink=True)
            del objs[n]
        sec_text = "Schnitt %s=%g (behält %s %s %g)" % (sec["axis"], pos, sec["axis"], "<" if sgn > 0 else ">", pos)

    # ---- Explosion
    offsets = {}
    centers = {}
    for n, o in objs.items():
        v = _verts_np(np, o)
        centers[n] = ((v.min(0) + v.max(0)) / 2).tolist()
    if expl:
        allv = np.vstack([_verts_np(np, o) for o in objs.values()])
        mc = ((allv.min(0) + allv.max(0)) / 2).tolist()
        names = list(objs)
        offsets = explode_offsets(names, [centers[n] for n in names], mc, expl)
        for n, off in offsets.items():
            objs[n].location = Vec(off)

    pts_parts = np.vstack([_verts_np(np, o) for o in objs.values()])
    zmin_parts = float(pts_parts[:, 2].min())
    bb = [float(x) for x in list(pts_parts.min(0)) + list(pts_parts.max(0))]

    # ---- Raum (Wand, Boden, Sofa) -- nur ohne Explosion
    extra = []
    sofa_pts = None
    if room and not expl:
        cfg = job.get("room_cfg") or {}
        wy = float(cfg.get("wall_y", 230.0))
        sw, sd, sh = [float(x) for x in cfg.get("sofa", (2400, 960, 750))]
        sx0 = float(cfg.get("sofa_x0", (bb[0] + bb[3]) / 2 - sw / 2))
        floor = _box_mesh(bpy, bmesh, "Boden", [(-3500, 7000, -4500, wy + 100, -40, 0)])
        wall = _box_mesh(bpy, bmesh, "Wand", [(-3500, 7000, wy, wy + 100, 0, 2700)])
        back_d = min(250.0, sd * 0.28)
        sofa = _box_mesh(bpy, bmesh, "Sofa_Schaetzung", [(sx0, sx0 + sw, -sd, 0.0, 0, sh * 0.58), (sx0, sx0 + sw, -back_d, 0.0, 0, sh), (sx0, sx0 + 170, -sd, 0.0, 0, sh * 0.80), (sx0 + sw - 170, sx0 + sw, -sd, 0.0, 0, sh * 0.80)], bevel=22.0)
        extra = [floor, wall, sofa]
        floor.data.materials.append(mb.solid("Boden", _srgb_to_lin((0.66, 0.63, 0.58)), 0.55))
        wall.data.materials.append(mb.solid("Wand", _srgb_to_lin((0.90, 0.89, 0.86)), 0.9))
        sofa.data.materials.append(mb.solid("Sofa", _srgb_to_lin((0.50, 0.50, 0.51)), 0.9))
        sofa_pts = np.array([[sx0, -sd, 0], [sx0 + sw, 0, sh]], float)
    elif not room:
        pass

    # ---- Welt, Licht
    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.82, 0.88, 1.0, 1.0) if room else (1, 1, 1, 1)
    bg.inputs["Strength"].default_value = float(job.get("ambient", 0.85))
    sun = bpy.data.lights.new("Sonne", "SUN")
    sun.energy = float(job.get("sun", 3.2))
    sun.angle = math.radians(float(job.get("sun_angle", 4.0)))
    so = bpy.data.objects.new("Sonne", sun)
    sc.collection.objects.link(so)
    saz, sel = math.radians(job.get("sun_az", -38)), math.radians(job.get("sun_el", 48))
    to_sun = Vec((math.sin(saz) * math.cos(sel), -math.cos(saz) * math.cos(sel), math.sin(sel)))
    so.rotation_euler = (-to_sun).to_track_quat("-Z", "Y").to_euler()
    fill = bpy.data.lights.new("Fuell", "SUN")
    fill.energy = 0.9
    fill.angle = math.radians(30)
    fo = bpy.data.objects.new("Fuell", fill)
    sc.collection.objects.link(fo)
    fd = Vec((0.7, 0.6, 0.5))
    fo.rotation_euler = (-fd).to_track_quat("-Z", "Y").to_euler()

    # Boden-Schattenfaenger (ohne Raum): Teile stehen nicht im Leeren
    catcher = None
    if not room:
        catcher = _box_mesh(bpy, bmesh, "Schatten", [(-9000, 11000, -9000, 9000, zmin_parts - 0.5, zmin_parts - 0.4)])
        catcher.is_shadow_catcher = True
        sc.render.film_transparent = True

    # ---- Kamera
    W = int(job.get("px", 1600))
    aspect = float(job.get("aspect", 1.6))
    H = int(round(W / aspect))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    az, el = job.get("dir", (-30, 22))
    lens = float(job.get("lens", 40.0))
    fr_pts = pts_parts
    dims = None
    if job.get("dims"):
        dims = _dim_geometry(np, bb, az, el)
        fr_pts = np.vstack([pts_parts] + [np.array([m["a"], m["b"]]) for m in dims])
    if sofa_pts is not None and job.get("frame_room", True):
        cx = np.array([[sofa_pts[0][0], sofa_pts[0][1], sofa_pts[0][2]], [sofa_pts[1][0], sofa_pts[1][1], sofa_pts[1][2]]])
        fr_pts = np.vstack([pts_parts, cx])
    cam_d = frame_camera(np, fr_pts, az, el, lens, aspect, float(job.get("margin", 0.94)), job.get("at"), job.get("size") or 600.0)
    cam = bpy.data.cameras.new("Cam")
    cam.lens, cam.sensor_width, cam.sensor_fit = lens, 36.0, "HORIZONTAL"
    cam.shift_x, cam.shift_y = cam_d["shift"]
    cam.clip_start, cam.clip_end = 5.0, 60000.0
    co = bpy.data.objects.new("Cam", cam)
    sc.collection.objects.link(co)
    M = mathutils.Matrix([[cam_d["r"][0], cam_d["u"][0], cam_d["e"][0], cam_d["C"][0]],
                          [cam_d["r"][1], cam_d["u"][1], cam_d["e"][1], cam_d["C"][1]],
                          [cam_d["r"][2], cam_d["u"][2], cam_d["e"][2], cam_d["C"][2]], [0, 0, 0, 1]])
    co.matrix_world = M
    sc.camera = co

    # ---- Render-Einstellungen
    out = job["out"]
    tmp_png = out + ".tmp.png"
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.filepath = tmp_png
    if cycles:
        sc.render.engine = "CYCLES"
        c = sc.cycles
        c.device = "CPU"
        c.samples = int(job.get("samples", 40))
        c.use_adaptive_sampling = True
        c.adaptive_threshold = 0.02
        c.use_denoising = True
        try:
            c.denoiser = "OPENIMAGEDENOISE"
        except Exception:
            pass
        c.max_bounces = 6
        c.diffuse_bounces = 4
        c.glossy_bounces = 3
        c.transmission_bounces = 4
        c.transparent_max_bounces = 6
        c.sample_clamp_indirect = 10.0
        sc.render.threads_mode = "FIXED"
        sc.render.threads = int(os.environ.get("CAD_RENDER_THREADS_SCHOEN", "8"))
    else:
        sc.render.engine = "BLENDER_EEVEE"
        try:
            sc.eevee.taa_render_samples = int(job.get("samples", 40))
            sc.eevee.use_raytracing = bool(job.get('rt', True))
            sc.eevee.use_shadows = True
        except Exception:
            pass
    sc.view_settings.view_transform = "AgX"
    for tr in ("Khronos PBR Neutral", "AgX"):
        try:
            sc.view_settings.view_transform = tr
            break
        except TypeError:
            continue
    sc.view_settings.look = "None"
    sc.render.use_freestyle = bool(job.get("lines", True))
    if sc.render.use_freestyle:
        try:
            vl = bpy.context.view_layer
            vl.use_freestyle = True
            ls = vl.freestyle_settings.linesets.new("kanten") if not vl.freestyle_settings.linesets else vl.freestyle_settings.linesets[0]
            ls.select_silhouette = ls.select_border = ls.select_crease = True
            ls.select_by_visibility = True
            colp = bpy.data.collections.new("Teile")          # Kanten nur an den Bauteilen (nicht an Boden/Wand/Schattenfaenger)
            sc.collection.children.link(colp)
            for o in objs.values():
                for c_ in list(o.users_collection):
                    c_.objects.unlink(o)
                colp.objects.link(o)
            ls.select_by_collection = True
            ls.collection = colp
            st = ls.linestyle or bpy.data.linestyles.new("kanten")
            ls.linestyle = st
            st.color = (0.16, 0.10, 0.05)
            st.alpha = 0.85
            st.thickness = float(job.get("line_px", 1.3))
            sc.render.line_thickness_mode = "ABSOLUTE"
            sc.render.line_thickness = 1.0
        except Exception as e:
            sc.render.use_freestyle = False
            WARN.append("Freestyle-Kanten nicht aktiv: %s: %s" % (type(e).__name__, e))
    sc.render.use_motion_blur = False
    sc.render.use_stamp = False

    t_r = time.time()
    if not job.get("no_render"):
        bpy.ops.render.render(write_still=True)
    tim["render"] = round(time.time() - t_r, 2)

    result = {"out": out, "bbox": bb, "views": [], "caption": list(job.get("caption") or []), "triangles": int(sum(len(o.data.polygons) for o in objs.values()))}
    names = list(objs)
    # ---- Nummernmarken (Explosion/Nummernliste): ID-Pass mit Workbench, damit Marken auf sichtbaren Flaechen stehen
    numbers = {}
    if job.get("render", True) is not False and not job.get("no_render") and job.get("numbers"):
        numbers = _id_pass(np, bpy, sc, objs, extra, catcher, W, H, Image)
    tim["idpass"] = round(time.time() - t_r - tim["render"], 2)

    if not job.get("no_render"):
        img = Image.open(tmp_png).convert("RGBA")
        bgc = job.get("bg", "weiss")
        if not room:
            if bgc == "transparent":
                canvas = img
            else:
                top, bot = ((255, 255, 255), (222, 224, 228)) if bgc == "weiss" else ((120, 124, 130), (70, 72, 78))
                gr = np.linspace(0, 1, H)[:, None, None]
                arr = np.array(top)[None, None, :] * (1 - gr) + np.array(bot)[None, None, :] * gr
                arr = np.repeat(arr, W, axis=1).astype("uint8")
                canvas = Image.fromarray(arr, "RGB").convert("RGBA")
                canvas.alpha_composite(img)
        else:
            canvas = img
        if bgc != "transparent" or room:
            canvas = canvas.convert("RGB")
        font = cr.load_font(ImageFont, 15)
        fontb = cr.load_font(ImageFont, 16)
        if dims:
            canvas = _draw_dims(np, canvas.convert("RGBA"), ImageDraw, fontb, dims, cam_d, W, H)
        if numbers:
            canvas = _draw_numbers(np, canvas, Image, ImageDraw, fontb, numbers, names, offsets, centers, cam_d, W, H, expl)
        items = [{"rgb": MATERIALS[k]["rgb"], "text": MATERIALS[k]["label"]} for k in tuple(k for k in MATERIALS if k != "platzhalter") + ("platzhalter",)
                 if any(info[n]["mat"] == k for n in names)]
        if any(is_cable(n) for n in names):
            items.append({"rgb": CABLE_RGB, "text": "Kabelweg (Prüfkörper)"})
        if room and extra:
            items.append({"rgb": (0.50, 0.50, 0.51), "text": "Sofa (Schätzung)"})
        lines = list(result["caption"])
        if numbers:
            canvas = _legend_table(np, canvas, Image, ImageDraw, font, numbers, names, info, items, lines)
        elif not job.get("no_legend"):
            if bgc == "transparent" and not room:
                bgwhite = Image.new("RGBA", canvas.size, (255, 255, 255, 255))
                strip = cr.add_strip(Image.new("RGB", canvas.size, (255, 255, 255)), lines, items, Image, ImageDraw, font)
                full = Image.new("RGBA", strip.size, (255, 255, 255, 255))
                full.paste(canvas, (0, 0))
                canvas = full
                canvas.paste(strip.crop((0, H, strip.width, strip.height)), (0, H))
            else:
                canvas = cr.add_strip(canvas.convert("RGB"), lines, items, Image, ImageDraw, font)
        canvas.save(out)
        os.unlink(tmp_png)
        result["size"] = list(canvas.size)
    cam_txt = "Perspektive %g mm (Blickrichtung az %g, el %g), Abstand %.0f mm, Stil schön (%s, %d Samples)" % (
        lens, az, el, cam_d["d"], "Cycles+Denoise" if cycles else "EEVEE", int(job.get("samples", 40)))
    result["views"].append({"text": cam_txt, "dir": [az, el], "lens": lens, "distance": round(float(cam_d["d"]), 1)})
    if sec_text:
        result["caption"].append(sec_text)
    result["time_detail"] = tim
    result["parts"] = names
    result["offsets"] = {n: [round(x, 1) for x in o] for n, o in offsets.items()}

    # ---- GLB
    if job.get("glb"):
        t_g = time.time()
        glb_info = export_glb(job, bpy, np, bmesh, Image, paths, mathutils)
        glb_info["seconds"] = round(time.time() - t_g, 2)
        result["glb"] = glb_info
    return result


def _id_pass(np, bpy, sc, objs, extra, catcher, W, H, Image):
    """Je Teil eine eindeutige Flachfarbe, Workbench ohne Glaettung -> je Teil sichtbare Pixel (Marken auf sichtbaren Flaechen)."""
    levels = [0.0, 0.25, 0.5, 0.75, 1.0]
    combos = [(r, g, b) for r in levels for g in levels for b in levels][1:]
    for o in extra:
        o.hide_render = True
    if catcher is not None:
        catcher.hide_render = True
    sc.render.film_transparent = False
    sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.use_freestyle = False
    sh = sc.display.shading
    sh.light, sh.color_type, sh.show_shadows, sh.show_cavity, sh.show_object_outline = "FLAT", "OBJECT", False, False, False
    sc.display.render_aa = "OFF"
    sc.view_settings.view_transform = "Standard"
    sc.render.filepath = sc.render.filepath + ".id.png"
    names = list(objs)
    code = {}
    for i, n in enumerate(names):
        c = combos[i % len(combos)]
        objs[n].color = (c[0], c[1], c[2], 1.0)
        code[n] = c
    bpy.ops.render.render(write_still=True)
    arr = np.array(Image.open(sc.render.filepath).convert("RGB"))
    os.unlink(sc.render.filepath)
    enc = lambda x: np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(np.clip(x, 0, 1), 1 / 2.4) - 0.055)
    lv = enc(np.array(levels)) * 255.0                              # erwartete 8-Bit-Werte je Stufe
    q = np.abs(arr[..., None].astype(float) - lv[None, None, None, :]).argmin(-1)      # H x W x 3 Stufenindex
    err = np.abs(arr.astype(float) - lv[q]).max(-1)
    key = q[..., 0] * 25 + q[..., 1] * 5 + q[..., 2]
    lut = np.full(125, -1, dtype=np.int32)
    for i, n in enumerate(names):
        c = code[n]
        lut[levels.index(c[0]) * 25 + levels.index(c[1]) * 5 + levels.index(c[2])] = i
    idx = np.where(err < 12, lut[key], -1)
    res = {}
    for i, n in enumerate(names):
        ys, xs = np.nonzero(idx == i)
        res[n] = {"i": i + 1, "px": int(len(xs))}
        if len(xs) > 30:
            res[n]["ys"], res[n]["xs"] = ys, xs
    return res


def _dim_geometry(np, bb, az, el):
    """Gesamtmasse (L=X, B=Y, H=Z) der Bounding Box als Bemassungslinien an den dem Betrachter zugewandten Kanten.
    Liefert Liste {axis, a, b, ea, eb, text}: a/b = Endpunkte der Masslinie, ea/eb = Fusspunkte am Modell (Hilfslinien)."""
    e, r, u = _basis(az, el)
    lo, hi = np.array(bb[:3], float), np.array(bb[3:], float)
    ext = hi - lo
    off = 0.10 * float(ext.max()) + 5.0
    sx = 1.0 if e[0] >= 0 else -1.0
    sy = 1.0 if e[1] >= 0 else -1.0
    fx = hi[0] if sx > 0 else lo[0]
    fy = hi[1] if sy > 0 else lo[1]
    dims = []
    # X: Unterkante an der Kamera-Seite
    ea, eb = np.array([lo[0], fy, lo[2]]), np.array([hi[0], fy, lo[2]])
    d = np.array([0.0, sy * off, 0.0])
    dims.append({"axis": 0, "a": ea + d, "b": eb + d, "ea": ea, "eb": eb, "val": ext[0]})
    # Y: Unterkante an der Kamera-Seite
    ea, eb = np.array([fx, lo[1], lo[2]]), np.array([fx, hi[1], lo[2]])
    d = np.array([sx * off, 0.0, 0.0])
    dims.append({"axis": 1, "a": ea + d, "b": eb + d, "ea": ea, "eb": eb, "val": ext[1]})
    # Z: senkrechte Kante, die auf dem Bild am weitesten links liegt
    best = None
    for cx in (lo[0], hi[0]):
        for cy in (lo[1], hi[1]):
            sc = float(np.array([cx, cy, lo[2]]) @ r)
            if best is None or sc < best[0]:
                best = (sc, cx, cy)
    _, cx, cy = best
    rh = np.array([r[0], r[1], 0.0])
    rh = rh / (np.linalg.norm(rh) + 1e-9)
    d = -rh * off
    ea, eb = np.array([cx, cy, lo[2]]), np.array([cx, cy, hi[2]])
    dims.append({"axis": 2, "a": ea + d, "b": eb + d, "ea": ea, "eb": eb, "val": ext[2]})
    return dims


def _draw_dims(np, canvas, ImageDraw, font, dims, cam, W, H):
    d = ImageDraw.Draw(canvas, "RGBA")
    cols = [(200, 40, 40), (30, 140, 60), (40, 80, 200)]

    def proj(P):
        x, y, _ = _project(np, np.asarray(P, float), cam["C"], cam["e"], cam["r"], cam["u"], cam["tw"], cam["th"])
        x, y = x - cam["c"][0], y - cam["c"][1]
        return (float(x) + 1) / 2 * W, (1 - float(y)) / 2 * H
    for m in dims:
        col = cols[m["axis"]] + (255,)
        a, b = proj(m["a"]), proj(m["b"])
        for e0, p in ((m["ea"], a), (m["eb"], b)):
            q = proj(e0)
            d.line([q, p], fill=cols[m["axis"]] + (150,), width=1)
        d.line([a, b], fill=col, width=2)
        ln = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        ux, uy = (b[0] - a[0]) / ln, (b[1] - a[1]) / ln
        for p, sgn in ((a, 1), (b, -1)):
            tip = p
            bx, by = p[0] + sgn * ux * 13, p[1] + sgn * uy * 13
            nx, ny = -uy * 4.5, ux * 4.5
            d.polygon([tip, (bx + nx, by + ny), (bx - nx, by - ny)], fill=col)
        t = "%.1f mm" % m["val"]
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        w = d.textlength(t, font=font)
        d.rounded_rectangle([mx - w / 2 - 6, my - 12, mx + w / 2 + 6, my + 12], radius=6, fill=(255, 255, 255, 240), outline=col, width=2)
        d.text((mx - w / 2, my - 9), t, fill=(20, 20, 20, 255), font=font)
    return canvas


def _draw_numbers(np, canvas, Image, ImageDraw, font, numbers, names, offsets, centers, cam, W, H, expl):
    d = ImageDraw.Draw(canvas, "RGBA")
    placed = []

    def proj(P):
        x, y, _ = _project(np, np.asarray(P, float), cam["C"], cam["e"], cam["r"], cam["u"], cam["tw"], cam["th"])
        x, y = x - cam["c"][0], y - cam["c"][1]
        return (float(x) + 1) / 2 * W, (1 - float(y)) / 2 * H
    # gestrichelte Montagelinien: Ursprungsmitte -> Position in der Explosion
    if expl:
        for n in names:
            off = offsets.get(n)
            if not off or max(abs(v) for v in off) < 1:
                continue
            a = proj(centers[n])
            b = proj([centers[n][i] + off[i] for i in range(3)])
            ln = math.hypot(b[0] - a[0], b[1] - a[1])
            k = max(int(ln // 9), 1)
            for j in range(k):
                if j % 2 == 0:
                    t0, t1 = j / k, min((j + 1) / k, 1)
                    d.line([(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0), (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)], fill=(60, 60, 60, 150), width=2)
    R = 13
    for n in sorted(names, key=lambda k: numbers[k]["px"]):
        e = numbers[n]
        if "xs" not in e:
            e["pos"] = None
            continue
        xs, ys = e["xs"], e["ys"]
        cx, cy = xs.mean(), ys.mean()
        rng = np.random.default_rng(e["i"])
        sel = rng.choice(len(xs), size=min(400, len(xs)), replace=False)
        cand = np.stack([xs[sel], ys[sel]], 1).astype(float)
        score = []
        for c in cand:
            dp = min([math.hypot(c[0] - p[0], c[1] - p[1]) for p in placed] + [999.0])
            edge = min(c[0], c[1], W - c[0], H - c[1])
            score.append(min(dp, 2 * R + 10) * 3 - math.hypot(c[0] - cx, c[1] - cy) * 0.25 + min(edge, R + 4))
        c = cand[int(np.argmax(score))]
        placed.append((c[0], c[1]))
        e["pos"] = (float(c[0]), float(c[1]))
    for n in names:
        e = numbers[n]
        if e.get("pos"):
            x, y = e["pos"]
            d.ellipse([x - R, y - R, x + R, y + R], fill=(255, 255, 255, 235), outline=(20, 20, 20, 255), width=2)
            t = str(e["i"])
            w = d.textlength(t, font=font)
            d.text((x - w / 2, y - 9), t, fill=(10, 10, 10, 255), font=font)
    return canvas


def _legend_table(np, canvas, Image, ImageDraw, font, numbers, names, info, items, lines):
    """Legende unter dem Bild: Nummer -> Name -> Material in Spalten, davor Materialfarben und Textzeilen."""
    import cad_render as cr
    W = canvas.width
    cols = 3
    rows = (len(names) + cols - 1) // cols
    rh = 20
    tmp = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    txt = []
    for ln in lines:
        txt += cr.wrap_text(tmp, ln, font, W - 12)
    sw_h = 22 if items else 0
    H2 = sw_h + len(txt) * 17 + rows * rh + 16
    out = Image.new("RGB", (W, canvas.height + H2), (255, 255, 255))
    out.paste(canvas.convert("RGB"), (0, 0))
    d = ImageDraw.Draw(out)
    y = canvas.height + 6
    x = 8
    for it in items:
        d.rectangle([x, y + 2, x + 13, y + 15], fill=tuple(int(255 * v) for v in it["rgb"]), outline=(40, 40, 40))
        d.text((x + 18, y), it["text"], fill=(20, 20, 20), font=font)
        x += 18 + int(d.textlength(it["text"], font=font)) + 18
    y += sw_h
    for t in txt:
        d.text((8, y), t, fill=(20, 20, 20), font=font)
        y += 17
    y += 4
    colw = W // cols
    order = sorted(names, key=lambda n: numbers[n]["i"])
    for k, n in enumerate(order):
        cx = 8 + (k // rows) * colw
        cy = y + (k % rows) * rh
        e = numbers[n]
        key = info[n]["mat"]
        rgb = CABLE_RGB if is_cable(n) else MATERIALS[key]["rgb"]
        d.ellipse([cx - 3, cy + 0, cx + 20, cy + 19], fill=(255, 255, 255), outline=(20, 20, 20), width=1)
        t = str(e["i"])
        d.text((cx + 8.5 - d.textlength(t, font=font) / 2, cy + 1), t, fill=(10, 10, 10), font=font)
        d.rectangle([cx + 23, cy + 4, cx + 33, cy + 15], fill=tuple(int(255 * v) for v in rgb), outline=(40, 40, 40))
        short = {"eiche": "Eiche", "multiplex": "Multiplex", "hartholz": "Hartholz", "platzhalter": "Platzhalter"}.get(key, key.upper())
        d.text((cx + 40, cy), "%s (%s)%s" % (n, short, "" if e.get("px", 0) > 30 else " verdeckt"), fill=(20, 20, 20), font=font)
    return out


# ----------------------------------------------------------------------------------------- GLB
def export_glb(job, bpy, np, bmesh, Image, paths, mathutils):
    """Eigene, saubere Szene: Teile als benannte Meshes in Metern, PBR-Materialien mit eingebetteten Texturen (JPEG)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    objs = _read_scene_objects(bpy, bmesh, np, job["parts"])
    mb = MatBook(bpy, paths, cycles=False, simple=True)
    for p in job["parts"]:
        o = objs[p["name"]]
        slots, kind = mb.part_slots(p["mat"], p["name"])
        if kind:
            _assign_uv_and_slots(np, o, kind, p["name"])
        for m in slots:
            o.data.materials.append(m)
        _smooth_by_angle(bmesh, o, 32.0)
    for n in job.get("hide") or []:
        if n in objs:
            bpy.data.objects.remove(objs[n], do_unlink=True)
    if job.get("room"):
        cfg = job.get("room_cfg") or {}
        wy = float(cfg.get("wall_y", 230.0))
        sw, sd, sh = [float(x) for x in cfg.get("sofa", (2400, 960, 750))]
        allv = np.vstack([_verts_np(np, o) for o in bpy.data.objects if o.type == "MESH"])
        sx0 = float(cfg.get("sofa_x0", (allv[:, 0].min() + allv[:, 0].max()) / 2 - sw / 2))
        fl = _box_mesh(bpy, bmesh, "Boden", [(-3500, 7000, -4500, wy + 100, -40, 0)])
        wl = _box_mesh(bpy, bmesh, "Wand", [(-3500, 7000, wy, wy + 100, 0, 2700)])
        sf = _box_mesh(bpy, bmesh, "Sofa_Schaetzung", [(sx0, sx0 + sw, -sd, 0.0, 0, sh * 0.58), (sx0, sx0 + sw, -min(250.0, sd * 0.28), 0.0, 0, sh), (sx0, sx0 + 170, -sd, 0.0, 0, sh * 0.80), (sx0 + sw - 170, sx0 + sw, -sd, 0.0, 0, sh * 0.80)], bevel=22.0)
        fl.data.materials.append(mb.solid("Boden", _srgb_to_lin((0.66, 0.63, 0.58)), 0.55))
        wl.data.materials.append(mb.solid("Wand", _srgb_to_lin((0.90, 0.89, 0.86)), 0.9))
        sf.data.materials.append(mb.solid("Sofa", _srgb_to_lin((0.50, 0.50, 0.51)), 0.9))
    # mm -> m
    for o in list(bpy.data.objects):
        if o.type != "MESH":
            continue
        if o.modifiers:
            dg = bpy.context.evaluated_depsgraph_get()
            ev = o.evaluated_get(dg)
            newme = bpy.data.meshes.new_from_object(ev)
            newme.name = o.name
            o.modifiers.clear()
            o.data = newme
        o.data.transform(mathutils.Matrix.Scale(0.001, 4))
        o.data.update()
    path = job["glb"]
    kw = dict(filepath=path, export_format="GLB", export_yup=True, export_apply=True, use_selection=False, export_materials="EXPORT",
              export_cameras=False, export_lights=False)
    props = bpy.ops.export_scene.gltf.get_rna_type().properties
    if "export_image_format" in props:
        kw["export_image_format"] = "JPEG"
    if "export_jpeg_quality" in props:
        kw["export_jpeg_quality"] = 85
    bpy.ops.export_scene.gltf(**kw)
    return {"path": path, "bytes": os.path.getsize(path), "objects": sum(1 for o in bpy.data.objects if o.type == "MESH")}


if __name__ == "__main__":
    try:
        import bpy  # noqa: F401
        IN_BLENDER = True
    except ImportError:
        IN_BLENDER = False
    if IN_BLENDER:
        blender_main()
    else:
        print(__doc__)
