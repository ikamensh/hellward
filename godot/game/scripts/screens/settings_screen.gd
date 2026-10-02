class_name SettingsScreen
extends Screen
## The settings, over the title or the pause menu: the music's and the sounds' volume, fullscreen, and whether the
## leaders' minds show in the battle's chronicle. ↑↓ pick a row, ←→ change it (Enter or Space flips a switch), the mouse does
## the same on the row's buttons. Every change is saved and applied at once (game.prefs, on this machine).

const ROWS := [["Music", "music"], ["Sound effects", "sfx"], ["Fullscreen", "fullscreen"],
	["Leaders' minds in the chronicle", "minds"]]
const STEPS := 10                     # a volume moves by a tenth

var _row := 0
var _rows: Array = []                 # per row: {key, back (its highlight), marker, and its controls}


func build() -> void:
	add_child(PauseScreen.veil(0.5))
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 12)
	col.add_child(PauseScreen.heading("Settings"))
	col.add_child(PauseScreen.rule(320))
	col.add_child(PauseScreen.gap(8))
	for i in ROWS.size():
		col.add_child(_make_row(i, String(ROWS[i][0]), String(ROWS[i][1])))
	col.add_child(PauseScreen.gap(10))
	var hint := Ui.caps("↑↓ choose    ←→ change    Esc closes", 14, Style.DIM_GOLD)
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(hint)
	var close := PauseScreen.primary(Ui.button("Close", "Esc", 300))
	close.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	close.pressed.connect(func(): game.close(self))
	col.add_child(close)
	add_child(PauseScreen.centred(PauseScreen.card(col, 860)))
	_show()


func _key(event: InputEvent) -> void:
	var k := event as InputEventKey
	if k != null and k.pressed and _opened >= GUARD:
		var key := String(_rows[_row]["key"])
		var handled := true
		match k.keycode:
			KEY_UP: _select(posmod(_row - 1, _rows.size()))
			KEY_DOWN: _select(posmod(_row + 1, _rows.size()))
			KEY_LEFT: _change(key, -1)
			KEY_RIGHT: _change(key, 1)
			KEY_ENTER, KEY_SPACE:
				if _is_switch(key):
					_change(key, 0)
				else:
					handled = false
			_: handled = false
		if handled:
			get_viewport().set_input_as_handled()
			return
	super(event)
	get_viewport().set_input_as_handled()   # an overlay takes every key: none reaches what is under it


## A row: its name, then − / a gauge of tenths / the percent / + for a volume, or Off / On for a switch.
func _make_row(i: int, name: String, key: String) -> Control:
	var back := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.set_corner_radius_all(3)
	sb.content_margin_left = 14
	sb.content_margin_right = 14
	sb.content_margin_top = 6
	sb.content_margin_bottom = 6
	back.add_theme_stylebox_override("panel", sb)
	back.mouse_entered.connect(func(): _select(i))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	back.add_child(row)
	var marker := Ui.label("›", 30, Style.GOLD, Style.title_font())
	marker.custom_minimum_size = Vector2(16, 0)
	row.add_child(marker)
	var label := Ui.label(name, 25, Style.BONE)
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(label)
	var entry := {"key": key, "back": sb, "marker": marker, "label": label}
	if _is_switch(key):
		var off := _small("Off", 98)
		off.pressed.connect(func(): _set_switch(key, false))
		var on := _small("On", 98)
		on.pressed.connect(func(): _set_switch(key, true))
		var pair := HBoxContainer.new()
		pair.add_theme_constant_override("separation", 6)
		pair.custom_minimum_size = Vector2(330, 0)
		pair.alignment = BoxContainer.ALIGNMENT_END
		pair.add_child(off)
		pair.add_child(on)
		row.add_child(pair)
		entry["off"] = off
		entry["on"] = on
	else:
		var less := _small("−", 44)
		less.pressed.connect(func(): _change(key, -1))
		row.add_child(less)
		var gauge := HBoxContainer.new()
		gauge.add_theme_constant_override("separation", 4)
		gauge.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		var ticks: Array = []
		for t in STEPS:
			var tick := Panel.new()
			var tsb := StyleBoxFlat.new()
			tsb.set_border_width_all(1)
			tsb.set_corner_radius_all(1)
			tick.add_theme_stylebox_override("panel", tsb)
			tick.custom_minimum_size = Vector2(12, 22)
			tick.mouse_filter = Control.MOUSE_FILTER_STOP
			var level := float(t + 1) / STEPS
			tick.gui_input.connect(func(e: InputEvent): _tick_clicked(e, key, level))
			gauge.add_child(tick)
			ticks.append(tsb)
		row.add_child(gauge)
		var value := Ui.label("", 22, Style.PALE_GOLD)
		value.custom_minimum_size = Vector2(64, 0)
		value.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		value.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		row.add_child(value)
		var more := _small("+", 44)
		more.pressed.connect(func(): _change(key, 1))
		row.add_child(more)
		entry["ticks"] = ticks
		entry["value"] = value
	_rows.append(entry)
	return back


func _small(text: String, width: float) -> Button:
	var b := Ui.button(text, "", width)
	b.add_theme_font_size_override("font_size", 22)
	b.add_theme_stylebox_override("normal", Style.plaque(Color(0.16, 0.12, 0.1), Style.BRONZE, false, Vector2(8, 4)))
	b.add_theme_stylebox_override("hover", Style.plaque(Color(0.24, 0.17, 0.12), Color(1.0, 0.85, 0.5), false, Vector2(8, 4)))
	b.add_theme_stylebox_override("pressed", Style.plaque(Color(0.12, 0.09, 0.08), Style.PALE_GOLD, true, Vector2(8, 4)))
	return b


func _is_switch(key: String) -> bool:
	return key == "fullscreen" or key == "minds"


func _tick_clicked(e: InputEvent, key: String, level: float) -> void:
	var mb := e as InputEventMouseButton
	if mb != null and mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
		Sfx.play("click")
		_store(key, level)


## A step of a volume (`step` -1 or +1), or a switch: ← off, → on, 0 flips it.
func _change(key: String, step: int) -> void:
	var p: Prefs = game.prefs
	if _is_switch(key):
		var now: bool = p.get(key)
		_set_switch(key, not now if step == 0 else step > 0)
		return
	var level: float = p.get(key)
	_store(key, clampf(roundf(level * STEPS + step) / STEPS, 0.0, 1.0))
	Sfx.play("click")


func _set_switch(key: String, on: bool) -> void:
	if bool(game.prefs.get(key)) != on:
		Sfx.play("click")
	_store(key, on)


## Kept at once: the game may end without this screen closing.
func _store(key: String, value: Variant) -> void:
	var p: Prefs = game.prefs
	p.set(key, value)
	p.save()
	p.apply(get_window())
	_show()


func _select(i: int) -> void:
	_row = i
	_show()


func _show() -> void:
	var p: Prefs = game.prefs
	for i in _rows.size():
		var entry: Dictionary = _rows[i]
		var chosen := i == _row
		var sb: StyleBoxFlat = entry["back"]
		sb.bg_color = Color(0.93, 0.76, 0.42, 0.08) if chosen else Color(0, 0, 0, 0)
		sb.border_color = Color(0.93, 0.76, 0.42, 0.35) if chosen else Color(0, 0, 0, 0)
		sb.set_border_width_all(1)
		(entry["marker"] as Label).modulate.a = 1.0 if chosen else 0.0
		(entry["label"] as Label).add_theme_color_override("font_color", Style.PALE_GOLD if chosen else Style.BONE)
		var key := String(entry["key"])
		if _is_switch(key):
			var on := bool(p.get(key))
			_lit(entry["on"], on)
			_lit(entry["off"], not on)
		else:
			var level: float = p.get(key)
			(entry["value"] as Label).text = "%d%%" % roundi(level * 100)
			var ticks: Array = entry["ticks"]
			for t in ticks.size():
				var tsb: StyleBoxFlat = ticks[t]
				var full := t < roundi(level * STEPS)
				tsb.bg_color = Style.GOLD.lerp(Color(1.0, 0.55, 0.2), 1.0 - float(t) / STEPS) if full else Color(0.06, 0.05, 0.05)
				tsb.border_color = Style.PALE_GOLD if full else Color(0.35, 0.27, 0.16)


## The switch's chosen side lit in gold; the other dark.
func _lit(b: Button, on: bool) -> void:
	if on:
		b.add_theme_stylebox_override("normal", Style.plaque(Color(0.3, 0.19, 0.08), Style.GOLD, false, Vector2(8, 4)))
		b.add_theme_color_override("font_color", Color(1.0, 0.93, 0.74))
	else:
		b.add_theme_stylebox_override("normal", Style.plaque(Color(0.09, 0.075, 0.07), Color(0.4, 0.32, 0.2), false, Vector2(8, 4)))
		b.add_theme_color_override("font_color", Color(0.55, 0.5, 0.42))
