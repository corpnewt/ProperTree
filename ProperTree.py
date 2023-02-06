#!/usr/bin/env python
import sys, os, binascii, base64, json, re, subprocess, webbrowser, multiprocessing, signal
from collections import OrderedDict
try:
    import Tkinter as tk
    import ttk
    import tkFileDialog as fd
    import tkMessageBox as mb
    from tkFont import Font, families
    from tkColorChooser import askcolor as ac
except:
    import tkinter as tk
    import tkinter.ttk as ttk
    from tkinter import filedialog as fd
    from tkinter import messagebox as mb
    from tkinter.font import Font, families
    from tkinter.colorchooser import askcolor as ac
try:
    unicode
except NameError:  # Python 3
    unicode = str
# Add this script's dir to the local PATH var - may improve import consistency
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from Scripts import plist, plistwindow, downloader

def _check_for_update(queue, version_url = None, user_initiated = False):
    args = [sys.executable]
    file_path = os.path.join(os.path.abspath(os.path.dirname(__file__)),"Scripts","update_check.py")
    if os.path.exists(file_path):
        args.append(file_path)
    else:
        return queue.put({
            "exception":"Could not locate update_check.py.",
            "error":"Missing Required Files",
            "user_initiated":user_initiated
        })
    if version_url: args.extend(["-u",version_url])
    proc = subprocess.Popen(args,stdout=subprocess.PIPE)
    o,e = proc.communicate()
    if sys.version_info >= (3,0): o = o.decode("utf-8")
    try:
        json_data = json.loads(o)
        # Append/update our user_initiated value
        json_data["user_initiated"] = user_initiated
    except:
        return queue.put({
            "exception":"Could not serialize returned JSON data.",
            "error":"An Error Occurred Checking For Updates",
            "user_initiated":user_initiated
        })
    queue.put(json_data)

class ProperTree:
    def __init__(self, plists = []):
        # Create a new queue for multiprocessing
        self.queue = multiprocessing.Queue()
        # Create the new tk object
        self.tk = tk.Tk()
        self.tk.withdraw() # Try to remove before it's drawn
        self.tk.title("Convert Values")
        self.tk.minsize(width=640,height=130)
        self.tk.resizable(True, False)
        self.tk.columnconfigure(2,weight=1)
        self.tk.columnconfigure(3,weight=1)
        # Build the Hex <--> Base64 converter
        f_label = tk.Label(self.tk, text="From:")
        f_label.grid(row=0,column=0,padx=10,pady=10)
        t_label = tk.Label(self.tk, text="To:")
        t_label.grid(row=1,column=0,padx=10,pady=10)

        # Create the settings window
        self.settings_window = tk.Toplevel(self.tk)
        self.settings_window.withdraw() # Try to remove before it's drawn
        self.settings_window.title("ProperTree Settings")
        self.settings_window.resizable(False, False)
        self.settings_window.columnconfigure(0,weight=1)
        self.settings_window.columnconfigure(1,weight=1)
        self.settings_window.columnconfigure(3,weight=1)
        self.settings_window.columnconfigure(4,weight=1)

        # Set the default max undo/redo steps to retain
        self.max_undo = 200
        
        # Left side - functional elements:
        
        # Let's add some checkboxes and stuffs
        sep_func = ttk.Separator(self.settings_window,orient="horizontal")
        sep_func.grid(row=0,column=1,columnspan=1,sticky="we",padx=10,pady=10)
        func_label = tk.Label(self.settings_window,text="Functionality Options:")
        func_label.grid(row=0,column=0,sticky="w",padx=10,pady=10)

        self.expand_on_open = tk.IntVar()
        self.use_xcode_data = tk.IntVar()
        self.sort_dict_keys = tk.IntVar()
        self.comment_ignore_case = tk.IntVar()
        self.comment_check_string = tk.IntVar()
        self.force_schema = tk.IntVar()
        self.expand_check = tk.Checkbutton(self.settings_window,text="Expand Children When Opening Plist",variable=self.expand_on_open,command=self.expand_command)
        self.xcode_check = tk.Checkbutton(self.settings_window,text="Use Xcode-Style <data> Tags (Inline) in XML Plists",variable=self.use_xcode_data,command=self.xcode_command)
        self.sort_check = tk.Checkbutton(self.settings_window,text="Ignore Dictionary Key Order",variable=self.sort_dict_keys,command=self.sort_command)
        self.ignore_case_check = tk.Checkbutton(self.settings_window,text="Ignore Case When Stripping Comments",variable=self.comment_ignore_case,command=self.ignore_case_command)
        self.check_string_check = tk.Checkbutton(self.settings_window,text="Check String Values When Stripping Comments",variable=self.comment_check_string,command=self.check_string_command)
        self.expand_check.grid(row=1,column=0,columnspan=2,sticky="w",padx=10)
        self.xcode_check.grid(row=2,column=0,columnspan=2,sticky="w",padx=10)
        self.sort_check.grid(row=3,column=0,columnspan=2,sticky="w",padx=10)
        self.ignore_case_check.grid(row=4,column=0,columnspan=2,sticky="w",padx=10)
        self.check_string_check.grid(row=5,column=0,columnspan=2,sticky="w",padx=10)
        comment_prefix_label = tk.Label(self.settings_window,text="Comment Prefix (default is #):")
        comment_prefix_label.grid(row=6,column=0,sticky="w",padx=10)
        self.comment_prefix_text = tk.Entry(self.settings_window)
        self.comment_prefix_text.grid(row=6,column=1,sticky="we",padx=10)
        self.plist_type_string = tk.StringVar(self.settings_window)
        self.plist_type_menu = tk.OptionMenu(self.settings_window, self.plist_type_string, "XML","Binary", command=self.change_plist_type)
        plist_label = tk.Label(self.settings_window,text="Default New Plist Type:")
        plist_label.grid(row=7,column=0,sticky="w",padx=10)
        self.plist_type_menu.grid(row=7,column=1,sticky="we",padx=10)
        self.data_type_string = tk.StringVar(self.settings_window)
        self.data_type_menu = tk.OptionMenu(self.settings_window, self.data_type_string, "Hex","Base64", command=self.change_data_type)
        data_label = tk.Label(self.settings_window,text="Data Display Default:")
        data_label.grid(row=8,column=0,sticky="w",padx=10)
        self.data_type_menu.grid(row=8,column=1,sticky="we",padx=10)
        self.int_type_string = tk.StringVar(self.settings_window)
        self.int_type_menu = tk.OptionMenu(self.settings_window, self.int_type_string, "Decimal", "Hex", command=self.change_int_type)
        int_label = tk.Label(self.settings_window,text="Integer Display Default:")
        int_label.grid(row=9,column=0,sticky="w",padx=10)
        self.int_type_menu.grid(row=9,column=1,sticky="we",padx=10)
        self.bool_type_string = tk.StringVar(self.settings_window)
        self.bool_type_menu = tk.OptionMenu(self.settings_window, self.bool_type_string, "True/False", "YES/NO", "On/Off", "1/0", u"\u2714/\u274c", command=self.change_bool_type)
        bool_label = tk.Label(self.settings_window,text="Boolean Display Default:")
        bool_label.grid(row=10,column=0,sticky="w",padx=10)
        self.bool_type_menu.grid(row=10,column=1,sticky="we",padx=10)
        self.snapshot_string = tk.StringVar(self.settings_window)
        self.snapshot_menu = tk.OptionMenu(self.settings_window, self.snapshot_string, "Auto-detect", command=self.change_snapshot_version)
        snapshot_label = tk.Label(self.settings_window,text="OC Snapshot Target Version:")
        snapshot_label.grid(row=11,column=0,sticky="w",padx=10)
        self.snapshot_menu.grid(row=11,column=1,sticky="we",padx=10)
        self.schema_check = tk.Checkbutton(self.settings_window,text="Force Update Snapshot Schema",variable=self.force_schema,command=self.schema_command)
        self.schema_check.grid(row=12,column=0,columnspan=2,sticky="w",padx=10)
        self.drag_label = tk.Label(self.settings_window,text="Drag Dead Zone (1-100 pixels):")
        self.drag_label.grid(row=13,column=0,sticky="w",padx=10)
        self.drag_scale = tk.Scale(self.settings_window,from_=1,to=100,orient=tk.HORIZONTAL)
        self.drag_scale.grid(row=13,column=1,sticky="we",padx=10)
        undo_max_label = tk.Label(self.settings_window,text="Max Undo (0=unlim, {}=default):".format(self.max_undo))
        undo_max_label.grid(row=14,column=0,sticky="w",padx=10)
        self.undo_max_text = tk.Entry(self.settings_window)
        self.undo_max_text.grid(row=14,column=1,sticky="we",padx=10)
        
        # Left/right separator:
        sep = ttk.Separator(self.settings_window,orient="vertical")
        sep.grid(row=1,column=2,rowspan=13,sticky="ns",padx=10)

        # Right side - theme elements:
        t_func = ttk.Separator(self.settings_window,orient="horizontal")
        t_func.grid(row=0,column=4,columnspan=1,sticky="we",padx=10,pady=10)
        tfunc_label = tk.Label(self.settings_window,text="Appearance Options:")
        tfunc_label.grid(row=0,column=3,sticky="w",padx=10,pady=10)

        self.op_label = tk.Label(self.settings_window,text="Window Opacity (25-100%):")
        self.op_label.grid(row=1,column=3,sticky="w",padx=10)
        self.op_scale = tk.Scale(self.settings_window,from_=25,to=100,orient=tk.HORIZONTAL,command=self.update_opacity)
        self.op_scale.grid(row=1,column=4,sticky="we",padx=10)
        r4_label = tk.Label(self.settings_window,text="Highlight Color:")
        r4_label.grid(row=2,column=3,sticky="w",padx=10)
        self.hl_canvas = tk.Canvas(self.settings_window, height=20, width=30, background="black", relief="groove", bd=2)
        self.hl_canvas.grid(row=2,column=4,sticky="we",padx=10)
        r1_label = tk.Label(self.settings_window,text="Alternating Row Color #1:")
        r1_label.grid(row=3,column=3,sticky="w",padx=10)
        self.r1_canvas = tk.Canvas(self.settings_window, height=20, width=30, background="black", relief="groove", bd=2)
        self.r1_canvas.grid(row=3,column=4,sticky="we",padx=10)
        r2_label = tk.Label(self.settings_window,text="Alternating Row Color #2:")
        r2_label.grid(row=4,column=3,sticky="w",padx=10)
        self.r2_canvas = tk.Canvas(self.settings_window, height=20, width=30, background="black", relief="groove", bd=2)
        self.r2_canvas.grid(row=4,column=4,sticky="we",padx=10)
        r3_label = tk.Label(self.settings_window,text="Column Header/BG Color:")
        r3_label.grid(row=5,column=3,sticky="w",padx=10)
        self.bg_canvas = tk.Canvas(self.settings_window, height=20, width=30, background="black", relief="groove", bd=2)
        self.bg_canvas.grid(row=5,column=4,sticky="we",padx=10)
        self.ig_bg_check = tk.IntVar()
        self.ig_bg = tk.Checkbutton(self.settings_window,text="Header Text Ignores BG Color",variable=self.ig_bg_check,command=self.check_ig_bg_command)
        self.ig_bg.grid(row=6,column=3,sticky="w",padx=10)
        self.bg_inv_check = tk.IntVar()
        self.bg_inv = tk.Checkbutton(self.settings_window,text="Invert Header Text Color",variable=self.bg_inv_check,command=self.check_bg_invert_command)
        self.bg_inv.grid(row=6,column=4,sticky="w",padx=10)
        self.r1_inv_check = tk.IntVar()
        self.r1_inv = tk.Checkbutton(self.settings_window,text="Invert Row #1 Text Color",variable=self.r1_inv_check,command=self.check_r1_invert_command)
        self.r1_inv.grid(row=7,column=4,sticky="w",padx=10)
        self.r2_inv_check = tk.IntVar()
        self.r2_inv = tk.Checkbutton(self.settings_window,text="Invert Row #2 Text Color",variable=self.r2_inv_check,command=self.check_r2_invert_command)
        self.r2_inv.grid(row=8,column=4,sticky="w",padx=10)
        self.hl_inv_check = tk.IntVar()
        self.hl_inv = tk.Checkbutton(self.settings_window,text="Invert Highlight Text Color",variable=self.hl_inv_check,command=self.check_hl_invert_command)
        self.hl_inv.grid(row=9,column=4,sticky="w",padx=10)

        self.default_font = Font(font='TkTextFont')
        self.custom_font = tk.IntVar()
        self.font_check = tk.Checkbutton(self.settings_window,text="Use Custom Font Size",variable=self.custom_font,command=self.font_command)
        self.font_string = tk.StringVar()
        self.font_spinbox = tk.Spinbox(self.settings_window,from_=1,to=128,textvariable=self.font_string)
        self.font_string.trace("w",self.update_font)
        self.font_check.grid(row=10,column=3,sticky="w",padx=10)
        self.font_spinbox.grid(row=10,column=4,sticky="we",padx=10)

        # Custom font picker - wacky implementation.
        self.font_var = tk.IntVar()
        self.font_family  = tk.StringVar()
        self.font_custom_check = tk.Checkbutton(self.settings_window,text="Use Custom Font",variable=self.font_var,command=self.font_select)
        self.font_custom = ttk.Combobox(self.settings_window,state="readonly",textvariable=self.font_family,values=sorted(families()))
        self.font_custom.bind('<<ComboboxSelected>>',self.font_pick)
        self.font_family.trace("w",self.update_font_family)
        self.font_custom_check.grid(row=11,column=3,stick="w",padx=10)
        self.font_custom.grid(row=11,column=4,sticky="we",padx=10)

        r5_label = tk.Label(self.settings_window,text="Restore Appearance Defaults:")
        r5_label.grid(row=12,column=3,sticky="w",padx=10)
        dt_func = ttk.Separator(self.settings_window,orient="horizontal")
        dt_func.grid(row=12,column=4,columnspan=1,sticky="we",padx=10)

        default_font = tk.Button(self.settings_window,text="Font Defaults",command=self.font_defaults)
        default_font.grid(row=13,column=3,sticky="we",padx=10)
        default_high = tk.Button(self.settings_window,text="Highlight Color",command=lambda:self.swap_colors("highlight"))
        default_high.grid(row=14,column=3,sticky="we",padx=10)
        default_light = tk.Button(self.settings_window,text="Light Mode Colors",command=lambda:self.swap_colors("light"))
        default_light.grid(row=13,column=4,sticky="we",padx=10)
        default_dark = tk.Button(self.settings_window,text="Dark Mode Colors",command=lambda:self.swap_colors("dark"))
        default_dark.grid(row=14,column=4,sticky="we",padx=10)

        sep_theme = ttk.Separator(self.settings_window,orient="horizontal")
        sep_theme.grid(row=15,column=0,columnspan=5,sticky="we",padx=10,pady=(10,0))

        # Add the check for updates checkbox and button
        self.update_int = tk.IntVar()
        self.update_check = tk.Checkbutton(self.settings_window,text="Check For Updates At Start",variable=self.update_int,command=self.update_command)
        self.update_check.grid(row=16,column=0,sticky="w",padx=10,pady=(5,0))
        self.notify_once_int = tk.IntVar()
        self.notify_once_check = tk.Checkbutton(self.settings_window,text="Only Notify Once Per Version",variable=self.notify_once_int,command=self.notify_once)
        self.notify_once_check.grid(row=17,column=0,sticky="w",padx=10,pady=(0,10))
        self.update_button = tk.Button(self.settings_window,text="Check Now",command=lambda:self.check_for_updates(user_initiated=True))
        self.update_button.grid(row=17,column=1,sticky="w",padx=10,pady=(0,10))
        reset_settings = tk.Button(self.settings_window,text="Restore All Defaults",command=self.reset_settings)
        reset_settings.grid(row=17,column=4,sticky="we",padx=10,pady=(0,10))

        # Setup the color picker click methods
        self.r1_canvas.bind("<ButtonRelease-1>",lambda x:self.pick_color("alternating_color_1",self.r1_canvas))
        self.r2_canvas.bind("<ButtonRelease-1>",lambda x:self.pick_color("alternating_color_2",self.r2_canvas))
        self.hl_canvas.bind("<ButtonRelease-1>",lambda x:self.pick_color("highlight_color",self.hl_canvas))
        self.bg_canvas.bind("<ButtonRelease-1>",lambda x:self.pick_color("background_color",self.bg_canvas))

        # Setup some canvas connections
        self.canvas_connect = {
            self.bg_canvas: {"invert":self.bg_inv_check},
            self.r1_canvas: {"invert":self.r1_inv_check},
            self.r2_canvas: {"invert":self.r2_inv_check},
            self.hl_canvas: {"invert":self.hl_inv_check}
        }
        
        self.default_dark  = {
            "alternating_color_1":"#161616",
            "alternating_color_2":"#202020",
            "highlight_color":"#1E90FF",
            "background_color":"#161616",
            "invert_background_text_color":False,
            "invert_row1_text_color":False,
            "invert_row2_text_color":False
        }
        self.default_light = {
            "alternating_color_1":"#F0F1F1",
            "alternating_color_2":"#FEFEFE",
            "highlight_color":"#1E90FF",
            "background_color":"#FEFEFE",
            "invert_background_text_color":False,
            "invert_row1_text_color":False,
            "invert_row2_text_color":False
        }

        # Setup the from/to option menus
        self.f_title = tk.StringVar(self.tk)
        self.t_title = tk.StringVar(self.tk)
        f_option = tk.OptionMenu(self.tk, self.f_title, "Ascii", "Base64", "Decimal", "Hex", command=self.change_from_type)
        t_option = tk.OptionMenu(self.tk, self.t_title, "Ascii", "Base64", "Decimal", "Hex", command=self.change_to_type)
        f_option.grid(row=0,column=1,sticky="we")
        t_option.grid(row=1,column=1,sticky="we")

        self.f_text = tk.Entry(self.tk)
        self.f_text.delete(0,tk.END)
        self.f_text.insert(0,"")
        self.f_text.grid(row=0,column=2,columnspan=2,sticky="we",padx=10,pady=10)

        self.t_text = tk.Entry(self.tk)
        self.t_text.configure(state='normal')
        self.t_text.delete(0,tk.END)
        self.t_text.insert(0,"")
        self.t_text.configure(state='readonly')
        self.t_text.grid(row=1,column=2,columnspan=2,sticky="we",padx=10,pady=10)

        self.c_button = tk.Button(self.tk, text="Convert", command=self.convert_values)
        self.c_button.grid(row=2,column=3,sticky="e",padx=10,pady=10)
        self.s_button = tk.Button(self.tk, text="To <--> From", command=self.swap_convert)
        self.s_button.grid(row=2,column=0,sticky="w",padx=10,pady=10)

        self.f_text.bind("<Return>", self.convert_values)
        self.f_text.bind("<KP_Enter>", self.convert_values)

        self.start_window = None

        # Regex to find the processor serial numbers when
        # opened from the Finder
        self.regexp = re.compile(r"^-psn_[0-9]+_[0-9]+$")

        # Setup the menu-related keybinds - and change the app name if needed
        key="Control"
        sign = "Ctrl+"
        self.use_dark = self.get_dark()
        if str(sys.platform) == "darwin":
            # Remap the quit function to our own
            self.tk.createcommand('::tk::mac::Quit', self.quit)
            self.tk.createcommand("::tk::mac::OpenDocument", self.open_plist_from_app)
            self.tk.createcommand("::tk::mac::ShowPreferences", lambda:self.show_window(self.settings_window))
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

        self.tk.protocol("WM_DELETE_WINDOW", lambda x=self.tk: self.close_window(window=x))
        self.settings_window.protocol("WM_DELETE_WINDOW", lambda x=self.settings_window: self.close_window(window=x))

        self.default_windows = (self.tk,self.settings_window)

        self.recent_menu = None
        if str(sys.platform) == "darwin":
            # Setup the top level menu
            file_menu = tk.Menu(self.tk)
            main_menu = tk.Menu(self.tk)
            self.recent_menu = tk.Menu(self.tk)
            main_menu.add_cascade(label="File", menu=file_menu)
            file_menu.add_command(label="New (Cmd+N)", command=self.new_plist)
            file_menu.add_command(label="Open (Cmd+O)", command=self.open_plist)
            file_menu.add_cascade(label="Open Recent", menu=self.recent_menu, command=self.open_recent)
            file_menu.add_command(label="Save (Cmd+S)", command=self.save_plist)
            file_menu.add_command(label="Save As... (Cmd+Shift+S)", command=self.save_plist_as)
            file_menu.add_command(label="Duplicate (Cmd+D)", command=self.duplicate_plist)
            file_menu.add_command(label="Reload From Disk (Cmd+L)", command=self.reload_from_disk)
            file_menu.add_separator()
            file_menu.add_command(label="OC Snapshot (Cmd+R)", command=self.oc_snapshot)
            file_menu.add_command(label="OC Clean Snapshot (Cmd+Shift+R)", command=self.oc_clean_snapshot)
            file_menu.add_separator()
            file_menu.add_command(label="Convert Window (Cmd+T)", command=lambda:self.show_window(self.tk))
            file_menu.add_command(label="Strip Comments (Cmd+M)", command=self.strip_comments)
            file_menu.add_command(label="Strip Disabled Entries (Cmd+E)", command=self.strip_disabled)
            file_menu.add_separator()
            file_menu.add_command(label="Settings (Cmd+,)",command=lambda:self.show_window(self.settings_window))
            file_menu.add_separator()
            file_menu.add_command(label="Toggle Find/Replace Pane (Cmd+F)",command=self.hide_show_find)
            file_menu.add_command(label="Toggle Plist/Data/Int Type Pane (Cmd+P)",command=self.hide_show_type)
            file_menu.add_separator()
            file_menu.add_command(label="Quit (Cmd+Q)", command=self.quit)
            self.tk.config(menu=main_menu)

        # Set bindings
        # on at least macOS, tk 8.5 works with <Command-Z>, but 8.6 requires <Shift-Command-z>
        # Can be bypassed by including both Shift and the capital letter
        self.tk.bind("<{}-w>".format(key), self.close_window)
        self.settings_window.bind("<{}-w>".format(key), self.close_window)
        self.tk.bind_all("<{}-n>".format(key), self.new_plist)
        self.tk.bind_all("<{}-o>".format(key), self.open_plist)
        self.tk.bind_all("<{}-s>".format(key), self.save_plist)
        self.tk.bind_all("<{}-Shift-S>".format(key), self.save_plist_as)
        self.tk.bind_all("<{}-d>".format(key), self.duplicate_plist)
        self.tk.bind_all("<{}-t>".format(key), lambda event, x=self.tk: self.show_window(x))
        self.tk.bind_all("<{}-z>".format(key), self.undo)
        self.tk.bind_all("<{}-Shift-Z>".format(key), self.redo)
        self.tk.bind_all("<{}-m>".format(key), self.strip_comments)
        self.tk.bind_all("<{}-e>".format(key), self.strip_disabled)
        self.tk.bind_all("<{}-r>".format(key), self.oc_snapshot)
        self.tk.bind_all("<{}-Shift-R>".format(key), self.oc_clean_snapshot)
        self.tk.bind_all("<{}-l>".format(key), self.reload_from_disk)
        if not str(sys.platform) == "darwin":
            # Rewrite the default Command-Q command
            self.tk.bind_all("<{}-q>".format(key), self.quit)
            self.tk.bind_all("<{}-comma>".format(key), lambda event, x=self.settings_window:self.show_window(x))
        
        cwd = os.getcwd()
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
        #
        # Load the settings - current available settings are:
        # 
        # last_window_width:            width value (default is 640)
        # last_window_height:           height value (default is 480)
        # expand_all_items_on_open:     bool
        # sort_dict:                    bool, false = OrderedDict
        # xcode_data:                   bool, true = <data>XXXX</data>, false = different lines
        # comment_strip_prefix:         string, defaults to #
        # comment_strip_ignore_case:    bool, true = ignore case when stripping comments
        # comment_strip_check_string:   bool, true = consider string values as well as keys
        # new_plist_default_type:       string, XML/Binary
        # display_data_as:              string, Hex/Base64
        # display_int_as:               string, Decimal/Hex
        # snapshot_version:             string, X.X.X version number, or Latest
        # force_snapshot_schema:        bool
        # alternating_color_1:          string, Dark: #161616 - Light: #F0F1F1
        # alternating_color_2:          string, Dark: #202020 - Light: #FEFEFE
        # highlight_color:              string, Dark: #1E90FF - Light: #1E90FF
        # background_color:             string, Dark: #161616 - Light: #FEFEFE
        # header_text_ignore_bg_color:  bool
        # invert_background_text_color: bool
        # invert_row1_text_color:       bool
        # invert_row2_text_color:       bool
        # invert_hl_text_color:         bool
        # drag_dead_zone:               pixel distance before drag starts (default is 20)
        # open_recent:                  list, paths recently opened
        # recent_max:                   int, max number of recent items
        # max_undo:                     int, max undo history - 0 = unlimited
        # check_for_updates_at_startup: bool
        # notify_once_per_version:      bool
        # last_version_checked:         str
        # opacity                       int, 10-100 (default is 100)
        #

        self.settings = {}
        if os.path.exists("Scripts/settings.json"):
            try:
                self.settings = json.load(open("Scripts/settings.json"))
            except:
                pass
        # Also load the snapshot defaults
        self.snapshot_data = {}
        if os.path.exists("Scripts/snapshot.plist"):
            try:
                with open("Scripts/snapshot.plist","rb") as f:
                    self.snapshot_data = plist.load(f)
            except:
                pass
        # And finally, load the version.json if it exists
        self.version = {}
        if os.path.exists("Scripts/version.json"):
            try: self.version = json.load(open("Scripts/version.json"))
            except: pass
        os.chdir(cwd)

        # Apply the version to the update button text
        self.update_button.configure(text="Check Now ({})".format(self.version.get("version","?.?.?")))

        # Setup the settings page to reflect our settings.json file

        self.allowed_types = ("XML","Binary")
        self.allowed_data  = ("Hex","Base64")
        self.allowed_int   = ("Decimal","Hex")
        self.allowed_bool  = ("True/False","YES/NO","On/Off","1/0",u"\u2714/\u274c")
        self.allowed_conv  = ("Ascii","Base64","Decimal","Hex")
        self.update_settings()

        self.case_insensitive = self.get_case_insensitive()
        # Normalize the pathing for Open Recents
        self.normpath_recents()
        if str(sys.platform) == "darwin": self.update_recents()
        self.check_dark_mode()

        self.version_url = "https://raw.githubusercontent.com/corpnewt/ProperTree/master/Scripts/version.json"
        self.repo_url = "https://github.com/corpnewt/ProperTree"

        # Implement a simple boolean lock, and check for updates if needed
        self.is_checking_for_updates = False
        if self.settings.get("check_for_updates_at_startup",True):
            self.tk.after(0, lambda:self.check_for_updates(user_initiated=False))

        # Prior implementations tried to wait 250ms to give open_plist_from_app()
        # enough time to parse anything double-clicked.  The issue was that both
        # check_open() and open_plist_from_app() would fire at roughly the same
        # time - resulting in one opening a blank doc, and the other opening the
        # double-clicked plist(s).  We now use the is_opening lock to determine
        # if one function is currently working - and the other will check in 5ms
        # intervals until the lock is lifted before processing.  This allows us
        # to overtake a blank doc opened by one with the other - hopefully fixing
        # the issue of multiple documents spawning on double-click in macOS.
        self.is_opening = False
        self.is_quitting = False
        self.check_open(plists)
        
        # Set up a signal handler for SIGINT that pipes to our quit() function
        signal.signal(signal.SIGINT,self.quit)
        # Set up our event loop "poker" to keep the event loop processing
        self.tk.after(200,self.sigint_check)

        # Start our run loop
        tk.mainloop()

    def sigint_check(self):
        # Helper to keep the event loop moving in order to ensure we can catch
        # KeyboardInterrupts as needed
        self.tk.after(200,self.sigint_check)

    def get_case_insensitive(self):
        # Helper function to check our file path, change case, and see if os.path.exists() still works
        our_path = os.path.abspath(__file__)
        # Walk our chars and find the first alpha character
        # then reverse it's case - and see if the path still exists
        for i,x in enumerate(our_path):
            if x.isalpha():
                x = x.upper() if x.islower() else x.lower()
                return os.path.exists(our_path[:i]+x+our_path[i+1:])
        # If we got here - there were no alpha chars in the path - we'll just uh... return False to be safe
        return False

    def check_dark_mode(self):
        check_dark = self.get_dark()
        if check_dark != self.use_dark and any((x not in self.settings for x in ("alternating_color_1","alternating_color_2","background_color"))):
            # Mode changed
            self.use_dark = check_dark
            self.update_settings()
        # Continue the loop
        self.tk.after(10000, lambda:self.check_dark_mode())

    def should_set_header_text(self):
        # In macOS, the header colors are only affected by the background
        # when in dark mode on specific python build
        # We'll try to get the system's actual dark mode here
        if str(sys.platform) != "darwin": return True # Don't make changes on Windows/Linux
        try:
            # Ask the window if it's in dark mode - only works when supported
            return bool(self.tk.call("tk::unsupported::MacWindowStyle","isdark",self.tk))
        except Exception as e:
            return False # If this fails, window doesn't support dark mode

    def get_dark(self):
        if os.name=="nt":
            # Get the registry entry to tell us if we're in dark/light mode
            p = subprocess.Popen(["reg","query","HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize","/v","AppsUseLightTheme"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            c = p.communicate()
            return c[0].decode("utf-8", "ignore").strip().lower().split(" ")[-1] in ("","0x0")
        elif str(sys.platform) != "darwin":
            return True # Default to dark mode on Linux platforms
        # Get the macOS version - and see if dark mode is a thing
        p = subprocess.Popen(["sw_vers","-productVersion"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        c = p.communicate()
        p_vers = c[0].decode("utf-8", "ignore").strip().lower()
        if p_vers < "10.14.0": return True # Default to dark on anything prior to 
        # At this point - we have an OS that supports dark mode, let's check our value
        p = subprocess.Popen(["defaults","read","-g","AppleInterfaceStyle"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        c = p.communicate()
        return c[0].decode("utf-8", "ignore").strip().lower() == "dark"

    def compare_version(self, v1, v2):
        # Splits the version numbers by periods and compare each value
        # Allows 0.0.10 > 0.0.9 where normal string comparison would return false
        # Also strips out any non-numeric values from each segment to avoid conflicts
        #
        # Returns True if v1 > v2, None if v1 == v2, and False if v1 < v2
        if not all((isinstance(x,str) for x in (v1,v2))):
            # Wrong types
            return False
        v1_seg = v1.split(".")
        v2_seg = v2.split(".")
        # Pad with 0s to ensure common length
        v1_seg += ["0"]*(len(v2_seg)-len(v1_seg))
        v2_seg += ["0"]*(len(v1_seg)-len(v2_seg))
        # Compare each segment - stripping non-numbers as needed
        for i in range(len(v1_seg)):
            a,b = v1_seg[i],v2_seg[i]
            try: a = int("".join([x for x in a if x.isdigit()]))
            except: a = 0
            try: b = int("".join([x for x in b if x.isdigit()]))
            except: b = 0
            if a > b: return True
            if a < b: return False
        # If we're here, both versions are the same
        return None

    def check_for_updates(self, user_initiated = False):
        if self.is_checking_for_updates: # Already checking
            if user_initiated:
                # We pressed the button - but another check is in progress
                self.tk.bell()
                mb.showerror("Already Checking For Updates","An update check is already in progress.  If you consistently get this error when manually checking for updates - it may indicate a netowrk issue.")
            return
        self.is_checking_for_updates = True # Lock out other update checks
        self.update_button.configure(
            state="disabled",
            text="Checking... ({})".format(self.version.get("version","?.?.?"))
        )
        # We'll leverage multiprocessing to avoid UI locks if the update checks take too long
        p = multiprocessing.Process(target=_check_for_update,args=(self.queue,self.version_url,user_initiated))
        p.daemon = True
        p.start()
        self.check_update_process(p)

    def reset_update_button(self):
        self.update_button.configure(
            state="normal",
            text="Check Now ({})".format(self.version.get("version","?.?.?"))
        )

    def check_update_process(self, p):
        # Helper to watch until an update is done
        if p.is_alive():
            self.tk.after(100,self.check_update_process,p)
            return
        # We've returned - reset our bool lock
        self.is_checking_for_updates = False
        # Check if we got anything from the queue
        if self.queue.empty(): # Nothing in the queue, bail
            return self.reset_update_button()
        # Retrieve any returned value and parse
        output_dict = self.queue.get()
        user_initiated = output_dict.get("user_initiated",False)
        # Check if we got an error or exception
        if "exception" in output_dict or "error" in output_dict:
            error = output_dict.get("error","An Error Occurred Checking For Updates")
            excep = output_dict.get("exception","Something went wrong when checking for updates.")
            if user_initiated:
                self.tk.bell()
                mb.showerror(error,excep)
            return self.reset_update_button()
        # Parse the output returned
        version_dict = output_dict.get("json",{})
        if not version_dict.get("version"):
            if user_initiated:
                self.tk.bell()
                mb.showerror("An Error Occurred Checking For Updates","Data returned was malformed or nonexistent.")
            return self.reset_update_button()
        # At this point - we should have json data containing the version key/value
        check_version = str(version_dict["version"]).lower()
        our_version   = str(self.version.get("version","0.0.0")).lower()
        notify_once   = self.settings.get("notify_once_per_version",True)
        last_version  = str(self.settings.get("last_version_checked","0.0.0")).lower()
        if self.compare_version(check_version,our_version) is True:
            if notify_once and last_version == check_version and not user_initiated:
                # Already notified about this version - ignore
                return self.reset_update_button()
            # Save the last version checked
            self.settings["last_version_checked"] = check_version
            # We got an update we're not ignoring - let's prompt
            self.tk.bell()
            result = mb.askyesno(
                title="New ProperTree Version Available",
                message="Version {} is available (currently on {}).\n\nWhat's new in {}:\n{}\n\nVisit ProperTree's github repo now?".format(
                    check_version,
                    our_version,
                    check_version,
                    version_dict.get("changes","No changes listed.")
                )
            )
            if result: # Open the url in the default browser
                webbrowser.open(self.repo_url)

        elif user_initiated:
            # No new updates - but we need to tell the user
            mb.showinfo(
                title="No Updates Available",
                message="You are currently running the latest version of ProperTree ({}).".format(our_version)
            )
        self.reset_update_button()
        # If we got here - we displayed some message, let's lift our window to the top
        windows = self.stackorder(self.tk,include_defaults=True)
        if not len(windows): return
        self.lift_window(windows[-1])

    def text_color(self, hex_color, invert = False):
        hex_color = hex_color.lower()
        if hex_color.startswith("0x"): hex_color = hex_color[2:]
        if hex_color.startswith("#"): hex_color = hex_color[1:]
        # Check for bogus hex and return "black" by default
        if len(hex_color) != 6 or not all((x in "0123456789abcdef" for x in hex_color)):
            return "white" if invert else "black"
        # Get the r, g, and b values and determine our fake luminance
        r = float(int(hex_color[0:2],16))
        g = float(int(hex_color[2:4],16))
        b = float(int(hex_color[4:6],16))
        l = (r*0.299 + g*0.587 + b*0.114) > 186
        if l: return "white" if invert else "black"
        return "black" if invert else "white"

    def set_window_opacity(self, opacity=None, window=None):
        if opacity is None:
            try: opacity = min(100,max(int(self.settings.get("opacity",100)),25))
            except: opacity = 100 # failsafe
        windows = (window,) if window else self.stackorder(self.tk,include_defaults=True)
        for window in self.stackorder(self.tk,include_defaults=True):
            window.attributes("-alpha",float(opacity)/float(100))

    def update_opacity(self, event = None):
        self.settings["opacity"] = self.op_scale.get()
        self.set_window_opacity(self.settings["opacity"])

    def expand_command(self, event = None):
        self.settings["expand_all_items_on_open"] = True if self.expand_on_open.get() else False

    def xcode_command(self, event = None):
        self.settings["xcode_data"] = True if self.use_xcode_data.get() else False

    def sort_command(self, event = None):
        self.settings["sort_dict"] = True if self.sort_dict_keys.get() else False

    def ignore_case_command(self, event = None):
        self.settings["comment_strip_ignore_case"] = True if self.comment_ignore_case.get() else False

    def check_string_command(self, event = None):
        self.settings["comment_strip_check_string"] = True if self.comment_check_string.get() else False

    def check_ig_bg_command(self, event = None):
        self.settings["header_text_ignore_bg_color"] = True if self.ig_bg_check.get() else False
        self.update_colors()

    def check_bg_invert_command(self, event = None):
        self.settings["invert_background_text_color"] = True if self.bg_inv_check.get() else False
        self.update_colors()

    def check_r1_invert_command(self, event = None):
        self.settings["invert_row1_text_color"] = True if self.r1_inv_check.get() else False
        self.update_colors()

    def check_r2_invert_command(self, event = None):
        self.settings["invert_row2_text_color"] = True if self.r2_inv_check.get() else False
        self.update_colors()

    def check_hl_invert_command(self, event = None):
        self.settings["invert_hl_text_color"] = True if self.hl_inv_check.get() else False
        self.update_colors()

    def schema_command(self, event = None):
        self.settings["force_snapshot_schema"] = True if self.force_schema.get() else False

    def update_command(self, event = None):
        self.settings["check_for_updates_at_startup"] = True if self.update_int.get() else False
        self.update_notify()

    def notify_once(self, event = None):
        self.settings["notify_once_per_version"] = True if self.notify_once_int.get() else False

    def update_notify(self):
        self.notify_once_check.configure(state="normal" if self.update_int.get() else "disabled")

    def change_plist_type(self, event = None):
        self.settings["new_plist_default_type"] = self.plist_type_string.get()

    def change_data_type(self, event = None):
        self.settings["display_data_as"] = self.data_type_string.get()

    def change_int_type(self, event = None):
        self.settings["display_int_as"] = self.int_type_string.get()

    def change_bool_type(self, event = None):
        self.settings["display_bool_as"] = self.bool_type_string.get()

    def change_snapshot_version(self, event = None):
        self.settings["snapshot_version"] = self.snapshot_string.get().split(" ")[0]

    def font_command(self, event = None):
        if self.custom_font.get():
            self.settings["use_custom_font_size"] = True
            self.font_spinbox.configure(state="normal")
        else:
            self.settings["use_custom_font_size"] = False
            self.font_spinbox.configure(state="disabled")
            # self.font_string.set(self.default_font["size"])
            self.settings.pop("font_size",None)
        self.update_font()

    def font_select(self, event = None):
        if self.font_var.get():
            self.settings["use_custom_font"] = True
            self.settings["font_family"] = self.font_family.get()
            self.font_custom.configure(state='readonly')
        else:
            self.settings["use_custom_font"] = False
            self.font_custom.configure(state='disabled')
            self.settings.pop("font_family",None)
        self.update_font_family()

    def font_pick(self, event = None):
        font_family = self.font_family.get()
        if self.settings["font_family"] == font_family:
            return
        self.settings["font_family"] = font_family
        self.update_font_family()

    def update_font(self, var = None, blank = None, trace_mode = None):
        try: font_size = int(self.font_string.get())
        except: return
        self.settings["font_size"] = font_size
        self.update_fonts()

    def update_font_family(self, event = None, blank = None, trace_mode = None):
        windows = self.stackorder(self.tk)
        if not len(windows): return
        for window in windows:
            if window in self.default_windows: continue
            window.set_font_family()

    def font_defaults(self, event = None):
        self.settings["use_custom_font"] = False
        self.settings.pop("font_family",None)
        self.settings["use_custom_font_size"] = False
        self.settings.pop("font_size",None)
        self.update_settings()

    def pick_color(self, color_name = None, canvas = None):
        if not color_name or not canvas: return # uh wut?
        _,color = ac(color=canvas["background"])
        if not color: return # User bailed
        self.settings[color_name] = color
        canvas.configure(background=color)
        self.update_colors()

    def swap_colors(self, color_type = None):
        if not isinstance(color_type,str): return
        color_type = color_type.lower()
        if color_type == "highlight":
            self.settings.pop("highlight_color",None)
            self.settings.pop("invert_hl_text_color",None)
            return self.update_settings()
        # Find out if we're setting it to light or dark mode - and if on macOS/Windows + using the system's current settings,
        # remove them to use defaults
        self.use_dark = self.get_dark()
        color_dict = self.default_light if color_type == "light" else self.default_dark
        to_remove = (self.use_dark and color_type == "dark") or (not self.use_dark and color_type != "dark")
        for x in color_dict:
            if color_type != "highlight" and x.lower() == "highlight_color": continue
            if to_remove: self.settings.pop(x,None)
            else: self.settings[x] = color_dict[x]
        self.update_settings()

    def reset_settings(self, event = None):
        self.settings = {}
        self.update_settings()

    def update_settings(self):
        self.expand_on_open.set(self.settings.get("expand_all_items_on_open",True))
        self.use_xcode_data.set(self.settings.get("xcode_data",True))
        self.sort_dict_keys.set(self.settings.get("sort_dict",False))
        def_type = self.settings.get("new_plist_default_type",self.allowed_types[0])
        self.plist_type_string.set(def_type if def_type in self.allowed_types else self.allowed_types[0])
        dat_type = self.settings.get("display_data_as",self.allowed_data[0])
        self.data_type_string.set(dat_type if dat_type in self.allowed_data else self.allowed_data[0])
        int_type = self.settings.get("display_int_as",self.allowed_int[0])
        self.int_type_string.set(int_type if int_type in self.allowed_int else self.allowed_int[0])
        bool_type = self.settings.get("display_bool_as",self.allowed_bool[0])
        self.bool_type_string.set(bool_type if bool_type in self.allowed_bool else self.allowed_bool[0])
        conv_f_type = self.settings.get("convert_from_type",self.allowed_conv[1])
        self.f_title.set(conv_f_type if conv_f_type in self.allowed_conv else self.allowed_conv[1])
        conv_t_type = self.settings.get("convert_to_type",self.allowed_conv[-1])
        self.t_title.set(conv_t_type if conv_t_type in self.allowed_conv else self.allowed_conv[-1])
        self.snapshot_menu["menu"].delete(0,"end")
        snapshot_versions = ["{} -> {}".format(x["min_version"],x.get("max_version","Current")) if x["min_version"]!=x.get("max_version","Current") else x["min_version"] for x in self.snapshot_data if "min_version" in x and len(x["min_version"])]
        snapshot_choices = ["Auto-detect","Latest"] + sorted(snapshot_versions,reverse=True)
        for choice in snapshot_choices:
            self.snapshot_menu["menu"].add_command(label=choice,command=tk._setit(self.snapshot_string,choice,self.change_snapshot_version))
        snapshot_vers = self.settings.get("snapshot_version","Auto-detect")
        snapshot_name = next((x for x in snapshot_choices if x.split(" ")[0] == snapshot_vers))
        self.snapshot_string.set(snapshot_name if snapshot_name in snapshot_choices else "Auto-detect")
        self.force_schema.set(self.settings.get("force_snapshot_schema",False))
        self.comment_ignore_case.set(self.settings.get("comment_strip_ignore_case",False))
        self.comment_check_string.set(self.settings.get("comment_strip_check_string",True))
        self.update_int.set(self.settings.get("check_for_updates_at_startup",True))
        self.notify_once_int.set(self.settings.get("notify_once_per_version",True))
        self.update_notify()
        self.comment_prefix_text.delete(0,tk.END)
        prefix = self.settings.get("comment_strip_prefix","#")
        prefix = "#" if not prefix else prefix
        self.comment_prefix_text.insert(0,prefix)
        self.undo_max_text.delete(0,tk.END)
        max_undo = self.settings.get("max_undo",self.max_undo)
        max_undo = self.max_undo if not isinstance(max_undo,int) or max_undo < 0 else max_undo
        self.undo_max_text.insert(0,str(max_undo))
        try: opacity = min(100,max(int(self.settings.get("opacity",100)),25))
        except: opacity = 100 # failsafe
        self.op_scale.set(opacity)
        self.set_window_opacity(opacity)
        default_color = self.default_dark if self.use_dark else self.default_light
        color_1 = "".join([x for x in self.settings.get("alternating_color_1",default_color["alternating_color_1"]) if x.lower() in "0123456789abcdef"])
        color_2 = "".join([x for x in self.settings.get("alternating_color_2",default_color["alternating_color_2"]) if x.lower() in "0123456789abcdef"])
        color_h = "".join([x for x in self.settings.get("highlight_color"    ,default_color["highlight_color"    ]) if x.lower() in "0123456789abcdef"])
        color_b = "".join([x for x in self.settings.get("background_color"   ,default_color["background_color"   ]) if x.lower() in "0123456789abcdef"])
        self.r1_canvas.configure(background="#"+color_1 if len(color_1) == 6 else default_color["alternating_color_1"])
        self.r2_canvas.configure(background="#"+color_2 if len(color_2) == 6 else default_color["alternating_color_2"])
        self.hl_canvas.configure(background="#"+color_h if len(color_h) == 6 else default_color["highlight_color"])
        self.bg_canvas.configure(background="#"+color_b if len(color_b) == 6 else default_color["background_color"])
        self.ig_bg_check.set(self.settings.get("header_text_ignore_bg_color",False))
        self.bg_inv_check.set(self.settings.get("invert_background_text_color",False))
        self.r1_inv_check.set(self.settings.get("invert_row1_text_color",False))
        self.r2_inv_check.set(self.settings.get("invert_row2_text_color",False))
        self.hl_inv_check.set(self.settings.get("invert_hl_text_color",False))
        self.drag_scale.set(self.settings.get("drag_dead_zone",20))
        self.font_string.set(self.settings.get("font_size",self.default_font["size"]))
        self.custom_font.set(self.settings.get("use_custom_font_size",False))
        self.font_family.set(self.settings.get("font_family",self.default_font.actual()["family"]))
        self.font_var.set(self.settings.get("use_custom_font",False))
        self.font_command()
        self.font_select()
        self.update_colors()

    def update_canvas_text(self, canvas = None):
        if canvas == None: # Update all
            canvas = (self.bg_canvas,self.r1_canvas,self.r2_canvas,self.hl_canvas)
        if not isinstance(canvas, (tuple,list)): canvas = (canvas,)
        for c in canvas:
            if not c in self.canvas_connect: continue # Not a recognized canvas - skip
            # Update each canvas as needed - but mind the text color
            color = self.text_color(c["background"],self.canvas_connect[c]["invert"].get())
            if self.canvas_connect[c].get("text_id",None) == None: # We haven't drawn it yet - try to
                # Get the size
                w = self.settings_window.winfo_width()
                h = c.winfo_height()
                if w==1==h: # Request width as we haven't drawn yet
                    w = self.settings_window.winfo_reqwidth()
                    h = c.winfo_reqheight()
                    cw = c.winfo_reqwidth()
                    # Not drawn - estimate position and pad for macOS and Win/Linux with best-guess
                    rw = int(w/2) if str(sys.platform)=="darwin" else int(w/2-cw/2)
                else:
                    # It's been drawn, calculate the new way - width of the widget/2 gives us the halfway point
                    cw = c.winfo_width()
                    rw = int(cw/2)
                self.canvas_connect[c]["text_id"] = c.create_text(rw,int(h/2),text="Sample Text")
            # Set the color
            c.itemconfig(self.canvas_connect[c]["text_id"], fill=color)

    def update_fonts(self):
        windows = self.stackorder(self.tk,include_defaults=True)
        if not len(windows): return
        font = Font(family=self.font_family.get()) if self.font_var.get() else Font(font="TkTextFont")
        font["size"] = self.font_string.get() if self.custom_font.get() else self.default_font["size"]
        for window in windows:
            if window in self.default_windows: continue
            form_text = next((x for x in window.winfo_children() if str(x).endswith("!formattedtext")),None)
            if form_text: # We need to manually set the text colors here
                form_text.update_font(font)
            else:
                window.set_font_size()

    def update_colors(self):
        self.update_canvas_text()
        # Update all windows' colors
        windows = self.stackorder(self.tk,include_defaults=True)
        if not len(windows):
            # Nothing to do
            return
        # Get the text colors for the FormattedText widgets as needed
        r1  = self.r1_canvas["background"]
        r1t = self.text_color(r1,invert=self.r1_inv_check.get())
        for window in windows:
            if window in self.default_windows: continue
            form_text = next((x for x in window.winfo_children() if str(x).endswith("!formattedtext")),None)
            if form_text: # We need to manually set the text colors here
                form_text.configure(bg=r1,fg=r1t)
            else: # Just have a standard window - no formatted text to update
                window.set_colors()

    def compare_paths(self,check,path):
        if not isinstance(path,(str,unicode,list)): return False
        if self.case_insensitive:
            check = check.lower()
            path = path.lower() if isinstance(path,(str,unicode)) else [x.lower() for x in path]
        return check in path if isinstance(path,list) else check == path

    def normpath_recents(self):
        normalized = [os.path.normpath(x) for x in self.settings.get("open_recent",[])]
        new_paths = []
        for path in normalized:
            if self.compare_paths(path,new_paths): continue # Don't add duplicates
            new_paths.append(path)
        self.settings["open_recent"] = new_paths

    def update_recents(self):
        # Helper to figure out which menu(s) to update, and actually update them
        targets = [self] if str(sys.platform) == "darwin" else [w for w in self.stackorder(self.tk) if not w in self.default_windows]
        for target in targets:
            self.update_recents_for_target(target)

    def update_recents_for_target(self,target):
        if not hasattr(target,"recent_menu"): return # Invalid target?
        # Helper to setup the Open Resent menu for the target menu
        recents = self.settings.get("open_recent",[])
        target.recent_menu.delete(0,tk.END)
        if not len(recents):
            target.recent_menu.add_command(label="No Recently Opened Files", state=tk.DISABLED)
        else:
            for recent in recents:
                target.recent_menu.add_command(label=recent, command=lambda x=recent:self.open_recent(x))
        # Add the separator and clear option
        target.recent_menu.add_separator()
        target.recent_menu.add_command(label="Clear Recently Opened", command=self.clear_recents)

    def add_recent(self,recent):
        # Add a new item to our Open Recent list, and make sure our list
        # doesn't grow beyond the recent_max value
        recent = os.path.normpath(recent) # Normalize the pathing
        recents = [x for x in self.settings.get("open_recent",[]) if not self.compare_paths(recent,x)]
        recents.insert(0,recent)
        recent_max = self.settings.get("recent_max",10)
        recents = recents[:recent_max]
        self.settings["open_recent"] = recents
        self.update_recents()

    def rem_recent(self,recent):
        # Removes a recent from the Open Recent list if it exists
        recent = os.path.normpath(recent) # Normalize the pathing
        recents = [x for x in self.settings.get("open_recent",[]) if not x == recent]
        self.settings["open_recent"] = recents
        self.update_recents()

    def clear_recents(self):
        self.settings.pop("open_recent",None)
        self.update_recents()

    def open_recent(self, path=None):
        # First check if the file exists - if not, throw an error, and remove it
        # from the recents menu
        if path is None: # Try getting the first item from settings
            paths = self.settings.get("open_recent",[])
            if paths: path = paths[0]
        if path is None: # Couldn't get any recents - bail
            return
        path = os.path.normpath(path)
        if not (os.path.exists(path) and os.path.isfile(path)):
            self.rem_recent(path)
            self.tk.bell()
            mb.showerror("An Error Occurred While Opening {}".format(os.path.basename(path)), "The path '{}' does not exist.".format(path))
            return
        return self.pre_open_with_path(path)

    def check_open(self, plists = []):
        if self.is_opening: # Already opening - loop until we're not
            self.tk.after(5, lambda:self.check_open(plists))
            return
        self.is_opening = True
        try:
            plists = [x for x in plists if not self.regexp.search(x)]
            if isinstance(plists, list) and len(plists):
                at_least_one = False
                # Iterate the passed plists and open them
                for p in set(plists):
                    window = self.pre_open_with_path(p)
                    if not window: continue
                    at_least_one = True
                    if self.start_window == None:
                        self.start_window = window
                if not at_least_one: # If none of them opened, open a fresh plist
                    windows = self.stackorder(self.tk)
                    if not len(windows):
                        self.start_window = self.new_plist()
            elif not len(self.stackorder(self.tk)):
                # create a fresh plist to start
                self.start_window = self.new_plist()
        except Exception as e:
            self.tk.bell()
            mb.showerror("Error in check_open() function",repr(e))
        self.is_opening = False

    def open_plist_from_app(self, *args):
        if self.is_opening: # Already opening - loop until we're not
            self.tk.after(5, lambda:self.open_plist_from_app(*args))
            return
        self.is_opening = True
        try:
            if isinstance(args, str):
                args = [args]
            args = [x for x in args if not self.regexp.search(x)]
            for arg in args:
                windows = self.stackorder(self.tk)
                # Verify that no other window has that file selected already
                existing_window = next((window for window in windows if not window in self.default_windows and window.current_plist==arg),None)
                if existing_window:
                    self.lift_window(existing_window)
                    continue
                if len(windows) == 1 and windows[0] == self.start_window and windows[0].edited == False and windows[0].current_plist == None:
                    # Fresh window - replace the contents
                    current_window = windows[0]
                else:
                    current_window = None
                # Let's load the plist
                window = self.pre_open_with_path(arg,current_window)
                if self.start_window == None: self.start_window = window
        except Exception as e:
            self.tk.bell()
            mb.showerror("Error in open_plist_from_app() function",repr(e))
        self.is_opening = False

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

    def close_window(self, event = None, window = None, check_close = True):
        if window: window.withdraw()
        else:
            # Remove the default window that comes from it
            windows = self.stackorder(self.tk,include_defaults=True)
            if windows: windows[-1].withdraw()
        if check_close: self.check_close()
    
    def check_close(self, lift_last = True):
        windows = self.stackorder(self.tk,include_defaults=True)
        if not windows:
            self.quit()
        elif lift_last:
            self.lift_window(windows[-1])

    def strip_comments(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1] # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.strip_comments(event)

    def strip_disabled(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1] # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.strip_disabled(event)

    def change_to_type(self, value):
        self.settings["convert_to_type"] = value
        self.convert_values()

    def change_from_type(self, value):
        self.settings["convert_from_type"] = value

    def show_window(self, window, event = None):
        if not window.winfo_viewable():
            # Let's center the window
            w = window.winfo_width()
            h = window.winfo_height()
            if w==1==h: # Request width as we haven't drawn yet
                if window == self.tk: # Use the defaults
                    w, h = 640, 130
                else: # Try to approximate
                    w = window.winfo_reqwidth()
                    h = window.winfo_reqheight()
            x = window.winfo_screenwidth() // 2 - w // 2
            y = window.winfo_screenheight() // 2 - h // 2
            window.geometry("+{}+{}".format(x, y))
            window.deiconify()
        self.lift_window(window)
        if window == self.tk:
            # Only set the focus if we're showing the convert window
            self.f_text.focus_set()

    def get_bytes(self, value):
        if sys.version_info >= (3,0) and not isinstance(value,bytes):
            # Convert to bytes
            value = value.encode("utf-8")
        return value

    def get_string(self, value):
        if sys.version_info >= (3,0) and not isinstance(value,(str,unicode)):
            # Convert from bytes
            value = value.decode("utf-8")
        return value

    def swap_convert(self, event = None):
        # Swaps the values of the to and from conversion dropdown menus
        t,f = self.t_title.get(),self.f_title.get()
        self.settings["convert_to_type"] = f
        self.settings["convert_from_type"] = t
        self.t_title.set(f)
        self.f_title.set(t)
        # Move any data from the To to the From, and run the conversion
        self.f_text.delete(0,tk.END)
        self.f_text.insert(0,self.t_text.get())
        self.convert_values()

    def convert_values(self, event = None):
        from_value = self.f_text.get()
        if not len(from_value):
            # Empty - nothing to convert
            return
        # Pre-check for hex potential issues
        from_type = self.f_title.get().lower()
        to_type   = self.t_title.get().lower()
        if from_type == "hex":
            if from_value.lower().startswith("0x"):
                from_value = from_value[2:]
            from_value = from_value.replace(" ","").replace("<","").replace(">","")
            if [x for x in from_value if x.lower() not in "0123456789abcdef"]:
                self.tk.bell()
                mb.showerror("Invalid Hex Data","Invalid character in passed hex data.") # ,parent=self.tk)
                return
        try:
            if from_type == "decimal":
                # Convert to hex bytes
                from_value = "{:x}".format(int(from_value))
                if len(from_value) % 2:
                    from_value = "0"+from_value
            # Handle the from data
            if from_type == "base64":
                padded_from = from_value
                from_stripped = from_value.rstrip("=")
                if len(from_stripped) % 4 > 1: # Pad to a multiple of 4
                    padded_from = from_stripped + "="*(4-len(from_stripped)%4)
                if padded_from != from_value:
                    # Changed it - update the from box, and set the from value
                    from_value = padded_from
                    self.f_text.delete(0,tk.END)
                    self.f_text.insert(0,from_value)
                from_value = base64.b64decode(self.get_bytes(from_value))
            elif from_type in ("hex","decimal"):
                if len(from_value) % 2:
                    # Ensure we pad our hex
                    from_value = "0"+from_value
                    # Reflect it visually for all cases that need it
                    if to_type not in ("hex","decimal"):
                        self.f_text.delete(0,tk.END)
                        self.f_text.insert(0,from_value)
                from_value = binascii.unhexlify(self.get_bytes(from_value))
            # Let's get the data converted
            to_value = self.get_bytes(from_value)
            if to_type == "base64":
                to_value = base64.b64encode(self.get_bytes(from_value))
            elif to_type == "hex":
                to_value = binascii.hexlify(self.get_bytes(from_value))
            elif to_type == "decimal":
                to_value = str(int(binascii.hexlify(self.get_bytes(from_value)),16))
            if not to_type == "decimal":
                to_value = self.get_string(to_value)
            if to_type == "hex":
                # Capitalize it, and pad with spaces
                to_value = "{}".format(" ".join((to_value[0+i:8+i] for i in range(0, len(to_value), 8))).upper())
            # Set the text box
            self.t_text.configure(state='normal')
            self.t_text.delete(0,tk.END)
            self.t_text.insert(0,to_value)
            self.t_text.configure(state='readonly')
        except Exception as e:
            # Clear the text box
            self.t_text.configure(state='normal')
            self.t_text.delete(0,tk.END)
            self.t_text.configure(state='readonly')
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
        title = window.title()[:-len(" - Edited") if window.edited else None]+" - Copy"
        plist_data = window.nodes_to_values()
        new_window = plistwindow.PlistWindow(self, self.tk)
        new_window.open_plist(None,plist_data)
        # Update the Open Recent menu
        if str(sys.platform) != "darwin": self.update_recents_for_target(new_window)
        self.lift_window(new_window)

    def save_plist(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1] # Get the last item (most recent)
        if window in self.default_windows:
            return
        if window.save_plist(event):
            # Saved correctly, let's ensure the path is saved in recents
            self.add_recent(window.current_plist)
            self.lift_window(window)
    
    def save_plist_as(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1] # Get the last item (most recent)
        if window in self.default_windows:
            return
        if window.save_plist_as(event):
            # Saved correctly, let's ensure the path is saved in recents
            self.add_recent(window.current_plist)
            self.lift_window(window)

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
            temp = "untitled{}.plist".format("" if number == 0 else "-"+str(number))
            temp_edit = temp + " - edited"
            if not any((x in titles for x in (temp,temp_edit))):
                final_title = temp
                break
            number += 1
        window = plistwindow.PlistWindow(self, self.tk)
        # Update the Open Recent menu
        if str(sys.platform) != "darwin": self.update_recents_for_target(window)
        # Ensure our default plist and data types are reflected
        window.plist_type_string.set(self.plist_type_string.get())
        window.data_type_string.set(self.data_type_string.get())
        window.int_type_string.set(self.int_type_string.get())
        window.bool_type_string.set(self.bool_type_string.get())
        window.open_plist(final_title.capitalize(),{}) # Created an empty root
        window.current_plist = None # Ensure it's initialized as new
        self.lift_window(window)
        return window

    def open_plist(self, event=None):
        # Prompt the user to open a plist, attempt to load it, and if successful,
        # set its path as our current_plist value
        path = fd.askopenfilename(title = "Select plist file") # ,parent=current_window) # Apparently parent here breaks on 10.15?
        if not len(path): return # User cancelled - bail
        path = os.path.abspath(os.path.expanduser(path))
        return self.pre_open_with_path(path)

    def pre_open_with_path(self, path, current_window = None):
        if not path: return # Hmmm... shouldn't happen, but just in case
        path = os.path.abspath(os.path.expanduser(path))
        windows = self.stackorder(self.tk)
        if current_window == None and len(windows) == 1 and windows[0] == self.start_window and windows[0].edited == False and windows[0].current_plist == None:
            # Fresh window - replace the contents
            current_window = windows[0]
        # Verify that no other window has that file selected already
        for window in windows[::-1]:
            if window in self.default_windows: continue
            if window.current_plist == path:
                # found one - just make this focus instead
                self.lift_window(window)
                return
        return self.open_plist_with_path(None,path,current_window)

    def open_plist_with_path(self, event = None, path = None, current_window = None):
        if not path: return # Uh... wut?
        path = os.path.abspath(os.path.expanduser(path))
        # Let's try to load the plist
        try:
            with open(path,"rb") as f:
                plist_type = "Binary" if plist._is_binary(f) else "XML"
                plist_data = plist.load(f,dict_type=dict if self.settings.get("sort_dict",False) else OrderedDict)
        except Exception as e:
            # Had an issue, throw up a display box
            self.tk.bell()
            mb.showerror("An Error Occurred While Opening {}".format(os.path.basename(path)), str(e)) # ,parent=current_window)
            return
        # Opened it correctly - let's load it, and set our values
        if not current_window:
            # Need to create one first
            current_window = plistwindow.PlistWindow(self, self.tk)
        # Ensure our default data type is reflected
        current_window.data_type_string.set(self.data_type_string.get())
        current_window.int_type_string.set(self.int_type_string.get())
        current_window.bool_type_string.set(self.bool_type_string.get())
        current_window.open_plist(path,plist_data,plist_type,self.settings.get("expand_all_items_on_open",True))
        self.lift_window(current_window)
        # Add it to our Open Recent list
        self.add_recent(path)
        return current_window

    def stackorder(self, root = None, include_defaults = False):
        """return a list of root and toplevel windows in stacking order (topmost is last)"""
        root = root or self.tk
        check_types = (tk.Toplevel,tk.Tk) if include_defaults else plistwindow.PlistWindow
        c = root.children
        s = root.tk.eval('wm stackorder {}'.format(root))
        L = [x.lstrip('.') for x in s.split()]
        # Remove any non-needed widgets
        w = {}
        for x in list(c):
            if isinstance(c.get(x),check_types):
                w[x] = c[x] # Retain the valid types
        if "" in L and isinstance(root,check_types):
            # We also need to append the root
            w[""] = root
        # Build a list of just the tkinter classes that follow the stack order
        stack_order = [w[x] for x in L if x in w]
        # Add any missing windows (might be minimized)
        stack_order = [x for x in w.values() if not x in stack_order] + stack_order
        # Return the list, omitting any windows that are withdrawn
        return [x for x in stack_order if x.wm_state() != "withdrawn"]

    def lift_window(self, window=None):
        if window is None:
            windows = self.stackorder(self.tk,include_defaults=True)
            if windows: # Get the last window we saw
                window = windows[-1]
        if window is None: return # No windows in the stack order?
        window.deiconify() # Lift minimized windows as well
        window.lift()
        window.focus_force()
        try: window._tree.focus_force()
        except: pass
        window.attributes("-topmost",True)
        self.tk.after_idle(window.attributes,"-topmost",False)

    def quit(self, event_or_signum=None, frame=None):
        if self.is_quitting: return # Already quitting - don't try to do this twice at once
        if isinstance(event_or_signum,int) and frame is not None:
            print("KeyboardInterrupt caught - cleaning up...")
        self.is_quitting = True # Lock this to one quit attempt at a time
        # Get a list of all windows with unsaved changes
        unsaved = [x for x in self.stackorder(self.tk) if x.edited]
        ask_to_save = True
        if len(unsaved) > 1: # Ask for review
            answer = mb.askyesnocancel(
                "Unsaved Changes",
                "You have {:,} document{} with unsaved changes.\nWould you like to review?\n(If you don't review, all unsaved changes will be lost)".format(
                    len(unsaved),
                    "" if len(unsaved)==1 else "s"
                ))
            if answer is None:
                # Unlock quitting and return - user canceled
                self.is_quitting = False
                self.lift_window()
                return
            ask_to_save = answer # Iterate the windows and ask to save as needed
        # Walk through the windows and close them - either reviewing changes or ignoring them.
        for window in self.stackorder(self.tk)[::-1]:
            if window in self.default_windows: continue
            self.lift_window(window)
            if not window.close_window(check_saving=ask_to_save,check_close=False):
                self.is_quitting = False # Unlock the quit
                return # User cancelled or we failed to save, bail
        # Make sure we retain any non-event updated settings
        prefix = self.comment_prefix_text.get()
        prefix = "#" if not prefix else prefix
        self.settings["comment_strip_prefix"] = prefix
        try:
            max_undo = int(self.undo_max_text.get())
            assert max_undo >= 0
        except:
            max_undo = self.max_undo
        self.settings["max_undo"] = max_undo
        self.settings["drag_dead_zone"] = self.drag_scale.get()
        # Actually quit the tkinter session
        self.tk.destroy()
        # Attempt to save the settings
        cwd = os.getcwd()
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
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
