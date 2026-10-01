"""``python -m hellward.server --connect PORT --token T``: the server the Godot client starts.

It connects to the client's loopback port, says hello (the protocol version and the client's token), waits for the
client's hello, then readies the simulation (compiling it on a first launch in a checkout, with a status line for the
client to show) and answers requests until the connection closes: the server lives exactly as long as its client.
A failure is sent to the client as an ``error`` message and ends the server with its traceback on stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import traceback
from pathlib import Path
from typing import Any

from hellward import fastsim
from hellward.server import PROTOCOL

DATA = Path.home() / ".hellward"


class Connection:
    def __init__(self, port: int) -> None:
        self.sock = socket.create_connection(("127.0.0.1", port))
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.reader = self.sock.makefile("rb")

    def send(self, *messages: dict[str, Any]) -> None:
        self.sock.sendall(b"".join(json.dumps(m, separators=(",", ":"), allow_nan=False).encode() + b"\n"
                                   for m in messages))

    def receive(self) -> dict[str, Any] | None:
        line = self.reader.readline()
        return json.loads(line) if line else None


def activate(say) -> None:
    """Run the compiled simulation: attach the build on disk, or compile it once (a checkout's first launch)."""
    if os.environ.get(fastsim.OPT_OUT):
        return
    if not os.environ.get(fastsim.ENV) and not (fastsim.BUILDS / fastsim.key()).is_dir():
        say("Compiling the leaders' minds (first launch only)...")
    try:
        fastsim.activate()
    except fastsim.NoToolchain as missing:
        print(f"hellward: {missing}; running the source simulation", file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hellward's server, for the Godot client")
    parser.add_argument("--connect", type=int, required=True, help="the client's loopback port")
    parser.add_argument("--token", default="", help="the client's token, said back in the hello")
    parser.add_argument("--data", type=Path, default=DATA, help="saves, replays and settings")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--profile", default="main")
    args = parser.parse_args(argv)
    link = Connection(args.connect)
    link.send({"t": "hello", "protocol": PROTOCOL, "token": args.token, "pid": os.getpid()})
    answer = link.receive()
    if answer is None:
        return 0
    if answer.get("t") != "hello" or answer.get("protocol") != PROTOCOL:
        link.send({"t": "error", "message": f"the client speaks protocol {answer.get('protocol')}, the server {PROTOCOL}"})
        return 2
    activate(lambda text: link.send({"t": "status", "text": text}))
    from hellward.server.campaign import Campaign
    from hellward.server.service import Service
    from hellward.server.thinking import Thinker
    from hellward.sim.players.adaptive import Adaptive

    thinker = Thinker()
    try:
        service = Service(Campaign(args.data, planner=thinker, demo_player=Adaptive, seed=args.seed,
                                   profile=args.profile))
        link.send({"t": "ready", "compiled": fastsim.compiled()})
        while (message := link.receive()) is not None:
            if message["t"] == "quit":
                break
            try:
                link.send(*service.handle(message))
            except Exception:
                link.send({"t": "error", "message": traceback.format_exc(limit=8)})
                raise
    finally:
        thinker.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
