"""The skill tree: six columns of three skills, learned with sigils, unlearned for free.

Opened from the world map or from a location's intro (then the columns that do nothing there are greyed). A
click learns a skill whose parent is learned and that the free sigils pay for; Unlearn all gives every sigil back.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from saga2d import Anchor, Button, Row, Scene

from hellward.sim.campaign import Location, idle
from hellward.sim.skills import COLUMNS, SKILLS, Skill, above, can_learn
from hellward.ui import style, widgets

if TYPE_CHECKING:
    from hellward.ui.flow import Flow

ICONS = {"fire": ("tower/pyre/2", 150 / 72), "lightning": ("tower/storm/2", 150 / 72), "cold": ("tower/frost/2", 150 / 72),
         "poison": ("tower/plague/2", 150 / 72), "warding": ("gate/intact", 80 / 60), "sorcery": ("ui/orb/mana/30", 1.0)}
COLOURS = {"fire": (255, 130, 50), "lightning": (140, 190, 255), "cold": (160, 225, 255), "poison": (130, 230, 70),
           "warding": (255, 222, 140), "sorcery": (120, 150, 255)}
COLUMN_X = 140
COLUMN_GAP = 200
TIER_Y = (220, 395, 570)
NODE_W, NODE_H = 176, 140


class SkillTreeScene(Scene):
    background_color = (8, 6, 8, 255)
    pause_below = True
    pop_on_cancel = True
    controls = {"u": "unlearn_all"}

    def __init__(self, flow: Flow, location: Location | None = None) -> None:
        self.flow = flow
        self.progress = flow.progress
        self.location = location
        self.spots: list[widgets.Hotspot] = []

    def on_enter(self) -> None:
        self.ui.add(Row(Button("Unlearn all", shortcut="U", on_click=self.unlearn_all, width=200),
                        Button("Close", shortcut="Esc", on_click=self.game.pop, width=160),
                        anchor=Anchor.BOTTOM, margin=(0, 16), spacing=14))

    def unlearn_all(self) -> None:
        if self.progress.learned:
            self.progress.unlearn_all()
            self.flow.sound.play("sell")

    def handle_input(self, event) -> bool:
        if event.type != "click":
            return False
        spot = widgets.hit(self.spots, event.x, event.y)
        if spot is None:
            return False
        if self.progress.learn(spot.name):
            self.flow.sound.play("upgrade")
        elif spot.name not in self.progress.learned:
            self.flow.sound.play("refuse")
        return True

    # -- Drawing ----------------------------------------------------------------------------------

    def draw(self) -> None:
        progress = self.progress
        self.spots = []
        self.draw_text("Skills", 640, 46, style="banner", anchor_x="center", anchor_y="center")
        where = f"  ·  greyed: nothing to work on in {self.location.name}" if self.location is not None else ""
        free = f"{progress.free} sigil{'' if progress.free == 1 else 's'} free"
        self.draw_text(f"{free} of {progress.sigils} won. Unlearning is free.{where}", 640, 88, font_size=15,
                       color=style.PALE_GOLD, anchor_x="center", anchor_y="center")
        for i, (column, name) in enumerate(COLUMNS.items()):
            cx = COLUMN_X + i * COLUMN_GAP
            image, aspect = ICONS[column]
            height = 36 * aspect if aspect > 1 else 36
            self.draw_image(image, cx - 18, 172 - height, 36, height)   # every icon stands on one line
            skills = sorted((s for s in SKILLS.values() if s.column == column), key=lambda s: s.tier)
            self.draw_text(name, cx, 192, style="heading", color=COLOURS[column] + (255,), anchor_x="center", anchor_y="center")
            for skill in skills:
                self._node(skill, cx)
        mouse = self.game.mouse_position
        if mouse is not None:
            spot = widgets.hit(self.spots, *mouse)
            if spot is not None and spot.tip:
                with self.screen_layer(5):
                    widgets.tooltip(self, spot.tip, mouse, mouse[1] - 16)

    def _node(self, skill: Skill, cx: float) -> None:
        progress = self.progress
        x, y = cx - NODE_W / 2, TIER_Y[skill.tier - 1]
        learned = skill.key in progress.learned
        learnable = can_learn(progress.learned, skill.key, progress.sigils)
        dormant = self.location is not None and idle(self.location, skill.needs)
        parent = above(skill)
        colour = COLOURS[skill.column]
        if parent is not None:   # the line down from the skill it needs
            lit = parent.key in progress.learned
            self.draw_line(cx, y - 35, cx, y, colour + (220,) if lit else (70, 60, 52, 200), 4 if lit else 2)
        fill = (40, 30, 22, 245) if learned else (18, 13, 14, 240)
        border = colour + (255,) if learned else (200, 170, 110, 255) if learnable else (70, 60, 52, 255)
        self.draw_rect(x, y, NODE_W, NODE_H, fill, border_color=border, border_width=2.5 if learned else 1.5, radius=8)
        if learned:
            self.draw_image(f"fx/soft/{_glow(skill.column)}", x + 10, y - 20, NODE_W - 20, 70, opacity=0.35)
        text = style.PALE_GOLD if (learned or learnable) else style.DIM
        size = 16 if len(skill.name) < 15 else 14
        self.draw_text(self.fit_text(skill.name, NODE_W - 12, font_size=size, font=style.TITLE_FONT), cx, y + 20, font_size=size,
                       color=text, font=style.TITLE_FONT, anchor_x="center", anchor_y="center")
        widgets.centred(self, skill.blurb, cx, y + 36, NODE_W - 16, font_size=12, color=style.BONE if not dormant else style.DIM,
                        max_lines=4)
        for k in range(skill.cost):   # its price in sigils
            px = cx + (k - (skill.cost - 1) / 2) * 16
            self.draw_circle(px, y + NODE_H - 14, 5.5, (230, 184, 90, 255) if learned else (120, 96, 60, 255))
        if dormant:
            with self.screen_layer(1):   # a veil over the whole node, its words and pips too
                self.draw_rect(x, y, NODE_W, NODE_H, (0, 0, 0, 150), radius=8)
        if learned:
            state = "Learned."
        elif learnable:
            state = f"Click to learn it for {skill.cost} sigil{'s' if skill.cost > 1 else ''}."
        elif parent is not None and parent.key not in progress.learned:
            state = f"Needs {parent.name} first."
        else:
            state = f"Costs {skill.cost} sigils; {progress.free} are free."
        note = "\nNothing to work on here." if dormant else ""
        self.spots.append(widgets.Hotspot(skill.key, (x, y, NODE_W, NODE_H), learnable, f"{skill.name}\n{skill.blurb}\n{state}{note}"))


def _glow(column: str) -> str:
    return {"fire": "fire", "lightning": "lightning", "cold": "cold", "poison": "poison", "warding": "holy", "sorcery": "curse"}[column]
