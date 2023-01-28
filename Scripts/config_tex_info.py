import os, sys
import tkinter as tk

def display_info_window(config_tex, search_list, width, valid_only, show_urls):
    # probably a simpler way to set up the formatted text
    # but found this format online and it works for now
    class FormattedText(tk.Text):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            from tkinter import font as tkFont
            default_font = tkFont.nametofont(self.cget("font"))

            bold_font = tkFont.Font(**default_font.configure())
            italic_font = tkFont.Font(**default_font.configure())
            normal_font = tkFont.Font(**default_font.configure())
            underline_font = tkFont.Font(**default_font.configure())

            bold_font.configure(weight="bold")
            italic_font.configure(slant="italic")
            underline_font.configure(underline=1)
            normal_font.configure(weight="normal", slant="roman")

            self.tag_configure("bold", font=bold_font)
            self.tag_configure("italic", font=italic_font)
            self.tag_configure("underline", font=underline_font)
            self.tag_configure("normal", font=normal_font)
            self.tag_configure(
                "inverse", background="white", foreground="black")

    result = parse_configuration_tex(config_tex, search_list, width, valid_only, show_urls)

    info_window = tk.Toplevel()
    info_window.title(" > ".join(search_list)) # set title to search path
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
        text.insert("end", result[0], "inverse")
        return

    style = "normal"

    in_escape = False
    for line in result:
        out = "" # build output string between esc seq one char at a time
        for c in line:
            # quick hack to decode the escape seqs ret from the parse
            # can improve this
            if in_escape:
                if c == '0':
                    style = "normal"
                if c == '1':
                    style = "bold"
                if c == '3':
                    style = "italic"
                if c == '4':
                    style = "underline"
                if c == '7':
                    style = "inverse"
                if c == 'm':
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
        text.insert("end", out, style) # reached end of line, dump out to window

def parse_configuration_tex(config_file, search_list, width, valid_only, show_urls):
    try:
        config = open(config_file, "r")
    except OSError:
        return ["Could not find/open Configuration.tex at " + config_file]

    result = []
    align = False
    sub_search = "\\subsection{"

    match len(search_list) - 1:
        case 0:
            pass
        case 1:
            sub_search += "Properties"
        case 2 | 3:
            match search_list[0]:
                case "NVRAM":
                    sub_search += "Introduction"
                case "DeviceProperties":
                    sub_search += "Common"
                case "Misc":
                    if len(search_list) < 4:
                        sub_search += search_list[1]
                        sub_search += " Properties"
                    else:
                        sub_search += "Entry Properties"
                case _:
                    sub_search += search_list[1]
                    sub_search += " Properties"
        case _:
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
        if "\\item" in line and ( itemize == 0 and enum == 0 ):
            break
        if "\\subsection{" in line or "\\section{" in line:
            break
        parsed_line = parse_line(line, columns, width, align, valid_only, show_urls)
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
        col_width = int(width / ( columns + 1 ))
    ignore = False
    col_contents_len = 0
    line = line.rstrip()
    for c in line:
        if build_key:
            match c:
                case c if c in "{[":
                    build_key = False
                    if not valid_only:
                        match key:
                            case "text":
                                ret += "\x1b[0m"
                            case "textit":
                                ret += "\x1b[3m"
                            case "textbf":
                                ret += "\x1b[1m"
                            case "emph":
                                ret += "\x1b[7m"
                            case "texttt":
                                ret += "\x1b[4m"
                            case "href":
                                if show_urls:
                                    ret += "\x1b[34m"
                                else:
                                    ignore = True
                            case _:
                                ignore = True
                    if key != "href":
                        key = ""
                case c if c in " ,()\\0123456789$&":
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
                case c if c in "_^#":
                    build_key = False
                    ret += c
                    col_contents_len += 1
                    key = ""
                case _:
                    key += c
        else:
            match c:
                case "\\":
                    build_key = True
                case c if c in "}]":
                    if not ignore:
                        if not valid_only:
                            ret += "\x1b[0m"
                            if key == "href":
                                ret += " "
                                key = ""
                            elif c == "]":
                                ret += "]"
                    ignore = False
                case "{":
                    if not valid_only:
                        ret += "\x1b[4m"
                case "&":
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
                case _:
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
    match key:
        case "kappa":
            return "\u03f0"
        case "lambda":
            return "\u03bb"
        case "mu":
            return "\u03bc"
        case "alpha":
            return "\u03b1"
        case "beta":
            return "\u03b2"
        case "gamma":
            return "\u03b3"
        case "leq":
            return "\u2264"
        case "cdot":
            return "\u00b7"
        case "in":
            return "\u220a"
        case "infty":
            return "\u221e"
        case "textbackslash":
            return "\\"
        case "hline":
            return "\u200b"
        case _:
            return " "
