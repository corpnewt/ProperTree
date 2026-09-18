#!/usr/bin/env python3
# plist_tui - the curses editor behind `plist <file>`
# new code in the ProperTree tree, BSD-3 like the rest (see LICENSE).
# imports helpers from propertreecli lazily, so the module only loads
# when an editor actually starts.
#
# layout, top to bottom:
#   header:  file (frost bold)  format  dirty marker      hints (dim)
#            ─ dim rule
#   tree:    key / type / value rows, ▸▾ for collapsed containers
#   status:  mode + transient messages
#   footer:  condensed keybind legend (dim)
#
# look follows W0lfSword: frost accents on grey, boxed menus, dim hints,
# status glyphs. selection is a frost bar with dark text.

import base64
import copy
import curses
import datetime
import locale
import os
import sys
import time
import traceback

# ── color mapping ─────────────────────────────────────────────
# W0lfSword indexes on 256-color terminals; degrade for 8/16-color.
# frost/brand are 256-color tones, the semantic colors stay ansi base.
_EXACT = {"frost": 117, "brand": 153, "dim": 240, "grn": 2, "amb": 3, "red": 1}
_16 = {"frost": 14, "brand": 14, "dim": 8, "grn": 10, "amb": 11, "red": 9}
_8 = {"frost": 6, "brand": 6, "dim": 7, "grn": 2, "amb": 3, "red": 1}
# theme = red turns every text color red: accents at 196, dim at 124 so
# hints stay muted, and the depth shades walk down through darker reds.
_RED_EXACT = {"frost": 196, "brand": 196, "dim": 124, "grn": 196, "amb": 196, "red": 196}
_RED_16 = {"frost": 9, "brand": 9, "dim": 1, "grn": 9, "amb": 9, "red": 9}
_RED_8 = {"frost": 1, "brand": 1, "dim": 1, "grn": 1, "amb": 1, "red": 1}
# pairs: 1 frost(accents/keys) 2 dim 3 grn 4 amb 5 red 6 brand 7 sel bar
# depth pairs 10..15: d1..d6 for nested levels. d0 is not a real pair -
# top-level keys draw as plain frost (PAIR d0 -> 1) so the root of a file
# looks exactly like it always did.
PAIR = {}
# nested-key ramp: a straight desaturation of frost (135,215,255) toward
# gray, walking green and blue down together while red stays fixed - no
# hue detours. 110 is steel, 103 is gray-blue (red=green), 102 is gray,
# then flat. no init_color on purpose: palette redefinition is
# terminal-dependent and entries 16-21 silently render as black on
# terminals that ignore it, which looks like missing text.
_DEPTH_STOCK = [110, 103, 102, 102, 102, 102]  # d1..d6, clamped at d3
# red theme: same idea, darker reds per level (clamped at 88)
_DEPTH_RED = [160, 124, 88, 88, 88, 88]

def _load_theme():
    # which palette theme the config asks for; never throws - a missing or
    # broken config just means frost
    try:
        from propertreecli import ensure_config, load_config
        ensure_config()
        return load_config().get("theme", "frost")
    except Exception:
        return "frost"

def _init_colors():
    curses.start_color()
    try:
        curses.use_default_colors()
    except curses.error:
        pass
    red = _load_theme() == "red"
    if curses.COLORS >= 256:
        m = _RED_EXACT if red else _EXACT
    elif curses.COLORS >= 16:
        m = _RED_16 if red else _16
    else:
        m = _RED_8 if red else _8
    depth = _DEPTH_RED if red else _DEPTH_STOCK
    for i, key in enumerate(("frost", "dim", "grn", "amb", "red", "brand"), 1):
        try:
            curses.init_pair(i, m[key], -1)
        except curses.error:
            curses.init_pair(i, m[key], 0)
    # selection bar: dark text on a frost background
    try:
        curses.init_pair(7, 0, m["frost"])
    except curses.error:
        curses.init_pair(7, 0, 14)
    PAIR["frost"] = 1
    PAIR["dim"] = 2
    PAIR["grn"] = 3
    PAIR["amb"] = 4
    PAIR["red"] = 5
    PAIR["brand"] = 6
    PAIR["d0"] = 1  # top level = plain frost, same as the original keys
    if curses.COLORS >= 256:
        # stock-index depth shades, pairs 10..15 (d1..d6)
        for i, idx in enumerate(depth):
            try:
                curses.init_pair(10 + i, idx, -1)
            except curses.error:
                curses.init_pair(10 + i, idx, 0)
            PAIR["d{}".format(i + 1)] = 10 + i
    else:
        # 8/16-color terminals: no depth tint, every key plain frost
        for i in range(1, len(depth) + 1):
            PAIR["d{}".format(i)] = 1

def P(name, bold=False):
    a = curses.color_pair(PAIR[name])
    return a | curses.A_BOLD if bold else a

# ── display helpers ───────────────────────────────────────────
def _esc(s):
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t")

def _type_name(v):
    from propertreecli import type_name
    return type_name(v)

def canonical(v):
    # text form used for editing prefill and type conversion
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, str):
        return v
    if isinstance(v, bytes):
        return " ".join("{:02X}".format(b) for b in v)
    if _is_uid(v):
        return str(getattr(v, "data", v))
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    d = getattr(v, "data", None)
    if isinstance(d, bytes):
        return " ".join("{:02X}".format(b) for b in d)
    return str(v)

def _is_uid(v):
    from propertreecli import _is_uid as iu
    return iu(v)

def value_color_name(v):
    if isinstance(v, bool):
        return "grn" if v else "dim"
    return None

_KINDS = {
    "string": "s", "integer": "i", "real": "f", "boolean": "b",
    "data": "x", "date": "d", "uid": "u",
}
_NEW_DEFAULTS = {
    "string": "", "integer": 0, "real": 0.0, "boolean": True,
    "data": b"", "date": None, "uid": None,
}

def _parse(text, kind):
    from propertreecli import parse_value
    return parse_value(text, kind)

# ── converter (ctrl+t) ────────────────────────────────────────
# the tk gui's Convert Window (Ctrl+T) is a scratchpad that
# renders text as bytes in one encoding and back out in another.
# same five views here: ascii, base64, decimal, hex, binary.
_CONV_NAMES = ("Ascii", "Base64", "Decimal", "Hex", "Binary")

def _convert_text(text, frm, to):
    # raise ValueError with a readable reason on bad input
    if not text:
        raise ValueError("nothing to convert")
    f, t = frm.lower(), to.lower()
    if f == "hex":
        v = text[2:] if text.lower().startswith("0x") else text
        v = v.replace(" ", "").replace("<", "").replace(">", "")
        if not v or any(c.lower() not in "0123456789abcdef" for c in v):
            raise ValueError("hex text may only hold 0-9 a-f (0x, <>, spaces ok)")
        if len(v) % 2:
            v = "0" + v
        data = bytes.fromhex(v)
    elif f in ("decimal", "binary"):
        base = 10 if f == "decimal" else 2
        try:
            n = int("".join(text.split()), base)
        except ValueError:
            raise ValueError("not a valid {} number: '{}'".format(frm, text.strip()))
        h = "{:x}".format(n)
        if len(h) % 2:
            h = "0" + h
        data = bytes.fromhex(h)
    elif f == "base64":
        s = "".join(text.split())
        s2 = s.rstrip("=")
        if len(s2) % 4 == 1:
            raise ValueError("not valid base64 text")
        s = s2 + "=" * ((4 - len(s2) % 4) % 4)
        try:
            data = base64.b64decode(s, validate=True)
        except Exception:
            raise ValueError("not valid base64 text")
    else:  # ascii
        data = text.encode("utf-8")
    if t == "base64":
        return base64.b64encode(data).decode("ascii")
    if t == "hex":
        out = data.hex().upper()
        return " ".join(out[i:i + 8] for i in range(0, len(out), 8))
    if t == "decimal":
        return str(int(data.hex() or "0", 16))
    if t == "binary":
        return "{:b}".format(int(data.hex() or "0", 16))
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("bytes are not valid utf-8 text (try hex or base64)")

def _convert_prefill(kind):
    # (from_index, to_index) preselects for a node kind
    if kind == "data":
        return 3, 1        # hex -> base64
    if kind == "integer":
        return 2, 3        # decimal -> hex
    return 0, 3            # string: ascii -> hex

def _convert_apply(kind, text, frm):
    # write the source text back into a value of the node's own kind,
    # interpreting the text as the from-encoding (what the user picked
    # in the converter). raises ValueError when that encoding cannot
    # round-trip into the plist type (view-only conversions).
    f = frm.lower()
    if kind == "data":
        if f == "hex":
            return bytes.fromhex("".join(text.split()))
        if f == "base64":
            return base64.b64decode("".join(text.split()))
        if f == "ascii":
            return text.encode("utf-8")
        raise ValueError("decimal/binary cannot rebuild data bytes - view only")
    if kind == "integer":
        base = {"decimal": 10, "hex": 16, "binary": 2}.get(f)
        if base is None:
            raise ValueError("ascii/base64 cannot rebuild an integer - view only")
        clean = "".join(text.split())
        if f == "hex":
            clean = clean[2:] if clean.lower().startswith("0x") else clean
        try:
            return int(clean, base)
        except ValueError:
            raise ValueError("not a valid {} number: '{}'".format(frm, text.strip()))
    # string
    if f == "ascii":
        return text
    if f == "hex":
        try:
            return bytes.fromhex("".join(text.split())).decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("those bytes are not utf-8 text - view only")
    if f == "base64":
        try:
            return base64.b64decode("".join(text.split())).decode("utf-8")
        except Exception:
            raise ValueError("not text in that base64 - view only")
    raise ValueError("decimal/binary cannot rebuild a string - view only")

# ── insert from template (T) ──────────────────────────────────
# the tk gui right-clicks a node and offers presets from
# Scripts/menu.plist: each preset knows its destination path
# (Root/ACPI/Add, Root/Kernel/Add, ...), the container types
# along it (d = dict, a = array), and the value to insert.
# the terminal editor has no pointer, so T offers the whole
# list and the preset's own path decides where it lands.
_MENU_CACHE_PATH = None
_MENU_CACHE_DATA = None

def _template_root():
    # repo layout: this file sits next to Scripts/menu.plist
    return os.path.join(os.path.dirname(os.path.realpath(__file__)),
                        "Scripts", "menu.plist")

def _template_data():
    # lazy one-time load of menu.plist; returns {section: {path: [items]}}
    global _MENU_CACHE_PATH, _MENU_CACHE_DATA
    p = _template_root()
    if _MENU_CACHE_PATH == p and _MENU_CACHE_DATA is not None:
        return _MENU_CACHE_DATA
    if not os.path.exists(p):
        return None
    try:
        from propertreecli import load_plist
        data = load_plist(p)
        _MENU_CACHE_PATH = p
        _MENU_CACHE_DATA = data
        return data
    except Exception:
        return None

# ── the editor ────────────────────────────────────────────────
class Editor:
    def __init__(self, stdscr, root, path):
        from propertreecli import file_format, ensure_config, load_config
        ensure_config()
        cfg = load_config()
        self.s = stdscr
        self.root = root
        self.path = path
        self.fmt = file_format(path)
        self.expand_mode = cfg.get("expand_mode", "auto")
        self.find_scope = cfg.get("find_scope", "both")  # keys | values | both
        self.rows = []          # visible rows, rebuilt per frame
        self.expanded = {}      # path tuple -> bool
        self.sel = 0
        self.top = 0
        self.undo = []
        self.redo = []
        self.dirty = False
        self.msg = ""
        self.msg_color = "dim"
        self.find = None        # active query
        self.matches = []       # row indexes matching self.find
        self.match_idx = -1
        self.clip_file = os.path.join(
            os.environ.get("XDG_RUNTIME_DIR") or "/tmp", "plist-clipboard.plist")
        self.log = "/tmp/plist_tui.log"
        self._row_of_path = {}
        self._node_count = 0
        # hold-to-accelerate state for j/k and the arrow keys
        self._hold_dir = 0
        self._ramp = 0.0
        self._frac = 0.0
        self._mv_last = 0.0
        self._cycle_i = 0       # last pick in a cycling prompt (find scope)

    # ── frames ────────────────────────────────────────────────
    def H(self):
        return self.s.getmaxyx()[0]

    def W(self):
        return self.s.getmaxyx()[1]

    def _count(self, node):
        # total descendants of a container (cached per frame)
        if isinstance(node, dict):
            return 1 + sum(self._count(v) for v in node.values())
        if isinstance(node, list):
            return 1 + sum(self._count(v) for v in node)
        return 1

    def _is_expanded(self, path, node):
        if path not in self.expanded:
            # decided by the config: all / auto (huge files fold deep
            # levels) / none (start collapsed, unfold by hand)
            mode = self.expand_mode
            if mode == "none":
                want = False
            elif mode == "all":
                want = True
            else:
                want = not (self._node_count > 1200 and len(path) > 1)
            self.expanded[path] = want
        return self.expanded[path]

    def _build_rows(self):
        rows = []

        def walk(node, path, depth):
            if isinstance(node, dict):
                for k, v in node.items():
                    p = path + [k]
                    if isinstance(v, (dict, list)):
                        n = self._count(v)
                        rows.append({"path": p, "key": k, "depth": depth,
                                     "node": v, "type": _type_name(v),
                                     "count": n, "leaf": False})
                        if self._is_expanded(tuple(p), v):
                            walk(v, p, depth + 1)
                    else:
                        rows.append({"path": p, "key": k, "depth": depth,
                                     "node": v, "type": _type_name(v),
                                     "leaf": True})
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    p = path + [i]
                    if isinstance(v, (dict, list)):
                        n = self._count(v)
                        rows.append({"path": p, "key": i, "depth": depth,
                                     "node": v, "type": _type_name(v),
                                     "count": n, "leaf": False})
                        if self._is_expanded(tuple(p), v):
                            walk(v, p, depth + 1)
                    else:
                        rows.append({"path": p, "key": i, "depth": depth,
                                     "node": v, "type": _type_name(v),
                                     "leaf": True})

        self._node_count = self._count(self.root)
        self.root_is_dict = isinstance(self.root, dict)
        self.root_is_list = isinstance(self.root, list)
        walk(self.root, [], 0)
        self.rows = rows
        if self.sel >= len(rows):
            self.sel = max(len(rows) - 1, 0)

    def _recompute_matches(self):
        self.matches = []
        if not self.find:
            return
        q = self.find.lower()
        for i, r in enumerate(self.rows):
            key_hit = isinstance(r["key"], str) and q in r["key"].lower()
            # only scalar rows carry a value; containers match on their key
            val_hit = r["leaf"] and q in canonical(r["node"]).lower()
            if self.find_scope == "keys":
                hit = key_hit
            elif self.find_scope == "values":
                hit = val_hit
            else:
                hit = key_hit or val_hit
            if hit:
                self.matches.append(i)

    # ── undo ──────────────────────────────────────────────────
    def _push_undo(self):
        self.undo.append(copy.deepcopy(self.root))
        if len(self.undo) > 200:
            self.undo.pop(0)
        self.redo = []
        self.dirty = True

    def _undo(self):
        if not self.undo:
            self._flash("nothing to undo")
            return
        self.redo.append(copy.deepcopy(self.root))
        self.root = self.undo.pop()
        self.dirty = True
        self._after_mutate()
        self._flash("undone", "grn")

    def _redo(self):
        if not self.redo:
            self._flash("nothing to redo")
            return
        self.undo.append(copy.deepcopy(self.root))
        self.root = self.redo.pop()
        self.dirty = True
        self._after_mutate()
        self._flash("redone", "grn")

    def _after_mutate(self):
        self._build_rows()
        self._recompute_matches()
        self._clamp()

    def _clamp(self):
        if self.sel >= len(self.rows):
            self.sel = max(len(self.rows) - 1, 0)

    def _goto(self, idx):
        # jump the selection to a row index; the next draw scrolls it in
        self.sel = idx
        self._clamp()

    def _flash(self, text, color="dim"):
        self.msg = text
        self.msg_color = color

    def _parent_of(self, row):
        p = row["path"]
        parent = self.root
        for seg in p[:-1]:
            if isinstance(parent, dict):
                parent = parent[seg]
            else:
                parent = parent[int(seg)]
        return parent, p[-1]

    def _sel_row(self):
        # the selected row, or None when the tree is empty: the root
        # container is never drawn as a row, so a fresh `plist new` (or
        # any empty root) has no rows at all for the row ops to point at
        if not self.rows:
            kind = ("dict" if getattr(self, "root_is_dict", False)
                    else "array" if getattr(self, "root_is_list", False) else "plist")
            self._flash("empty {} - press i to add the first entry".format(kind))
            return None
        return self.rows[self.sel]

    def _target_of_row(self, row):
        # (container, anchor, into_container) for an add or a paste: a
        # container row takes children, a leaf row takes siblings, and no
        # row at all means the root itself is the container
        if row is None:
            return self.root, None, True
        if isinstance(row["node"], (dict, list)):
            return self._node_at(row["path"]), None, True
        return self._node_at(row["path"][:-1]), row["path"][-1], False

    def _last(self):
        # index of the last row, 0 when the tree is empty (never -1)
        return max(len(self.rows) - 1, 0)

    # ── save / quit ───────────────────────────────────────────
    def _save(self):
        from propertreecli import file_format, write_plist
        try:
            write_plist(self.root, self.path, file_format(self.path))
        except Exception as e:
            self._flash("save failed: {}".format(e), "red")
            return False
        self.dirty = False
        self._flash("saved \u2713", "grn")
        return True

    def _confirm_dirty(self):
        if not self.dirty:
            return "y"
        m = self._menu("save changes?", ["yes", "no", "cancel"])
        return "y" if m == 0 else ("n" if m == 1 else "c")

    # ── row ops ───────────────────────────────────────────────
    def _row_index_of_path(self, path):
        for i, r in enumerate(self.rows):
            if tuple(r["path"]) == tuple(path):
                return i
        return None

    def _rebuild_rows_keep(self, path):
        # rebuild after an expand/collapse, keeping the selection on the
        # container that was toggled (its children appear or vanish below)
        self._build_rows()
        i = self._row_index_of_path(path)
        self.sel = i if i is not None else self.sel
        self._clamp()
        self._recompute_matches()

    def _toggle_expand(self, row=None):
        row = row or self._sel_row()
        if row is None:
            return
        p = tuple(row["path"])
        self.expanded[p] = not self.expanded.get(p, True)
        self._rebuild_rows_keep(row["path"])

    def _row_is_container(self, row):
        return not row["leaf"]

    def _parent_is_dict(self, row):
        if len(row["path"]) == 1:
            return self.root_is_dict
        parent, _ = self._parent_of(row)
        return isinstance(parent, dict)

    def _add_entry(self):
        # no rows means an empty tree, so the root is the container to
        # add into - this is the only way to fill a fresh plist
        row = self.rows[self.sel] if self.rows else None
        if row is None and not isinstance(self.root, (dict, list)):
            self._flash("the root is a {} value - nothing to add to".format(
                _type_name(self.root)), "red")
            return
        parent, anchor, _ = self._target_of_row(row)
        types = list(_KINDS.keys()) + ["dict", "array"]
        pick = self._menu("add entry - type", types)
        if pick is None:
            return
        tname = types[pick]
        if tname in ("dict", "array"):
            value = {} if tname == "dict" else []
        else:
            if tname == "uid" and not self._binary():
                self._flash("uid only survives in binary plists", "red")
                return
            if tname == "date":
                value = datetime.datetime.now().replace(microsecond=0)
            elif tname == "uid":
                value = _parse("0", "u")
            else:
                value = _NEW_DEFAULTS[tname]
        if isinstance(parent, dict):
            key = self._prompt("key name:", "")
            if key is None:
                return
            if key in parent:
                self._flash("key already exists: {}".format(key), "red")
                return
            if anchor is None:
                self._push_undo()
                parent[key] = value
            else:
                self._push_undo()
                self._dict_insert_after(parent, anchor, key, value)
        else:
            self._push_undo()
            if anchor is None:
                parent.append(value)
            else:
                parent.insert(int(anchor) + 1, value)
        self._after_mutate()
        self._flash("added {}".format(_type_name(value)), "grn")

    def _dict_insert_after(self, d, anchor, key, value):
        # dicts keep insertion order; rebuild with the new key after anchor
        items = list(d.items())
        out = {}
        for k, v in items:
            out[k] = v
            if k == anchor:
                out[key] = value
        self._replace_parent_dict(d, out)

    def _replace_parent_dict(self, old, new):
        # swap `old` for `new` wherever it sits under self.root
        if old is self.root:
            self.root = new
            return
        stack = [(self.root, None, None)]
        while stack:
            cur, parent, key = stack.pop()
            if cur is old:
                if isinstance(parent, dict):
                    # rebuild the parent, swapping the one entry in place
                    items = list(parent.items())
                    out = {}
                    for k, v in items:
                        out[k] = new if v is old else v
                    self._replace_parent_dict(parent, out)
                else:
                    parent[key] = new
                return
            if isinstance(cur, dict):
                for k, v in cur.items():
                    stack.append((v, cur, k))
            elif isinstance(cur, list):
                for i, v in enumerate(cur):
                    stack.append((v, cur, i))

    def _delete_row(self):
        row = self._sel_row()
        if row is None:
            return
        parent, last = self._parent_of(row)
        label = self._row_label(row)
        if isinstance(parent, dict):
            if not self._confirm("delete {}?".format(label)):
                return
            self._push_undo()
            if parent is self.root:
                items = list(parent.items())
                out = {k: v for k, v in items if k != last}
                self.root = out
            else:
                self._rebuild_dict_without(parent, last)
        elif isinstance(parent, list):
            if not self._confirm("delete {}?".format(label)):
                return
            self._push_undo()
            del parent[int(last)]
        else:
            self._flash("cannot delete the root value", "red")
            return
        self._after_mutate()
        self._flash("deleted {}".format(label), "grn")

    def _rebuild_dict_without(self, d, drop):
        items = list(d.items())
        out = {k: v for k, v in items if k != drop}
        self._replace_parent_dict(d, out)

    def _rename_row(self):
        row = self._sel_row()
        if row is None:
            return
        if not isinstance(row["key"], str):
            self._flash("array elements have no key to rename", "red")
            return
        if not self._parent_is_dict(row):
            return
        parent, last = self._parent_of(row)
        new = self._prompt("rename {} to:".format(last), last)
        if new is None or new == last:
            return
        if new in parent:
            self._flash("key already exists: {}".format(new), "red")
            return
        self._push_undo()
        items = list(parent.items())
        out = {}
        for k, v in items:
            if k == last:
                out[new] = v
            else:
                out[k] = v
        self._replace_parent_dict(parent, out)
        self._after_mutate()
        self._flash("renamed to {}".format(new), "grn")

    def _change_type(self):
        row = self._sel_row()
        if row is None:
            return
        if not row["leaf"]:
            self._flash("change type works on values, not containers", "red")
            return
        cur = _type_name(row["node"])
        options = [t for t in _KINDS if t != cur]
        pick = self._menu("change type (from {})".format(cur), options)
        if pick is None:
            return
        target = options[pick]
        kind = _KINDS[target]
        if target == "uid" and not self._binary():
            self._flash("uid only survives in binary plists", "red")
            return
        text = canonical(row["node"])
        if target == "string":
            new = text
        else:
            try:
                new = _parse(text, kind)
            except ValueError as e:
                self._flash("cannot convert: {}".format(e), "red")
                return
        if new == row["node"]:
            self._flash("already a {}".format(target))
            return
        self._push_undo()
        parent, last = self._parent_of(row)
        if isinstance(parent, dict):
            parent[last] = new
        else:
            parent[int(last)] = new
        self._after_mutate()
        self._flash("changed to {}".format(target), "grn")

    # ── converter (^t) ────────────────────────────────────────
    def _convert_value(self):
        # port of the tk gui's Convert Window, bound to the selected
        # value: pick from/to encodings, tweak the text, convert.
        # enter on the result writes the source back into the value
        # (interpreted as its own kind), so pasting foreign base64
        # or hex into a data field works in one trip.
        row = self._sel_row()
        if row is None:
            return
        if not row["leaf"]:
            self._flash("converter works on values, not containers", "red")
            return
        v = row["node"]
        kind = _type_name(v)
        if kind not in ("string", "data", "integer"):
            self._flash("converter works on string, data, and integer values", "red")
            return
        label = self._row_label(row)
        fi, ti = _convert_prefill(kind)
        f = self._menu("convert {} - from ({})".format(label, _CONV_NAMES[fi]),
                       list(_CONV_NAMES), sel=fi)
        if f is None:
            return
        t = self._menu("convert {} - to ({})".format(label, _CONV_NAMES[ti]),
                       list(_CONV_NAMES), sel=ti)
        if t is None:
            return
        fname, tname = _CONV_NAMES[f], _CONV_NAMES[t]
        text = self._prompt("convert ({} -> {}):".format(fname, tname),
                            canonical(v))
        if text is None:
            return
        if not text.strip() and kind != "string":
            self._flash("nothing to convert", "red")
            return
        try:
            result = _convert_text(text, fname, tname)
        except ValueError as e:
            self._flash(str(e), "red")
            return
        # result box: show the conversion, enter writes back
        w = self.W()
        chunk = max(w - 8, 12)
        lines = ["{}  ({} -> {})".format(label, fname, tname)]
        rl = result if len(result) <= chunk else result[:chunk - 1] + "\u2026"
        lines.append(rl)
        lines.append("")
        lines.append("enter = write source back as {}".format(kind))
        if not self._choice_box("convert", lines):
            self._flash("converted (not written)")
            return
        try:
            new = _convert_apply(kind, text, fname)
        except ValueError as e:
            self._flash(str(e), "red")
            return
        if new == v:
            self._flash("unchanged")
            return
        self._push_undo()
        parent, last = self._parent_of(row)
        if isinstance(parent, dict):
            parent[last] = new
        else:
            parent[int(last)] = new
        self._after_mutate()
        self._flash("converted \u2713", "grn")

    # ── insert from template (T) ──────────────────────────────
    def _insert_template(self):
        data = _template_data()
        if not data:
            self._flash("template data missing - Scripts/menu.plist not found", "red")
            return
        if not isinstance(self.root, dict):
            self._flash("template presets need a dictionary root", "red")
            return
        sections = sorted(s for s in data if isinstance(data[s], dict) and data[s])
        if not sections:
            self._flash("no template sections found", "red")
            return
        pick = self._menu("insert from template - section", sections)
        if pick is None:
            return
        section = sections[pick]
        paths = sorted(p for p in data[section]
                       if isinstance(data[section][p], list) and data[section][p])
        labels = [p.replace("Root/", "", 1) if p.startswith("Root/") else p
                  for p in paths]
        pick = self._menu("insert from template - {}".format(section), labels)
        if pick is None:
            return
        path = paths[pick]
        # presets are the entries with a name + types + value; separator
        # and title rows are menu furniture the terminal does not need
        presets = [e for e in data[section][path]
                   if isinstance(e, dict) and "name" in e
                   and "types" in e and "value" in e]
        if not presets:
            self._flash("no insertable presets under {}".format(labels[pick]), "red")
            return
        names = [e["name"] for e in presets]
        pick = self._menu("insert - {}".format(labels[pick]), names)
        if pick is None:
            return
        self._template_apply(path, presets[pick])

    def _template_apply(self, path, preset):
        # walk the preset's own path from the root, creating missing
        # containers (d = dict, a = array), then drop the value in:
        # arrays append, dicts merge keys. mirrors the tk gui's
        # merge_menu_preset, minus the drag-and-drop bookkeeping.
        types = str(preset.get("types", "")).split("/")
        value = preset.get("value")
        segs = [s for s in str(path).split("/") if s]
        if segs and segs[0].lower() == "root":
            segs, types = segs[1:], types[1:]
        if not segs or len(segs) != len(types) or not isinstance(value, dict):
            self._flash("malformed preset ({})".format(path), "red")
            return
        # walk until the first segment that is missing or the wrong
        # type - from there down everything gets (re)built fresh
        cur = self.root
        question = None
        replace_kind = None
        complete = True
        for seg, typ in zip(segs, types):
            want_list = str(typ).lower() == "a"
            if not isinstance(cur, dict):
                # an array sits mid-path; presets only descend dicts
                self._flash("preset path crosses an array ({})".format(path), "red")
                return
            if seg not in cur:
                complete = False
                break
            ex = cur[seg]
            good = isinstance(ex, list) if want_list else isinstance(ex, dict)
            if not good:
                question = "{} is a {} - replace it with {}?".format(
                    seg, _type_name(ex), "array" if want_list else "dict")
                replace_kind = "array" if want_list else "dict"
                complete = False
                break
            cur = ex
        if question is not None and not self._confirm(question):
            self._flash("template not applied")
            return
        if complete and isinstance(cur, dict):
            for k in value:
                if k in cur:
                    if not self._confirm("key {} already exists - replace it?".format(k)):
                        self._flash("template not applied")
                        return
        # apply (single undo step covers the whole insert)
        self._push_undo()
        cur = self.root
        for seg, typ in zip(segs, types):
            want_list = str(typ).lower() == "a"
            if isinstance(cur, dict):
                if seg not in cur or not (
                        isinstance(cur[seg], list) if want_list
                        else isinstance(cur[seg], dict)):
                    cur[seg] = [] if want_list else {}
                cur = cur[seg]
        if isinstance(cur, list):
            cur.append(copy.deepcopy(value))
            sel_path = segs + [len(cur) - 1]
        else:
            for k, v in value.items():
                cur[k] = copy.deepcopy(v)
            sel_path = segs + [list(value)[-1]]
        # expand the container path so the insert is visible, then jump to it
        for i in range(1, len(segs) + 1):
            self.expanded[tuple(segs[:i])] = True
        self._after_mutate()
        idx = self._row_index_of_path(sel_path)
        if idx is not None:
            self.sel = idx
        self._flash("inserted {}".format(preset.get("name", path)), "grn")

    def _duplicate_row(self):
        # copy the whole entry and insert it right after itself; dict keys
        # get a "copy" suffix that auto-increments on collision
        row = self._sel_row()
        if row is None:
            return
        parent, last = self._parent_of(row)
        payload = copy.deepcopy(row["node"])
        self._push_undo()
        if isinstance(parent, dict):
            base = "{} copy".format(last) if isinstance(last, str) else "copy"
            key, n = base, 2
            while key in parent:
                key = "{} {}".format(base, n)
                n += 1
            self._dict_insert_after(parent, last, key, payload)
            newpath = row["path"][:-1] + [key]
        elif isinstance(parent, list):
            i = int(last)
            parent.insert(i + 1, payload)
            newpath = row["path"][:-1] + [i + 1]
        else:
            return
        self._rebuild_rows_keep(newpath)
        self._flash("duplicated", "grn")

    def _sibling_jump(self, direction):
        # { / }: jump to the previous / next sibling of the current row
        row = self._sel_row()
        if row is None:
            return
        parent_path = tuple(row["path"][:-1])
        sib = [i for i, r in enumerate(self.rows)
               if tuple(r["path"][:-1]) == parent_path]
        if len(sib) < 2:
            self._flash("no siblings here")
            return
        pos = sib.index(self.sel)
        npos = pos + direction
        if not 0 <= npos < len(sib):
            self._flash("at the {} sibling".format("first" if direction < 0 else "last"))
            return
        self.sel = sib[npos]

    def _move_row(self, delta):
        row = self._sel_row()
        if row is None:
            return
        parent, last = self._parent_of(row)
        if isinstance(parent, dict):
            keys = list(parent.keys())
            i = keys.index(last)
            j = i + delta
            if not 0 <= j < len(keys):
                self._flash("already at the edge", "dim")
                return
            self._push_undo()
            other = keys[j]
            items = list(parent.items())
            out = {}
            for k, v in items:
                if k == last:
                    out[other] = parent[other]
                elif k == other:
                    out[last] = parent[last]
                else:
                    out[k] = v
            self._replace_parent_dict(parent, out)
        elif isinstance(parent, list):
            i = int(last)
            j = i + delta
            if not 0 <= j < len(parent):
                self._flash("already at the edge", "dim")
                return
            self._push_undo()
            parent[i], parent[j] = parent[j], parent[i]
        else:
            return
        self._after_mutate()
        if delta < 0 and self.sel > 0:
            self.sel -= 1
        elif delta > 0 and self.sel < len(self.rows) - 1:
            self.sel += 1
        self._flash("moved {}".format("up" if delta < 0 else "down"), "grn")

    # ── value editing ─────────────────────────────────────────
    def _edit_value(self):
        row = self._sel_row()
        if row is None:
            return
        if not row["leaf"]:
            self._toggle_expand(row)
            return
        v = row["node"]
        if isinstance(v, bool):
            self._push_undo()
            parent, last = self._parent_of(row)
            if isinstance(parent, dict):
                parent[last] = not v
            else:
                parent[int(last)] = not v
            self._after_mutate()
            self._flash("toggled to {}".format("true" if not v else "false"), "grn")
            return
        text = self._prompt("value ({}):".format(_type_name(v)), canonical(v))
        if text is None:
            return
        try:
            new = _parse(text, _KINDS[_type_name(v)])
        except ValueError as e:
            self._flash(str(e), "red")
            return
        if new == v:
            self._flash("unchanged")
            return
        self._push_undo()
        parent, last = self._parent_of(row)
        if isinstance(parent, dict):
            parent[last] = new
        else:
            parent[int(last)] = new
        self._after_mutate()
        self._flash("edited \u2713", "grn")

    # ── clipboard ─────────────────────────────────────────────
    def _copy_row(self, cut=False):
        row = self._sel_row()
        if row is None:
            return
        payload = copy.deepcopy(row["node"])
        from propertreecli import _plist_mod
        plist = _plist_mod()
        try:
            with open(self.clip_file, "wb") as f:
                plist.dump({"v": payload}, f, fmt=plist.FMT_XML, sort_keys=False)
        except Exception as e:
            self._flash("clipboard write failed: {}".format(e), "red")
            return
        if cut:
            if not row["leaf"] and not self._confirm(
                    "cut {} (its whole subtree)?".format(self._row_label(row))):
                return
            self._delete_row_no_confirm()
            self._flash("cut {}".format(self._row_label(row)), "grn")
        else:
            self._flash("copied {}".format(self._row_label(row)), "grn")

    def _delete_row_no_confirm(self):
        row = self._sel_row()
        if row is None:
            return
        parent, last = self._parent_of(row)
        self._push_undo()
        if isinstance(parent, dict):
            if parent is self.root:
                self.root = {k: v for k, v in parent.items() if k != last}
            else:
                self._rebuild_dict_without(parent, last)
        else:
            del parent[int(last)]
        self._after_mutate()

    def _paste(self):
        if not os.path.exists(self.clip_file):
            self._flash("clipboard is empty", "red")
            return
        from propertreecli import _plist_mod
        try:
            with open(self.clip_file, "rb") as f:
                data = _plist_mod().load(f)
            payload = data["v"]
        except Exception as e:
            self._flash("clipboard read failed: {}".format(e), "red")
            return
        row = self.rows[self.sel] if self.rows else None
        if row is None and not isinstance(self.root, (dict, list)):
            self._flash("the root is a {} value - nothing to paste into".format(
                _type_name(self.root)), "red")
            return
        parent, anchor, _ = self._target_of_row(row)
        if isinstance(parent, dict):
            default = (str(row["key"])
                       if row is not None and isinstance(row["key"], str) else "")
            key = self._prompt("paste as key:", default)
            if key is None:
                return
            if key in parent:
                self._flash("key already exists: {}".format(key), "red")
                return
            self._push_undo()
            if anchor is None:
                parent[key] = payload
            else:
                self._dict_insert_after(parent, anchor, key, payload)
        else:
            self._push_undo()
            if anchor is None:
                parent.append(payload)
            else:
                parent.insert(int(anchor) + 1, payload)
        self._after_mutate()
        self._flash("pasted \u2713", "grn")

    def _node_at(self, path):
        cur = self.root
        for seg in path:
            cur = cur[seg] if isinstance(cur, dict) else cur[int(seg)]
        return cur

    def _row_label(self, row):
        if isinstance(row["key"], str):
            return row["key"]
        return "#{} ({})".format(row["key"], _type_name(row["node"]))

    def _binary(self):
        return self.fmt == "binary"

    # ── find ──────────────────────────────────────────────────
    _SCOPES = ("keys", "values", "both")

    def _find(self):
        # tab inside the prompt cycles keys -> values -> both; the last
        # used scope sticks for n/N and R until the next / search
        start = self._SCOPES.index(self.find_scope)
        q = self._prompt("find:", self.find or "",
                         cycle=self._SCOPES, cycle_i=start)
        if q is None:
            return
        self.find_scope = self._SCOPES[self._cycle_i % len(self._SCOPES)]
        if q == "":
            self.find = None
            self.matches = []
            self._flash("find cleared")
            return
        self.find = q
        self._recompute_matches()
        if not self.matches:
            self._flash("no {} match for '{}'".format(self.find_scope, q), "red")
            return
        # jump to the first match at or after the selection
        pos = next((i for i in self.matches if i >= self.sel), self.matches[0])
        self.match_idx = self.matches.index(pos)
        self._goto(pos)
        self._flash("match {}/{} ({})".format(self.match_idx + 1, len(self.matches),
                                              self.find_scope), "grn")

    def _find_step(self, d):
        if not self.matches:
            self._flash("no active find (press /)", "red")
            return
        self.match_idx = (self.match_idx + d) % len(self.matches)
        self._goto(self.matches[self.match_idx])
        self._flash("match {}/{} ({})".format(self.match_idx + 1, len(self.matches),
                                              self.find_scope), "grn")

    def _replace_all(self):
        if not self.find:
            self._flash("no active find (press / first)", "red")
            return
        if self.find_scope == "keys":
            self._flash("replace works on values - press / then tab to scope=values", "red")
            return
        q = self.find
        repl = self._prompt("replace '{}' with:".format(q), "")
        if repl is None:
            return
        count = 0

        def fix(v):
            nonlocal count
            if isinstance(v, dict):
                return {k: fix(x) for k, x in v.items()}
            if isinstance(v, list):
                return [fix(x) for x in v]
            if isinstance(v, str) and q in v:
                count += 1
                return v.replace(q, repl)
            return v

        self._push_undo()
        self.root = fix(self.root)
        self._after_mutate()
        if count:
            self._flash("replaced {} in string values".format(count), "grn")
        else:
            self._flash("no string values matched (keys are left alone)", "red")
            self._undo()

    # ── popups ────────────────────────────────────────────────
    def _box(self, title, lines, width=None, color="frost"):
        h, w = self.H(), self.W()
        width = width or min(max(len(title) + 4, max(len(l) for l in lines) + 4), w - 4)
        height = len(lines) + 4
        top = max((h - height) // 2, 0)
        left = max((w - width) // 2, 0)
        self.s.move(top, 0)  # force a sync point
        border = P("brand" if color == "brand" else "frost", bold=True)
        self.s.addstr(top, left, "\u2554" + "\u2550" * (width - 2) + "\u2557", border)
        self.s.addstr(top + 1, left, "\u2551" + " " * (width - 2) + "\u2551", border)
        t = title[: width - 4]
        pad = width - 2 - len(t)
        self.s.addstr(top + 1, left + 1, " " * (pad // 2) + t + " " * (pad - pad // 2), P("frost", bold=True))
        for i, l in enumerate(lines):
            self.s.addstr(top + 2 + i, left, "\u2551", border)
            self.s.addstr(top + 2 + i, left + 1, " " * (width - 2), P("dim"))
            self.s.addstr(top + 2 + i, left + 1, l[: width - 2])
            self.s.addstr(top + 2 + i, left + width - 1, "\u2551", border)
        self.s.addstr(top + height - 1, left,
                      "\u255a" + "\u2550" * (width - 2) + "\u255d", border)

    def _menu(self, title, items, sel=0):
        # centered pick list; returns index or None. j/k or arrows move,
        # enter picks, esc cancels.
        h, w = self.H(), self.W()
        sel = sel % len(items)
        top = 0
        while True:
            self._draw()
            shown = items
            rows_h = min(len(shown), h - 6)
            offset = min(max(sel - rows_h + 1, 0), max(len(shown) - rows_h, 0))
            vis = shown[offset:offset + rows_h]
            width = min(max(len(title) + 6, max(len(i) for i in vis) + 8), w - 4)
            top = max((h - len(vis) - 4) // 2, 0)
            left = max((w - width) // 2, 0)
            self._box(title, [" " * (width - 4)] * len(vis), width)
            for i, item in enumerate(vis):
                y = top + 3 + i
                x = left + 2
                if offset + i == sel:
                    self.s.addstr(y, x, "{:>2}.".format(offset + i + 1), P("frost", bold=True) | curses.A_REVERSE)
                    self.s.addstr(y, x + 3, item, curses.A_REVERSE | P("frost", bold=True))
                else:
                    self.s.addstr(y, x, "{:>2}.".format(offset + i + 1), P("frost", bold=True))
                    self.s.addstr(y, x + 3, item)
            self.s.refresh()
            ch = self.s.getch()
            if ch in (ord("j"), curses.KEY_DOWN):
                sel = min(sel + 1, len(items) - 1)
            elif ch in (ord("k"), curses.KEY_UP):
                sel = max(sel - 1, 0)
            elif ch in (curses.KEY_NPAGE,):
                sel = min(sel + rows_h, len(items) - 1)
            elif ch in (curses.KEY_PPAGE,):
                sel = max(sel - rows_h, 0)
            elif ch in (10, 13, curses.KEY_ENTER, ord(" ")):
                return sel
            elif ch in (27, ord("q")):
                return None
        return None

    def _confirm(self, question):
        m = self._menu(question, ["yes", "no"], sel=1)
        return m == 0

    def _help(self):
        lines = [
            "move        arrows, j/k, g/G, home/end, pgup/pgdn",
            "page        ctrl+d / ctrl+u (half screen)",
            "siblings    { }  jump to the prev/next sibling",
            "fold        left/right or space, enter on a container",
            "edit        enter on a value (booleans toggle)",
            "add         i  (into a container, else as sibling)",
            "            an empty plist has no rows: i fills the root",
            "duplicate   D  (copies under a new key / array slot)",
            "delete      d  (asks first, even for leaves)",
            "rename      r  (dict keys)",
            "type        t  (scalar conversions)",
            "convert     ^t (text: ascii/base64/decimal/hex/binary)",
            "template    T  (insert OC/Clover presets from menu.plist)",
            "move entry  <  >  (reorder inside its parent)",
            "copy/cut/paste   c  x  p  (shared /tmp clipboard)",
            "undo/redo   u / ctrl+r (200 steps)",
            "find        /  then n / N to cycle, esc clears",
            "            tab inside the prompt: keys / values / both",
            "replace     R  (replace-all in string values, values scope)",
            "save        ctrl+s  or F2",
            "quit        q  (save prompt when dirty)",
            "",
            "writes are atomic and verified; the file keeps its format",
            "and key order. esc cancels prompts. ? shows this again.",
        ]
        self._static_box("plist - keybinds", lines)

    def _static_box(self, title, lines):
        self._draw()
        h, w = self.H(), self.W()
        width = min(max(len(title) + 6, max(len(l) for l in lines) + 6), w - 4)
        vis = lines[: max(h - 6, 1)]
        top = max((h - len(vis) - 4) // 2, 0)
        left = max((w - width) // 2, 0)
        self._box(title, [" " * (width - 4)] * len(vis), width)
        for i, l in enumerate(vis):
            y = top + 3 + i
            self.s.addstr(y, left + 2, l[: width - 4])
        self.s.refresh()
        while True:
            ch = self.s.getch()
            if ch != -1:
                return

    def _choice_box(self, title, lines):
        # like _static_box, but enter = yes and esc = no so callers
        # can branch on the answer
        self._draw()
        h, w = self.H(), self.W()
        width = min(max(len(title) + 6, max(len(l) for l in lines) + 6), w - 4)
        vis = lines[: max(h - 6, 1)]
        top = max((h - len(vis) - 4) // 2, 0)
        left = max((w - width) // 2, 0)
        self._box(title, [" " * (width - 4)] * len(vis), width)
        for i, l in enumerate(vis):
            y = top + 3 + i
            self.s.addstr(y, left + 2, l[: width - 4])
        self.s.refresh()
        while True:
            ch = self.s.getch()
            if ch in (10, 13, curses.KEY_ENTER):
                return True
            if ch in (27, ord("q"), ord("n")):
                return False
            if ch != -1:
                return False

    # ── prompt line ───────────────────────────────────────────
    def _prompt(self, label, prefill="", cycle=None, cycle_i=0):
        # blocking line editor on the status row; returns text or None.
        # cycle = optional list of modes shown in the label; tab steps
        # through them and the pick lands in self._cycle_i.
        buf = list(prefill)
        pos = len(buf)
        self._cycle_i = cycle_i % len(cycle) if cycle else 0
        while True:
            h, w = self.H(), self.W()
            lab = label
            if cycle:
                lab = "{} <{}>".format(label, cycle[self._cycle_i])
            self._draw()
            y = h - 3
            self.s.move(y, 0)
            self.s.clrtoeol()
            self.s.addstr(y, 0, " " + lab + " ", P("frost", bold=True))
            x0 = len(lab) + 2
            show = "".join(buf)
            # window the buffer so the caret stays visible
            avail = max(w - x0 - 1, 1)
            if len(show) <= avail:
                win = 0
            elif pos >= avail:
                win = min(pos - avail + 1, len(show) - avail)
            else:
                win = 0
            view = show[win:win + avail]
            self.s.addstr(y, x0, view, curses.A_UNDERLINE)
            try:
                self.s.move(y, x0 + (pos - win))
            except curses.error:
                pass
            self.s.refresh()
            ch = self.s.getch()
            if ch in (9,) and cycle:  # tab: cycle the mode
                self._cycle_i = (self._cycle_i + 1) % len(cycle)
                continue
            if ch in (27,):
                return None
            if ch in (10, 13, curses.KEY_ENTER):
                return "".join(buf)
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                if pos > 0:
                    del buf[pos - 1]
                    pos -= 1
            elif ch in (21,):  # ctrl+u: clear line
                buf = []
                pos = 0
            elif ch == curses.KEY_LEFT:
                pos = max(pos - 1, 0)
            elif ch == curses.KEY_RIGHT:
                pos = min(pos + 1, len(buf))
            elif ch in (curses.KEY_HOME,):
                pos = 0
            elif ch in (curses.KEY_END,):
                pos = len(buf)
            elif 32 <= ch < 127:
                buf.insert(pos, chr(ch))
                pos += 1

    # ── drawing ───────────────────────────────────────────────
    def _draw(self, status=None):
        self.s.erase()
        h, w = self.H(), self.W()
        if h < 10 or w < 30:
            self.s.addstr(0, 0, "terminal too small for the editor")
            self.s.refresh()
            return
        # header
        dirty = "*" if self.dirty else ""
        name = self.path
        if len(name) + 20 > w:
            name = "..." + name[-(w - 23):]
        self.s.addstr(0, 0, " " + name, P("frost", bold=True))
        x = len(name) + 2
        fmt = "binary" if self.path.endswith("plist") and self._binary() else "xml"
        self.s.addstr(0, x, "[{}]".format(fmt), P("dim"))
        if self.dirty:
            self.s.addstr(0, x + len(fmt) + 2, dirty, P("amb", bold=True))
        right = "? help   q quit   ^s save"[: max(w - 30, 1)]
        self.s.addstr(0, max(w - len(right) - 1, x + 10), right, P("dim"))
        try:
            self.s.addstr(1, 0, " " + "\u2500" * (w - 1), P("dim"))
        except curses.error:
            pass

        # tree
        body_top, body_bot = 2, h - 4
        list_h = body_bot - body_top
        if self.sel < self.top:
            self.top = self.sel
        if self.sel >= self.top + list_h:
            self.top = self.sel - list_h + 1
        self._keyw = 0
        for r in self.rows[self.top:self.top + list_h]:
            kt = str(r["key"])
            self._keyw = max(self._keyw, min(len(kt), 26))
        self._keyw = min(max(self._keyw, 8), 26)
        for i, r in enumerate(self.rows[self.top:self.top + list_h]):
            y = body_top + i
            self._draw_row(y, r, self.top + i == self.sel, self.top + i)
        if not self.rows:
            self._draw_empty(body_top)
        # footer / status
        self._draw_status(status)

    def _draw_empty(self, y):
        # an empty root draws no rows: say what the file is and how to
        # fill it rather than leaving the body blank
        if self.root_is_dict:
            what = "dictionary"
        elif self.root_is_list:
            what = "array"
        else:
            what = "{} value".format(_type_name(self.root))
        self.s.addstr(y, 2, "(empty {} root)".format(what), P("dim"))
        hint = "press "
        self.s.addstr(y + 1, 2, hint, P("dim"))
        self.s.addstr(y + 1, 2 + len(hint), "i", P("frost", bold=True))
        hint2 = " to add the first entry, or "
        self.s.addstr(y + 1, 2 + len(hint) + 1, hint2, P("dim"))
        self.s.addstr(y + 1, 2 + len(hint) + 1 + len(hint2), "T", P("frost", bold=True))
        self.s.addstr(y + 1, 2 + len(hint) + 2 + len(hint2),
                      " for an OpenCore preset", P("dim"))

    def _row_value_text(self, r):
        if not r["leaf"]:
            if r["count"] == 0:
                return "(empty)"
            collapsed = not self.expanded.get(tuple(r["path"]), True)
            if collapsed:
                return "{} entries".format(r["count"])
            return ""
        v = r["node"]
        t = canonical(v)
        return _esc(t)

    def _draw_row(self, y, r, selected, abs_idx):
        w = self.W()
        indent = " " * (2 + r["depth"] * 2)
        if not r["leaf"]:
            arrow = "\u25be" if self.expanded.get(tuple(r["path"]), True) else "\u25b8"
        else:
            arrow = " "
        x = 0
        key = str(r["key"])
        if isinstance(r["key"], int):
            keypair = P("dim")
        else:
            # blue by depth: top-level keys keep plain frost, nested keys
            # stay the same hue, slightly desaturated (d1..d6, clamped)
            keypair = P("d{}".format(min(r["depth"], 6)), bold=True)
        # pad key to the column width
        key_txt = key[: self._keyw]
        if len(key) > self._keyw:
            key_txt = key[: self._keyw - 1] + "\u2026"
        segments = []
        if not r["leaf"]:
            segments.append((indent + arrow + " ", P("dim")))
        else:
            segments.append((indent + "  ", P("dim")))
        segments.append((key_txt.ljust(self._keyw) + " ", keypair))
        segments.append((_type_name(r["node"]).ljust(9), P("dim")))
        vc = value_color_name(r["node"])
        vt = self._row_value_text(r)
        seg_col = P("grn") if vc == "grn" else (P("dim") if vc == "dim" else 0)
        match = bool(self.find) and abs_idx in self.matches
        if selected:
            # frost selection bar, dark text
            for txt, attr in segments:
                try:
                    self.s.addstr(y, x, txt, curses.color_pair(7) | curses.A_BOLD)
                except curses.error:
                    pass
                x += len(txt)
            try:
                self.s.addstr(y, x, vt, curses.color_pair(7) | curses.A_BOLD)
                self.s.addstr(y, x + len(vt), " " * (w - x - len(vt)), curses.color_pair(7))
            except curses.error:
                pass
        else:
            for txt, attr in segments:
                try:
                    self.s.addstr(y, x, txt, attr)
                except curses.error:
                    pass
                x += len(txt)
            try:
                if match:
                    self.s.addstr(y, x, vt, P("amb"))
                else:
                    self.s.addstr(y, x, vt, seg_col)
            except curses.error:
                pass

    def _draw_status(self, status=None):
        h, w = self.H(), self.W()
        y = h - 3
        self.s.move(y, 0)
        self.s.clrtoeol()
        mode = status or "normal"
        self.s.addstr(y, 0, " " + mode, P("frost", bold=True))
        if self.find:
            m = "find: {}  ({})".format(self.find, len(self.matches))
            self.s.addstr(y, len(mode) + 2, m, P("amb"))
        if self.msg:
            xx = len(mode) + 2 + (len("find: ") + len(self.find or "") + 4 if self.find else 0)
            room = max(w - xx - 3, 1)
            self.s.addstr(y, min(xx + 2, w - 1), self.msg[:room], P(self.msg_color))
        self.s.move(h - 2, 0)
        self.s.clrtoeol()
        self.s.addstr(h - 2, 0, " " + "\u2500" * (w - 1), P("dim"))
        legend = ("\u2191\u2193 move  \u2190\u2192 fold  enter edit  i add  d del  "
                  "c/x/p copy cut paste  u undo  / find  ? help").strip()
        # never occupy the bottom-right cell: ncurses errors on it
        self.s.addstr(h - 1, 0, (" " + legend)[: w - 1], P("dim"))

    # ── main loop ─────────────────────────────────────────────
    def run(self):
        self._build_rows()
        self._flash("arrow keys to move - ? for help", "dim")
        while True:
            self._draw()
            self.s.refresh()
            ch = self.s.getch()
            try:
                if self._handle(ch):
                    return
            except Exception as e:
                with open(self.log, "a") as f:
                    f.write(traceback.format_exc())
                self._flash("error: {} (see {})".format(e, self.log), "red")

    def _move_sel(self, d):
        # d is -1 (up) or 1 (down). holding a direction accelerates
        # smoothly: a fractional accumulator adds roughly 1 row per
        # repeat plus a slowly growing ramp, so the step size drifts
        # 1 -> 2 -> 3 -> 4 over a few seconds of holding instead of
        # jumping between fixed tiers. no teleporting half-pages.
        now = time.monotonic()
        if d == self._hold_dir and (now - self._mv_last) < 0.4:
            self._ramp = min(self._ramp + 0.03, 2.2)
        else:
            self._hold_dir = d
            self._ramp = 0.03
            self._frac = 0.0
        self._mv_last = now
        self._frac += 1.0 + self._ramp
        step = int(self._frac)
        self._frac -= step
        if d < 0:
            self.sel = max(self.sel - step, 0)
        else:
            self.sel = min(self.sel + step, self._last())

    def _handle(self, ch):
        if ch == -1:
            return None
        if ch not in (ord("j"), ord("k"), curses.KEY_DOWN, curses.KEY_UP):
            # any other key breaks the hold-acceleration ramp
            self._hold_dir = 0
            self._ramp = 0.0
            self._frac = 0.0
        r = self.sel
        if ch in (ord("j"), curses.KEY_DOWN):
            self._move_sel(1)
        elif ch in (ord("k"), curses.KEY_UP):
            self._move_sel(-1)
        elif ch in (ord("g"),):
            self.sel = 0
        elif ch in (ord("G"),):
            self.sel = self._last()
        elif ch in (curses.KEY_NPAGE,):
            self.sel = min(self.sel + self.H() - 6, self._last())
        elif ch in (curses.KEY_PPAGE,):
            self.sel = max(self.sel - (self.H() - 6), 0)
        elif ch in (curses.KEY_LEFT, ord("h")):
            if not self.rows:
                return None
            row = self.rows[self.sel]
            p = tuple(row["path"])
            if not row["leaf"] and self.expanded.get(p, True):
                self._toggle_expand(row)
            elif len(row["path"]) > 1:
                # folded already: jump to the parent row
                target = tuple(row["path"][:-1])
                i = self._row_index_of_path(target)
                if i is not None:
                    self.sel = i
        elif ch in (curses.KEY_RIGHT, ord("l"), ord(" ")):
            if not self.rows:
                return None
            row = self.rows[self.sel]
            p = tuple(row["path"])
            if not row["leaf"] and not self.expanded.get(p, True):
                self._toggle_expand(row)
        elif ch in (ord("{"),):
            self._sibling_jump(-1)
        elif ch in (ord("}"),):
            self._sibling_jump(1)
        elif ch in (4, 21):  # ctrl+d / ctrl+u: half a page
            step = max((self.H() - 6) // 2, 1)
            if ch == 4:
                self.sel = min(self.sel + step, self._last())
            else:
                self.sel = max(self.sel - step, 0)
        elif ch in (curses.KEY_HOME,):
            self.sel = 0
        elif ch in (curses.KEY_END,):
            self.sel = self._last()
        elif ch in (10, 13, curses.KEY_ENTER):
            self._edit_value()
        elif ch in (ord("i"), curses.KEY_IC):
            self._add_entry()
        elif ch in (ord("D"),):
            self._duplicate_row()
        elif ch == ord("d"):
            self._delete_row()
        elif ch == ord("r"):
            self._rename_row()
        elif ch == ord("t"):
            self._change_type()
        elif ch in (20,):  # ctrl+t: the value converter (tk gui parity)
            self._convert_value()
        elif ch == ord("T"):
            self._insert_template()
        elif ch in (ord("c"),):
            self._copy_row(cut=False)
        elif ch in (ord("x"),):
            self._copy_row(cut=True)
        elif ch in (ord("p"),):
            self._paste()
        elif ch in (ord("u"), 26):  # u or ctrl+z
            self._undo()
        elif ch in (18, 25):  # ctrl+r or ctrl+y
            self._redo()
        elif ch == ord("R"):
            self._replace_all()
        elif ch == ord("/"):
            self._find()
        elif ch in (ord("n"),):
            self._find_step(1)
        elif ch in (ord("N"),):
            self._find_step(-1)
        elif ch == ord("<"):
            self._move_row(-1)
        elif ch == ord(">"):
            self._move_row(1)
        elif ch == 27:  # esc: clear find / close overlays
            if self.find:
                self.find = None
                self.matches = []
                self._flash("find cleared")
        elif ch in (ord("?"),):
            self._help()
        elif ch in (ord("q"), 3):  # q or ctrl+c
            c = self._confirm_dirty()
            if c == "y":
                if not self._save():
                    return None
                return True
            if c == "n":
                return True
        elif ch in (19, curses.KEY_F2):  # ctrl+s or F2
            self._save()
        elif ch == curses.KEY_RESIZE:
            pass
        return None

def run_editor(root, path):
    # main entry: wraps everything in curses and returns an exit code
    def app(stdscr):
        try:
            locale.setlocale(locale.LC_ALL, "")
        except locale.Error:
            pass
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        stdscr.keypad(True)
        # stay in cbreak (keypad escape parsing needs it) but drop IXON so
        # ctrl+s arrives as a key instead of pausing output, and ISIG so
        # ctrl+c arrives as a key (quit-with-confirm) instead of a signal
        try:
            import termios as _termios
            _a = _termios.tcgetattr(sys.stdin.fileno())
            _a[0] &= ~_termios.IXON
            _a[3] &= ~_termios.ISIG
            _termios.tcsetattr(sys.stdin.fileno(), _termios.TCSANOW, _a)
        except Exception:
            pass
        _init_colors()
        ed = Editor(stdscr, root, path)
        ed.run()

    try:
        curses.wrapper(app)
        return 0
    except KeyboardInterrupt:
        return 130

if __name__ == "__main__":
    print("plist_tui is a module - run it through propertreecli.py")
