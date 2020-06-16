#!/bin/bash

python3 -m nuitka --follow-imports propertree.py

#CYTHON_FLAGS="--cplus -3 --warning-extra"
#cat propertree.command | sed 's|from scripts import menu, plist, plistwindow, run, utils||g' >> propertree.tmp
#cat scripts/*.py propertree.tmp >> propertree.py
#cython propertree.py --embed $CYTHON_FLAGS
#cython scripts/plist.py $CYTHON_FLAGS
#cython scripts/plistwindow.py $CYTHON_FLAGS
#cython scripts/run.py $CYTHON_FLAGS
#cython scripts/utils.py $CYTHON_FLAGS
