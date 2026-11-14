#!/usr/bin/env python3
"""cad_render - STL -> PNG mit Lineal und Textlegende (Blender-Workbench, headless, ohne DISPLAY).

Zwei Betriebsarten in einer Datei:
  * normales Python (Client):  run_job(job) startet  env -u LD_LIBRARY_PATH -u DISPLAY blender -b --python cad_render.py -- job.json
  * innerhalb von Blender:     rendert alle Ansichten des Jobs in einem Blender-Start, legt Lineale/Beschriftung per PIL darueber.
Eigenstaendig nutzbar:  cad_render.py modell.stl [-o out.png] [--view sheet|iso|front|back|left|right|top|bottom]
                        [--dir az,el] [--at x,y,z --size mm] [--box x0,y0,z0,x1,y1,z1] [--px N] [--persp] [--json]

Koordinaten: 1 Blender-Einheit = 1 mm = 1 Modell-mm (STL unveraendert). Kamera standardmaessig orthografisch, damit
Lineal-Werte exakte Modellkoordinaten sind. Blickrichtung ueber Azimut/Elevation: az 0 = Blick von vorn (von -Y), 90 = von
rechts (+X), el 90 = von oben.
"""
import json, math, os, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
PRESETS = {  # Name -> (azimut, elevation) der Kameraposition
    "iso": (40, 30), "front": (0, 0), "back": (180, 0), "right": (90, 0), "left": (270, 0),
    "top": (0, 90), "bottom": (0, -90),
}
SHEET_VIEWS = ["iso", "front", "right", "top"]
DEFAULT_PX = 800
SHEET_MAX = 1024
SHEET_W, SHEET_H = 1450, 2000    # Sheets (mehrere Kacheln): Breite/Hoehe-Grenze, damit Kacheln lesbar bleiben
MAX_IMG = 1100          # harte Obergrenze fuer die Kantenlaenge des fertigen Bildes (Render <= 1024 plus Lineal-Rand)
LIGHT = ("STUDIO", "studio.sl")   # Studio-Licht: Flaechenrichtung lesbar (Matcap basic_bright war flach)
PALETTE = [(0.95, 0.97, 1.0), (1.0, 0.82, 0.68), (0.78, 1.0, 0.8), (1.0, 0.8, 0.95), (1.0, 0.97, 0.7)]


# ============================================================================================ Client
def blender_exe():
    import shutil
    return os.environ.get("CAD_BLENDER") or shutil.which("blender")


def blender_env():
    """Umgebung wie fuer `env -u LD_LIBRARY_PATH -u DISPLAY blender` (sonst glibc-Fehler bzw. Display-Abhaengigkeit)."""
    e = {k: v for k, v in os.environ.items() if k not in ("LD_LIBRARY_PATH", "DISPLAY", "WAYLAND_DISPLAY")}
    e.setdefault("HOME", os.path.expanduser("~"))
    e.setdefault("LP_NUM_THREADS", os.environ.get("CAD_RENDER_THREADS", "4"))   # Software-GL: nicht alle Kerne belegen (Straggler bei Last)
    return e


def blender_cmd(job_path, script=None):
    return [blender_exe(), "-b", "--factory-startup", "-t", os.environ.get("CAD_RENDER_THREADS", "4"), "--python", script or os.path.abspath(__file__), "--", job_path]


def _slot(n=3):
    """Hoechstens n gleichzeitige Blender-Render (flock-Slots): bei vielen parallelen Prozessen gab es 30-s-Ausreisser."""
    import fcntl
    d = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    while True:
        for i in range(n):
            f = open(os.path.join(d, "cad_render.slot%d" % i), "a+")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return f
            except OSError:
                f.close()
        time.sleep(0.1)


def run_job(job, timeout=120, script=None):
    """Fuehrt den Job aus. Gibt das Legenden-Dict zurueck (Schluessel 'ok','out','views','seconds',...)."""
    t0 = time.time()
    job = dict(job)
    fd, jp = tempfile.mkstemp(prefix="cadjob_", suffix=".json", dir=os.environ.get("CAD_TMP") or None)
    os.close(fd)
    leg = jp + ".legend.json"
    job["legend_out"] = leg
    json.dump(job, open(jp, "w"))
    slot = _slot(int(os.environ.get("CAD_RENDER_SLOTS", "3")))
    try:
        p = subprocess.run(blender_cmd(jp, script), env=blender_env(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout, text=True)
        if os.path.exists(leg):
            res = json.load(open(leg))
        else:
            tail = "\n".join(p.stdout.strip().splitlines()[-6:])
            res = {"ok": False, "error": "Blender lieferte keine Legende (Exit %d): %s" % (p.returncode, tail)}
    except subprocess.TimeoutExpired:
        res = {"ok": False, "error": "Blender-Zeitueberschreitung (%ds)" % timeout}
    finally:
        slot.close()
        for f in (jp, leg):
            try:
                os.unlink(f)
            except OSError:
                pass
    res["seconds"] = round(time.time() - t0, 2)
    return res


def legend_text(res):
    if not res.get("ok"):
        return "FEHLER: " + str(res.get("error"))
    L = ["Bild: %s  (%dx%d px, %.1fs)" % (res["out"], res["size"][0], res["size"][1], res["seconds"])]
    for v in res["views"]:
        L.append("  " + v["text"])
    for c in res.get("caption") or []:
        L.append("  " + c)
    if res.get("bbox"):
        b = res["bbox"]
        L.append("  Modell-BBox x %.2f..%.2f  y %.2f..%.2f  z %.2f..%.2f  (%.1f x %.1f x %.1f mm)" %
                 (b[0], b[3], b[1], b[4], b[2], b[5], b[3] - b[0], b[4] - b[1], b[5] - b[2]))
    return "\n".join(L)


def parse_vec(s, n):
    v = [float(x) for x in s.replace(";", ",").split(",")]
    if len(v) != n:
        raise ValueError("erwarte %d Zahlen: %r" % (n, s))
    return v


def view_from_args(name=None, dir_=None, at=None, size=None, box=None, persp=False, px=None, cut=None, label=None):
    v = {"name": name or "iso", "persp": bool(persp)}
    if cut is not None:
        v["cut"] = float(cut)
    if label:
        v["focus_name"] = label
    if dir_:
        v["dir"] = parse_vec(dir_, 2) if isinstance(dir_, str) else list(dir_)
        v["name"] = name or "dir %g,%g" % tuple(v["dir"])
    else:
        n = name or "iso"
        if n not in PRESETS:
            raise ValueError("unbekannte Ansicht %r (iso front back left right top bottom oder --dir az,el)" % n)
        v["dir"] = list(PRESETS[n])
    if at:
        v["at"] = parse_vec(at, 3) if isinstance(at, str) else list(at)
        v["size"] = float(size or 20)
    if box:
        v["box"] = parse_vec(box, 6) if isinstance(box, str) else list(box)
    if px:
        v["px"] = int(px)
    return v


def cli_main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stl", nargs="+")
    ap.add_argument("-o", "--out")
    ap.add_argument("--view", default="sheet")
    ap.add_argument("--dir"); ap.add_argument("--at"); ap.add_argument("--size", type=float); ap.add_argument("--box")
    ap.add_argument("--px", type=int); ap.add_argument("--persp", action="store_true")
    ap.add_argument("--cut", type=float, help="Geometrie weiter als CUT mm vor der Zielebene (--at) wegschneiden")
    ap.add_argument("--edges", default="freestyle", choices=["freestyle", "outline", "none"])
    ap.add_argument("--no-ruler", action="store_true"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    out = a.out or os.path.join("/mnt/raid1/3d_print/cad_out", os.path.splitext(os.path.basename(a.stl[0]))[0] + "_%s.png" % a.view)
    job = {"models": [{"path": os.path.abspath(p)} for p in a.stl], "out": out, "edges": a.edges, "ruler": not a.no_ruler}
    if a.view == "sheet" and not (a.dir or a.at or a.box):
        job["sheet"] = True
        job["views"] = [view_from_args(n) for n in SHEET_VIEWS]
    else:
        job["views"] = [view_from_args(None if a.dir else a.view, a.dir, a.at, a.size, a.box, a.persp, a.px, a.cut)]
    res = run_job(job)
    print(json.dumps(res, indent=1) if a.json else legend_text(res))
    return 0 if res.get("ok") else 3


# ============================================================================================ Blender-Teil
def blender_main():
    import bpy, mathutils
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    job = json.load(open(sys.argv[sys.argv.index("--") + 1]))
    t_start = time.time()
    result = {"ok": False}
    try:
        result = render_job(job, bpy, mathutils, np, Image, ImageDraw, ImageFont)
        result["ok"] = True
    except Exception as e:  # Fehler als Text zurueck, nicht als Blender-Traceback
        import traceback
        result = {"ok": False, "error": "%s: %s" % (type(e).__name__, e), "trace": traceback.format_exc()}
    result["blender_seconds"] = round(time.time() - t_start, 2)
    json.dump(result, open(job["legend_out"], "w"))


def nice_step(mm_per_px, min_px=48):
    for e in range(-2, 5):
        for m, minor in ((1, 5), (2, 4), (5, 5)):
            st = m * 10.0 ** e
            if st / mm_per_px >= min_px:
                return st, st / minor
    return 1000.0, 200.0


def fmt(v, step):
    d = 0 if step >= 1 else (1 if step >= 0.1 else 2)
    s = "%.*f" % (d, v + 0.0)
    return "0" if float(s) == 0 else s


CAP_COLOR = (1.0, 0.5, 0.4)
OVERHANG_COLORS = {"neutral": (0.80, 0.82, 0.85), "slant": (0.92, 0.10, 0.08), "bridge": (1.0, 0.70, 0.05)}


def paint_overhang(objs, np, zref, angle=45.0):
    """Vertex-Farben nach Normalenwinkel (Logik wie overhang_check.py): nach unten zeigend, flacher als `angle`-1 Grad zur
    Waagerechten und hoeher als 0.3 mm ueber der Bauplatte -> rot (schraeg) bzw. orange (waagerecht, Bruecke)."""
    for o in objs:
        me = o.data
        n = len(me.polygons)
        nrm = np.empty(n * 3); me.polygons.foreach_get("normal", nrm); nrm = nrm.reshape(n, 3)
        co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
        lv = np.empty(len(me.loops), dtype=np.int64); me.loops.foreach_get("vertex_index", lv)
        lt = np.empty(n, dtype=np.int64); me.polygons.foreach_get("loop_total", lt)
        ls_ = np.empty(n, dtype=np.int64); me.polygons.foreach_get("loop_start", ls_)
        zc = co[lv[ls_], 2] / 3 + co[lv[ls_ + 1], 2] / 3 + co[lv[ls_ + 2], 2] / 3
        nz = nrm[:, 2]
        incl = np.degrees(np.arccos(np.clip(-nz, -1, 1)))
        crit = (nz < -1e-6) & (zc - zref >= 0.3) & (incl < angle - 1)
        col = np.tile(np.array(OVERHANG_COLORS["neutral"] + (1.0,)), (n, 1))
        col[crit & (incl >= 5)] = OVERHANG_COLORS["slant"] + (1.0,)
        col[crit & (incl < 5)] = OVERHANG_COLORS["bridge"] + (1.0,)
        per_loop = np.repeat(col, lt, axis=0)
        attr = me.color_attributes.new("c", "FLOAT_COLOR", "CORNER")
        attr.data.foreach_set("color", per_loop.ravel())
        me.color_attributes.active_color = attr
        me.color_attributes.render_color_index = len(me.color_attributes) - 1


FONT_CANDIDATES = ["/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf",
                   "/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def load_font(ImageFont, size):
    """Schrift mit Umlauten (DejaVu/Liberation); sonst Pillow-Standard (dann ohne Umlaute, siehe ascii_ok)."""
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except OSError:
                pass
    return ImageFont.load_default(size=size)


def wrap_text(d, text, font, width):
    out, cur = [], ""
    for w in text.split(" "):
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= width or not cur:
            cur = t
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out


def add_strip(img, lines, items, Image, ImageDraw, font):
    """Textstreifen unter das Bild: Legende (Farbfelder) und Beschriftungszeilen."""
    if not lines and not items:
        return img
    tmp = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    W = img.width
    rows = []
    for ln in lines or []:
        rows += wrap_text(tmp, ln, font, W - 12)
    sw = []
    x, y = 6, 0
    for it in items or []:
        tw = tmp.textlength(it["text"], font=font)
        if x + 20 + tw > W - 6 and x > 6:
            x, y = 6, y + 18
        sw.append((x, y, it))
        x += 20 + tw + 16
    item_h = (y + 18) if items else 0
    h = item_h + 16 * len(rows) + 10
    out = Image.new("RGB", (W, img.height + h), (255, 255, 255))
    out.paste(img, (0, 0))
    d = ImageDraw.Draw(out)
    d.line([(0, img.height), (W, img.height)], fill=(150, 150, 150))
    for (x, y, it) in sw:
        c = tuple(int(255 * v) for v in it["rgb"])
        d.rectangle([x, img.height + 5 + y, x + 13, img.height + 18 + y], fill=c, outline=(40, 40, 40))
        d.text((x + 18, img.height + 4 + y), it["text"], fill=(20, 20, 20), font=font)
    ty = img.height + item_h + 5
    for r in rows:
        d.text((6, ty), r, fill=(20, 20, 20), font=font)
        ty += 16
    return out


def render_job(job, bpy, mathutils, np, Image, ImageDraw, ImageFont):
    Vec = mathutils.Vector
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    # ---- Modelle laden ---------------------------------------------------------------------------
    imp = getattr(bpy.ops.wm, "stl_import", None) or bpy.ops.import_mesh.stl
    objs, allv, omodel = [], [], []
    for i, m in enumerate(job["models"]):
        before = set(bpy.data.objects)
        imp(filepath=m["path"])
        new = [o for o in bpy.data.objects if o not in before]
        if not new:
            raise RuntimeError("STL nicht lesbar: %s" % m["path"])
        for o in new:
            col = m.get("color") or PALETTE[i % len(PALETTE)]
            o.color = (col[0], col[1], col[2], 1.0)
            n = len(o.data.vertices)
            a = np.empty(n * 3, dtype=np.float64)
            o.data.vertices.foreach_get("co", a)
            allv.append(a.reshape(n, 3))   # Objekt-Transform = Identitaet (kein global_scale)
            objs.append(o)
            omodel.append(i)
    mode = job.get("mode", "shaded")
    if mode == "overhang":
        zref = job.get("zref")
        if zref is None:
            zref = float(min(a[:, 2].min() for a in allv))
        paint_overhang(objs, np, zref, job.get("angle", 45.0))
    cap_objs = []
    if mode == "section":
        col_main = bpy.data.collections.new("main")
        col_cap = bpy.data.collections.new("cap")
        scene.collection.children.link(col_main)
        scene.collection.children.link(col_cap)
        capc = job.get("cap_color", CAP_COLOR)
        for o in list(objs):
            scene.collection.objects.unlink(o)
            col_main.objects.link(o)
            c = bpy.data.objects.new(o.name + "_cap", o.data.copy())
            c.data.flip_normals()              # Rueckseiten (Blick ins Innere) werden zur Vorderseite -> Schnittflaeche
            c.color = (capc[0], capc[1], capc[2], 1.0)
            col_cap.objects.link(c)
            cap_objs.append(c)
    V = np.concatenate(allv)
    if len(V) == 0:
        raise RuntimeError("leeres Modell")
    bmin, bmax = V.min(0), V.max(0)
    bbox = [float(x) for x in list(bmin) + list(bmax)]
    diag = float(np.linalg.norm(bmax - bmin)) or 1.0
    cen = (bmin + bmax) / 2
    if len(V) > 300000:
        Vs = V[np.random.RandomState(0).choice(len(V), 300000, replace=False)]
    else:
        Vs = V

    # ---- Szene: Workbench, Licht, Kanten -----------------------------------------------------------
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.resolution_percentage = 100
    scene.display.render_aa = "8"
    try:
        scene.view_settings.view_transform = "Standard"
    except TypeError:
        pass
    sh = scene.display.shading
    sh.light = job.get("light", LIGHT[0])
    sh.studio_light = job.get("studio_light", LIGHT[1] if sh.light == LIGHT[0] else "Default")
    sh.color_type = "VERTEX" if mode == "overhang" else "OBJECT"
    if mode == "section":
        sh.show_backface_culling = True
    if mode in ("xray", "wire"):
        sh.show_xray = True
        sh.xray_alpha = 0.0 if mode == "wire" else 0.3
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.cavity_ridge_factor = 0.8
    sh.cavity_valley_factor = 1.0
    sh.show_object_outline = job.get("edges", "freestyle") != "none"
    sh.object_outline_color = (0.05, 0.05, 0.05)
    sh.show_specular_highlight = False
    scene.display.shading.background_type = "VIEWPORT"
    bg = (0.93, 0.94, 0.95)
    wd = bpy.data.worlds.new("w")
    wd.color = bg
    scene.world = wd
    sh.background_type = "WORLD"
    hid_ls = None
    if job.get("edges", "freestyle") == "freestyle":
        scene.render.use_freestyle = True
        scene.render.line_thickness_mode = "ABSOLUTE"
        scene.render.line_thickness = 1.0
        vl = bpy.context.view_layer
        vl.use_freestyle = True
        fs = vl.freestyle_settings
        fs.crease_angle = math.radians(job.get("crease", 35))
        def mk_lineset(name, vis, color, thick):
            ls = fs.linesets.new(name)
            ls.select_by_visibility = True
            ls.visibility = vis
            ls.select_by_edge_types = True
            ls.select_silhouette = True
            ls.select_border = True
            ls.select_crease = True
            ls.select_contour = False
            if mode == "section":
                ls.select_by_collection = True
                ls.collection = col_main
            ls.linestyle = bpy.data.linestyles.new(name)
            ls.linestyle.color = color
            ls.linestyle.thickness = thick
            return ls
        mk_lineset("edges", "VISIBLE", (0.05, 0.05, 0.05), job.get("line_px", 1.2))
        hid_ls = mk_lineset("hidden", "HIDDEN", (0.25, 0.4, 0.75), 0.9)
        hid_ls.show_render = mode in ("xray", "wire")      # je Kachel schaltbar (v["xray"], z. B. bei verdecktem Fokusziel)

    cam_data = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    # ---- Ansichten ------------------------------------------------------------------------------
    sheet = bool(job.get("sheet"))
    ruler = job.get("ruler", True)
    views = job["views"]
    base_px = job.get("px") or (450 if sheet else DEFAULT_PX)
    tmpdir = tempfile.mkdtemp(prefix="cadrender_")
    cells, vlegs = [], []
    font = load_font(ImageFont, 13)
    font_s = load_font(ImageFont, 11)
    for vi, v in enumerate(views):
        az, el = v["dir"]
        e = Vec((math.sin(math.radians(az)) * math.cos(math.radians(el)),
                 -math.cos(math.radians(az)) * math.cos(math.radians(el)),
                 math.sin(math.radians(el))))
        f = -e
        up = Vec((0, math.copysign(1, el), 0)) if abs(el) >= 89.5 else Vec((0, 0, 1))
        r = f.cross(up).normalized()
        u = r.cross(f).normalized()
        rn, un, fn = np.array(r), np.array(u), np.array(f)
        # Ausschnitt in Bildkoordinaten (a = entlang r, b = entlang u)
        if v.get("box"):
            bx = v["box"]
            pts = np.array([[x, y, z] for x in (bx[0], bx[3]) for y in (bx[1], bx[4]) for z in (bx[2], bx[5])])
            A, B = pts @ rn, pts @ un
            amin, amax, bmin_, bmax_ = A.min(), A.max(), B.min(), B.max()
            pad = max(0.08 * max(amax - amin, bmax_ - bmin_), 0.5)
            amin -= pad; amax += pad; bmin_ -= pad; bmax_ += pad
            focus_pt = np.array([(bx[0] + bx[3]) / 2, (bx[1] + bx[4]) / 2, (bx[2] + bx[5]) / 2])
        elif v.get("at"):
            at = np.array(v["at"], dtype=float)
            h = float(v.get("size", 20)) / 2
            amin, amax = at @ rn - h, at @ rn + h
            bmin_, bmax_ = at @ un - h, at @ un + h
            focus_pt = at
        else:
            A, B = Vs @ rn, Vs @ un
            amin, amax, bmin_, bmax_ = A.min(), A.max(), B.min(), B.max()
            pad = max(0.06 * max(amax - amin, bmax_ - bmin_), 1.0)
            amin -= pad; amax += pad; bmin_ -= pad; bmax_ += pad
            focus_pt = cen
        amid, bmid = (amin + amax) / 2, (bmin_ + bmax_) / 2
        wmm, hmm = amax - amin, bmax_ - bmin_
        long_px = int(v.get("px") or base_px)
        long_px = max(64, min(long_px, SHEET_MAX if not sheet else 600))
        s = max(wmm, hmm) / long_px                       # mm pro Pixel
        W, H = max(16, int(round(wmm / s))), max(16, int(round(hmm / s)))
        # Kameraposition: auf der Blickachse durch das Bildzentrum, weit vor dem Modell
        depth_c = float(focus_pt @ fn)
        center_w = rn * amid + un * bmid + fn * depth_c
        D = 2.0 * diag + float(np.linalg.norm(focus_pt - cen)) + 10
        cam.location = Vec(center_w - fn * D)
        m3 = mathutils.Matrix(((r.x, u.x, -f.x), (r.y, u.y, -f.y), (r.z, u.z, -f.z)))
        cam.rotation_euler = m3.to_euler()
        dep = Vs @ fn
        cam_depth = depth_c - D
        cam_data.clip_start = max(0.01, float(dep.min() - cam_depth) - 1.0)
        cam_data.clip_end = float(dep.max() - cam_depth) + 1.0
        if v.get("cut") is not None:      # alles, was mehr als <cut> mm vor der Zielebene liegt, wegschneiden
            cam_data.clip_start = max(cam_data.clip_start, D - float(v["cut"]))
        if v.get("clip_at") is not None:   # Schnittebene: alles zwischen Kamera und dieser Ebene verschwindet
            cam_data.clip_start = max(0.01, D + float(np.array(v["clip_at"], dtype=float) @ fn) - depth_c)
        persp = bool(v.get("persp"))
        if persp:
            cam_data.type = "PERSP"
            cam_data.sensor_fit = "AUTO"
            cam_data.sensor_width = 36
            cam_data.lens = 36 * D / max(wmm, hmm)
            cam_data.clip_start = max(0.5, cam_data.clip_start if v.get("cut") is not None else 0.5)
        else:
            cam_data.type = "ORTHO"
            cam_data.ortho_scale = max(wmm, hmm)
        scene.render.resolution_x, scene.render.resolution_y = W, H
        for c_ in cap_objs:                               # Schnittflaeche gleichmaessig hell: alle Normalen zur Kamera
            nl = len(c_.data.loops)
            try:
                c_.data.normals_split_custom_set([(-f.x, -f.y, -f.z)] * nl)
            except Exception:
                pass
        vx = mode in ("xray", "wire") or bool(v.get("xray"))
        sh.show_xray = vx
        sh.xray_alpha = 0.0 if mode == "wire" else 0.3
        if hid_ls is not None:
            hid_ls.show_render = vx
        only = v.get("only")                              # Isolation: nur diese Modelle (Teile) in dieser Ansicht
        for k_, o_ in enumerate(objs):
            vis = only is None or omodel[k_] in only
            o_.hide_render = not vis
            if cap_objs:
                cap_objs[k_].hide_render = not vis
        png = os.path.join(tmpdir, "v%d.png" % vi)
        scene.render.filepath = png
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        t_render = time.time() - t0
        img = Image.open(png).convert("RGB")
        arr = np.asarray(img).astype(int)
        mask = np.abs(arr - arr[0, 0]).max(axis=2) > 10          # alles, was nicht Hintergrund ist
        ys, xs = np.nonzero(mask)
        sil = None                                                # Silhouette in Bildkoordinaten (mm, Achse r bzw. u)
        if len(xs):
            sil = [float(amin + xs.min() * s), float(amin + (xs.max() + 1) * s),
                   float(bmax_ - (ys.max() + 1) * s), float(bmax_ - ys.min() * s)]

        # ---- Overlay: Lineal, Gitter, Titel ---------------------------------------------------
        def proj(p):
            p = np.asarray(p, dtype=float)
            return (W / 2 + (p @ rn - amid) / s, H / 2 - (p @ un - bmid) / s)

        axes = {"x": np.array([1.0, 0, 0]), "y": np.array([0, 1.0, 0]), "z": np.array([0, 0, 1.0])}

        def axis_of(vec):
            for k, a in axes.items():
                d = float(vec @ a)
                if abs(abs(d) - 1) < 1e-6:
                    return k, d
            return None, 0

        ah, sh_ = axis_of(rn)
        av, sv_ = axis_of(un)
        axis_aligned = ah is not None and av is not None and not persp
        ML, MB, MT, MR = (54 if ruler else 4), (30 if ruler else 4), 24, 8
        cw_, ch_ = W + ML + MR, H + MT + MB
        canvas = Image.new("RGB", (cw_, ch_), (255, 255, 255))
        canvas.paste(img, (ML, MT))
        ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        ink = (30, 30, 30, 255)
        info_txt = ""
        ox, oy = ML, MT

        def line(p, q, col, w=1):
            d.line([(p[0] + ox, p[1] + oy), (q[0] + ox, q[1] + oy)], fill=col, width=w)

        if ruler and axis_aligned:
            # waagerecht: Koordinate der Achse ah, Wert = sgn * (Bildkoordinate a)
            for (ax, sg, lo, hi, horiz) in ((ah, sh_, amin, amax, True), (av, sv_, bmin_, bmax_, False)):
                vals = sorted([sg * lo, sg * hi])
                step, minor = nice_step(s)
                k0 = math.ceil(vals[0] / minor - 1e-9)
                k1 = math.floor(vals[1] / minor + 1e-9)
                for k in range(k0, k1 + 1):
                    val = k * minor
                    t = sg * val                      # Bildkoordinate
                    major = abs(val / step - round(val / step)) < 1e-6
                    if horiz:
                        px_ = (t - amid) / s + W / 2
                        line((px_, H), (px_, H + (8 if major else 4)), ink)
                        if major:
                            line((px_, 0), (px_, H), (90, 110, 170, 70))
                            txt = fmt(val, step)
                            tw = d.textlength(txt, font=font_s)
                            d.text((px_ + ox - tw / 2, H + oy + 9), txt, fill=ink, font=font_s)
                    else:
                        py_ = H / 2 - (t - bmid) / s
                        line((-0, py_), (-(8 if major else 4), py_), ink)
                        if major:
                            line((0, py_), (W, py_), (90, 110, 170, 70))
                            txt = fmt(val, step)
                            tw = d.textlength(txt, font=font_s)
                            d.text((ox - 11 - tw, py_ + oy - 6), txt, fill=ink, font=font_s)
            _lab = "%s [mm]" % ah.upper() + ("" if sh_ > 0 else " (-)")
            d.text((ox + W - d.textlength(_lab, font=font_s) - 4, H + oy + 9 + 10 - 2), _lab, fill=(150, 30, 30, 255), font=font_s)
            d.text((4, MT - 1 - 0), "%s" % av.upper() + ("" if sv_ > 0 else " (-)"), fill=(150, 30, 30, 255), font=font_s)
            line((0, 0), (0, H), ink); line((0, H), (W, H), ink)
            info_txt = "Lineal: waagerecht %s%s, senkrecht %s%s" % ("+" if sh_ > 0 else "-", ah.upper(), "+" if sv_ > 0 else "-", av.upper())
        elif ruler and not persp:
            # schraege Ansicht: Lineal entlang der Silhouettenkanten der BBox (Werte = Modellkoordinaten)
            corners = {(i, j, k): np.array([(bmin, bmax)[i][0] if False else (bbox[0], bbox[3])[i],
                                            (bbox[1], bbox[4])[j], (bbox[2], bbox[5])[k]]) for i in (0, 1) for j in (0, 1) for k in (0, 1)}
            def faces_cam(axis, side):    # Flaeche der BBox zeigt zur Kamera?
                n = np.zeros(3); n[axis] = 1 if side else -1
                return float(n @ -fn) > 0
            colors = {0: (200, 40, 40, 255), 1: (30, 140, 40, 255), 2: (40, 70, 210, 255)}
            for axis in (0, 1, 2):
                others = [a for a in (0, 1, 2) if a != axis]
                best = None
                for i in (0, 1):
                    for j in (0, 1):
                        sil = faces_cam(others[0], i) != faces_cam(others[1], j)
                        if not sil:
                            continue
                        c = [0, 0, 0]; c[others[0]] = i; c[others[1]] = j
                        c0 = list(c); c0[axis] = 0
                        c1 = list(c); c1[axis] = 1
                        p0, p1 = corners[tuple(c0)], corners[tuple(c1)]
                        mid = proj((p0 + p1) / 2)
                        score = (mid[1] * -1) if axis != 2 else -mid[0]   # unten bzw. links bevorzugt
                        if best is None or score > best[0]:
                            best = (score, p0, p1)
                if best is None:
                    continue
                _, p0, p1 = best
                a0, a1 = proj(p0), proj(p1)
                line(a0, a1, colors[axis], 2)
                lo, hi = bbox[axis], bbox[axis + 3]
                ln = hi - lo
                px_len = math.hypot(a1[0] - a0[0], a1[1] - a0[1])
                spp = ln / max(px_len, 1e-6)
                step, minor = nice_step(spp, 40)
                vx = np.array([a1[0] - a0[0], a1[1] - a0[1]]) / max(px_len, 1e-6)
                nrm = np.array([-vx[1], vx[0]])
                # Tick-Normale: nach aussen (weg vom Bildzentrum)
                midp = np.array([(a0[0] + a1[0]) / 2 - W / 2, (a0[1] + a1[1]) / 2 - H / 2])
                if float(nrm @ midp) < 0:
                    nrm = -nrm
                k0 = math.ceil(lo / minor - 1e-9); k1 = math.floor(hi / minor + 1e-9)
                for k in range(k0, k1 + 1):
                    val = k * minor
                    q = np.array(a0) + (np.array(a1) - np.array(a0)) * ((val - lo) / ln)
                    major = abs(val / step - round(val / step)) < 1e-6
                    L = 8 if major else 4
                    line(q, q + nrm * L, colors[axis])
                    if major:
                        txt = fmt(val, step)
                        tp = q + nrm * (L + 9)
                        tw = d.textlength(txt, font=font_s)
                        d.text((tp[0] + ox - tw / 2, tp[1] + oy - 6), txt, fill=colors[axis], font=font_s)
                ep = np.array(a1) + nrm * 22
                d.text((ep[0] + ox - 4, ep[1] + oy - 7), "xyz"[axis].upper(), fill=colors[axis], font=font)
            info_txt = "Lineal an BBox-Kanten: rot X, gruen Y, blau Z (Werte = Modell-mm; Bildabstand je Achse verkuerzt)"
        if ruler and not persp and not axis_aligned:
            # Massstabsbalken (gilt fuer Strecken parallel zur Bildebene) und Kreuz im Zielpunkt
            st = nice_step(s, 60)[0]
            bl = st / s
            bx0, by0 = W - 20 - bl, H - 22
            line((bx0, by0), (bx0 + bl, by0), ink, 2)
            line((bx0, by0 - 5), (bx0, by0 + 5), ink); line((bx0 + bl, by0 - 5), (bx0 + bl, by0 + 5), ink)
            lab = "%s mm (Bildebene)" % fmt(st, st)
            d.text((min(bx0, W - d.textlength(lab, font=font_s) - 4) + ox, by0 + oy - 20), lab, fill=ink, font=font_s)
            if v.get("at"):
                cx_, cy_ = proj(focus_pt)
                line((cx_ - 7, cy_), (cx_ + 7, cy_), (220, 30, 30, 255)); line((cx_, cy_ - 7), (cx_, cy_ + 7), (220, 30, 30, 255))
        sec = job.get("section")
        if sec and axis_aligned and sec.get("contours"):
            ai = {"x": 0, "y": 1, "z": 2}
            ih, iv = ai[ah], ai[av]
            for poly in sec["contours"]:
                pts_ = [proj(p) for p in poly]
                if len(pts_) > 1:
                    d.line([(a_ + ox, b_ + oy) for a_, b_ in pts_], fill=(15, 15, 15, 255), width=2)
            m = sec.get("measure")
            if m:
                segs = [(p, q) for poly in sec["contours"] for p, q in zip(poly[:-1], poly[1:])]
                cx_, cy_ = proj(m)
                line((cx_ - 6, cy_), (cx_ + 6, cy_), (220, 30, 30, 255), 2); line((cx_, cy_ - 6), (cx_, cy_ + 6), (220, 30, 30, 255), 2)
                for horiz in (True, False):
                    ia, ib = (ih, iv) if horiz else (iv, ih)
                    c0 = m[ib] + 1e-4
                    xs_ = []
                    for p, q in segs:
                        if (p[ib] - c0) * (q[ib] - c0) < 0:
                            t_ = (c0 - p[ib]) / (q[ib] - p[ib])
                            xs_.append(p[ia] + t_ * (q[ia] - p[ia]))
                    xs_.sort()
                    ivs = [(xs_[k], xs_[k + 1]) for k in range(0, len(xs_) - 1, 2) if xs_[k + 1] - xs_[k] >= 0.05]
                    ivs.sort(key=lambda t: abs((t[0] + t[1]) / 2 - m[ia]))
                    for n_, (a0_, b0_) in enumerate(ivs[:8]):
                        P0 = list(m); P0[ia] = a0_; P0[sec["axis_i"]] = sec["pos"]
                        P1 = list(m); P1[ia] = b0_; P1[sec["axis_i"]] = sec["pos"]
                        q0, q1 = proj(P0), proj(P1)
                        col_ = (20, 90, 220, 255)
                        line(q0, q1, col_, 2)
                        tk = np.array([0, 6]) if horiz else np.array([6, 0])
                        for qq in (q0, q1):
                            line((qq[0] - tk[0], qq[1] - tk[1]), (qq[0] + tk[0], qq[1] + tk[1]), col_, 2)
                        txt = "%.2f" % (b0_ - a0_)
                        tw = d.textlength(txt, font=font_s)
                        mx, my = (q0[0] + q1[0]) / 2, (q0[1] + q1[1]) / 2
                        off = (-14 - 12 * (n_ % 2)) if horiz else 0
                        tx, ty = (mx - tw / 2, my + off) if horiz else (mx + 8, my - 6 + 12 * (n_ % 2))
                        d.rectangle([tx + ox - 1, ty + oy - 1, tx + ox + tw + 1, ty + oy + 12], fill=(255, 255, 255, 215))
                        d.text((tx + ox, ty + oy), txt, fill=col_, font=font_s)
        # Achsenkreuz unten links im Bild (Orientierung)
        ax0 = (30, H - 30)
        for k, colr in zip("" if axis_aligned else "xyz", ((200, 40, 40, 255), (30, 140, 40, 255), (40, 70, 210, 255))):
            vx_ = float(axes[k] @ rn); vy_ = float(axes[k] @ un)
            if math.hypot(vx_, vy_) < 0.08:
                d.ellipse([ax0[0] + ox - 3, ax0[1] + oy - 3, ax0[0] + ox + 3, ax0[1] + oy + 3], outline=colr)
                d.text((ax0[0] + ox + 5, ax0[1] + oy - 5), k.upper() + "(zum Betrachter)" if float(axes[k] @ fn) < 0 else k.upper() + "(weg)", fill=colr, font=font_s)
                continue
            q = (ax0[0] + 22 * vx_, ax0[1] - 22 * vy_)
            line(ax0, q, colr, 2)
            d.text((q[0] + ox + 3, q[1] + oy - 6), k.upper(), fill=colr, font=font_s)
        # Titel
        mode = "persp" if persp else "ortho"
        dname = v.get("name", "")
        title = "%s | %s | %.3f mm/px" % (dname, "xray" if v.get("xray") and mode == "shaded" else mode, s)
        if v.get("focus_name"):
            title = "%s: %s" % (v["focus_name"], title)
        d.text((ML + 4, 4), title, fill=(20, 20, 20, 255), font=font)
        canvas = Image.alpha_composite(canvas.convert("RGBA"), ov).convert("RGB")
        cells.append(canvas)
        # Legende (Text)
        reg = "Ausschnitt "
        if axis_aligned:
            reg += "%s %.1f..%.1f, %s %.1f..%.1f" % (
                ah, *sorted([sh_ * amin, sh_ * amax]), av, *sorted([sv_ * bmin_, sv_ * bmax_]))
        else:
            c_ = center_w
            reg += "Mitte (%.1f,%.1f,%.1f), %.0f x %.0f mm" % (c_[0], c_[1], c_[2], wmm, hmm)
        if axis_aligned:
            where = "Lineal %s%s waagerecht, %s%s senkrecht" % ("+" if sh_ > 0 else "-", ah.upper(), "+" if sv_ > 0 else "-", av.upper())
        elif persp:
            where = "ohne Lineal (Perspektive)"
        else:
            where = "Lineal an BBox-Kanten (X rot, Y gruen, Z blau) + Massstabsbalken"
        if v.get("focus_name"):
            dname = "%s (%s)" % (v["focus_name"], dname)
        txt = "%s: %s az/el %g/%g, %.3f mm/px, %dx%d px; %s; %s" % (dname, mode, az, el, s, W, H, reg, where)
        vlegs.append({"name": dname, "text": txt, "mm_per_px": round(s, 4), "px": [W, H],
                      "region_mm": [round(float(wmm), 3), round(float(hmm), 3)], "dir": [az, el],
                      "right_axis": [round(float(x), 3) for x in rn], "up_axis": [round(float(x), 3) for x in un],
                      "center": [round(float(x), 3) for x in center_w], "render_seconds": round(t_render, 2),
                      "margin": [ML, MT], "silhouette": sil, "mapping": {"amid": float(amid), "bmid": float(bmid)}})

    # ---- Ausgabe: Einzelbild oder Sheet --------------------------------------------------------------
    out = job["out"]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    if sheet and len(cells) > 1:
        cols = job.get("cols") or (2 if len(cells) <= 4 else 3)
        rows = [cells[i:i + cols] for i in range(0, len(cells), cols)]
        colw = [max(r[c].width for r in rows if len(r) > c) for c in range(cols)]
        rowh = [max(c.height for c in r) for r in rows]
        foot = 20
        sheet_img = Image.new("RGB", (sum(colw), sum(rowh) + foot), (255, 255, 255))
        y = 0
        for ri, r_ in enumerate(rows):
            x = 0
            for ci, c in enumerate(r_):
                sheet_img.paste(c, (x, y))
                x += colw[ci]
            y += rowh[ri]
        dd = ImageDraw.Draw(sheet_img)
        dd.text((6, sum(rowh) + 3), "BBox x %.1f..%.1f  y %.1f..%.1f  z %.1f..%.1f mm  (%.1f x %.1f x %.1f)" % (
            bbox[0], bbox[3], bbox[1], bbox[4], bbox[2], bbox[5], bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2]),
            fill=(20, 20, 20), font=font_s)
        final = sheet_img
    else:
        final = cells[0]
    lim_w, lim_h = (SHEET_W, SHEET_H) if (sheet and len(cells) > 1) else (MAX_IMG, MAX_IMG)
    if final.width > lim_w or final.height > lim_h:
        k = min(lim_w / final.width, lim_h / final.height)
        final = final.resize((int(final.width * k), int(final.height * k)), Image.LANCZOS)
    final = add_strip(final, job.get("caption"), job.get("legend_items"), Image, ImageDraw, font)
    final.save(out)
    for f in os.listdir(tmpdir):
        os.unlink(os.path.join(tmpdir, f))
    os.rmdir(tmpdir)
    return {"out": out, "size": list(final.size), "views": vlegs, "bbox": bbox, "caption": job.get("caption", []), "triangles": int(sum(len(o.data.polygons) for o in objs))}


if __name__ == "__main__":
    try:
        import bpy  # noqa: F401
        IN_BLENDER = True
    except ImportError:
        IN_BLENDER = False
    if IN_BLENDER:
        blender_main()
    else:
        sys.exit(cli_main(sys.argv[1:]))
