# Referenz: Houdini-Topf mit Druckstützen (write_3d_print6) ansehen
import Mesh
d = "/mnt/raid1/3d_print/plant_pot/v001_2026-11-14_nachbau_cubepot_aus_houdini_referenz_exp/modell/"
doc = App.ActiveDocument or App.newDocument("ref")
m = Mesh.Mesh(d + "houdini_pot_mit_support.stl")
o = doc.addObject("Mesh::Feature", "TopfSupport"); o.Mesh = m
segs = m.getSeparateComponents()
print("Komponenten", len(segs))
import collections
for s in sorted(segs, key=lambda s: -s.CountFacets)[:6]:
    print(s.CountFacets, s.BoundBox)
doc.recompute()
