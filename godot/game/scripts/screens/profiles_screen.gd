class_name ProfilesScreen
extends Screen
## The campaign profiles, over the title: each keeps its own progress. Choose one (1-5, five to a page), or name a new
## one (N): letters, digits and underscores in lower case as it is typed; the server says why a name will not do.
## data = {profiles: [names], current}.

const PAGE := 5

var _page := 0
var _col: VBoxContainer
var _field: LineEdit
var _busy := false


func build() -> void:
	add_child(PauseScreen.veil(0.5))
	_col = VBoxContainer.new()
	_col.add_theme_constant_override("separation", 12)
	add_child(PauseScreen.centred(PauseScreen.card(_col, 640)))
	var names: Array = data["profiles"]
	_page = maxi(names.find(data["current"]), 0) / PAGE
	_list()


func _key(event: InputEvent) -> void:
	super(event)
	get_viewport().set_input_as_handled()   # an overlay takes every key: none reaches the title under it


func _clear() -> void:
	for c in _col.get_children():
		_col.remove_child(c)
		c.queue_free()
	_field = null


func _list() -> void:
	_clear()
	_col.add_child(PauseScreen.heading("Campaign profiles", 40))
	_col.add_child(PauseScreen.rule(360))
	_col.add_child(Ui.paragraph("Each profile saves its own progress.", 22, Style.DIM_GOLD, 540, HORIZONTAL_ALIGNMENT_CENTER))
	_col.add_child(PauseScreen.gap(4))
	var names: Array = data["profiles"]
	var current := String(data["current"])
	var first := _page * PAGE
	for i in range(first, mini(first + PAGE, names.size())):
		var name := String(names[i])
		var b := Ui.button(name + ("  •  current" if name == current else ""), str(i - first + 1), 540)
		b.add_theme_font_size_override("font_size", 22)
		if name == current:
			PauseScreen.primary(b)
		b.pressed.connect(func(): _choose(name))
		_centre(b)
	var pages := (names.size() - 1) / PAGE + 1
	if pages > 1:
		var row := HBoxContainer.new()
		row.alignment = BoxContainer.ALIGNMENT_CENTER
		row.add_theme_constant_override("separation", 14)
		var back := Ui.button("Previous", "Left", 200)
		back.disabled = _page == 0
		back.pressed.connect(_turn.bind(-1), CONNECT_DEFERRED)
		var at := Ui.label("%d / %d" % [_page + 1, pages], 22, Style.PALE_GOLD)
		at.custom_minimum_size = Vector2(90, 0)
		at.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		at.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		var on := Ui.button("Next", "Right", 200)
		on.disabled = _page + 1 >= pages
		on.pressed.connect(_turn.bind(1), CONNECT_DEFERRED)
		for c in [back, at, on]:
			row.add_child(c)
		_col.add_child(row)
	_col.add_child(PauseScreen.gap(8))
	var fresh := Ui.button("New campaign profile", "N", 540)
	fresh.pressed.connect(_new, CONNECT_DEFERRED)
	_centre(fresh)
	var close := Ui.button("Back", "Esc", 540)
	close.pressed.connect(func(): game.close(self))
	_centre(close)


func _turn(by: int) -> void:
	_page += by
	_list()


## A new campaign's name, typed into a sunken field.
func _new() -> void:
	_clear()
	_col.add_child(PauseScreen.heading("New campaign", 40))
	_col.add_child(PauseScreen.rule(360))
	_col.add_child(Ui.paragraph("Use letters, digits or _. Start with a letter or _.", 22, Style.DIM_GOLD, 540,
		HORIZONTAL_ALIGNMENT_CENTER))
	_col.add_child(PauseScreen.gap(6))
	_field = LineEdit.new()
	_field.placeholder_text = "Name your campaign"
	_field.max_length = 24
	_field.alignment = HORIZONTAL_ALIGNMENT_CENTER
	_field.custom_minimum_size = Vector2(540, 70)
	_field.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_field.context_menu_enabled = false
	_field.add_theme_font_override("font", Style.text_font())
	_field.add_theme_font_size_override("font_size", 32)
	_field.add_theme_color_override("font_color", Style.PALE_GOLD)
	_field.add_theme_color_override("font_placeholder_color", Color(0.5, 0.44, 0.36))
	_field.add_theme_color_override("caret_color", Style.GOLD)
	_field.add_theme_color_override("selection_color", Color(0.93, 0.76, 0.42, 0.3))
	_field.add_theme_constant_override("caret_width", 2)
	var well := Style.well(Style.GOLD)
	well.set_content_margin_all(14)
	_field.add_theme_stylebox_override("normal", well)
	_field.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	_field.keep_editing_on_text_submit = true
	_field.text_changed.connect(_typed)
	_field.text_submitted.connect(func(_t: String): _create())
	_field.gui_input.connect(_field_key)
	_col.add_child(_field)
	var hint := Ui.paragraph("Enter creates it; Esc goes back to the list.", 20, Style.DIM_GOLD, 540,
		HORIZONTAL_ALIGNMENT_CENTER)
	_col.add_child(hint)
	_col.add_child(PauseScreen.gap(6))
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 14)
	var create := PauseScreen.primary(Ui.button("Create", "Enter", 263))
	create.pressed.connect(_create)
	var back := Ui.button("Back", "Esc", 263)
	back.pressed.connect(_list, CONNECT_DEFERRED)
	row.add_child(create)
	row.add_child(back)
	_col.add_child(row)
	_edit.call_deferred()


## Only what a name may hold: lower case letters, digits, underscores.
func _typed(text: String) -> void:
	var kept := ""
	for ch in text.to_lower():
		if (ch >= "a" and ch <= "z") or (ch >= "0" and ch <= "9") or ch == "_":
			kept += ch
	if kept != text:
		var caret := _field.caret_column - (text.length() - kept.length())
		_field.text = kept
		_field.caret_column = clampi(caret, 0, kept.length())


## The field keeps the keys typed into it; Esc there goes back to the list (the field would only stop editing).
func _field_key(event: InputEvent) -> void:
	var k := event as InputEventKey
	if k != null and k.pressed and not k.echo and k.keycode == KEY_ESCAPE:
		_field.accept_event()
		Sfx.play("click")
		_list.call_deferred()


func _choose(name: String) -> void:
	if _busy:
		return
	_busy = true
	var answer = await ask("switch_profile", {"name": name})
	_busy = false
	if answer != null:
		game.close(self)


func _create() -> void:
	if _busy or _field == null:
		return
	_busy = true
	var answer = await ask("create_profile", {"name": _field.text})
	_busy = false
	if answer != null:
		game.close(self)
	elif _field != null:
		_edit()


func _edit() -> void:
	_field.grab_focus()
	_field.edit()


func _centre(b: Button) -> void:
	b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_col.add_child(b)
