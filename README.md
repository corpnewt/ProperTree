# ProperTree
A cross-platform plist editor written in Python3

## Get Started

On *nix systems:

```
git clone https://github.com/corpnewt/ProperTree
python3 ./ProperTree/ProperTree.command
```
On Windows:

```
git clone https://github.com/corpnewt/ProperTree
./ProperTree/ProperTree.bat
```

## FAQ

* **When I try to run ProperTree, I get `[ModuleNotFoundError: No module name 'tkinter']`**

  That is because the graphical interface library that ProperTree depends on isn't present or cannot be detected, you need to install `tkinter` from your package manager. 

  To install it on Ubuntu (and Ubuntu-based distros), you can run `sudo apt-get install python3-tk -y`

* **ProperTree doesn't run because it doesn't have permissions, what gives?**

  This shouldn't happen and it is recommended that you download only from the official ProperTree repository, but if you are confident about your source, then running `chmod +x ProperTree.command` should sort it out

