class_name Hud
extends CanvasLayer
## The screen over the battle: the life and mana orbs, the tower slots, gold and the wave, the chosen
## tower's orders, wave banners and the chronicle of the leaders' curses.

signal slot_pressed(kind: String)
signal order(name: String)            # "wave", "upgrade", "sell", "cleanse", "pace"

const SLOTS := ["arrow", "pyre", "frost", "storm"]

var world: World
var _life_orb: ColorRect
var _mana_orb: ColorRect
var _life_text: Label
var _mana_text: Label
var _gold: Label
var _wave: Label
var _call: Button
var _slots := {}
var _costs := {}
var _banner: Control
var _banner_title: Label
var _banner_line: Label
var _banner_tween: Tween
var _chronicle: VBoxContainer
var _orders: PanelContainer
var _orders_title: Label
var _orders_line: Label
var _upgrade: Button
var _sell: Button
var _cleanse: Button
var _pace: Button
var _selected: Tower


func setup(w: World) -> void:
	world = w
	world.changed.connect(refresh)
	world.announce.connect(_announce)
	_build()
	refresh()


func _build() -> void:
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)

	# the bottom panel, dark iron with a gold edge
	var panel := Panel.new()
	panel.anchor_left = 0.0
	panel.anchor_right = 1.0
	panel.anchor_top = 1.0
	panel.anchor_bottom = 1.0
	panel.offset_top = -132
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.045, 0.035, 0.035, 0.94)
	sb.border_color = Color(0.55, 0.42, 0.22)
	sb.border_width_top = 3
	sb.shadow_color = Color(0, 0, 0, 0.6)
	sb.shadow_size = 18
	panel.add_theme_stylebox_override("panel", sb)
	root.add_child(panel)

	_life_orb = _orb(Color(0.78, 0.05, 0.04))
	_life_orb.position = Vector2(26, -190)
	_life_orb.anchor_top = 1.0
	_life_orb.anchor_bottom = 1.0
	root.add_child(_life_orb)
	_life_text = _label(Style.title_font(), 46, Style.PALE_GOLD)
	_life_orb.add_child(_life_text)
	_life_text.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_life_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_life_text.vertical_alignment = VERTICAL_ALIGNMENT_CENTER

	_mana_orb = _orb(Color(0.1, 0.22, 0.85))
	_mana_orb.anchor_left = 1.0
	_mana_orb.anchor_right = 1.0
	_mana_orb.anchor_top = 1.0
	_mana_orb.anchor_bottom = 1.0
	_mana_orb.position = Vector2(-206, -190)
	root.add_child(_mana_orb)
	_mana_text = _label(Style.title_font(), 40, Style.PALE_GOLD)
	_mana_orb.add_child(_mana_text)
	_mana_text.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_mana_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_mana_text.vertical_alignment = VERTICAL_ALIGNMENT_CENTER

	var bar := HBoxContainer.new()
	bar.anchor_top = 1.0
	bar.anchor_bottom = 1.0
	bar.anchor_left = 0.0
	bar.anchor_right = 1.0
	bar.offset_left = 240
	bar.offset_right = -240
	bar.offset_top = -118
	bar.offset_bottom = -10
	bar.add_theme_constant_override("separation", 14)
	root.add_child(bar)
	for i in SLOTS.size():
		bar.add_child(_slot(SLOTS[i], i + 1))
	var cleanse := _slot_button("C", Style.CURSE)
	cleanse.text = "Cleanse"
	cleanse.tooltip_text = "Cleanse (C): lift a curse from the chosen tower. 35 mana."
	cleanse.pressed.connect(func(): order.emit("cleanse"))
	bar.add_child(cleanse)

	var info := VBoxContainer.new()
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	info.add_theme_constant_override("separation", 2)
	bar.add_child(info)
	var title_row := HBoxContainer.new()
	info.add_child(title_row)
	var place := _label(Style.title_font(), 36, Style.GOLD)
	place.text = "Tristram"
	place.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_row.add_child(place)
	var coin := ColorRect.new()
	coin.custom_minimum_size = Vector2(22, 22)
	coin.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var cm := ShaderMaterial.new()
	cm.shader = preload("res://shaders/orb.gdshader")
	cm.set_shader_parameter("liquid", Color(1.0, 0.75, 0.2))
	cm.set_shader_parameter("level", 1.0)
	coin.material = cm
	title_row.add_child(coin)
	_gold = _label(Style.title_font(), 36, Style.PALE_GOLD)
	title_row.add_child(_gold)
	_wave = _label(Style.text_font(), 21, Style.BONE)
	info.add_child(_wave)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	info.add_child(row)
	_call = _button("Summon the next wave  (Space)")
	_call.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_call.pressed.connect(func(): order.emit("wave"))
	row.add_child(_call)
	_pace = _button("Pace 1x  (F)")
	_pace.pressed.connect(func(): order.emit("pace"))
	row.add_child(_pace)

	# the chosen tower's orders, over the panel
	_orders = PanelContainer.new()
	var ob := StyleBoxFlat.new()
	ob.bg_color = Color(0.05, 0.04, 0.04, 0.9)
	ob.border_color = Color(0.55, 0.42, 0.22)
	ob.set_border_width_all(2)
	ob.set_corner_radius_all(4)
	ob.content_margin_left = 16
	ob.content_margin_right = 16
	ob.content_margin_top = 8
	ob.content_margin_bottom = 10
	_orders.add_theme_stylebox_override("panel", ob)
	_orders.anchor_left = 0.5
	_orders.anchor_right = 0.5
	_orders.anchor_top = 1.0
	_orders.anchor_bottom = 1.0
	_orders.offset_left = -300
	_orders.offset_right = 300
	_orders.offset_top = -258
	_orders.offset_bottom = -146
	root.add_child(_orders)
	var ov := VBoxContainer.new()
	_orders.add_child(ov)
	_orders_title = _label(Style.title_font(), 28, Style.GOLD)
	ov.add_child(_orders_title)
	_orders_line = _label(Style.text_font(), 18, Style.BONE)
	ov.add_child(_orders_line)
	var orow := HBoxContainer.new()
	orow.add_theme_constant_override("separation", 10)
	ov.add_child(orow)
	_upgrade = _button("Upgrade (U)")
	_upgrade.pressed.connect(func(): order.emit("upgrade"))
	orow.add_child(_upgrade)
	_sell = _button("Sell (S)")
	_sell.pressed.connect(func(): order.emit("sell"))
	orow.add_child(_sell)
	_cleanse = _button("Cleanse (C)")
	_cleanse.pressed.connect(func(): order.emit("cleanse"))
	orow.add_child(_cleanse)
	_orders.visible = false

	# wave banners across the upper third
	_banner = VBoxContainer.new()
	_banner.anchor_left = 0.0
	_banner.anchor_right = 1.0
	_banner.offset_top = 150
	_banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(_banner)
	_banner_title = _label(Style.title_font(), 76, Style.GOLD)
	_banner_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_banner_title.add_theme_constant_override("outline_size", 14)
	_banner_title.add_theme_color_override("font_outline_color", Color(0.05, 0.02, 0.0, 0.9))
	_banner.add_child(_banner_title)
	_banner_line = _label(Style.text_font(), 30, Style.BONE)
	_banner_line.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_banner_line.add_theme_constant_override("outline_size", 10)
	_banner_line.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	_banner.add_child(_banner_line)
	_banner.modulate.a = 0.0

	_chronicle = VBoxContainer.new()
	_chronicle.anchor_left = 1.0
	_chronicle.anchor_right = 1.0
	_chronicle.offset_left = -560
	_chronicle.offset_right = -24
	_chronicle.offset_top = 22
	_chronicle.alignment = BoxContainer.ALIGNMENT_BEGIN
	_chronicle.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(_chronicle)


func _orb(color: Color) -> ColorRect:
	var r := ColorRect.new()
	r.size = Vector2(180, 180)
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/orb.gdshader")
	m.set_shader_parameter("liquid", color)
	var nt := NoiseTexture2D.new()
	nt.seamless = true
	var fn := FastNoiseLite.new()
	fn.frequency = 0.012
	fn.fractal_octaves = 4
	nt.noise = fn
	m.set_shader_parameter("noise", nt)
	r.material = m
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return r


func _label(font: Font, size: int, color: Color) -> Label:
	var l := Label.new()
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.8))
	l.add_theme_constant_override("shadow_offset_x", 2)
	l.add_theme_constant_override("shadow_offset_y", 2)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


func _button(text: String) -> Button:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_font_override("font", Style.text_font())
	b.add_theme_font_size_override("font_size", 19)
	b.add_theme_color_override("font_color", Style.PALE_GOLD)
	b.add_theme_color_override("font_hover_color", Color(1, 0.95, 0.8))
	b.add_theme_color_override("font_disabled_color", Color(0.45, 0.4, 0.35))
	for state in ["normal", "hover", "pressed", "disabled"]:
		var s := StyleBoxFlat.new()
		s.bg_color = {"normal": Color(0.16, 0.1, 0.07), "hover": Color(0.3, 0.18, 0.1),
			"pressed": Color(0.42, 0.26, 0.14), "disabled": Color(0.1, 0.08, 0.07)}[state]
		s.border_color = Color(0.6, 0.45, 0.24) if state != "disabled" else Color(0.3, 0.25, 0.2)
		s.set_border_width_all(2)
		s.set_corner_radius_all(3)
		s.content_margin_left = 14
		s.content_margin_right = 14
		s.content_margin_top = 4
		s.content_margin_bottom = 4
		b.add_theme_stylebox_override(state, s)
	return b


func _slot_button(key: String, accent: Color) -> Button:
	var b := _button("")
	b.custom_minimum_size = Vector2(104, 104)
	b.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
	b.vertical_icon_alignment = VERTICAL_ALIGNMENT_TOP
	b.expand_icon = true
	b.add_theme_color_override("font_color", accent)
	var k := _label(Style.title_font(), 22, Style.PALE_GOLD)
	k.text = key
	k.position = Vector2(8, 2)
	b.add_child(k)
	return b


func _slot(kind: String, number: int) -> Control:
	var b := _slot_button(str(number), Style.PALE_GOLD)
	b.icon = _icon(kind)
	b.tooltip_text = "%s (%d): %s" % [Tower.NAMES[kind], number, world.data["towers"][kind]["blurb"]]
	b.pressed.connect(func(): slot_pressed.emit(kind))
	var cost := _label(Style.title_font(), 22, Style.GOLD)
	cost.anchor_left = 1.0
	cost.anchor_right = 1.0
	cost.anchor_top = 1.0
	cost.anchor_bottom = 1.0
	cost.offset_left = -44
	cost.offset_top = -30
	b.add_child(cost)
	_slots[kind] = b
	_costs[kind] = cost
	return b


## The tower model itself, lit and photographed once in its own little world.
func _icon(kind: String) -> Texture2D:
	var vp := SubViewport.new()
	vp.size = Vector2i(192, 192)
	vp.transparent_bg = true
	vp.own_world_3d = true
	vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	add_child(vp)
	var model := Models.make("tower_arrow_1" if kind == "arrow" else "tower_" + kind)
	vp.add_child(model)
	var cam := Camera3D.new()
	cam.fov = 30
	vp.add_child(cam)
	cam.position = Vector3(4.2, 4.6, 7.2)
	cam.look_at(Vector3(0, 2.3, 0))
	var key := DirectionalLight3D.new()
	key.light_color = Color(1.0, 0.75, 0.5)
	key.light_energy = 3.5
	key.rotation_degrees = Vector3(-35, 40, 0)
	vp.add_child(key)
	var rim := DirectionalLight3D.new()
	rim.light_color = Color(0.5, 0.6, 1.0)
	rim.light_energy = 1.5
	rim.rotation_degrees = Vector3(-20, 200, 0)
	vp.add_child(rim)
	var env := Environment.new()
	env.background_mode = Environment.BG_CLEAR_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.55, 0.5, 0.5)
	env.ambient_light_energy = 1.4
	env.glow_enabled = true
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	return vp.get_texture()


func refresh() -> void:
	(_life_orb.material as ShaderMaterial).set_shader_parameter("level", float(world.lives) / World.START_LIVES)
	_life_text.text = str(world.lives)
	_gold.text = " %d" % world.gold
	var total: int = world.waves().size()
	if world.wave < 0:
		_wave.text = "Five waves come. Build beside the lanes, then summon the first."
	else:
		_wave.text = "Wave %d of %d:  %s" % [world.wave + 1, total, world.waves()[world.wave]["name"]]
	_call.disabled = not world.can_call()
	for kind in SLOTS:
		var cost := world.tower_cost(kind, 0)
		_costs[kind].text = str(cost)
		_costs[kind].add_theme_color_override("font_color", Style.GOLD if world.gold >= cost else Style.BLOOD)
	_refresh_orders()


func _process(_delta: float) -> void:
	(_mana_orb.material as ShaderMaterial).set_shader_parameter("level", world.mana / World.MANA_MAX)
	_mana_text.text = str(int(world.mana))
	if _selected and is_instance_valid(_selected):
		_refresh_orders()


func set_pace(fast: bool) -> void:
	_pace.text = "Pace 2x  (F)" if fast else "Pace 1x  (F)"


func select(t: Tower) -> void:
	_selected = t
	_refresh_orders()


func _refresh_orders() -> void:
	var t := _selected
	_orders.visible = t != null and is_instance_valid(t) and not t.removed
	if not _orders.visible:
		return
	var lv := t.level()
	_orders_title.text = "%s  %s" % [t.title(), ["I", "II", "III"][t.rank]]
	var state := "  Cursed: blows halved." if t.cursed > 0.0 else ""
	_orders_line.text = "%d damage, %.1f a second, reach %.1f.%s" % [int(lv["damage"]), float(lv["rate"]), float(lv["range"]), state]
	if t.rank < 2:
		var cost := world.tower_cost(t.kind, t.rank + 1)
		_upgrade.text = "Upgrade (U)  %d" % cost
		_upgrade.disabled = world.gold < cost
	else:
		_upgrade.text = "Highest rank"
		_upgrade.disabled = true
	_sell.text = "Sell (S)  +%d" % int(t.spent * 0.7)
	_sell.disabled = t.cursed > 0.0
	_cleanse.disabled = t.cursed <= 0.0 or world.mana < World.CLEANSE_COST
	_orders_line.add_theme_color_override("font_color", Style.CURSE if t.cursed > 0.0 else Style.BONE)


func _announce(title: String, line: String) -> void:
	if title == "":
		_chronicle_line(line)
		return
	_banner_title.text = title
	_banner_line.text = line
	if _banner_tween:
		_banner_tween.kill()
	_banner_tween = create_tween()
	_banner_tween.tween_property(_banner, "modulate:a", 1.0, 0.5)
	_banner_tween.tween_interval(2.6)
	_banner_tween.tween_property(_banner, "modulate:a", 0.0, 1.0)


func _chronicle_line(text: String) -> void:
	var l := _label(Style.text_font(), 22, Style.CURSE)
	l.text = text
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_chronicle.add_child(l)
	while _chronicle.get_child_count() > 5:
		_chronicle.get_child(0).free()
	var tw := l.create_tween()
	tw.tween_interval(7.0)
	tw.tween_property(l, "modulate:a", 0.0, 1.5)
	tw.tween_callback(l.queue_free)
