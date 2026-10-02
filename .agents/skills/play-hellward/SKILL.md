---
name: play-hellward
description: Playtest Hellward through the text seat to judge difficulty, balance, and fun, improving the seat's tooling whenever it hides state, lacks an order, or wastes tokens.
---

# Play Hellward

Play the game through `tools/llm_play.py` (the LLM seat, `docs/llm.md`), as a
player would: to find out how hard it is and whether it plays well — not to
exercise code paths. A playthrough has two deliverables: the verdict
(difficulty; balance/fun and the decisions the game actually demands) and any
tooling improvements the run exposed.

## Playing

- Lab (free experimentation): `uv run python tools/llm_play.py <location> --seed N --skills a,b`.
- Campaign (honest progression): `--profile NAME` (use `--data` under `/tmp`
  unless the user wants their real saves touched). Decided defences bank
  sigils/salvage/trophies; quitting mid-fight keeps nothing.
- Play `watch`-driven: one digest per wave, builds at breaks, `watch leaks N`
  when protecting a life threshold. The digest's action line usually answers
  what to build — don't re-ask `status`/`advise` after every digest.
- Batch several commands per call; keep interactive sessions short and `quit`
  when done (long PTY sessions have starved the runtime's file descriptors
  before — prefer `--script` for fixed, non-reactive sequences).
- Autos are the real-time hands (`smite_leader`, `smite_leak` on by default);
  arm `hymn`/`meteor`/`orb` deliberately and note when they misfire.

## Improving the seat

Whenever the run shows the seat hiding state a player needs, missing an order a
player has, or spending tokens to no effect, fix `hellward/llm/` (views,
advisors, autos, driver) right then:

- Keep the budgets in `docs/llm.md` (briefing < 6000, `status` < 1600, digest
  < 1200/`watch` < 1600 chars) and update the doc with every protocol change.
- Extend `tests/test_llm.py` for the new behavior. Keep tests content-robust:
  build on `advisor.placement` tiles (never hardcoded coordinates), compute
  body counts from the authored waves, assert structural facts (stopped
  mid-wave, reached the break) over exact numbers — the campaign gets
  rebalanced often.
- New commands go in `driver.py` HELP, `docs/llm.md`, and a test together.
- `uv run pytest tests/test_llm.py -q`, `uv run mypy hellward/llm/
  tools/llm_play.py`, and `uv run ruff check` stay green.

## Boundaries

- Never change game rules (`hellward/sim/`) from a playthrough: balance
  findings are a report, not a patch. The sim belongs to another session —
  coordinate instead of editing.
- If other sessions are active in the tree, do tooling work on a branch and
  never commit their files; verify against a clean worktree when the tree is
  mid-refactor.

## Report

After a playthrough, report: per-level outcome (victory/defeat, lives and
sigils kept, attempts), a difficulty verdict (too easy/fair/brutal, and where
it bites), balance and fun notes (which decisions mattered, which options felt
dead, pacing), and tooling gaps found — fixed or filed.
