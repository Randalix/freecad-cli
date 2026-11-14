"""Test: Ziel komplett von einem anderen Teil umschlossen -> keine Achsansicht frei -> Kachel automatisch xray.
Aufruf: cad run -k bench/focus_enclosed.py && cad look --focus Kern -o /mnt/raid1/3d_print/cad_out/bench_focus_enclosed.png"""
import Part, FreeCAD as App
doc = App.newDocument("Enc")
hull = Part.makeBox(100, 100, 100)
core = Part.makeBox(20, 20, 20, App.Vector(40, 40, 40))
for n, s in (("Huelle", hull), ("Kern", core)):
    o = doc.addObject("Part::Feature", n); o.Shape = s
doc.recompute()
cad.report(Huelle=hull, Kern=core)
cad.focus("Kern", (50, 50, 50), 60, view="front")
