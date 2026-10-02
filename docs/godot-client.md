# Hellward on Godot: Python rules, Godot client

Status: agreed with Ilya on 2026-10-01; steps 1-3 built on 2026-10-01/02 and released as 0.2.0 for Apple Silicon
and Windows (step 5; [docs/release.md](release.md)) on https://games.tachyon-ai.eu/hellward/ (see "As built" at the end). The decision
is [ADR 0002](adr/0002-python-server-godot-client.md). The client grew from the 3D Tristram demo, now `godot/`; why
Godot is in [its engine notes](../godot/docs/engine.md).

## Goal

Hellward becomes a Godot 4 game with the 3D demo's look. Its rules, campaign and saves run in a Python process,
the **server**. Godot is the **client**: every screen, all input, sound and visuals. The saga2d client is retired;
git history keeps it for reference.

## Requirements

### 1. Who owns what

| Server (Python, the authority) | Client (Godot, presentation only) |
|---|---|
| Battles: `hellward/sim` as it is, compiled (`fastsim`), stepping at `SIM_DT` (0.05 s) | Every screen: title, profiles, world map, briefing, skill tree, forge, story pages and Chronicle, battle, pause, reckoning |
| The leaders' planner, in worker processes as `ui/thinking.py` runs it today: a decision never stalls a step (decisions took up to 197 ms inline) | Input, camera, HUD, effects, sound and music playback |
| Campaign progression: unlocks, sigils, the skill tree, respec, breaches, salvage, the forge | Local preferences: volume, fullscreen, resolution, graphics quality |
| Profiles and saves in `~/.hellward/saves`, including upgrading old save files | Smoothing positions between server steps; cosmetic prediction only (a ghost tower, a click), never a rule |
| Which story page is due, which pages were seen | Story pages' layout and art (the panels in `assets/story/` move to the client) |
| Replays (the order log), scripted players, the demo defender | |

The client computes no rule: no damage, cost, range, unlock or outcome. It shows what the server says, and asks.

### 2. One repository

Merge `~/saga/hellward3d` into `~/saga/hellward` (the Godot project in `godot/`), so a protocol change lands in one
commit on both sides and one test run covers both. Delete `hellward3d` afterwards, and update the stack root
(`README.md`, `AGENTS.md`, `Makefile`: `make hellward` starts the Godot client).

### 3. Process and transport

- The client starts the server as a child process at launch: in development `uv run python -m hellward.server`, in a
  release a bundled Python. The title shows at once; the client connects in the background (the server takes 1-2 s).
- The server lives exactly as long as the client: it exits when the client's connection or its stdin closes.
  Either side dying is reported plainly, never swallowed.
- Messages are newline-delimited JSON. Measured on 2026-10-01 over real defences (Tristram, Hell's Gate, Temple):
  a step's message is 270-400 bytes (2.6 KB at most), ~8 KB/s; encoding 5 us; Godot parses the largest in 26 us;
  a loopback round trip is 8-17 us. The transport is not a cost worth optimising.
- Godot has no Unix-socket peer: use loopback TCP (`StreamPeerTCP`), or the child's stdio via `OS.execute_with_pipe`
  (verify non-blocking reads in Godot 4.7 before choosing it: it would need no port and ends with the client).
- Events are compact and typed: kinds, ids and numbers. Never Python object text (a planner `Decision`'s repr made
  the largest measured message).
- A `hello` exchange carries a protocol version; a mismatch is an error, not a guess.

### 4. Battle protocol

- On start the server sends the level once: grid, routes, doors and arches, theme, waves, the arsenal on offer, the
  monster and tower tables the HUD shows. (This replaces `hellward3d/tools/export_level.py`.)
- Each step the server sends the step's events (spawn, move state, hit with element, death, leak, shot and its target,
  curse pondered, chanted, landed, broken, marked; spells; gates; wave called and cleared; gold, lives, mana;
  outcome) and a snapshot of every monster (id, kind, route, distance along it, lane offset, life, chill, frozen,
  poison, chanting) and tower (id, kind, rank, curses and their time left, cooldown readiness).
- The client sends orders: build, upgrade, sell, cleanse, spells with their target (Smite, Meteor, Frozen Orb), gate
  build and repair, call the wave, sell salvage, breach choices, pace, pause. The server answers each with accepted or
  refused and why, and the client plays the refusal.
- Real time: the server steps at 20 Hz times the pace; the client draws at its frame rate, smoothing between steps.
- Scripted players stay server-side. "Demo" is the server running a scripted player while the client watches; the
  client's film director keeps working from events (it already only reads events and positions).
- Replays: the server logs every order with its step, and a logged defence replays on the server as today
  (`tools/margin.py --replay`).

### 5. Campaign protocol

Profiles (list, create, switch); the campaign view (acts, locations, which are open, sigils and best results); a
location's briefing (who comes, resistances, leaders' curses, lesson, taunt, arsenal, breach); the skill tree (nodes,
ranks, costs, learned; learn, unlearn, respec); the forge (salvage, trophies, patterns, equip); the story (pages due
now, Chronicle); starting a battle with the chosen loadout and its result coming back into the campaign.

### 6. Content

The demo covers Tristram, Fallen, Shaman, Zombie, Skeleton and four tower families. The campaign needs all twelve
locations (two acts, each with its theme), every monster kind and boss (Azazel, the Bone Priest), all seven tower
families in three ranks, gates and arches, the four spells, breaches, both world maps and the story panels. Build
them with the demo's pipeline: Blender scripts, Codex-painted textures, the material library, the effect sprites.

### 7. What goes, what stays

- **Deleted:** `hellward/ui/` except what moves to the server (`progress.py` without saga2d, `thinking.py`),
  `hellward/art/` (the stand-in renderers and sprite registration), `hellward/__main__.py`'s saga2d game,
  `audio/bank.py`, the painted sprite sheets and rig pilots in `assets/` (`painted`, `puppet`, `rigged`, `terrain`),
  and the 3D demo's GDScript rules (`world.gd`'s waves and economy, `monster.gd`'s movement, `demo.gd`'s defender).
- **Kept:** `hellward/sim/` unchanged by the move; `story.py` (content); `audio/cues.py` and `music.py` as asset
  tools that write the files the client plays; the balance, tuning and replay tools and their tests.
- `fastsim.py` compiles through `saga2d.compiled`: keep that one dependency on the saga2d release, or move the helper
  into Hellward. Nothing else may import saga2d.

### 8. Verification

- The simulation and its tools are untouched by the move: `uv run pytest -q`, `tools/balance.py`,
  `tools/curse_quality.py` give the same numbers before and after; `tests/test_fastsim.py` holds.
- A protocol test plays a logged defence through the server and checks its event digest against `hands.defend`
  run directly: the server adds transport, never a different battle.
- A client test (headless Godot, as `hellward3d/tools/test.sh`) plays a battle against the real server: build by
  mouse, call waves, a curse lands and Cleanse lifts it, victory and defeat end the battle and its music.
- A campaign test walks title, profile, map, briefing, skill tree, battle and back, against the real server.
- A protocol benchmark keeps the measured budget honest (message size, encode and parse time, round trip).
- Visual changes are checked in rendered frames. Rendering never disturbs the person at the Mac: only through
  `godot-capture.sh` and `scenes/capture.tscn` (offscreen, silent, no Dock icon); never the Godot binary directly.

### 9. Not now

Online play (keep it possible: the server is already the authority over a socket), mobile, porting the simulation to
GDScript or C#, a Windows build (the transport choice must not rule it out).

## Order of work

1. The server: `python -m hellward.server`, the transport, the battle protocol, the protocol test.
2. The client plays Tristram through the server: the demo's battle screen driven by server events; its GDScript rules
   deleted. Merge the repositories here, and retire the saga2d client once this battle works end to end.
3. The campaign protocol and the Godot screens: title, profiles, map, briefing, skill tree, forge, story.
4. Content: the other eleven locations, the rest of the monsters, towers, gates, spells and bosses.
5. A release build: Godot export plus bundled Python, on the Mac first.

## As built (2026-10-02)

- **Transport.** Loopback TCP, the other way round: the client listens on an ephemeral port and starts
  `python -m hellward.server --connect PORT --token T`, which connects back and says the token and its protocol
  in its hello; the client answers with its own. No port is agreed in advance, nothing listens but the client,
  and the server ends when the connection closes (its planner workers end with it). Godot's child stdio was not
  needed. `Net` (`godot/game/scripts/net.gd`) is the client's side, `hellward/server/__main__.py` the server's.
- **The clock is the client's.** Rather than the server stepping at 20 Hz on its own, the client counts its
  frames' time (`Engine.time_scale` is the pace) and asks for the whole steps it adds up to (`advance`); the server
  answers each with a frame. The battle still runs at 20 Hz times the pace in real time, and it gains: a paused or
  hidden game asks for nothing, tests and recordings at a fixed frame rate stay in step with what they draw, a
  slow planner holds the clock (at most four steps asked ahead) instead of bursting, and the client always knows
  how far between two steps it is drawing. Online play would hand the clock back to the server.
- **Messages.** `hellward/server/protocol.py` and `service.py` list them: the battle's start (map, routes, gates,
  waves, arsenal, tables), a frame per step (events with the newcomers' facts, purse and clocks, monsters
  `[id, s, hp, flags, chill, frozen, poison, door]`, towers `[id, level, reach, curses, ward, upgrade cost, needs,
  refund]`, gates, burning ground), orders answered by a frame and a reply or by a refusal with its reason, and
  the campaign's requests answered with finished words (a briefing's lines, a skill's tooltip, the reckoning).
- **Measured** (`tools/protocol_bench.py`, 2026-10-01, M4, veteran player): a frame is 0.9-1.0 KB on average and
  2.2 KB at most (17-19 KB/s); the server builds and encodes one in 19-21 us; a request's round trip is 50 us
  (p99 100 us); Godot parses the largest frame of a defence in 35 us. Held to a budget by
  `tests/test_protocol_budget.py` and `godot/game/tests/run.gd`.
- **Verification.** `tests/test_server.py` (a scripted defence through the server is `hands.defend` event for
  event; a person's orders log a defence whose ghost fights the identical battle), `tests/test_campaign_server.py`
  (the campaign's rules through the real server, including a defence won by the real rules), `godot/tools/test.sh`
  (the client against the real server: building by mouse, refusals, waves, a curse and Cleanse, defeat and
  victory with their music, the frame parse, and a walk through the campaign's screens).
- **Content (step 4, under way).** All twelve locations play with their own scenery. Every tower family has a
  model per rank (`tools/blender/tower_<kind>.py` builds `tower_<kind>_1..3`). Monsters: the Fallen, Shaman, Zombie
  and Skeleton are hand-made (godot/docs/monsters.md); the other fifteen kinds, the two bosses among them, have
  concepts painted from the 2D game's sheets and short specs (`biped.py`, `beast.py`) waiting on their generated
  meshes, and wear a tinted stand-in (`monster.gd STAND_INS`) until then. What is built and what is a stand-in:
  `tools/assets.py`, `godot/tools/survey.sh`; checked by `tests/test_client_assets.py`, the client tests (every
  kind's body over every location), `godot/tools/blender/audit.py` (clips) and `tools/visual_check.py` (every screen
  and battle rendered and checked).