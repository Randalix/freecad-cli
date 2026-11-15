#!/usr/bin/env python3
"""Schichtzeiten und Bahnarten je Schicht aus G-Code (OrcaSlicer/Bambu, .gcode oder .gcode.3mf).

Entstanden bei der Linie in der Topf-Außenwand auf Höhe des Innenbodens (Square Pot, Joe 15.11.2026): Sprünge der
Schichtzeit (z. B. 13 s Wand gegen 160 s Brücke + massiver Boden) machen die Abkühlung der Außenwand ungleich.

Zeiten = Weglänge / Vorschub (ohne Beschleunigung, Fahrten und Wartezeiten) -> nur als Verhältnis zwischen Schichten
brauchbar, nicht als absolute Druckzeit.

Nutzung:
  python3 gcode_schichten.py datei.gcode.3mf [--z0 6 --z1 16] [--sprung 3]
Spalten: Höhe, Zeit s, Außenwand-Vorschub mm/s, Lüfter (0-255), Bahnlänge mm je Art.
--sprung F markiert Schichten, deren Zeit sich gegenüber der vorigen um mehr als Faktor F ändert.
"""
import math, re, sys, zipfile


def lade(fn):
    if fn.endswith(".3mf"):
        with zipfile.ZipFile(fn) as z:
            name = next(n for n in z.namelist() if n.endswith(".gcode"))
            return z.read(name).decode("utf-8", "replace").splitlines()
    return open(fn, encoding="utf-8", errors="replace").read().splitlines()


def schichten(lines):
    L, cur = {}, None
    typ, x, y, F, fan = "", 0.0, 0.0, 0.0, 0
    for ln in lines:
        if ln.startswith("; Z_HEIGHT:") or ln.startswith(";Z:"):
            z = float(ln.split(":")[1]); cur = L.setdefault(z, dict(t=0.0, owF=set(), fan=set(), arten={}))
        elif ln.startswith(("; FEATURE:", ";TYPE:")):
            typ = ln.split(":", 1)[1].strip()
        elif ln.startswith("M106"):
            m = re.search(r"S(\d+)", ln); fan = int(m.group(1)) if m else fan
        elif ln.startswith(("G1", "G0")) and cur is not None:
            d = dict(re.findall(r"([XYEF])(-?[\d.]+)", ln))
            if "F" in d: F = float(d["F"])
            nx, ny = float(d.get("X", x)), float(d.get("Y", y))
            dist = math.hypot(nx - x, ny - y)
            if F > 0 and dist > 0: cur["t"] += dist / (F / 60)
            if "E" in d and float(d["E"]) > 0 and dist > 0:
                cur["arten"][typ] = cur["arten"].get(typ, 0) + dist; cur["fan"].add(fan)
                if typ == "Outer wall": cur["owF"].add(F / 60)
            x, y = nx, ny
    return L


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("gcode")
    ap.add_argument("--z0", type=float, default=-1e9)
    ap.add_argument("--z1", type=float, default=1e9)
    ap.add_argument("--sprung", type=float, default=3.0)
    a = ap.parse_args(argv)
    L = schichten(lade(a.gcode)); prev = None
    for z in sorted(L):
        c = L[z]
        if a.z0 <= z <= a.z1:
            mark = "  <-- Sprung" if prev and c["t"] > 0 and max(c["t"], prev) / max(min(c["t"], prev), 1e-9) > a.sprung else ""
            print("z %6.2f  %6.1f s  Außenwand %s mm/s  Lüfter %s  %s%s" % (
                z, c["t"], "/".join("%.0f" % v for v in sorted(c["owF"])) or "-", "/".join(map(str, sorted(c["fan"]))) or "-",
                ", ".join("%s %d" % (k, v) for k, v in sorted(c["arten"].items(), key=lambda kv: -kv[1])), mark))
        prev = c["t"]
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
