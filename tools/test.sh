#!/bin/sh
# Hellward 3D's integration tests, headless: tools/test.sh
# Fails on a failed check, a non-zero exit, or any script error printed along the way.
cd "$(dirname "$0")/.."
log=$(mktemp /tmp/hw3d-test.XXXXXX)
godot=/Applications/Godot.app/Contents/MacOS/Godot
$godot --headless --path game --import >/dev/null 2>&1
$godot --headless --path game --resolution 1920x1080 --fixed-fps 30 res://tests/run.tscn >"$log" 2>&1
code=$?
grep -E "^-- |FAIL|all passed|FAILED" "$log"
errors=$(grep -E "SCRIPT ERROR|^ERROR" "$log" | grep -c -v "resources still in use at exit")
if [ "$errors" -gt 0 ]; then
  echo "script errors: $errors"; grep -E -A2 "SCRIPT ERROR|^ERROR" "$log" | head -30
fi
rm -f "$log"
[ "$code" -eq 0 ] && [ "$errors" -eq 0 ]
