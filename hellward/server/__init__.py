"""Hellward's server: the rules, the campaign and the saves, for the Godot client.

The client starts ``python -m hellward.server --connect PORT --token T`` as its child; the server connects back to
the client's loopback port and they exchange newline-delimited JSON (:mod:`hellward.server.protocol`). The server
is the authority: every battle runs in :mod:`hellward.sim` here (:mod:`hellward.server.battle`), and the campaign
and its saves live here too (:mod:`hellward.server.campaign`). The client draws, plays sound and asks.
``docs/godot-client.md`` is the design.
"""

PROTOCOL = 1   # both sides say theirs in the hello; a different number is an error, never a guess
