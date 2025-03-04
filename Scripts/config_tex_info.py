import os
import sys
import re
if sys.version_info.major >= 3:
    import tkinter as tk
    import tkinter.ttk as ttk
    import tkinter.font as tk_font
    from tkinter import messagebox as mb
else:
    import Tkinter as tk
    import ttk
    import tkFont as tk_font #pylint: disable=E0401
    import tkMessageBox as mb #pylint: disable=E0401

class ConfigurationLoadError(Exception):
    """Raised when the Configuration.tex could not be found or opened."""
    pass


def display_info_window(config_tex, search_list, width, valid_only, show_urls, calling_window, font=None, fg="white", bg="black"):
    # probably a simpler way to set up the formatted text
    # but found this format online and it works for now
    class FormattedText(tk.Text):
        def __init__(self, *args, **kwargs):
            # super(FormattedText,self).__init__(*args, **kwargs)
            tk.Text.__init__(self, *args, **kwargs)
            self.font = kwargs.get("font")
            self.update_font()

        def update_font(self, font=None):
            self.font = font or self.font
            if not self.font:  # Fall back to defaults
                self.font = tk_font.nametofont(self.cget("font"))

            #TODO find a way to turn attributes on and off individually
            # instead of defining a font for each combination
            self.bold_font = tk_font.Font(**self.font.configure())
            self.bold_mono_font = tk_font.Font(**self.font.configure())
            self.italic_font = tk_font.Font(**self.font.configure())
            self.mono_font = tk_font.Font(**self.font.configure())
            self.normal_font = tk_font.Font(**self.font.configure())
            self.underline_font = tk_font.Font(**self.font.configure())
            self.url_font = tk_font.Font(**self.font.configure())

            self.bold_font.configure(weight="bold")
            self.bold_mono_font.configure(family="Courier New", weight="bold")
            self.italic_font.configure(slant="italic")
            self.mono_font.configure(family="Courier New")
            self.underline_font.configure(underline=1)
            self.url_font.configure(family="Courier New")

            self.tag_configure("bold", font=self.bold_font)
            self.tag_configure("bold_mono", font=self.bold_mono_font)
            self.tag_configure("italic", font=self.italic_font)
            self.tag_configure("underline", font=self.underline_font)
            self.tag_configure("mono", font=self.mono_font)
            self.tag_configure("normal", font=self.normal_font)
            self.tag_configure("url", font=self.url_font, foreground="blue")
            self.tag_configure(
                "reverse", font=self.normal_font, background="white", foreground="black")

    # Another online discovery for auto-hiding scrollbars in a text widget
    class AutoHideScrollbar(ttk.Scrollbar):
        def set(self, low, high):
            if float(low) <= 0 and float(high) >= 1.0:
                try: self.tk.call("grid", "remove", self)
                except: pass
            else:
                try: self.grid()
                except: pass
            ttk.Scrollbar.set(self, low, high)

    try:
        result = parse_configuration_tex(
            config_tex, search_list, width, valid_only, show_urls)
    except ConfigurationLoadError:
        mb.showerror(
            "Configuration.tex Error",
            "Could not find/open Configuration.tex at: {}".format(
                config_tex or "No Path Specified"
            ))
        return

    pad_pixels = 30
    info_window = tk.Toplevel()
    info_window.withdraw()  # Hide it until we're ready to draw
    info_window.update_idletasks()
    title = " -> ".join([x for x in search_list if not x == "*"])
    info_window.title('"{}" Info'.format(title))  # set title to search path
    # Create and place the scrollbar
    vsb = AutoHideScrollbar(info_window)
    vsb.grid(row=0, column=1, sticky="ns")
    # Create, place, and color the text widget
    text = FormattedText(
        info_window,
        yscrollcommand=vsb.set,
        highlightthickness=0,
        borderwidth=5,
        wrap=tk.WORD,
        font=font
    )
    text.grid(row=0, column=0, sticky="nsew")
    text.configure(bg=bg, fg=fg)
    # Set up the scroll command
    vsb.config(command=text.yview)
    # Allow the text widget to expand
    info_window.rowconfigure(0, weight=1)
    info_window.columnconfigure(0, weight=1)

    # Madness to get the titlebar height
    offset_y = 0
    if os.name == "nt":
        import ctypes
        try:  # >= win 8.1
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except:  # win 8.0 or less
            ctypes.windll.user32.SetProcessDPIAware()
    offset_y = int(info_window.geometry().rsplit('+', 1)[-1])
    bar_height = info_window.winfo_rooty() - offset_y

    # very basic error checking and display
    # length of zero means no result was found
    # length of one is an error message
    if result:
        style = "normal"

        in_escape = False
        esc_code = ""

        # uncomment print line to get output in console while debugging
        # print(result)
        out = ""  # build output string between esc seq one char at a time
        max_w = line_w = 0  # keep track of the longest line we have
        total_h = line_h = 0

        def dump_out(out, style):
            text.insert("end", out, style)
            line_w = getattr(text, style+"_font").measure(out)
            line_h = getattr(text, style+"_font").metrics("linespace")
            return (line_w, line_h)

        for c in result:
            # quick hack to decode the escape seqs ret from the parse
            # only including encodings needed for Configuration.tex and a
            # few others for now
            if in_escape:
                esc_code += c
                if c == "m":  # end of esc code
                    # should be using these to turn font attributes on and off
                    # but for now just have a style defined for current needs
                    if esc_code == '[0m':
                        style = "normal"
                    if esc_code == "[10m": # switch to default family
                        style = "normal"
                    if esc_code == '[1m': # bold on
                        if style == "mono":
                            style = "bold_mono" # until a better method is found
                        else:
                            style = "bold"
                    if esc_code == "[22m": # bold off
                        if style == "bold_mono":
                            style = "mono"
                        else:
                            style = "normal"
                    if esc_code == '[3m': # italic on
                        style = "italic"
                    # [23m italic off
                    if esc_code == "[4m": # underline on
                        style = "underline"
                    # [24m underline off
                    if esc_code == '[11m': # switch to mono family
                        style = "mono"
                    if esc_code == '[7m': # reverse on
                        style = "reverse"
                    # [27m not reverse
                    if esc_code == '[34m': # foreground blue
                        if show_urls:
                            style = "url"
                        else:
                            style = "mono"
                    out = ""  # found valid esc - clear out
                    esc_code = ""
                    in_escape = False
                continue
            if c == '\x1b':
                # found end of one esc and start of another
                # dump formatted output to window
                # and start over
                w, h = dump_out(out, style)
                line_w += w
                line_h = max(line_h, h)
                out = ""
                in_escape = True
                continue
            # Check for a newline and dump the output
            if c == "\n":
                w, h = dump_out(out, style)
                line_w += w
                line_h = max(line_h, h)
                max_w = max(line_w, max_w)
                total_h += line_h
                line_w = 0  # reset the line width counter
                out = ""
            out += c
        if out:
            w, h = dump_out(out, style)
            line_w += w
            line_h = max(line_h, h)
            max_w = max(line_w, max_w)
            total_h += line_h
    else:
        # Don't show the window - instead, show an error
        # that nothing was found
        info_window.destroy()
        mb.showerror(
            "Info Not Found",
            "No info found for: \"{}\"".format(title))
        return

    # Fit the line width to our max line length topping out at our width value
    # Adjust the width to a fancy mess
    max_mono_w = text.mono_font.measure("-"*width)
    width      = min((max_w, max_mono_w))+pad_pixels
    height     = total_h+bar_height+5
    # Calculate our x,y based on the calling window - attempting to center the info window
    # horizontally, but only lowering it by 30 pixels
    info_window.geometry("{}x{}+{}+{}".format(
        width,
        height,
        int(calling_window.winfo_rootx()+(calling_window.winfo_width()/2)-(width/2)),
        int(calling_window.winfo_rooty()+30)
    ))
    info_window.deiconify()
    # text.configure(width=final_w)
    # Adjust the height to the line count
    # text.configure(height=int(text.index("end-1c").split(".")[0])+1) # Add an extra line for looks
    # Set the text to read-only
    text.configure(state="disabled")
    # Ensure we return a reference to the window for updating colors and stack order checks
    return info_window


def parse_configuration_tex(config_file, search_list, width, valid_only, show_urls):
    # valid_only: True - return only the valid config.plist options for the search term &
    # return an empty list if no valid options found
    #     False: return whole text of section
    #
    # show_urls: True - return full url of links in the text
    #     False - return only link text with no url
    try:
        config = open(config_file, "r")
    except:
        raise ConfigurationLoadError

    result = []
    search_len = len(search_list)
    if search_len == 0:  # we shouldn't get here, but just in case
        return result

    search_terms = ["\\section{"]
    search_terms[0] += search_list[0]
    text_search = search_list[search_len - 1] # ultimately looking for last item

    # set the search terms based on selected position
    if search_len == 1:
        # we're done
        pass
    elif search_len == 2:
        search_terms.append("\\subsection{Properties")
        search_terms.append("texttt{" + text_search + "}\\")
    elif search_len == 3:
        if search_list[0] == "NVRAM": # look for value in Introduction
            search_terms.append("\\subsection{Introduction")
            search_terms.append("texttt{" + text_search + "}")
        else:
            search_terms.append(
                "\\subsection{" + search_list[1] + " Properties")
            search_terms.append("texttt{" + text_search + "}\\")
    elif search_len == 4:
        item_zero = search_list[0]
        sub_search = "\\subsection{"
        if item_zero == "NVRAM": # look for UUID:term in Introduction
            sub_search = "\\subsection{Introduction"
            text_search = search_list[2]
            text_search += ":"
            text_search += search_list[3]
            text_search += "}"
        elif item_zero == "DeviceProperties": # look in Common
            sub_search += "Common"
            text_search += "}"
        elif item_zero == "Misc": # Entry Properties or subsub
            if len(search_list[2]) < 3:
                sub_search += "Entry Properties"
            else:
                sub_search = "\\subsubsection{"
                sub_search += search_list[1]
            text_search += "}"
        else:
            sub_search += search_list[1]
            sub_search += " Properties"
            text_search += "}\\"
        search_terms.append(sub_search)
        search_terms.append("texttt{" + text_search)
    elif search_len == 5:
        sub_search = "\\subsubsection{"
        sub_search += search_list[1]
        search_terms.append(sub_search)
        search_terms.append("texttt{" + text_search)

    # keep a set of prefixes that would break us out of our search
    disallowed = set()
    # move down the Configuration.tex to the section we want
    for i in range(0, len(search_terms)):
        while True:
            line = config.readline()
            if not line:
                return result
            line = line.strip()
            # Check for disallowed
            if line.startswith(tuple(disallowed)) and (search_terms[0] != "\\section{NVRAM" or not "\\label{nvram" in line):
                # We've broken out of our current scope - bail
                return result
            if search_terms[i] in line:
                # Make sure parent search prefixes get added
                # to the disallowed set
                if not search_terms[i].startswith("texttt{"):
                    # Retain the prefix as needed
                    disallowed.add(search_terms[i].split("{")[0]+"{")
                break

    align = False
    itemize = 0
    not_first_item = False
    in_listing = False
    enum = 0
    columns = 0
    lines_between_valid = 0
    last_line_ended_in_colon = False
    last_line_had_forced_return = False
    last_line_ended_in_return = False
    last_line_was_blank = False

    while True:
        # track document state & preprocess line before parsing
        line = config.readline()
        if not line:
            break
        line = line.strip()
        if line.startswith("%"): # skip comments
            continue
        if "\\subsection{Introduction}" in line:
            continue
        if "\\begin{tabular}" in line:
            result.append("\x1b[11m")
            for c in line:
                if c == "c":
                    columns += 1
            continue
        if "\\begin(align*}" in line:
            align = True
            continue
        if "\\end{align*}}" in line:
            align = False
            continue
        if "\\begin{itemize}" in line:
            itemize += 1
            continue
        if "\\begin{enumerate}" in line:
            enum += 1
            continue
        if "\\begin{lstlisting}" in line:
            in_listing = True
            result.append("\n\x1b[11m")
            result.append("-"*width)
            result.append("\n")
            continue
        if "\\begin{" in line: # ignore other begins
            continue
        if "\\mbox" in line:
            continue
        if "\\end{tabular}" in line:
            result.append("\x1b[10m")
            columns = 0
            continue
        if "\\end{itemize}" in line:
            itemize -= 1
            if itemize == 0 and enum == 0:
                not_first_item = False
            continue
        if "\\end{enumerate}" in line:
            enum = 0
            if itemize == 0:
                not_first_item = False
            continue
        if "\\end{lstlisting}" in line:
            in_listing = False
            result.append("-"*width)
            result.append("\x1b[10m\n")
            continue
        if "\\end{" in line: # ignore other ends
            continue
        if "\\item" in line:
            if itemize == 0 and enum == 0:
                break # skip line, not itemizing, shouldn't get here
            else:
                if not_first_item or not last_line_ended_in_return:
                    # newline before this item
                    result.append("\n")
                not_first_item = True
                if itemize == 0: # in enum
                    if search_len == 1: # first level enumerate, use numeric
                        replace_str = str(enum) + "."
                    else: # use alpha
                        replace_str = "(" + chr(96 + enum) + ")"
                    line = line.replace("\\item", replace_str)
                    enum += 1
                elif itemize == 1: # first level item
                    line = line.replace("\\item", u"\u2022")
                else:
                    line = line.replace("\\item", "-")
                # fix indenting
                line = "    "*itemize + line
                if enum != 0:
                    line = "    " + line
        else:
            if itemize > 0 or enum > 0: # inside multi line item
                if last_line_had_forced_return:
                    line = "    "*itemize + line
                    line = "       " + line # indent
        if "section{" in line: # stop when next section is found
# let's try only checking for "section{" instead of 3 checks
#        if "\\section{" in line or "\\subsection{" in line or "\\subsubsection{" in line:
            # reached end of current section
            break

        if line.strip() == "": # blank line, need linefeed, maybe two, maybe none
            if last_line_ended_in_colon:
                parsed_line = "\n"
            else:
                if last_line_was_blank:  # skip this blank line
                    continue
                else:
                    parsed_line = "\n\n"
            last_line_was_blank = True
        else:
            last_line_was_blank = False
            parsed_line = parse_line(line, columns, width,
                                     align, valid_only, show_urls)
            if len(parsed_line) == 0:
                continue
            # post process line
            last_line_had_forced_return = False
            last_line_ended_in_colon = False
            if parsed_line.endswith("\n"):
                last_line_had_forced_return = True
            elif parsed_line.endswith(":"):
                parsed_line += "\n"
                if not_first_item:
                    # treat as forced return instead
                    last_line_had_forced_return = True
                else:
                    last_line_ended_in_colon = True
            else:
                parsed_line += " "  # add space for next word

        if parsed_line.endswith("\n"):
            # slightly different use than last_line_had_forced_return
            last_line_ended_in_return = True
        else:
            last_line_ended_in_return = False
        if valid_only: # we only want to return valid plist options for the field
            if itemize > 0:
                if "---" in line:
                    if lines_between_valid < 10:
                        result.append(parsed_line)
            else:
                if len(result) > 0:
                    lines_between_valid += 1
        else:
            result.append(parsed_line)
            if in_listing:
                result.append("\n")
    # Join the result into a single string and remove
    # leading, trailing, and excessive newlines
    # result = re.sub(r"\n{2,}",r"\n\n","".join(result))
    # return result.strip("\n")

    # leave all excess internal newlines for now for easier debugging
    return "".join(result).strip("\n")

    # return re.sub("\n{2,}", "\n\n", "".join(result)).strip("\n")


def parse_line(line, columns, width, align, valid_only, show_urls):
    ret = ""
    build_key = False
    key = ""
    col_width = 0
    if columns > 0:
        col_width = int(width / (columns + 1))
    ignore = False
    col_contents_len = 0
    line = line.rstrip()
    for c in line:
        if build_key:
            if c in "{[":
                build_key = False
                if not valid_only:
                    if key == "text":
                        ret += "\x1b[0m"
                    elif key == "textit":
                        ret += "\x1b[3m"
                    elif key == "textbf":
                        ret += "\x1b[1m"
                    elif key == "emph":
                        ret += "\x1b[3m"
                    elif key == "texttt":
                        ret += "\x1b[11m"
                    elif key == "href":
                        if show_urls:
                            ret += "\x1b[34m"
                        else:
                            ignore = True
                    else:
                        ignore = True
                if key != "href":
                    key = ""
            elif c in " ,()\\0123456789$&":
                build_key = False
                ret += special_char(key)
                col_contents_len += 1
                if c in ",()0123456789$":
                    ret += c
                if c == "\\":
                    if len(key) > 0:
                        build_key = True
                key = ""
            elif c in "_^#":
                build_key = False
                ret += c
                col_contents_len += 1
                key = ""
            else:
                key += c
        else:
            if c == "\\":
                build_key = True
            elif c in "}]":
                if not ignore:
                    if not valid_only:
                        if columns > 0:
                            ret += "\x1b[22m"
                        else:
                            ret += "\x1b[0m"
                        if key == "href":
                            # ret += " "
                            key = ""
                        elif c == "]":
                            ret += "]"
                ignore = False
            elif c == "{":
                if not valid_only:
                    ret += "\x1b[11m"
            elif c == "&":
                if columns > 0:
                    pad = col_width - col_contents_len - 1
                    if pad > 0:
                        ret += " "*pad
                    col_contents_len = 0
                    ret += "|"
                else:
                    if not align:
                        ret += "&"
            else:
                if not ignore:
                    ret += c
                    col_contents_len += 1

    if len(key) > 0:
        ret += special_char(key)

    if not valid_only:
        if key == "tightlist":
            ret = ""
        else:
            if key == "hline":
                ret = "-"*(width-4)
                ret += "\n"
        if line.endswith("\\\\"):
            ret += "\n"
    return ret


def special_char(key):
    if key == "kappa":
        return u"\u03f0"
    elif key == "lambda":
        return u"\u03bb"
    elif key == "mu":
        return u"\u03bc"
    elif key == "alpha":
        return u"\u03b1"
    elif key == "beta":
        return u"\u03b2"
    elif key == "gamma":
        return u"\u03b3"
    elif key == "leq":
        return u"\u2264"
    elif key == "cdot":
        return u"\u00b7"
    elif key == "in":
        return u"\u220a"
    elif key == "infty":
        return u"\u221e"
    elif key == "textbackslash":
        return "\\"
    elif key == "hline":
        return u"\u200b"
    else:
        return " "
