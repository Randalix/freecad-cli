"""CPU-Zeit alt (Sicherung cadgeom.py.bak-20261113-p4) gegen neu fuer find_overhangs (cad run bench/compare_bridge_old_new.py)."""
import time, types, cadgeom
old = types.ModuleType("cadgeom_old"); exec(compile(open("/mnt/raid1/3d_print/tools/freecad/cadgeom.py.bak-20261113-p4").read(), "cadgeom_old", "exec"), old.__dict__)
f = "/mnt/raid1/3d_print/tuecher_bin/gridfinity_tuecher.stl"
sc = cadgeom.get_scene({"file": f})
for name, m in (("alt", old), ("neu", cadgeom)):
    t = time.process_time(); hs = m.find_overhangs(sc); dt = time.process_time() - t
    print(name, "%.2fs CPU" % dt, [(h["kind"], h["value"]) for h in hs])
sc2 = cadgeom.get_scene({"file": "/mnt/raid1/3d_print/kotbeutel_bin/gridfinity_bin.stl"})
for name, m in (("alt", old), ("neu", cadgeom)):
    t = time.process_time(); hs = m.find_overhangs(sc2); dt = time.process_time() - t
    print("bin", name, "%.2fs CPU" % dt, [(h["kind"], h["value"]) for h in hs])
