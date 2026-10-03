class_name Hud
extends CanvasLayer
## The screen over the battle, in Diablo's manner: a narrow iron bar at the bottom capped by the life and mana
## orbs in their sculpted holders, the tower slots, the wave and the gold on it, the chosen tower's card above it.
## Banners, a leader's bar and the chronicle of curses live on a layer of their own (`_over`), so H (toggle) puts
## the HUD away and film mode (cinematic) fades it while they stay. A monster under the mouse shows its life, armor,
## element tags and the hit each of the player's towers deals it (`hover`).

signal slot_pressed(kind: String)     # a tower kind, "gate", or "spell:<key>"
signal order(name: String)            # "wave", "skip", "upgrade", "sell", "attune", "mode:<key>", "pace", "salvage", "breach:<mode>", "menu"

const SPELLS := {"smite": "Z", "meteor": "X", "orb": "C", "hymn": "R"}
const SPELL_TONES := {"smite": Color(1.0, 0.95, 0.7), "meteor": Color(1.0, 0.45, 0.12), "orb": Color(0.45, 0.7, 1.0),
	"hymn": Color(1.0, 0.78, 0.3)}
const BAR := Vector2(1240, 112)       # the bottom bar, centred, LIFT px above the screen's edge
const LIFT := 10.0
const ORB := 176.0                    # an orb's glass, across
const ORB_RISE := 128.0               # an orb's centre above the screen's edge
const ORB_REACH := 780.0
const COIN := preload("res://assets/ui/coin.png")              # the orbs' frames reach this far either side of the middle: the HUD's width
const FRAME_HOLE := 0.40              # a painted frame's opening, as a fraction of its half-size (tools/fxsprites.py)
const SLOT := 82.0
const GAP := 8.0                      # between slots
const INSET := 150.0                  # the bar's ends, under the orbs' frames: its contents start inside them
const SHADE := 260.0                  # the dark the scene sinks into towards the bar
const NUMERALS := ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
const ELEMENT_TONES := {"physical": Color(0.82, 0.76, 0.66), "fire": Color(1.0, 0.55, 0.25),
	"cold": Color(0.55, 0.8, 1.0), "lightning": Color(0.72, 0.72, 1.0), "poison": Color(0.55, 0.9, 0.3),
	"bone": Color(0.9, 0.86, 0.72), "nature": Color(0.45, 0.85, 0.4)}
const TOWER_HUES := {"arrow": Color(0.55, 0.32, 0.14), "pyre": Color(0.7, 0.26, 0.08),   # a portrait's halo, per kind
	"frost": Color(0.16, 0.32, 0.6), "storm": Color(0.32, 0.22, 0.62), "plague": Color(0.24, 0.5, 0.14),
	"altar": Color(0.55, 0.5, 0.38), "grove": Color(0.2, 0.48, 0.18),
	"idol": Color(0.75, 0.82, 0.9), "censer": Color(0.85, 0.35, 0.2),
	"well": Color(0.5, 0.68, 0.88), "effigy": Color(0.52, 0.46, 0.62),
	"ballista": Color(0.5, 0.36, 0.2), "hook": Color(0.36, 0.38, 0.42), "knife": Color(0.42, 0.44, 0.5)}
const TONES := {"wave": Color(0.95, 0.76, 0.4), "curse": Color(0.76, 0.42, 1.0),
	"won": Color(0.86, 0.9, 0.55), "lost": Color(0.88, 0.12, 0.07)}

var world: World
var prefs: Prefs                      # its `interface` is the HUD's size (main sets it; the settings change it live)
var _root: Control
var _over: CanvasLayer
var _top: Control                     # `_over`'s root
var _asked := 0.0                     # the interface size the HUD was last fitted for
var _scale := 1.0                     # the size it is drawn at: as asked, as far as the window's width allows
var _fonts := {}                      # Style's fonts -> the HUD's copies (`_sharp` rasterises them at its size)
var _sharp: Array[SystemFont] = []
var _shown := true
var _show_tween: Tween
var _life_orb: ShaderMaterial
var _mana_orb: ShaderMaterial
var _life_text: Label
var _mana_text: Label
var _gold: Label
var _wave_kicker: Label
var _wave_name: Label
var _progress: ShaderMaterial
var _progress_text: Label
var _call: Button
var _skip: Button                   # the grind's offer, while a wave is surely clean
var _pace: Button
var _slots := {}
var _slot_pics := {}
var _costs := {}
var _slot_keys: Array = []           # the build bar: the towers offered here, then the gate
var _slot_size := SLOT
var _spell_slots := {}                # spell -> [Button, veil Label, cost Label]
var _choices: VBoxContainer           # the breach offer and the salvage held, over the bar
var _choice_title: Label
var _choice_line: Label
var _choice_row: HBoxContainer
var _salvage_line: Label
var _salvage_sell: Button

var _banner: Control
var _banner_smoke: ShaderMaterial
var _banner_title: Label
var _banner_rule: Control
var _banner_line: Label
var _banner_tween: Tween
var _chronicle: VBoxContainer

var _leader: Control
var _leader_name: Label
var _leader_life: ShaderMaterial
var _leader_cast: ShaderMaterial
var _leader_cast_box: Control
var _leader_cast_text: Label

var _card: PanelContainer
var _card_style: StyleBoxFlat
var _card_iron: ShaderMaterial
var _card_kind: Label
var _card_pic: TextureRect
var _card_title: Label
var _pips: Array = []
var _stats := {}                      # row name -> [row label, now, next]
var _curse_box: Control
var _curse_bar: ShaderMaterial
var _curse_text: Label
var _upgrade: Button
var _sell: Button
var _mode: Button                   # the chosen tower's strategy: a press teaches the next owned one
var _attune: Button                 # attune the chosen tower, while it is not
var _charges: Label                 # its charges, once attuned
var _hymn_box: Control
var _hymn_bar: ShaderMaterial
var _hymn_text: Label
var _selected: Tower
var _portraits := {}                  # "kind:rank" -> [SubViewport, the turning pivot]
var _turning: Node3D

var _leader_kind: Label
var _hover: PanelContainer
var _hover_title: Label
var _hover_life: Label
var _hover_notes: VBoxContainer
var _hover_grid: GridContainer
var _hovered: Monster
var _hover_shown: Array = []          # the monster, strikes and movers the plate was filled for

var _goals_box: VBoxContainer         # the run's wager: each goal with its verdict's color
var _strikes: Label                   # while a boss walks: how many more strikes end the run
var _xp_bar: ShaderMaterial           # the level's gauge, a thin strip above the bar
var _xp_text: Label
var _wager: Button                    # a run's break: open the bonus wagers
var _wagers: Control                  # the stakes on the table, with their previews
var _wager_rows: VBoxContainer
var _wager_open := false


## Film mode: the bar and orbs sink away, leaving the battle and the banners.
func cinematic(on: bool, seconds := 1.0) -> void:
	_reveal(not on, seconds)


## H: the bar and orbs away, or back.
func toggle() -> void:
	_reveal(not _shown, 0.35)


## A title card over the picture: the banner, held for `hold` seconds.
func title_card(title: String, line: String, hold := 3.0) -> void:
	_show_banner(title, line, TONES["wave"], hold, 1.2)


func setup(w: World) -> void:
	world = w
	_slot_keys = (world.start["arsenal"]["towers"] as Array).duplicate()   # the bar's own list: the gate joins it
	if world.offers("gate"):
		_slot_keys.append("gate")
	_slot_size = min(SLOT, (BAR.x - 2 * INSET - 420.0 - GAP * (_slot_keys.size() - 1)) / max(_slot_keys.size(), 1))
	world.changed.connect(refresh)
	world.announce.connect(_announce)
	world.refused.connect(func(why: String): _chronicle_line(why, Color(1.0, 0.62, 0.45)))
	_build()
	if world.demo:
		_root.get_child(0).visible = true
	refresh()


## The build bar's keys, in the order of the number keys.
func slots() -> Array:
	return _slot_keys


func _reveal(on: bool, seconds: float) -> void:
	_shown = on
	if _show_tween:
		_show_tween.kill()
	if on:
		_root.visible = true
	_show_tween = create_tween().set_parallel()
	_show_tween.tween_property(self, "offset:y", 0.0 if on else 140.0, seconds) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT if on else Tween.EASE_IN)
	_show_tween.tween_property(_root, "modulate:a", 1.0 if on else 0.0, seconds)
	if not on:
		_show_tween.chain().tween_callback(func(): _root.visible = false)


func _build() -> void:
	_root = Control.new()
	_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.theme = _tooltips()
	add_child(_root)
	_over = CanvasLayer.new()
	_over.layer = layer + 1
	add_child(_over)
	var top := Control.new()
	top.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_over.add_child(top)
	_top = top

	_build_bar()
	_build_orbs()
	_build_slots()
	_build_spells()
	_build_choices(top)
	_build_info()
	_build_card()
	_build_banner(top)
	_build_leader(top)
	_build_run(top)
	_build_hover()
	_chronicle = VBoxContainer.new()
	_pin(_chronicle, 1.0, 0.0, Rect2(-620, 22, 596, 0))
	_chronicle.add_theme_constant_override("separation", 4)
	top.add_child(_chronicle)
	_fit()
	get_viewport().size_changed.connect(_fit)


# the bar: a dark rising from the bottom edge, then the iron bar centred on it
func _build_bar() -> void:
	var shade := TextureRect.new()
	shade.texture = _gradient([[0.0, Color(0, 0, 0, 0)], [0.45, Color(0, 0, 0, 0.32)], [1.0, Color(0, 0, 0, 0.9)]], true)
	shade.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	shade.stretch_mode = TextureRect.STRETCH_SCALE
	shade.anchor_left = 0.0
	shade.anchor_right = 1.0
	shade.anchor_top = 1.0
	shade.anchor_bottom = 1.0
	shade.offset_top = -SHADE
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(shade)
	var bar := ColorRect.new()
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/hud_panel.gdshader")
	m.set_shader_parameter("size", BAR)
	m.set_shader_parameter("spacing", SLOT + GAP)
	m.set_shader_parameter("rivet_from", INSET - GAP / 2)   # rivets in the gaps between the slots
	bar.material = m
	_pin(bar, 0.5, 1.0, Rect2(-BAR.x / 2, -LIFT - BAR.y, BAR.x, BAR.y))
	_root.add_child(bar)


func _build_orbs() -> void:
	var life := _orb(-1.0, Color(0.72, 0.04, 0.03), Color(1.0, 0.36, 0.16), "orb_life_frame")
	_life_orb = life[0]
	_life_text = life[1]
	_life_text.add_theme_font_size_override("font_size", 46)
	life[2].tooltip_text = "Life: each monster that reaches the sanctuary takes some. None left, and %s falls." % \
		world.start["location"]["name"]
	var mana := _orb(1.0, Color(0.06, 0.16, 0.78), Color(0.45, 0.62, 1.0), "orb_mana_frame")
	_mana_orb = mana[0]
	_mana_text = mana[1]
	_mana_text.add_theme_font_size_override("font_size", 38)
	mana[2].tooltip_text = "Mana: it wells back slowly, and your spells spend it."


## An orb at one end of the bar (`side` -1 left, 1 right): the glass, its sculpted frame over it, its number.
func _orb(side: float, liquid: Color, glow: Color, frame: String) -> Array:
	var centre := Vector2(side * (BAR.x / 2 - 6), -ORB_RISE)
	var glass := ColorRect.new()
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/orb.gdshader")
	m.set_shader_parameter("liquid", liquid)
	m.set_shader_parameter("glow", glow)
	m.set_shader_parameter("noise", _noise(0.012, 4))
	glass.material = m
	_pin(glass, 0.5, 1.0, Rect2(centre - Vector2(ORB, ORB) / 2, Vector2(ORB, ORB)))
	_root.add_child(glass)
	var size := ORB / 2 * 0.95 / FRAME_HOLE * 2
	var holder := TextureRect.new()
	holder.texture = load("res://assets/ui/%s.png" % frame)
	holder.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	holder.stretch_mode = TextureRect.STRETCH_SCALE
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_pin(holder, 0.5, 1.0, Rect2(centre - Vector2(size, size) / 2, Vector2(size, size)))
	_root.add_child(holder)
	var text := _label(Style.title_font(), 44, Style.PALE_GOLD)
	text.add_theme_constant_override("outline_size", 10)
	text.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.75))
	text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	text.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_pin(text, 0.5, 1.0, Rect2(centre - Vector2(ORB, ORB) / 2 + Vector2(0, 4), Vector2(ORB, ORB)))
	_root.add_child(text)
	return [m, text, glass]


func _build_slots() -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", GAP)
	var n := _slot_keys.size()
	_pin(row, 0.5, 1.0, Rect2(-BAR.x / 2 + INSET, -LIFT - BAR.y / 2 - _slot_size / 2, n * _slot_size + (n - 1) * GAP,
		_slot_size))
	_root.add_child(row)
	for i in n:
		var kind: String = _slot_keys[i]
		var b: Button
		if kind == "gate":
			b = _slot(str(i + 1), _icon("gate"), "Warded Gate (%d): bars an arch; walkers must break it, flyers pass over. "
				% (i + 1) + "Hold it, then click an arch.")
		else:
			var table: Dictionary = world.tower_table(kind)
			b = _slot(str(i + 1), _portrait(kind, 0, 176, kind == "pyre")[0].get_texture(),
				"%s (%d): %s" % [table["name"], i + 1, table["blurb"]])
		b.custom_minimum_size = Vector2(_slot_size, _slot_size)
		b.pressed.connect(func(): slot_pressed.emit(kind))
		var cost := _cost(b, _coin_icon(15))
		_slots[kind] = b
		_costs[kind] = cost
		row.add_child(b)


## The spells offered here, in a row over the bar's right end, in the order of their keys (Q W E R).
func _build_spells() -> void:
	var keys := []
	for key in SPELLS:
		if world.offers(key):
			keys.append(key)
	var size := 66.0
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", GAP)
	row.alignment = BoxContainer.ALIGNMENT_END
	var width := keys.size() * size + (keys.size() - 1) * GAP
	_pin(row, 0.5, 1.0, Rect2(BAR.x / 2 - INSET - width, -LIFT - BAR.y - size - 10, width, size))
	_root.add_child(row)
	for key in keys:
		var spell: Dictionary = world.start["spells"][key]
		var tip := "%s (%s): %s %d mana." % [spell["name"], SPELLS[key], spell["blurb"], int(world.spell_cost(key))]
		if float(spell["recharge"]) > 0.0:
			tip += " Then %d s to gather itself. Not while paused." % int(spell["recharge"])
		var b := _slot(SPELLS[key], _icon(key), tip)
		b.custom_minimum_size = Vector2(size, size)
		b.pressed.connect(func(): slot_pressed.emit("spell:" + key))
		var drop := ColorRect.new()
		var dm := ShaderMaterial.new()
		dm.shader = preload("res://shaders/orb.gdshader")
		dm.set_shader_parameter("liquid", Color(0.1, 0.25, 0.9))
		dm.set_shader_parameter("glow", Color(0.5, 0.7, 1.0))
		dm.set_shader_parameter("noise", _noise(0.05, 2))
		drop.material = dm
		var cost := _cost(b, drop)
		cost.text = str(int(world.spell_cost(key)))
		var veil := _label(Style.title_font(), 26, Style.PALE_GOLD)
		veil.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		veil.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		veil.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		veil.add_theme_constant_override("outline_size", 8)
		veil.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
		b.add_child(veil)
		_spell_slots[key] = [b, veil, cost]
		row.add_child(b)


## A picture for a slot without a tower portrait: its painted icon if there is one, else a glowing rune disc.
func _icon(key: String) -> Texture2D:
	var path := "res://assets/ui/%s.png" % key
	if ResourceLoader.exists(path):
		return load(path)
	var g := Gradient.new()
	var tone: Color = SPELL_TONES.get(key, Color(0.8, 0.7, 0.55))
	g.set_color(0, Color(tone * 1.2, 1.0))
	g.set_color(1, Color(tone * 0.15, 1.0))
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = Vector2(0.5, 0.5)
	t.fill_to = Vector2(1.0, 0.5)
	return t


## Over the bar: the sealed side entrance's offer while it stands, the salvage held while there is any.
func _build_choices(top: Control) -> void:
	_choices = VBoxContainer.new()
	_choices.add_theme_constant_override("separation", 6)
	_choices.alignment = BoxContainer.ALIGNMENT_END
	_pin(_choices, 0.5, 1.0, Rect2(-330, -LIFT - BAR.y - 250, 660, 236))
	_choices.mouse_filter = Control.MOUSE_FILTER_IGNORE
	top.add_child(_choices)
	_choice_title = _label(Style.title_font(), 26, Style.GOLD)
	_choice_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_choices.add_child(_choice_title)
	_choice_line = _label(Style.text_font(), 21, Style.BONE)
	_choice_line.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_choice_line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_choices.add_child(_choice_line)
	_choice_row = HBoxContainer.new()
	_choice_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_choice_row.alignment = BoxContainer.ALIGNMENT_CENTER
	_choice_row.add_theme_constant_override("separation", 10)
	_choices.add_child(_choice_row)
	var breach = world.start["breach"]
	if breach != null:
		var cash := _button("Open · +%d gold" % int(world.start["breach_cash"]))
		cash.pressed.connect(func(): order.emit("breach:cash"))
		_choice_row.add_child(cash)
		var trophy := _button("Open · trophy")
		if breach["claimed"] != null:
			trophy.text = "Trophy forfeited" if String(breach["claimed"]) == "cash" else "Trophy already claimed"
			trophy.disabled = true
		trophy.pressed.connect(func(): order.emit("breach:trophy"))
		_choice_row.add_child(trophy)
		var keep := _button("Keep sealed")
		keep.pressed.connect(func(): order.emit("breach:decline"))
		_choice_row.add_child(keep)
	var salvage := HBoxContainer.new()
	salvage.mouse_filter = Control.MOUSE_FILTER_IGNORE   # only its button takes clicks, not the row's whole width
	salvage.alignment = BoxContainer.ALIGNMENT_CENTER
	salvage.add_theme_constant_override("separation", 10)
	_choices.add_child(salvage)
	_salvage_line = _caps(16, Style.GOLD)
	salvage.add_child(_salvage_line)
	_salvage_sell = _button("Sell 1 for %d gold · V" % int(world.start["salvage_sale_gold"]))
	_salvage_sell.pressed.connect(func(): order.emit("salvage"))
	salvage.add_child(_salvage_sell)


func _refresh_choices() -> void:
	var st: Dictionary = world.state
	var breach = st["breach"]
	var offered: bool = breach != null and bool(breach["offered"]) and not world.demo
	_choice_title.visible = offered
	_choice_line.visible = offered
	_choice_row.visible = offered
	if offered:
		var spec: Dictionary = world.start["breach"]
		_choice_title.text = "Sealed entrance: %s" % spec["name"]
		var pack := []
		for g in spec["pack"]:
			pack.append("%d %s" % [int(g["count"]), world.monster_table(String(g["kind"]))["name"]])
		_choice_line.text = "%s\nNext wave: %s (%s) · %s. Clear every side enemy for the chosen reward; a trophy is " % [
			spec["blurb"], spec["elite_name"], world.monster_table(String(spec["elite"]["kind"]))["name"],
			", ".join(pack)] + "kept only on victory."
	var held := int(st["salvage"])
	_salvage_line.get_parent().visible = held > 0 and world.outcome == "" and not world.demo
	_salvage_line.text = "Salvage held: %d" % held
	_salvage_sell.visible = st["break_left"] != null and not world.demo
	if not _salvage_sell.visible:
		_salvage_line.text += " · bank on victory, sell at a break"


## A slot: a sunken well with its picture, its key top left.
func _slot(key: String, picture: Texture2D, tip: String) -> Button:
	var b := Button.new()
	b.custom_minimum_size = Vector2(SLOT, SLOT)
	b.focus_mode = Control.FOCUS_NONE
	b.tooltip_text = tip
	b.add_theme_stylebox_override("normal", Style.well(Style.BRONZE))
	b.add_theme_stylebox_override("hover", Style.well(Color(1.0, 0.85, 0.5)))
	b.add_theme_stylebox_override("pressed", Style.well(Style.PALE_GOLD))
	b.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	var pic := TextureRect.new()
	pic.texture = picture
	pic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	pic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	pic.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in [SIDE_LEFT, SIDE_TOP]:
		pic.set_offset(side, 4)
	for side in [SIDE_RIGHT, SIDE_BOTTOM]:
		pic.set_offset(side, -4)
	pic.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.add_child(pic)
	_slot_pics[b] = pic
	var k := _caps(16, Style.PALE_GOLD)
	k.text = key
	k.position = Vector2(8, 5)
	k.add_theme_constant_override("outline_size", 5)
	k.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	b.add_child(k)
	b.mouse_entered.connect(func(): pic.self_modulate = Color(1.3, 1.22, 1.1))
	b.mouse_exited.connect(func(): pic.self_modulate = Color.WHITE)
	return b


## A price in a slot's lower right corner, after a small icon.
func _cost(slot: Button, icon: Control) -> Label:
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_END
	row.add_theme_constant_override("separation", 3)
	row.anchor_left = 0.0
	row.anchor_right = 1.0
	row.anchor_top = 1.0
	row.anchor_bottom = 1.0
	row.offset_left = 6
	row.offset_right = -7
	row.offset_top = -24
	row.offset_bottom = -5
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	slot.add_child(row)
	icon.custom_minimum_size = Vector2(14, 14)
	icon.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(icon)
	var l := _label(Style.small_font(), 18, Style.GOLD)
	l.add_theme_constant_override("outline_size", 6)
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.95))
	row.add_child(l)
	return l


# the wave, its progress, the gold, the summons and the pace, right of the slots
func _build_info() -> void:
	var n := _slot_keys.size()
	var left := -BAR.x / 2 + INSET + n * _slot_size + (n - 1) * GAP + 18
	var right := BAR.x / 2 - INSET - 22   # the angel's wing reaches further in
	var rule := TextureRect.new()
	rule.texture = _gradient([[0.0, Color(Style.GOLD, 0.0)], [0.5, Color(Style.GOLD, 0.8)], [1.0, Color(Style.GOLD, 0.0)]], true)
	rule.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	rule.stretch_mode = TextureRect.STRETCH_SCALE
	rule.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_pin(rule, 0.5, 1.0, Rect2(left - 10, -LIFT - BAR.y + 20, 1, BAR.y - 40))
	_root.add_child(rule)
	var info := VBoxContainer.new()
	info.add_theme_constant_override("separation", 5)
	info.add_theme_constant_override("separation", 2)
	_pin(info, 0.5, 1.0, Rect2(left, -LIFT - BAR.y + 12, right - left, BAR.y - 24))
	_root.add_child(info)

	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 10)
	info.add_child(head)
	_wave_name = _label(Style.text_font(), 22, Style.GOLD)
	_wave_name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_wave_name.clip_text = true
	_wave_name.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS   # a long line beside many slots
	head.add_child(_wave_name)
	var coin := _coin_icon(26)
	coin.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	head.add_child(coin)
	_gold = _label(Style.title_font(), 28, Style.PALE_GOLD)
	head.add_child(_gold)

	var prog := HBoxContainer.new()
	prog.add_theme_constant_override("separation", 10)
	info.add_child(prog)
	_wave_kicker = _caps(15, Style.DIM_GOLD)   # beside the gauge: the name above gets the row's width
	_wave_kicker.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	prog.add_child(_wave_kicker)
	var bar := ColorRect.new()
	_progress = _gauge(bar, Color(0.75, 0.16, 0.08), Vector2(0, 10))
	bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	prog.add_child(bar)
	_progress_text = _caps(14, Style.BONE)
	_progress_text.custom_minimum_size = Vector2(96, 0)
	_progress_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	prog.add_child(_progress_text)

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	info.add_child(row)
	_call = _button("Summon · Space")
	_call.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_call.pressed.connect(func(): order.emit("wave"))
	row.add_child(_call)
	_skip = _button("")
	_skip.custom_minimum_size = Vector2(150, 0)
	_skip.pressed.connect(func(): order.emit("skip"))
	row.add_child(_skip)
	_pace = _button("")
	_pace.custom_minimum_size = Vector2(118, 0)
	_pace.pressed.connect(func(): order.emit("pace"))
	row.add_child(_pace)
	set_pace(false)


# the chosen tower's card, above the bar's left end: its portrait, rank, what an upgrade brings, its orders
func _build_card() -> void:
	_card = PanelContainer.new()
	_card_style = StyleBoxFlat.new()          # no face: only the glow round the iron
	_card_style.bg_color = Color(0, 0, 0, 0)
	_card_style.shadow_size = 18
	_card.add_theme_stylebox_override("panel", _card_style)
	_pin(_card, 0.5, 1.0, Rect2(-BAR.x / 2 + INSET + 10, -LIFT - BAR.y - 10, 490, 0))
	_card.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_root.add_child(_card)
	var iron := ColorRect.new()
	_card_iron = ShaderMaterial.new()
	_card_iron.shader = preload("res://shaders/hud_panel.gdshader")
	_card_iron.set_shader_parameter("engraved", false)
	_card_iron.set_shader_parameter("chamfer", 14.0)
	_card_iron.set_shader_parameter("trim", 4.0)
	iron.material = _card_iron
	iron.resized.connect(func(): _card_iron.set_shader_parameter("size", iron.size))
	_card.add_child(iron)
	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 14)
	_card.add_child(margin)
	var cols := HBoxContainer.new()
	cols.add_theme_constant_override("separation", 14)
	margin.add_child(cols)
	var frame := PanelContainer.new()
	frame.add_theme_stylebox_override("panel", Style.well(Style.BRONZE))
	frame.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	cols.add_child(frame)
	_card_pic = TextureRect.new()
	_card_pic.custom_minimum_size = Vector2(124, 124)
	_card_pic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_card_pic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	frame.add_child(_card_pic)

	var body := VBoxContainer.new()
	body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 6)
	cols.add_child(body)
	var head := HBoxContainer.new()
	body.add_child(head)
	_card_title = _caps(18, Style.GOLD)
	_card_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(_card_title)
	var pips := HBoxContainer.new()
	pips.add_theme_constant_override("separation", 2)
	pips.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	head.add_child(pips)
	for i in 3:
		pips.add_child(_pip())
	_card_kind = _caps(13, Style.DIM_GOLD)
	body.add_child(_card_kind)

	var grid := GridContainer.new()
	grid.columns = 3
	grid.add_theme_constant_override("h_separation", 14)
	grid.add_theme_constant_override("v_separation", 1)
	body.add_child(grid)
	for row in ["damage", "rate", "reach", "chill"]:
		var name := _caps(14, Style.DIM_GOLD)
		name.text = {"damage": "Damage", "rate": "Shots", "reach": "Reach", "chill": "Chill"}[row]
		name.custom_minimum_size = Vector2(70, 0)
		var now := _label(Style.text_font(), 19, Style.BONE)
		now.custom_minimum_size = Vector2(56, 0)
		var next := _label(Style.text_font(), 19, Color(0.75, 0.9, 0.5))
		for l in [name, now, next]:
			l.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			grid.add_child(l)
		_stats[row] = [name, now, next]

	_curse_box = VBoxContainer.new()
	_curse_box.add_theme_constant_override("separation", 3)
	body.add_child(_curse_box)
	_curse_text = _caps(14, Style.CURSE)
	_curse_box.add_child(_curse_text)
	var cb := ColorRect.new()
	_curse_bar = _gauge(cb, Color(0.55, 0.2, 0.9), Vector2(0, 8))
	_curse_box.add_child(cb)


	_hymn_box = VBoxContainer.new()
	_hymn_box.add_theme_constant_override("separation", 3)
	body.add_child(_hymn_box)
	_hymn_text = _caps(12, SPELL_TONES["hymn"])
	_hymn_box.add_child(_hymn_text)
	var hb := ColorRect.new()
	_hymn_bar = _gauge(hb, SPELL_TONES["hymn"] * 0.8, Vector2(0, 8))
	_hymn_box.add_child(hb)

	var orders := HBoxContainer.new()
	orders.add_theme_constant_override("separation", 6)
	body.add_child(orders)
	_upgrade = _button("")
	_upgrade.icon_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_upgrade.add_theme_constant_override("icon_max_width", 16)
	_upgrade.pressed.connect(func(): order.emit("upgrade"))
	orders.add_child(_upgrade)
	_sell = _button("")
	_sell.pressed.connect(func(): order.emit("sell"))
	orders.add_child(_sell)
	_mode = _button("")
	_mode.pressed.connect(cycle_mode)
	orders.add_child(_mode)
	_attune = _button("")
	_attune.pressed.connect(func(): order.emit("attune"))
	orders.add_child(_attune)
	_charges = _caps(15, Style.DIM_GOLD)
	orders.add_child(_charges)

	_card.visible = false


func _pip() -> Control:
	var holder := Control.new()
	holder.custom_minimum_size = Vector2(16, 16)
	var p := Panel.new()
	var sb := StyleBoxFlat.new()
	sb.set_border_width_all(1)
	sb.border_color = Style.GOLD
	p.add_theme_stylebox_override("panel", sb)
	p.size = Vector2(9, 9)
	p.position = Vector2(3.5, 3.5)
	p.pivot_offset = Vector2(4.5, 4.5)
	p.rotation = PI / 4
	holder.add_child(p)
	_pips.append(sb)
	return holder


# wave banners across the upper third: smoke behind, the title, a gilt rule, the line
func _build_banner(top: Control) -> void:
	_banner = Control.new()
	_banner.anchor_left = 0.0
	_banner.anchor_right = 1.0
	_banner.offset_top = 120
	_banner.offset_bottom = 400
	_banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	top.add_child(_banner)
	var smoke := ColorRect.new()
	smoke.set_anchors_preset(Control.PRESET_FULL_RECT)
	smoke.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_banner_smoke = ShaderMaterial.new()
	_banner_smoke.shader = preload("res://shaders/hud_banner.gdshader")
	_banner_smoke.set_shader_parameter("noise", _noise(0.006, 5))
	smoke.material = _banner_smoke
	_banner.add_child(smoke)
	var words := VBoxContainer.new()
	words.set_anchors_preset(Control.PRESET_FULL_RECT)
	words.alignment = BoxContainer.ALIGNMENT_CENTER
	words.add_theme_constant_override("separation", 2)
	words.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_banner.add_child(words)
	_banner_title = _label(Style.display_font(), 72, Style.GOLD)
	_banner_title.uppercase = true
	_banner_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_banner_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART   # a long title wraps rather than runs off
	_banner_title.add_theme_constant_override("outline_size", 12)
	_banner_title.add_theme_color_override("font_outline_color", Color(0.04, 0.02, 0.0, 0.85))
	words.add_child(_banner_title)
	_banner_rule = _rule(560)
	words.add_child(_banner_rule)
	_banner_line = _label(Style.text_font(), 30, Style.BONE)
	_banner_line.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_banner_line.add_theme_constant_override("outline_size", 8)
	_banner_line.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	words.add_child(_banner_line)
	_banner.modulate.a = 0.0


## A thin gilt rule fading out at both ends, a small lozenge at its middle.
func _rule(width: float) -> Control:
	var holder := Control.new()
	holder.custom_minimum_size = Vector2(0, 16)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var line := TextureRect.new()
	line.texture = _gradient([[0.0, Color(1, 1, 1, 0)], [0.5, Color(1, 1, 1, 1)], [1.0, Color(1, 1, 1, 0)]], false)
	line.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	line.stretch_mode = TextureRect.STRETCH_SCALE
	line.anchor_left = 0.5
	line.anchor_right = 0.5
	line.offset_left = -width / 2
	line.offset_right = width / 2
	line.offset_top = 7
	line.offset_bottom = 9
	holder.add_child(line)
	var gem := ColorRect.new()
	gem.size = Vector2(9, 9)
	gem.pivot_offset = Vector2(4.5, 4.5)
	gem.rotation = PI / 4
	gem.anchor_left = 0.5
	gem.anchor_right = 0.5
	gem.position = Vector2(-4.5, 3.5)
	holder.add_child(gem)
	return holder


# a leader on screen gets a bar at the top, as a unique monster did in Diablo II: its name, its life, its curse
func _build_leader(top: Control) -> void:
	_leader = Control.new()
	_pin(_leader, 0.5, 0.0, Rect2(-360, 0, 720, 170))
	_leader.mouse_filter = Control.MOUSE_FILTER_IGNORE
	top.add_child(_leader)
	var back := TextureRect.new()
	var dark := _gradient([[0.0, Color(0.02, 0.0, 0.03, 0.78)], [0.6, Color(0.02, 0.0, 0.03, 0.5)], [1.0, Color(0, 0, 0, 0)]], true)
	dark.fill = GradientTexture2D.FILL_RADIAL
	dark.fill_from = Vector2(0.5, 0.3)
	dark.fill_to = Vector2(1.0, 0.3)
	dark.width = 256
	back.texture = dark
	back.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	back.stretch_mode = TextureRect.STRETCH_SCALE
	back.set_anchors_preset(Control.PRESET_FULL_RECT)
	back.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_leader.add_child(back)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 4)
	col.alignment = BoxContainer.ALIGNMENT_BEGIN
	_pin(col, 0.5, 0.0, Rect2(-240, 14, 480, 0))
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_leader.add_child(col)
	_leader_name = _label(Style.title_font(), 32, Color(0.95, 0.8, 1.0))
	_leader_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_leader_name.add_theme_constant_override("outline_size", 10)
	_leader_name.add_theme_color_override("font_outline_color", Color(0.12, 0.0, 0.2, 0.85))
	col.add_child(_leader_name)
	var life := ColorRect.new()
	_leader_life = _gauge(life, Color(0.78, 0.07, 0.04), Vector2(480, 16))
	col.add_child(life)

	_leader_kind = _caps(11, Color(0.82, 0.74, 0.9))
	_leader_kind.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(_leader_kind)
	_leader_cast_box = VBoxContainer.new()
	_leader_cast_box.add_theme_constant_override("separation", 3)
	col.add_child(_leader_cast_box)
	var cast := ColorRect.new()
	_leader_cast = _gauge(cast, Color(0.62, 0.25, 1.0), Vector2(320, 9))
	cast.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_leader_cast_box.add_child(cast)
	_leader_cast_text = _caps(16, Color(0.86, 0.68, 1.0))
	_leader_cast_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_leader_cast_text.add_theme_constant_override("outline_size", 6)
	_leader_cast_text.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	_leader_cast_box.add_child(_leader_cast_text)
	_leader.modulate.a = 0.0


# a monster under the mouse: a dark plate by the cursor with its name, life, armor and tags, and the hits table
# the run above the battle: its wager's lines, the strikes a boss has left, the level's gauge, the wagers
func _build_run(top: Control) -> void:
	_goals_box = VBoxContainer.new()
	_goals_box.add_theme_constant_override("separation", 2)
	_pin(_goals_box, 0.0, 0.0, Rect2(24, 22, 520, 0))
	_goals_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	top.add_child(_goals_box)
	for g in world.goals:
		var line := _caps(17, Style.BONE)
		line.name = "goal_%s" % String(g["key"])
		_goals_box.add_child(line)
	_strikes = _caps(18, Color(1.0, 0.45, 0.35))
	_pin(_strikes, 0.0, 0.0, Rect2(24, 22 + 3 * 24, 520, 0))
	_strikes.mouse_filter = Control.MOUSE_FILTER_IGNORE
	top.add_child(_strikes)

	var xp := ColorRect.new()
	_xp_bar = _gauge(xp, Color(0.45, 0.35, 0.85), Vector2(0, 5))
	_pin(xp, 0.5, 1.0, Rect2(-BAR.x / 2, -LIFT - BAR.y - 9, BAR.x, 5))
	_root.add_child(xp)
	_xp_text = _caps(15, Style.DIM_GOLD)
	_pin(_xp_text, 0.5, 1.0, Rect2(-BAR.x / 2, -LIFT - BAR.y - 32, 300, 0))
	_root.add_child(_xp_text)

	_wager = _button("Wager")
	_wager.custom_minimum_size = Vector2(118, 0)
	_wager.pressed.connect(_open_wagers)
	_pin(_wager, 1.0, 1.0, Rect2(-142, -LIFT - BAR.y - 52, 118, 0))
	_root.add_child(_wager)

	_wagers = PanelContainer.new()
	_pin(_wagers, 0.5, 0.5, Rect2(-330, -190, 330, 190))
	_wagers.visible = false
	_over.add_child(_wagers)
	_wager_rows = VBoxContainer.new()
	_wager_rows.add_theme_constant_override("separation", 10)
	_wagers.add_child(_wager_rows)


func _build_hover() -> void:
	_hover = PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.035, 0.03, 0.034, 0.94)
	sb.border_color = Style.BRONZE
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(2)
	sb.content_margin_left = 14
	sb.content_margin_right = 14
	sb.content_margin_top = 8
	sb.content_margin_bottom = 10
	sb.shadow_color = Color(0, 0, 0, 0.6)
	sb.shadow_size = 10
	_hover.add_theme_stylebox_override("panel", sb)
	_hover.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hover.visible = false
	_root.add_child(_hover)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 3)
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hover.add_child(col)
	_hover_title = _label(Style.title_font(), 24, Style.GOLD)
	col.add_child(_hover_title)
	_hover_life = _label(Style.text_font(), 18, Style.BONE)
	col.add_child(_hover_life)
	_hover_notes = VBoxContainer.new()
	_hover_notes.add_theme_constant_override("separation", 1)
	col.add_child(_hover_notes)
	var rule := TextureRect.new()
	rule.texture = _gradient([[0.0, Color(Style.BRONZE, 0.0)], [0.5, Color(Style.BRONZE, 0.9)], [1.0, Color(Style.BRONZE, 0.0)]], false)
	rule.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	rule.stretch_mode = TextureRect.STRETCH_SCALE
	rule.custom_minimum_size = Vector2(0, 1)
	col.add_child(rule)
	_hover_grid = GridContainer.new()
	_hover_grid.columns = 4
	_hover_grid.add_theme_constant_override("h_separation", 14)
	_hover_grid.add_theme_constant_override("v_separation", 0)
	col.add_child(_hover_grid)


## The monster under the mouse at `at` (viewport pixels), or null: its plate shows by the cursor, its life kept
## current. The hits are the server's (the battle's `hits` table): what each rank of each tower here deals it.
func hover(m: Monster, at := Vector2.ZERO) -> void:
	if m == null or not is_instance_valid(m) or not m.alive():
		_hovered = null
		_hover_shown = []
		_hover.visible = false
		return
	var shown := [m, m.strikes, m.moved]   # a return or a hook changes what the plate says of it
	if shown != _hover_shown:
		_hover_shown = shown
		_fill_hover(m)
	_hovered = m
	_hover.visible = true
	_hover_life.text = "Life %d / %d" % [ceili(m.hp), ceili(m.max_hp)]
	var armor := int(m.stats["armor"])
	if armor > 0:
		_hover_life.text += "   ·   Armor %d" % armor
	_hover.reset_size()
	var view := get_viewport().get_visible_rect().size
	var size := _hover.get_combined_minimum_size()
	var pos := at + Vector2(26, 22)
	if pos.x + size.x > view.x - 8:
		pos.x = at.x - 26 - size.x
	pos.y = clampf(pos.y, 8, view.y - size.y - LIFT - BAR.y - 8)
	_hover.position = pos


## The monster the plate shows, or null.
func hovered() -> Monster:
	return _hovered if _hover.visible else null


## The plate's words, line by line (the tests read them).
func hover_text() -> String:
	var out := [_hover_title.text, _hover_life.text]
	for l in _hover_notes.get_children():
		out.append((l as Label).text)
	var row := []
	for l in _hover_grid.get_children():
		row.append((l as Label).text)
		if row.size() == _hover_grid.columns:
			out.append(" ".join(row).strip_edges())
			row = []
	return "\n".join(out)


func _fill_hover(m: Monster) -> void:
	var table: Dictionary = m.stats
	_hover_title.text = m.title()
	_hover_title.add_theme_color_override("font_color", Color(0.9, 0.72, 1.0) if m.leader else Style.GOLD)
	for c in _hover_notes.get_children():
		c.free()
	var tags := [["Protected", table["protected"], Color(0.62, 0.62, 0.66)],
		["Vulnerable", table["vulnerable"], Color(0.95, 0.55, 0.4)]]
	for tag in tags:
		if (tag[1] as Array).is_empty():
			continue
		var names := []
		for e in tag[1]:
			names.append(String(e).capitalize())
		var l := _caps(12, tag[2])
		l.text = "%s: %s" % [tag[0], ", ".join(names)]
		_hover_notes.add_child(l)
	var traits := []
	if bool(table["flying"]):
		traits.append("Flies")
	if m.boss:
		traits.append("Boss · %d %s" % [m.strikes, "strike" if m.strikes == 1 else "strikes"])
	if m.moved & 1:
		traits.append("Hooked once")
	if not traits.is_empty():
		var l := _caps(12, Style.DIM_GOLD)
		l.text = " · ".join(traits)
		_hover_notes.add_child(l)
	for c in _hover_grid.get_children():
		c.free()
	var hits: Dictionary = table["hits"]
	if hits.is_empty():
		return
	var head := _caps(11, Style.DIM_GOLD)
	head.text = "Your hits"
	_hover_grid.add_child(head)
	for r in 3:
		var n := _caps(11, Style.DIM_GOLD)
		n.text = NUMERALS[r]
		n.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		_hover_grid.add_child(n)
	for kind in hits:
		var tower: Dictionary = world.tower_table(kind)
		var name := _label(Style.text_font(), 17, ELEMENT_TONES.get(String(tower["element"]), Style.BONE))
		name.text = String(tower["name"])
		_hover_grid.add_child(name)
		for r in 3:
			var felt := int(hits[kind][r])
			var dealt := int(round(float(tower["levels"][r]["damage"])))
			var v := _label(Style.text_font(), 17, Style.BONE if felt == dealt else
				(Color(0.95, 0.5, 0.38) if felt < dealt else Color(0.7, 0.92, 0.5)))
			v.text = str(felt)
			v.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
			v.custom_minimum_size = Vector2(30, 0)
			_hover_grid.add_child(v)


## A tower's portrait: its model with its fire and glow, a cool key light and a warm rim, framed from three
## quarters in front on its upper part. A `live` one keeps rendering, so its flame moves.
func _portrait(kind: String, rank: int, px: int, live: bool) -> Array:
	var key := "%s:%d:%d" % [kind, rank, px]
	if _portraits.has(key):
		return _portraits[key]
	var vp := SubViewport.new()
	vp.size = Vector2i(px, px)
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS if live else SubViewport.UPDATE_ONCE
	add_child(vp)
	var pivot := Node3D.new()
	vp.add_child(pivot)
	var model := Models.make(Tower.model_name(kind, rank))
	pivot.add_child(model)
	Tower.dress_fx(model, kind, rank)
	var box := _bounds(model)
	var top := box.end.y + (1.0 if kind == "pyre" else 0.15)
	var span := (top - box.position.y) * 0.8
	var centre := Vector3(box.get_center().x, top - span * 0.46, box.get_center().z)
	var width := Vector2(box.size.x, box.size.z).length()
	var cam := Camera3D.new()
	cam.fov = 24
	vp.add_child(cam)
	var yaw := deg_to_rad(32)
	var pitch := deg_to_rad(12)
	var toward := Vector3(sin(yaw) * cos(pitch), sin(pitch), -cos(yaw) * cos(pitch))
	var half_view := tan(deg_to_rad(cam.fov) / 2)
	var dist := maxf(span * 1.08, width) * 0.6 / half_view
	cam.look_at_from_position(centre + toward * dist, centre)
	# a glow behind it in the tower's own colour, so the dark stone stands off the dark
	var back := MeshInstance3D.new()
	var quad := QuadMesh.new()
	var behind := dist + width
	quad.size = Vector2.ONE * behind * half_view * 2.4
	back.mesh = quad
	var bm := StandardMaterial3D.new()
	bm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	var hue: Color = TOWER_HUES[kind]
	var glow := GradientTexture2D.new()
	glow.gradient = Gradient.new()
	glow.gradient.colors = PackedColorArray([hue, Color(0.02, 0.018, 0.022)])
	glow.fill = GradientTexture2D.FILL_RADIAL
	glow.fill_from = Vector2(0.5, 0.42)
	glow.fill_to = Vector2(0.5, 0.95)
	bm.albedo_texture = glow
	back.material_override = bm
	back.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	vp.add_child(back)
	back.look_at_from_position(centre - toward * width, centre + toward * dist)
	back.rotate_object_local(Vector3.UP, PI)
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
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.02, 0.018, 0.022)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.42, 0.44, 0.55)
	env.ambient_light_energy = 1.1
	env.glow_enabled = true
	env.glow_intensity = 0.8
	env.glow_hdr_threshold = 1.0
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.45
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	_portraits[key] = [vp, pivot]
	return _portraits[key]


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


func refresh() -> void:
	_life_orb.set_shader_parameter("level", float(world.lives) / world.start_lives)
	_life_text.text = str(world.lives)
	_gold.text = str(world.gold)
	var total: int = world.waves().size()
	if world.wave < 0:
		_wave_kicker.text = "%d waves come" % total
		_wave_name.text = "Build beside the lanes"
		_progress.set_shader_parameter("fill", 0.0)
		_progress_text.text = ""
	else:
		var w: Dictionary = world.waves()[world.wave]
		_wave_kicker.text = "Wave %s · %s" % [NUMERALS[world.wave], NUMERALS[total - 1]]
		_wave_name.text = w["name"]
		var count := 0
		for g in world.roster(world.wave):
			count += int(g["count"])
		var done: int = world.slain.get(world.wave, 0)
		_progress.set_shader_parameter("fill", min(1.0, float(done) / max(count, 1)))
		_progress_text.text = "%d / %d slain" % [min(done, count), count]
	_call.disabled = not world.can_call() or world.demo
	var bonus := int(world.state["early_bonus"])
	_call.text = "Summon · Space" + ("  +%d" % bonus if bonus > 0 else "")
	var offer = world.state.get("skip_offer")
	_skip.visible = offer is Dictionary and not (offer as Dictionary).is_empty() and not world.demo \
		and world.outcome == ""
	if _skip.visible:
		_skip.text = "Skip · G  +%d" % int((offer as Dictionary)["bonus"])
	for kind in _slot_keys:
		var cost := int(world.state["door_cost"]) if kind == "gate" else world.tower_cost(kind)
		_costs[kind].text = str(cost)
		var poor: bool = world.gold < cost
		_costs[kind].add_theme_color_override("font_color", Color(0.9, 0.2, 0.12) if poor else Style.GOLD)
		_slot_pics[_slots[kind]].modulate = Color(0.62, 0.58, 0.58) if poor else Color.WHITE
	_refresh_choices()
	_refresh_card()
	_refresh_run()


## The run's lines, every frame: each goal in its verdict's color, a boss's strikes, the level's gauge, and the
## wager button while a run's break is open.
func _refresh_run() -> void:
	var run := bool(world.start.get("run", false))
	_goals_box.visible = run and not world.goals.is_empty()
	_xp_text.visible = run
	for g in world.goals:
		var line := _goals_box.get_node_or_null("goal_%s" % String(g["key"])) as Label
		if line == null:
			continue
		match String(g["verdict"]):
			"met":
				line.add_theme_color_override("font_color", Style.GOLD)
				line.text = "✓  %s" % String(g["line"])
			"failed":
				line.add_theme_color_override("font_color", Color(0.62, 0.5, 0.45))
				line.text = "✗  %s" % String(g["line"])
			_:
				line.add_theme_color_override("font_color", Style.BONE)
				line.text = "·  %s" % String(g["line"])
	var strikes := 0
	if run and world.boss_out():
		var each := int(world.start.get("boss_strike_lives", 5))
		strikes = int(ceil(float(world.lives) / max(each, 1)))
	_strikes.visible = strikes > 0
	if strikes > 0:
		_strikes.text = "%d more strike%s end%s the run" % [strikes, "" if strikes == 1 else "s",
			"s" if strikes == 1 else ""]
	if world.xp_next > 0:
		_xp_bar.set_shader_parameter("fill", clampf(world.xp / world.xp_next, 0.0, 1.0))
		_xp_text.text = "Level %d · %d of %d" % [world.xp_level, int(world.xp), int(world.xp_next)]
	var open := run and world.state["break_left"] != null and not world.demo and world.outcome == ""
	_wager.visible = open and not _wager_open
	if not open and _wager_open:
		_wagers.visible = false
		_wager_open = false


## The bonus wagers on the table: each stake's pack and price, a finger on each.
func _open_wagers() -> void:
	if _wager_open:
		return
	_wager_open = true
	for child in _wager_rows.get_children():
		child.queue_free()
	var title := _caps(19, Style.GOLD)
	title.text = "Wager a bonus wave"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_wager_rows.add_child(title)
	var table: Dictionary = await Net.ask("summon_preview", {}).done
	if table.is_empty():
		_wager_open = false
		return
	for row in table["stakes"]:
		var words := Ui.label(String(row["words"]), 18, Style.BONE)
		words.custom_minimum_size = Vector2(560, 0)
		words.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_wager_rows.add_child(words)
		var take := _button("Summon stake %d · %d gold" % [int(row["stake"]), int(row["wager"])])
		take.disabled = world.gold < int(row["wager"])
		take.pressed.connect(func(): _summon(int(row["stake"])))
		_wager_rows.add_child(take)
	var shut := _button("Not now")
	shut.pressed.connect(_close_wagers)
	_wager_rows.add_child(shut)
	_wagers.visible = true


func _summon(stake: int) -> void:
	_close_wagers()
	order.emit("summon:%d" % stake)


func _close_wagers() -> void:
	_wagers.visible = false
	_wager_open = false


func _process(delta: float) -> void:
	if prefs.interface != _asked:
		_fit()
	# the side entrance's offer and the salvage stand above the chosen tower's card, never over its orders
	var lift := _card.get_combined_minimum_size().y + 8.0 if _card.visible else 0.0
	if _spell_slots.size() > 2:   # three or four spells reach in from the right as far as the middle's lines
		lift = maxf(lift, 76.0)
	_choices.offset_bottom = -LIFT - BAR.y - 14.0 - lift
	_choices.offset_top = _choices.offset_bottom - 236.0
	_mana_orb.set_shader_parameter("level", world.mana / max(world.mana_max, 1.0))
	_mana_text.text = str(int(world.mana))
	for key in _spell_slots:
		var parts: Array = _spell_slots[key]
		var left := world.recharge(key)
		var ready: bool = world.mana >= world.spell_cost(key) and left <= 0.0 and not world.paused
		_slot_pics[parts[0]].modulate = Color.WHITE if ready else Color(0.5, 0.48, 0.55)
		parts[1].text = str(ceili(left)) if left > 0.0 else ""
	if _selected and is_instance_valid(_selected):
		_refresh_card()
	if _turning:
		_turning.rotate_y(delta * 0.35)
	_refresh_leader(delta)


func set_pace(fast: bool) -> void:
	_pace.text = "PACE 2× · F" if fast else "PACE 1× · F"


func select(t: Tower) -> void:
	_selected = t
	_refresh_card()


func _refresh_card() -> void:
	var t := _selected
	var was := _card.visible
	_card.visible = t != null and is_instance_valid(t) and not t.removed
	if not _card.visible:
		_show_portrait(false)
		_turning = null
		return
	var portrait := _portrait(t.kind, t.rank, 248, true)
	if _turning != portrait[1]:                 # another tower or rank: only the portrait on show keeps rendering
		_show_portrait(false)
		_card_pic.texture = portrait[0].get_texture()
		_turning = portrait[1]
		_show_portrait(true)
		_card_title.text = t.title()
		for i in 3:
			_pips[i].bg_color = Style.GOLD if i <= t.rank else Color(0.08, 0.06, 0.05)
		var element: String = world.tower_table(t.kind)["element"]
		_card_kind.text = "%s damage · rank %s" % [element, NUMERALS[t.rank]]
		_card_kind.add_theme_color_override("font_color", ELEMENT_TONES[element])
	var levels: Array = world.tower_table(t.kind)["levels"]
	var lv: Dictionary = levels[t.rank]
	var up: Dictionary = levels[t.rank + 1] if t.rank + 1 < levels.size() else {}
	_stat("damage", "%d" % int(lv["damage"]), "%d" % int(up["damage"]) if up else "")
	_stat("rate", "%s/s" % String.num(float(lv["rate"]), 2), "%s/s" % String.num(float(up["rate"]), 2) if up else "")
	_stat("reach", "%.1f" % t.reach, "%.1f" % float(up["range"]) if up else "")
	_stat("chill", "%d%%" % int(100 * float(lv["chill"])), "%d%%" % int(100 * float(up["chill"])) if up else "")
	for l in _stats["chill"]:
		l.visible = float(lv["chill"]) > 0.0
	var cursed := t.cursed()
	_curse_box.visible = cursed
	if cursed:
		var names := []
		for c in t.curses:
			names.append(String(world.start["curses"][c]["name"]))
		_curse_text.text = "%s · %d s" % [" · ".join(names), ceili(t.curse_left())]
		var longest := 1.0
		for c in t.curses:
			longest = max(longest, float(world.start["curses"][c]["duration"]))
		_curse_bar.set_shader_parameter("fill", t.curse_left() / longest)
	_hymn_box.visible = t.hymn > 0.0
	if t.hymn > 0.0:
		_hymn_text.text = "%s · %d s" % [world.start["spells"]["hymn"]["name"], ceili(t.hymn)]
		_hymn_bar.set_shader_parameter("fill", t.hymn / maxf(float(world.start["spells"]["hymn"]["lasting"]), t.hymn))
	_card_iron.set_shader_parameter("curse", 1.0 if cursed else 0.0)
	_card_style.shadow_color = Color(0.5, 0.12, 0.9, 0.5) if cursed else Color(0, 0, 0, 0.6)
	if t.upgrade_cost != null:
		var cost := int(t.upgrade_cost)
		_upgrade.icon = null if t.needs != null else COIN   # a coin only beside a price
		if t.needs != null:
			_upgrade.text = "NEEDS A SKILL · K"
			_upgrade.tooltip_text = "Learn the next rank in the skill tree."
			_upgrade.disabled = true
		else:
			_upgrade.text = "UPGRADE · U   %d" % cost
			_upgrade.tooltip_text = ""
			_upgrade.disabled = world.gold < cost or world.demo
	else:
		_upgrade.icon = null
		_upgrade.text = "HIGHEST RANK"
		_upgrade.disabled = true
	_sell.text = "SELL · DEL  +%d" % t.refund
	_sell.disabled = cursed or world.demo
	_mode.visible = (world.start.get("modes", []) as Array).size() > 1
	if _mode.visible:
		_mode.text = "AIMS %s · M" % _mode_name(t.mode).to_upper()
		_mode.disabled = world.demo
	var craft: Dictionary = world.start.get("attune", {})
	_attune.visible = bool(craft.get("unlocked", false)) and not t.attuned and t.attunable
	if _attune.visible:
		_attune.text = "ATTUNE · T   %d" % int(craft["gold"])
		_attune.tooltip_text = "Hold charges for empowered shots, spent where they kill."
		_attune.disabled = world.gold < int(craft["gold"]) or world.demo
	_charges.visible = t.attuned
	if t.attuned:
		_charges.text = "CHARGES %d / 3" % int(t.charges)
	if not was:
		_card.modulate.a = 0.0
		_card.create_tween().tween_property(_card, "modulate:a", 1.0, 0.18)


## The chosen tower's strategy, named from the battle's owned modes.
func _mode_name(mode: String) -> String:
	for m in world.start.get("modes", []):
		if String(m["key"]) == mode:
			return String(m["name"])
	return mode.capitalize()


## Teach the chosen tower the next owned strategy.
func cycle_mode() -> void:
	var modes := world.start.get("modes", []) as Array
	if _selected == null or modes.size() < 2:
		return
	var keys: Array = []
	for m in modes:
		keys.append(String(m["key"]))
	var next: String = keys[(keys.find(_selected.mode) + 1) % keys.size()]
	order.emit("mode:" + next)


func _show_portrait(on: bool) -> void:
	if _turning:
		(_turning.get_parent() as SubViewport).render_target_update_mode = \
			SubViewport.UPDATE_ALWAYS if on else SubViewport.UPDATE_DISABLED


func _stat(row: String, now: String, next: String) -> void:
	_stats[row][1].text = now
	_stats[row][2].text = "→ " + next if next != "" and next != now else ""


func _refresh_leader(delta: float) -> void:
	var cam := get_viewport().get_camera_3d()
	var best: Monster = null
	var score := -1.0
	for m in world.monsters.values():
		if (m.leader or m.boss) and m.alive() and cam and cam.is_position_in_frustum(m.chest()):
			var s: float = m.progress + (2.0 if m.casting() >= 0.0 else 0.0)   # a cursing one first, then the foremost
			if s > score:
				best = m
				score = s
	_leader.modulate.a = move_toward(_leader.modulate.a, 1.0 if best else 0.0, delta * 4.0)
	if best == null:
		return
	_leader_name.text = best.title()
	_leader_life.set_shader_parameter("fill", best.hp / best.max_hp)
	var what := []
	if best.boss:
		what.append("Boss · %d %s on the shrine" % [best.strikes, "strike" if best.strikes == 1 else "strikes"]
			if best.strikes > 0 else "Boss · cast back from the shrine, it comes again")
	if best.leader:
		what.append("Leader · curses the towers that hurt its pack")
	_leader_kind.text = " · ".join(what)
	var cast := best.casting()
	var target := best.curse_target()
	_leader_cast_box.modulate.a = 1.0 if cast >= 0.0 else 0.0
	if cast >= 0.0:
		_leader_cast.set_shader_parameter("fill", cast)
		_leader_cast_text.text = "Ponders a curse…" if best.pondering() or target == null \
			else "Chants a curse on the %s" % target.title()


func _announce(title: String, line: String) -> void:
	if title == "":
		_chronicle_line(line)
		return
	var tone: Color = TONES["wave"]
	if world.outcome == "victory":
		tone = TONES["won"]
	elif world.outcome == "defeat":
		tone = TONES["lost"]
	elif "curse" in (title + line).to_lower():
		tone = TONES["curse"]
	var wave := RegEx.create_from_string("^Wave (\\d+) of \\d+$").search(title)
	if wave:
		title = "Wave " + NUMERALS[int(wave.get_string(1)) - 1]
	_show_banner(title, line, tone, 2.6, 0.5)


## The banner arrives a little large and settles as it fades in, holds, then fades.
func _show_banner(title: String, line: String, tone: Color, hold: float, fade_in: float) -> void:
	_banner_title.text = title
	_banner_line.text = line
	_banner_title.add_theme_color_override("font_color", tone)
	_banner_rule.modulate = Color(tone, 0.9)
	_banner_smoke.set_shader_parameter("tint", tone)
	if _banner_tween:
		_banner_tween.kill()
	_banner.pivot_offset = _banner.size / 2
	_banner.scale = Vector2(1.25, 1.25)
	_banner.modulate.a = 0.0
	_banner_tween = create_tween().set_parallel()
	_banner_tween.tween_property(_banner, "scale", Vector2.ONE, fade_in * 1.6).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	_banner_tween.tween_property(_banner, "modulate:a", 1.0, fade_in)
	_banner_tween.chain().tween_interval(hold)
	_banner_tween.chain().tween_property(_banner, "modulate:a", 0.0, 1.0)


func _chronicle_line(text: String, color := Color(0.82, 0.6, 1.0)) -> void:
	var back := PanelContainer.new()
	var sb := StyleBoxTexture.new()
	sb.texture = _gradient([[0.0, Color(0, 0, 0, 0)], [0.35, Color(0.03, 0.0, 0.06, 0.55)], [1.0, Color(0.03, 0.0, 0.06, 0.7)]], false)
	sb.content_margin_left = 60
	sb.content_margin_right = 14
	sb.content_margin_top = 3
	sb.content_margin_bottom = 4
	back.add_theme_stylebox_override("panel", sb)
	back.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var l := _label(Style.text_font(), 22, color)
	l.text = text
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART   # a long line wraps in the column, never past the edge
	back.add_child(l)
	_chronicle.add_child(back)
	while _chronicle.get_child_count() > 5:
		_chronicle.get_child(0).free()
	back.modulate.a = 0.0
	var tw := back.create_tween()
	tw.tween_property(back, "modulate:a", 1.0, 0.4)
	tw.tween_interval(7.0)
	tw.tween_property(back, "modulate:a", 0.0, 1.5)
	tw.tween_callback(back.queue_free)


# -- small builders

## Tooltips in the HUD's manner: Baskerville on dark iron in a bronze rim.
func _tooltips() -> Theme:
	var t := Theme.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.04, 0.034, 0.038, 0.96)
	sb.border_color = Style.BRONZE
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(2)
	sb.content_margin_left = 12
	sb.content_margin_right = 12
	sb.content_margin_top = 6
	sb.content_margin_bottom = 7
	t.set_stylebox("panel", "TooltipPanel", sb)
	t.set_font("font", "TooltipLabel", Style.text_font())
	t.set_font_size("font_size", "TooltipLabel", 21)
	t.set_color("font_color", "TooltipLabel", Style.BONE)
	return t


func _pin(c: Control, ax: float, ay: float, rect: Rect2) -> Control:
	c.anchor_left = ax
	c.anchor_right = ax
	c.anchor_top = ay
	c.anchor_bottom = ay
	c.offset_left = rect.position.x
	c.offset_top = rect.position.y
	c.offset_right = rect.end.x
	c.offset_bottom = rect.end.y
	return c


## The HUD at the interface size the settings ask for, as far as the window's width keeps the orbs' frames on it:
## both layers scale, their roots span the window in the layers' own units (the bar keeps to the bottom edge, the
## banners to the middle), and the HUD's fonts rasterise at the size they are drawn - a layer's scale alone would
## magnify glyphs rasterised small. Tooltips are windows of their own, outside the layers: their text grows apart.
func _fit() -> void:
	_asked = prefs.interface
	var window := get_viewport().get_visible_rect().size
	_scale = minf(_asked, window.x / (2.0 * ORB_REACH))
	var span := window / _scale
	for l: CanvasLayer in [self, _over]:
		l.scale = Vector2(_scale, _scale)
	for c: Control in [_root, _top]:
		c.position = Vector2.ZERO
		c.size = span
	for f in _sharp:
		f.oversampling = get_viewport().get_oversampling() * _scale
	_root.theme.set_font_size("font_size", "TooltipLabel", roundi(21 * _scale))
	# the chronicle keeps right of the leader's column (centred, 250 either side)
	_chronicle.offset_left = -minf(620.0, span.x / 2 - 262.0)


## The HUD's copy of one of Style's fonts: its own system font, so `_fit` can rasterise it at the HUD's size.
func _own(font: Font) -> Font:
	if not _fonts.has(font):
		var copy := font.duplicate() as Font
		var base := (copy as FontVariation).base_font.duplicate() as SystemFont if copy is FontVariation else copy as SystemFont
		if copy is FontVariation:
			(copy as FontVariation).base_font = base
		base.oversampling = get_viewport().get_oversampling() * _scale
		_sharp.append(base)
		_fonts[font] = copy
	return _fonts[font]


func _label(font: Font, size: int, color: Color) -> Label:
	var l := Label.new()
	l.add_theme_font_override("font", _own(font))
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.8))
	l.add_theme_constant_override("shadow_offset_x", 2)
	l.add_theme_constant_override("shadow_offset_y", 2)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


## A small label in tracked capitals.
func _caps(size: int, color: Color) -> Label:
	var l := _label(Style.small_font(), size, color)
	l.uppercase = true
	l.add_theme_constant_override("shadow_offset_x", 1)
	l.add_theme_constant_override("shadow_offset_y", 1)
	return l


## A plaque button; its text in tracked capitals.
func _button(text: String) -> Button:
	var b := Button.new()
	b.text = text.to_upper()
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_font_override("font", _own(Style.small_font()))
	b.add_theme_font_size_override("font_size", 15)
	b.add_theme_color_override("font_color", Style.PALE_GOLD)
	b.add_theme_color_override("font_hover_color", Color(1, 0.97, 0.86))
	b.add_theme_color_override("font_pressed_color", Style.GOLD)
	b.add_theme_color_override("font_disabled_color", Color(0.6, 0.55, 0.47))
	b.add_theme_stylebox_override("normal", Style.plaque(Color(0.2, 0.12, 0.07), Style.BRONZE))
	b.add_theme_stylebox_override("hover", Style.plaque(Color(0.32, 0.19, 0.09), Style.GOLD))
	b.add_theme_stylebox_override("pressed", Style.plaque(Color(0.13, 0.08, 0.05), Style.GOLD, true))
	b.add_theme_stylebox_override("disabled", Style.plaque(Color(0.1, 0.085, 0.08), Color(0.38, 0.33, 0.27)))
	b.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	return b


func _coin_icon(px: int) -> TextureRect:
	var c := TextureRect.new()
	c.texture = load("res://assets/ui/coin.png")
	c.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	c.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	c.custom_minimum_size = Vector2(px, px)
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return c


## A gauge drawn by shaders/hud_bar.gdshader on `rect`; its material, for its fill.
func _gauge(rect: ColorRect, color: Color, size: Vector2) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/hud_bar.gdshader")
	m.set_shader_parameter("color", color)
	rect.material = m
	rect.custom_minimum_size = size
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	rect.resized.connect(func(): m.set_shader_parameter("size", rect.size))
	return m


## A gradient texture from [offset, colour] stops, running down (`vertical`) or across.
func _gradient(stops: Array, vertical: bool) -> GradientTexture2D:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array(stops.map(func(s): return s[0]))
	g.colors = PackedColorArray(stops.map(func(s): return s[1]))
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill_to = Vector2(0, 1) if vertical else Vector2(1, 0)
	t.width = 4 if vertical else 256
	t.height = 256 if vertical else 4
	return t


func _noise(frequency: float, octaves: int) -> NoiseTexture2D:
	var nt := NoiseTexture2D.new()
	nt.seamless = true
	var fn := FastNoiseLite.new()
	fn.frequency = frequency
	fn.fractal_octaves = octaves
	nt.noise = fn
	return nt
