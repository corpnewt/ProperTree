#!/usr/bin/env python
import sys, os, binascii, base64, json, re
from collections import OrderedDict
try:
    import Tkinter as tk
    import ttk
    import tkFileDialog as fd
    import tkMessageBox as mb
except:
    import tkinter as tk
    import tkinter.ttk as ttk
    from tkinter import filedialog as fd
    from tkinter import messagebox as mb
# Add this script's dir to the local PATH var - may improve import consistency
sys.path.append(os.path.abspath(os.path.dirname(os.path.realpath(__file__))))
from Scripts import *

class ProperTree:
    def __init__(self, plists = []):
        # Create the new tk object
        self.tk = tk.Tk()
        self.convert_frame = ttk.Frame(self.tk)
        self.convert_frame.grid()
        self.convert_frame.pack(fill="both",expand=True)
        self.tk.title("Convert Values")
        self.tk.minsize(width=640,height=130)
        self.tk.maxsize(width=10000,height=130)
        self.tk.resizable(True, False)
        self.tk.columnconfigure(2,weight=1)
        self.tk.columnconfigure(3,weight=1)
        # Build the Hex <--> Base64 converter
        f_label = ttk.Label(self.convert_frame, text="From:")
        f_label.grid(row=0,column=0,padx=10,pady=10)
        t_label = ttk.Label(self.convert_frame, text="To:")
        t_label.grid(row=1,column=0,padx=10,pady=10)

        # Create the settings window
        self.settings_window = tk.Toplevel(self.tk)
        self.settings_frame = ttk.Frame(self.settings_window)
        self.settings_frame.pack(fill="both",expand=True)
        self.settings_window.title("ProperTree Settings")
        w = 380
        h = 150
        self.settings_window.minsize(width=w,height=h)
        self.settings_window.resizable(False, False)
        self.settings_frame.columnconfigure(0,weight=1)
        self.settings_frame.columnconfigure(1,weight=1)
        # Let's also center the window
        x = self.settings_window.winfo_screenwidth() // 2 - w // 2
        y = self.settings_window.winfo_screenheight() // 2 - h // 2
        self.settings_window.geometry("{}x{}+{}+{}".format(w,h, x, y))
        # Let's add some checkboxes and stuffs
        self.expand_on_open = tk.IntVar()
        self.use_xcode_data = tk.IntVar()
        self.sort_dict_keys = tk.IntVar()
        self.expand_check = ttk.Checkbutton(self.settings_frame,text="Expand Children When Opening Plist",variable=self.expand_on_open,command=self.expand_command)
        self.xcode_check = ttk.Checkbutton(self.settings_frame,text="Use Xcode-Style <data> Tags (Inline) in XML Plists",variable=self.use_xcode_data,command=self.xcode_command)
        self.sort_check = ttk.Checkbutton(self.settings_frame,text="Ignore Dictionary Key Order",variable=self.sort_dict_keys,command=self.sort_command)
        self.expand_check.grid(row=0,column=0,columnspan=2,sticky="w",padx=10,pady=(10,0))
        self.xcode_check.grid(row=1,column=0,columnspan=2,sticky="w",padx=10)
        self.sort_check.grid(row=2,column=0,columnspan=2,sticky="w",padx=10)
        self.plist_type_string = tk.StringVar(self.settings_frame)
        self.plist_type_menu = ttk.OptionMenu(self.settings_frame, self.plist_type_string, "XML", "XML","Binary", command=self.change_plist_type)
        plist_label = ttk.Label(self.settings_frame,text="Default New Plist Type:")
        plist_label.grid(row=3,column=0,sticky="w",padx=10)
        self.plist_type_menu.grid(row=3,column=1,sticky="we",padx=10)
        reset_settings = ttk.Button(self.settings_frame,text="Reset To Defaults",command=self.reset_settings)
        reset_settings.grid(row=4,column=1,sticky="e",padx=10,pady=(0,10))

        # Setup the from/to option menus
        f_title = tk.StringVar(self.tk)
        t_title = tk.StringVar(self.tk)
        f_title.set("Base64")
        t_title.set("Hex")
        f_option = ttk.OptionMenu(self.convert_frame, f_title, "Base64", "Ascii", "Base64", "Decimal", "Hex", command=self.change_from_type)
        t_option = ttk.OptionMenu(self.convert_frame, t_title, "Hex", "Ascii", "Base64", "Decimal", "Hex", command=self.change_to_type)
        self.from_type = "Base64"
        self.to_type   = "Hex"
        f_option.grid(row=0,column=1,sticky="we")
        t_option.grid(row=1,column=1,sticky="we")

        self.f_text = ttk.Entry(self.convert_frame)
        self.f_text.delete(0,tk.END)
        self.f_text.insert(0,"")
        self.f_text.grid(row=0,column=2,columnspan=2,sticky="we",padx=10,pady=10)

        self.t_text = ttk.Entry(self.convert_frame)
        self.t_text.configure(state='normal')
        self.t_text.delete(0,tk.END)
        self.t_text.insert(0,"")
        self.t_text.configure(state='readonly')
        self.t_text.grid(row=1,column=2,columnspan=2,sticky="we",padx=10,pady=10)

        self.c_button = ttk.Button(self.convert_frame, text="Convert", command=self.convert_values)
        self.c_button.grid(row=2,column=3,sticky="e",padx=10,pady=10)

        self.f_text.bind("<Return>", self.convert_values)
        self.f_text.bind("<KP_Enter>", self.convert_values)

        self.convert_frame.columnconfigure(2, weight=1)

        self.start_window = None

        # Regex to find the processor serial numbers when
        # opened from the Finder
        self.regexp = re.compile(r"^-psn_[0-9]+_[0-9]+$")

        # Setup the menu-related keybinds - and change the app name if needed
        key="Control"
        sign = "Ctrl+"
        if str(sys.platform) == "darwin":
            # Remap the quit function to our own
            self.tk.createcommand('::tk::mac::Quit', self.quit)
            self.tk.createcommand("::tk::mac::OpenDocument", self.open_plist_from_app)
            self.tk.createcommand("::tk::mac::ReopenApplication", self.open_plist_from_app)
            self.tk.createcommand("::tk::mac::ShowPreferences", self.show_settings)
            # Import the needed modules to change the bundle name and force focus
            try:
                from Foundation import NSBundle
                from Cocoa import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
                app = NSRunningApplication.runningApplicationWithProcessIdentifier_(os.getpid())
                app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                bundle = NSBundle.mainBundle()
                if bundle:
                    info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
                    if info and info['CFBundleName'] == 'Python':
                        info['CFBundleName'] = "ProperTree"
            except:
                pass
            key="Command"
            sign=key+"+"

        self.tk.protocol("WM_DELETE_WINDOW", self.close_window)
        self.settings_window.protocol("WM_DELETE_WINDOW", self.close_window)
        # Close initial windows
        self.tk.withdraw()
        self.settings_window.withdraw()

        self.default_windows = (self.tk,self.settings_window)

        if str(sys.platform) == "darwin":
            # Setup the top level menu
            file_menu = tk.Menu(self.tk)
            main_menu = tk.Menu(self.tk)
            main_menu.add_cascade(label="File", menu=file_menu)
            file_menu.add_command(label="New", command=self.new_plist, accelerator="Cmd+N")
            file_menu.add_command(label="Open", command=self.open_plist, accelerator="Cmd+O")
            file_menu.add_command(label="Save", command=self.save_plist, accelerator="Cmd+S")
            file_menu.add_command(label="Save As...", command=self.save_plist_as, accelerator="Cmd+Shift+S")
            file_menu.add_command(label="Duplicate", command=self.duplicate_plist, accelerator="Cmd+D")
            file_menu.add_command(label="Reload From Disk", command=self.reload_from_disk, accelerator="Cmd+L")
            file_menu.add_separator()
            file_menu.add_command(label="OC Snapshot", command=self.oc_snapshot, accelerator="Cmd+R")
            file_menu.add_command(label="OC Clean Snapshot", command=self.oc_clean_snapshot, accelerator="Cmd+Shift+R")
            file_menu.add_separator()
            file_menu.add_command(label="Convert Window", command=self.show_convert, accelerator="Cmd+T")
            file_menu.add_command(label="Strip Comments", command=self.strip_comments, accelerator="Cmd+M")
            file_menu.add_separator()
            file_menu.add_command(label="Toggle Find/Replace Pane",command=self.hide_show_find, accelerator="Cmd+F")
            file_menu.add_command(label="Toggle Plist/Data Type Pane",command=self.hide_show_type, accelerator="Cmd+P")
            self.tk.config(menu=main_menu)

        # Set bindings
        self.tk.bind("<{}-w>".format(key), self.close_window)
        self.settings_window.bind("<{}-w>".format(key), self.close_window)
        self.tk.bind_all("<{}-n>".format(key), self.new_plist)
        self.tk.bind_all("<{}-o>".format(key), self.open_plist)
        self.tk.bind_all("<{}-s>".format(key), self.save_plist)
        self.tk.bind_all("<{}-S>".format(key), self.save_plist_as)
        self.tk.bind_all("<{}-d>".format(key), self.duplicate_plist)
        self.tk.bind_all("<{}-t>".format(key), self.show_convert)
        self.tk.bind_all("<{}-z>".format(key), self.undo)
        self.tk.bind_all("<{}-Z>".format(key), self.redo)
        self.tk.bind_all("<{}-m>".format(key), self.strip_comments)
        self.tk.bind_all("<{}-r>".format(key), self.oc_snapshot)
        self.tk.bind_all("<{}-R>".format(key), self.oc_clean_snapshot)
        self.tk.bind_all("<{}-l>".format(key), self.reload_from_disk)
        self.tk.bind_all("<{}-comma>".format(key), self.show_settings)
        if not str(sys.platform) == "darwin":
            # Rewrite the default Command-Q command
            self.tk.bind_all("<{}-q>".format(key), self.quit)
        
        cwd = os.getcwd()
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        #
        # Load the settings - current available settings are:
        # 
        # last_window_width:         width value (default is 640)
        # last_window_height:        height value (default is 480)
        # expand_all_items_on_open:  bool
        # sort_dict:                 bool, false = OrderedDict
        # xcode_data:                bool, true = <data>XXXX</data>, false = different lines
        # new_plist_default_type:    string, XML/Binary
        #
        self.settings = {}
        try:
            if os.path.exists("Scripts/settings.json"):
                self.settings = json.load(open("Scripts/settings.json"))
        except:
            pass
        os.chdir(cwd)

        # Setup the settings page to reflect our settings.json file

        self.allowed_types = ("XML","Binary")
        self.update_settings()
        
        # Wait before opening a new document to see if we need to.
        # This was annoying to debug, but seems to work.
        self.tk.after(100, lambda:self.check_open(plists))

        # Start our run loop
        tk.mainloop()

    def expand_command(self, event = None):
        self.settings["expand_all_items_on_open"] = True if self.expand_on_open.get() else False

    def xcode_command(self, event = None):
        self.settings["xcode_data"] = True if self.use_xcode_data.get() else False

    def sort_command(self, event = None):
        self.settings["sort_dict"] = True if self.sort_dict_keys.get() else False

    def change_plist_type(self, event = None):
        self.settings["new_plist_default_type"] = self.plist_type_string.get()

    def reset_settings(self, event = None):
        self.settings = {}
        self.update_settings()

    def update_settings(self):
        self.expand_on_open.set(self.settings.get("expand_all_items_on_open",True))
        self.use_xcode_data.set(self.settings.get("xcode_data",True))
        self.sort_dict_keys.set(self.settings.get("sort_dict",False))
        def_type = self.settings.get("new_plist_default_type","XML")
        self.plist_type_string.set(def_type if def_type in self.allowed_types else self.allowed_types[0])

    def check_open(self, plists = []):
        plists = [x for x in plists if not self.regexp.search(x)]
        if isinstance(plists, list) and len(plists):
            # Iterate the passed plists and open them
            for p in set(plists):
                window = self.open_plist_with_path(None,p,None)
                if self.start_window == None:
                    self.start_window = window
        elif not len(self.stackorder(self.tk)):
            # create a fresh plist to start
            self.start_window = self.new_plist()

    def open_plist_from_app(self, *args):
        if isinstance(args, str):
            args = [args]
        args = [x for x in args if not self.regexp.search(x)]
        for arg in args:
            # Let's load the plist
            if self.start_window == None:
                self.start_window = self.open_plist_with_path(None,arg,None)
            elif self.start_window.current_plist == None:
                self.open_plist_with_path(None,arg,self.start_window)
            else:
                self.open_plist_with_path(None,arg,None)

    def change_hd_type(self, value):
        self.hd_type = value

    def reload_from_disk(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1] # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.reload_from_disk(event)

    def change_data_display(self, new_data = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1] # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.change_data_display(new_data)

    def oc_clean_snapshot(self, event = None):
        self.oc_snapshot(event,True)

    def oc_snapshot(self, event = None, clean = False):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1] # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.oc_snapshot(event,clean)

    def hide_show_find(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1] # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.hide_show_find(event)

    def hide_show_type(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1] # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.hide_show_type(event)

    def close_window(self, event = None, check_close = True):
        # Remove the default window that comes from it
        windows = self.stackorder(self.tk)
        if len(windows):
            windows[-1].withdraw()
            windows = windows[:-1]
        if check_close and not len(windows):
            # Quit if all windows are closed
            self.quit()

    def strip_comments(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1] # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.strip_comments(event)

    def change_to_type(self, value):
        self.to_type = value
        self.convert_values()

    def change_from_type(self, value):
        self.from_type = value

    def show_settings(self, event = None):
        self.settings_window.deiconify()

    def show_convert(self, event = None):
        if self.tk.state() == "normal":
            self.tk.withdraw()
        else:
            self.tk.deiconify()

    def convert_values(self, event = None):
        from_value = self.f_text.get()
        if not len(from_value):
            # Empty - nothing to convert
            return
        # Pre-check for hex potential issues
        if self.from_type.lower() == "hex":
            if from_value.lower().startswith("0x"):
                from_value = from_value[2:]
            from_value = from_value.replace(" ","").replace("<","").replace(">","")
            if [x for x in from_value if x.lower() not in "0123456789abcdef"]:
                self.tk.bell()
                mb.showerror("Invalid Hex Data","Invalid character in passed hex data.") # ,parent=self.tk)
                return
        try:
            if self.from_type.lower() == "decimal":
                # Convert to hex bytes
                from_value = "{:x}".format(int(from_value))
                if len(from_value) % 2:
                    from_value = "0"+from_value
            # Handle the from data
            if sys.version_info >= (3,0):
                # Convert to bytes
                from_value = from_value.encode("utf-8")
            if self.from_type.lower() == "base64":
                from_value = base64.b64decode(from_value)
            elif self.from_type.lower() in ["hex","decimal"]:
                from_value = binascii.unhexlify(from_value)
            # Let's get the data converted
            to_value = from_value
            if self.to_type.lower() == "base64":
                to_value = base64.b64encode(from_value)
            elif self.to_type.lower() == "hex":
                to_value = binascii.hexlify(from_value)
            elif self.to_type.lower() == "decimal":
                to_value = str(int(binascii.hexlify(from_value),16))
            if sys.version_info >= (3,0) and not self.to_type.lower() == "decimal":
                # Convert to bytes
                to_value = to_value.decode("utf-8")
            if self.to_type.lower() == "hex":
                # Capitalize it, and pad with spaces
                to_value = "{}".format(" ".join((to_value[0+i:8+i] for i in range(0, len(to_value), 8))).upper())
            # Set the text box
            self.t_text.configure(state='normal')
            self.t_text.delete(0,tk.END)
            self.t_text.insert(0,to_value)
            self.t_text.configure(state='readonly')
        except Exception as e:
            self.tk.bell()
            mb.showerror("Conversion Error",str(e)) # ,parent=self.tk)

    ###                       ###
    # Save/Load Plist Functions #
    ###                       ###

    def duplicate_plist(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1] # Get the last item (most recent)
        if window in self.default_windows:
            return
        plist_data = window.nodes_to_values()
        plistwindow.PlistWindow(self, self.tk).open_plist(None,plist_data)

    def save_plist(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1] # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.save_plist(event)
    
    def save_plist_as(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1] # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.save_plist_as(event)

    def undo(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1] # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.reundo(event)

    def redo(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1] # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.reundo(event,False)
    
    def new_plist(self, event = None):
        # Creates a new plistwindow object
        # Let's try to create a unique name (if Untitled.plist is used, add a number)
        titles = [x.title().lower() for x in self.stackorder(self.tk)]
        number = 0
        final_title = "Untitled.plist"
        while True:
            temp = "Untitled{}.plist".format("" if number == 0 else "-"+str(number))
            if not temp.lower() in titles:
                final_title = temp
                break
            number += 1
        window = plistwindow.PlistWindow(self, self.tk)
        window.open_plist(final_title,{}) # Created an empty root
        window.current_plist = None # Ensure it's initialized as new
        default_type = self.settings.get("new_plist_default_type","XML")
        window.plist_type_string.set(default_type if default_type in self.allowed_types else self.allowed_types[0])
        window.focus_force()
        window.update()
        return window

    def open_plist(self, event=None):
        # Prompt the user to open a plist, attempt to load it, and if successful,
        # set its path as our current_plist value
        current_window = None
        windows = self.stackorder(self.tk)
        if len(windows) == 1 and windows[0] == self.start_window and windows[0].edited == False and windows[0].current_plist == None:
            # Fresh window - replace the contents
            current_window = windows[0]
        path = fd.askopenfilename(title = "Select plist file") # ,parent=current_window) # Apparently parent here breaks on 10.15?
        if not len(path):
            # User cancelled - bail
            return None
        path = os.path.realpath(os.path.expanduser(path))
        # Verify that no other window has that file selected already
        for window in windows:
            if window in self.default_windows:
                continue
            if window.current_plist == path:
                # found one - just make this focus instead
                window.focus_force()
                window.update()
                window.bell()
                mb.showerror("File Already Open", "{} is already open here.".format(path)) # , parent=window)
                return
        self.open_plist_with_path(event,path,current_window)

    def open_plist_with_path(self, event = None, path = None, current_window = None, plist_type = "XML"):
        if path == None:
            # Uh... wut?
            return
        path = os.path.realpath(os.path.expanduser(path))
        # Let's try to load the plist
        try:
            with open(path,"rb") as f:
                plist_type = "Binary" if plist._is_binary(f) else "XML"
                plist_data = plist.load(f,dict_type=dict if self.settings.get("sort_dict",False) else OrderedDict)
        except Exception as e:
            # Had an issue, throw up a display box
            self.tk.bell()
            mb.showerror("An Error Occurred While Opening {}".format(os.path.basename(path)), str(e)) # ,parent=current_window)
            return None
        # Opened it correctly - let's load it, and set our values
        if current_window:
            current_window.open_plist(path,plist_data,plist_type,self.settings.get("expand_all_items_on_open",True))
        else:
            # Need to create one first
            current_window = plistwindow.PlistWindow(self, self.tk)
            current_window.open_plist(path,plist_data,plist_type,self.settings.get("expand_all_items_on_open",True))
        current_window.focus_force()
        current_window.update()
        return True

    def stackorder(self, root):
        """return a list of root and toplevel windows in stacking order (topmost is last)"""
        c = root.children
        s = root.tk.eval('wm stackorder {}'.format(root))
        L = [x.lstrip('.') for x in s.split()]
        return [(c[x] if x else root) for x in L]

    def quit(self, event=None):
        # Check if we need to save first, then quit if we didn't cancel
        for window in self.stackorder(self.tk)[::-1]:
            if window in self.default_windows:
                continue
            if window.check_save() == None:
                # User cancelled or we failed to save, bail
                return
            window.destroy()
        # Actually quit the tkinter session
        self.tk.destroy()
        # Attempt to save the settings
        cwd = os.getcwd()
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        try:
            json.dump(self.settings,open("Scripts/settings.json","w"),indent=4)
        except:
            pass
        os.chdir(cwd)

if __name__ == '__main__':
    plists = []
    if len(sys.argv) > 1:
        plists = sys.argv[1:]
    p = ProperTree(plists)
