class_name SummaryScreen
extends Screen
## A run's summary when it ended: won or lost, every place it held with what each cost and paid, and the laying
## down, which banks what the run earned and goes back to the title.
## data = the run's view (Campaign.run_view).

var _names := {}                      # location keys to their names, from the campaign's view


func build() -> void:
	add_child(Ui.backdrop("res://assets/ui/title.jpg"))
	add_child(PauseScreen.veil(0.55))
	var prof = await ask("campaign")
	if prof != null:
		for act in prof["acts"]:
			for place in act["places"]:
				_names[String(place["key"])] = String(place["name"])
	_lay()


func _lay() -> void:
	var won := bool(data["won"])
	var tone: Color = Style.GOLD if won else Color(0.88, 0.12, 0.07)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	col.alignment = BoxContainer.ALIGNMENT_CENTER
	col.add_child(PauseScreen.heading("The run is won" if won else "The run is lost", 64, tone))
	col.add_child(PauseScreen.rule(560))
	var inner := VBoxContainer.new()
	inner.add_theme_constant_override("separation", 10)
	for record in data["records"]:
		var met := (record["goals"] as Array).filter(func(g): return String(g["verdict"]) == "met").size()
		inner.add_child(Ui.paragraph("%s: %d lives lost, %d sigils, %d of %d goals met." % [
			_named(String(record["location"])), int(record["lives_lost"]), int(record["sigils"]), met,
			(record["goals"] as Array).size()], 22, Style.BONE, 880, HORIZONTAL_ALIGNMENT_CENTER))
	inner.add_child(PauseScreen.gap(2))
	inner.add_child(Ui.paragraph("Level %d, %d gold unspent, %d salvage for the purse." % [
		int(data["level"]), int(data["gold"]), int(data["salvage"])], 22, Style.PALE_GOLD, 880,
		HORIZONTAL_ALIGNMENT_CENTER))
	col.add_child(PauseScreen.card(inner, 960))
	col.add_child(PauseScreen.gap(10))
	var lay := PauseScreen.primary(Ui.button("Lay down the run", "Enter", 320))
	lay.pressed.connect(func(): game.abandon_run())
	var ways := HBoxContainer.new()
	ways.alignment = BoxContainer.ALIGNMENT_CENTER
	ways.add_child(lay)
	col.add_child(ways)
	add_child(PauseScreen.centred(col))


func _named(key: String) -> String:
	return String(_names.get(key, key.capitalize()))
