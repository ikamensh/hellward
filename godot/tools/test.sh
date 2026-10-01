#!/bin/sh
# Hellward's client tests, headless, against the real server: tools/test.sh [NAME-PART]
# Fails on a failed check, a non-zero exit, or any script error printed along the way. The server saves into a
# scratch folder; HELLWARD_TEST runs only the tests whose name contains it.
cd "$(dirname "$0")/.."
log=$(mktemp /tmp/hw-test.XXXXXX)
data=$(mktemp -d /tmp/hw-test-data.XXXXXX)
godot=tools/godot-capture.sh   # the shim keeps even headless runs out of the Dock
HELLWARD_DATA="$data" HELLWARD_TEST="$1" $godot --headless --path game --resolution 1920x1080 --fixed-fps 30 res://tests/run.tscn >"$log" 2>&1
code=$?
grep -E "^-- |FAIL|all passed|FAILED" "$log"
errors=$(grep -E "SCRIPT ERROR|^ERROR" "$log" | grep -c -v "resources still in use at exit")
if [ "$errors" -gt 0 ]; then
  echo "script errors: $errors"; grep -E -A2 "SCRIPT ERROR|^ERROR" "$log" | head -30
fi
rm -f "$log"
rm -rf "$data"
[ "$code" -eq 0 ] && [ "$errors" -eq 0 ]
