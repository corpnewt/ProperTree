#!/usr/bin/env python3
# propertreecli - a plist editor for the terminal
# new code in corpnewt's ProperTree tree, BSD-3 like the rest (see
# LICENSE). the terminal look is styled after W0lfSword, a toolkit of
# mine.
#
# VERSION is the single source of truth. the command is `plist`; the
# file keeps the repo name so it can never shadow Scripts/plist.py on
# import.
VERSION = "0.5.0"

import argparse
import datetime
import json
import os
import plistlib
import shutil
import sys
import traceback

# repo root, resolved through the ~/.local/bin symlink so the Scripts
# import works no matter which directory the command runs from
_HERE = os.path.dirname(os.path.realpath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ── color palette - arctic wolf ───────────────────────────────
# one accent (C_FROST), one muted tone (C_DIM), three semantic colors
# (grn ok, amb warn, red error). C_BRAND is for the tree art only.
# bold (B) marks important words. everything resets with NC.
C_BRAND = "\033[38;5;153m"
C_FROST = "\033[38;5;117m"
C_DIM   = "\033[38;5;240m"
C_GRN   = "\033[0;32m"
C_AMB   = "\033[1;33m"
C_RED   = "\033[0;31m"
B       = "\033[1m"
NC      = "\033[0m"

COLOR = True  # flipped off by --no-color, NO_COLOR, or a non-tty stdout

def color_on():
    return COLOR

def reset_colors():
    global C_BRAND, C_FROST, C_DIM, C_GRN, C_AMB, C_RED, B, NC
    C_BRAND = C_FROST = C_DIM = C_GRN = C_AMB = C_RED = B = NC = ""

# ── drawing helpers ───────────────────────────────────────────
def term_cols():
    return shutil.get_terminal_size((80, 24)).columns

def _vis_len(s):
    # visible length of an ansi-free string
    return len(s)

def _trunc(s, n):
    if _vis_len(s) <= n:
        return s
    if n <= 1:
        return s[:n]
    return s[: n - 1] + "\u2026"

def rule(n=None):
    # dim horizontal rule
    n = n or min(term_cols() - 2, 76)
    print("  " + C_DIM + "\u2500" * n + NC)

def banner(title, sub=None, color=None):
    # even boxed banner, W0lfSword style: computed padding, so the title
    # centers regardless of length. only drawn on a tty.
    color = color or C_FROST
    w = term_cols() - 6
    w = min(max(w, 40), 72)
    w -= w % 2
    inner = w - 2
    lines = [title] + ([sub] if sub else [])
    print("  " + color + B + "\u2554" + "\u2550" * inner + "\u2557" + NC)
    for t in lines:
        t = _trunc(t, inner)
        pad = inner - _vis_len(t)
        l = pad // 2
        r = pad - l
        print("  " + color + B + "\u2551" + NC + " " * l + t + " " * r + color + B + "\u2551" + NC)
    print("  " + color + B + "\u255a" + "\u2550" * inner + "\u255d" + NC)

# ── the tree logo ─────────────────────────────────────────────
# built from column math instead of hand-tuned so the branches always
# line up. a plist is a tree: root tag branching into its children.
def tree_art_lines():
    pad = " " * 8
    w = 21
    b = "+" + "-" * (w - 2) + "+"
    # inner text centered: "<plist>" in a w-2 wide cell
    tag = "<plist>"
    cell = w - 2
    lp = (cell - len(tag)) // 2
    rp = cell - lp - len(tag)
    mid = w // 2  # 10: center column inside the box
    half = (w - 3) // 2  # 9: dash runs on the branch line
    lines = [
        pad + b,
        pad + "|" + " " * lp + tag + " " * rp + "|",
        pad + "+" + "-" * half + "+" + "-" * half + "+",
        pad + " " * mid + "|",
        pad + "+" + "-" * half + "+" + "-" * half + "+",
        pad + "|" + " " * half + "|" + " " * half + "|",
    ]
    # labels centered under the three branch points (cols 0, mid, w-1),
    # in absolute columns so the left one never clips
    labels = [(0, "<dict>"), (mid, "<array>"), (w - 1, "<string>")]
    row_w = len(pad) + w + 8
    row = [" "] * row_w
    for col, text in labels:
        start = len(pad) + col - len(text) // 2
        for i, ch in enumerate(text):
            if 0 <= start + i < row_w:
                row[start + i] = ch
    lines.append("".join(row).rstrip())
    return lines

def show_logo():
    if not COLOR:
        return
    art = tree_art_lines()
    print(C_BRAND + "\n".join(art) + NC)
    print("")

# ── status glyphs (W0lfSword convention) ──────────────────────
def ok(text):   print("  " + C_GRN + "\u2713" + NC + " " + text)
def err(text):  print("  " + C_RED + "\u2717" + NC + " " + text, file=sys.stderr)
def warn(text): print("  " + C_AMB + "\u26a0" + NC + " " + text, file=sys.stderr)
def info(text): print("  " + C_FROST + "\u2139" + NC + " " + text)
def hint(text): print("  " + C_DIM + "  \u2192 " + text + NC)
def hint_err(text): print("  " + C_DIM + "  \u2192 " + text + NC, file=sys.stderr)

# ── plist io ──────────────────────────────────────────────────
def _plist_mod():
    # lazy import: --version/--help must work even if Scripts/plist.py
    # misbehaves on some python build
    from Scripts import plist as _plist
    return _plist

def is_binary(path):
    with open(path, "rb") as f:
        return f.read(8) == b"bplist00"

def file_format(path):
    return "binary" if is_binary(path) else "xml"

def load_plist(path):
    return _plist_mod().load(open(path, "rb"))

def write_plist(root, path, fmt="xml"):
    # atomic write + verify: dump to a temp file, parse it back, then
    # swap it in. a broken write never leaves a half-written plist behind.
    from Scripts import plist as _plist
    fmt = _plist.FMT_BINARY if fmt == "binary" else _plist.FMT_XML
    tmp = path + ".tmp"
    try:
        with open(tmp, "wb") as f:
            _plist.dump(root, f, fmt=fmt, sort_keys=False)
        with open(tmp, "rb") as f:
            _plist.load(f)  # throws if the dump is garbage
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

# ── value formatting ──────────────────────────────────────────
def type_name(v):
    if isinstance(v, bool):       return "boolean"
    if isinstance(v, int):        return "integer"
    if isinstance(v, float):      return "real"
    if isinstance(v, str):        return "string"
    if isinstance(v, bytes):      return "data"
    if isinstance(v, plistlib.UID) or type(v).__name__ == "UID":
        return "uid"
    if isinstance(v, datetime.datetime):
        return "date"
    if isinstance(v, dict):       return "dict"
    if isinstance(v, list):       return "array"
    return type(v).__name__.lower()

def value_text(v):
    # plain text for a leaf value; dict/array return "" (children drawn
    # below). strings get control chars unescaped so rows stay single-line.
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, str):
        return v.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t")
    if isinstance(v, bytes):
        s = " ".join("{:02X}".format(x) for x in v[:32])
        return s + (" \u2026" if len(v) > 32 else "")
    if isinstance(v, plistlib.UID) or type(v).__name__ == "UID":
        return str(getattr(v, "data", v))
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    # data objects from old parsers (plistlib.Data and friends)
    d = getattr(v, "data", None)
    if d is not None and isinstance(d, bytes):
        return " ".join("{:02X}".format(x) for x in d[:32])
    return str(v)

def value_color(v):
    # booleans read as status: enabled green, disabled grey. everything
    # else keeps the default foreground - frost is for keys.
    if isinstance(v, bool):
        return C_GRN if v else C_DIM
    return ""

# ── tree rendering ────────────────────────────────────────────
def _max_key_len(node):
    best = 0
    if isinstance(node, dict):
        for k, v in node.items():
            best = max(best, len(k))
            if isinstance(v, (dict, list)):
                best = max(best, _max_key_len(v))
    elif isinstance(node, list):
        for v in node:
            if isinstance(v, (dict, list)):
                best = max(best, _max_key_len(v))
    return best

def _render_node(node, prefix, keyw, cols, last=True, key=None):
    # one row per entry: guides (dim), key (bold frost), type (dim),
    # value (plain or status-colored). containers recurse. visible width
    # is tracked separately from the ansi codes so values don't truncate
    # early when colors are on.
    leaf = not isinstance(node, (dict, list))
    if key is None and isinstance(node, dict):
        key = ""
    guide = prefix + ("\u2514\u2500 " if last else "\u251c\u2500 ")
    out = [C_DIM + guide + NC]
    vis = len(guide)
    if key is not None:
        ktxt = _trunc(str(key), keyw)
        # array indexes are structural, not keys: dim them
        if isinstance(key, int):
            out.append(C_DIM + ktxt + NC)
        else:
            out.append(C_FROST + B + ktxt + NC)
        out.append(" " * (keyw - len(ktxt)) + " ")
        vis += keyw + 1
        out.append(C_DIM + type_name(node).ljust(9) + " " + NC)
        vis += 10
        if leaf:
            vt = value_text(node)
            vc = value_color(node)
            out.append(vc + _trunc(vt, max(cols - vis, 0)) + (NC if vc else ""))
        elif len(node) == 0:
            out.append(C_DIM + "(empty)" + NC)
    print("".join(out))
    if not leaf:
        child_prefix = prefix + ("   " if last else "\u2502  ")
        items = list(node.items()) if isinstance(node, dict) else list(enumerate(node))
        for i, (ck, cv) in enumerate(items):
            _render_node(cv, child_prefix, keyw, cols, last=i == len(items) - 1, key=ck)

def show_tree(root, cols=None):
    cols = cols or term_cols() - 2
    keyw = min(max(_max_key_len(root), 8), 32)
    if isinstance(root, (dict, list)):
        # the root container has no row of its own; its entries do
        items = list(root.items()) if isinstance(root, dict) else list(enumerate(root))
        for i, (k, v) in enumerate(items):
            _render_node(v, "  ", keyw, cols, last=i == len(items) - 1, key=k)
    else:
        _render_node(root, "  ", keyw, cols, last=True, key="root")

def _describe_root(root):
    if isinstance(root, dict):
        n = len(root)
        return "{} key{}".format(n, "" if n == 1 else "s")
    if isinstance(root, list):
        n = len(root)
        return "{} item{}".format(n, "" if n == 1 else "s")
    return type_name(root)

def _open_error(path, e):
    # friendly failure text for the common cases: missing file, directory,
    # or something that is not a plist
    if isinstance(e, FileNotFoundError):
        err("cannot open {}: no such file".format(path))
        hint_err("create it with: plist new {}".format(path))
    elif isinstance(e, IsADirectoryError):
        err("{} is a directory, not a plist".format(path))
    else:
        err("cannot open {}: {}".format(path, e))
        hint_err("is it a plist? xml and binary both work")

def open_and_show(path, show_banner=True):
    root = _load_or_err(path)
    if root is None:
        return 1
    fmt = file_format(path)
    if show_banner and COLOR:
        show_logo()
        banner(path, "{} plist - {}".format(fmt, _describe_root(root)))
    else:
        print(path)
    show_tree(root)
    return 0

# ── config ────────────────────────────────────────────────────
# plain key=value file, # comments, template written on first run.
# the schema doubles as the docs, same trick as W0lfSword's config_schema().
CONFIG_DEFAULTS = {"expand_mode": "auto", "format": "xml", "find_scope": "both",
                   "theme": "frost"}
# valid values per key, so `plist settings set` can validate before writing
CONFIG_VALID = {
    "expand_mode": ("all", "auto", "none"),
    "format": ("xml", "binary"),
    "find_scope": ("keys", "values", "both"),
    "theme": ("frost", "red"),
}
CONFIG_TEMPLATE = """# plist config - plain key=value, # comments. the editor reads this
# on open. edit by hand, or manage it with: plist settings
#   plist settings              show current values
#   plist settings set K V      change one (validated)
#   plist settings reset        back to defaults

# expand_mode - how containers look when the editor opens a file:
#   all   every container expanded
#   auto  expand everything unless the file is huge (>1200 nodes)
#   none  everything collapsed; unfold with right arrow or space
expand_mode = auto

# format - what `plist new` writes by default: xml | binary
format = xml

# find_scope - what / searches by default: keys | values | both
# (tab inside the find prompt cycles the scope for that search)
find_scope = both

# theme - frost is the usual pale blue; red turns every text color red
theme = frost
"""

def config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config")
    return os.path.join(base, "propertreecli")

def config_path():
    return os.path.join(config_dir(), "config")

def ensure_config():
    p = config_path()
    if os.path.exists(p):
        return p
    try:
        os.makedirs(config_dir(), exist_ok=True)
        with open(p, "w") as f:
            f.write(CONFIG_TEMPLATE)
    except OSError:
        pass
    return p

def load_config():
    cfg = dict(CONFIG_DEFAULTS)
    try:
        with open(config_path()) as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if not line or "=" not in line:
                    continue
                k, v = [x.strip() for x in line.split("=", 1)]
                cfg[k] = v
    except OSError:
        pass
    if cfg.get("expand_mode") not in CONFIG_VALID["expand_mode"]:
        cfg["expand_mode"] = "auto"
    if cfg.get("format") not in CONFIG_VALID["format"]:
        cfg["format"] = "xml"
    if cfg.get("find_scope") not in CONFIG_VALID["find_scope"]:
        cfg["find_scope"] = "both"
    if cfg.get("theme") not in CONFIG_VALID["theme"]:
        cfg["theme"] = "frost"
    return cfg

# ── keypaths ──────────────────────────────────────────────────
class PathError(Exception):
    pass

def split_path(s):
    # dot separated; a backslash escapes a literal dot in a key name
    parts, buf = [], []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            buf.append(s[i + 1])
            i += 2
            continue
        if c == ".":
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    parts.append("".join(buf))
    for p in parts:
        if p == "":
            raise PathError("empty segment in keypath '{}'".format(s))
    return parts

def _step_into(cur, seg, create=False):
    # descend one level during path resolution
    if isinstance(cur, dict):
        if seg in cur:
            return cur[seg]
        if create:
            cur[seg] = {}
            return cur[seg]
        raise PathError("no key '{}'".format(seg))
    if isinstance(cur, list):
        try:
            i = int(seg)
        except ValueError:
            raise PathError("'{}' is not an array index".format(seg))
        if i < len(cur):
            return cur[i]
        if create and i == len(cur):
            cur.append({})
            return cur[-1]
        raise PathError("array index {} out of range (len {})".format(i, len(cur)))
    raise PathError("cannot descend into a {} value".format(type_name(cur)))

def _resolve_path(root, segs, create=False):
    # walk everything but the last segment; returns (container, last)
    cur = root
    for seg in segs[:-1]:
        cur = _step_into(cur, seg, create=create)
    return cur, segs[-1]

def _is_uid(v):
    return isinstance(v, plistlib.UID) or type(v).__name__ == "UID"

def _has_uid(v):
    if isinstance(v, dict):
        return any(_has_uid(x) for x in v.values())
    if isinstance(v, list):
        return any(_has_uid(x) for x in v)
    return _is_uid(v)

# ── one-shot value io ─────────────────────────────────────────
_BOOL_WORDS = {
    "true": True, "false": False, "yes": True, "no": False,
    "on": True, "off": False, "1": True, "0": False,
}

def parse_value(raw, kind):
    # kind: s string (default), i integer (0x ok), f real, b boolean,
    # x data from hex, d date (iso), u uid (binary plists only)
    if kind == "s":
        return raw
    if kind == "i":
        try:
            return int(raw, 0)
        except ValueError:
            raise ValueError("not an integer: '{}'".format(raw))
    if kind == "f":
        try:
            return float(raw)
        except ValueError:
            raise ValueError("not a number: '{}'".format(raw))
    if kind == "b":
        w = raw.lower()
        if w not in _BOOL_WORDS:
            raise ValueError("not a boolean: '{}' (try true/false, yes/no, on/off, 1/0)".format(raw))
        return _BOOL_WORDS[w]
    if kind == "x":
        try:
            return bytes.fromhex("".join(raw.split()))
        except ValueError:
            raise ValueError("not hex data: '{}'".format(raw))
    if kind == "d":
        try:
            return datetime.datetime.fromisoformat(raw.replace(" ", "T", 1))
        except ValueError:
            raise ValueError("not an iso date: '{}' (try 2024-03-01 or 2024-03-01 12:30:00)".format(raw))
    if kind == "u":
        if not hasattr(plistlib, "UID"):
            raise ValueError("uid needs python 3.8+")
        try:
            return plistlib.UID(int(raw, 0))
        except ValueError:
            raise ValueError("not an integer uid: '{}'".format(raw))
    raise ValueError("unknown type flag '{}'".format(kind))

def _data_bytes(v):
    # bytes, or the data payload of legacy plistlib.Data style objects
    if isinstance(v, bytes):
        return v
    d = getattr(v, "data", None)
    return d if isinstance(d, bytes) else None

def to_jsonable(v):
    if isinstance(v, dict):
        return {k: to_jsonable(x) for k, x in v.items()}
    if isinstance(v, list):
        return [to_jsonable(x) for x in v]
    if isinstance(v, bool) or isinstance(v, (int, float)) or isinstance(v, str):
        return v
    d = _data_bytes(v)
    if d is not None:
        return " ".join("{:02X}".format(b) for b in d)
    if _is_uid(v):
        return getattr(v, "data", v)
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return str(v)

def print_value(v, json_mode=False):
    # script output: strings raw, bools lowercase, data as continuous
    # hex (pipes into xxd -r -p), dates iso. containers tree out, or
    # json with --json.
    if json_mode:
        print(json.dumps(to_jsonable(v)))
        return
    if isinstance(v, (dict, list)):
        show_tree(v)
        return
    d = _data_bytes(v)
    if isinstance(v, bool):
        print("true" if v else "false")
    elif d is not None:
        print("".join("{:02X}".format(b) for b in d))
    elif _is_uid(v):
        print(getattr(v, "data", v))
    elif isinstance(v, datetime.datetime):
        print(v.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        print(v)

def _load_or_err(path):
    try:
        return load_plist(path)
    except Exception as e:
        _open_error(path, e)
        if os.environ.get("PROPERTREECLI_DEBUG"):
            traceback.print_exc()
        return None

def _write_or_err(root, path):
    try:
        write_plist(root, path, file_format(path))
    except Exception as e:
        err("cannot write {}: {}".format(path, e))
        if os.environ.get("PROPERTREECLI_DEBUG"):
            traceback.print_exc()
        return 1
    ok("wrote {}".format(path))
    return 0

def cmd_get(argv, json_mode=False):
    p = argparse.ArgumentParser(prog="plist get",
        description="print the value at a keypath")
    p.add_argument("file")
    p.add_argument("keypath")
    a = p.parse_args(argv)
    root = _load_or_err(a.file)
    if root is None:
        return 1
    try:
        segs = split_path(a.keypath)
        if len(segs) == 1 and not isinstance(root, (dict, list)):
            raise PathError("root is a {} value, not a container".format(type_name(root)))
        parent, last = _resolve_path(root, segs)
        v = _step_into(parent, last)
    except PathError as e:
        err("{}: {}".format(a.keypath, e))
        return 2
    print_value(v, json_mode)
    return 0

def cmd_set(argv):
    p = argparse.ArgumentParser(prog="plist set",
        description="set the value at a keypath; missing dictionaries along "
                    "the path are created, arrays accept index == length to "
                    "append. the file keeps its format and key order.")
    p.add_argument("file")
    p.add_argument("keypath")
    p.add_argument("value", nargs="?", help="value to store; omit with -b to flip an existing boolean")
    g = p.add_mutually_exclusive_group()
    g.add_argument("-i", action="store_const", const="i", dest="kind", help="integer (0x hex ok)")
    g.add_argument("-f", action="store_const", const="f", dest="kind", help="real number")
    g.add_argument("-b", action="store_const", const="b", dest="kind", help="boolean (true/false/yes/no/on/off/1/0)")
    g.add_argument("-x", action="store_const", const="x", dest="kind", help="data from a hex string")
    g.add_argument("-d", action="store_const", const="d", dest="kind", help="date (iso)")
    g.add_argument("-u", action="store_const", const="u", dest="kind", help="uid (binary plists only)")
    a = p.parse_args(argv)
    kind = a.kind or "s"
    root = _load_or_err(a.file)
    if root is None:
        return 1
    if a.value is None:
        if kind == "b":
            # flag flip: needs an existing boolean
            try:
                segs = split_path(a.keypath)
                parent, last = _resolve_path(root, segs)
                cur = _step_into(parent, last)
            except PathError as e:
                err("{}: {}".format(a.keypath, e))
                return 2
            if not isinstance(cur, bool):
                err("{} is a {} - flip needs an existing boolean".format(a.keypath, type_name(cur)))
                return 1
            parsed = not cur
        else:
            p.error("missing value")
    else:
        try:
            parsed = parse_value(a.value, kind)
        except ValueError as e:
            err(str(e))
            return 1
    if kind == "u" and file_format(a.file) != "binary":
        err("uid values only survive in binary plists - {} is xml".format(a.file))
        return 1
    try:
        segs = split_path(a.keypath)
        container, last = _resolve_path(root, segs, create=True)
        if isinstance(container, dict):
            existing = container.get(last)
            if isinstance(existing, (dict, list)):
                err("{} is a {} - refusing to replace a container (del it first)".format(
                    a.keypath, type_name(existing)))
                return 1
            container[last] = parsed
        elif isinstance(container, list):
            try:
                i = int(last)
            except ValueError:
                err("'{}' is not an array index".format(last))
                return 2
            if i < len(container):
                existing = container[i]
                if isinstance(existing, (dict, list)):
                    err("{} is a {} - refusing to replace a container (del it first)".format(
                        a.keypath, type_name(existing)))
                    return 1
                container[i] = parsed
            elif i == len(container):
                container.append(parsed)
            else:
                err("array index {} out of range (len {})".format(i, len(container)))
                return 2
        else:
            err("root is a {} value, not a container".format(type_name(root)))
            return 1
    except PathError as e:
        err("{}: {}".format(a.keypath, e))
        return 2
    if _has_uid(root) and file_format(a.file) != "binary":
        err("file contains uid values; only binary plists can store them")
        return 1
    code = _write_or_err(root, a.file)
    if code == 0:
        ok("{} = {}".format(a.keypath, a.value if a.value is not None else "flipped"))
    return code

def cmd_del(argv):
    p = argparse.ArgumentParser(prog="plist del",
        description="remove the key or array element at a keypath")
    p.add_argument("file")
    p.add_argument("keypath")
    a = p.parse_args(argv)
    root = _load_or_err(a.file)
    if root is None:
        return 1
    try:
        segs = split_path(a.keypath)
        container, last = _resolve_path(root, segs)
        if isinstance(container, dict):
            if last not in container:
                raise PathError("no key '{}'".format(last))
            del container[last]
        elif isinstance(container, list):
            try:
                i = int(last)
            except ValueError:
                raise PathError("'{}' is not an array index".format(last))
            if not 0 <= i < len(container):
                raise PathError("array index {} out of range (len {})".format(i, len(container)))
            del container[i]
        else:
            raise PathError("cannot descend into a {} value".format(type_name(container)))
    except PathError as e:
        err("{}: {}".format(a.keypath, e))
        return 2
    code = _write_or_err(root, a.file)
    if code == 0:
        ok("removed {}".format(a.keypath))
    return code

def _fmt_diff_value(v):
    # short value text for diff lines: containers as a count summary
    if isinstance(v, dict):
        return "<dict {} keys>".format(len(v))
    if isinstance(v, list):
        return "<array {} items>".format(len(v))
    return value_text(v)

def _diff_walk(a, b, path, out):
    # out is a list of (kind, path, a_text, b_text) where kind is
    # "+" added, "-" removed, "~" changed. arrays compare by index,
    # dicts by key; recursion stops at the first difference.
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a:
            if k not in b:
                out.append(("-", path + [k], _fmt_diff_value(a[k]), None))
        for k in b:
            if k not in a:
                out.append(("+", path + [k], None, _fmt_diff_value(b[k])))
        for k in a:
            if k in b:
                _diff_walk(a[k], b[k], path + [k], out)
    elif isinstance(a, list) and isinstance(b, list):
        for i in range(max(len(a), len(b))):
            if i >= len(a):
                out.append(("+", path + [i], None, _fmt_diff_value(b[i])))
            elif i >= len(b):
                out.append(("-", path + [i], _fmt_diff_value(a[i]), None))
            else:
                _diff_walk(a[i], b[i], path + [i], out)
    elif a != b:
        out.append(("~", path, _fmt_diff_value(a), _fmt_diff_value(b)))

def _fmt_diff_path(path):
    # dotted keypath for display; array indexes read as plain numbers
    return ".".join(str(s) for s in path)

def cmd_diff(argv):
    # plist diff <fileA> <fileB>: walk both trees, print what differs.
    # exit codes: 0 identical, 1 differences, 2 file/usage error.
    p = argparse.ArgumentParser(prog="plist diff",
        description="compare two plists, print added/removed/changed keypaths")
    p.add_argument("files", nargs=2, metavar="file")
    a = p.parse_args(argv)
    f1, f2 = a.files
    r1 = _load_or_err(f1)
    if r1 is None:
        return 2
    r2 = _load_or_err(f2)
    if r2 is None:
        return 2
    out = []
    _diff_walk(r1, r2, [], out)
    # sort by keypath so the output is stable and readable
    out.sort(key=lambda t: _fmt_diff_path(t[1]))
    for kind, path, va, vb in out:
        kp = _fmt_diff_path(path)
        if kind == "+":
            print("  " + C_GRN + "+ " + NC + kp + " = " + vb)
        elif kind == "-":
            print("  " + C_RED + "- " + NC + kp + " = " + va)
        else:
            print("  " + C_AMB + "~ " + NC + kp + ": " + va + "  ->  " + vb)
    if out:
        n_add = sum(1 for t in out if t[0] == "+")
        n_del = sum(1 for t in out if t[0] == "-")
        n_chg = len(out) - n_add - n_del
        info("{} added, {} removed, {} changed".format(n_add, n_del, n_chg))
        return 1
    ok("identical")
    return 0

def cmd_new(argv):
    p = argparse.ArgumentParser(prog="plist new",
        description="create a new empty plist and open it in the editor")
    p.add_argument("path", help="file to create (refuses to overwrite)")
    p.add_argument("--binary", action="store_true",
        help="write a binary plist (default: xml, or the config format)")
    p.add_argument("--root", choices=("dict", "array"), default="dict",
        help="root container type (default dict)")
    a = p.parse_args(argv)
    if os.path.exists(a.path):
        err("{} already exists - refusing to overwrite".format(a.path))
        return 1
    root = {} if a.root == "dict" else []
    fmt = "binary" if a.binary else load_config().get("format", "xml")
    try:
        write_plist(root, a.path, fmt)
    except Exception as e:
        err("cannot create {}: {}".format(a.path, e))
        if os.environ.get("PROPERTREECLI_DEBUG"):
            traceback.print_exc()
        return 1
    ok("created {} ({} plist, {} root)".format(a.path, fmt, a.root))
    if _tty():
        return _start_editor(a.path)
    return 0

def cmd_convert(argv):
    p = argparse.ArgumentParser(prog="plist convert",
        description="rewrite a plist in the other format, in place unless -o")
    p.add_argument("file")
    p.add_argument("-t", "--to", required=True, choices=("xml", "binary"),
        help="target format")
    p.add_argument("-o", "--out", help="output path (default: overwrite the file)")
    a = p.parse_args(argv)
    root = _load_or_err(a.file)
    if root is None:
        return 1
    if a.to == "xml" and _has_uid(root):
        err("{} holds uid values - xml plists cannot represent them".format(a.file))
        return 1
    out = a.out or a.file
    try:
        write_plist(root, out, a.to)
    except Exception as e:
        err("cannot write {}: {}".format(out, e))
        if os.environ.get("PROPERTREECLI_DEBUG"):
            traceback.print_exc()
        return 1
    ok("wrote {} as a {} plist".format(out, a.to))
    return 0

def _write_config_file(p, text):
    # atomic-ish config write: temp file + rename, same discipline as plists
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, p)

def cmd_settings(argv):
    # plist settings | settings set key value | settings reset
    p = argparse.ArgumentParser(prog="plist settings",
        description="show or change the plist config file")
    p.add_argument("action", nargs="?", default="show", choices=("show", "set", "reset"))
    p.add_argument("rest", nargs="*")
    a = p.parse_args(argv)
    path = ensure_config()
    if a.action == "show":
        cfg = load_config()
        ok("config: {}".format(path))
        for k in CONFIG_DEFAULTS:
            info("{} = {}".format(k, cfg.get(k, CONFIG_DEFAULTS[k])))
        return 0
    if a.action == "reset":
        try:
            os.remove(path)
        except OSError:
            pass
        ensure_config()
        ok("config reset to defaults: {}".format(path))
        return 0
    # set key value
    if len(a.rest) != 2:
        err("settings set takes a key and a value, e.g.: plist settings set format binary")
        return 2
    key, value = a.rest
    if key not in CONFIG_VALID:
        err("unknown setting '{}' - known: {}".format(key, ", ".join(sorted(CONFIG_VALID))))
        return 2
    if value not in CONFIG_VALID[key]:
        err("'{}' is not valid for {} - use one of: {}".format(
            value, key, ", ".join(CONFIG_VALID[key])))
        return 2
    # update the file in place, preserving comments and other keys
    lines = []
    try:
        with open(path) as f:
            lines = f.readlines()
    except OSError:
        pass
    found = False
    for i, ln in enumerate(lines):
        body = ln.split("#", 1)[0].strip()
        if body.startswith(key + "=") or body.startswith(key + " =")\
                or body == key:
            lines[i] = "{} = {}\n".format(key, value)
            found = True
            break
    if not found:
        lines.append("{} = {}\n".format(key, value))
    _write_config_file(path, "".join(lines))
    ok("{} = {}".format(key, value))
    return 0

# ── cli ───────────────────────────────────────────────────────
JSON_OUT = False

COMMANDS = ("get", "set", "del", "diff", "convert", "edit", "new", "settings", "help")

SHORT_USAGE = (
    "usage: plist [--json] [--no-color] <command> [args] | <file...>\n"
    "       commands: get, set, del, diff, convert, edit, new, settings   (plist help for details)"
)

HELP = """\
plist v{} - a plist editor for the terminal (W0lfSword-flavored)

usage:
  plist [file]                            open a plist in the interactive
                                          editor (falls back to a tree print
                                          when stdout is piped)
  plist <file...>                         show plists as a tree
  plist edit <file>                       force the interactive editor
  plist get <file> <keypath> [--json]     print the value at a keypath
  plist set <file> <keypath> <value> [-i|-f|-b|-x|-d|-u]
                                          set the value at a keypath
  plist del <file> <keypath>              remove a key or array element
  plist diff <fileA> <fileB>              show added/removed/changed keys
                                          (exit 0 identical, 1 differs)
  plist convert <file> --to xml|binary [-o out]
                                          rewrite in the other format
  plist new <file> [--binary] [--root dict|array]
                                          create an empty plist (xml by
                                          default) and open the editor
  plist settings                          show the config values
  plist settings set <key> <value>        change one (validated)
  plist settings reset                    back to defaults

options:
  --json       machine-readable output (get only)
  --no-color   plain output (implied when stdout is not a tty)
  --version    print the version
  -h, --help   this help

the editor:
  arrow keys or j/k move, left/right (or space) fold containers, home/end
  top/bottom, {{ }} jump to the previous/next sibling, ctrl+d / ctrl+u
  half a page, enter edits a value (booleans toggle), i adds an entry,
  d deletes, D duplicates, r renames a key, t changes a value's type,
  c/x/p copy/cut/paste, u undoes (ctrl+r redoes, 200 steps), / finds
  with n/N cycling, R replaces the find text in string values, ctrl+s
  saves, q quits (it asks when dirty), ? shows every keybind. the file
  keeps its format and key order, and writes are atomic + verified by
  re-reading.

config: ~/.config/propertreecli/config (created on first editor run).
expand_mode = all | auto | none decides how containers open; format
= xml | binary is what plist new writes; find_scope = keys | values |
both is what / searches by default (tab inside the find prompt cycles
the scope for that search); theme = frost | red picks the palette
(red turns every text color red). plist settings shows and changes
these.

one-shots:
  keypaths are dot separated: Misc.Boot.Timeout or Drivers.0.Path; a
  backslash escapes a literal dot in a key name (com\\\\.apple\\\\.x). get and
  del walk existing keys; set creates missing dictionaries along the way
  and appends to arrays at index == length. values default to strings:
  -i integer (0x hex ok)   -f real   -b boolean (true/false/yes/no/on/off/
  1/0; omit the value to flip an existing boolean)   -x data from hex
  -d date (iso)   -u uid (binary plists only). values that start with a
  dash need a -- separator first: plist set f.plist Boot-args -- -v x

get prints strings raw, booleans lowercase, data as continuous hex (pipe
it into xxd -r -p), dates iso; containers tree out. exit codes:
0 ok, 1 file or value error, 2 bad keypath or usage
""".format(VERSION)

def _apply_color_flags():
    global COLOR
    if not COLOR or os.environ.get("NO_COLOR"):
        COLOR = False
    elif not sys.stdout.isatty():
        COLOR = False
    if not COLOR:
        reset_colors()
        return
    # theme = red from the config file turns every color red (frost 196,
    # dim 124 so hints stay muted) - same idea as the editor palette
    try:
        if load_config().get("theme") == "red":
            global C_BRAND, C_FROST, C_DIM, C_GRN, C_AMB, C_RED
            C_BRAND = C_FROST = C_GRN = C_AMB = C_RED = "\033[38;5;196m"
            C_DIM = "\033[38;5;124m"
    except Exception:
        pass

def _tty():
    return sys.stdout.isatty() and sys.stdin.isatty()

def _start_editor(path):
    # the curses editor (plist_tui); only works on a real terminal
    if not _tty():
        err("the editor needs a terminal - run it in one, or use get/set/del")
        return 1
    root = _load_or_err(path)
    if root is None:
        return 1
    try:
        from plist_tui import run_editor
    except Exception as e:
        err("editor failed to load: {}".format(e))
        if os.environ.get("PROPERTREECLI_DEBUG"):
            traceback.print_exc()
        return 1
    return run_editor(root, path)

def main(argv=None):
    global COLOR, JSON_OUT
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    # global flags can sit anywhere (W0lfSword pre-scans the same way)
    rest, help_wanted = [], False
    for a in argv:
        if a == "--json":
            JSON_OUT = True
        elif a == "--no-color":
            COLOR = False
        elif a == "--version":
            print("plist v" + VERSION)
            return 0
        elif a in ("-h", "--help"):
            help_wanted = True
        else:
            rest.append(a)
    _apply_color_flags()

    if not rest:
        if help_wanted:
            print(HELP)
            return 0
        if os.path.exists("config.plist"):
            return _start_editor("config.plist") if _tty() else open_and_show("config.plist")
        err("nothing to open: no config.plist in this directory")
        hint_err("try: plist <file.plist>     (open a plist)")
        hint_err("     plist new my.plist     (start from scratch)")
        hint_err("     plist help             (everything)")
        return 1

    cmd = rest[0]
    if cmd in COMMANDS:
        sub = rest[1:]
        if help_wanted:
            sub.insert(0, "-h")
        if cmd == "help":
            print(HELP)
            return 0
        if cmd == "edit":
            if len(sub) != 1:
                err("edit takes exactly one plist file")
                return 2
            return _start_editor(sub[0])
        if cmd == "new":
            return cmd_new(sub)
        if cmd == "settings":
            return cmd_settings(sub)
        if cmd == "get":
            return cmd_get(sub, json_mode=JSON_OUT)
        if cmd == "set":
            return cmd_set(sub)
        if cmd == "del":
            return cmd_del(sub)
        if cmd == "diff":
            return cmd_diff(sub)
        return cmd_convert(sub)
    if help_wanted or cmd.startswith("-"):
        print(HELP)
        return 0 if help_wanted else 2

    # not a command: plist files. one file on a terminal opens the
    # editor; anything else prints the tree (plain when piped)
    if len(rest) == 1 and _tty() and not help_wanted:
        return _start_editor(rest[0])
    code = 0
    for i, f in enumerate(rest):
        if i:
            print("")
        code |= open_and_show(f)
    return code

if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # stdout closed early (propertreecli file.plist | head) - not an error
        try:
            sys.stdout.close()
        except Exception:
            pass
        sys.exit(0)
