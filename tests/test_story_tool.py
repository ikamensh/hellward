"""The story panels' painter (tools/story.py): prompt() carries the act's style, the rules and
every named reference's design; pictures() passes only files that exist, the prologue base first."""

import importlib.util
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"


def load_story_tool():
    spec = importlib.util.spec_from_file_location("story_tool", TOOLS / "story.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["story_tool"] = module
    spec.loader.exec_module(module)
    return module


story_tool = load_story_tool()

from hellward.story import REFERENCES, RULES, STORIES, STYLES  # noqa: E402


def pages():
    return [(story.act, page) for story in STORIES.values() for page in story.pages]


def test_prompt_carries_the_style_the_rules_and_every_named_reference():
    assert len(pages()) > 0
    for act, page in pages():
        text = story_tool.prompt(page, act)
        assert STYLES[act] in text
        assert page.panel in text
        assert RULES in text
        for name in page.refs:
            assert REFERENCES[name] in text
            assert "Keep this design:" in text


def test_pictures_lists_only_existing_files(monkeypatch, tmp_path):
    monkeypatch.setattr(story_tool, "REFS_DIR", tmp_path / "refs")
    monkeypatch.setattr(story_tool, "PROLOGUE_DIR", tmp_path / "prologue")
    (tmp_path / "refs").mkdir()
    (page,) = [page for _, page in pages() if page.key == "tristram-before"]
    assert story_tool.pictures(page) == []
    (tmp_path / "refs" / "you.jpg").write_bytes(b"you")
    assert story_tool.pictures(page) == [tmp_path / "refs" / "you.jpg"]


@pytest.mark.parametrize("key,base", [("act1-end-2", "glass"), ("act2-end-1", "bones")])
def test_pictures_puts_the_base_prologue_panel_first(monkeypatch, tmp_path, key, base):
    monkeypatch.setattr(story_tool, "REFS_DIR", tmp_path / "refs")
    monkeypatch.setattr(story_tool, "PROLOGUE_DIR", tmp_path / "prologue")
    (tmp_path / "refs").mkdir()
    (tmp_path / "prologue").mkdir()
    (page,) = [page for _, page in pages() if page.key == key]
    for name in page.refs:
        (tmp_path / "refs" / f"{name}.jpg").write_bytes(b"ref")
    assert all(p.name != f"{base}.jpg" for p in story_tool.pictures(page))
    (tmp_path / "prologue" / f"{base}.jpg").write_bytes(b"base")
    pics = story_tool.pictures(page)
    assert pics[0] == tmp_path / "prologue" / f"{base}.jpg"
    assert len(pics) == 1 + len(page.refs)
