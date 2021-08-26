#!/usr/bin/env python
import base64
import binascii
import json
import os
import re
import subprocess
import sys
from collections import OrderedDict

from Scripts import plist, plistwindow

try:
    import Tkinter as tk
    import ttk
    import tkFileDialog as fd
    import tkMessageBox as mb
    from tkFont import Font
    from tkColorChooser import askcolor as ac
except:
    import tkinter as tk
    import tkinter.ttk as ttk
    from tkinter import filedialog as fd
    from tkinter import messagebox as mb
    from tkinter.font import Font
    from tkinter.colorchooser import askcolor as ac
# Add this script's dir to the local PATH var - may improve import consistency
sys.path.append(os.path.abspath(os.path.dirname(os.path.realpath(__file__))))


class ProperTree:
    def __init__(self, plists=[]):
        # Create the new tk object
        self.tk = tk.Tk()
        self.tk.title("Convert Values")
        self.tk.minsize(width=640, height=130)
        self.tk.resizable(True, False)
        self.tk.columnconfigure(2, weight=1)
        self.tk.columnconfigure(3, weight=1)
        # Build the Hex <--> Base64 converter
        f_label = tk.Label(self.tk, text="From:")
        f_label.grid(row=0, column=0, padx=10, pady=10)
        t_label = tk.Label(self.tk, text="To:")
        t_label.grid(row=1, column=0, padx=10, pady=10)

        # Create the settings window
        self.settings_window = tk.Toplevel(self.tk)
        self.settings_window.title("ProperTree Settings")
        self.settings_window.resizable(False, False)
        self.settings_window.columnconfigure(0, weight=1)
        self.settings_window.columnconfigure(1, weight=1)
        # Let's add some checkboxes and stuffs
        self.expand_on_open = tk.IntVar()
        self.use_xcode_data = tk.IntVar()
        self.sort_dict_keys = tk.IntVar()
        self.comment_ignore_case = tk.IntVar()
        self.comment_check_string = tk.IntVar()
        self.force_schema = tk.IntVar()
        self.expand_check = tk.Checkbutton(
            self.settings_window, text="Expand Children When Opening Plist", variable=self.expand_on_open,
            command=self.expand_command)
        self.xcode_check = tk.Checkbutton(
            self.settings_window, text="Use Xcode-Style <data> Tags (Inline) in XML Plists",
            variable=self.use_xcode_data, command=self.xcode_command)
        self.sort_check = tk.Checkbutton(
            self.settings_window, text="Ignore Dictionary Key Order", variable=self.sort_dict_keys,
            command=self.sort_command)
        self.ignore_case_check = tk.Checkbutton(
            self.settings_window, text="Ignore Case When Stripping Comments", variable=self.comment_ignore_case,
            command=self.ignore_case_command)
        self.check_string_check = tk.Checkbutton(self.settings_window,
                                                 text="Check String Values When Stripping Comments",
                                                 variable=self.comment_check_string, command=self.check_string_command)
        self.expand_check.grid(row=0, column=0, columnspan=2,
                               sticky="w", padx=10, pady=(10, 0))
        self.xcode_check.grid(
            row=1, column=0, columnspan=2, sticky="w", padx=10)
        self.sort_check.grid(
            row=2, column=0, columnspan=2, sticky="w", padx=10)
        self.ignore_case_check.grid(
            row=3, column=0, columnspan=2, sticky="w", padx=10)
        self.check_string_check.grid(
            row=4, column=0, columnspan=2, sticky="w", padx=10)
        comment_prefix_label = tk.Label(
            self.settings_window, text="Comment Prefix (default is #):")
        comment_prefix_label.grid(row=5, column=0, sticky="w", padx=10)
        self.comment_prefix_text = tk.Entry(self.settings_window)
        self.comment_prefix_text.grid(row=5, column=1, sticky="we", padx=10)
        self.plist_type_string = tk.StringVar(self.settings_window)
        self.plist_type_menu = tk.OptionMenu(
            self.settings_window, self.plist_type_string, "XML", "Binary", command=self.change_plist_type)
        plist_label = tk.Label(self.settings_window,
                               text="Default New Plist Type:")
        plist_label.grid(row=6, column=0, sticky="w", padx=10)
        self.plist_type_menu.grid(row=6, column=1, sticky="we", padx=10)
        self.data_type_string = tk.StringVar(self.settings_window)
        self.data_type_menu = tk.OptionMenu(
            self.settings_window, self.data_type_string, "Hex", "Base64", command=self.change_data_type)
        data_label = tk.Label(self.settings_window,
                              text="Data Display Default:")
        data_label.grid(row=7, column=0, sticky="w", padx=10)
        self.data_type_menu.grid(row=7, column=1, sticky="we", padx=10)
        self.int_type_string = tk.StringVar(self.settings_window)
        self.int_type_menu = tk.OptionMenu(
            self.settings_window, self.int_type_string, "Decimal", "Hex", command=self.change_int_type)
        int_label = tk.Label(self.settings_window,
                             text="Integer Display Default:")
        int_label.grid(row=8, column=0, sticky="w", padx=10)
        self.int_type_menu.grid(row=8, column=1, sticky="we", padx=10)
        self.snapshot_string = tk.StringVar(self.settings_window)
        self.snapshot_menu = tk.OptionMenu(
            self.settings_window, self.snapshot_string, "Latest", command=self.change_snapshot_version)
        snapshot_label = tk.Label(
            self.settings_window, text="Snapshot OC Version:")
        snapshot_label.grid(row=9, column=0, sticky="w", padx=10)
        self.snapshot_menu.grid(row=9, column=1, sticky="we", padx=10)
        self.schema_check = tk.Checkbutton(
            self.settings_window, text="Force Update Snapshot Schema", variable=self.force_schema,
            command=self.schema_command)
        self.schema_check.grid(
            row=10, column=0, columnspan=2, sticky="w", padx=10)
        sep = ttk.Separator(self.settings_window, orient="horizontal")
        sep.grid(row=11, column=0, columnspan=2, sticky="we", padx=10, pady=10)
        r1_label = tk.Label(self.settings_window,
                            text="Alternating Row Color #1:")
        r1_label.grid(row=12, column=0, sticky="w", padx=10)
        self.r1_canvas = tk.Canvas(
            self.settings_window, height=20, width=30, background="black", relief="groove", bd=2)
        self.r1_canvas.grid(row=12, column=1, sticky="we", padx=10)
        r2_label = tk.Label(self.settings_window,
                            text="Alternating Row Color #2:")
        r2_label.grid(row=13, column=0, sticky="w", padx=10)
        self.r2_canvas = tk.Canvas(
            self.settings_window, height=20, width=30, background="black", relief="groove", bd=2)
        self.r2_canvas.grid(row=13, column=1, sticky="we", padx=10)
        r3_label = tk.Label(self.settings_window, text="Background Color:")
        r3_label.grid(row=14, column=0, sticky="w", padx=10)
        self.bg_canvas = tk.Canvas(
            self.settings_window, height=20, width=30, background="black", relief="groove", bd=2)
        self.bg_canvas.grid(row=14, column=1, sticky="we", padx=10)
        r4_label = tk.Label(self.settings_window, text="Highlight Color:")
        r4_label.grid(row=15, column=0, sticky="w", padx=10)
        self.hl_canvas = tk.Canvas(
            self.settings_window, height=20, width=30, background="black", relief="groove", bd=2)
        self.hl_canvas.grid(row=15, column=1, sticky="we", padx=10)
        self.r1_inv_check = tk.IntVar()
        self.r1_inv = tk.Checkbutton(self.settings_window, text="Invert Row #1 Text Color",
                                     variable=self.r1_inv_check, command=self.check_r1_invert_command)
        self.r1_inv.grid(row=16, column=1, sticky="w", padx=10)
        self.r2_inv_check = tk.IntVar()
        self.r2_inv = tk.Checkbutton(self.settings_window, text="Invert Row #2 Text Color",
                                     variable=self.r2_inv_check, command=self.check_r2_invert_command)
        self.r2_inv.grid(row=17, column=1, sticky="w", padx=10)
        self.hl_inv_check = tk.IntVar()
        self.hl_inv = tk.Checkbutton(self.settings_window, text="Invert Highlight Text Color",
                                     variable=self.hl_inv_check, command=self.check_hl_invert_command)
        self.hl_inv.grid(row=18, column=1, sticky="w", padx=10)
        self.drag_label = tk.Label(
            self.settings_window, text="Drag Dead Zone (1-100 pixels):")
        self.drag_label.grid(row=19, column=0, sticky="w", padx=10)
        self.drag_scale = tk.Scale(
            self.settings_window, from_=1, to=100, orient=tk.HORIZONTAL)
        self.drag_scale.grid(row=19, column=1, sticky="we", padx=10)

        self.default_font = Font(font='TkTextFont')
        self.custom_font = tk.IntVar()
        self.font_check = tk.Checkbutton(
            self.settings_window, text="Use Custom Font Size", variable=self.custom_font, command=self.font_command)
        self.font_string = tk.StringVar()
        self.font_spinbox = tk.Spinbox(
            self.settings_window, from_=1, to=128, textvariable=self.font_string)
        self.font_string.trace("w", self.update_font)
        self.font_check.grid(row=20, column=0, sticky="w", padx=10)
        self.font_spinbox.grid(row=20, column=1, sticky="we", padx=10)

        sep_theme = ttk.Separator(self.settings_window, orient="horizontal")
        sep_theme.grid(row=21, column=0, columnspan=2,
                       sticky="we", padx=10, pady=10)
        r5_label = tk.Label(self.settings_window,
                            text="Default Theme Options:")
        r5_label.grid(row=22, column=0, sticky="w", padx=10)
        default_high = tk.Button(self.settings_window, text="Reset Highlight",
                                 command=lambda: self.swap_colors("highlight"))
        default_high.grid(row=23, column=0, sticky="we", padx=10)
        default_light = tk.Button(
            self.settings_window, text="Light Mode Defaults", command=lambda: self.swap_colors("light"))
        default_light.grid(row=22, column=1, sticky="we", padx=10)
        default_dark = tk.Button(
            self.settings_window, text="Dark Mode Defaults", command=lambda: self.swap_colors("dark"))
        default_dark.grid(row=23, column=1, sticky="we", padx=10)
        reset_settings = tk.Button(
            self.settings_window, text="Reset All To Defaults", command=self.reset_settings)
        reset_settings.grid(row=24, column=1, sticky="we", padx=10, pady=10)

        # Setup the color picker click methods
        self.r1_canvas.bind(
            "<ButtonRelease-1>", lambda x: self.pick_color("alternating_color_1", self.r1_canvas))
        self.r2_canvas.bind(
            "<ButtonRelease-1>", lambda x: self.pick_color("alternating_color_2", self.r2_canvas))
        self.hl_canvas.bind(
            "<ButtonRelease-1>", lambda x: self.pick_color("highlight_color", self.hl_canvas))
        self.bg_canvas.bind(
            "<ButtonRelease-1>", lambda x: self.pick_color("background_color", self.bg_canvas))

        # Setup some canvas connections
        self.canvas_connect = {
            self.r1_canvas: {"invert": self.r1_inv_check},
            self.r2_canvas: {"invert": self.r2_inv_check},
            self.hl_canvas: {"invert": self.hl_inv_check}
        }

        self.default_dark = {
            "alternating_color_1": "#161616",
            "alternating_color_2": "#202020",
            "highlight_color": "#1E90FF",
            "background_color": "#161616",
            "invert_row1_text_color": False,
            "invert_row2_text_color": False
        }
        self.default_light = {
            "alternating_color_1": "#F0F1F1",
            "alternating_color_2": "#FEFEFE",
            "highlight_color": "#1E90FF",
            "background_color": "#FEFEFE",
            "invert_row1_text_color": False,
            "invert_row2_text_color": False
        }

        # Setup the from/to option menus
        f_title = tk.StringVar(self.tk)
        t_title = tk.StringVar(self.tk)
        f_title.set("Base64")
        t_title.set("Hex")
        f_option = tk.OptionMenu(
            self.tk, f_title, "Ascii", "Base64", "Decimal", "Hex", command=self.change_from_type)
        t_option = tk.OptionMenu(
            self.tk, t_title, "Ascii", "Base64", "Decimal", "Hex", command=self.change_to_type)
        self.from_type = "Base64"
        self.to_type = "Hex"
        f_option.grid(row=0, column=1, sticky="we")
        t_option.grid(row=1, column=1, sticky="we")

        self.f_text = tk.Entry(self.tk)
        self.f_text.delete(0, tk.END)
        self.f_text.insert(0, "")
        self.f_text.grid(row=0, column=2, columnspan=2,
                         sticky="we", padx=10, pady=10)

        self.t_text = tk.Entry(self.tk)
        self.t_text.configure(state='normal')
        self.t_text.delete(0, tk.END)
        self.t_text.insert(0, "")
        self.t_text.configure(state='readonly')
        self.t_text.grid(row=1, column=2, columnspan=2,
                         sticky="we", padx=10, pady=10)

        self.c_button = tk.Button(
            self.tk, text="Convert", command=self.convert_values)
        self.c_button.grid(row=2, column=3, sticky="e", padx=10, pady=10)

        self.f_text.bind("<Return>", self.convert_values)
        self.f_text.bind("<KP_Enter>", self.convert_values)

        self.start_window = None

        # Regex to find the processor serial numbers when
        # opened from the Finder
        self.regexp = re.compile(r"^-psn_[0-9]+_[0-9]+$")

        # Setup the menu-related keybinds - and change the app name if needed
        key = "Control"
        sign = "Ctrl+"
        self.use_dark = self.get_dark()
        if str(sys.platform) == "darwin":
            # Remap the quit function to our own
            self.tk.createcommand('::tk::mac::Quit', self.quit)
            self.tk.createcommand("::tk::mac::OpenDocument",
                                  self.open_plist_from_app)
            self.tk.createcommand(
                "::tk::mac::ShowPreferences", lambda: self.show_window(self.settings_window))
            # Import the needed modules to change the bundle name and force focus
            try:
                from Foundation import NSBundle
                from Cocoa import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
                app = NSRunningApplication.runningApplicationWithProcessIdentifier_(
                    os.getpid())
                app.activateWithOptions_(
                    NSApplicationActivateIgnoringOtherApps)
                bundle = NSBundle.mainBundle()
                if bundle:
                    info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
                    if info and info['CFBundleName'] == 'Python':
                        info['CFBundleName'] = "ProperTree"
            except:
                pass
            key = "Command"
            sign = key + "+"

        self.tk.protocol("WM_DELETE_WINDOW", self.close_window)
        self.settings_window.protocol("WM_DELETE_WINDOW", self.close_window)
        # Close initial windows
        self.tk.withdraw()
        self.settings_window.withdraw()

        self.default_windows = (self.tk, self.settings_window)

        if str(sys.platform) == "darwin":
            # Setup the top level menu
            file_menu = tk.Menu(self.tk)
            main_menu = tk.Menu(self.tk)
            main_menu.add_cascade(label="File", menu=file_menu)
            file_menu.add_command(label="New (Cmd+N)", command=self.new_plist)
            file_menu.add_command(label="Open (Cmd+O)",
                                  command=self.open_plist)
            file_menu.add_command(label="Save (Cmd+S)",
                                  command=self.save_plist)
            file_menu.add_command(
                label="Save As... (Cmd+Shift+S)", command=self.save_plist_as)
            file_menu.add_command(label="Duplicate (Cmd+D)",
                                  command=self.duplicate_plist)
            file_menu.add_command(
                label="Reload From Disk (Cmd+L)", command=self.reload_from_disk)
            file_menu.add_separator()
            file_menu.add_command(
                label="OC Snapshot (Cmd+R)", command=self.oc_snapshot)
            file_menu.add_command(
                label="OC Clean Snapshot (Cmd+Shift+R)", command=self.oc_clean_snapshot)
            file_menu.add_separator()
            file_menu.add_command(
                label="Convert Window (Cmd+T)", command=lambda: self.show_window(self.tk))
            file_menu.add_command(
                label="Strip Comments (Cmd+M)", command=self.strip_comments)
            file_menu.add_command(
                label="Strip Disabled Entries (Cmd+E)", command=self.strip_disabled)
            file_menu.add_separator()
            file_menu.add_command(
                label="Settings (Cmd+,)", command=lambda: self.show_window(self.settings_window))
            file_menu.add_separator()
            file_menu.add_command(
                label="Toggle Find/Replace Pane (Cmd+F)", command=self.hide_show_find)
            file_menu.add_command(
                label="Toggle Plist/Data/Int Type Pane (Cmd+P)", command=self.hide_show_type)
            file_menu.add_separator()
            file_menu.add_command(label="Quit (Cmd+Q)", command=self.quit)
            self.tk.config(menu=main_menu)

        # Set bindings
        # on at least macOS, tk 8.5 works with <Command-Z>, but 8.6 requires <Shift-Command-z>
        self.tk.bind("<{}-w>".format(key), self.close_window)
        self.settings_window.bind("<{}-w>".format(key), self.close_window)
        self.tk.bind_all("<{}-n>".format(key), self.new_plist)
        self.tk.bind_all("<{}-o>".format(key), self.open_plist)
        self.tk.bind_all("<{}-s>".format(key), self.save_plist)
        self.tk.bind_all("<Shift-{}-s>".format(key) if tk.TkVersion >= 8.6 and str(
            sys.platform) == "darwin" else "<{}-S>".format(key), self.save_plist_as)
        self.tk.bind_all("<{}-d>".format(key), self.duplicate_plist)
        self.tk.bind_all("<{}-t>".format(key), lambda event,
                                                      x=self.tk: self.show_window(x))
        self.tk.bind_all("<{}-z>".format(key), self.undo)
        self.tk.bind_all("<Shift-{}-z>".format(key) if tk.TkVersion >= 8.6 and str(
            sys.platform) == "darwin" else "<{}-Z>".format(key), self.redo)
        self.tk.bind_all("<{}-m>".format(key), self.strip_comments)
        self.tk.bind_all("<{}-e>".format(key), self.strip_disabled)
        self.tk.bind_all("<{}-r>".format(key), self.oc_snapshot)
        self.tk.bind_all("<Shift-{}-R>".format(key) if tk.TkVersion >= 8.6 and str(
            sys.platform) == "darwin" else "<{}-R>".format(key), self.oc_clean_snapshot)
        self.tk.bind_all("<{}-l>".format(key), self.reload_from_disk)
        if not str(sys.platform) == "darwin":
            # Rewrite the default Command-Q command
            self.tk.bind_all("<{}-q>".format(key), self.quit)
            self.tk.bind_all("<{}-comma>".format(key), lambda event,
                                                              x=self.settings_window: self.show_window(x))

        cwd = os.getcwd()
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        #
        # Load the settings - current available settings are:
        #
        # last_window_width:          width value (default is 640)
        # last_window_height:         height value (default is 480)
        # expand_all_items_on_open:   bool
        # sort_dict:                  bool, false = OrderedDict
        # xcode_data:                 bool, true = <data>XXXX</data>, false = different lines
        # comment_strip_prefix:       string, defaults to #
        # comment_strip_ignore_case:  bool, true = ignore case when stripping comments
        # comment_strip_check_string: bool, true = consider string values as well as keys
        # new_plist_default_type:     string, XML/Binary
        # display_data_as:            string, Hex/Base64
        # display_int_as:             string, Decimal/Hex
        # snapshot_version:           string, X.X.X version number, or Latest
        # force_snapshot_schema:      bool
        # alternating_color_1:        string, Dark: #161616 - Light: #F0F1F1
        # alternating_color_2:        string, Dark: #202020 - Light: #FEFEFE
        # highlight_color:            string, Dark: #1E90FF - Light: #1E90FF
        # background_color:           string, Dark: #161616 - Light: #FEFEFE
        # invert_row1_text_color:     bool
        # invert_row2_text_color:     bool
        # invert_hl_text_color:       bool
        # drag_dead_zone:             pixel distance before drag starts (default is 20)
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
                with open("Scripts/snapshot.plist", "rb") as f:
                    self.snapshot_data = plist.load(f)
            except:
                pass
        os.chdir(cwd)

        # Setup the settings page to reflect our settings.json file

        self.allowed_types = ("XML", "Binary")
        self.allowed_data = ("Hex", "Base64")
        self.allowed_int = ("Decimal", "Hex")
        self.update_settings()

        # Wait before opening a new document to see if we need to.
        # This was annoying to debug, but seems to work.
        self.tk.after(250, lambda: self.check_open(plists))
        self.check_dark_mode()

        # Start our run loop
        tk.mainloop()

    def check_dark_mode(self):
        check_dark = self.get_dark()
        if check_dark != self.use_dark and any(
                (x not in self.settings for x in ("alternating_color_1", "alternating_color_2", "background_color"))):
            # Mode changed
            self.use_dark = check_dark
            self.update_settings()
        # Continue the loop
        self.tk.after(10000, lambda: self.check_dark_mode())

    def get_dark(self):
        if os.name == "nt":
            # Get the registry entry to tell us if we're in dark/light mode
            p = subprocess.Popen(["reg", "query", "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                                  "/v", "AppsUseLightTheme"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            c = p.communicate()
            return c[0].decode("utf-8", "ignore").strip().lower().split(" ")[-1] in ("", "0x0")
        elif str(sys.platform) != "darwin":
            return True  # Default to dark mode on Linux platforms
        # Get the macOS version - and see if dark mode is a thing
        p = subprocess.Popen(["sw_vers", "-productVersion"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        c = p.communicate()
        p_vers = c[0].decode("utf-8", "ignore").strip().lower()
        if p_vers < "10.14.0":
            return True  # Default to dark on anything prior to
        # At this point - we have an OS that supports dark mode, let's check our value
        p = subprocess.Popen(["defaults", "read", "-g", "AppleInterfaceStyle"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        c = p.communicate()
        return c[0].decode("utf-8", "ignore").strip().lower() == "dark"

    def text_color(self, hex_color, invert=False):
        hex_color = hex_color.lower()
        if hex_color.startswith("0x"):
            hex_color = hex_color[2:]
        if hex_color.startswith("#"):
            hex_color = hex_color[1:]
        # Check for bogus hex and return "black" by default
        if len(hex_color) != 6 or not all((x in "0123456789abcdef" for x in hex_color)):
            return "white" if invert else "black"
        # Get the r, g, and b values and determine our fake luminance
        r = float(int(hex_color[0:2], 16))
        g = float(int(hex_color[2:4], 16))
        b = float(int(hex_color[4:6], 16))
        l = (r * 0.299 + g * 0.587 + b * 0.114) > 186
        if l:
            return "white" if invert else "black"
        return "black" if invert else "white"

    def expand_command(self, event=None):
        self.settings["expand_all_items_on_open"] = True if self.expand_on_open.get(
        ) else False

    def xcode_command(self, event=None):
        self.settings["xcode_data"] = True if self.use_xcode_data.get() else False

    def sort_command(self, event=None):
        self.settings["sort_dict"] = True if self.sort_dict_keys.get() else False

    def ignore_case_command(self, event=None):
        self.settings["comment_strip_ignore_case"] = True if self.comment_ignore_case.get(
        ) else False

    def check_string_command(self, event=None):
        self.settings["comment_strip_check_string"] = True if self.comment_check_string.get(
        ) else False

    def check_r1_invert_command(self, event=None):
        self.settings["invert_row1_text_color"] = True if self.r1_inv_check.get(
        ) else False
        self.update_colors()

    def check_r2_invert_command(self, event=None):
        self.settings["invert_row2_text_color"] = True if self.r2_inv_check.get(
        ) else False
        self.update_colors()

    def check_hl_invert_command(self, event=None):
        self.settings["invert_hl_text_color"] = True if self.hl_inv_check.get(
        ) else False
        self.update_colors()

    def schema_command(self, event=None):
        self.settings["force_snapshot_schema"] = True if self.force_schema.get(
        ) else False

    def change_plist_type(self, event=None):
        self.settings["new_plist_default_type"] = self.plist_type_string.get()

    def change_data_type(self, event=None):
        self.settings["display_data_as"] = self.data_type_string.get()

    def change_int_type(self, event=None):
        self.settings["display_int_as"] = self.int_type_string.get()

    def change_snapshot_version(self, event=None):
        self.settings["snapshot_version"] = self.snapshot_string.get().split(" ")[
            0]

    def font_command(self, event=None):
        if self.custom_font.get():
            self.settings["use_custom_font_size"] = True
            self.font_spinbox.configure(state="normal")
        else:
            self.settings["use_custom_font_size"] = False
            self.font_spinbox.configure(state="disabled")
            self.font_string.set(self.default_font["size"])
            self.settings.pop("font_size", None)
        self.update_font()

    def update_font(self, var=None, blank=None, trace_mode=None):
        try:
            font_size = int(self.font_string.get())
        except:
            return
        self.settings["font_size"] = font_size
        self.update_fonts()

    def pick_color(self, color_name=None, canvas=None):
        if not color_name or not canvas:
            return  # uh wut?
        _, color = ac(color=canvas["background"])
        if not color:
            return  # User bailed
        self.settings[color_name] = color
        canvas.configure(background=color)
        self.update_colors()

    def swap_colors(self, color_type=None):
        if not isinstance(color_type, str):
            return
        color_type = color_type.lower()
        if color_type == "highlight":
            self.settings.pop("highlight_color", None)
            self.settings.pop("invert_hl_text_color", None)
            return self.update_settings()
        # Find out if we're setting it to light or dark mode - and if on macOS/Windows + using the system's current settings,
        # remove them to use defaults
        self.use_dark = self.get_dark()
        color_dict = self.default_light if color_type == "light" else self.default_dark
        to_remove = (self.use_dark and color_type == "dark") or (
                not self.use_dark and color_type != "dark")
        for x in color_dict:
            if color_type != "highlight" and x.lower() == "highlight_color":
                continue
            if to_remove:
                self.settings.pop(x, None)
            else:
                self.settings[x] = color_dict[x]
        self.update_settings()

    def reset_settings(self, event=None):
        self.settings = {}
        self.update_settings()

    def update_settings(self):
        self.expand_on_open.set(self.settings.get(
            "expand_all_items_on_open", True))
        self.use_xcode_data.set(self.settings.get("xcode_data", True))
        self.sort_dict_keys.set(self.settings.get("sort_dict", False))
        def_type = self.settings.get(
            "new_plist_default_type", self.allowed_types[0])
        self.plist_type_string.set(
            def_type if def_type in self.allowed_types else self.allowed_types[0])
        dat_type = self.settings.get("display_data_as", self.allowed_data[0])
        self.data_type_string.set(
            dat_type if dat_type in self.allowed_data else self.allowed_data[0])
        int_type = self.settings.get("display_int_as", self.allowed_int[0])
        self.int_type_string.set(
            int_type if int_type in self.allowed_int else self.allowed_int[0])
        self.snapshot_menu["menu"].delete(0, "end")
        snapshot_versions = ["{} -> {}".format(x["min_version"], x.get("max_version", "Current"))
                             for x in self.snapshot_data if "min_version" in x and len(x["min_version"])]
        snapshot_choices = ["Latest"] + sorted(snapshot_versions, reverse=True)
        for choice in snapshot_choices:
            self.snapshot_menu["menu"].add_command(label=choice, command=tk._setit(
                self.snapshot_string, choice, self.change_snapshot_version))
        snapshot_vers = self.settings.get("snapshot_version", "Latest")
        snapshot_name = next(
            (x for x in snapshot_choices if x.split(" ")[0] == snapshot_vers))
        self.snapshot_string.set(
            snapshot_name if snapshot_name in snapshot_choices else "Latest")
        self.force_schema.set(self.settings.get(
            "force_snapshot_schema", False))
        self.comment_ignore_case.set(self.settings.get(
            "comment_strip_ignore_case", False))
        self.comment_check_string.set(
            self.settings.get("comment_strip_check_string", True))
        self.comment_prefix_text.delete(0, tk.END)
        prefix = self.settings.get("comment_strip_prefix", "#")
        prefix = "#" if not prefix else prefix
        self.comment_prefix_text.insert(0, prefix)
        default_color = self.default_dark if self.use_dark else self.default_light
        color_1 = "".join([x for x in self.settings.get(
            "alternating_color_1", default_color["alternating_color_1"]) if x.lower() in "0123456789abcdef"])
        color_2 = "".join([x for x in self.settings.get(
            "alternating_color_2", default_color["alternating_color_2"]) if x.lower() in "0123456789abcdef"])
        color_h = "".join([x for x in self.settings.get(
            "highlight_color", default_color["highlight_color"]) if x.lower() in "0123456789abcdef"])
        color_b = "".join([x for x in self.settings.get(
            "background_color", default_color["background_color"]) if x.lower() in "0123456789abcdef"])
        self.r1_canvas.configure(
            background="#" + color_1 if len(color_1) == 6 else default_color["alternating_color_1"])
        self.r2_canvas.configure(
            background="#" + color_2 if len(color_2) == 6 else default_color["alternating_color_2"])
        self.hl_canvas.configure(
            background="#" + color_h if len(color_h) == 6 else default_color["highlight_color"])
        self.bg_canvas.configure(
            background="#" + color_b if len(color_b) == 6 else default_color["background_color"])
        self.r1_inv_check.set(self.settings.get(
            "invert_row1_text_color", False))
        self.r2_inv_check.set(self.settings.get(
            "invert_row2_text_color", False))
        self.hl_inv_check.set(self.settings.get("invert_hl_text_color", False))
        self.drag_scale.set(self.settings.get("drag_dead_zone", 20))
        self.font_string.set(self.settings.get(
            "font_size", self.default_font["size"]))
        self.custom_font.set(self.settings.get("use_custom_font_size", False))
        self.font_command()
        self.update_colors()

    def update_canvas_text(self, canvas=None):
        if canvas == None:  # Update all
            canvas = (self.r1_canvas, self.r2_canvas, self.hl_canvas)
        if not isinstance(canvas, (tuple, list)):
            canvas = (canvas,)
        for c in canvas:
            if not c in self.canvas_connect:
                continue  # Not a recognized canvas - skip
            # Update each canvas as needed - but mind the text color
            color = self.text_color(
                c["background"], self.canvas_connect[c]["invert"].get())
            # We haven't drawn it yet - try to
            if self.canvas_connect[c].get("text_id", None) == None:
                # Get the size
                w = self.settings_window.winfo_width()
                h = c.winfo_height()
                if w == 1 == h:  # Request width as we haven't drawn yet
                    w = self.settings_window.winfo_reqwidth()
                    h = c.winfo_reqheight()
                self.canvas_connect[c]["text_id"] = c.create_text(
                    (w - 20) / 2, h / 2, text="Sample Text")
            # Set the color
            c.itemconfig(self.canvas_connect[c]["text_id"], fill=color)

    def update_fonts(self):
        windows = self.stackorder(self.tk)
        if not len(windows):
            return
        for window in windows:
            if window in self.default_windows:
                continue
            window.set_font_size()

    def update_colors(self):
        self.update_canvas_text()
        # Update all windows' colors
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        for window in windows:
            if window in self.default_windows:
                continue
            window.set_colors()

    def check_open(self, plists=[]):
        plists = [x for x in plists if not self.regexp.search(x)]
        if isinstance(plists, list) and len(plists):
            at_least_one = False
            # Iterate the passed plists and open them
            for p in set(plists):
                window = self.open_plist_with_path(None, p, None)
                if not window:
                    continue
                at_least_one = True
                if self.start_window == None:
                    self.start_window = window
            if not at_least_one:  # Check if we have any other windows open - and close as needed
                windows = self.stackorder(self.tk)
                if not len(windows):
                    self.quit()
        elif not len(self.stackorder(self.tk)):
            # create a fresh plist to start
            self.start_window = self.new_plist()

    def open_plist_from_app(self, *args):
        if isinstance(args, str):
            args = [args]
        args = [x for x in args if not self.regexp.search(x)]
        for arg in args:
            windows = self.stackorder(self.tk)
            # Verify that no other window has that file selected already
            existing_window = next(
                (window for window in windows if not window in self.default_windows and window.current_plist == arg),
                None)
            if existing_window:
                self.lift_window(existing_window)
                continue
            if len(windows) == 1 and windows[0] == self.start_window and windows[0].edited == False and windows[
                0].current_plist == None:
                # Fresh window - replace the contents
                current_window = windows[0]
            else:
                current_window = None
            # Let's load the plist
            window = self.open_plist_with_path(None, arg, current_window)
            if self.start_window == None:
                self.start_window = window

    def change_hd_type(self, value):
        self.hd_type = value

    def reload_from_disk(self, event=None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1]  # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.reload_from_disk(event)

    def change_data_display(self, new_data=None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1]  # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.change_data_display(new_data)

    def oc_clean_snapshot(self, event=None):
        self.oc_snapshot(event, True)

    def oc_snapshot(self, event=None, clean=False):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1]  # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.oc_snapshot(event, clean)

    def hide_show_find(self, event=None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1]  # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.hide_show_find(event)

    def hide_show_type(self, event=None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1]  # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.hide_show_type(event)

    def close_window(self, event=None, check_close=True):
        # Remove the default window that comes from it
        windows = self.stackorder(self.tk)
        if len(windows):
            windows[-1].withdraw()
            windows = windows[:-1]
        if check_close and not len(windows):
            # Quit if all windows are closed
            self.quit()

    def strip_comments(self, event=None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1]  # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.strip_comments(event)

    def strip_disabled(self, event=None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1]  # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.strip_disabled(event)

    def change_to_type(self, value):
        self.to_type = value
        self.convert_values()

    def change_from_type(self, value):
        self.from_type = value

    def show_window(self, window, event=None):
        if not window.winfo_viewable():
            # Let's center the window
            w = window.winfo_width()
            h = window.winfo_height()
            if w == 1 == h:  # Request width as we haven't drawn yet
                if window == self.tk:  # Use the defaults
                    w, h = 640, 130
                else:  # Try to approximate
                    w = window.winfo_reqwidth()
                    h = window.winfo_reqheight()
            x = window.winfo_screenwidth() // 2 - w // 2
            y = window.winfo_screenheight() // 2 - h // 2
            window.geometry("+{}+{}".format(x, y))
            window.deiconify()
        window.lift()

    def convert_values(self, event=None):
        from_value = self.f_text.get()
        if not len(from_value):
            # Empty - nothing to convert
            return
        # Pre-check for hex potential issues
        if self.from_type.lower() == "hex":
            if from_value.lower().startswith("0x"):
                from_value = from_value[2:]
            from_value = from_value.replace(
                " ", "").replace("<", "").replace(">", "")
            if [x for x in from_value if x.lower() not in "0123456789abcdef"]:
                self.tk.bell()
                # ,parent=self.tk)
                mb.showerror("Invalid Hex Data",
                             "Invalid character in passed hex data.")
                return
        try:
            if self.from_type.lower() == "decimal":
                # Convert to hex bytes
                from_value = "{:x}".format(int(from_value))
                if len(from_value) % 2:
                    from_value = "0" + from_value
            # Handle the from data
            if sys.version_info >= (3, 0):
                # Convert to bytes
                from_value = from_value.encode("utf-8")
            if self.from_type.lower() == "base64":
                from_value = base64.b64decode(from_value)
            elif self.from_type.lower() in ["hex", "decimal"]:
                from_value = binascii.unhexlify(from_value)
            # Let's get the data converted
            to_value = from_value
            if self.to_type.lower() == "base64":
                to_value = base64.b64encode(from_value)
            elif self.to_type.lower() == "hex":
                to_value = binascii.hexlify(from_value)
            elif self.to_type.lower() == "decimal":
                to_value = str(int(binascii.hexlify(from_value), 16))
            if sys.version_info >= (3, 0) and not self.to_type.lower() == "decimal":
                # Convert to bytes
                to_value = to_value.decode("utf-8")
            if self.to_type.lower() == "hex":
                # Capitalize it, and pad with spaces
                to_value = "{}".format(
                    " ".join((to_value[0 + i:8 + i] for i in range(0, len(to_value), 8))).upper())
            # Set the text box
            self.t_text.configure(state='normal')
            self.t_text.delete(0, tk.END)
            self.t_text.insert(0, to_value)
            self.t_text.configure(state='readonly')
        except Exception as e:
            self.tk.bell()
            mb.showerror("Conversion Error", str(e))  # ,parent=self.tk)

    ###                       ###
    # Save/Load Plist Functions #
    ###                       ###

    def duplicate_plist(self, event=None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1]  # Get the last item (most recent)
        if window in self.default_windows:
            return
        plist_data = window.nodes_to_values()
        plistwindow.PlistWindow(self, self.tk).open_plist(None, plist_data)

    def save_plist(self, event=None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1]  # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.save_plist(event)

    def save_plist_as(self, event=None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1]  # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.save_plist_as(event)

    def undo(self, event=None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1]  # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.reundo(event)

    def redo(self, event=None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # Nothing to do
            return
        window = windows[-1]  # Get the last item (most recent)
        if window in self.default_windows:
            return
        window.reundo(event, False)

    def new_plist(self, event=None):
        # Creates a new plistwindow object
        # Let's try to create a unique name (if Untitled.plist is used, add a number)
        titles = [x.title().lower() for x in self.stackorder(self.tk)]
        number = 0
        final_title = "Untitled.plist"
        while True:
            temp = "untitled{}.plist".format(
                "" if number == 0 else "-" + str(number))
            temp_edit = temp + " - edited"
            if not any((x in titles for x in (temp, temp_edit))):
                final_title = temp
                break
            number += 1
        window = plistwindow.PlistWindow(self, self.tk)
        # Ensure our default plist and data types are reflected
        window.plist_type_string.set(self.plist_type_string.get())
        window.data_type_string.set(self.data_type_string.get())
        window.int_type_string.set(self.int_type_string.get())
        window.open_plist(final_title.capitalize(), {}
                          )  # Created an empty root
        window.current_plist = None  # Ensure it's initialized as new
        self.lift_window(window)
        return window

    def open_plist(self, event=None):
        # Prompt the user to open a plist, attempt to load it, and if successful,
        # set its path as our current_plist value
        # ,parent=current_window) # Apparently parent here breaks on 10.15?
        path = fd.askopenfilename(title="Select plist file")
        if not len(path):
            return  # User cancelled - bail
        path = os.path.realpath(os.path.expanduser(path))
        current_window = None
        windows = self.stackorder(self.tk)
        if len(windows) == 1 and windows[0] == self.start_window and windows[0].edited == False and windows[
            0].current_plist == None:
            # Fresh window - replace the contents
            current_window = windows[0]
        # Verify that no other window has that file selected already
        for window in windows:
            if window in self.default_windows:
                continue
            if window.current_plist == path:
                # found one - just make this focus instead
                self.lift_window(window)
                window.bell()
                # , parent=window)
                mb.showerror("File Already Open",
                             "{} is already open here.".format(path))
                return
        return self.open_plist_with_path(event, path, current_window)

    def open_plist_with_path(self, event=None, path=None, current_window=None, plist_type="XML"):
        if path == None:
            # Uh... wut?
            return
        path = os.path.realpath(os.path.expanduser(path))
        # Let's try to load the plist
        try:
            with open(path, "rb") as f:
                plist_type = "Binary" if plist._is_binary(f) else "XML"
                plist_data = plist.load(f, dict_type=dict if self.settings.get(
                    "sort_dict", False) else OrderedDict)
        except Exception as e:
            # Had an issue, throw up a display box
            self.tk.bell()
            mb.showerror("An Error Occurred While Opening {}".format(
                os.path.basename(path)), str(e))  # ,parent=current_window)
            return
        # Opened it correctly - let's load it, and set our values
        if not current_window:
            # Need to create one first
            current_window = plistwindow.PlistWindow(self, self.tk)
        # Ensure our default data type is reflected
        current_window.data_type_string.set(self.data_type_string.get())
        current_window.int_type_string.set(self.int_type_string.get())
        current_window.open_plist(path, plist_data, plist_type, self.settings.get(
            "expand_all_items_on_open", True))
        self.lift_window(current_window)
        return current_window

    def stackorder(self, root):
        """return a list of root and toplevel windows in stacking order (topmost is last)"""
        c = root.children
        s = root.tk.eval('wm stackorder {}'.format(root))
        L = [x.lstrip('.') for x in s.split()]
        return [(c[x] if x else root) for x in L]

    def lift_window(self, window):
        window.lift()
        window.focus_force()
        try:
            window._tree.focus_force()
        except:
            pass
        window.attributes("-topmost", True)
        self.tk.after_idle(window.attributes, "-topmost", False)

    def quit(self, event=None):
        # Check if we need to save first, then quit if we didn't cancel
        for window in self.stackorder(self.tk)[::-1]:
            if window in self.default_windows:
                continue
            if not window.close_window(check_close=False):
                return  # User cancelled or we failed to save, bail
        # Make sure we retain any non-event updated settings
        prefix = self.comment_prefix_text.get()
        prefix = "#" if not prefix else prefix
        self.settings["comment_strip_prefix"] = prefix
        self.settings["drag_dead_zone"] = self.drag_scale.get()
        # Actually quit the tkinter session
        self.tk.destroy()
        # Attempt to save the settings
        cwd = os.getcwd()
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        try:
            json.dump(self.settings, open(
                "Scripts/settings.json", "w"), indent=4)
        except:
            pass
        os.chdir(cwd)


if __name__ == '__main__':
    plists = []
    if len(sys.argv) > 1:
        plists = sys.argv[1:]
    p = ProperTree(plists)
