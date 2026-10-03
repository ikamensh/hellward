---
name: story-hellward
description: Walk Hellward's story as the player sees it to critique words, panels, pacing and vibe, improving the story and its tooling.
---

# Walk Hellward's Story

Walk the campaign through `tools/llm_story.py` (the story seat,
`docs/story.md`), as a player meets it: to judge whether the story lands —
not to playtest difficulty or exercise code paths. A walk has two
deliverables: the critique (words, panels, pacing, vibe) and any story or
tooling improvements it earns.

## Walking

- `uv run python tools/llm_story.py list` names the beats in the player's
  order; `show <n|key>` prints one, `all` prints every one, no command walks
  them interactively. `--notes` adds what the painter was told.
- Open every panel the beats name (`read_file` reads images natively):
  prologue shots, story pages, each fight's level still. Open the labeled
  `monsters.jpg` sheet once, at the first fight, and read later fights'
  `new here` kinds against it.
- A fight beat is watched, not played: its still, waves, new monsters, music
  blurb and hardship gauge stand in for the defence. Never open `llm_play.py`
  from a story walk — difficulty questions belong to `play-hellward`.
- Judge words and panels together (does the panel show what the text says?),
  pacing across beats (what the player learns, and when), and vibe (music
  blurb + still vs. the words' mood). `docs/story.md` holds the rules the
  words keep (tense, length, the arc, the palette); `docs/story-canon.md`
  holds the canon, the review principles and the promise ledger —
  critique against them with beat keys and canon tags, and file new holes
  in the canon before fixing anything around them.

## Improving the story

Words live in `hellward/story.py` (pages), `hellward/sim/locations/*`
(taunts, lessons, blurbs, wave names — words only, never numbers or rules)
and `hellward/audio/music.py` (track blurbs). Follow the canon's loop
(`docs/story-canon.md`, "The loop"): canon decision first, then words, then
repaint, stills, tooling. Creative text changes need user approval —
propose, never rewrite unasked. When a walk earns edits:

- Make the words edit, then re-`show` the beats it touches and re-read them
  against their panels.
- A panel that no longer matches its words is repainted with
  `uv run python tools/story.py paint --only KEY` — one panel at a time,
  never the whole set unasked (the painter costs credit).
- After visual changes (models, dressing, lighting), re-render the walk's
  stills with `uv run python tools/llm_story.py stills` (a few minutes) and
  look at what changed before keeping it.
- Keep `docs/story.md` (the taunts table especially) in sync with the words.

## Improving the seat

When the walk hides player experience a critique needs, or wastes effort to
no effect, fix `tools/llm_story.py` right then:

- Extend `tests/test_llm_story.py` for the new behavior. Keep tests
  content-robust: derive wave counts, kinds and order from the authored
  data, assert structural facts over exact numbers — the campaign gets
  rebalanced often. Static gauges (hardship) carry their source and date.
- `uv run pytest tests/test_llm_story.py -q` stays green.

## Boundaries

- Never change game rules or numbers (`hellward/sim/` mechanics, balance,
  content stats) from a story walk: rules findings are a report, not a
  patch. Words-only edits in `hellward/sim/locations/*` are the story's.
- Never hand-edit the stills (`hellward/assets/story/levels/`,
  `monsters.jpg`): they are rendered output — regen them.
- If other sessions are active in the tree, do story work on a branch and
  never commit their files.

## Report

After a walk, report: what was walked (beats or the whole arc), the critique
(words, panels, pacing, vibe — with beat keys and canon tags), the edits
made (words, repainted panels, re-rendered stills), canon holes opened or
closed, and what still wants a painter or a future pass.
