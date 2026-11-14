"""linienwand - erwartete Wandspuren fuer eine Wandstaerke (OrcaSlicer 2.4.2, Wandgenerator classic).

Gebaut 14.11.2026 fuer `cad check --line-w`. Kalibriert an Slicer-Schaetzungen (nicht gedruckt) im Versuch
/mnt/raid1/3d_print/experimente/wand_gapfill/ (Testbox 40x40x30, Wand 0,70-3,60 mm, 0,1- und 0,02-mm-Stufen,
Linien 0,42/0,45 und 0,6, Schichthoehe 0,2, precise_outer_wall=1, Wandlinien 3): Gap-Fill ja/nein stimmte in 139 von
141 Faellen, die 2 Abweichungen liegen auf der Grenze (Rest 0,02 bzw. 0,06 mm, dort nur 0,15 m Gap-Fill in 1 Schicht).

Modell (aus den Spurlagen im G-Code-Schnitt abgeleitet):
  * classic legt die Wandlinien von beiden Seiten: k Schleifen -> 2k Spuren, der Rest in der Mitte wird Gap-Fill
    (bzw. Infill, wenn alle Wandlinien verbraucht sind und der Rest breit ist).
  * Kante der k-ten Spur ab Wandflaeche: E1 = w_aussen, E2 = w_aussen + w_innen (precise_outer_wall: Aussen- und
    erste Innenspur liegen auf voller Nennbreite nebeneinander), Ek = E2 + (k-2)*s mit Spurabstand
    s = w_innen - h*(1 - pi/4) (Slic3r/Orca-Abstand; 0,6 -> 0,557, 0,45 -> 0,407).
  * Schleife k (k>=2) entsteht, wenn T >= 2*(Ek - w_innen/2) + 0,55*w_innen (Mindestbreite der Restflaeche; gemessen
    0,23-0,25 mm bei 0,45 und 0,32-0,34 mm bei 0,6).
  * Rest = T - 2*Ek. Rest <= 0: Spuren beruehren/ueberlappen sich, kein Gap-Fill. Rest > 0,015 mm (k=1: > 0,07 mm):
    Gap-Fill ueber die ganze Wandhoehe.
"""
import math

D_FAK = 0.55     # Mindestbreite fuer eine weitere Schleife, Anteil von w_innen (kalibriert)
TOL = 0.015      # Rest bis hierhin: noch kein Gap-Fill (k >= 2); Grenze gemessen zwischen 0,00 und 0,02
TOL1 = 0.07      # dto. fuer k = 1 (nur die beiden Aussenspuren)
INFILL_FAK = 1.3 # Rest > INFILL_FAK * w_innen bei verbrauchten Wandlinien -> Infill statt Gap-Fill (1 Messpunkt, grob)


def spacing(w, h=0.2):
    return w - h * (1 - math.pi / 4)


def parse_lw(spec):
    """'0.6' -> (0.6, 0.6); '0.42/0.45' -> (0.42, 0.45); 'std' -> Orca-Profil 0.42/0.45."""
    spec = spec.strip().lower().replace(",", ".")
    if spec in ("std", "standard"):
        return 0.42, 0.45
    if "/" in spec:
        a, b = spec.split("/", 1)
        return float(a), float(b)
    return float(spec), float(spec)


def edge(k, wo, wi, h=0.2):
    return wo if k == 1 else wo + wi + (k - 2) * spacing(wi, h)


def spuren(T, wo, wi, h=0.2, loops=2):
    """Erwartung fuer Wandstaerke T: dict(spuren, rest, gapfill, urteil, text)."""
    k = 1
    for kk in range(2, loops + 1):
        if T >= 2 * (edge(kk, wo, wi, h) - wi / 2) + D_FAK * wi - 1e-9:
            k = kk
    rest = T - 2 * edge(k, wo, wi, h)
    tol = TOL1 if k == 1 else TOL
    if T < 1.4 * wo and k == 1 and rest <= tol:
        n = 1 if T < 1.4 * wo - 1e-9 else 2
    else:
        n = 2 * k
    if rest <= tol:
        urteil, text = "ok", "%d Spuren, kein Gap-Fill" % n + (" (Überlappung %.2f mm)" % -rest if rest < -0.005 else "")
    elif k == loops and rest > INFILL_FAK * wi:
        urteil, text = "Hinweis", "%d Spuren + Infill in der Mitte (%.2f mm; Wandlinien %d erschöpft)" % (n, rest, loops)
    else:
        urteil, text = "Hinweis", "%d Spuren + Gap-Fill %.2f mm in der Mitte" % (n, rest)
    return {"spuren": n, "rest": round(rest, 3), "gapfill": rest > tol, "urteil": urteil, "text": text}


def fenster(wo, wi, h=0.2, loops=2, t_max=4.0):
    """Gap-freie Wandstaerken-Bereiche [(von, bis, spuren)] (laut Modell)."""
    out = []
    for k in range(1, loops + 1):
        lo = 0.0 if k == 1 else 2 * (edge(k, wo, wi, h) - wi / 2) + D_FAK * wi
        hi = 2 * edge(k, wo, wi, h) + (TOL1 if k == 1 else TOL)
        if lo < t_max:
            out.append((round(lo, 2), round(min(hi, t_max), 2), 2 * k))
    return out


def naechste_saubere(T, wo, wi, h=0.2, loops=2):
    """Naechste gap-freie Wandstaerke (auf 0,05 mm gerundet, mit Abstand 0,02/0,03 mm zu den Fenstergrenzen)."""
    best = None
    for lo, hi, n in fenster(wo, wi, h, loops):
        lo = max(lo, 1.4 * wo if n == 2 else lo)
        a, b = math.ceil((lo + 0.02) * 20 - 1e-6) / 20, math.floor((hi - 0.03) * 20 + 1e-6) / 20   # Abstand zu den Grenzen
        if a > b:
            continue
        c = min(max(T, a), b)
        c = round(c * 20) / 20
        if best is None or abs(c - T) < abs(best - T):
            best = c
    return best


if __name__ == "__main__":
    import sys
    lw = parse_lw(sys.argv[1] if len(sys.argv) > 1 else "0.6")
    for t in [float(x) for x in sys.argv[2:]] or [1.6, 1.8, 2.4]:
        print(t, spuren(t, *lw), naechste_saubere(t, *lw))
    print(fenster(*lw, loops=3))
