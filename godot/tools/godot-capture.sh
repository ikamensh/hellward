#!/bin/sh
# Run Godot for captures without disturbing the desktop: on a Mac the injected shim makes it a background
# (accessory) app with no Dock icon, which never activates or shows its window. Run scenes through
# res://scenes/capture.tscn (scene=...), which renders offscreen, so captures keep full speed with the window hidden
# or the screen locked. Elsewhere (Windows CI) Godot runs as it is: $GODOT, or godot on the PATH.
# Usage: tools/godot-capture.sh [godot args]
here=$(cd "$(dirname "$0")" && pwd)
game="$here/../game"
if [ "$(uname)" = "Darwin" ]; then
  godot=${GODOT:-/Applications/Godot.app/Contents/MacOS/Godot}
  shim="$here/capture/noactivate.dylib"
  [ "$shim" -nt "$here/capture/noactivate.m" ] || clang -dynamiclib -fobjc-arc -framework AppKit -o "$shim" "$here/capture/noactivate.m"
  inject="DYLD_INSERT_LIBRARIES=$shim"
else
  godot=${GODOT:-godot}
  command -v cygpath >/dev/null && godot=$(cygpath -u "$godot")   # Git Bash on Windows
  inject=""
fi
# new or changed assets need importing, and a new class_name script is unknown until the editor rescans;
# HW_NO_IMPORT=1 skips it: parallel captures must not import into the same cache at once
cache="$game/.godot/global_script_class_cache.cfg"
if [ -z "$HW_NO_IMPORT" ] && { [ ! -f "$cache" ] || [ -n "$(find "$game/scripts" "$game/assets" "$game/shaders" -type f ! -name '*.import' -newer "$cache" | head -1)" ]; }; then
  env $inject "$godot" --headless --path "$game" --import >/dev/null 2>&1
  touch "$cache"
fi
# the server the game starts saves into a scratch folder, never the player's ~/.hellward (removed afterwards)
made=""
[ -n "$HELLWARD_DATA" ] || { made=$(mktemp -d /tmp/hw-capture-data.XXXXXX); HELLWARD_DATA=$made; export HELLWARD_DATA; }
# and the client keeps its settings there too, never in the player's own
[ -n "$HELLWARD_PREFS" ] || { HELLWARD_PREFS="$HELLWARD_DATA/client-settings.cfg"; export HELLWARD_PREFS; }
# captures are silent: a recording's soundtrack is mixed from the game's sound log (tools/mixdown.py)
env $inject "$godot" --audio-driver Dummy "$@"
code=$?
[ -z "$made" ] || rm -rf "$made"
exit $code
