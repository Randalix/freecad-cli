# freecad-cli — `cad`: FreeCAD per Skript, ohne GUI

`cad` lässt Agenten (und Menschen) FreeCAD-Modelle per Python-Skript bauen, messen, ansehen und prüfen, ohne GUI und ohne MCP-Server. Ein persistenter headless FreeCAD-Worker hält das Dokument im Speicher, ein dünner Client (`cad`) spricht über einen Unix-Socket mit ihm. Bilder rendert Blender headless: technische Ansicht mit Lineal oder ein „schöner" Stil mit Materialien, Bemaßung, Schnitt, Explosion und GLB-Export. Ein Skill ([`skill/SKILL.md`](skill/SKILL.md)) bringt Claude Code die Arbeitsweise bei.

```
cad run model.py --report              # Skript ausführen, Messwerte der Objekte
cad look                               # Sheet iso/front/right/top mit mm-Lineal
cad look --style schoen --dims         # Bild für Menschen: Material, Perspektive, Bemaßung
cad look --section x=40 --focus all    # Schnitt, kritische Stellen heranzoomen
cad hotspots / cad check --line-w std  # kritische Stellen, Druckbarkeit, Gap-Fill
cad projekt demo && cad version "v1"   # Projekt mit versionierten Ordnern
```
Alle Befehle: `cad --help`, `cad look -h`.

## Voraussetzungen
| | getestet mit | wofür |
|---|---|---|
| Linux mit systemd (User-Instanz) | | Worker-Dienst; ohne systemd Worker von Hand starten |
| Python 3 | 3.9+ (nur Standardbibliothek) | Client `cad`, `cadrun`, `cadprojekt.py` |
| FreeCAD | 1.1.4 (AppImage genügt) | Worker: `freecad -c cad_worker.py` (headless) |
| Blender | 5.1.1 | Render, Schnitte, Explosion, GLB; das Python von Blender braucht `numpy` und `Pillow` |

Optional: `ssh` (nur wenn Projektordner auf einer Netzfreigabe liegen, auf der Symlinks nicht möglich sind).

## Installation
1. **Klonen** an einen beliebigen Ort:
   ```
   git clone <repo-url> ~/tools/freecad-cli
   cd ~/tools/freecad-cli
   ```
2. **FreeCAD und Blender** bereitstellen (siehe Voraussetzungen). FreeCAD muss headless laufen: `freecad -c </dev/null` darf nicht auf ein Display warten; im Skript nie `PySide`/`pivy` importieren. Blender wird mit `env -u LD_LIBRARY_PATH -u DISPLAY` gestartet (macht `cad` selbst); liegt es nicht im `PATH`, `CAD_BLENDER=/pfad/zu/blender` setzen.
3. **Konfigurieren:** `cad.env.example` nach `~/.config/cad/env` kopieren und anpassen (Zeilen `KEY=VALUE`; Umgebungsvariablen haben Vorrang, Pfad der Datei über `CAD_CONFIG`). Mindestens:
   ```
   CAD_DIR=~/tools/freecad-cli            # Ort dieses Repos (Worker findet seine Module)
   CAD_PROJEKT_ROOT=~/cad-projekte        # Wurzel der Projekte  <root>/<projekt>/vNNN_…/
   CAD_OUT=~/cad-projekte/cad_out         # Ausgaben ohne aktives Projekt
   CAD_BLENDER=/opt/blender/blender       # nur falls nicht im PATH
   ```
   (`~` am Wertanfang wird expandiert.)
4. **`cad` in den PATH:**
   ```
   ln -s "$CAD_DIR/cad" ~/bin/cad && ln -s "$CAD_DIR/cadrun" ~/bin/cadrun
   ```
5. **Worker-Dienst** installieren: `systemd/cadworker.service` nach `~/.config/systemd/user/` kopieren, `ExecStart` (Pfad zu FreeCAD und zu `cad_worker.py`) und `Environment=` (die `CAD_*`-Variablen) anpassen, dann `systemctl --user daemon-reload`. `cad run …` startet den Dienst bei Bedarf; er beendet sich nach 15 Minuten ohne Anfrage (`CAD_IDLE_S`).
6. **Skill für Claude Code** (optional): `skill/SKILL.md` nach `<projekt>/.claude/skills/cad/SKILL.md` oder `~/.claude/skills/cad/SKILL.md` kopieren. Der Skill beschreibt die Schleife bauen → messen → ansehen → prüfen und die Regel, dass zur Abnahme immer das gerenderte Bild vorgelegt wird.
7. **Prüfen:**
   ```
   cad worker status
   python3 bench/run_bench.py --quick     # Regression/Zeit, erwartet: alle PASS
   cad look pfad/zum/modell.FCStd          # Blender-Render nach $CAD_OUT
   ```

## Konfiguration
| Variable | Bedeutung | Standard im Code |
|---|---|---|
| `CAD_DIR` | Ort dieses Repos | Verzeichnis des Skripts bzw. `/mnt/raid1/3d_print/tools/freecad` (Worker) |
| `CAD_PROJEKT_ROOT` | Wurzel der Projektordner | `/mnt/raid1/3d_print` |
| `CAD_OUT` | Ausgabe ohne aktives Projekt | `/mnt/raid1/3d_print/cad_out` |
| `CAD_STATE` | Zustandsdatei des aktiven Projekts (pro Sitzung setzbar) | `<CAD_DIR>/.projekt_state.json` |
| `CAD_BLENDER` | Blender-Programm | `blender` im `PATH` |
| `CAD_SYMLINK_HOST` | ssh-Ziel (`user@host`), um Symlinks auf einer Netzfreigabe ohne Symlink-Unterstützung anzulegen | leer (aus) |
| `CAD_REMOTE_PATH_MAP` | `<lokaler Präfix>=<Präfix auf dem Server>` für diese ssh-Befehle | leer |
| `CAD_NO_OUTPUT_DIR` | Ordner, in den `cad` nie Bilder schreibt (z. B. ein Notizen-Vault) | leer |
| `CAD_CONFIG` | Pfad der Konfigurationsdatei | `~/.config/cad/env` |
| `CAD_IDLE_S`, `CAD_REQ_TIMEOUT` | Leerlauf bis Worker-Stopp (900 s), Anfrage-Timeout (5 s) | |
| `CAD_RENDER_THREADS`, `CAD_RENDER_SLOTS`, `CAD_TMP` | Blender-Threads (4), parallele Renderjobs (3), Temp-Ordner | |

Hinweis: Einige Standardwerte im Code zeigen noch auf das Layout des Autors (`/mnt/raid1/3d_print/…` als Projektwurzel); sie lassen sich mit den Variablen oben überschreiben. Die Beispielmodelle `gridfinity_*.py` und `cad_selftest.py` nennen Pfade des Autors und müssen bei fremder Ablage angepasst werden.

## Projektstruktur (`cad projekt`, `cad version`)
```
<CAD_PROJEKT_ROOT>/<projekt>/
  PROJEKT.md  CHANGELOG.md
  aktuell -> vNNN_<datum>_<label>
  vNNN_<datum>_<label>/{modell,slice,vorschau,messung}/   eine Version = ein Stand
  experimente/  _archiv/
```
`cad version "Label"` legt die nächste Version an; `cad look`, `--report` und `--glb` schreiben automatisch in die aktive Version (`cad.outdir("modell")` im Skript). `cad freigabe "Notiz"` sperrt eine Version gegen weiteres Schreiben.

## Aufbau des Repos
| Pfad | Inhalt |
|---|---|
| `cad`, `cadrun` | Client (CLI) |
| `cad_worker.py` | Worker im FreeCAD (Unix-Socket) |
| `cadlib.py`, `cadgeom.py`, `linienwand.py` | Skript-API (`cad.report`, `cad.focus`, `cad.material`, `cad.outdir`), Geometrie/Hotspots, Gap-Fill-Rechner |
| `cad_render.py`, `cad_schoen.py` | Blender-Renderer (technisch / schön, GLB) |
| `cadprojekt.py` | Projektstruktur |
| `materials.json` | eigene Materialien für den Schön-Stil (`cad materials …`) |
| `gridfinity_*.py` | Beispielmodelle (Gridfinity-Behälter) |
| `bench/`, `cad_selftest.py` | Regression, Zeitmessung, Referenzen |
| `research/` | Recherche-Notizen (CLI statt MCP, Snap-Fit) |
| `cadconf.py`, `cad.env.example` | Konfigurationsdatei `~/.config/cad/env` |
| `skill/SKILL.md` | Skill für Claude Code |
| `systemd/cadworker.service` | Beispiel-Unit für den Worker |

## Entwickeln
- Nicht im Repo (`.gitignore`): `*.bak-*`, `__pycache__`, Logs, `.projekt_state.json`, `*.FCBak`. Modelle, Bilder und Slices gehören in die Projektordner, nicht hierher.
- Vor Änderungen am Renderer oder an der Geometrie `python3 bench/run_bench.py` laufen lassen (erwartet: alle PASS).

## Lizenz
MIT, siehe [LICENSE](LICENSE).
