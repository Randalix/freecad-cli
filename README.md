# freecad-cli — `cad`: scripted FreeCAD, no GUI

`cad` lets agents (and humans) build, measure, view and check FreeCAD models from Python scripts, with no GUI and no MCP server. A persistent headless FreeCAD worker keeps the document in memory; a thin client (`cad`) talks to it over a Unix socket. Images are rendered headless in Blender: a technical view with a millimetre ruler, or a "pretty" style (`schoen`) with materials, dimensions, sections, exploded views and GLB export. A skill ([`skill/SKILL.md`](skill/SKILL.md)) teaches Claude Code the workflow.

```
cad run model.py --report              # run a script, print measurements of the objects
cad look                               # sheet iso/front/right/top with mm ruler
cad look --style schoen --dims         # image for humans: materials, perspective, dimensions
cad look --section x=40 --focus all    # section view, zoom in on critical spots
cad hotspots / cad check --line-w std  # critical spots, printability, gap fill
cad projekt demo && cad version "v1"   # project with versioned folders
```
All commands: `cad --help`, `cad look -h`.

> Note: the code, comments, commit messages and some command names (`projekt`, `freigabe`, `schoen`, `aktuell`, …) are in German. The commands are listed here as they are typed.

## Requirements
| | tested with | used for |
|---|---|---|
| Linux with systemd (user instance) | | worker service; without systemd, start the worker by hand |
| Python 3 | 3.9+ (standard library only) | client `cad`, `cadrun`, `cadprojekt.py` |
| FreeCAD | 1.1.4 (AppImage is fine) | worker: `freecad -c cad_worker.py` (headless) |
| Blender | 5.1.1 | rendering, sections, exploded views, GLB; Blender's Python needs `numpy` and `Pillow` |

Optional: `ssh` (only needed when project folders live on a network share that does not support symlinks).

## Installation
1. **Clone** anywhere:
   ```
   git clone https://github.com/Randalix/freecad-cli ~/tools/freecad-cli
   cd ~/tools/freecad-cli
   ```
2. **Provide FreeCAD and Blender** (see requirements). FreeCAD must run headless: `freecad -c </dev/null` must not wait for a display; never import `PySide`/`pivy` in model scripts. Blender is started with `env -u LD_LIBRARY_PATH -u DISPLAY` (`cad` does this itself); if it is not on `PATH`, set `CAD_BLENDER=/path/to/blender`.
3. **Configure:** copy `cad.env.example` to `~/.config/cad/env` and adjust it (`KEY=VALUE` lines; environment variables take precedence, the file location can be changed with `CAD_CONFIG`). At minimum:
   ```
   CAD_DIR=~/tools/freecad-cli            # location of this repo (the worker loads its modules from here)
   CAD_PROJEKT_ROOT=~/cad-projects        # project root  <root>/<project>/vNNN_…/
   CAD_OUT=~/cad-projects/cad_out         # output when no project is active
   CAD_BLENDER=/opt/blender/blender       # only if not on PATH
   ```
   (A leading `~` in a value is expanded.)
4. **Put `cad` on your PATH:**
   ```
   ln -s "$CAD_DIR/cad" ~/bin/cad && ln -s "$CAD_DIR/cadrun" ~/bin/cadrun
   ```
5. **Install the worker service:** copy `systemd/cadworker.service` to `~/.config/systemd/user/`, adjust `ExecStart` (paths to FreeCAD and `cad_worker.py`) and `Environment=` (the `CAD_*` variables), then run `systemctl --user daemon-reload`. `cad run …` starts the service on demand; it exits after 15 minutes without requests (`CAD_IDLE_S`).
6. **Claude Code skill** (optional): copy `skill/SKILL.md` to `<project>/.claude/skills/cad/SKILL.md` or `~/.claude/skills/cad/SKILL.md`. The skill describes the loop build → measure → look → check, and the rule that a rendered image is always presented for sign-off.
7. **Verify:**
   ```
   cad worker status
   python3 bench/run_bench.py --quick     # regression/timing, expected: all PASS
   cad look path/to/model.FCStd           # Blender render into $CAD_OUT
   ```

## Configuration
| Variable | Meaning | Default in code |
|---|---|---|
| `CAD_DIR` | location of this repo | directory of the script, or `/mnt/raid1/3d_print/tools/freecad` (worker) |
| `CAD_PROJEKT_ROOT` | root of the project folders | `/mnt/raid1/3d_print` |
| `CAD_OUT` | output when no project is active | `/mnt/raid1/3d_print/cad_out` |
| `CAD_STATE` | state file of the active project (can be set per session) | `<CAD_DIR>/.projekt_state.json` |
| `CAD_BLENDER` | Blender executable | `blender` on `PATH` |
| `CAD_SYMLINK_HOST` | ssh target (`user@host`) used to create symlinks on a network share without symlink support | empty (off) |
| `CAD_REMOTE_PATH_MAP` | `<local prefix>=<prefix on the server>` for those ssh commands | empty |
| `CAD_NO_OUTPUT_DIR` | folder `cad` never writes images into (e.g. a notes vault) | empty |
| `CAD_CONFIG` | path of the config file | `~/.config/cad/env` |
| `CAD_IDLE_S`, `CAD_REQ_TIMEOUT` | idle time until the worker stops (900 s), request timeout (5 s) | |
| `CAD_RENDER_THREADS`, `CAD_RENDER_SLOTS`, `CAD_TMP` | Blender threads (4), parallel render jobs (3), temp folder | |

Some defaults in the code still point to the author's layout (`/mnt/raid1/3d_print/…` as project root); override them with the variables above. The example models `gridfinity_*.py`, `plant_pot/` and `cad_selftest.py` reference the author's paths and need adjusting if the repo lives elsewhere.

## Project layout (`cad projekt`, `cad version`)
```
<CAD_PROJEKT_ROOT>/<project>/
  PROJEKT.md  CHANGELOG.md
  aktuell -> vNNN_<date>_<label>                            "aktuell" = current version
  vNNN_<date>_<label>/{modell,slice,vorschau,messung}/      model, slice, preview, measurement; one version = one state
  experimente/  _archiv/                                     experiments, archive
```
`cad version "Label"` creates the next version; `cad look`, `--report` and `--glb` write into the active version automatically (`cad.outdir("modell")` inside a script). `cad freigabe "note"` releases a version and locks it against further writes.

## Repository contents
| Path | Contents |
|---|---|
| `cad`, `cadrun` | client (CLI) |
| `cad_worker.py` | worker running inside FreeCAD (Unix socket) |
| `cadlib.py`, `cadgeom.py`, `linienwand.py` | script API (`cad.report`, `cad.focus`, `cad.material`, `cad.outdir`), geometry/hotspots, gap-fill calculator for line widths |
| `cad_render.py`, `cad_schoen.py` | Blender renderers (technical / pretty, GLB) |
| `cadprojekt.py` | project structure |
| `materials.json` | custom materials for the pretty style (`cad materials …`) |
| `gridfinity_*.py` | example models (Gridfinity bins) |
| `plant_pot/` | square self-watering pot (pot + water reservoir + wick basket): fully parametric model `plant_pot.py` with built-in safety checks, plus check scripts (twist travel, pour position, clearance, seating) |
| `stl_facetten.py` | check for visible facets in STLs (curves meshed too coarsely); CLI and function, no numpy |
| `gcode_schichten.py` | G-code analysis per layer: layer time, outer-wall feed rate, fan and path types; flags time jumps |
| `bench/`, `cad_selftest.py` | regression, timing, references |
| `research/` | research notes (CLI instead of MCP, snap fits) |
| `cadconf.py`, `cad.env.example` | config file `~/.config/cad/env` |
| `skill/SKILL.md` | skill for Claude Code |
| `systemd/cadworker.service` | example unit for the worker |

### Example: parametric plant pot
Every parameter of `plant_pot/plant_pot.py` can be overridden from outside without editing the file:
```
cad run -c 'SIZE_X=150; HEIGHT=120; exec(open("/path/to/freecad-cli/plant_pot/plant_pot.py").read())' --report
```
This takes about 30 s and prints volumes, water capacity and the results of the built-in checks. It writes STLs (pot, reservoir, wick basket, test rings, named after the size, e.g. `pot_150x150x120.stl`) and a slicer JSON into the `modell/` folder of the active project version, or into `$CAD_OUT` when no project is active. With `--report`, a run via `-c` also writes `messung/report_code.json`.

## Development
- Not in the repo (`.gitignore`): `*.bak-*`, `__pycache__`, logs, `.projekt_state.json`, `*.FCBak`. Models, images and slices belong in project folders, not here.
- Before changing the renderer or geometry code, run `python3 bench/run_bench.py` (expected: all PASS).

## License
MIT, see [LICENSE](LICENSE).
