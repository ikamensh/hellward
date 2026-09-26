"""The pause menu and the settings: overlays over the fight or the title.

Settings live in ``~/.hellward/settings.json`` (``game.settings``): the music and effects volumes, the
window, and whether the leaders' minds show over the towers. They apply and are saved the moment they
change. ``--fullscreen`` starts one session fullscreen without changing the saved choice.
"""

from __future__ import annotations

from typing import Any, Callable

from saga2d import Anchor, Button, Game, Label, Layout, Panel, Row, Scene, Settings, Style

from hellward.ui import style

DEFAULTS: dict[str, Any] = {"music": 0.6, "sfx": 0.8, "fullscreen": False, "minds": True}
PANEL = Style(background_color=(18, 13, 14, 255), border_color=style.PANEL_EDGE, border_width=2, padding=26, radius=6)
QUIET_BUTTON = Style(background_color=(40, 30, 28, 255), hover_color=(78, 56, 40, 255), press_color=(120, 84, 48, 255),
                     border_color=(120, 94, 60, 255), border_width=1, padding=8, radius=4)


def validate(values: dict[str, Any]) -> None:
    for key in ("music", "sfx"):
        if not 0.0 <= values[key] <= 1.0:
            raise ValueError(f"{key} volume must be between 0 and 1")


def settings(game: Game) -> Settings:
    """The game's settings. A file that cannot be read or holds impossible values is kept aside as
    ``settings.recovery-<id>.json`` and replaced by the defaults, so saving never fails on it later."""
    values = game.settings(DEFAULTS, validator=validate)
    if values.error is not None:
        print(f"Hellward: {values.error}; starting from the default settings (the old file is kept as a recovery copy)")
        values.reset()
        values.save()
    return values


def apply_volumes(game: Game, values: Settings) -> None:
    game.audio.set_volume("music", values["music"])
    game.audio.set_volume("sfx", values["sfx"])


class _Overlay(Scene):
    """A panel over whatever is beneath, which stops while it is open; Escape closes it."""

    transparent = True
    pause_below = True
    pop_on_cancel = True

    def panel(self, title: str) -> Panel:
        panel = Panel(layout=Layout.VERTICAL, spacing=12, anchor=Anchor.CENTER, style=PANEL)
        panel.add(Label(title, text_style="banner", width=340, align="center"))
        self.ui.add(panel)
        return panel

    def draw(self) -> None:
        w, h = self.game.resolution
        self.draw_rect(0, 0, w, h, (0, 0, 0, 150))


class PauseScene(_Overlay):
    controls = {"s": "open_settings", "r": "restart", "m": "to_map", "t": "to_title"}   # no key leaves: Q is Smite in the fight

    def __init__(self, *, restart: Callable[[], None], to_map: Callable[[], None], to_title: Callable[[], None],
                 on_settings: Callable[[], None]) -> None:
        self._restart, self._to_map, self._to_title, self._on_settings = restart, to_map, to_title, on_settings

    def on_enter(self) -> None:
        panel = self.panel("Paused")
        for text, key, action in (("Resume", "Esc", self.game.pop), ("Settings", "S", self.open_settings),
                                  ("Start this defence again", "R", self.restart), ("To the map", "M", self.to_map),
                                  ("Back to the title", "T", self.to_title), ("Leave the game", None, self.quit)):
            panel.add(Button(text, hotkey=key, on_click=action, width=340, style=None if text == "Resume" else QUIET_BUTTON))

    def open_settings(self) -> None:
        self.game.push(SettingsScene(settings(self.game), on_close=self._on_settings))

    def restart(self) -> None:
        self._restart()

    def to_map(self) -> None:
        self._to_map()

    def to_title(self) -> None:
        self._to_title()

    def quit(self) -> None:
        self.game.quit()


class SettingsScene(_Overlay):
    """↑↓ pick a row, ←→ change it, Esc closes; the − and + buttons do the same with the mouse."""

    controls = {"left": "decrease", "right": "increase"}
    ROWS = (("Music", "music", "percent"), ("Sound effects", "sfx", "percent"), ("Fullscreen", "fullscreen", "toggle"),
            ("Leaders' minds over the towers", "minds", "toggle"))

    def __init__(self, values: Settings, *, on_close: Callable[[], None] | None = None) -> None:
        self.values = values
        self.after = on_close
        self.rows: dict[Row, str] = {}

    def on_enter(self) -> None:
        self.ui.enable_focus(navigation="vertical", activate=())
        panel = self.panel("Settings")
        for name, key, kind in self.ROWS:
            row = Row(spacing=10, focusable=True)
            self.rows[row] = key
            row.add(Label(lambda r=row: "›" if r.focused else "", text_style="hud", width=16, text_color=style.GOLD))
            row.add(Label(name, text_style="body", width=250))
            row.add(Button("−", on_click=lambda k=key: self.change(k, -1), width=40, focusable=False, style=QUIET_BUTTON))
            row.add(Label(lambda k=key, t=kind: self.shown(k, t), text_style="hud", width=70, align="center"))
            row.add(Button("+", on_click=lambda k=key: self.change(k, 1), width=40, focusable=False, style=QUIET_BUTTON))
            panel.add(row)
        self.ui.focus(next(iter(self.rows)))
        panel.add(Label("↑↓ choose   ←→ change   Esc closes", text_style="small", width=460, align="center"))

    def shown(self, key: str, kind: str) -> str:
        value = self.values[key]
        return f"{round(value * 100)}%" if kind == "percent" else ("On" if value else "Off")

    def change(self, key: str, direction: int) -> None:
        kind = next(k for _name, row_key, k in self.ROWS if row_key == key)
        if kind == "percent":
            self.values[key] = round(max(0.0, min(1.0, self.values[key] + 0.1 * direction)), 2)
            apply_volumes(self.game, self.values)
        else:
            self.values[key] = not self.values[key]
            if key == "fullscreen":
                self.game.set_fullscreen(self.values["fullscreen"])
        # Saved at once: Cmd+Q, and Ctrl-C on a Mac, end the process without closing any scene.
        self.values.save()

    def decrease(self) -> None:
        self.change(self.rows[self.ui.focused], -1)

    def increase(self) -> None:
        self.change(self.rows[self.ui.focused], 1)

    def on_exit(self) -> None:
        if self.after is not None:
            self.after()
