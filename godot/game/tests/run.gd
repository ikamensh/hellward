extends Node
## Hellward's client tests: each builds the real battle scene against the real server (python -m hellward.server,
## started by Net with a scratch save folder) and plays it.
##     tools/test.sh            (headless; fails on a failed check or any script error)
## The client steps at a fixed 30 fps (--fixed-fps 30) as fast as the machine allows; Engine.time_scale is the pace.

var failures: Array = []
var checks := 0
var _main: Node


func _ready() -> void:
	if not await Net.wait_ready():
		print("FAILED: no server: ", Net.error)
		get_tree().quit(1)
		return
	var only := OS.get_environment("HELLWARD_TEST")
	for t in [test_battle_starts_with_the_locations_purse, test_intro_hands_over_the_camera, test_mouse_builds_a_tower,
			test_the_server_refuses_a_tower_on_the_lane, test_a_wave_brings_monsters_that_walk,
			test_a_curse_lands_and_cleanse_lifts_it, test_defeat_ends_the_battle_and_its_music,
			test_the_watched_defence_holds_and_ends_with_victory]:
		if only != "" and only not in t.get_method():
			continue
		_main = null
		print("-- ", t.get_method())
		var before := checks
		await t.call()
		if checks == before:
			failures.append("%s ran no checks (a script error stopped it)" % t.get_method())
		if is_instance_valid(_main):
			_main.queue_free()
			await frames(2)
		Engine.time_scale = 1.0
	print("FAILED: %d" % failures.size() if failures else "all passed")
	for f in failures:
		print("  ", f)
	Net.stop()
	get_tree().quit(1 if failures else 0)


func check(ok: bool, what: String) -> void:
	checks += 1
	if not ok:
		failures.append(what)
		print("   FAIL ", what)


func start(args := {}) -> Node:
	_main = load("res://scenes/main.tscn").instantiate()
	if not args.has("intro"):
		args["nointro"] = ""
	_main.args = args
	add_child(_main)
	await _main.started
	await frames(2)
	return _main


func frames(n: int) -> void:
	for i in n:
		await get_tree().process_frame


func seconds(s: float) -> void:
	await frames(int(s * 30))


## Wait up to `limit` seconds of game time for `ready` to hold; whether it did.
func until(ready: Callable, limit: float) -> bool:
	for i in int(limit * 30 / Engine.time_scale) + 1:
		if ready.call():
			return true
		await frames(1)
	return ready.call()


func press(vp: Viewport, keycode: Key) -> void:
	var key := InputEventKey.new()
	key.keycode = keycode
	key.pressed = true
	vp.push_input(key)


func click(m: Node, tile: Vector2i) -> void:
	var vp: Viewport = m.get_viewport()
	var screen: Vector2 = m.rig.cam.unproject_position(m.level.tile_pos(tile))
	var ev := InputEventMouseButton.new()
	ev.button_index = MOUSE_BUTTON_LEFT
	ev.pressed = true
	ev.position = vp.get_final_transform() * screen   # a click arrives in window coordinates
	vp.push_input(ev)


## Bare floor tiles beside the main route, nearest its middle first: where an arrow tower reaches the path.
func lane_side(lv: Level, count: int) -> Array:
	var out: Array = []
	for d in range(1, 4):
		for y in lv.height:
			for x in lv.width:
				var t := Vector2i(x, y)
				if lv.cell(t) != ".":
					continue
				for n in [Vector2i(d, 0), Vector2i(-d, 0), Vector2i(0, d), Vector2i(0, -d)]:
					if lv.cell(t + n) == "P" and not out.has(t):
						out.append(t)
	out.sort_custom(func(a, b): return abs(a.x - lv.width / 2) < abs(b.x - lv.width / 2))
	return out.slice(0, count)


func test_battle_starts_with_the_locations_purse() -> void:
	var m := await start()
	await seconds(3)
	var w: World = m.world
	check(w.outcome == "", "the battle has not ended by itself")
	check(w.gold == int(w.start["state"]["gold"]), "gold starts at the location's purse (%d)" % w.gold)
	check(w.time > 2.0, "the server's clock runs with this side's (%.2f s)" % w.time)
	check(w.lives == 20, "twenty lives")


## Played normally, the opening flies over the field, then hands the camera to the player; a key skips it.
func test_intro_hands_over_the_camera() -> void:
	var m := await start({"intro": ""})
	check(not m.rig.user_control, "the opening holds the camera")
	await seconds(1)
	press(m.get_viewport(), KEY_ESCAPE)
	await seconds(4)
	check(m.rig.user_control, "a key skips the opening and the player has the camera")


## The player's hands: 1 holds an Arrow Tower, a click on floor builds it there, and it costs its price.
func test_mouse_builds_a_tower() -> void:
	var m := await start()
	m.rig.user_control = false   # the virtual cursor would pan the camera at the screen's edge
	var w: World = m.world
	var tile: Vector2i = lane_side(m.level, 1)[0]
	var gold := w.gold
	press(m.get_viewport(), KEY_1)
	await frames(2)
	check(m.builder.held == "arrow", "1 holds an Arrow Tower")
	click(m, tile)
	check(await until(func(): return w.towers.size() == 1, 3.0), "the server builds it")
	if w.towers.size() == 1:
		check(w.towers.values()[0].tile == tile, "on the tile under the mouse")
	check(w.gold == gold - w.tower_cost("arrow"), "it costs the tower's price")
	check(m.builder.held == "", "the hand is empty after building")


func test_the_server_refuses_a_tower_on_the_lane() -> void:
	var m := await start()
	m.rig.user_control = false
	var w: World = m.world
	var why := []
	w.refused.connect(func(text: String): why.append(text))
	var lane := Vector2i(10, 8)
	check(m.level.cell(lane) == "P", "the test tile is a lane")
	press(m.get_viewport(), KEY_1)
	await frames(2)
	click(m, lane)
	check(await until(func(): return not why.is_empty(), 3.0), "the server refuses it")
	check(why.size() > 0 and "bare floor" in why[0], "and says why (%s)" % [why])
	check(w.towers.is_empty(), "no tower stands on the lane")


func test_a_wave_brings_monsters_that_walk() -> void:
	var m := await start()
	var w: World = m.world
	press(m.get_viewport(), KEY_SPACE)
	check(await until(func(): return w.wave == 0, 3.0), "Space calls the first wave")
	check(await until(func(): return w.monsters.size() > 0, 6.0), "the wave puts monsters on the field")
	if w.monsters.is_empty():
		return
	var first: Monster = w.monsters.values()[0]
	var was := first.global_position
	await seconds(2)
	check(first.global_position.distance_to(was) > 1.0, "a monster walks its route")


## Towers by the lanes draw a Fallen Shaman's curse; C on the cursed tower cleanses it for mana.
func test_a_curse_lands_and_cleanse_lifts_it() -> void:
	var m := await start()
	m.rig.user_control = false
	var w: World = m.world
	Engine.time_scale = 4.0
	var curses := []
	w.happened.connect(func(e: Array): if e[0] == "cursed" and not e[4].is_empty(): curses.append(e))
	for tile in lane_side(m.level, 4):
		await w.order("build", {"kind": "arrow", "tile": [tile.x, tile.y]})
	check(w.towers.size() >= 3, "towers stand by the lanes (%d)" % w.towers.size())
	var cursed: Tower = null
	for i in 600:
		if w.can_call():
			await w.order("call_wave")
		await seconds(1)
		for t in w.towers.values():
			if t.cursed():
				cursed = t
		if cursed or w.outcome != "":
			break
	check(cursed != null, "a leader's curse lands on a tower (curses seen: %d)" % curses.size())
	if cursed == null:
		return
	Engine.time_scale = 1.0
	m.builder.choose(cursed)
	await check_cleanse(m, cursed)


func check_cleanse(m: Node, cursed: Tower) -> void:
	var w: World = m.world
	await until(func(): return w.mana >= w.spell_cost("cleanse"), 60.0)
	var mana := w.mana
	press(m.get_viewport(), KEY_C)
	check(await until(func(): return not cursed.cursed(), 3.0), "C cleanses the chosen tower")
	check(w.mana < mana, "Cleanse costs mana (%.0f -> %.0f)" % [mana, w.mana])


## With no towers, the waves walk in: the defence falls, the battle stops and its music with it.
func test_defeat_ends_the_battle_and_its_music() -> void:
	var m := await start()
	var w: World = m.world
	Engine.time_scale = 8.0
	var ended := []
	m.ended.connect(func(result: Dictionary): ended.append(result))
	for i in 400:
		if w.can_call():
			await w.order("call_wave")
		await seconds(1)
		if w.outcome != "":
			break
	check(w.outcome == "defeat", "an undefended sanctuary falls (%s)" % w.outcome)
	var step := w.step
	await seconds(2)
	check(w.step == step, "the battle stops where it stands")
	check(await until(func(): return not ended.is_empty(), 6.0), "the battle ends for the reckoning")
	check(ended.size() > 0 and ended[0].get("title", "") == "The Sanctuary Has Fallen", "the reckoning says so (%s)" % [ended])
	check(not Sfx.music_playing(), "its music stops")


## End to end: a strong scripted player, played by the server, holds Tristram; the battle ends with the title's music.
func test_the_watched_defence_holds_and_ends_with_victory() -> void:
	var m := await start({"demo": "", "player": "adaptive"})
	var w: World = m.world
	Engine.time_scale = 8.0
	check(await until(func(): return w.outcome != "", 900.0), "the watched defence ends")
	check(w.outcome == "victory", "the scripted defence wins (outcome '%s', wave %d, lives %d)" % [w.outcome, w.wave + 1, w.lives])
	check(w.towers.size() >= 4, "it built a defence (%d towers)" % w.towers.size())
	check(Sfx.music_name() == "title", "the title's music plays after the victory (%s)" % Sfx.music_name())
