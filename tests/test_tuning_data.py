"""The tuning data: every gameplay number in hellward/sim/data, and an override file for experiments."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from hellward.sim import tuning


def _in_child(override: str | None, code: str) -> str:
    env = dict(os.environ, HELLWARD_INTERPRETED="1")
    env.pop(tuning.ENV, None)
    if override is not None:
        env[tuning.ENV] = override
    done = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(done.stderr)
    return done.stdout.strip()


def test_an_override_file_changes_the_numbers_a_new_process_reads(tmp_path):
    override = tmp_path / "harder.toml"
    override.write_text('[monsters.fallen]\nlife = 20\nspeed = 2.0\n')
    code = ("import json; from hellward.sim.content import MONSTERS; "
            "print(json.dumps([MONSTERS['fallen'].hp, MONSTERS['fallen'].speed, MONSTERS['skeleton'].speed]))")
    base = json.loads(_in_child(None, code))
    harder = json.loads(_in_child(str(override), code))
    assert harder[0] == 2 * base[0]
    assert harder[1] == 2.0
    assert harder[2] == base[2]


def test_a_misspelt_override_is_an_error(tmp_path):
    override = tmp_path / "typo.toml"
    override.write_text('[economy]\nbase_gold_unitt = 12\n')
    with pytest.raises(KeyError, match="economy.base_gold_unitt"):
        tuning.load(str(override))


def test_an_override_cannot_replace_a_table_with_a_value(tmp_path):
    override = tmp_path / "flat.toml"
    override.write_text('monsters = 3\n')
    with pytest.raises(TypeError):
        tuning.load(str(override))
