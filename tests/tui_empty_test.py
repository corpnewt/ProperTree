#!/usr/bin/env python3
# regression smoke test: filling a brand new (empty root) plist in the tui
import os, fcntl, pty, plistlib, select, struct, subprocess, sys, termios, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WD = "/tmp/plist_tui_tests"          # scratch files for the run
XDG = os.path.join(WD, "config")     # first-run config stays out of $HOME
LOG = "/tmp/plist_tui.log"           # the editor appends tracebacks here
os.makedirs(XDG, exist_ok=True)
os.makedirs(WD, exist_ok=True)

DOWN, UP, RIGHT, LEFT = b"\x1bOB", b"\x1bOA", b"\x1bOC", b"\x1bOD"
CTRL_S = b"\x13"
fails = []

def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + ("  " + extra if extra and not cond else ""))
    if not cond:
        fails.append(name)

class Tui:
    def __init__(self, path):
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
        env = dict(os.environ, TERM="xterm-256color", LC_ALL="C.UTF-8",
                   LANG="C.UTF-8", XDG_CONFIG_HOME=XDG)
        self.proc = subprocess.Popen([sys.executable, os.path.join(REPO, "propertreecli.py"),
                                      "edit", path],
                                     stdin=slave, stdout=slave, stderr=slave,
                                     env=env, close_fds=True)
        os.close(slave)
        self.buf = b""

    def pump(self, t=0.4):
        end = time.time() + t
        while time.time() < end:
            r, _, _ = select.select([self.master], [], [], 0.1)
            if r:
                try:
                    c = os.read(self.master, 65536)
                except OSError:
                    break
                if not c:
                    break
                self.buf += c
                if len(self.buf) > 400000:
                    self.buf = self.buf[-200000:]

    def wait_for(self, text, timeout=6):
        end = time.time() + timeout
        while time.time() < end:
            if text in self.buf.decode("utf-8", "replace"):
                return True
            self.pump(0.2)
        return False

    def send(self, d, t=0.35):
        os.write(self.master, d if isinstance(d, bytes) else d.encode())
        time.sleep(t)
        self.pump()

    def quit(self):
        self.send(b"q")
        time.sleep(0.8)
        self.pump(0.5)
        try:
            rc = self.proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            return None
        os.close(self.master)
        return rc

def new_plist(path, *extra):
    return subprocess.run([sys.executable, os.path.join(REPO, "propertreecli.py"),
                           "new", path] + list(extra),
                          capture_output=True, env=dict(os.environ, XDG_CONFIG_HOME=XDG)).returncode

def load(path):
    with open(path, "rb") as f:
        return plistlib.load(f)

open(LOG, "w").close()  # the editor appends tracebacks here

# ── empty dict root ────────────────────────────────────────────────────
F = os.path.join(WD, "fresh.plist")
os.path.exists(F) and os.unlink(F)
check("plist new creates the file", new_plist(F) == 0 and os.path.exists(F))
t = Tui(F)
check("empty root is announced", t.wait_for("empty dictionary root"))
# every one of these used to raise IndexError on an empty tree
for k in (LEFT, RIGHT, UP, DOWN, b"\r", b"c", b"d", b"r", b"t", b"D", b"x",
          b"g", b"G", b">{", b"{"):
    t.send(k)
check("no crash from row keys", not os.path.getsize(LOG), open(LOG).read()[-400:])
check("still alive after row keys", t.proc.poll() is None)

# i -> string -> key name
t.send(b"i"); t.send(b"\r"); t.send(b"Alpha\r")
check("first entry added to the root", t.wait_for("Alpha"))
t.send(b"i"); t.send(b"\r"); t.send(b"Beta\r")
# last row, then a dict child: menu item 9 is "dict"
t.send(b"G"); t.send(b"i"); t.send(b"j" * 7); t.send(b"\r"); t.send(b"Nested\r")
t.send(b"G"); t.send(b"i"); t.send(b"\r"); t.send(b"Child\r")
t.send(CTRL_S, t=0.6)
d = load(F)
check("dict root filled", d == {"Alpha": "", "Beta": "", "Nested": {"Child": ""}}, repr(d))
# delete the child through the confirm menu
t.send(b"G"); t.send(b"d"); t.send(b"k\r")   # confirm menu defaults to no
t.send(CTRL_S, t=0.6)
d = load(F)
check("delete works on the filled tree", d == {"Alpha": "", "Beta": "", "Nested": {}}, repr(d))
rc = t.quit()
check("clean quit (dict)", rc == 0, "rc=%s" % rc)
check("no tracebacks (dict run)", not os.path.getsize(LOG), open(LOG).read()[-400:])

# ── empty array root ───────────────────────────────────────────────────
A = os.path.join(WD, "fresh_array.plist")
os.path.exists(A) and os.unlink(A)
check("plist new --root array", new_plist(A, "--root", "array") == 0)
t = Tui(A)
check("empty array root is announced", t.wait_for("empty array root"))
t.send(b"i"); t.send(b"\r"); t.send(CTRL_S, t=0.6)
d = load(A)
check("array root filled", d == [""], repr(d))
t.send(b"i"); t.send(b"j" * 8); t.send(b"\r")            # -> array, appended
t.send(b"i"); t.send(b"j" * 3); t.send(b"\r")            # -> boolean, appended
t.send(CTRL_S, t=0.6)
d = load(A)
check("array keeps taking mixed types", d == ["", True, []], repr(d))
t.send(b">")
t.send(b"G"); t.send(b"i"); t.send(b"\r")   # on the empty array row: adds into it
t.send(CTRL_S, t=0.6)
d = load(A)
check("move row + add into the last container", d == [True, "", [""]], repr(d))
rc = t.quit()
check("clean quit (array)", rc == 0, "rc=%s" % rc)
check("no tracebacks (array run)", not os.path.getsize(LOG), open(LOG).read()[-400:])

print("FAILS:", len(fails))
sys.exit(1 if fails else 0)
