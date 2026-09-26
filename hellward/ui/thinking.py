"""The leaders think in another process, so a rollout never costs the screen a frame.

The world asks for a decision at a step boundary and reads it half a second of game time later
(:data:`hellward.sim.model.DECIDE_DELAY`); the worker has that long, and the decision is the same one
:func:`hellward.sim.planner.decide` returns inline, so the game stays deterministic for a seed.

The workers run the same compiled simulation as the game: the pool initializer activates the build the
parent activated (through :data:`hellward.sim.fastsim.ENV`) before anything unpickles a world, so the
worlds the game sends over round-trip between the compiled parent and the compiled workers. This module
imports nothing from the simulation at load time for exactly that reason: a spawned worker imports it
before the initializer runs.
"""

from __future__ import annotations

import multiprocessing
import multiprocessing.connection
import os
import signal
import threading
from concurrent.futures import Future, ProcessPoolExecutor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hellward.sim import planner
    from hellward.sim.model import World


def _decide(world: World, leader_id: int) -> planner.Decision:
    from hellward.sim import planner

    return planner.decide(world, leader_id)


def _start_worker() -> None:
    """Activate the parent's build, then serve the game: ignore Ctrl-C and end with it however it ends."""
    from hellward.sim import fastsim

    try:
        fastsim.activate()
    except fastsim.NoToolchain:
        pass   # the game runs the source: so does this worker
    _serve_the_game()


def _serve_the_game() -> None:
    """A worker ignores Ctrl-C (the game closes the pool) and ends with the game however it ends: Cmd+Q on
    a Mac, for one, exits the process without closing anything."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    parent = multiprocessing.parent_process()

    def watch() -> None:
        multiprocessing.connection.wait([parent.sentinel])
        os._exit(0)

    threading.Thread(target=watch, name="hellward-parent-watch", daemon=True).start()


class Thinker:
    def __init__(self, workers: int = 2) -> None:
        self.pool = ProcessPoolExecutor(workers, initializer=_start_worker)
        self.pool.submit(int, 0).result()   # start the workers now, not in the first fight

    def __call__(self, world: World, leader_id: int) -> Future:
        return self.pool.submit(_decide, world.clone(), leader_id)

    def close(self) -> None:
        self.pool.shutdown(wait=True, cancel_futures=True)   # waiting releases the pool's semaphores
