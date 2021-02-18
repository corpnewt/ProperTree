#!/usr/bin/env python
import sys, os, plist, shutil, tempfile, subprocess
if 2/3==0: input = raw_input

min_tk_version = {
    "11":"8.6"
}
min_only_suggestion = True
test_load_tk = True

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
        if os_ver <= curr_os: curr_min = min_tk_version[os_ver]
    return curr_min

def gather_python(show_all=False):
    # Let's find the available python installs, check their tk version
    # and try to pick the latest one supported - or throw an error if
    # we're on macOS 11.x+ and using Tk 8.5 or older.
    pypaths = []
    envpaths = []
    for py in ("python","python3"):
        p = subprocess.Popen(["which",py], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        c = p.communicate()
        binpath = "/usr/bin/{}".format(py)
        envpath = "/usr/bin/env {}".format(py)
        avail = [x for x in _decode(c[0]).split("\n") if len(x) and not x in pypaths and not x == binpath]
        if os.path.exists(binpath): avail.insert(0,binpath)
        if len(avail): # Only add paths that we found and verified
            pypaths.extend(avail)
            if not envpath in envpaths: envpaths.append((envpath,None,None))
    py_tk = []
    for path in pypaths:
        # Get the version of python first
        path = path.strip()
        p = subprocess.Popen([path,"-V"], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        c = p.communicate()
        pv = (_decode(c[0]) + _decode(c[1])).strip().split(" ")[-1]
        if not len(pv): continue # Bad version?
        tk_string = "Tkinter" if pv.startswith("2.") else "tkinter"
        command = "import {} as tk; print(tk.TkVersion)".format(tk_string)
        p = subprocess.Popen([path,"-c",command], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        c = p.communicate()
        tk = _decode(c[0]).strip()
        if test_load_tk:
            command = "import {} as tk; tk.Tk()".format(tk_string)
            p = subprocess.Popen([path,"-c",command], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            c = p.communicate()
            if p.returncode != 0:
                # Failed to run correctly - skip it
                continue
        py_tk.append((path,pv,tk))
    min_tk = get_min_tk_version()
    if min_tk and not show_all:
        return [x for x in py_tk if x[-1] >= min_tk]+envpaths
    return py_tk+envpaths

def select_py(py_versions,min_tk,pt_current):
    current = next((x[0] for x in py_versions if x[0] == pt_current),None)
    while True:
        os.system("clear")
        print(" - Currently Available Python Versions -")
        print("")
        for i,x in enumerate(py_versions,1):
            print("{}. {}{}{}{}".format(
                i,
                x[0],
                " {}".format(x[1]) if x[1] else "",
                " - tk {}".format(x[2]) if x[2] else "",
                "" if x[2]==None or min_tk!=None and x[2] >= min_tk else " ({}+ recommended)".format(min_tk),
            ))
        print("")
        if current: print("C. Current ({})".format(current))
        print("Q. Quit")
        print("")
        menu = input("Please select the python version to use:  ").lower()
        if not len(menu): return
        if menu == "q": exit()
        if menu == "c" and current: return next((x for x in py_versions if x[0] == current))
        try: menu = int(menu)
        except: continue
        if not 0 < menu <= len(py_versions): continue
        return py_versions[menu-1]

def main():
    # Let's check for an existing app - remove it if it exists,
    # then create and format a new bundle
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    os.chdir("../")
    temp = None
    print("Locating python versions...")
    py_versions = gather_python(min_only_suggestion)
    if not py_versions:
        print(" - No python installs with functioning tk found!  Aborting!")
        exit(1)
    pt_current = None
    if os.path.exists("ProperTree.app/Contents/MacOS/ProperTree.command"):
        # Let's try to read the shebang
        try:
            with open("ProperTree.app/Contents/MacOS/ProperTree.command","r") as f:
                pt = f.read().split("\n")
                if pt[0].startswith("#!"):
                    # Got a shebang - save it
                    pt_current = pt[0][2:]
        except: pass
    min_tk = get_min_tk_version()
    py_version = py_versions[0] if len(py_versions) == 1 else select_py(py_versions,min_tk,pt_current)
    os.system("clear")
    print("Building .app with the following python install:")
    print(" - {}".format(py_version[0]))
    print(" --> {}".format(py_version[1]))
    print(" --> tk {}".format(py_version[2]))
    pypath = py_version[0]
    print("Checking for existing ProperTree.app...")
    if os.path.exists("ProperTree.app"):
        print(" - Found, removing...")
        if os.path.exists("ProperTree.app/Contents/MacOS/Scripts/settings.json"):
            print(" --> Found settings.json - preserving...")
            temp = tempfile.mkdtemp()
            shutil.copy("ProperTree.app/Contents/MacOS/Scripts/settings.json", os.path.join(temp, "settings.json"))
        shutil.rmtree("ProperTree.app")
    # Make the directory structure
    print("Creating bundle structure...")
    os.makedirs("ProperTree.app/Contents/MacOS/Scripts")
    os.makedirs("ProperTree.app/Contents/Resources")
    print("Copying scripts...")
    print(" - ProperTree.command")
    with open("ProperTree.command","r") as f:
        ptcom = f.read().split("\n")
    if ptcom[0].startswith("#!"):
        # Got a shebang - remove it
        ptcom.pop(0)
    # Set the new shebang
    ptcom.insert(0,"#!{}".format(pypath))
    with open("ProperTree.app/Contents/MacOS/ProperTree.command","w") as f:
        f.write("\n".join(ptcom))
    # chmod +x
    p = subprocess.Popen(["chmod","+x","ProperTree.app/Contents/MacOS/ProperTree.command"], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    c = p.communicate()
    # Copy everything else
    for x in os.listdir("Scripts"):
        if x.startswith(".") or not x.lower().endswith((".py",".plist",".icns")):
            continue
        print(" - "+x)
        target = "ProperTree.app/Contents/Resources" if x.lower().endswith(".icns") else "ProperTree.app/Contents/MacOS/Scripts"
        shutil.copy(os.path.join("Scripts",x),target)
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
    with open("ProperTree.app/Contents/Info.plist","wb") as f:
        plist.dump(info,f)
    if temp:
        print("Restoring settings.json...")
        shutil.copy(os.path.join(temp, "settings.json"),"ProperTree.app/Contents/MacOS/Scripts/settings.json")
        shutil.rmtree(temp,ignore_errors=True)

if __name__ == '__main__':
    if not str(sys.platform) == "darwin":
        print("Can only be run on macOS")
        exit(1)
    try:
        main()
    except Exception as e:
        print("An error occurred!")
        print(str(e))
        exit(1)
