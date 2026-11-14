import time, itertools, FreeCAD as App
doc = App.ActiveDocument
objs = [o for o in doc.Objects if hasattr(o, "Shape") and o.Shape.Solids]
print("Objekte", len(objs))
t = time.time(); hits = []; n = 0
for a, b in itertools.combinations(objs, 2):
    n += 1
    if not a.Shape.BoundBox.intersect(b.Shape.BoundBox): continue
    v = a.Shape.common(b.Shape).Volume
    if v > 1e-3: hits.append((a.Name, b.Name, round(v, 1)))
print("Paare %d, mit Boxueberlappung geprueft in %.2fs, Durchdringungen: %d" % (n, time.time() - t, len(hits)))
for h in hits[:8]: print(" ", h)
