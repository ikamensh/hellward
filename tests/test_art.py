"""Tests for the art module: every monster and tower has a rig and a restyle subject."""

from hellward.art import figures, structures
from hellward.sim.content import MONSTERS, TOWERS
from tools.restyle import MONSTER_SUBJECTS, FIXES


class TestMonsterRigs:
    """Every monster in MONSTERS has a rig builder and can be rendered."""

    def test_every_monster_has_a_builder(self):
        for kind in MONSTERS:
            assert kind in figures.BUILDERS, f"{kind}: no builder in figures.BUILDERS"

    def test_every_monster_renders_all_frames(self):
        for kind in MONSTERS:
            frames = figures.frames(kind)
            for facing in figures.FACINGS:
                for frame in frames:
                    img = figures.render(kind, facing, frame)
                    assert img.width > 0 and img.height > 0, f"{kind}/{facing}/{frame}: empty image"


class TestAct2MonsterRigs:
    """Act II specific monster rigs are distinct and readable."""

    act2_kinds = ("flayer", "zealot", "spider", "bat", "hulk", "drowned", "fetish", "inquisitor", "bone_priest")

    def test_act2_monsters_have_distinct_builders(self):
        for kind in self.act2_kinds:
            assert kind in figures.BUILDERS
            builder = figures.BUILDERS[kind]
            # Each should be a distinct function, not a lambda reusing Act I
            assert builder.__name__ == kind, f"{kind}: builder reuses another kind's rig"

    def test_act2_monsters_render_distinctly(self):
        """Each Act II monster should produce visually distinct images at game size."""
        images = {}
        for kind in self.act2_kinds:
            images[kind] = figures.render(kind, "front", "walk1")

        # No two should have identical pixel data (comparing resized to same size)
        from PIL import Image
        for k1 in self.act2_kinds:
            for k2 in self.act2_kinds:
                if k1 >= k2:
                    continue
                # Resize both to same size for comparison
                img1 = images[k1].convert("RGB").resize((64, 64), Image.Resampling.LANCZOS)
                img2 = images[k2].convert("RGB").resize((64, 64), Image.Resampling.LANCZOS)
                diff = sum(
                    abs(a - b) for p1, p2 in zip(img1.get_flattened_data(), img2.get_flattened_data())
                    for a, b in zip(p1, p2)
                )
                assert diff > 1000, f"{k1} and {k2} look too similar"


class TestTowerRigs:
    """Every tower in TOWERS has a rig builder and can be rendered."""

    def test_every_tower_has_a_builder(self):
        for kind in TOWERS:
            assert kind in structures.TOWER_BUILDERS, f"{kind}: no builder in structures.TOWER_BUILDERS"

    def test_every_tower_renders_all_ranks(self):
        for kind in TOWERS:
            for rank in range(3):
                img = structures.tower_image(kind, rank)
                assert img.width > 0 and img.height > 0, f"{kind}/rank{rank}: empty image"

    def test_arrow_tower_has_three_visible_ranks(self):
        """The starting tower has a visible stand-in at every upgrade rank."""
        assert "arrow" in structures.TOWER_KINDS
        images = [structures.tower_image("arrow", rank) for rank in range(3)]
        assert all(image.getbbox() is not None for image in images)
        assert len({image.tobytes() for image in images}) == 3
        assert all(structures.tower_top("arrow", rank) < structures.tower_top("arrow", rank + 1)
                   for rank in range(2))

    def test_arrow_tower_loads_as_a_game_asset(self, tmp_path):
        """The art registry exposes the new tower even while the painted sheet has only older towers."""
        from saga2d import Game
        from hellward.art import sprites

        game = Game("Hellward art test", backend="mock", asset_path=tmp_path / "cache", save_dir=tmp_path / "saves")
        try:
            sprites.register(game, tmp_path / "cache")
            for rank in range(3):
                assert game.assets.has_image(f"tower/arrow/{rank}")
        finally:
            game.close()


class TestAct2TowerRigs:
    """Act II towers (altar, grove) have proper rigs."""

    def test_altar_and_grove_in_tower_kinds(self):
        assert "altar" in structures.TOWER_KINDS
        assert "grove" in structures.TOWER_KINDS
        assert "altar" in structures.TOWER_BUILDERS
        assert "grove" in structures.TOWER_BUILDERS

    def test_act2_towers_render_three_ranks(self):
        for kind in ("altar", "grove"):
            for rank in range(3):
                img = structures.tower_image(kind, rank)
                assert img.width > 0 and img.height > 0, f"{kind}/rank{rank}: empty image"

    def test_act2_towers_grow_with_rank(self):
        """Higher ranks should be taller (check mesh bounds, not rendered cell which is fixed)."""
        from hellward.art.rig import PROJECTION
        from sagaforge import render3d as r3
        for kind in ("altar", "grove"):
            heights = []
            for rank in range(3):
                mesh = structures.TOWER_BUILDERS[kind](rank)
                _, y0, _, y1 = r3.bounds(mesh, PROJECTION)
                heights.append(y1 - y0)
            assert heights[0] < heights[1] < heights[2], f"{kind}: mesh heights {heights} don't grow"


class TestRestyleSubjects:
    """Every monster and tower has a restyle subject and fixes where needed."""

    def test_every_monster_has_a_restyle_subject(self):
        for kind in MONSTERS:
            assert kind in MONSTER_SUBJECTS, f"{kind}: missing from MONSTER_SUBJECTS"

    def test_act2_monsters_have_restyle_subjects(self):
        act2 = ("flayer", "zealot", "spider", "bat", "hulk", "drowned", "fetish", "inquisitor", "bone_priest")
        for kind in act2:
            assert kind in MONSTER_SUBJECTS
            subject = MONSTER_SUBJECTS[kind]
            assert len(subject) > 50, f"{kind}: subject too short"
            assert ":" in subject, f"{kind}: subject should describe the monster"

    def test_every_monster_with_crude_parts_has_a_fix(self):
        """Monsters with known crude stand-in parts should have FIXES entries."""
        crude_kinds = ("skeleton", "priest", "witch", "gargoyle", "azazel", "zombie",
                       "spider", "bat", "hulk", "drowned", "fetish", "bone_priest")
        for kind in crude_kinds:
            assert kind in FIXES, f"{kind}: missing FIXES entry for crude parts"

    def test_tower_subject_includes_every_tower(self):
        from tools.restyle import tower_subject
        subj = tower_subject()
        assert len(subj.sheet.cells) == len(structures.TOWER_KINDS) * 3
        keys = [c.key for c in subj.sheet.cells]
        assert keys[:len(structures.TOWER_KINDS)] == [f"{kind}/0" for kind in structures.TOWER_KINDS]
        assert "arrow tower" in subj.prompt.lower()
        assert "seven" in subj.prompt.lower()
        for kind in structures.TOWER_KINDS:
            for rank in range(3):
                assert f"{kind}/{rank}" in keys, f"tower subject missing {kind}/{rank}"


class TestWorldMapAct2:
    """Act II world map has anchors, trails and chambers."""

    def test_act2_anchors_exist(self):
        from hellward.art import worldmap
        assert 2 in worldmap.ANCHORS
        act2_anchors = worldmap.ANCHORS[2]
        expected = ("docks", "spider_forest", "jungle", "drowned_city", "travincal", "temple")
        for key in expected:
            assert key in act2_anchors, f"Act II missing anchor {key}"

    def test_act2_trails_connect_anchors(self):
        from hellward.art import worldmap
        trails = worldmap.TRAIL[2]
        # docks -> spider_forest -> jungle -> drowned_city -> travincal -> temple
        path = ("docks", "spider_forest", "jungle", "drowned_city", "travincal", "temple")
        for a, b in zip(path, path[1:]):
            assert (a, b) in trails or (b, a) in trails, f"missing trail {a}-{b}"
            trail = worldmap.trail(a, b, act=2)
            assert trail[0] == worldmap.ANCHORS[2][a]
            assert trail[-1] == worldmap.ANCHORS[2][b]

    def test_act2_chambers_exist(self):
        from hellward.art import worldmap
        assert 2 in worldmap.CHAMBERS
        for key in ("docks", "spider_forest", "jungle", "drowned_city", "travincal", "temple"):
            assert key in worldmap.CHAMBERS[2], f"Act II missing chamber {key}"

    def test_act2_stand_in_renders(self):
        from hellward.art import worldmap
        img = worldmap.picture(act=2)
        assert img.size == (worldmap.WIDTH * worldmap.DENSITY, worldmap.HEIGHT * worldmap.DENSITY)


def test_authored_hall_floor_reads_differently_from_tower_ground():
    """A hall's spare width is monster space even where no route centreline passes."""
    import numpy as np

    from hellward.art import mapart
    from hellward.sim.level import Level

    halls = frozenset((x, y) for x in range(9) for y in (2, 3) if 0 < x < 8 or y == 3)
    level = Level("hall art", 9, 7, ((0, 3), (8, 3)), (), halls=halls)
    image = mapart.stand_in(level, mapart.THEMES["village"])

    def brightness(x: int, y: int) -> float:
        px = mapart.PX
        patch = np.asarray(image.crop(((x + 0.4) * px, (y + 0.4) * px,
                                       (x + 0.6) * px, (y + 0.6) * px)), dtype=np.float32)
        return float(patch.mean())

    assert brightness(4, 2) > brightness(4, 1) + 8


def test_painted_floor_stamp_changes_when_only_hall_width_changes():
    """An old painting cannot silently put monster space under a tower plot."""
    from dataclasses import replace

    from hellward.art.mapart import layout_fingerprint
    from hellward.sim.level import Level

    halls = frozenset((x, 3) for x in range(9))
    level = Level("hall stamp", 9, 7, ((0, 3), (8, 3)), (), halls=halls)
    widened = replace(level, halls=halls | {(4, 2)})
    assert layout_fingerprint(level) != layout_fingerprint(widened)

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
