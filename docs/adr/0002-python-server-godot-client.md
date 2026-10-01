# 0002: Python server, Godot client

Status: accepted on 2026-10-01 (Ilya). Requirements: [godot-client.md](../godot-client.md).

## Context

Painted sprites did not give Hellward a look worth taking further; a 3D Tristram in Godot 4 did. Hellward's rules
(the fixed-step simulation, the leaders' rollout planner) and its balance, tuning and replay tools are Python, and
the planner's quality depends on cloning and stepping that simulation.

## Decision

The Python simulation stays the authority and runs as a server process; Godot is a client that draws, plays sound and
sends orders. The server also owns the campaign, its rules and the saves; the client owns every screen, menus
included. The saga2d client is retired.

## Alternatives and consequences

Porting the rules to GDScript or C# would give one process, but two copies of the rules (the tools would keep the
Python one) that drift apart, and the planner would need a rewrite for speed. Python drawing the menus with saga2d
while Godot draws battles would mean two windows and two looks. With the split, transport is negligible (measured:
messages under 2.6 KB, round trips under 20 us); the costs are rebuilding the screens in Godot, shipping Python with
the game, and debugging across two languages.
