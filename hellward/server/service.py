"""The client's requests, answered: one message in, the messages it sends back.

A request carries a type ``t`` and, when it wants an answer, an ``id``; the answer is ``{"t": "reply", "id", "ok":
true, "data"}`` or ``{"ok": false, "why"}`` for a refusal the client shows. ``advance`` (the client's clock) has
no answer: it gets a frame per step. An accepted battle order sends its frame before its reply.

=================  ==============================================================================
campaign side      ``profiles``, ``create_profile`` (name), ``switch_profile`` (name), ``campaign``,
                   ``seen`` (key), ``chronicle``, ``briefing`` (location), ``skills`` (location?),
                   ``learn`` (key, location?), ``unlearn`` (column), ``unlearn_all`` (location?),
                   ``forge_view``, ``forge`` (key)
a run            ``start_run`` (seed?), ``run``, ``camp``, ``abandon``
battles            ``defend`` (location) and ``demo`` (location?) answer with the battle's start;
                   ``order`` (name, ...); ``advance`` (steps); ``abandon``; ``leave`` (again) after the reckoning;
                   in a run, the ``summon`` order (stake) and ``summon_preview``
=================  ==============================================================================
"""

from __future__ import annotations

from typing import Any

from hellward.server.battle import Battle
from hellward.server.campaign import Campaign, Refusal

REQUESTS = ("profiles", "create_profile", "switch_profile", "campaign", "seen", "chronicle", "briefing", "skills",
            "learn", "unlearn", "unlearn_all", "forge_view", "forge", "leave", "start_run", "camp", "abandon",
            "summon_preview", "resume", "take_relic")


class Service:
    def __init__(self, campaign: Campaign) -> None:
        self.campaign = campaign

    @property
    def battle(self) -> Battle | None:
        return self.campaign.battle

    def handle(self, message: dict[str, Any]) -> list[dict]:
        kind = message["t"]
        args = {k: v for k, v in message.items() if k not in ("t", "id")}
        if kind == "advance":
            battle = self._battle()
            return battle.advance(int(args["steps"]))
        ident = message["id"]
        try:
            if kind == "order":
                battle = self._battle()
                name = args.pop("name")
                why, frame = battle.order(name, args)
                if why is not None:
                    return [{"t": "reply", "id": ident, "ok": False, "why": why}]
                assert frame is not None
                return [frame, {"t": "reply", "id": ident, "ok": True, "data": None}]
            if kind == "defend":
                data = self.campaign.defend(**args).start()
            elif kind == "run":   # the campaign's run, not its method: the live run answers
                data = self.campaign.run_view()
            elif kind == "demo":
                data = self.campaign.demo(**args).start()
            elif kind in REQUESTS:
                data = getattr(self.campaign, kind)(**args)
            else:
                raise ValueError(f"unknown request {kind!r}")
        except Refusal as refusal:
            return [{"t": "reply", "id": ident, "ok": False, "why": str(refusal)}]
        return [{"t": "reply", "id": ident, "ok": True, "data": data}]

    def _battle(self) -> Battle:
        if self.battle is None:
            raise ValueError("no battle is being fought")
        return self.battle
