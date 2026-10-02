# Stage 2 — Ten to a hundred, on scarce ground

The second readiness stage ([design-choices.md](../design-choices.md) section 20): the design's number scale,
shorter locations, maps where good ground is scarce, cell worth while placing, and the Kit that stage 3's runs
build on. It ships as a release Ilya plays, after stage 1. The maps' measurements and decisions are in
[2-maps-analysis.md](2-maps-analysis.md). This spec took one critique round (systems, feasibility, player
experience); their fixes are folded in.

## Rules

### Numbers (G2.4, G3.4)

**The life curve.**
- A role-1 monster has 10 life at Tristram's first wave (`economy.base_hp = 10`).
- Life grows ×1.16 per location (`economy.life_growth`, replacing `location_growth` everywhere it is read: monster
  life, spell power, gate life) and ×1.05 per wave.
- Hits and life round **half up** (an explicit function, not Python's `round`).

**Roles are compressed.** No ordinary monster may exceed 200 with the tuned factors applied, and the Temple's
per-body median sits in 60–120. The roles' starting points:

| Monster | Role |
|---|---:|
| Fallen | 1.0 |
| Flayer | 0.9 |
| Bat | 0.8 |
| Skeleton | 1.3 |
| Spider | 1.3 |
| Zombie | 1.5 |
| Goatman | 1.6 |
| Zealot | 1.8 |
| Drowned | 2.0 |
| Leaders | 1.8–2.2 |
| Overlord | 2.4 |
| Hulk | 2.6 |
| Azazel | 16 (about 430 at Hell's Gate) |
| Bone Priest | 12 (about 780 at the Temple) |

**Gold.**
- Prices do not grow: the gold unit is `economy.base_gold_unit` everywhere.
- Income grows ×1.12 per location (`economy.income_growth`), on top of the growth per wave.
- The **starting stipend** grows ×1.16 per location (`economy.stipend_growth`), so a location's first wave is held
  as Tristram's is.
- Breach payouts and salvage sales scale with the income unit.
- `wave_density` and its knobs are deleted: the authored counts are the counts.

**Per-location factors.**
- Each location's life factor sits in its own module (below), bounded to **0.85–1.2**.
- If tuning wants more, the roster, the spacing or the stipend changes instead.

**Margin targets** are a sawtooth, so the arc has felt power spikes:

| Where | Target margin |
|---|---:|
| Each act's first location, and a location that introduces a tower | about 1.35 |
| Each act's last location | about 1.1 |
| In between | interpolated |

The first wave's margin is reported too.

**The power table** (`tools/scorecard.py`, G3.4). For each location, on the untuned curve (factor 1):
- **The reference board:** the best board that location's gold buys on its top-worth cells, at most 8 towers and not
  all rank III.
- **Its damage:** felt damage (`felt_hit`) against the last wave's kind mix, weighted by life.
- **The demand:** the life arriving per second, counted per route as each monster's life divided by its seconds
  inside the covered stretch, so speed counts.

It prints whether gold or cells bind.

**Spells** scale with the location and are exempt from the hit cap of 30.

### Waves (G2.1)

- **Counts:** four to six waves per location, at most 30 bodies a wave.
  - Act I: Tristram 4, the Graveyard and the Cathedral 5, then 5–6.
  - Act II: 5–6.
  - Fetish raises count toward the p99 limit of 25 alive at once.
- **Rosters escalate by kind, not count:** faster kinds (Flayers, Bats, Spiders) and more armored ones later. Each
  location's first wave is a light probe.
- **Every drawn route is walked:**
  - by wanderers from its entrance, or the route is deleted;
  - a wanderer's chosen route shows as it spawns.
- Breaches stay until stage 3's bonus waves.

### Ground (R1–R3, R5)

**Map-authoring rules.** Each map is re-designed by hand to the decisions in 2-maps-analysis.md, plus these:
- **Occupied:** at least 40% of the ground beside the halls, weighted by worth.
- **Prime cells:** at most 12, counted with every boulder cleared.
- **At least two prime clusters,** at least 5 tiles apart, at different kinds of choke: a gate's flank, a loop's
  island, the merge.
- **Neighbours differ:** consecutive maps do not share their main archetype.
- **Every entrance keeps a good cell.**
- **The geometry may change:** shorter shared stretches, islands, narrower halls at chokes.
- **Tristram's** hand-placed dressing (`dressing.gd` HOUSES and PROPS) is laid out again with its map.
- **Re-measured:** the gate-queue bonus in `tools/maps.py` is measured again after stage 1's Knife Post, before maps
  are authored.

**Terrain:**
- **Rock** (the pillar tile): clusters of boulders, ruins, collapsed walls.
- **Water** (the pool tile): ponds by the kept clusters.
- **Boulders:** up to three rock cells per map, never on Tristram. They are a new name: "rubble" already means a
  broken gate.
  - Each sits on a cell that would be prime once cleared, at least 3 tiles from the main cluster, so clearing buys
    spacing against curses.
  - During any break, including the one before wave 1, `clear` turns one into floor for 1, 2, then 3 **income
    units** (the location's unit, ×1.12 per location), so it stays a choice in Act II.
  - Event: `cleared_boulder`. Order: `clear` with a tile.

**Cell worth:**
- `tools/maps.py`'s `cell_worth` moves into the simulation as a pure function of the level and the location's waves.
- It is computed **per tower kind in the arsenal** (each kind's reach; the Knife Post's queue bonus counts double),
  and with and without each gate.
- Boulder cells carry their would-be worth.

**Upgrades (R3):**
- `rank_cost_units` may differ per tower kind.
- Ranks II and III buy less damage per gold than another rank-I tower, and more per cell. This is judged against
  the location's real armor mix, from the per-kind hit table.

### The Kit

- **`hellward.sim.kit.Kit`** is a frozen dataclass of what a defence starts from:
  - `location` (a `Location`, serialised as its key, so a replay refuses one outside the campaign);
  - the learned skills, the loadout, starting gold, sanctuary lives, the seed;
  - empty slots for stage 3's relics and carried counters.
- **The tool knobs stay World keyword arguments:** `hardness`, `curse_scale`, `record`, `planner`.
- **`clone()`** copies the derived perks and baked ranks; it does not rebuild them.
- **A replay** is a Kit plus the order log.
- It lands as one mechanical commit, after stage 1's simulation merges and before any other stage 2 change to the
  simulation, with `tools/sim_bench.py`'s p95 decision time quoted (T4).

### Plans that cannot go stale

- The planned player's plans carry a fingerprint of the map, the waves and the prices, as the warden's do.
- `tools/margin.py` and the scorecard refuse a location whose plan is stale.
- **The strongest bot** at a location is the better of the planned and the warden players there.

## The wire and the client

- **The battle's start:**
  - per-kind cell worth, with and without each gate;
  - the boulders, with their would-be worth and clearing prices.
- **Orders and events:** `clear`, `cleared_boulder`.
- **While placing a tower:**
  - the client tints every buildable cell by that kind's worth (with the gates as they stand) and outlines the prime
    cells;
  - the hover shows the worth as a share of the map's best;
  - it shows **"a curse here catches N"**: the towers already built within the largest curse radius the location's
    leaders cast.
- **The upgrade preview** shows the next rank's hit against the location's roster (the hits table).
- **Terrain:**
  - rock clusters as boulders, ruins or a collapsed wall, in the location's theme;
  - ponds as water;
  - boulders visibly clearable, with their price.

## Order of work

0. **Stage 1 merges** into `design`. Stage 1's own tuning only checks that the strongest bot still wins; stage 2
   replaces every factor.
1. **Mechanical split** (one agent): each location moves to its own module, `hellward/sim/locations/<key>.py`,
   holding its level, waves and life factor, with `fastsim.MODULES` updated. Then the Kit. Both are behaviour-free;
   the suite passes unchanged.
2. **In parallel, file-disjoint:**
   - **numbers:** economy.toml, balance.py, monster roles, per-kind rank prices, the power table; checked from the
     tables, no bots;
   - **ground rules:** cell worth in the simulation, boulders and clearing, the wire;
   - **the client,** against the wire's names.
3. **Per location, one commit each:**
   - the steps: waves, then `tools/maps.py`, then the map, then its plan's search, then its life factor;
   - one pipeline per act, so the two heavy-job slots stay busy while agents author the next map;
   - the warden's map-fingerprint test stays green.
4. **The scorecard** over everything, the exit criteria, the release.

## Exit criteria

**Scorecard:**
- **G2.1:** ≤ 30 bodies a wave, p99 ≤ 25 alive at once.
- **G2.2:** median ≤ 10 towers.
- **G2.4:** every target, with the tuned factors applied.
- **G3.4:** the power table closes on the untuned curve at every location.
- **R1, R3, R5** met on every map.
- Every life factor within 0.85–1.2.

**Tests:**
- the Kit round-trip (a World from a Kit, replayed, gives the same events);
- clearing a boulder (price, any break, refusal);
- cell worth's properties, and that the tint follows the selected kind;
- stale plans refused;
- the compiled simulation equals the source;
- the server equals `hands.defend`;
- `godot/tools/test.sh`.

**Ilya sees:**
- Tristram's 10-life Fallen;
- one late location (the Drowned City or the Temple) played start to finish at the new scale, recorded through the
  capture tools, to judge whether it is a slog;
- each map's worth tint and curse preview while placing;
- a boulder cleared;
- the power table as a chart.
