#!/usr/bin/env bash
# plist install  -  symlink into ~/.local/bin (or the dir given)
# usage: ./install.sh [dir]          link the plist command into dir
#        ./install.sh --uninstall [dir]   remove the links
set -euo pipefail
repo="$(cd "$(dirname "$0")" && pwd)"
dir="${2:-$HOME/.local/bin}"

if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$dir/plist" "$dir/propertreecli"
    echo "removed $dir/plist"
    exit 0
fi

mkdir -p "$dir"
ln -sfn "$repo/propertreecli.py" "$dir/plist"
# old name kept as an alias so nothing that learned it breaks
ln -sfn "$repo/propertreecli.py" "$dir/propertreecli"
echo "linked $dir/plist -> $repo/propertreecli.py"

case ":$PATH:" in
    *":$dir:"*) ;;
    *) echo "add $dir to your PATH to run it from anywhere:"
       echo "  export PATH=\"$dir:\$PATH\""
       ;;
esac
