class_name PauseScreen
extends Screen
## The pause menu over the defence: the battle stays behind a dark, blurred veil, the ways out on an iron card.
## No key leaves the game (Q is Smite in the fight).
##
## It also holds the overlays' frame, which the settings, the profiles and the reckoning share: the veil, the iron
## card in its gold trim (the HUD's tower card), a heading in tracked capitals and the gilt rule under it.

const VEIL := """
shader_type canvas_item;
// What is behind an overlay, blurred, greyed a little and darkened towards the corners; `fade` brings it in.
uniform sampler2D screen : hint_screen_texture, filter_linear_mipmap;
uniform float dark = 0.55;
uniform float blur = 2.5;
uniform float fade : hint_range(0.0, 1.0) = 1.0;
void fragment() {
	vec3 c = textureLod(screen, SCREEN_UV, blur * fade).rgb;
	c = mix(c, vec3(dot(c, vec3(0.3, 0.59, 0.11))), 0.4 * fade);
	vec2 d = (UV - 0.5) * vec2(1.5, 1.0);
	float corner = smoothstep(0.15, 0.95, length(d));
	c *= mix(1.0, (1.0 - dark) * (1.0 - 0.65 * corner), fade);
	COLOR = vec4(c * vec3(1.0, 0.96, 0.94), 1.0);
}
"""

static var _veil_shader: Shader

var _buttons: Array = []


func build() -> void:
	add_child(PauseScreen.veil(0.3))
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 12)
	col.add_child(PauseScreen.heading("Paused"))
	col.add_child(PauseScreen.rule(300))
	col.add_child(PauseScreen.gap(6))
	var resume := PauseScreen.primary(Ui.button("Resume", "Esc", 420))
	resume.pressed.connect(func(): game.resume(self))
	_add(col, resume)
	var settings := Ui.button("Settings", "S", 420)
	settings.pressed.connect(game.settings)
	_add(col, settings)
	col.add_child(PauseScreen.gap(4))
	for way in [["Start this defence again", "R", game.restart], ["To the map", "M", game.to_map],
			["Back to the title", "T", game.to_title], ["Leave the game", "", game.leave]]:
		var b := Ui.button(String(way[0]), String(way[1]), 420)
		var go: Callable = way[2]
		b.pressed.connect(func(): _leave(go))
		_add(col, b)
	add_child(PauseScreen.centred(PauseScreen.card(col, 520)))


func _key(event: InputEvent) -> void:
	super(event)
	get_viewport().set_input_as_handled()   # an overlay takes every key: none reaches the battle under it


func _add(col: VBoxContainer, b: Button) -> void:
	b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(b)
	_buttons.append(b)


## A way out abandons the defence: once chosen, the menu takes no second choice while the server answers.
func _leave(go: Callable) -> void:
	for b in _buttons:
		(b as Button).disabled = true
	go.call()


# -- The overlays' frame -----------------------------------------------------------------------------

## The battle (or the screen) behind, blurred and darkened by `dark`; it fades in as the overlay opens.
static func veil(dark: float) -> ColorRect:
	if _veil_shader == null:
		_veil_shader = Shader.new()
		_veil_shader.code = VEIL
	var v := ColorRect.new()
	v.set_anchors_preset(Control.PRESET_FULL_RECT)
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var m := ShaderMaterial.new()
	m.shader = _veil_shader
	m.set_shader_parameter("dark", dark)
	m.set_shader_parameter("fade", 0.0)
	v.material = m
	v.ready.connect(func(): v.create_tween().tween_property(m, "shader_parameter/fade", 1.0, 0.3))
	return v


## Hammered iron in a bevelled gold trim (shaders/hud_panel, as the HUD's tower card), holding `content`.
static func card(content: Control, width: float) -> PanelContainer:
	var c := PanelContainer.new()
	var shade := StyleBoxFlat.new()            # no face: only the shadow round the iron
	shade.bg_color = Color(0, 0, 0, 0)
	shade.shadow_color = Color(0, 0, 0, 0.75)
	shade.shadow_size = 36
	c.add_theme_stylebox_override("panel", shade)
	c.custom_minimum_size = Vector2(width, 0)
	c.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	var iron := ColorRect.new()
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/hud_panel.gdshader")
	m.set_shader_parameter("chamfer", 20.0)
	m.set_shader_parameter("trim", 5.0)
	m.set_shader_parameter("spacing", 72.0)
	m.set_shader_parameter("rivet_from", 36.0)
	iron.material = m
	iron.mouse_filter = Control.MOUSE_FILTER_IGNORE
	iron.resized.connect(func(): m.set_shader_parameter("size", iron.size))
	c.add_child(iron)
	var margin := MarginContainer.new()
	for side in ["left", "right"]:
		margin.add_theme_constant_override("margin_" + side, 44)
	margin.add_theme_constant_override("margin_top", 40)
	margin.add_theme_constant_override("margin_bottom", 40)
	margin.add_child(content)
	c.add_child(margin)
	return c


## `c` centred in the window, whatever its size.
static func centred(c: Control) -> CenterContainer:
	var holder := CenterContainer.new()
	holder.set_anchors_preset(Control.PRESET_FULL_RECT)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(c)
	return holder


## An overlay's heading: tracked capitals in Big Caslon, as the HUD's banners.
static func heading(text: String, size := 46, color := Style.GOLD) -> Label:
	var l := Ui.label(text.to_upper(), size, color, Style.display_font())
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.add_theme_constant_override("outline_size", 10)
	l.add_theme_color_override("font_outline_color", Color(0.04, 0.02, 0.0, 0.9))
	return l


## A thin gilt rule fading out at both ends, a small lozenge at its middle (the HUD banner's).
static func rule(width: float, tone := Style.GOLD) -> Control:
	var holder := Control.new()
	holder.custom_minimum_size = Vector2(0, 16)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.modulate = Color(tone, 0.9)
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.5, 1.0])
	g.colors = PackedColorArray([Color(1, 1, 1, 0), Color(1, 1, 1, 1), Color(1, 1, 1, 0)])
	var tex := GradientTexture2D.new()
	tex.gradient = g
	tex.width = 256
	tex.height = 4
	var line := TextureRect.new()
	line.texture = tex
	line.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	line.stretch_mode = TextureRect.STRETCH_SCALE
	line.anchor_left = 0.5
	line.anchor_right = 0.5
	line.offset_left = -width / 2
	line.offset_right = width / 2
	line.offset_top = 7
	line.offset_bottom = 9
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(line)
	var gem := ColorRect.new()
	gem.size = Vector2(9, 9)
	gem.pivot_offset = Vector2(4.5, 4.5)
	gem.rotation = PI / 4
	gem.anchor_left = 0.5
	gem.anchor_right = 0.5
	gem.position = Vector2(-4.5, 3.5)
	gem.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(gem)
	return holder


## Empty height between rows of a column.
static func gap(height: float) -> Control:
	var c := Control.new()
	c.custom_minimum_size = Vector2(0, height)
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return c


## The way most taken (Resume, Descend, Again): a warmer face in a gold rim.
static func primary(b: Button) -> Button:
	b.add_theme_stylebox_override("normal", Style.plaque(Color(0.24, 0.15, 0.08), Style.GOLD, false, Vector2(22, 10)))
	b.add_theme_stylebox_override("hover", Style.plaque(Color(0.34, 0.21, 0.1), Color(1.0, 0.9, 0.6), false, Vector2(22, 10)))
	b.add_theme_color_override("font_color", Color(1.0, 0.93, 0.74))
	return b
