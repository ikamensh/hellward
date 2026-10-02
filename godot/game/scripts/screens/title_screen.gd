class_name TitleScreen
extends Screen
## The title: the painted nave with the horde breaking in, HELLWARD hanging in the dark vault above it, the two
## lines that say what the game is, and the ways in below the lit door. While the server starts its status shows
## where the profile line goes and the campaign's ways wait for it.

const TAGLINE := "The demons have leaders now. They watch your towers, and they choose."
const SUBLINE := "Each curse is picked by playing the fight ahead, again and again, before it is cast."
const WAKING := "Waking the game's rules..."
const GILT := """
shader_type canvas_item;
// The name's gold: lit at the top of the letters, darker towards their feet, a band of light across them.
uniform float top = 40.0;
uniform float bottom = 150.0;
varying float y;
void vertex() { y = VERTEX.y; }
void fragment() {
	float t = clamp((y - top) / (bottom - top), 0.0, 1.0);
	float gold = step(0.3, COLOR.r);
	COLOR.rgb *= mix(1.0, mix(1.22, 0.62, t), gold);
	COLOR.rgb += vec3(1.0, 0.92, 0.7) * 0.22 * exp(-pow((t - 0.32) / 0.07, 2.0)) * gold;
}
"""

const DRIFT := """
shader_type canvas_item;
// The painting drawn `zoom` times closer about its middle, by fractions of a pixel: a Control's own scale snaps its
// position to whole pixels, and so slow a drift moved in visible steps.
uniform float zoom = 1.0;
varying vec4 tint;
void vertex() { tint = COLOR; }
void fragment() { COLOR = texture(TEXTURE, (UV - 0.5) / zoom + 0.5) * tint; }
"""

var _clock := 0.0
var _name: Label
var _vault: TextureRect
var _line: Label
var _campaign: Array = []             # the ways that need the server: disabled until it is ready


func build() -> void:
	var back := Ui.backdrop("res://assets/ui/title.jpg")
	add_child(back)
	_drift(back.get_child(back.get_child_count() - 1) as Control)   # the painting: the kit's backdrop puts it last
	_vault = _shade([[0.0, Color(0, 0, 0, 0.92)], [0.55, Color(0, 0, 0, 0.62)], [1.0, Color(0, 0, 0, 0)]], 0.0, 0.0, 0.0, 520.0)
	add_child(_vault)
	add_child(_shade([[0.0, Color(0, 0, 0, 0)], [0.45, Color(0, 0, 0, 0.6)], [1.0, Color(0, 0, 0, 0.92)]], 1.0, 1.0, -560.0, 0.0))
	add_child(_embers())

	var head := VBoxContainer.new()
	head.anchor_right = 1.0
	head.offset_top = 70
	head.add_theme_constant_override("separation", 6)
	head.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(head)
	_name = PauseScreen.heading("Hellward", 150)
	_name.add_theme_constant_override("outline_size", 18)
	_name.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.7))
	_name.add_theme_constant_override("shadow_offset_x", 4)
	_name.add_theme_constant_override("shadow_offset_y", 6)
	var gilt := ShaderMaterial.new()
	gilt.shader = Shader.new()
	gilt.shader.code = GILT
	_name.material = gilt
	head.add_child(_name)
	head.add_child(PauseScreen.rule(640))
	head.add_child(_centred(Ui.label(TAGLINE, 30, Style.BONE)))
	head.add_child(_centred(Ui.label(SUBLINE, 23, Style.PALE_GOLD)))

	var menu := VBoxContainer.new()
	menu.anchor_left = 0.5
	menu.anchor_right = 0.5
	menu.anchor_top = 1.0
	menu.anchor_bottom = 1.0
	menu.offset_bottom = -64
	menu.grow_horizontal = Control.GROW_DIRECTION_BOTH
	menu.grow_vertical = Control.GROW_DIRECTION_BEGIN
	menu.add_theme_constant_override("separation", 10)
	add_child(menu)
	_line = _centred(Ui.label("", 22, Style.BONE))
	menu.add_child(_line)
	menu.add_child(PauseScreen.gap(4))
	var descend := PauseScreen.primary(Ui.button("Descend", "Enter", 440))
	descend.add_theme_font_size_override("font_size", 24)
	for way in [[descend, game.descend, true], [Ui.button("Campaign profiles", "P", 440), game.profiles, true],
			[Ui.button("Chronicle", "C", 440), game.chronicle, true],
			[Ui.button("Watch the leaders at work", "D", 440), game.demo, true],
			[Ui.button("Settings", "S", 440), game.settings, false], [Ui.button("Leave", "Q", 440), game.leave, false]]:
		var b: Button = way[0]
		b.pressed.connect(way[1])
		menu.add_child(b)
		if bool(way[2]):
			_campaign.append(b)

	if Net.is_ready:
		reload()
	else:
		for b in _campaign:
			(b as Button).disabled = true
		_status(WAKING)
		Net.status.connect(_status)
		Net.connected.connect(_on_ready)


func _process(delta: float) -> void:
	super(delta)
	_clock += delta
	var pulse := 0.5 + 0.5 * sin(_clock * 1.3)      # the vault breathes and the name glows with it
	_name.add_theme_color_override("font_color", Color(0.9 + 0.08 * pulse, 0.73, 0.4))
	_vault.modulate.a = 0.88 + 0.12 * pulse


## The profile line: whose campaign Descend goes on with.
func reload() -> void:
	var answer = await ask("profiles")
	if answer != null:
		_line.text = "Campaign profile: %s" % String(answer["current"])
		_line.add_theme_color_override("font_color", Style.BONE)


func _on_ready() -> void:
	for b in _campaign:
		(b as Button).disabled = false
	reload()


func _status(text: String) -> void:
	_line.text = text
	_line.add_theme_color_override("font_color", Style.DIM_GOLD)


## The painting drifts closer, slowly, and back (the kit's backdrop crops it evenly, so its middle is UV 0.5).
func _drift(pic: Control) -> void:
	var mat := ShaderMaterial.new()
	mat.shader = Shader.new()
	mat.shader.code = DRIFT
	pic.material = mat
	var zoom := func(z: float): mat.set_shader_parameter("zoom", z)
	var tw := pic.create_tween().set_loops()
	tw.tween_method(zoom, 1.0, 1.06, 28.0).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_method(zoom, 1.06, 1.0, 28.0).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)


## A band of dark across the window, from `stops` running down; anchored at the top (0) or the bottom (1).
func _shade(stops: Array, anchor_top: float, anchor_bottom: float, top: float, bottom: float) -> TextureRect:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array(stops.map(func(s): return s[0]))
	g.colors = PackedColorArray(stops.map(func(s): return s[1]))
	var tex := GradientTexture2D.new()
	tex.gradient = g
	tex.fill_to = Vector2(0, 1)
	tex.width = 4
	tex.height = 256
	var r := TextureRect.new()
	r.texture = tex
	r.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	r.stretch_mode = TextureRect.STRETCH_SCALE
	r.anchor_right = 1.0
	r.anchor_top = anchor_top
	r.anchor_bottom = anchor_bottom
	r.offset_top = top
	r.offset_bottom = bottom
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return r


## Embers rising from the floor of the nave.
func _embers() -> Control:
	var holder := Control.new()
	holder.set_anchors_preset(Control.PRESET_FULL_RECT)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var dot := GradientTexture2D.new()
	var g := Gradient.new()
	g.colors = PackedColorArray([Color(1, 1, 1, 1), Color(1, 1, 1, 0)])
	dot.gradient = g
	dot.fill = GradientTexture2D.FILL_RADIAL
	dot.fill_from = Vector2(0.5, 0.5)
	dot.fill_to = Vector2(0.5, 0.0)
	dot.width = 32
	dot.height = 32
	var p := CPUParticles2D.new()
	p.texture = dot
	p.amount = 110
	p.lifetime = 9.0
	p.preprocess = 9.0
	p.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
	p.emission_rect_extents = Vector2(Ui.W * 0.55, 20)
	p.position = Vector2(Ui.W / 2, Ui.H + 30)
	p.direction = Vector2(0, -1)
	p.spread = 18.0
	p.gravity = Vector2(0, -6)
	p.initial_velocity_min = 40.0
	p.initial_velocity_max = 110.0
	p.angular_velocity_min = 0.0
	p.scale_amount_min = 0.18
	p.scale_amount_max = 0.5
	var ramp := Gradient.new()
	ramp.offsets = PackedFloat32Array([0.0, 0.15, 0.7, 1.0])
	ramp.colors = PackedColorArray([Color(1.0, 0.6, 0.2, 0.0), Color(1.0, 0.62, 0.25, 0.9), Color(1.0, 0.35, 0.08, 0.5),
		Color(0.6, 0.1, 0.02, 0.0)])
	p.color_ramp = ramp
	var add := CanvasItemMaterial.new()
	add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	p.material = add
	holder.add_child(p)
	holder.resized.connect(func(): p.position = Vector2(holder.size.x / 2, holder.size.y + 30))
	return holder


func _centred(l: Label) -> Label:
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	return l
