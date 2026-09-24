"""The leaders think in another process, so a rollout never costs the screen a frame.

The world asks for a decision at a step boundary and reads it half a second of game time later
(:data:`hellward.sim.model.DECIDE_DELAY`); the worker has that long, and the decision is the same one
:func:`hellward.sim.planner.decide` returns inline, so the game stays deterministic for a seed.
"""

from __future__ import annotations

from concurrent.futures import Future, ProcessPoolExecutor

from hellward.sim import planner
from hellward.sim.model import World


def _decide(world: World, leader_id: int) -> planner.Decision:
    return planner.decide(world, leader_id)


class Thinker:
    def __init__(self, workers: int = 2) -> None:
        self.pool = ProcessPoolExecutor(workers)
        self.pool.submit(int, 0).result()   # start the workers now, not in the first fight

    def __call__(self, world: World, leader_id: int) -> Future:
        return self.pool.submit(_decide, world.clone(), leader_id)

    def close(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=True)
