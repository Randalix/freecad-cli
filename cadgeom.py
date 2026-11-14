"""cadgeom - Geometrie-Analyse im Worker: Hotspots, Druckbarkeit, Schnitte, Diff (nur im FreeCAD-Python importierbar).

Operationen (aufgerufen von cadlib.op):  hotspots, check, look, diff
Alles arbeitet auf einem Dreiecksnetz (FreeCAD-Mesh, bei FCStd/STEP/Lauf mit LinearDeflection 0,1 aus den Formen erzeugt):
  * Ueberhang/Bruecke   Normalen aus dem Netz, Logik und Grenzen wie tools/printer/overhang_check.py (45 Grad gegen die
                        Waagerechte, Orientierung wie in der Datei, erste 0,3 mm ueber der Platte ausgenommen, Bruecken bis 10 mm ok).
  * duenne Wand         Strahlsonde: von jedem Dreieck-Schwerpunkt p aus liegt der Probepunkt q = p - n*t (t = Grenze und halbe
                        Grenze) hinter/innerhalb der Wand; Mesh.nearestFacetOnRay (ungerichtet, naechster Treffer auf der Geraden)
                        liefert die Gegenflaeche. Antiparallele Gegenflaeche (n . n_hit < -0.9) -> Dicke D = t + (Treffer - q) . (-n).
                        D < Grenze -> Treffer. Schraege/spitz zulaufende Flaechen (Keile, Fasen) fallen durch den Antiparallel-Test.
  * kleiner Spalt       Formen: Part.Shape.distToShape je Solid-Paar (exakt); reine Netze: Abstand der dicht abgetasteten Teile.
  * offenes Netz        Kantenzaehlung (Kante nur in 1 Dreieck = offen, in > 2 = nicht-mannigfaltig).
Teile = zusammenhaengende Netzkomponenten (Dreiecke mit gemeinsamen Punkten)."""
import math, os, struct, time

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

import FreeCAD as App
import cadlib

ANGLE = 45.0
MIN_AREA = 4.0            # mm2, wie overhang_check.py
MAX_BRIDGE = 10.0         # mm Spannweite
MIN_WALL = 0.8
GAP_MAX = 0.3
MAX_SAMPLES = 30000       # Strahlsonden je Analyse (alle Dreiecke bis zu dieser Zahl, sonst flaechengewichtet)
SEV_RANK = {"hoch": 0, "mittel": 1, "niedrig": 2, "info": 3}
KIND_RANK = {"offenes_netz": 0, "duenne_wand": 1, "ueberhang": 2, "bruecke": 3, "spalt": 4, "fokus": 5}
_cache = {}


# ----------------------------------------------------------------------------------------------- Szene
class Scene:
    pass


def _file_key(req):
    f = req.get("file")
    if f:
        try:
            return ("file", os.path.abspath(f), os.path.getmtime(f))
        except OSError:
            return ("file", f, 0)
    last = cadlib._state["last"]
    return ("run", last["time"]) if last else None


def _cc(n, i, j):
    g = coo_matrix((np.ones(len(i)), (i, j)), shape=(n, n))
    return connected_components(g, directed=False)


def _tri_clusters(F, n_pts, sel):
    """Zusammenhaengende Flaechenstuecke unter den Dreiecken `sel` (Indizes): Label je Eintrag in sel."""
    f = F[sel]
    i = np.r_[f[:, 0], f[:, 1], f[:, 2]]
    j = np.r_[f[:, 1], f[:, 2], f[:, 0]]
    _, lab = _cc(n_pts, i, j)
    return lab[f[:, 0]]


def _shape_gaps(shapes, names):
    """Exakte Spalte zwischen Solids (distToShape); nur Paare, deren Bounding-Boxen sich auf < GAP_MAX nahekommen."""
    sols = []
    for shp, nm in zip(shapes, names):
        try:
            ss = shp.Solids
            for k, s in enumerate(ss):
                sols.append((nm if len(ss) == 1 else "%s.%d" % (nm, k + 1), k, s))
        except Exception:
            pass
    out = []
    if not (2 <= len(sols) <= 60):
        return out, len(sols)
    t0 = time.time()
    for a in range(len(sols)):
        ba = sols[a][2].BoundBox
        for b in range(a + 1, len(sols)):
            bb = sols[b][2].BoundBox
            gx = max(ba.XMin - bb.XMax, bb.XMin - ba.XMax, 0)
            gy = max(ba.YMin - bb.YMax, bb.YMin - ba.YMax, 0)
            gz = max(ba.ZMin - bb.ZMax, bb.ZMin - ba.ZMax, 0)
            if math.sqrt(gx * gx + gy * gy + gz * gz) > GAP_MAX:
                continue
            try:
                d, pts, _ = sols[a][2].distToShape(sols[b][2])
            except Exception:
                continue
            if 1e-6 < d < GAP_MAX and pts:
                p, q = pts[0]
                out.append({"d": d, "p": [p.x, p.y, p.z], "q": [q.x, q.y, q.z], "a": sols[a][0], "b": sols[b][0]})
            if time.time() - t0 > 4:
                return out, len(sols)
    return out, len(sols)


def get_scene(req):
    """Netz-Szene fuer Datei oder letzten Lauf (zwischengespeichert)."""
    import Mesh, MeshPart
    key = _file_key(req)
    if key is None:
        raise ValueError("kein Lauf im Worker: erst `cad run <skript>` ausfuehren (oder Datei angeben)")
    defl = req.get("deflection", cadlib.DEFLECTION)
    if (key, defl) in _cache:
        return _cache[(key, defl)]
    t0 = time.time()
    if req.get("file"):
        items = cadlib.load_file(req["file"])
        stem = os.path.splitext(os.path.basename(req["file"]))[0]
        focus = []
    else:
        last = cadlib._state["last"]
        items, stem = last["targets"], last["name"]
        focus = list(cadlib._state["focus"])
    if not items:
        raise ValueError("keine Part/Mesh-Objekte vorhanden")
    meshes, names, shapes = [], [], []
    for o, n in items:
        names.append(n)
        if hasattr(o, "CountFacets"):
            meshes.append(o)
            shapes.append(None)
        elif hasattr(o, "Mesh") and not hasattr(o, "Shape"):
            meshes.append(o.Mesh)
            shapes.append(None)
        else:
            shp = o.Shape if hasattr(o, "Shape") else o
            shapes.append(shp)
            meshes.append(MeshPart.meshFromShape(Shape=shp, LinearDeflection=defl, AngularDeflection=math.radians(15)))
    sc = Scene()
    sc.stem, sc.names, sc.focus = stem, names, focus
    sc.source = req.get("file") or "(letzter Lauf)"
    sc.valid_shape = all(bool(s.isValid()) for s in shapes if s is not None)
    sc.n_solids = sum(len(s.Solids) for s in shapes if s is not None)
    sc.shape_gaps, _ = _shape_gaps([s for s in shapes if s is not None], [n for s, n in zip(shapes, names) if s is not None])
    if len(meshes) == 1:
        sc.mesh = meshes[0]
    else:
        sc.mesh = Mesh.Mesh()
        for m in meshes:
            sc.mesh.addMesh(m)
    pts, fac = sc.mesh.Topology
    sc.P = np.array([[p.x, p.y, p.z] for p in pts], dtype=np.float64).reshape(-1, 3)
    sc.F = np.array(fac, dtype=np.int64).reshape(-1, 3)
    sc.m = len(sc.F)
    counts = [mm.CountFacets for mm in meshes]
    sc.item = np.repeat(np.arange(len(meshes)), counts) if sum(counts) == sc.m else np.zeros(sc.m, dtype=np.int64)
    sc.T = sc.P[sc.F]                                       # (m,3,3)
    nv = np.cross(sc.T[:, 1] - sc.T[:, 0], sc.T[:, 2] - sc.T[:, 0])
    ln = np.linalg.norm(nv, axis=1)
    sc.area = ln / 2
    sc.N = np.divide(nv, ln[:, None], out=np.zeros_like(nv), where=ln[:, None] > 1e-12)
    sc.C = sc.T.mean(axis=1)
    ncomp, vlab = _cc(len(sc.P), np.r_[sc.F[:, 0], sc.F[:, 1]], np.r_[sc.F[:, 1], sc.F[:, 2]])
    sc.comp = vlab[sc.F[:, 0]]
    sc.ncomp = ncomp
    sc.comps = []
    per_item_n = {}
    for c in range(ncomp):
        idx = np.nonzero(sc.comp == c)[0]
        it = int(sc.item[idx[0]])
        per_item_n[it] = per_item_n.get(it, 0) + 1
        tri = sc.T[idx].reshape(-1, 3)
        sc.comps.append({"id": c, "item": it, "tris": int(len(idx)), "bbox": [round(float(x), 3) for x in list(tri.min(0)) + list(tri.max(0))],
                         "_k": per_item_n[it]})
    for c in sc.comps:
        c["name"] = names[c["item"]] if sum(1 for d in sc.comps if d["item"] == c["item"]) == 1 else "%s.%d" % (names[c["item"]], c["_k"])
    sc.zmin = float(sc.P[:, 2].min())
    sc.bbox = [float(x) for x in list(sc.P.min(0)) + list(sc.P.max(0))]
    sc.volume = _volume(sc.T)
    sc.t_build = time.time() - t0
    if req.get("file") and req["file"].lower().endswith(".fcstd"):
        for d in list(App.listDocuments().keys()):
            if App.getDocument(d).FileName == req["file"]:
                App.closeDocument(d)
    if len(_cache) >= 3:
        _cache.pop(next(iter(_cache)))
    _cache[(key, defl)] = sc
    return sc


def _volume(T):
    return float(np.einsum("ij,ij->i", T[:, 0], np.cross(T[:, 1], T[:, 2])).sum() / 6)


def comp_names(sc, ids):
    return ", ".join(sc.comps[i]["name"] for i in sorted(set(int(x) for x in ids)))


# ----------------------------------------------------------------------------------------------- Erkennung
def _box(pts, pad=0.0):
    lo, hi = pts.min(0) - pad, pts.max(0) + pad
    return [round(float(x), 3) for x in list(lo) + list(hi)]


def _view_from_normal(n):
    n = np.asarray(n, dtype=float)
    n = n / (np.linalg.norm(n) or 1)
    el = math.degrees(math.asin(max(-1, min(1, n[2]))))
    az = math.degrees(math.atan2(n[0], -n[1])) if abs(n[2]) < 0.9999 else 0.0
    return [round(az % 360, 1), round(el, 1)]


def _subdivide(T, L, cap=400000):
    """Dreiecke (n,3,3) per Halbierung der laengsten Kante, bis jede Kante <= L (Zahl der Stuecke ~ Flaeche/L^2 + Laenge/L;
    duenne Splitter erzeugen KEINE k^2 Punkte wie das alte Gitter je Dreieck)."""
    for _ in range(60):
        e = np.stack([np.linalg.norm(T[:, 1] - T[:, 0], axis=1), np.linalg.norm(T[:, 2] - T[:, 1], axis=1),
                      np.linalg.norm(T[:, 0] - T[:, 2], axis=1)], axis=1)
        k = e.argmax(1)
        big = e[np.arange(len(T)), k] > L
        if not big.any() or len(T) > cap:
            break
        keep, S, kk = T[~big], T[big], k[big]
        # laengste Kante i: Eckpunkte i, i+1; Gegenecke i+2
        r = np.arange(len(S))
        a, b, c = S[r, kk], S[r, (kk + 1) % 3], S[r, (kk + 2) % 3]
        m = (a + b) / 2
        T = np.concatenate([keep, np.stack([a, m, c], 1), np.stack([m, b, c], 1)])
    return T


def _bridge_span(sc, idx, info=None):
    """Freie Spannweite einer waagerechten Flaeche: 2 x groesster Abstand eines Flaechenpunkts zum Flaechenrand
    (Rechteck 14 x 30 -> 14 mm, wie die BBox-Schaetzung in overhang_check.py; Fugenraster zwischen Fuessen -> Streifenbreite).
    Verfahren (adaptiv, Kosten ~ O(Flaeche/L0^2) statt O(Flaeche/0,5^2)): Dreiecke per Kantenhalbierung in Stuecke mit Kante <= L0
    zerlegen (L0 so, dass ca. 6000-20000 Stuecke), Abstand der Stueckschwerpunkte zum Rand (KD-Baum ueber Randpunkte), dann nur die Stuecke
    mit Abstand >= dmax - 0,7 L (ein Stueck, das den wahren Maximalpunkt enthaelt, liegt immer darin) mit L/3 neu zerlegen, bis L <= L_fin = 0,4 % der Spannweite (0,3..1,0 mm).
    Fehlerschranke: Abstand liegt hoechstens 0,67 x L_fin (Stueck-Umkreis) unter dem wahren Maximum, Spannweite also hoechstens
    1,33 x L_fin zu klein (<= 0,4 mm bei kleinen, <= 0,5-1,3 % bei grossen Flaechen); Randabtastung (Abstand L/2) ueberschaetzt < 0,02 mm."""
    F = sc.F[idx]
    # gleiche Flaeche an anderer Stelle (z. B. mehrere gleiche Fachboeden): Ergebnis wiederverwenden (Schluessel = verschobene, sortierte Dreiecke)
    rel = np.round(sc.P[F] - sc.P[F].reshape(-1, 3).min(0), 3).reshape(len(F), 9)
    key = rel[np.lexsort(rel.T)].tobytes()
    memo = sc.__dict__.setdefault("_span_memo", {})
    if key in memo:
        return memo[key]
    e = np.sort(np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]], axis=1)
    u, cnt = np.unique(e, axis=0, return_counts=True)
    bd = u[cnt == 1]
    if not len(bd):
        return 1e9
    area = float(sc.area[idx].sum())
    N0 = 6000.0
    a, b = sc.P[bd[:, 0]], sc.P[bd[:, 1]]
    ln = np.linalg.norm(b - a, axis=1)
    blen = float(ln.sum())
    L, L_fin = max(0.3, min(area / max(blen, 1e-9), 4 * math.sqrt(area / N0))), 0.3      # duenne Streifen: Startgroesse ~ Streifenbreite

    def edge_tree(h):
        hb = max(h, blen / 200000.0)
        k = np.maximum(1, np.ceil(ln / hb).astype(np.int64))
        rep = np.repeat(np.arange(len(bd)), k + 1)
        t = (np.arange(len(rep)) - np.repeat(np.cumsum(k + 1) - (k + 1), k + 1)) / k[rep]
        return cKDTree(a[rep] + (b[rep] - a[rep]) * t[:, None])

    T = sc.P[F]
    best, rounds, npts = 0.0, 0, 0
    while True:
        T = _subdivide(T, L)
        d = edge_tree(L / 2).query(T.mean(1))[0]
        npts += len(T)
        best = float(d.max())                                     # nur die feinste Runde zaehlt (grobe Randabtastung ueberschaetzt)
        rounds += 1
        if rounds == 1:
            L_fin = min(max(0.3, 0.004 * 2 * best), 1.0)        # Ziel: Fehler <= ca. 0,5 % der Spannweite, mindestens 0,3 mm Stuecke
        if L <= L_fin + 1e-9 or rounds >= 7:
            break
        sel = d >= d.max() - 0.7 * L
        if sel.sum() > 3000:          # Plateau (z. B. gleich breiter Streifen): gleichwertige Kandidaten, die besten 3000 genuegen
            sel = d >= np.sort(d)[-3000]
        T = T[sel]
        L = max(L_fin, L / 3)
    if info is not None:
        info.update(rounds=rounds, points=npts, final_L=L)
    memo[key] = float(2 * best)
    return memo[key]


def find_overhangs(sc, angle=ANGLE):
    out = []
    nz = sc.N[:, 2]
    zc = sc.C[:, 2]
    incl = np.degrees(np.arccos(np.clip(-nz, -1, 1)))
    crit = (nz < -1e-6) & (zc - sc.zmin >= 0.3) & (incl < angle - 1) & (sc.area > 0)
    for bridge in (False, True):
        sel = np.nonzero(crit & ((incl < 5) if bridge else (incl >= 5)))[0]
        if not len(sel):
            continue
        lab = _tri_clusters(sc.F, len(sc.P), sel)
        for c in np.unique(lab):
            idx = sel[lab == c]
            area = float(sc.area[idx].sum())
            if area < MIN_AREA:
                continue
            pts = sc.T[idx].reshape(-1, 3)
            box = _box(pts)
            dx, dy = box[3] - box[0], box[4] - box[1]
            minc = float(incl[idx].min())
            z = float(np.average(sc.C[idx, 2], weights=sc.area[idx]))
            nmean = (sc.N[idx] * sc.area[idx, None]).sum(0)
            parts = sorted(set(int(x) for x in sc.comp[idx]))
            if bridge:
                span = _bridge_span(sc, idx)
                sev = "info" if span <= MAX_BRIDGE else ("hoch" if span > 25 else "mittel")
                if span > MAX_BRIDGE:
                    reason = "Brücke %.0f mm Spannweite (> %.0f mm), waagerechte Unterseite %.0f mm² bei z=%.1f" % (span, MAX_BRIDGE, area, z)
                else:
                    reason = "kurze Brücke %.0f mm (≤ %.0f mm, unkritisch), %.0f mm² bei z=%.1f" % (span, MAX_BRIDGE, area, z)
                out.append({"kind": "bruecke", "severity": sev, "reason": reason, "value": round(span, 2), "area": round(area, 1),
                            "box": box, "center": [round(float(x), 3) for x in sc.C[idx].mean(0)], "parts": parts,
                            "view": [0.0, -90.0], "mode": "overhang"})
            else:
                sev = "hoch" if minc < 35 else "mittel"
                reason = "Überhang %.0f° zur Waagerechten (Grenze %.0f°), %.0f mm², z %.1f..%.1f" % (minc, angle, area, box[2], box[5])
                out.append({"kind": "ueberhang", "severity": sev, "reason": reason, "value": round(minc, 1), "area": round(area, 1),
                            "box": box, "center": [round(float(x), 3) for x in sc.C[idx].mean(0)], "parts": parts,
                            "view": _view_from_normal(nmean), "mode": "overhang"})
    return out


def _first_hits(sc, idx, L, rs=3.0):
    """Strahlen von den Schwerpunkten der Dreiecke idx nach innen (-Normale), Laenge L: erster Treffer je Strahl.
    Rueckgabe (t, tri) je Strahl (t = inf ohne Treffer). Kleine Dreiecke ueber KD-Baum der Schwerpunkte, grosse (Radius > rs) brute force."""
    n = len(idx)
    O = sc.C[idx] - sc.N[idx] * 1e-3
    Dv = -sc.N[idx]
    best_t = np.full(n, np.inf)
    best_j = np.full(n, -1, dtype=np.int64)
    T0, T1, T2 = sc.T[:, 0], sc.T[:, 1], sc.T[:, 2]
    rad = np.max(np.linalg.norm(sc.T - sc.C[:, None, :], axis=2), axis=1)
    small = np.nonzero((rad <= rs) & (sc.area > 1e-9))[0]
    large = np.nonzero((rad > rs) & (sc.area > 1e-9))[0]

    def mt(qi, tj):
        e1, e2 = T1[tj] - T0[tj], T2[tj] - T0[tj]
        d = Dv[qi]
        pv = np.cross(d, e2)
        det = np.einsum("ij,ij->i", e1, pv)
        ok = np.abs(det) > 1e-12
        inv = np.divide(1.0, det, out=np.zeros_like(det), where=ok)
        tv = O[qi] - T0[tj]
        u = np.einsum("ij,ij->i", tv, pv) * inv
        qv = np.cross(tv, e1)
        v = np.einsum("ij,ij->i", d, qv) * inv
        t = np.einsum("ij,ij->i", e2, qv) * inv
        hit = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > 1e-9) & (t <= L) & (tj != idx[qi])
        qi, tj, t = qi[hit], tj[hit], t[hit]
        np.minimum.at(best_t, qi, t)
        # Dreieck des (jetzt) kleinsten t je Strahl merken
        sel = t <= best_t[qi] + 1e-12
        best_j[qi[sel]] = tj[sel]

    if len(small):
        tree = cKDTree(sc.C[small])
        lists = tree.query_ball_point(O, L + rs + 1e-3)
        lens = np.fromiter((len(x) for x in lists), dtype=np.int64, count=n)
        if lens.sum():
            qi = np.repeat(np.arange(n), lens)
            tj = small[np.concatenate([np.asarray(x, dtype=np.int64) for x in lists if len(x)])]
            for ch in range(0, len(qi), 600000):
                mt(qi[ch:ch + 600000], tj[ch:ch + 600000])
    for tj in large:
        lo, hi_ = sc.T[tj].min(0) - L - 1e-3, sc.T[tj].max(0) + L + 1e-3
        m = np.all((O >= lo) & (O <= hi_), axis=1)
        qi = np.nonzero(m)[0]
        if len(qi):
            mt(qi, np.full(len(qi), tj))
    return best_t, best_j, O, Dv


def find_thin_walls(sc, min_wall=MIN_WALL):
    cand = np.nonzero(sc.area > 1e-6)[0]
    if len(cand) > MAX_SAMPLES:
        p = sc.area[cand] / sc.area[cand].sum()
        cand = np.sort(np.random.RandomState(0).choice(cand, MAX_SAMPLES, replace=False, p=p))
    t, j, O, Dv = _first_hits(sc, cand, min_wall)
    ok = np.isfinite(t) & (j >= 0) & (t > 0.02)
    ok[ok] = np.einsum("ij,ij->i", sc.N[j[ok]], -Dv[ok]) < -0.9        # Gegenflaeche antiparallel
    hit_idx = cand[ok].tolist()
    hit_d = (t[ok] + 1e-3).tolist()
    hit_p = (O[ok] + Dv[ok] * t[ok][:, None]).tolist()
    out = []
    if not hit_idx:
        return out
    hi = np.array(hit_idx); hd = np.array(hit_d); hp = np.array(hit_p)
    pts = sc.C[hi]
    # Cluster: Dreiecke mit gemeinsamen Punkten + Naehe (1,5 mm, fasst Vorder- und Rueckseite einer Wand zusammen)
    tree = cKDTree(pts)
    pairs = tree.query_pairs(1.5, output_type="ndarray").reshape(-1, 2)
    rep, ea, eb = {}, [], []
    for li, ti in enumerate(hi.tolist()):
        for v in sc.F[ti].tolist():
            if v in rep:
                ea.append(li); eb.append(rep[v])
            else:
                rep[v] = li
    ea = np.r_[pairs[:, 0], np.array(ea, dtype=np.int64), np.arange(len(pts))]
    eb = np.r_[pairs[:, 1], np.array(eb, dtype=np.int64), np.arange(len(pts))]
    _, lab = _cc(len(pts), ea, eb)
    for c in np.unique(lab):
        k = np.nonzero(lab == c)[0]
        area = float(sc.area[hi[k]].sum())
        if area < 0.5:
            continue
        j = k[np.argmin(hd[k])]
        dmin = float(hd[j])
        allp = np.vstack([sc.T[hi[k]].reshape(-1, 3), hp[k]])
        box = _box(allp)
        nm = np.abs(sc.N[hi[k]]).mean(0)
        nvec = (sc.N[hi[k]] * sc.area[hi[k], None]).sum(0)
        # Messpunkt: Mitte der Wand an der duennsten Stelle
        mid = (pts[j] + hp[j]) / 2
        ext = np.array(box[3:]) - np.array(box[:3])
        cand_ax = [a for a in range(3) if nm[a] < 0.5] or [int(np.argmin(nm))]
        ax = max(cand_ax, key=lambda a: ext[a])           # Schnittebene senkrecht zur laengsten Ausdehnung (Profil der Wand) und parallel zur Wandnormale
        mid = mid.copy()
        mid[ax] = (box[ax] + box[ax + 3]) / 2                # Schnittlage: Mitte der Wandflaeche (nicht Dreiecksschwerpunkt)
        ratio = dmin / min_wall
        sev = "hoch" if ratio < 0.5 else ("mittel" if ratio < 0.8 else "niedrig")
        axn = "xyz"[int(np.argmax(nm))]
        reason = "dünne Wand %.2f mm (< %.2f mm), Wandnormale ~%s, %.0f mm² betroffen" % (dmin, min_wall, axn.upper(), area)
        out.append({"kind": "duenne_wand", "severity": sev, "reason": reason, "value": round(dmin, 3), "area": round(area, 1),
                    "box": box, "center": [round(float(x), 3) for x in mid], "parts": sorted(set(int(x) for x in sc.comp[hi[k]])),
                    "view": _view_from_normal(nvec), "mode": "section",
                    "section": {"axis": "xyz"[ax], "pos": round(float(mid[ax]), 3)}, "measure": [round(float(x), 3) for x in mid]})
    return out


def find_line_walls(sc, t_max=4.0, min_area=2.0, nz_max=0.3):
    """Waende/Lippen/Rippen fuer `cad check --line-w`: senkrechte Waende (|n_z| < nz_max) mit Dicke bis t_max.
    Gleiche Strahlsonde wie find_thin_walls (Gegenflaeche antiparallel), nur laengerer Strahl. Gruppiert nach Dicke
    (0,02-mm-Klassen) und Ort (Wandmittelflaeche, 3 mm Naehe), damit Vorder- und Rueckseite eine Zeile ergeben.
    Rueckgabe je Wand: Dicke (Median, min, max), Flaeche (beide Seiten / 2), Mitte, Normalenachse, Box."""
    cand = np.nonzero((sc.area > 1e-6) & (np.abs(sc.N[:, 2]) < nz_max))[0]
    if len(cand) > MAX_SAMPLES:
        p = sc.area[cand] / sc.area[cand].sum()
        cand = np.sort(np.random.RandomState(0).choice(cand, MAX_SAMPLES, replace=False, p=p))
    if not len(cand):
        return []
    t, j, O, Dv = _first_hits(sc, cand, t_max)
    ok = np.isfinite(t) & (j >= 0) & (t > 0.05)
    ok[ok] = np.einsum("ij,ij->i", sc.N[j[ok]], -Dv[ok]) < -0.97
    if not ok.any():
        return []
    hi = cand[ok]; d = t[ok] + 1e-3
    mid = O[ok] + Dv[ok] * (t[ok] / 2)[:, None]
    cls = np.round(d / 0.02).astype(np.int64)
    out = []
    for c in np.unique(cls):
        k = np.nonzero(cls == c)[0]
        if not len(k):
            continue
        tree = cKDTree(mid[k])
        pairs = tree.query_pairs(3.0, output_type="ndarray").reshape(-1, 2)
        _, lab = _cc(len(k), np.r_[pairs[:, 0], np.arange(len(k))], np.r_[pairs[:, 1], np.arange(len(k))])
        for g in np.unique(lab):
            kk = k[lab == g]
            area = float(sc.area[hi[kk]].sum()) / 2
            if area < min_area:
                continue
            dd = d[kk]
            j0 = kk[np.argmin(np.abs(dd - np.median(dd)))]
            nm = np.abs(sc.N[hi[kk]]).mean(0)
            box = _box(mid[kk])
            out.append({"t": round(float(np.median(dd)), 3), "t_min": round(float(dd.min()), 3), "t_max": round(float(dd.max()), 3),
                        "area": round(area, 1), "center": [round(float(x), 2) for x in mid[j0]], "axis": "xyz"[int(np.argmax(nm))].upper(),
                        "box": box, "parts": sorted(set(int(x) for x in sc.comp[hi[kk]]))})
    out.sort(key=lambda w: -w["area"])
    return out


def find_open_edges(sc):
    e = np.sort(np.r_[sc.F[:, [0, 1]], sc.F[:, [1, 2]], sc.F[:, [2, 0]]], axis=1)
    u, inv, cnt = np.unique(e, axis=0, return_inverse=True, return_counts=True)
    out = []
    for kind, mask in (("offene", cnt == 1), ("nicht-mannigfaltige", cnt > 2)):
        E = u[mask]
        if not len(E):
            continue
        lab_n, lab = _cc(len(sc.P), E[:, 0], E[:, 1])
        for c in np.unique(lab[E[:, 0]]):
            ee = E[lab[E[:, 0]] == c]
            pts = sc.P[ee.ravel()]
            length = float(np.linalg.norm(sc.P[ee[:, 0]] - sc.P[ee[:, 1]], axis=1).sum())
            tri = np.nonzero(np.isin(sc.F[:, 0], ee.ravel()))[0]
            parts = sorted(set(int(x) for x in sc.comp[tri])) if len(tri) else []
            nvec = sc.N[tri].sum(0) if len(tri) else np.array([0, 0, 1.0])
            out.append({"kind": "offenes_netz", "severity": "hoch",
                        "reason": "%s Kanten (%d, zusammen %.1f mm): Netz nicht geschlossen/mannigfaltig" % (kind, len(ee), length),
                        "value": len(ee), "box": _box(pts), "center": [round(float(x), 3) for x in pts.mean(0)], "parts": parts,
                        "view": _view_from_normal(nvec), "mode": "shaded"})
    return out


def _sample_surface(P, F, spacing, cap=2_000_000):
    """Punkte (und Dreiecksindex) dicht auf den Dreiecken, Abstand <= spacing."""
    T = P[F]
    e = np.maximum.reduce([np.linalg.norm(T[:, 1] - T[:, 0], axis=1), np.linalg.norm(T[:, 2] - T[:, 1], axis=1),
                           np.linalg.norm(T[:, 0] - T[:, 2], axis=1)])
    k = np.maximum(1, np.ceil(e / spacing).astype(np.int64))
    pts, tid = [], []
    for kk in np.unique(k):
        idx = np.nonzero(k == kk)[0]
        w = [(i / kk, j / kk) for i in range(kk + 1) for j in range(kk + 1 - i)]
        if len(w) * len(idx) > cap:
            kk2 = max(1, int(math.sqrt(cap / len(idx)) * 1.4))
            w = [(i / kk2, j / kk2) for i in range(kk2 + 1) for j in range(kk2 + 1 - i)]
        W = np.array(w)
        a, b = W[:, 0:1], W[:, 1:2]
        for ch in np.array_split(idx, max(1, len(idx) * len(W) // 400000)):
            t = T[ch]
            q = t[:, None, 0, :] * (1 - a - b)[None] + t[:, None, 1, :] * a[None] + t[:, None, 2, :] * b[None]
            pts.append(q.reshape(-1, 3))
            tid.append(np.repeat(ch, len(W)))
    return np.vstack(pts), np.concatenate(tid)


def find_mesh_gaps(sc):
    """Spalte < GAP_MAX zwischen Netzkomponenten (ohne Formen): dichte Abtastung der Naehe-Bereiche, KD-Baum."""
    out = []
    n = sc.ncomp
    if not (2 <= n <= 60):
        return out
    bb = np.array([c["bbox"] for c in sc.comps])
    for a in range(n):
        for b in range(a + 1, n):
            g = np.maximum(0, np.maximum(bb[a, :3] - bb[b, 3:], bb[b, :3] - bb[a, 3:]))
            if np.linalg.norm(g) > GAP_MAX:
                continue
            lo = np.maximum(bb[a, :3], bb[b, :3]) - GAP_MAX - 0.2
            hi = np.minimum(bb[a, 3:], bb[b, 3:]) + GAP_MAX + 0.2
            sets = []
            for c in (a, b):
                idx = np.nonzero(sc.comp == c)[0]
                t = sc.T[idx]
                ok = np.all((t.max(1) >= lo) & (t.min(1) <= hi), axis=1)
                idx = idx[ok]
                if not len(idx):
                    break
                sets.append(_sample_surface(sc.P, sc.F[idx], 0.12)[0])
            if len(sets) < 2:
                continue
            tr = cKDTree(sets[1])
            d, j = tr.query(sets[0], distance_upper_bound=2 * GAP_MAX)
            i = int(np.argmin(d))
            if 1e-4 < d[i] < GAP_MAX:
                out.append({"d": float(d[i]), "p": sets[0][i].tolist(), "q": sets[1][j[i]].tolist(), "a": sc.comps[a]["name"], "b": sc.comps[b]["name"]})
    return out


def find_gaps(sc):
    raw = sc.shape_gaps if sc.n_solids >= 2 else find_mesh_gaps(sc)
    out = []
    for g in raw:
        p, q = np.array(g["p"]), np.array(g["q"])
        mid = (p + q) / 2
        d = g["d"]
        sev = "hoch" if d < 0.15 else "mittel"
        reason = "kleiner Spalt %.2f mm zwischen %s und %s (< %.1f mm: Teile können beim Druck verschmelzen)" % (d, g["a"], g["b"], GAP_MAX)
        v = q - p
        ax = int(np.argmin(np.abs(v)))     # Blick senkrecht zur Spaltrichtung: Achse mit kleinster Komponente
        names = {0: [90.0, 0.0], 1: [0.0, 0.0], 2: [0.0, 90.0]}
        view = names[ax] if abs(v[ax]) < 0.3 * np.linalg.norm(v) else [40.0, 30.0]
        out.append({"kind": "spalt", "severity": sev, "reason": reason, "value": round(d, 3), "box": _box(np.vstack([p, q]), 0.3),
                    "center": [round(float(x), 3) for x in mid], "parts": [], "part_names": [g["a"], g["b"]], "view": view, "mode": "xray"})
    return out


def find_focus(sc):
    out = []
    for f in sc.focus:
        c = np.array(f["center"]); h = f["size"] / 2
        v = f["view"]
        out.append({"kind": "fokus", "severity": "info", "reason": "im Skript markiert: cad.focus('%s')" % f["name"], "value": f["name"],
                    "box": [round(float(x), 3) for x in list(c - h) + list(c + h)], "center": [round(float(x), 3) for x in c], "parts": [],
                    "view": list(v) if isinstance(v, (list, tuple)) else v, "mode": "shaded", "focus": f["name"]})
    return out


# Profile: print (Standard, Druckteile: alles) | moebel (Bauteile ohne Druckbezug: keine Bruecke/Ueberhang, keine Bettpruefung)
PROFILES = {"print": {"suppress": ()}, "moebel": {"suppress": ("bruecke", "ueberhang")}}
PRINT_BED = 256.0


def profile_of(req):
    p = (req or {}).get("profile") or "print"
    if p not in PROFILES:
        raise ValueError("unbekanntes Profil %r (print | moebel)" % p)
    return p


def profile_hint(sc, profile, hs):
    """Nur Hinweis (nie stilles Umschalten): Modell groesser als das Druckbett und trotzdem Bruecken/Ueberhang gemeldet -> vermutlich Moebel."""
    size = [sc.bbox[3] - sc.bbox[0], sc.bbox[4] - sc.bbox[1], sc.bbox[5] - sc.bbox[2]]
    if profile == "print" and max(size) > PRINT_BED and any(h["kind"] in ("bruecke", "ueberhang") for h in hs):
        n = sum(1 for h in hs if h["kind"] in ("bruecke", "ueberhang"))
        return ("Hinweis: Modell %.0f x %.0f x %.0f mm passt nicht aufs Druckbett (%.0f mm) - %d Brücken/Überhänge sind für Möbel/Bauteile ohne Druck "
                "bedeutungslos: `--profile moebel` blendet sie aus." % (*size, PRINT_BED, n))
    return None


def analyze(sc, min_wall=MIN_WALL, angle=ANGLE, profile="print"):
    key = ("hot", round(min_wall, 4), angle, profile)
    c = sc.__dict__.setdefault("_hot", {})
    if key in c:
        return c[key]
    t0 = time.time()
    hs = find_open_edges(sc) + find_thin_walls(sc, min_wall) + (find_overhangs(sc, angle) if "bruecke" not in PROFILES[profile]["suppress"] else []) + \
        find_gaps(sc) + find_focus(sc)
    hs.sort(key=lambda h: (SEV_RANK[h["severity"]], KIND_RANK[h["kind"]], -(h.get("area") or 0)))
    for i, h in enumerate(hs, 1):
        h["n"] = i
        h["part_names"] = h.get("part_names") or [sc.comps[p]["name"] for p in h["parts"]]
    res = {"hotspots": hs, "seconds": round(time.time() - t0, 2), "profile": profile, "hint": profile_hint(sc, profile, hs) if profile == "print" else None}
    c[key] = res
    return res


def scene_info(sc):
    return {"source": sc.source, "triangles": int(sc.m), "parts": sc.ncomp, "bbox": [round(x, 3) for x in sc.bbox],
            "volume": round(sc.volume, 1), "part_list": [{k: v for k, v in c.items() if not k.startswith("_")} for c in sc.comps],
            "build_seconds": round(sc.t_build, 2)}


# ----------------------------------------------------------------------------------------------- Operationen
def op_hotspots(req):
    sc = get_scene(req)
    prof = profile_of(req)
    res = analyze(sc, float(req.get("min_wall", MIN_WALL)), profile=prof)
    return {"ok": True, "stdout": "", "error": None, "hotspots": res["hotspots"], "analysis_seconds": res["seconds"], "scene": scene_info(sc),
            "profile": prof, "hint": res["hint"]}


def op_check(req):
    """Befunde fuer `cad check`: Bett, Gueltigkeit/Geschlossenheit, Ueberhang/Bruecken (overhang_check.analyze), Teileabstand, duenne Wand."""
    import importlib.util
    sc = get_scene(req)
    prof = profile_of(req)
    moebel = "bruecke" in PROFILES[prof]["suppress"]
    bed = req.get("bed") or [256, 256, 256]
    size = [sc.bbox[3] - sc.bbox[0], sc.bbox[4] - sc.bbox[1], sc.bbox[5] - sc.bbox[2]]
    items = []

    def add(name, status, text, hs=None):
        items.append({"check": name, "status": status, "text": text, "hotspots": hs or []})

    over = [i for i, (s, b) in enumerate(zip(size, bed)) if s > b + 1e-6]
    if moebel:
        add("profil", "OK", "Profil moebel: Bett, Überhang/Brücke und Teileabstand entfallen (nicht druckbezogen); geprüft werden Geschlossenheit/Gültigkeit, dünne Wand, Spalt")
    elif over:
        add("bett", "FAIL", "Teil %.1f x %.1f x %.1f mm passt nicht aufs Bett %gx%gx%g (Achse %s zu groß)" % (*size, *bed, ",".join("XYZ"[i] for i in over)))
    else:
        add("bett", "OK", "%.1f x %.1f x %.1f mm, Bett %gx%gx%g" % (*size, *bed))
    hint = None
    opens = find_open_edges(sc)
    if opens or not sc.valid_shape:
        add("geschlossen", "FAIL", ("offene/nicht-mannigfaltige Netzkanten: %d Stelle(n)" % len(opens)) if opens else "Form ist laut FreeCAD ungültig (isValid=False)", opens)
    else:
        add("geschlossen", "OK", "Netz geschlossen (%d Dreiecke, %d Teil(e)), Volumen %.0f mm³" % (sc.m, sc.ncomp, sc.volume))
    if not moebel:
        # Ueberhang: Logik und Grenzen aus tools/printer/overhang_check.py (importiert, nicht kopiert)
        spec = importlib.util.spec_from_file_location("overhang_check", "/mnt/raid1/3d_print/tools/printer/overhang_check.py")
        oc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oc)
        zmin, zmax, warn, sa, ba, contact = oc.analyze(sc.T.tolist(), ANGLE, MIN_AREA, MAX_BRIDGE)
        ov = [h for h in find_overhangs(sc) if h["kind"] in ("ueberhang", "bruecke")]
        crit = [h for h in ov if h["severity"] != "info"]
        infos = [h for h in ov if h["severity"] == "info"]
        if crit:
            lines = "; ".join(h["reason"] for h in crit[:3])
            add("ueberhang", "WARN", "%d kritische(r) Überhang/Brücke ohne Support: %s%s" % (len(crit), lines, " (+%d weitere)" % (len(crit) - 3) if len(crit) > 3 else ""), crit)
        else:
            extra = ""
            if infos:
                extra = " - %d kurze Brücke(n) ≤ %.0f mm als Info (größte Spannweite %.0f mm)" % (len(infos), MAX_BRIDGE, max(h["value"] for h in infos))
            if warn:
                extra += "; overhang_check.py schätzt über die ganze Höhenbandfläche strenger (%s), hier zählt die freie Spannweite je Fläche" % warn[0][1].split(",")[0]
            add("ueberhang", "OK", "keine kritischen Überhänge (Grenze %.0f° zur Waagerechten, Brücken bis %.0f mm)%s" % (ANGLE, MAX_BRIDGE, extra), infos)
        hint = profile_hint(sc, prof, ov)
    thin = [h for h in find_thin_walls(sc, float(req.get("min_wall", MIN_WALL))) if h["severity"] in ("hoch", "mittel")]
    if thin:
        add("duenne_wand", "WARN", "%d dünne Wand/Wände unter %.2f mm (dünnste %.2f mm)" % (len(thin), req.get("min_wall", MIN_WALL), min(h["value"] for h in thin)), thin)
    else:
        add("duenne_wand", "OK", "keine Wand dünner als %.2f mm (bzw. nur knapp darunter)" % req.get("min_wall", MIN_WALL))
    gaps = find_gaps(sc)
    if gaps:
        add("spalt", "WARN", "%d kleine(r) Spalt(e) < %.1f mm zwischen Teilen (kleinster %.2f mm)" % (len(gaps), GAP_MAX, min(h["value"] for h in gaps)), gaps)
    # Teileabstand: viele Einzelteile weit auseinander
    if sc.ncomp > 1 and not moebel:
        bb = np.array([c["bbox"] for c in sc.comps])
        far = []
        for a in range(sc.ncomp):
            dmin = 1e9
            for b in range(sc.ncomp):
                if a != b:
                    g = np.maximum(0, np.maximum(bb[a, :3] - bb[b, 3:], bb[b, :3] - bb[a, 3:]))
                    dmin = min(dmin, float(np.linalg.norm(g)))
            if dmin > 30:
                far.append((sc.comps[a]["name"], dmin))
        if far:
            add("teileabstand", "WARN", "%d Teile, davon weit entfernt (> 30 mm vom nächsten Teil): %s - Platte unnötig groß, Düse fährt weit" % (
                sc.ncomp, ", ".join("%s %.0f mm" % f for f in far[:4])))
        else:
            add("teileabstand", "OK", "%d Teile, Abstände unauffällig (≤ 30 mm zum Nachbarn)" % sc.ncomp)
    status = 1 if any(i["status"] != "OK" for i in items) else 0
    res = {"ok": True, "stdout": "", "error": None, "items": items, "exit": status, "scene": scene_info(sc), "profile": prof, "hint": hint}
    if req.get("line_walls"):
        res["line_walls"] = find_line_walls(sc, float(req.get("t_max", 4.0)))
        for w in res["line_walls"]:
            w["part_names"] = [sc.comps[i]["name"] for i in w["parts"]]
    return res


# ----------------------------------------------------------------------------------------------- Dateien/Schnitt
def write_stl(path, P, F):
    T = P[F].astype(np.float32)
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    ln = np.linalg.norm(n, axis=1)
    n = np.divide(n, ln[:, None], out=np.zeros_like(n), where=ln[:, None] > 0)
    rec = np.zeros(len(F), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, T
    with open(path, "wb") as f:
        f.write(b"cad".ljust(80, b"\0"))
        f.write(struct.pack("<I", len(F)))
        rec.tofile(f)


def section_segments(T, axis, pos):
    """Schnittstrecken der Dreiecke T (m,3,3) mit der Ebene x/y/z = pos -> Liste von [p, q]."""
    a = "xyz".index(axis)
    s = T[:, :, a] - (pos + 1e-7)
    sg = s > 0
    k = sg.sum(1)
    sel = np.nonzero((k > 0) & (k < 3))[0]
    if not len(sel):
        return []
    Ts, ss = T[sel], s[sel]
    pts = []
    for i, j in ((0, 1), (1, 2), (2, 0)):
        cr = (ss[:, i] > 0) != (ss[:, j] > 0)
        t = np.divide(ss[:, i], ss[:, i] - ss[:, j], out=np.zeros(len(ss)), where=cr)
        pts.append((cr, Ts[:, i] + t[:, None] * (Ts[:, j] - Ts[:, i])))
    segs = []
    for r in range(len(sel)):
        q = [p[r] for c, p in pts if c[r]]
        if len(q) == 2:
            segs.append([[round(float(x), 4) for x in q[0]], [round(float(x), 4) for x in q[1]]])
    return segs


def _write_parts(sc, components):
    cadlib._cleanup_cache()
    rid = "%d_%d_%d" % (os.getpid(), int(time.time()), len(_cache))
    files = []
    if components and sc.ncomp <= 60:
        for c in sc.comps:
            idx = np.nonzero(sc.comp == c["id"])[0]
            path = os.path.join(cadlib.CACHE, "%s_c%02d.stl" % (rid, c["id"]))
            write_stl(path, sc.P, sc.F[idx])
            files.append({"path": path, "name": c["name"], "item": c["item"], "comp": c["id"], "triangles": c["tris"], "bbox": c["bbox"]})
    else:
        for it, nm in enumerate(sc.names):
            idx = np.nonzero(sc.item == it)[0]
            path = os.path.join(cadlib.CACHE, "%s_i%02d.stl" % (rid, it))
            write_stl(path, sc.P, sc.F[idx])
            tri = sc.T[idx].reshape(-1, 3)
            files.append({"path": path, "name": nm, "item": it, "comp": None, "triangles": int(len(idx)),
                          "bbox": [round(float(x), 3) for x in list(tri.min(0)) + list(tri.max(0))]})
    return files


# ----------------------------------------------------------------------------------------------- Sichtbarkeit (Verdeckung)
VIS_PRESETS = {"front": (0, 0), "back": (180, 0), "right": (90, 0), "left": (270, 0), "top": (0, 90), "bottom": (0, -90), "iso": (40, 30)}


def _view_basis(az, el):
    """Kamerarichtung e (vom Ziel zur Kamera), rechts r, oben u - wie in cad_render.render_job."""
    e = np.array([math.sin(math.radians(az)) * math.cos(math.radians(el)), -math.cos(math.radians(az)) * math.cos(math.radians(el)), math.sin(math.radians(el))])
    up = np.array([0.0, math.copysign(1, el), 0.0]) if abs(el) >= 89.5 else np.array([0.0, 0.0, 1.0])
    r = np.cross(-e, up); r /= np.linalg.norm(r)
    u = np.cross(r, -e); u /= np.linalg.norm(u)
    return e, r, u


def visibility(sc, center, size, az, el, comp_ids, n=24):
    """Strahlprobe wie die Kamera: n x n parallele Strahlen ueber den Ausschnitt (orthografisch), erster Treffer je Strahl.
    Rueckgabe: je Teil {rays: Strahlen, die das Teil treffen, first: davon als erster Treffer}, Anteil flaecher Treffer (Normale zur Kamera > 0,95)."""
    e, r, u = _view_basis(az, el)
    center = np.asarray(center, float)
    idx = np.nonzero(np.isin(sc.comp, comp_ids))[0]
    T = sc.T[idx]
    if len(T) > 30000:
        n = 12
    g = (np.arange(n) + 0.5) / n - 0.5
    gu, gv = np.meshgrid(g * size, g * size)
    org = center + e * (np.linalg.norm(sc.bbox[3:]) + np.linalg.norm(sc.bbox[:3]) + size) + gu.reshape(-1, 1) * r + gv.reshape(-1, 1) * u   # (R,3)
    d = -e
    v0, v1, v2 = T[:, 0], T[:, 1], T[:, 2]
    e1, e2 = v1 - v0, v2 - v0
    pv = np.cross(d, e2)                                  # (m,3)
    det = np.einsum("ij,ij->i", e1, pv)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    nR = len(org)
    best_t = np.full(nR, np.inf)
    best_i = np.full(nR, -1)
    hit_any = np.zeros((nR, len(comp_ids)), dtype=bool)
    cmap = {int(c): k for k, c in enumerate(comp_ids)}
    tcomp = np.array([cmap[int(c)] for c in sc.comp[idx]])
    step = max(1, 1500000 // max(len(T), 1))
    for a in range(0, nR, step):
        o = org[a:a + step]
        tv = o[:, None, :] - v0[None]                    # (r,m,3)
        uu = np.einsum("rmj,mj->rm", tv, pv) * inv
        qv = np.cross(tv, e1[None])
        vv = np.einsum("j,rmj->rm", d, qv) * inv
        tt = np.einsum("mj,rmj->rm", e2, qv) * inv
        hit = ok[None] & (uu >= -1e-9) & (vv >= -1e-9) & (uu + vv <= 1 + 1e-9) & (tt > 0)
        tt = np.where(hit, tt, np.inf)
        j = tt.argmin(1)
        best_t[a:a + step] = tt[np.arange(len(o)), j]
        best_i[a:a + step] = np.where(np.isfinite(best_t[a:a + step]), j, -1)
        rr, mm = np.nonzero(hit)
        hit_any[rr + a, tcomp[mm]] = True
    first = np.full(len(comp_ids), 0)
    occ = np.zeros((len(comp_ids), len(comp_ids)), dtype=int)      # occ[k, j]: Strahlen, die Teil k treffen, aber zuerst Teil j
    flat = 0
    nh = 0
    for k in range(nR):
        if best_i[k] >= 0:
            fc = tcomp[best_i[k]]
            first[fc] += 1
            occ[np.nonzero(hit_any[k])[0], fc] += 1
            nh += 1
            if abs(float(sc.N[idx[best_i[k]]] @ e)) > 0.95:
                flat += 1
    occ[np.arange(len(comp_ids)), np.arange(len(comp_ids))] = 0
    return {"rays": hit_any.sum(0).tolist(), "first": first.tolist(), "hits": nh, "total": nR, "flat": (flat / nh) if nh else 1.0,
            "occluder": [int(comp_ids[int(o.argmax())]) if o.max() > 0 else -1 for o in occ]}


def assess_focus(sc, fv, isolate=True):
    """Verdeckung fuer eine Fokus-Kachel: fv = {center, size, dir:[az,el], name}. Waehlt bei Verdeckung/flaechiger Ansicht eine bessere Richtung.
    Ziel-Teile = Teile, deren Box den Fokuspunkt (+-0,5 mm) enthaelt. Verdeckt = Teil wird von Strahlen getroffen, ist aber nie erster Treffer."""
    c = np.array(fv["center"], float)
    h = fv["size"] / 2
    reg = [*(c - h), *(c + h)]
    comps = [k for k, cc in enumerate(sc.comps) if (not isolate) or all(cc["bbox"][i] <= reg[i + 3] + 0.5 and cc["bbox"][i + 3] >= reg[i] - 0.5 for i in range(3))]
    if not comps:
        return {"name": fv.get("name"), "status": "leer"}
    targets = [k for k in comps if all(sc.comps[k]["bbox"][i] - 0.5 <= c[i] <= sc.comps[k]["bbox"][i + 3] + 0.5 for i in range(3))]

    def rate(az, el):
        r = visibility(sc, c, fv["size"], az, el, comps)
        hidden = [comps[i] for i in range(len(comps)) if r["rays"][i] >= 3 and r["first"][i] <= 0.02 * r["rays"][i]]
        occ = {k: r["occluder"][comps.index(k)] for k in hidden}
        return {"hidden": hidden, "hidden_targets": [k for k in hidden if k in targets], "flat": r["flat"], "dir": [az, el], "hits": r["hits"], "occluder": occ}

    cur = rate(*fv["dir"])
    res = {"name": fv.get("name"), "status": "ok", "current": cur, "targets": [sc.comps[k]["name"] for k in targets],
           "hidden": [sc.comps[k]["name"] for k in cur["hidden"]], "hidden_targets": [sc.comps[k]["name"] for k in cur["hidden_targets"]],
           "flat": round(cur["flat"], 3)}
    # Nur verdeckte Ziel-Teile gelten als Problem. Ein Kriterium "flaechige Kachel" wurde gemessen und verworfen: bei achsparallelen
    # Moebel-Boxen sind 7 von 9 Fokus-Kacheln flaechig (Normale zur Kamera), das trennt nicht.
    bad = bool(cur["hidden_targets"])
    if bad and cur["hits"]:
        cands = []
        for nm, (az, el) in VIS_PRESETS.items():
            if [az, el] == list(fv["dir"]):
                continue
            q = rate(az, el)
            score = (len(q["hidden_targets"]), len(q["hidden"]), 0 if nm == "iso" else 1)
            cands.append((score, nm, q))
        cands.sort(key=lambda x: x[0])
        best = cands[0]
        now = (len(cur["hidden_targets"]), len(cur["hidden"]))
        if best[0][:2] < now and best[0][0] < now[0]:
            res["alternative"] = {"view": best[1], "dir": best[2]["dir"], "hidden_targets": [sc.comps[k]["name"] for k in best[2]["hidden_targets"]],
                                  "hidden": [sc.comps[k]["name"] for k in best[2]["hidden"]], "flat": round(best[2]["flat"], 3)}
    res["problem"] = "verdeckt" if bad else None
    res["occluders"] = {sc.comps[k]["name"]: (sc.comps[o]["name"] if o >= 0 else None) for k, o in cur["occluder"].items() if k in cur["hidden_targets"]}
    return res



def op_look(req):
    """Alles fuer `cad look`, was Geometrie braucht: Teile als STL, optional Hotspot N, Schnittkontur."""
    os.makedirs(cadlib.CACHE, exist_ok=True)
    sc = get_scene(req)
    out = {"ok": True, "stdout": "", "error": None, "stem": sc.stem, "focus": sc.focus, "zref": sc.zmin, "scene": scene_info(sc)}
    if req.get("hotspot"):
        hs = analyze(sc, float(req.get("min_wall", MIN_WALL)), profile=profile_of(req))["hotspots"]
        n = int(req["hotspot"])
        if not (1 <= n <= len(hs)):
            return {"ok": False, "stdout": "", "error": "Hotspot %d gibt es nicht (%d Treffer: cad hotspots)" % (n, len(hs))}
        out["hotspot"] = hs[n - 1]
        out["n_hotspots"] = len(hs)
    out["stls"] = _write_parts(sc, bool(req.get("components")))
    if req.get("assess_focus") and sc.focus:
        want = req["assess_focus"]
        out["assess"] = {}
        for f in sc.focus:
            if want in ("all", f["name"]):
                v = f["view"]
                az, el = VIS_PRESETS[v] if isinstance(v, str) and v in VIS_PRESETS else (v if not isinstance(v, str) else (0, 0))
                try:
                    out["assess"][f["name"]] = assess_focus(sc, {"name": f["name"], "center": f["center"], "size": f["size"], "dir": [az, el]}, bool(req.get("components")))
                except Exception as e:           # Verdeckungspruefung ist Komfort: nie das Bild verhindern
                    out["assess"][f["name"]] = {"name": f["name"], "status": "fehler", "error": str(e)[:120], "problem": None}
    sec = req.get("section")
    if not sec and out.get("hotspot") and out["hotspot"].get("section") and req.get("mode") in (None, "section"):
        sec = out["hotspot"]["section"]                  # duenne Wand: Schnitt automatisch
    if sec:
        out["section_used"] = {"axis": sec["axis"], "pos": float(sec["pos"])}
        ax, pos = sec["axis"], float(sec["pos"])
        out["contours"] = {}
        for f in out["stls"]:
            if f["comp"] is None:
                idx = np.nonzero(sc.item == f["item"])[0]
            else:
                idx = np.nonzero(sc.comp == f["comp"])[0]
            a = "xyz".index(ax)
            if f["bbox"][a] - 1e-6 <= pos <= f["bbox"][a + 3] + 1e-6:
                out["contours"][str(f["path"])] = section_segments(sc.T[idx], ax, pos)
    return out


def op_diff(req):
    """Flaechenvergleich alt/neu: Dreiecke der Neu-Datei ohne Gegenstueck in Alt = hinzugefuegt, umgekehrt = entfernt."""
    os.makedirs(cadlib.CACHE, exist_ok=True)
    a = get_scene({"file": req["file"], "cwd": req.get("cwd")})
    b = get_scene({"file": req["file2"], "cwd": req.get("cwd")})
    t0 = time.time()
    area = a.area.sum() + b.area.sum()
    spacing = max(0.25, math.sqrt(area / 1.2e6))
    tol = 1.2 * spacing + 0.05
    sa, ta = _sample_surface(a.P, a.F, spacing)
    sb, tb = _sample_surface(b.P, b.F, spacing)
    ub = 2 * tol                               # nur "naeher/weiter als tol" zaehlt; die Schranke verhindert Ausreisser-Laufzeiten (Gitterpunkt-Gleichstaende)
    d_ab = cKDTree(sb).query(sa, distance_upper_bound=ub)[0]           # Abstand der Alt-Punkte zur Neu-Flaeche
    d_ba = cKDTree(sa).query(sb, distance_upper_bound=ub)[0]
    far_a = np.bincount(ta, weights=(d_ab > tol).astype(float), minlength=a.m) / np.maximum(np.bincount(ta, minlength=a.m), 1)
    far_b = np.bincount(tb, weights=(d_ba > tol).astype(float), minlength=b.m) / np.maximum(np.bincount(tb, minlength=b.m), 1)
    removed = np.nonzero(far_a > 0.5)[0]
    added = np.nonzero(far_b > 0.5)[0]
    common = np.nonzero(far_b <= 0.5)[0]
    rid = "%d_%d_diff" % (os.getpid(), int(time.time()))
    cadlib._cleanup_cache()
    files = []
    for nm, sc_, idx, col in (("gleich (neu)", b, common, [0.80, 0.82, 0.86]), ("hinzugefügt", b, added, [0.15, 0.72, 0.22]),
                              ("entfernt", a, removed, [0.92, 0.12, 0.10])):
        if not len(idx):
            continue
        path = os.path.join(cadlib.CACHE, "%s_%d.stl" % (rid, len(files)))
        write_stl(path, sc_.P, sc_.F[idx])
        tri = sc_.T[idx].reshape(-1, 3)
        files.append({"path": path, "name": nm, "color": col, "triangles": int(len(idx)), "bbox": [round(float(x), 3) for x in list(tri.min(0)) + list(tri.max(0))]})
    stats = {"added_area": round(float(b.area[added].sum()), 1), "removed_area": round(float(a.area[removed].sum()), 1),
             "volume_old": round(a.volume, 1), "volume_new": round(b.volume, 1), "dvolume": round(b.volume - a.volume, 1),
             "bbox_old": [round(x, 2) for x in a.bbox], "bbox_new": [round(x, 2) for x in b.bbox], "tol": round(tol, 3), "spacing": round(spacing, 3),
             "seconds": round(time.time() - t0, 2)}
    allb = np.array([f["bbox"] for f in files]) if files else None
    return {"ok": True, "stdout": "", "error": None, "stls": files, "stats": stats, "stem": "%s_vs_%s" % (a.stem, b.stem),
            "zref": min(a.zmin, b.zmin), "names": [a.stem, b.stem]}
