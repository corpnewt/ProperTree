#!/usr/bin/env bash
export TCL_LIBRARY="/usr/local/opt/tcl-tk/lib/tcl8.6"
export TK_LIBRARY="/usr/local/opt/tcl-tk/lib/tk8.6"

rm -rf *.build *.dist propertree.command.dist propertree ./misc/darwin/ProperTree.app/Contents/MacOS/* release
python3 -m nuitka --follow-imports propertree.command --standalone --plugin-enable=tk-inter --include-plugin-directory=scripts
mv propertree.command.dist/propertree.command propertree.command.dist/ProperTree
strip propertree.command.dist/ProperTree
mkdir -p ./misc/darwin/ProperTree.app/Contents/MacOS/ release/
mv propertree.command.dist/* ./misc/darwin/ProperTree.app/Contents/MacOS/
cp -Rv scripts ./misc/darwin/ProperTree.app/Contents/MacOS/scripts
