# Hellward

A gothic tower defence on [Saga2D](../saga2d/) in which the demons have **leaders**, and a leader
curses your towers. It picks the tower and the curse by playing the fight ahead in its head, again
and again, before it casts. Descend from the burning village of Tristram through its graveyard,
cathedral, catacombs and caves to the gate of hell. Hold each place with towers of fire, lightning,
cold and poison, with warded gates that bar the arches, and with spells. Every victory earns sigils
for a skill tree that carries down with you.

## Play the latest version

```bash
cd ~/saga/hellward
uv run hellward             # the title screen; Descend opens the world map
uv run hellward --demo      # a scripted player defends the cathedral against the leaders
```

The first launch renders the stand-in art and the sounds into `~/.hellward/cache` (a few seconds).
`--seed N` changes where the monsters walk; `--fullscreen` fills the screen.

## How to play

| | |
|---|---|
| **1–4** or a build slot, then click the floor | a Pyre (fire), Storm Obelisk (lightning), Frost Shrine (cold) or Plague Totem (poison) |
| **5**, then click an arch | a warded gate: walkers stop and batter it, flyers pass over |
| click a tower | select it: **U** upgrade, **S** sell, **C** cleanse (mana) |
| **Q** | Smite: with a leader pondering or chanting, it strikes the one closest to cursing and the curse never comes; otherwise click a monster |
| **W**, then click the floor | Meteor: it lands a moment later and leaves the floor burning |
| **E**, then click the floor | Frozen Orb: everything near it freezes, and a leader's curse breaks |
| **Space** | call the next wave (gold for every second you spare) |
| **F** / **P** | double the pace / pause |
| **Tab** | show or hide the leaders' minds: the life each curse would save its pack |
| right click / **Esc** | let go of what you hold |
| **Esc** with nothing held, or **Menu** | pause: settings (music and effects volume, fullscreen), start again, the title, leave |

Hover a monster to read its resistances in the bar at the top. Leaders wear a violet ring. When
one ponders, dots rise over its head; when it chants, a violet beam reaches for a tower and a rune
circle closes round that tower's foot. Smite or freeze the leader before the circle closes and the
curse never lands, or **Cleanse** a cursed tower after. Spells spend mana (the blue orb) and are not
cast while paused. The red orb is the sanctuary's life.

**The campaign.** Each location's intro names who comes, what they resist, the curses their
leaders cast and how to answer them. A victory earns one to three **sigils** by the life you keep;
spend them in the **skill tree** (K on the map or an intro), and unlearn them for free before the
next place. A slot with a padlock is something this place does not offer yet. Holding Hell's Gate wins the
descent. Progress is saved in `~/.hellward/saves`.

## More

- [Design](docs/design.md): the rules of one defence, how a leader chooses, and how close to optimal it is.
- [Campaign](docs/campaign.md): the locations, the skill tree, the spells, the world map, and tuning by simulation.
- [Audio](docs/audio.md): the cues, the music and how they are made.
- [AGENTS.md](AGENTS.md): commands and layout for development.
