class_name Ui
extends RefCounted
## The campaign screens' kit, in the HUD's manner (Style): old gold on dark iron, Luminari titles, Baskerville text,
## bevelled plaques for buttons, painted pictures cover-fitted behind. Every screen builds itself in code from these.

const W := 1920.0                    # the screens are laid out on a 1920 x 1080 canvas (the window stretches it)
const H := 1080.0


static func label(text: String, size: int, color: Color, font: Font = null) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", font if font else Style.text_font())
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.add_theme_constant_override("outline_size", 6)
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


## A title in Luminari.
static func title(text: String, size := 64, color := Style.GOLD) -> Label:
	var l := label(text, size, color, Style.title_font())
	l.add_theme_constant_override("outline_size", 12)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	return l


## Tracked capitals for headings and kickers.
static func caps(text: String, size := 18, color := Style.DIM_GOLD) -> Label:
	return label(text.to_upper(), size, color, Style.small_font())


## A paragraph that wraps inside `width`.
static func paragraph(text: String, size: int, color: Color, width: float, align := HORIZONTAL_ALIGNMENT_LEFT) -> Label:
	var l := label(text, size, color)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.custom_minimum_size = Vector2(width, 0)
	l.horizontal_alignment = align
	return l


## A plaque button; `key` is its shortcut, shown after the text ("Descend · Enter") and pressed by that key.
static func button(text: String, key := "", width := 0.0) -> Button:
	var b := Button.new()
	b.text = text + ("  ·  " + key if key != "" else "")
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_font_override("font", Style.small_font())
	b.add_theme_font_size_override("font_size", 20)
	b.add_theme_color_override("font_color", Style.PALE_GOLD)
	b.add_theme_color_override("font_hover_color", Color(1.0, 0.95, 0.8))
	b.add_theme_color_override("font_disabled_color", Color(0.45, 0.4, 0.34))
	b.add_theme_stylebox_override("normal", Style.plaque(Color(0.16, 0.12, 0.1), Style.BRONZE, false, Vector2(22, 10)))
	b.add_theme_stylebox_override("hover", Style.plaque(Color(0.24, 0.17, 0.12), Color(1.0, 0.85, 0.5), false, Vector2(22, 10)))
	b.add_theme_stylebox_override("pressed", Style.plaque(Color(0.12, 0.09, 0.08), Style.PALE_GOLD, true, Vector2(22, 10)))
	b.add_theme_stylebox_override("disabled", Style.plaque(Color(0.08, 0.07, 0.07), Color(0.3, 0.25, 0.2), false, Vector2(22, 10)))
	b.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	if width > 0.0:
		b.custom_minimum_size = Vector2(width, 0)
	if key != "":
		b.set_meta("key", key)
	b.pressed.connect(func(): Sfx.play("click"))
	return b


## A dark iron panel with a bronze rim.
static func panel(edge := Style.BRONZE, fill := Color(0.06, 0.045, 0.045, 0.9)) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = fill
	sb.border_color = edge
	sb.set_border_width_all(2)
	sb.set_corner_radius_all(6)
	sb.shadow_color = Color(0, 0, 0, 0.6)
	sb.shadow_size = 10
	sb.set_content_margin_all(16)
	return sb


static func box(edge := Style.BRONZE, fill := Color(0.06, 0.045, 0.045, 0.9)) -> PanelContainer:
	var p := PanelContainer.new()
	p.add_theme_stylebox_override("panel", panel(edge, fill))
	return p


## A picture filling the screen, cropped to cover it (res:// path); a dark gradient when it is missing.
static func backdrop(path: String, dim := 0.0) -> Control:
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var back := ColorRect.new()
	back.color = Color(0.03, 0.02, 0.025)
	back.set_anchors_preset(Control.PRESET_FULL_RECT)
	back.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(back)
	if ResourceLoader.exists(path):
		var pic := TextureRect.new()
		pic.texture = load(path)
		pic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		pic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		pic.set_anchors_preset(Control.PRESET_FULL_RECT)
		pic.mouse_filter = Control.MOUSE_FILTER_IGNORE
		root.add_child(pic)
	if dim > 0.0:
		var veil := ColorRect.new()
		veil.color = Color(0, 0, 0, dim)
		veil.set_anchors_preset(Control.PRESET_FULL_RECT)
		veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
		root.add_child(veil)
	return root


## Sigil pips: `won` of three lit.
static func pips(won: int, size := 14.0) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", int(size * 0.8))
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for i in 3:
		var p := Panel.new()
		var sb := StyleBoxFlat.new()
		sb.bg_color = Style.GOLD if i < won else Color(0.12, 0.1, 0.08)
		sb.border_color = Style.PALE_GOLD if i < won else Style.BRONZE
		sb.set_border_width_all(2)
		sb.set_corner_radius_all(int(size))
		if i < won:
			sb.shadow_color = Color(1.0, 0.7, 0.3, 0.6)
			sb.shadow_size = 6
		p.add_theme_stylebox_override("panel", sb)
		p.custom_minimum_size = Vector2(size, size)
		p.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.add_child(p)
	return row


## Tooltips in the HUD's manner: Baskerville on dark iron in a bronze rim. Set on a screen's root.
static func theme() -> Theme:
	var t := Theme.new()
	var sb := panel(Style.BRONZE, Color(0.05, 0.04, 0.04, 0.96))
	sb.set_content_margin_all(12)
	t.set_stylebox("panel", "TooltipPanel", sb)
	t.set_font("font", "TooltipLabel", Style.text_font())
	t.set_font_size("font_size", "TooltipLabel", 20)
	t.set_color("font_color", "TooltipLabel", Style.BONE)
	return t


## The key a button answers to ("Enter", "Esc", "K", "1"...) as a Godot keycode.
static func keycode(key: String) -> Key:
	match key:
		"Enter": return KEY_ENTER
		"Esc": return KEY_ESCAPE
		"Space": return KEY_SPACE
	return OS.find_keycode_from_string(key)
