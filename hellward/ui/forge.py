"""The pre-defence forge: commit scarce drops to one authored pattern per tower family."""

from __future__ import annotations

from typing import TYPE_CHECKING

from saga2d import Anchor, Button, Scene

from hellward.sim.campaign import LOCATIONS, ORDER
from hellward.sim.items import PATTERNS, Pattern
from hellward.ui import style, widgets

if TYPE_CHECKING:
    from hellward.ui.flow import Flow


class ForgeScene(Scene):
    background_color = (8, 6, 8, 255)
    pause_below = True
    pop_on_cancel = True

    def __init__(self, flow: Flow) -> None:
        self.flow = flow
        self.progress = flow.progress
        self.spots: list[widgets.Hotspot] = []

    def on_enter(self) -> None:
        self.ui.add(Button("Back to briefing", shortcut="Esc", on_click=self.game.pop, width=240,
                           anchor=Anchor.BOTTOM, margin=(0, 22)))

    def handle_input(self, event) -> bool:
        if event.type != "click":
            return False
        spot = widgets.hit(self.spots, event.x, event.y)
        if spot is None:
            return False
        if not spot.enabled:
            self.flow.sound.play("refuse")
            return True
        key = spot.name
        pattern = PATTERNS[key]
        if key not in self.progress.patterns:
            self.progress.forge(key)
            self.progress.equip(key)
            self.flow.sound.play("upgrade")
        elif key in self.progress.loadout.equipped:
            self.progress.unequip(pattern.family)
            self.flow.sound.play("sell")
        else:
            self.progress.equip(key)
            self.flow.sound.play("upgrade")
        return True

    def draw(self) -> None:
        progress = self.progress
        self.spots = []
        self.draw_text("Tower Forge", 640, 48, style="banner", anchor_x="center", anchor_y="center")
        trophy_count = len(progress.trophies)
        trophy_label = "trophy" if trophy_count == 1 else "trophies"
        self.draw_text(f"{progress.salvage} salvage  ·  {trophy_count} {trophy_label} unspent", 640, 94,
                       font_size=20, color=style.PALE_GOLD, anchor_x="center", anchor_y="center")
        self.draw_text("Save monster drops for permanent patterns, or sell them during a wave break for battle gold.",
                       640, 126, font_size=14, color=style.BONE, anchor_x="center", anchor_y="center")
        self.draw_text("One pattern per tower family can be equipped before a defence. Forging spends salvage and trophies.",
                       640, 150, font_size=14, color=style.DIM, anchor_x="center", anchor_y="center")
        for i, pattern in enumerate(PATTERNS.values()):
            x = 61 + (i % 3) * 395
            y = 187 + (i // 3) * 223
            self._card(pattern, x, y)
        mouse = self.game.mouse_position
        if mouse is not None:
            spot = widgets.hit(self.spots, *mouse)
            if spot is not None and spot.tip:
                with self.screen_layer(5):
                    widgets.tooltip(self, spot.tip, mouse, mouse[1] - 14)

    def _card(self, pattern: Pattern, x: float, y: float) -> None:
        progress = self.progress
        owned = pattern.key in progress.patterns
        equipped = pattern.key in progress.loadout.equipped
        reached = progress.stage + 1 >= pattern.first_location
        active_here = ORDER.index(progress.at) + 1 >= pattern.first_location
        affordable = progress.salvage >= pattern.salvage_cost and len(progress.trophies) >= pattern.trophy_cost
        enabled = owned or (reached and affordable)
        edge = style.HOLY if equipped else style.GOLD if enabled else style.PANEL_EDGE
        self.draw_rect(x, y, 365, 202, (18, 12, 14, 245), border_color=edge,
                       border_width=2.0 if equipped else 1.3, radius=7)
        art = f"tower/{pattern.family}/2"
        if self.game.assets.has_image(art):
            self.draw_image(art, x + 20, y + 8, 37, 37 * 150 / 72)
        self.draw_text(pattern.name, x + 78, y + 28, font_size=19, color=style.PALE_GOLD if enabled else style.DIM,
                       font=style.TITLE_FONT, anchor_y="center")
        self.draw_text(f"{pattern.family.title()} Tower", x + 78, y + 53, font_size=13,
                       color=style.BONE, anchor_y="center")
        widgets.centred(self, pattern.blurb, x + 183, y + 91, 326, font_size=13, color=style.BONE, max_lines=2)
        price = f"{pattern.salvage_cost} salvage"
        if pattern.trophy_cost:
            price += f" + {pattern.trophy_cost} trophies"
        if equipped and not active_here:
            price = f"Inactive here · opens at {LOCATIONS[ORDER[pattern.first_location - 1]].called}"
        self.draw_text(price, x + 183, y + 141, font_size=13,
                       color=style.DIM if equipped and not active_here else style.GOLD if affordable else style.DIM,
                       anchor_x="center", anchor_y="center")
        if owned:
            label = "Unequip" if equipped else "Equip"
            if equipped and not active_here:
                label = "Unequip (inactive here)"
                reason = f"Equipped, but it has no effect here. It opens at {LOCATIONS[ORDER[pattern.first_location - 1]].called}."
            else:
                reason = "Owned permanently. Switch patterns without paying again."
        elif not reached:
            label = f"Opens at {LOCATIONS[ORDER[pattern.first_location - 1]].called}"
            reason = "Win earlier locations to unlock this pattern."
        elif not affordable:
            label = "Need more drops"
            reason = "Defeat monsters and claim side trophies to gather its materials."
        else:
            label = "Forge and equip"
            reason = "Spend these materials permanently and equip the pattern for the next defence."
        bx, by = x + 83, y + 163
        self.draw_rect(bx, by, 199, 29, (62, 45, 31, 255) if enabled else (32, 27, 26, 255),
                       border_color=edge, border_width=1.2, radius=4)
        self.draw_text(label, bx + 99, by + 14, font_size=13, color=style.PALE_GOLD if enabled else style.DIM,
                       anchor_x="center", anchor_y="center")
        self.spots.append(widgets.Hotspot(pattern.key, (bx, by, 199, 29), enabled,
                                          f"{pattern.name}\n{pattern.blurb}\n{reason}"))
