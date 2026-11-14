import Part, FreeCAD as App
a = Part.makeBox(20, 20, 20)
b = Part.makeBox(10, 10, 10, App.Vector(40, 0, 0))
doc = App.newDocument("T")
oa = doc.addObject("Part::Feature", "A"); oa.Shape = a
ob = doc.addObject("Part::Feature", "B"); ob.Shape = b
doc.recompute()
