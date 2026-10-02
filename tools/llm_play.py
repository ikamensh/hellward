"""Play Hellward as text: the LLM's seat at the game.

    uv run python tools/llm_play.py tristram --profile sophie   # the campaign, kept
    uv run python tools/llm_play.py graveyard --seed 3 --skills adept_arrow
    uv run python tools/llm_play.py tristram --script tools/llm_demo.txt

With --profile the session keeps a campaign in the data dir (saves, replays):
`defend` opens locations, decided defences bank sigils, salvage and trophies,
and `learn`/`forge` spend them. Without one it is a lab: any location, fixed
skills, nothing kept. See docs/llm.md for the protocol and its budgets.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward.llm.driver import Session, policy_for  # noqa: E402
from hellward.server.campaign import Campaign, Refusal  # noqa: E402
from hellward.sim.campaign import LOCATIONS, ORDER  # noqa: E402
from hellward.sim.players.adaptive import Adaptive  # noqa: E402
from hellward.sim.skills import SKILLS, kept  # noqa: E402


def skills_for(names: str, location: str) -> frozenset[str]:
    wanted = frozenset(n for n in names.replace(",", " ").split() if n)
    unknown = sorted(wanted - SKILLS.keys())
    if unknown:
        raise SystemExit(f"no such skills: {', '.join(unknown)}")
    stage = ORDER.index(location)
    learned = kept(wanted, 63, stage)
    dropped = sorted(wanted - learned)
    if dropped:
        print(f"(dropped, needs an earlier skill or a later location: {', '.join(dropped)})")
    return learned


def main() -> None:
    parser = argparse.ArgumentParser(description="Play Hellward through text.")
    parser.add_argument("location", choices=sorted(LOCATIONS))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--skills", default="", help="comma-separated skill keys (lab only)")
    parser.add_argument("--leaders", default="smart",
                        choices=["none", "random", "nearest", "greedy", "smart"])
    parser.add_argument("--profile", default=None, help="keep a campaign under this profile")
    parser.add_argument("--data", type=Path, default=Path.home() / ".hellward",
                        help="saves and replays (with --profile)")
    parser.add_argument("--script", type=Path, default=None, help="run commands from a file")
    args = parser.parse_args()
    campaign = None
    if args.profile is not None:
        if args.skills:
            print("(with --profile the profile's skills rule; --skills ignored)")
        if args.leaders == "none":
            raise SystemExit("a kept campaign needs its leaders: --leaders none is lab-only")
        policy = policy_for(args.leaders, args.seed)
        assert policy is not None
        campaign = Campaign(args.data, planner=policy, demo_player=Adaptive, seed=args.seed,
                            profile=args.profile.strip().lower())
    try:
        session = Session(args.location, seed=args.seed, skills=skills_for(args.skills, args.location),
                          leaders=args.leaders, campaign=campaign)
    except (ValueError, Refusal) as bad:
        raise SystemExit(f"cannot defend {args.location}: {bad}") from bad
    print(session.open())
    lines: list[str] = []
    if args.script is not None:
        lines = args.script.read_text().splitlines()
    while not session.closed:
        if lines:
            line = lines.pop(0)
            print(f"> {line}")
        else:
            if args.script is not None:
                return
            try:
                line = input("> ")
            except (EOFError, KeyboardInterrupt):
                print()
                return
        print(session.do(line))
        if session.battle is not None and session.world.outcome is not None and not lines \
                and args.script is not None:
            return


if __name__ == "__main__":
    main()
