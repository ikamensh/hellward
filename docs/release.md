# Releasing Hellward

A release is the Godot client exported with the server beside it: a Python (the one the simulation is compiled
for), the `hellward` package (rules, server, story) and its compiled simulation. Players need no Python and no
terminal. Packages go on the GitHub release `vX.Y.Z` of `ikamensh/hellward` and into saga-online's catalog, which
publishes the game's page on https://games.tachyon-ai.eu/.

## Build

```bash
uv run python tools/package.py mac        # on an Apple Silicon Mac: dist/Hellward-X.Y.Z-darwin-arm64-app.zip
git tag vX.Y.Z && git push origin vX.Y.Z  # the Windows package workflow builds, tests and attaches the Windows zip
```

`tools/package.py` exports the client (`godot/game/export_presets.cfg`; Godot's export templates for the engine's
version must be installed), lays out the server (`Hellward.app/Contents/Resources/server`, or `server\` beside
`Hellward.exe`: `python/`, `hellward/`, `build/<key>/`), checks the packaged Python makes the build's key, plays a
Tristram defence through the packaged server from a read-only copy (compiled, to its end), ad-hoc signs the Mac
app and zips it beside a manifest (`.json`: size, SHA-256, source commit, the smoke defence). The client finds its
server through `godot/game/scripts/net.gd` `server_command`. `.github/workflows/windows.yml` does the same on
`windows-latest` (MSVC compiles the simulation there) after the server's and the client's tests.

## Publish

1. `gh release create vX.Y.Z dist/Hellward-X.Y.Z-darwin-arm64-app.zip --title "Hellward X.Y.Z"` with notes;
   the workflow attaches the Windows zip to the same release.
2. In saga-online: the `hellward` entry of `releases/catalog.json` (version, source commit, date, notes URL, each
   package's URL, size and SHA-256 from the manifests) and its page copy and screenshots (`website/content.py`,
   `website/media/hellward/`); its tests; push; publish the site as saga-online's `deploy/README.md` says.
3. Fetch each public download and compare its SHA-256 with the catalog.

The Mac app is ad-hoc signed and not notarized, the Windows build unsigned: the game page carries the first-launch
steps (Mac: move it to Applications, then Control-click Open or System Settings > Privacy & Security > Open Anyway).
