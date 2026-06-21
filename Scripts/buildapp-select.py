#!/usr/bin/env python
import sys, os, plist, shutil, tempfile, subprocess, argparse, time
if 2/3==0: input = raw_input

min_tk_version = {
    "11":"8.6"
}
preserve_paths = (
    "Contents/MacOS/Scripts/settings.json",
    "Contents/MacOS/Configuration.tex"
)

def _decode(value, encoding="utf-8", errors="ignore"):
        # Helper method to only decode if bytes type
        if sys.version_info >= (3,0) and isinstance(value, bytes):
            return value.decode(encoding,errors)
        return value

def get_os_version():
    p = subprocess.Popen(["sw_vers","-productVersion"], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    c = p.communicate()
    return _decode(c[0]).strip()

def get_min_tk_version():
    curr_os = get_os_version()
    curr_min = None
    for os_ver in sorted(min_tk_version):
        if os_ver <= curr_os:
            curr_min = min_tk_version[os_ver]
    return curr_min

def gather_python(
    min_only_suggestion=True,
    test_load_tk=True,
    path_list=None
):
    # Let's find the available python installs, check their tk version
    # and try to pick the latest one supported - or throw an error if
    # we're on macOS 11.x+ and using Tk 8.5 or older.
    pypaths = (path_list if isinstance(path_list,(list,tuple)) else [path_list]) if path_list else []
    envpaths = []
    if not pypaths:
        for py in ("python","python3"):
            p = subprocess.Popen(["which","-a",py], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            c = p.communicate()
            binpath = "/usr/bin/{}".format(py)
            envpath = "/usr/bin/env {}".format(py)
            avail = []
            for x in _decode(c[0]).split("\n"):
                if len(x) and not x in pypaths and not x == binpath and not x in avail:
                    avail.append(x)
            if os.path.exists(binpath):
                avail.insert(0,binpath)
            if len(avail): # Only add paths that we found and verified
                pypaths.extend(avail)
                if not envpath in envpaths:
                    envpaths.append((envpath,None,None))
    py_tk = []
    py_tk_failed = []
    for path in pypaths:
        # Get the version of python first
        path = path.strip()
        print(" - Checking: {}".format(path))
        if not os.path.isfile(path):
            print(" --> Doesn't exist, skipping...")
            continue
        if path == "/usr/bin/python3":
            # Check if we're running 10.15 or newer - and try running "xcode-select -p"
            # If it errors - we need to skip this path - as it's just a stub.
            if get_os_version() >= "10.15": # At least Catalina
                p = subprocess.Popen(["xcode-select","-p"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                p.communicate()
                if p.returncode != 0:
                    print(" --> Just a stub, skipping...")
                    continue # Not setup - skip
        p = subprocess.Popen([path,"-V"], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        c = p.communicate()
        pv = (_decode(c[0]) + _decode(c[1])).strip().split(" ")[-1]
        if not len(pv):
            print(" --> Invalid version - skipping...")
            continue # Bad version?
        print(" --> Located Python v{}".format(pv))
        tk_string = "Tkinter" if pv.startswith("2.") else "tkinter"
        command = "import {} as tk; print(tk.Tcl().call('info','patchlevel'))".format(tk_string)
        p = subprocess.Popen([path,"-c",command], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        c = p.communicate()
        tk = _decode(c[0]).strip()
        print(" --> Located {} v{}".format(tk_string,tk))
        if test_load_tk:
            command = "import {} as tk; tk.Tk()".format(tk_string)
            p = subprocess.Popen([path,"-c",command], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            t = time.time()
            printed = False
            while True:
                time_elapsed = time.time() - t
                if time_elapsed >= 5 and not printed:
                    print(" !! Check for any dialogs asking to reopen Python windows !!")
                    print(" !! Choosing to \"Reopen\" may prevent mulitple prompts !!")
                    printed = True
                if p.poll() is None:
                    # Still waiting...
                    time.sleep(0.02)
                else:
                    # Got a return value - break
                    break
            if p.returncode != 0:
                # Failed to run correctly - retain it
                py_tk_failed.append((path,pv,tk))
                print(" --> {} failed to load - skipping...".format(tk_string))
                print("   - You may see a crash log displayed due to {} failing -".format(tk_string))
                continue
        py_tk.append((path,pv,tk))
    min_tk = get_min_tk_version()
    if min_tk and not min_only_suggestion:
        return ([x for x in py_tk if x[-1] >= min_tk]+envpaths,py_tk_failed)
    return (py_tk+envpaths,py_tk_failed)

def select_py(
    py_versions,
    min_tk,
    pt_current,
    py_tk_failed
):
    current = next((x[0] for x in py_versions if x[0] == pt_current),None)
    while True:
        output = ""
        if py_tk_failed:
            output = " - Omitted Python Versions Due To Unsupported Tk -\n\n"
            for x in py_tk_failed:
                output += "- {}{}{}{}\n".format(
                    x[0],
                    " {}".format(x[1]) if x[1] else "",
                    " - tk {}".format(x[2]) if x[2] else "",
                    "" if min_tk is None or x[2] is None or x[2] >= min_tk else " ({}+ recommended)".format(min_tk)
                )
            output += "\n"
        output += " - Currently Available Python Versions -\n\n"
        for i,x in enumerate(py_versions,1):
            output += "{}. {}{}{}{}\n".format(
                i,
                x[0],
                " {}".format(x[1]) if x[1] else "",
                " - tk {}".format(x[2]) if x[2] else "",
                "" if min_tk is None or x[2] is None or x[2] >= min_tk else " ({}+ recommended)".format(min_tk),
            )
        output += "\n"
        if current:
            output += "C. Current ({})\n".format(current)
        output += "Q. Quit\n"
        # Gather our width and height and resize the window if needed
        w = max((len(x) for x in output.split("\n")))
        h = len(output.split("\n"))+1
        print('\033[8;{};{}t'.format(h if h > 24 else 24, w if w > 80 else 80))
        os.system("clear")
        print(output)
        menu = input("Please select the python version to use{}:  ".format(" (default is C)" if current else "")).lower()
        if not len(menu):
            if current:
                menu = "c"
            else:
                continue
        if menu == "q":
            exit()
        if menu == "c" and current:
            return next((x for x in py_versions if x[0] == current))
        try:
            menu = int(menu)
        except:
            continue
        if not 0 < menu <= len(py_versions):
            continue
        return py_versions[menu-1]

def main(
    use_current=False,
    path_list=None,
    min_only_suggestion=True,
    test_load_tk=True,
    app_path=None,
    no_verify=False
):
    # Let's check for an existing app - remove it if it exists,
    # then create and format a new bundle
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__),"../"))
    temp = None
    pt_current = None
    # Default to ../ProperTree.app, or use a user-provided output
    # folder.
    if app_path is None:
        app_path = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(__file__)),"../","ProperTree.app"))
    if not app_path.lower().endswith(".app"):
        # If the path doesn't end in .app, append ProperTree.app
        # to it.
        app_path = os.path.join(app_path,"ProperTree.app")
    scripts_path   = os.path.join(app_path,"Contents","MacOS","Scripts")
    resources_path = os.path.join(app_path,"Contents","Resources")
    command_path   = os.path.join(app_path,"Contents","MacOS","ProperTree.command")
    info_path      = os.path.join(app_path,"Contents","Info.plist")
    if os.path.exists(command_path):
        # Let's try to read the shebang
        try:
            with open(command_path,"r") as f:
                pt = f.read().split("\n")
                if pt[0].startswith("#!"):
                    # Got a shebang - save it
                    pt_current = pt[0][2:].strip()
        except:
            pass
    if use_current: # Override any passed path_list with our current if needed
        if not pt_current:
            print(" - No current ProperTree python version detected!  Aborting!")
            exit(1)
        path_list = pt_current
    if no_verify:
        if not path_list:
            print(" - --no-verify requires a python path via -p or -c!  Aborting!")
            exit(1)
        pypath = path_list[0] if isinstance(path_list,(list,tuple)) else path_list
        py_version = (pypath,"","")
    else:
        print("Locating python versions...")
        py_versions,py_tk_failed = gather_python(
            min_only_suggestion=min_only_suggestion,
            test_load_tk=test_load_tk,
            path_list=path_list
        )
        if not py_versions:
            print(" - No python installs with functioning tk found!  Aborting!")
            exit(1)
        min_tk = get_min_tk_version()
        py_version = py_versions[0] if len(py_versions) == 1 else select_py(py_versions,min_tk,pt_current,py_tk_failed)
    os.system("clear")
    print("Building .app with the following python install:")
    print(" - {}".format(py_version[0]))
    print(" --> {}".format(py_version[1]))
    print(" --> tk {}".format(py_version[2]))
    pypath = py_version[0]
    print("Checking for existing {}...".format(app_path))
    if os.path.isfile(app_path):
        print(" - Found, but is a file - aborting...")
        exit(1)
    # Populate our preserved paths to reflect our potentially custom app path
    app_preserve_paths = [os.path.join(app_path,path) for path in preserve_paths]
    if os.path.isdir(app_path):
        print(" - Found, removing...")
        for path in app_preserve_paths:
            if os.path.exists(path):
                print(" --> Found {} - preserving...".format(os.path.basename(path)))
                temp = temp or tempfile.mkdtemp()
                shutil.copy(path,os.path.join(temp,os.path.basename(path)))
        shutil.rmtree(app_path)
    # Make the directory structure
    print("Creating bundle structure...")
    os.makedirs(os.path.join(app_path,"Contents","MacOS","Scripts"))
    os.makedirs(os.path.join(app_path,"Contents","Resources"))
    print("Copying scripts...")
    print(" - ProperTree.py -> ProperTree.command")
    with open(os.path.join(parent_dir,"ProperTree.py"),"r") as f:
        ptcom = f.read().split("\n")
    if ptcom[0].startswith("#!"):
        # Got a shebang - remove it
        ptcom.pop(0)
    # Set the new shebang
    ptcom.insert(0,"#!{}".format(pypath))
    with open(command_path,"w") as f:
        f.write("\n".join(ptcom))
    # chmod +x
    p = subprocess.Popen(["chmod","+x",command_path], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.communicate()
    # Copy everything else
    for x in os.listdir(os.path.join(parent_dir,"Scripts")):
        if x.startswith(".") or not x.lower().endswith((".py",".plist",".icns","version.json")):
            continue
        print(" - "+x)
        target = resources_path if x.lower().endswith(".icns") else scripts_path
        shutil.copy(os.path.join(parent_dir,"Scripts",x),target)
    print("Building Info.plist...")
    info = {
        "CFBundleShortVersionString": "0.0", 
        "CFBundleSignature": "????", 
        "CFBundleInfoDictionaryVersion": "0.0", 
        "CFBundleIconFile": "icon", 
        "NSHumanReadableCopyright": "Copyright 2019 CorpNewt", 
        "CFBundleIconFile": "shortcut.icns",
        "CFBundleIdentifier": "com.corpnewt.ProperTree", 
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Property List", 
                "CFBundleTypeRole": "Viewer", 
                "CFBundleTypeIconFile": "plist", 
                "CFBundleTypeExtensions": [
                    "plist"
                ]
            }
        ], 
        "CFBundleDevelopmentRegion": "English", 
        "CFBundleExecutable": "ProperTree.command", 
        "CFBundleName": "ProperTree", 
        "LSMinimumSystemVersion": "10.4",
        "LSMultipleInstancesProhibited": True,
        "CFBundlePackageType": "APPL", 
        "CFBundleVersion": "0.0"
    }
    with open(info_path,"wb") as f:
        plist.dump(info,f)
    if temp:
        for path in app_preserve_paths:
            t_path = os.path.join(temp,os.path.basename(path))
            if os.path.exists(t_path):
                print("Restoring {}...".format(os.path.basename(path)))
                shutil.copy(t_path,path)
        shutil.rmtree(temp,ignore_errors=True)
    print("{} to: {}".format(
        "Saved" if os.path.isdir(app_path) else "Something went wrong saving",
        app_path
    ))

if __name__ == '__main__':
    # Setup the cli args
    parser = argparse.ArgumentParser(prog="buildapp-select.command", description="BuildAppSelect - a py script that builds ProperTree.app")
    parser.add_argument("-c", "--use-current", help="Use the current shebang in the ProperTree.app (assumes the app is in the parent dir of this script)", action="store_true")
    parser.add_argument("-p", "--python-path", help="The python path to use in the shebang of the ProperTree.app (-c overrides this)")
    parser.add_argument("-m", "--minimum-tk-enforced", help="Enforces minimum tk versions depending on the OS version (default is just to suggest)", action="store_true")
    parser.add_argument("-t", "--do-not-test-load-tk", help="Do not attempt to load discovered tk instances to verify whether or not they crash", action="store_true")
    parser.add_argument("-o", "--output-path", help="Sets the target output path for the ProperTree.app.  Defaults to the parent directory of this script")
    parser.add_argument("-n", "--no-verify", help="Skip all python/tk discovery and validation; use the path from -p (or -c) verbatim.  Requires -p or -c.", action="store_true")
    args = parser.parse_args()
    if not args.no_verify and str(sys.platform) != "darwin":
        print("Can only be run on macOS")
        exit(1)
    try:
        main(
            use_current=args.use_current,
            path_list=args.python_path,
            min_only_suggestion=not args.minimum_tk_enforced,
            test_load_tk=not args.do_not_test_load_tk,
            app_path=args.output_path,
            no_verify=args.no_verify
        )
    except Exception as e:
        print("An error occurred!")
        print(str(e))
        exit(1)
