"""The simulation compiled to C by mypyc, for the tools that play thousands of defences.

    uv run python -m hellward.sim.fastsim      # build it now (the tools build it on first use) and say where

The modules in :data:`MODULES` (the tables, the maps, the campaign, the skills, the world, the leaders' planner
and the scripted players) are compiled from their own source, so a compiled defence is the interpreted one:
mypyc keeps Python's integer and float semantics and every operation's order, and the C is built with
``-ffp-contract=off`` so that no multiply and add are fused into one rounding. ``tests/test_fastsim.py`` holds
the two to the same events and the same world, to the bit. A new scripted player joins :data:`MODULES` when
the balance tools play it, and its module must then pass ``mypy`` like the rest.

What the compiler asks in return is that the annotations are true. A value of the wrong type reaching compiled
code raises ``TypeError`` there, where the interpreter would have carried on, so ``uv run mypy`` over the modules
stays clean. A compiled class has no ``__dict__`` (no ``vars()``), a ``Final`` constant is inlined where it is
read (rebinding it changes nothing compiled), and the built-in ``sum`` adds floats differently compiled
(:mod:`hellward.sim.sums` says how).

A build is filed under ``build/fastsim/`` by a hash of the sources, the interpreter and the platform, so an
edited source is never run as an old build: the next activation compiles it again, and removes the builds no
process has started on for :data:`STALE_AFTER` (:func:`prune`).

:func:`activate` is called by ``tools/balance.py``, ``tools/curse_quality.py`` and ``tools/sim_bench.py`` when
they run as programs, before they import the simulation, and again in the worker processes they spawn, which
run the same script as ``__mp_main__`` and take the parent's build from :data:`ENV`. A process that imports
them as a library stays as it was. The game, its planner's worker (:mod:`hellward.ui.thinking`) and the tests
run the source. ``HELLWARD_INTERPRETED=1`` makes :func:`activate` a no-op.
"""

from __future__ import annotations

import copyreg
import dataclasses
import hashlib
import importlib
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]   # hellward/, whose subpackages hold the modules
BUILDS = PACKAGE.parent / "build" / "fastsim"
MODULES = ("sim.sums", "sim.content", "sim.level", "sim.campaign", "sim.skills", "sim.model", "sim.planner",
           "sim.players.hands", "sim.players.ordinary", "sim.players.apprentice")
FLAGS = () if sys.platform == "win32" else ("-ffp-contract=off",)   # every float operation rounds on its own, as Python's
ENV = "HELLWARD_FASTSIM"          # the build a process activated, for the worker processes it starts
OPT_OUT = "HELLWARD_INTERPRETED"
NO_TOOLCHAIN = 3                  # the compiling process's exit status when this machine cannot compile at all
STALE_AFTER = 3 * 24 * 3600       # longer than any run: its workers attach when it starts


class NoToolchain(RuntimeError):
    """This machine cannot compile the simulation: mypyc or a C compiler is missing. The message says which."""


def source(module: str) -> str:
    """The file of a module of :data:`MODULES`, under ``hellward/``."""
    return module.replace(".", "/") + ".py"


def key() -> str:
    """The build's identity: its sources, its compiler flags, the interpreter and the platform."""
    digest = hashlib.sha256()
    for module in MODULES:
        digest.update(module.encode() + b"\0" + (PACKAGE / source(module)).read_bytes() + b"\0")
    digest.update(f"{FLAGS}|{sys.implementation.cache_tag}|{sysconfig.get_platform()}".encode())
    return digest.hexdigest()[:20]


BUILD_SCRIPT = """
import json, sys
from pathlib import Path
from setuptools import Extension, setup
config = json.loads(sys.argv[1])
try:
    from mypyc.build import mypycify
except ImportError:
    print("mypyc is not installed (uv sync --extra dev installs it)", file=sys.stderr)
    sys.exit(config["no_toolchain"])
probe = Path(config["obj"], "probe.c")
probe.parent.mkdir(parents=True)
probe.write_text("#include <Python.h>\\nPyMODINIT_FUNC PyInit_probe(void) { return NULL; }\\n")
try:  # before mypyc spends its time: setup() turns a missing C compiler into SystemExit("error: ...")
    setup(name="probe", packages=[], py_modules=[], ext_modules=[Extension("probe", [str(probe)])],
          script_args=["build_ext", "--build-lib", str(probe.parent), "--build-temp", str(probe.parent)])
except SystemExit as failed:
    print("no C compiler (" + " ".join(str(failed).split()) + ")", file=sys.stderr)
    sys.exit(config["no_toolchain"])
modules = mypycify(["--cache-dir=" + config["cache"], "--follow-imports=silent", *config["paths"]], target_dir=config["c"])
for module in modules:
    module.extra_compile_args.extend(config["flags"])
setup(name="hellward-fastsim", packages=[], py_modules=[], ext_modules=modules,
      script_args=["build_ext", "--build-lib", config["out"], "--build-temp", config["obj"]])
"""


def build() -> Path:
    """The compiled modules for the current sources, compiling them first if no build has them yet."""
    target = BUILDS / key()
    if target.is_dir():
        return target
    BUILDS.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f"{target.name}-", dir=BUILDS))
    config = {"paths": [f"hellward/{source(m)}" for m in MODULES], "flags": list(FLAGS), "no_toolchain": NO_TOOLCHAIN,
              "cache": str(staging / "mypy"), "c": str(staging / "c"), "out": str(staging), "obj": str(staging / "obj")}
    print(f"compiling the simulation with mypyc into {target}, once per change to its sources...", file=sys.stderr,
          flush=True)
    done = subprocess.run([sys.executable, "-c", BUILD_SCRIPT, json.dumps(config)], cwd=PACKAGE.parent,
                          capture_output=True, text=True)
    if done.returncode:
        shutil.rmtree(staging, ignore_errors=True)
        if done.returncode == NO_TOOLCHAIN:
            raise NoToolchain(f"{done.stderr.strip().splitlines()[-1]}; {OPT_OUT}=1 runs the source")
        raise RuntimeError(f"mypyc could not compile the simulation (uv run mypy shows why):\n{done.stdout[-4000:]}\n"
                           f"{done.stderr[-4000:]}")
    for scratch in ("mypy", "c", "obj"):
        shutil.rmtree(staging / scratch)
    try:
        staging.rename(target)
    except OSError:   # another process finished the same build first; theirs is as good
        shutil.rmtree(staging)
    prune(keep=target)
    return target


def prune(keep: Path) -> None:
    """Remove what no process has attached for :data:`STALE_AFTER` from :data:`BUILDS`: old builds and the staging
    folders of interrupted ones, never *keep* or the build this process runs (:data:`ENV`).

    Every activation touches its build, a spawned worker's too, so the age is the time since a process last started
    on it; a process that has loaded its modules no longer needs their files (macOS, Linux). A build is renamed out
    of its key before it is removed, so a removal that stops half way never leaves a folder that :func:`build` would
    take for a whole build."""
    spared = {keep.name, Path(os.environ.get(ENV, keep)).name}
    now = time.time()
    for entry in BUILDS.iterdir():
        if entry.name in spared:
            continue
        try:
            if now - entry.stat().st_mtime < STALE_AFTER:
                continue
            doomed = entry if entry.name.endswith(".pruned") else entry.rename(entry.with_name(entry.name + ".pruned"))
        except OSError:   # another process pruned it meanwhile
            continue
        shutil.rmtree(doomed, ignore_errors=True)


def attach(path: str | os.PathLike[str]) -> None:
    """Import :data:`MODULES` from the build at *path* from now on; it must match the current sources.

    The build holds no ``__init__.py``: each source package stays the package, with the build's folder first on its
    path, put there before the package's own ``__init__`` runs (``players/__init__.py`` imports the players). The
    modules are imported here, and their frozen dataclasses made picklable (:func:`_by_fields`)."""
    root = Path(path)
    if not root.is_dir():
        raise ImportError(f"the compiled simulation {root.name} is missing")
    if root.name != key():
        raise ImportError(f"the compiled simulation {root.name} was built from other sources: the current ones make {key()}")
    os.utime(root)   # in use: prune() spares it for STALE_AFTER from now
    packages = sorted({f"hellward.{m.rpartition('.')[0]}" for m in MODULES})   # parents before their subpackages
    folders = {name: str(root / name.replace(".", "/")) for name in packages}
    if all(name in sys.modules and folders[name] in sys.modules[name].__path__ for name in packages):
        return
    loaded = sorted(name for name in sys.modules if name.startswith("hellward.") and name.removeprefix("hellward.") in MODULES)
    if loaded:
        raise RuntimeError(f"the compiled simulation must be activated before it is imported; already loaded: {loaded}")
    sys.path.insert(0, str(root))   # mypyc's shared library of the whole group
    for name in packages:
        _search_first(name, folders[name])
    os.environ[ENV] = str(root)
    for module in MODULES:
        for value in vars(importlib.import_module(f"hellward.{module}")).values():
            params = getattr(value, "__dataclass_params__", None)   # a dataclass's, or its instances'
            if isinstance(value, type) and params is not None and params.frozen:
                copyreg.pickle(value, _by_fields)


def _search_first(name: str, folder: str) -> None:
    """Put *folder* first on package *name*'s path, importing the package if need be, between the making of the
    package and the running of its ``__init__``, as the import system itself does."""
    package = sys.modules.get(name)
    if package is not None:
        package.__path__.insert(0, folder)
        return
    spec = importlib.util.find_spec(name)
    if spec is None or spec.loader is None or spec.submodule_search_locations is None:
        raise ImportError(f"{name} is not a package")
    spec.submodule_search_locations.insert(0, folder)
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    parent, _, child = name.rpartition(".")
    setattr(sys.modules[parent], child, package)
    spec.loader.exec_module(package)


def _by_fields(row: Any) -> tuple[type, tuple[Any, ...]]:
    """A compiled frozen dataclass (a table's row, a map, a plan) pickled as a call of its class with its fields:
    unpickling sets an object's attributes one by one, which a compiled frozen dataclass refuses."""
    return type(row), tuple(getattr(row, f.name) for f in dataclasses.fields(row) if f.init)


def activate() -> Path | None:
    """Run the compiled simulation in this process and every process it starts; its build path, or None when opted out.

    A worker process takes the build its parent activated, never one of its own: sources edited since the parent
    started are refused rather than compiled again in every worker."""
    if os.environ.get(OPT_OUT):
        return None
    inherited = os.environ.get(ENV)
    root = Path(inherited) if inherited else build()
    attach(root)
    return root


def compiled() -> bool:
    """Whether this process runs the compiled simulation (the world's module came from a build)."""
    from hellward.sim import model

    return model.__file__.endswith(tuple(importlib.machinery.EXTENSION_SUFFIXES))


if __name__ == "__main__":
    print(build())
