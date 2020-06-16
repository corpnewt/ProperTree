#!/usr/bin/env bash

brew install python3 tcl-tk
pip3 install nuitka cython

export TCL_LIBRARY="/usr/local/opt/tcl-tk/lib/tcl8.6"
export TK_LIBRARY="/usr/local/opt/tcl-tk/lib/tk8.6"
