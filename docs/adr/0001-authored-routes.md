# 0001: Authored routes through open maps

Status: accepted for the redesign.

## Context

Hellward's current movement, reach caches, leader estimates, gates, scripted players
and renderer all use one coordinate along one path. Open maps need multiple entrances,
wandering monsters and direct runners without making the leader's lookahead too slow
or nondeterministic.

## Decision

Each level offers authored, validated routes through open ground. A monster receives a
route at spawn. Wanderers choose a seeded detour; runners choose the shortest route.
Routes give exact future positions and gate crossings. The world compares monsters by
remaining travel rather than one shared path coordinate.

## Alternatives and consequences

Continuous two-dimensional steering could produce more organic movement and react to
new obstacles. It would also need collision and anti-stuck behavior, a gate
attack-versus-bypass policy, and a new, costlier planner estimate. Authored routes
keep the exact rollout and cheap estimate aligned. They require deliberate level
authoring and enough distinct detours that wandering reads as wandering; they cannot
react to arbitrary tower placement. We therefore keep build areas off the routes and
benchmark the planner after the migration.
