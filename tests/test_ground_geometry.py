"""Painted floors belong to the map geometry they were made from."""

from dataclasses import replace

from PIL import Image, ImageChops
from saga2d import Game

from hellward.art import mapart, sprites
from hellward.sim.campaign import TRISTRAM
from hellward.sim.level import Level, Route
from tools import restyle


def test_a_floor_painting_only_replaces_the_layout_it_was_painted_for(tmp_path, monkeypatch):
    monkeypatch.setattr(mapart, "PAINTED", tmp_path)
    level = Level("yard", 9, 9, ((0, 4), (8, 4)), (),
                  extra_routes=(Route("branch", ((0, 4), (4, 2), (8, 4))),))
    changed = Level("yard", 9, 9, ((0, 4), (8, 4)), (),
                    extra_routes=(Route("branch", ((0, 4), (4, 6), (8, 4))),))
    painting = Image.new("RGB", (level.width * mapart.PX, level.height * mapart.PX), (242, 17, 213))
    painting.save(mapart.painted("yard"))

    assert ImageChops.difference(mapart.ground("yard", level, mapart.THEMES["village"]), painting).getbbox()
    mapart.record_painted_layout("yard", level)
    assert ImageChops.difference(mapart.ground("yard", level, mapart.THEMES["village"]), painting).getbbox() is None
    assert ImageChops.difference(mapart.ground("yard", changed, mapart.THEMES["village"]), painting).getbbox()


def test_a_game_caches_each_layout_under_its_own_ground_name(tmp_path):
    first = Level("yard", 9, 9, ((0, 4), (8, 4)), ())
    changed = Level("yard", 9, 9, ((0, 4), (8, 4)), (),
                    extra_routes=(Route("branch", ((0, 4), (4, 2), (8, 4))),))
    game = Game("Hellward", backend="mock", asset_path=tmp_path / "cache", save_dir=tmp_path / "saves")
    try:
        first_name = sprites.ground(game, replace(TRISTRAM, level=first))
        changed_name = sprites.ground(game, replace(TRISTRAM, level=changed))
        assert first_name != changed_name
        assert game.assets.has_image(first_name)
        assert game.assets.has_image(changed_name)
    finally:
        game.close()


def test_ground_refresh_records_layout_and_uses_a_new_render_after_a_map_change(tmp_path, monkeypatch):
    painted_dir = tmp_path / "painted"
    painted_dir.mkdir()
    render_dir = tmp_path / "renders"
    render_dir.mkdir()
    monkeypatch.setattr(mapart, "PAINTED", painted_dir)
    first = Level("yard", 9, 9, ((0, 4), (8, 4)), ())
    changed = Level("yard", 9, 9, ((0, 4), (8, 4)), (),
                    extra_routes=(Route("branch", ((0, 4), (4, 2), (8, 4))),))
    rendered = []

    def fake_paint(source, prompt, out, provider, aspect):
        rendered.append(out)
        if out.exists():
            return
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.open(source).save(out)

    monkeypatch.setattr(restyle, "_paint", fake_paint)
    monkeypatch.setitem(restyle.LOCATIONS, "tristram", replace(TRISTRAM, level=first))
    restyle._ground(render_dir, "tristram", "codex")
    assert mapart.painted_matches("tristram", first)

    monkeypatch.setitem(restyle.LOCATIONS, "tristram", replace(TRISTRAM, level=changed))
    restyle._ground(render_dir, "tristram", "codex")
    assert mapart.painted_matches("tristram", changed)
    assert rendered[0] != rendered[1]


def test_procedural_ground_marks_each_open_entrance_without_opening_the_breach():
    level = Level("yard", 9, 9, ((0, 4), (8, 4)), (),
                  extra_routes=(Route("side", ((0, 1), (4, 1), (8, 4))),
                                Route("breach", ((4, 0), (4, 3), (8, 4)))))
    image = mapart.stand_in(level, mapart.THEMES["village"])

    def fire_at(tile):
        cx, cy = (tile[0] + 0.5) * mapart.PX, (tile[1] + 0.5) * mapart.PX
        box = (int(cx - 32), int(cy - 32), int(cx + 32), int(cy + 32))
        return sum(r > 170 and r > g * 1.8 and b < 70 for r, g, b in image.crop(box).get_flattened_data())

    assert fire_at((0, 4)) > 20
    assert fire_at((0, 1)) > 20
    assert fire_at((4, 0)) < 20
