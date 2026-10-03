class_name SkillsScreen
extends Screen
## The skill tree, over the map or a location's intro: thirteen columns (ten tower kinds, Warding, Sorcery,
## Battle Magic) of up to five skills, each needing the one above it, bought with sigils. The server's `skills`
## view is what it shows; a click on a skill asks to learn it and the reply is the new view. Opened from an
## intro (`location`), the skills that do nothing there are greyed. Unlearn all (U) gives every sigil back; Close (Esc).
##
## The forge builds with this screen's kit too: the stage, the heading, the iron plates, the element sigils, the
## backdrop's gradients and frame.

const TONES := {"arrow": Color(0.86, 0.72, 0.48), "fire": Color(1.0, 0.5, 0.18), "lightning": Color(0.68, 0.7, 1.0),
	"cold": Color(0.5, 0.85, 1.0), "poison": Color(0.66, 0.93, 0.25), "bone": Color(0.9, 0.86, 0.74),
	"nature": Color(0.38, 0.82, 0.42), "warding": Color(1.0, 0.84, 0.48), "sorcery": Color(0.45, 0.55, 1.0),
	"ballista": Color(0.72, 0.74, 0.8), "hook": Color(0.85, 0.55, 0.3), "knife": Color(0.6, 0.75, 0.85),
	"spells": Color(0.75, 0.55, 1.0)}
const NODE := Vector2(140, 150)
const PITCH := 146.0                  # from one column's centre to the next
const TIER_Y := [244.0, 407.0, 570.0, 733.0, 896.0]   # the last row ends above the frame's inner line (1057)
const HEAD_Y := 160.0                 # the columns' sigils
const MARGIN := 26.0                  # a plate's glow reaches this far past it
const PLATE_SHADER := """
shader_type canvas_item;
// A plate of dark hammered iron with cut corners in a bevelled rim of `rim`, lit from within at the top and
// glowing round its edge in `glow` (alpha: strength), breathing by `pulse`; `grey` drains its colour. Drawn in
// pixels (`size`, the glow's margin included) so the rim stays crisp whatever the size.
uniform vec2 size = vec2(230.0, 212.0);
uniform float margin = 26.0;
uniform float chamfer = 12.0;
uniform float trim = 3.0;
uniform vec4 rim : source_color = vec4(0.62, 0.46, 0.24, 1.0);
uniform vec4 face : source_color = vec4(0.075, 0.064, 0.064, 1.0);
uniform vec4 glow : source_color = vec4(1.0, 0.7, 0.3, 0.0);
uniform float inner = 0.0;
uniform float pulse = 0.0;
uniform float grey = 0.0;
uniform float hover = 0.0;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0)), f.x), f.y);
}
float fbm(vec2 p) {
	float v = 0.0;
	float a = 0.5;
	for (int i = 0; i < 4; i++) {
		v += a * vnoise(p);
		p = p * 2.03 + vec2(17.1, 9.2);
		a *= 0.5;
	}
	return v;
}
float inset(vec2 px) {
	vec2 p = px - vec2(margin);
	vec2 s = size - vec2(2.0 * margin);
	float d = min(min(p.x, s.x - p.x), min(p.y, s.y - p.y));
	float k = 0.7071;
	d = min(d, (p.x + p.y - chamfer) * k);
	d = min(d, (s.x - p.x + p.y - chamfer) * k);
	d = min(d, (p.x + s.y - p.y - chamfer) * k);
	d = min(d, (s.x - p.x + s.y - p.y - chamfer) * k);
	return d;
}
void fragment() {
	vec2 px = UV * size;
	float d = inset(px);
	float breathe = 1.0 + pulse * 0.5 * sin(TIME * 2.4);
	float shine = glow.a * breathe + hover * 0.35;
	vec4 halo = vec4(glow.rgb, clamp(shine, 0.0, 1.0) * exp(d / (margin * 0.3)) * smoothstep(-margin, -margin * 0.55, d));
	vec2 p = px - vec2(margin);
	vec2 s = size - vec2(2.0 * margin);
	vec2 e = vec2(1.0, 0.0);
	float h0 = fbm(px * 0.07);
	float dent = clamp(0.5 - 8.0 * dot(vec2(fbm((px + e.xy) * 0.07) - h0, fbm((px + e.yx) * 0.07) - h0), vec2(-0.35, -1.0)), 0.0, 1.0);
	vec3 col = face.rgb * (0.7 + 0.35 * fbm(px * 0.015) + 0.45 * dent);
	col *= 1.18 - 0.4 * (p.y / s.y);
	col += glow.rgb * inner * 0.3 * exp(-p.y / (s.y * 0.42)) * (0.75 + 0.5 * h0) * breathe;
	col *= mix(0.45, 1.0, smoothstep(trim, trim + 7.0, d));   // the shadow inside the rim
	if (d < trim) {
		vec2 inward = normalize(vec2(inset(px + e.xy) - inset(px - e.xy), inset(px + e.yx) - inset(px - e.yx)) + 1e-4);
		float t = d / trim;
		vec2 facing = t < 0.5 ? -inward : inward;
		float lit = 0.7 + 0.55 * dot(facing, normalize(vec2(-0.35, -1.0)));
		col = rim.rgb * lit * (0.8 + 0.4 * fbm(px * 0.15)) * (1.0 + hover * 0.4);
	}
	float l = dot(col, vec3(0.299, 0.587, 0.114));
	col = mix(col, vec3(l) * 0.7, grey);
	halo.rgb = mix(halo.rgb, vec3(dot(halo.rgb, vec3(0.299, 0.587, 0.114))), grey);
	float body = smoothstep(-0.7, 0.7, d);
	COLOR = mix(halo, vec4(col, 1.0), body);
}
"""

static var _plate_shader: Shader

var _stage: Control
var _circle: Control                  # the ritual circle behind the tree, turning
var _busy := false


func build() -> void:
	add_child(_backdrop())
	_lay_out("")


func back() -> void:
	game.close(self)


func _process(delta: float) -> void:
	super(delta)
	_circle.rotation += delta * TAU / 240.0


## A plate of iron for a box of `size`: a ColorRect reaching MARGIN past it on every side for its glow. Its material
## takes rim, glow, inner, pulse, grey and hover.
static func plate(size: Vector2, rim: Color, glow: Color, inner := 0.0, pulse := 0.0, grey := 0.0, chamfer := 12.0) -> ColorRect:
	if _plate_shader == null:
		_plate_shader = Shader.new()
		_plate_shader.code = PLATE_SHADER
	var r := ColorRect.new()
	var m := ShaderMaterial.new()
	m.shader = _plate_shader
	m.set_shader_parameter("size", size + Vector2(2, 2) * MARGIN)
	m.set_shader_parameter("margin", MARGIN)
	m.set_shader_parameter("chamfer", chamfer)
	m.set_shader_parameter("rim", rim)
	m.set_shader_parameter("glow", glow)
	m.set_shader_parameter("inner", inner)
	m.set_shader_parameter("pulse", pulse)
	m.set_shader_parameter("grey", grey)
	r.material = m
	r.position = -Vector2(MARGIN, MARGIN)
	r.size = size + Vector2(2, 2) * MARGIN
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return r


## `c` drained of colour and darkened, as a skill that does nothing here is shown.
static func greyed(c: Color, amount := 1.0) -> Color:
	var l := c.get_luminance()
	return c.lerp(Color(l, l, l, c.a) * Color(0.62, 0.62, 0.62, 1.0), amount)


## `c` drained of colour but not of light: the words of a skill that does nothing here.
static func drained(c: Color) -> Color:
	var l := c.get_luminance()
	return Color(l, l, l, c.a)


# -- Laying out --------------------------------------------------------------------------------------

func _lay_out(flash: String) -> void:
	var first := _stage == null
	if not first:
		remove_child(_stage)
		_stage.queue_free()
	_stage = stage(self)
	var columns: Array = data["columns"]
	var where := {}                        # skill key -> its box on the stage
	var nodes := {}
	for n in data["nodes"]:
		var node: Dictionary = n
		var col := _column_index(String(node["column"]))
		var tier: int = int(node["tier"])
		var centre := Vector2(_column_x(col), float(TIER_Y[tier - 1]) + NODE.y / 2)
		where[String(node["key"])] = Rect2(centre - NODE / 2, NODE)
		nodes[String(node["key"])] = node
	_stage.add_child(_wires(nodes, where))
	_header()
	for i in columns.size():
		_column_head(i, String(columns[i]["key"]), String(columns[i]["name"]), nodes)
	for key in nodes:
		var slot := _node(nodes[key], where[key])
		if first:
			var node: Dictionary = nodes[key]
			slot.modulate.a = 0.0
			var tw := slot.create_tween()
			tw.tween_interval(0.05 + 0.035 * _column_index(String(node["column"])) + 0.06 * int(node["tier"]))
			tw.tween_property(slot, "modulate:a", 1.0, 0.3)
		elif key == flash:
			slot.pivot_offset = NODE / 2
			slot.scale = Vector2(1.08, 1.08)
			slot.modulate = Color(2.2, 1.9, 1.4)
			var tw := slot.create_tween().set_parallel()
			tw.tween_property(slot, "scale", Vector2.ONE, 0.45).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
			tw.tween_property(slot, "modulate", Color.WHITE, 0.7)
	_legend()
	_orders()


func _column_index(key: String) -> int:
	var columns: Array = data["columns"]
	for i in columns.size():
		if String(columns[i]["key"]) == key:
			return i
	push_error("no column %s" % key)
	return 0


func _column_x(i: int) -> float:
	var n: int = (data["columns"] as Array).size()
	return Ui.W / 2 + (i - (n - 1) / 2.0) * PITCH


## The 1920 x 1080 layout a screen is built on, centred on a window of any shape; added to `screen`.
static func stage(screen: Control) -> Control:
	var c := Control.new()
	c.anchor_left = 0.5
	c.anchor_right = 0.5
	c.anchor_top = 0.5
	c.anchor_bottom = 0.5
	c.offset_left = -Ui.W / 2
	c.offset_right = Ui.W / 2
	c.offset_top = -Ui.H / 2
	c.offset_bottom = Ui.H / 2
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	screen.add_child(c)
	return c


## Words in `font` with a soft shadow under them rather than an outline.
static func words(text: String, font: Font, size: int, color: Color) -> Label:
	var l := Ui.label(text, size, color, font)
	l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.85))
	l.add_theme_constant_override("shadow_offset_x", 1)
	l.add_theme_constant_override("shadow_offset_y", 2)
	l.add_theme_constant_override("shadow_outline_size", 1)
	return l


## A page's heading on the stage: its title in banner capitals, a gilt rule, a line under it.
static func heading(on: Control, title: String, line: String) -> void:
	var t := words(title, Style.display_font(), 54, Style.GOLD)
	t.uppercase = true
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	t.add_theme_constant_override("outline_size", 10)
	t.add_theme_color_override("font_outline_color", Color(0.04, 0.02, 0.0, 0.85))
	t.position = Vector2(0, 18)
	t.size = Vector2(Ui.W, 70)
	on.add_child(t)
	var r := rule(560.0, Style.GOLD)
	r.position = Vector2(Ui.W / 2, 86)
	on.add_child(r)
	var l := words(line, Style.text_font(), 24, Style.PALE_GOLD)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.position = Vector2(0, 96)
	l.size = Vector2(Ui.W, 32)
	on.add_child(l)


## The title, the server's heading line and the purse of sigils.
func _header() -> void:
	heading(_stage, "Skills", String(data["heading"]))

	# the purse: the sigils free to spend, in a gilt ring
	var free: int = int(data["free"])
	var purse := Control.new()
	purse.position = Vector2(Ui.W - 220, 62)   # its larger captions clear of the frame on the right
	purse.mouse_filter = Control.MOUSE_FILTER_IGNORE
	purse.draw.connect(func(): _draw_purse(purse, free))
	_stage.add_child(purse)
	var count := words(str(free), Style.title_font(), 40, Style.PALE_GOLD if free > 0 else Style.DIM_GOLD)
	count.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	count.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	count.add_theme_constant_override("outline_size", 8)
	count.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
	count.position = Vector2(-40, -36)
	count.size = Vector2(80, 70)
	purse.add_child(count)
	var caption := words("sigils free", Style.small_font(), 17, Style.DIM_GOLD)
	caption.uppercase = true
	caption.position = Vector2(48, -24)
	purse.add_child(caption)
	var won := words("of %d won" % int(data["sigils"]), Style.small_font(), 17, Style.BONE)
	won.uppercase = true
	won.position = Vector2(48, 0)
	purse.add_child(won)


func _draw_purse(ci: Control, free: int) -> void:
	var r := 38.0
	var lit := free > 0
	for i in 10:   # a halo
		ci.draw_circle(Vector2.ZERO, r + 18 - i * 1.8, Color(1.0, 0.7, 0.3, 0.025 if lit else 0.01))
	ci.draw_circle(Vector2.ZERO, r, Color(0.05, 0.04, 0.04))
	ci.draw_circle(Vector2.ZERO, r - 6, Color(0.16, 0.09, 0.05) if lit else Color(0.07, 0.06, 0.06))
	ci.draw_circle(Vector2.ZERO, r - 14, Color(0.28, 0.14, 0.06, 0.7) if lit else Color(0.08, 0.07, 0.07))
	ci.draw_arc(Vector2.ZERO, r - 1.5, 0, TAU, 64, Style.GOLD if lit else Style.BRONZE, 3.0, true)
	ci.draw_arc(Vector2.ZERO, r - 6, 0, TAU, 64, Color(Style.BRONZE, 0.7), 1.2, true)
	for k in 4:   # four studs on the ring
		var a := k * TAU / 4 + TAU / 8
		ci.draw_circle(Vector2.from_angle(a) * (r - 1.5), 3.2, Style.PALE_GOLD if lit else Style.DIM_GOLD)


## A thin gilt rule centred on its position, fading at both ends, a lozenge at its middle.
static func rule(width: float, color: Color) -> Control:
	var c := Control.new()
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	c.draw.connect(func():
		var steps := 24
		for i in steps:
			var t0 := float(i) / steps
			var t1 := float(i + 1) / steps
			var a := 1.0 - absf((t0 + t1) - 1.0)
			c.draw_line(Vector2(lerpf(-width / 2, width / 2, t0), 0), Vector2(lerpf(-width / 2, width / 2, t1), 0),
				Color(color, a * 0.85), 1.6, true)
		c.draw_colored_polygon(PackedVector2Array([Vector2(0, -5), Vector2(5, 0), Vector2(0, 5), Vector2(-5, 0)]), color))
	return c


## A column's sigil and its name; the sigil is lit while a skill under it is learned.
func _column_head(i: int, key: String, title: String, nodes: Dictionary) -> void:
	var tone: Color = TONES.get(key, Style.GOLD)
	var lit := false
	var dormant := true
	for k in nodes:
		var node: Dictionary = nodes[k]
		if String(node["column"]) == key:
			lit = lit or bool(node["learned"])
			dormant = dormant and bool(node["dormant"])
	if dormant:
		tone = greyed(tone)
	var x := _column_x(i)
	var medal := Control.new()
	medal.position = Vector2(x, HEAD_Y)
	medal.mouse_filter = Control.MOUSE_FILTER_IGNORE
	medal.draw.connect(func(): medallion(medal, key, Vector2.ZERO, 31.0, tone, lit))
	_stage.add_child(medal)
	var l := words(title, Style.small_font(), 19, tone if lit else tone.darkened(0.15))
	l.uppercase = true
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.position = Vector2(x - PITCH / 2, HEAD_Y + 38)
	l.size = Vector2(PITCH, 24)
	_stage.add_child(l)


## An element's sigil in a bronze-ringed medallion: its glyph in `tone`, glowing when `lit`.
static func medallion(ci: CanvasItem, key: String, c: Vector2, r: float, tone: Color, lit: bool) -> void:
	for i in 12:   # the halo
		ci.draw_circle(c, r * 1.7 - i * r * 0.06, Color(tone, (0.03 if lit else 0.012)))
	ci.draw_circle(c, r, Color(0.03, 0.026, 0.03))
	for i in 8:    # the glow inside, deepest at the middle
		ci.draw_circle(c, r * (0.92 - i * 0.1), Color(tone * 0.5, 0.07 if lit else 0.035))
	ci.draw_arc(c, r - 1.5, 0, TAU, 64, Style.BRONZE.lerp(tone, 0.25) if lit else Style.BRONZE.darkened(0.25), 3.0, true)
	ci.draw_arc(c, r - 5.5, 0, TAU, 64, Color(0, 0, 0, 0.8), 1.5, true)
	ci.draw_arc(c, r + 1.5, 0, TAU, 64, Color(0, 0, 0, 0.9), 1.5, true)
	glyph(ci, key, c + Vector2(0, 2), r * 0.62, Color(0, 0, 0, 0.75), Color(0.03, 0.026, 0.03))   # its shadow
	var ink := tone.lightened(0.15) if lit else tone.darkened(0.2)
	glyph(ci, key, c, r * 0.62, ink, Color(0.03, 0.026, 0.03))


## An element's sign drawn in `ink` within radius `r` of `c` (`hole`: the dark cut into it, a skull's eyes).
static func glyph(ci: CanvasItem, key: String, c: Vector2, r: float, ink: Color, hole: Color) -> void:
	var w := maxf(r * 0.13, 1.5)
	var at := func(x: float, y: float) -> Vector2: return c + Vector2(x, y) * r
	var poly := func(pts: Array) -> PackedVector2Array:
		var out := PackedVector2Array()
		for p in pts:
			out.append(c + (p as Vector2) * r)
		return out
	match key:
		"arrow":
			ci.draw_line(at.call(-0.62, 0.62), at.call(0.4, -0.4), ink, w, true)
			ci.draw_colored_polygon(poly.call([Vector2(0.7, -0.7), Vector2(0.18, -0.52), Vector2(0.52, -0.18)]), ink)
			for k in 2:
				var t := -0.62 + k * 0.2
				ci.draw_line(at.call(t, -t), at.call(t - 0.24, -t - 0.06), ink, w * 0.8, true)
				ci.draw_line(at.call(t, -t), at.call(t + 0.06, -t + 0.24), ink, w * 0.8, true)
		"fire":
			var outer := [Vector2(0, 0.85), Vector2(-0.38, 0.7), Vector2(-0.6, 0.35), Vector2(-0.55, -0.05),
				Vector2(-0.32, -0.38), Vector2(-0.3, -0.06), Vector2(-0.1, -0.24), Vector2(-0.06, -0.58), Vector2(0.06, -0.9),
				Vector2(0.24, -0.5), Vector2(0.4, -0.3), Vector2(0.46, -0.56), Vector2(0.6, -0.16), Vector2(0.62, 0.28),
				Vector2(0.4, 0.68)]
			ci.draw_colored_polygon(poly.call(outer), ink)
			var core := []
			for p in outer:
				core.append(Vector2(p.x * 0.45, 0.42 + (p.y - 0.42) * 0.5))
			ci.draw_colored_polygon(poly.call(core), hole.lerp(ink, 0.35))
		"lightning":
			ci.draw_colored_polygon(poly.call([Vector2(0.08, -0.9), Vector2(0.5, -0.9), Vector2(0.14, -0.14),
				Vector2(0.46, -0.14), Vector2(-0.28, 0.92), Vector2(-0.06, 0.1), Vector2(-0.4, 0.1)]), ink)
		"cold":
			for k in 3:
				var d := Vector2.from_angle(PI / 2 + k * PI / 3)
				ci.draw_line(c - d * r * 0.88, c + d * r * 0.88, ink, w, true)
				for s in [-1.0, 1.0]:
					var base: Vector2 = c + d * r * 0.5 * s
					for turn in [-0.8, 0.8]:
						ci.draw_line(base, base + (d * s).rotated(turn) * r * 0.3, ink, w * 0.8, true)
			ci.draw_circle(c, r * 0.14, ink)
		"poison":
			var drop := [Vector2(0, -0.9)]
			for k in 15:
				var a := deg_to_rad(-35.0 + k * 250.0 / 14.0)
				drop.append(Vector2(0, 0.28) + Vector2.from_angle(a) * 0.55)
			ci.draw_colored_polygon(poly.call(drop), ink)
			ci.draw_circle(at.call(-0.14, 0.32), r * 0.13, hole.lerp(ink, 0.3))
			ci.draw_circle(at.call(0.62, -0.42), r * 0.12, ink)
			ci.draw_circle(at.call(0.76, -0.1), r * 0.08, ink)
		"bone":
			ci.draw_circle(at.call(0, -0.16), r * 0.6, ink)
			ci.draw_colored_polygon(poly.call([Vector2(-0.34, 0.2), Vector2(0.34, 0.2), Vector2(0.3, 0.72),
				Vector2(-0.3, 0.72)]), ink)
			for s in [-1.0, 1.0]:
				ci.draw_circle(at.call(0.24 * s, -0.12), r * 0.16, hole)
			ci.draw_colored_polygon(poly.call([Vector2(0, 0.12), Vector2(-0.08, 0.3), Vector2(0.08, 0.3)]), hole)
			for k in 3:
				var x := -0.15 + k * 0.15
				ci.draw_line(at.call(x, 0.46), at.call(x, 0.72), hole, maxf(w * 0.5, 1.0), true)
		"nature":
			var a: Vector2 = at.call(-0.62, 0.62)
			var b: Vector2 = at.call(0.66, -0.66)
			var n := (b - a).normalized().orthogonal()
			var leaf := PackedVector2Array()
			for k in 13:
				var t := k / 12.0
				leaf.append(a.lerp(b, t) + n * sin(PI * t) * r * 0.42)
			for k in range(11, 0, -1):
				var t := k / 12.0
				leaf.append(a.lerp(b, t) - n * sin(PI * t) * r * 0.42)
			ci.draw_colored_polygon(leaf, ink)
			ci.draw_line(a, a.lerp(b, 0.85), hole, maxf(w * 0.55, 1.0), true)
			ci.draw_line(a, at.call(-0.86, 0.86), ink, w * 0.9, true)
		"warding":
			var shield := [Vector2(-0.6, -0.72), Vector2(0, -0.86), Vector2(0.6, -0.72), Vector2(0.6, -0.05)]
			for k in 9:
				var t := k / 8.0
				shield.append(Vector2(0.6 * cos(t * PI / 2), -0.05 + 0.9 * sin(t * PI / 2)))
			for k in range(7, -1, -1):
				var t := k / 8.0
				shield.append(Vector2(-0.6 * cos(t * PI / 2), -0.05 + 0.9 * sin(t * PI / 2)))
			shield.append(Vector2(-0.6, -0.05))
			ci.draw_colored_polygon(poly.call(shield), ink)
			ci.draw_line(at.call(0, -0.6), at.call(0, 0.6), hole, w, true)
			ci.draw_line(at.call(-0.36, -0.22), at.call(0.36, -0.22), hole, w, true)
		"sorcery":
			ci.draw_arc(c, r * 0.86, 0, TAU, 48, ink, w * 0.8, true)
			var star := PackedVector2Array()
			for k in 6:
				star.append(c + Vector2.from_angle(-PI / 2 + (k * 2 % 5) * TAU / 5) * r * 0.86)
			ci.draw_polyline(star, ink, w * 0.8, true)
		_:
			ci.draw_circle(c, r * 0.5, ink)


## The lines from each skill up to the one it needs (lit once that one is learned), and from each column's sigil
## down to its first skill.
func _wires(nodes: Dictionary, where: Dictionary) -> Control:
	var c := Control.new()
	c.set_anchors_preset(Control.PRESET_FULL_RECT)
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	c.draw.connect(func():
		for key in nodes:
			var node: Dictionary = nodes[key]
			var box: Rect2 = where[key]
			var tone: Color = TONES.get(String(node["column"]), Style.GOLD)
			if bool(node["dormant"]):
				tone = greyed(tone)
			var to := Vector2(box.get_center().x, box.position.y + 2)
			var from: Vector2
			var lit: bool
			if node["parent"] == null:
				from = Vector2(to.x, HEAD_Y + 64)
				lit = true
				tone = tone.darkened(0.35)
			else:
				var up: Rect2 = where[String(node["parent"])]
				from = Vector2(up.get_center().x, up.end.y - 2)
				lit = bool(nodes[String(node["parent"])]["learned"])
			_wire(c, from, to, tone, lit))
	return c


func _wire(c: Control, from: Vector2, to: Vector2, tone: Color, lit: bool) -> void:
	var mid := (from + to) / 2
	if lit:
		c.draw_line(from, to, Color(tone, 0.12), 14.0)
		c.draw_line(from, to, Color(tone, 0.25), 7.0)
		c.draw_line(from, to, tone, 3.0)
		c.draw_line(from, to, tone.lightened(0.5), 1.0)
	else:
		c.draw_line(from, to, Color(0, 0, 0, 0.8), 5.0)
		c.draw_line(from, to, Color(0.26, 0.21, 0.17), 2.0)
	var gem := PackedVector2Array([mid + Vector2(0, -7), mid + Vector2(6, 0), mid + Vector2(0, 7), mid + Vector2(-6, 0)])
	c.draw_colored_polygon(gem, Color(0, 0, 0, 0.9))
	var inner := PackedVector2Array([mid + Vector2(0, -5), mid + Vector2(4, 0), mid + Vector2(0, 5), mid + Vector2(-4, 0)])
	c.draw_colored_polygon(inner, tone.lightened(0.2) if lit else Color(0.3, 0.25, 0.2))


## One skill: an iron plate with its name, its blurb and its price in pips; learned ones glow in their column's
## colour, learnable ones breathe in gold, locked ones are dim, dormant ones grey. Its tooltip is the server's tip.
func _node(node: Dictionary, box: Rect2) -> Control:
	var key := String(node["key"])
	var learned: bool = node["learned"]
	var learnable: bool = node["learnable"]
	var dormant: bool = node["dormant"]
	var tone: Color = TONES.get(String(node["column"]), Style.GOLD)
	var rim: Color
	var glow: Color
	var inner := 0.0
	var pulse := 0.0
	var name_color: Color
	var text_color: Color
	if learned:
		rim = Style.GOLD.lerp(tone, 0.3).lightened(0.1)
		glow = Color(tone, 0.4 if dormant else 0.8)
		inner = 1.25
		pulse = 0.25
		name_color = Style.PALE_GOLD
		text_color = Style.BONE
	elif learnable:
		rim = Style.PALE_GOLD
		glow = Color(1.0, 0.8, 0.45, 0.42)
		pulse = 1.0
		name_color = Color(1.0, 0.95, 0.82)
		text_color = Style.BONE
	else:
		rim = Color(0.36, 0.29, 0.22)
		glow = Color(0, 0, 0, 0)
		name_color = Color(0.64, 0.58, 0.5)
		text_color = Color(0.6, 0.57, 0.52)
	if dormant:   # drained of colour, not of light: the grey plate says "nothing here", the words stay readable
		name_color = drained(name_color).darkened(0.12)
		text_color = drained(text_color).darkened(0.1)
	var slot := Control.new()
	slot.position = box.position
	slot.size = box.size
	slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_stage.add_child(slot)
	var p := plate(box.size, rim, glow, inner, pulse, 0.85 if dormant else 0.0)
	slot.add_child(p)
	if learned:   # the iron takes its column's colour, its sign burnt faintly into it
		(p.material as ShaderMaterial).set_shader_parameter("face", Color(0.075, 0.064, 0.064).lerp(tone * 0.3, 0.4))
		var column := String(node["column"])
		var ink := Color(greyed(tone) if dormant else tone, 0.11)
		var mark := Control.new()
		mark.set_anchors_preset(Control.PRESET_FULL_RECT)
		mark.mouse_filter = Control.MOUSE_FILTER_IGNORE
		mark.draw.connect(func(): glyph(mark, column, box.size / 2 + Vector2(0, 12), 54.0, ink, Color(0, 0, 0, 0.12)))
		slot.add_child(mark)

	var font := Style.text_font()
	var width := box.size.x - 18
	var size := 22
	while size > 17 and font.get_string_size(String(node["name"]), HORIZONTAL_ALIGNMENT_LEFT, -1, size).x > width:
		size -= 1
	var title := words(String(node["name"]), font, size, name_color)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	title.position = Vector2(9, 10)
	title.size = Vector2(width, 28)
	slot.add_child(title)

	var blurb_size := 18
	var room := box.size.y - 52 - 30
	while blurb_size > 15 and font.get_multiline_string_size(String(node["blurb"]), HORIZONTAL_ALIGNMENT_CENTER,
			box.size.x - 22, blurb_size).y > room - 8:   # the label's line spacing adds a little to the font's own
		blurb_size -= 1
	var blurb := words(String(node["blurb"]), font, blurb_size, text_color)
	blurb.add_theme_constant_override("shadow_offset_y", 1)
	blurb.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	blurb.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	blurb.position = Vector2(11, 50)
	blurb.size = Vector2(box.size.x - 22, room)
	slot.add_child(blurb)

	var cost: int = int(node["cost"])
	var deco := Control.new()
	deco.set_anchors_preset(Control.PRESET_FULL_RECT)
	deco.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var line_tone := greyed(tone, 0.85) if dormant else tone
	deco.draw.connect(func(): _decorate(deco, box.size, cost, learned, learnable, dormant, line_tone))
	slot.add_child(deco)

	var hit := Button.new()
	hit.flat = true
	hit.focus_mode = Control.FOCUS_NONE
	for state in ["normal", "hover", "pressed", "disabled", "focus", "hover_pressed"]:
		hit.add_theme_stylebox_override(state, StyleBoxEmpty.new())
	hit.set_anchors_preset(Control.PRESET_FULL_RECT)
	hit.tooltip_text = String(node["tip"])
	hit.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND if learnable else Control.CURSOR_ARROW
	var m := p.material as ShaderMaterial
	hit.mouse_entered.connect(func(): m.set_shader_parameter("hover", 1.0 if learnable or learned else 0.4))
	hit.mouse_exited.connect(func(): m.set_shader_parameter("hover", 0.0))
	hit.pressed.connect(func(): _learn(key, learned))
	slot.add_child(hit)
	return slot


## A node's rule under its name and its price: one pip per sigil, gold once paid.
func _decorate(c: Control, size: Vector2, cost: int, learned: bool, learnable: bool, dormant: bool, tone: Color) -> void:
	var y := 44.0
	var span := size.x * 0.32
	for i in 12:
		var t0 := i / 12.0
		var t1 := (i + 1) / 12.0
		var a := 1.0 - absf(t0 + t1 - 1.0)
		c.draw_line(Vector2(size.x / 2 + lerpf(-span, span, t0), y), Vector2(size.x / 2 + lerpf(-span, span, t1), y),
			Color(tone, a * (0.7 if learned else 0.35)), 1.2, true)
	var gap := 17.0
	var py := size.y - 17.0
	for k in cost:
		var at := Vector2(size.x / 2 + (k - (cost - 1) / 2.0) * gap, py)
		var fill: Color
		var edge: Color
		if learned:
			fill = Style.GOLD
			edge = Style.PALE_GOLD
			c.draw_circle(at, 9.0, Color(1.0, 0.7, 0.3, 0.18))
		elif learnable:
			fill = Color(0.22, 0.14, 0.07)
			edge = Style.PALE_GOLD
		else:
			fill = Color(0.07, 0.06, 0.05)
			edge = Color(0.42, 0.34, 0.25)
		if dormant:
			fill = greyed(fill, 0.85)
			edge = greyed(edge, 0.85)
		var s := 6.0
		c.draw_colored_polygon(PackedVector2Array([at + Vector2(0, -s - 1.5), at + Vector2(s + 1.5, 0),
			at + Vector2(0, s + 1.5), at + Vector2(-s - 1.5, 0)]), Color(0, 0, 0, 0.9))
		c.draw_colored_polygon(PackedVector2Array([at + Vector2(0, -s), at + Vector2(s, 0), at + Vector2(0, s),
			at + Vector2(-s, 0)]), edge)
		c.draw_colored_polygon(PackedVector2Array([at + Vector2(0, -s + 2), at + Vector2(s - 2, 0), at + Vector2(0, s - 2),
			at + Vector2(-s + 2, 0)]), fill)


## What the plates mean, under the Arrow column, whose tree ends at its second skill.
func _legend() -> void:
	var at := Vector2(_column_x(0) - NODE.x / 2 + 6, TIER_Y[2] + 22)
	var keys := [["Learned", "learned"], ["Ready to learn", "learnable"], ["Locked", "locked"]]
	if String(data.get("location", "")) != "":
		keys.append(["No effect here", "dormant"])
	for i in keys.size():
		var y := at.y + i * 40
		var kind: String = keys[i][1]
		var swatch := Control.new()
		swatch.position = Vector2(at.x, y)
		swatch.size = Vector2(40, 26)
		swatch.mouse_filter = Control.MOUSE_FILTER_IGNORE
		# a skill that does nothing here is mostly a locked one: the swatch shows it so, drained of colour
		var rim: Color = {"learned": Style.GOLD, "learnable": Style.PALE_GOLD, "locked": Color(0.36, 0.29, 0.22),
			"dormant": Color(0.36, 0.29, 0.22)}[kind]
		var glow: Color = {"learned": Color(1.0, 0.7, 0.3, 0.8), "learnable": Color(1.0, 0.8, 0.45, 0.42),
			"locked": Color(0, 0, 0, 0), "dormant": Color(0, 0, 0, 0)}[kind]
		var p := plate(swatch.size, rim, glow, 1.5 if kind == "learned" else 0.0, 1.0 if kind == "learnable" else 0.0,
			0.85 if kind == "dormant" else 0.0, 6.0)
		if kind == "learned":
			(p.material as ShaderMaterial).set_shader_parameter("face", Color(0.075, 0.064, 0.064).lerp(Color(0.3, 0.2, 0.1), 0.45))
		swatch.add_child(p)
		_stage.add_child(swatch)
		var l := words(String(keys[i][0]), Style.text_font(), 19, Style.BONE if kind != "dormant" else drained(Style.BONE).darkened(0.1))
		l.position = Vector2(at.x + 54, y)
		_stage.add_child(l)


## Unlearn all and Close, under Warding and Sorcery, whose trees end at their second skill.
func _orders() -> void:
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 14)
	var x := (_column_x(10) + _column_x(11)) / 2
	col.position = Vector2(x - 120, TIER_Y[2] + 30)
	col.size = Vector2(240, 0)
	_stage.add_child(col)
	var unlearn := Ui.button("Unlearn all", "U", 240)
	unlearn.disabled = not bool(data["any"])
	unlearn.tooltip_text = "Every sigil back, to spend again." if bool(data["any"]) else "Nothing is learned yet."
	unlearn.pressed.connect(_unlearn)
	col.add_child(unlearn)
	var close := Ui.button("Close", "Esc", 240)
	close.pressed.connect(back)
	col.add_child(close)


# -- The backdrop -------------------------------------------------------------------------------------

## A smoky dark, warmer above the tree, a ritual circle turning slowly behind it, a gilt frame round the screen.
func _backdrop() -> Control:
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var base := ColorRect.new()
	base.color = Color(0.022, 0.016, 0.02)
	base.set_anchors_preset(Control.PRESET_FULL_RECT)
	base.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(base)
	root.add_child(radial(Color(0.2, 0.07, 0.03, 0.75), Color(0.2, 0.07, 0.03, 0.0), Vector2(0.5, 0.42), 0.62))
	var circle := TextureRect.new()
	circle.texture = load("res://assets/fx/rune_circle.png")
	circle.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	circle.stretch_mode = TextureRect.STRETCH_SCALE
	circle.anchor_left = 0.5
	circle.anchor_right = 0.5
	circle.anchor_top = 0.5
	circle.anchor_bottom = 0.5
	var s := 980.0
	circle.offset_left = -s / 2
	circle.offset_right = s / 2
	circle.offset_top = -s / 2 + 60
	circle.offset_bottom = s / 2 + 60
	circle.pivot_offset = Vector2(s, s) / 2
	circle.modulate = Color(0.6, 0.2, 0.12, 0.1)
	circle.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(circle)
	_circle = circle
	root.add_child(radial(Color(0, 0, 0, 0.0), Color(0, 0, 0, 0.88), Vector2(0.5, 0.5), 0.78))
	var frame := Control.new()
	frame.set_anchors_preset(Control.PRESET_FULL_RECT)
	frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	frame.draw.connect(func(): frame_lines(frame, frame.size))
	frame.resized.connect(frame.queue_redraw)
	root.add_child(frame)
	return root


## A radial gradient over the whole screen from `inside` at `centre` to `outside` at `reach` (of the width).
static func radial(inside: Color, outside: Color, centre: Vector2, reach: float) -> TextureRect:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 1.0])
	g.colors = PackedColorArray([inside, outside])
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = centre
	t.fill_to = centre + Vector2(reach, 0)
	t.width = 256
	t.height = 256
	var r := TextureRect.new()
	r.texture = t
	r.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	r.stretch_mode = TextureRect.STRETCH_SCALE
	r.set_anchors_preset(Control.PRESET_FULL_RECT)
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return r


## A double gilt line round the screen with lozenges at its corners.
static func frame_lines(c: CanvasItem, size: Vector2) -> void:
	for inset in [[16.0, 1.6, 0.55], [23.0, 1.0, 0.3]]:
		var d: float = inset[0]
		c.draw_rect(Rect2(Vector2(d, d), size - Vector2(d, d) * 2), Color(Style.BRONZE, float(inset[2])), false, float(inset[1]), true)
	for corner in [Vector2(16, 16), Vector2(size.x - 16, 16), Vector2(16, size.y - 16), Vector2(size.x - 16, size.y - 16)]:
		var at: Vector2 = corner
		c.draw_colored_polygon(PackedVector2Array([at + Vector2(0, -8), at + Vector2(8, 0), at + Vector2(0, 8),
			at + Vector2(-8, 0)]), Style.BRONZE)
		c.draw_colored_polygon(PackedVector2Array([at + Vector2(0, -4), at + Vector2(4, 0), at + Vector2(0, 4),
			at + Vector2(-4, 0)]), Style.PALE_GOLD)


# -- Orders ------------------------------------------------------------------------------------------

func _with_location(args: Dictionary) -> Dictionary:
	var at := String(data.get("location", ""))
	if at != "":
		args["location"] = at
	return args


func _learn(key: String, learned: bool) -> void:
	if _busy or learned:
		return
	_busy = true
	var view = await ask("learn", _with_location({"key": key}))
	_busy = false
	if view != null:
		_show(view, key)
		Sfx.play("upgrade")


func _unlearn() -> void:
	if _busy or not bool(data["any"]):
		return
	_busy = true
	var view = await ask("unlearn_all", _with_location({}))
	_busy = false
	if view != null:
		_show(view, "")
		Sfx.play("sell")


func _show(view: Dictionary, flash: String) -> void:
	var at := String(data.get("location", ""))
	data = view
	data["location"] = at
	_lay_out(flash)
