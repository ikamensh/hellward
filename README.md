# Hellward

A gothic tower defence in 3D in which the demons have **leaders**, and a leader curses your towers. It picks
the tower and the curse by playing the fight ahead in its head, again and again, before it casts. Defend
twelve locations in two acts, from burning Tristram through Hell's Gate and across Kurast to the Temple of Light.
The first defence gives you a single-target Arrow Tower and Cleanse; gates, elemental towers, spells and larger
attacks arrive gradually. Monsters enter from different sides and may wander along longer trails, while runners
head straight for the sanctuary.

The game is a [Godot 4.7](https://godotengine.org) client (`godot/`) over a Python server (`hellward/server`)
that plays the rules, the leaders' minds and the campaign: [docs/godot-client.md](docs/godot-client.md).

## Play the latest version

```bash
brew install --cask godot            # once (Godot 4.7)
cd ~/saga/hellward
uv sync --extra dev                  # once: the server's environment
uv run hellward                      # the title screen; Descend begins the campaign
uv run hellward -- screen=map        # straight to a screen (title, map, briefing location=KEY, skills, forge...)
```

The client starts the server itself. The first launch after an update imports the client's new files and
compiles the leaders' minds (up to a minute, once). The title's **Campaign profiles** button (or **P**) switches between saves or names a new one;
the `main` profile keeps your existing save. Saves live in `~/.hellward/saves`, replays of your defences in
`~/.hellward/replays`; the client's own settings (volumes, fullscreen) stay on this machine.

## How to play

| | |
|---|---|
| **1** or the first build slot, then click buildable ground | an Arrow Tower: one arrow at one monster; your opening attack |
| **2–5**, then click buildable ground | Pyre, Storm, Frost and Plague towers as later locations unlock them |
| **6**, then click an arch | a warded gate, available from the Graveyard: walkers stop and batter it, flyers pass over |
| **7–8**, then click buildable ground | Bone Altar and Druid Grove support towers in Act II |
| click a tower | select it: **U** upgrade, **Delete** sell, **R** cleanse (mana) |
| **Z** (from the Graveyard) | Smite: with a leader pondering or chanting, it strikes the one closest to cursing; otherwise click a monster |
| **X** (from Travincal), then click the floor | Meteor: it lands a moment later and leaves the floor burning |
| **C** (from the Jungle), then click the floor | Frozen Orb: nearby monsters freeze; an interruptible leader's chant breaks |
| **V** during a wave break | sell one held salvage for battle gold instead of banking it for the forge |
| **Space** | call the next wave; ending a break early can grant a small gold bonus |
| **F** | double the pace |
| **H** | hide the HUD |
| **WASD** / arrow keys / the window's edges | pan the camera; during a defence the mouse stays in the window (Settings can let it go) |
| **Q** / **E** or the wheel, middle drag | zoom in / out, turn the camera |
| right click / **Esc** | let go of what you hold |
| **Esc** with nothing held | pause: settings (music and effects volume, fullscreen, the battle interface's size, the mouse kept in the window), start again, the map, the title, leave |

Leaders wear a violet ring and their life shows over the field. When
one ponders, dots rise over its head; when it chants, a violet beam reaches for a tower and a rune
circle closes round that tower's foot. Later, Smite or Frozen Orb can break an interruptible chant
before it lands. Marked and resolute curses cannot be interrupted; **Cleanse** removes curses from
a tower afterward, even in the opening defence. Spells spend mana (the blue orb) and are not cast
while paused. The red orb is the sanctuary's life.

**The campaign.** Each location's intro names who comes, what they resist, the curses their
leaders cast and how to answer them. A victory earns one to three **sigils** by the life you keep;
spend them in the **skill tree** (K on the map or an intro), and unlearn them for free before the
next place. The **Forge** (F on an intro) spends banked monster salvage and rare trophies on
permanent tower patterns; equip one pattern per tower family before a defence. A padlock marks a
power this location does not offer yet. Holding Hell's Gate opens Act II; holding the Temple of
Light completes the campaign.

Some wave breaks offer a sealed **breach** entrance. The panel shows its harder side pack and named
elite: keep it sealed, open it for battle gold, or seek a trophy for a future pattern. Clear the
whole side pack to earn the chosen reward. A victorious cash clear forfeits that site's one-time
trophy. Unsold salvage is banked only on victory, and replaying a location credits only an
improvement over its previous best banked amount.

## More

- [Design](docs/design.md): the rules of one defence, how a leader chooses, and how close to optimal it is.
- [Campaign](docs/campaign.md): the locations, the skill tree, the spells, the world map, and tuning by simulation.
- [Progression redesign](docs/redesign.md): routes, breaches, salvage, patterns and the slower unlock order.
- [Audio](docs/audio.md): the cues, the music and how they are made.
- [The Godot client and the server](docs/godot-client.md): who owns what, the protocol, the measured costs.
- [AGENTS.md](AGENTS.md): commands and layout for development.
