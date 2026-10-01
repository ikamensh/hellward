class_name Style
extends RefCounted
## The 2D game's look carried over: Luminari for titles, Baskerville for text, old gold on dark iron.

const GOLD := Color(0.93, 0.76, 0.42)
const PALE_GOLD := Color(0.98, 0.9, 0.7)
const BONE := Color(0.86, 0.82, 0.74)
const BLOOD := Color(0.75, 0.08, 0.05)
const IRON := Color(0.07, 0.06, 0.06, 0.92)
const CURSE := Color(0.72, 0.35, 1.0)

static var _title: Font
static var _text: Font


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
