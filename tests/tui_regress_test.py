#!/usr/bin/env python3
# regression check: the row ops on a non-empty tree still behave (the
# empty-tree guards must not have changed the normal paths)
import os, fcntl, pty, plistlib, select, struct, subprocess, sys, termios, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WD = "/tmp/plist_tui_tests"          # scratch files for the run
XDG = os.path.join(WD, "config")     # first-run config stays out of $HOME
LOG = "/tmp/plist_tui.log"           # the editor appends tracebacks here
F = os.path.join(WD, "normal.plist")
os.makedirs(XDG, exist_ok=True); os.makedirs(WD, exist_ok=True)
with open(F, "wb") as f:
    plistlib.dump({"Alpha": "one", "Flag": True, "Nest": {"Deep": "x"}},
                  f, fmt=plistlib.FMT_XML, sort_keys=False)

DOWN, UP = b"\x1bOB", b"\x1bOA"
CTRL_S, CTRL_Z = b"\x13", b"\x1a"
fails = []
def check(n, c, extra=""):
    print(("PASS " if c else "FAIL ") + n + ("  " + extra if extra and not c else ""))
    if not c: fails.append(n)

master, slave = pty.openpty()
fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
env = dict(os.environ, TERM="xterm-256color", LC_ALL="C.UTF-8", XDG_CONFIG_HOME=XDG)
proc = subprocess.Popen([sys.executable, os.path.join(REPO, "propertreecli.py"), "edit", F],
                        stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
os.close(slave)
buf = b""
def pump(t=0.4):
    global buf
    end = time.time() + t
    while time.time() < end:
        r, _, _ = select.select([master], [], [], 0.1)
        if r:
            try: c = os.read(master, 65536)
            except OSError: break
            if not c: break
            buf += c
def wait_for(text, timeout=6):
    end = time.time() + timeout
    while time.time() < end:
        if text in buf.decode("utf-8", "replace"): return True
        pump(0.2)
    return False
def send(d, t=0.35):
    os.write(master, d if isinstance(d, bytes) else d.encode()); time.sleep(t); pump()
def load():
    with open(F, "rb") as f: return plistlib.load(f)

open(LOG, "w").close()
check("boots", wait_for("Alpha") and wait_for("Nest"))
# rows: 0 Alpha, 1 Flag, 2 Nest, 3 Deep (Nest auto-expands in a small file)
def down(n):
    for _ in range(n):
        send(b"j")
# add a sibling after Alpha (root dict, leaf row)
send(b"i"); send(b"\r"); send(b"Mid\r")
send(b"g"); down(3)                       # Nest
send(b"i"); send(b"\r"); send(b"Extra\r")
send(b"g"); down(4)                       # Deep (Extra appends after it in Nest)
send(b"c", t=0.5)
send(b"g")                                # back to Alpha
send(b"p"); send(b"\x15Pasted\r", t=0.6)   # ctrl+u clears the prefilled key
send(CTRL_S, t=0.6)
d = load()
check("sibling insert keeps dict order",
      list(d) == ["Alpha", "Pasted", "Mid", "Flag", "Nest"], repr(list(d)))
check("child added into the container", d["Nest"].get("Extra") == "", repr(d))
check("paste copies the value", d["Pasted"] == "x", repr(d))
send(b"g"); down(3)                       # Flag
send(b"\r", t=0.5)
send(CTRL_S, t=0.5)
check("enter toggles a boolean", load()["Flag"] is False, repr(load()))
send(CTRL_Z, t=0.5); send(CTRL_S, t=0.5)
check("undo restores it", load()["Flag"] is True, repr(load()))
send(b"g"); send(b"r"); send(b"\x15Renamed\r", t=0.5)
send(CTRL_S, t=0.5)
check("rename", load().get("Renamed") == "one", repr(load()))
send(b"q", t=0.8); pump(0.5)
try:
    rc = proc.wait(timeout=4)
except subprocess.TimeoutExpired:
    proc.kill(); rc = None
check("clean quit", rc == 0, "rc=%s" % rc)
check("no tracebacks", not os.path.getsize(LOG), open(LOG).read()[-400:])
os.close(master)
print("FAILS:", len(fails))
sys.exit(1 if fails else 0)
