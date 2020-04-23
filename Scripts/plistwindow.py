#!/usr/bin/env python
import sys, os, plistlib, base64, binascii, datetime, tempfile, shutil, re, itertools, math
from collections import OrderedDict
try:
    # Python 2
    import Tkinter as tk
    import ttk
    import tkFileDialog as fd
    import tkMessageBox as mb
    from itertools import izip_longest as izip
except ImportError:
    # Python 3
    import tkinter as tk
    import tkinter.ttk as ttk
    from tkinter import filedialog as fd
    from tkinter import messagebox as mb
    from itertools import zip_longest as izip
sys.path.append(os.path.abspath(os.path.dirname(os.path.realpath(__file__))))
import plist

try:
    long
    unicode
except NameError:  # Python 3
    long = int
    unicode = str


class EntryPopup(tk.Entry):
    def __init__(self, parent, master, text, cell, column, **kw):
        tk.Entry.__init__(self, parent, **kw)

        self.insert(0, text)
        self.select_all() 
        self['state'] = 'normal'
        self['readonlybackground'] = 'white'
        self['selectbackground'] = '#1BA1E2'
        self['exportselection'] = True

        self.cell = cell
        self.column = column
        self.parent = parent
        self.master = master

        self.focus_force()
        
        if str(sys.platform) == "darwin":
            self.bind("<Command-a>", self.select_all)
            self.bind("<Command-c>", self.copy)
            self.bind("<Command-v>", self.paste)
        else:
            self.bind("<Control-a>", self.select_all)
            self.bind("<Control-c>", self.copy)
            self.bind("<Control-v>", self.paste)
        self.bind("<Escape>", self.cancel)
        self.bind("<Return>", self.confirm)
        self.bind("<KP_Enter>", self.confirm)
        self.bind("<Up>", self.goto_start)
        self.bind("<Down>", self.goto_end)
        self.bind("<Tab>", self.next_field)

    def cancel(self, event):
        # Force the parent focus then destroy self
        self.parent.focus_force()
        self.destroy()

    def next_field(self, event):
        # We need to determine if our other field can be edited
        # and if so - trigger another double click event there
        edit_col = None
        if self.column == "#0":
            check_type = self.master.get_check_type(self.cell).lower()
            # We are currently in the key column
            if check_type in ["array","dictionary"]:
                # Can't edit the other field with these - bail
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
            e.x = x+5
            e.y = y+5
            e.x_root = 0
            e.y_root = 0
            self.master.on_double_click(e)
            return 'break'

    def goto_start(self, event):
        self.selection_range(0, 0)
        self.icursor(0)
        return 'break'

    def goto_end(self, event):
        self.selection_range(0, 0)
        self.icursor(len(self.get()))
        return 'break'

    def copy(self, event):
        try:
            get = self.selection_get()
        except:
            get = ""
        if not len(get):
            return 'break'
        self.clipboard_clear()
        self.clipboard_append(get)
        self.update()
        return 'break'

    def paste(self, event):
        try:
            contents = self.clipboard_get()
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
        return 'break'

    def select_all(self, *ignore):
        self.selection_range(0, 'end')
        # returns 'break' to interrupt default key-bindings
        return 'break'

    def confirm(self, event):
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
                    if not event == None:
                        self.bell()
                        if not mb.askyesno("Invalid Key Name","That key name already exists in that dict.\n\nWould you like to keep editing?",parent=self.parent):
                            self.destroy()
                    return
            # Add to undo stack
            self.master.add_undo({"type":"edit","cell":self.cell,"text":self.parent.item(self.cell,"text"),"values":self.parent.item(self.cell,"values")})
            # No matches, should be safe to set
            self.parent.item(self.cell, text=self.get())
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
            if type_value.lower() == "date" and value.lower() in ["today","now"]:
                # Set it to today first
                value = datetime.datetime.now().strftime("%b %d, %Y %I:%M:%S %p")
            output = self.master.qualify_value(value,type_value)
            if output[0] == False:
                # Didn't pass the test - show the error and prompt for edit continuing
                if not event == None:
                    self.bell()
                    if not mb.askyesno(output[1],output[2]+"\n\nWould you like to keep editing?",parent=self.parent):
                        self.destroy()
                return
            # Set the value to the new output
            value = output[1]
            # Add to undo stack
            self.master.add_undo({"type":"edit","cell":self.cell,"text":self.parent.item(self.cell,"text"),"values":original})
            # Replace our value (may be slightly modified)
            values[index-1] = value
            # Set the values
            self.parent.item(self.cell, values=values)
        self.cancel(None)

class PlistWindow(tk.Toplevel):
    def __init__(self, controller, root, **kw):
        tk.Toplevel.__init__(self, root, **kw)
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        self.plist_header = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>"""
        self.plist_footer = """
</dict>
</plist>"""
        # Create the window
        self.root = root
        self.controller = controller
        self.undo_stack = []
        self.redo_stack = []
        self.drag_undo = None
        self.clicked_drag = False
        self.data_display = "hex" # hex or base64
        # self.xcode_data = self.controller.xcode_data # keep <data>xxxx</data> in one line when true
        # self.sort_dict = self.controller.sort_dict # Preserve key ordering in dictionaries when loading/saving
        self.menu_code = u"\u21D5"
        #self.drag_code = u"\u2630"
        self.drag_code = u"\u2261"

        # self = tk.Toplevel(self.root)
        try:
            w = int(self.controller.settings.get("last_window_width",640))
            h = int(self.controller.settings.get("last_window_height",480))
        except:
            # wut - who be breakin dis?
            w = 640
            h = 480
        # Save the previous states for comparison
        self.previous_height = h
        self.previous_width = w
        self.minsize(width=640,height=480)
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
        self.edited = False
        self.dragging = False
        self.drag_start = None
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
        self.type_menu.add_command(label="String", command=lambda:self.change_type(self.menu_code + " String"))

        # Set up the Root node type menu - only supports Array and Dict
        self.root_type_menu = tk.Menu(self, tearoff=0)
        self.root_type_menu.add_command(label="Dictionary", command=lambda:self.change_type(self.menu_code + " Dictionary"))
        self.root_type_menu.add_command(label="Array", command=lambda:self.change_type(self.menu_code + " Array"))
        
        # Set up the boolean selection menu
        self.bool_menu = tk.Menu(self, tearoff=0)
        self.bool_menu.add_command(label="True", command=lambda:self.set_bool("True"))
        self.bool_menu.add_command(label="False", command=lambda:self.set_bool("False"))

        # Create the treeview
        self._tree_frame = tk.Frame(self)
        self._tree = ttk.Treeview(self._tree_frame, columns=("Type","Value","Drag"), selectmode="browse")
        self._tree.heading("#0", text="Key")
        self._tree.heading("#1", text="Type")
        self._tree.heading("#2", text="Value")
        self._tree.column("Type",width=100,stretch=False)
        self._tree.column("Drag",minwidth=40,width=40,stretch=False,anchor="center")

        # Set the close window and copy/paste bindings
        key = "Command" if str(sys.platform) == "darwin" else "Control"
        # Add the window bindings
        self.bind("<{}-w>".format(key), self.close_window)
        self.bind("<{}-f>".format(key), self.hide_show_find)
        self.bind("<{}-p>".format(key), self.hide_show_type)
        # Add the treeview bindings
        self._tree.bind("<{}-c>".format(key), self.copy_selection)
        self._tree.bind("<{}-C>".format(key), self.copy_all)
        self._tree.bind("<{}-v>".format(key), self.paste_selection)

        # Create the scrollbar
        vsb = ttk.Scrollbar(self._tree_frame, orient='vertical', command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)

        # Bind right click
        if str(sys.platform) == "darwin":
            self._tree.bind("<ButtonRelease-2>", self.popup) # ButtonRelease-2 on mac
        else:
            self._tree.bind("<ButtonRelease-3>", self.popup)

        # Set bindings
        self._tree.bind("<Double-1>", self.on_double_click)
        self._tree.bind("<1>", self.on_single_click)
        self._tree.bind('<<TreeviewSelect>>', self.tree_click_event)
        self._tree.bind('<<TreeviewOpen>>', self.pre_alternate)
        self._tree.bind('<<TreeviewClose>>', self.alternate_colors)
        self._tree.bind("<B1-Motion>", self.move_selection)
        self._tree.bind("<ButtonRelease-1>",self.confirm_drag)
        self._tree.bind("<Button-1>",self.clicked)
        self._tree.bind("=", self.new_row)
        self._tree.bind("+", self.new_row)
        self._tree.bind("-", self.remove_row)
        self._tree.bind("<Delete>", self.remove_row)
        self._tree.bind("<Return>", self.start_editing)
        self._tree.bind("<KP_Enter>", self.start_editing)
        self._tree.bind("<Escape>", self.deselect)
        self.bind("<FocusIn>", self.got_focus)

        # Setup menu bar (hopefully per-window) - only happens on non-mac systems
        if not str(sys.platform) == "darwin":
            key="Control"
            sign = "Ctrl+"
            main_menu = tk.Menu(self)
            file_menu = tk.Menu(self, tearoff=0)
            main_menu.add_cascade(label="File", menu=file_menu)
            file_menu.add_command(label="New ({}N)".format(sign), command=self.controller.new_plist)
            file_menu.add_command(label="Open ({}O)".format(sign), command=self.controller.open_plist)
            file_menu.add_command(label="Save ({}S)".format(sign), command=self.controller.save_plist)
            file_menu.add_command(label="Save As ({}Shift+S)".format(sign), command=self.controller.save_plist_as)
            file_menu.add_command(label="Duplicate ({}D)".format(sign), command=self.controller.duplicate_plist)
            file_menu.add_command(label="Reload From Disk ({}L)".format(sign), command=self.reload_from_disk)
            file_menu.add_separator()
            file_menu.add_command(label="OC Snapshot ({}R)".format(sign), command=self.oc_snapshot)
            file_menu.add_command(label="OC Clean Snapshot ({}Shift+R)".format(sign), command=self.oc_clean_snapshot)
            file_menu.add_separator()
            file_menu.add_command(label="Convert Window ({}T)".format(sign), command=self.controller.show_convert)
            file_menu.add_command(label="Strip Comments ({}M)".format(sign), command=self.strip_comments)
            file_menu.add_separator()
            file_menu.add_command(label="Settings ({},)".format(sign),command=self.controller.show_settings)
            file_menu.add_separator()
            file_menu.add_command(label="Toggle Find/Replace Pane ({}F)".format(sign),command=self.hide_show_find)
            file_menu.add_command(label="Toggle Plist/Data Type Pane ({}P)".format(sign),command=self.hide_show_type)
            if not str(sys.platform) == "darwin":
                file_menu.add_separator()
                file_menu.add_command(label="Quit ({}Q)".format(sign), command=self.controller.quit)
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
        self.display_frame.columnconfigure(2,weight=1)
        self.display_frame.columnconfigure(4,weight=1)
        pt_label = tk.Label(self.display_frame,text="Plist Type:")
        dt_label = tk.Label(self.display_frame,text="Display Data as:")
        self.plist_type_string = tk.StringVar(self.display_frame)
        self.plist_type_menu = tk.OptionMenu(self.display_frame, self.plist_type_string, "XML","Binary", command=self.change_plist_type)
        self.plist_type_string.set("XML")
        self.data_type_string = tk.StringVar(self.display_frame)
        self.data_type_menu = tk.OptionMenu(self.display_frame, self.data_type_string, "Hex","Base64", command=self.change_data_type)
        self.data_type_string.set("Hex")
        pt_label.grid(row=1,column=1,padx=10,pady=(0,5),sticky="w")
        dt_label.grid(row=1,column=3,padx=10,pady=(0,5),sticky="w")
        self.plist_type_menu.grid(row=1,column=2,padx=10,pady=10,sticky="we")
        self.data_type_menu.grid(row=1,column=4,padx=10,pady=10,sticky="we")
        
        # Create our find/replace view
        self.find_frame = tk.Frame(self,height=20)
        self.find_frame.columnconfigure(2,weight=1)
        f_label = tk.Label(self.find_frame, text="Find:")
        f_label.grid(row=0,column=0,sticky="e")
        r_label = tk.Label(self.find_frame, text="Replace:")
        r_label.grid(row=1,column=0,sticky="e")
        self.find_type = "Key"
        self.f_text = tk.Entry(self.find_frame)
        self.f_text.bind("<Return>", self.find_next)
        self.f_text.bind("<KP_Enter>", self.find_next)
        self.f_text.delete(0,tk.END)
        self.f_text.insert(0,"")
        self.f_text.grid(row=0,column=2,sticky="we",padx=10,pady=10)
        self.r_text = tk.Entry(self.find_frame)
        self.r_text.bind("<Return>", self.replace)
        self.r_text.bind("<KP_Enter>", self.replace)
        self.r_text.delete(0,tk.END)
        self.r_text.insert(0,"")
        self.r_text.grid(row=1,column=2,columnspan=1,sticky="we",padx=10,pady=10)
        f_title = tk.StringVar(self.find_frame)
        f_title.set("Key")
        f_option = tk.OptionMenu(self.find_frame, f_title, "Key", "Boolean", "Data", "Date", "Number", "String", command=self.change_find_type)
        f_option['menu'].insert_separator(1)
        f_option.grid(row=0,column=1)
        self.fp_button = tk.Button(self.find_frame,text="< Prev",width=8,command=self.find_prev)
        self.fp_button.grid(row=0,column=3,sticky="e",padx=0,pady=10)
        self.fn_button = tk.Button(self.find_frame,text="Next >",width=8,command=self.find_next)
        self.fn_button.grid(row=0,column=4,sticky="w",padx=0,pady=10)
        self.r_button = tk.Button(self.find_frame,text="Replace",command=self.replace)
        self.r_button.grid(row=1,column=4,sticky="we",padx=10,pady=10)
        self.r_all_var = tk.IntVar()
        self.r_all = tk.Checkbutton(self.find_frame,text="Replace All",variable=self.r_all_var)
        self.r_all.grid(row=1,column=5,sticky="w")
        self.f_case_var = tk.IntVar()
        self.f_case = tk.Checkbutton(self.find_frame,text="Case-Sensitive",variable=self.f_case_var)
        self.f_case.grid(row=0,column=5,sticky="w")

        # Add the scroll bars and show the treeview
        vsb.pack(side="right",fill="y")
        self._tree.pack(side="bottom",fill="both",expand=True)
        self.draw_frames()
        self.entry_popup = None

    def window_resize(self, event=None, obj=None):
        if not event or not obj: return
        if self.winfo_height() == self.previous_height and self.winfo_width() == self.previous_width: return
        self.previous_height = self.winfo_height()
        self.previous_width = self.winfo_width()
        self.controller.settings["last_window_width"] = self.previous_width
        self.controller.settings["last_window_height"] = self.previous_height

    def change_plist_type(self, value):
        if not self.edited:
            self.edited = True
            self.title(self.title()+" - Edited")

    def change_data_type(self, value):
        self.change_data_display(value.lower())

    def change_find_type(self, value):
        self.find_type = value

    def qualify_value(self, value, value_type):
        value_type = value_type.lower()
        if value_type == "data":
            if self.data_display == "hex":
                if value.lower().startswith("0x"):
                    value = value[2:]
                value = value.replace(" ","").replace("<","").replace(">","")
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
            value = str(value)
        elif value_type == "boolean":
            if not value.lower() in ["true","false"]:
                return (False,"Invalid Boolean Data","Booleans can only be True/False.")
            value = "True" if value.lower() == "true" else "False"
        return (True,value)

    def draw_frames(self, event=None, changed=None):
        self.find_frame.pack_forget()
        self.display_frame.pack_forget()
        self._tree_frame.pack_forget()
        if self.show_find_replace:
            # Add the show_find pane, make the find pane active, and highlight any text
            self.find_frame.pack(side="top",fill="x",padx=10)
            if changed == "hideshow":
                self.f_text.focus()
                self.f_text.selection_range(0, 'end')
        self._tree_frame.pack(fill="both",expand=True)
        if self.show_type:
            self.display_frame.pack(side="bottom",fill="x",padx=10)

    def hide_show_find(self, event=None):
        # Let's find out if we're set to show
        self.show_find_replace ^= True
        self.draw_frames(event,"hideshow")

    def hide_show_type(self, event=None):
        # Let's find out if we're set to show
        self.show_type ^= True
        self.draw_frames(event,"showtype")

    def do_replace(self, node, find, new_text):
        # We can assume that we have a legit match for whatever is passed
        # Let's get some info first
        case_sensitive = self.f_case_var.get()
        node_type      = self.get_check_type(node)
        parent_type    = self.get_check_type(self._tree.parent(node))
        find_type      = self.find_type.lower()

        if find_type == "key":
            # We're only replacing the text
            name = self._tree.item(node,"text")
            new_name = re.sub(("" if case_sensitive else "(?i)")+re.escape(find), lambda m: new_text, name)
            self._tree.item(node,text=new_name)
            return
        # Check the values
        values = self.get_padded_values(node,3)
        if find_type == "string":
            # Just replacing the text value
            values[1] = re.sub(("" if case_sensitive else "(?i)")+re.escape(find), lambda m: new_text, values[1])
            self._tree.item(node,values=values)
        elif find_type == "data":
            # if hex, we need to strip spaces and brackets, upper() both, and compare
            if self.data_display == "hex":
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
            if node == None:
                # Nothing found - let's throw an error
                self.bell()
                mb.showerror("No Replaceable Matches Found", '"{}" did not match any {} fields in the current plist.'.format(find,self.find_type.lower()),parent=self)
                return
            return
        # At this point, we should have something to replace
        replacements = []
        for x in matches:
            name = self._tree.item(x[1],"text")
            values = self._tree.item(x[1],"values")
            self.do_replace(x[1],find,repl)
            replacements.append({
                "type":"edit",
                "cell":x[1],
                "text":name,
                "values":values
                })
            self._tree.selection_set(x[1])
            self._tree.see(x[1])
        self.alternate_colors()
        self.add_undo(replacements)
        # Ensure we're edited
        if not self.edited:
            self.edited = True
            self.title(self.title()+" - Edited")
        # Let's try to find the next
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
            if self.data_display == "hex":
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
        elif node_type in ["date","boolean","number"]:
            if text.lower() == value.lower():
                # Can only return if we find the same date
                return True
        # If we got here, we didn't find it
        return False

    def find_all(self, text=""):
        # Builds a list of tuples that list the node, the index of the found entry, and 
        # where it found it name/value (name == 0, value == 1 respectively)
        if text == None or not len(text):
            return []
        nodes = self.iter_nodes(False)
        found = []
        for node in nodes:
            match = self.is_match(node, text)
            if not match == False:
                found.append((nodes.index(node),node))
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
            if not replacing:
                self.bell()
                mb.showerror("No Matches Found", '"{}" did not match any {} fields in the current plist.'.format(type_check[1],self.find_type.lower()),parent=self)
            return None
        # Let's get the index of our selected item
        node  = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        nodes = self.iter_nodes(False)
        index = len(nodes) if node == "" else nodes.index(node)
        # Find the item at a lower index than our current selection
        for match in matches[::-1]:
            if match[0] < index:
                # Found one - select it
                self._tree.selection_set(match[1])
                self._tree.see(match[1])
                self.alternate_colors()
                return match
        # If we got here - start over
        self._tree.selection_set(matches[-1][1])
        self._tree.see(matches[-1][1])
        self.alternate_colors()
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
        index = len(nodes) if node == "" else nodes.index(node)
        # Find the item at a higher index than our current selection
        for match in matches:
            if match[0] > index:
                # Found one - select it
                self._tree.selection_set(match[1])
                self._tree.see(match[1])
                self.alternate_colors()
                return match
        # If we got here - start over
        self._tree.selection_set(matches[0][1])
        self._tree.see(matches[0][1])
        self.alternate_colors()
        return match[0]

    def deselect(self, event=None):
        # Clear the table selection
        for x in self._tree.selection():
            self._tree.selection_remove(x)

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
        edit_col = "#0"
        if parent_type == "array":
            if check_type == "boolean":
                # Can't edit anything - bail
                return 'break'
            # Can at least edit the value
            edit_col = "#2"
        # Let's get the bounding box for our other field
        try:
            x,y,width,height = self._tree.bbox(node, edit_col)
        except ValueError:
            # Couldn't unpack - bail
            return    
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
            mb.showerror("An Error Occurred While Opening {}".format(os.path.basename(self.current_plist)), str(e),parent=self)
            return
        # We should have the plist data now
        self.open_plist(self.current_plist,plist_data, self.plist_type_string.get())

    def walk_kexts(self,path,parent=""):
        kexts = []
        # Let's make sure we check Lilu first if it exists
        kext_list   = sorted([x for x in os.listdir(path) if not x.lower() in ("fakesmc.kext","lilu.kext","virtualsmc.kext")])
        merged_list = sorted([x for x in os.listdir(path) if x.lower() in ("fakesmc.kext","lilu.kext","virtualsmc.kext")])
        merged_list.extend(kext_list)
        for x in merged_list:
            if x.startswith("."):
                continue
            if not x.lower().endswith(".kext"):
                continue
            kdir = os.path.join(path,x)
            if not os.path.isdir(kdir):
                continue
            kdict = {
                "Comment":"",
                "Enabled":True,
                "MaxKernel":"",
                "MinKernel":"",
                "BundlePath":parent+"/"+x if len(parent) else x,
                "ExecutablePath":""
            }
            kinfo = {}
            # Should be valid-ish - let's check for a binary
            binpath = os.path.join(kdir,"Contents","MacOS",os.path.splitext(x)[0])
            if os.path.exists(binpath):
                kdict["ExecutablePath"] = "Contents/MacOS/"+os.path.splitext(x)[0]
            # Get the Info.plist
            if os.path.exists(os.path.join(kdir,"Contents","Info.plist")):
                kdict["PlistPath"] = "Contents/Info.plist"
                try:
                    with open(os.path.join(kdir,"Contents","Info.plist"),"rb") as f:
                        info_plist = plist.load(f)
                    kinfo["CFBundleIdentifier"] = info_plist.get("CFBundleIdentifier",None)
                    kinfo["OSBundleLibraries"] = info_plist.get("OSBundleLibraries",[])
                except: pass
            elif os.path.exists(os.path.join(kdir,"Info.plist")):
                kdict["PlistPath"] = "Info.plist"
            if not kdict.get("PlistPath"):
                # We have at least an Info.plist
                continue
            # Should have something here
            kexts.append((kdict,kinfo))
            # Check if we have a PlugIns folder
            pdir = kdir+"/Contents/PlugIns"
            if os.path.exists(pdir) and os.path.isdir(pdir):
                kexts.extend(self.walk_kexts(pdir,(parent+"/"+x if len(parent) else x)+"/Contents/PlugIns"))
        return kexts

    def oc_clean_snapshot(self, event = None):
        self.oc_snapshot(event,True)

    def oc_snapshot(self, event = None, clean = False):
        oc_folder = fd.askdirectory(title="Select OC Folder:")
        if not len(oc_folder):
            return

        # Verify folder structure - should be as follows:
        # OC
        #  +- ACPI
        #  | +- SSDT.aml
        #  +- Drivers
        #  | +- EfiDriver.efi
        #  +- Kexts
        #  | +- Something.kext
        #  +- config.plist
        #  +- Tools (Optional)
        #  | +- SomeTool.efi
        #  | +- SomeFolder
        #  | | +- SomeOtherTool.efi
        
        oc_acpi    = os.path.join(oc_folder,"ACPI")
        oc_drivers = os.path.join(oc_folder,"Drivers")
        oc_kexts   = os.path.join(oc_folder,"Kexts")
        oc_tools   = os.path.join(oc_folder,"Tools")

        for x in [oc_acpi,oc_drivers,oc_kexts]:
            if not os.path.exists(x):
                self.bell()
                mb.showerror("Incorrect OC Folder Struction", "{} does not exist.".format(x), parent=self)
                return
            if not os.path.isdir(x):
                self.bell()
                mb.showerror("Incorrect OC Folder Struction", "{} exists, but is not a directory.".format(x), parent=self)
                return

        # Folders are valid - lets work through each section

        # ACPI is first, we'll iterate the .aml files we have and add what is missing
        # while also removing what exists in the plist and not in the folder.
        # If something exists in the table already, we won't touch it.  This leaves the
        # enabled and comment properties untouched.
        #
        # Let's make sure we have the ACPI -> Add sections in our config

        tree_dict = self.nodes_to_values()
        # We're going to replace the whole list
        if not "ACPI" in tree_dict or not isinstance(tree_dict["ACPI"],dict):
            tree_dict["ACPI"] = {"Add":[]}
        if not "Add" in tree_dict["ACPI"] or not isinstance(tree_dict["ACPI"]["Add"],list):
            tree_dict["ACPI"]["Add"] = []
        # Now we walk the existing add values
        new_acpi = []
        for path, subdirs, files in os.walk(oc_acpi):
            for name in files:
                if not name.startswith(".") and name.lower().endswith(".aml"):
                    new_acpi.append(os.path.join(path,name)[len(oc_acpi):].replace("\\", "/").lstrip("/"))
        add = [] if clean else tree_dict["ACPI"]["Add"]
        for aml in sorted(new_acpi,key=lambda x:x.lower()):
            if aml.lower() in [x.get("Path","").lower() for x in add if isinstance(x,dict)]:
                # Found it - skip
                continue
            # Doesn't exist, add it
            add.append({
                "Enabled":True,
                "Comment":os.path.basename(aml),
                "Path":aml
            })
        new_add = []
        for aml in add:
            if not isinstance(aml,dict):
                # Not the right type - skip it
                continue
            if not aml.get("Path","").lower() in [x.lower() for x in new_acpi]:
                # Not there, skip
                continue
            new_add.append(aml)
        tree_dict["ACPI"]["Add"] = new_add

        # Next we need to walk the .efi drivers - in basically the same exact manner
        if not "UEFI" in tree_dict or not isinstance(tree_dict["UEFI"],dict):
            tree_dict["UEFI"] = {"Drivers":[]}
        if not "Drivers" in tree_dict["UEFI"] or not isinstance(tree_dict["UEFI"]["Drivers"],list):
            tree_dict["UEFI"]["Drivers"] = []
        # Now we walk the existing values
        new_efi = [x for x in os.listdir(oc_drivers) if x.lower().endswith(".efi") and not x.startswith(".")]
        add = [] if clean else tree_dict["UEFI"]["Drivers"]
        for efi in sorted(new_efi,key=lambda x:x.lower()):
            if efi.lower() in [x.lower() for x in add]:
                # Found it - skip
                continue
            # Doesn't exist, add it
            add.append(efi)
        new_add = []
        for efi in add:
            if not efi.lower() in [x.lower() for x in new_efi]:
                # Not there, skip
                continue
            new_add.append(efi)
        tree_dict["UEFI"]["Drivers"] = new_add

        # Now we need to walk the kexts
        if not "Kernel" in tree_dict or not isinstance(tree_dict["Kernel"],dict):
            tree_dict["Kernel"] = {"Add":[]}
        if not "Add" in tree_dict["Kernel"] or not isinstance(tree_dict["Kernel"]["Add"],list):
            tree_dict["Kernel"]["Add"] = []
        kext_list = self.walk_kexts(oc_kexts)
        bundle_list = [x[0].get("BundlePath","") for x in kext_list]
        kexts = [] if clean else tree_dict["Kernel"]["Add"]
        original_kexts = [x for x in kexts if x.get("BundlePath","") in bundle_list] # get the original load order for comparison purposes - but omit any that no longer exist
        for kext,info in kext_list:
            if kext["BundlePath"].lower() in [x.get("BundlePath","").lower() for x in kexts if isinstance(x,dict)]:
                # Already have it, skip
                continue
            # We need it, it seems
            kexts.append(kext)
        new_kexts = []
        for kext in kexts:
            if not isinstance(kext,dict):
                # Not a dict - skip it
                continue
            if not kext.get("BundlePath","").lower() in [x[0]["BundlePath"].lower() for x in kext_list]:
                # Not there, skip it
                continue
            new_kexts.append(kext)
        # Let's check inheritance via the info
        # We need to ensure that no 2 kexts consider each other as parents
        unordered_kexts = []
        for x in new_kexts:
            x = next((y for y in kext_list if y[0].get("BundlePath","") == x.get("BundlePath","")),None)
            if not x: continue
            parents = [next((z for z in new_kexts if z.get("BundlePath","") == y[0].get("BundlePath","")),[]) for y in kext_list if y[1].get("CFBundleIdentifier",None) in x[1].get("OSBundleLibraries",[])]
            children = [next((z for z in new_kexts if z.get("BundlePath","") == y[0].get("BundlePath","")),[]) for y in kext_list if x[1].get("CFBundleIdentifier",None) in y[1].get("OSBundleLibraries",[])]
            parents = [y for y in parents if not y in children and not y.get("BundlePath","") == x[0].get("BundlePath","")]
            unordered_kexts.append({
                "kext":x[0],
                "parents":parents
            })
        ordered_kexts = []
        while len(unordered_kexts): # This could be dangerous if things aren't properly prepared above
            kext = unordered_kexts.pop(0)
            if len(kext["parents"]) and not all(x in ordered_kexts for x in kext["parents"]):
                unordered_kexts.append(kext)
                continue
            ordered_kexts.append(next(x for x in new_kexts if x.get("BundlePath","") == kext["kext"].get("BundlePath","")))
        # Let's compare against the original load order - to prevent mis-prompting
        missing_kexts = [x for x in ordered_kexts if not x in original_kexts]
        original_kexts.extend(missing_kexts)
        # Let's walk both lists and gather all kexts that are in different spots
        rearranged = []
        while True:
            check1 = [x.get("BundlePath","") for x in ordered_kexts if not x.get("BundlePath","") in rearranged]
            check2 = [x.get("BundlePath","") for x in original_kexts if not x.get("BundlePath","") in rearranged]
            out_of_place = next((x for x in range(len(check1)) if check1[x] != check2[x]),None)
            if out_of_place == None: break
            rearranged.append(check2[out_of_place])
        # Verify if the load order changed - and prompt the user if need be
        if len(rearranged):
            if not mb.askyesno("Incorrect Kext Load Order","Correct the following kext load inheritance issues?\n\n{}".format("\n".join(rearranged)),parent=self):
                ordered_kexts = original_kexts # We didn't want to update it

        tree_dict["Kernel"]["Add"] = ordered_kexts

        # Let's walk the Tools folder if it exists
        if not "Misc" in tree_dict or not isinstance(tree_dict["Misc"],dict):
            tree_dict["Misc"] = {"Tools":[]}
        if not "Drivers" in tree_dict["Misc"] or not isinstance(tree_dict["Misc"]["Tools"],list):
            tree_dict["Misc"]["Tools"] = []
        if os.path.exists(oc_tools) and os.path.isdir(oc_tools):
            tools_list = []
            # We need to gather a list of all the files inside that and with .efi
            for path, subdirs, files in os.walk(oc_tools):
                for name in files:
                    if not name.startswith(".") and name.lower().endswith(".efi"):
                        # Save it
                        tools_list.append({
                            "Arguments":"",
                            "Auxiliary":False,
                            "Name":name,
                            "Comment":name,
                            "Enabled":True,
                            "Path":os.path.join(path,name)[len(oc_tools):].replace("\\", "/").lstrip("/") # Strip the /Volumes/EFI/
                        })
            tools = [] if clean else tree_dict["Misc"]["Tools"]
            for tool in sorted(tools_list, key=lambda x: x.get("Path","").lower()):
                if tool["Path"].lower() in [x.get("Path","").lower() for x in tool if isinstance(x,dict)]:
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
            tree_dict["Misc"]["Tools"] = new_tools
        else:
            # Make sure our Tools list is empty
            tree_dict["Misc"]["Tools"] = []

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
        # Ensure we're edited
        if not self.edited:
            self.edited = True
            self.title(self.title()+" - Edited")
        self.update_all_children()
        self.alternate_colors()

    def get_check_type(self, cell=None, string=None):
        if not cell == None:
            t = self.get_padded_values(cell,1)[0]
        elif not string == None:
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
        if not event:
            return
        column = self._tree.identify_column(event.x)
        rowid  = self._tree.identify_row(event.y)
        if rowid and column == "#3":
            # Mouse down in the drag column
            self.clicked_drag = True

    def change_data_display(self, new_display = "hex"):
        self.data_type_string.set(new_display[0].upper()+new_display[1:])
        # This will change how data is displayed - we do this by converting all our existing
        # data values to bytes, then reconverting and displaying appropriately
        if new_display == self.data_display:
            # Nothing to do here
            return
        nodes = self.iter_nodes(False)
        removedlist = []
        for node in nodes:
            values = self.get_padded_values(node,3)
            t = self.get_check_type(node).lower()
            value = values[1]
            if t == "data":
                # We need to adjust how it is displayed, load the bytes first
                if new_display == "hex":
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
                self._tree.item(node,values=values)
        self.data_display = new_display

    def add_undo(self, action):
        if not isinstance(action,list):
            action = [action]
        self.undo_stack.append(action)
        self.redo_stack = [] # clear the redo stack

    def reundo(self, event=None, undo = True, single_undo = None):
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
            return
        task_list = u.pop(-1)
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
                self._tree.move(cell,task["from"],task.get("index","end"))
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
                self._tree.move(cell,task["from"],task.get("index","end"))
        # Let's check if we have an r_task_list - and add it if it wasn't a one-off
        if len(r_task_list) and single_undo == None:
            r.append(r_task_list)
        # Ensure we're edited
        if not self.edited:
            self.edited = True
            self.title(self.title()+" - Edited")
        self.update_all_children()
        self.alternate_colors()

    def got_focus(self, event=None):
        # Lift us to the top of the stack order
        # only when the window specifically gained focus
        if event and event.widget == self:
            self.lift()

    def move_selection(self, event):
        # Verify we had clicked in the drag column
        if not self.clicked_drag:
            # Nope, ignore
            return
        if self.drag_start == None:
            # Let's set the drag start
            self.drag_start = (event.x, event.y)
            return
        # Find how far we've drug so far
        if not self.dragging:
            x, y = self.drag_start
            drag_distance = math.sqrt((event.x - x)**2 + (event.y - y)**2)
            if drag_distance < 30:
                # Not drug enough
                return
        move_to = self._tree.index(self._tree.identify_row(event.y))
        tv_item = self._tree.identify('item', event.x, event.y)
        tv_item = self.get_root_node() if tv_item == "" else tv_item # Force Root node as needed
        self._tree.item(tv_item,open=True)
        if not self.get_check_type(tv_item).lower() in ["dictionary","array"]:
            # Allow adding as child
            if not tv_item == self.get_root_node():
                tv_item = self._tree.parent(tv_item)
                self._tree.item(tv_item,open=True)
        # Let's get the bounding box for the target, and if we're in the lower half,
        # we'll add as a child, uper half will add as a sibling
        else:
            rowid = self._tree.identify_row(event.y)
            column = self._tree.identify_column(event.x)
            try:
                x,y,width,height = self._tree.bbox(rowid, column)
            except:
                # We drug outside the possible bounds - ignore this
                return
            if event.y >= y+height/2 and event.y < y+height and not self._tree.parent(tv_item) == "":
                # Just above should add as a sibling
                tv_item = self._tree.parent(tv_item)
                self._tree.item(tv_item,open=True)
            else:
                # Just below should add it at item 0
                move_to = 0
        target = self.get_root_node() if not len(self._tree.selection()) else self._tree.selection()[0]
        if target == self.get_root_node(): return # Nothing to do here as we can't drag it
        # Make sure the selected node is closed
        self._tree.item(target,open=False)
        if self._tree.index(target) == move_to and tv_item == target:
            # Already the same
            return
        # Make sure if we drag to the bottom, it stays at the bottom
        if self._tree.identify_region(event.x, event.y) == "nothing" and not event.y < 5:
            move_to = len(self.iter_nodes())
        # Save a reference to the item
        if not self.drag_undo:
            self.drag_undo = {"from":self._tree.parent(target),"index":self._tree.index(target),"name":self._tree.item(target,"text")}
        try:
            self._tree.move(target, tv_item, move_to)
        except:
            pass
        else:
            self._tree.item(target,open=False)
            if not self.edited:
                self.edited = True
                self.title(self.title()+" - Edited")
            self.dragging = True

    def confirm_drag(self, event):
        if not self.dragging:
            return
        self.dragging = False
        self.drag_start = None
        target = self.get_root_node() if not len(self._tree.selection()) else self._tree.selection()[0]
        self._tree.item(target,open=True)
        node = self._tree.parent(target)
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
        verify = t in ["dictionary",""]
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
        self.alternate_colors()

    def strip_comments(self, event=None, prefix = "#"):
        # Strips out any values attached to keys beginning with "#"
        nodes = self.iter_nodes(False)
        removedlist = []
        for node in nodes:
            name = self._tree.item(node,"text")
            if str(name).startswith(prefix):
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
        if not self.edited:
            self.edited = True
            self.title(self.title()+" - Edited")
        self.update_all_children()
        self.alternate_colors()

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
        # Post a dialog asking if we want to save the current plist
        answer = mb.askyesnocancel("Unsaved Changes", "Save changes to {}?".format(self.get_title()))
        if answer == True:
            return self.save_plist()
        return answer

    def save_plist(self, event=None):
        # Pass the current plist to the save_plist_as function
        return self.save_plist_as(event, self.current_plist)

    def save_plist_as(self, event=None, path=None):
        if path == None:
            # Get the file dialog
            path = fd.asksaveasfilename(
                title="Please select a file name for saving:",
                defaultextension=".plist",
                initialfile=self.get_title(),
                initialdir=self.get_dir()
                )
            if not len(path):
                # User cancelled - no changes
                return None
        # Should have the save path
        plist_data = self.nodes_to_values()
        # Create a temp folder and save there first
        temp = tempfile.mkdtemp()
        temp_file = os.path.join(temp, os.path.basename(path))
        try:
            if self.plist_type_string.get().lower() == "binary":
                with open(temp_file,"wb") as f:
                    plist.dump(plist_data,f,sort_keys=self.controller.settings.get("sort_dict",False),fmt=plist.FMT_BINARY)
            # elif not self.xcode_data:
            elif not self.controller.settings.get("xcode_data",True):
                with open(temp_file,"wb") as f:
                    plist.dump(plist_data,f,sort_keys=self.controller.settings.get("sort_dict",False))
            else:
                # Dump to a string first
                plist_text = plist.dumps(plist_data,sort_keys=self.controller.settings.get("sort_dict",False))
                new_plist = []
                data_tag = ""
                for x in plist_text.split("\n"):
                    if x.strip() == "<data>":
                        data_tag = x
                        continue
                    if not len(data_tag):
                        # Not primed, and wasn't <data>
                        new_plist.append(x)
                        continue
                    data_tag += x.strip()
                    # Check for the end
                    if x.strip() == "</data>":
                        # Found the end, append it and reset
                        new_plist.append(data_tag)
                        data_tag = ""
                # At this point, we have a list of lines - with all <data> tags on the same line
                # let's write to file
                with open(temp_file,"wb") as f:
                    temp_string = "\n".join(new_plist)
                    if sys.version_info >= (3,0):
                        temp_string = temp_string.encode("utf-8")
                    f.write(temp_string)
        except Exception as e:
            try:
                shutil.rmtree(temp,ignore_errors=True)
            except:
                pass
            # Had an issue, throw up a display box
            self.bell()
            mb.showerror("An Error Occurred While Saving", str(e), parent=self)
            return None
        try:
            # Copy the temp over
            shutil.copy(temp_file,path)
        except Exception as e:
            try:
                shutil.rmtree(temp,ignore_errors=True)
            except:
                pass
            # Had an issue, throw up a display box
            self.bell()
            mb.showerror("An Error Occurred While Saving", str(e), parent=self)
            return None
        try:
            shutil.rmtree(temp,ignore_errors=True)
        except:
            pass
        # Retain the new path if the save worked correctly
        self.current_plist = path
        # Set the window title to the path
        self.title(path)
        # No changes - so we'll reset that
        self.edited = False
        return True

    def open_plist(self, path, plist_data, plist_type = "XML",auto_expand=True):
        # Opened it correctly - let's load it, and set our values
        self.plist_type_string.set(plist_type)
        self._tree.delete(*self._tree.get_children())
        self.add_node(plist_data)
        self.current_plist = path
        if path == None:
            self.title("Untitled.plist - Edited")
            self.edited = True
        else:
            self.title(path)
            self.edited = False
        self.undo_stack = []
        self.redo_stack = []
        # Close if need be
        if not auto_expand:
            self.collapse_all()
        # Ensure the root is expanded at least
        self._tree.item(self.get_root_node(),open=True)
        self.alternate_colors()

    def close_window(self, event=None):
        # Check if we need to save first, then quit if we didn't cancel
        if self.check_save() == None:
            # User cancelled or we failed to save, bail
            return None
        # See if we're the only window left, and close the session after
        windows = self.stackorder(self.root)
        if len(windows) == 1 and windows[0] == self:
            # Last and closing
            self.controller.close_window(event,True)
        else:
            self.destroy()
        return True

    def copy_selection(self, event = None):
        node = self._tree.focus()
        if node == "":
            # Nothing to copy
            return
        try:
            clipboard_string = plist.dumps(self.nodes_to_values(node,None),sort_keys=self.controller.settings.get("sort_dict",False))
            # Get just the values
            self.clipboard_clear()
            self.clipboard_append(clipboard_string)
        except:
            pass

    def copy_all(self, event = None):
        try:
            clipboard_string = plist.dumps(self.nodes_to_values(self.get_root_node(),None),sort_keys=self.controller.settings.get("sort_dict",False))
            # Get just the values
            self.clipboard_clear()
            self.clipboard_append(clipboard_string)
        except:
            pass

    def paste_selection(self, event = None):
        # Try to format the clipboard contents as a plist
        try:
            clip = self.clipboard_get()
        except:
            clip = ""
        plist_data = None
        try:
            plist_data = plist.loads(clip,dict_type=dict if self.controller.settings.get("sort_dict",False) else OrderedDict)
        except:
            # May need the header
            cb = self.plist_header + "\n" + clip + "\n" + self.plist_footer
            try:
                plist_data = plist.loads(cb,dict_type=dict if self.controller.settings.get("sort_dict",False) else OrderedDict)
            except Exception as e:
                # Let's throw an error
                self.bell()
                mb.showerror("An Error Occurred While Pasting", str(e),parent=self)
                return 'break'
        if plist_data == None:
            if len(clip):
                # Check if we actually pasted something
                self.bell()
                mb.showerror("An Error Occurred While Pasting", "The pasted value is not a valid plist string.",parent=self)
            # Nothing to paste
            return 'break'
        node = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        # Verify the type - or get the parent
        t = self.get_check_type(node).lower()
        if not node == "" and not t in ["dictionary","array"]:
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
            if node == self.get_root_node() and self.get_root_type() == None:
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
            for (key,val) in dict_list:
                if t == "dictionary":
                    # create a unique name
                    names = [self._tree.item(x,"text") for x in self._tree.get_children(node)]
                    name = str(key)
                    num  = 0
                    while True:
                        temp_name = name if num == 0 else name+" "+str(num)
                        if temp_name in names:
                            num += 1
                            continue
                        # Should be good here
                        name = temp_name
                        break
                    key = name
                last = self.add_node(val, node, key)
                add_list.append({"type":"add","cell":last})
                self._tree.item(last,open=True)
        first = self.get_root_node() if not len(add_list) else add_list[0].get("cell")
        self.add_undo(add_list)
        self._tree.focus()
        self._tree.selection_set(first)
        self._tree.see(first)
        self._tree.update()
        if not self.edited:
            self.edited = True
            self.title(self.title()+" - Edited")
        self.update_all_children()
        self.alternate_colors()

    def stackorder(self, root):
        """return a list of root and toplevel windows in stacking order (topmost is last)"""
        c = root.children
        s = root.tk.eval('wm stackorder {}'.format(root))
        L = [x.lstrip('.') for x in s.split()]
        return [(c[x] if x else root) for x in L]

    ###                                             ###
    # Converstion to/from Dict and Treeview Functions #
    ###                                             ###

    def add_node(self, value, parentNode="", key=None):
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
        i = self._tree.insert(parentNode, "end", text=key, values=values)

        if isinstance(value, dict):
            self._tree.item(i, open=True)
            dict_list = list(value.items()) if not self.controller.settings.get("sort_dict",False) else sorted(list(value.items()))
            for (key,val) in dict_list:
                self.add_node(val, i, key)
        elif isinstance(value, (list,tuple)):
            self._tree.item(i, open=True)
            for (key,val) in enumerate(value):
                self.add_node(val, i, key)
        elif self.is_data(value):
            self._tree.item(i, values=(self.get_type(value),self.get_data(value),"" if parentNode == "" else self.drag_code,))
        elif isinstance(value, datetime.datetime):
            self._tree.item(i, values=(self.get_type(value),value.strftime("%b %d, %Y %I:%M:%S %p"),"" if parentNode == "" else self.drag_code,))
        else:
            self._tree.item(i, values=(self.get_type(value),value,"" if parentNode == "" else self.drag_code,))
        return i

    def get_value_from_node(self,node=""):
        values = self.get_padded_values(node, 3)
        value = values[1]
        check_type = self.get_check_type(node).lower()
        # Iterate value types
        if check_type == "dictionary":
            value = {} if self.controller.settings.get("sort_dict",False) else OrderedDict()
        elif check_type == "array":
            value = []
        elif check_type == "boolean":
            value = True if values[1].lower() == "true" else False
        elif check_type == "number":
            try:
                value = int(value)
            except:
                try:
                    value = float(value)
                except:
                    value = 0 # default to 0 if we have to have something
        elif check_type == "data":
            if self.data_display == "hex":
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

    def nodes_to_values(self,node="",parent=None):
        if node in ("",None,self.get_root_node()):
            # Top level - set the parent to the type of our Root
            node = self.get_root_node()
            parent = self.get_root_type()
            if parent == None: return self.get_value_from_node(node) # Return the raw value - we don't have a collection
            for child in self._tree.get_children(node):
                parent = self.nodes_to_values(child,parent)
            return parent
        # Not top - process
        if parent == None:
            # We need to setup the parent
            p = self._tree.parent(node)
            if p in ("",self.get_root_node()):
                # The parent is the Root node
                parent = self.get_root_type()
            else:
                # Get the type based on our prefs
                parent = [] if self.get_check_type(p).lower() == "array" else {} if self.controller.settings.get("sort_dict",False) else OrderedDict()
        name = self._tree.item(node,"text")
        value = self.get_value_from_node(node)
        # At this point, we should have the name and value
        for child in self._tree.get_children(node):
            value = self.nodes_to_values(child,value)
        if isinstance(parent,list):
            parent.append(value)
        elif isinstance(parent,dict):
            if isinstance(name,unicode):
                parent[name] = value
            else:
                parent[str(name)] = value
        return parent

    def get_type(self, value):
        if isinstance(value, dict):
            return self.menu_code + " Dictionary"
        elif isinstance(value, list):
            return self.menu_code + " Array"
        elif isinstance(value, datetime.datetime):
            return self.menu_code + " Date"
        elif self.is_data(value):
            return self.menu_code + " Data"
        elif isinstance(value, bool):
            return self.menu_code + " Boolean"
        elif isinstance(value, (int,float,long)):
            return self.menu_code + " Number"
        elif isinstance(value, (str,unicode)):
            return self.menu_code + " String"
        else:
            return self.menu_code + str(type(value))

    def is_data(self, value):
        if (sys.version_info >= (3, 0) and isinstance(value, bytes)) or (sys.version_info < (3,0) and isinstance(value, plistlib.Data)):
            return True
        return False

    def get_data(self, value):
        if sys.version_info < (3,0) and isinstance(value, plistlib.Data):
            value = value.data
        if not len(value):
            return "<>" if self.data_display == "hex" else ""
        if self.data_display == "hex":
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

    def new_row(self,target=None,force_sibling=False):
        if target == None or isinstance(target, tk.Event):
            target = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        target = self.get_root_node() if target == "" else target # Force the Root node if need be
        if target == self.get_root_node() and not self.get_check_type(self.get_root_node()).lower() in ("array","dictionary"):
            return # Can't add to a non-collection!
        values = self.get_padded_values(target, 1)
        new_cell = None
        if not self.get_check_type(target).lower() in ["dictionary","array"] or not self._tree.item(target,"open") or force_sibling:
            target = self._tree.parent(target)
        # create a unique name
        names = [self._tree.item(x,"text")for x in self._tree.get_children(target)]
        name = "New String"
        num  = 0
        while True:
            temp_name = name if num == 0 else name+" "+str(num)
            if temp_name in names:
                num += 1
                continue
            # Should be good here
            name = temp_name
            break
        new_cell = self._tree.insert(target, "end", text=name, values=(self.menu_code + " String","",self.drag_code,))
        # Verify that array names are updated to show the proper indexes
        if self.get_check_type(target).lower() == "array":
            self.update_array_counts(target)
        # Select and scroll to the target
        self._tree.focus(new_cell)
        self._tree.selection_set(new_cell)
        self._tree.see(new_cell)
        if not self.edited:
            self.edited = True
            self.title(self.title()+" - Edited")
        self.add_undo({"type":"add","cell":new_cell})
        if target == "":
            # Top level, nothing to do here but edit the new row
            self.alternate_colors()
            return
        # Update the child counts
        self.update_children(target)
        # Ensure the target is opened
        self._tree.item(target,open=True)
        # Flush our alternating lines
        self.alternate_colors()

    def remove_row(self,target=None):
        if target == None or isinstance(target, tk.Event):
            target = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        if target in ("",self.get_root_node()):
            # Can't remove top level
            return
        parent = self._tree.parent(target)
        self.add_undo({
            "type":"remove",
            "cell":target,
            "from":parent,
            "index":self._tree.index(target)
        })
        self._tree.detach(target)
        # self._tree.delete(target) # Removes completely
        # Might include an undo function for removals, at least - tbd
        if not self.edited:
            self.edited = True
            self.title(self.title()+" - Edited")
        # Check if the parent was an array/dict, and update counts
        if parent == "":
            return
        if self.get_check_type(parent).lower() == "array":
            self.update_array_counts(parent)
        self.update_children(parent)
        self.alternate_colors()

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
        # Set the resulting values
        values[1] = children
        self._tree.item(target,values=values)

    def update_array_counts(self, target):
        for x,child in enumerate(self._tree.get_children(target)):
            # Only updating the "text" field
            self._tree.item(child,text=x)

    def change_type(self, value, cell = None):
        # Need to walk the values and pad
        if cell == None:
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
            values[1] = 0
        elif value.lower() == "boolean":
            values[1] = "True"
        elif value.lower() == "array":
            self._tree.item(cell,open=True)
            values[1] = "0 children"
        elif value.lower() == "dictionary":
            self._tree.item(cell,open=True)
            values[1] = "0 key/value pairs"
        elif value.lower() == "date":
            values[1] = datetime.datetime.now().strftime("%b %d, %Y %I:%M:%S %p")
        elif value.lower() == "data":
            values[1] = "<>" if self.data_display == "hex" else ""
        else:
            values[1] = ""
        # Set the values
        self._tree.item(cell, values=values)
        if not self.edited:
            self.edited = True
            self.title(self.title()+" - Edited")

    ###             ###
    # Click Functions #
    ###             ###

    def set_bool(self, value):
        # Need to walk the values and pad
        values = self.get_padded_values("" if not len(self._tree.selection()) else self._tree.selection()[0], 3)
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
        if not self.edited:
            self.edited = True
            self.title(self.title()+" - Edited")

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
        if cell == None:
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
                path.append(self._tree.item(current_cell,"text").replace("/","\/"))
            else:
                path.append("*")
            current_cell = cell            
        return "/".join(path[::-1])

    def merge_menu_preset(self, val = None):
        if val == None:
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
                current_cell = self._tree.insert(current_cell,"end",text=p,values=(self.menu_code+" "+needed_type,"",self.drag_code,),open=True)
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
        if not self.edited:
            self.edited = True
            self.title(self.title()+" - Edited")
        self.update_all_children()
        self.alternate_colors()

    def popup(self, event):
        # Select the item there if possible
        cell = self._tree.identify('item', event.x, event.y)
        if cell:
            self._tree.selection_set(cell)
            self._tree.focus(cell)
        # Build right click menu
        popup_menu = tk.Menu(self, tearoff=0)
        if self.get_check_type(cell).lower() in ["array","dictionary"]:
            popup_menu.add_command(label="Expand Children", command=self.expand_children)
            popup_menu.add_command(label="Collapse Children", command=self.collapse_children)
            popup_menu.add_separator()
        popup_menu.add_command(label="Expand All", command=self.expand_all)
        popup_menu.add_command(label="Collapse All", command=self.collapse_all)
        popup_menu.add_separator()
        # Determine if we are adding a child or a sibling
        if cell in ("",self.get_root_node()):
            # Top level - get the Root
            if self.get_check_type(self.get_root_node()).lower() in ("array","dictionary"):
                popup_menu.add_command(label="New top level entry (+)".format(self._tree.item(cell,"text")), command=lambda:self.new_row(self.get_root_node()))
        else:
            if self.get_check_type(cell).lower() in ["array","dictionary"] and (self._tree.item(cell,"open") or not len(self._tree.get_children(cell))):
                popup_menu.add_command(label="New child under '{}' (+)".format(self._tree.item(cell,"text")), command=lambda:self.new_row(cell))
                popup_menu.add_command(label="New sibling of '{}'".format(self._tree.item(cell,"text")), command=lambda:self.new_row(cell,True))
                popup_menu.add_command(label="Remove '{}' and any children (-)".format(self._tree.item(cell,"text")), command=lambda:self.remove_row(cell))
            else:
                popup_menu.add_command(label="New sibling of '{}' (+)".format(self._tree.item(cell,"text")), command=lambda:self.new_row(cell))
                popup_menu.add_command(label="Remove '{}' (-)".format(self._tree.item(cell,"text")), command=lambda:self.remove_row(cell))
        # Add the copy and paste options
        popup_menu.add_separator()
        sign = "Command" if str(sys.platform) == "darwin" else "Ctrl"
        c_state = "normal" if len(self._tree.selection()) else "disabled"
        try: p_state = "normal" if len(self.root.clipboard_get()) else "disabled"
        except: p_state = "disabled" # Invalid clipboard content
        popup_menu.add_command(label="Copy ({}+C)".format(sign),command=self.copy_selection,state=c_state)
        popup_menu.add_command(label="Paste ({}+V)".format(sign),command=self.paste_selection,state=p_state)
        
        # Walk through the menu data if it exists
        cell_path = self.get_cell_path(cell)
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
        self.alternate_colors()

    def collapse_children(self):
        # Get all children of the selected node
        cell = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        nodes = self.iter_nodes(False, cell)
        nodes.append(cell)
        for node in nodes:
            self._tree.item(node,open=False)
        self.alternate_colors()

    def tree_click_event(self, event):
        # close previous popups
        self.destroy_popups()

    def on_single_click(self, event):
        # close previous popups
        self.destroy_popups()

    def on_double_click(self, event):
        # close previous popups
        self.destroy_popups()
        # what row and column was clicked on
        rowid = self._tree.identify_row(event.y)
        column = self._tree.identify_column(event.x)
        if rowid == "":
            # Nothing double clicked, bail
            return
        # clicked row parent id
        parent = self._tree.parent(rowid)
        # get column position info
        x,y,width,height = self._tree.bbox(rowid, column)
        # get the actual item name we're editing
        tv_item = self._tree.identify('item', event.x, event.y)
        # y-axis offset
        pady = height // 2
        # Get the actual text
        index = int(column.replace("#",""))
        try:
            # t = self._tree.item(rowid,"values")[0]
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
            if t.lower() in ["dictionary","array"]:
                # Can't edit the "value" directly - should only show the number of children
                return 'break'
            elif t.lower() == "boolean":
                # Bool change
                try:
                    self.bool_menu.tk_popup(event.x_root, event.y_root, 0)
                finally:
                    self.bool_menu.grab_release()
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
        if index ==2 and t.lower() == "data":
            # Special formatting of hex values
            text = text.replace("<","").replace(">","")
        cell = self._tree.item("" if not len(self._tree.selection()) else self._tree.selection()[0])
        # place Entry popup properly
        self.entry_popup = EntryPopup(self._tree, self, text, tv_item, column)
        self.entry_popup.place( x=x, y=y+pady, anchor="w", width=width)
        if not self.edited:
            self.edited = True
            self.title(self.title()+" - Edited")
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

    def iter_nodes(self, visible = True, current_item = None):
        items = []
        if current_item == None or isinstance(current_item, tk.Event):
            current_item = ""
        for child in self._tree.get_children(current_item):
            items.append(child)
            if not visible or self._tree.item(child,"open"):
                items.extend(self.iter_nodes(visible, child))
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

    def pre_alternate(self, event):
        # Only called before an item opens - we need to open it manually to ensure
        # colors alternate correctly
        cell = "" if not len(self._tree.selection()) else self._tree.selection()[0]
        if not self._tree.item(cell,"open"):
            self._tree.item(cell,open=True)
        # Call the actual alternate_colors function
        self.alternate_colors(event)

    def alternate_colors(self, event = None):
        # Let's walk the children of our treeview
        visible = self.iter_nodes(True,event)
        for x,item in enumerate(visible):
            tags = self._tree.item(item,"tags")
            if not isinstance(tags,list):
                tags = []
            # Remove odd or even
            try:
                tags.remove("odd")
            except:
                pass
            try:
                tags.remove("even")
            except:
                pass
            tags.append("odd" if x % 2 else "even")
            self._tree.item(item, tags=tags)
        self._tree.tag_configure('odd', background='#E8E8E8')
        self._tree.tag_configure('even', background='#DFDFDF')
