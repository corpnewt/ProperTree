#!/bin/bash

# because i don't want to replace again and again
CYTHON_FLAGS="--embed --cplus -3 --warning-extra"

cython propertree.py $CYTHON_FLAGS
cython scripts/plist.py $CYTHON_FLAGS
cython scripts/plistwindow.py $CYTHON_FLAGS
cython scripts/run.py $CYTHON_FLAGS
cython scripts/utils.py $CYTHON_FLAGS
