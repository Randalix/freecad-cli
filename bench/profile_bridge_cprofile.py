import time, cProfile, pstats, io, cadgeom, numpy as np
sc = cadgeom.get_scene({})
orig = cadgeom._bridge_span
big=[]
def w(sc_, idx):
    a=float(sc_.area[idx].sum())
    if a>100000:
        pr=cProfile.Profile(); pr.enable(); r=orig(sc_, idx); pr.disable()
        s=io.StringIO(); pstats.Stats(pr,stream=s).sort_stats("cumtime").print_stats(8); print(s.getvalue()[:2500]); return r
    return orig(sc_, idx)
cadgeom._bridge_span=w
cadgeom.find_overhangs(sc)
cadgeom._bridge_span=orig
