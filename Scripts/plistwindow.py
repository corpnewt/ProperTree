#!/usr/bin/env python
import sys, os, plistlib, base64, binascii, datetime, tempfile, shutil, re, itertools, math
try:
    # Python 2
    import Tkinter as tk
    import ttk
    import tkFileDialog as fd
    import tkMessageBox as mb
    from itertools import izip_longest as izip
except:
    # Python 3
    import tkinter as tk
    import tkinter.ttk as ttk
    from tkinter import filedialog as fd
    from tkinter import messagebox as mb
    from itertools import zip_longest as izip
sys.path.append(os.path.abspath(os.path.dirname(os.path.realpath(__file__))))
import plist

class EntryPopup(tk.Entry):
    def __init__(self, parent, text, cell, column, **kw):
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
        self.master = parent._nametowidget(parent.winfo_parent())

        self.focus_force()
        
        if str(sys.platform) == "darwin":
            self.bind("<Command-a>", self.select_all)
            self.bind("<Command-c>", self.copy)
            self.bind("<Command-v>", self.paste)
        else:
            self.bind("<Control-a>", self.select_all)
            self.bind("<Control-c>", self.copy)
            self.bind("<Control-v>", self.paste)
        self.bind("<Escape>", lambda *ignore: self.destroy())
        self.bind("<Return>", self.confirm)
        self.bind("<KP_Enter>", self.confirm)
        self.bind("<Up>", self.goto_start)
        self.bind("<Down>", self.goto_end)

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
        contents = self.clipboard_get()
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
                        # print("Key names must be unique!\a")
                    return
            # Add to undo stack
            self.master.add_undo({"cell":self.cell,"name":self.parent.item(self.cell,"text")})
            # No matches, should be safe to set
            self.parent.item(self.cell, text=self.get())
        else:
            # Need to walk the values and pad
            values = self.parent.item(self.cell)["values"]
            values = [] if values == "" else values
            # Count up, padding as we need
            index = int(self.column.replace("#",""))
            values += [''] * (index - len(values))

            original = [x for x in values]

            # Sanitize our value based on type
            type_value = self.master.get_check_type(self.cell).lower()
            value = self.get()
            # We need to sanitize data and numbers for sure
            if type_value == "data":
                if self.master.data_display == "hex":
                    # Length must be a multiple of 2, and we need to
                    # assert only hex chars
                    # Strip the 0x prefix if it exists
                    if value.lower().startswith("0x"):
                        value = value[2:]
                    # Strip spaces, as some programs include them
                    value = value.replace(" ","")
                    # Ensure all chars are hex
                    if [x for x in value if x.lower() not in "0123456789abcdef"]:
                        # Got non-hex values
                        if not event == None:
                            # print("Non-hex character in data!\a")
                            self.bell()
                            if not mb.askyesno("Invalid Hex Data","Invalid character in passed hex data.\n\nWould you like to keep editing?",parent=self.parent):
                                self.destroy()
                        return
                    # Ensure we have an even number of chars
                    if len(value) % 2:
                        if not event == None:
                            self.bell()
                            if not mb.askyesno("Invalid Hex Data","Hex data must contain an even number of chars.\n\nWould you like to keep editing?",parent=self.parent):
                                self.destroy()
                            # print("Hex needs an even number of chars!\a")
                        return
                    # At this point, we can split our hex into groups of 8 chars and separate with
                    # a space for easy readability
                    value = "<{}>".format(" ".join((value[0+i:8+i] for i in range(0, len(value), 8))).upper())
                else:
                    # Base64 data - we need to make sure all values are within base64 spec, and that we're padded to 4 chars with =
                    # first we strip the = signs, then verify the data, then, if we have anything, we pad to 4 chars
                    value = value.rstrip("=")
                    if [x for x in value if x.lower() not in "0123456789abcdefghijklmnopqrstuvwxyz+/="]:
                        # Got non-hex values
                        if not event == None:
                            # print("Non-hex character in data!\a")
                            self.bell()
                            if not mb.askyesno("Invalid Base64 Data","Invalid base64 data passed.\n\nWould you like to keep editing?",parent=self.parent):
                                self.destroy()
                        return
                    if len(value) > 0 and len(value) % 4:
                        # we have leftover chars - pad to 4 with =
                        value += "=" * (4-len(value)%4)
                    # As a last resort, we'll convert it to base64 to verify it's good
                    try:
                        test = value
                        if sys.version_info >= (3,0):
                            test = test.encode("utf-8")
                        base64.b64decode(test)
                    except Exception as e:
                        # Not the correct format :(
                        if not event == None:
                            self.bell()
                            if not mb.askyesno("Invalid Base64 Data","Invalid base64 data passed.\n\n{}\n\nWould you like to keep editing?".format(str(e)),parent=self.parent):
                                self.destroy()
                        return
            elif type_value == "date":
                # We can take a few options for dates here.
                #
                # Now/Today
                # Mar 11, 2019 12:29:00 PM
                # YYYY-MM-DD HH:MM:SS Z
                #
                if value.lower() in ["now","today"]:
                    # Get the current date as a datetime object
                    value = datetime.datetime.now().strftime("%b %d, %Y %I:%M:%S %p")
                else:
                    # Try to parse with strptime
                    try:
                        value = datetime.datetime.strptime(value,"%b %d, %Y %I:%M:%S %p").strftime("%b %d, %Y %I:%M:%S %p")
                    except:
                        # Try the other method
                        try:
                            value = datetime.datetime.strptime(value,"%Y-%m-%d %H:%M:%S %z").strftime("%b %d, %Y %I:%M:%S %p")
                        except:
                            # Not the correct format :(
                            if not event == None:
                                self.bell()
                                if not mb.askyesno("Invalid Date","Couldn't convert the passed string to a date.\n\nValid formats include:\nNow/Today\nMar 11, 2019 12:29:00 PM\nYYYY-MM-DD HH:MM:SS Z\n\nWould you like to keep editing?",parent=self.parent):
                                    self.destroy()
                            return
            elif type_value == "number":
                # We need to check if we're using hex or decimal
                # then verify the chars involved
                if value.lower().startswith("0x"):
                    try:
                        value = int(value,16)
                    except:
                        # Something went wrong
                        if not event == None:
                            self.bell()
                            if not mb.askyesno("Invalid Hex Data","Couldn't convert the passed hex string to an integer.\n\nWould you like to keep editing?",parent=self.parent):
                                self.destroy()
                            # print("Could not convert hex!\a")
                        return
                else:
                    # Not hex, let's try casting as an int first,
                    # then as a float second - strip any commas
                    value = value.replace(",","")
                    try:
                        value = int(value)
                    except:
                        try:
                            value = float(value)
                        except:
                            # Failure!
                            if not event == None:
                                # print("Not a number!\a")
                                self.bell()
                                if not mb.askyesno("Invalid Number Data","Couldn't convert to an integer or float.\n\nWould you like to keep editing?",parent=self.parent):
                                    self.destroy()
                            return
                # At this point, we should have the decimal value
                value = str(value)
            # Add to undo stack
            self.master.add_undo({"cell":self.cell,"value":original})
            # Replace our value (may be slightly modified)
            values[index-1] = value
            # Set the values
            self.parent.item(self.cell, values=values)
        self.destroy()

class PlistWindow(tk.Toplevel):
    def __init__(self, controller, root, **kw):
        tk.Toplevel.__init__(self, root, **kw)
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        # Create the window
        self.root = root
        self.controller = controller
        self.undo_stack = []
        self.redo_stack = []
        self.drag_undo = None
        self.clicked_drag = False
        self.data_display = "hex" # hex or base64
        self.menu_code = u"\u21D5"
        #self.drag_code = u"\u2630"
        self.drag_code = u"\u2261"

        # self = tk.Toplevel(self.root)
        self.minsize(width=640,height=480)
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        w = 640
        h = 480
        # Let's also center the window
        x = self.winfo_screenwidth() // 2 - w // 2
        y = self.winfo_screenheight() // 2 - h // 2
        self.geometry("{}x{}+{}+{}".format(w,h, x, y))
        # Set the title to "Untitled.plist"
        self.title("Untitled.plist")

        # Set the close window binding
        if str(sys.platform) == "darwin":
            self.bind("<Command-w>", self.close_window)
        else:
            self.bind("<Control-w>", self.close_window)

        # Set up the options
        self.current_plist = None # None = new
        self.edited = False
        self.dragging = False
        self.drag_start = None
        self.type_menu = tk.Menu(self, tearoff=0)
        self.type_menu.add_command(label="Dictionary", command=lambda:self.change_type(self.menu_code + " Dictionary"))
        self.type_menu.add_command(label="Array", command=lambda:self.change_type(self.menu_code + " Array"))
        self.type_menu.add_separator()
        self.type_menu.add_command(label="Boolean", command=lambda:self.change_type(self.menu_code + " Boolean"))
        self.type_menu.add_command(label="Data", command=lambda:self.change_type(self.menu_code + " Data"))
        self.type_menu.add_command(label="Date", command=lambda:self.change_type(self.menu_code + " Date"))
        self.type_menu.add_command(label="Number", command=lambda:self.change_type(self.menu_code + " Number"))
        self.type_menu.add_command(label="String", command=lambda:self.change_type(self.menu_code + " String"))
        
        # Set up the boolean selection menu
        self.bool_menu = tk.Menu(self, tearoff=0)
        self.bool_menu.add_command(label="True", command=lambda:self.set_bool("True"))
        self.bool_menu.add_command(label="False", command=lambda:self.set_bool("False"))

        # Create the treeview
        self._tree = ttk.Treeview(self, columns=("Type","Value","Drag"))
        self._tree.heading("#0", text="Key")
        self._tree.heading("#1", text="Type")
        self._tree.heading("#2", text="Value")
        self._tree.column("Type",width=100,stretch=False)
        self._tree.column("Drag",minwidth=40,width=40,stretch=False,anchor="center")

        # Create the scrollbar
        vsb = ttk.Scrollbar(self, orient='vertical', command=self._tree.yview)
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
        self.bind("<FocusIn>", self.got_focus)

        # Setup menu bar (hopefully per-window) - only happens on non-mac systems
        if not str(sys.platform) == "darwin":
            key="Control"
            sign = "Ctr+"
            main_menu = tk.Menu(self)
            file_menu = tk.Menu(self, tearoff=0)
            main_menu.add_cascade(label="File", menu=file_menu)
            file_menu.add_command(label="New ({}N)".format(sign), command=self.controller.new_plist)
            file_menu.add_command(label="Open ({}O)".format(sign), command=self.controller.open_plist)
            file_menu.add_command(label="Save ({}S)".format(sign), command=self.controller.save_plist)
            file_menu.add_command(label="Save As ({}Shift+S)".format(sign), command=self.controller.save_plist_as)
            file_menu.add_command(label="Duplicate ({}D)".format(sign), command=self.controller.duplicate_plist)
            file_menu.add_separator()
            file_menu.add_command(label="Convert Window ({}T)".format(sign), command=self.controller.show_convert)
            file_menu.add_command(label="Strip Comments ({}M)".format(sign), command=self.strip_comments)
            file_menu.add_separator()
            file_menu.add_command(label="View Data As Hex", command=lambda:self.change_data_display("hex"))
            file_menu.add_command(label="View Data As Base64", command=lambda:self.change_data_display("base64"))
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

        # Sort dictionary keys?
        self.sort_dict = True
        
        # Add the treeview
        vsb.pack(side="right",fill="y")
        self._tree.pack(side="bottom", fill="both", expand=True)
        self.entry_popup = None

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

    def reundo(self, event=None, undo = True):
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
        # Let's check if we have an r_task_list - and add it
        if len(r_task_list):
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
        self._tree.item(tv_item,open=True)
        if not self.get_check_type(tv_item).lower() in ["dictionary","array"]:
            # Allow adding as child
            if not tv_item == "":
                tv_item = self._tree.parent(tv_item)
                self._tree.item(tv_item,open=True)
        # Let's get the bounding box for the target, and if we're in the lower half,
        # we'll add as a child, uper half will add as a sibling
        else:
            rowid = self._tree.identify_row(event.y)
            column = self._tree.identify_column(event.x)
            x,y,width,height = self._tree.bbox(rowid, column)
            if event.y >= y+height/2 and event.y < y+height:
                # Just above should add as a sibling
                tv_item = self._tree.parent(tv_item)
                self._tree.item(tv_item,open=True)
            else:
                # Just below should add it at item 0
                move_to = 0
        target = self._tree.focus()
        if self._tree.index(target) == move_to and tv_item == target:
            # Already the same
            return
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
        target = self._tree.focus()
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

    def check_save(self):
        if not self.edited:
            return True # No changes, all good
        # Post a dialog asking if we want to save the current plist
        answer = mb.askyesnocancel("Unsaved Changes", "Save changes to current document?", parent=self)
        if answer == True:
            return self.save_plist()
        return answer

    def save_plist(self, event=None):
        # Pass the current plist to the save_plist_as function
        return self.save_plist_as(event, self.current_plist)

    def save_plist_as(self, event=None, path=None):
        if path == None:
            # Get the file dialog
            path = fd.asksaveasfilename(parent=self, title = "Please select a file name for saving:",filetypes=[("Plist files", "*.plist")])
            if not len(path):
                # User cancelled - no changes
                return None
            if not path.lower().endswith(".plist"):
                path+=".plist"
        # Should have the save path
        plist_data = self.nodes_to_values()
        # Create a temp folder and save there first
        temp = tempfile.mkdtemp()
        temp_file = os.path.join(temp, os.path.basename(path))
        try:
            with open(temp_file,"wb") as f:
                plist.dump(plist_data,f)
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

    def open_plist(self, path, plist_data):
        # Opened it correctly - let's load it, and set our values
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
            self.root.quit()
        else:
            self.destroy()
        return True

    def paste_selection(self, value):
        node = self._tree.focus()
        # Verify the type - or get the parent
        t = self.get_check_type(node).lower()
        if not node == "" and not t in ["dictionary","array"]:
            node = self._tree.parent(node)
        t = self.get_check_type(node).lower()
        verify = t in ["dictionary",""]
        dict_list = list(value.items()) if not self.sort_dict else sorted(list(value.items()))
        for (key,val) in dict_list:
            if verify:
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
            self._tree.item(last,open=True)
        self.add_undo({"type":"add","cell":last})
        self._tree.focus(last)
        self._tree.selection_set(last)
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
            i = ""
        else:
            if isinstance(value,(list,tuple)):
                children = "1 child" if len(value) == 1 else "{} children".format(len(value))
                values = (self.get_type(value),children,self.drag_code)
            elif isinstance(value,dict):
                children = "1 key/value pair" if len(value) == 1 else "{} key/value pairs".format(len(value))
                values = (self.get_type(value),children,self.drag_code)
            else:
                values = (self.get_type(value),value,self.drag_code)
            i = self._tree.insert(parentNode, "end", text=key, values=values)

        if isinstance(value, dict):
            self._tree.item(i, open=True)
            dict_list = list(value.items()) if not self.sort_dict else sorted(list(value.items()))
            for (key,val) in dict_list:
                self.add_node(val, i, key)
        elif isinstance(value, (list,tuple)):
            self._tree.item(i, open=True)
            for (key,val) in enumerate(value):
                self.add_node(val, i, key)
        elif self.is_data(value):
            self._tree.item(i, values=(self.get_type(value),self.get_data(value),self.drag_code,))
        elif isinstance(value, datetime.datetime):
            self._tree.item(i, values=(self.get_type(value),value.strftime("%b %d, %Y %I:%M:%S %p"),self.drag_code,))
        else:
            self._tree.item(i, values=(self.get_type(value),value,self.drag_code,))
        return i

    def nodes_to_values(self,node="",parent={}):
        if node == "" or node == None:
            # top level
            parent = {}
            for child in self._tree.get_children(node):
                parent = self.nodes_to_values(child,parent)
            return parent
        # Not top - process
        name = self._tree.item(node,"text")
        values = self.get_padded_values(node, 3)
        value = values[1]
        check_type = self.get_check_type(node).lower()
        # Iterate value types
        if check_type == "dictionary":
            value = {}
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
        # At this point, we should have the name and value
        for child in self._tree.get_children(node):
            value = self.nodes_to_values(child,value)
        if isinstance(parent,list):
            parent.append(value)
        elif isinstance(parent,dict):
            parent[name] = value
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
        elif isinstance(value, (int,float)):
            return self.menu_code + " Number"
        elif isinstance(value, str):
            return self.menu_code + " String"
        else:
            return self.menu_code + type(value)

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
            target = self._tree.focus()
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
            target = self._tree.focus()
        if target == "":
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

    def change_type(self, value):
        # Need to walk the values and pad
        values = self.get_padded_values(self._tree.focus(), 3)
        # Verify we actually changed type
        if values[0] == value:
            # No change, bail
            return
        original = [x for x in values]
        # Replace our value
        values[0] = value
        # Remove children if needed
        changes = []
        for i in self._tree.get_children(self._tree.focus()):
            changes.append({
                "type":"remove",
                "cell":i,
                "from":self._tree.parent(i),
                "index":self._tree.index(i)
            })
            self._tree.detach(i)
        cell = self._tree.focus()
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
            self._tree.item(self._tree.focus(),open=True)
            values[1] = "0 children"
        elif value.lower() == "dictionary":
            self._tree.item(self._tree.focus(),open=True)
            values[1] = "0 key/value pairs"
        elif value.lower() == "date":
            values[1] = datetime.datetime.now().strftime("%b %d, %Y %I:%M:%S %p")
        elif value.lower() == "data":
            values[1] = "<>" if self.data_display == "hex" else ""
        else:
            values[1] = ""
        # Set the values
        self._tree.item(self._tree.focus(), values=values)
        if not self.edited:
            self.edited = True
            self.title(self.title()+" - Edited")

    ###             ###
    # Click Functions #
    ###             ###

    def set_bool(self, value):
        # Need to walk the values and pad
        values = self.get_padded_values(self._tree.focus(), 3)
        cell = self._tree.focus()
        self.add_undo({
            "type":"edit",
            "cell":cell,
            "text":self._tree.item(cell,"text"),
            "value":[x for x in values]
            })
        values[1] = value
        # Set the values
        self._tree.item(self._tree.focus(), values=values)
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
                        mb.showerror("Incorrect Type", "{} is {}, should be {}.".format(cell_name,current_type,needed_type), parent=self)
                        return
                    found = True
                    current_cell = x
                    break
            if not found:
                # Need to add it
                current_cell = self._tree.insert(current_cell,"end",text=p,values=(self.menu_code+" "+needed_type,"",self.drag_code,),open=True)
                if created == None:
                    # Only get the top level item created
                    created = current_cell
        
        # At this point - we should be able to add the final piece
        # let's first make sure it doesn't already exist - if it does, we
        # will overwrite it
        '''current_type = self.get_check_type(current_cell).lower()
        if current_type == "dictionary":
            # Scan through and make sure we have all the keys needed
            for x in self._tree.get_children(current_cell):
                name = self._tree.item(x,"text")
                if name in value:
                    # Need to change this one
                    if len(self._tree.get_children(x)):
                        # Add some remove commands'''
        last_cell = self.add_node(value,current_cell,"")
        if created == None:
            created = last_cell
        self.add_undo({
            "type":"add",
            "cell":created
            })
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
        # self.popup_menu.add_cascade(label="New", menu=new_menu)
        popup_menu.add_command(label="Expand All", command=self.expand_all)
        popup_menu.add_command(label="Collapse All", command=self.collapse_all)
        popup_menu.add_separator()
        # Determine if we are adding a child or a sibling
        if cell == "":
            # Top level
            popup_menu.add_command(label="New top level entry (+)".format(self._tree.item(cell,"text")), command=lambda:self.new_row(cell))
        else:
            if self.get_check_type(cell).lower() in ["array","dictionary"] and (self._tree.item(cell,"open") or not len(self._tree.get_children(cell))):
                popup_menu.add_command(label="New child under '{}' (+)".format(self._tree.item(cell,"text")), command=lambda:self.new_row(cell))
                popup_menu.add_command(label="New sibling of '{}'".format(self._tree.item(cell,"text")), command=lambda:self.new_row(cell,True))
                popup_menu.add_command(label="Remove '{}' and any children (-)".format(self._tree.item(cell,"text")), command=lambda:self.remove_row(cell))
            else:
                popup_menu.add_command(label="New sibling of '{}' (+)".format(self._tree.item(cell,"text")), command=lambda:self.new_row(cell))
                popup_menu.add_command(label="Remove '{}' (-)".format(self._tree.item(cell,"text")), command=lambda:self.remove_row(cell))
        
        # Walk through the menu data if it exists
        cell_path = self.get_cell_path(cell)
        open_core = self.menu_data.get("OpenCore",{})
        clover    = self.menu_data.get("Clover",{})
        oc_valid  = [x for x in list(open_core) if x.startswith(cell_path)]
        cl_valid  = [x for x in list(clover) if x.startswith(cell_path)]
        if len(oc_valid) or len(cl_valid):
            popup_menu.add_separator()
        if len(oc_valid):
            oc_menu = tk.Menu(popup_menu, tearoff=0)
            for item in sorted(oc_valid):
                item_menu = tk.Menu(oc_menu, tearoff=0)
                for x in open_core[item]:
                    name  = x["name"]
                    value = x["value"]
                    types = x["types"]
                    passed = (cell,item,types,value)
                    item_menu.add_command(label=name, command=lambda item=passed: self.merge_menu_preset(item))
                oc_menu.add_cascade(label=item,menu=item_menu)
            popup_menu.add_cascade(label="OpenCore",menu=oc_menu)
        if len(cl_valid):
            clover_menu = tk.Menu(popup_menu, tearoff=0)
            for item in sorted(cl_valid):
                item_menu = tk.Menu(clover_menu, tearoff=0)
                for x in clover[item]:
                    name  = x["name"]
                    value = x["value"]
                    types = x["types"]
                    passed = (cell,item,types,value)
                    item_menu.add_command(label=name, command=lambda item=passed: self.merge_menu_preset(item))
                clover_menu.add_cascade(label=item,menu=item_menu)
            popup_menu.add_cascade(label="Clover",menu=clover_menu)
            
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
            pt = self._tree.item(self._tree.parent(tv_item),"values")[0]
        except:
            pt = ""
        if index == 1:
            # Type change - let's show our menu
            try:
                self.type_menu.tk_popup(event.x_root, event.y_root, 0)
            finally:
                self.type_menu.grab_release()
            return 'break'
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
        cell = self._tree.item(self._tree.focus())
        # place Entry popup properly
        self.entry_popup = EntryPopup(self._tree, text, tv_item, column)
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

    def pre_alternate(self, event):
        # Only called before an item opens - we need to open it manually to ensure
        # colors alternate correctly
        cell = self._tree.focus()
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