"""cadconf - optionale Konfigurationsdatei fuer cad (reines Python).

Liest ~/.config/cad/env (Pfad ueberschreibbar mit CAD_CONFIG): Zeilen KEY=VALUE, Kommentare mit #. Setzt nur Variablen,
die noch nicht in der Umgebung stehen. Wird beim Import ausgefuehrt; Beispiel siehe README (Abschnitt Konfiguration)."""
import os


def load():
    p = os.environ.get("CAD_CONFIG") or os.path.join(os.path.expanduser("~"), ".config", "cad", "env")
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), os.path.expanduser(v.strip().strip('"').strip("'")))
    except OSError:
        pass


load()
