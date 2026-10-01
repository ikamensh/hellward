#!/bin/sh
# Run Godot for captures without disturbing the desktop: the injected shim makes it a background (accessory)
# app with no Dock icon, which never activates or shows its window. Run scenes through res://scenes/capture.tscn (scene=...), which renders offscreen, so
# captures keep full speed with the window hidden or the screen locked. Usage: tools/godot-capture.sh [godot args]
here=$(cd "$(dirname "$0")" && pwd)
shim="$here/capture/noactivate.dylib"
[ "$shim" -nt "$here/capture/noactivate.m" ] || clang -dynamiclib -fobjc-arc -framework AppKit -o "$shim" "$here/capture/noactivate.m"
# new or changed assets need importing, and a new class_name script is unknown until the editor rescans
game="$here/../game"
cache="$game/.godot/global_script_class_cache.cfg"
if [ ! -f "$cache" ] || [ -n "$(find "$game/scripts" "$game/assets" "$game/shaders" -type f ! -name '*.import' -newer "$cache" | head -1)" ]; then
  DYLD_INSERT_LIBRARIES="$shim" /Applications/Godot.app/Contents/MacOS/Godot --headless --path "$game" --import >/dev/null 2>&1
  touch "$cache"
fi
# captures are silent: a recording's soundtrack is mixed from the game's sound log (tools/mixdown.py)
DYLD_INSERT_LIBRARIES="$shim" exec /Applications/Godot.app/Contents/MacOS/Godot --audio-driver Dummy "$@"
