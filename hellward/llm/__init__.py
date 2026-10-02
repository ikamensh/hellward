"""An LLM plays a defence through text: a briefing once, orders as lines, a digest every few seconds.

``view`` renders the world as compact text (see ``docs/llm.md`` for the budgets), ``advisor`` answers
quick math questions (where to build, what a wave needs), ``auto`` holds real-time reflexes the LLM
cannot (smite a chanting leader, hymn a busy tower), and ``driver`` runs the turn loop around them.
Everything here reads the world as a person reads the screen: no planner state, no clones.
"""
