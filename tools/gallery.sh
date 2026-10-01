#!/bin/sh
# Several named views (game/scripts/shots.gd) from one run, as one contact sheet:
#   tools/gallery.sh OUT.png VIEW,VIEW,... [FRAMES] [extra user args, e.g. demo]
# The battle runs FRAMES frames at 30 fps first (default 40). Runs invisibly (tools/godot-capture.sh).
set -e
cd "$(dirname "$0")/.."
out=$(cd "$(dirname "$1")" && pwd)/$(basename "$1"); views=$2; frames=${3:-40}; shift 2; [ $# -gt 0 ] && shift
tmp=$(mktemp -d /tmp/hw3d-gallery.XXXXXX)
tools/godot-capture.sh --path game --fixed-fps 30 res://scenes/capture.tscn -- scene=res://scenes/main.tscn "gallery=$views" "out=$tmp" "frames=$frames" "$@" 2>&1 \
  | grep -E "ERROR|SCRIPT ERROR|at: " | head -20 || true
files=""
for v in $(echo "$views" | tr , ' '); do files="$files $tmp/$v.png"; done
cols=2; [ "$(echo "$views" | tr , '\n' | wc -l)" -eq 1 ] && cols=1
uv run --quiet python tools/sheet.py "$out" $files --cols $cols --width 2400 >/dev/null
rm -rf "$tmp"
echo "$out"
