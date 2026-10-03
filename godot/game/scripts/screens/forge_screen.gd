class_name ForgeScreen
extends Screen
## The tower forge, before a defence: the server's patterns (`forge_view`), one card each with its tower turning in
## a portrait, what it does, its price in salvage and trophies and one button: forge and equip, equip, or unequip.
## The grid's last slot teaches targeting strategies for salvage. A click asks the server (`forge`) and the reply
## is the new view. Back (Esc).

const CARD := Vector2(540, 334)
const GAP := 36.0
const TOP := 206.0                    # the first row of cards
const PORTRAIT := Vector2(196, 298)
const FAMILY_COLUMNS := {"arrow": "arrow", "pyre": "fire", "storm": "lightning", "frost": "cold", "plague": "poison",
	"altar": "bone", "grove": "nature"}
const GLOWS := {"arrow": Color(0.55, 0.32, 0.14), "pyre": Color(0.7, 0.26, 0.08), "frost": Color(0.16, 0.32, 0.6),
	"storm": Color(0.32, 0.22, 0.62), "plague": Color(0.22, 0.45, 0.12), "altar": Color(0.5, 0.45, 0.35),
	"grove": Color(0.2, 0.45, 0.16)}

var _stage: Control
var _portraits := {}                  # "kind:rank" -> [SubViewport, the turning pivot], kept across rebuilds
var _busy := false


func build() -> void:
	add_child(_backdrop())
	_lay_out("")


func back() -> void:
	game.close(self)


func _process(delta: float) -> void:
	super(delta)
	for key in _portraits:
		(_portraits[key][1] as Node3D).rotate_y(delta * 0.35)


func _lay_out(flash: String) -> void:
	var first := _stage == null
	if not first:
		remove_child(_stage)
		_stage.queue_free()
	_stage = SkillsScreen.stage(self)
	_header()
	var cards: Array = data["cards"]
	var total := cards.size() + 1   # the strategies share the grid's last slot
	var seen := {}                         # a family's cards so far: its first shows rank I, the next rank II...
	for i in cards.size():
		var card: Dictionary = cards[i]
		var family := String(card["family"])
		var rank: int = mini(int(seen.get(family, 0)), 2)
		seen[family] = int(seen.get(family, 0)) + 1
		var box := _card(card, _slot(i, total), rank)
		if first:
			box.modulate.a = 0.0
			var tw := box.create_tween()
			tw.tween_interval(0.08 + 0.07 * i)
			tw.tween_property(box, "modulate:a", 1.0, 0.35)
		elif String(card["key"]) == flash:
			box.pivot_offset = CARD / 2
			box.scale = Vector2(1.04, 1.04)
			box.modulate = Color(1.9, 1.7, 1.3)
			var tw := box.create_tween().set_parallel()
			tw.tween_property(box, "scale", Vector2.ONE, 0.45).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
			tw.tween_property(box, "modulate", Color.WHITE, 0.7)
	_strategies(_slot(cards.size(), total))
	var leave := Ui.button("Back", "Esc", 300)
	leave.position = Vector2(Ui.W / 2 - 150, 976)
	leave.pressed.connect(back)
	_stage.add_child(leave)


## The grid's i-th slot of `total` cards: rows of three, each row centred.
func _slot(i: int, total: int) -> Rect2:
	var row: int = i / 3
	var in_row: int = mini(total - row * 3, 3)
	var x := Ui.W / 2 - (in_row * CARD.x + (in_row - 1) * GAP) / 2 + (i % 3) * (CARD.x + GAP)
	return Rect2(Vector2(x, TOP + row * (CARD.y + GAP)), CARD)


## The strategies' card in the grid's last slot: each aim, its price, and its Teach button.
func _strategies(box: Rect2) -> void:
	var slot := Control.new()
	slot.position = box.position
	slot.size = box.size
	slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_stage.add_child(slot)
	slot.add_child(SkillsScreen.plate(box.size, Style.BRONZE, Color(0, 0, 0, 0), 0.0, 0.0, 0.0, 16.0))
	var title := SkillsScreen.words("Tower Strategies", Style.title_font(), 32, Style.GOLD)
	title.position = Vector2(22, 16)
	title.size = Vector2(box.size.x - 44, 42)
	slot.add_child(title)
	var y := 68.0
	for gift in data["strategies"]:
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 12)
		row.position = Vector2(22, y)
		row.size = Vector2(box.size.x - 44, 56)
		slot.add_child(row)
		var words := SkillsScreen.words("%s — %s" % [String(gift["name"]), String(gift["price"])],
			Style.text_font(), 20, Style.BONE if bool(gift["enabled"]) else Color(0.5, 0.47, 0.43))
		words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		words.tooltip_text = "%s %s" % [String(gift["words"]), String(gift["why"])]
		row.add_child(words)
		var act := Ui.button(String(gift["label"]), "", 150)
		act.disabled = not bool(gift["enabled"]) or bool(gift["owned"])
		act.tooltip_text = String(gift["why"])
		var key := String(gift["key"])
		act.pressed.connect(func(): _teach(key))
		row.add_child(act)
		y += 64.0


func _teach(key: String) -> void:
	if _busy:
		return
	_busy = true
	var view = await ask("forge", {"key": key})
	_busy = false
	if view != null:
		data = view
		_lay_out("")
		Sfx.play("upgrade")


## The title, the drops held and how the forge works.
func _header() -> void:
	SkillsScreen.heading(_stage, "Tower Forge", String(data["line"]))
	var help := [["Save monster drops for permanent patterns, or sell them during a wave break for battle gold.", Style.BONE],
		["One pattern per tower family can be equipped before a defence. Forging spends salvage and trophies.",
			Color(0.62, 0.58, 0.52)],
		["Strategies teach every tower a new aim, in every defence.", Color(0.62, 0.58, 0.52)]]
	for i in help.size():
		var l := SkillsScreen.words(String(help[i][0]), Style.text_font(), 19, help[i][1])
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.position = Vector2(0, 138 + i * 26)
		l.size = Vector2(Ui.W, 26)
		_stage.add_child(l)


## One pattern: its tower turning in a sunken well, its name and family, what it does, its price, its button.
## Equipped ones glow and wear a gilt tag; ones that cannot be forged yet are dim.
func _card(card: Dictionary, box: Rect2, rank: int) -> Control:
	var family := String(card["family"])
	var column: String = FAMILY_COLUMNS.get(family, "arrow")
	var tone: Color = SkillsScreen.TONES.get(column, Style.GOLD)
	var owned: bool = card["owned"]
	var equipped: bool = card["equipped"]
	var enabled: bool = card["enabled"]
	var rim: Color
	var glow: Color
	var inner := 0.0
	var pulse := 0.0
	if equipped:
		rim = Style.GOLD.lightened(0.1)
		glow = Color(1.0, 0.8, 0.42, 0.75)
		inner = 1.0
		pulse = 0.25
	elif owned:
		rim = Style.GOLD.darkened(0.1)
		glow = Color(1.0, 0.75, 0.4, 0.18)
	elif enabled:
		rim = Style.PALE_GOLD
		glow = Color(1.0, 0.78, 0.4, 0.45)
		pulse = 1.0
	else:
		rim = Color(0.36, 0.29, 0.22)
		glow = Color(0, 0, 0, 0)
	var lit := enabled or owned
	var slot := Control.new()
	slot.position = box.position
	slot.size = box.size
	slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_stage.add_child(slot)
	slot.add_child(SkillsScreen.plate(box.size, rim, glow, inner, pulse, 0.0, 16.0))

	# the portrait in its well, the tag under it
	var well := PanelContainer.new()
	well.add_theme_stylebox_override("panel", Style.well(Style.GOLD if equipped else Style.BRONZE if lit else Style.BRONZE.darkened(0.35)))
	well.position = Vector2(18, 18)
	well.size = PORTRAIT
	well.mouse_filter = Control.MOUSE_FILTER_IGNORE
	slot.add_child(well)
	var pic := TextureRect.new()
	pic.texture = _portrait(family, rank)
	pic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	pic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	pic.custom_minimum_size = PORTRAIT - Vector2(10, 10)
	pic.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if not lit:
		pic.modulate = Color(0.34, 0.32, 0.33)
	well.add_child(pic)
	if owned:
		slot.add_child(_tag("Equipped" if equipped else "Owned", equipped, Vector2(18 + PORTRAIT.x / 2, 18 + PORTRAIT.y - 6)))

	# the words
	var x := 18 + PORTRAIT.x + 22
	var width := box.size.x - x - 22
	var font := Style.title_font()
	var size := 34
	while size > 24 and font.get_string_size(String(card["name"]), HORIZONTAL_ALIGNMENT_LEFT, -1, size).x > width:
		size -= 1
	var title := SkillsScreen.words(String(card["name"]), font, size, Style.GOLD if lit else Color(0.5, 0.45, 0.38))
	title.position = Vector2(x, 20)
	title.size = Vector2(width, 44)
	slot.add_child(title)
	var kin := Control.new()
	kin.position = Vector2(x + 12, 84)
	kin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	kin.draw.connect(func(): SkillsScreen.medallion(kin, column, Vector2.ZERO, 12.0, tone, lit))
	slot.add_child(kin)
	var kind := SkillsScreen.words(String(card["family_name"]), Style.small_font(), 18, tone if lit else tone.darkened(0.35))
	kind.uppercase = true
	kind.position = Vector2(x + 32, 71)
	slot.add_child(kind)
	var rule := Control.new()
	rule.position = Vector2(x, 110)
	rule.mouse_filter = Control.MOUSE_FILTER_IGNORE
	rule.draw.connect(func():
		for i in 12:
			var t0 := i / 12.0
			var t1 := (i + 1) / 12.0
			rule.draw_line(Vector2(t0 * width, 0), Vector2(t1 * width, 0), Color(tone, (1.0 - t0) * (0.6 if lit else 0.3)), 1.2, true))
	slot.add_child(rule)
	var blurb := SkillsScreen.words(String(card["blurb"]), Style.text_font(), 20, Style.BONE if lit else Color(0.5, 0.47, 0.43))
	blurb.add_theme_constant_override("shadow_offset_y", 1)
	blurb.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	blurb.position = Vector2(x, 122)
	blurb.size = Vector2(width, 104)
	slot.add_child(blurb)
	var price_kicker := SkillsScreen.words("Price", Style.small_font(), 16, Style.DIM_GOLD if lit else Color(0.45, 0.4, 0.34))
	price_kicker.uppercase = true
	price_kicker.position = Vector2(x, 232)
	slot.add_child(price_kicker)
	var price := SkillsScreen.words(String(card["price"]), Style.text_font(), 21,
		(Style.GOLD if not owned else Style.DIM_GOLD) if lit else Color(0.5, 0.46, 0.4))
	price.position = Vector2(x + price_kicker.get_minimum_size().x + 10, 226)
	slot.add_child(price)

	var act := Ui.button(String(card["label"]), "", width)
	var fs := 20   # smaller, to 16, until the label fits the button's face (the server's "Opens at the ..." run long)
	while fs > 16 and Style.small_font().get_string_size(act.text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x > width - 44:
		fs -= 1
	act.add_theme_font_size_override("font_size", fs)
	act.clip_text = true
	act.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	act.position = Vector2(x, box.size.y - 66)
	act.size = Vector2(width, 46)
	act.disabled = not enabled
	act.tooltip_text = String(card["why"])
	var key := String(card["key"])
	act.pressed.connect(func(): _forge(key, equipped))
	slot.add_child(act)
	return slot


## A gilt tag hung over the bottom of a portrait, centred on `at`: "Equipped" in dark on gold, or "Owned" in bronze.
func _tag(text: String, bright: bool, at: Vector2) -> Control:
	var tag := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.82, 0.64, 0.32) if bright else Color(0.12, 0.09, 0.07)
	sb.border_color = Style.PALE_GOLD if bright else Style.BRONZE
	sb.set_border_width_all(2)
	sb.set_corner_radius_all(3)
	sb.content_margin_left = 16
	sb.content_margin_right = 16
	sb.content_margin_top = 3
	sb.content_margin_bottom = 4
	sb.shadow_color = Color(1.0, 0.75, 0.35, 0.55) if bright else Color(0, 0, 0, 0.6)
	sb.shadow_size = 10 if bright else 4
	tag.add_theme_stylebox_override("panel", sb)
	tag.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var l := Ui.label(text.to_upper(), 18, Color(0.16, 0.08, 0.03) if bright else Style.GOLD, Style.small_font())
	if bright:
		Ui.ink(l)
	tag.add_child(l)
	tag.resized.connect(func(): tag.position = at - tag.size / 2)
	return tag


## A tower of `kind` at `rank` turning slowly on a dark floor in a glow of its own colour, lit cool from the front
## and warm from behind, its fire and glow on (the HUD's portraits, framed whole and taller).
func _portrait(kind: String, rank: int) -> Texture2D:
	var key := "%s:%d" % [kind, rank]
	if _portraits.has(key):
		return (_portraits[key][0] as SubViewport).get_texture()
	var vp := SubViewport.new()
	vp.size = Vector2i(PORTRAIT * 2)
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(vp)
	var pivot := Node3D.new()
	vp.add_child(pivot)
	var model := Models.make(Tower.model_name(kind, rank))
	pivot.add_child(model)
	Tower.dress_fx(model, kind, rank)
	if Tower.STAND_INS.has(kind):   # a kind without a model of its own wears another's, tinted
		var overlay := ShaderMaterial.new()
		overlay.shader = preload("res://shaders/overlay.gdshader")
		overlay.set_shader_parameter("tint", Tower.STAND_INS[kind][1])
		for mi in model.find_children("*", "MeshInstance3D", true, false):
			(mi as MeshInstance3D).material_overlay = overlay
	var box := _bounds(model)
	var top := box.end.y + (0.9 if kind == "pyre" else 0.25)
	var bottom := box.position.y - 0.35
	var centre := Vector3(box.get_center().x, (top + bottom) / 2, box.get_center().z)
	var width := Vector2(box.size.x, box.size.z).length()
	var floor_disc := MeshInstance3D.new()   # a floor of dark stone fading into the dark
	var disc := PlaneMesh.new()
	disc.size = Vector2.ONE * width * 2.2
	floor_disc.mesh = disc
	var fm := StandardMaterial3D.new()
	var fade := GradientTexture2D.new()
	fade.gradient = Gradient.new()
	fade.gradient.colors = PackedColorArray([Color(0.11, 0.1, 0.1, 1.0), Color(0.02, 0.018, 0.022, 0.0)])
	fade.fill = GradientTexture2D.FILL_RADIAL
	fade.fill_from = Vector2(0.5, 0.5)
	fade.fill_to = Vector2(0.5, 1.0)
	fm.albedo_texture = fade
	fm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	fm.roughness = 1.0
	floor_disc.material_override = fm
	floor_disc.position = Vector3(box.get_center().x, box.position.y, box.get_center().z)
	vp.add_child(floor_disc)
	var cam := Camera3D.new()
	cam.fov = 24
	vp.add_child(cam)
	var aspect := PORTRAIT.x / PORTRAIT.y
	var yaw := deg_to_rad(32)
	var pitch := deg_to_rad(9)
	var toward := Vector3(sin(yaw) * cos(pitch), sin(pitch), -cos(yaw) * cos(pitch))
	var half_view := tan(deg_to_rad(cam.fov) / 2)
	var dist := maxf((top - bottom) * 0.54, width * 0.42 / aspect) / half_view
	cam.look_at_from_position(centre + toward * dist, centre)
	var back := MeshInstance3D.new()
	var quad := QuadMesh.new()
	var behind := dist + width
	quad.size = Vector2.ONE * behind * half_view * 2.6
	back.mesh = quad
	var bm := StandardMaterial3D.new()
	bm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	var glow := GradientTexture2D.new()
	glow.gradient = Gradient.new()
	glow.gradient.colors = PackedColorArray([GLOWS.get(kind, Color(0.5, 0.35, 0.2)), Color(0.02, 0.018, 0.022)])
	glow.fill = GradientTexture2D.FILL_RADIAL
	glow.fill_from = Vector2(0.5, 0.4)
	glow.fill_to = Vector2(0.5, 0.95)
	bm.albedo_texture = glow
	back.material_override = bm
	back.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	vp.add_child(back)
	back.look_at_from_position(centre - toward * width, centre + toward * dist)
	back.rotate_object_local(Vector3.UP, PI)
	var key_light := DirectionalLight3D.new()
	key_light.light_color = Color(0.75, 0.84, 1.0)
	key_light.light_energy = 3.0
	vp.add_child(key_light)
	key_light.look_at_from_position(centre + toward.rotated(Vector3.UP, deg_to_rad(-55)) * 10 + Vector3(0, 6, 0), centre)
	var rim := DirectionalLight3D.new()
	rim.light_color = Color(1.0, 0.58, 0.28)
	rim.light_energy = 6.0
	vp.add_child(rim)
	rim.look_at_from_position(centre - toward.rotated(Vector3.UP, deg_to_rad(-40)) * 10 + Vector3(0, 3, 0), centre)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.02, 0.018, 0.022)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.42, 0.44, 0.55)
	env.ambient_light_energy = 1.1
	env.glow_enabled = true
	env.glow_intensity = 0.8
	env.glow_hdr_threshold = 1.0
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.45
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	_portraits[key] = [vp, pivot]
	return vp.get_texture()


## A model's bounds in its own space, from its meshes.
static func _bounds(root: Node3D) -> AABB:
	var box := AABB()
	var first := true
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		var t := Transform3D.IDENTITY
		var n: Node = mi
		while n != root:
			t = (n as Node3D).transform * t
			n = n.get_parent()
		var b: AABB = t * (mi as MeshInstance3D).get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box


## The forge's dark: a fire's glow rising from below, embers drifting up through it, a gilt frame round the screen.
func _backdrop() -> Control:
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var base := ColorRect.new()
	base.color = Color(0.022, 0.016, 0.02)
	base.set_anchors_preset(Control.PRESET_FULL_RECT)
	base.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(base)
	root.add_child(SkillsScreen.radial(Color(0.36, 0.12, 0.03, 0.8), Color(0.3, 0.1, 0.03, 0.0), Vector2(0.5, 1.05), 0.7))
	root.add_child(SkillsScreen.radial(Color(0.16, 0.07, 0.03, 0.5), Color(0.16, 0.07, 0.03, 0.0), Vector2(0.5, 0.0), 0.5))
	var embers := CPUParticles2D.new()
	embers.amount = 70
	embers.lifetime = 9.0
	embers.preprocess = 9.0
	embers.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
	embers.emission_rect_extents = Vector2(Ui.W * 0.45, 10)
	embers.direction = Vector2(0, -1)
	embers.spread = 18.0
	embers.gravity = Vector2(0, -6)
	embers.initial_velocity_min = 25.0
	embers.initial_velocity_max = 70.0
	embers.scale_amount_min = 1.5
	embers.scale_amount_max = 3.5
	var fade := Gradient.new()
	fade.offsets = PackedFloat32Array([0.0, 0.2, 0.7, 1.0])
	fade.colors = PackedColorArray([Color(1.0, 0.6, 0.2, 0.0), Color(1.0, 0.55, 0.18, 0.9), Color(1.0, 0.35, 0.1, 0.5),
		Color(0.8, 0.2, 0.05, 0.0)])
	embers.color_ramp = fade
	root.add_child(embers)
	root.resized.connect(func():   # along the bottom edge of whatever the window is
		embers.position = Vector2(root.size.x / 2, root.size.y + 10)
		embers.emission_rect_extents = Vector2(root.size.x * 0.45, 10))
	var veil := SkillsScreen.radial(Color(0, 0, 0, 0.0), Color(0, 0, 0, 0.85), Vector2(0.5, 0.5), 0.8)
	root.add_child(veil)
	var frame := Control.new()
	frame.set_anchors_preset(Control.PRESET_FULL_RECT)
	frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	frame.draw.connect(func(): SkillsScreen.frame_lines(frame, frame.size))
	frame.resized.connect(frame.queue_redraw)
	root.add_child(frame)
	return root


func _forge(key: String, unequip: bool) -> void:
	if _busy:
		return
	_busy = true
	var view = await ask("forge", {"key": key})
	_busy = false
	if view != null:
		data = view
		_lay_out(key)
		Sfx.play("sell" if unequip else "upgrade")
