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

On any system you can choose the `Clone or download` button, followed by the `Download ZIP` button to download the entire repo as a zip file (note, this does not allow you to update via `git pull` - any updates would require you to download the repo again in the same fashion).

### Cloning The Repo Via Git

#### On *nix systems:

```
git clone https://github.com/corpnewt/ProperTree
python ./ProperTree/ProperTree.command
```

\* On macOS, you can simply double-click the `ProperTree.command` after cloning to launch.

#### On Windows:

```
git clone https://github.com/corpnewt/ProperTree
./ProperTree/ProperTree.bat
```

***

## FAQ

* **How can I have ProperTree open when I double-click a .plist file?**

  On macOS you can run `buildapp.command` located in ProperTree's `Scripts` directory to build an application bundle which can be associated with .plist files.  While this approach *works* - it sometimes has odd issues when attempting to open multiple .plist files by double-clicking.  Typically the first will work as normal, but opening any subsequent .plist file requires using the File -> Open menu.
  
  On Windows, you can run `AssociatePlistFiles.bat` located in ProperTree's `Scripts` directory to associate .plist files with `ProperTree.bat`, and also to add an `Open with ProperTree` option to the contextual menu when right-clicking .plist files.  This approach is location-dependent, and moving your copy of ProperTree will require you re-run `AssociatePlistFiles.bat`.

* **When I try to run ProperTree, I get `[ModuleNotFoundError: No module name 'tkinter']`**

  That is because the graphical interface library that ProperTree depends on isn't present or cannot be detected, you need to install `tkinter` from your package manager. 

  To install it on Ubuntu (and Ubuntu-based distros), you can run `sudo apt-get install python3-tk -y`

* **ProperTree doesn't run because it doesn't have permissions, what gives?**

  This shouldn't happen and it is recommended that you download only from the official ProperTree repository, but if you are confident about your source, then running `chmod +x ProperTree.command` should sort it out

* **I use an international keyboard layout on macOS and some keys crash ProperTree with `NSRangeException', reason: '-[__NSCFConstantString characterAtIndex:]: Range or index out of bounds`**

  This is a bug in the Cocoa implementation of Tcl/Tk on macOS (discussed [here](https://bugs.python.org/issue22566)).  The latest python 2 installer from [python.org](https://www.python.org/downloads/release/python-2718/) ships with, and uses Tcl/Tk 8.6.8 which has this issue fixed.  Given that the shebang in `ProperTree.command` leverages `#!/usr/bin/env python` - the first python 2 binary found should be used.
