# Hellward

A gothic tower defence on [Saga2D](../saga2d/) in which the demons have **leaders**, and a leader
curses your towers. It picks the tower and the curse by playing the fight ahead in its head, again
and again, before it casts. Hold the sanctuary gate of a desecrated cathedral for ten waves with
towers of fire, lightning, cold and poison, and with warded gates that bar the arches.

## Play the latest version

```bash
cd ~/saga/hellward
uv run hellward             # the title screen
uv run hellward --demo      # the scripted defender plays against the leaders
```

The first launch renders the stand-in art and the sounds into `~/.hellward/cache` (a few seconds).
`--seed N` changes where the monsters walk; `--fullscreen` fills the screen.

## How to play

| | |
|---|---|
| **1–4** or a build slot, then click the floor | a Pyre (fire), Storm Obelisk (lightning), Frost Shrine (cold) or Plague Totem (poison) |
| **5**, then click an arch | a warded gate: walkers stop and batter it, flyers pass over |
| click a tower | select it: **U** upgrade, **S** sell, **C** cleanse |
| **Space** | call the next wave (gold for every second you spare) |
| **F** / **P** | double the pace / pause |
| **Tab** | show or hide the leaders' minds: the life each curse would save its pack |
| right click / **Esc** | let go of what you hold |

Hover a monster to read its resistances in the bar at the top. Leaders wear a violet ring. When
one ponders, dots rise over its head; when it chants, a violet beam reaches for a tower. Kill it
mid-chant and the curse fizzles, or spend mana (the blue orb) to **Cleanse** a cursed tower. The red
orb is the sanctuary's life.

## More

- [Design](docs/design.md): the rules, how a leader chooses, and how close to optimal it is.
- [Audio](docs/audio.md): the cues, the music and how they are made.
- [AGENTS.md](AGENTS.md): commands and layout for development.
