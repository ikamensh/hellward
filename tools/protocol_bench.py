"""What the protocol costs: the size of a step's frame, the server's time to make and encode one, a round trip.

    uv run python tools/protocol_bench.py [--locations tristram,hells_gate,temple] [--out FILE.json]

Each location is fought through the real server (``python -m hellward.server``) by a scripted player; every frame
that comes back is measured. Encoding is timed in this process on the same defences (the frame built and dumped
from the live world after each step). Round trips are a cheap request answered by the server. The client's parse
time is measured in Godot by ``tools/test.sh`` (tests/run.gd). docs/godot-client.md quotes the numbers;
tests/test_protocol_budget.py holds them to a budget.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

from hellward import fastsim

fastsim.activate()

from hellward.server import protocol  # noqa: E402
from hellward.server.client import Client  # noqa: E402
from hellward.sim import planner  # noqa: E402
from hellward.sim.campaign import LOCATIONS, ORDER  # noqa: E402
from hellward.sim.model import World  # noqa: E402
from hellward.sim.players import PLAYERS  # noqa: E402
from hellward.sim.players.hands import defend  # noqa: E402

PLAYER = "veteran"


def sizes(location: str, seed: int) -> list[int]:
    """Every frame's size in bytes, newline included, over one defence fought through the server."""
    with tempfile.TemporaryDirectory() as data, Client(Path(data), seed=seed) as client:
        client.request("demo", location=location, player=PLAYER)
        out = []
        while True:
            before = client.received
            frames = client.advance(1)
            out.append(client.received - before)
            if frames[-1]["state"]["outcome"] is not None:
                return out


def encode_times(location: str, seed: int) -> list[float]:
    """Seconds to build and encode each step's frame from the live world, in this process."""
    took: list[float] = []
    step = [0]

    def watch(world: World) -> None:
        step[0] += 1
        started = time.perf_counter()
        json.dumps(protocol.frame(world, step[0], world.events), separators=(",", ":"))
        took.append(time.perf_counter() - started)

    defend(LOCATIONS[location], PLAYERS[PLAYER](seed), seed=seed, sigils=3 * ORDER.index(location),
           planner=planner.smart, watch=watch)
    return took


def round_trips(n: int = 500) -> list[float]:
    with tempfile.TemporaryDirectory() as data, Client(Path(data)) as client:
        client.request("profiles")
        out = []
        for _ in range(n):
            started = time.perf_counter()
            client.request("profiles")
            out.append(time.perf_counter() - started)
        return out


def measure(locations: list[str], seed: int = 0) -> dict:
    result: dict = {"locations": {}}
    for key in locations:
        b = sizes(key, seed)
        e = encode_times(key, seed)
        result["locations"][key] = {
            "steps": len(b), "bytes_mean": round(statistics.mean(b)), "bytes_p99": sorted(b)[int(len(b) * 0.99)],
            "bytes_max": max(b), "kb_per_s": round(statistics.mean(b) * 20 / 1024, 1),
            "encode_us_mean": round(statistics.mean(e) * 1e6), "encode_us_max": round(max(e) * 1e6)}
    rt = round_trips()
    result["round_trip_us_median"] = round(statistics.median(rt) * 1e6)
    result["round_trip_us_p99"] = round(sorted(rt)[int(len(rt) * 0.99)] * 1e6)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--locations", default="tristram,hells_gate,temple")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = measure(args.locations.split(","))
    for key, row in result["locations"].items():
        print(f"{key:12} {row['steps']:5} steps  frame {row['bytes_mean']:5} B mean, {row['bytes_p99']:5} p99, "
              f"{row['bytes_max']:5} max ({row['kb_per_s']} KB/s)  encode {row['encode_us_mean']} us mean, "
              f"{row['encode_us_max']} max")
    print(f"round trip {result['round_trip_us_median']} us median, {result['round_trip_us_p99']} us p99")
    if args.out:
        args.out.write_text(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
