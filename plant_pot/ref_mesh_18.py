# Referenz: alte Houdini-Exporte square_pot_18 (Topf) + Reservoir als Mesh laden und ansehen
import Mesh, Part
G = "/mnt/raid1/3d_print/plant_pot/geo/"
doc = App.ActiveDocument or App.newDocument("ref")
for name, fn, dx in (("Topf", "square_pot_18.obj", 0), ("Reservoir", "square_pot_reservoir_18.obj", 200)):
    m = Mesh.Mesh(G + fn)
    m.translate(dx, 0, 0)
    o = doc.addObject("Mesh::Feature", name); o.Mesh = m
    print(name, "Dreiecke", m.CountFacets, "solid", m.isSolid(), "Volumen %.0f" % m.Volume, "BBox", m.BoundBox)
doc.recompute()
