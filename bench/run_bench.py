#!/usr/bin/env python3
"""Wiederholbares Benchmark/Regressionstest fuer `cad` (Hotspots, Check, Selbsttest). Aufruf: python3 bench/run_bench.py [--quick] [--json]
Alle Messungen laufen ueber die CLI `cad`; Zeit = Wanduhr inkl. CLI-Start (Worker vorher neu gestartet, also kalter Cache).
Exit 0 = alles PASS, 1 = mindestens ein FAIL. Referenz Couch-Baseline: bench/ref/couch_hotspots_baseline_20261113.json
--quick laesst Couch-Modell und Selbsttest aus."""
import argparse, collections, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
KB = "/mnt/raid1/3d_print/kotbeutel_bin/"
FILES = {
    "nase": KB + "gridfinity_nase_serie.stl", "lid": KB + "gridfinity_lid.stl", "bin": KB + "gridfinity_bin.stl",
    "tuecher": "/mnt/raid1/3d_print/tuecher_bin/gridfinity_tuecher.stl", "overhang": "/mnt/raid1/3d_print/cad_out/test/overhang_test.stl",
}
COUCH_DIR = "/mnt/raid1/3d_print/cad_out/test/couch_fixture"   # eingefrorenes Modell (bench/fixtures/couch_console.py, OUT_DIR umgebogen); das Live-Modell wuchs am 13.11. nach der Referenz (41 statt 29 Teile)
COUCH_REF = os.path.join(HERE, "ref", "couch_hotspots_baseline_20261113.json")
COUCH_MAX_S = 5.0
rows = []


def sh(args, cwd=None, timeout=600):
    t = time.time()
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p, time.time() - t


def cad_json(args, cwd=None):
    p, dt = sh(["cad"] + args + ["--json"], cwd)
    try:
        return json.loads(p.stdout), p.returncode, dt
    except ValueError:
        return {"hotspots": [], "items": []}, p.returncode, dt


_hot = {}


def hot(k):
    """Hotspots einer Referenzdatei, nur einmal (kalt) gemessen."""
    if k not in _hot:
        _hot[k] = cad_json(["hotspots", FILES[k]])
    return _hot[k]


def row(name, secs, text, ok):
    rows.append((name, secs, text, ok))


def counts(hs):
    return collections.Counter("%s/%s" % (h["kind"], h["severity"]) for h in hs)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--quick", action="store_true"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    sh(["cad", "worker", "restart"])

    # Nasen-Serie: dünne Wand 0,35 hoch / 0,55 mittel / 0,75 niedrig, nichts anderes (Nutdecke kein Überhang)
    d, rc, dt = hot("nase")
    hs = d["hotspots"]; vals = sorted(h["value"] for h in hs if h["kind"] == "duenne_wand")
    ok = (len(hs) == 3 and len(vals) == 3 and all(abs(v - e) <= 0.03 for v, e in zip(vals, (0.35, 0.55, 0.75)))
          and [h["severity"] for h in sorted(hs, key=lambda h: h["value"])] == ["hoch", "mittel", "niedrig"] and rc == 1)
    row("nase: 3x duenne Wand 0.35/0.55/0.75", dt, "%d Treffer %s" % (len(hs), vals), ok)

    # Hinweis "Moebelprofil" darf bei keiner Druckreferenz erscheinen (alle <= Bett)
    hints = []
    for k in ("nase", "lid", "bin", "tuecher", "overhang"):
        d, rc, dt = hot(k); hints.append(d.get("hint"))
    row("profil-hinweis: bei Druckreferenzen kein Hinweis", 0, "%d von 5 mit Hinweis" % sum(1 for h in hints if h), not any(hints))

    # Deckel: 0 Treffer, check Exit 0
    d, rc, dt = hot("lid")
    row("deckel: hotspots 0 Treffer", dt, "%d Treffer" % len(d["hotspots"]), len(d["hotspots"]) == 0 and rc == 0)
    p, dt = sh(["cad", "check", FILES["lid"]])
    row("deckel: check Exit 0", dt, "Exit %d" % p.returncode, p.returncode == 0)

    # Tuecher/Bin: nur kurze Bruecken (~4 mm) als Info
    for k in ("tuecher", "bin"):
        d, rc, dt = hot(k); hs = d["hotspots"]
        br = [h["value"] for h in hs]
        ok = bool(hs) and all(h["kind"] == "bruecke" and h["severity"] == "info" for h in hs) and all(2.5 <= v <= 5.5 for v in br) and rc == 0
        row("%s: nur kurze Bruecke (Info ~4 mm)" % k, dt, "%d Treffer, Spannweite %.1f..%.1f" % (len(hs), min(br or [0]), max(br or [0])), ok)

    # Ueberhang-Testdatei: 30 Grad hoch + Bruecke 14 mm mittel
    d, rc, dt = hot("overhang"); hs = d["hotspots"]
    ov = [h for h in hs if h["kind"] == "ueberhang"]; br = [h for h in hs if h["kind"] == "bruecke"]
    ok = (len(hs) == 2 and len(ov) == 1 and ov[0]["severity"] == "hoch" and abs(ov[0]["value"] - 30) <= 1
          and len(br) == 1 and br[0]["severity"] == "mittel" and abs(br[0]["value"] - 14) <= 0.5 and rc == 1)
    row("ueberhang-test: 30 Grad hoch + Bruecke 14 mittel", dt, "%s" % [(h["kind"], h["severity"], h["value"]) for h in hs], ok)

    if not a.quick:
        # Couch-Modell (print-Profil = Standard): Zeit und Treffer gegen Baseline
        p, dt = sh(["cad", "run", "couch_console.py"], cwd=COUCH_DIR)
        row("couch: cad run couch_console.py", dt, "Exit %d" % p.returncode, p.returncode == 0)
        d, rc, dt = cad_json(["hotspots", "--max", "500"], cwd=COUCH_DIR); hs = d["hotspots"]
        ref = json.load(open(COUCH_REF))["hotspots"]
        row("couch: hotspots Zeit < %.0f s" % COUCH_MAX_S, dt, "%.1f s (Baseline 36-64 s), Load %.0f" % (dt, os.getloadavg()[0]), dt < COUCH_MAX_S)
        c, cr = counts(hs), counts(ref)
        row("couch: Trefferzahlen wie Baseline", 0, "%d vs %d; Abweichungen %s" % (len(hs), len(ref), {k: (c[k], cr[k]) for k in set(c) | set(cr) if c[k] != cr[k]}),
            c == cr)
        rb = sorted(h["value"] for h in ref if h["kind"] == "bruecke"); nb = sorted(h["value"] for h in hs if h["kind"] == "bruecke")
        worst = max((abs(x - y) - max(0.6, 0.03 * y) for x, y in zip(nb, rb)), default=0) if len(nb) == len(rb) else 1.0
        dmax = max((abs(x - y) for x, y in zip(nb, rb)), default=0)
        row("couch: Spannweiten wie Baseline (<= 3 % oder 0,6 mm)", 0, "groesste Abweichung %.2f mm" % dmax, worst <= 0)
        # Profil moebel (falls vorhanden)
        p, dt = sh(["cad", "hotspots", "--profile", "moebel", "--json", "--max", "500"], cwd=COUCH_DIR)
        if p.returncode in (0, 1) and p.stdout.startswith("{"):
            hm = json.loads(p.stdout)["hotspots"]; cm = counts(hm)
            ok = not any(k.startswith(("bruecke", "ueberhang")) for k in cm) and cm.get("offenes_netz/hoch", 0) == 6 and cm.get("fokus/info", 0) == 9
            row("couch: Profil moebel (keine Bruecke, 6 offen, 9 Fokus)", dt, str(dict(cm)), ok)
        else:
            row("couch: Profil moebel", dt, "nicht vorhanden (noch nicht gebaut)", False)
        d_ = counts(hs)
        row("couch: Profil-Hinweis erscheint (print, > Bett, Bruecken)", 0, "Hinweis %s" % ("ja" if d.get("hint") else "nein"), bool(d.get("hint")))
        # Fokus-Sheet: Verdeckung erkannt, Sheet breit genug
        p, dt = sh(["cad", "look", "--focus", "all", "--json", "-o", "/mnt/raid1/3d_print/cad_out/bench_focus.png"], cwd=COUCH_DIR)
        try:
            lk = json.loads(p.stdout); cap = " ".join(lk.get("caption", []))
            row("focus: Verdeckung erkannt (Mittelstuetze, Laptopfach), Breite 1300..1450 px", dt,
                "Bild %s, verdeckt-Meldungen %d" % (lk["size"], cap.count("verdeckt")),
                "Mittelstuetze: Ziel Mittelstuetze" in cap and "Laptopfach: Ziel Laptop" in cap and 1300 <= lk["size"][0] <= 1450)
        except Exception as e:
            row("focus: Verdeckung erkannt", dt, "Fehler %s" % e, False)
        p, dt = sh(["cad", "look", "--focus", "Mittelstuetze", "--keep-view", "--json", "-o", "/mnt/raid1/3d_print/cad_out/bench_focus_keep.png"], cwd=COUCH_DIR)
        try:
            lk = json.loads(p.stdout); cap = " ".join(lk.get("caption", []))
            row("focus --keep-view: nur Warnung, Ansicht bleibt front", dt, "WARNUNG" if "WARNUNG" in cap else "keine Warnung", "WARNUNG" in cap and lk["views"][0]["dir"] == [0, 0])
        except Exception as e:
            row("focus --keep-view", dt, "Fehler %s" % e, False)
        # Font: Umlaute haben eigene Glyphen (nicht das Ersatzzeichen); PIL liegt nur in python3.11 (wie im Blender-Renderer)
        code = ("import sys; sys.path.insert(0, %r)\nimport cad_render as cr\nfrom PIL import Image, ImageDraw, ImageFont\n"
                "f = cr.load_font(ImageFont, 24)\n"
                "def glyph(ch):\n    im = Image.new('L', (40, 40), 255); ImageDraw.Draw(im).text((4, 4), ch, font=f, fill=0); return im.tobytes()\n"
                "tofu = glyph('\\uffff')\nbad = [ch for ch in 'äöüßÄÖÜ²°≤' if glyph(ch) == tofu]\n"
                "print('fehlend:', ''.join(bad) or 'keine', '|', getattr(f, 'path', 'Standardschrift'))\n") % TOOLS
        p, dt = sh(["python3.11", "-c", code])
        row("font: Umlaute/ß/²/°/≤ gerendert (kein Ersatzzeichen)", dt, p.stdout.strip() or p.stderr.strip()[-80:], "fehlend: keine" in p.stdout)
        # Selbsttest Lineal
        env = {k: v for k, v in os.environ.items() if k != "DISPLAY"}
        t = time.time(); p = subprocess.run(["python3", os.path.join(TOOLS, "cad_selftest.py")], capture_output=True, text=True, env=env, timeout=600); dt = time.time() - t
        w = [l for l in p.stdout.splitlines() if l.startswith("WORST")]
        try:
            worst_mm = float(w[0].split()[1])
        except Exception:
            worst_mm = 99
        row("selbsttest: Lineal-Abweichung <= 0.65 mm (Toleranz 0.66, gemessen 0.652)", dt, "%.3f mm" % worst_mm, worst_mm <= 0.66)

    if a.json:
        print(json.dumps([{"name": n, "seconds": round(s, 2), "text": t, "pass": o} for n, s, t, o in rows], ensure_ascii=False, indent=1))
    else:
        print("%-52s %7s  %-5s %s" % ("Test", "Zeit s", "", "Messwert"))
        for n, s, t, o in rows:
            print("%-52s %7.2f  %-5s %s" % (n, s, "PASS" if o else "FAIL", t))
        print("\n%d/%d PASS" % (sum(1 for r in rows if r[3]), len(rows)))
    sys.exit(0 if all(r[3] for r in rows) else 1)


main()
