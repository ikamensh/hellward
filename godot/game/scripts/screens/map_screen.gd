class_name MapScreen
extends Screen
## The world map (the 2D game's ui/mapscreen.py): an act's painted map, its six places on it, the trail between
## them, and the lantern that walks it. Choosing an opened place walks the lantern down the trails to it (a click
## skips the walk), then opens its intro; a first descent (`first`) walks on by itself to the act's next place.
## The bar holds the act tabs, the skill tree, the forge and the way back to the title.
##
## Places and trails are in the painted picture's own pixels (data/worldmap.json) and drawn through the picture's
## fit: it covers the screen where it can, and on a screen too wide for that it shrinks until every place, its
## name and the lantern over it fit between the header and the bar. Captures: `walk=KEY` sends the lantern to KEY
## at once; `walk=first` makes the map a first descent.

const PACE := 340.0                   # picture pixels a second the lantern walks
const FIRST_STEP := 1.2               # seconds the map shows before a first descent walks on by itself
const PICTURE := Vector2(1280, 800)   # the painted maps' size, which the anchors and trails are in
const HEAD := 108.0                   # the header's band, over the middle of the picture
const HEAD_REACH := 340.0             # picture pixels either side of the middle that lie under the header
const FOOT := 76.0                    # the bar's band at the bottom
const SIDE := 200.0                   # room a place needs from the screen's side edges (its name hangs out)
const RING := 27.0                    # a place's medallion, radius
const LIFT := 56.0                    # the lantern's flame above the ground it walks
const LAMP := 1.5                     # the lantern's drawing scale
const ABOVE := LIFT + 44.0            # room a place needs above it: the lantern standing there
const NUMERALS := ["I", "II", "III", "IV", "V", "VI"]
const ASIDE := {"hells_gate": -1.0}   # names hung beside the medallion (-1 left, 1 right), not below it
const LOCKED_ACT := "Hold Hell's Gate to cross the sea"

const MEDALLION := """
shader_type canvas_item;
// A place's medallion: a dark iron face (ember-warm when opened) in a bevelled ring, gold when opened and
// cold iron when not, lit from above; a soft shadow round it.
uniform float lit = 1.0;
uniform float hover = 0.0;
const float INNER = 0.70;
const float OUTER = 0.88;

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	float aa = fwidth(r) * 1.2;
	vec2 n = p / max(r, 1e-4);
	vec2 light = normalize(vec2(-0.45, -1.0));
	vec4 col = vec4(0.0, 0.0, 0.0, 0.7 * (1.0 - smoothstep(OUTER, 1.0, r)));
	vec3 face = mix(vec3(0.05, 0.045, 0.05), vec3(0.24, 0.075, 0.035), lit * (1.0 - 0.7 * r / INNER));
	face *= 1.0 - 0.35 * dot(n, -light) * r;
	face = mix(face, face * 0.35, smoothstep(aa * 1.5, 0.0, abs(r - INNER * 0.84)) * 0.8);
	face += vec3(0.5, 0.18, 0.06) * hover * lit * (1.0 - r / INNER) * 0.5;
	col = mix(col, vec4(face, 1.0), 1.0 - smoothstep(INNER - aa, INNER, r));
	float t = (r - INNER) / (OUTER - INNER);
	vec2 facing = t < 0.5 ? -n : n;
	float shade = 0.55 + 0.65 * dot(facing, -light) * (1.0 - abs(t - 0.5) * 1.4);
	vec3 gold = mix(vec3(0.38, 0.24, 0.1), vec3(0.95, 0.76, 0.42), clamp(shade, 0.0, 1.2));
	gold += vec3(1.0, 0.9, 0.6) * pow(clamp(shade, 0.0, 1.0), 8.0) * 0.45;
	vec3 iron = mix(vec3(0.08, 0.07, 0.07), vec3(0.36, 0.32, 0.29), clamp(shade, 0.0, 1.2));
	vec3 ring = mix(iron, gold, lit) * (1.0 + 0.4 * hover);
	col = mix(col, vec4(ring, 1.0), smoothstep(INNER - aa, INNER, r) * (1.0 - smoothstep(OUTER - aa, OUTER, r)));
	COLOR = col;
}
"""

const HOLY := """
shader_type canvas_item;
render_mode blend_add;
// The holy light on the place the descent goes on to: a pulsing glow, slow turning rays, a ring rising outwards.
uniform vec4 tint : source_color = vec4(1.0, 0.9, 0.66, 1.0);
uniform float rim = 0.2;              // a ring just outside the medallion, as a fraction of the half-size

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	float a = atan(p.y, p.x);
	float pulse = 0.5 + 0.5 * sin(TIME * 3.0);
	float glow = exp(-r * r * 9.0) * 0.9 + exp(-r * r * 2.6) * 0.35;
	float rays = pow(0.5 + 0.5 * sin(a * 7.0 + TIME * 0.35), 7.0) * 0.55
		+ pow(0.5 + 0.5 * sin(a * 11.0 - TIME * 0.22 + 1.3), 9.0) * 0.4;
	rays *= smoothstep(1.0, 0.3, r) * smoothstep(0.1, 0.3, r);
	float k = fract(TIME * 0.4);
	float ring = exp(-pow((r - (0.3 + 0.55 * k)) / 0.035, 2.0)) * (1.0 - k) * 0.5;
	float halo = exp(-pow((r - rim) / 0.014, 2.0)) * (0.55 + 0.45 * pulse);
	float v = (glow + rays) * (0.65 + 0.35 * pulse) + ring + halo;
	COLOR = vec4(tint.rgb, v * smoothstep(1.0, 0.85, r));
}
"""

const FADE := """
shader_type canvas_item;
// The painted map, fading out towards any edge that does not reach the screen's (`fade`: left, top, right,
// bottom, as fractions of the picture).
uniform vec4 fade = vec4(0.0);

void fragment() {
	vec4 c = texture(TEXTURE, UV);
	float a = 1.0;
	if (fade.x > 0.0) { a *= smoothstep(0.0, fade.x, UV.x); }
	if (fade.y > 0.0) { a *= smoothstep(0.0, fade.y, UV.y); }
	if (fade.z > 0.0) { a *= smoothstep(0.0, fade.z, 1.0 - UV.x); }
	if (fade.w > 0.0) { a *= smoothstep(0.0, fade.w, 1.0 - UV.y); }
	COLOR = vec4(c.rgb, c.a * a);
}
"""

const BLUR := """
shader_type canvas_item;
// Behind a picture that cannot cover a wide screen: the same picture blurred and darkened.
void fragment() {
	vec3 s = vec3(0.0);
	for (int i = -3; i <= 3; i++) {
		for (int j = -3; j <= 3; j++) {
			s += texture(TEXTURE, UV + vec2(float(i), float(j)) * 0.012).rgb;
		}
	}
	COLOR = vec4(s / 49.0 * 0.32, 1.0);
}
"""

static var _worldmap := {}

var act := 1                          # the act shown
var _view := {}                       # that act as the server sees it: name, places, line, open
var _keys: Array = []                 # its places in order
var _anchors := {}                    # place key -> Vector2, picture pixels
var _held := {}                       # place key -> held (its trail onwards is lit)
var _scale := 1.0                     # the picture's fit: screen = _offset + picture pixels * _scale
var _offset := Vector2.ZERO
var _under: TextureRect
var _picture: TextureRect
var _paths: Control                   # the trails' dots
var _shine: Control                   # their glow, added over the picture
var _dots: Array = []                 # per trail: [PackedVector2Array of screen points, lit]
var _spots := {}                      # place key -> its Control, standing on the place
var _lamp: Control
var _lamp_glow: TextureRect
var _lamp_core: TextureRect
var _lamp_pool: TextureRect
var _lantern := Vector2.ZERO          # where the lantern is, picture pixels
var _stand := ""                      # the place it stands at on this map
var _present := false                 # whether it stands on this map (the campaign's `at` is in this act)
var _walk: Array = []                 # the points still ahead of it
var _going := ""                      # the place it walks to
var _leaving := false                 # it arrived: the intro is opening
var _first := false
var _clock := 0.0
var _flicker := 1.0
var _made := {}                       # shaders and the glow texture, made once per screen


func build() -> void:
	act = int(data["act"])
	_first = bool(data.get("first", false))
	resized.connect(_layout)
	_compose()
	var walk := String(game.args.get("walk", ""))
	if walk == "first":
		_first = true
	elif walk != "":
		_go(walk)


## Ask the server again and show the same act (an overlay above, the skill tree or the forge, has closed).
func reload() -> void:
	var view = await ask("campaign")
	if view == null:
		return
	var with: Dictionary = view.duplicate()
	with["act"] = act
	with["first"] = false
	data = with
	_first = false
	_compose()


# -- Building ----------------------------------------------------------------------------------------

func _compose() -> void:
	for c in get_children():
		remove_child(c)
		c.queue_free()
	_spots.clear()
	_walk.clear()
	_going = ""
	_leaving = false
	_clock = 0.0
	for a in data["acts"]:
		if int(a["act"]) == act:
			_view = a
	var map: Dictionary = _map_data()
	_anchors.clear()
	_held.clear()
	_keys.clear()
	var anchors: Dictionary = map["anchors"][str(act)]
	for p in _view["places"]:
		var key: String = p["key"]
		var xy: Array = anchors[key]
		_keys.append(key)
		_anchors[key] = Vector2(float(xy[0]), float(xy[1]))
		_held[key] = bool(p["held"])
	var at := String(data["at"])
	_present = _anchors.has(at)
	_stand = at if _present else String(_keys[0])
	_lantern = _anchors[_stand]

	_backdrop()
	_ambience()
	_paths = _layer()
	_paths.draw.connect(_draw_trails)
	_shine = _layer()
	_shine.material = _added()
	_shine.draw.connect(_draw_shine)
	_lantern_light()
	for p in _view["places"]:
		_place(p)
	_lantern_body()
	_header()
	_bar()
	_layout()


func _backdrop() -> void:
	var back := ColorRect.new()
	back.color = Color(0.025, 0.018, 0.022)
	back.set_anchors_preset(Control.PRESET_FULL_RECT)
	back.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(back)
	var tex: Texture2D = load("res://assets/ui/worldmap-%d.jpg" % act)
	_under = TextureRect.new()
	_under.texture = tex
	_under.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_under.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	_under.set_anchors_preset(Control.PRESET_FULL_RECT)
	_under.material = _material("blur")
	_under.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_under)
	_picture = TextureRect.new()
	_picture.texture = tex
	_picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_picture.stretch_mode = TextureRect.STRETCH_SCALE
	_picture.material = _material("fade")
	_picture.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_picture)
	var vignette := ColorRect.new()
	var vm := ShaderMaterial.new()
	vm.shader = preload("res://shaders/vignette.gdshader")
	vignette.material = vm
	vignette.set_anchors_preset(Control.PRESET_FULL_RECT)
	vignette.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(vignette)
	var top := _shade([[0.0, Color(0, 0, 0, 0.8)], [0.55, Color(0, 0, 0, 0.35)], [1.0, Color(0, 0, 0, 0)]])
	top.anchor_right = 1.0
	top.offset_bottom = 230
	add_child(top)
	var bottom := _shade([[0.0, Color(0, 0, 0, 0)], [0.5, Color(0, 0, 0, 0.3)], [1.0, Color(0, 0, 0, 0.85)]])
	bottom.anchor_right = 1.0
	bottom.anchor_top = 1.0
	bottom.anchor_bottom = 1.0
	bottom.offset_top = -200
	add_child(bottom)


## Embers rising from the deep in Act I; fireflies drifting over the jungle in Act II.
func _ambience() -> void:
	var motes := CPUParticles2D.new()
	motes.texture = _glow_texture()
	motes.material = _added()
	motes.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
	motes.lifetime = 9.0
	motes.preprocess = 9.0
	motes.randomness = 0.6
	var ramp := Gradient.new()
	if act == 1:
		motes.amount = 70
		motes.direction = Vector2(0.15, -1)
		motes.spread = 25.0
		motes.gravity = Vector2(0, -6)
		motes.initial_velocity_min = 12.0
		motes.initial_velocity_max = 34.0
		motes.scale_amount_min = 0.06
		motes.scale_amount_max = 0.16
		ramp.offsets = PackedFloat32Array([0.0, 0.15, 0.7, 1.0])
		ramp.colors = PackedColorArray([Color(1.0, 0.45, 0.12, 0.0), Color(1.0, 0.55, 0.2, 0.9),
			Color(1.0, 0.3, 0.08, 0.5), Color(0.6, 0.1, 0.02, 0.0)])
	else:
		motes.amount = 46
		motes.direction = Vector2(1, 0)
		motes.spread = 180.0
		motes.gravity = Vector2.ZERO
		motes.initial_velocity_min = 4.0
		motes.initial_velocity_max = 16.0
		motes.angular_velocity_min = -40.0
		motes.angular_velocity_max = 40.0
		motes.scale_amount_min = 0.07
		motes.scale_amount_max = 0.13
		ramp.offsets = PackedFloat32Array([0.0, 0.2, 0.3, 0.5, 0.62, 0.85, 1.0])
		ramp.colors = PackedColorArray([Color(0.8, 1.0, 0.4, 0.0), Color(0.85, 1.0, 0.45, 0.9),
			Color(0.8, 1.0, 0.4, 0.15), Color(0.85, 1.0, 0.45, 0.95), Color(0.8, 1.0, 0.4, 0.1),
			Color(0.85, 1.0, 0.45, 0.8), Color(0.8, 1.0, 0.4, 0.0)])
	motes.color_ramp = ramp
	motes.set_meta("motes", true)
	add_child(motes)


## A place: its holy light if the descent goes on there, a warm glow if opened, the numbered medallion, its name
## with the sigils won there; a click on it (or its name) walks the lantern there.
func _place(p: Dictionary) -> void:
	var key: String = p["key"]
	var opened: bool = p["opened"]
	var spot := Control.new()
	spot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(spot)
	_spots[key] = spot
	if bool(p["next"]):
		var holy := ColorRect.new()
		var hm := _material("holy")
		hm.set_shader_parameter("rim", (RING + 5.0) / 150.0)
		holy.material = hm
		holy.size = Vector2(300, 300)
		holy.position = -holy.size / 2
		holy.mouse_filter = Control.MOUSE_FILTER_IGNORE
		spot.add_child(holy)
	if opened:
		var warm := _glow(Vector2(170, 170), Color(1.0, 0.55, 0.25, 0.3))
		spot.add_child(warm)

	var half := RING / 0.88
	var medal := ColorRect.new()
	var mm: ShaderMaterial = _material("medallion")
	mm.set_shader_parameter("lit", 1.0 if opened else 0.0)
	medal.material = mm
	medal.size = Vector2(half, half) * 2
	medal.position = -medal.size / 2
	medal.pivot_offset = medal.size / 2
	medal.mouse_filter = Control.MOUSE_FILTER_STOP
	medal.tooltip_text = String(p["tip"])
	spot.add_child(medal)
	var numeral := Ui.label(NUMERALS[int(p["number"]) - 1], 23,
		Style.PALE_GOLD if opened else Color(0.52, 0.47, 0.42), Style.title_font())
	numeral.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	numeral.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	numeral.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	numeral.offset_top = 2
	medal.add_child(numeral)

	var plaque := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.035, 0.026, 0.028, 0.86)
	sb.border_color = Style.BRONZE if opened else Color(0.3, 0.26, 0.22)
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(3)
	sb.shadow_color = Color(0, 0, 0, 0.55)
	sb.shadow_size = 8
	sb.content_margin_left = 14
	sb.content_margin_right = 14
	sb.content_margin_top = 4
	sb.content_margin_bottom = 6
	plaque.add_theme_stylebox_override("panel", sb)
	plaque.mouse_filter = Control.MOUSE_FILTER_STOP
	plaque.tooltip_text = String(p["tip"])
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 3)
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	plaque.add_child(col)
	var called := Ui.caps(String(p["name"]), 20, Style.GOLD if opened else Color(0.5, 0.45, 0.4))
	called.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(called)
	if opened:
		var pips := Ui.pips(int(p["best"]), 9.0)
		pips.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		col.add_child(pips)
	spot.add_child(plaque)
	var side: float = ASIDE.get(key, 0.0)
	var hang := func():
		var s := plaque.size
		if side == 0.0:
			plaque.position = Vector2(-s.x / 2, RING + 9)
		else:
			plaque.position = Vector2(side * (RING + 12) - (s.x if side < 0.0 else 0.0), -s.y / 2)
	plaque.resized.connect(hang)
	hang.call()

	for c: Control in [medal, plaque]:
		if opened:
			c.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		c.gui_input.connect(func(e: InputEvent): _pressed(e, key, opened))
		c.mouse_entered.connect(func(): _hover(medal, sb, opened, true))
		c.mouse_exited.connect(func(): _hover(medal, sb, opened, false))


func _hover(medal: Control, sb: StyleBoxFlat, opened: bool, on: bool) -> void:
	if not opened:
		return
	(medal.material as ShaderMaterial).set_shader_parameter("hover", 1.0 if on else 0.0)
	sb.border_color = Color(1.0, 0.85, 0.5) if on else Style.BRONZE
	medal.create_tween().tween_property(medal, "scale", Vector2.ONE * (1.1 if on else 1.0), 0.12)


## The light the lantern throws, laid under the places so a medallion under it keeps its colours: a pool on the
## ground, a wide warm glow.
func _lantern_light() -> void:
	_lamp_pool = _glow(Vector2(260, 130), Color(1.0, 0.5, 0.18, 0.75))
	add_child(_lamp_pool)
	_lamp_glow = _glow(Vector2(300, 300), Color(1.0, 0.55, 0.2, 0.9))
	_lamp_glow.pivot_offset = _lamp_glow.size / 2
	add_child(_lamp_glow)


## The lantern itself, over the places: an iron lantern hanging over the ground it stands on, its hot core.
func _lantern_body() -> void:
	_lamp_core = _glow(Vector2(90, 90), Color(1.0, 0.82, 0.48, 0.9))
	add_child(_lamp_core)
	_lamp = Control.new()
	_lamp.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_lamp.scale = Vector2(LAMP, LAMP)
	_lamp.pivot_offset = Vector2(0, -26)
	_lamp.draw.connect(_draw_lamp)
	add_child(_lamp)


## The act's name, a gilt rule, the line of sigils won and free.
func _header() -> void:
	var smoke := ColorRect.new()
	var sm := ShaderMaterial.new()
	sm.shader = preload("res://shaders/hud_banner.gdshader")
	sm.set_shader_parameter("tint", Style.GOLD)
	sm.set_shader_parameter("noise", _noise())
	smoke.material = sm
	_pin(smoke, 0.5, 0.0, Rect2(-720, -46, 1440, 220))
	smoke.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(smoke)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 0)
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_pin(col, 0.5, 0.0, Rect2(-700, 10, 1400, 100))
	add_child(col)
	var title := Ui.label(String(_view["name"]).to_upper(), 46, Style.GOLD, Style.display_font())
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_constant_override("outline_size", 12)
	title.add_theme_color_override("font_outline_color", Color(0.04, 0.02, 0.0, 0.85))
	col.add_child(title)
	col.add_child(_rule(480))
	var line := Ui.label(String(_view["line"]), 22, Style.BONE)
	line.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(line)


## The iron bar at the bottom: Act I, Act II | Skills, Forge | The title.
func _bar() -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for a in data["acts"]:
		var n := int(a["act"])
		var tab := Ui.button("Act " + "I".repeat(n), str(n), 150)
		if not bool(a["open"]):
			tab.disabled = true
			tab.tooltip_text = LOCKED_ACT
		if n == act:
			tab.add_theme_stylebox_override("normal",
				Style.plaque(Color(0.3, 0.2, 0.11), Style.PALE_GOLD, true, Vector2(22, 10)))
			tab.add_theme_stylebox_override("hover",
				Style.plaque(Color(0.3, 0.2, 0.11), Style.PALE_GOLD, true, Vector2(22, 10)))
			tab.add_theme_color_override("font_color", Color(1.0, 0.95, 0.8))
		tab.pressed.connect(_show_act.bind(n))
		row.add_child(tab)
	row.add_child(_divider())
	var skills := Ui.button("Skills", "K", 160)
	var free := int(data["free"])
	skills.tooltip_text = "The skill tree: %d sigil%s to spend." % [free, "" if free == 1 else "s"]
	skills.pressed.connect(func():
		_halt()
		game.skills())
	row.add_child(skills)
	if free > 0:
		skills.add_child(_badge(free))
	var forge := Ui.button("Forge", "F", 160)
	forge.tooltip_text = "The tower forge: %d salvage banked, %d trophies won." % [int(data["salvage"]),
		int(data["trophies"])]
	forge.pressed.connect(func():
		_halt()
		game.forge())
	row.add_child(forge)
	row.add_child(_divider())
	var leave := Ui.button("The title", "Esc", 190)
	leave.pressed.connect(func(): game.title())
	row.add_child(leave)

	var bar := ColorRect.new()
	add_child(bar)
	add_child(row)
	var inner := row.get_combined_minimum_size()
	var bar_size := Vector2(inner.x + 76, 66)
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/hud_panel.gdshader")
	m.set_shader_parameter("size", bar_size)
	m.set_shader_parameter("chamfer", 18.0)
	m.set_shader_parameter("trim", 5.0)
	m.set_shader_parameter("spacing", 96.0)
	m.set_shader_parameter("rivet_from", 0.0)
	bar.material = m
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_pin(bar, 0.5, 1.0, Rect2(-bar_size.x / 2, -10 - bar_size.y, bar_size.x, bar_size.y))
	_pin(row, 0.5, 1.0, Rect2(-inner.x / 2, -10 - bar_size.y / 2 - inner.y / 2, inner.x, inner.y))


## A gold count on the Skills plaque's corner: sigils waiting to be spent.
func _badge(n: int) -> Label:
	var b := Ui.ink(Ui.label(str(n), 18, Color(0.12, 0.06, 0.02), Style.small_font()))
	var sb := StyleBoxFlat.new()
	sb.bg_color = Style.GOLD
	sb.border_color = Style.PALE_GOLD
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(12)
	sb.shadow_color = Color(1.0, 0.7, 0.3, 0.7)
	sb.shadow_size = 7
	sb.content_margin_left = 7
	sb.content_margin_right = 7
	b.add_theme_stylebox_override("normal", sb)
	b.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	b.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	b.anchor_left = 1.0
	b.anchor_right = 1.0
	b.offset_left = -16
	b.offset_right = 8
	b.offset_top = -10
	b.offset_bottom = 14
	b.grow_horizontal = Control.GROW_DIRECTION_BOTH
	var tw := b.create_tween().set_loops()
	tw.tween_property(b, "modulate", Color(1.25, 1.15, 1.0), 0.8).set_trans(Tween.TRANS_SINE)
	tw.tween_property(b, "modulate", Color(0.85, 0.8, 0.75), 0.8).set_trans(Tween.TRANS_SINE)
	return b


# -- Fitting the picture -----------------------------------------------------------------------------

## Fit the picture to the screen and put everything that stands on it where it belongs.
func _layout() -> void:
	if _picture == null or size.x <= 0.0:
		return
	_fit()
	var shown := PICTURE * _scale
	_picture.position = _offset
	_picture.size = shown
	var fade := Vector4(
		0.06 if _offset.x > 0.5 else 0.0, 0.06 if _offset.y > 0.5 else 0.0,
		0.06 if _offset.x + shown.x < size.x - 0.5 else 0.0, 0.06 if _offset.y + shown.y < size.y - 0.5 else 0.0)
	(_picture.material as ShaderMaterial).set_shader_parameter("fade", fade)
	_under.visible = fade != Vector4.ZERO
	for c in get_children():
		if c.has_meta("motes"):
			var motes := c as CPUParticles2D
			motes.position = size / 2
			motes.emission_rect_extents = size / 2
	for key in _spots:
		(_spots[key] as Control).position = _screen(_anchors[key])
	_dots.clear()
	for i in _keys.size() - 1:
		_dots.append([_beads(_trail(_keys[i], _keys[i + 1])), _held[_keys[i]]])
	_place_lantern()


## The largest scale up to covering the screen at which every place keeps its room (the lantern over it, its name
## under it, the header and the bar clear of both), then the offset nearest the centre that keeps it all inside.
func _fit() -> void:
	var view := size
	var s := maxf(view.x / PICTURE.x, view.y / PICTURE.y)
	var x0 := INF
	var x1 := -INF
	for key in _keys:
		var p: Vector2 = _anchors[key]
		x0 = minf(x0, p.x)
		x1 = maxf(x1, p.x)
		for other in _keys:
			var q: Vector2 = _anchors[other]
			if q.y > p.y:
				s = minf(s, (view.y - _top(key) - FOOT - _below(other)) / (q.y - p.y))
	s = minf(s, (view.x - 2.0 * SIDE) / maxf(x1 - x0, 1.0))
	var lo := Vector2(-INF, -INF)
	var hi := Vector2(INF, INF)
	for key in _keys:
		var p: Vector2 = _anchors[key] * s
		lo = Vector2(maxf(lo.x, SIDE - p.x), maxf(lo.y, _top(key) - p.y))
		hi = Vector2(minf(hi.x, view.x - SIDE - p.x), minf(hi.y, view.y - FOOT - _below(key) - p.y))
	var centred := (view - PICTURE * s) / 2.0
	_scale = s
	_offset = Vector2(_settle(centred.x, lo.x, hi.x, view.x - PICTURE.x * s),
		_settle(centred.y, lo.y, hi.y, view.y - PICTURE.y * s))


## An offset along one axis: inside [lo, hi], and covering the screen (in [slack, 0]) too when it can.
static func _settle(v: float, lo: float, hi: float, slack: float) -> float:
	if slack < 0.0 and maxf(lo, slack) <= minf(hi, 0.0):
		return clampf(v, maxf(lo, slack), minf(hi, 0.0))
	return clampf(v, lo, hi)


## The room a place needs above its ground: the lantern standing there, under the header if it is in the middle.
func _top(key: String) -> float:
	var p: Vector2 = _anchors[key]
	return ABOVE + (HEAD if absf(p.x - PICTURE.x / 2) < HEAD_REACH else 0.0)


## The room a place needs below: its name, unless it hangs beside it.
func _below(key: String) -> float:
	return RING + 14.0 if ASIDE.has(key) else RING + 80.0


func _screen(p: Vector2) -> Vector2:
	return _offset + p * _scale


## The trail between two neighbouring places, from `a` to `b`, in picture pixels.
func _trail(a: String, b: String) -> Array:
	for t in _map_data()["trails"][str(act)]:
		var pts: Array = []
		for xy in t["points"]:
			pts.append(Vector2(float(xy[0]), float(xy[1])))
		if t["from"] == a and t["to"] == b:
			return pts
		if t["from"] == b and t["to"] == a:
			pts.reverse()
			return pts
	push_error("no trail %s - %s" % [a, b])
	return [_anchors[a], _anchors[b]]


## Beads along a trail, evenly spaced on the screen, clear of the medallions at its ends.
func _beads(points: Array) -> PackedVector2Array:
	var out := PackedVector2Array()
	var gap := 15.0
	var screen: Array = points.map(func(p): return _screen(p))
	var total := 0.0
	for i in screen.size() - 1:
		total += (screen[i] as Vector2).distance_to(screen[i + 1])
	var along := 0.0
	var next := RING + 8.0
	for i in screen.size() - 1:
		var a: Vector2 = screen[i]
		var b: Vector2 = screen[i + 1]
		var length := a.distance_to(b)
		while next <= along + length and next <= total - RING - 8.0:
			out.append(a.lerp(b, (next - along) / length))
			next += gap
		along += length
	return out


# -- The lantern's walk ------------------------------------------------------------------------------

func _gui_input(event: InputEvent) -> void:
	var click := event as InputEventMouseButton
	if click != null and click.pressed and click.button_index == MOUSE_BUTTON_LEFT and _going != "":
		accept_event()
		_arrive()


func _pressed(event: InputEvent, key: String, opened: bool) -> void:
	var click := event as InputEventMouseButton
	if click == null or not click.pressed or click.button_index != MOUSE_BUTTON_LEFT:
		return
	accept_event()
	if _opened < GUARD or _leaving:
		return
	if _going != "":
		_arrive()
	elif opened:
		Sfx.play("click")
		_go(key)
	else:
		Sfx.play("refuse")


## Walk the lantern along the trails to a place of this act, then open its intro.
func _go(key: String) -> void:
	if not _anchors.has(key) or _going != "" or _leaving:
		return
	var a := _keys.find(_stand)
	var b := _keys.find(key)
	var step := 1 if b >= a else -1
	_walk.clear()
	var i := a
	while i != b:
		_walk.append_array(_trail(_keys[i], _keys[i + step]).slice(1))
		i += step
	_going = key
	_first = false


func _arrive() -> void:
	var key := _going
	_going = ""
	_walk.clear()
	_stand = key
	_present = true
	_lantern = _anchors[key]
	_place_lantern()
	_leaving = true
	await game.intro(key)
	_leaving = false


## Stop a walk where it began (an overlay opens over the map).
func _halt() -> void:
	_first = false
	if _going != "":
		_going = ""
		_walk.clear()
		_lantern = _anchors[_stand]


func _show_act(n: int) -> void:
	if n == act:
		return
	act = n
	_first = false
	_compose()


func _process(delta: float) -> void:
	super(delta)
	_clock += delta
	if _first and _going == "" and not _leaving and _clock > FIRST_STEP:
		for p in _view["places"]:
			if bool(p["next"]):
				_go(String(p["key"]))
		_first = false
	if _going != "":
		var step := PACE * delta
		while not _walk.is_empty() and step > 0.0:
			var target: Vector2 = _walk[0]
			var d := _lantern.distance_to(target)
			if d <= step:
				_lantern = target
				_walk.pop_front()
				step -= d
			else:
				_lantern += (target - _lantern) * step / d
				step = 0.0
		if _walk.is_empty():
			_arrive()
	_flicker = 0.86 + 0.1 * sin(_clock * 13.0) * sin(_clock * 7.1) + 0.04 * sin(_clock * 23.0)
	_place_lantern()
	_paths.queue_redraw()
	_shine.queue_redraw()


func _place_lantern() -> void:
	if _lamp == null:
		return
	var shown := _present or _first or _going != "" or _leaving
	var ground := _screen(_lantern)
	var flame := ground - Vector2(0, LIFT + sin(_clock * 2.2) * 2.5)
	for c: Control in [_lamp, _lamp_glow, _lamp_core, _lamp_pool]:
		c.visible = shown
	_lamp.position = flame
	_lamp.rotation = (0.1 * sin(_clock * 6.0) if _going != "" else 0.03 * sin(_clock * 1.7))
	_lamp_glow.position = flame - _lamp_glow.size / 2
	_lamp_glow.scale = Vector2.ONE * _flicker
	_lamp_glow.self_modulate.a = _flicker
	_lamp_core.position = flame - _lamp_core.size / 2
	_lamp_core.self_modulate.a = _flicker
	_lamp_pool.position = ground - _lamp_pool.size / 2 + Vector2(0, -4)
	_lamp_pool.self_modulate.a = 0.6 + 0.4 * _flicker
	_lamp.queue_redraw()


# -- Drawing -----------------------------------------------------------------------------------------

## Beads along the trails: gold where the way is open (a light running down it towards the next place),
## dark where it is not yet.
func _draw_trails() -> void:
	for t in _dots:
		var pts: PackedVector2Array = t[0]
		var lit: bool = t[1]
		for i in pts.size():
			if lit:
				var run := pow(0.5 + 0.5 * sin(i * 0.5 - _clock * 4.0), 4.0)
				_paths.draw_circle(pts[i], 4.6, Color(0, 0, 0, 0.65), true, -1.0, true)
				_paths.draw_circle(pts[i], 3.1, Style.GOLD.lerp(Color(1.0, 0.97, 0.85), run), true, -1.0, true)
			else:
				_paths.draw_circle(pts[i], 3.4, Color(0, 0, 0, 0.6), true, -1.0, true)
				_paths.draw_circle(pts[i], 2.2, Color(0.4, 0.33, 0.27, 0.9), true, -1.0, true)


func _draw_shine() -> void:
	var tex := _glow_texture()
	for t in _dots:
		if not bool(t[1]):
			continue
		var pts: PackedVector2Array = t[0]
		for i in pts.size():
			var run := pow(0.5 + 0.5 * sin(i * 0.5 - _clock * 4.0), 4.0)
			var r := 12.0 + 8.0 * run
			_shine.draw_texture_rect(tex, Rect2(pts[i] - Vector2(r, r), Vector2(r, r) * 2), false,
				Color(1.0, 0.6, 0.25, 0.18 + 0.3 * run))


## The lantern, drawn about its flame: a ring to hang it by, an iron cap, four panes of warm glass round the
## flame, an iron foot.
func _draw_lamp() -> void:
	var c := _lamp
	var iron := Color(0.1, 0.08, 0.075)
	var rim := Color(0.8, 0.62, 0.34)
	c.draw_arc(Vector2(0, -24.5), 4.5, PI, TAU, 14, rim, 1.6, true)
	c.draw_line(Vector2(-4.5, -24.5), Vector2(-4.5, -21), rim, 1.4, true)
	c.draw_line(Vector2(4.5, -24.5), Vector2(4.5, -21), rim, 1.4, true)
	var cap := PackedVector2Array([Vector2(-10, -12.5), Vector2(-5, -21), Vector2(5, -21), Vector2(10, -12.5)])
	c.draw_colored_polygon(cap, iron)
	c.draw_polyline(cap + PackedVector2Array([cap[0]]), rim, 1.3, true)
	var heat := Color(1.0, 0.62 + 0.1 * _flicker, 0.26, 0.92)
	c.draw_rect(Rect2(-7.5, -12.5, 15, 21), heat)
	c.draw_rect(Rect2(-5.5, -10.5, 11, 17), Color(1.0, 0.84, 0.5, 0.85))
	var tall := 7.0 * _flicker
	var flame := PackedVector2Array([Vector2(0, -tall), Vector2(2.6, 0.5), Vector2(2.2, 3.4),
		Vector2(0, 4.6), Vector2(-2.2, 3.4), Vector2(-2.6, 0.5)])
	c.draw_colored_polygon(flame, Color(1.0, 0.97, 0.82))
	c.draw_line(Vector2(0, -12.5), Vector2(0, 8.5), Color(iron, 0.85), 1.0, true)
	c.draw_rect(Rect2(-7.5, -12.5, 15, 21), iron, false, 1.8)
	var foot := PackedVector2Array([Vector2(-10, 8.5), Vector2(10, 8.5), Vector2(7, 13.5), Vector2(-7, 13.5)])
	c.draw_colored_polygon(foot, iron)
	c.draw_polyline(foot + PackedVector2Array([foot[0]]), rim, 1.3, true)


# -- Pieces ------------------------------------------------------------------------------------------

func _layer() -> Control:
	var c := Control.new()
	c.set_anchors_preset(Control.PRESET_FULL_RECT)
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(c)
	return c


## A soft round light of `color`, added to what is under it.
func _glow(at_size: Vector2, color: Color) -> TextureRect:
	var g := TextureRect.new()
	g.texture = _glow_texture()
	g.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	g.stretch_mode = TextureRect.STRETCH_SCALE
	g.size = at_size
	g.position = -at_size / 2
	g.modulate = color
	g.material = _added()
	g.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return g


func _glow_texture() -> Texture2D:
	if not _made.has("glow"):
		var g := Gradient.new()
		g.offsets = PackedFloat32Array([0.0, 0.12, 0.35, 0.65, 1.0])
		g.colors = PackedColorArray([Color(1, 1, 1, 1), Color(1, 1, 1, 0.75), Color(1, 1, 1, 0.28),
			Color(1, 1, 1, 0.07), Color(1, 1, 1, 0)])
		var t := GradientTexture2D.new()
		t.gradient = g
		t.fill = GradientTexture2D.FILL_RADIAL
		t.fill_from = Vector2(0.5, 0.5)
		t.fill_to = Vector2(1.0, 0.5)
		t.width = 128
		t.height = 128
		_made["glow"] = t
	return _made["glow"]


static func _added() -> CanvasItemMaterial:
	var m := CanvasItemMaterial.new()
	m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	return m


func _material(kind: String) -> ShaderMaterial:
	if not _made.has(kind):
		var sh := Shader.new()
		sh.code = {"medallion": MEDALLION, "holy": HOLY, "fade": FADE, "blur": BLUR}[kind]
		_made[kind] = sh
	var m := ShaderMaterial.new()
	m.shader = _made[kind]
	return m


static func _map_data() -> Dictionary:
	if _worldmap.is_empty():
		_worldmap = JSON.parse_string(FileAccess.get_file_as_string("res://data/worldmap.json"))
	return _worldmap


## A gradient through `stops` ([offset, colour]...), top to bottom or left to right.
static func _gradient(stops: Array, vertical: bool) -> GradientTexture2D:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array(stops.map(func(s): return s[0]))
	g.colors = PackedColorArray(stops.map(func(s): return s[1]))
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill_to = Vector2(0, 1) if vertical else Vector2(1, 0)
	t.width = 4 if vertical else 256
	t.height = 256 if vertical else 4
	return t


## A dark falling away down the screen (`stops` top to bottom), stretched over the width.
func _shade(stops: Array) -> TextureRect:
	var r := TextureRect.new()
	r.texture = _gradient(stops, true)
	r.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	r.stretch_mode = TextureRect.STRETCH_SCALE
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return r


static func _noise() -> NoiseTexture2D:
	var nt := NoiseTexture2D.new()
	nt.seamless = true
	var fn := FastNoiseLite.new()
	fn.frequency = 0.006
	fn.fractal_octaves = 5
	nt.noise = fn
	return nt


## A thin gilt rule fading out at both ends, a small lozenge at its middle (the HUD's banner rule).
func _rule(width: float) -> Control:
	var holder := Control.new()
	holder.custom_minimum_size = Vector2(0, 14)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var line := TextureRect.new()
	line.texture = _gradient([[0.0, Color(Style.GOLD, 0.0)], [0.5, Color(Style.GOLD, 0.9)], [1.0, Color(Style.GOLD, 0.0)]],
		false)
	line.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	line.stretch_mode = TextureRect.STRETCH_SCALE
	line.anchor_left = 0.5
	line.anchor_right = 0.5
	line.offset_left = -width / 2
	line.offset_right = width / 2
	line.offset_top = 6
	line.offset_bottom = 8
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(line)
	var gem := ColorRect.new()
	gem.color = Style.GOLD
	gem.size = Vector2(8, 8)
	gem.pivot_offset = Vector2(4, 4)
	gem.rotation = PI / 4
	gem.anchor_left = 0.5
	gem.anchor_right = 0.5
	gem.position = Vector2(-4, 3)
	gem.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(gem)
	return holder


## A short upright gilt rule between groups of buttons.
func _divider() -> Control:
	var r := TextureRect.new()
	r.texture = _gradient([[0.0, Color(Style.GOLD, 0.0)], [0.5, Color(Style.GOLD, 0.8)], [1.0, Color(Style.GOLD, 0.0)]],
		true)
	r.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	r.stretch_mode = TextureRect.STRETCH_SCALE
	r.custom_minimum_size = Vector2(2, 40)
	r.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var box := MarginContainer.new()
	box.add_theme_constant_override("margin_left", 8)
	box.add_theme_constant_override("margin_right", 8)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(r)
	return box


func _pin(c: Control, ax: float, ay: float, rect: Rect2) -> void:
	c.anchor_left = ax
	c.anchor_right = ax
	c.anchor_top = ay
	c.anchor_bottom = ay
	c.offset_left = rect.position.x
	c.offset_top = rect.position.y
	c.offset_right = rect.end.x
	c.offset_bottom = rect.end.y
