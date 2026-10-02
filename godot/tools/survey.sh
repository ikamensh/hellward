#!/bin/sh
# Everything the rules have, as the client shows it: tools/survey.sh OUT_DIR
# OUT_DIR/towers.png (every tower kind at each rank), monsters.png (every monster kind, a stand-in marked by a red
# post), and locations/<key>.png (each location's battle from overhead, mid-wave). The kinds and locations are
# the server's (hellward.sim), so a kind added to the rules shows up here with no edit. tools/assets.py is the
# same in text.
set -e
cd "$(dirname "$0")/.."
out=$(mkdir -p "$1/locations" && cd "$1" && pwd)
q() { (cd .. && uv run --quiet python -c "$1"); }
towers=$(q "from hellward.sim.content import TOWERS; print(','.join(TOWERS))")
monsters=$(q "from hellward.sim.content import MONSTERS; print(','.join(MONSTERS))")
locations=$(q "from hellward.sim.campaign import LOCATIONS; print(' '.join(LOCATIONS))")
cap() { tools/godot-capture.sh --path game --fixed-fps 30 res://scenes/capture.tscn -- "$@" 2>&1 \
  | grep -E "SCRIPT ERROR|^ERROR" | head -5 || true; }
cap scene=res://scenes/survey.tscn res=1920x1080 what=towers "kinds=$towers" "out=$out/towers.png"
cap scene=res://scenes/survey.tscn res=1920x1080 what=monsters "kinds=$monsters" "out=$out/monsters.png"
for loc in $locations; do
  tools/shot.sh overview "$out/locations/$loc.png" 900 demo "location=$loc" >/dev/null 2>&1 || echo "FAILED $loc"
done
ls "$out" "$out/locations"
