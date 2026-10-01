"""Package Hellward for players: the Godot client exported, with the server beside it (a Python, the hellward package
and its compiled simulation), so playing needs no Python and no terminal.

    uv run python tools/package.py mac        # dist/Hellward-VERSION-darwin-arm64-app.zip (on an Apple Silicon Mac)
    uv run python tools/package.py windows    # dist/Hellward-VERSION-windows-x64-portable.zip (on Windows)

The server's files go where the client looks for them (godot/game/scripts/net.gd ``server_command``): beside the
game's executable in ``server/`` (Windows) or in ``Hellward.app/Contents/Resources/server`` (macOS), holding
``python/`` (this checkout's own CPython, the one the simulation is compiled for), ``hellward/`` (the rules, the
server and the story, byte-compiled) and ``build/<key>/`` (the compiled simulation). Before zipping, the packaged
server is started from the package and plays a defence to its end through the protocol, compiled.
The Godot export templates for the engine's version must be installed (Godot's Export Templates manager, or
~/Library/Application Support/Godot/export_templates/<version>.stable/).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME = ROOT / "godot" / "game"
DIST = ROOT / "dist"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
PACKAGE = ("__init__.py", "compiled.py", "fastsim.py", "story.py", "sim", "server")   # what the server imports
PRUNE = ("test", "idlelib", "tkinter", "turtledemo", "ensurepip", "lib2to3", "pydoc_data", "config-3")   # stdlib it never uses


def godot() -> str:
    found = os.environ.get("GODOT") or ("/Applications/Godot.app/Contents/MacOS/Godot" if sys.platform == "darwin"
                                        else shutil.which("godot"))
    if not found:
        raise SystemExit("package: Godot 4.7 is needed (GODOT=path)")
    return found


def compiled_build() -> Path:
    """The compiled simulation for the current sources, built once (in a process of its own)."""
    out = subprocess.run([sys.executable, "-m", "hellward.fastsim"], cwd=ROOT, check=True, capture_output=True,
                         text=True).stdout.strip().splitlines()[-1]
    return Path(out)


def export(preset: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ}
    shim = ROOT / "godot" / "tools" / "capture" / "noactivate.dylib"
    if sys.platform == "darwin":
        env["DYLD_INSERT_LIBRARIES"] = str(shim)   # no Dock icon, no window, no focus while exporting
    subprocess.run([godot(), "--headless", "--path", str(GAME), "--export-release", preset, str(out)], check=True,
                   env=env)


def server(into: Path, build: Path) -> Path:
    """Lay out the server: this checkout's base Python, the package, the compiled build. Returns the python."""
    if into.exists():
        shutil.rmtree(into)
    base = Path(sys.base_prefix)
    shutil.copytree(base, into / "python", symlinks=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.a", "include", "share", "Tk*", "tcl*", "tk*",
                                                  "itcl*", "thread*", "libtcl*", "libtk*", "*.pyc"))
    stdlib = Path(sysconfig.get_paths(vars={"installed_base": str(into / "python"),
                                            "base": str(into / "python")})["stdlib"])
    for name in PRUNE:
        for path in stdlib.glob(f"{name}*"):
            shutil.rmtree(path) if path.is_dir() else path.unlink()
    for name in PACKAGE:
        src = ROOT / "hellward" / name
        dst = into / "hellward" / name
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    shutil.copytree(build, into / "build" / build.name, ignore=shutil.ignore_patterns("__pycache__"))
    python = into / "python" / ("python.exe" if os.name == "nt" else "bin/python3")
    env = server_env(into)
    subprocess.run([str(python), "-m", "compileall", "-q", str(into / "hellward"), str(stdlib)], check=True, env=env)
    key = subprocess.run([str(python), "-c", "from hellward import fastsim; print(fastsim.key())"], check=True,
                         capture_output=True, text=True, env=env).stdout.strip()
    if key != build.name:
        raise SystemExit(f"package: the packaged Python makes key {key}, the build is {build.name}")
    return python


def server_env(into: Path) -> dict[str, str]:
    """What the client sets before it starts the packaged server (net.gd)."""
    clean = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "VIRTUAL_ENV", "HELLWARD_"))}
    return {**clean, "PYTHONPATH": str(into), "HELLWARD_BUILDS": str(into / "build"), "PYTHONDONTWRITEBYTECODE": "1"}


def smoke(python: Path, into: Path) -> dict:
    """The packaged server, started from the package as the client starts it, plays Tristram to its end."""
    from hellward.server.client import Client

    with tempfile.TemporaryDirectory() as data:
        if os.name != "nt":
            subprocess.run(["chmod", "-R", "a-w", str(into)], check=True)   # as in a read-only bundle: nothing writes
        try:
            with Client(Path(data), command=[str(python), "-m", "hellward.server"], env=server_env(into)) as client:
                if not client.compiled:
                    raise SystemExit("package: the packaged server runs the source simulation, not the build")
                client.request("demo", location="tristram", player="ordinary")
                while (last := client.advance(400)[-1])["state"]["outcome"] is None:
                    pass
        finally:
            if os.name != "nt":
                subprocess.run(["chmod", "-R", "u+w", str(into)], check=True)
    return {"outcome": last["state"]["outcome"], "lives": last["state"]["lives"], "steps": last["step"]}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def mac() -> Path:
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise SystemExit("package mac: run on an Apple Silicon Mac")
    build = compiled_build()
    stage = DIST / "mac"
    app = stage / "Hellward.app"
    if stage.exists():
        shutil.rmtree(stage)
    export("macOS", app)
    resources = app / "Contents" / "Resources" / "server"
    python = server(resources, build)
    played = smoke(python, resources)
    print(f"packaged server: {played}")
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    out = DIST / f"Hellward-{VERSION}-darwin-arm64-app.zip"
    out.unlink(missing_ok=True)
    subprocess.run(["ditto", "-c", "-k", "--keepParent", str(app), str(out)], check=True)
    record(out, played)
    return out


def windows() -> Path:
    if os.name != "nt":
        raise SystemExit("package windows: run on Windows (the simulation is compiled for the machine it runs on)")
    build = compiled_build()
    stage = DIST / "windows" / "Hellward"
    if stage.parent.exists():
        shutil.rmtree(stage.parent)
    export("Windows", stage / "Hellward.exe")
    python = server(stage / "server", build)
    played = smoke(python, stage / "server")
    print(f"packaged server: {played}")
    out = DIST / f"Hellward-{VERSION}-windows-x64-portable.zip"
    out.unlink(missing_ok=True)
    shutil.make_archive(str(out.with_suffix("")), "zip", stage.parent, "Hellward")
    record(out, played)
    return out


def record(out: Path, played: dict) -> None:
    manifest = {"file": out.name, "bytes": out.stat().st_size, "sha256": digest(out), "version": VERSION,
                "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                                text=True).stdout.strip(), "smoke": played}
    out.with_suffix(".json").write_text(json.dumps(manifest, indent=1))
    print(json.dumps(manifest, indent=1))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("target", choices=("mac", "windows"))
    args = parser.parse_args()
    print(mac() if args.target == "mac" else windows())
    return 0


if __name__ == "__main__":
    sys.exit(main())
