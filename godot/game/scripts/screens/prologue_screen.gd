class_name PrologueScreen
extends Screen
## The prologue, the intro comic (../hellward/docs/intro.md) played from assets/story/prologue/timeline.json: painted
## panels under slow pushes and pans, four towers waking side by side, the bones' visions flickering faster and
## faster, the lamp going out and catching again under the title. The Bone Priest's recorded lines sound at their
## times under parchment captions, the score ducking beneath them and dying with the lamp; the game's own cues mark
## the shots. Enter or a click ends it, and so does its end, into `data.then`; Esc into `data.skip`, else `data.then`.
## data: {then: Callable, skip: Callable (optional)}.

const DIR := "res://assets/story/prologue/"
const STRIP := ["fire", "thunder", "frost", "dead"]   # upright panels side by side, each lit on its word
const VISIONS := ["bones-v0", "bones-v1", "bones-v2"]
const GUTTER := 18.0
const OPEN := 1.5          # the first panel comes up from black
const SINK := 1.2          # the ember's panel sinks into the dark
const CLOSE := 0.8         # the title goes to black at the very end
const HOLD := 1.2          # the title stays this long past the timeline (the score rings on)
const TITLE := Vector2(0.62, 0.42)   # where HELLWARD sits, in the dark right of the relit lamp
const INSET := 0.04        # of each edge cropped away: the painter's paper borders
const FLAME := Vector2(548, 515)   # the flame in lamp.jpg, in its pixels...
const LAMP_AT := Vector2(0.21, 0.6)  # ...and where it burns on the title, a fraction of the screen each way
const CAPTION_WIDTH := 1180.0
const MUSIC_DB := -8.0
const DUCK_DB := -7.0      # the music under a spoken line
const VOICE_DB := 2.0
const CUE_DB := -7.0

# Shots that dissolve out of the one before instead of cutting: seconds.
const DISSOLVE := {"lamp": 0.4, "wake": 0.6, "priest": 0.7, "bones": 0.5, "curse": 0.4, "ember": 0.6}
# Each panel's camera: [zoom from, zoom to, focus from, focus to] (focus 0..1 of the slack each way).
const MOVES := {
	"glass": [1.25, 1.1, Vector2(0.5, 0.95), Vector2(0.5, 0.05)],      # from the pit up the window to the lamp
	"lamp": [1.1, 1.16, Vector2(0.15, 0.5), Vector2(0.4, 0.5)],
	"breach": [1.0, 1.16, Vector2(0.5, 0.45), Vector2(0.5, 0.6)],     # the horde comes at you
	"wake": [1.14, 1.06, Vector2(0.65, 0.5), Vector2(0.35, 0.5)],
	"priest": [1.04, 1.15, Vector2(0.5, 0.42), Vector2(0.5, 0.36)],   # closing on him
	"bones": [1.06, 1.12, Vector2(0.5, 0.5), Vector2(0.5, 0.45)],
	"curse": [1.08, 1.13, Vector2(0.65, 0.5), Vector2(0.35, 0.5)],
	"ember": [1.06, 1.18, Vector2(0.45, 0.5), Vector2(0.25, 0.6)],    # in on the dying flame
}
# The game's cues on the shots, as the comic's soundtrack lays them (tools/intro.py): [cue, seconds in, dB].
const CUES := {"glass": [["wave", 0.3, CUE_DB]], "fire": [["fireball", 0.1, CUE_DB]],
	"thunder": [["lightning", 0.05, CUE_DB]], "frost": [["frost", 0.05, CUE_DB]], "dead": [["venom_cast", 0.0, -10.0]],
	"priest": [["ponder", 0.2, CUE_DB]], "bones": [["chant", 1.5, CUE_DB]],
	"curse": [["curse", 0.2, CUE_DB], ["door_hit", 1.2, CUE_DB], ["door_hit", 2.1, CUE_DB]],
	"ember": [["leak", 1.2, CUE_DB]], "title": [["hymn", 0.9, -4.0], ["cleared", 1.9, -6.0], ["wave", 2.0, -10.0]]}

var _shots: Array
var _words: Array
var _ends: Array           # when each caption leaves
var _end := 0.0
var _clock := 0.0
var _done := false
var _shown := -1           # the shot on stage
var _prev: Control         # the shot dissolving away under it
var _stage: Control
var _nodes := {}           # shot key -> what shows it (the strip's four share one)
var _strip: Control
var _panels: Array = []
var _bones: StoryScreen.Picture
var _relit: StoryScreen.Picture
var _flame: TextureRect
var _flash: ColorRect
var _title: Control
var _name: Label
var _name_font: FontVariation
var _dare: Label
var _glow: TextureRect
var _caption: PanelContainer
var _caption_text: Label
var _hint: Label
var _veil: ColorRect
var _music: AudioStreamPlayer
var _players: Array = []   # voices and cues sounding
var _fired := {}           # voices and cues already started
var _duck := 0.0
var _textures := {}        # picture key -> its texture, or null when it is not painted


func build() -> void:
	var timeline: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(DIR + "timeline.json"))
	_shots = timeline["shots"]
	_words = timeline["words"]
	for s in _shots:
		_end = maxf(_end, float(s["start"]) + float(s["length"]))
	_end += HOLD
	for i in _words.size():
		var w: Dictionary = _words[i]
		var next := float(_words[i + 1]["at"]) if i + 1 < _words.size() else _end
		_ends.append(minf(float(w["at"]) + float(w["length"]) + 0.4, next))
	add_child(StoryScreen.fill(Color(0.047, 0.039, 0.039)))
	_stage = Control.new()
	_stage.set_anchors_preset(Control.PRESET_FULL_RECT)
	_stage.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_stage)
	for s in _shots:
		var key := String(s["key"])
		if key in STRIP:
			if _strip == null:
				_build_strip()
			_nodes[key] = _strip
		elif key == "title":
			_build_relit()
			_nodes[key] = _relit
		else:
			var pic := _picture(key)
			_stage.add_child(pic)
			_nodes[key] = pic
			if key == "bones":
				_bones = pic
	_flash = StoryScreen.fill(Color(Style.CURSE, 0.0))
	_flash.material = _additive()
	add_child(_flash)
	add_child(StoryScreen.film(0.62, 0.055))
	_build_title()
	_build_caption()
	_hint = Ui.caps("Esc: skip", 15, Style.DIM_GOLD)
	_hint.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	_hint.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_hint.offset_left = -40
	_hint.offset_right = -40
	_hint.offset_top = 32
	_hint.modulate.a = 0.0
	add_child(_hint)
	_veil = StoryScreen.fill(Color.BLACK)
	add_child(_veil)
	Sfx.stop_music(0.5)
	_music = AudioStreamPlayer.new()
	_music.stream = load(DIR + "music.wav")
	_music.bus = "Music"
	_music.volume_db = MUSIC_DB
	add_child(_music)
	_music.play()
	_process(0.0)


func _process(delta: float) -> void:
	super(delta)
	if _done:
		return
	_clock += delta
	if _clock >= _end:
		_finish(data["then"])
		return
	var i := _shot_at(_clock)
	var shot: Dictionary = _shots[i]
	var key := String(shot["key"])
	var local := _clock - float(shot["start"])
	var length := float(shot["length"]) if i + 1 < _shots.size() else _end - float(shot["start"])
	var node: Control = _nodes[key]
	if i != _shown:
		var was: Control = _nodes[String(_shots[_shown]["key"])] if _shown >= 0 else null
		_prev = was if was != node else null
		_shown = i
		_stage.move_child(node, -1)
	var fade: float = DISSOLVE.get(key, 0.0)
	var mix := 1.0 if fade <= 0.0 else smoothstep(0.0, 1.0, local / fade)
	for n in _stage.get_children():
		(n as Control).visible = n == node or (n == _prev and mix < 1.0)
	node.modulate.a = mix
	_flash.color.a = 0.0
	if key in STRIP:
		_light_strip()
	elif key == "title":
		_kindle(local, length)
	else:
		if key == "bones":
			_flicker(local, length)
		_move(node as StoryScreen.Picture, key, local / length)
	_title.visible = key == "title"
	var veil := 0.0
	if i == 0:
		veil = 1.0 - clampf(_clock / OPEN, 0.0, 1.0)
	elif key == "ember":
		veil = 1.0 - clampf((length - local) / SINK, 0.0, 1.0)
	elif key == "title":
		veil = 1.0 - clampf((length - local) / CLOSE, 0.0, 1.0)
	_veil.color.a = veil
	_hint.modulate.a = clampf(_clock - 1.0, 0.0, 1.0) * clampf(6.0 - _clock, 0.0, 1.0) * 0.8
	_show_caption(key)
	_sound(delta)


func _key(event: InputEvent) -> void:
	var k := event as InputEventKey
	if k != null and k.pressed and not k.echo and k.keycode in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
		get_viewport().set_input_as_handled()
		if _opened >= GUARD:
			_finish(data["then"])
		return
	super(event)


func _gui_input(event: InputEvent) -> void:
	var m := event as InputEventMouseButton
	if m != null and m.pressed and m.button_index == MOUSE_BUTTON_LEFT:
		accept_event()
		if _opened >= GUARD:
			_finish(data["then"])


func back() -> void:
	var skip: Callable = data.get("skip", data["then"])
	_finish(skip)


## The voices and cues stop; the score fades out on its own while `way` shows the next screen.
func _finish(way: Callable) -> void:
	if _done:
		return
	_done = true
	for p in _players:
		if is_instance_valid(p):
			p.stop()
			p.queue_free()
	_players.clear()
	var music := _music
	music.reparent(get_tree().root)
	var tw := music.create_tween()
	tw.tween_property(music, "volume_db", -60.0, 1.0)
	tw.tween_callback(music.queue_free)
	way.call()


func _shot_at(t: float) -> int:
	var at := 0
	for i in _shots.size():
		if float(_shots[i]["start"]) <= t:
			at = i
	return at


func _start(key: String) -> float:
	for s in _shots:
		if String(s["key"]) == key:
			return float(s["start"])
	return 0.0


# -- Pictures ---------------------------------------------------------------------------------------

func _picture(key: String) -> StoryScreen.Picture:
	var pic := StoryScreen.Picture.new(_texture(key))
	pic.inset = INSET
	return pic


## A panel's slow push or pan at `p` (0..1) through its shot, eased at both ends.
func _move(pic: StoryScreen.Picture, key: String, p: float) -> void:
	var m: Array = MOVES.get(key, [1.06, 1.12, Vector2(0.65, 0.5), Vector2(0.35, 0.5)])
	p = clampf(p * 1.3, 0.0, 1.0) if key == "glass" else clampf(p, 0.0, 1.0)
	var e := lerpf(p, smoothstep(0.0, 1.0, p), 0.6)
	var f0: Vector2 = m[2]
	var f1: Vector2 = m[3]
	pic.frame(lerpf(float(m[0]), float(m[1]), e), f0.lerp(f1, e))


func _build_strip() -> void:
	_strip = Control.new()
	_strip.set_anchors_preset(Control.PRESET_FULL_RECT)
	_strip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_stage.add_child(_strip)
	for key in STRIP:
		var pic := _picture(String(key))
		pic.set_anchors_preset(Control.PRESET_TOP_LEFT)
		pic.outline = Color(0.02, 0.012, 0.01)
		_strip.add_child(pic)
		_panels.append(pic)


## The four towers side by side: each a dark grey ghost until its word, then lit in a flare, the camera easing in.
func _light_strip() -> void:
	var w := (_strip.size.x - GUTTER * (STRIP.size() + 1)) / STRIP.size()
	var h := _strip.size.y - 2.0 * GUTTER
	for i in STRIP.size():
		var pic: StoryScreen.Picture = _panels[i]
		pic.position = Vector2(GUTTER + i * (w + GUTTER), GUTTER)
		pic.size = Vector2(w, h)
		var t := _clock - _start(String(STRIP[i]))
		var lit := clampf(t / 0.3, 0.0, 1.0)
		var flare := 1.0 + 0.5 * exp(-pow((t - 0.25) / 0.1, 2.0))
		pic.grade(lerpf(0.22, 0.0, lit) * flare, lerpf(0.05, 1.0, lit) * flare)
		var e := smoothstep(0.0, 1.0, clampf(t / 5.0, 0.0, 1.0))
		pic.frame(1.0 + 0.06 * e, Vector2(0.5, 0.5 - 0.1 * e))


## The bones, then the futures he tries, each held for less time than the one before, then the bones again in a
## violet flash.
func _flicker(local: float, length: float) -> void:
	var land := length * 0.86
	var key := "bones"
	var cut := local                   # time since the last cut
	if local >= 1.2 and local < land:
		var at := 1.2
		var hold := 0.7
		var n := 0
		while at + hold <= local:
			at += hold
			hold = maxf(0.07, hold * 0.75)
			n += 1
		key = String(VISIONS[n % VISIONS.size()])
		cut = local - at
	elif local >= land:
		cut = local - land
	_bones.texture = _texture(key)
	_bones.grade(0.0, 1.0 + 0.3 * exp(-cut / 0.08) if local >= 1.2 else 1.0)
	_flash.color.a = 0.4 * exp(-(local - land) / 0.3) if local >= land else 0.0


func _texture(key: String) -> Texture2D:
	if not _textures.has(key):
		_textures[key] = StoryScreen.painting(DIR + key + ".jpg")
	return _textures[key]


# -- The title ---------------------------------------------------------------------------------------

## The lamp again, black at first; it catches and flickers, and its warm light pools round the flame.
func _build_relit() -> void:
	_relit = _picture("lamp")
	_stage.add_child(_relit)
	var pool := TextureRect.new()             # the dark beyond the lamp's light
	pool.texture = StoryScreen.gradient([0.0, 0.1, 0.42, 1.0], [Color(0, 0, 0, 0), Color(0, 0, 0, 0.05),
		Color(0, 0, 0, 0.86), Color(0, 0, 0, 0.94)], true)
	pool.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	pool.size = Vector2(4400, 4400)
	pool.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_relit.add_child(pool)
	_flame = TextureRect.new()
	_flame.texture = _radial(Color(1.0, 0.32, 0.12))
	_flame.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_flame.size = Vector2(620, 620)
	_flame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_flame.material = _additive()
	_relit.add_child(_flame)


func _build_title() -> void:
	_title = Control.new()
	_title.set_anchors_preset(Control.PRESET_FULL_RECT)
	_title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_title)
	_glow = TextureRect.new()
	_glow.texture = _radial(Color(1.0, 0.45, 0.15))
	_glow.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_glow.stretch_mode = TextureRect.STRETCH_SCALE
	_glow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_place(_glow, TITLE, Vector2(1500, 420))
	_glow.material = _additive()
	_title.add_child(_glow)
	_name = Ui.title("HELLWARD", 150, Color8(236, 186, 100))
	_name_font = FontVariation.new()
	_name_font.base_font = Style.title_font()
	_name.add_theme_font_override("font", _name_font)
	_name.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.9))
	_name.add_theme_constant_override("shadow_offset_x", 5)
	_name.add_theme_constant_override("shadow_offset_y", 5)
	_name.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_place(_name, TITLE, Vector2(1400, 220))
	_title.add_child(_name)
	_dare = Ui.label("Keep it burning.", 52, Color8(222, 212, 190))
	_dare.add_theme_constant_override("outline_size", 8)
	_dare.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_dare.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_place(_dare, TITLE + Vector2(0, 118.0 / Ui.H), Vector2(1000, 90))
	_title.add_child(_dare)


## `c` centred on `at` (fractions of the screen), `extent` big.
func _place(c: Control, at: Vector2, extent: Vector2) -> void:
	c.anchor_left = at.x
	c.anchor_right = at.x
	c.anchor_top = at.y
	c.anchor_bottom = at.y
	c.offset_left = -extent.x * 0.5
	c.offset_right = extent.x * 0.5
	c.offset_top = -extent.y * 0.5
	c.offset_bottom = extent.y * 0.5


## The title shot at `local` seconds: black; the lamp catches, flickering; HELLWARD; the dare.
func _kindle(local: float, length: float) -> void:
	var kindle := clampf((local - 0.9) / 1.2, 0.0, 1.0)
	var flicker := 1.0 + 0.14 * kindle * sin(23.0 * local) * sin(7.0 * local + 1.0)
	_relit.grade(0.0, 0.75 * kindle * flicker)
	var e := smoothstep(0.0, 1.0, clampf(local / length, 0.0, 1.0))
	_relit.zoom = lerpf(1.22, 1.28, e)
	_relit.focus_on(FLAME, LAMP_AT - Vector2(0.0, 0.02 * e))
	var flame := _relit.to_local_point(FLAME)
	for c in _relit.get_children():
		var r := c as Control
		r.position = flame - r.size * 0.5
	_flame.modulate = Color(1, 1, 1, 0.55 * kindle * flicker)
	var word := smoothstep(0.0, 1.0, clampf((local - 2.0) / 1.0, 0.0, 1.0))
	var dare := smoothstep(0.0, 1.0, clampf((local - 3.0) / 0.8, 0.0, 1.0))
	_name.modulate.a = word
	_name_font.spacing_glyph = int(lerpf(2.0, 14.0, clampf((local - 2.0) / (length - 2.0), 0.0, 1.0)))
	_glow.modulate = Color(1, 1, 1, 0.35 * word * flicker)
	_dare.modulate.a = dare


## A soft round light of `color`, bright in the middle and gone at the rim.
static func _radial(color: Color) -> GradientTexture2D:
	return StoryScreen.gradient([0.0, 0.35, 1.0], [color, Color(color, 0.35), Color(color, 0.0)], true)


static func _additive() -> CanvasItemMaterial:
	var m := CanvasItemMaterial.new()
	m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	return m


# -- Captions -----------------------------------------------------------------------------------------

## The comic's caption: dark ink on a parchment box with an ink rim, low in the frame.
func _build_caption() -> void:
	_caption = PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color8(222, 206, 170, 240)
	sb.border_color = Color8(60, 30, 20)
	sb.set_border_width_all(3)
	sb.set_corner_radius_all(2)
	sb.shadow_color = Color(0, 0, 0, 0.6)
	sb.shadow_size = 14
	sb.shadow_offset = Vector2(0, 5)
	sb.content_margin_left = 36
	sb.content_margin_right = 36
	sb.content_margin_top = 14
	sb.content_margin_bottom = 16
	_caption.add_theme_stylebox_override("panel", sb)
	_caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_caption.anchor_left = 0.5
	_caption.anchor_right = 0.5
	_caption.anchor_top = 1.0
	_caption.anchor_bottom = 1.0
	_caption.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_caption.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_caption_text = Ui.label("", 42, Color8(40, 18, 12))
	_caption_text.add_theme_constant_override("outline_size", 0)
	_caption_text.add_theme_constant_override("line_spacing", 2)
	_caption_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_caption.add_child(_caption_text)
	_caption.modulate.a = 0.0
	add_child(_caption)


func _show_caption(key: String) -> void:
	var text := ""
	var alpha := 0.0
	if key != "title":
		for i in _words.size():
			var at := float(_words[i]["at"])
			var end: float = _ends[i]
			if at <= _clock and _clock < end:
				text = StoryScreen.typeset(String(_words[i]["text"]))
				alpha = minf(1.0, minf((_clock - at) / 0.3, (end - _clock) / 0.3))
	_caption.modulate.a = alpha
	if text == "" or text == _caption_text.text:
		return
	_caption_text.text = text
	# a long line wraps into lines of even length rather than a full one and a stub
	var font := _caption_text.get_theme_font("font")
	var wide := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 42).x
	if wide > CAPTION_WIDTH:
		var lines := ceilf(wide / CAPTION_WIDTH)
		_caption_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_caption_text.custom_minimum_size = Vector2(wide / lines + 60.0, 0)
	else:
		_caption_text.autowrap_mode = TextServer.AUTOWRAP_OFF
		_caption_text.custom_minimum_size = Vector2.ZERO
	var x := 0.5
	if key in STRIP:                     # under its own panel
		var pic: StoryScreen.Picture = _panels[STRIP.find(key)]
		x = (pic.position.x + pic.size.x * 0.5) / size.x
	_caption.anchor_left = x
	_caption.anchor_right = x
	_caption.offset_left = 0
	_caption.offset_right = 0
	_caption.offset_top = -78
	_caption.offset_bottom = -78
	_caption.reset_size()


# -- Sound --------------------------------------------------------------------------------------------

## The lines and the cues at their times; the score ducks under a line and dies with the lamp.
func _sound(delta: float) -> void:
	for i in _words.size():
		var w: Dictionary = _words[i]
		if w.has("voice") and _clock >= float(w["at"]) and not _fired.has("voice%d" % i):
			_fired["voice%d" % i] = true
			_play(load(DIR + "voice-" + String(w["voice"]) + ".wav"), VOICE_DB, true)
	for s in _shots:
		var key := String(s["key"])
		var marks: Array = CUES.get(key, [])
		for j in marks.size():
			var mark: Array = marks[j]
			var id := "%s%d" % [key, j]
			if _clock >= float(s["start"]) + float(mark[1]) and not _fired.has(id):
				_fired[id] = true
				_play(_cue(String(mark[0])), float(mark[2]), false)
	var speaking := false
	for p in _players:
		if is_instance_valid(p) and (p as AudioStreamPlayer).playing and bool(p.get_meta("voice")):
			speaking = true
	_duck = move_toward(_duck, DUCK_DB if speaking else 0.0, delta * 40.0)
	var gone := _start("ember") + 1.6                     # the hand closes over the lamp, and the music with it
	var left := clampf((gone + 1.2 - _clock) / 1.2, 0.0, 1.0)
	_music.volume_db = MUSIC_DB + _duck + linear_to_db(maxf(left, 0.001))


func _play(stream: AudioStream, db: float, voice: bool) -> void:
	var p := AudioStreamPlayer.new()
	p.stream = stream
	p.bus = "Sfx"
	p.volume_db = db
	p.set_meta("voice", voice)
	p.finished.connect(func():
		_players.erase(p)
		p.queue_free())
	add_child(p)
	p.play()
	_players.append(p)


## A game cue's first take.
func _cue(name: String) -> AudioStream:
	var take := Sfx.DIR + name + "_0.wav"
	return load(take if ResourceLoader.exists(take) else Sfx.DIR + name + ".wav")
