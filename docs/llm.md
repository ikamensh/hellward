# Hellward for an LLM player

An LLM plays a defence as text through `tools/llm_play.py`: a briefing once,
one command per line, and a digest every few seconds of game time. The package
`hellward/llm/` holds the views (`view.py`), the quick math (`advisor.py`), the
real-time reflexes (`auto.py`) and the turn loop (`driver.py`).

```bash
uv run python tools/llm_play.py tristram --profile sophie   # the campaign, kept
uv run python tools/llm_play.py graveyard --seed 3 --skills adept_arrow   # the lab
uv run python tools/llm_play.py tristram --script myscript.txt   # one command per line
```

The loop is: read the briefing, `build` during the break, `call` the wave (or let
it come), `watch` for one digest at the next break, repeat. Spells the LLM
cannot aim in real time are armed as autos (`auto meteor on`) and reported in
the digest. Nothing mid-wave needs ruminating on: `watch` plays to the next
break (or `watch leaks N` stops early once N lives leak), and the digest ends
with an action line (`afford (14g): arrow gate | top: arrow (13,10)`) so a
`status` and an `advise` rarely need asking after it. `wait` stays for the
moments fine control is wanted.

## Profile and meta progression

With `--profile`, the session keeps a campaign in the data dir (default
`~/.hellward`, `--data` overrides): the same profiles, saves and replays as the
game. `defend` opens only open locations; a decided defence banks its sigils,
unsold salvage and side trophy and saves; quitting mid-fight keeps nothing.
Without `--profile` it is a lab: any location, `--skills` fixed at launch,
nothing kept.

| Command | Effect |
|---|---|
| `campaign` | profile, free/won sigils, per-act map (best/open/closed), materials |
| `defend <location>` | begin that defence (profile-gated, or free in the lab) |
| `learn <skill>` / `unlearn` | spend sigils / take everything back; applies next `defend` |
| `skills [location]` | the tree, one line per column (`*`learned, learnable[cost]) |
| `forge [pattern]` | the forge, or its one button (forge+equip / equip / unequip) |
| `profiles` / `profile <name>` | list profiles / switch (a new name starts one; ends the defence) |

Meta budgets: `campaign` < 800 chars, `skills` < 2500, `forge` < 1500.
A kept campaign needs honest leaders: `--leaders none` is lab-only.

Every defence runs through the server's battle object, orders and autos join
its replay log, and decided profile defences write replay files: a logged
defence's ghost fights the identical battle, event for event.

## Token budgets

The briefing is sent once; everything repeated stays small. Tests hold these:

| Text | Budget | Typical |
|---|---|---|
| Briefing (arsenal, foes, waves, map) | < 6000 chars | ~3000 |
| `status` | < 1600 chars | ~400 |
| `wait` digest | < 1200 chars | ~350 (ends with the action line) |
| `watch` digest | < 1600 chars | ~400 (one per wave) |
| `advise` answer | < 800 chars (N=5) | ~300 |

The map prints once (one char per tile with x/y rulers, towers as `T`).
`status` never reprints it; `map` does on request. The field is bucketed by
route progress (far/mid/near/gate thirds with kind counts and life), not listed
per monster — only leaders and smite targets carry ids.

## Commands

Tiles are `x y` (x right, y down, as the map's rulers read). `help` in the game
lists the same.

| Command | Effect |
|---|---|
| `status [towers]` | purse, tower counts (+cursed/hymned/ranked), next wave; `towers` lists all |
| `map` | the map with towers |
| `threats` | smite targets with ids (chanting leaders first) |
| `build <kind> <x> <y>` / `up` / `sell` / `gate <n>` | the building orders |
| `call` | start the next wave early for bonus gold |
| `breach cash\|trophy\|decline`, `salvage` | the break's side choices |
| `smite [id]`, `hymn <x> <y>`, `meteor <x> <y>`, `orb <x> <y>` | aimed spells (bare `smite` picks the best target) |
| `auto [<rule> on\|off]` | reflexes (below); bare `auto` lists them |
| `advise <kind> [N]` | best N tiles for a tower kind (default 5, max 10) |
| `advise wave [n]` | a wave's mix and the best tower per gold |
| `advise up <x> <y>` | rank this tower or build anew, per gold |
| `wait [seconds]` | play on (default 4) and report the digest |
| `watch [leaks N]` | play to the next break (or N leaked lives) in one digest |
| `briefing`, `quit` | repeat the briefing; leave |

A refusal answers `refused: <why>` and changes nothing. Unknown commands and
bad arguments say so with the right shape.

## Advisors (quick math, no lookahead)

- `advise <kind>` scores every empty buildable tile by traffic-weighted path in
  reach times felt damage per second against the coming mix, less the shared
  curse-spacing penalty. Support towers score cover with a note of their own
  rule (knife near a gate, hook over small-foe traffic).
- `advise wave [n]` totals the wave (bodies, life, flyers, armor, leaders) and
  ranks the offered damage towers by felt dps per gold against its mix.
- `advise up <x> <y>` compares the rank's marginal dps per gold against every
  new tower's. All three are pure arithmetic over the authored waves and the map
  geometry: milliseconds, deterministic for a state, no simulation.

## Autos (the real-time hands)

The LLM answers a leader's sign a second late (`REACT`), like a person, and its
aimed spells keep a one-second gap. Armed reflexes act every step inside that:

| Rule | Default | Reflex |
|---|---|---|
| `smite_leader` | on | smite a chanting/marked leader a Smite kills |
| `smite_leak` | on | smite a foe ≤2.5 s out a Smite kills |
| `hymn` | off | hymn the busiest tower (3+ foes in/near reach), keeping Smite mana |
| `meteor` | off | meteor a 3+ pack worth 3 blows |
| `orb` | off | freeze a mobbed gate under half life |

Autos see only what the screen shows (delayed signs, positions, life): no
planner state, no clones. The digest reports every cast.

## Example

```
> advise arrow
arrow tiles: (14,10) score 11.1 cover 5.6 dps 2.0; (16,7) ...
> build arrow 14 10
built #2 arrow at 14,10 — t=0.0 BREAK 30.0s wave -/5 | gold 24 lives 20 mana 60/100
> build arrow 16 7
built #3 arrow at 16,7 — t=0.0 BREAK 30.0s wave -/5 | gold 12 lives 20 mana 60/100
> call
called w1 'The Fallen Swarm' (+0g) — t=0.0 FIGHTING wave 1/5 | gold 12 ...
> wait 4
+4.0s t=4.0 FIGHTING wave 1/5 | gold 12 lives 20 mana 66/100 (gold 12->12, kills 0->0)
waves: started w1
field: 4 foes 24hp: far fallenx4 (24hp)
```

## Limits (v1)

The story, world-map travel animation and act endings stay in the client; the
text seat plays defences and spends their rewards. `wait` caps at 30 s per
call. The leaders play `smart` by default.
