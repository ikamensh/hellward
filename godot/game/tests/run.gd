extends Node
## Hellward 3D's integration tests: each builds the real game scene and plays it.
##     tools/test.sh            (headless; fails on a failed check or any script error)
## The battle steps at a fixed 30 fps (--fixed-fps 30), as fast as the machine allows.

var failures: Array = []
var checks := 0
var _main: Node


func _ready() -> void:
	for t in [test_scene_runs, test_intro_hands_over_the_camera, test_building_obeys_map_and_purse,
			test_early_wave_keeps_its_bonus, test_defeat_stops_the_battle, test_wave_kills_pay_gold,
			test_shaman_curses_and_cleanse_lifts, test_mouse_builds_a_tower, test_scripted_defence_holds_tristram]:
		_main = null
		print("-- ", t.get_method())
		var before := checks
		await t.call()
		if checks == before:
			failures.append("%s ran no checks (a script error stopped it)" % t.get_method())
		if is_instance_valid(_main):
			_main.queue_free()
			await get_tree().process_frame
		Engine.time_scale = 1.0
	print("FAILED: %d" % failures.size() if failures else "all passed")
	for f in failures:
		print("  ", f)
	get_tree().quit(1 if failures else 0)


func check(ok: bool, what: String) -> void:
	checks += 1
	if not ok:
		failures.append(what)
		print("   FAIL ", what)


func start(args := {}) -> Node:
	_main = load("res://scenes/main.tscn").instantiate()
	args["nointro"] = ""
	_main.args = args
	add_child(_main)
	await frames(2)
	return _main


func frames(n: int) -> void:
	for i in n:
		await get_tree().process_frame


func seconds(s: float) -> void:
	await frames(int(s * 30))


func test_scene_runs() -> void:
	var m := await start()
	await seconds(3)
	check(m.world.outcome == "", "the battle has not ended by itself")
	check(m.world.gold == int(m.level.data["start_gold"]), "gold starts at the location's purse")


## Played normally, the opening flies over the village, then hands the camera to the player; a key skips it.
func test_intro_hands_over_the_camera() -> void:
	_main = load("res://scenes/main.tscn").instantiate()
	_main.args = {}
	add_child(_main)
	await frames(2)
	check(not _main.rig.user_control, "the opening holds the camera")
	await seconds(1)
	var key := InputEventKey.new()
	key.keycode = KEY_ESCAPE
	key.pressed = true
	_main.get_viewport().push_input(key)
	await seconds(4)
	check(_main.rig.user_control, "a key skips the opening and the player has the camera")


## Towers stand only on buildable floor, never on a lane or another tower, and cost exactly their price.
func test_building_obeys_map_and_purse() -> void:
	var m := await start()
	var w: World = m.world
	var lv: Level = m.level
	var floor_tile := Vector2i(16, 7)
	var lane_tile := Vector2i(10, 8)
	check(lv.cell(floor_tile) == "." and lv.cell(lane_tile) == "P", "test tiles are floor and lane")
	var gold := w.gold
	check(w.build("arrow", lane_tile) == null, "no tower on a lane")
	check(w.gold == gold, "a refused build costs nothing")
	var t := w.build("arrow", floor_tile)
	check(t != null, "a tower on floor")
	check(w.gold == gold - w.tower_cost("arrow", 0), "the build costs the tower's price")
	check(w.build("arrow", floor_tile) == null, "no second tower on the same tile")
	w.gold = 0
	check(w.build("pyre", Vector2i(13, 6)) == null and w.gold == 0, "no tower without the gold, and gold never negative")


func test_wave_kills_pay_gold() -> void:
	var m := await start()
	var w: World = m.world
	w.gold = 200
	for tile in [Vector2i(16, 7), Vector2i(11, 10), Vector2i(22, 5), Vector2i(13, 6), Vector2i(18, 11)]:
		w.build("arrow", tile)
	var gold := w.gold
	w.call_wave()
	await seconds(1)
	check(w.monsters.size() > 0, "a wave puts monsters on the field")
	for i in 120:
		await seconds(1)
		if not w.wave_active():
			break
	check(not w.wave_active(), "the first wave ends")
	check(w.gold > gold, "kills and the clear bonus pay gold")
	check(w.lives > 0, "five arrow towers hold the first wave")


## Calling the next wave before the field is clear still pays the earlier wave's clear bonus (regression).
func test_early_wave_keeps_its_bonus() -> void:
	var m := await start()
	var w: World = m.world
	w.gold = 400
	for tile in [Vector2i(16, 7), Vector2i(11, 10), Vector2i(22, 5), Vector2i(13, 6), Vector2i(18, 11), Vector2i(28, 6)]:
		w.build("arrow", tile)
	w.call_wave()
	await seconds(2)
	w.call_wave()   # early: the first wave is still on the field
	var expected: int = int(w.waves()[0]["clear_bonus"]) + int(w.waves()[1]["clear_bonus"])
	var before := w.gold
	for i in 200:
		await seconds(1)
		if not w.wave_active():
			break
	check(not w.wave_active(), "both waves end")
	check(w.paid == 1, "both waves are paid")
	check(w.gold >= before + expected, "the gold includes both clear bonuses")


## When the last life goes, the battle stops where it stands: no more shots, kills or gold (regression).
func test_defeat_stops_the_battle() -> void:
	var m := await start()
	var w: World = m.world
	w.gold = 100
	w.build("arrow", Vector2i(16, 7))
	w.lives = 1
	w.call_wave()
	for i in 120:
		await seconds(1)
		if w.outcome != "":
			break
	check(w.outcome == "lost", "a lone tower loses Tristram with one life")
	var gold := w.gold
	await seconds(5)
	check(w.gold == gold, "no gold changes after the defeat")
	check(w.near(w.level.centre(), 999.0).is_empty(), "towers find nothing to shoot")


## A Fallen Shaman curses a tower near its path; Cleanse lifts the curse for mana.
func test_shaman_curses_and_cleanse_lifts() -> void:
	var m := await start()
	var w: World = m.world
	w.gold = 500
	var towers: Array = []
	for tile in [Vector2i(9, 6), Vector2i(12, 6), Vector2i(14, 6), Vector2i(8, 10), Vector2i(11, 10)]:
		towers.append(w.build("arrow", tile))
	check(not towers.has(null), "five towers stand by the lanes")
	w.spawners.append({"kind": "shaman", "left": 1, "interval": 1.0, "next": w.time, "life": 50.0, "wave": 0})
	var cursed: Tower = null
	for i in 40 * 30:
		await frames(1)
		for t in towers:
			if t.cursed > 0.0:
				cursed = t
		if cursed:
			break
	check(cursed != null, "the shaman curses a tower within 40 s")
	if cursed:
		w.mana = 100.0
		check(w.cleanse(cursed), "Cleanse works on a cursed tower")
		check(cursed.cursed <= 0.0, "Cleanse lifts the curse")
		check(is_equal_approx(w.mana, 100.0 - World.CLEANSE_COST), "Cleanse costs its mana")
		check(not w.cleanse(cursed), "nothing to cleanse twice")


## The player's hands: 1 holds an Arrow Tower, a click on floor builds it there.
func test_mouse_builds_a_tower() -> void:
	var m := await start()
	m.rig.user_control = false   # the virtual cursor would pan the camera at the screen's edge
	var w: World = m.world
	var tile := Vector2i(16, 7)
	var screen: Vector2 = m.rig.cam.unproject_position(m.level.tile_pos(tile))
	var vp: Viewport = m.get_viewport()
	var key := InputEventKey.new()
	key.keycode = KEY_1
	key.pressed = true
	vp.push_input(key)
	await frames(2)
	check(m.builder.held == "arrow", "1 holds an Arrow Tower")
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	click.position = vp.get_final_transform() * screen   # a click arrives in window coordinates
	vp.push_input(click)
	await frames(2)
	check(w.towers.size() == 1 and w.towers[0].tile == tile, "the click builds it on the tile under the mouse")
	check(m.builder.held == "", "the hand is empty after building")


## End to end: the scripted defender plays all five waves and Tristram holds.
func test_scripted_defence_holds_tristram() -> void:
	var m := await start({"demo": ""})
	var w: World = m.world
	for i in 900:
		await seconds(1)
		if w.outcome != "":
			break
	check(w.outcome == "won", "the scripted defence wins (outcome '%s', wave %d, lives %d)" % [w.outcome, w.wave + 1, w.lives])
	check(w.towers.size() >= 8, "it built a full defence (%d towers)" % w.towers.size())
