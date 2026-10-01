class_name Style
extends RefCounted
## The 2D game's look carried over: Luminari for the orbs' numbers and names, Baskerville for text, tracked
## capitals for banners (Big Caslon) and small labels (semibold Baskerville) - Luminari's T reads as a G, even
## large ("Gristram") - old gold on dark iron.

const GOLD := Color(0.93, 0.76, 0.42)
const PALE_GOLD := Color(0.98, 0.9, 0.7)
const DIM_GOLD := Color(0.72, 0.6, 0.4)
const BONE := Color(0.86, 0.82, 0.74)
const BLOOD := Color(0.75, 0.08, 0.05)
const IRON := Color(0.07, 0.06, 0.06, 0.92)
const CURSE := Color(0.72, 0.35, 1.0)
const BRONZE := Color(0.62, 0.46, 0.24)

static var _title: Font
static var _text: Font
static var _small: Font
static var _display: Font


static func title_font() -> Font:
	if _title == null:
		var f := SystemFont.new()
		f.font_names = PackedStringArray(["Luminari", "Palatino", "Georgia", "serif"])
		_title = f
	return _title


static func text_font() -> Font:
	if _text == null:
		var f := SystemFont.new()
		f.font_names = PackedStringArray(["Baskerville", "Georgia", "serif"])
		_text = f
	return _text


## Banner titles: Big Caslon, widely letter-spaced, meant for capitals.
static func display_font() -> Font:
	if _display == null:
		var base := SystemFont.new()
		base.font_names = PackedStringArray(["Big Caslon", "Baskerville", "Georgia", "serif"])
		var f := FontVariation.new()
		f.base_font = base
		f.spacing_glyph = 7
		_display = f
	return _display


## Small labels and buttons: semibold Baskerville, letter-spaced, meant for capitals.
static func small_font() -> Font:
	if _small == null:
		var base := SystemFont.new()
		base.font_names = PackedStringArray(["Baskerville", "Georgia", "serif"])
		base.font_weight = 600
		var f := FontVariation.new()
		f.base_font = base
		f.spacing_glyph = 2
		_small = f
	return _small


## A bevelled plaque: a face shading from `face` at the top to dark below, in a rim of `rim` lit from above (or
## from below when `sunk`, a pressed button), outlined in black. Nine-sliced, so it fits any button.
static func plaque(face: Color, rim: Color, sunk := false, margin := Vector2(14, 5)) -> StyleBoxTexture:
	var w := 40
	var h := 32
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	for y in h:
		for x in w:
			var top := y
			var bottom := h - 1 - y
			var left := x
			var right := w - 1 - x
			var d := mini(mini(top, bottom), mini(left, right))
			var c: Color
			if d == 0:
				var corner := (x == 0 or x == w - 1) and (y == 0 or y == h - 1)
				c = Color(0, 0, 0, 0.0 if corner else 0.9)
			elif d <= 2:
				var side := 1.25 if d == top else (0.6 if d == bottom else (1.0 if d == left else 0.78))
				if sunk:
					side = 1.75 - side
				c = rim * side * (1.1 if d == 1 else 0.9)
			else:
				var v := float(y) / h
				c = face * lerpf(1.3, 0.7, v)
				if d == 3 and top == 3 and not sunk:
					c = face.lerp(rim, 0.45) * 1.2       # a lit lip under the rim
				elif d == 3:
					c = c * 0.7
			c.a = 1.0 if d > 0 else c.a
			img.set_pixel(x, y, c)
	var sb := StyleBoxTexture.new()
	sb.texture = ImageTexture.create_from_image(img)
	sb.set_texture_margin_all(4)
	sb.content_margin_left = margin.x
	sb.content_margin_right = margin.x
	sb.content_margin_top = margin.y
	sb.content_margin_bottom = margin.y
	return sb


## A sunken well for a slot or a portrait: near-black inside with a soft inner shadow, a bevelled rim of `rim`.
static func well(rim: Color, inner := Color(0.03, 0.026, 0.03)) -> StyleBoxTexture:
	var s := 48
	var img := Image.create(s, s, false, Image.FORMAT_RGBA8)
	for y in s:
		for x in s:
			var top := y
			var bottom := s - 1 - y
			var left := x
			var right := s - 1 - x
			var d := mini(mini(top, bottom), mini(left, right))
			var c: Color
			if d == 0:
				c = Color(0, 0, 0, 0.95)
			elif d <= 3:
				var side := 1.2 if d == top else (0.55 if d == bottom else (1.0 if d == left else 0.75))
				c = rim * side * (1.15 if d == 1 else (0.95 if d == 2 else 0.6))
				c.a = 1.0
			else:
				var shadow := clampf((d - 3) / 9.0, 0.0, 1.0)
				c = inner * lerpf(0.25, 1.0, shadow)
				c.a = 1.0
			img.set_pixel(x, y, c)
	var sb := StyleBoxTexture.new()
	sb.texture = ImageTexture.create_from_image(img)
	sb.set_texture_margin_all(14)
	sb.set_content_margin_all(5)
	return sb
