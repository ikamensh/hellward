"""The world on screen: a sprite for every monster, tower, gate, arch and pillar, kept in step with the rules.

The scene steps the world in whole :data:`~hellward.sim.model.SIM_DT` s; :meth:`WorldView.before_step`
remembers where each monster was, so :meth:`WorldView.sync` can draw it part of the way to where it is
now. Walk frames advance with distance travelled. The enhanced figures have their own directional
hit and death clips; these and door blows advance on the battle clock, including pause and speed.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from saga2d import RenderLayer, Scene, Sprite, SpriteAnchor

from hellward.art import figures, puppet, rigged, sprites
from hellward.art.fx import ELEMENT_COLORS
from hellward.art.mapart import THEMES
from hellward.art.rig import PROJECTION, TILE
from hellward.art.sprites import Art, Cell
from hellward.art.structures import tower_top
from hellward.sim.content import CURSES, Curse
from hellward.sim.level import Tile
from hellward.sim.model import Monster, Tower, World
from hellward.ui.lighting import Light
from hellward.ui.puppet import PuppetBody

MAP_X, MAP_Y = 40, 0
T = TILE
Z = PROJECTION.z_scale        # logical pixels per tile of height
TOWER_SCALE = 1.3             # towers stand taller than their stand-ins: the painted ones were cut to the stand-ins' height
ELEMENT_LIGHT = {"arrow": ELEMENT_COLORS["holy"], "pyre": ELEMENT_COLORS["fire"], "storm": ELEMENT_COLORS["lightning"], "frost": ELEMENT_COLORS["cold"],
                 "plague": ELEMENT_COLORS["poison"], "altar": (214, 204, 176), "grove": ELEMENT_COLORS["poison"]}
ELEMENT_OF_VIEW = {"arrow": "holy", "pyre": "fire", "storm": "lightning", "frost": "cold", "plague": "poison", "altar": "curse",
                   "grove": "poison"}
CURSE_TINT = {Curse.WEAKEN: (0.9, 0.55, 0.55), Curse.DECREPIFY: (0.8, 0.72, 0.55), Curse.DIM_VISION: (0.55, 0.5, 0.75),
              Curse.BONE_PRISON: (0.6, 0.6, 0.6)}
TORCH = (255, 150, 60)
CURSE_COLOR = {Curse.WEAKEN: "blood", Curse.DECREPIFY: "ember", Curse.DIM_VISION: "curse", Curse.BONE_PRISON: "holy"}
HIT_FRAME_DT = 0.07
DEATH_TIMING = {"fallen": (0.07, 0.65), "skeleton": (0.09, 0.8), "zombie": (0.12, 1.03)}
LEGACY_DEATH_LIFE = 0.8


def px(x: float, y: float) -> tuple[float, float]:
    """World logical pixels of a point given in tiles."""
    return MAP_X + x * T, MAP_Y + y * T


def placed(image: str, cell: Cell, x: float, y: float, *, layer: RenderLayer = RenderLayer.UNITS, scale: float = 1.0) -> Sprite:
    """A sprite whose cell origin (its ground point) stands at world pixel ``(x, y)``, sorted by that line."""
    return Sprite(image, position=(x - cell.origin[0] * scale, y - cell.origin[1] * scale), anchor=SpriteAnchor.TOP_LEFT,
                  size=(cell.size[0] * scale, cell.size[1] * scale), layer=layer, y_sort=True,
                  ground=(cell.size[1] - cell.origin[1]) * scale)


def facing_of(dx: float, dy: float) -> str:
    if abs(dx) > abs(dy):
        return "right" if dx > 0 else "left"
    return "front" if dy > 0 else "back"


@dataclass
class Figure:
    monster: Monster
    sprite: Sprite
    shadow: Sprite
    prev: float
    aura: Sprite | None = None
    facing: str = "front"
    flash: float = 0.0
    flash_tint: tuple[float, float, float] = (1.0, 1.0, 1.0)
    hit_time: float = -1.0  # seconds into an enhanced hit, or -1 while there is no hit
    attack_time: float = 0.0
    x: float = 0.0          # where it was last drawn, in world pixels
    y: float = 0.0
    dying: float = -1.0     # seconds into its fall, or -1 while alive
    fall: int = 1
    rigged: bool = False
    puppet: PuppetBody | None = None


@dataclass
class Standing:
    tower: Tower
    sprite: Sprite
    glow: Sprite
    sigils: dict[Curse, Sprite]
    pulse: float = 0.0      # brightens when it fires


class WorldView:
    def __init__(self, scene: Scene, world: World, art: Art) -> None:
        self.scene = scene
        self.world = world
        self.art = art
        self.level = world.level
        self.clock = 0.0
        level = self.level
        scene.add_sprite(Sprite(sprites.ground(scene.game, world.location), position=(MAP_X, MAP_Y), anchor=SpriteAnchor.TOP_LEFT,
                                size=(level.width * T, level.height * T), layer=RenderLayer.BACKGROUND))
        for x, y in level.doors:
            cx, cy = px(x + 0.5, y + 0.5)
            scene.add_sprite(placed("arch", art.arch, cx, cy + 0.3 * T))
        self.gates: dict[int, Sprite] = {}
        self.theme = THEMES[world.location.theme]
        if self.theme.pillars:   # elsewhere the obstacles lie flat in the painted floor
            for x in range(level.width):
                for y in range(level.height):
                    if level.tile(x, y) is Tile.PILLAR:
                        cx, cy = px(x + 0.5, y + 0.5)
                        scene.add_sprite(placed("pillar", art.pillar, cx, cy + 0.2 * T))
        self.figures: dict[int, Figure] = {}
        self.towers: dict[int, Standing] = {}
        self.dying: list[Figure] = []
        self.breach_lit = world.breach_opened
        open_entrances = {route.entrance for route in level.routes if not route.key.startswith("breach")}
        sealed_routes = ({route.entrance: route for route in level.routes
                          if route.key.startswith("breach") and route.entrance not in open_entrances}
                         if not self.breach_lit else {})
        self.seals = [scene.add_sprite(Sprite("fx/sigil/curse", position=px(*route.point(0.6)),
                                               size=(T * 0.9, T * 0.9), layer=RenderLayer.OBJECTS, opacity=170))
                      for _, route in sorted(sealed_routes.items())]
        self.static_lights = self._static_lights()
        self.torches = [self._sprite_glow("fire", light.x, light.y, 22) for light in self.static_lights if light.color == TORCH]

    def _sprite_glow(self, element: str, x: float, y: float, size: float) -> Sprite:
        return self.scene.add_sprite(Sprite(f"fx/glow/{element}", position=(x, y), size=(size, size), layer=RenderLayer.EFFECTS))

    def _static_lights(self) -> list[Light]:
        level = self.level
        lit_routes = [route for route in level.routes if self.breach_lit or not route.key.startswith("breach")]
        lights = []
        for x, y in dict.fromkeys(route.entrance for route in lit_routes):
            lights.append(Light(*px(x + 0.5, y + 0.5), 190, (255, 60, 30), 1.1))
        x, y = level.route("main").exit
        lights.append(Light(*px(x + 0.5, y + 0.5), 170, (255, 214, 140), 1.1))
        rng = random.Random(level.name)
        kind = self.theme.lights
        if kind == "torches":   # along the north wall, between the windows, and down the sides
            for x in range(1, level.width - 1, 3):
                lights.append(Light(*px(x + 0.5, 0.85), 95, TORCH, 0.75))
            for y in range(3, level.height - 1, 4):
                lights.append(Light(*px(0.85, y + 0.5), 80, TORCH, 0.6))
                lights.append(Light(*px(level.width - 0.85, y + 0.5), 80, TORCH, 0.6))
        elif kind == "fires":   # the houses round the square are burning
            for _ in range(9):
                edge = rng.choice(("top", "bottom", "left", "right"))
                x = rng.uniform(1, level.width - 1) if edge in ("top", "bottom") else (0.6 if edge == "left" else level.width - 0.6)
                y = rng.uniform(1, level.height - 1) if edge in ("left", "right") else (0.6 if edge == "top" else level.height - 0.6)
                lights.append(Light(*px(x, y), rng.uniform(110, 170), (255, 110, 40), 0.9))
        elif kind == "moon":   # cold moonlight in patches through the mist
            for _ in range(8):
                x, y = rng.uniform(2, level.width - 2), rng.uniform(2, level.height - 2)
                lights.append(Light(*px(x, y), rng.uniform(150, 230), (150, 170, 220), 0.45))
        for x, y in sorted(level.pools):
            if self.theme.pool == "lava":
                lights.append(Light(*px(x + 0.5, y + 0.5), 110, (255, 100, 30), 0.9))
        if self.theme.pillars:
            for x in range(level.width):
                for y in range(level.height):
                    if level.tile(x, y) is Tile.PILLAR:
                        lights.append(Light(*px(x + 0.5, y + 0.2), 90, (255, 190, 110), 0.7))
        for x, y in level.doors:
            lights.append(Light(*px(x + 0.5, y + 0.3), 60, (255, 210, 140), 0.45))
        candles: set[tuple[int, int]] = set()
        for route in lit_routes:
            s = 2.5
            while s < route.length - 1:   # light every walked trail, including the wandering branches
                x, y = route.point(s)
                tile = int(x), int(y)
                if tile not in candles:
                    lights.append(Light(*px(x, y), 85, (255, 170, 90), 0.45))
                    candles.add(tile)
                s += 4.0
        return lights

    # -- Keeping up with the rules ------------------------------------------------------------

    def before_step(self) -> None:
        for figure in self.figures.values():
            figure.prev = figure.monster.s

    def _monster_facing(self, monster: Monster, s: float, previous: str | None = None) -> str:
        route = self.level.route(monster.route)
        kind = monster.kind.key
        if kind not in figures.ENHANCED:
            return facing_of(*route.heading(s))
        # A short travel tangent turns through diagonal bearings before the route's sharp corner.
        ahead = route.point(min(route.length, s + 0.25))
        behind = route.point(max(0.0, s - 0.25))
        angle = math.atan2(ahead[0] - behind[0], ahead[1] - behind[1])
        facings = figures.facings(kind)
        if previous in facings:
            old_angle = facings.index(previous) * math.pi / 4
            delta = (angle - old_angle + math.pi) % (2 * math.pi) - math.pi
            if abs(delta) < math.radians(30):
                return previous
        return facings[round(angle / (math.pi / 4)) % len(facings)]

    @staticmethod
    def _show_frame(figure: Figure, frame: str) -> None:
        family = "mon3d" if figure.rigged else "mon"
        name = f"{family}/{figure.monster.kind.key}/{figure.facing}/{frame}"
        if figure.sprite.image != name:
            figure.sprite.image = name

    def spawn(self, monster: Monster) -> None:
        cell = self.art.monster[monster.kind.key]
        x, y = self.monster_point(monster)
        facing = self._monster_facing(monster, monster.s)
        use_rigged = (monster.kind.key in self.art.rigged and
                      (self.art.monster_style == "rigged" or
                       (self.art.monster_style == "mixed" and
                        bool(random.Random(f"{monster.kind.key}:{monster.id}").getrandbits(1)))))
        family = "mon3d" if use_rigged else "mon"
        sprite = self.scene.add_sprite(placed(f"{family}/{monster.kind.key}/{facing}/walk1", cell, x, y))
        body = None
        if monster.kind.key in self.art.puppets:
            sprite.visible = False
            body = PuppetBody(self.scene, monster.kind.key, facing)
            body.walk(facing, monster.s, x, y)
        size = monster.kind.size
        shadow = self.scene.add_sprite(Sprite("fx/shadow", position=(x, y + 2),
                                              size=(T * size * 1.1, T * size * 0.4), layer=RenderLayer.OBJECTS))
        aura = None
        if monster.kind.leader is not None:
            aura = self.scene.add_sprite(Sprite("fx/ring/curse", position=(x, y + 1),
                                                size=(T * 0.9, T * 0.5), layer=RenderLayer.OBJECTS, opacity=150))
        self.figures[monster.id] = Figure(monster, sprite, shadow, monster.s, aura=aura, facing=facing,
                                          x=x, y=y, rigged=use_rigged, puppet=body)

    def kill(self, monster_id: int) -> Figure | None:
        figure = self.figures.pop(monster_id, None)
        if figure is None:
            return None
        enhanced = figure.monster.kind.key in figures.ENHANCED
        figure.dying = 0.0
        figure.hit_time = -1.0
        if figure.puppet is None:
            figure.facing = self._monster_facing(figure.monster, figure.monster.s, figure.facing)
        figure.fall = 1 if monster_id % 2 else -1
        if enhanced:
            # Death starts at the rules' final position, even when it happened between rendered frames.
            figure.x, figure.y = self.monster_point(figure.monster)
            cell = self.art.monster[figure.monster.kind.key]
            figure.sprite.position = (figure.x - cell.origin[0], figure.y - cell.origin[1])
            figure.shadow.position = (figure.x, figure.y + 2)
        else:
            figure.shadow.remove()
        if figure.aura is not None:
            figure.aura.remove()
        self.dying.append(figure)
        return figure

    def vanish(self, monster_id: int) -> None:
        figure = self.figures.pop(monster_id, None)
        if figure is not None:
            if figure.puppet is not None:
                figure.puppet.remove()
            for sprite in (figure.sprite, figure.shadow, figure.aura):
                if sprite is not None:
                    sprite.remove()

    def hit(self, monster_id: int, element: str) -> None:
        figure = self.figures.get(monster_id)
        if figure is not None:
            if figure.monster.kind.key in figures.ENHANCED and figure.hit_time < 0:
                figure.hit_time = 0.0
            figure.flash = 0.09
            figure.flash_tint = {"physical": (1.0, 0.93, 0.76), "fire": (1.0, 0.7, 0.45), "lightning": (0.75, 0.85, 1.0), "cold": (0.7, 0.9, 1.0),
                                 "poison": (0.7, 1.0, 0.55), "holy": (1.0, 0.95, 0.7)}[element]

    def build(self, tower: Tower) -> None:
        cx, cy = px(tower.tile[0] + 0.5, tower.tile[1] + 0.5)
        if self.scene.game.assets.has_image(f"tower/{tower.kind.key}/{tower.level}"):
            sprite = self.scene.add_sprite(placed(f"tower/{tower.kind.key}/{tower.level}", self.art.tower, cx, cy + 0.25 * T,
                                                  scale=TOWER_SCALE))
        else:   # no sprite for the kind yet: a coloured rune disc on its tile
            color = (214, 204, 176) if tower.kind.key == "altar" else (120, 230, 60)
            sprite = self.scene.add_sprite(Sprite("fx/soft/holy", position=(cx, cy), size=(T, T),
                                                  layer=RenderLayer.UNITS, y_sort=True, ground=T * 0.25))
            sprite.tint = tuple(c / 255 for c in color)
        element = ELEMENT_OF_VIEW[tower.kind.key]
        glow = self.scene.add_sprite(Sprite(f"fx/glow/{element}", position=self.tower_top(tower), size=(30, 30),
                                            layer=RenderLayer.EFFECTS, opacity=200))
        self.towers[tower.id] = Standing(tower, sprite, glow, {})

    def rebuild(self, tower: Tower) -> None:
        standing = self.towers[tower.id]
        if self.scene.game.assets.has_image(f"tower/{tower.kind.key}/{tower.level}"):
            standing.sprite.image = f"tower/{tower.kind.key}/{tower.level}"
        standing.glow.position = self.tower_top(tower)

    def raze(self, tower_id: int) -> None:
        standing = self.towers.pop(tower_id)
        for sprite in (standing.sprite, standing.glow, *standing.sigils.values()):
            sprite.remove()

    def tower_base(self, tower: Tower) -> tuple[float, float]:
        """Where a tower meets the floor, in world pixels."""
        cx, cy = px(tower.tile[0] + 0.5, tower.tile[1] + 0.5)
        return cx, cy + 0.25 * T

    def tower_top(self, tower: Tower) -> tuple[float, float]:
        cx, cy = px(tower.tile[0] + 0.5, tower.tile[1] + 0.5)
        return cx, cy + 0.25 * T - tower_top(tower.kind.key, tower.level) * Z * TOWER_SCALE

    def monster_point(self, monster: Monster, s: float | None = None) -> tuple[float, float]:
        """Where a monster's feet are drawn, with its place across the corridor."""
        s = monster.s if s is None else s
        route = self.level.route(monster.route)
        x, y = route.point(s)
        ax, ay = route.heading(max(0.0, s - 0.35))
        bx, by = route.heading(min(route.length - 1e-6, s + 0.35))
        nx, ny = -(ay + by) / 2, (ax + bx) / 2
        return px(x + nx * monster.lane, y + ny * monster.lane)

    def chest(self, monster: Monster) -> tuple[float, float]:
        """Where spells strike a monster: its middle, in world pixels."""
        figure = self.figures.get(monster.id)
        x, y = (figure.x, figure.y) if figure is not None else self.monster_point(monster)
        lift = monster.kind.size * T * 0.5 + (0.32 * figures.SCALE * Z if monster.kind.flying else 0.0)
        return x, y - lift

    # -- Every frame ----------------------------------------------------------------------------

    def sync(self, alpha: float, dt: float, *, animation_dt: float | None = None) -> None:
        motion_dt = dt if animation_dt is None else animation_dt
        self.clock += motion_dt
        if self.world.breach_opened and not self.breach_lit:
            self.breach_lit = True
            for seal in self.seals:
                seal.remove()
            self.seals.clear()
            self.static_lights = self._static_lights()
        for figure in self.figures.values():
            m = figure.monster
            s = figure.prev + (m.s - figure.prev) * alpha
            x, y = self.monster_point(m, s)
            if m.kind.flying:
                y_draw = y - 3 * math.sin(self.clock * 5 + m.id)
            else:
                y_draw = y
            figure.x, figure.y = x, y
            if figure.hit_time < 0:
                figure.facing = self._monster_facing(m, s, figure.facing)
            hit = figure.hit_time
            attack = figure.attack_time if m.door >= 0 else -1.0
            if figure.puppet is not None:
                frame = "walk1"
                if figure.hit_time >= 0:
                    figure.hit_time += motion_dt
                    if figure.hit_time >= puppet.HIT_LIFE:
                        figure.hit_time = -1.0
                figure.attack_time = figure.attack_time + motion_dt if m.door >= 0 else 0.0
            elif m.kind.key in figures.ENHANCED:
                hit_frames = figures.hit_frames(m.kind.key)
                if figure.hit_time >= 0:
                    frame = hit_frames[min(int(figure.hit_time / HIT_FRAME_DT), len(hit_frames) - 1)]
                    figure.hit_time += motion_dt
                    if figure.hit_time >= len(hit_frames) * HIT_FRAME_DT:
                        figure.hit_time = -1.0
                elif m.door >= 0:
                    phase = (figure.attack_time * 1.2 + m.id * 0.37) % 1.0
                    frame = "wind" if phase < 0.45 else "strike" if phase < 0.62 else "recover"
                elif m.chant_curse is not None:
                    frame = "raise" if m.chant_left > m.kind.leader.channel - 0.3 else "chant"
                    figure.facing = "front"
                else:
                    walk = rigged.WALK if figure.rigged else figures.walk(m.kind.key)
                    stride = figures.stride(m.kind.key) / (2 if figure.rigged else 1)
                    frame = walk[int(s / stride) % len(walk)]
                figure.attack_time = figure.attack_time + motion_dt if m.door >= 0 else 0.0
            elif m.door >= 0:
                phase = (self.clock * 1.2 + m.id * 0.37) % 1.0
                frame = "wind" if phase < 0.45 else "strike" if phase < 0.62 else "recover"
            elif m.chant_curse is not None:
                frame = "raise" if m.chant_left > m.kind.leader.channel - 0.3 else "chant"
                figure.facing = "front"
            else:
                frame = figures.WALK[int(s / figures.STRIDE) % 4]
            cell = self.art.monster[m.kind.key]
            sprite = figure.sprite
            if figure.puppet is None:
                self._show_frame(figure, frame)
            sprite.position = (x - cell.origin[0], y_draw - cell.origin[1])
            tint = (1.0, 1.0, 1.0)
            if m.frozen > 0:
                tint = (0.55, 0.78, 1.0)
            elif m.chill_left > 0:
                tint = (0.62, 0.8, 1.0)
            elif m.poison:
                tint = (0.74, 1.0, 0.62)
            if figure.flash > 0:
                figure.flash -= motion_dt
                tint = figure.flash_tint
            sprite.tint = tint
            if figure.puppet is not None:
                figure.puppet.update(figure.facing, s, x, y_draw, hit=hit, attack=attack, tint=tint)
            figure.shadow.position = (x, y + 2)
            figure.shadow.opacity = 150 if not m.kind.flying else 90
            if figure.aura is not None:
                pulse = 0.5 + 0.5 * math.sin(self.clock * 3 + m.id)
                figure.aura.position = (x, y + 1)
                figure.aura.opacity = int(90 + 110 * pulse) if m.chant_curse is None else 255
                w = T * (0.8 + 0.15 * pulse) * (1.3 if m.chant_curse is not None else 1.0)
                figure.aura.size = (w, w * 0.5)
        for figure in list(self.dying):
            kind = figure.monster.kind.key
            if figure.puppet is not None:
                lifetime = puppet.DEATH_LIFE[kind]
                figure.puppet.update(figure.facing, figure.monster.s, figure.x, figure.y,
                                     death=figure.dying, fall=figure.fall)
                figure.shadow.opacity = round(150 * min(1.0, max(0.0, (lifetime - figure.dying) / 0.35)))
            elif kind in figures.ENHANCED:
                frame_dt, lifetime = DEATH_TIMING[kind]
                death_frames = figures.death_frames(kind)
                frame = death_frames[min(int(figure.dying / frame_dt), len(death_frames) - 1)]
                self._show_frame(figure, frame)
                fade = max(0.0, (figure.dying - len(death_frames) * frame_dt) /
                           (lifetime - len(death_frames) * frame_dt))
                figure.sprite.opacity = int(255 * (1 - min(1.0, fade)))
                figure.shadow.opacity = int(150 * (1 - min(1.0, fade)))
            else:
                lifetime = LEGACY_DEATH_LIFE
                t = min(1.0, figure.dying / 0.45)
                figure.sprite.rotation = figure.fall * 80 * (t * t)
                figure.sprite.opacity = int(255 * (1 - max(0.0, (figure.dying - 0.3) / 0.5)))
            figure.dying += motion_dt
            if figure.dying > lifetime:
                figure.sprite.remove()
                if figure.puppet is not None:
                    figure.puppet.remove()
                if figure.monster.kind.key in figures.ENHANCED:
                    figure.shadow.remove()
                self.dying.remove(figure)
        for standing in self.towers.values():
            tower = standing.tower
            tint = (1.0, 1.0, 1.0)
            for curse in tower.curses:
                tint = tuple(a * b for a, b in zip(tint, CURSE_TINT[curse]))
            if standing.sprite.image == "fx/soft/holy":   # a rune disc for a kind with no sprite yet
                base = (214 / 255, 204 / 255, 176 / 255) if tower.kind.key == "altar" else (120 / 255, 230 / 255, 60 / 255)
                tint = tuple(a * b for a, b in zip(tint, base))
            standing.sprite.tint = tint
            standing.pulse = max(0.0, standing.pulse - dt * 3)
            flicker = 0.85 + 0.15 * math.sin(self.clock * 11 + tower.id * 1.7) * math.sin(self.clock * 7.3 + tower.id)
            base = 26 + 6 * tower.level
            silenced = tower.silenced
            size = base * (flicker + standing.pulse * 0.8) * (0.4 if silenced else 1.0)
            standing.glow.size = (size, size)
            standing.glow.opacity = 120 if silenced else 210
            self._sigils(standing)
        for door in self.world.doors:
            self._gate(door.index, door.built, door.hp)
        for i, torch in enumerate(self.torches):
            f = 0.8 + 0.2 * math.sin(self.clock * 13 + i * 2.1) * math.sin(self.clock * 5.1 + i)
            torch.size = (22 * f, 22 * f)

    def _sigils(self, standing: Standing) -> None:
        tower = standing.tower
        for curse in list(standing.sigils):
            if curse not in tower.curses:
                standing.sigils.pop(curse).remove()
        x, y = self.tower_top(tower)
        for i, (curse, left) in enumerate(sorted(tower.curses.items(), key=lambda kv: kv[0].value)):
            sigil = standing.sigils.get(curse)
            if sigil is None:
                sigil = standing.sigils[curse] = self.scene.add_sprite(
                    Sprite(f"fx/sigil/{CURSE_COLOR[curse]}", size=(40, 40), layer=RenderLayer.EFFECTS))
            fade = min(1.0, left / 1.0)
            sigil.position = (x, y - 18 - i * 10)
            sigil.rotation = (self.clock * 50 * (1 if i % 2 else -1)) % 360
            sigil.opacity = int(230 * fade)

    def _gate(self, index: int, built: bool, hp: float) -> None:
        sprite = self.gates.get(index)
        if not built and sprite is None:
            return
        look = "broken" if not built else "intact" if hp > self.world.gate_life * 0.5 else "damaged"
        if sprite is None:
            x, y = self.level.doors[index]
            sprite = self.gates[index] = self.scene.add_sprite(placed(f"gate/{look}", self.art.gate, *px(x + 0.5, y + 0.5)))
        sprite.image = f"gate/{look}"

    def lights(self) -> list[Light]:
        lights = list(self.static_lights)
        for i, light in enumerate(lights):
            if light.color in (TORCH, (255, 110, 40), (255, 100, 30)):   # flames flicker
                lights[i] = Light(light.x, light.y, light.radius, light.color,
                                  light.intensity * (0.85 + 0.15 * math.sin(self.clock * 13 + i * 2.1)))
        for standing in self.towers.values():
            tower = standing.tower
            x, y = self.tower_top(tower)
            strength = (0.55 + 0.12 * tower.level + standing.pulse * 0.6) * (0.35 if tower.silenced else 1.0)
            lights.append(Light(x, y + 30, 70 + 12 * tower.level + standing.pulse * 30, ELEMENT_LIGHT[tower.kind.key], strength))
            if tower.curses:
                lights.append(Light(x, y, 50, (160, 40, 200), 0.5))
        for figure in self.figures.values():
            m = figure.monster
            if m.kind.key == "azazel":
                lights.append(Light(figure.x, figure.y - 30, 110, (255, 90, 30), 0.9))
            elif m.kind.leader is not None:
                glow = 0.8 if m.chant_curse is not None else 0.3
                lights.append(Light(figure.x, figure.y - 20, 60, (180, 50, 220), glow))
        return lights

    def curse_names(self, tower: Tower) -> list[str]:
        return [f"{CURSES[c].name} {left:.0f}s" for c, left in sorted(tower.curses.items(), key=lambda kv: -kv[1])]
