#!/usr/bin/env bash
export TCL_LIBRARY="/usr/local/opt/tcl-tk/lib/tcl8.6"
export TK_LIBRARY="/usr/local/opt/tcl-tk/lib/tk8.6"

rm -rf *.build *.dist propertree.command.dist propertree propertree.command.bin
python3 -m nuitka --follow-imports propertree.command # --standalone --plugin-enable=tk-inter
mv propertree.command.bin ProperTree
#mv propertree.command.dist propertree
strip propertree

#CYTHON_FLAGS="--cplus -3 --warning-extra"
#cat propertree.command | sed 's|from scripts import menu, plist, plistwindow, run, utils||g' >> propertree.tmp
#cat scripts/*.py propertree.tmp >> propertree.py
#cython propertree.py --embed $CYTHON_FLAGS
#cython scripts/plist.py $CYTHON_FLAGS
#cython scripts/plistwindow.py $CYTHON_FLAGS
#cython scripts/run.py $CYTHON_FLAGS
#cython scripts/utils.py $CYTHON_FLAGS
