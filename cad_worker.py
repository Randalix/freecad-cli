"""Persistenter Headless-FreeCAD-Worker.  Start: freecad -c cad_worker.py   (User-Dienst `cadworker`)
Socket: $XDG_RUNTIME_DIR/cadworker.sock, Rueckfall /run/user/$UID, zuletzt /tmp.  Protokoll: eine JSON-Zeile je Anfrage.
Anfragen   {"cmd": "ping"|"status"}                      sofort beantwortet, setzt den Leerlauf NICHT zurueck
           {"op": "run", "file"|"code", "cwd", "keep", "args", "report", "export"}   Skript ausfuehren
           {"op": "info", "file"}  /  {"op": "export", ...}   (cadlib.py, laufen wie Skripte im Hauptthread)
Antworten  optional {"event": "queued", "ahead": N}, dann {"ok": bool, "stdout", "error", "traceback", "seconds", ...}
Skripte laufen im Hauptthread nacheinander (FreeCAD ist nicht threadsicher); Verbindungen werden in Threads angenommen:
ein halb offener Client (kein Request in REQ_TIMEOUT s) blockiert nichts. Beendet sich nach IDLE_S s ohne Lauf."""
import contextlib, io, json, os, queue, select, socket, sys, threading, time, traceback

import FreeCAD as App

CAD_DIR = os.environ.get("CAD_DIR", "/mnt/raid1/3d_print/tools/freecad")
if CAD_DIR not in sys.path:
    sys.path.insert(0, CAD_DIR)


def sock_path():
    d = os.environ.get("XDG_RUNTIME_DIR")
    if not d or not os.path.isdir(d):
        d = "/run/user/%d" % os.getuid()
        if not os.path.isdir(d):
            d = "/tmp"
    return os.path.join(d, "cadworker.sock")


SOCK = sock_path()
IDLE_S = int(os.environ.get("CAD_IDLE_S", "900"))
REQ_TIMEOUT = float(os.environ.get("CAD_REQ_TIMEOUT", "5"))
MAX_QUEUE = 16
MAX_REQ = 32 * 1024 * 1024

START = time.time()
state = {"busy": False, "script": None, "since": 0.0, "last": time.time(), "runs": 0}
q = queue.Queue()
qlock = threading.Lock()
ns_keep = {}


def short_error(exc, filename):
    """Eine Zeile Fehlertext plus Quellzeile der letzten Stelle im Skript."""
    head = "%s: %s" % (type(exc).__name__, exc)
    loc = ""
    if isinstance(exc, SyntaxError):
        loc = "%s:%s: %s" % (os.path.basename(exc.filename or filename), exc.lineno, (exc.text or "").strip())
    else:
        hit = None
        for fr in traceback.extract_tb(exc.__traceback__):
            if fr.filename == filename or fr.filename.startswith(os.path.dirname(filename) + os.sep):
                hit = fr
        if hit is not None:
            loc = "%s:%s: %s" % (os.path.basename(hit.filename), hit.lineno, (hit.line or "").strip())
    return head + ("\n  " + loc if loc else "")


def purge_modules(directory):
    """Module aus dem Skriptordner vergessen, damit geaenderte Hilfsmodule neu geladen werden."""
    if not directory:
        return
    prefix = directory.rstrip(os.sep) + os.sep
    for name, mod in list(sys.modules.items()):
        f = getattr(mod, "__file__", None)
        if f and f.startswith(prefix):
            del sys.modules[name]


def run_script(req):
    global ns_keep
    keep = bool(req.get("keep"))
    cwd = req.get("cwd")
    file = req.get("file")
    if cwd and os.path.isdir(cwd):
        os.chdir(cwd)
    script_dir = os.path.dirname(file) if file else (cwd or os.getcwd())
    if not keep:
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)
        ns = {}
    else:
        ns = ns_keep
    ns_keep = ns
    import cadlib
    cadlib.reset_run(keep)
    if hasattr(cadlib, "set_projekt"):
        cadlib.set_projekt(req.get("projekt"))      # Projektstruktur: cad.outdir() nutzt den Zustand des Aufrufers
    before = cadlib.snapshot()
    filename = file or "<code>"
    ns.update({"__name__": "__main__", "__file__": filename, "App": App, "cad": cadlib})
    code = req["code"] if "code" in req else open(file).read()
    sys.argv = [filename] + list(req.get("args", []))
    sys.path.insert(0, script_dir)
    purge_modules(script_dir)
    out = io.StringIO()
    err = tb = None
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            exec(compile(code, filename, "exec"), ns)
    except BaseException as e:      # auch SystemExit/KeyboardInterrupt aus Skripten abfangen
        if isinstance(e, SystemExit) and not e.code:
            pass
        else:
            err = short_error(e, filename)
            tb = traceback.format_exc()
    finally:
        try:
            sys.path.remove(script_dir)
        except ValueError:
            pass
    resp = {"stdout": out.getvalue(), "error": err, "traceback": tb, "ok": err is None}
    try:
        cadlib.post_run(req, before, resp)
    except Exception as e:
        resp["warning"] = "cadlib.post_run: %s: %s" % (type(e).__name__, e)
    return resp


def handle(req):
    t = time.time()
    try:
        op = req.get("op", "run")
        if op == "run":
            resp = run_script(req)
        else:
            import cadlib
            resp = cadlib.op(op, req)
    except BaseException as e:
        resp = {"ok": False, "stdout": "", "error": "%s: %s" % (type(e).__name__, e), "traceback": traceback.format_exc()}
    resp["seconds"] = round(time.time() - t, 2)
    return resp


def alive(conn):
    try:
        r, _, _ = select.select([conn], [], [], 0)
        return not r or conn.recv(1, socket.MSG_PEEK) != b""
    except OSError:
        return False


def send(conn, obj):
    conn.sendall((json.dumps(obj) + "\n").encode())


def status_dict():
    now = time.time()
    return {"ok": True, "pid": os.getpid(), "state": "busy" if state["busy"] else "idle", "script": state["script"],
            "busy_seconds": round(now - state["since"], 1) if state["busy"] else 0, "queued": q.qsize(),
            "runs": state["runs"], "uptime": round(now - START), "idle_seconds": 0 if state["busy"] else round(now - state["last"]),
            "idle_limit": IDLE_S, "socket": SOCK, "cwd": os.getcwd(), "freecad": ".".join(App.Version()[:3])}


def serve(conn):
    try:
        with conn:
            conn.settimeout(REQ_TIMEOUT)
            buf = b""
            while not buf.endswith(b"\n") and len(buf) < MAX_REQ:
                chunk = conn.recv(65536)
                if not chunk:
                    return              # Probe oder Abbruch ohne Anfrage
                buf += chunk
            if not buf.strip():
                return
            conn.settimeout(30)
            try:
                req = json.loads(buf.decode())
            except ValueError:
                send(conn, {"ok": False, "error": "ungueltige Anfrage"})
                return
            if req.get("cmd") in ("ping", "status"):
                send(conn, status_dict())
                return
            with qlock:
                ahead = q.qsize() + (1 if state["busy"] else 0)
                if q.qsize() >= MAX_QUEUE:
                    send(conn, {"ok": False, "error": "busy: Warteschlange voll (%d)" % ahead, "busy": True})
                    return
                job = {"req": req, "conn": conn, "done": threading.Event(), "resp": None}
                q.put(job)
            if ahead:
                send(conn, {"event": "queued", "ahead": ahead})
            job["done"].wait()
            if job["resp"] is not None:
                send(conn, job["resp"])
    except (OSError, socket.timeout):
        pass


def acceptor(srv):
    while True:
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        threading.Thread(target=serve, args=(conn,), daemon=True).start()


def main():
    if os.path.exists(SOCK):
        os.unlink(SOCK)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCK)
    os.chmod(SOCK, 0o600)
    srv.listen(32)
    threading.Thread(target=acceptor, args=(srv,), daemon=True).start()
    try:
        while True:
            try:
                job = q.get(timeout=1)
            except queue.Empty:
                if time.time() - state["last"] > IDLE_S:
                    break
                continue
            if not alive(job["conn"]):          # Client weg, bevor er dran war
                job["done"].set()
                continue
            req = job["req"]
            state.update(busy=True, since=time.time(), script=req.get("file") or "<code>")
            try:
                job["resp"] = handle(req)
            finally:
                state.update(busy=False, script=None, last=time.time(), runs=state["runs"] + 1)
                job["done"].set()
    finally:
        if os.path.exists(SOCK):
            os.unlink(SOCK)
    os._exit(0)


main()
