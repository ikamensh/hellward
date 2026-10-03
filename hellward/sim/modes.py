"""Tower control strategies: how a tower chooses its target, bought once in the forge.

Every tower aims foremost until its owner teaches it otherwise. A strategy is owned by the profile
forever and set per tower in a defence; ``first`` is free, the rest cost banked salvage. Special
attacks keep their nature (a nova strikes all in reach, a hook its victim): a strategy steers the
choice of one target.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping


@dataclass(frozen=True)
class Mode:
    key: str
    name: str
    words: str
    salvage_cost: int = 0


MODES: Final[Mapping[str, Mode]] = MappingProxyType({m.key: m for m in (
    Mode("first", "Foremost", "Strike the monster nearest the sanctuary.", 0),
    Mode("strong", "Strongest", "Strike the monster with the most life in reach.", 4),
    Mode("weak", "Weakest", "Finish the monster with the least life in reach.", 4),
    Mode("fast", "Swiftest", "Strike the fastest monster in reach.", 6),
    Mode("last", "Rearmost", "Strike the monster nearest the portal.", 6),
)})

ATTUNE: Final = Mode("attune", "Attunement",
                     "Towers may hold 3 charges: empowered shots, spent where they kill.", 8)
