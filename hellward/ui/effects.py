"""What the rules' events look like: bolts in flight, chain lightning, novas, blasts, deaths, curses.

:meth:`Effects.event` turns one event from :attr:`World.events` into sprites, particles, flashes of light
and floating words; :meth:`Effects.update` moves them and :meth:`Effects.draw` draws the ones made of
lines and text. Nothing here changes the rules.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from saga2d import ParticleEmitter, RenderLayer, Scene, Sprite

from hellward.sim.content import CURSES, MONSTERS
from hellward.sim.model import Bolt, World
from hellward.sim.planner import Decision
from hellward.ui import style
from hellward.ui.lighting import Light
from hellward.ui.view import T, WorldView, px

ELEMENT_OF = {"pyre": "fire", "storm": "lightning", "frost": "cold", "plague": "poison"}
BLOOD = {"skeleton": "fx/dust", "gargoyle": "fx/dust", "zombie": "fx/ichor"}


@dataclass
class Missile:
    bolt: Bolt
    head: Sprite
    trail: Sprite
    sparks: ParticleEmitter
    total: float
    age: float = 0.0
    origin: tuple[float, float] = (0.0, 0.0)
    target: tuple[float, float] = (0.0, 0.0)


@dataclass
class Bloom:
    """A sprite that grows and fades: a blast, a flash, a ring."""

    sprite: Sprite
    life: float
    start: float
    end: float
    age: float = 0.0
    opacity: float = 255.0
    aspect: float = 1.0
    spin: float = 0.0


@dataclass
class Bolt3:
    """One chain-lightning strike: the zigzags are redrawn a few times while it lasts."""

    points: list[tuple[float, float]]
    life: float = 0.22
    age: float = 0.0
    seed: int = 0


@dataclass
class Words:
    text: str
    x: float
    y: float
    color: tuple[int, int, int, int]
    life: float = 1.2
    age: float = 0.0
    rise: float = 26.0
    size: int = 14
    font: str | None = None


@dataclass
class Thought:
    """A leader's reckoning, shown over the towers it weighed."""

    decision: Decision
    leader: int
    life: float = 3.0
    age: float = 0.0


@dataclass
class Glow:
    light: Light
    life: float
    age: float = 0.0


@dataclass
class Effects:
    scene: Scene
    view: WorldView
    world: World
    missiles: dict[int, Missile] = field(default_factory=dict)
    blooms: list[Bloom] = field(default_factory=list)
    chains: list[Bolt3] = field(default_factory=list)
    words: list[Words] = field(default_factory=list)
    thoughts: list[Thought] = field(default_factory=list)
    glows: list[Glow] = field(default_factory=list)
    decals: list[Sprite] = field(default_factory=list)
    rng: random.Random = field(default_factory=lambda: random.Random(5))
    show_thoughts: bool = True

    # -- Building blocks --------------------------------------------------------------------

    def bloom(self, image: str, x: float, y: float, start: float, end: float, life: float, *, opacity: float = 255,
              aspect: float = 1.0, layer: RenderLayer = RenderLayer.EFFECTS, spin: float = 0.0) -> None:
        sprite = self.scene.add_sprite(Sprite(image, position=(x, y), size=(start, start * aspect), layer=layer, opacity=int(opacity)))
        self.blooms.append(Bloom(sprite, life, start, end, opacity=opacity, aspect=aspect, spin=spin))

    def burst(self, images: str | list[str], x: float, y: float, count: int, *, speed=(40, 140), life=(0.25, 0.6),
              size=(10, 10), direction=(0, 360), layer: RenderLayer = RenderLayer.EFFECTS, shrink: bool = True) -> None:
        self.scene.add_emitter(ParticleEmitter(images, (x, y), count=count, speed=speed, lifetime=life, size=size,
                                               direction=direction, layer=layer, shrink=shrink, rng=self.rng).burst())

    def light(self, x: float, y: float, radius: float, color: tuple[int, int, int], intensity: float, life: float) -> None:
        self.glows.append(Glow(Light(x, y, radius, color, intensity), life))

    def say(self, text: str, x: float, y: float, color, *, size: int = 14, life: float = 1.2, rise: float = 26.0,
            font: str | None = None) -> None:
        self.words.append(Words(text, x, y, color, life, rise=rise, size=size, font=font))

    def decal(self, image: str, x: float, y: float, size: float) -> None:
        sprite = self.scene.add_sprite(Sprite(image, position=(x, y), size=(size, size * 0.7), layer=RenderLayer.OBJECTS,
                                              opacity=200, rotation=self.rng.uniform(0, 360)))
        self.decals.append(sprite)
        if len(self.decals) > 70:
            self.decals.pop(0).remove()

    # -- Events -----------------------------------------------------------------------------------

    def event(self, e: tuple) -> None:
        kind = e[0]
        handler = getattr(self, f"on_{kind}", None)
        if handler is not None:
            handler(*e[1:])

    def on_spawn(self, monster_id: int) -> None:
        m = self.world.monster(monster_id)
        self.view.spawn(m)
        x, y = self.view.monster_point(m)
        self.bloom("fx/soft/ember", x, y - 10, 10, 50, 0.4, opacity=200)
        self.light(x, y, 90, (255, 70, 30), 0.8, 0.4)

    def on_bolt(self, bolt: Bolt) -> None:
        element = ELEMENT_OF[bolt.kind]
        tower = self.world.towers.get(bolt.tower)
        origin = self.view.tower_top(tower) if tower is not None else px(*bolt.origin)
        size = 22 if element == "fire" else 16
        head = self.scene.add_sprite(Sprite(f"fx/glow/{element}", position=origin, size=(size, size), layer=RenderLayer.EFFECTS))
        trail = self.scene.add_sprite(Sprite(f"fx/trail/{element}", position=origin, size=(size * 2.2, size * 0.65),
                                             layer=RenderLayer.EFFECTS, opacity=220))
        sparks = self.scene.add_emitter(ParticleEmitter(
            "fx/spark" if element == "fire" else f"fx/venom/{bolt.id % 3}", origin, speed=(5, 25), lifetime=(0.2, 0.45),
            size=(7, 7) if element == "fire" else (12, 12), layer=RenderLayer.EFFECTS, shrink=True, rng=self.rng).continuous(40))
        self.missiles[bolt.id] = Missile(bolt, head, trail, sparks, max(bolt.left, 0.05), origin=origin, target=origin)
        standing = self.view.towers.get(bolt.tower)
        if standing is not None:
            standing.pulse = 1.0

    def on_impact(self, bolt: Bolt, last: tuple[float, float], struck: list[int]) -> None:
        missile = self.missiles.pop(bolt.id, None)
        if missile is not None:
            x, y = missile.head.position
            for sprite in (missile.head, missile.trail):
                sprite.remove()
            missile.sparks.stop()
        else:
            x, y = px(*last)
        if bolt.kind == "pyre":
            big = bolt.splash > 0
            self.bloom("fx/glow/fire", x, y, 14, 70 if big else 36, 0.35)
            if big:
                self.bloom("fx/ring/fire", x, y, 10, bolt.splash * T * 2.2, 0.4, opacity=220, aspect=0.6)
                self.burst("fx/spark", x, y, 26, speed=(60, 190), size=(6, 6))
                self.burst([f"fx/smoke/{i}" for i in range(3)], x, y - 6, 5, speed=(10, 40), life=(0.5, 1.0), size=(30, 30), shrink=False)
                self.decal("fx/dust", x, y + 8, 30)
            else:
                self.burst("fx/spark", x, y, 10, speed=(40, 120), size=(5, 5))
            self.light(x, y, 150 if big else 90, (255, 130, 40), 1.2 if big else 0.8, 0.35)
        else:
            self.bloom("fx/glow/poison", x, y, 12, 34, 0.35)
            self.burst([f"fx/venom/{i}" for i in range(3)], x, y, 6, speed=(10, 45), life=(0.4, 0.8), size=(16, 16))
            self.light(x, y, 60, (120, 230, 60), 0.6, 0.3)

    def on_chain(self, tower_id: int, struck: list[int], where: list[tuple[float, float]]) -> None:
        tower = self.world.towers.get(tower_id)
        points = [self.view.tower_top(tower)] if tower is not None else []
        for monster_id, spot in zip(struck, where):
            m = self.world.monster(monster_id)
            points.append(self.view.chest(m) if m is not None else px(*spot))
        self.chains.append(Bolt3(points, seed=self.rng.randrange(1 << 20)))
        for x, y in points[1:]:
            self.bloom("fx/glow/lightning", x, y, 10, 30, 0.2)
            self.light(x, y, 80, (140, 190, 255), 0.9, 0.18)
        if points:
            self.light(*points[0], 110, (150, 200, 255), 1.0, 0.2)
        standing = self.view.towers.get(tower_id)
        if standing is not None:
            standing.pulse = 1.0

    def on_nova(self, tower_id: int) -> None:
        tower = self.world.towers[tower_id]
        cx, cy = px(tower.tile[0] + 0.5, tower.tile[1] + 0.5)
        reach = tower.reach * T * 2
        self.bloom("fx/ring/cold", cx, cy, 20, reach, 0.45, opacity=235, aspect=1.0)
        self.bloom("fx/soft/cold", cx, cy, 20, reach * 0.9, 0.5, opacity=110)
        self.burst("fx/shard", cx, cy - 10, 18, speed=(90, 170), life=(0.3, 0.5), size=(9, 9), shrink=False)
        self.light(cx, cy, reach * 0.6, (150, 220, 255), 1.0, 0.4)
        standing = self.view.towers.get(tower_id)
        if standing is not None:
            standing.pulse = 1.0

    def on_hit(self, monster_id: int, element) -> None:
        self.view.hit(monster_id, element.value)

    def on_death(self, monster_id: int, key: str, element, where: tuple[float, float], bounty: int) -> None:
        figure = self.view.kill(monster_id)
        x, y = (figure.x, figure.y) if figure is not None else px(*where)
        size = MONSTERS[key].size
        self.decal(BLOOD.get(key, "fx/blood"), x, y + 2, T * size * 0.9)
        if key in ("skeleton", "priest"):
            self.burst("fx/dust", x, y - 10, 10, speed=(30, 90), size=(10, 10))
        else:
            self.burst("fx/blood", x, y - T * size * 0.4, 10, speed=(30, 110), size=(9, 9))
        if element.value == "fire":
            self.burst([f"fx/smoke/{i}" for i in range(3)], x, y - 14, 4, speed=(5, 25), life=(0.6, 1.1), size=(26, 26), shrink=False)
        self.say(f"+{bounty}", x, y - T * size - 8, style.GOLD, size=13 if bounty < 20 else 17)
        if key == "azazel":
            self.scene.camera.shake(9, 1.2)
            self.bloom("fx/glow/fire", x, y - 30, 40, 260, 1.2)
            self.light(x, y, 300, (255, 120, 40), 1.6, 1.4)

    def on_leak(self, monster_id: int, key: str, lives: int) -> None:
        figure = self.view.figures.get(monster_id)
        x, y = (figure.x, figure.y) if figure is not None else px(*self.world.level.point(self.world.level.length))
        self.view.vanish(monster_id)
        self.bloom("fx/glow/blood", x, y - 20, 30, 140, 0.6)
        self.say(f"-{lives} life" if lives == 1 else f"-{lives} lives", x - 20, y - 50, style.BLOOD, size=18, life=1.8)
        self.scene.camera.shake(4 + lives, 0.35)
        self.light(x, y, 200, (255, 30, 30), 1.2, 0.6)

    def on_door_broken(self, index: int) -> None:
        x, y = self.world.level.doors[index]
        cx, cy = px(x + 0.5, y + 0.5)
        self.scene.camera.shake(6, 0.45)
        self.burst([f"fx/smoke/{i}" for i in range(3)], cx, cy - 20, 10, speed=(20, 80), life=(0.6, 1.2), size=(34, 34), shrink=False)
        self.burst("fx/dust", cx, cy - 20, 18, speed=(60, 160), size=(10, 10))
        self.say("The gate is broken!", cx - 60, cy - 60, style.BLOOD, size=17, life=2.0, font=style.TITLE_FONT)

    def on_door_built(self, index: int) -> None:
        x, y = self.world.level.doors[index]
        cx, cy = px(x + 0.5, y + 0.5)
        self.bloom("fx/soft/holy", cx, cy - 20, 20, 90, 0.6, opacity=200)
        self.burst("fx/spark", cx, cy - 20, 16, speed=(30, 90), size=(6, 6))

    def on_built(self, tower_id: int) -> None:
        tower = self.world.towers[tower_id]
        self.view.build(tower)
        self._raise_dust(tower)

    def on_upgraded(self, tower_id: int) -> None:
        tower = self.world.towers[tower_id]
        self.view.rebuild(tower)
        self._raise_dust(tower)
        x, y = self.view.tower_top(tower)
        self.bloom(f"fx/glow/{ELEMENT_OF[tower.kind.key]}", x, y, 20, 90, 0.6)

    def _raise_dust(self, tower) -> None:
        cx, cy = px(tower.tile[0] + 0.5, tower.tile[1] + 0.5)
        self.burst([f"fx/smoke/{i}" for i in range(3)], cx, cy + 6, 8, speed=(20, 60), life=(0.4, 0.8), size=(24, 24), direction=(180, 360), shrink=False)
        self.light(cx, cy, 80, (255, 200, 140), 0.7, 0.5)

    def on_sold(self, tower_id: int, tile, refund: int) -> None:
        self.view.raze(tower_id)
        cx, cy = px(tile[0] + 0.5, tile[1] + 0.5)
        self.burst([f"fx/smoke/{i}" for i in range(3)], cx, cy, 8, speed=(20, 60), life=(0.4, 0.8), size=(24, 24), shrink=False)
        self.say(f"+{refund}", cx, cy - 40, style.GOLD, size=15)

    def on_plan(self, leader_id: int, decision: Decision) -> None:
        if decision.options:
            self.thoughts = [Thought(decision, leader_id)]   # one leader's reckoning at a time: two over one tower is noise

    def on_chant(self, leader_id: int, curse, tower_id: int) -> None:
        m = self.world.monster(leader_id)
        if m is not None:
            x, y = self.view.chest(m)
            self.bloom("fx/soft/curse", x, y, 10, 60, 0.9, opacity=200)

    def on_cursed(self, leader_id: int, tower_id: int, curse) -> None:
        tower = self.world.towers[tower_id]
        x, y = self.view.tower_top(tower)
        self.bloom("fx/sigil/curse", x, y, 80, 30, 0.5, spin=300)
        self.bloom("fx/glow/curse", x, y, 20, 90, 0.5)
        self.burst([f"fx/miasma/{i}" for i in range(3)], x, y + 20, 10, speed=(20, 60), life=(0.6, 1.2), size=(26, 26), shrink=False)
        self.light(x, y, 140, (170, 40, 220), 1.2, 0.6)
        self.say(CURSES[curse].name, x - 30, y - 34, style.CURSE, size=16, life=1.8, font=style.TITLE_FONT)

    def on_fizzle(self, leader_id: int, tower_id: int) -> None:
        m = self.world.monster(leader_id)
        if m is not None:
            x, y = self.view.chest(m)
            self.burst([f"fx/miasma/{i}" for i in range(3)], x, y, 5, speed=(10, 30), size=(18, 18))
            self.say("fizzles", x - 20, y - 30, style.DIM, size=12)

    def on_cleansed(self, tower_id: int, lifted) -> None:
        tower = self.world.towers[tower_id]
        cx, cy = px(tower.tile[0] + 0.5, tower.tile[1] + 0.5)
        x, y = self.view.tower_top(tower)
        for i in range(5):
            self.bloom("fx/soft/holy", x, cy - i * 22, 16, 60, 0.7 + i * 0.05, opacity=220)
        self.burst("fx/spark", x, y, 30, speed=(40, 140), size=(7, 7))
        self.light(cx, cy, 180, (255, 230, 150), 1.5, 0.8)
        self.say("Cleansed", x - 34, y - 30, style.HOLY, size=16, font=style.TITLE_FONT)

    # -- Every frame ------------------------------------------------------------------------------

    def update(self, dt: float) -> None:
        for missile in list(self.missiles.values()):
            missile.age += dt
            bolt = missile.bolt
            m = self.world.monster(bolt.target)
            if m is not None and m.hp > 0:
                missile.target = self.view.chest(m)
            elif missile.target == missile.origin:
                missile.target = px(*bolt.last)
            t = min(1.0, missile.age / missile.total)
            (ox, oy), (tx, ty) = missile.origin, missile.target
            arc = -30 * math.sin(math.pi * t) if bolt.kind == "plague" else -8 * math.sin(math.pi * t)
            x, y = ox + (tx - ox) * t, oy + (ty - oy) * t + arc
            angle = math.degrees(math.atan2(ty - oy, tx - ox))
            missile.head.position = (x, y)
            missile.trail.rotation = angle
            w = missile.trail.size[0]
            missile.trail.position = (x - math.cos(math.radians(angle)) * w * 0.4, y - math.sin(math.radians(angle)) * w * 0.4)
            missile.sparks.position = (x, y)
            if missile.age > missile.total + 0.5:   # its impact never came (the rules lost it): let it go
                self.missiles.pop(bolt.id)
                missile.head.remove()
                missile.trail.remove()
                missile.sparks.stop()
        for bloom in list(self.blooms):
            bloom.age += dt
            t = bloom.age / bloom.life
            if t >= 1:
                bloom.sprite.remove()
                self.blooms.remove(bloom)
                continue
            ease = 1 - (1 - t) ** 2
            size = bloom.start + (bloom.end - bloom.start) * ease
            bloom.sprite.size = (size, size * bloom.aspect)
            bloom.sprite.opacity = int(bloom.opacity * (1 - t) ** 1.3)
            if bloom.spin:
                bloom.sprite.rotation = bloom.spin * bloom.age
        for chain in list(self.chains):
            chain.age += dt
            if chain.age >= chain.life:
                self.chains.remove(chain)
        for words in list(self.words):
            words.age += dt
            if words.age >= words.life:
                self.words.remove(words)
        for thought in list(self.thoughts):
            thought.age += dt
            if thought.age >= thought.life:
                self.thoughts.remove(thought)
        for glow in list(self.glows):
            glow.age += dt
            if glow.age >= glow.life:
                self.glows.remove(glow)

    def lights(self) -> list[Light]:
        out = [Light(g.light.x, g.light.y, g.light.radius, g.light.color, g.light.intensity * (1 - g.age / g.life)) for g in self.glows]
        for missile in self.missiles.values():
            x, y = missile.head.position
            if missile.bolt.kind == "pyre":
                out.append(Light(x, y, 70, (255, 140, 50), 0.9))
            else:
                out.append(Light(x, y, 40, (120, 230, 60), 0.5))
        return out

    def draw(self) -> None:
        scene = self.scene
        for chain in self.chains:
            rng = random.Random(chain.seed + int(chain.age / 0.045))
            fade = 1 - chain.age / chain.life
            for (x0, y0), (x1, y1) in zip(chain.points, chain.points[1:]):
                path = _zigzag(rng, x0, y0, x1, y1)
                for width, color in ((7, (90, 140, 255, int(70 * fade))), (3.5, (170, 205, 255, int(200 * fade))), (1.4, (255, 255, 255, int(255 * fade)))):
                    for (a, b), (c, d) in zip(path, path[1:]):
                        scene.draw_line(a, b, c, d, color, width, space="world", layer=RenderLayer.EFFECTS)
        for leader in self.world.leaders():
            if leader.chant_curse is None:
                continue
            tower = self.world.towers.get(leader.chant_tower)
            if tower is None:
                continue
            (x0, y0), (x1, y1) = self.view.chest(leader), self.view.tower_top(tower)
            spec = leader.kind.leader
            grow = 1 - leader.chant_left / spec.channel
            rng = random.Random(leader.id * 7 + int(self.view.clock / 0.06))
            path = _zigzag(rng, x0, y0, x0 + (x1 - x0) * grow, y0 + (y1 - y0) * grow, jag=7)
            for width, color in ((6, (120, 20, 160, 90)), (2.5, (210, 90, 255, 220)), (1, (255, 220, 255, 255))):
                for (a, b), (c, d) in zip(path, path[1:]):
                    scene.draw_line(a, b, c, d, color, width, space="world", layer=RenderLayer.EFFECTS)
        for words in self.words:
            t = words.age / words.life
            alpha = int(words.color[3] * (1 - max(0.0, t - 0.6) / 0.4))
            y = words.y - words.rise * (1 - (1 - t) ** 2)
            scene.draw_text(words.text, words.x + 1, y + 1, font_size=words.size, color=(0, 0, 0, alpha), font=words.font or style.TEXT_FONT,
                            anchor_x="center", space="world", layer=RenderLayer.UI_WORLD)
            scene.draw_text(words.text, words.x, y, font_size=words.size, color=words.color[:3] + (alpha,), font=words.font or style.TEXT_FONT,
                            anchor_x="center", space="world", layer=RenderLayer.UI_WORLD)
        if self.show_thoughts:
            for thought in self.thoughts:
                self._draw_thought(thought)

    def _draw_thought(self, thought: Thought) -> None:
        scene = self.scene
        decision = thought.decision
        fade = min(1.0, (thought.life - thought.age) / 0.6) * min(1.0, thought.age / 0.15)
        chosen = decision.cast
        for option in decision.options:
            tower = self.world.towers.get(option.tower)
            if tower is None:
                continue
            x, y = self.view.tower_top(tower)
            picked = chosen is not None and option.tower == chosen.tower and option.curse == chosen.curse
            others = [o for o in decision.options if o.tower == option.tower]
            if not picked and any(chosen is not None and o.tower == chosen.tower and o.curse == chosen.curse for o in others):
                continue   # the chosen curse speaks for its tower
            best_here = max(others, key=lambda o: o.gain)
            if not picked and option is not best_here:
                continue
            text = f"{CURSES[option.curse].name} {option.gain:+.0f}" if picked else f"{option.gain:+.0f}"
            color = (255, 120, 255, int(255 * fade)) if picked else (200, 170, 200, int(170 * fade))
            size = 15 if picked else 12
            w = len(text) * size * 0.52 + 10
            # the box goes a layer below its words: in world space an order is taken from a shape's bottom edge
            scene.draw_rect(x - w / 2, y - 44, w, size + 8, (20, 6, 24, int(170 * fade)), radius=4, space="world", layer=RenderLayer.EFFECTS)
            scene.draw_text(text, x, y - 44 + 4, font_size=size, color=color, font=style.TEXT_FONT, anchor_x="center",
                            anchor_y="top", space="world", layer=RenderLayer.UI_WORLD)
        leader = self.world.monster(thought.leader)
        if leader is not None and chosen is None and decision.later is not None and decision.reason:
            x, y = self.view.chest(leader)
            text = f"waits: {decision.later.gain:+.0f} in {decision.later.delay:.0f}s"
            scene.draw_text(text, x, y - 40, font_size=12, color=(220, 170, 255, int(230 * fade)), font=style.TEXT_FONT,
                            anchor_x="center", space="world", layer=RenderLayer.UI_WORLD)


def _zigzag(rng: random.Random, x0: float, y0: float, x1: float, y1: float, jag: float = 10) -> list[tuple[float, float]]:
    """A jagged path between two points, by midpoint displacement."""
    points = [(x0, y0), (x1, y1)]
    for depth in range(4):
        out = [points[0]]
        scale = jag / (depth + 1)
        for (a, b), (c, d) in zip(points, points[1:]):
            mx, my = (a + c) / 2, (b + d) / 2
            nx, ny = -(d - b), c - a
            n = math.hypot(nx, ny) or 1.0
            off = rng.uniform(-scale, scale)
            out += [(mx + nx / n * off, my + ny / n * off), (c, d)]
        points = out
    return points
