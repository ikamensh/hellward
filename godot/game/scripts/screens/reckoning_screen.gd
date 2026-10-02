class_name ReckoningScreen
extends Screen
## The end of a defence, over the battle behind a dark veil: how it went (the server's result: Campaign._keep), the
## sigils it won lit one by one, what was banked and opened, and the way on: Again or To the map.

const FIRST := 0.6                   # the first sigil lights this long after the reckoning opens, the next ones
const EVERY := 0.45                  # this far apart, each with the upgrade cue
const TONES := {"holy": Color(1.0, 0.91, 0.59), "gold": Style.GOLD, "unique": Color(0.78, 0.7, 0.47),
	"pale": Style.PALE_GOLD}
const LOST := Color(0.88, 0.12, 0.07)

var _clock := 0.0
var _lit := 0
var _earned := 0
var _sigils: Array = []              # [lozenge stylebox, the lozenge, its flare] per slot
var _buttons: Array = []


func build() -> void:
	var won := bool(data["won"])
	var tone: Color = Style.GOLD if won else LOST
	_earned = int(data["earned"])
	add_child(PauseScreen.veil(0.45))

	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	col.alignment = BoxContainer.ALIGNMENT_CENTER
	var title := PauseScreen.heading(String(data["title"]), 76, tone)
	title.add_child(_smoke(tone))
	col.add_child(title)
	col.add_child(PauseScreen.rule(620, tone))
	col.add_child(PauseScreen.heading(String(data["location"]), 28, Style.PALE_GOLD))
	col.add_child(PauseScreen.gap(14))

	var inner := VBoxContainer.new()
	inner.add_theme_constant_override("separation", 14)
	var stats := HBoxContainer.new()
	stats.alignment = BoxContainer.ALIGNMENT_CENTER
	stats.add_theme_constant_override("separation", 70)
	inner.add_child(stats)
	for line in data["lines"]:
		var text := String(line)
		var parts := text.split(": ", true, 1)
		if parts.size() == 2 and not parts[1].contains(". ") and parts[1].length() <= 12:
			stats.add_child(_stat(parts[0], parts[1]))
		else:
			inner.add_child(Ui.paragraph(text, 22, Style.BONE, 860, HORIZONTAL_ALIGNMENT_CENTER))
	inner.add_child(PauseScreen.gap(4))
	inner.add_child(_sigil_row())
	inner.add_child(Ui.paragraph(String(data["note"]), 24, Style.PALE_GOLD, 860, HORIZONTAL_ALIGNMENT_CENTER))
	for pair in data["extra"]:
		var line_tone: Color = TONES[String(pair[0])]
		inner.add_child(Ui.paragraph(String(pair[1]), 22, line_tone, 860, HORIZONTAL_ALIGNMENT_CENTER))
	col.add_child(PauseScreen.card(inner, 960))
	col.add_child(PauseScreen.gap(14))

	var ways := HBoxContainer.new()
	ways.alignment = BoxContainer.ALIGNMENT_CENTER
	ways.add_theme_constant_override("separation", 20)
	var again := PauseScreen.primary(Ui.button("Again", "Enter", 280))
	again.pressed.connect(func(): _leave(true))
	var to_map := Ui.button("To the map", "Esc", 280)
	to_map.pressed.connect(func(): _leave(false))
	for b in [again, to_map]:
		ways.add_child(b)
		_buttons.append(b)
	col.add_child(ways)
	add_child(PauseScreen.centred(col))

	modulate.a = 0.0
	create_tween().tween_property(self, "modulate:a", 1.0, 0.35)


func _process(delta: float) -> void:
	super(delta)
	_clock += delta
	var due := mini(_earned, int((_clock - FIRST) / EVERY) + 1) if _clock >= FIRST else 0
	while _lit < due:
		_light(_lit)
		_lit += 1


func _key(event: InputEvent) -> void:
	super(event)
	get_viewport().set_input_as_handled()   # an overlay takes every key: none reaches the battle under it


func _leave(again: bool) -> void:
	for b in _buttons:
		(b as Button).disabled = true
	game.leave_reckoning(again)


## One of the result's figures: its number large, what it counts in small capitals under it.
func _stat(what: String, value: String) -> VBoxContainer:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 0)
	var v := Ui.label(value, 46, Style.PALE_GOLD, Style.title_font())
	v.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(v)
	var w := Ui.caps(what, 18, Style.DIM_GOLD)
	w.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(w)
	return box


## Three sigil slots, dark until they light.
func _sigil_row() -> Control:
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 46)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for i in 3:
		var holder := Control.new()
		holder.custom_minimum_size = Vector2(64, 64)
		holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var flare := TextureRect.new()
		flare.texture = _glow()
		flare.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		flare.size = Vector2(190, 190)
		flare.position = Vector2(32 - 95, 32 - 95)
		flare.pivot_offset = Vector2(95, 95)
		flare.modulate = Color(1.0, 0.75, 0.35, 0.0)
		flare.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var add := CanvasItemMaterial.new()
		add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		flare.material = add
		holder.add_child(flare)
		var gem := Panel.new()
		var sb := StyleBoxFlat.new()
		sb.bg_color = Color(0.07, 0.055, 0.05)
		sb.border_color = Style.BRONZE
		sb.set_border_width_all(3)
		sb.set_corner_radius_all(3)
		sb.shadow_color = Color(0, 0, 0, 0.8)
		sb.shadow_size = 6
		gem.add_theme_stylebox_override("panel", sb)
		gem.size = Vector2(36, 36)
		gem.position = Vector2(14, 14)
		gem.pivot_offset = Vector2(18, 18)
		gem.rotation = PI / 4
		gem.mouse_filter = Control.MOUSE_FILTER_IGNORE
		holder.add_child(gem)
		row.add_child(holder)
		_sigils.append([sb, gem, flare])
	return row


## A sigil lights: it fills with gold, swells and settles, a flare blooms behind it, the upgrade cue sounds.
func _light(i: int) -> void:
	var sb: StyleBoxFlat = _sigils[i][0]
	var gem: Panel = _sigils[i][1]
	var flare: TextureRect = _sigils[i][2]
	sb.bg_color = Style.GOLD
	sb.border_color = Style.PALE_GOLD
	sb.shadow_color = Color(1.0, 0.68, 0.25, 0.75)
	sb.shadow_size = 14
	Sfx.play("upgrade")
	gem.scale = Vector2(1.6, 1.6)
	var tw := create_tween().set_parallel()
	tw.tween_property(gem, "scale", Vector2.ONE, 0.5).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	flare.scale = Vector2(0.4, 0.4)
	tw.tween_property(flare, "scale", Vector2.ONE, 0.5).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.tween_property(flare, "modulate:a", 1.0, 0.12)
	tw.chain().tween_property(flare, "modulate:a", 0.45, 0.8)


## Dark smoke in a band behind the title, warmed by the outcome's colour (the HUD banner's shader).
func _smoke(tone: Color) -> Control:
	var band := ColorRect.new()
	band.show_behind_parent = true
	band.set_anchors_preset(Control.PRESET_FULL_RECT)
	band.offset_left = -520
	band.offset_right = 520
	band.offset_top = -120
	band.offset_bottom = 150
	band.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/hud_banner.gdshader")
	var nt := NoiseTexture2D.new()
	nt.seamless = true
	var fn := FastNoiseLite.new()
	fn.frequency = 0.006
	fn.fractal_octaves = 5
	nt.noise = fn
	m.set_shader_parameter("noise", nt)
	m.set_shader_parameter("tint", tone)
	band.material = m
	return band


func _glow() -> GradientTexture2D:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.25, 1.0])
	g.colors = PackedColorArray([Color(1, 1, 1, 0.9), Color(1, 1, 1, 0.35), Color(1, 1, 1, 0)])
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = Vector2(0.5, 0.5)
	t.fill_to = Vector2(0.5, 0.0)
	t.width = 128
	t.height = 128
	return t
