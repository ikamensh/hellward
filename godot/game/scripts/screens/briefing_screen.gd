class_name BriefingScreen
extends Screen
## A location's intro (the 2D game's ui/briefing.py): who comes, each kind alive in a small firelit portrait, the
## curses their leaders cast and the answer to them, what the player may use here, and the sigils won so far. The
## Bone Priest, who has watched this fight before, says a word first. Defend (Enter) begins; Skills (K) and the
## Forge (F) open over it, and it asks the server again when they close; Story (S) tells the before page again;
## Esc goes back to the map.

const MARGIN := 120.0                       # the page's sides on the 1920 x 1080 canvas
const GAP := 14.0                           # between the host's cards
const BUTTONS := 72.0                       # the buttons' row, up from the page's foot
const LEADER_NAME := Color(0.93, 0.8, 1.0)
const LEADER_RIM := Color(0.6, 0.32, 0.85)
const UNIQUE := Color(0.84, 0.72, 0.46)     # the sealed side entrance, in Diablo's colour for uniques
const HOLY := Color(0.98, 0.9, 0.62)
const WASTE := Color(0.92, 0.24, 0.15)      # blood, lifted to read on the dark
const SPELL_KEYS := {"smite": "Z", "meteor": "X", "orb": "C", "hymn": "R"}
const GLYPH_TONES := {"smite": Color(1.0, 0.92, 0.6), "meteor": Color(1.0, 0.45, 0.12), "gate": Color(0.85, 0.62, 0.3),
	"hymn": Color(1.0, 0.78, 0.3)}
const TOWER_HUES := {"arrow": Color(0.55, 0.32, 0.14), "ballista": Color(0.5, 0.36, 0.2), "hook": Color(0.36, 0.38, 0.42),
	"knife": Color(0.42, 0.44, 0.5), "pyre": Color(0.7, 0.26, 0.08), "frost": Color(0.16, 0.32, 0.6),
	"storm": Color(0.32, 0.22, 0.62)}
const NOTE_HEADS := ["Armor", "Protected", "Vulnerable", "Flies", "Strikes", "Curses", "Raises", "Marks", "Each",
	"Unarmored"]
const TAGS := {"Protected from": Color(0.74, 0.69, 0.6), "Vulnerable to": Color(0.72, 0.9, 0.5)}
const SLOT := 68.0                          # an arsenal item's well
const PORTRAIT_BG := Color(0.026, 0.02, 0.024)

static var _italic_font: Font

var _taunt: Label
var _clock := 0.0
var _faded := false
var _covered := false
var _live: Array = []                       # the SubViewports that keep rendering while the screen is on top
var _bobbing: Array = []                    # [flyer's model, its height, its phase]
var _runes: Array = []                      # the curse sigils, turning


func build() -> void:
	add_child(Ui.backdrop("res://assets/story/%s-before.jpg" % String(data["key"]), 0.0))
	_veil()
	var page := Control.new()
	page.set_anchors_preset(Control.PRESET_CENTER)
	page.offset_left = -Ui.W / 2
	page.offset_right = Ui.W / 2
	page.offset_top = -Ui.H / 2
	page.offset_bottom = Ui.H / 2
	page.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(page)
	var body := VBoxContainer.new()
	body.position = Vector2(MARGIN, 16)
	body.size = Vector2(Ui.W - 2 * MARGIN, Ui.H - BUTTONS - 26)   # a sparse place spreads into the spare height
	body.add_theme_constant_override("separation", 0)
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	page.add_child(body)
	_header(body)
	_space(body, 10, 1.0)
	body.add_child(_taunt_row())
	_space(body, 10, 1.0)
	body.add_child(_heading("The host"))
	_space(body, 10)
	body.add_child(_host())
	if data["breach"] != null:
		_space(body, 10)
		body.add_child(_breach(data["breach"]))
	_space(body, 18, 1.5)
	var lower := HBoxContainer.new()
	lower.add_theme_constant_override("separation", 24)
	lower.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(lower)
	lower.add_child(_curses())
	lower.add_child(_arsenal())
	lower.add_child(_sigils())
	_space(body, 0, 1.0)
	page.add_child(_buttons())
	if not _faded:
		_faded = true
		modulate.a = 0.0
		create_tween().tween_property(self, "modulate:a", 1.0, 0.4)


## Skills or the Forge closed over it: ask again (ranks, wasted sigils) and lay it out anew; the story is told.
func reload() -> void:
	var fresh = await ask("briefing", {"location": String(data["key"])})
	if fresh == null:
		return
	data = fresh
	for c in get_children():
		remove_child(c)
		c.queue_free()
	_live.clear()
	_bobbing.clear()
	_runes.clear()
	_taunt = null
	build()


func _process(delta: float) -> void:
	super(delta)
	_clock += delta
	if _taunt:
		var glow := 0.5 + 0.5 * sin(_clock * 1.8)
		_taunt.self_modulate = Color(1, 1, 1, 0.8 + 0.2 * glow)
		_taunt.add_theme_color_override("font_outline_color", Color(0.42, 0.1, 0.7, 0.18 + 0.22 * glow))
	for r in _runes:
		(r as Control).rotation += delta * 0.18
	for b in _bobbing:
		(b[0] as Node3D).position.y = float(b[1]) + sin(_clock * 2.1 + float(b[2])) * float(b[1]) * 0.12
	# under the skill tree or the forge the portraits stop rendering
	var covered := get_index() < get_parent().get_child_count() - 1
	if covered != _covered:
		_covered = covered
		for vp in _live:
			(vp as SubViewport).render_target_update_mode = \
				SubViewport.UPDATE_DISABLED if covered else SubViewport.UPDATE_WHEN_VISIBLE


# -- The page ------------------------------------------------------------------------------------------

## The painting of the place, sunk into the dark; the corners darker still, embers rising.
func _veil() -> void:
	var dark := ColorRect.new()
	dark.color = Color(0.02, 0.012, 0.016, 0.8)
	dark.set_anchors_preset(Control.PRESET_FULL_RECT)
	dark.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(dark)
	var corners := ColorRect.new()
	var vm := ShaderMaterial.new()
	vm.shader = preload("res://shaders/vignette.gdshader")
	corners.material = vm
	corners.set_anchors_preset(Control.PRESET_FULL_RECT)
	corners.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(corners)
	var floor := TextureRect.new()
	floor.texture = _fade([[0.0, Color(0, 0, 0, 0)], [1.0, Color(0.16, 0.05, 0.02, 0.55)]], true)
	floor.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	floor.stretch_mode = TextureRect.STRETCH_SCALE
	floor.anchor_right = 1.0
	floor.anchor_top = 0.62
	floor.anchor_bottom = 1.0
	floor.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(floor)
	var embers := CPUParticles2D.new()
	embers.amount = 48
	embers.lifetime = 9.0
	embers.preprocess = 9.0
	embers.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
	embers.emission_rect_extents = Vector2(Ui.W * 0.55, 20)
	embers.direction = Vector2(0, -1)
	embers.spread = 18.0
	embers.gravity = Vector2(6, -6)
	embers.initial_velocity_min = 25.0
	embers.initial_velocity_max = 70.0
	embers.scale_amount_min = 0.15
	embers.scale_amount_max = 0.4
	embers.texture = _spark()
	var ramp := Gradient.new()
	ramp.offsets = PackedFloat32Array([0.0, 0.15, 0.7, 1.0])
	ramp.colors = PackedColorArray([Color(1.0, 0.6, 0.25, 0.0), Color(1.0, 0.55, 0.2, 0.75), Color(0.9, 0.3, 0.1, 0.45),
		Color(0.6, 0.15, 0.05, 0.0)])
	embers.color_ramp = ramp
	var add := CanvasItemMaterial.new()
	add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	embers.material = add
	var holder := Control.new()
	holder.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(embers)
	add_child(holder)


## The place's name in tracked capitals, a gilt rule, which act and how many waves, and what it teaches.
func _header(body: VBoxContainer) -> void:
	var name := Ui.label(String(data["name"]).to_upper(), 64, Style.GOLD, Style.display_font())
	name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name.add_theme_constant_override("outline_size", 14)
	name.add_theme_color_override("font_outline_color", Color(0.05, 0.02, 0.0, 0.9))
	body.add_child(name)
	body.add_child(_rule(640))
	var heading := Ui.caps(String(data["heading"]), 21, Style.DIM_GOLD)
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	body.add_child(heading)
	_space(body, 4)
	body.add_child(Ui.paragraph(String(data["lesson"]), 24, Style.BONE, Ui.W - 2 * MARGIN, HORIZONTAL_ALIGNMENT_CENTER))


## The Bone Priest's word: his face in a violet-rimmed well, the taunt glowing in curse violet.
func _taunt_row() -> Control:
	var centre := CenterContainer.new()
	centre.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var band := PanelContainer.new()
	var smoke := StyleBoxTexture.new()
	var glow := _fade([[0.0, Color(0.3, 0.06, 0.45, 0.42)], [0.55, Color(0.16, 0.03, 0.24, 0.22)], [1.0, Color(0, 0, 0, 0)]], false)
	glow.fill = GradientTexture2D.FILL_RADIAL
	glow.fill_from = Vector2(0.5, 0.5)
	glow.fill_to = Vector2(1.0, 0.5)
	glow.width = 256
	glow.height = 64
	smoke.texture = glow
	smoke.content_margin_left = 90
	smoke.content_margin_right = 90
	smoke.content_margin_top = 6
	smoke.content_margin_bottom = 6
	band.add_theme_stylebox_override("panel", smoke)
	band.mouse_filter = Control.MOUSE_FILTER_IGNORE
	centre.add_child(band)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 26)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	band.add_child(row)
	var frame := PanelContainer.new()
	frame.add_theme_stylebox_override("panel", Style.well(LEADER_RIM))
	frame.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	frame.tooltip_text = "The Bone Priest"
	row.add_child(frame)
	var face := TextureRect.new()
	var crop := AtlasTexture.new()
	crop.atlas = load("res://assets/story/priest.jpg")
	crop.region = Rect2(150, 70, 310, 310)
	face.texture = crop
	face.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	face.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	face.custom_minimum_size = Vector2(80, 80)
	face.mouse_filter = Control.MOUSE_FILTER_IGNORE
	frame.add_child(face)
	var words := VBoxContainer.new()
	words.alignment = BoxContainer.ALIGNMENT_CENTER
	words.add_theme_constant_override("separation", 2)
	words.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(words)
	_taunt = Ui.paragraph("“%s”" % String(data["taunt"]), 24, Style.CURSE.lerp(Color.WHITE, 0.12), 1180)
	_taunt.add_theme_font_override("font", _italic())
	_taunt.add_theme_constant_override("outline_size", 10)
	words.add_child(_taunt)
	var who := Ui.caps("— the Bone Priest", 18, Color(0.66, 0.55, 0.72))
	who.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	words.add_child(who)
	return centre


## A card per monster kind: its portrait, name, life and pace, and what it resists; a leader's rimmed in violet.
func _host() -> Control:
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", int(GAP))
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var host: Array = data["host"]
	var n := host.size()
	var few := n <= 3                           # a small host gets large portraits, a great one small
	var width := minf(300.0 if few else 250.0, (Ui.W - 2 * MARGIN - GAP * (n - 1)) / n)
	var tall := 196.0 if few else 140.0 if n <= 5 else 124.0
	for h in host:
		row.add_child(_monster_card(h, width, minf(tall, width * 0.72)))
	return row


func _monster_card(h: Dictionary, width: float, tall: float) -> Control:
	var leader := bool(h["leader"])
	var kind := String(h["kind"])
	var notes := _notes(String(h["notes"]))
	var card := _iron(leader)
	card.custom_minimum_size = Vector2(width, 0)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 4)
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_inset(card, 10, 10, 10, 12).add_child(col)
	var frame := PanelContainer.new()
	frame.add_theme_stylebox_override("panel", Style.well(LEADER_RIM if leader else Style.BRONZE))
	frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	col.add_child(frame)
	var pic := _monster_portrait(kind, leader, notes.any(func(s): return s.begins_with("Flies")),
		Vector2(width - 30, tall))
	frame.add_child(pic)
	if leader:
		var tag := _tag("Leader", Color(0.24, 0.07, 0.34), LEADER_RIM, LEADER_NAME)
		tag.anchor_left = 0.5
		tag.anchor_right = 0.5
		tag.offset_top = 5
		tag.grow_horizontal = Control.GROW_DIRECTION_BOTH
		pic.add_child(tag)
	_space(col, 2)
	var name := Ui.label(String(h["name"]).to_upper(), 20 if width > 200 else 18, LEADER_NAME if leader else Style.GOLD,
		Style.small_font())
	name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	col.add_child(name)
	var line := Ui.label(String(h["line"]), 19, Style.BONE)
	line.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	col.add_child(line)
	col.add_child(_rule(width * 0.6, 8))
	var said := RichTextLabel.new()
	said.bbcode_enabled = true
	said.fit_content = true
	said.scroll_active = false
	said.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	said.add_theme_font_override("normal_font", Style.text_font())
	said.add_theme_font_size_override("normal_font_size", 18)
	said.add_theme_constant_override("outline_size", 5)
	said.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
	said.add_theme_constant_override("line_separation", -2)
	said.mouse_filter = Control.MOUSE_FILTER_IGNORE
	said.text = _described(notes)
	col.add_child(said)
	return card


## The curses the leaders here cast, a card each with its turning sigil, and the answer to them.
func _curses() -> Control:
	var box := _panel()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var col := box.get_child(0) as VBoxContainer
	col.add_child(_heading("Their curses"))
	var curses: Array = data["curses"]
	var grid := GridContainer.new()
	grid.columns = 1 if curses.size() == 1 else 2
	grid.add_theme_constant_override("h_separation", 12)
	grid.add_theme_constant_override("v_separation", 8)
	grid.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if curses.size() == 1:
		grid.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(grid)
	for c in curses:
		var card := PanelContainer.new()
		var sb := StyleBoxFlat.new()
		sb.bg_color = Color(0.1, 0.035, 0.12, 0.92)
		sb.border_color = Color(0.55, 0.26, 0.74)
		sb.set_border_width_all(2)
		sb.set_corner_radius_all(6)
		sb.shadow_color = Color(0.35, 0.05, 0.55, 0.35)
		sb.shadow_size = 8
		sb.set_content_margin_all(6)
		sb.content_margin_left = 8
		card.add_theme_stylebox_override("panel", sb)
		card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		if curses.size() == 1:
			card.custom_minimum_size = Vector2(560, 0)
		var title := String(c["title"])
		card.tooltip_text = "%s\n%s" % [title.get_slice(",", 0), String(data["answer"])]
		grid.add_child(card)
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 12)
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		card.add_child(row)
		var rune := TextureRect.new()
		rune.texture = load("res://assets/fx/rune_circle.png")
		rune.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		rune.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		rune.custom_minimum_size = Vector2(42, 42)
		rune.pivot_offset = Vector2(21, 21)
		rune.rotation = randf() * TAU
		rune.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		rune.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_runes.append(rune)
		row.add_child(rune)
		var words := VBoxContainer.new()
		words.add_theme_constant_override("separation", 2)
		words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		words.alignment = BoxContainer.ALIGNMENT_CENTER
		words.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.add_child(words)
		words.add_child(Ui.label(title, 22, Style.CURSE.lerp(Color.WHITE, 0.15), Style.title_font()))
		var what := Ui.label(String(c["line"]), 19, Style.BONE)
		what.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		words.add_child(what)
	var answer := HBoxContainer.new()
	answer.alignment = BoxContainer.ALIGNMENT_CENTER
	answer.add_theme_constant_override("separation", 12)
	answer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	col.add_child(answer)
	var cross := TextureRect.new()
	cross.texture = load("res://assets/ui/holy.png")
	cross.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	cross.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	cross.custom_minimum_size = Vector2(38, 38)
	cross.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	cross.mouse_filter = Control.MOUSE_FILTER_IGNORE
	answer.add_child(cross)
	var said := String(data["answer"])
	var size := 21
	var words := Ui.label(said, size, HOLY)
	words.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	words.custom_minimum_size = Vector2(minf(Style.text_font().get_string_size(said, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x + 8,
		720), 0)
	words.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	answer.add_child(words)
	return box


## What the player may use here: the towers (rank pips: the ranks the skills allow), the gate and the spells,
## what is new since the last place marked.
func _arsenal() -> Control:
	var box := _panel()
	var col := box.get_child(0) as VBoxContainer
	col.add_child(_heading("Your arsenal"))
	var things: Array = data["arsenal"]
	var grid := GridContainer.new()
	grid.columns = mini(things.size(), 6)
	grid.add_theme_constant_override("h_separation", 12)
	grid.add_theme_constant_override("v_separation", 6)
	grid.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	grid.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var middle := _middle(col)
	middle.add_child(grid)
	var new: Array = things.filter(func(t): return bool(t["new"])).map(func(t): return String(t["name"]))
	if not new.is_empty():
		var said := Ui.label("New here: " + ", ".join(new), 20, Style.GOLD)
		said.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		middle.add_child(said)
	for t in things:
		grid.add_child(_arsenal_item(t))
	return box


func _arsenal_item(t: Dictionary) -> Control:
	var key := String(t["key"])
	var ranks := int(t["ranks"])
	var new := bool(t["new"])
	var item := Control.new()
	item.custom_minimum_size = Vector2(SLOT, SLOT + 22)
	item.tooltip_text = "%s\n%s" % [String(t["name"]), String(t["tip"])]
	var well := PanelContainer.new()
	well.add_theme_stylebox_override("panel", Style.well(Style.GOLD if new else Style.BRONZE))
	well.position = Vector2(0, 6)
	well.size = Vector2(SLOT, SLOT)
	well.mouse_filter = Control.MOUSE_FILTER_IGNORE
	item.add_child(well)
	var pic: Control
	if ranks > 0:
		pic = _tower_portrait(key, ranks - 1, int(SLOT - 10) * 2)
	elif ResourceLoader.exists("res://assets/ui/%s.png" % key):
		var tr := TextureRect.new()
		tr.texture = load("res://assets/ui/%s.png" % key)
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		pic = tr
	elif key == "orb":
		var orb := ColorRect.new()
		var om := ShaderMaterial.new()
		om.shader = preload("res://shaders/orb.gdshader")
		om.set_shader_parameter("liquid", Color(0.12, 0.3, 0.85))
		om.set_shader_parameter("glow", Color(0.6, 0.85, 1.0))
		om.set_shader_parameter("noise", _noise())
		orb.material = om
		pic = orb
	else:
		var g := Glyph.new()
		g.what = key
		g.tone = GLYPH_TONES.get(key, Style.GOLD)
		pic = g
	pic.mouse_filter = Control.MOUSE_FILTER_IGNORE
	well.add_child(pic)
	if Hud.SPELLS.has(key):
		var k := Ui.caps(Hud.SPELLS[key], 17, Style.PALE_GOLD)
		k.position = Vector2(8, 8)
		item.add_child(k)
	if ranks > 0:
		var pips := HBoxContainer.new()
		pips.add_theme_constant_override("separation", 3)
		pips.alignment = BoxContainer.ALIGNMENT_CENTER
		pips.position = Vector2(0, SLOT + 8)
		pips.size = Vector2(SLOT, 14)
		pips.mouse_filter = Control.MOUSE_FILTER_IGNORE
		for i in 3:
			pips.add_child(_gem(9, Style.GOLD if i < ranks else Color(0.1, 0.08, 0.06), Style.GOLD))
		item.add_child(pips)
	if new:
		var tag := _tag("New", Color(0.42, 0.26, 0.06), Style.GOLD, Color(1.0, 0.94, 0.75))
		tag.position = Vector2(SLOT / 2 - 4, -3)
		item.add_child(tag)
	return item


## The sigils won here, what the next one asks, and the sigils sitting idle in skills that do nothing here.
func _sigils() -> Control:
	var box := _panel()
	box.custom_minimum_size = Vector2(340, 0)
	var col := box.get_child(0) as VBoxContainer
	col.add_child(_heading("Sigils here"))
	col = _middle(col)
	var pips := Ui.pips(int(data["best"]), 26)
	pips.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(pips)
	_space(col, 4)
	var next = data["next_sigil"]
	col.add_child(Ui.paragraph(String(next) if next != null else "All three are won.", 21,
		Style.BONE if next != null else Style.GOLD, 300, HORIZONTAL_ALIGNMENT_CENTER))
	if data["waste"] != null:
		col.add_child(Ui.paragraph(String(data["waste"]), 21, WASTE, 300, HORIZONTAL_ALIGNMENT_CENTER))
	return box


## The sealed side entrance, under the host: its name, what comes through it, and whether its trophy is won.
func _breach(breach: Dictionary) -> Control:
	var strip := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.07, 0.05, 0.03, 0.85)
	sb.border_color = Color(UNIQUE, 0.55)
	sb.border_width_top = 1
	sb.border_width_bottom = 1
	sb.content_margin_top = 6
	sb.content_margin_bottom = 6
	strip.add_theme_stylebox_override("panel", sb)
	strip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 14)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	strip.add_child(row)
	var claim := String(breach["claimed"]) if breach["claimed"] != null else ""
	var said: String = {"trophy": "Its trophy is yours.", "cash": "Its cache was taken: no trophy here."}.get(claim,
		"Clear its side pack and win to keep its trophy.")
	for part in [Ui.caps("Sealed side entrance", 18, Style.DIM_GOLD), _gem(7, UNIQUE, UNIQUE),
			Ui.caps(String(breach["name"]), 22, UNIQUE), Ui.label(String(breach["blurb"]), 22, Style.BONE),
			_gem(7, UNIQUE, UNIQUE),
			Ui.label(said, 22, HOLY if claim == "trophy" else Style.PALE_GOLD if claim == "" else Style.DIM_GOLD)]:
		(part as Control).size_flags_vertical = Control.SIZE_SHRINK_CENTER
		row.add_child(part)
	return strip


func _buttons() -> Control:
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 16)
	row.position = Vector2(0, Ui.H - BUTTONS)
	row.size = Vector2(Ui.W, 56)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var defend := Ui.button("Defend", "Enter", 250)
	defend.add_theme_font_size_override("font_size", 24)
	defend.pressed.connect(func(): game.defend(String(data["key"])))
	if not bool(data["opened"]):
		defend.disabled = true
		defend.tooltip_text = "The way here is not open yet."
	row.add_child(defend)
	var skills := Ui.button("Skills", "K", 190)
	skills.pressed.connect(func(): game.skills(String(data["key"])))
	row.add_child(skills)
	var forge := Ui.button("Forge", "F", 190)
	forge.pressed.connect(game.forge)
	row.add_child(forge)
	if data["before"] != null:
		var story := Ui.button("Story", "S", 190)
		story.pressed.connect(func(): game.retell(data))
		row.add_child(story)
	var back := Ui.button("Back to the map", "Esc", 290)
	back.pressed.connect(game.world_map)
	row.add_child(back)
	return row


# -- Portraits -------------------------------------------------------------------------------------------

## A monster kind alive in a small firelit stage: the model it wears (a stand-in tinted as in battle), idling or,
## a leader, chanting on its violet ring; a flyer hovers over its shadow.
func _monster_portrait(kind: String, leader: bool, flies: bool, size: Vector2) -> TextureRect:
	var k := clampf(get_viewport().get_final_transform().get_scale().x, 1.0, 2.0)
	var vp := _stage(Vector2i(size * k), true)
	var base: String = kind if Monster.HEIGHTS.has(kind) else String(Monster.STAND_INS.get(kind, ["fallen"])[0])
	var model := Models.make("mon_" + base)
	vp.add_child(model)
	var anim := Models.player(model)
	var action := Models.anim_name(anim, "cast") if leader else ""
	if action == "":
		action = Models.anim_name(anim, "idle")
	anim.get_animation(action).loop_mode = Animation.LOOP_LINEAR
	anim.play(action)
	anim.seek(randf() * anim.current_animation_length, true)
	var overlay := ShaderMaterial.new()
	overlay.shader = preload("res://shaders/overlay.gdshader")
	overlay.set_shader_parameter("moonrim", 0.12)
	if Monster.STAND_INS.has(kind):
		overlay.set_shader_parameter("tint", Monster.STAND_INS[kind][1])
	for mi in model.find_children("*", "MeshInstance3D", true, false):
		(mi as MeshInstance3D).material_overlay = overlay
	var hue: Color = LEADER_NAME if leader else \
		Monster.RIM.get(kind, Monster.STAND_INS.get(kind, [null, Color(0.9, 0.4, 0.3)])[1])
	var box := _bounds(model)
	var tall := box.size.y
	var lift := tall * 0.28 if flies else 0.0
	if flies:
		model.position.y = lift
		_bobbing.append([model, lift, randf() * TAU])
	var centre := Vector3(box.get_center().x, (box.position.y + box.end.y + lift) / 2 - tall * 0.06, box.get_center().z)
	var cam := Camera3D.new()
	cam.fov = 30
	vp.add_child(cam)
	var yaw := deg_to_rad(26)
	var pitch := deg_to_rad(11)
	var toward := Vector3(sin(yaw) * cos(pitch), sin(pitch), -cos(yaw) * cos(pitch))
	var half := tan(deg_to_rad(cam.fov) / 2)
	var dist := maxf((tall + lift) * 0.53 / half, maxf(box.size.x, box.size.z) * 0.6 / (half * size.x / size.y))
	cam.look_at_from_position(centre + toward * dist, centre)
	var width := maxf(box.size.x, box.size.z)
	_halo(vp, centre, toward, dist, width + 1.2, hue * 0.2, half)
	# the pool it stands in: a shadow at its feet fading into firelit ground
	var pool := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(2.8, 2.8)
	pool.mesh = plane
	var pm := StandardMaterial3D.new()
	pm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	pm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	var ground := _fade([[0.0, Color(0, 0, 0, 0.75)], [0.3, Color(0.3, 0.13, 0.05, 0.55)], [1.0, Color(0.1, 0.04, 0.02, 0)]],
		false)
	ground.fill = GradientTexture2D.FILL_RADIAL
	ground.fill_from = Vector2(0.5, 0.5)
	ground.fill_to = Vector2(1.0, 0.5)
	ground.width = 128
	ground.height = 128
	pm.albedo_texture = ground
	pool.material_override = pm
	pool.position = Vector3(box.get_center().x, 0.01, box.get_center().z)
	vp.add_child(pool)
	if leader:
		var ring := MeshInstance3D.new()
		var rp := PlaneMesh.new()
		rp.size = Vector2(2.6, 2.6)
		ring.mesh = rp
		var rm := ShaderMaterial.new()
		rm.shader = preload("res://shaders/ring.gdshader")
		rm.set_shader_parameter("radius", 0.72)
		rm.set_shader_parameter("color", Color(0.7, 0.25, 1.0, 0.5))
		ring.material_override = rm
		ring.position = pool.position + Vector3(0, 0.02, 0)
		vp.add_child(ring)
	var key_light := DirectionalLight3D.new()
	key_light.light_color = Color(1.0, 0.78, 0.56)
	key_light.light_energy = 0.9
	vp.add_child(key_light)
	key_light.look_at_from_position(centre + toward.rotated(Vector3.UP, deg_to_rad(-45)) * 10 + Vector3(0, 7, 0), centre)
	var rim := DirectionalLight3D.new()
	rim.light_color = hue
	rim.light_energy = 2.4
	vp.add_child(rim)
	rim.look_at_from_position(centre - toward.rotated(Vector3.UP, deg_to_rad(35)) * 10 + Vector3(0, 4, 0), centre)
	var fire := Fx.fire_light(3.0, 7.0)
	fire.position = centre + toward.rotated(Vector3.UP, deg_to_rad(55)) * 2.2 + Vector3(0, -tall * 0.3, 0)
	vp.add_child(fire)
	var env := _environment(vp, 1.1)
	env.ambient_light_energy = 0.3
	return _shown(vp, size)


## A tower at the highest rank the skills allow, framed on its upper part as the battle's slots show it.
func _tower_portrait(kind: String, rank: int, px: int) -> TextureRect:
	var vp := _stage(Vector2i(px, px), kind == "pyre")   # only the Pyre's flame moves
	var model := Models.make(Tower.model_name(kind, rank))
	vp.add_child(model)
	Tower.dress_fx(model, kind, rank)
	var base: String = Tower.STAND_INS[kind][0] if Tower.STAND_INS.has(kind) else kind
	var tint: Color = Tower.STAND_INS[kind][1] if Tower.STAND_INS.has(kind) else Color.WHITE
	if Tower.STAND_INS.has(kind):
		var overlay := ShaderMaterial.new()
		overlay.shader = preload("res://shaders/overlay.gdshader")
		overlay.set_shader_parameter("tint", tint)
		for mi in model.find_children("*", "MeshInstance3D", true, false):
			(mi as MeshInstance3D).material_overlay = overlay
	var box := _bounds(model)
	var top := box.end.y + (1.0 if base == "pyre" else 0.15)
	var span := (top - box.position.y) * 0.8
	var centre := Vector3(box.get_center().x, top - span * 0.46, box.get_center().z)
	var width := Vector2(box.size.x, box.size.z).length()
	var cam := Camera3D.new()
	cam.fov = 24
	vp.add_child(cam)
	var yaw := deg_to_rad(32)
	var pitch := deg_to_rad(12)
	var toward := Vector3(sin(yaw) * cos(pitch), sin(pitch), -cos(yaw) * cos(pitch))
	var half := tan(deg_to_rad(cam.fov) / 2)
	var dist := maxf(span * 1.08, width) * 0.6 / half
	cam.look_at_from_position(centre + toward * dist, centre)
	_halo(vp, centre, toward, dist, width, Hud.TOWER_HUES[base] * tint, half)
	var key_light := DirectionalLight3D.new()
	key_light.light_color = Color(0.75, 0.84, 1.0)
	key_light.light_energy = 3.2
	vp.add_child(key_light)
	key_light.look_at_from_position(centre + toward.rotated(Vector3.UP, deg_to_rad(-55)) * 10 + Vector3(0, 6, 0), centre)
	var rim := DirectionalLight3D.new()
	rim.light_color = Color(1.0, 0.58, 0.28)
	rim.light_energy = 6.0
	vp.add_child(rim)
	rim.look_at_from_position(centre - toward.rotated(Vector3.UP, deg_to_rad(-40)) * 10 + Vector3(0, 3, 0), centre)
	var env := _environment(vp, 1.45)
	env.ambient_light_color = Color(0.42, 0.44, 0.55)
	env.ambient_light_energy = 1.1
	return _shown(vp, Vector2(SLOT - 10, SLOT - 10))


func _stage(px: Vector2i, live: bool) -> SubViewport:
	var vp := SubViewport.new()
	vp.size = px
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_ONCE if not live else \
		SubViewport.UPDATE_DISABLED if _covered else SubViewport.UPDATE_WHEN_VISIBLE
	if live:
		_live.append(vp)
	return vp


## The stage's viewport shown at `size` (its picture may be finer, for a window scaled up).
func _shown(vp: SubViewport, size: Vector2) -> TextureRect:
	var pic := TextureRect.new()
	pic.texture = vp.get_texture()
	pic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	pic.stretch_mode = TextureRect.STRETCH_SCALE
	pic.custom_minimum_size = size
	pic.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pic.add_child(vp)
	return pic


## A glow behind the figure in its own colour, so the dark body stands off the dark.
func _halo(vp: SubViewport, centre: Vector3, toward: Vector3, dist: float, width: float, hue: Color, half: float) -> void:
	var back := MeshInstance3D.new()
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE * (dist + width) * half * 2.6
	back.mesh = quad
	var bm := StandardMaterial3D.new()
	bm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	var glow := GradientTexture2D.new()
	glow.gradient = Gradient.new()
	glow.gradient.colors = PackedColorArray([hue, PORTRAIT_BG])
	glow.fill = GradientTexture2D.FILL_RADIAL
	glow.fill_from = Vector2(0.5, 0.42)
	glow.fill_to = Vector2(0.5, 0.95)
	bm.albedo_texture = glow
	back.material_override = bm
	back.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	vp.add_child(back)
	back.look_at_from_position(centre - toward * width, centre + toward * dist)
	back.rotate_object_local(Vector3.UP, PI)


func _environment(vp: SubViewport, exposure: float) -> Environment:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = PORTRAIT_BG
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.36, 0.32, 0.36)
	env.ambient_light_energy = 0.6
	env.glow_enabled = true
	env.glow_intensity = 0.7
	env.glow_hdr_threshold = 1.0
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = exposure
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	return env


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


# -- The kit's small pieces ------------------------------------------------------------------------------

## A panel of dark iron in a bronze rim; its first child is the column to fill.
func _panel() -> PanelContainer:
	var box := Ui.box(Color(0.42, 0.31, 0.17), Color(0.035, 0.026, 0.03, 0.82))
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(col)
	return box


## A card of hammered iron in a gold trim (violet for a leader's), as the battle's tower card.
func _iron(leader: bool) -> PanelContainer:
	var card := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0, 0, 0, 0)
	sb.shadow_color = Color(LEADER_RIM, 0.5) if leader else Color(0, 0, 0, 0.6)
	sb.shadow_size = 16
	card.add_theme_stylebox_override("panel", sb)
	card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var iron := ColorRect.new()
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/hud_panel.gdshader")
	m.set_shader_parameter("engraved", false)
	m.set_shader_parameter("chamfer", 12.0)
	m.set_shader_parameter("trim", 3.0)
	m.set_shader_parameter("curse", 1.0 if leader else 0.0)
	iron.material = m
	iron.mouse_filter = Control.MOUSE_FILTER_IGNORE
	iron.resized.connect(func(): m.set_shader_parameter("size", iron.size))
	card.add_child(iron)
	return card


func _inset(parent: Control, left: int, right: int, top: int, bottom: int) -> MarginContainer:
	var m := MarginContainer.new()
	m.add_theme_constant_override("margin_left", left)
	m.add_theme_constant_override("margin_right", right)
	m.add_theme_constant_override("margin_top", top)
	m.add_theme_constant_override("margin_bottom", bottom)
	m.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(m)
	return m


## A section's heading: a gilt lozenge, the words in tracked capitals, a rule fading off to the right.
func _heading(text: String) -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var gem := _gem(10, Style.GOLD, Style.PALE_GOLD)
	gem.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(gem)
	row.add_child(Ui.caps(text, 21, Style.GOLD))
	var line := TextureRect.new()
	line.texture = _fade([[0.0, Color(Style.BRONZE, 0.95)], [1.0, Color(Style.BRONZE, 0.0)]], false)
	line.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	line.stretch_mode = TextureRect.STRETCH_SCALE
	line.custom_minimum_size = Vector2(0, 2)
	line.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	line.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(line)
	return row


## A thin gilt rule fading out at both ends, a small lozenge at its middle.
func _rule(width: float, height := 18.0) -> Control:
	var holder := Control.new()
	holder.custom_minimum_size = Vector2(0, height)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var line := TextureRect.new()
	line.texture = _fade([[0.0, Color(Style.GOLD, 0)], [0.5, Color(Style.GOLD, 0.9)], [1.0, Color(Style.GOLD, 0)]], false)
	line.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	line.stretch_mode = TextureRect.STRETCH_SCALE
	line.anchor_left = 0.5
	line.anchor_right = 0.5
	line.anchor_top = 0.5
	line.anchor_bottom = 0.5
	line.offset_left = -width / 2
	line.offset_right = width / 2
	line.offset_top = -1
	line.offset_bottom = 1
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(line)
	var gem := _gem(9, Style.GOLD, Style.PALE_GOLD)
	gem.anchor_left = 0.5
	gem.anchor_right = 0.5
	gem.anchor_top = 0.5
	gem.anchor_bottom = 0.5
	gem.offset_left = -gem.custom_minimum_size.x / 2
	gem.offset_top = -gem.custom_minimum_size.y / 2
	holder.add_child(gem)
	return holder


## A small lozenge: a rank pip, or the gilt mark before a heading.
func _gem(px: float, fill: Color, edge: Color) -> Control:
	var holder := Control.new()
	holder.custom_minimum_size = Vector2(px, px) * 1.42
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var p := Panel.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = fill
	sb.border_color = edge
	sb.set_border_width_all(1)
	p.add_theme_stylebox_override("panel", sb)
	p.size = Vector2(px, px)
	p.position = Vector2(px, px) * 0.21
	p.pivot_offset = Vector2(px, px) / 2
	p.rotation = PI / 4
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(p)
	return holder


## A small plaque of tracked capitals: "Leader" over a portrait, "New" on an arsenal item.
func _tag(text: String, fill: Color, edge: Color, ink: Color) -> PanelContainer:
	var tag := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = fill
	sb.border_color = edge
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(3)
	sb.content_margin_left = 7
	sb.content_margin_right = 7
	sb.content_margin_top = 1
	sb.content_margin_bottom = 2
	sb.shadow_color = Color(0, 0, 0, 0.6)
	sb.shadow_size = 4
	tag.add_theme_stylebox_override("panel", sb)
	tag.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tag.add_child(Ui.ink(Ui.caps(text, 15, ink)))
	return tag


## A column taking the rest of a panel's height, its contents centred in it.
func _middle(col: VBoxContainer) -> VBoxContainer:
	var middle := VBoxContainer.new()
	middle.alignment = BoxContainer.ALIGNMENT_CENTER
	middle.add_theme_constant_override("separation", 10)
	middle.size_flags_vertical = Control.SIZE_EXPAND_FILL
	middle.mouse_filter = Control.MOUSE_FILTER_IGNORE
	col.add_child(middle)
	return middle


## A gap of `px`, which takes a share (`grow`) of the page's spare height.
func _space(parent: Control, px: float, grow := 0.0) -> void:
	var s := Control.new()
	s.custom_minimum_size = Vector2(0, px)
	if grow > 0.0:
		s.size_flags_vertical = Control.SIZE_EXPAND_FILL
		s.size_flags_stretch_ratio = grow
	s.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(s)


## A gradient texture from [offset, colour] stops, running down (`vertical`) or across.
static func _fade(stops: Array, vertical: bool) -> GradientTexture2D:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array(stops.map(func(s): return s[0]))
	g.colors = PackedColorArray(stops.map(func(s): return s[1]))
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill_to = Vector2(0, 1) if vertical else Vector2(1, 0)
	t.width = 4 if vertical else 256
	t.height = 256 if vertical else 4
	return t


static func _spark() -> GradientTexture2D:
	var t := _fade([[0.0, Color(1, 1, 1, 1)], [0.35, Color(1, 1, 1, 0.5)], [1.0, Color(1, 1, 1, 0)]], false)
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = Vector2(0.5, 0.5)
	t.fill_to = Vector2(1.0, 0.5)
	t.width = 32
	t.height = 32
	return t


static func _noise() -> NoiseTexture2D:
	var nt := NoiseTexture2D.new()
	nt.seamless = true
	var fn := FastNoiseLite.new()
	fn.frequency = 0.05
	fn.fractal_octaves = 2
	nt.noise = fn
	return nt


static func _italic() -> Font:
	if _italic_font == null:
		var f := SystemFont.new()
		f.font_names = PackedStringArray(["Baskerville", "Georgia", "serif"])
		f.font_italic = true
		_italic_font = f
	return _italic_font


## The server's notes on a kind ("Armor 2, Protected from Fire, Curses: Weaken, Decrepify") one per line, a curse
## list kept whole.
static func _notes(text: String) -> Array:
	var out: Array = []
	for part in text.split(", "):
		var head := out.is_empty() or NOTE_HEADS.any(func(h): return part.begins_with(h))
		if head:
			out.append(part)
		else:
			out[-1] = String(out[-1]) + ", " + part
	return out


## The notes as the card shows them, in Diablo's manner: one line per kind of note, the tagged elements gathered on
## one line, each element in its colour, what a leader does in violet.
static func _described(notes: Array) -> String:
	var elements := {}                  # "Protected from", "Vulnerable to" -> the elements' names
	var lines: Array = []
	for n in notes:
		var note := String(n)
		var head := ""
		for h in TAGS:
			if note.begins_with(h + " "):
				head = h
		if head == "":
			lines.append("[color=#%s]%s[/color]" % [_note_tone(note).to_html(false), note])
			continue
		if not elements.has(head):
			elements[head] = []
			lines.append(head)
		var element := note.substr(head.length() + 1)
		var tone: Color = Hud.ELEMENT_TONES.get(element.to_lower(), Style.BONE).lerp(Style.BONE, 0.2)
		elements[head].append("[color=#%s]%s[/color]" % [tone.to_html(false), element])
	for i in lines.size():
		var head := String(lines[i])
		if elements.has(head):
			lines[i] = "[color=#%s]%s[/color] %s" % [TAGS[head].to_html(false), head, ", ".join(elements[head])]
	return "[center]%s[/center]" % "\n".join(lines)


static func _note_tone(note: String) -> Color:
	if note.begins_with("Flies"):
		return Color(0.7, 0.82, 1.0)
	if note.begins_with("Unarmored"):
		return Style.DIM_GOLD
	if note.begins_with("Armor"):
		return Color(0.8, 0.82, 0.88)
	if note.begins_with("Strikes"):
		return Color(1.0, 0.8, 0.45)    # a boss's strike on the shrine
	return Color(0.84, 0.64, 1.0)       # what a leader does: its curses, raising, marking, burning


## A spell's or the gate's sign where no painted icon exists: a glow in its colour and the sign drawn over it.
class Glyph:
	extends Control

	var what := ""
	var tone := Color.WHITE

	func _draw() -> void:
		var c := size / 2
		var r := minf(size.x, size.y) / 2
		for i in 10:
			draw_circle(c, r * (1.0 - i * 0.085), Color(tone * 0.6, 0.05 + i * 0.012))
		match what:
			"smite":
				var bolt := PackedVector2Array()
				for p in [Vector2(0.12, -0.85), Vector2(-0.36, 0.1), Vector2(-0.02, 0.1), Vector2(-0.2, 0.86),
						Vector2(0.4, -0.2), Vector2(0.06, -0.2), Vector2(0.32, -0.85)]:
					bolt.append(c + p * r * 0.9)
				draw_colored_polygon(bolt, Color(1.0, 0.97, 0.82))
				bolt.append(bolt[0])
				draw_polyline(bolt, Color(0.85, 0.6, 0.2), 1.5, true)
			"meteor":
				var at := c + Vector2(-0.22, 0.22) * r
				var back := (Vector2(0.75, -0.75) * r)
				var side := back.orthogonal().normalized() * r * 0.3
				draw_polygon(PackedVector2Array([at + side, at - side, at + back]),
					PackedColorArray([Color(1.0, 0.45, 0.1, 0.9), Color(1.0, 0.45, 0.1, 0.9), Color(1.0, 0.2, 0.0, 0.0)]))
				draw_circle(at, r * 0.32, Color(1.0, 0.42, 0.1))
				draw_circle(at, r * 0.2, Color(1.0, 0.85, 0.45))
			"gate":
				var iron := Color(0.8, 0.62, 0.34)
				var w := r * 1.1
				var top := c.y - r * 0.35
				var bottom := c.y + r * 0.75
				draw_arc(Vector2(c.x, top), w / 2, PI, TAU, 24, iron, 3.0, true)
				draw_line(Vector2(c.x - w / 2, top), Vector2(c.x - w / 2, bottom), iron, 3.0, true)
				draw_line(Vector2(c.x + w / 2, top), Vector2(c.x + w / 2, bottom), iron, 3.0, true)
				for i in 4:
					var x := c.x - w / 2 + w * (i + 1) / 5.0
					var rise := sqrt(maxf(0.0, w * w / 4 - pow(x - c.x, 2)))
					draw_line(Vector2(x, top - rise), Vector2(x, bottom - 4), iron, 2.0, true)
					draw_colored_polygon(PackedVector2Array([Vector2(x - 3, bottom - 5), Vector2(x + 3, bottom - 5),
						Vector2(x, bottom + 1)]), iron)
				for y in [top + r * 0.15, top + r * 0.6]:
					draw_line(Vector2(c.x - w / 2, y), Vector2(c.x + w / 2, y), iron, 2.0, true)
