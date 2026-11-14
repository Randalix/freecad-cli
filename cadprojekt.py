"""cadprojekt - Projektstruktur mit Versionen fuer CAD-/3D-Druck-Projekte (reines Python, ohne FreeCAD).

Struktur:
  <CAD_PROJEKT_ROOT>/<projekt>/
    PROJEKT.md, CHANGELOG.md, aktuell -> vNNN_<datum>_<label>
    vNNN_YYYY-MM-DD_<label>/{modell,slice,vorschau,messung}/ [freigabe.md]
    experimente/  _archiv/
Zustand (aktives Projekt/Version): <Werkzeugordner>/.projekt_state.json (atomar geschrieben; anderer Ort: CAD_STATE=<datei>).
Benutzt von `cad` (projekt/version/freigabe, Ausgabepfade) und cadlib (`cad.outdir()` im Skript).
Ohne aktives Projekt bleibt cad_out der Fallback (mit Warnzeile)."""
import datetime, errno, json, os, re, shlex, subprocess, tempfile

import cadconf  # noqa: F401  (laedt ~/.config/cad/env)

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.environ.get("CAD_PROJEKT_ROOT", "/mnt/raid1/3d_print")
FALLBACK = os.environ.get("CAD_OUT", "/mnt/raid1/3d_print/cad_out")
KINDS = ("modell", "slice", "vorschau", "messung")
RESERVED = {"tools", "cad_out", "experimente", "list", "show", "aus", "_archiv"}
VER_RE = re.compile(r"^v(\d{3})_(\d{4}-\d{2}-\d{2})_(.+)$")
NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
WARN_FALLBACK = "kein aktives Projekt (cad projekt <name>)"
# Liegen die Projekte auf einer Netzfreigabe (z. B. CIFS), lassen sich dort oft keine Symlinks anlegen (EOPNOTSUPP), und
# serverseitige Symlinks sehen auf dem Client wie normale Dateien/Ordner aus. Dann legt cad Symlinks per ssh auf dem
# Dateiserver an: CAD_SYMLINK_HOST=<user@host>, CAD_REMOTE_PATH_MAP="<lokaler Praefix>=<Praefix auf dem Server>".
REMOTE = os.environ.get("CAD_SYMLINK_HOST", "")
REMOTE_MAP = os.environ.get("CAD_REMOTE_PATH_MAP", "")


class Fehler(Exception):
    pass


class Gesperrt(Fehler):
    pass


def state_file():
    return os.environ.get("CAD_STATE") or os.path.join(HERE, ".projekt_state.json")


def load_state():
    try:
        with open(state_file()) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(d):
    p = state_file()
    d = dict(d, geaendert=datetime.datetime.now().isoformat(timespec="seconds"))
    fd, tmp = tempfile.mkstemp(prefix=".projekt_state.", dir=os.path.dirname(p))
    with os.fdopen(fd, "w") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.chmod(tmp, 0o666)
    os.replace(tmp, p)


def projekt_dir(name):
    return os.path.join(ROOT, name)


def check_name(name):
    if not name or not NAME_RE.match(name) or name in RESERVED or "/" in name:
        raise Fehler("ungueltiger Projektname %r (Buchstaben, Ziffern, _ . -; nicht %s)" % (name, ", ".join(sorted(RESERVED))))


def slug(label):
    s = label.strip().lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), (",", "")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9.]+", "_", s).strip("_.")
    return (s or "version")[:40].rstrip("_")


def versions(pdir):
    """Versionsordner eines Projekts, sortiert nach Nummer: [(nr, name)]."""
    out = []
    try:
        for n in os.listdir(pdir):
            m = VER_RE.match(n)
            if m and os.path.isdir(os.path.join(pdir, n)) and not os.path.islink(os.path.join(pdir, n)):
                out.append((int(m.group(1)), n))
    except OSError:
        pass
    return sorted(out)


def find_version(pdir, ref):
    """ref: 'v002', '2', 'v002_2026-...' -> Ordnername."""
    r = str(ref).strip().lower().lstrip("v")
    for nr, n in versions(pdir):
        if n == ref or (r.isdigit() and int(r) == nr):
            return n
    raise Fehler("Version %r gibt es in %s nicht (vorhanden: %s)" % (ref, pdir, ", ".join(n for _, n in versions(pdir)) or "keine"))


def active():
    """(projekt, version, versionspfad) aus dem Zustand; fehlende Teile = None."""
    st = load_state()
    p, v = st.get("projekt"), st.get("version")
    if not p or not os.path.isdir(projekt_dir(p)):
        return None, None, None
    if v and os.path.isdir(os.path.join(projekt_dir(p), v)):
        return p, v, os.path.join(projekt_dir(p), v)
    return p, None, None


def is_frozen(vdir):
    return bool(vdir) and os.path.isfile(os.path.join(vdir, "freigabe.md"))


def version_of(path):
    """Versionsordner (<ROOT>/<projekt>/vNNN_...), in dem `path` liegt, sonst None (folgt Symlinks)."""
    for x in (os.path.abspath(path), os.path.realpath(path)):
        for root in {os.path.abspath(ROOT), os.path.realpath(ROOT)}:
            if not x.startswith(root + os.sep):
                continue
            parts = x[len(root) + 1:].split(os.sep)
            if len(parts) >= 3 and parts[1] == "aktuell":       # Symlink auf dem Dateiserver, hier nicht aufloesbar
                t = read_symlink(os.path.join(root, parts[0], "aktuell"))
                if t and VER_RE.match(os.path.basename(t.rstrip("/"))):
                    return os.path.join(root, parts[0], os.path.basename(t.rstrip("/")))
            if len(parts) >= 2 and VER_RE.match(parts[1]):
                return os.path.join(root, parts[0], parts[1])
    return None


def check_write(path):
    """Schreiben nach `path` pruefen: Fehler, wenn die Version freigegeben ist; Hinweistext, wenn eine Datei
    einer Version ueberschrieben wuerde (sonst None)."""
    v = version_of(path)
    if not v:
        return None
    if is_frozen(v):
        raise Gesperrt("%s ist freigegeben (freigabe.md) und wird nicht mehr veraendert - neue Version anlegen: cad version \"<Label>\"" % os.path.basename(v))
    if os.path.lexists(path):
        return "ueberschreibt %s in %s (neue Aenderung = cad version \"<Label>\")" % (os.path.relpath(path, v), os.path.basename(v))
    return None


def outdir(kind, create=True):
    """Ausgabeordner der aktiven Version fuer kind (modell|slice|vorschau|messung).
    Rueckgabe (pfad, warnung): ohne aktives Projekt/Version -> (cad_out, Warnzeile). Gesperrt bei freigabe.md."""
    if kind not in KINDS:
        raise Fehler("outdir: %r ist keine Ablage (%s)" % (kind, "|".join(KINDS)))
    p, v, vdir = active()
    if not p:
        return FALLBACK, WARN_FALLBACK + " - Ausgabe nach " + FALLBACK
    if not vdir:
        return FALLBACK, "Projekt %s hat keine aktive Version (cad version \"<Label>\") - Ausgabe nach %s" % (p, FALLBACK)
    if is_frozen(vdir):
        raise Gesperrt("%s/%s ist freigegeben (freigabe.md) - neue Version anlegen: cad version \"<Label>\"" % (p, v))
    d = os.path.join(vdir, kind)
    if create:
        os.makedirs(d, exist_ok=True)
    return d, None


# ------------------------------------------------------------------------------------------- Befehle
PROJEKT_TMPL = """# {name}

Zweck: (kurz, was das Teil tun soll)
Vorgaben: (Maße, Material, Grenzen; nur Bestätigtes)
Entscheidungen: (Datum, wer, was)
Quelle: (Link oder Notiz)

Neue Änderung = `cad version "<Label>"`.
Angelegt: {datum}
"""
CHANGELOG_TMPL = """# CHANGELOG {name}

Eine Zeile je Version: was hat sich geändert, warum. Neueste unten.

"""


def ensure_projekt(name):
    check_name(name)
    d = projekt_dir(name)
    neu = not os.path.isdir(d)
    os.makedirs(d, exist_ok=True)
    made = []
    today = datetime.date.today().isoformat()
    for fn, tmpl in (("PROJEKT.md", PROJEKT_TMPL), ("CHANGELOG.md", CHANGELOG_TMPL)):
        f = os.path.join(d, fn)
        if not os.path.exists(f):
            with open(f, "w") as fh:
                fh.write(tmpl.format(name=name, datum=today))
            made.append(fn)
    return d, neu, made


def set_projekt(name):
    d, neu, made = ensure_projekt(name)
    vs = versions(d)
    v = vs[-1][1] if vs else None          # neueste Version (= aktuell)
    save_state({"projekt": name, "version": v})
    return d, neu, made, v


def clear():
    save_state({})


def set_version(ref):
    p, _, _ = active()
    if not p:
        raise Fehler(WARN_FALLBACK)
    v = find_version(projekt_dir(p), ref)
    save_state({"projekt": p, "version": v})
    return p, v


def remote_path(p):
    """Pfad auf dem Dateiserver (CAD_REMOTE_PATH_MAP="<lokal>=<server>", sonst unveraendert)."""
    p = os.path.abspath(p)
    if "=" in REMOTE_MAP:
        a, b = REMOTE_MAP.split("=", 1)
        if p.startswith(a):
            return b + p[len(a):]
    return p


def remote(cmd, timeout=20):
    """Befehl auf dem Dateiserver (ssh, BatchMode) -> (rc, stdout+stderr)."""
    if not REMOTE:
        return 255, "CAD_SYMLINK_HOST nicht gesetzt (Symlinks auf dieser Freigabe nur per ssh auf dem Dateiserver moeglich)"
    try:
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", REMOTE, cmd],
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 255, str(e)


def make_symlink(target, link):
    """Symlink link -> target (relativ) anlegen/ersetzen; ein vorhandenes echtes File/Ordner wird nie ersetzt.
    Erst lokal, bei EOPNOTSUPP (Netzfreigabe) per ssh auf dem Dateiserver."""
    try:
        if os.path.lexists(link) and not os.path.islink(link):
            raise OSError(errno.EOPNOTSUPP, "pruefen auf dem Dateiserver")
        tmp = link + ".tmp%d" % os.getpid()
        os.symlink(target, tmp)
        os.replace(tmp, link)
        return
    except OSError as e:
        if e.errno not in (errno.EOPNOTSUPP, errno.EPERM, errno.ENOSYS):
            raise
    L = remote_path(link)
    rc, out = remote("L=%s; if [ -e \"$L\" ] && [ ! -L \"$L\" ]; then echo \"kein Symlink: $L\"; exit 3; fi; ln -sfn %s \"$L\""
                    % (shlex.quote(L), shlex.quote(target)))
    if rc != 0:
        raise Fehler("Symlink %s -> %s nicht angelegt (Dateiserver: %s)" % (link, target, out or rc))


def read_symlink(link):
    """Ziel eines Symlinks (lokal oder, auf der Freigabe unsichtbar, per ssh auf dem Dateiserver); None wenn keiner."""
    if os.path.islink(link):
        return os.readlink(link)
    if not os.path.exists(link):
        return None
    rc, out = remote("readlink %s" % shlex.quote(remote_path(link)), timeout=10)
    return out if rc == 0 and out else None


def _set_link(pdir, target):
    make_symlink(target, os.path.join(pdir, "aktuell"))


def new_version(label, basiert_auf=None, datum=None):
    p, cur_v, _ = active()
    if not p:
        raise Fehler(WARN_FALLBACK)
    if not label or not label.strip():
        raise Fehler("cad version: Label fehlt (z. B. cad version \"Hoehe 84, Fussspiel 0,30\")")
    pdir = projekt_dir(p)
    basis = find_version(pdir, basiert_auf) if basiert_auf else None
    vs = versions(pdir)
    nr = (vs[-1][0] + 1) if vs else 1
    datum = datum or datetime.date.today().isoformat()
    name = "v%03d_%s_%s" % (nr, datum, slug(label))
    vdir = os.path.join(pdir, name)
    os.makedirs(vdir)
    for k in KINDS:
        os.makedirs(os.path.join(vdir, k))
    link_err = None
    try:
        _set_link(pdir, name)
    except Fehler as e:
        link_err = str(e)
    line = "- %s (%s): %s%s\n" % ("v%03d" % nr, datum, label.strip(), " (basiert auf %s)" % basis.split("_")[0] if basis else "")
    with open(os.path.join(pdir, "CHANGELOG.md"), "a") as f:
        f.write(line)
    save_state({"projekt": p, "version": name})
    return p, name, vdir, basis, link_err


def freigabe(notiz):
    p, v, vdir = active()
    if not vdir:
        raise Fehler("keine aktive Version (cad projekt <name>; cad version \"<Label>\")")
    f = os.path.join(vdir, "freigabe.md")
    if os.path.exists(f):
        raise Gesperrt("%s/%s ist schon freigegeben (%s)" % (p, v, f))
    files = []
    for k in KINDS:
        d = os.path.join(vdir, k)
        for root, _, fs in os.walk(d):
            for fn in sorted(fs):
                fp = os.path.join(root, fn)
                files.append("- `%s` (%d Bytes)" % (os.path.relpath(fp, vdir), os.path.getsize(fp)))
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(f, "w") as fh:
        fh.write("# Freigabe %s %s\n\nDatum: %s\nNotiz: %s\n\nStand der Version (Dateien bei Freigabe):\n%s\n\n"
                 "Diese Version wird nicht mehr veraendert; Aenderungen = neue Version (`cad version`).\n"
                 % (p, v, now, notiz.strip(), "\n".join(files) or "- (keine Dateien)"))
    return p, v, f


def projekt_list():
    out = []
    try:
        names = sorted(os.listdir(ROOT))
    except OSError:
        names = []
    for n in names:
        d = os.path.join(ROOT, n)
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, "PROJEKT.md")):
            vs = versions(d)
            out.append({"projekt": n, "versionen": len(vs), "neueste": vs[-1][1] if vs else None})
    return out


def projekt_show(name=None):
    if not name:
        name, _, _ = active()
        if not name:
            raise Fehler(WARN_FALLBACK)
    d = projekt_dir(name)
    if not os.path.isdir(d):
        raise Fehler("Projekt %s gibt es nicht (%s)" % (name, d))
    st = load_state()
    rows = []
    for nr, v in versions(d):
        vdir = os.path.join(d, v)
        n = sum(len(fs) for k in KINDS for _, _, fs in os.walk(os.path.join(vdir, k)))
        rows.append({"version": v, "dateien": n, "freigabe": is_frozen(vdir),
                     "aktiv": st.get("projekt") == name and st.get("version") == v})
    return {"projekt": name, "pfad": d, "aktuell": read_symlink(os.path.join(d, "aktuell")),
            "versionen": rows, "experimente": sorted(os.listdir(os.path.join(d, "experimente"))) if os.path.isdir(os.path.join(d, "experimente")) else []}
