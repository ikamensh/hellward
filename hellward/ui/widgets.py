"""Small pieces the screens share: clickable places drawn by hand, and the tooltip over them."""

from __future__ import annotations

from dataclasses import dataclass

from saga2d import Scene

from hellward.ui import style


@dataclass
class Hotspot:
    name: str
    box: tuple[float, float, float, float]   # x, y, width, height in screen pixels
    enabled: bool = True
    tip: str = ""

    def hit(self, x: float, y: float) -> bool:
        bx, by, w, h = self.box
        return bx <= x <= bx + w and by <= y <= by + h


def hit(spots: list[Hotspot], x: float, y: float) -> Hotspot | None:
    for spot in reversed(spots):   # the last drawn is on top
        if spot.hit(x, y):
            return spot
    return None


def tooltip(scene: Scene, tip: str, mouse: tuple[float, float], above: float, width: float = 320) -> None:
    """A dark box of lines over the pointer: the first line in gold, the rest in bone."""
    lines = tip.split("\n")
    layout = [scene.layout_text(line, width - 20, font_size=13) for line in lines]
    height = sum(part.height for part in layout) + 10 * len(layout) + 8
    x = min(max(mouse[0] - width / 2, 44), 1236 - width)
    y = max(4, above - height)
    scene.draw_rect(x, y, width, height, (16, 12, 12, 240), border_color=style.PANEL_EDGE, border_width=1.5, radius=4)
    yy = y + 8
    for i, line in enumerate(lines):
        yy += scene.draw_paragraph(line, x + 10, yy, width - 20, font_size=13, color=style.GOLD if i == 0 else style.BONE) + 8


def sigil_pips(scene: Scene, x: float, y: float, won: int, size: float = 9, gap: float = 22) -> None:
    """Three sigil slots centred on x, the won ones lit gold."""
    for i in range(3):
        cx = x + (i - 1) * gap
        lit = i < won
        scene.draw_circle(cx, y, size + 2, (20, 14, 10, 230))
        scene.draw_circle(cx, y, size, (230, 184, 90, 255) if lit else (70, 58, 46, 255))
        if lit:
            scene.draw_circle(cx - size * 0.3, y - size * 0.3, size * 0.35, (255, 238, 180, 255))


def centred(scene: Scene, text: str, cx: float, y: float, width: float, *, font_size: int, color, font: str | None = None,
            max_lines: int | None = None) -> float:
    """A word-wrapped paragraph with every line centred on cx, from its top at y; returns its height."""
    layout = scene.layout_text(text, width, font_size=font_size, font=font, max_lines=max_lines)
    for i, line in enumerate(layout.lines):
        scene.draw_text(line, cx, y + i * layout.line_height, font_size=font_size, color=color, font=font, anchor_x="center",
                        anchor_y="top")
    return layout.height
