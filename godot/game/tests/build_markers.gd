extends "res://tests/run.gd"
## Build-clarity input tests: the ghost's states under the mouse (ok, ground, taken, poor), the whole-map
## buildability field, the gate-arch diamonds, and the staging args captures use (build=/ghost=/choose=). Each builds
## the real battle scene against the real server and plays it with the inherited hands (press/click/move_mouse).
## Wiring (run.gd stays untouched until the parent wires this): in run.gd's _ready, add a child of this script and
## await its all_tests(), appending its failures; standalone, a temporary res://tests/build_markers.tscn (a Node with
## this script) runs them through tools/test.sh's shape.

func all_tests() -> Array:
	return [test_ghost_valid_on_bare_floor, test_ghost_refused_on_the_lane, test_ghost_taken_on_a_standing_tower,
		test_ghost_poor_without_the_gold, test_field_and_slot_follow_the_hand,
		test_arch_diamonds_show_while_the_gate_is_held, test_staging_args_hold_and_place]


func _ready() -> void:
	if not await Net.wait_ready():
		print("FAILED: no server: ", Net.error)
		get_tree().quit(1)
		return
	var only := OS.get_environment("HELLWARD_TEST")
	for t in all_tests():
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


## 1 holds an Arrow Tower and the bare floor takes it: the ghost shows green, no cursor tag, the field on.
func test_ghost_valid_on_bare_floor() -> void:
	var m := await start()
	m.rig.user_control = false
	var tile := Vector2i(14, 7)
	check(m.level.cell(tile) == ".", "the test tile is bare floor")
	press(m.get_viewport(), KEY_1)
	await frames(2)
	check(m.builder.held == "arrow", "1 holds an Arrow Tower")
	move_mouse(m, m.level.tile_pos(tile))
	await frames(2)
	check(m.builder.ghost_state("arrow", tile) == "ok", "the ghost calls bare floor ok")
	check(m.builder._ghost.visible, "the ghost shows on bare floor")
	check(not m.hud._hint.visible, "no cursor tag where a tower may rise")
	check(m.builder._field.visible, "the buildability field shows while a tower is held")


## On the lane the ghost refuses: ground state, and the cursor tag says bare floor.
func test_ghost_refused_on_the_lane() -> void:
	var m := await start()
	m.rig.user_control = false
	var lane := Vector2i(16, 9)
	check(m.level.cell(lane) == "P", "the test tile is a lane")
	press(m.get_viewport(), KEY_1)
	await frames(2)
	move_mouse(m, m.level.tile_pos(lane))
	await frames(2)
	check(m.builder.ghost_state("arrow", lane) == "ground", "the ghost calls the lane unbuildable ground")
	check(m.hud._hint.visible and "Bare floor" in m.hud._hint_text.text,
		"the cursor tag says bare floor (%s)" % m.hud._hint_text.text)


## Where a tower stands the ghost calls it taken, and the cursor tag says occupied.
func test_ghost_taken_on_a_standing_tower() -> void:
	var m := await start()
	m.rig.user_control = false
	var w: World = m.world
	var tile := Vector2i(14, 7)
	await w.order("build", {"kind": "arrow", "tile": [tile.x, tile.y]})
	check(w.towers.size() == 1, "a tower stands on the tile")
	press(m.get_viewport(), KEY_1)
	await frames(2)
	move_mouse(m, m.level.tile_pos(tile))
	await frames(2)
	check(m.builder.ghost_state("arrow", tile) == "taken", "the ghost calls a standing tower taken")
	check(m.hud._hint.visible and "Occupied" in m.hud._hint_text.text,
		"the cursor tag says occupied (%s)" % m.hud._hint_text.text)


## With the purse short of the price the ghost calls it poor, and the cursor tag names the price.
func test_ghost_poor_without_the_gold() -> void:
	var m := await start()
	m.rig.user_control = false
	var w: World = m.world
	for tile in lane_side(m.level, 6):
		if w.gold < w.tower_cost("arrow"):
			break
		await w.order("build", {"kind": "arrow", "tile": [tile.x, tile.y]})
	check(w.gold < w.tower_cost("arrow"), "the purse cannot cover another Arrow (%d gold)" % w.gold)
	press(m.get_viewport(), KEY_1)
	await frames(2)
	check(m.builder.held == "arrow", "1 still holds an Arrow Tower")
	var tile := _free_floor(m)
	move_mouse(m, m.level.tile_pos(tile))
	await frames(2)
	check(m.builder.ghost_state("arrow", tile) == "poor", "the ghost calls an empty purse poor")
	check(m.hud._hint.visible and "gold" in m.hud._hint_text.text,
		"the cursor tag names the price (%s)" % m.hud._hint_text.text)


## The field and the held slot follow the hand: on with a tower held, gone when it lets go.
func test_field_and_slot_follow_the_hand() -> void:
	var m := await start()
	m.rig.user_control = false
	check(not m.builder._field.visible, "no field with an empty hand")
	press(m.get_viewport(), KEY_1)
	await frames(2)
	check(m.builder._field.visible, "the field shows while a tower is held")
	check(m.hud.held() == "arrow", "the HUD knows the hand holds an Arrow")
	press(m.get_viewport(), KEY_ESCAPE)
	await frames(2)
	check(m.builder.held == "", "Esc lets go")
	check(not m.builder._field.visible, "the field goes with it")
	check(m.hud.held() == "", "the HUD knows the hand is empty")


## At the Graveyard, where the gate is offered: holding it diamonds every arch, and the arch's tile offers warding.
func test_arch_diamonds_show_while_the_gate_is_held() -> void:
	await Net.ask("create_profile", {"name": "warder"}).done
	check(await win("tristram", "adaptive"), "the scripted player holds Tristram, opening the Graveyard")
	var m := await start({"location": "graveyard"})
	m.rig.user_control = false
	var w: World = m.world
	check(w.offers("gate"), "the Graveyard offers the gate")
	check(not w.level.arches.is_empty(), "its doors have arch sockets")
	var slots: Array = m.hud.slots()
	check(slots.find("gate") == 1, "the gate is the bar's second slot (%s)" % [slots])
	press(m.get_viewport(), KEY_2)
	await frames(2)
	check(m.builder.held == "gate", "2 holds the gate")
	check(m.hud.held() == "gate", "the HUD marks the gate slot held")
	var shown: int = m.builder._arch_marks.filter(func(d): return d.visible).size()
	check(shown == w.level.arches.size() and shown > 0, "every arch shows its diamond (%d)" % shown)
	var arch_tile: Vector2i = w.level.arches[0][1]
	move_mouse(m, m.level.tile_pos(arch_tile))
	await frames(2)
	check(m.builder._tile_mark.visible, "the arch's tile is marked")
	check(m.hud._hint.visible and "arch" in m.hud._hint_text.text.to_lower(),
		"the cursor tag offers to ward it (%s)" % m.hud._hint_text.text)
	await Net.ask("switch_profile", {"name": "main"}).done


## Captures' staging args: ghost= holds with the cursor staged, build= orders, choose= chooses, spells too.
func test_staging_args_hold_and_place() -> void:
	var m := await start()
	m.rig.user_control = false
	var w: World = m.world
	check(m.level.cell(Vector2i(16, 7)) == ".", "the build tile is bare floor")
	m.builder.stage("ghost=arrow@14,7")
	await frames(2)
	check(m.builder.held == "arrow", "ghost= holds the tower")
	check(m.builder._staged == Vector2i(14, 7), "and stages the cursor on its tile")
	check(m.builder._ghost.visible, "the staged ghost shows")
	check(m.builder._field.visible, "the field shows for a staged hold")
	m.builder.stage("build=arrow@16,7")
	check(await until(func(): return w.towers.size() == 1, 5.0), "build= raises the ordered tower")
	m.builder.stage("choose=@16,7")
	await frames(3)
	check(m.builder.chosen != null and m.builder.chosen.tile == Vector2i(16, 7), "choose= chooses the tower there")
	check(m.builder._reach_mark.visible, "its reach shows")
	m.builder.let_go()
	m.builder.stage("ghost=smite@16,9")
	await frames(2)
	check(m.builder.held == "spell:smite", "ghost= holds a spell too")
	check(m.builder._reach_mark.visible, "its ring shows")
	check(m.hud._hint.visible and "Smite" in m.hud._hint_text.text,
		"with its cursor hint (%s)" % m.hud._hint_text.text)


## A bare floor tile with no tower on it.
func _free_floor(m: Node) -> Vector2i:
	for y in m.level.height:
		for x in m.level.width:
			var t := Vector2i(x, y)
			if m.level.cell(t) == "." and m.world.tower_at(t) == null:
				return t
	return Vector2i(-1, -1)
