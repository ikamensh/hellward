"""The veteran: the tuning's yardstick (docs/campaign.md, "Tuning by simulation"). A strong player with a person's
hands: the warden's rules, drafting its skills and build from the intro with no stored or searched plan, seeing a
leader's sign 0.8-1.2 s late and casting one aimed spell a second at most."""

from __future__ import annotations

from hellward.sim.players.warden import Warden


def veteran(seed: int) -> Warden:
    return Warden(name="veteran", reaction=(0.8, 1.2), aim_gap=1.0, plans={})
