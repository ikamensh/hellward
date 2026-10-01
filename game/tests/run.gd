extends Node
## Hellward 3D's integration tests: each builds the real game scene and plays it.
##     tools/test.sh            (headless; fails on a failed check or any script error)
## The battle steps at a fixed 30 fps (--fixed-fps 30), as fast as the machine allows.

var failures: Array = []
var _main: Node


func _ready() -> void:
	for t in [test_scene_runs, test_building_obeys_map_and_purse, test_wave_kills_pay_gold,
			test_shaman_curses_and_cleanse_lifts, test_mouse_builds_a_tower, test_scripted_defence_holds_tristram]:
		_main = null
		print("-- ", t.get_method())
		await t.call()
		if is_instance_valid(_main):
			_main.queue_free()
			await get_tree().process_frame
		Engine.time_scale = 1.0
	print("FAILED: %d" % failures.size() if failures else "all passed")
	for f in failures:
		print("  ", f)
	get_tree().quit(1 if failures else 0)


func check(ok: bool, what: String) -> void:
	if not ok:
		failures.append(what)
		print("   FAIL ", what)


func start(args := {}) -> Node:
	_main = load("res://scenes/main.tscn").instantiate()
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


## A Fallen Shaman curses a tower near its path; Cleanse lifts the curse for mana.
func test_shaman_curses_and_cleanse_lifts() -> void:
	var m := await start()
	var w: World = m.world
	w.gold = 500
	var towers: Array = []
	for tile in [Vector2i(9, 6), Vector2i(12, 6), Vector2i(14, 6), Vector2i(8, 10), Vector2i(11, 10)]:
		towers.append(w.build("arrow", tile))
	check(not towers.has(null), "five towers stand by the lanes")
	w.spawners.append({"kind": "shaman", "left": 1, "interval": 1.0, "next": w.time, "life": 50.0})
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
