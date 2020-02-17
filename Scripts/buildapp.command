#!/usr/bin/env python
import sys, os, plist, shutil, tempfile

def main():
    # Let's check for an existing app - remove it if it exists,
    # then create and format a new bundle
    temp = None
    print("Checking for existing ProperTree.app...")
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    os.chdir("../")
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
    shutil.copy("ProperTree.command","ProperTree.app/Contents/MacOS")
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
