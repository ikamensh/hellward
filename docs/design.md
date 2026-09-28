# Hellward — one defence

Hellward is a gothic tower defence about protecting a sanctuary lamp. Demons approach through branching halls, and their leaders curse the towers defending it. A leader chooses its curse by simulating the fight ahead. [The campaign](campaign.md) connects twelve defences across two acts; [the story](story.md) gives their cast and stakes.

Ilya's original brief (2026-09-24) asked for Diablo-inspired monsters and magic, doors that hold enemies while they break, and leaders whose curses are almost optimal rather than arbitrary. The later progression redesign starts much smaller: a few arrows against enemies with single-digit life, then hard choices about when to buy power and when to save resources for future fights.

## A defence

- **Map and movement.** Each 33 × 18 map separates monster halls from tower plots. The halls branch around buildable islands and rejoin at the sanctuary; monsters stay on their walkable floor, and towers stand only outside it. Tristram has several routes from one entrance. Every later location has two ordinary entrances, a direct route and a longer loop from each, and some have a sealed third entrance. A monster commits to one route when it spawns. Fallen, skeletons, zombies, goatmen, spiders, hulks and drowned may take a seeded loop; fast enemies and leaders run their authored direct route. A tower attacks by actual distance, and enemies on different routes are ordered by how far they remain from the sanctuary.
- **Opening power.** Tristram offers only the single-target Arrow Tower and Cleanse. An Arrow costs 12 gold at the opening and hits for 2; its later ranks hit for 3 and 4. The first Fallen has 7 life. The first Shaman has 14 before wave growth. All opening hits and enemy life use the 1–20 scale.
- **Growth.** `sim/balance.py` holds the common knobs: base life 7, 5.5% growth per location, 5% growth per wave, Arrow hit 2, and a starting budget of three rank-I Arrows plus half an Arrow unit per later location. Legacy swarm sizes shrink with campaign depth and stop shrinking at 40%, keeping single-target play viable. Enemy roles and tower roles multiply the common scale. A wave's gold budget starts at one local Arrow-price unit and grows by half a unit per wave; kills and the clear reward share it, so a larger swarm does not create unlimited money. Prices rise with the local gold unit. Bosses and optional elites add encounter multipliers.
- **Towers.** Arrow, Pyre, Storm Obelisk, Frost Shrine and Plague Totem attack or afflict one target at first. Pyre's blast, Storm's jump, Frost's burst, and the major spells arrive later through skills, forging, or location unlocks. Bone Altar marks a knot of enemies to take more damage; Druid Grove lends a nearby tower a damage bonus. Neither support tower deals damage directly. Every tower has three ranks; skills unlock the upper ranks, and battle gold pays for them. The [campaign](campaign.md) lists the unlock order.
- **Resistances and gates.** Skeletons ignore poison; zombies are vulnerable to fire; goatmen resist lightning; gargoyles and bats fly over gates. A warded gate costs one local Arrow-price unit and has base 70 life before location and skill scaling. It stops only walkers whose trail crosses its arch; others can go around. A standing gate mends after a wave. A broken gate cannot be rebuilt until the wave break.
- **Leaders and counterplay.** A curse falls on a marked spot and catches every unwarded tower in its radius. Weaken cuts damage, Decrepify cuts attack rate, Dim Vision cuts reach, and Bone Prison silences. Cleanse clears one tower. Smite interrupts one leader's pondering or chant for modest direct damage. Frozen Orb can also interrupt once it unlocks. A broken leader becomes resolute: its next curse is a mark that neither spell can break. Killing the leader before that mark lands still stops it.
- **Optional risk.** At six locations, a sealed breach can add a named elite and harder pack to the next wave. The player declines, chooses a battle-gold cache, or seeks a forging trophy. Kills pay gold immediately. A few ordinary enemies also drop salvage: selling it during a break buys power now; banking it on victory moves a forged tower pattern closer. See [campaign](campaign.md) for the persistent rewards and recipes.

The opening has no damaging area attack. The earliest optional Pyre blast requires saved trophies and salvage at the Docks; the first skill route to area damage and Frozen Orb opens in the Jungle. Strong damage remains concentrated in invested ranks and scarce patterns.

## How a leader chooses (`sim/planner.py`)

When its curse is ready, a leader asks its planner. The world is copied at a step boundary and the decision is read after a visible pondering delay. The game computes the answer in a worker process; the same seed and state give the same answer inline or in a replay.

1. **Candidates:** each curse the leader knows at every reachable tower's spot. The spot's radius includes nearby unwarded towers.
2. **Estimate:** project each monster on its committed trail, including gate stops, and estimate the damage each candidate prevents. The ten strongest candidates proceed.
3. **Rollouts:** clone the real world and step it at 0.1 s for the curse and a short aftermath, once without a curse and once per candidate. Compare monster life still on the field, life leaked to the sanctuary, damage to gates, and how long the pack stays alive.
4. **Timing:** also try the best candidates two and four seconds later. Hold a curse only when waiting has enough measured value.

The rollout shares the game's rules for route movement, tower reach, gates, resistances, forged patterns, salvage and optional packs. The estimate is cheaper; `tools/curse_quality.py` checks how well its shortlist and the final choice perform. Compare quality and balance measurements only when they use the same profile and campaign rules; earlier tables predate this redesign.

## Showing the leaders' minds

A pondering leader shows dots. A chant draws a growing violet sign at its target; a mark burns on its spot before it lands. The chronicle names the leader's choice and estimated gain, and the optional leaders' minds overlay writes candidate gains by the towers. A cursed tower wears a spinning sigil. Hovering a monster shows its name, life, resistances and, for a leader, its curses.

## Look and sound

Figures use posed low-poly stand-ins and painted sheets; effects layer glows, rings, lightning and particles over the field. The lighting draws a darkness layer with pools around sources. Each location has its own floor theme; route geometry and painted ground must agree when a map is repainted. The restrained Arrow release joins the magical tower cues. See [audio](audio.md) for the sound system.
