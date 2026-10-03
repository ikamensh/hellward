"""The story's pages: every key names its moment, every page has words and a panel the client can show.
(When the server tells a story: tests/test_campaign_server.py.)"""

import re
from pathlib import Path

from hellward.sim.campaign import LOCATIONS
from hellward.story import STORIES

PANELS = Path(__file__).resolve().parent.parent / "godot" / "game" / "assets" / "story"


def test_every_story_key_names_its_moment_and_every_page_has_text():
    for key in STORIES:
        assert re.fullmatch(r"[a-z_]+/(before|after)", key) or re.fullmatch(r"act\d/end", key), key
    for story in STORIES.values():
        for page in story.pages:
            assert page.text and all(line.strip() for line in page.text), page.key
    for key, story in STORIES.items():
        if story.act == 1:
            assert key == "act1/end" or key.split("/")[0] in LOCATIONS, key


def test_every_page_has_its_painted_panel_in_the_client():
    for story in STORIES.values():
        for page in story.pages:
            assert (PANELS / f"{page.key}.jpg").is_file(), page.key


def test_every_page_balances_its_quotes():
    for story in STORIES.values():
        for page in story.pages:
            assert " ".join(page.text).count('"') % 2 == 0, page.key
