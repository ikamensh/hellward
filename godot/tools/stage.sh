#!/bin/sh
# A staged moment of a battle, rendered: tools/stage.sh NAME OUT_DIR  (NAME: uv run python ../tools/stages.py --list)
# The repository's tools/stages.py finds the moment by playing the stage's defence; game/scripts/stage.gd plays it
# through the server's demo and saves OUT_DIR/NAME_N.png. Runs through tools/godot-capture.sh: no window appears.
set -e
cd "$(dirname "$0")/.."
name=$1; out=$(mkdir -p "$2" && cd "$2" && pwd)
uv run --project .. python ../tools/stages.py "$name" "$out/$name.json"
tools/godot-capture.sh --path game --fixed-fps 30 res://scenes/capture.tscn -- scene=res://scenes/stage.tscn \
  "stage=$out/$name.json" "out=$out" "name=$name" timeout=600 2>&1 | grep -E "^stage:|ERROR|SCRIPT ERROR|at: " | head -20
rm -f "$out/$name.json"
ls "$out"/"$name"_*.png
