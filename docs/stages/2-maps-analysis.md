# Stage 2 — the maps' real estate today, and what to occupy

Preparation for readiness stage 2 ("ten to a hundred, on scarce ground", [design-choices.md](../design-choices.md)
section 20). It measures today's twelve maps against R1 and R5 ([design-criteria.md](../design-criteria.md)) and
proposes, per location, what to occupy with rock and water. Nothing here changes the game.

```bash
uv run python tools/maps.py                 # the table, today and as proposed
uv run python tools/maps.py --out DIR       # a heatmap per location: today above, proposed below
uv run python tools/maps.py --cells         # the cells the proposal keeps, rocks and floods
uv run python tools/scorecard.py            # R1 and R5 among the other criteria
```

The heatmaps from commit `bef6bd3` are kept in `~/saga/evidence/hellward/maps/`.

## How a cell is measured

- **Worth** (`tools/maps.py: cell_worth`): the length of each route a tower on the cell reaches at the rank-I
  Arrow's reach (2.8), weighted by the route's share of the location's monsters, summed over the routes. Its unit
  is tiles of the average monster's walk.
  - A route's share counts the monsters its waves send down it. A wanderer counts evenly on every route from its
    entrance, as the simulation picks among them. Breach packs are optional and not counted.
  - A cell that reaches a gate's queue (the stretch from 1.05 to 0.45 tiles before the crossing) gains up to one
    more tile, weighted by the share of walkers (not flyers) on that route.
  - It uses only `Level`'s public API (`routes`, `Route.coverage`, `crossings`, `buildable`), so it can move into
    the simulation as it is when the client shows cell worth while placing (R2).
- **Prime:** worth at least 60% of the map's best.
- **Clustered:** a prime cell with another prime cell within 2 tiles, centre to centre.
- **Ground beside the halls:** every floor, rock or water cell touching a hall (8-neighbour). One tile further out, a
  rank-I Arrow reaches nothing of a straight hall, so this band is the ground towers fight over.
- **Occupied:** rock or water (today's `PILLAR` and `POOL`) among that ground.

### Why 60%, and why the gate counts for little

The planned player's builds (`hellward/sim/players/plans/`, searched by `tools/plan_player.py`) are the strongest
placements the project has. Over the twelve maps, the share of cells in each worth band it builds on:

| Worth (share of the map's best) | ≥ 0.9 | 0.8–0.9 | 0.7–0.8 | 0.6–0.7 | 0.5–0.6 | 0.4–0.5 | 0.3–0.4 | < 0.3 |
|---|---|---|---|---|---|---|---|---|
| Cells it builds on | 28 / 34 | 28 / 53 | 22 / 38 | 20 / 53 | 17 / 70 | 16 / 97 | 11 / 146 | 8 / 438 |
| Share | 82% | 53% | 58% | 38% | 24% | 16% | 8% | 2% |

Above 0.6 it builds on about half the cells (98 of 178), just below on a quarter, and under 0.3 almost never. So
prime, "what a strong player fights for", is 0.6 of the best. The prime count is sensitive to this: at 0.85,
every one of today's maps would already have twelve prime cells or fewer.

The search only moves towers among the 40 cells a similar coverage ranking puts first, so this is not independent
evidence. Within those 40 cells per map, worth still separates the cells it builds on from the rest (AUC 0.78), and
weighting routes by traffic helps a little (0.77 unweighted). A bigger gate bonus makes the fit worse:

| Gate queue bonus (tiles) | 0 | 1 | 2 | 4 |
|---|---|---|---|---|
| AUC within the search's candidates | 0.780 | 0.776 | 0.765 | 0.741 |

The bonus stays at one tile. Re-measure it after stage 1: the Knife Post's ×2 on monsters standing at a gate should
make the queue worth more.

## Today

| Location | Buildable | Beside halls | Occupied | Prime | Clustered | Groups | Best | R1: prime over 12 | R1: cells to occupy | R5 |
|---|---|---|---|---|---|---|---|---|---|---|
| Tristram | 258 | 104 | 2% | 21 | 20 | 9+4+4+3+1 | 3.64 | 9 | 40 | 95% |
| Graveyard | 252 | 79 | 3% | 21 | 19 | 14+5+1+1 | 4.39 | 9 | 30 | 90% |
| Cathedral | 252 | 86 | 1% | 30 | 27 | 14+10+3+1+1+1 | 4.80 | 18 | 34 | 90% |
| Catacombs | 222 | 104 | 3% | 4 | 2 | 2+1+1 | 5.39 | — | 39 | **50%** |
| Caves | 210 | 99 | 6% | 13 | 7 | 5+2+1+1+1+1+1+1 | 3.63 | 1 | 34 | **54%** |
| Hell's Gate | 189 | 98 | 2% | 17 | 16 | 7+5+4+1 | 3.75 | 5 | 38 | 94% |
| Kurast Docks | 201 | 69 | 1% | 8 | 7 | 3+2+2+1 | 6.01 | — | 27 | 88% |
| Spider Forest | 160 | 94 | 3% | 6 | 4 | 4+1+1 | 4.92 | — | 35 | **67%** |
| Flayer Jungle | 157 | 71 | 4% | 9 | 9 | 6+3 | 3.85 | — | 26 | 100% |
| Drowned City | 168 | 93 | 9% | 14 | 11 | 7+2+2+1+1+1 | 3.64 | 2 | 30 | 79% |
| Travincal | 175 | 97 | 5% | 16 | 14 | 5+5+2+2+1+1 | 3.56 | 4 | 34 | 88% |
| Temple of Light | 191 | 89 | 4% | 19 | 16 | 9+3+2+2+1+1+1 | 3.77 | 7 | 32 | 84% |

R5's static target is 75% of prime cells clustered (`LEAST_CLUSTERED`). No map meets R1: occupied ground is 1–9%
against 40%, and eight maps have more than twelve prime cells. Three miss R5.

What the heatmaps show:
- **Prime cells are of three kinds.**
  - The two strips flanking the stretch every route shares into the sanctuary. Every map has them; they are the
    whole excess on the Graveyard (14 and 5 cells long) and the Cathedral (14 and 13).
  - Small floor islands enclosed by route loops, which reach several legs at once: Spider Forest (16,11) and
    (20,11), Jungle (12–14,12), Travincal (15–16,11).
  - Cells beside a gate, on seven maps.
- **Most of the floor reaches nothing.** Halls are carved as every route ±1, so a map with four routes is mostly
  hall, and 53–77% of its buildable cells are out of reach of every walked route (Docks: 154 of 201).
- **Some routes carry nobody.** Every Docks monster is a runner, so its meander and side detour are never walked;
  Travincal's side detour is empty too; the Jungle's and Travincal's meanders carry 3%. Their halls are neither
  buildable nor walked.
- **The Jungle's gate is out of every tower's reach:** halls surround it on all sides, so no cell reaches its
  queue.

## The proposal

`tools/maps.py: propose` occupies cells and moves nothing else:
- **It keeps:**
  - the best cell and the best prime cells near it (up to eight), so the map's best, and with it the prime
    threshold, stays;
  - each entrance's own best prime cell, alone if need be, so neither approach loses its best spot;
  - then clusters round the best remaining prime cells, up to twelve kept in all.
- **Rock** goes on every other prime cell, lone ones included. Rock rather than water, because rock can be cleared
  for gold (section 9): a denied prime cell is what a rich player buys back.
- **Water** goes on the least worth ground beside the halls, growing pools from what is occupied, until 40% is.

The test (`tests/test_maps.py`) holds it to R1 on every map and to every entrance keeping its best cell.

| Location | Rock | Water | Occupied | Prime | Clustered | Groups |
|---|---|---|---|---|---|---|
| Tristram | 9 | 31 | 40% | 12 | 12 | 8+4 |
| Graveyard | 9 | 21 | 41% | 12 | 11 | 11+1 |
| Cathedral | 18 | 16 | 41% | 12 | 11 | 8+3+1 |
| Catacombs | 1 | 38 | 40% | 3 | 2 | 2+1 |
| Caves | 4 | 30 | 40% | 9 | 7 | 5+2+1+1 |
| Hell's Gate | 6 | 32 | 41% | 11 | 11 | 7+4 |
| Kurast Docks | 1 | 26 | 41% | 7 | 7 | 3+2+2 |
| Spider Forest | 1 | 34 | 40% | 5 | 4 | 4+1 |
| Flayer Jungle | 0 | 26 | 41% | 9 | 9 | 6+3 |
| Drowned City | 2 | 28 | 41% | 12 | 11 | 7+2+2+1 |
| Travincal | 4 | 30 | 40% | 12 | 11 | 5+2+2+2+1 |
| Temple of Light | 7 | 25 | 40% | 12 | 12 | 8+2+2 |

Every map then meets R1, and every map but the Catacombs meets R5 (the Catacombs' best cell has no room for a
neighbour). Cells are (x, y); "y6 x9–15" is a run along row 6.

**Tristram:**
- **Map:** no gate, three lanes from one entrance (main 38%, north 31%, south 31%).
- **Today:** prime cells sit in the strips between the lanes (y6 x8–15 with (16,7), y11 x15–18, y10 x7–9) and on
  the approach to the sanctuary (y11 x28–31, the best at (30,11)).
- **Keep:** y6 x9–15 and (16,7), the strip both north and main lanes pass; y11 x28–31.
- **Rock:** (8,6), (31,7), y10 x7–9, y11 x15–18.
- **Water:** 31 cells on the outer flanks of the north and south lanes, which only one lane passes.
- **Note:** the eight cells kept in a row make the location's lesson ("spread your arrows") cost something.

**The Graveyard:**
- **Map:** gate (12,8); the lanes share the last stretch along y5 (main and meander from x12, the side lanes from
  x21 and x24).
- **Today:** a 14-cell strip below the shared stretch (y7 x18–31) and 5 above it (y3 x27–31). The best cell,
  (14,7), stands alone beside the gate's exit; it reaches the climb, the queue and the shared stretch. (10,10)
  stands alone inside the meander's loop.
- **Keep:** (14,7), y7 x21–31.
- **Rock:** y3 x27–31, y7 x18–20, (10,10).
- **Water:** 21 cells: x1 and x7–8 along y6–9, the corners of y1–2, and y15–16.
- **Better by geometry:** an 11-cell line clusters weakly (a curse catches three of it). Joining the lanes nearer
  the sanctuary shortens the strip, and the rock with it.

**The Cathedral:**
- **Map:** gate (13,8); the main lane's last 19 tiles run along y12, with the side lane beside it on y13 and then
  on it from x21.
- **Today:** the worst map. 14 prime cells above that run (y10 x18–31), 13 below (y14 x15–17, x22–31), a lone best
  at the main lane's turn (15,10), and two lone cells west of the main lane's descent ((11,5), (11,11)).
- **Keep:** (15,10), y14 x15–17, y14 x22–29.
- **Rock:** y10 x18–31, y14 x30–31, (11,5), (11,11): 18 cells.
- **Water:** 16 cells, mostly x1–2 and x8–10 along y6–10.
- **Better by geometry:** 18 rocks make a wall of rubble along the nave. Shortening the run the lanes share along
  y12 (the main lane turns onto it at x13) is the fix.

**The Catacombs:**
- **Map:** gate (5,6); every lane ends down x27.
- **Today:** 4 prime cells. The best, (25,16), sits in the one-cell pocket between the main lane's last run (y14)
  and the shared descent. A pair, (24,12) and (25,12), sits where the side lanes converge. (29,15) stands alone.
- **Rock:** (29,15).
- **Water:** 38 cells, mostly x8–20 along y1–8 and the east wall (x30–31).
- **Unmet:** R5 stays missed. The pocket holds one tower; widening it (move the main lane's last run up a row) gives
  the best cell neighbours.

**The Caves:**
- **Map:** gate (16,4); 21% of the monsters are flyers, which the gate does not stop.
- **Today:** the approach strip y3 x27–31 (the best at (30,3)), a pair in the meander's loop ((18,7), (19,7)), and
  six lone cells.
- **Keep:** the strip, the pair, and each entrance's own best ((23,7) for the north, (10,11) for the west).
- **Rock:** (14,2), (18,4) (the gate's east flank), (15,10), (20,13).
- **Water:** 30 cells, mostly a row along y7 x3–13, south of the existing lava.
- **Result:** R5 at 78%, just met.

**Hell's Gate:**
- **Map:** gate (13,8); a breach lane from (22,0).
- **Today:** both gate flanks are prime (x11 y5–8, with the best at (11,5); x15 y6–10), plus the strip below the
  shared stretch (y15 x25–31) and (6,5).
- **Keep:** the west flank and the strip.
- **Rock:** the east flank, (6,5).
- **Water:** 32 cells, mostly along the breach lane, which no wave walks.
- **Note:** keeping one flank makes the gate the cluster a curse can catch.

**Kurast Docks:**
- **Map:** gate (17,5); two walked lanes (main 53%, side 47%). The meander and the side detour carry nobody.
- **Today:** the best cells are at the merge, (29,6) and (30,6) (6.01, the highest worth on any map), plus
  y2 x28–30, (25,6), (25,8), and the gate's west flank (15,6) alone.
- **Rock:** (15,6).
- **Water:** 26 cells, mostly along the south edge of the unwalked side detour's hall (y9 x2–11, y10 x11–15).
- **Note:** delete the two unwalked routes, or give the Docks wanderers. Their halls take most of the map's upper
  left (x0–21, y0–9).

**The Spider Forest:**
- **Map:** gate (9,5); 25% flyers.
- **Today:** the two best cells are one-cell islands four tiles apart, (20,11) and (16,11), each enclosed by
  lanes. Below the shared stretch: y16 x26–28 and (30,16).
- **Rock:** (16,11).
- **Water:** 34 cells.
- **Result:** R5 at 80%, but the best cell stands alone.
- **Better by geometry:** one island of two or three cells, instead of two islands, puts the best spots together.

**The Flayer Jungle:**
- **Today:** prime cells already meet R1 and R5: y16 x25–31 below the shared stretch, and the island y12 x12–14
  (the best at (14,12)).
- **Water:** 26 cells; nothing else.
- **Note:** the gate (12,7) has halls on every side, so no tower reaches its queue. The Knife Post needs a gate it
  can reach.

**The Drowned City:**
- **Map:** gate (11,6); 36% flyers.
- **Today:** the strip above the shared stretch (y2 x25–31, the best at (30,2)), the gate's east flank ((13,7),
  (13,8)), a pair in the meander's loop (y12 x18–19), and three lone cells.
- **Keep:** those, plus (21,3), the west entrance's own best.
- **Rock:** (18,3), (25,8).
- **Water:** 28 cells, mostly the breach lane's flanks and y10 x2–8.

**Travincal:**
- **Map:** gate (8,5); the side detour is empty and the meander carries 3%.
- **Today:** both flanks of the side lane's first run (y12 x4–8; y16 x2 and x4–7), the island (15,11)–(16,11)
  (the best), (23,11) and (24,12), and the gate's east flank ((10,4), (10,7)) as two lone cells.
- **Keep:** every other prime cell; (10,7), the north entrance's own best, stays alone.
- **Rock:** (10,4), y16 x2, y16 x4–5.
- **Water:** 30 cells, around the meander's eastern loop (x14–29, y1–11), which 3% walk.

**The Temple of Light:**
- **Map:** gate (9,4); a breach lane from (32,2).
- **Today:** the strip below the shared stretch (y14 x23–31, the best at (30,14)), both gate flanks (x7 y2–4;
  (11,4) and (11,6)), the west entrance's pair (y10 x8–9), and three lone cells.
- **Keep:** the east flank, the pair, y14 x24–31.
- **Rock:** the west flank, (16,6), (20,13), (23,14), (31,10).
- **Water:** 25 cells.

## To decide before the maps are re-authored

1. **Prime at 60% of the best.** This sets how hard R1's twelve is. At 85%, every map passes it today.
2. **Occupy, or also move lanes?** Occupying alone meets R1 everywhere. But the Cathedral needs 18 rocks, the
   Graveyard and Tristram 9 each, and four lone best cells (Graveyard, Cathedral, Catacombs, Spider Forest) can only
   get neighbours by geometry. Two causes are cheaper to fix at the source:
   - long shared stretches into the sanctuary, which make the prime strips;
   - halls carved as every lane ±1, which leave 53–77% of the floor out of reach.

   Stage 2 should say whether it may move routes and merge points.
3. **What R1's 40% counts.** Counted by cells, the cheapest 40% (zero-worth flanks, breach lanes, empty detours)
   meets the target without taking a single choice from the player; the proposal does exactly that. If scarcity
   should also bite on the second tier (30–60% of the best, where a player spreads to escape area curses), measure
   occupation by worth, or set a target for the second tier. I recommend weighting by worth.
4. **Rock and water as rules.**
   - Today `POOL` means "nothing stands here" (lava, an open grave). The design's water admits a Moon Well (stage
     5).
   - The proposal's rock on prime cells assumes those are the clearable ones: how many a map, and at what price?
   - Water beside a kept cluster is where a Moon Well would feed it; the proposal puts water where it costs least
     instead.
5. **Unwalked routes.** Delete the Docks' meander and side detour and Travincal's side detour, or give those
   locations wanderers. Say whether a breach lane's flanks count as ground (the proposal floods them for free).
6. **Order of work.** Stage 2 also rewrites the waves (four to six a location), which moves every route's share and
   so every cell's worth. Re-author the waves first, re-run `tools/maps.py`, then the maps. Re-measure the gate
   bonus after stage 1's Knife Post.
