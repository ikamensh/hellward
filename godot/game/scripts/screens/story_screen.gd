class_name StoryScreen
extends Screen
## A story's pages: each page's painted panel fills the screen under a slow push, its paragraphs fade in one after
## another over a dark band at the bottom. Enter or a click first shows every paragraph, then turns the page; after
## the last page `data.then`. Esc skips to `data.skip`, else `data.then`. A missing picture is a dark gradient.
## data: {pages: [{key, text: [paragraphs]}], then: Callable, skip: Callable (optional)}.
## The prologue borrows its pieces: `Picture`, `painting()`, `film()`, `fill()`, `gradient()` and `typeset()`.

const DIR := "res://assets/story/"
const FADE := 0.8          # each paragraph fades in over this, one after another
const LEAD := 0.6          # the picture shows alone this long before the words begin
const TURN := 0.7          # one page's picture dissolves into the next's over this
const PUSH := 18.0         # the slow push takes this long...
const ZOOM := 1.07         # ...to come this close
const BAND := 440.0        # the dark band the words sit on
const WIDTH := 1240.0      # the words' measure

static var _film: Shader

var _pages: Array
var _index := -1
var _clock := 0.0
var _revealed := false
var _done := false
var _stage: Control
var _picture: Picture
var _words: VBoxContainer
var _footer: Label
var _veil: ColorRect


func build() -> void:
	_pages = data["pages"]
	add_child(fill(Color(0.024, 0.016, 0.024)))
	_stage = Control.new()
	_stage.set_anchors_preset(Control.PRESET_FULL_RECT)
	_stage.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_stage)
	add_child(film())
	var band := TextureRect.new()
	band.texture = gradient([0.0, 0.3, 1.0], [Color(0, 0, 0, 0), Color(0, 0, 0, 0.8), Color(0, 0, 0, 0.94)])
	band.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	band.stretch_mode = TextureRect.STRETCH_SCALE
	band.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	band.offset_top = -BAND
	band.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(band)
	_footer = Ui.caps("Enter: continue  ·  Esc: skip", 16, Style.DIM_GOLD)
	_footer.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_footer.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	_footer.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_footer.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_footer.offset_top = -30
	_footer.offset_bottom = -30
	add_child(_footer)
	_veil = fill(Color.BLACK)
	add_child(_veil)
	create_tween().tween_property(_veil, "color:a", 0.0, 0.8)
	_turn()


func _process(delta: float) -> void:
	super(delta)
	_clock += delta
	var t := clampf(_clock / PUSH, 0.0, 1.0)
	t = 1.0 - (1.0 - t) * (1.0 - t)
	var side := -1.0 if _index % 2 == 0 else 1.0       # alternate pages drift alternate ways
	_picture.frame(lerpf(1.0, ZOOM, t), Vector2(0.5 - side * (0.08 - 0.16 * t), 0.46 - 0.06 * t))
	var lines := _words.get_children()
	for i in range(1, lines.size()):                     # the first child is the ornament
		var l := lines[i] as Label
		l.modulate.a = 1.0 if _revealed else clampf((_clock - LEAD - (i - 1) * FADE) / FADE, 0.0, 1.0)
	_footer.modulate.a = 0.55 + 0.45 * (0.5 + 0.5 * sin(_clock * 2.4)) if _shown() else 0.5


func _key(event: InputEvent) -> void:
	var k := event as InputEventKey
	if k != null and k.pressed and not k.echo and k.keycode in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
		get_viewport().set_input_as_handled()
		if _opened >= GUARD:
			_advance()
		return
	super(event)


func _gui_input(event: InputEvent) -> void:
	var m := event as InputEventMouseButton
	if m != null and m.pressed and m.button_index == MOUSE_BUTTON_LEFT:
		accept_event()
		if _opened >= GUARD:
			_advance()


func back() -> void:
	var skip: Callable = data.get("skip", data["then"])
	_finish(skip)


## Every paragraph of the page fully shown.
func _shown() -> bool:
	return _revealed or _clock >= LEAD + FADE * (_words.get_child_count() - 1)


func _advance() -> void:
	if _done:
		return
	if not _shown():
		_revealed = true
	elif _index + 1 < _pages.size():
		_turn()
	else:
		var then: Callable = data["then"]
		_finish(then)


func _finish(way: Callable) -> void:
	if _done:
		return
	_done = true
	var tw := create_tween()
	tw.tween_property(_veil, "color:a", 1.0, 0.4)
	tw.tween_callback(way)


## The next page: its picture dissolves in over the last one, its words take the old words' place.
func _turn() -> void:
	_index += 1
	_clock = 0.0
	_revealed = false
	var page: Dictionary = _pages[_index]
	var old := _picture
	_picture = Picture.new(painting(DIR + String(page["key"]) + ".jpg"))
	_picture.inset = 0.01
	_stage.add_child(_picture)
	if old != null:
		_picture.modulate.a = 0.0
		var tw := create_tween()
		tw.tween_property(_picture, "modulate:a", 1.0, TURN)
		tw.tween_callback(old.queue_free)
	if _words != null:
		var gone := _words
		var tw := create_tween()
		tw.tween_property(gone, "modulate:a", 0.0, 0.25)
		tw.tween_callback(gone.queue_free)
	_words = VBoxContainer.new()
	_words.add_theme_constant_override("separation", 16)
	_words.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_words.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	_words.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_words.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_words.offset_top = -86
	_words.offset_bottom = -86
	var rule := Ornament.new()
	rule.pages = _pages.size()
	rule.page = _index
	_words.add_child(rule)
	var text: Array = page["text"]
	for p in text:
		var l := Ui.paragraph(typeset(String(p)), 30, Style.BONE, WIDTH)
		l.add_theme_constant_override("line_spacing", 6)
		l.modulate.a = 0.0
		_words.add_child(l)
	add_child(_words)
	move_child(_words, _veil.get_index())


## A painted picture (res:// path), or null while it is not painted.
static func painting(path: String) -> Texture2D:
	return load(path) if ResourceLoader.exists(path) else null


## The whole screen in one colour, letting clicks through.
static func fill(color: Color) -> ColorRect:
	var r := ColorRect.new()
	r.color = color
	r.set_anchors_preset(Control.PRESET_FULL_RECT)
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return r


## `colors` at `offsets`: top to bottom, or from the middle out when `radial`.
static func gradient(offsets: Array, colors: Array, radial := false) -> GradientTexture2D:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array(offsets)
	g.colors = PackedColorArray(colors)
	var tex := GradientTexture2D.new()
	tex.gradient = g
	if radial:
		tex.fill = GradientTexture2D.FILL_RADIAL
		tex.fill_from = Vector2(0.5, 0.5)
		tex.fill_to = Vector2(1.0, 0.5)
	else:
		tex.fill_from = Vector2(0, 0)
		tex.fill_to = Vector2(0, 1)
	tex.width = 256
	tex.height = 256
	return tex


## Book typography: curly quotes and apostrophes, an ellipsis for three dots.
static func typeset(text: String) -> String:
	var out := ""
	var opening := true
	for ch in text.replace("...", "…"):
		if ch == "\"":
			out += "“" if opening else "”"
			opening = not opening
		elif ch == "'":
			out += "’"
		else:
			out += ch
	return out


## Film over the pictures: corners sinking into the dark and a fine moving grain.
static func film(vignette := 0.6, grain := 0.05) -> ColorRect:
	var r := ColorRect.new()
	r.set_anchors_preset(Control.PRESET_FULL_RECT)
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if _film == null:
		_film = Shader.new()
		_film.code = FILM
	var m := ShaderMaterial.new()
	m.shader = _film
	m.set_shader_parameter("vignette", vignette)
	m.set_shader_parameter("grain", grain)
	r.material = m
	return r


const FILM := """
shader_type canvas_item;
uniform float vignette = 0.6;
uniform float grain = 0.05;

uint pcg(uint v) {
	uint state = v * 747796405u + 2891336453u;
	uint word = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
	return (word >> 22u) ^ word;
}

void fragment() {
	float v = smoothstep(0.32, 0.78, length(UV - 0.5)) * vignette;
	uvec2 cell = uvec2(FRAGCOORD.xy / 1.5);
	uint n = pcg(cell.x + pcg(cell.y + pcg(uint(TIME * 24.0))));
	float g = float(n & 65535u) / 32767.5 - 1.0;
	float ga = abs(g) * grain;
	float a = 1.0 - (1.0 - ga) * (1.0 - v);
	COLOR = vec4(vec3(step(0.0, g)) * ga * (1.0 - v) / max(a, 0.0001), a);
}
"""


## A painted picture cover-fitted into its rect, `inset` of each edge cropped away (the painter's paper borders),
## `zoom` closer than the cover with the crop at `focus` (0..1 of the slack each way). `grade` greys it and sets its
## brightness. A missing picture (null) is a dark gradient.
class Picture extends Control:
	const GRADE := """
shader_type canvas_item;
uniform float grey = 0.0;
uniform float colour = 1.0;
void fragment() {
	float l = dot(COLOR.rgb, vec3(0.299, 0.587, 0.114));
	COLOR.rgb = vec3(l) * grey + COLOR.rgb * colour;
}
"""
	static var _shader: Shader

	var texture: Texture2D
	var inset := 0.0
	var zoom := 1.0
	var focus := Vector2(0.5, 0.5)
	var outline := Color(0, 0, 0, 0)

	func _init(tex: Texture2D) -> void:
		texture = tex
		set_anchors_preset(Control.PRESET_FULL_RECT)
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
		if _shader == null:
			_shader = Shader.new()
			_shader.code = GRADE
		var m := ShaderMaterial.new()
		m.shader = _shader
		material = m

	func frame(z: float, f: Vector2) -> void:
		zoom = z
		focus = f
		queue_redraw()

	## Colour times `colour` plus its grey times `grey`: (0, 1) as painted, (0.22, 0.05) a dark grey ghost of it.
	func grade(grey: float, colour: float) -> void:
		material.set_shader_parameter("grey", grey)
		material.set_shader_parameter("colour", colour)

	## The part of the texture shown.
	func crop() -> Rect2:
		var t := texture.get_size()
		var safe := Rect2(t * inset, t * (1.0 - 2.0 * inset))
		var c := safe.size
		var aspect := size.x / maxf(size.y, 1.0)
		if c.x / c.y > aspect:
			c.x = c.y * aspect
		else:
			c.y = c.x / aspect
		c /= zoom
		return Rect2(safe.position + (safe.size - c) * focus, c)

	## Set the focus so the texture's `pixel` shows at `at` (fractions of this control), as near as the slack allows.
	func focus_on(pixel: Vector2, at: Vector2) -> void:
		focus = Vector2(0.5, 0.5)
		var c := crop()
		var t := texture.get_size()
		var slack := t * (1.0 - 2.0 * inset) - c.size
		var want := pixel - at * c.size - t * inset
		focus = Vector2(clampf(want.x / maxf(slack.x, 1.0), 0.0, 1.0), clampf(want.y / maxf(slack.y, 1.0), 0.0, 1.0))
		queue_redraw()

	## Where a pixel of the texture is on screen, in this control's coordinates.
	func to_local_point(pixel: Vector2) -> Vector2:
		var c := crop()
		return (pixel - c.position) / c.size * size

	func _draw() -> void:
		var r := Rect2(Vector2.ZERO, size)
		if texture == null:
			var top := Color(0.1, 0.055, 0.08)
			var bottom := Color(0.024, 0.016, 0.024)
			draw_polygon(PackedVector2Array([r.position, Vector2(r.end.x, 0), r.end, Vector2(0, r.end.y)]),
				PackedColorArray([top, top, bottom, bottom]))
		else:
			draw_texture_rect_region(texture, r, crop())
		if outline.a > 0.0:
			draw_rect(r, outline, false, 3.0)


## The rule over the words: a gold hairline fading out at both ends, a diamond for each page, the current one lit.
class Ornament extends Control:
	var pages := 1
	var page := 0

	func _init() -> void:
		custom_minimum_size = Vector2(0, 30)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var y := size.y * 0.5
		var mid := size.x * 0.5
		var step := 22.0
		var half := (pages - 1) * step * 0.5 + 20.0
		var gold := Color(Style.GOLD, 0.75)
		for s in [-1.0, 1.0]:
			var side: float = s
			draw_polyline_colors(PackedVector2Array([Vector2(mid + side * half, y), Vector2(mid + side * 440.0, y)]),
				PackedColorArray([gold, Color(Style.GOLD, 0.0)]), 1.5, true)
		for i in pages:
			var c := Vector2(mid - (pages - 1) * step * 0.5 + i * step, y)
			var r := 6.0 if i == page else 4.5
			var face := Style.GOLD if i == page else Color(Style.BRONZE, 0.7)
			draw_colored_polygon(PackedVector2Array([c + Vector2(0, -r), c + Vector2(r, 0), c + Vector2(0, r),
				c + Vector2(-r, 0)]), face)
