"""Every gameplay number, read once from the TOML files in ``hellward/sim/data/``.

Each file is a table named by its stem (``economy.toml`` is ``economy``), and a value is addressed by a dotted
path: ``number("economy.base_hp")``. Tuning means editing those files; nothing else holds a gameplay number.

``HELLWARD_TUNING`` names an override file for an experiment: its top-level tables are the file stems, and every
value in it replaces the one at the same path (``[economy]`` then ``base_hp = 8`` replaces ``economy.base_hp``). A
key the data does not have is an error, so a misspelt override never passes silently. Spawned worker processes
inherit the variable, so the planner's workers and the tools' pools read the same numbers as their parent.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Final

DATA: Final = Path(__file__).resolve().parent / "data"
ENV: Final = "HELLWARD_TUNING"


def _merge(base: dict[str, Any], over: dict[str, Any], where: str) -> None:
    for key, value in over.items():
        path = f"{where}.{key}" if where else key
        if key not in base:
            raise KeyError(f"{ENV}: no tuning value at {path}")
        if isinstance(value, dict) != isinstance(base[key], dict):
            raise TypeError(f"{ENV}: {path} is a {'table' if isinstance(base[key], dict) else 'value'} in the data")
        if isinstance(value, dict):
            _merge(base[key], value, path)
        else:
            base[key] = value


def load(override: str | None = None) -> dict[str, Any]:
    """The data files, with an override file's values in place."""
    tables: dict[str, Any] = {}
    for path in sorted(DATA.glob("*.toml")):
        with path.open("rb") as f:
            tables[path.stem] = tomllib.load(f)
    if override:
        with Path(override).open("rb") as f:
            _merge(tables, tomllib.load(f), "")
    return tables


TABLES: Final = load(os.environ.get(ENV))


def get(path: str) -> Any:
    """The value or table at a dotted path."""
    node: Any = TABLES
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"no tuning value at {path}")
        node = node[part]
    return node


def number(path: str) -> float:
    value = get(path)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"tuning value {path} is not a number: {value!r}")
    return float(value)


def integer(path: str) -> int:
    value = get(path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"tuning value {path} is not an integer: {value!r}")
    return value


def table(path: str) -> dict[str, Any]:
    value = get(path)
    if not isinstance(value, dict):
        raise TypeError(f"tuning value {path} is not a table")
    return value


def numbers(path: str) -> tuple[float, ...]:
    value = get(path)
    if not isinstance(value, list):
        raise TypeError(f"tuning value {path} is not a list")
    return tuple(float(v) for v in value)
