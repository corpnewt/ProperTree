# What is it?

ProperTree is a cross-platform GUI plist editor written using Python *(compatible with both 2.x and 3.x)* and Tkinter.

## Features

- [x] Cross-platform - should work anywhere python and tkinter do
- [x] Document-based to support multiple windows
- [x] Node drag and drop to reorder
- [x] Copy and paste
- [x] Find/Replace - allows searching keys or values
- [x] Ordered - or unordered - dictionary support
- [x] Full undo-redo stack
- [x] Backported support for binary property lists and unicode in python 2
- [x] Expanded integer casting to allow for hex integers (eg. `0xFFFF`) in xml `<integer>` tags
- [x] Context-aware right-click menu that includes template info to OpenCore or Clover config.plist files
- [x] OC (Clean) Snapshot to walk the contents of ACPI, Drivers, Kexts, and Tools for OpenCore config.plist files
- [x] Value converter that supports Base64, Hex, Ascii, and Decimal

***

## Getting ProperTree

### Downloading The Repo As A ZIP File

On any system you can choose the green `Code` button, followed by the `Download ZIP` button (or click [here](https://github.com/corpnewt/ProperTree/archive/refs/heads/master.zip)) to download the entire repo as a zip file (note, this does not allow you to update via `git pull` - any updates would require you to download the repo again in the same fashion).

### Cloning The Repo Via Git

#### On *nix systems:

```
git clone https://github.com/corpnewt/ProperTree
python ./ProperTree/ProperTree.py
- or -
python3 ./ProperTree/ProperTree.py
```

\* On macOS, you can simply double-click the `ProperTree.command` after cloning to launch.

#### On Windows:

```
git clone https://github.com/corpnewt/ProperTree
./ProperTree/ProperTree.bat
```

***

## FAQ

* **What does OC Snapshot do?**

  The OC Snapshot function will prompt you to select an OC folder, then walk the contents of the ACPI, Kexts, Tools, and Drivers directories within that folder - comparing all entries to the current document's `ACPI -> Add`, `Kernel -> Add`, `Misc -> Tools`, and `UEFI -> Drivers` respectively.  It will add or remove entries as needed, and also ensures kext load order by comparing each kext's `CFBundleIdentifier` to all other kexts' `OSBundleLibraries` within their Info.plist - making sure that any kext that is relied on by others is loaded before them.  It will also warn if it detects duplicate `CFBundleIdentifiers` (with support for `MinKernel`, `MaxKernel`, and `MatchKernel` overlap checks), and offer to disable all after the first found.  It checks for disabled parent kexts with enabled child kexts as well.  The schema used is (by default) determined by comparing the MD5 hash of the `OpenCore.efi` file to a known list of Acidanthera debug/release versions.  If the MD5 hash does not match any known version, it will fall back to the newest schema in the script's `snapshot.plist`.  This behavior can be customized in the Settings per the `OC Snapshot Target Version` menu.

* **What is the difference between OC Snapshot and OC Clean Snapshot?**

  Both snapshot variants accomplish the same tasks - they just leverage different starting points.  An OC **Clean** Snapshot will first clear out `ACPI -> Add`, `Kernel -> Add`, `Misc -> Tools`, and `UEFI -> Drivers`, then add everything from within the respective ACPI, Kexts, Tools, and Drivers directory anew.  A regular OC Snapshot starts with the information within the current document for those four locations, and only pulls changes - adding and removing entries as needed.
  
* **When should I use an OC Clean Snapshot vs an OC Snapshot?**

  Typically, an OC **Clean** Snapshot should only be used the first time you snapshot to ensure any sample entries in the config.plist are removed and added anew.  Every subsequent snapshot should be a regular OC Snapshot to ensure any customizations you've made are preserved.

* **ProperTree opens a black window on macOS Monterey (12.x)**

  It appears the default tk implementation that ships with macOS Monterey doesn't display correctly.  A workaround is to download and install the latest build of python 3 from python.org (found [here](https://www.python.org/downloads/macos/)) which has a compatible tk bundled, then use the `buildapp-select.command` located in ProperTree's `Scripts` directory to build an application bundle targeting the installed python's path.  You can then leverage the `ProperTree.app` bundle it creates.
  
* **ProperTree cannot open or save plist files on macOS Monterey (12.x)**

  This appears to be an issue with the built-in tk, and the earlier "universal" installers from python.org.  With at least python 3.10.2, this issue has been resolved in the universal builds.  You can get the latest python 3 installer [here](https://www.python.org/downloads/macos/).  After installing, use the `buildapp-select.command` located in ProperTree's `Scripts` directory to build an application bundle targeting the installed python's path.  You can then leverage the `ProperTree.app` bundle it creates.

* **How can I have ProperTree open when I double-click a .plist file?**

  On macOS you can run `buildapp-select.command` located in ProperTree's `Scripts` directory to build an application bundle which can be associated with .plist files.
  
  On Windows, you can run `AssociatePlistFiles.bat` located in ProperTree's `Scripts` directory to associate .plist files with `ProperTree.bat`, and also to add an `Open with ProperTree` option to the contextual menu when right-clicking .plist files.  This approach is location-dependent, and moving your copy of ProperTree will require you re-run `AssociatePlistFiles.bat`.

* **When I try to run ProperTree, I get `[ModuleNotFoundError: No module name 'tkinter']`**

  That is because the graphical interface library that ProperTree depends on isn't present or cannot be detected, you need to install `tkinter` from your package manager. 

  To install it on Ubuntu (and Ubuntu-based distros), you can run `sudo apt-get install python3-tk -y`

* **ProperTree doesn't run because it doesn't have permissions, what gives?**

  This shouldn't happen and it is recommended that you download only from the official ProperTree repository, but if you are confident about your source, then running `chmod +x ProperTree.command` should sort it out

* **I use an international keyboard layout on macOS and some keys crash ProperTree with `NSRangeException', reason: '-[__NSCFConstantString characterAtIndex:]: Range or index out of bounds`**

  This is a bug in the Cocoa implementation of Tcl/Tk on macOS (discussed [here](https://bugs.python.org/issue22566)).  The latest python 2 installer from [python.org](https://www.python.org/downloads/release/python-2718/) ships with, and uses Tcl/Tk 8.6.8 which has this issue fixed.  Given that the shebang in `ProperTree.command` leverages `#!/usr/bin/env python` - the first python 2 binary found should be used. `buildapp-select.command` from ProperTree's `Scripts` directory can be used to hardcode a specific python install's path into the .app bundle's executable shebang.
  
* **ProperTree crashes on Big Sur (macOS 11)**

  __As of macOS 11.2 (20D5029f), the system's `tk` installation appears to be fixed, and works correctly.  As such, it should not require an external python version to function.__

  This is due to the default python installs on macOS leveraging an older `tk` version - which lacks support for macOS 11.  To solve this, you can download and install the latest python 3 version from https://www.python.org/downloads/mac-osx/ (note: Currently the "universal" 3.9.1 installer causes theme issues and should not be used) then leverage the `buildapp-select.command` from ProperTree's `Scripts` directory to build a .app bundle that will leverage that python version.
  
  If you already have python 3 installed via `brew` or another package manager - it is likely still linking to the system `tk` version, which will still have issues unless linked against a newer version. 

* **`buildapp-select.command` Usage**

  An example of the output of `buildapp-select.command` is shown below.  It will walk the output of `which python` and `which python3`, then attempt to load the `tk` interface while keeping track of which work and which fail.  The example below is from macOS 11.2 (20D4029f) with the system versions of python 2 and 3, as well as python 3.9.1 installed from python.org.  If there's an existing `ProperTree.app` in the directory above the `Scripts` folder, the shebang of that app will be located and served up as the `C. Current` option.  At the following menu, I would select option `3` or `C` to use the non-system python install.

```
 - Currently Available Python Versions -

1. /usr/bin/python 2.7.16 - tk 8.5 (8.6+ recommended)
2. /usr/bin/python3 3.8.2 - tk 8.5 (8.6+ recommended)
3. /Library/Frameworks/Python.framework/Versions/3.9/bin/python3 3.9.1 - tk 8.6
4. /usr/bin/env python
5. /usr/bin/env python3

C. Current (/Library/Frameworks/Python.framework/Versions/3.9/bin/python3)
Q. Quit

Please select the python version to use:  
```
