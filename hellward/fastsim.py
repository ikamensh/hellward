"""Hellward's compiled simulation recipe and source/compiled bootstrap.

:mod:`hellward.compiled` owns the mypyc build cache and import handoff. This module chooses the simulation modules
and registers frozen dataclasses for pickle after attach. The server and the tools must activate before importing
any module in :data:`MODULES`. Spawned workers use the build selected by their parent through :data:`ENV`.
:data:`BUILDS` may be moved with ``HELLWARD_BUILDS`` (a release ships its build there).
"""

from __future__ import annotations

import copyreg
import dataclasses
import importlib
import importlib.machinery
import os
from pathlib import Path
from typing import Any

from hellward.compiled import CompiledPackage, NoToolchain

PACKAGE = Path(__file__).resolve().parent
BUILDS = Path(os.environ.get("HELLWARD_BUILDS") or PACKAGE.parent / "build" / "fastsim")
MODULES = ("sim.sums", "sim.content", "sim.level", "sim.campaign", "sim.skills", "sim.model", "sim.planner",
           "sim.players.hands", "sim.players.ordinary", "sim.players.apprentice")
FLAGS = () if os.name == "nt" else ("-ffp-contract=off",)
ENV = "HELLWARD_FASTSIM"
OPT_OUT = "HELLWARD_INTERPRETED"
STALE_AFTER = 3 * 24 * 3600


RUNTIME = CompiledPackage(PACKAGE, MODULES, BUILDS, ENV, OPT_OUT, flags=FLAGS, stale_after=STALE_AFTER)


def key() -> str:
    return RUNTIME.key()


def build() -> Path:
    return RUNTIME.build()


def attach(path: str | os.PathLike[str]) -> None:
    RUNTIME.attach(path)
    _register_pickle()


def _register_pickle() -> None:
    for module in MODULES:
        for value in vars(importlib.import_module(f"hellward.{module}")).values():
            params = getattr(value, "__dataclass_params__", None)
            if isinstance(value, type) and params is not None and params.frozen:
                copyreg.pickle(value, _by_fields)


def _by_fields(row: Any) -> tuple[type, tuple[Any, ...]]:
    """mypyc frozen dataclasses unpickle through their constructors."""
    return type(row), tuple(getattr(row, field.name) for field in dataclasses.fields(row) if field.init)


def activate() -> Path | None:
    """Build or inherit and attach the compiled simulation, unless opted out."""
    root = RUNTIME.activate()
    if root is not None:
        _register_pickle()
    return root


def compiled() -> bool:
    """Whether the world module currently comes from a compiled build."""
    from hellward.sim import model

    return model.__file__.endswith(tuple(importlib.machinery.EXTENSION_SUFFIXES))


if __name__ == "__main__":
    print(build())
