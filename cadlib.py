"""cadlib - Hilfsbibliothek im Worker-Namespace (`cad`) und Operationen des Workers (nur im FreeCAD-Python importierbar).

Im Skript:   cad.material(name, "eiche|multiplex|hartholz|pla|platzhalter")   Material fuer --style schoen / GLB
             cad.report(*shapes)     Messwerte ausgeben und die Formen als Ergebnis des Laufs markieren
             cad.focus(name, center, size, view="front")   benannten kritischen Bereich fuer `cad look --focus` merken
             cad.api("Part.Shape.multiFuse")  Doku/Signatur einer FreeCAD-Funktion ausgeben
             cad.outdir("modell"|"slice"|"vorschau"|"messung" [, projekt=, fallback=])  Ordner der aktiven Version
                     (cad projekt <name>; cad version "<Label>"), ohne Projekt cad_out bzw. fallback mit Warnzeile
Der Worker ruft: reset_run(keep), snapshot(), post_run(req, before, resp), op(name, req).
PySide6/pivy/VTK werden hier nie importiert."""
import importlib, inspect, math, os, time

import FreeCAD as App

OUT_ROOT = os.environ.get("CAD_OUT", "/mnt/raid1/3d_print/cad_out")
CACHE = os.path.join(OUT_ROOT, ".cache")
DEFLECTION = 0.1          # feste Vernetzung fuer Bilder (mm)
_state = {"reported": [], "focus": [], "last": None, "run_id": 0, "mats": {}, "projekt": None}


# --------------------------------------------------------------------------------------- Skript-API
def reset_run(keep=False):
    _state["reported"] = [] if not keep else _state["reported"]
    _state["focus"] = [] if not keep else _state["focus"]
    _state["mats"] = {} if not keep else _state["mats"]


def _bbox(b):
    return [round(b.XMin, 3), round(b.YMin, 3), round(b.ZMin, 3), round(b.XMax, 3), round(b.YMax, 3), round(b.ZMax, 3)]


def measure(obj, name=None):
    m = _measure(obj, name)
    m["text"] = fmt_measure(m)
    return m


def _measure(obj, name=None):
    """Messwerte fuer Part.Shape, Mesh.Mesh oder ein Dokumentobjekt (Part::Feature / Mesh::Feature)."""
    if hasattr(obj, "Shape") and hasattr(obj, "Name"):
        name = name or obj.Name
        obj = obj.Shape
    elif hasattr(obj, "Mesh") and hasattr(obj, "Name"):
        name = name or obj.Name
        obj = obj.Mesh
    if hasattr(obj, "Solids"):                      # Part.Shape
        bb = obj.BoundBox
        m = {"name": name or "shape", "kind": "shape", "valid": bool(obj.isValid()), "solids": len(obj.Solids),
             "volume": round(obj.Volume, 2), "area": round(obj.Area, 2), "faces": len(obj.Faces),
             "bbox": _bbox(bb), "size": [round(bb.XLength, 3), round(bb.YLength, 3), round(bb.ZLength, 3)]}
        return m
    if hasattr(obj, "CountFacets"):                 # Mesh.Mesh
        bb = obj.BoundBox
        closed = bool(obj.isSolid()) and not obj.hasNonManifolds()
        return {"name": name or "mesh", "kind": "mesh", "valid": closed, "closed": closed, "triangles": obj.CountFacets,
                "volume": round(obj.Volume, 2), "area": round(obj.Area, 2),
                "bbox": _bbox(bb), "size": [round(bb.XLength, 3), round(bb.YLength, 3), round(bb.ZLength, 3)]}
    raise TypeError("cad.report: kein Shape/Mesh: %r" % (obj,))


def fmt_measure(m):
    b = m["bbox"]
    if m["kind"] == "shape":
        head = "valid=%s solids=%d faces=%d" % (m["valid"], m["solids"], m["faces"])
    else:
        head = "closed=%s triangles=%d" % ("ja" if m["closed"] else "NEIN", m["triangles"])
    return "%s: %s volume=%.0f mm3 area=%.0f mm2 bbox x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f (%.2f x %.2f x %.2f)" % (
        m["name"], head, m["volume"], m["area"], b[0], b[3], b[1], b[4], b[2], b[5], *m["size"])


def report(*shapes, **named):
    """Messwerte der Formen ausgeben (und als Ergebnis des Laufs merken): cad.report(a, b) oder cad.report(Deckel=a, Box=b).
    Gibt die Liste der Messwert-Dicts zurueck."""
    out = []
    items = [(None, s) for s in shapes] + [(k, v) for k, v in named.items()]
    for i, (nm, s) in enumerate(items):
        if isinstance(s, tuple) and len(s) == 2 and isinstance(s[1], str):      # cad.report(Name=(shape, "eiche"))
            s, mat = s
            material(nm or getattr(s, "Name", None) or "shape%d" % (i + 1), mat)
        m = measure(s, nm or (None if hasattr(s, "Name") else "shape%d" % (i + 1)))
        out.append(m)
        _state["reported"].append((s, m["name"]))
        print("[report] " + m["text"])
    return out


def material(name, mat):
    """Material eines Teils fuer `cad look --style schoen` und GLB: cad.material("Eichenplatte", "eiche").
    mat: eiche | multiplex | hartholz | platzhalter. Ohne Angabe gilt ein Fallback aus dem Teilenamen
    (Eiche -> eiche; *Platzhalter*, Kabelweg*, Laptop -> platzhalter; Rest -> grau mit Warnung, kein Material vergeben). Auch: cad.report(Name=(shape, "eiche"))."""
    import cad_schoen
    _state["mats"][str(name)] = cad_schoen.norm_material(mat)


def focus(name, center, size=20.0, view="front"):
    """Benannter kritischer Bereich: Mittelpunkt (x,y,z) in Modell-mm, Ausschnittsgroesse in mm, Blickrichtung (Preset oder (az,el))."""
    c = [float(x) for x in center]
    if len(c) != 3:
        raise ValueError("cad.focus: center braucht x,y,z")
    _state["focus"] = [f for f in _state["focus"] if f["name"] != name]
    _state["focus"].append({"name": str(name), "center": c, "size": float(size), "view": view})


def fit(a, b, move=(0, 0, 0)):
    """Passung zweier Formen: cad.fit(deckel, behaelter, move=(x,y,z)) verschiebt a um `move` (Kopie) und gibt
    Ueberlappungsvolumen (mm3) und kleinsten Abstand (mm) aus; Rueckgabe dict. Ueberlappung > 0 = Kollision, Abstand = Spiel."""
    sa, sb = _shape_of(a), _shape_of(b)
    sa = sa.copy()
    sa.translate(App.Vector(*move))
    d = sa.distToShape(sb)[0]
    vol = sa.common(sb).Volume
    res = {"overlap_mm3": round(vol, 3), "min_distance_mm": round(d, 4)}
    print("[fit] Ueberlappung %.3f mm3, kleinster Abstand %.4f mm (move=%s)" % (vol, d, tuple(move)))
    return res


def api(dotted):
    """Signatur und Doku einer FreeCAD-Funktion/-Klasse: cad.api('Part.Shape.multiFuse')."""
    parts = dotted.split(".")
    obj = None
    for i in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:i]))
            rest = parts[i:]
            break
        except ImportError:
            continue
    if obj is None:
        raise ImportError("Modul nicht gefunden: " + dotted)
    for p in rest:
        obj = getattr(obj, p)
    doc = inspect.getdoc(obj) or "(keine Doku)"
    names = [n for n in dir(obj) if not n.startswith("_")] if inspect.isclass(obj) or inspect.ismodule(obj) else []
    print("[api] %s\n%s" % (dotted, doc[:1500]))
    if names:
        print("[api] Namen: " + ", ".join(names[:60]) + (" ..." if len(names) > 60 else ""))


def set_projekt(info):
    """Vom Worker vor jedem Lauf: Projektzustand des aufrufenden `cad` (inkl. CAD_STATE-Datei)."""
    _state["projekt"] = info if isinstance(info, dict) else None


def outdir(kind="modell", projekt=None, fallback=None):
    """Ausgabeordner der aktiven Version: cad.outdir("modell"|"slice"|"vorschau"|"messung").
    projekt=NAME: nur nutzen, wenn NAME das aktive Projekt ist (Testprojekte mit '_' am Anfang nehmen jedes Skript an);
    sonst/ohne aktives Projekt: fallback (Standard cad_out) mit Warnzeile. Freigegebene Version (freigabe.md) -> Fehler."""
    import cadprojekt as cp
    info = _state.get("projekt") or {}
    old = os.environ.get("CAD_STATE")
    if info.get("state_file"):
        os.environ["CAD_STATE"] = info["state_file"]
    try:
        act = cp.load_state().get("projekt")
        mismatch = bool(act and projekt and act != projekt and not act.startswith("_"))
        if fallback and (mismatch or not act or not cp.active()[1]) and os.path.isfile(os.path.join(fallback, "PROJEKT.md")):
            # Projektordner mit Versionen: die alten Dateinamen dort sind Symlinks in Versionen (auf dem Dateiserver angelegt,
            # hier unsichtbar) - "wie bisher" schreiben wuerde eine Version still ueberschreiben.
            raise RuntimeError("%s ist ein Projektordner mit Versionen: erst `cad projekt %s` und `cad version \"<Label>\"` "
                               "(oder `cad version --nutze vNNN`), dann neu ausfuehren. Aktiv ist: %s"
                               % (fallback, projekt or os.path.basename(fallback.rstrip("/")), act or "kein Projekt"))
        if mismatch:
            d = fallback or cp.FALLBACK
            print("[cad] WARNUNG: aktives Projekt %s ist nicht %s - Ausgabe wie bisher nach %s" % (act, projekt, d))
            return d
        try:
            d, warn = cp.outdir(kind)
        except cp.Gesperrt as e:
            raise RuntimeError(str(e))
        if warn:
            if fallback:
                warn = warn.split(" - ")[0] + " - Ausgabe wie bisher nach " + fallback
                d = fallback
            print("[cad] WARNUNG: " + warn)
        os.makedirs(d, exist_ok=True)
        return d
    finally:
        if info.get("state_file"):
            if old is None:
                os.environ.pop("CAD_STATE", None)
            else:
                os.environ["CAD_STATE"] = old


# --------------------------------------------------------------------------------------- Worker-Haken
def snapshot():
    return {(d.Name, o.Name) for d in App.listDocuments().values() for o in d.Objects}


def run_objects(before=None):
    """Objekte des Laufs: Part::Feature/Mesh::Feature, die keinem anderen Objekt als Eingang dienen."""
    res = []
    for d in App.listDocuments().values():
        for o in d.Objects:
            if before and (d.Name, o.Name) in before:
                continue
            if not (hasattr(o, "Shape") or hasattr(o, "Mesh")):
                continue
            if hasattr(o, "Shape") and o.Shape.isNull():
                continue
            if o.InList:
                continue
            res.append(o)
    return res


def post_run(req, before, resp):
    explicit = [(s, n) for s, n in _state["reported"]]
    objs = run_objects(before)
    targets = explicit or [(o, o.Name) for o in objs]
    _state["last"] = {"targets": targets, "name": os.path.splitext(os.path.basename(req.get("file") or "code"))[0],
                      "time": time.time()}
    resp["focus"] = list(_state["focus"])
    resp["n_objects"] = len(targets)
    resp["report_printed"] = bool(explicit)
    if req.get("report"):
        resp["report"] = []
        for s, n in targets:
            try:
                resp["report"].append(measure(s, n))
            except Exception as e:
                resp["report"].append({"name": n, "error": str(e)})


# --------------------------------------------------------------------------------------- Operationen
def load_file(path):
    """Datei laden (FCStd/STEP/STL/IGES/BREP) -> Liste (Objekt/Shape/Mesh, Name)."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".fcstd":
        doc = App.openDocument(path)
        objs = run_objects()
        mine = [(o, o.Name) for o in objs if o.Document.Name == doc.Name]
        return mine
    if ext == ".stl":
        import Mesh
        return [(Mesh.Mesh(path), os.path.splitext(os.path.basename(path))[0])]
    if ext in (".step", ".stp", ".iges", ".igs", ".brep"):
        import Part
        s = Part.read(path)
        return [(s, os.path.splitext(os.path.basename(path))[0])]
    raise ValueError("Dateityp nicht unterstuetzt: " + ext)


def op(name, req):
    if name == "info":
        items = load_file(req["file"])
        ms = [measure(o, n) for o, n in items]
        for d in list(App.listDocuments().keys()):
            if os.path.abspath(App.getDocument(d).FileName or "") == os.path.abspath(req["file"]):
                App.closeDocument(d)
        return {"ok": True, "stdout": "", "error": None, "info": ms}
    if name == "export":
        return export_stls(req)
    if name in ("hotspots", "check", "look", "diff"):
        import cadgeom
        return getattr(cadgeom, "op_" + name)(req)
    raise ValueError("unbekannte Operation: " + name)


def _shape_of(o):
    return o.Shape if hasattr(o, "Shape") else o


def _cleanup_cache():
    """Cache aelter als 1 Tag wegraeumen."""
    os.makedirs(CACHE, exist_ok=True)
    now = time.time()
    for f in os.listdir(CACHE):
        p = os.path.join(CACHE, f)
        try:
            if now - os.path.getmtime(p) > 86400:
                os.unlink(p)
        except OSError:
            pass


def export_stls(req):
    """Objekte des letzten Laufs (oder einer Datei) als STL (feste Vernetzung) fuer den Blender-Renderer schreiben."""
    import MeshPart, Mesh
    import cad_schoen
    os.makedirs(CACHE, exist_ok=True)
    if req.get("file"):
        items = load_file(req["file"])
        stem = os.path.splitext(os.path.basename(req["file"]))[0]
    else:
        last = _state["last"]
        if not last:
            return {"ok": False, "stdout": "", "error": "kein Lauf im Worker: erst `cad run <skript>` ausfuehren (oder Datei angeben)"}
        items, stem = last["targets"], last["name"]
    if not items:
        return {"ok": False, "stdout": "", "error": "der Lauf hat keine Part/Mesh-Objekte erzeugt (Objekt mit doc.addObject('Part::Feature', ...) anlegen oder cad.report(shape) aufrufen)"}
    _state["run_id"] += 1
    rid = "%d_%d" % (os.getpid(), _state["run_id"])
    _cleanup_cache()
    files = []
    for i, (o, n) in enumerate(items):
        path = os.path.join(CACHE, "%s_%02d_%s.stl" % (rid, i, "".join(c if c.isalnum() else "_" for c in n)[:30]))
        if hasattr(o, "CountFacets") or (hasattr(o, "Mesh") and not hasattr(o, "Shape")):
            mesh = o if hasattr(o, "CountFacets") else o.Mesh
        else:
            shp = _shape_of(o)
            mesh = MeshPart.meshFromShape(Shape=shp, LinearDeflection=req.get("deflection", DEFLECTION),
                                          AngularDeflection=math.radians(15))
        mesh.write(path)
        files.append({"path": path, "name": n, "triangles": mesh.CountFacets, "bbox": _bbox(mesh.BoundBox),
                      "mat": _state["mats"].get(n) or cad_schoen.default_material(n)})
    if req.get("file") and req["file"].lower().endswith(".fcstd"):
        for d in list(App.listDocuments().keys()):
            if App.getDocument(d).FileName == req["file"]:
                App.closeDocument(d)
    return {"ok": True, "stdout": "", "error": None, "stls": files, "stem": stem, "focus": list(_state["focus"])}
