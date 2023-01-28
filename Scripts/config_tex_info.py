import os
import sys
if sys.version_info.major == 3:
    import tkinter as tk, tkinter.font as tk_font
else:
    import Tkinter as tk, tkFont as tk_font



def display_info_window(config_tex, search_list, width, valid_only, show_urls):
    # probably a simpler way to set up the formatted text
    # but found this format online and it works for now
    class FormattedText(tk.Text):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            default_font = tk_font.nametofont(self.cget("font"))

            bold_font = tk_font.Font(**default_font.configure())
            italic_font = tk_font.Font(**default_font.configure())
            mono_font = tk_font.Font(**default_font.configure())
            normal_font = tk_font.Font(**default_font.configure())
            underline_font = tk_font.Font(**default_font.configure())

            bold_font.configure(weight="bold")
            italic_font.configure(slant="italic")
            mono_font.configure(family="Courier New")
            underline_font.configure(underline=1)

            self.tag_configure("bold", font=bold_font)
            self.tag_configure("italic", font=italic_font)
            self.tag_configure("underline", font=underline_font)
            self.tag_configure("mono", font=mono_font)
            self.tag_configure("normal", font=normal_font)
            self.tag_configure(
                "reverse", font=normal_font, background="white", foreground="black")

    result = parse_configuration_tex(
        config_tex, search_list, width, valid_only, show_urls)

    info_window = tk.Toplevel()
    info_window.title(" > ".join(search_list))  # set title to search path
    info_win_height = len(result) + 1  # size info_window to the search result
    if info_win_height > 40:
        info_win_height = 40
    text = FormattedText(info_window, width=width, height=info_win_height)
    text.pack(fill="both", expand=True)

    # very basic error checking and display
    # length of zero means no result was found
    # length of one is an error message
    if len(result) == 0:
        text.insert("end", "no info found for: ", "bold")
        text.insert("end", search_list, "bold")
        return
    if len(result) == 1:
        text.insert("end", result[0], "reverse")
        return

    style = "normal"

    in_escape = False
    for line in result:
        out = ""  # build output string between esc seq one char at a time
        for c in line:
            # quick hack to decode the escape seqs ret from the parse
            # can improve this
            if in_escape:
                if c == 'N':
                    style = "normal"
                if c == 'B':
                    style = "bold"
                if c == 'I':
                    style = "italic"
                if c == 'U':
                    style = "mono"
                if c == 'R':
                    style = "reverse"
                out = ""
                in_escape = False
                continue
            if c == '\x1b':
                # found end of one esc and start of another
                # dump formatted output to window
                # and start over
                text.insert("end", out, style)
                out = ""
                in_escape = True
                continue
            out += c
        # reached end of line, dump out to window
        text.insert("end", out, style)


def parse_configuration_tex(config_file, search_list, width, valid_only, show_urls):
    try:
        config = open(config_file, "r")
    except OSError:
        return ["Could not find/open Configuration.tex at " + config_file]

    result = []
    align = False
    sub_search = "\\subsection{"

    search_len = len(search_list) - 1
    if search_len == 1:
        sub_search += "Properties"
    elif search_len == 2 or search_len == 3:
        item_zero = search_list[0]
        if item_zero == "NVRAM":
            sub_search += "Introduction"
        elif item_zero == "DeviceProperties":
            sub_search += "Common"
        elif item_zero == "Misc":
            if len(search_list) < 4:
                sub_search += search_list[1]
                sub_search += " Properties"
            else:
                sub_search += "Entry Properties"
        else:
            sub_search += search_list[1]
            sub_search += " Properties"
    elif search_len != 0:
        return result

    sec_search = "\\section{"
    sec_search += search_list[0]

    while True:
        line = config.readline()
        if not line:
            return result
        if sec_search in line:
            break

    if len(search_list) != 1:
        while True:
            line = config.readline()
            if not line:
                return result
            if sub_search in line:
                break
        text_search = "texttt{"
        if search_list[0] == "NVRAM" and len(search_list) > 2:
            text_search += search_list[2]
            if len(search_list) == 4:
                text_search += ":"
                text_search += search_list[3]
        elif search_list[0] == "DeviceProperties" and len(search_list) == 4:
            text_search += search_list[3]
        else:
            text_search += search_list[len(search_list) - 1]
            text_search += "}\\"

        while True:
            line = config.readline()
            if not line:
                return result
            if text_search in line:
                break

    itemize = 0
    enum = 0
    columns = 0
    lines_between_valid = 0

    while True:
        line = config.readline()
        if not line:
            break
        if "\\subsection{Introduction}" in line:
            continue
        if "\\begin{tabular}" in line:
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
        if "\\mbox" in line:
            continue
        if "\\end{tabular}" in line:
            columns = 0
            continue
        if "\\end{itemize}" in line:
            itemize -= 1
            continue
        if "\\end{enumerate}" in line:
            enum -= 1
            continue
        if "\\end{" in line:
            continue
        if "\\item" in line and (itemize == 0 and enum == 0):
            break
        if "\\subsection{" in line or "\\section{" in line:
            break
        parsed_line = parse_line(line, columns, width,
                                 align, valid_only, show_urls)
        if valid_only:
            if itemize > 0:
                if "---" in line:
                    if lines_between_valid < 10:
                        result.append(parsed_line)
            else:
                if len(result) > 0:
                    lines_between_valid += 1
        else:
            if len(parsed_line) != 0:
                result.append(parsed_line)
    return result


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
                        ret += "\x1bN"
                    elif key == "textit":
                        ret += "\x1bI"
                    elif key == "textbf":
                        ret += "\x1bB"
                    elif key == "emph":
                        ret += "\x1bI"
                    elif key == "texttt":
                        ret += "\x1bU"
                    elif key == "href":
                        if show_urls:
                            ret += "\x1bL"
                        else:
                            ignore = True
                    else:
                        ignore = True
                if key != "href":
                    key = ""
            elif c in " ,()\\0123456789$&":
                build_key = False
                if key == "item":
                    if not valid_only:
                        ret += "•"
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
                        ret += "\x1bN"
                        if key == "href":
                            ret += " "
                            key = ""
                        elif c == "]":
                            ret += "]"
                ignore = False
            elif c == "{":
                if not valid_only:
                    ret += "\x1bU"
            elif c == "&":
                if columns > 0:
                    pad = col_width - col_contents_len - 1
                    if pad > 0:
                        for _ in range(pad):
                            ret += " "
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
        if key == "tightlint":
            ret = ""
        else:
            if key == "hline":
                ret = ""
                for _ in range(width - 4):
                    ret += "-"
            ret += "\n"
    return ret


def special_char(key):
    if key == "kappa":
        return "\u03f0"
    elif key == "lambda":
        return "\u03bb"
    elif key == "mu":
        return "\u03bc"
    elif key == "alpha":
        return "\u03b1"
    elif key == "beta":
        return "\u03b2"
    elif key == "gamma":
        return "\u03b3"
    elif key == "leq":
        return "\u2264"
    elif key == "cdot":
        return "\u00b7"
    elif key == "in":
        return "\u220a"
    elif key == "infty":
        return "\u221e"
    elif key == "textbackslash":
        return "\\"
    elif key == "hline":
        return "\u200b"
    else:
        return " "
