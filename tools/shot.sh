#!/bin/sh
# Capture the game at a named view (game/scripts/shots.gd): tools/shot.sh NAME OUT.png [FRAMES] [extra user args]
# Steps FRAMES frames at a fixed 30 fps (default 40, so particles and fog settle) and saves the last one, 1920x1080.
# Runs through tools/godot-capture.sh: no window appears and the desktop keeps its focus.
set -e
cd "$(dirname "$0")/.."
name=$1; out=$(cd "$(dirname "$2")" && pwd)/$(basename "$2"); frames=${3:-40}; shift 2; [ $# -gt 0 ] && shift
tools/godot-capture.sh --path game --fixed-fps 30 res://scenes/capture.tscn -- scene=res://scenes/main.tscn "shot=$name" "snap=$out" "frames=$frames" "$@" 2>&1 \
  | grep -E "ERROR|SCRIPT ERROR|at: " | head -20 || true
test -f "$out"
echo "$out"
