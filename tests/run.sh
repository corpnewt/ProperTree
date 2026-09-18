#!/usr/bin/env bash
# tui tests - pty driven, stdlib only, no test framework
# usage: tests/run.sh          run everything
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

python3 -m py_compile plist_tui.py propertreecli.py Scripts/plist.py
echo "compile ok"

rm -rf /tmp/plist_tui_tests
python3 tests/tui_empty_test.py
python3 tests/tui_regress_test.py
echo "all tui tests passed"
