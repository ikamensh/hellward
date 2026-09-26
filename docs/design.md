# Hellward — design

A tower defence under a desecrated gothic cathedral. Demons walk from a hell portal to the
sanctuary; the player builds towers of four kinds of magic beside their way and bars the arches
with warded gates. What is new: some monsters are **leaders**, and a leader curses the player's
towers, choosing which tower and which curse by playing the fight ahead in its head.

This page is the rules of one defence and how a leader chooses. Around it is a campaign of six
locations with a skill tree, spells and a world map: [campaign](campaign.md).

The brief (Ilya, 2026-09-24): "a TD game where enemy has leaders who curse your towers
strategically ... either fast simulation or smart heuristics to make their curses almost optimal,
otherwise a normal TD game. Diablo-themed graphics and monster kinds, towers are different kinds of
magic, also Diablo-themed. Doors at key positions that take some time for monsters to destroy. Just
enough content in high visual and audio quality to make an impressive demo."

The stack's [making a game](../../docs/making-a-game.md) puts a feel build in front of Ilya before any
painted art or generated sound. This brief asked for a finished-looking demo in one go, so the look and
sound passes ran in the same session; the feel-build clip was still recorded, and Ilya's verdict on the
loop goes here when he has played it.

## The loop

- **One map at a time, five to eight waves** ([campaign](campaign.md) has the six). The Cathedral's
  path is 56 tiles long and folds back on itself twice, so a tower in a fold covers three stretches of
  it. Three **door sockets** sit in arches on the path.
- **Towers** (`sim/content.py`), three ranks each:
  - **Pyre** (fire): firebolts; fireballs with a blast from the second rank.
  - **Storm Obelisk** (lightning): chain lightning that leaps two to five times.
  - **Frost Shrine** (cold): a nova that chills everything in reach. A chilled monster walks slower
    and batters doors more weakly.
  - **Plague Totem** (poison): venom that seeks the strongest monster, stacking up to four times.
- **Monsters** carry Diablo-style resistances. Skeletons are immune to poison. Zombies burn easily
  and shrug off poison. Goatmen resist lightning. Gargoyles fly over gates. Overlords break gates
  fast. Azazel the Flayer, the boss of Hell's Gate, is immune to fire.
- **Warded gates** (60 gold, 650 life) stop walkers at the arch. Walkers queue and batter the gate
  until it breaks, which is where fireballs, novas and chain lightning pay off. A gate that stands
  mends by half when a wave is cleared; a broken one can be rebuilt.
- **Leaders** walk with their pack:
  - the **Fallen Shaman** casts Weaken (a third of the damage);
  - the **Bone Priest** casts Bone Prison (silenced for 4.5 s) or Dim Vision (half the reach);
  - the **Blood Witch** casts Decrepify (40% attack speed) or Weaken.

  A curse lasts 8 s, 4.5 s for Bone Prison.
- **Counterplay:** the blue orb is mana. **Cleanse** (35 mana) burns every curse off one tower;
  **Smite** and **Frozen Orb** break a leader's pondering or chant, so the curse never comes; killing a
  leader mid-chant makes it fizzle too. The spells are in [campaign](campaign.md).

## How a leader chooses (`sim/planner.py`)

When its curse is ready, a leader asks its planner. The world is copied at a step boundary and the
decision is read half a second of game time later (the leader visibly ponders). In the game a
worker process computes it, and the answer is the same one an inline call returns, so a seed
replays exactly.

1. **Candidates:** every tower the leader will still reach when its chant ends, times every curse it
   knows.
2. **Estimate:** for each candidate, the damage the curse would stop the tower dealing while it lasts.
   It uses where each monster will walk, stops at standing gates, and what each monster resists.
   This ranks the candidates and picks the ten that get rolled out.
3. **Rollouts:** the world is cloned and played forward at 0.1 s steps, once casting nothing and
   once per candidate, for the curse's length plus three seconds (plus four more for timing). A
   candidate's gain is how much more the pack keeps. The score counts:
   - the life of monsters still standing;
   - monsters that reached the sanctuary, at twice their life;
   - life knocked off gates;
   - half the pack's life averaged over the look-ahead. A curse that only delays deaths still
     buys ground, and without this term every curse against the fast-dying Fallen scored zero.
4. **Timing:** the best three are also tried two and four seconds later. The leader holds its curse
   while waiting is worth 1.2 times the best curse now plus 5 life; it thinks again a second later.

A rollout sees everything the estimate misses: the fireball that would hit the whole queue at a gate,
the frost that keeps a gate standing, the leader's own life, the curses other leaders have already
cast, and the wave still spawning. It is the game's own rules at a coarser step (`World.clone`,
`World.step`), so there is no second model of the game to keep in sync.

**How close to optimal** (`tools/curse_quality.py`, 40 decision moments from whole defences). Each
moment's truth is every legal curse played out at the game's own step for 16 s:

| policy | share of the best gain | top pick |
|---|---|---|
| rollouts (the game's) | 0.91 | 77% |
| the estimate alone | 0.66 | 38% |
| the nearest tower | 0.51 | 26% |
| random | 0.44 | — |

A decision costs about 60 ms (7 rollouts), at most about 180 ms. Of the moments where the leader
chose to wait, waiting beat casting at once in 10 of 13.

**What it does to a defence** (`tools/balance.py`, 12 scripted defenders, uncapped lives): with
no curses, and with random curses, they lose 0 lives. Against the planner they lose 17.9 on
average and 3 of the 12 fall. The scripted defender cleanses by a fixed rule; a player who reads
the leaders' minds does better.

## Showing the leaders' minds

- A leader pondering shows dots over its head.
- A chant draws a violet beam growing from the leader's staff to the tower, and the tower glows.
- The chronicle (top right) says what the leader weighed, its choice and the life it expects to
  spare its pack, or that it holds its curse because waiting is worth more.
- **Leaders' minds** (Tab, on by default) writes each weighed tower's gain over it for three
  seconds, with the chosen curse named.
- A cursed tower wears a spinning sigil per curse and is tinted by it.
- Hovering a monster shows Diablo's bar at the top of the screen: name, life, resistances, and for
  a leader its curses.

## Look and sound

- **Figures:** posed low-poly rigs (`art/figures.py`, `art/structures.py`), painted by Codex's image
  tool through `tools/restyle.py`. Monsters walk (4 frames), batter gates (3) and, if they lead,
  chant (2), in three facings; left is the right facing mirrored. The painter got the rig's poses,
  the subject in words and a style paragraph. Sheets are padded to 3:2, and five of the first
  thirteen came back on a dark vignette instead of the magenta key and were painted again.
- **Map:** the cathedral floor is one picture painted over its stand-in
  (`hellward/assets/painted/ground.png`).
- **Lighting:** darkness with pools of light (`ui/lighting.py`): one small picture stretched over
  the map each frame, below the effects and above everything that stands.
- **Effects** (`ui/effects.py`): layered procedural glows, jagged lightning, rings and particles.
- **Sound:** see [audio](audio.md).
