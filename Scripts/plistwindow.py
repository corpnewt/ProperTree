#!/usr/bin/env python
import sys, os, plistlib, base64, binascii, datetime, tempfile, shutil, re, subprocess, math, hashlib, time

from collections import OrderedDict, deque
from io import BytesIO
from Scripts import config_tex_info, plist

try:
    # Python 2
    import Tkinter as tk
    import ttk
    import tkFileDialog as fd
    import tkMessageBox as mb
    from tkFont import Font
    from itertools import izip_longest as izip
    from StringIO import StringIO
except ImportError:
    # Python 3
    import tkinter as tk
    import tkinter.ttk as ttk
    from tkinter import filedialog as fd
    from tkinter import messagebox as mb
    from tkinter.font import Font
    from itertools import zip_longest as izip
    long = int
    unicode = str
    basestring = str
    from io import StringIO

class EntryPlus(ttk.Entry):
    def __init__(self,parent,master,controller,**kw):
        tk.Entry.__init__(self, parent, **kw)

        self.parent = parent
        self.master = master
        self.controller = controller

        key = "Command" if str(sys.platform) == "darwin" else "Control"
        self.bind("<{}-a>".format(key), self.select_all)
        self.bind("<{}-c>".format(key), self.copy)
        self.bind("<{}-v>".format(key), self.paste)
        self.bind("<Left>", self.goto_left)
        self.bind("<Right>", self.goto_right)
        self.bind("<Shift-Left>", self.select_left)
        self.bind("<Shift-Right>", self.select_right)
        self.bind("<Shift-Up>", self.select_prior)
        self.bind("<Shift-Down>", self.select_after)
        self.bind("<Up>", self.goto_start)
        self.bind("<Down>", self.goto_end)
        self.bind("<Escape>", self.clear_selection)
        self.bind("<Shift-Button-1>",self.selection_clicked)
        self.bind("<Double-Shift-Button-1>",self.selection_double_clicked)

    def selection_clicked(self, event=None):
        return self.selection_click(event)

    def selection_double_clicked(self, event=None):
        return self.selection_click(event,selection_type="word")

    def selection_click(self, event, selection_type="click"):
        if not event:
            # Skip if our event is borked
            return
        try:
            # Get our current icursor index
            index = self.index(tk.INSERT)
            # Try to get the closest gap to our event
            closest_gap = self.controller.tk.call("ttk::entry::ClosestGap",self._w,event.x)
            # Default values for start/end
            start = end = index
            # Let's check for a selection
            if self.selection_present():
                # We're adjusting an existing selection
                start = self.index(tk.SEL_FIRST)
                end   = self.index(tk.SEL_LAST)
            def get_bounds(call,word,index,fallback=0):
                g = int(self.controller.tk.call(call,word,index))
                return g if g != -1 else fallback
            # Figure out which we're updating
            if index == start:
                if selection_type == "word":
                    # Select the whole word
                    closest_gap = get_bounds(
                        "tcl_wordBreakBefore",
                        self.get(),
                        closest_gap
                    )
                start = closest_gap
            else:
                if selection_type == "word":
                    # Select the whole word
                    word = self.get()
                    closest_gap = get_bounds(
                        "tcl_wordBreakAfter",
                        word,
                        closest_gap,
                        len(word)
                    )
                end = closest_gap
            # Set our selection
            self.icursor(closest_gap)
            self.selection_range(
                min(start,end),
                max(start,end)
            )
            return 'break'
        except:
            pass

    def clear_selection(self, event=None):
        self.selection_range(0, 0)
        return 'break'

    def set_icursor(self, position):
        self.icursor(position)
        # Attempt to show the cursor after setting - should scroll the
        # widget in most cases.
        try:
            self.controller.tk.call("ttk::entry::See",self._w,position)
        except:
            pass

    def select_prior(self, *ignore):
        try:
            if self.index(tk.INSERT) == self.index(tk.SEL_LAST):
                # Just set the cursor position
                return self.goto_left_right()
            else:
                self.selection_range(0,tk.SEL_LAST)
        except:
            self.selection_range(0,self.index(tk.INSERT))
        self.set_icursor(0)
        return 'break'

    def select_after(self, *ignore):
        try:
            if self.index(tk.INSERT) == self.index(tk.SEL_FIRST):
                # Just set the cursor position
                return self.goto_left_right(left=False)
            else:
                self.selection_range(tk.SEL_FIRST,tk.END)
        except:
            self.selection_range(self.index(tk.INSERT),tk.END)
        self.set_icursor(tk.END)
        return 'break'

    def select_left_right(self, amount=-1):
        index = self.index(tk.INSERT)
        # Check if we have a valid amount, and if we have room
        # to move - or just bail.
        if not isinstance(amount, int) or amount == 0 or \
        (amount < 0 and index == 0) or \
        (amount > 0 and index == self.index(tk.END)):
            return 'break'
        # Get the baseline values
        if self.selection_present():
            try:
                start = self.index(tk.SEL_FIRST)
                end   = self.index(tk.SEL_LAST)
            except:
                # Default to the index
                start = end = index
        else:
            start = end = index
        # Clamp the index
        new_index = min(max(0,index + amount),self.index(tk.END))
        # Figure out which we're updating
        if index == start:
            start = new_index
        else:
            end = new_index
        # Set our selection
        self.set_icursor(new_index)
        self.selection_range(
            min(start,end),
            max(start,end)
        )
        return 'break'

    def select_left(self, *ignore):
        return self.select_left_right(amount=-1)

    def select_right(self, *ignore):
        return self.select_left_right(amount=1)

    def select_all(self, *ignore):
        self.selection_range(0,tk.END)
        self.set_icursor(tk.END)
        # returns 'break' to interrupt default key-bindings
        return 'break'

    def goto_start(self, event=None):
        self.selection_range(0, 0)
        self.set_icursor(0)
        return 'break'

    def goto_end(self, event=None):
        self.selection_range(0, 0)
        self.set_icursor(tk.END)
        return 'break'

    def goto_left_right(self, left=True):
        try:
            target = self.index(
                tk.SEL_FIRST if left else tk.SEL_LAST
            )
            # We have some text selected, clear it
            # and set the cursor at the left or right
            # as needed
            self.selection_range(0, 0)
            self.set_icursor(target)
        except:
            # No selection - just move the cursor
            # to the left or right if possible
            if left:
                cursor = max(0,self.index(tk.INSERT)-1)
            else:
                cursor = min(len(self.get()),self.index(tk.INSERT)+1)
            self.set_icursor(cursor)
        return 'break'

    def goto_left(self, event=None):
        return self.goto_left_right()

    def goto_right(self, event=None):
        return self.goto_left_right(left=False)
    
    def copy(self, event=None):
        try:
            get = self.selection_get()
        except:
            get = ""
        if not len(get):
            return 'break'
        # Use the _clipboard_append method of the controller
        # if passed, otherwise fall back to the master's
        # clipboard_append which may not roll over to the
        # system clipboard
        if hasattr(self.controller,"_clipboard_append"):
            self.controller._clipboard_append(get)
        else:
            self.master.clipboard_append(get)
        self.update()
        return 'break'

    def paste(self, event=None):
        try:
            contents = self.master.clipboard_get()
        except:
            contents = ""
        if len(contents):
            try:
                get = self.selection_get()
            except:
                get = ""
            if len(get):
                # Have a selection - let's get the first and last
                start = self.index(tk.SEL_FIRST)
                end   = self.index(tk.SEL_LAST)
                self.delete(start,end)
            else:
                start = self.index(tk.INSERT)
            self.insert(start,contents)
            self.set_icursor(start+len(contents))
        return 'break'

class EntryPopup(EntryPlus):
    def __init__(self, parent, master, controller, text, cell, column, **kw):
        EntryPlus.__init__(self, parent, master, controller, **kw)

        self.original_text = text
        self.insert(0, text)
        self['state'] = 'normal'
        self['readonlybackground'] = 'white'
        self['selectbackground'] = '#1BA1E2'
        self['exportselection'] = True

        self.cell = cell
        self.column = column
        self['font'] = Font(font=self.master.font)

        self.focus_force()
        
        self.bind("<Key>",self.reveal)
        self.bind("<Escape>", lambda x:[self.reveal(x),self.cancel(x)])
        self.bind("<Return>", lambda x:[self.reveal(x),self.confirm(x)])
        self.bind("<KP_Enter>", lambda x:[self.reveal(x),self.confirm(x)])
        self.bind("<Up>", lambda x:[self.reveal(x),self.goto_start(x)])
        self.bind("<Down>", lambda x:[self.reveal(x),self.goto_end(x)])
        self.bind("<Tab>", lambda x:[self.reveal(x),self.next_field(x)])
        self.bind("<FocusOut>", self.focus_out)

        # Lock to avoid prematurely cancelling on focus_out
        self.confirming = False
        self.controller.tk.after(0,self.select_all)

    def reveal(self, event=None):
        # Make sure we're visible if editing
        self.parent.see(self.cell)
        self.relocate()

    def focus_out(self, event=None):
        if self.confirming: return # Don't do anything if we're still confirming
        if self.master.focus_get():
            # Pass True as the event to allow the bell() when our window still
            # has focus (means we're actively editing)
            self.confirm(event=True)
        else:
            # Pass None as the event to prevent the bell()
            self.confirm(no_prompt=True)

    def relocate(self, event=None):
        # Helper called when the window is scrolled to move the popup
        bbox = self.parent.bbox(self.cell, column=self.column)
        if bbox:
            # Move the entry to accommodate the new cell bbox
            x,y,width,height = bbox
            pady = height//2
            self.place(x=x,y=y+pady,anchor="w",width=width)
        elif self.winfo_viewable():
            # Entry left the visible area, and our popup is still visible,
            # hide it
            self.place_forget()

    def cancel(self, event=None):
        # Destroy ourself, then force the parent to focus
        self.destroy()
        self.master.entry_popup = None
        self.parent.focus_force()

    def next_field(self, event=None):
        # We need to determine if our other field can be edited
        # and if so - trigger another double click event there
        edit_col = None
        if self.column == "#0":
            check_type = self.master.get_check_type(self.cell).lower()
            # We are currently in the key column
            if check_type in ("dictionary","array","boolean"):
                # Can't edit the other field with these, or they require
                # a popup menu which is handled via other keybinds - bail
                return 'break'
            edit_col = "#2"
        elif self.column == "#2":
            # It's the value column - let's see if we can edit the key
            parent = self.master._tree.parent(self.cell)
            check_type = "dictionary" if not len(parent) else self.master.get_check_type(parent).lower()
            if check_type == "array" or self.cell == self.master.get_root_node():
                # Can't edit array keys - as they're just indexes
                return 'break'
            edit_col = "#0"
        if edit_col:
            # Let's get the bounding box for our other field
            x,y,width,height = self.master._tree.bbox(self.cell, edit_col)
            # Create an event
            e = tk.Event
            e.x, e.y, e.x_root, e.y_root = x+5, y+5, 0, 0
            self.master.on_double_click(e)
            return 'break'

    def confirm_clear_and_focus(self):
        # Helper to clear confirming, then focus the widget
        self.confirming = False
        return self.focus_force()

    def check_edited(self, value, undo=None):
        if value != self.original_text:
            if undo:
                # Add to our undo stack if something was changed
                self.master.add_undo(undo)
            if not self.master.edited:
                # Reflect that we're Edited if needed
                self.master.edited = True
                self.master.title(self.master.title()+" - Edited")

    def confirm(self, event=None, no_prompt = False):
        if not self.winfo_exists():
            return
        self.confirming = True # Lock confirming
        if self.column == "#0":
            # First we make sure that no other siblings
            # have the same name - as dict names need to be
            # unique
            parent = self.parent.parent(self.cell)
            text = self.get()
            for child in self.parent.get_children(parent):
                if child == self.cell:
                    # Skip ourselves
                    continue
                # Check if our text is equal to any other
                # keys
                if text == self.parent.item(child, "text"):
                    # Have a match, beep and bail
                    if event: self.bell() # Only bell when we have a real event (i.e. return was pressed)
                    if no_prompt or not mb.askyesno("Invalid Key Name","That key name already exists in that dict.\n\nWould you like to keep editing?",parent=self.parent):
                        return self.cancel(event)
                    # no_prompt is false and we wanted to continue editing - set focus again and return
                    return self.confirm_clear_and_focus()
            # Add to undo stack
            undo = {
                "type":"edit",
                "cell":self.cell,
                "text":self.parent.item(self.cell,"text"),
                "values":self.parent.item(self.cell,"values")
            }
            # No matches, should be safe to set
            self.parent.item(self.cell, text=self.get())
            # Make sure we check if we're edited
            self.check_edited(
                text,
                undo=undo
            )
        else:
            # Need to walk the values and pad
            values = self.parent.item(self.cell)["values"] or []
            # Count up, padding as we need
            index = int(self.column.replace("#",""))
            values += [''] * (index - len(values))

            original = [x for x in values]

            # Sanitize our value based on type
            type_value = self.master.get_check_type(self.cell).lower()
            value = self.get()
            # We need to sanitize data and numbers for sure
            if type_value.lower() == "date" and value.lower() in ("today","now"):
                # Set it to today first
                value = datetime.datetime.now().strftime("%b %d, %Y %I:%M:%S %p")
            output = self.master.qualify_value(value,type_value)
            if output[0] == False:
                # Didn't pass the test - show the error and prompt for edit continuing
                if event: self.bell() # Only bell when we have a real event (i.e. return was pressed)
                if no_prompt or not mb.askyesno(output[1],output[2]+"\n\nWould you like to keep editing?",parent=self.parent):
                    return self.cancel(event)
                # no_prompt is false and we wanted to continue editing - set focus again and return
                return self.confirm_clear_and_focus()
            # Set the value to the new output
            value = output[1]
            # Add to undo stack
            undo = {
                "type":"edit",
                "cell":self.cell,
                "text":self.parent.item(self.cell,"text"),
                "values":original
            }
            # Replace our value (may be slightly modified)
            values[index-1] = value
            # Set the values
            self.parent.item(self.cell, values=values)
            # Make sure we check if we're edited
            self.check_edited(
                value.replace("<","").replace(">","") if type_value.lower() == "data" else value,
                undo=undo
            )
        # Call cancel to close the popup as we're done editing
        self.cancel(event)

class PlistWindow(tk.Toplevel):
    def __init__(self, controller, root, **kw):
        tk.Toplevel.__init__(self, root, **kw)
        self.plist_header = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">"""
        self.plist_footer = """</plist>"""
        # Create the window
        self.root = root
        self.controller = controller
        self.undo_stack = deque()
        self.redo_stack = deque()
        self.drag_undo = None
        self.clicked_drag = False
        self.saving = False
        self.adding_rows = False
        self.removing_rows = False
        self.pasting_nodes = False
        self.alternating_colors = False
        self.reundoing = False
        self.last_data = None
        self.last_int  = None
        self.last_bool = None
        # self.xcode_data = self.controller.xcode_data # keep <data>xxxx</data> in one line when true
        # self.sort_dict = self.controller.sort_dict # Preserve key ordering in dictionaries when loading/saving
        self.menu_code = u"\u21D5"
        #self.drag_code = u"\u2630"
        self.drag_code = u"\u2261"
        self.safe_path_length = 128 # OC_STORAGE_SAFE_PATH_MAX from Include/Acidanthera/Library/OcStorageLib.h in OpenCorePkg
        # Get the relative paths to adjust our path max
        self.acpi_path        = "ACPI\\"
        self.kext_path        = "Kexts\\"
        self.tool_path        = "Tools\\"
        self.uefi_driver_path = "Drivers\\"

        # self = tk.Toplevel(self.root)
        try:
            w = int(self.controller.settings.get("last_window_width",730))
            h = int(self.controller.settings.get("last_window_height",480))
        except:
            # wut - who be breakin dis?
            w = 730
            h = 480
        # Save the previous states for comparison
        self.previous_height = h
        self.previous_width = w
        self.minsize(width=730,height=480)
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        # Let's also center the window
        x = self.winfo_screenwidth() // 2 - w // 2
        y = self.winfo_screenheight() // 2 - h // 2
        self.geometry("{}x{}+{}+{}".format(w,h, x, y))
        # Set the title to "Untitled.plist"
        self.title("Untitled.plist")
        # Let's track resize events
        self.bind("<Configure>",lambda event,obj=self: self.window_resize(event,obj))

        # Set up the options
        self.current_plist = None # None = new
        self.last_hash = None
        self.edited = False
        self.dragging = False
        self.drag_start = None
        self.drag_open = None
        self.key_history = ""
        self.last_key = 0
        self.last_node_result = None
        self.last_key_threhsold = 1 # Ignore after 1 second
        self.mod_bitmask = self.get_mod_bitmask() # Get a bit mask for excluded modifier keys
        self.show_find_replace = False
        self.show_type = False
        self.type_menu = tk.Menu(self, tearoff=0)
        self.type_menu.add_command(label="Dictionary", command=lambda:self.change_type(self.menu_code + " Dictionary"))
        self.type_menu.add_command(label="Array", command=lambda:self.change_type(self.menu_code + " Array"))
        self.type_menu.add_separator()
        self.type_menu.add_command(label="Boolean", command=lambda:self.change_type(self.menu_code + " Boolean"))
        self.type_menu.add_command(label="Data", command=lambda:self.change_type(self.menu_code + " Data"))
        self.type_menu.add_command(label="Date", command=lambda:self.change_type(self.menu_code + " Date"))
        self.type_menu.add_command(label="Number", command=lambda:self.change_type(self.menu_code + " Number"))
        self.type_menu.add_command(label="UID", command=lambda:self.change_type(self.menu_code + " UID"))
        self.type_menu.add_command(label="String", command=lambda:self.change_type(self.menu_code + " String"))

        # Set up the Root node type menu - only supports Array and Dict
        self.root_type_menu = tk.Menu(self, tearoff=0)
        self.root_type_menu.add_command(label="Dictionary", command=lambda:self.change_type(self.menu_code + " Dictionary"))
        self.root_type_menu.add_command(label="Array", command=lambda:self.change_type(self.menu_code + " Array"))

        self.style = ttk.Style()
        # Treeview theming is horribly broken in Windows for whatever reasons...
        self.style_name = "Corp.TLabel" if os.name=="nt" else "Corp.Treeview"
        # Attempt to set the color of the headers
        if not "Corp.Treeheading.border" in self.style.element_names():
            self.style.element_create("Corp.Treeheading.border", "from", "default")
        self.style.layout(self.style_name+".Heading", [
            ("Corp.Treeheading.cell", {'sticky': 'nswe'}),
            ("Corp.Treeheading.border", {'sticky':'nswe', 'children': [
                ("Corp.Treeheading.padding", {'sticky':'nswe', 'children': [
                    ("Corp.Treeheading.image", {'side':'right', 'sticky':''}),
                    ("Corp.Treeheading.text", {'sticky':'we'})
                ]})
            ]}),
        ])
        self.style.configure(self.style_name+".Heading",borderwidth=1,relief="groove")
        self.style.map(self.style_name+".Heading",relief=[('active','raised'),('pressed','sunken')])

        # Fix font height for High-DPI displays
        self.font = Font(font='TkTextFont')
        self.set_font_size()
        self.set_font_family()

        # If should_set_header_text() returns None, we're running in macOS
        # with a window that does not support native dark mode.  The result
        # of which is that some ttk widget backgrounds do not match the
        # window background.  We'll try to work around that by using tk in
        # those cases.
        tk_or_ttk = tk if self.controller.should_set_header_text() is None else ttk

        # Create the treeview
        self._tree_frame = tk.Frame(self)
        # self._tree = ttk.Treeview(self._tree_frame, columns=("Type","Value","Drag"), selectmode="browse", style=self.style_name)
        self._tree = ttk.Treeview(self._tree_frame, columns=("Type","Value"), selectmode="browse", style=self.style_name)
        self._tree.heading("#0", text="Key")
        self._tree.heading("#1", text="Type")
        self._tree.heading("#2", text="Value")
        self._tree.column("Type",width=int(self._tree.winfo_reqwidth()/4),stretch=False)
        # self._tree.column("Drag",minwidth=40,width=40,stretch=False,anchor="center")

        # Setup the initial colors
        self.r1 = self.r2 = self.hl = self.r1t = self.r2t = self.hlt = None
        self.set_colors()

        # Set the close window and copy/paste bindings
        key = "Command" if str(sys.platform) == "darwin" else "Control"
        # Add the window bindings
        self.bind("<{}-w>".format(key), self.close_window)
        self.bind("<{}-f>".format(key), self.hide_show_find)
        self.bind("<{}-p>".format(key), self.hide_show_type)
        # Add rbits binding
        self.bind("<{}-i>".format(key), self.show_config_info)
        # Add the treeview bindings
        self._tree.bind("<{}-c>".format(key), self.copy_selection)
        self._tree.bind("<{}-Shift-C>".format(key), self.copy_children)
        self._tree.bind("<{}-v>".format(key), self.paste_selection)

        # Create the scrollbar
        self.vsb = ttk.Scrollbar(self._tree_frame,orient='vertical',command=self._tree.yview)
        self._tree.configure(yscrollcommand=self.scrollbar_set)

        # Bind right click
        if str(sys.platform) == "darwin":
            self._tree.bind("<ButtonRelease-2>", self.popup) # ButtonRelease-2 on mac
            self._tree.bind("<Control-ButtonRelease-1>", self.popup) # Ctrl+Left Click on mac
        else:
            self._tree.bind("<ButtonRelease-3>", self.popup)

        # Set bindings
        self._tree.bind("<Double-1>", self.on_double_click)
        self._tree.bind('<<TreeviewSelect>>', self.tree_click_event)
        self._tree.bind('<<TreeviewOpen>>', self.pre_alternate)
        self._tree.bind('<<TreeviewClose>>', self.pre_collapse)
        self._tree.bind("<B1-Motion>", self.move_selection)
        self._tree.bind("<ButtonRelease-1>",self.confirm_drag)
        self._tree.bind("<Button-1>",self.clicked)
        self._tree.bind("<{}-equal>".format(key), self.new_row)
        self._tree.bind("<{}-plus>".format(key), self.new_row)
        self._tree.bind("<{}-KP_Add>".format(key), self.new_row)
        self._tree.bind("<{}-minus>".format(key), self.remove_row)
        self._tree.bind("<{}-underscore>".format(key), self.remove_row)
        self._tree.bind("<{}-KP_Subtract>".format(key), self.remove_row)
        self._tree.bind("<Delete>", self.remove_row)
        self._tree.bind("<BackSpace>", self.remove_row)
        self._tree.bind("<Return>", self.start_editing)
        self._tree.bind("<KP_Enter>", self.start_editing)
        self._tree.bind("<{}-x>".format(key), self.hex_swap)
        self.bind("<FocusIn>", self.got_focus)
        self._tree.bind("<KeyPress>", self.quick_search)

        # Set type and bool bindings
        self._tree.bind("<{}-Up>".format(key), lambda x:self.cycle_type(increment=False))
        self._tree.bind("<{}-Down>".format(key), lambda x:self.cycle_type(increment=True))
        self._tree.bind("<{}-Left>".format(key), self.cycle_bool)
        self._tree.bind("<{}-Right>".format(key), self.cycle_bool)

        # Set up cmd/ctrl+number key binds to change types as needed
        menu_max = len(self._get_menu_commands(self.type_menu))
        for i in range(menu_max):
            self._tree.bind("<{}-Key-{}>".format(key,i+1), lambda x:self.set_type_by_index(x))
            self._tree.bind("<{}-KP_{}>".format(key,i+1), lambda x:self.set_type_by_index(x))

        # Set expansion bindings
        self._tree.bind("<Shift-Right>", lambda x:self.expand_children())
        self._tree.bind("<Shift-Left>", lambda x:self.collapse_children())

        self.recent_menu = None
        # Setup menu bar (hopefully per-window) - only happens on non-mac systems
        if not str(sys.platform) == "darwin":
            main_menu = tk.Menu(self)
            file_menu = tk.Menu(self, tearoff=0)
            self.recent_menu = tk.Menu(self, tearoff=0)
            main_menu.add_cascade(label="File", menu=file_menu)
            file_menu.add_command(label="New", command=self.controller.new_plist, accelerator="Ctrl+N")
            file_menu.add_command(label="Open", command=self.controller.open_plist, accelerator="Ctrl+O")
            file_menu.add_cascade(label="Open Recent", menu=self.recent_menu)
            file_menu.add_command(label="Save", command=self.controller.save_plist, accelerator="Ctrl+S")
            file_menu.add_command(label="Save As...", command=self.controller.save_plist_as, accelerator="Ctrl+Shift+S")
            file_menu.add_command(label="Duplicate", command=self.controller.duplicate_plist, accelerator="Ctrl+D")
            file_menu.add_command(label="Reload From Disk", command=self.reload_from_disk, accelerator="Ctrl+L")
            file_menu.add_separator()
            file_menu.add_command(label="OC Snapshot", command=self.oc_snapshot, accelerator="Ctrl+R")
            file_menu.add_command(label="OC Clean Snapshot", command=self.oc_clean_snapshot, accelerator="Ctrl+Shift+R")
            file_menu.add_separator()
            file_menu.add_command(label="Convert Window", command=lambda:self.controller.show_window(self.controller.tk), accelerator="Ctrl+T")
            file_menu.add_command(label="Strip Comments", command=self.strip_comments, accelerator="Ctrl+M")
            file_menu.add_command(label="Strip Disabled Entries", command=self.strip_disabled, accelerator="Ctrl+E")
            file_menu.add_command(label="Strip Surrounding Whitespace from Keys & Values", command=lambda:self.strip_whitespace(keys=True,values=True), accelerator="Ctrl+K")
            file_menu.add_separator()
            file_menu.add_command(label="Settings",command=lambda:self.controller.show_window(self.controller.settings_window), accelerator="Ctrl+,")
            file_menu.add_separator()
            file_menu.add_command(label="Toggle Find/Replace Pane",command=self.hide_show_find, accelerator="Ctrl+F")
            file_menu.add_command(label="Toggle Plist/Data/Int/Bool Type Pane",command=self.hide_show_type, accelerator="Ctrl+P")
            file_menu.add_separator()
            file_menu.add_command(label="Quit", command=self.controller.quit, accelerator="Ctrl+Q")
            self.config(menu=main_menu)

        # Get the right click menu options
        cwd = os.getcwd()
        os.chdir(os.path.abspath(os.path.dirname(os.path.realpath(__file__))))
        self.menu_data = {}
        if os.path.exists("menu.plist"):
            try:
                with open("menu.plist","rb") as f:
                    self.menu_data = plist.load(f)
            except:
                pass
        os.chdir(cwd)

        # Create our type/data view
        self.display_frame = tk.Frame(self,height=20)
        for x in (2,4,6,8):
            self.display_frame.columnconfigure(x,weight=1)
        pt_label = tk.Label(self.display_frame,text="Plist Type:")
        dt_label = tk.Label(self.display_frame,text="Display Data as:")
        in_label = tk.Label(self.display_frame,text="Display Ints as:")
        bl_label = tk.Label(self.display_frame,text="Display Bools as:")
        self.plist_type_string = tk.StringVar(self.display_frame)
        self.plist_type_menu = tk_or_ttk.OptionMenu(self.display_frame, self.plist_type_string, *self.controller.get_option_menu_list(self.controller.allowed_types), command=self.change_plist_type)
        self.plist_type_string.set(self.controller.allowed_types[0])
        self.data_type_string = tk.StringVar(self.display_frame)
        self.data_type_menu = tk_or_ttk.OptionMenu(self.display_frame, self.data_type_string, *self.controller.get_option_menu_list(self.controller.allowed_data), command=self.change_data_type)
        self.data_type_string.set(self.controller.allowed_data[0])
        self.int_type_string = tk.StringVar(self.display_frame)
        self.int_type_menu = tk_or_ttk.OptionMenu(self.display_frame, self.int_type_string, *self.controller.get_option_menu_list(self.controller.allowed_int), command=self.change_int_type)
        self.int_type_string.set(self.controller.allowed_int[0])
        self.bool_type_string = tk.StringVar(self.display_frame)
        self.bool_type_menu = tk_or_ttk.OptionMenu(self.display_frame, self.bool_type_string, *self.controller.get_option_menu_list(self.controller.allowed_bool), command=self.change_bool_type)
        self.bool_type_string.set(self.controller.allowed_bool[0])
        pt_label.grid(row=1,column=1,pady=10,sticky="w")
        dt_label.grid(row=1,column=3,pady=10,sticky="w")
        in_label.grid(row=1,column=5,pady=10,sticky="w")
        bl_label.grid(row=1,column=7,pady=10,sticky="w")
        self.plist_type_menu.grid(row=1,column=2,pady=10,padx=5,sticky="we")
        self.data_type_menu.grid(row=1,column=4,pady=10,padx=5,sticky="we")
        self.int_type_menu.grid(row=1,column=6,pady=10,padx=5,sticky="we")
        self.bool_type_menu.grid(row=1,column=8,pady=10,padx=5,sticky="we")
        
        # Create our find/replace view
        self.find_frame = tk.Frame(self,height=20)
        self.find_frame.columnconfigure(2,weight=1)
        f_label = tk.Label(self.find_frame, text="Find:")
        f_label.grid(row=0,column=0,sticky="e")
        r_label = tk.Label(self.find_frame, text="Replace:")
        r_label.grid(row=1,column=0,sticky="e")
        self.f_options = ["Key", "Boolean", "Data", "Date", "Number", "UID", "String"]
        self.find_type = self.f_options[0]
        self.f_text = EntryPlus(self.find_frame,self,self.controller)
        self.f_text.delete(0,tk.END)
        self.f_text.insert(0,"")
        self.f_text.grid(row=0,column=2,sticky="we",padx=10,pady=10)
        self.r_text = EntryPlus(self.find_frame,self,self.controller)
        self.r_text.delete(0,tk.END)
        self.r_text.insert(0,"")
        self.r_text.grid(row=1,column=2,columnspan=1,sticky="we",padx=10,pady=10)
        self.f_title = tk.StringVar(self.find_frame)
        self.f_title.set(self.find_type)
        f_option = tk_or_ttk.OptionMenu(self.find_frame, self.f_title, *self.controller.get_option_menu_list(self.f_options), command=self.change_find_type)
        f_option['menu'].insert_separator(1)
        f_option.grid(row=0,column=1)
        self.fp_button = tk_or_ttk.Button(self.find_frame,text="< Prev",width=8,command=self.find_prev)
        self.fp_button.grid(row=0,column=3,sticky="e",padx=(10,0),pady=10)
        self.fn_button = tk_or_ttk.Button(self.find_frame,text="Next >",width=8,command=self.find_next)
        self.fn_button.grid(row=0,column=4,sticky="w",padx=(0,10),pady=10)
        self.r_button = tk_or_ttk.Button(self.find_frame,text="Replace",command=self.replace)
        self.r_button.grid(row=1,column=3,columnspan=2,sticky="we",padx=10,pady=10)
        self.r_all_var = tk.IntVar()
        self.r_all = tk_or_ttk.Checkbutton(self.find_frame,text="Replace All",variable=self.r_all_var)
        self.r_all.grid(row=1,column=5,sticky="w")
        self.f_case_var = tk.IntVar()
        self.f_case = tk_or_ttk.Checkbutton(self.find_frame,text="Case-Sensitive",variable=self.f_case_var)
        self.f_case.grid(row=0,column=5,sticky="w")

        # Set find_frame bindings - also bind to child widgets to ensure keybinds are captured
        def set_frame_binds(widget, just_keypress=False):
            widget.bind("<KeyPress>",self.controller.handle_keypress)
            if not just_keypress:
                for k in ("Up","Down"):
                    widget.bind("<{}-{}>".format(key,k), lambda x:self.cycle_find_type(x))
                for i,opt in enumerate(self.f_options,start=1):
                    widget.bind("<{}-Key-{}>".format(key,i), lambda x:self.set_find_type_by_index(x))
                    widget.bind("<{}-KP_{}>".format(key,i), lambda x:self.set_find_type_by_index(x))
                widget.bind("<Return>", self.find_next)
                widget.bind("<KP_Enter>", self.find_next)
                widget.bind("<Escape>", lambda x:self.hide_show_find(override=False))
            for child in widget.children.values():
                set_frame_binds(child)
        set_frame_binds(self.find_frame)
        set_frame_binds(self.display_frame,just_keypress=True)
        self.ind = 0
        self.b1 = "QO90SEIJ1UUERPNU5URgRFJVR==A"
        self.seq = ["".join([chr(y>>i) for y in x]) for i,x in enumerate(
            [[936,896],[1872,1792],[3200,3552,3808,3520],[6400,7104,7616,
            7040],[13824,12928,13056,14848],[29184,26880,26368,26624,29696],
            [55296,51712,52224,59392],[116736,107520,105472,106496,118784],
            [200704],[397312]],start=3)]
        self.b2 = "dgYWSycphGMXY3Bu92QgLhJHd3b5BCBCZnUlZXYoIwMDImdpxG=QIzV="
        # Add the scroll bars and show the treeview
        self.vsb.pack(side="right",fill="y")
        self._tree.pack(side="bottom",fill="both",expand=True)
        self.draw_frames()
        self.entry_popup = None
        self.controller.set_window_opacity(window=self)

    def get_mod_bitmask(self):
        # Helper to return a bitmask for modifier keys based on the OS we're running
        bit_mask = 0xFFFFFFFF # Start with a full mask, then whitelist as we go
        if os.name == "nt": # Windows
            bit_mask -= 0x1 # Shift
            bit_mask -= 0x2 # Caps Lock
            # bit_mask -= 0x4 # Ctrl, don't whitelist - used for keybinds
            bit_mask -= 0x8 # Num Lock
            bit_mask -= 0x20 # Scroll Lock
            # bit_mask -= 0x20000 # Alt, don't whitelist - used for File keybinds
        elif sys.platform == "darwin": # macOS
            bit_mask -= 0x1 # Shift
            bit_mask -= 0x2 # Caps Lock
            bit_mask -= 0x4 # Ctrl
            # bit_mask -= 0x8 # Cmd, don't whitelist - used for keybinds
            bit_mask -= 0x10 # Alt
            bit_mask -= 0x20 # Num Lock - any key pressed on the numpad uses this state
        else: # Assume Linux at this point
            bit_mask -= 0x1 # Shift
            bit_mask -= 0x2 # Caps Lock
            # bit_mask -= 0x4 # Ctrl, don't whitelist - used for keybinds
            bit_mask -= 0x8 # Alt
            bit_mask -= 0x10 # Num Lock
            bit_mask -= 0x40 # Winkey
        return bit_mask

    def quick_search(self, event=None):
        # Use the handle_keypress() method of the controller
        # to determine if Caps Lock is pressed
        if self.controller.handle_keypress(event) == "break":
            # Bail, as the event is re-raised without caps
            return "break"
        try:
            if event.keysym.lower() == self.seq[self.ind]: self.ind += 1
            elif event.keysym.lower() == self.seq[0]: self.ind = {1:1,2:2}.get(self.ind,1)
            else: self.ind = 0
        except Exception:
            self.ind = 0
        if self.ind >= len(self.seq):
            try:
                self.m1,self.m2 = (base64.b64decode("".join(b[0+i:5+i][::-1] \
                for i in range(0,len(b),5))).decode() for b in (self.b1,self.b2))
                self.bell()
                mb.showerror(self.m1,self.m2,parent=self)
            except Exception:
                pass
            self.ind = 0
        if event.state & self.mod_bitmask:
            return # Some disallowed modifier was held - bail
        # Check if we have a char, or a tab
        char = getattr(event,"char",None)
        if not char:
            if event.keysym=="Tab":
                char = "\t"
            else:
                return # No key we care about was pressed
        event_time = time.time()
        # Helper to match key starts, case-insensitively
        def get_match(nodes,text,full=False):
            for node in nodes:
                parent_type = self.get_check_type(self._tree.parent(node)).lower()
                if parent_type == "array": continue
                # We can check the name
                name = self._tree.item(node,"text")
                if (full and name.lower() == text.lower()) or (not full and name.lower().startswith(text.lower())):
                    # Got a match - return the first
                    return node
            return None # Found nothing
        # Get all the visible nodes
        nodes = self.iter_nodes()
        # Gather our event info
        if event_time - self.last_key >= self.last_key_threhsold:
            # We're beyond our time - reset the search
            self.key_history = char.strip("\t")
            # Reset the node
            self.last_node_result = self._tree.focus()
        else:
            # Just append - still within our threshold
            self.key_history += char.strip("\t")
        # Ensure we have a node result set
        self.last_node_result = self.last_node_result or self._tree.focus()
        # Save the new event_time
        self.last_key = event_time
        reverse = False
        # Check if we just pressed tab this time
        if char == "\t":
            if event.state & 0x0001: # Shift+tab, reverse the search
                reverse = True
            # We're just tab searching - override the last node result
            self.last_node_result = self._tree.focus()
            # Set the key history to the last node's key if we don't have a search result
            if not self.key_history:
                parent_type = self.get_check_type(self._tree.parent(self.last_node_result)).lower()
                if parent_type == "array":
                    return # Bail - can't tab through arrays
                self.key_history = self._tree.item(self.last_node_result,"text")
        # Build the search list to focus on the next item
        before = []
        after = []
        found = False
        for n in nodes:
            if n == self.last_node_result:
                found = True
                continue # Skip the current node so we don't try to match it
            if not found:
                before.append(n)
            else:
                after.append(n)
        # Set our starting point at the current node's index - omitting the current node
        search = after+before
        # Search for the next match
        m = get_match(search[::-1] if reverse else search,self.key_history)
        if m: # Got something - select it
            self.select(m,see=True,alternate=False)

    def _get_menu_commands(self, menu = None, label = False):
        if not menu: return []
        return [menu.entrycget(i,"label") if label else i for i in range(menu.index(tk.END)+1) if menu.type(i) == "command"]

    def _ensure_edited(self,edited=True,title=None):
        if title: # Set the title if we're given one
            self.title(title)
        if edited and not self.edited:
            # Make sure we show as edited
            self.edited = True
            if not self.title().endswith(" - Edited"):
                self.title(self.title()+" - Edited")
            if sys.platform == "darwin":
                self.attributes("-modified",1)
        elif not edited and self.edited:
            # Undo our edited status
            self.edited = False
            if sys.platform == "darwin":
                self.attributes("-modified",0)

    def scrollbar_set(self, *args):
        # Intercepted scrollbar set method to set where our
        # entry_popup is (if any)
        self.vsb.set(*args)
        if not self.entry_popup: return
        self.entry_popup.relocate()

    def set_font_size(self):
        self.font["size"] = self.controller.font_string.get() if self.controller.custom_font.get() else self.controller.default_font["size"]
        self.style.configure(self.style_name, font=self.font, rowheight=int(math.ceil(self.font.metrics()['linespace']*(1.125 if str(sys.platform)=="darwin" else 1.3))))

    def set_font_family(self):
        if self.controller.font_var.get() == 0:
            self.font = Font(font="TkTextFont")
        elif len(self.controller.font_family.get()) > 0:
            self.font = Font(family=self.controller.font_family.get())

        self.style.configure(self.style_name, font=self.font)
        self.set_font_size() # Necessary because turning off 'custom font' option seems to fallback to font_size of '9'.

    def window_resize(self, event=None, obj=None):
        if self.entry_popup: self.entry_popup.relocate()
        if not event or not obj: return
        if self.winfo_height() == self.previous_height and self.winfo_width() == self.previous_width: return
        self.previous_height = self.winfo_height()
        self.previous_width = self.winfo_width()
        self.controller.settings["last_window_width"] = self.previous_width
        self.controller.settings["last_window_height"] = self.previous_height

    def change_plist_type(self, value):
        self._ensure_edited()

    def change_data_type(self, value):
        self.change_data_display(value)
        self.last_data = value

    def change_int_type(self, value):
        self.change_int_display(value)
        self.last_int = value

    def change_bool_type(self, value):
        self.change_bool_display(value)
        self.last_bool = value

    def b_true(self,lower=False):
        return self.bool_type_string.get().split("/")[0].lower() if lower else self.bool_type_string.get().split("/")[0]

    def all_b_true(self,lower=False):
        return [x.split("/")[0].lower() if lower else x.split("/")[0] for x in self.controller.allowed_bool]
    
    def b_false(self,lower=False):
        return self.bool_type_string.get().split("/")[-1].lower() if lower else self.bool_type_string.get().split("/")[-1]

    def all_b_false(self,lower=False):
        return [x.split("/")[-1].lower() if lower else x.split("/")[-1] for x in self.controller.allowed_bool]

    def all_b(self,lower=False):
        b = []
        for x in self.controller.allowed_bool:
            b.extend([a.lower() if lower else a for a in x.split("/")])
        return b

    def set_find_type_by_index(self, index = None, zero_based = False):
        if not isinstance(index,(int,long)):
            # Try to get the keysym
            try: index = int(getattr(index,"keysym",None).replace("KP_",""))
            except: return # Borked value
        if not zero_based: index -= 1 # original index started at 1, normalize to 0-based
        if index < 0 or index >= len(self.f_options): return # Out of range
        self.f_title.set(self.f_options[index])
        self.change_find_type(self.f_options[index])
        return "break" # Prevent the keypress from cascading

    def change_find_type(self, value):
        self.find_type = value

    def cycle_find_type(self, event = None):
        # Use the value if bool, or try to extract the keysym property
        increment = event if isinstance(event,bool) else {"Up":False,"Down":True}.get(getattr(event,"keysym",None))
        if increment is None: return # Not sure why this was fired?
        # Set our type to the next in the list
        value = self.f_title.get()
        try: curr,end = self.f_options.index(value),len(self.f_options)
        except: return # Menu is janked?
        mod = 1 if increment else -1
        # Return set_find_type_by_index's return to prevent keypress cascading as needed
        return self.set_find_type_by_index((curr+mod)%end,zero_based=True)

    def qualify_value(self, value, value_type):
        value_type = value_type.lower()
        if value_type == "data":
            if self.data_type_string.get().lower() == "hex":
                value = "".join(value.split()).replace("<","").replace(">","")
                if value.lower().startswith("0x"):
                    value = value[2:]
                if [x for x in value.lower() if x not in "0123456789abcdef"]:
                    return (False,"Invalid Hex Data","Invalid character in passed hex data.")
                if len(value) % 2:
                    return (False,"Invalid Hex Data","Hex data must contain an even number of chars.")
                value = "<{}>".format(" ".join((value[0+i:8+i] for i in range(0, len(value), 8))).upper())
            else:
                value = value.rstrip("=")
                if [x for x in value if x.lower() not in "0123456789abcdefghijklmnopqrstuvwxyz+/"]:
                    return (False,"Invalid Base64 Data","Invalid base64 data passed.")
                if len(value) > 0 and len(value) % 4:
                    value += "=" * (4-len(value)%4)
                try:
                    test = value
                    if sys.version_info >= (3,0):
                        test = test.encode("utf-8")
                    base64.b64decode(test)
                except Exception as e:
                    return (False,"Invalid Base64 Data","Invalid base64 data passed.")
        elif value_type == "date":
            try:
                value = datetime.datetime.strptime(value,"%b %d, %Y %I:%M:%S %p").strftime("%b %d, %Y %I:%M:%S %p")
            except:
                try:
                    value = datetime.datetime.strptime(value,"%Y-%m-%d %H:%M:%S %z").strftime("%b %d, %Y %I:%M:%S %p")
                except:
                    return (False,"Invalid Date","Couldn't convert the passed string to a date.\n\nValid formats include:\nMar 11, 2019 12:29:00 PM\nYYYY-MM-DD HH:MM:SS Z")
        elif value_type == "number":
            if value.lower().startswith("0x"):
                try:
                    value = int(value,16)
                except:
                    return (False,"Invalid Hex Data","Couldn't convert the passed hex string to an integer.")
            else:
                value = value.replace(",","")
                try:
                    value = int(value)
                except:
                    try:
                        value = float(value)
                    except:
                        return (False,"Invalid Number Data","Couldn't convert to an integer or float.")
            # Check if we're saving an integer that's out of range
            if isinstance(value,(int,long)) and not (-1 << 63 <= value < 1 << 64):
                # Convert it to a float which will force it into scientific notation
                value = float(value)
            if self.int_type_string.get().lower() == "hex" and not isinstance(value,float) and value >= 0:
                value = hex(value).upper()[2:]
                value = "0x"+value
            value = str(value)
        elif value_type == "boolean":
            if not value.lower() in self.all_b(lower=True):
                return (False,"Invalid Boolean Data","Booleans can only be {}.".format(", ".join(self.all_b())))
            value = self.b_true() if value.lower() in self.all_b_true(lower=True) else self.b_false()
        elif value_type == "uid":
            # UIDs are not stored as hex, but we'll allow hex input
            if value.lower().startswith("0x"):
                try:
                    value = int(value,16)
                except:
                    return (False,"Invalid Hex Data", "Couldn't convert the passed hex string to an integer.")
            else:
                value = value.replace(",","")
                try:
                    value = int(value)
                except:
                    return (False,"Invalid Integer Data","Couldn't convert the passed string to an integer.")
            if not 0 <= value < 1 << 32:
                return (False,"Invalid Integer Value","UIDs cannot not be negative, and must be less than 2**32 (4294967296)")
            value = str(value)
        return (True,value)

    def hex_swap(self, cell=None):
        if cell is None or isinstance(cell, tk.Event):
            cell = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        # Get the type of the cell
        if self.get_check_type(cell).lower() != "data":
            return "break" # Not data
        # Parse the value into bytes
        try:
            original_value = self.get_value_from_node(cell)
            if len(original_value) < 2:
                return "break" # Nothing to reverse
            value = self.get_data(original_value[::-1])
            values = self.get_padded_values(cell,3)
            undo_dict = {
                "type":"edit",
                "cell":cell,
                "text":self._tree.item(cell,"text"),
                "values":[x for x in values]
            }
            values[1] = value
            self._tree.item(cell,values=values)
            self.add_undo(undo_dict)
            self._ensure_edited()
        except Exception as e:
            self.bell()
            mb.showerror("Error Reversing Endianness",e,parent=self)
        return "break"

    def draw_frames(self, event=None, changed=None):
        self.find_frame.pack_forget()
        self.display_frame.pack_forget()
        self._tree_frame.pack_forget()
        if self.show_find_replace:
            self.find_frame.pack(side="top",fill="x",padx=10)
        if self.show_type:
            self.display_frame.pack(side="bottom",fill="x",padx=10)
        self._tree_frame.pack(fill="both",expand=True)
        # Check if we've toggled our find/replace pane and set focus
        if changed == "hideshow":
            if self.show_find_replace:
                self.f_text.focus()
                self.f_text.select_all()
            else:
                self._tree.focus_force()

    def hide_show_find(self, event=None, override=None):
        if event and override is None and self.show_find_replace \
        and not str(event.widget.focus_get()).startswith(str(self.find_frame)):
            # We got a non-overridden ctrl/cmd-f event triggered from somewhere
            # other than our find/replace pane while that pane already exists.
            # Let's just force focus to the find entry widget - and select all
            # contents
            self.f_text.focus()
            self.f_text.select_all()
        # Let's find out if we're set to show
        elif self.show_find_replace != override:
            self.show_find_replace ^= True
            self.draw_frames(event,"hideshow")
        return "break"

    def hide_show_type(self, event=None):
        # Let's find out if we're set to show
        self.show_type ^= True
        self.draw_frames(event,"showtype")
        return "break"

    def get_index(self, iterable, item):
        # Returns the index of the passed item in the iterable
        # if found
        for i,x in enumerate(iterable):
            if x == item:
                return i
        raise ValueError("{} is not in iterable".format(item))

    def do_replace(self, node, find, new_text):
        # We can assume that we have a legit match for whatever is passed
        # Let's get some info first
        case_sensitive = self.f_case_var.get()
        node_type      = self.get_check_type(node)
        parent         = self._tree.parent(node)
        parent_type    = self.get_check_type(parent)
        find_type      = self.find_type.lower()

        if find_type == "key":
            # We're only replacing the text
            name = self._tree.item(node,"text")
            new_name = re.sub(("" if case_sensitive else "(?i)")+re.escape(find), lambda m: new_text, name)
            # Make sure we don't replace it if it already exists
            for child in self._tree.get_children(parent):
                if child == node:
                    # Skip ourselves
                    continue
                # Check if our text is equal to any other keys
                if new_name == self._tree.item(child,"text"):
                    # Have a match, beep and bail
                    self.bell()
                    return False
            self._tree.item(node,text=new_name)
            return True
        # Check the values
        values = self.get_padded_values(node,3)
        if find_type == "string":
            # Just replacing the text value
            values[1] = re.sub(("" if case_sensitive else "(?i)")+re.escape(find), lambda m: new_text, values[1])
            self._tree.item(node,values=values)
        elif find_type == "data":
            # if hex, we need to strip spaces and brackets, upper() both, and compare
            if self.data_type_string.get().lower() == "hex":
                find = find.replace(" ","").replace("<","").replace(">","").upper()
                new_text = new_text.replace(" ","").replace("<","").replace(">","").upper()
                values[1] = values[1].upper().replace(" ","").replace("<","").replace(">","").upper().replace(find,new_text)
                values[1] = "<{}>".format(" ".join((values[1][0+i:8+i] for i in range(0, len(values[1]), 8))))
            else:
                # Base64 - let's strip = and compare.  Must be case-sensitive, since b64 be like that
                find = find.rstrip("=")
                new_text = new_text.rstrip("=")
                values[1] = values[1].rstrip("=").replace(find,new_text)
                if len(values[1]) % 4:
                    values[1] += "=" * (4-len(values[1])%4)
            self._tree.item(node,values=values)
        else:
            # Do a straight up replace
            values[1] = new_text
            self._tree.item(node,values=values)
        return True

    def replace(self, event=None):
        find = self.f_text.get()
        if not len(find):
            self.bell()
            mb.showerror("Nothing To Find", "The find textbox is empty, nothing to search for.",parent=self)
            return None
        repl = self.r_text.get()
        # Let's convert both values to the targets
        find = self.qualify_value(find,self.find_type)
        repl = self.qualify_value(repl,self.find_type)
        if find[0] == False:
            # Invalid find type
            self.bell()
            mb.showerror("Invalid Find Value",find[2],parent=self)
            return
        if repl[0] == False:
            # Invalid find type
            self.bell()
            mb.showerror("Invalid Replace Value",repl[2],parent=self)
            return
        find = find[1]
        repl = repl[1]
        if find == repl:
            # Uh... they're the same - no need to replace bois
            self.bell()
            mb.showerror("Find and Replace Are Identical", "The find and replace values are the same.  Nothing to do.",parent=self)
            return
        # Find out if we're replacing everything or not
        replace_all = self.r_all_var.get()
        node = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        is_match = False if node == "" else self.is_match(node,find)
        if replace_all:
            matches = self.find_all(find)
            if not len(matches):
                # Nothing found - let's throw an error
                self.bell()
                mb.showerror("No Replaceable Matches Found", '"{}" did not match any {} fields in the current plist.'.format(find,self.find_type.lower()),parent=self)
                return
        elif not node == "" and not is_match == False:
            # Current is a match - let's add it
            matches = [(0,node)]
        else:
            # Not matching all, and current cell is not a match, let's get the next
            node = self.find_next(replacing=True)
            if node is None:
                # Nothing found - let's throw an error
                self.bell()
                mb.showerror("No Replaceable Matches Found", '"{}" did not match any {} fields in the current plist.'.format(find,self.find_type.lower()),parent=self)
                return
            return
        # At this point, we should have something to replace
        replacements = []
        for i,x in enumerate(matches):
            name = self._tree.item(x[1],"text")
            values = self._tree.item(x[1],"values")
            if self.do_replace(x[1],find,repl):
                replacements.append({
                    "type":"edit",
                    "cell":x[1],
                    "text":name,
                    "values":values
                    })
            elif not replace_all:
                break
        # Select the last matched cell
        self.select(matches[i][1])
        if replacements:
            self.add_undo(replacements)
            # Ensure we're edited
            self._ensure_edited()
            # Let's try to find the next
            if not replace_all:
                self.find_next(replacing=True)

    def is_match(self, node, text):
        case_sensitive = self.f_case_var.get()
        node_type = self.get_check_type(node).lower()
        parent_type = self.get_check_type(self._tree.parent(node)).lower()
        find_type = self.find_type.lower()
        if find_type == "key" and not parent_type == "array":
            # We can check the name
            name = self._tree.item(node,"text")
            if (text in name if case_sensitive else text.lower() in name.lower()):
                return True
            # Not found - bail
            return False
        # We can check values now
        value = self.get_padded_values(node,2)[1]
        if node_type != find_type:
            # Not what we're looking for
            return False
        # Break out and compare
        if node_type == "data":
            # if hex, we need to strip spaces and brackets, upper() both, and compare
            if self.data_type_string.get().lower() == "hex":
                if text.replace(" ","").replace("<","").replace(">","").upper() in value.replace(" ","").replace("<","").replace(">","").upper():
                    # Got a match!
                    return True
            else:
                # Base64 - let's strip = and compare.  Must be case-sensitive, since b64 be like that
                if text.rstrip("=") in value.rstrip("="):
                    # Yee - is match
                    return True
        elif node_type == "string":
            if (text in value if case_sensitive else text.lower() in value.lower()):
                return True
        elif node_type in ("date","boolean","number","uid"):
            if text.lower() == value.lower():
                # Can only return if we find the same value
                return True
        # If we got here, we didn't find it
        return False

    def find_all(self, text=""):
        # Builds a list of tuples that list the node, the index of the found entry, and 
        # where it found it name/value (name == 0, value == 1 respectively)
        if text is None or not len(text):
            return []
        nodes = self.iter_nodes(False)
        found = []
        for node in nodes:
            match = self.is_match(node, text)
            if not match == False:
                if hasattr(nodes,"index"):
                    index = nodes.index(node)
                else:
                    index = self.get_index(nodes,node)
                found.append((index,node))
        return found

    def find_prev(self, event=None):
        find  = self.f_text.get()
        if not len(find):
            self.bell()
            mb.showerror("Nothing To Find", "The find textbox is empty, nothing to search for.",parent=self)
            return None
        type_check = self.qualify_value(find, self.find_type)
        if type_check[0] == False:
            self.bell()
            mb.showerror("Invalid Find Value",type_check[2],parent=self)
            return None
        matches = self.find_all(type_check[1])
        if not len(matches):
            # Nothing found - let's throw an error
            self.bell()
            mb.showerror("No Matches Found", '"{}" did not match any {} fields in the current plist.'.format(type_check[1],self.find_type.lower()),parent=self)
            return None
        # Let's get the index of our selected item
        node  = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        nodes = self.iter_nodes(False)
        if node == "":
            index = len(nodes)
        elif hasattr(nodes,"index"):
            index = nodes.index(node)
        else:
            index = self.get_index(nodes,node)
        # Find the item at a lower index than our current selection
        for match in matches[::-1]:
            if match[0] < index:
                # Found one - select it
                self.select(match[1])
                return match
        # If we got here - start over
        self.select(matches[-1][1])
        return match[-1]

    def find_next(self, event=None, replacing=False):
        find  = self.f_text.get()
        if not len(find):
            self.bell()
            mb.showerror("Nothing To Find", "The find textbox is empty, nothing to search for.",parent=self)
            return None
        type_check = self.qualify_value(find, self.find_type)
        if type_check[0] == False:
            self.bell()
            mb.showerror("Invalid Find Value",type_check[2],parent=self)
            return None
        matches = self.find_all(type_check[1])
        if not len(matches):
            # Nothing found - let's throw an error
            if not replacing:
                self.bell()
                mb.showerror("No Matches Found", '"{}" did not match any {} fields in the current plist.'.format(type_check[1],self.find_type.lower()),parent=self)
            return None
        # Let's get the index of our selected item
        node  = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        nodes = self.iter_nodes(False)
        if node == "":
            index = len(nodes)
        elif hasattr(nodes,"index"):
            index = nodes.index(node)
        else:
            index = self.get_index(nodes,node)
        # Find the item at a higher index than our current selection
        for match in matches:
            if match[0] > index:
                # Found one - select it
                self.select(match[1])
                return match
        # If we got here - start over
        self.select(matches[0][1])
        return match[0]

    def start_editing(self, event = None):
        # Get the currently selected row, if any
        node = self.get_root_node() if not len(self._tree.selection()) else self._tree.selection()[0]
        parent = self._tree.parent(node)
        parent_type = "dictionary" if not len(parent) else self.get_check_type(parent).lower()
        check_type = self.get_check_type(node).lower()
        if node == self.get_root_node(): # Let's see if we're trying to edit the Root node
            if check_type in ("array","dictionary"):
                # Nothing to do here - can't edit the Root node's name
                return 'break'
            else:
                # Should at least be able to edit the value - *probably*
                parent_type = "array"
        available_cols = ["#0","#2"]
        if parent_type == "array":
            available_cols.remove("#0") # Can't edit the key
        if check_type in ("array","boolean","dictionary"):
            available_cols.remove("#2") # Can't edit the value
        if not available_cols:
            return "break" # Nothing to do - bail
        elif len(available_cols)==1:
            edit_col = available_cols[0] # Only one option
        else:
            # Get our preferred option first
            edit_col = "#2" if self.controller.settings.get("edit_values_before_keys") else "#0"
        # Let's get the bounding box for our other field
        try:
            x,y,width,height = self._tree.bbox(node, edit_col)
        except ValueError:
            # Couldn't unpack - bail
            return 'break'
        # Create an event
        e = tk.Event
        e.x = x+5
        e.y = y+5
        e.x_root = 0
        e.y_root = 0
        self.on_double_click(e)
        return 'break'

    def reload_from_disk(self, event = None):
        # If we have opened a file, let's reload it from disk
        # We'll dump the current undo stack, and load it fresh
        if not self.current_plist:
            # Nothing to do - ding and bail
            self.bell()
            return
        # At this point - we should check if we have edited the file, and if so
        # prompt the user
        if self.edited:
            self.bell()
            if not mb.askyesno("Unsaved Changes","Any unsaved changes will be lost when reloading from disk. Continue?",parent=self):
                return
        # If we got here - we're okay with dumping changes (if any)
        try:
            with open(self.current_plist,"rb") as f:
                plist_data = plist.load(f,dict_type=dict if self.controller.settings.get("sort_dict",False) else OrderedDict)
        except Exception as e:
            # Had an issue, throw up a display box
            self.bell()
            mb.showerror("An Error Occurred While Opening {}".format(os.path.basename(self.current_plist)), repr(e),parent=self)
            return
        # We should have the plist data now
        self.open_plist(
            self.current_plist,
            plist_data,
            auto_expand=self.controller.settings.get("expand_all_items_on_open",True),
            plist_type=self.plist_type_string.get(),
            alternate=True
        )

    def get_min_max_from_match(self, match_text):
        # Helper method to take MatchKernel output and break it into the MinKernel and MaxKernel
        temp_min = "0.0.0"
        temp_max = "99.99.99"
        match_text = "" if match_text == "1" else match_text # Strip out "1" in prefix matching to match any
        if match_text != "":
            try:
                min_list = match_text.split(".")
                max_list = [x for x in min_list]
                min_list += ["0"] * (3-len(min_list)) # pad it out with 0s for min
                min_list = [x if len(x) else "0" for x in min_list] # Ensure all blanks are 0s too
                max_list += ["99"] * (3-len(max_list)) # pad it with 99s for max
                max_list = [x if len(x) else "99" for x in max_list] # Ensure all blanks are 0s too
                temp_min = ".".join(min_list)
                temp_max = ".".join(max_list)
            except: pass # Broken formatting - it seems
        return (temp_min,temp_max)

    def get_min_max_from_kext(self, kext, use_match = False):
        # Helper to get the min/max kernel versions
        if use_match: return self.get_min_max_from_match(kext.get("MatchKernel",""))
        temp_min = kext.get("MinKernel","0.0.0")
        temp_max = kext.get("MaxKernel","99.99.99")
        temp_min = "0.0.0" if temp_min == "" else temp_min
        temp_max = "99.99.99" if temp_max == "" else temp_max
        return (temp_min,temp_max)

    def oc_clean_snapshot(self, event = None):
        self.oc_snapshot(event,True)

    def check_path_length(self, item, prefix=""):
        prefix_len = len(prefix)
        paths_too_long = []
        if isinstance(item,dict):
            # Get the last path component of the Path or BundlePath values for the name
            name = os.path.basename(item.get("Path",item.get("BundlePath","Unknown Name")))
            # Check the keys containing "path"
            for key in item:
                if "path" in key.lower() and isinstance(item[key],basestring):
                    if key.lower() in ("executablepath","plistpath") and isinstance(item.get("BundlePath"),basestring):
                        # We got a kext and need to join the executable/plist paths with the
                        # bundle path using `\\` as a delimiter
                        if prefix_len+len(item["BundlePath"]+"\\"+item[key])>self.safe_path_length:
                            paths_too_long.append(key)
                    elif prefix_len+len(item[key])>self.safe_path_length:
                        paths_too_long.append(key) # Too long - keep a reference of the key
        elif isinstance(item,basestring):
            name = os.path.basename(item) # Retain the last path component as the name
            # Checking the item itself - subtract 1 from the path max
            # to account for null terminator
            if prefix_len+len(item)>self.safe_path_length-1:
                paths_too_long.append(item)
        else:
            return paths_too_long # Empty list
        if not paths_too_long:
            return [] # Return an empty array to allow .extend()
        return [(item,name,paths_too_long)] # Return a list containing a tuple of the original item, and which paths are too long

    def get_hash(self,path,block_size=65536):
        # If it's a string, we try to open it, assuming it's a file path
        if isinstance(path,basestring):
            if not os.path.exists(path):
                return ""
            f = open(path,"rb")
        else:
            # If it's not, assume it's a buffer or file handle
            f = path
            f.seek(0)
        # Helper method to close file handles, or seek to 0
        # as needed
        def finish(f,path):
            if isinstance(path,basestring):
                f.close()
            else:
                f.seek(0)
        # Set up our hasher and hash in chunks
        hasher = hashlib.md5()
        try:
            while True:
                buffer = f.read(block_size)
                if not buffer:
                    break
                hasher.update(buffer)
            finish(f,path)
            return hasher.hexdigest()
        except:
            pass
        # Make sure we close our file handle, or seek to 0
        finish(f,path)
        return "" # Couldn't determine hash :(

    def oc_snapshot(self, event = None, clean = False):
        # Make sure we have snapshot data from the controller
        if not self.controller.snapshot_data:
            self.bell()
            mb.showerror(
                "OC{} Snapshot Aborted".format(
                    " Clean" if clean else ""
                ),
                (
                    "{} is missing or malformed.\n\n"
                    "Please correct or replace the file.\n\n"
                    "If running from a network drive or cloud backup, try running locally."
                ).format(
                    os.path.join(os.path.abspath(os.path.dirname(os.path.realpath(__file__))),"snapshot.plist")
                ),
                parent=self
            )
            return
        # Get the target directory from our current file's directory - if any, and if it exists
        target_dir = os.path.dirname(self.current_plist) if self.current_plist and os.path.isdir(os.path.dirname(self.current_plist)) else None
        # If it doesn't exist, get the last_snapshot_path, if any
        target_dir = target_dir or self.controller.settings.get("last_snapshot_path")
        # Ensure it's a directory if we have something
        if target_dir and not os.path.isdir(target_dir):
            target_dir = None # Reset to nothing
        # Prompt for the OC folder
        oc_folder = fd.askdirectory(title="Select OC Folder:",initialdir=target_dir)
        self.controller.lift_window(self) # Lift the window to continue catching events
        if not len(oc_folder):
            return

        # Verify folder structure - should be as follows:
        # OC
        #  +- ACPI
        #  | +- SSDT.aml/.bin
        #  +- Drivers
        #  | +- EfiDriver.efi
        #  +- Kexts
        #  | +- Something.kext
        #  +- config.plist
        #  +- Tools (Optional)
        #  | +- SomeTool.efi
        #  | +- SomeFolder
        #  | | +- SomeOtherTool.efi
        
        def check_folders(path):
            return_dict = {
                "oc_acpi":   os.path.normpath(os.path.join(path,"ACPI")),
                "oc_drivers":os.path.normpath(os.path.join(path,"Drivers")),
                "oc_kexts":  os.path.normpath(os.path.join(path,"Kexts")),
                "oc_tools":  os.path.normpath(os.path.join(path,"Tools")),
                "oc_efi":    os.path.normpath(os.path.join(path,"OpenCore.efi"))
            }
            return_dict["missing"] = [return_dict[x] for x in ("oc_acpi","oc_drivers","oc_kexts") if not os.path.isdir(return_dict[x])]
            return return_dict

        oc_path_check = check_folders(oc_folder)
        if oc_path_check["missing"]:
            # User might have selected their EFI folder - try to resolve
            # an OC folder within
            efi_oc_folder = os.path.join(oc_folder,"OC")
            efi_path_check = check_folders(efi_oc_folder)
            if efi_path_check["missing"]:
                # No dice - show the missing dialog box
                self.bell()
                mb.showerror(
                    "Incorrect OC Folder Structure",
                    "The following required folders do not exist:\n\n{}\n\nPlease make sure you're selecting a valid OC folder.".format(
                        ", ".join([os.path.basename(x) for x in oc_path_check["missing"]])
                    ),
                    parent=self
                )
                return
            # We got it - update path related vars
            oc_folder = efi_oc_folder
            oc_path_check = efi_path_check
        
        # Extract our vars
        oc_acpi    = oc_path_check["oc_acpi"]
        oc_drivers = oc_path_check["oc_drivers"]
        oc_kexts   = oc_path_check["oc_kexts"]
        oc_tools   = oc_path_check["oc_tools"]
        oc_efi     = oc_path_check["oc_efi"]

        # Folders are valid - let's save a reference for next time and work through each section
        self.controller.settings["last_snapshot_path"] = oc_folder
        # Let's get the hash of OpenCore.efi, compare to a known list, and then compare that version to our snapshot_version if found
        oc_hash = self.get_hash(oc_efi)
        # Let's get the version of the snapshot that matches our target, and that matches our hash if any
        latest_snap = {} # Highest min_version
        target_snap = {} # Matches our hash
        select_snap = {} # Whatever the user selected
        user_snap   = self.controller.settings.get("snapshot_version","Auto-detect")
        for snap in self.controller.snapshot_data:
            hashes = snap.get("release_hashes",[])
            hashes.extend(snap.get("debug_hashes",[]))
            # Retain the highest version we see
            if snap.get("min_version","0.0.0") > latest_snap.get("min_version","0.0.0"):
                latest_snap = snap
                # If we want the latest, retain the select_snap as well
                if user_snap.lower() == "latest": select_snap = snap
            # Also retain the last snap that matches our hash
            if len(oc_hash) and (oc_hash in snap.get("release_hashes",[]) or oc_hash in snap.get("debug_hashes",[])):
                target_snap = snap
                # If we're auto-detecting, retain the select_snap as well
                if user_snap.lower() == "auto-detect": select_snap = snap
            # Save the snap that matches the user's choice too if not Latest or Auto-detect
            if user_snap.lower() not in ("auto-detect","latest") and user_snap >= snap.get("min_version","0.0.0") and snap.get("min_version","0.0.0") > select_snap.get("min_version","0.0.0"):
                select_snap = snap
        # Make sure we have a value for select_snap - either its own, or the latest
        select_snap = select_snap or latest_snap
        if target_snap and target_snap != select_snap: # Version mismatch - warn
            tar_min,tar_max = target_snap.get("min_version","0.0.0"),target_snap.get("max_version","Current")
            sel_min,sel_max = select_snap.get("min_version","0.0.0"),select_snap.get("max_version","Current")
            found_ver  = tar_min if tar_min==tar_max else "{} -> {}".format(tar_min,tar_max)
            select_ver = sel_min if sel_min==sel_max else "{} -> {}".format(sel_min,sel_max)
            if mb.askyesno("Snapshot Version Mismatch","Detected OpenCore.efi version: {}\n\nOC Snapshot target version: {}{}\n\nWould you like to snapshot for the detected OpenCore.efi version instead?".format(
                found_ver,
                select_ver,
                " (Latest)" if user_snap.lower() == "latest" else ""
            ),parent=self):
                # We want to change for this snapshot
                select_snap = target_snap
        # Apply our snapshot values
        acpi_add   = select_snap.get("acpi_add",{})
        kext_add   = select_snap.get("kext_add",{})
        tool_add   = select_snap.get("tool_add",{})
        driver_add = select_snap.get("driver_add",{})

        long_paths = [] # We'll add any paths that exceed the OC_STORAGE_SAFE_PATH_MAX of 128 chars

        tree_dict = self.nodes_to_values(binary=False)
        # We have our plist contents - let's check all our paths and types - and ensure
        # that things line up as needed.  If not - we'll warn the user, and ask if they
        # want to continue.
        path_walk = (
            (("ACPI","Add"),list),
            (("Kernel","Add"),list),
            (("Misc","Tools"),list),
            (("UEFI","Drivers"),list)
        )
        missing_paths = []
        incorrect_types = []
        dict_type = dict if self.controller.settings.get("sort_dict",False) else OrderedDict
        for path_list,path_type in path_walk:
            # Start with a top-level perspective, and walk paths as needed
            target_path = tree_dict
            path_missing = False
            for i,path in enumerate(path_list,start=1):
                use_type = path_type if i >= len(path_list) else dict_type
                if not path in target_path:
                    # The path is missing - let's create it in the tree_dict
                    # in case the user wants to continue
                    target_path[path] = use_type()
                    if not path_missing:
                        # Let's also toggle our boolean to prevent referencing
                        # multiple steps in the same path, and save the highest
                        # level missing path to report
                        path_missing = True
                        missing_paths.append(" -> ".join(path_list[:i]))
                else:
                    # Check types
                    if not isinstance(target_path[path],path_type if i >= len(path_list) else dict):
                        # Incorrect type.  Save that for later, and update
                        # the tree_dict
                        exp_type = self.get_type(use_type(),menu_code=False)
                        got_type = self.get_type(target_path[path],menu_code=False)
                        incorrect_types.append("{}: Expected {}, got {}".format(
                            " -> ".join(path_list[:i]),
                            exp_type,
                            got_type
                        ))
                        target_path[path] = use_type()
                # Update our scope for the next loop
                target_path = target_path[path]
        # Check if we have any missing paths or incorrect types - and show a dialog as
        # needed
        if missing_paths or incorrect_types:
            # Let's build our error
            error_list = []
            verb = []
            title = []
            if missing_paths:
                title.append("Incomplete")
                verb.append("add missing paths")
                error_list.extend(
                    ["The following entries are missing:\n"] + missing_paths + [""]
                )
            if incorrect_types:
                title.append("Incorrect")
                verb.append("fix incorrect types")
                error_list.extend(
                    ["The following types are incorrect:\n"] + incorrect_types + [""]
                )
            # Flesh out the rest of the error - offering to correct the above
            error_list.extend([
                "This may mean that your plist is incomplete, or you are performing an OC{} Snapshot on the wrong file.\n".format(
                    " Clean" if clean else ""
                ),
                "Would you like to {} and continue?".format(", ".join(verb))
            ])
            if not mb.askyesno("{} Plist Structure".format("/".join(title)),"\n".join(error_list),parent=self):
                # User said "no", let's bail
                return

        def path_is_valid(test_path):
            # Check if any of the path elements equal __MACOSX and skip those
            # as we don't want to include extended attributes or similar.
            return not any(x == "__MACOSX" for x in os.path.normpath(test_path).split(os.path.sep))

        # ACPI is first, we'll iterate the .aml/.bin files we have and add what is missing
        # while also removing what exists in the plist and not in the folder.
        # If something exists in the table already, we won't touch it.  This leaves the
        # enabled and comment properties untouched.
        #
        # Now we walk the existing add values
        new_acpi = []
        for path, subdirs, files in os.walk(oc_acpi):
            if not path_is_valid(path):
                continue
            for name in files:
                if not name.startswith(".") and name.lower().endswith((".aml",".bin")):
                    new_acpi.append(os.path.join(path,name)[len(oc_acpi):].replace("\\", "/").lstrip("/"))
        add = [] if clean else tree_dict["ACPI"]["Add"]
        for aml in sorted(new_acpi,key=lambda x:x.lower()):
            if aml.lower() in [x.get("Path","").lower() for x in add if isinstance(x,dict)]:
                # Found it - skip
                continue
            # Doesn't exist, add it
            new_aml_entry = {
                "Comment":os.path.basename(aml),
                "Enabled":True,
                "Path":aml
            }
            # Add our snapshot custom entries, if any
            for x in acpi_add: new_aml_entry[x] = acpi_add[x]
            add.append(OrderedDict(sorted(new_aml_entry.items(),key=lambda x: str(x[0]).lower())))
        new_add = []
        for aml in add:
            if not isinstance(aml,dict):
                # Not the right type - skip it
                continue
            if not aml.get("Path","").lower() in [x.lower() for x in new_acpi]:
                # Not there, skip
                continue
            new_add.append(aml)
            # Check path length
            long_paths.extend(self.check_path_length(aml,self.acpi_path))
        # Make sure we don't have duplicates
        acpi_enabled = []
        acpi_duplicates = []
        acpi_duplicates_disabled = []
        for a in new_add:
            if a.get("Enabled"):
                if a.get("Path","") in acpi_enabled:
                    # Got a dupe - shallow copy and disable
                    new_a = OrderedDict() if isinstance(a,OrderedDict) else {}
                    for key in a: new_a[key] = a[key]
                    new_a["Enabled"] = False
                    acpi_duplicates_disabled.append(new_a)
                    if not a.get("Path","") in acpi_duplicates:
                        acpi_duplicates.append(a.get("Path",""))
                else:
                    # First hit - add the Path to acpi_enabled
                    acpi_enabled.append(a.get("Path",""))
                    acpi_duplicates_disabled.append(a)
        if len(acpi_duplicates):
            if mb.askyesno("Duplicate ACPI Paths","Disable the following ACPI entries with duplicate Paths?\n\n{}".format("\n".join(acpi_duplicates)),parent=self):
                new_add = acpi_duplicates_disabled
        # Save the results
        tree_dict["ACPI"]["Add"] = new_add

        # Now we need to walk the kexts
        kext_list = []
        omitted_kexts = []
        # We need to check any directory whose name ends with .kext
        for path, subdirs, files in os.walk(oc_kexts):
            if not path_is_valid(path):
                continue
            for name in sorted(subdirs, key=lambda x:x.lower()):
                if name.startswith(".") or not name.lower().endswith(".kext"): continue
                kdict = {
                    # "Arch":"Any",
                    "BundlePath":os.path.join(path,name)[len(oc_kexts):].replace("\\", "/").lstrip("/"),
                    "Comment":name,
                    "Enabled":True,
                    # "MaxKernel":"",
                    # "MinKernel":"",
                    "ExecutablePath":""
                }
                # Add our entries from kext_add as needed
                for y in kext_add: kdict[y] = kext_add[y]
                # Get the Info.plist
                plist_full_path = plist_rel_path = None
                for kpath, ksubdirs, kfiles in os.walk(os.path.join(path,name)):
                    if not path_is_valid(kpath):
                        continue
                    for kname in kfiles:
                        if kname.lower() == "info.plist":
                            plist_full_path = os.path.join(kpath,kname)
                            plist_rel_path  = plist_full_path[len(os.path.join(path,name)):].replace("\\", "/").lstrip("/")
                            break
                    if plist_full_path: break # Found it - break
                else:
                    # Didn't find it - skip
                    omitted_kexts.append(name)
                    continue
                kdict["PlistPath"] = plist_rel_path
                # Let's load the plist and check for other info
                try:
                    with open(plist_full_path,"rb") as f:
                        info_plist = plist.load(f)
                    if not "CFBundleIdentifier" in info_plist or not isinstance(info_plist["CFBundleIdentifier"],basestring):
                        omitted_kexts.append(name)
                        continue # Requires a valid CFBundleIdentifier string
                    kinfo = {
                        "CFBundleIdentifier": info_plist["CFBundleIdentifier"],
                        "OSBundleLibraries": info_plist.get("OSBundleLibraries",[]),
                        "cfbi": info_plist["CFBundleIdentifier"].lower(), # Case insensitive
                        "osbl": [x.lower() for x in info_plist.get("OSBundleLibraries",[]) if isinstance(x,basestring)] # Case insensitive
                    }
                    if info_plist.get("CFBundleExecutable",None):
                        exec_rel_path  = None
                        exec_full_path = os.path.join(path,name,"Contents","MacOS",info_plist["CFBundleExecutable"])
                        if os.path.exists(exec_full_path):
                            # Found it in the usual spot
                            exec_rel_path = "Contents/MacOS/"+info_plist["CFBundleExecutable"]
                        else:
                            # Didn't find it in the usual spot - check for it anywhere in the kext
                            cfbundle_lower = info_plist["CFBundleExecutable"].lower()
                            exec_rel_path = exec_full_path = None
                            for kpath, ksubdirs, kfiles in os.walk(os.path.join(path,name)):
                                if not path_is_valid(kpath):
                                    continue
                                for kname in kfiles:
                                    if kname.lower() == cfbundle_lower:
                                        exec_full_path = os.path.join(kpath,kname)
                                        exec_rel_path  = exec_full_path[len(os.path.join(path,name)):].replace("\\", "/").lstrip("/")
                                        break
                        if not exec_rel_path or not exec_full_path or not os.path.getsize(exec_full_path):
                            omitted_kexts.append(name)
                            continue # Requires an executable that doesn't exist - bail
                        # Found something
                        kdict["ExecutablePath"] = exec_rel_path
                except Exception as e:
                    omitted_kexts.append(name)
                    continue # Something else broke here - bail
                # Should have something valid here
                kext_list.append((OrderedDict(sorted(kdict.items(),key=lambda x: str(x[0]).lower())),kinfo))
        if omitted_kexts:
            mb.showwarning(
                "Invalid Kexts",
                "The following kexts have been omitted from the snapshot as they are incomplete or incorrectly configured:\n\n{}".format(
                    "\n".join(omitted_kexts)
                ),
                parent=self
            )
        bundle_list = [x[0].get("BundlePath","") for x in kext_list]
        kexts = [] if clean else tree_dict["Kernel"]["Add"]
        original_kexts = [x for x in kexts if isinstance(x,dict) and x.get("BundlePath","") in bundle_list] # get the original load order for comparison purposes - but omit any that no longer exist
        for kext,info in kext_list:
            if kext["BundlePath"].lower() in [x.get("BundlePath","").lower() for x in kexts if isinstance(x,dict)]:
                # Already have it, skip
                continue
            # We need it, it seems
            kexts.append(kext)
        new_kexts = []
        for kext in kexts:
            if not isinstance(kext,dict) or not kext.get("BundlePath"):
                # Not a dict, or missing BundlePath - skip it
                continue
            # Get our first match based on BundlePath which should be unique
            kext_match = next((k for k,i in kext_list if k["BundlePath"].lower() == kext["BundlePath"].lower()),None)
            if not kext_match:
                # Not there, skip it
                continue
            # Make sure the ExecutablePath and PlistPath are updated if different
            for check in ("ExecutablePath","PlistPath"):
                if kext.get(check,"") != kext_match.get(check,""):
                    kext[check] = kext_match.get(check,"")
            new_kexts.append(kext)
        # Let's check inheritance via the info
        unordered_kexts = []
        for x in new_kexts:
            info = next((y[1] for y in kext_list if y[0].get("BundlePath","") == x.get("BundlePath","")),None)
            if not info: continue
            parents = [(z,y[1]) for z in new_kexts for y in kext_list if z.get("BundlePath","") == y[0].get("BundlePath","") if y[1].get("cfbi",None) in info.get("osbl",[])]
            children = [next((z for z in new_kexts if z.get("BundlePath","") == y[0].get("BundlePath","")),[]) for y in kext_list if info.get("cfbi",None) in y[1].get("osbl",[])]
            unordered_kexts.append({
                "kext":x,
                "parents":parents
            })
        ordered_kexts = []
        disabled_parents = []
        cyclic_kexts = []
        loops_without_changes = 0
        cyclic_dependencies = False
        while len(unordered_kexts): # This could be dangerous if things aren't properly prepared above
            kext = unordered_kexts.pop(0)
            if len(kext["parents"]):
                # Gather a list of enabled/disabled parents - and ensure we properly populate
                # our disabled_parents list
                enabled_parents = [x[1].get("cfbi") for x in kext["parents"] if x[0].get("Enabled")]
                if kext["kext"].get("Enabled"):
                    for p in kext["parents"]:
                        p_cf = p[1].get("cfbi")
                        if not p_cf: continue # Broken - can't check
                        if p_cf in enabled_parents: continue # Already have an enabled copy
                        if any((p_cf == x[1].get("cfbi") for x in disabled_parents)):
                            continue # Already have a warning copy
                        disabled_parents.append(p)
                if not all(x[0] in ordered_kexts for x in kext["parents"]):
                    loops_without_changes += 1
                    cyclic_kexts.append(kext["kext"])
                    if loops_without_changes > len(unordered_kexts):
                        cyclic_dependencies = True
                        break
                    unordered_kexts.append(kext)
                    continue
            cyclic_kexts = [] # Reset the cyclic kext list
            loops_without_changes = 0 # Reset the counter
            ordered_kexts.append(kext["kext"])
        # If we bailed because of cyclic deps - let's warn the user
        if cyclic_dependencies:
            mb.showwarning(
                "Cyclic Kext Dependencies",
                "The following kexts have been omitted from the snapshot for cyclic dependencies:\n\n{}".format(
                    "\n".join([x.get("BundlePath","") for x in cyclic_kexts])
                ),
                parent=self
            )
        # Let's compare against the original load order - to prevent mis-prompting
        missing_kexts = [x for x in ordered_kexts if not x in original_kexts]
        original_kexts.extend(missing_kexts)
        # Let's walk both lists and gather all kexts that are in different spots
        rearranged = []
        while True:
            check1 = [x.get("BundlePath","") for x in ordered_kexts if not x.get("BundlePath","") in rearranged]
            check2 = [x.get("BundlePath","") for x in original_kexts if not x.get("BundlePath","") in rearranged]
            out_of_place = next((x for x in range(len(check1)) if check1[x] != check2[x]),None)
            if out_of_place is None: break
            rearranged.append(check2[out_of_place])
        # Verify if the load order changed - and prompt the user if need be
        if len(rearranged):
            if not mb.askyesno("Incorrect Kext Load Order","Correct the following kext load inheritance issues?\n\n{}".format("\n".join(rearranged)),parent=self):
                ordered_kexts = original_kexts # We didn't want to update it
        if len(disabled_parents):
            if mb.askyesno("Disabled Parent Kexts","Enable the following disabled parent kexts?\n\n{}".format("\n".join([x[0].get("BundlePath","") for x in disabled_parents])),parent=self):
                for p in disabled_parents: p[0]["Enabled"] = True
        # Finally - we walk the kexts and ensure that we're not loading the same CFBundleIdentifier more than once
        enabled_kexts = []
        bundles_enabled = []
        duplicate_bundles = []
        duplicates_disabled = []
        for kext in ordered_kexts:
            # Check path length
            long_paths.extend(self.check_path_length(kext,self.kext_path))
            temp_kext = OrderedDict() if isinstance(kext,OrderedDict) else {}
            # Shallow copy the kext entry to avoid changing it in ordered_kexts
            for x in kext: temp_kext[x] = kext[x]
            duplicates_disabled.append(temp_kext)
            # Ignore if alreday disabled
            if not temp_kext.get("Enabled",False): continue
            # Ensure we haven't already seen this BundlePath before
            if temp_kext.get("BundlePath","") in bundles_enabled+duplicate_bundles:
                temp_kext["Enabled"] = False
                # Make sure we keep a reference to the bundle if needed
                if not temp_kext.get("BundlePath","") in duplicate_bundles:
                    duplicate_bundles.append(temp_kext.get("BundlePath",""))
            else:
                # Get the original info
                info = next((x[1] for x in kext_list if x[0].get("BundlePath","") == temp_kext.get("BundlePath","")),None)
                if not info or not info.get("cfbi",None): continue # Broken info
                # Let's see if it's already in enabled_kexts - and compare the Min/Max/Match Kernel options
                temp_min,temp_max = self.get_min_max_from_kext(temp_kext,"MatchKernel" in kext_add)
                # Gather a list of like IDs
                comp_kexts = [x for x in enabled_kexts if x[1]["cfbi"] == info["cfbi"]]
                # Walk the comp_kexts, and disable if we find an overlap
                for comp_info in comp_kexts:
                    comp_kext = comp_info[0]
                    # Gather our min/max
                    comp_min,comp_max = self.get_min_max_from_kext(comp_kext,"MatchKernel" in kext_add)
                    # Let's see if we don't overlap
                    if temp_min > comp_max or temp_max < comp_min: # We're good, continue
                        continue
                    # We overlapped - let's disable it
                    temp_kext["Enabled"] = False
                    # Add it to the list - then break out of this 
                    if not temp_kext.get("BundlePath","") in duplicate_bundles:
                        duplicate_bundles.append(temp_kext.get("BundlePath",""))
                    break
            # Check if we ended up disabling temp_kext, and if not - add it to the enabled_kexts list
            if temp_kext.get("Enabled",False):
                bundles_enabled.append(temp_kext.get("BundlePath",""))
                enabled_kexts.append((temp_kext,info))
        # Check if we have duplicates - and offer to disable them
        if len(duplicate_bundles):
            if mb.askyesno("Duplicate CFBundleIdentifiers","Disable the following kexts with duplicate CFBundleIdentifiers?\n\n{}".format("\n".join(duplicate_bundles)),parent=self):
                ordered_kexts = duplicates_disabled
        tree_dict["Kernel"]["Add"] = ordered_kexts

        # Let's walk the Tools folder if it exists
        if os.path.exists(oc_tools) and os.path.isdir(oc_tools):
            tools_list = []
            # We need to gather a list of all the files inside that and with .efi
            for path, subdirs, files in os.walk(oc_tools):
                if not path_is_valid(path):
                    continue
                for name in files:
                    if not name.startswith(".") and name.lower().endswith(".efi"):
                        # Save it
                        new_tool_entry = {
                            # "Arguments":"",
                            # "Auxiliary":True,
                            "Name":name,
                            "Comment":name,
                            "Enabled":True,
                            "Path":os.path.join(path,name)[len(oc_tools):].replace("\\", "/").lstrip("/") # Strip the /Volumes/EFI/
                        }
                        # Add our snapshot custom entries, if any
                        for x in tool_add:
                            if x == "Flavour" and new_tool_entry["Name"].lower().endswith("shell.efi"):
                                # Adjust the Flavour to reflect what type of shell it is - we can use OpenShell:UEFIShell:Shell
                                # to reflect this
                                new_tool_entry[x] = "OpenShell:UEFIShell:Shell"
                            else:
                                new_tool_entry[x] = tool_add[x]
                        tools_list.append(OrderedDict(sorted(new_tool_entry.items(),key=lambda x:str(x[0]).lower())))
            tools = [] if clean else tree_dict["Misc"]["Tools"]
            for tool in sorted(tools_list, key=lambda x: x.get("Path","").lower()):
                if tool["Path"].lower() in [x.get("Path","").lower() for x in tools if isinstance(x,dict)]:
                    # Already have it, skip
                    continue
                # We need it, it seems
                tools.append(tool)
            new_tools = []
            for tool in tools:
                if not isinstance(tool,dict):
                    # Not a dict - skip it
                    continue
                if not tool.get("Path","").lower() in [x["Path"].lower() for x in tools_list]:
                    # Not there, skip it
                    continue
                new_tools.append(tool)
                # Check path length
                long_paths.extend(self.check_path_length(tool,self.tool_path))
            # Make sure we don't have duplicates
            tools_enabled = []
            tools_duplicates = []
            tools_duplicates_disabled = []
            for t in new_tools:
                if t.get("Enabled"):
                    if t.get("Path","") in tools_enabled:
                        # Got a dupe - shallow copy and disable
                        new_t = OrderedDict() if isinstance(t,OrderedDict) else {}
                        for key in t: new_t[key] = t[key]
                        new_t["Enabled"] = False
                        tools_duplicates_disabled.append(new_t)
                        if not t.get("Path","") in tools_duplicates:
                            tools_duplicates.append(t.get("Path",""))
                    else:
                        # First hit - add the Path to tools_enabled
                        tools_enabled.append(t.get("Path",""))
                        tools_duplicates_disabled.append(t)
            if len(tools_duplicates):
                if mb.askyesno("Duplicate Tools","Disable the following Tools with duplicate Paths?\n\n{}".format("\n".join(tools_duplicates)),parent=self):
                    new_tools = tools_duplicates_disabled
            # Save the results
            tree_dict["Misc"]["Tools"] = new_tools
        else:
            # Make sure our Tools list is empty
            tree_dict["Misc"]["Tools"] = []

        # Last we need to walk the .efi drivers
        drivers_list = []
        # We need to gather a list of all the files inside that and with .efi
        for path, subdirs, files in os.walk(oc_drivers):
            if not path_is_valid(path):
                continue
            for name in files:
                if not name.startswith(".") and name.lower().endswith(".efi"):
                    # Check if we're using the new approach - or just listing the paths
                    if not driver_add:
                        drivers_list.append(os.path.join(path,name)[len(oc_drivers):].replace("\\", "/").lstrip("/")) # Strip the /Volumes/EFI/
                    else:
                        new_driver_entry = {
                            # "Arguments": "",
                            "Enabled":True,
                            "Path":os.path.join(path,name)[len(oc_drivers):].replace("\\", "/").lstrip("/") # Strip the /Volumes/EFI/
                        }
                        # Add our snapshot custom entries, if any - include the name of the .efi driver if the Comment
                        for x in driver_add: new_driver_entry[x] = name if x.lower() == "comment" else driver_add[x]
                        drivers_list.append(OrderedDict(sorted(new_driver_entry.items(),key=lambda x:str(x[0]).lower())))
        drivers = [] if clean else tree_dict["UEFI"]["Drivers"]
        for driver in sorted(drivers_list, key=lambda x: x.get("Path","").lower() if driver_add else x):
            if not driver_add: # Old way
                if not isinstance(driver,basestring) or driver.lower() in [x.lower() for x in drivers if isinstance(x,basestring)]:
                    continue
            else:
                if driver["Path"].lower() in [x.get("Path","").lower() for x in drivers if isinstance(x,dict)]:
                    # Already have it, skip
                    continue
            # We need it, it seems
            drivers.append(driver)
        new_drivers = []
        for driver in drivers:
            if not driver_add: # Old way
                if not isinstance(driver,basestring) or not driver.lower() in [x.lower() for x in drivers_list if isinstance(x,basestring)]:
                    continue
            else:
                if not isinstance(driver,dict):
                    # Not a dict - skip it
                    continue
                if not driver.get("Path","").lower() in [x["Path"].lower() for x in drivers_list]:
                    # Not there, skip it
                    continue
            new_drivers.append(driver)
            # Check path length
            long_paths.extend(self.check_path_length(driver,self.uefi_driver_path))
        # Make sure we don't have duplicates
        drivers_enabled = []
        drivers_duplicates = []
        drivers_duplicates_disabled = []
        for d in new_drivers:
            if isinstance(d,dict):
                # The new way
                if d.get("Enabled"):
                    if d.get("Path","") in drivers_enabled:
                        # Got a dupe - shallow copy and disable
                        new_d = OrderedDict() if isinstance(d,OrderedDict) else {}
                        for key in d: new_d[key] = d[key]
                        new_d["Enabled"] = False
                        drivers_duplicates_disabled.append(new_d)
                        if not d.get("Path","") in drivers_duplicates:
                            drivers_duplicates.append(d.get("Path",""))
                    else:
                        # First hit - add the Path to drivers_enabled
                        drivers_enabled.append(d.get("Path",""))
                        drivers_duplicates_disabled.append(d)
            else:
                # The old way
                if d in drivers_enabled:
                    # Got a dupe
                    if not d in drivers_duplicates:
                        drivers_duplicates.append(d)
                else:
                    drivers_enabled.append(d)
                    drivers_duplicates_disabled.append(d)
        if len(drivers_duplicates):
            if mb.askyesno("Duplicate Drivers","Disable the following Drivers with duplicate Paths?\n\n{}".format("\n".join(drivers_duplicates)),parent=self):
                new_drivers = drivers_duplicates_disabled
        # Save the results
        tree_dict["UEFI"]["Drivers"] = new_drivers

        # Check if we're forcing schema - and ensure values line up
        if self.controller.settings.get("force_snapshot_schema",False):
            ignored = ["Comment","Enabled","Path","BundlePath","ExecutablePath","PlistPath","Name"]
            for entries,values in ((tree_dict["ACPI"]["Add"],acpi_add),(tree_dict["Kernel"]["Add"],kext_add),(tree_dict["Misc"]["Tools"],tool_add),(tree_dict["UEFI"]["Drivers"],driver_add)):
                values["Comment"] = ""
                values["Enabled"] = True
                if not values: continue # Skip if nothing to check
                for entry in entries:
                    to_remove = [x for x in entry if not x in values and not x in ignored]
                    to_add =    [x for x in values if not x in entry]
                    for add in to_add:
                        if add.lower() == "comment":
                            val = os.path.basename(entry.get("Path",entry.get("BundlePath",values[add])))
                        else:
                            val = values[add]
                        entry[add] = val
                    for rem in to_remove:
                        entry.pop(rem,None)
        
        # Now we remove the original tree - then replace it
        undo_list = []
        for x in self._tree.get_children():
            undo_list.append({
                "type":"remove",
                "cell":x,
                "from":self._tree.parent(x),
                "index":self._tree.index(x)
            })
            self._tree.detach(x)
        # Finally, we add the nodes back
        self.add_node(tree_dict)
        # Add all the root items to our undo list
        for child in self._tree.get_children():
            undo_list.append({
                "type":"add",
                "cell":child
            })
        self.add_undo(undo_list)
        # Select the root element
        self.select(self.get_root_node())
        # Ensure we're edited
        self._ensure_edited()
        self.update_all_children()
        self.alternate_colors()
        # Check if we have any paths that are too long
        if long_paths:
            formatted = []
            for entry in long_paths:
                item,name,keys = entry
                if isinstance(item,basestring): # It's an older string path
                    formatted.append(name)
                elif isinstance(item,dict):
                    formatted.append("{} -> {}".format(name,", ".join(keys)))
            # Show the dialog warning of lengthy paths
            mb.showwarning(
                "Potentially Unsafe Paths",
                "The following exceed the {:,} character safe path max declared by OpenCore and may not work as intended:\n\n{}".format(
                    self.safe_path_length,
                    "\n".join(formatted)
                ),
                parent=self
            )

    def get_check_type(self, cell=None, string=None):
        if not cell is None:
            t = self.get_padded_values(cell,1)[0]
        elif not string is None:
            t = string
        else:
            return None
        if t.startswith(self.menu_code):
            t = t.replace(self.menu_code+" ","")
            t = t.replace(self.menu_code,"")
        return t

    def clicked(self, event = None):
        # Reset every click
        self.clicked_drag = False
        if not event or not self.controller.enable_drag_and_drop.get():
            return
        rowid = self._tree.identify_row(event.y)
        if rowid and self._tree.bbox(rowid):
            self.clicked_drag = True
    
    def _change_display(self,new_display,target_funct):
        # Walks the nodes, undo, and redo stacks and runs
        # the target funct accordingly
        target_funct(self.iter_nodes(False),new_display)
        for u in self.undo_stack:
            target_funct(u,new_display)
        for r in self.redo_stack:
            target_funct(r,new_display)

    def _qualify_node(self,node,type_check):
        # Helper function to qualify a passed node - or check if it's
        # an undo/redo entry.  Returns (None,None,None) if it doesn't qualify,
        # or a tuple of (node,task,values)
        task = None
        if isinstance(node,dict): # Should be an undo/redo action
            if node.get("type") in ("move","add"): return (None,None,None) # Handled by the nodes loop
            task = node
            node = task.get("cell")
        if not node: return (None,None,None) # Broken formatting?
        if task and task.get("type") == "edit":
            values = list(task.get("values",[]))
            if len(values) < 2: return (None,None,None) # Broken :(
        else:
            values = self.get_padded_values(node,3)
        t = self.get_check_type(cell=None,string=values[0]).lower()
        if t != type_check: return (None,None,None)
        return (node,task,values)

    def change_int_display(self,new_display="Decimal"):
        if new_display == self.last_int: return
        self.int_type_string.set(new_display[0].upper()+new_display[1:])
        self._change_display(new_display,self._change_int_display)

    def _change_int_display(self,node_list,new_display="Decimal"):
        if not isinstance(node_list,(list,tuple,deque)): node_list = [node_list]
        for node in node_list:
            node,task,values = self._qualify_node(node,"number")
            if task == False or values is None: continue # Didn't qualify
            value = values[1]
            if new_display.lower() == "hex":
                try:
                    value = int(value)
                    if value >= 0: value = "0x"+hex(value).upper()[2:]
                except: pass
            else:
                if value.lower().startswith("0x"):
                    value = str(int(value,16))
            values[1] = value
            if task and task.get("type") == "edit":
                task["values"] = values
            else:
                self._tree.item(node,values=values)

    def change_bool_display(self,new_display="True/False"):
        if new_display == self.last_bool: return
        self.bool_type_string.set(new_display)
        # Walk all nodes, then walk the undo/redo stack to ensure
        # all bool values are updated.
        self._change_display(new_display,self._change_bool_display)

    def _change_bool_display(self,node_list,new_display="True/False"):
        if not isinstance(node_list,(list,tuple,deque)): node_list = [node_list]
        on,off = new_display.split("/")
        on_list = [x.split("/")[0] for x in self.controller.allowed_bool]
        for node in node_list:
            node,task,values = self._qualify_node(node,"boolean")
            if task == False or values is None: continue # Didn't qualify
            values[1] = on if values[1] in on_list else off
            if task and task.get("type") == "edit":
                task["values"] = values
            else:
                self._tree.item(node,values=values)

    def change_data_display(self,new_display="Hex"):
        if new_display == self.last_data: return
        self.data_type_string.set(new_display[0].upper()+new_display[1:])
        # This will change how data is displayed - we do this by converting all our existing
        # data values to bytes, then reconverting and displaying appropriately
        self._change_display(new_display,self._change_data_display)

    def _change_data_display(self,node_list,new_display="Hex"):
        if not isinstance(node_list,(list,tuple,deque)): node_list = [node_list]
        for node in node_list:
            node,task,values = self._qualify_node(node,"data")
            if values is None: continue # Didn't qualify
            value = values[1]
            # We need to adjust how it is displayed, load the bytes first
            if new_display.lower() == "hex":
                # Convert to hex
                if sys.version_info < (3,0):
                    value = binascii.hexlify(base64.b64decode(value))
                else:
                    value = binascii.hexlify(base64.b64decode(value.encode("utf-8"))).decode("utf-8")
                # format the hex
                value = "<{}>".format(" ".join((value[0+i:8+i] for i in range(0, len(value), 8))).upper())
            else:
                # Assume base64
                if sys.version_info < (3, 0):
                    value = base64.b64encode(binascii.unhexlify(value.replace("<","").replace(">","").replace(" ","")))
                else:
                    value = base64.b64encode(binascii.unhexlify(value.replace("<","").replace(">","").replace(" ","").encode("utf-8"))).decode("utf-8")
            values[1] = value
            if task and task.get("type") == "edit":
                task["values"] = values
            else:
                self._tree.item(node,values=values)

    def add_undo(self, action):
        if not isinstance(action,list):
            action = [action]
        try: # Get the max undo items
            max_undo = int(self.controller.undo_max_text.get())
            assert max_undo >= 0
        except:
            max_undo = self.controller.max_undo
        self.undo_stack.append(action)
        # See if we need to limit the undo_stack
        if max_undo > 0:
            # Pop the first item until we're at/under max
            while len(self.undo_stack) > max_undo:
                self.undo_stack.popleft()
        self.redo_stack = [] # clear the redo stack

    def reundo(self, event=None, undo = True, single_undo = None):
        # We can't start a new reundo until the last has finished
        if self.reundoing: return
        # Lock the reundo task to this instance
        self.reundoing = True
        # Let's come up with a more centralized way to do this
        # We'll break down the potential actions into a few types:
        #
        # add, remove, edit
        #
        # edited:  {"type":"edit","cell":cell_edited,"text":text_value,"values":values_list}
        # added:   {"type":"add","cell":cell_added}
        # removed: {"type":"remove","cell":cell_removed,"from":cell_removed_from,"index":index_in_parent_children}
        # moved:   {"type":"move","cell":cell_moved,"from":old_parent,"to":new_parent,"index":index_in_old_parent}
        #
        # All actions are lists of individual changes, in the order they happened.
        # If a cell was changed from a Dict to a String, we would have a removed entry
        # for each child under that cell, then an edit entry for the cell itself.
        #
        if undo:
            u = self.undo_stack
            r = self.redo_stack
        else:
            r = self.undo_stack
            u = self.redo_stack
        # Allow a single undo without any trace
        if single_undo != None:
            u = [single_undo]
            r = []
        if not len(u):
            self.bell()
            # Nothing to undo/redo
            self.reundoing = False
            return
        # Check if we have any open EntryPopups and cancel them
        if self.entry_popup:
            self.entry_popup.cancel()
        # Retain the original selection
        selected,nodes = self.preselect()
        task_list = u.pop()
        r_task_list = []
        # Iterate in reverse to undo the last thing first
        for task in task_list[::-1]:
            cell = task["cell"]
            ttype = task["type"].lower()
            if ttype == "edit":
                # We changed something in the cell, build a snapshot of the current
                r_task_list.append({
                    "type":"edit",
                    "cell":cell,
                    "text":self._tree.item(cell,"text"),
                    "values":self._tree.item(cell,"values")
                    })
                # Now we undo our edit
                self._tree.item(cell,text=task["text"],values=task["values"])
            elif ttype == "add":
                # We added new things - let's create a removal list
                r_task_list.append({
                    "type":"remove",
                    "cell":cell,
                    "from":self._tree.parent(cell),
                    "index":self._tree.index(cell)
                })
                # Now we actually remove it
                self._tree.detach(cell)
            elif ttype == "remove":
                # We removed this cell, let's attach it to its old parent
                r_task_list.append({
                    "type":"add",
                    "cell":cell,
                })
                # Now we actually add it
                self._tree.move(cell,task["from"],task.get("index",tk.END))
                selected = cell
            elif ttype == "move":
                # We moved a cell - let's save the old info
                r_task_list.append({
                    "type":"move",
                    "cell":cell,
                    "from":self._tree.parent(cell),
                    "to":task["from"],
                    "index":self._tree.index(cell)
                })
                # Let's actually move it now
                self._tree.move(cell,task["from"],task.get("index",tk.END))
        # Let's check if we have an r_task_list - and add it if it wasn't a one-off
        if len(r_task_list) and single_undo is None:
            r.append(r_task_list)
        # Ensure we're edited
        self._ensure_edited()
        # Change selection if needed
        self.update_all_children()
        self.reselect((selected,nodes))
        self.reundoing = False

    def preselect(self):
        # Returns a tuple of the selected item and current visible nodes
        return (self._tree.focus(),self.iter_nodes())

    def reselect(self, selection_tuple = None):
        # Select the node or index that was last selected
        if not selection_tuple or not isinstance(selection_tuple,tuple):
            # Just select the root
            return self.select(self.get_root_node())
        selected,original_nodes = selection_tuple
        nodes = self.iter_nodes()
        if selected in nodes: return self.select(selected)
        # Our item no longer exists, let's adjust our selection
        try:
            # Deques only allow checking index in python 3+
            index = original_nodes.index(selected)
        except:
            # Convert to a tuple, and get the index from there
            index = tuple(original_nodes).index(selected)
        self.select(nodes[index] if index < len(nodes) else nodes[-1])

    def got_focus(self, event=None):
        # Lift us to the top of the stack order
        # only when the window specifically gained focus
        if event and event.widget == self:
            self.lift()
            if self.controller.settings.get("warn_if_modified",True) \
            and self.current_plist and os.path.isfile(self.current_plist) and self.last_hash:
                # We have a valid file - see if the file
                # has been modified since then
                try:
                    modified_hash = self.get_hash(self.current_plist)
                except Exception:
                    self.last_hash = None
                    return
                if self.last_hash != modified_hash:
                    # Update to avoid continually warning
                    self.last_hash = modified_hash
                    self.bell()
                    if mb.askyesno(
                        "File Was Modified",
                        "{} was modified by another application, do you want to reload it from disk?".format(
                            os.path.basename(self.current_plist)
                        ),
                        parent=self):
                        self.reload_from_disk()

    def move_selection(self, event):
        # Check if we have a entry_popup - and relocate it
        if self.entry_popup: self.entry_popup.relocate()
        # Verify we had clicked in the drag column
        if not self.clicked_drag:
            # Nope, ignore
            return
        target = self.get_root_node() if not len(self._tree.selection()) else self._tree.selection()[0]
        if target == self.get_root_node(): return # Nothing to do here as we can't drag it
        if self.drag_start is None:
            # Let's set the drag start globals
            self.drag_start = (event.x, event.y)
            self.drag_undo = None
            return
        # Find how far we've drug so far
        if not self.dragging:
            x, y = self.drag_start
            drag_distance = math.sqrt((event.x - x)**2 + (event.y - y)**2)
            if drag_distance < self.controller.drag_scale.get():
                # Not drug enough
                return
            # We've passed the threshold, start dragging
            self.dragging = True
        # Save a reference to the item
        if not self.drag_undo:
            self.drag_undo = {"from":self._tree.parent(target),"index":self._tree.index(target),"name":self._tree.item(target,"text")}
        # Make sure if we drag to the bottom, it stays at the bottom
        if self._tree.identify_region(event.x, event.y) == "nothing" and not event.y < 5:
            move_to = len(self.iter_nodes())
        else:
            move_to = self._tree.index(self._tree.identify_row(event.y))
        tv_item = self._tree.identify('item', event.x, event.y)
        tv_item = tv_item or self.get_root_node() # Force Root node as needed
        # Check if it's not a collection - or if it is, if it has children and is closed,
        # then keep it a sibling.
        if not self.get_check_type(tv_item).lower() in ("dictionary","array") \
        or (len(self._tree.get_children(tv_item)) and not self._tree.item(tv_item,"open")):
            # Keep it a sibling
            if not tv_item == self.get_root_node():
                tv_item = self._tree.parent(tv_item)
        # Let's get the bounding box for the target, and if we're in the lower half,
        # we'll add as a child, uper half will add as a sibling
        else:
            rowid = self._tree.identify_row(event.y)
            column = self._tree.identify_column(event.x)
            try:
                x,y,width,height = self._tree.bbox(rowid, column)
            except:
                # We drug outside the possible bounds
                if move_to == len(self.iter_nodes()): # Drug down
                    self._tree.move(target,self.get_root_node(),move_to)
                return
            if y+(height/2)<=event.y<y+height and self._tree.parent(tv_item) != "":
                # Just above should add as a sibling
                tv_item = self._tree.parent(tv_item)
            else:
                # Just below should add it at item 0 and make sure the element is opened
                self._tree.item(tv_item,open=True)
                move_to = 0
        # Retain the open state, and make sure the selected node is closed
        if self.drag_open is None: self.drag_open = self._tree.item(target,"open")
        if self._tree.item(target,"open"): self._tree.item(target,open=False)
        if self._tree.index(target) == move_to and tv_item == target:
            # Already the same
            return
        try:
            self._tree.move(target, tv_item, move_to)
        except:
            pass
        else:
            self.alternate_colors()

    def confirm_drag(self, event):
        if not self.dragging or not self.drag_undo:
            return
        self.dragging = False
        self.drag_start = None
        target = self.get_root_node() if not len(self._tree.selection()) else self._tree.selection()[0]
        self._tree.item(target,open=self.drag_open)
        self.drag_open = None
        node = self._tree.parent(target)
        # Make sure we actually moved it somewhere
        if self.drag_undo["from"] == node and self.drag_undo["index"] == self._tree.index(target):
            return # Didn't actually move it - bail
        # We moved it - make sure it shows as edited
        self._ensure_edited()
        # Finalize the drag undo
        undo_tasks = []
        # Add the move command
        undo_tasks.append({
            "type":"move",
            "cell":target,
            "from":self.drag_undo["from"],
            "to":node,
            "index":self.drag_undo["index"]
        })
        # Create a unique name
        t = self.get_check_type(node).lower()
        verify = t in ("dictionary","")
        if verify:
            names = [self._tree.item(x,"text") for x in self._tree.get_children(node) if not x == target]
            name = self._tree.item(target,"text")
            num  = 0
            while True:
                temp_name = name if num == 0 else name+" "+str(num)
                if temp_name in names:
                    num += 1
                    continue
                # Should be good here
                name = temp_name
                break
            self._tree.item(target,text=name)
        # Update children first, then check for name change
        self.update_all_children()
        if self._tree.item(target,"text") != self.drag_undo["name"]:
            # Name changed - we need an edit command
            undo_tasks.append({
                "type":"edit",
                "cell":target,
                "text":self.drag_undo["name"],
                "values":self._tree.item(target,"values")
                })
        # Post the undo, and clear the global
        self.add_undo(undo_tasks)
        self.drag_undo = None

    def strip_comments(self, event=None):
        # Strips out any values attached to keys beginning with the prefix
        nodes = self.iter_nodes(False)
        removedlist = []
        selected = self.preselect()
        # Find out if we should ignore case
        ignore_case = True if self.controller.comment_ignore_case.get() else False
        # Check if we should strip string values too
        check_string = True if self.controller.comment_check_string.get() else False
        # Get the current prefix - and default to "#" if needed
        prefix = self.controller.comment_prefix_text.get()
        # Normalize the case if needed as well
        prefix = "#" if not prefix else prefix.lower() if ignore_case else prefix
        for node in nodes:
            if node == self.get_root_node(): continue # Can't strip the root node
            name = str(self._tree.item(node,"text"))
            name = name.lower() if ignore_case else name # Normalize case if needed
            if check_string and self.get_check_type(node).lower() == "string":
                val = self.get_padded_values(node)[1]
                names = (name,val)
            else: names = (name,)
            if any((x.startswith(prefix)) for x in names):
                # Found one, remove it
                removedlist.append({
                    "type":"remove",
                    "cell":node,
                    "from":self._tree.parent(node),
                    "index":self._tree.index(node)
                })
                self._tree.detach(node)
        if not len(removedlist):
            # Nothing removed
            return
        # We removed some, flush the changes, update the view,
        # post the undo, and make sure we're edited
        self.add_undo(removedlist)
        self._ensure_edited()
        self.update_all_children()
        self.reselect(selected)

    def strip_disabled(self, event=None):
        # Strips out dicts if they contain Enabled = False, or Disabled = True
        nodes = self.iter_nodes(False)
        root = self.get_root_node()
        selected = self.preselect()
        removedlist = []
        for node in nodes:
            name = str(self._tree.item(node,"text")).lower()
            values = self.get_padded_values(node, 3)
            value = values[1]
            check_type = self.get_check_type(node).lower()
            if check_type=="boolean" and (name=="enabled" and value==self.b_false()) or (name=="disabled" and value==self.b_true()):
                # Found one, remove its parent
                rem_node = self._tree.parent(node)
                if root in (node, rem_node):
                    # Can't remove the root - skip it
                    continue
                removedlist.append({
                    "type":"remove",
                    "cell":rem_node,
                    "from":self._tree.parent(rem_node),
                    "index":self._tree.index(rem_node)
                })
                self._tree.detach(rem_node)
        if not len(removedlist):
            # Nothing removed
            return
        # We removed some, flush the changes, update the view,
        # post the undo, and make sure we're edited
        self.add_undo(removedlist)
        self._ensure_edited()
        self.update_all_children()
        self.reselect(selected)

    def strip_whitespace(self, event=None, keys=False, values=False):
        # Strips whitespace from keys and/or values
        if not keys and not values:
            # Nothing to do
            return
        nodes = self.iter_nodes(False)
        changed_list = []
        numbered_key = []
        for node in nodes:
            # vals[0] = type, vals[1] = value
            vals = self.get_padded_values(node)
            key = key_orig = str(self._tree.item(node,"text"))
            val = val_orig = vals[1]
            key_numbered = False
            if keys:
                parent = self._tree.parent(node)
                if self.get_check_type(parent).lower() == "dictionary":
                    # Only strip keys that have dictionary parents
                    key = key.strip()
                    # Ensure the name is unique
                    names = [self._tree.item(x,"text")for x in self._tree.get_children(parent) if x!=node]
                    num_key = self.get_unique_name(key,names)
                    if num_key != key:
                        # We appended a number to our key - retain it
                        key_numbered = True
                        key = num_key
            if values: val = val.strip()
            # Check if either are different - and add them
            # to our list for undoing.
            if (keys and key != key_orig) or (values and val != val_orig):
                # Retain the original for the undo/redo stack
                changed_list.append({
                    "type":"edit",
                    "cell":node,
                    "text":self._tree.item(node,"text"),
                    "values":self._tree.item(node,"values")
                })
                # Apply our changes
                self._tree.item(node,text=key)
                self._tree.item(node,values=(vals[0],val))
                # Retain the updated numbered path as needed
                if key_numbered:
                    numbered_key.append(self.get_cell_path(node))
        if not changed_list:
            # Nothing changed
            return
        # We changed some, flush the changes, update the view,
        # post the undo, and make sure we're edited
        self.add_undo(changed_list)
        self._ensure_edited()
        self.update_all_children()
        self._tree.update()
        if numbered_key:
            # One or more keys had numbers appended to remain unique,
            # let's warn the user of that change.
            self.bell()
            key_string = "\n".join([" - {}".format(x) for x in numbered_key])
            mb.showerror(
                "Keys Updated For Uniqueness",
                "The following dictionary keys were updated after stripping whitespace to remain unique:\n{}".format(
                    key_string
                ),
                parent=self
            )
            self.controller.lift_window(self)

    ###                       ###
    # Save/Load Plist Functions #
    ###                       ###

    def get_title(self):
        name = self.title()[0:-len(" - Edited")] if self.edited else self.title()
        return os.path.basename(name)

    def get_dir(self):
        return os.path.dirname(self.current_plist) if self.current_plist else None

    def check_save(self):
        if not self.edited:
            return True # No changes, all good
        self.saving = True # Lock saving status
        # Post a dialog asking if we want to save the current plist
        answer = mb.askyesnocancel("Unsaved Changes", "Save changes to {}?".format(self.get_title()))
        self.saving = False # Reset saving status
        if answer == True:
            return self.save_plist()
        return answer

    def save_plist(self, event=None):
        # Pass the current plist to the save_plist_as function
        return self.save_plist_as(event, self.current_plist)

    def _format_data_string(self,plist_text):
        # Helper method to format <data> tags inline
        if not isinstance(plist_text,(list,tuple)):
            # Split it if it's not already a list
            plist_text = plist_text.split("\n")
        new_plist = []
        data_tag = ""
        types = ("</array>","</dict>")
        for i,x in enumerate(plist_text):
            x_stripped = x.strip()
            try:
                type_check = types[types.index(x_stripped)].replace("</","<")
                if plist_text[i-1].strip() == type_check:
                    new_plist[-1] = x.replace("</","<").replace(">","/>")
                    data_tag = ""
                    continue
            except (ValueError, IndexError) as e:
                pass
            if x_stripped == "<data>":
                data_tag = x
                continue
            if not len(data_tag):
                # Not primed, and wasn't <data>
                new_plist.append(x)
                continue
            data_tag += x_stripped
            # Check for the end
            if x_stripped == "</data>":
                # Found the end, append it and reset
                new_plist.append(data_tag)
                data_tag = ""
        return "\n".join(new_plist)

    def save_plist_as(self, event=None, path=None):
        if path is None:
            # Get the file dialog
            path = fd.asksaveasfilename(
                title="Please select a file name for saving:",
                defaultextension=".plist",
                initialfile=self.get_title(),
                initialdir=self.get_dir()
                )
            if not len(path):
                # User cancelled - no changes
                self.controller.lift_window(self)
                return None
        # Check if it should be binary
        binary = self.plist_type_string.get().lower() == "binary"
        # Should have the save path
        plist_data = self.nodes_to_values(binary=binary)
        # Create a temp folder and save there first
        temp = tempfile.mkdtemp()
        temp_file = os.path.join(temp, os.path.basename(path))
        # Set up an in-memory target for the plist - use StringIO on python 2, and
        # BytesIO after
        m = StringIO() if sys.version_info < (3,0) else BytesIO()
        try:
            if binary:
                plist.dump(plist_data,m,sort_keys=self.controller.settings.get("sort_dict",False),fmt=plist.FMT_BINARY)
            elif not self.controller.settings.get("xcode_data",True):
                plist.dump(plist_data,m,sort_keys=self.controller.settings.get("sort_dict",False))
            else:
                # Dump to a string first
                plist_text = self._format_data_string(plist.dumps(plist_data,sort_keys=self.controller.settings.get("sort_dict",False)))
                # At this point, we have a list of lines - with all <data> tags on the same line
                # let's write to buffer
                if sys.version_info >= (3,0):
                    plist_text = plist_text.encode("utf-8")
                m.write(plist_text)
            # Get the hash value of m, and then save it to a file
            mem_hash = self.get_hash(m)
            with open(temp_file,"wb") as f:
                shutil.copyfileobj(m,f)
            temp_hash = self.get_hash(temp_file)
            # Make sure the temp file was serialized properly
            if mem_hash != temp_hash:
                raise Exception("The in-memory and temp file hashes do not match.  Serializing to the temp directory failed.")
            if os.path.isfile(path):
                # We are overwriting an existing file - try to clone the perms and ownership
                try: shutil.copystat(path,temp_file)
                except: pass
                # Update the accessed and modified times
                update_timestamp = time.time()
                try: os.utime(temp_file,(update_timestamp,update_timestamp))
                except: pass
            # Copy the temp over
            shutil.copy(temp_file,path)
            # Let's ensure the md5 of the temp file and saved file are the same
            # There have been some reports of file issues when saving directly to an ESP
            save_hash = self.get_hash(path)
            if temp_hash != save_hash: # Some issue occurred - let's throw an exception
                raise Exception((
                    "The saved and temp file hashes do not match - copying from the temp directory to the destination was unsuccessful.\n\n"
                    "If the destination volume is an ESP, try first saving to your Desktop, then copying the file over manually."
                ))
        except Exception as e:
            # Had an issue, throw up a display box
            self.bell()
            mb.showerror("An Error Occurred While Saving", str(e), parent=self)
            self.controller.lift_window(self)
            return None
        finally:
            # Close our StringIO/BytesIO buffer
            m.close()
            try:
                # Remove the temp dir if possible
                shutil.rmtree(temp,ignore_errors=True)
            except:
                pass
        # Normalize the path as needed
        path = os.path.normpath(path) if path else path
        # Retain the new path if the save worked correctly
        self.current_plist = path
        try:
            self.last_hash = save_hash
        except Exception:
            self.last_hash = None # Reset them
        # Set the window title to the path
        self.title(path)
        # No changes - so we'll reset that
        self._ensure_edited(edited=False)
        return True

    def open_plist(self, path, plist_data, plist_type = "XML", auto_expand = True, alternate = True, title = None):
        # Opened it correctly - let's load it, and set our values
        self.plist_type_string.set(plist_type)
        self._tree.delete(*self._tree.get_children())
        self.add_node(plist_data,check_binary=plist_type.lower() == "binary")
        self.current_plist = os.path.normpath(path) if path else path
        try:
            self.last_hash = self.get_hash(path)
        except Exception:
            self.last_hash = None
        if path is None:
            self._ensure_edited(title=title or "Untitled.plist")
        else:
            self._ensure_edited(edited=False,title=path)
        self.undo_stack.clear()
        self.redo_stack.clear()
        # Close if need be
        if not auto_expand:
            self.collapse_all()
        # Ensure the root is expanded at least
        root = self.get_root_node()
        self._tree.item(root,open=True)
        self.select(root,alternate=alternate)

    def close_window(self, event = None, check_saving = True, check_close = True):
        # Check if we need to save first, then quit if we didn't cancel
        if check_saving and (self.saving or self.check_save() is None):
            # User cancelled or we failed to save, lift the window and bail
            self.controller.lift_window(self)
            return None
        # Destroy our current window - and initiate a check in the controller
        self.destroy()
        if check_close: self.controller.check_close()
        return True

    def _clipboard_append(self, clipboard_string = None):
        self.controller._clipboard_append(clipboard_string=clipboard_string)

    def copy_selection(self, event = None):
        node = self._tree.focus()
        if node == "":
            # Nothing to copy
            return
        try:
            clipboard_string = plist.dumps(self.nodes_to_values(node),sort_keys=self.controller.settings.get("sort_dict",False))
            if self.controller.settings.get("xcode_data",True):
                clipboard_string = self._format_data_string(clipboard_string)
            # Get just the values
            self._clipboard_append(clipboard_string)
        except:
            pass

    def copy_children(self, event = None):
        node = self._tree.focus()
        if node in ("",self.get_root_node()) or not self.get_check_type(node).lower() in ("array","dictionary"):
            # Run the regular copy operation
            return self.copy_selection()
        try:
            plist_data = self.nodes_to_values(node)
            if isinstance(plist_data,dict) and len(plist_data):
                # Set it to the first key's value
                plist_data = plist_data[list(plist_data)[0]]
            elif isinstance(plist_data,list) and len(plist_data):
                # Set it to the first item of the array
                plist_data = plist_data[0]
            clipboard_string = plist.dumps(plist_data,sort_keys=self.controller.settings.get("sort_dict",False))
            self._clipboard_append(clipboard_string)
        except:
            pass

    def _walk_tags(self, data):
        last_open = parent_tag = None
        opening_tags = []
        tag_stack = deque()
        tags_to_remove = deque()
        tag_search = re.compile(r"<[^?!]\/?[a-z]+>")
        for tag in tag_search.finditer(data):
            tag_text = tag.group(0)
            if tag_text[1] == "/":
                open_tag = tag_text.replace("/","")
                # Got a closing tag - make sure it matches the last
                # opening tag - or prepend the opening tag
                if not len(tag_stack):
                    if last_open is None:
                        opening_tags.insert(0,open_tag)
                    continue
                last_tag = tag_stack.pop()
                if last_tag != open_tag:
                    # Doesn't match - scope is wrong
                    tag_stack.append(last_tag)
                    opening_tags.insert(0,open_tag)
                elif not len(tag_stack):
                    # We left our scope entirely
                    parent_tag = "array"
            else:
                # Got a new tag - append it to the stack
                if tag_text == "<key>" and last_open is None:
                    # Prepend a dict open tag
                    tag_stack.appendleft("<dict>")
                    opening_tags.insert(0,"<dict>")
                # Add the open tag and retain it
                tag_stack.append(tag_text)
                last_open = tag_text
        # If we made it through - check if we need anything
        if not any((opening_tags,tag_stack,tags_to_remove)) and parent_tag is None:
            return None
        # Walk the orphaned tags and return their closing elements
        closing_tags = []
        while tag_stack:
            orphan = tag_stack.pop()
            if orphan[1] != "/":
                closing_tags.append("</"+orphan[1:])
        # Adjust the original data as needed to strip any leading
        # tags that close missing elements
        adj = 0
        for t in tags_to_remove:
            start,end = t.span()
            data = data[:start-adj]+data[end-adj:]
            adj += end-start
        # If we bailed on scope - wrap things in an array
        if parent_tag is not None:
            opening_tags.insert(0,"<array>")
            closing_tags.append("</array>")
        # Return the final data
        return "".join(opening_tags+[data.strip()]+closing_tags).strip()

    def paste_selection(self, event = None):
        # We can't paste if another paste operation is in progress
        if self.pasting_nodes: return
        # Lock the paste operation to this instance
        self.pasting_nodes = True
        # Try to format the clipboard contents as a plist
        try:
            clip = self.clipboard_get()
        except:
            clip = ""
        plist_data = None
        try:
            plist_data = plist.loads(clip,dict_type=dict if self.controller.settings.get("sort_dict",False) else OrderedDict)
        except:
            # Let's get all lines that aren't headers/footers
            clip = "\n".join([c for c in clip.strip().split("\n") if not c.startswith(("<?","<!","<plist ","</plist>"))]).strip()
            corrected = self._walk_tags(clip)
            if corrected is not None:
                clip = corrected
            cb_list = [self.plist_header,clip,self.plist_footer]
            # If we start with a key, assume it's a dict.  If we don't start with an array but have multiple newline-delimited elements, assume an array
            # - for all else, let the type remain
            element_type = "dict" if clip.startswith("<key>") else "array" if not clip.startswith(("<array>","<dict>")) and len(clip.split("\n")) > 1 else None
            if element_type:
                cb_list.insert(1,"<{}>".format(element_type))
                cb_list.insert(3,"</{}>".format(element_type))
            cb = "\n".join(cb_list)
            try:
                plist_data = plist.loads(cb,dict_type=dict if self.controller.settings.get("sort_dict",False) else OrderedDict)
            except Exception as e:
                # Let's throw an error
                self.bell()
                mb.showerror("An Error Occurred While Pasting", repr(e),parent=self)
                self.pasting_nodes = False
                return 'break'
        if plist_data is None:
            if len(clip):
                # Check if we actually pasted something
                self.bell()
                mb.showerror("An Error Occurred While Pasting", "The pasted value is not a valid plist string.",parent=self)
            # Nothing to paste
            self.pasting_nodes = False
            return 'break'
        node = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        # Verify the type - or get the parent
        t = self.get_check_type(node).lower()
        index = 0
        if not node == "" and (not t in ("dictionary","array") or (self._tree.get_children(node) and not self._tree.item(node,"open"))):
            index = self._tree.index(node)+1
            node = self._tree.parent(node)
        node = self.get_root_node() if node == "" else node # Force Root node if need be
        t = self.get_check_type(node).lower()
        # Convert data to dict first
        if isinstance(plist_data,list): # Convert to a dict to add
            new_plist = {} if self.controller.settings.get("sort_dict",False) else OrderedDict()
            for i,x in enumerate(plist_data):
                new_plist[str(i)] = x
            plist_data = new_plist
        add_list = []
        if not isinstance(plist_data,dict):
            # Check if we're replacing the Root node
            if node == self.get_root_node() and self.get_root_type() is None:
                # Update the cell to reflect what's going on
                add_list.append({"type":"edit","cell":node,"text":self._tree.item(node,"text"),"values":self._tree.item(node,"values")})
                if self.is_data(plist_data):
                    self._tree.item(node, values=(self.get_type(plist_data),self.get_data(plist_data),"",))
                elif isinstance(plist_data, datetime.datetime):
                    self._tree.item(node, values=(self.get_type(plist_data),plist_data.strftime("%b %d, %Y %I:%M:%S %p"),"",))
                else:
                    self._tree.item(node, values=(self.get_type(plist_data),plist_data,"",))
            else:
                # I guess we're not - let's force it into a dict to be savage
                plist_data = {"New item":plist_data}
        if isinstance(plist_data,dict):
            dict_list = list(plist_data.items()) if not self.controller.settings.get("sort_dict",False) else sorted(list(plist_data.items()))
            names = [self._tree.item(x,"text") for x in self._tree.get_children(node)] if t == "dictionary" else []
            for (key,val) in dict_list[::-1]:
                if t == "dictionary":
                    # create a unique name
                    key = self.get_unique_name(str(key),names)
                    names.append(key)
                last = self.add_node(val, node, key)
                # Move it into place
                self._tree.move(last,node,index)
                add_list.append({"type":"add","cell":last})
                self._tree.item(last,open=True)
        first = self.get_root_node() if not len(add_list) else add_list[0].get("cell")
        self.add_undo(add_list)
        self._ensure_edited()
        self.update_all_children()
        self.select(first)
        self.pasting_nodes = False

    ###                                             ###
    # Converstion to/from Dict and Treeview Functions #
    ###                                             ###

    def add_node(self, value, parentNode="", key=None, check_binary=False):
        node_stack = deque()
        node_stack.append((value,parentNode,key,check_binary))
        top_node = None
        while node_stack:
            node = node_stack.popleft()
            last_check,remaining = self._add_node(*node)
            if top_node is None and last_check is not None:
                # Retain the top_node as needed
                top_node = last_check
            if remaining is None:
                # We don't have to add any more
                continue
            elif isinstance(remaining,list):
                # Got entries to add
                node_stack.extend(remaining)
        # We exited the loop - return the top_node if any
        return top_node

    def _add_node(self, value, parentNode, key, check_binary):
        if value is None:
            return (None,None)
        if key is None:
            key = "Root" # Show the Root
        if isinstance(value,(list,tuple)):
            children = "1 child" if len(value) == 1 else "{} children".format(len(value))
            values = (self.get_type(value),children,"" if parentNode == "" else self.drag_code)
        elif isinstance(value,dict):
            children = "1 key/value pair" if len(value) == 1 else "{} key/value pairs".format(len(value))
            values = (self.get_type(value),children,"" if parentNode == "" else self.drag_code)
        else:
            values = (self.get_type(value),value,"" if parentNode == "" else self.drag_code)
        i = self._tree.insert(parentNode, tk.END, text=key, values=values)
        remaining = None
        if isinstance(value, dict):
            if (not check_binary or (check_binary and self.plist_type_string.get().lower() != "binary")) \
            and len(value) == 1 and "CF$UID" in value and isinstance(value["CF$UID"],(int,long)) \
            and 0 <= value["CF$UID"] < 1 << 32:
                # Got a UID - ensure it's within the unsigned 32-bit int bounds
                value = value["CF$UID"]
                self._tree.item(i, values=(self.get_type(value,override="UID"),value,"" if parentNode == "" else self.drag_code,))
            else:
                self._tree.item(i, open=True)
                dict_list = list(value.items()) if not self.controller.settings.get("sort_dict",False) else sorted(list(value.items()))
                # Iterate our dict_list and create the pending nodes to add
                remaining = [(val,i,key,check_binary) for (key,val) in dict_list]
        elif isinstance(value, (list,tuple)):
            self._tree.item(i, open=True)
            # Iterate our values and create the pending nodes to add
            remaining = [(val,i,key,check_binary) for (key,val) in enumerate(value)]
        elif self.is_data(value):
            self._tree.item(i, values=(self.get_type(value),self.get_data(value),"" if parentNode == "" else self.drag_code,))
        elif isinstance(value, datetime.datetime):
            self._tree.item(i, values=(self.get_type(value),value.strftime("%b %d, %Y %I:%M:%S %p"),"" if parentNode == "" else self.drag_code,))
        elif isinstance(value, (int,long)) and not isinstance(value, bool) and self.int_type_string.get().lower() == "hex":
            value = int(value)
            # Get the type before converting to hex string
            value_type = self.get_type(value)
            if value >= 0: value = "0x"+hex(value).upper()[2:]
            self._tree.item(i, values=(value_type,value,"" if parentNode == "" else self.drag_code,))
        elif isinstance(value, bool):
            self._tree.item(i, values=(self.get_type(value),self.b_true() if value else self.b_false(),"" if parentNode == "" else self.drag_code,))
        elif isinstance(value,plist.UID) or (hasattr(plistlib,"UID") and isinstance(value,plistlib.UID)):
            self._tree.item(i, values=(self.get_type(value),value.data,"" if parentNode == "" else self.drag_code,))
        else:
            self._tree.item(i, values=(self.get_type(value),value,"" if parentNode == "" else self.drag_code,))
        return (i,remaining)

    def get_value_from_node(self,node="",binary=False):
        values = self.get_padded_values(node, 3)
        value = values[1]
        check_type = self.get_check_type(node).lower()
        # Iterate value types
        if check_type == "dictionary":
            value = {} if self.controller.settings.get("sort_dict",False) else OrderedDict()
        elif check_type == "array":
            value = []
        elif check_type == "boolean":
            value = True if values[1].lower() in self.all_b_true(lower=True) else False
        elif check_type == "number":
            if self.int_type_string.get().lower() == "hex" and value.lower().startswith("0x"):
                try:
                    value = int(value,16)
                except:
                    value = 0
            else:
                try:
                    value = int(value)
                except:
                    try:
                        value = float(value)
                    except:
                        value = 0 # default to 0 if we have to have something
        elif check_type == "uid":
            try:
                value = int(value)
            except:
                value = 0 # Same principle as the integer
            # UIDs behave differently depending on XML vs binary context
            value = plist.UID(value) if binary else {"CF$UID":value}
        elif check_type == "data":
            if self.data_type_string.get().lower() == "hex":
                # Convert the hex
                if sys.version_info < (3, 0):
                    value = plistlib.Data(binascii.unhexlify(value.replace("<","").replace(">","").replace(" ","")))
                else:
                    value = binascii.unhexlify(value.replace("<","").replace(">","").replace(" ","").encode("utf-8"))
            else:
                # Assume base64
                if sys.version_info < (3,0):
                    value = plistlib.Data(base64.b64decode(value))
                else:
                    value = base64.b64decode(value.encode("utf-8"))
        elif check_type == "date":
            value = datetime.datetime.strptime(value,"%b %d, %Y %I:%M:%S %p")
        return value

    def nodes_to_values(self,node="",parent=None,binary=False):
        node_stack = deque()
        if node in ("",None,self.get_root_node()):
            # Top level - set the parent to the type of our Root
            node = self.get_root_node()
            parent = self.get_root_type()
            if parent is None:
                # Return the raw value - we don't have a collection
                return self.get_value_from_node(node,binary=binary)
            # Add any children to our stack
            node_stack.extend([(c,parent) for c in self._tree.get_children(node)[::-1]])
        else:
            if parent is None:
                # We need to setup the parent
                p = self._tree.parent(node)
                if p in ("",self.get_root_node()):
                    # The parent is the Root node
                    parent = self.get_root_type()
                else:
                    # Get the type based on our prefs
                    parent = [] if self.get_check_type(p).lower() == "array" else \
                            {} if self.controller.settings.get("sort_dict",False) else OrderedDict()
            node_stack.append((node,parent))
        # Start walking our stack
        while node_stack:
            n,p = node_stack.pop()
            if parent is None and p is not None:
                parent = p
            name = self._tree.item(n,"text")
            value = self.get_value_from_node(n,binary=binary)
            if isinstance(p,list):
                p.append(value)
            elif isinstance(p,dict):
                if isinstance(name,basestring):
                    p[name] = value
                else:
                    p[str(name)] = value
            for c in self._tree.get_children(n)[::-1]:
                node_stack.append((c,value))
        return parent

    def get_type(self, value, override=None, menu_code=True):
        prefix = self.menu_code + " " if menu_code else ""
        if override and isinstance(override,basestring):
            return prefix + override
        elif isinstance(value, dict):
            return prefix + "Dictionary"
        elif isinstance(value, list):
            return prefix + "Array"
        elif isinstance(value, datetime.datetime):
            return prefix + "Date"
        elif self.is_data(value):
            return prefix + "Data"
        elif isinstance(value, bool):
            return prefix + "Boolean"
        elif isinstance(value, (int,float,long)):
            return prefix + "Number"
        elif isinstance(value, basestring):
            return prefix + "String"
        elif isinstance(value,plist.UID) or (hasattr(plistlib,"UID") and isinstance(value,plistlib.UID)):
            return prefix + "UID"
        else:
            return prefix + str(type(value))

    def is_data(self, value):
        return (sys.version_info >= (3, 0) and isinstance(value, bytes)) or (sys.version_info < (3,0) and isinstance(value, plistlib.Data))

    def get_data(self, value):
        if sys.version_info < (3,0) and isinstance(value, plistlib.Data):
            value = value.data
        if not len(value):
            return "<>" if self.data_type_string.get().lower() == "hex" else ""
        if self.data_type_string.get().lower() == "hex":
            h = binascii.hexlify(value)
            if sys.version_info >= (3,0):
                h = h.decode("utf-8")
            return "<{}>".format(" ".join((h[0+i:8+i] for i in range(0, len(h), 8))).upper())
        else:
            h = base64.b64encode(value)
            if sys.version_info >= (3,0):
                h = h.decode("utf-8")
            return h

    ###                   ###
    # Node Update Functions #
    ###                   ###

    def get_unique_name(self,name,names,int_check=False):
        start = 1
        sep = " - "
        # create a unique name
        num = start # Initialize our counter
        while True:
            temp_name = str(name+num) if isinstance(name,(int,long)) else name if num == start else name+str(sep)+str(num)
            if not temp_name in names: break
            num += 1
        return temp_name

    def new_row(self,target=None,force_sibling=False):
        # We can't create new rows if another operation is in progress
        if self.adding_rows: return
        # Lock the new row operation to this instance
        self.adding_rows = True
        if target is None or isinstance(target, tk.Event):
            target = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        if target == self.get_root_node() and not self.get_check_type(self.get_root_node()).lower() in ("array","dictionary"):
            self.adding_rows = False
            return # Can't add to a non-collection!
        new_cell = None
        index = 0
        if not self.get_check_type(target).lower() in ("dictionary","array") or force_sibling or (not self._tree.item(target,"open") and len(self._tree.get_children(target))):
            index = self._tree.index(target)+1
            target = self._tree.parent(target)
        target = self.get_root_node() if target == "" else target # Force the Root node if need be
        # create a unique name
        name = ""
        if self.get_check_type(target).lower() == "dictionary":
            names = [self._tree.item(x,"text")for x in self._tree.get_children(target)]
            name = self.get_unique_name("New String",names)
        new_cell = self._tree.insert(target, index, text=name, values=(self.menu_code + " String","",self.drag_code,))
        # Verify that array names are updated to show the proper indexes
        if self.get_check_type(target).lower() == "array":
            self.update_array_counts(target)
        # Select and scroll to the target
        self.select(new_cell,alternate=False)
        self._ensure_edited()
        self.add_undo({"type":"add","cell":new_cell})
        if target == "":
            # Top level, nothing to do here but edit the new row
            self.alternate_colors(start_with=new_cell)
            self.adding_rows = False
            return
        # Update the child counts
        self.update_children(target)
        # Ensure the target is opened
        self._tree.item(target,open=True)
        # Flush our alternating lines
        self.alternate_colors(start_with=new_cell)
        self.adding_rows = False

    def remove_row(self,target=None):
        # We can't remove rows if another operation is in progress
        if self.removing_rows: return
        # Lock the new row operation to this instance
        self.removing_rows = True
        if target is None or isinstance(target, tk.Event):
            target = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        if target in ("",self.get_root_node()):
            # Can't remove top level
            self.removing_rows = False
            return
        parent = self._tree.parent(target)
        self.add_undo({
            "type":"remove",
            "cell":target,
            "from":parent,
            "index":self._tree.index(target)
        })
        # Retain the index of our selected node to select the new target
        target_index = self._tree.get_children(parent).index(target)
        self._tree.detach(target)
        # Figure out what's left - select the node at the same index if possible,
        # the last index if not, and the parent if no other items
        remaining = self._tree.get_children(parent)
        new_target = parent if not len(remaining) else remaining[target_index] if target_index < len(remaining) else remaining[-1]
        self.select(new_target,alternate=False)
        self._ensure_edited()
        # Check if the parent was an array/dict, and update counts
        if parent == "":
            self.removing_rows = False
            return
        if self.get_check_type(parent).lower() == "array":
            self.update_array_counts(parent)
        self.update_children(parent)
        self.alternate_colors(start_with=new_target)
        self.removing_rows = False

    ###                          ###
    # Treeview Data Helper Methods #
    ###                          ###

    def get_padded_values(self, item, pad_to = 2):
        values = list(self._tree.item(item,"values"))
        values = [] if values == "" else values
        values += [''] * (pad_to - len(values))
        return values

    def update_all_children(self):
        # Iterate the whole list, and ensure all arrays and dicts have their children updated
        # properly
        nodes = self.iter_nodes(False)
        for node in nodes:
            check_type = self.get_check_type(node).lower()
            if check_type == "dictionary":
                self.update_children(node)
            elif check_type == "array":
                self.update_children(node)
                self.update_array_counts(node)

    def update_children(self, target):
        # Update the key/value pairs or children count
        child_count = self._tree.get_children(target)
        values = self.get_padded_values(target, 3)
        if self.get_check_type(target).lower() == "dictionary":
            children = "1 key/value pair" if len(child_count) == 1 else "{} key/value pairs".format(len(child_count))
        elif self.get_check_type(target).lower() == "array":
            children = "1 child" if len(child_count) == 1 else "{} children".format(len(child_count))
        else:
            children = None
        # Set the resulting values as needed
        if children:
            try:
                values[1] = children
                self._tree.item(target,values=values)
            except:
                pass

    def update_array_counts(self, target):
        for x,child in enumerate(self._tree.get_children(target)):
            # Only updating the "text" field
            self._tree.item(child,text=x)

    def cycle_bool(self, event=None):
        cell = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        value = self.get_check_type(cell)
        if not value.lower() == "boolean":
            return "break"
        bool_val = self.get_value_from_node(cell)
        self.set_bool(self.b_false() if bool_val else self.b_true())
        return "break"

    def set_type_by_index(self, index = None, menu = None, zero_based = False):
        # Set our type based on index value
        if not isinstance(index,(int,long)):
            # Try to get the keysym
            try: index = int(getattr(index,"keysym",None).replace("KP_",""))
            except: return # Borked value
        if not menu: # We need to retrieve the menu manually
            cell = "" if not len(self._tree.selection()) else self._tree.selection()[0]
            menu = self.root_type_menu if cell in ("",self.get_root_node()) else self.type_menu
        valid_vals = self._get_menu_commands(menu,label=True)
        if not valid_vals: return # Menu has no commands
        if not zero_based: index -= 1 # original index started at 1, normalize to 0-based
        if index < 0 or index >= len(valid_vals): return # Out of range
        target_index = menu.index(valid_vals[index])
        if target_index is None: return # Nothing found
        menu.invoke(target_index)
        return "break" # Prevent the keypress from cascading

    def cycle_type(self, increment = True):
        # Set our type to the next in the list
        cell = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        value = self.get_check_type(cell)
        menu = self.root_type_menu if cell in ("",self.get_root_node()) else self.type_menu
        valid_vals = self._get_menu_commands(menu,label=True)
        if not valid_vals: return # Menu has no commands
        try: curr = valid_vals.index(value)
        except: return # Our current value isn't in the menu?
        mod = 1 if increment else -1
        # Return set_type_by_index's return to prevent keypress cascading as needed
        return self.set_type_by_index((curr+mod)%len(valid_vals),menu=menu,zero_based=True)

    def change_type(self, value, cell = None):
        # Need to walk the values and pad
        if cell is None:
            cell = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        values = self.get_padded_values(cell, 3)
        # Verify we actually changed type
        if values[0] == value:
            # No change, bail
            return
        original = [x for x in values]
        # Replace our value
        values[0] = value
        # Remove children if needed
        changes = []
        for i in self._tree.get_children(cell):
            changes.append({
                "type":"remove",
                "cell":i,
                "from":self._tree.parent(i),
                "index":self._tree.index(i)
            })
            self._tree.detach(i)
        changes.append({
            "type":"edit",
            "cell":cell,
            "text":self._tree.item(cell,"text"),
            "values":self._tree.item(cell,"values")
        })
        # Add to the undo stack
        self.add_undo(changes)
        # Set the value if need be
        value = self.get_check_type(None,value).lower()
        if value.lower() == "number":
            values[1] = "0" if self.int_type_string.get().lower() == "decimal" else "0x0"
        elif value.lower() == "boolean":
            values[1] = self.b_true()
        elif value.lower() == "array":
            self._tree.item(cell,open=True)
            values[1] = "0 children"
        elif value.lower() == "dictionary":
            self._tree.item(cell,open=True)
            values[1] = "0 key/value pairs"
        elif value.lower() == "date":
            values[1] = datetime.datetime.now().strftime("%b %d, %Y %I:%M:%S %p")
        elif value.lower() == "data":
            values[1] = "<>" if self.data_type_string.get().lower() == "hex" else ""
        elif value.lower() == "uid":
            values[1] = "0"
        else:
            values[1] = ""
        # Set the values
        self._tree.item(cell, values=values)
        self._ensure_edited()

    ###             ###
    # Click Functions #
    ###             ###

    def set_bool(self, value):
        # Need to walk the values and pad
        values = self.get_padded_values("" if not len(self._tree.selection()) else self._tree.selection()[0], 3)
        if values[1] == value: return # Nothing to do, setting it to itself.
        cell = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        self.add_undo({
            "type":"edit",
            "cell":cell,
            "text":self._tree.item(cell,"text"),
            "values":[x for x in values]
            })
        values[1] = value
        # Set the values
        self._tree.item("" if not len(self._tree.selection()) else self._tree.selection()[0], values=values)
        self._ensure_edited()

    def split(self, a, escape = '\\', separator = '/'):
        result = []
        token = ''
        state = 0
        for t in a:
            if state == 0:
                if t == escape:
                    state = 1
                elif t == separator:
                    result.append(token)
                    token = ''
                else:
                    token += t
            elif state == 1:
                token += t
                state = 0
        result.append(token)
        return result
    
    def get_cell_path(self, cell = None):
        # Returns the path to the given cell
        # Will clear out array indexes - as those should be ignored
        if cell is None:
            return None
        current_cell = cell
        path = []
        while True:
            if current_cell == "":
                # Reached the top
                break
            cell = self._tree.parent(current_cell)
            if not self.get_check_type(cell).lower() == "array":
                # Our name isn't just a number add the key
                path.append(self._tree.item(current_cell,"text").replace("/","\\/"))
            else:
                path.append("*")
            current_cell = cell            
        return "/".join(path[::-1])

    def merge_menu_preset(self, val = None):
        if val is None:
            return
        # We need to walk the path of the item to ensure all
        # items exist - each should be a dict, unless specified
        # by a "*", which denotes a list.
        cell,path,itypes,value = val
        paths = self.split(str(path))
        types = itypes.split("/")
        if not len(paths) == len(types):
            self.bell()
            mb.showerror("Incorrect Patch Format", "Patch is incomplete.", parent=self)
            return
        if not len(paths) or paths[0] == "*":
            # No path, or it's an array
            self.bell()
            mb.showerror("Incorrect Patch Format", "Patch starts with an array - must be a dictionary.", parent=self)
            return
        # Iterate both the paths and types lists - checking for each value,
        # and ensuring the type
        created = None
        current_cell = ""
        undo_list = []
        for p,t in izip(paths,types):
            found = False
            needed_type = {"d":"Dictionary","a":"Array"}.get(t.lower(),"Dictionary")
            for x in self._tree.get_children(current_cell):
                cell_name = self._tree.item(x,"text")
                if cell_name == p:
                    current_type = self.get_check_type(x)
                    if not current_type.lower() == needed_type.lower():
                        # Raise an error - type mismatch
                        self.bell()
                        if mb.askyesno("Incorrect Type","{} is {}, should be {}.\n\nWould you like to replace it?".format(cell_name,current_type,needed_type),parent=self):
                            # We need to remove any children, and change the type
                            for y in self._tree.get_children(x):
                                undo_list.append({
                                    "type":"remove",
                                    "cell":y,
                                    "from":x,
                                    "index":self._tree.index(y)
                                })
                                self._tree.detach(y)
                            # Change the type
                            undo_list.append({
                                "type":"edit",
                                "cell":x,
                                "text":self._tree.item(x,"text"),
                                "values":self._tree.item(x,"values")
                            })
                            values = self.get_padded_values(x,3)
                            values[0] = self.menu_code + " " + needed_type
                            if needed_type.lower() == "dictionary":
                                values[1] = "0 key/value pairs"
                            else:
                                values[1] = "0 children"
                            self._tree.item(x, values=values)
                        else:
                            # Let's undo anything we've already done and bail
                            self.reundo(None,True,undo_list)
                            return
                    found = True
                    current_cell = x
                    break
            if not found:
                # Need to add it
                current_cell = self._tree.insert(current_cell,tk.END,text=p,values=(self.menu_code+" "+needed_type,"",self.drag_code,),open=True)
                undo_list.append({
                    "type":"add",
                    "cell":current_cell
                })
        # At this point - we should be able to add the final piece
        # let's first make sure it doesn't already exist - if it does, we
        # will overwrite it
        current_type = self.get_check_type(current_cell).lower()
        just_add = True
        replace_asked = False
        if current_type == "dictionary":
            # Scan through and make sure we have all the keys needed
            for x in self._tree.get_children(current_cell):
                name = self._tree.item(x,"text")
                if name in value:
                    if not replace_asked:
                        # Ask first
                        self.bell()
                        if mb.askyesno("Key(s) Already Exist","One or more keys already exist at the destination.\n\nWould you like to replace them?",parent=self):
                            replace_asked = True
                        else:
                            # User said no, let's undo
                            self.reundo(None,True,undo_list)
                            return
                    # Remove the top level item
                    undo_list.append({
                        "type":"remove",
                        "cell":x,
                        "from":current_cell,
                        "index":self._tree.index(x)
                    })
                    self._tree.detach(x)
            # Add the entries
            if isinstance(value,dict):
                just_add = False
                for x in value:
                    created = self.add_node(value[x],current_cell,x)
                    undo_list.append({
                        "type":"add",
                        "cell":created
                    })
        if just_add:
            last_cell = self.add_node(value,current_cell,"")
            undo_list.append({
                "type":"add",
                "cell":last_cell
            })
        self.add_undo(undo_list)
        self._ensure_edited()
        self.update_all_children()
        self.alternate_colors()

    def sorted_nicely(self, l, reverse = False):
        convert = lambda text: int(text) if text.isdigit() else text
        alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key.lower())]
        return sorted(l,key=lambda x:alphanum_key(self._tree.item(x,"text")),reverse=reverse)

    def do_sort(self, cell, recursive = False, reverse = False):
        node_stack = deque()
        node_stack.append(cell)
        undo_tasks = deque()
        while node_stack:
            node = node_stack.pop()
            children = self._tree.get_children(node)
            # Make sure we have something to sort
            if not children:
                continue
            # Make sure we have a dictionary
            if not self.get_check_type(node).lower() == "dictionary":
                continue
            sorted_children = self.sorted_nicely(children,reverse=reverse)
            # Make sure we're actually making changes
            skip_sort = all(sorted_children[i] == child for i,child in enumerate(children))
            if skip_sort and not recursive:
                continue
            for index,child in enumerate(sorted_children):
                # Check if we have a collection - and if we're recursively sorting
                if recursive and self.get_check_type(child).lower() in ("dictionary","array"):
                    node_stack.append(child)
                # Let's ensure at least one item moved, and then add to the undo task
                if not skip_sort:
                    undo_tasks.append({
                        "type":"move",
                        "cell":child,
                        "from":node,
                        "to":node,
                        "index":self._tree.index(child)
                    })
                    # Actually move the node
                    self._tree.move(child,node,index)
        return list(undo_tasks)

    def sort_keys(self, cell, recursive = False, reverse = False):
        # Let's build a sorted list of keys, then generate move edits for each
        undo_tasks = self.do_sort(cell,recursive=recursive,reverse=reverse)
        if not len(undo_tasks): return # Nothing changed - bail
        self._ensure_edited()
        self.add_undo(undo_tasks)
        self.alternate_colors()

    def popup(self, event):
        # Select the item there if possible
        cell = self._tree.identify('item', event.x, event.y)
        if cell: self.select(cell,alternate=False)
        # Build right click menu
        popup_menu = tk.Menu(self, tearoff=0)
        is_mac = sys.platform == "darwin"
        check_type = self.get_check_type(cell).lower()
        if check_type in ("array","dictionary","data"):
            if check_type in ("array","dictionary"):
                popup_menu.add_command(label="Expand Node", command=self.expand_node)
                popup_menu.add_command(label="Collapse Node", command=self.collapse_node)
                popup_menu.add_separator()
                popup_menu.add_command(label="Expand Children", command=self.expand_children)
                popup_menu.add_command(label="Collapse Children", command=self.collapse_children)
            else:
                popup_menu.add_command(label="Reverse Endianness{}".format(
                    " (Cmd+X)" if is_mac else ""
                ), command=lambda:self.hex_swap(cell), accelerator=None if is_mac else "(Ctrl+X)")
            popup_menu.add_separator()
        popup_menu.add_command(label="Expand All", command=self.expand_all)
        popup_menu.add_command(label="Collapse All", command=self.collapse_all)
        popup_menu.add_separator()
        # Determine if we are adding a child or a sibling
        if cell in ("",self.get_root_node()):
            # Top level - get the Root
            if self.get_check_type(self.get_root_node()).lower() in ("array","dictionary"):
                popup_menu.add_command(label="New top level entry{}".format(" (Cmd +)" if is_mac else ""), command=lambda:self.new_row(self.get_root_node()),accelerator=None if is_mac else "(Ctrl +)")
        else:
            if self.get_check_type(cell).lower() in ("dictionary","array") and (self._tree.item(cell,"open") or not len(self._tree.get_children(cell))):
                popup_menu.add_command(label="New child under '{}'{}".format(
                    self._tree.item(cell,"text"),
                    " (Cmd +)" if is_mac else ""
                ), command=lambda:self.new_row(cell),accelerator=None if is_mac else "(Ctrl +)")
                popup_menu.add_command(label="New sibling of '{}'".format(
                    self._tree.item(cell,"text")
                ), command=lambda:self.new_row(cell,True))
                popup_menu.add_command(label="Remove '{}' and any children{}".format(
                    self._tree.item(cell,"text"),
                    " (Cmd -)" if is_mac else "")
                , command=lambda:self.remove_row(cell),accelerator=None if is_mac else "(Ctrl -)")
            else:
                popup_menu.add_command(label="New sibling of '{}'{}".format(self._tree.item(cell,"text")," (Cmd +)" if is_mac else ""), command=lambda:self.new_row(cell),accelerator=None if is_mac else "(Ctrl +)")
                popup_menu.add_command(label="Remove '{}'{}".format(self._tree.item(cell,"text")," (Cmd -)" if is_mac else ""), command=lambda:self.remove_row(cell),accelerator=None if is_mac else "(Ctrl -)")
        # Let's get our sorting menus
        parent = cell if cell in ("",self.get_root_node()) else self._tree.parent(cell)
        if self.get_check_type(parent).lower() in ("dictionary","array"):
            # Add a separator, and the Sort Keys options
            popup_menu.add_separator()
            # Find out if we can recursively start with the cell, or if we need to start with the parent
            recurs_target = cell if self.get_check_type(cell).lower() in ("dictionary","array") and len(self._tree.get_children(cell)) else parent
            popup_menu.add_command(label="Recursively sort keys starting at '{}'".format(self._tree.item(recurs_target,"text")), command=lambda:self.sort_keys(recurs_target,recursive=True))
            popup_menu.add_command(label="Recursively reverse sort keys starting at '{}'".format(self._tree.item(recurs_target,"text")), command=lambda:self.sort_keys(recurs_target,recursive=True,reverse=True))
            # Check the actual cell
            sort_target = cell if cell in ("",self.get_root_node()) or (self.get_check_type(cell).lower() == "dictionary" and len(self._tree.get_children(cell))>1) else self._tree.parent(cell)
            popup_menu.add_command(label="Sort keys in '{}'".format(self._tree.item(sort_target,"text")), command=lambda:self.sort_keys(sort_target))
            popup_menu.add_command(label="Reverse sort keys in '{}'".format(self._tree.item(sort_target,"text")), command=lambda:self.sort_keys(sort_target,reverse=True))
            
        # Add the copy and paste options
        popup_menu.add_separator()
        c_state = "normal" if len(self._tree.selection()) else "disabled"
        try: p_state = "normal" if len(self.root.clipboard_get()) else "disabled"
        except: p_state = "disabled" # Invalid clipboard content
        popup_menu.add_command(label="Copy{}".format(" (Cmd+C)" if is_mac else ""),command=self.copy_selection,state=c_state,accelerator=None if is_mac else "(Ctrl+C)")
        if not cell in ("",self.get_root_node()) and self.get_check_type(cell).lower() in ("array","dictionary"):
            popup_menu.add_command(label="Copy Children{}".format(" (Cmd+Shift+C)" if is_mac else ""), command=self.copy_children,state=c_state,accelerator=None if is_mac else "(Ctrl+Shift+C)")
        popup_menu.add_command(label="Paste{}".format(" (Cmd+V)" if is_mac else ""),command=self.paste_selection,state=p_state,accelerator=None if is_mac else "(Ctrl+V)")
        cell_path = self.get_cell_path(cell)
        # Add rbits option
        cell_search = [x for x in self.split(cell_path) if x and x!="*"]
        if cell_search and cell_search[0] == "Root": cell_search = cell_search[1:]
        if cell_search and os.path.isfile(self.controller.get_best_tex_path()):
            popup_menu.add_separator()
            popup_menu.add_command(label="Show info for \"{}\"{}".format(
                " -> ".join(cell_search), " (Cmd+I)" if is_mac else ""), command=self.show_config_info, accelerator=None if is_mac else "(Ctrl+I)")
        
        # Walk through the menu data if it exists
        first_key = True
        for key in sorted(list(self.menu_data)):
            options = self.menu_data[key]
            valid   = [x for x in list(options) if x.startswith(cell_path)]
            if not len(valid):
                # No hits - bail
                continue
            # Add a separator
            if first_key:
                popup_menu.add_separator()
                first_key = False
            # Iterate and add
            option_menu = tk.Menu(popup_menu,tearoff=0)
            for item in sorted(valid):
                item_menu = tk.Menu(option_menu,tearoff=0)
                for x in options[item]:
                    if x.get("separator",False) != False:
                        item_menu.add_separator()
                    elif x.get("title",False) != False:
                        item_menu.add("command",label=x.get("title",""),state="disabled")
                    else:
                        name  = x["name"]
                        value = x["value"]
                        types = x["types"]
                        passed = (cell,item,types,value)
                        item_menu.add_command(label=name,command=lambda item=passed: self.merge_menu_preset(item))
                parts = self.split(item)
                option_menu.add_cascade(label=" -> ".join(parts[1 if parts[0].lower() == "root" and len(parts) > 1 else 0:]),menu=item_menu)
            popup_menu.add_cascade(label=key,menu=option_menu)
            
        try:
            popup_menu.tk_popup(event.x_root, event.y_root, 0)
        except:
            pass
        finally:
            popup_menu.grab_release()

    def expand_node(self):
        # Get selected node
        cell = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        self._tree.item(cell,open=True)
        self.alternate_colors(start_with=cell)

    def collapse_node(self):
        # Get selected node
        cell = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        self._tree.item(cell,open=False)
        self.alternate_colors(start_with=cell)

    def expand_all(self):
        # Get all nodes
        nodes = self.iter_nodes(False)
        for node in nodes:
            self._tree.item(node,open=True)
        self.alternate_colors()

    def collapse_all(self):
        # Get all nodes
        nodes = self.iter_nodes(False)
        for node in nodes:
            self._tree.item(node,open=False)
        self.alternate_colors()

    def expand_children(self):
        # Get all children of the selected node
        cell = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        nodes = self.iter_nodes(False, cell)
        nodes.append(cell)
        for node in nodes:
            self._tree.item(node,open=True)
        self.alternate_colors(start_with=cell)
        return "break" # Prevent keybinds from propagating further

    def collapse_children(self):
        # Get all children of the selected node
        cell = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        nodes = self.iter_nodes(False, cell)
        for node in nodes:
            self._tree.item(node,open=False)
        self.alternate_colors(start_with=cell)
        return "break" # Prevent keybinds from propagating further

    def tree_click_event(self, event):
        # close previous popups
        self.destroy_popups()
        self.alternate_colors()

    def on_double_click(self, event):
        # close previous popups
        self.destroy_popups()
        # what row and column was clicked on
        rowid = self._tree.identify_row(event.y)
        column = self._tree.identify_column(event.x)
        if not rowid or not self._tree.bbox(rowid):
            # Nothing double clicked, bail
            return "break"
        # clicked row parent id
        parent = self._tree.parent(rowid)
        # get the actual item name we're editing
        tv_item = self._tree.identify('item', event.x, event.y)
        # If our event.x/y_root are both 0, try to set them to the
        # center of the tv_item's bbox
        if event.x_root == event.y_root == 0:
            try:
                x,y,width,height = self._tree.bbox(tv_item,column)
                event.x_root = self.winfo_rootx()+x+round(width/2)
                event.y_root = self.winfo_rooty()+y+round(height/2)
            except:
                pass
        # Get the actual text
        index = int(column.replace("#",""))
        try:
            t = self.get_check_type(rowid)
        except:
            t = ""
        try:
            pt = self.get_check_type(self._tree.parent(tv_item))
        except:
            pt = ""
        if index == 1:
            # Type change - let's show our menu
            type_menu = self.root_type_menu if parent == "" else self.type_menu
            try:
                type_menu.tk_popup(event.x_root, event.y_root, 0)
            finally:
                type_menu.grab_release()
            return 'break'
        if parent == "" and (index == 0 or self.get_check_type(self.get_root_node()).lower() in ("array","dictionary")): return 'break' # Not changing the type - can't change the name of Root
        if index == 2:
            if t.lower() in ("dictionary","array"):
                # Can't edit the "value" directly - should only show the number of children
                return 'break'
            elif t.lower() == "boolean":
                # Set up the boolean selection menu
                bool_menu = tk.Menu(self, tearoff=0)
                bool_menu.add_command(label=self.b_true(), command=lambda:self.set_bool(self.b_true()))
                bool_menu.add_command(label=self.b_false(), command=lambda:self.set_bool(self.b_false()))
                # Bool change
                try:
                    bool_menu.tk_popup(event.x_root, event.y_root, 0)
                finally:
                    bool_menu.grab_release()
                return 'break'
        if index == 0:
            if pt.lower() == "array":
                # No names here, bail
                return 'break'
            # The name of the item, can be changed at any time
            text = self._tree.item(rowid, 'text')
        else:
            try:
                text = self._tree.item(rowid, 'values')[index-1]
            except:
                text = ""
        if index == 2 and t.lower() == "data":
            # Special formatting of hex values
            text = text.replace("<","").replace(">","")
        # place Entry popup properly
        self.entry_popup = EntryPopup(self._tree, self, self.controller, text, tv_item, column)
        self.entry_popup.relocate()
        return 'break'

    ###                   ###
    # Maintenance Functions #
    ###                   ###

    def destroy_popups(self):
        # auto-confirm changes
        if not self.entry_popup:
            return
        try:
            self.entry_popup.confirm(None)
        except:
            pass
        try:
            self.entry_popup.destroy()
        except:
            pass
        self.entry_popup = None

    def iter_nodes(self, visible=True, current_item=None):
        # Implement an iterative depth-first search to prevent
        # max recursion in rare cases
        if current_item is None or isinstance(current_item, tk.Event):
            current_item = ""
        node_stack = deque()
        node_stack.append(current_item)
        items = deque()
        while node_stack:
            node = node_stack.pop()
            if node and node != current_item:
                items.append(node)
            if not visible or self._tree.item(node,"open") or node == "":
                for child in self._tree.get_children(node)[::-1]:
                    node_stack.append(child)
        return items

    def get_root_node(self):
        children = self._tree.get_children("")
        if not len(children) == 1: raise Exception("Root is malformed!")
        return children[0]

    def get_root_type(self):
        check_type = self.get_check_type(self.get_root_node()).lower()
        # Iterate value types
        if check_type == "dictionary":
            return {} if self.controller.settings.get("sort_dict",False) else OrderedDict()
        elif check_type == "array":
            return []
        return None

    def select(self, node, see = True, alternate = True):
        self._tree.selection_set(node)
        self._tree.focus(node)
        self._tree.update()
        if see: self._tree.see(node)
        if alternate: self.alternate_colors()

    def pre_alternate(self, event):
        # Only called before an item opens - we need to open it manually to ensure
        # colors alternate correctly
        cell = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        if not self._tree.item(cell,"open"):
            self._tree.item(cell,open=True)
        # Call the actual alternate_colors function
        self.alternate_colors(start_with=cell)

    def pre_collapse(self, event):
        # Called before items close - we should ensure we alternate colors starting
        # at the selected cell and on
        cell = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        if self._tree.item(cell,"open"):
            self._tree.item(cell,open=False)
        # Call the alternate_colors function
        self.alternate_colors(start_with=cell)

    def set_colors(self, event = None, alternate = False):
        # Setup the colors and styles
        self.r1 = self.controller.r1_canvas["background"]
        self.r2 = self.controller.r2_canvas["background"]
        self.hl = self.controller.hl_canvas["background"]
        self.bg = self.controller.bg_canvas["background"]
        if self.controller.ig_bg_check.get() or not self.controller.should_set_header_text():
            # Ignoring background color when updating header text
            self.bgt = "white" if self.controller.bg_inv_check.get() else "black"
        else:
            self.bgt = self.controller.text_color(self.bg,invert=self.controller.bg_inv_check.get())
        self.r1t = self.controller.text_color(self.r1,invert=self.controller.r1_inv_check.get())
        self.r2t = self.controller.text_color(self.r2,invert=self.controller.r2_inv_check.get())
        self.hlt = self.controller.text_color(self.hl,invert=self.controller.hl_inv_check.get())
        self.style.configure(self.style_name, background=self.bg, fieldbackground=self.bg)
        self.style.configure(self.style_name+".Heading", background=self.bg, foreground=self.bgt)
        self.style.map(self.style_name, background=[("selected", self.hl)], foreground=[("selected", self.hlt)])
        self._tree.tag_configure('even', foreground=self.r1t, background=self.r1)
        self._tree.tag_configure('odd', foreground=self.r2t, background=self.r2)
        self._tree.tag_configure("selected", foreground="black", background=self.hl)
        if alternate: self.alternate_colors()

    def alternate_colors(self, event = None, start_with = None):
        if self.alternating_colors: return
        self.alternating_colors = True
        focus = self._tree.focus()
        # Let's walk the children of our treeview
        visible = self.iter_nodes(visible=True)
        # Set up our tag tuples
        sel,odd,even = ("selected",),("odd",),("even",)
        found_start = False
        for x,item in enumerate(visible):
            if start_with is not None and start_with == item:
                # We found the cell we were looking for
                found_start = True
            if start_with is None or found_start:
                # We either aren't looking for a specific cell,
                # or we already found it
                tag = sel if item==focus else odd if x % 2 else even
                if self._tree.item(item,"tags") != tag:
                    self._tree.item(item,tags=tag)
        self.alternating_colors = False

    def show_config_info(self, event = None):
        # find the path of selected cell
        cell = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        # don't strip * - needed to differentiate sub section from subsub section
        search_list = self.split(self.get_cell_path(cell))
        # but remove it if it's the last item
        if search_list and search_list[-1] == "*":
            search_list.pop()
        if search_list and search_list[0] == "Root":
            search_list = search_list[1:] # Remove "Root"
        if not search_list: # nothing to search for
            return

        # Check if a window with this entry is already open
        check_title = '"{}" Info'.format(" -> ".join([x for x in search_list if not x=="*"]))
        window = next((x for x in self.controller.stackorder(self.controller.tk,include_defaults=True) if x.title() == check_title),None)
        if not window:
            config_tex_path = self.controller.get_best_tex_path()
            if config_tex_path and os.path.isfile(config_tex_path):
                # Ensure the selected cell is visible
                self._tree.see(cell)
                window = config_tex_info.display_info_window(
                    config_tex_path,
                    search_list,
                    120,
                    False,
                    False,
                    self, # Pass our window as the caller
                    font=self.font,
                    fg=self.r1t,
                    bg=self.r1
                )
            if window:
                # Override the window closing protocol to allow stack order checks
                window.protocol("WM_DELETE_WINDOW", lambda x=window:self.controller.close_window(window=x))
                window.bind("<{}-w>".format("Command" if sys.platform == "darwin" else "Control"), self.controller.close_window)
                self.controller.set_window_opacity(window=window)
                self.controller.set_win_titlebar(windows=window)
            else:
                window = self # Ensure we're lifted again
        # Ensure window is lifted
        self.controller.lift_window(window)
