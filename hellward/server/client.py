"""A Python stand-in for the Godot client: it listens, starts the server as its child, and speaks the protocol.

For the tests and the protocol benchmark; the game's own client is ``godot/game/scripts/net.gd``.
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from hellward.server import PROTOCOL


class Refused(Exception):
    """The server turned a request down; the message is its reason."""


class Client:
    def __init__(self, data: Path, *, seed: int = 0, env: dict[str, str] | None = None, timeout: float = 120.0,
                 command: list[str] | None = None) -> None:
        """Start the server (``command``, by default this Python's ``-m hellward.server``) and greet it."""
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(timeout)
        token = secrets.token_hex(8)
        server = command or [sys.executable, "-m", "hellward.server"]
        self.process = subprocess.Popen(
            [*server, "--connect", str(listener.getsockname()[1]), "--token", token, "--data", str(data),
             "--seed", str(seed)], env={**os.environ, **(env or {})})
        self.sock, _ = listener.accept()
        listener.close()
        self.sock.settimeout(timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.reader = self.sock.makefile("rb")
        self.received = 0                   # bytes, for the benchmark
        hello = self.receive()
        # (its pid is not checked: on Windows a virtual environment's python.exe starts the interpreter as a child)
        if (hello["t"], hello["protocol"], hello["token"]) != ("hello", PROTOCOL, token):
            raise RuntimeError(f"unexpected hello: {hello}")
        self.send({"t": "hello", "protocol": PROTOCOL})
        self.status: list[str] = []
        while (message := self.receive())["t"] != "ready":
            self.status.append(message["text"])
        self.compiled: bool = message["compiled"]
        self._ids = 0

    def send(self, message: dict[str, Any]) -> None:
        self.sock.sendall(json.dumps(message).encode() + b"\n")

    def receive(self) -> dict[str, Any]:
        line = self.reader.readline()
        if not line:
            raise ConnectionError("the server closed the connection")
        self.received += len(line)
        message = json.loads(line)
        if message["t"] == "error":
            raise RuntimeError(f"the server failed:\n{message['message']}")
        return message

    def ask(self, request: str, /, **args: Any) -> tuple[list[dict], Any]:
        """A request and its answer: the frames that came before the reply, and the reply's data."""
        self._ids += 1
        self.send({"t": request, "id": self._ids, **args})
        frames = []
        while (message := self.receive())["t"] != "reply":
            frames.append(message)
        if message["id"] != self._ids:
            raise RuntimeError(f"reply {message['id']} to request {self._ids}")
        if not message["ok"]:
            raise Refused(message["why"])
        return frames, message["data"]

    def request(self, request: str, /, **args: Any) -> Any:
        return self.ask(request, **args)[1]

    def order(self, name: str, **args: Any) -> list[dict]:
        """A battle order: the frame of what it did (refusals raise :class:`Refused`)."""
        return self.ask("order", name=name, **args)[0]

    def advance(self, steps: int = 1) -> list[dict]:
        """Whole steps of the battle, a frame each (fewer when it ends or is paused)."""
        self.send({"t": "advance", "steps": steps})
        frames = []
        for _ in range(steps):
            frames.append(self.receive())
            if frames[-1]["state"]["outcome"] is not None:
                break
        return frames

    def close(self) -> int:
        self.send({"t": "quit"})
        code = self.process.wait(timeout=60)
        self.sock.close()
        return code

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *_: Any) -> None:
        if self.process.poll() is None:
            self.close()
