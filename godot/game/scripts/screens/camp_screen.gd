class_name CampScreen
extends Screen
## The camp between a run's locations: the pool, the purse, the level and the points, the goals drawn for the
## place ahead and what the run has held so far, the relics won and the camp's offered choice of one more.
## Continue walks into the intro; the tree and the forge open over the camp; laying the run down banks its
## salvage and ends it. On the first run the way on is marked.
## data = the run's view (Campaign.run_view).

var _names := {}                      # location keys to their names, from the campaign's view
var _first := false
var _page: Control                    # the laid page, so taking a relic lays it again


func build() -> void:
	add_child(Ui.backdrop("res://assets/ui/title.jpg"))
	add_child(PauseScreen.veil(0.55))
	var prof = await ask("campaign")
	if prof != null:
		_first = int(prof["runs_won"]) + int(prof["runs_lost"]) == 0
		for act in prof["acts"]:
			for place in act["places"]:
				_names[String(place["key"])] = String(place["name"])
	_lay()


func _lay() -> void:
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	col.alignment = BoxContainer.ALIGNMENT_CENTER
	col.add_child(PauseScreen.heading("The Camp", 64))
	col.add_child(PauseScreen.rule(560))
	var at := _named(String(data["location"])) if data["location"] != null else "Nowhere"
	col.add_child(PauseScreen.heading("%s waits — the %s of 12" % [at, _ordinal(int(data["index"]) + 1)], 26,
		Style.PALE_GOLD))

	var inner := VBoxContainer.new()
	inner.add_theme_constant_override("separation", 12)
	var stats := HBoxContainer.new()
	stats.alignment = BoxContainer.ALIGNMENT_CENTER
	stats.add_theme_constant_override("separation", 48)
	for pair in [["Pool", "%d of %d" % [int(data["pool"]), int(data["pool_max"])]], ["Gold", str(int(data["gold"]))],
			["Level", str(int(data["level"]))], ["Points", str(int(data["skill_points"]))],
			["Reskill", str(int(data["reskill_points"]))], ["Salvage", str(int(data["salvage"]))]]:
		stats.add_child(_stat(String(pair[0]), String(pair[1])))
	inner.add_child(stats)
	inner.add_child(PauseScreen.gap(2))
	for goal in data["drawn"]:
		inner.add_child(Ui.paragraph("Wagered: %s" % String(goal["line"]), 21, Style.BONE, 880,
			HORIZONTAL_ALIGNMENT_CENTER))
	for record in data["records"]:
		var met := (record["goals"] as Array).filter(func(g): return String(g["verdict"]) == "met").size()
		inner.add_child(Ui.paragraph("%s held: %d lives lost, %d sigils, %d of %d goals met." % [
			_named(String(record["location"])), int(record["lives_lost"]), int(record["sigils"]), met,
			(record["goals"] as Array).size()], 21, Style.DIM_GOLD, 880, HORIZONTAL_ALIGNMENT_CENTER))
	if _first and (data["records"] as Array).is_empty():
		inner.add_child(Ui.paragraph("Your first run: hold %s. Spend points on the tree before you go." % [at], 22,
			Style.GOLD, 880, HORIZONTAL_ALIGNMENT_CENTER))
	for held in data["relics"]:
		var line := "%s — %s" % [String(held["name"]), String(held["words"])]
		if int(held["every"]) > 0:
			line += " (%d/%d)" % [int(held["count"]) % int(held["every"]), int(held["every"])]
		inner.add_child(Ui.paragraph(line, 20, Style.PALE_GOLD, 880, HORIZONTAL_ALIGNMENT_CENTER))
	col.add_child(PauseScreen.card(inner, 960))
	if not (data["offer"] as Array).is_empty():
		col.add_child(PauseScreen.gap(6))
		col.add_child(_offer())
	col.add_child(PauseScreen.gap(10))

	var ways := HBoxContainer.new()
	ways.alignment = BoxContainer.ALIGNMENT_CENTER
	ways.add_theme_constant_override("separation", 16)
	var ahead := PauseScreen.primary(Ui.button("Continue", "Enter", 230))
	ahead.pressed.connect(func(): game.intro(String(data["location"])))
	var tree := Ui.button("The Tree", "T", 230)
	tree.pressed.connect(func(): game.skills(String(data["location"])))
	var forge := Ui.button("The Forge", "F", 230)
	forge.pressed.connect(func(): game.forge())
	var lay := Ui.button("Lay down the run", "Q", 230)
	lay.pressed.connect(func(): game.abandon_run())
	for b in [ahead, tree, forge, lay]:
		ways.add_child(b)
	col.add_child(ways)
	_page = PauseScreen.centred(col)
	add_child(_page)


## The camp's offered choice after a held location: each relic's name and words, a finger on each.
func _offer() -> Control:
	var inner := VBoxContainer.new()
	inner.add_theme_constant_override("separation", 8)
	inner.add_child(PauseScreen.heading("Take one relic", 26, Style.PALE_GOLD))
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 16)
	var n := 1
	for gift in data["offer"]:
		var take := Ui.button("%s — %s" % [String(gift["name"]), String(gift["words"])], str(n), 280)
		take.pressed.connect(func(): _take(String(gift["key"])))
		row.add_child(take)
		n += 1
	inner.add_child(row)
	return PauseScreen.card(inner, 960)


func _take(key: String) -> void:
	var view = await ask("take_relic", {"key": key})
	if view == null:
		return
	data = view
	_page.queue_free()
	_lay()


func _named(key: String) -> String:
	return String(_names.get(key, key.capitalize()))


func _ordinal(n: int) -> String:
	if n == 1:
		return "1st"
	if n == 2:
		return "2nd"
	if n == 3:
		return "3rd"
	return "%dth" % n


## One of the run's figures: its number large, what it counts in small capitals under it.
func _stat(what: String, value: String) -> VBoxContainer:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 0)
	var v := Ui.label(value, 40, Style.PALE_GOLD, Style.title_font())
	v.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(v)
	var w := Ui.caps(what, 17, Style.DIM_GOLD)
	w.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(w)
	return box
