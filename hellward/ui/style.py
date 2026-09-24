"""Colours, fonts and the theme: dark iron, old gold and blood.

The titles are set in Luminari and the text in Baskerville when the system has them (macOS does; they are
read from the system, never shipped), otherwise in the engine's Nunito.
"""

from __future__ import annotations

from pathlib import Path

from saga2d import Game, TextStyle, Theme, fonts

GOLD = (214, 176, 96, 255)
PALE_GOLD = (240, 220, 170, 255)
BONE = (222, 212, 190, 255)
DIM = (150, 140, 128, 255)
BLOOD = (200, 36, 36, 255)
CURSE = (222, 132, 255, 255)
UNIQUE = (199, 179, 119, 255)     # a leader's name, as Diablo writes a unique monster's
BOSS = (255, 140, 40, 255)
MAGIC = (110, 130, 255, 255)
HOLY = (255, 232, 150, 255)
PANEL = (22, 18, 20, 255)
PANEL_EDGE = (92, 76, 58, 255)

_SYSTEM = Path("/System/Library/Fonts/Supplemental")
TITLE_FONT = fonts.EXTRABOLD
TEXT_FONT = fonts.SEMIBOLD


def load_fonts(game: Game) -> None:
    global TITLE_FONT, TEXT_FONT
    fonts.load(game)
    if (_SYSTEM / "Luminari.ttf").exists():
        TITLE_FONT = game.backend.load_font("Luminari", str(_SYSTEM / "Luminari.ttf"))
    if (_SYSTEM / "Baskerville.ttc").exists():
        TEXT_FONT = game.backend.load_font("Baskerville", str(_SYSTEM / "Baskerville.ttc"))


def theme() -> Theme:
    return Theme(
        font=TEXT_FONT, font_size=16, text_color=BONE,
        panel_background_color=PANEL, panel_border_color=PANEL_EDGE, panel_border_width=2,
        button_background_color=(46, 36, 32, 255), button_hover_color=(78, 58, 42, 255),
        button_press_color=(120, 84, 48, 255), button_text_color=PALE_GOLD, button_font_size=18,
        button_radius=3, keycap_color=(255, 230, 180, 40), keycap_text_color=PALE_GOLD,
        progressbar_color=BLOOD,
        text_styles={
            "title": TextStyle(64, GOLD, TITLE_FONT),
            "banner": TextStyle(34, GOLD, TITLE_FONT),
            "heading": TextStyle(20, GOLD, TITLE_FONT),
            "body": TextStyle(15, BONE, TEXT_FONT),
            "small": TextStyle(13, DIM, TEXT_FONT),
            "hud": TextStyle(18, PALE_GOLD, TEXT_FONT),
            "tag": TextStyle(12, BONE, fonts.EXTRABOLD),
        },
    )
