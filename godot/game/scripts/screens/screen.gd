class_name Screen
extends Control
## A campaign screen: full-window, built in code in `build()` once the shell hands it the game and its data.
## Buttons made with Ui.button(text, key) answer their key; for a moment after a screen opens keys are ignored, so
## the key that opened it does not press something on it too.

const GUARD := 0.3

var game: Game
var data := {}                        # what the server said this screen shows
var _opened := 0.0


func _init() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	theme = Ui.theme()


## Lay the screen out from `data`; called by the shell after it is in the tree.
func build() -> void:
	pass


func _process(delta: float) -> void:
	_opened += delta


func _unhandled_key_input(event: InputEvent) -> void:
	var k := event as InputEventKey
	if k == null or not k.pressed or k.echo or _opened < GUARD:
		return
	for b in find_children("*", "Button", true, false):
		var button := b as Button
		if button.has_meta("key") and button.is_visible_in_tree() and not button.disabled \
				and Ui.keycode(String(button.get_meta("key"))) == k.keycode:
			get_viewport().set_input_as_handled()
			button.pressed.emit()
			return
	if k.keycode == KEY_ESCAPE:
		get_viewport().set_input_as_handled()
		back()


## Esc with no button for it.
func back() -> void:
	pass


## Ask the server; the reply's data, or null after showing why it refused.
func ask(kind: String, args := {}):
	var reply: Dictionary = await Net.ask(kind, args).done
	if not bool(reply["ok"]):
		Sfx.play("refuse")
		game.notice(String(reply["why"]))
		return null
	return reply["data"]


## What the shell calls when an overlay over this screen closes: ask the server again and show what changed.
func reload() -> void:
	pass
