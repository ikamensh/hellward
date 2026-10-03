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
			test_a_curse_lands_on_a_tower, test_r_sings_battle_hymn_over_a_tower,
			test_a_monster_at_the_shrine_strikes_it_and_is_gone, test_the_plate_of_a_monster_under_the_mouse,
			test_defeat_ends_the_battle_and_its_music,
			test_the_watched_defence_holds_and_ends_with_victory, test_a_campaign_walk_through_every_screen,
			test_a_run_from_the_long_night_to_its_laying_down, test_the_camp_offers_relics_and_one_is_taken,
			test_the_bar_offers_the_grind_and_g_skips_it, test_the_card_teaches_strategies_sold_in_the_forge,
			test_every_location_lays_out_and_plays]:
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


## Wait for `ready` to hold: up to `limit` seconds of game time and, as well, of real time (headless frames can
## outrun a slow server, a CI runner's); whether it did.
func until(ready: Callable, limit: float) -> bool:
	var started := Time.get_ticks_msec()
	var budget := int(limit * 30 / Engine.time_scale) + 1
	var i := 0
	while not ready.call():
		if i >= budget and Time.get_ticks_msec() - started >= limit * 1000:
			return false
		i += 1
		await frames(1)
	return true


## Let a battle run until it is decided or `limit` seconds of its own time pass, however slowly the machine steps it.
func play_out(w: World, limit: float) -> bool:
	while w.outcome == "" and w.time < limit:
		await frames(30)
	return w.outcome != ""


func press(vp: Viewport, keycode: Key) -> void:
	var key := InputEventKey.new()
	key.keycode = keycode
	key.physical_keycode = keycode   # the game reads keys by their place (a QWERTY keyboard here)
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


## The mouse moved to `at` (the 3D point under it) on the battle's screen.
func move_mouse(m: Node, at: Vector3) -> void:
	var vp: Viewport = m.get_viewport()
	var ev := InputEventMouseMotion.new()
	ev.position = vp.get_final_transform() * m.rig.cam.unproject_position(at)
	vp.push_input(ev)


## Win `location` for the profile in play, its defence played by the campaign's scripted `player` (the tests' honest
## way on to a later location); whether it was won.
func win(location: String, player: String) -> bool:
	var reply: Dictionary = await Net.ask("defend", {"location": location, "player": player}).done
	if not bool(reply["ok"]):
		return false
	var last := [{}]
	var keep := func(f: Dictionary): last[0] = f
	Net.frame.connect(keep)
	var step := 0
	while not last[0].has("result"):
		step += 400
		Net.advance(400)
		var started := Time.get_ticks_msec()
		while not last[0].has("result") and int(last[0].get("step", 0)) < step and Time.get_ticks_msec() - started < 60000:
			await frames(1)
	Net.frame.disconnect(keep)
	return bool(last[0]["result"]["won"])


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
	var lane := Vector2i(16, 9)
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


## Towers by the lanes draw a Fallen Shaman's curse: the tower shows it, and its card says which and how long.
func test_a_curse_lands_on_a_tower() -> void:
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
	await frames(2)
	check(m.hud._curse_box.visible and String(w.start["curses"][cursed.curses.keys()[0]]["name"]).to_upper()
		in m.hud._curse_text.text.to_upper(), "the chosen tower's card names its curse (%s)" % m.hud._curse_text.text)
	check(not w.offers("cleanse") and not m.hud._spell_slots.has("cleanse"), "no Cleanse lifts it")


## At the Graveyard, where Battle Hymn is learned: R with a tower chosen sings it over that tower for mana, and its
## gold aura shows while the server's seconds last; with none chosen, R takes Hymn in hand and a click on a tower
## casts it there.
func test_r_sings_battle_hymn_over_a_tower() -> void:
	await Net.ask("create_profile", {"name": "singer"}).done
	check(await win("tristram", "adaptive"), "the campaign's scripted player holds Tristram, opening the Graveyard")
	var learned: Dictionary = await Net.ask("learn", {"key": "unlock_hymn"}).done
	check(bool(learned["ok"]), "Tristram's sigils learn Battle Hymn's unlock")
	var m := await start({"location": "graveyard"})
	m.rig.user_control = false
	var w: World = m.world
	check(w.offers("hymn") and m.hud._spell_slots.has("hymn"), "Hymn is on the spell bar")
	var tiles := lane_side(m.level, 2)
	for tile in tiles:
		await w.order("build", {"kind": "arrow", "tile": [tile.x, tile.y]})
	check(w.towers.size() == 2, "two towers stand (%d)" % w.towers.size())
	if w.towers.size() < 2:
		await Net.ask("switch_profile", {"name": "main"}).done
		return
	var first: Tower = w.tower_at(tiles[0])
	var second: Tower = w.tower_at(tiles[1])
	Engine.time_scale = 4.0
	check(await until(func(): return w.mana >= w.spell_cost("hymn"), 120.0), "the mana for a hymn wells up")
	Engine.time_scale = 1.0
	m.builder.choose(first)
	var mana := w.mana
	press(m.get_viewport(), KEY_R)
	check(await until(func(): return first.hymn > 0.0, 3.0), "R sings Hymn over the chosen tower")
	check(w.mana < mana, "Hymn costs mana (%.0f -> %.0f)" % [mana, w.mana])
	check(is_instance_valid(first._aura) and m.hud._hymn_box.visible, "its gold aura shows, and its card the hymn's time")
	check(await until(func(): return first.hymn <= 0.0, 30.0), "the hymn ends when the server says")
	await frames(2)
	check(not is_instance_valid(first._aura), "and its aura goes with it")
	m.builder.choose(null)
	Engine.time_scale = 4.0
	check(await until(func(): return w.mana >= w.spell_cost("hymn") and w.recharge("hymn") <= 0.0, 120.0),
		"Hymn gathers itself again")
	Engine.time_scale = 1.0
	press(m.get_viewport(), KEY_R)
	await frames(2)
	check(m.builder.held == "spell:hymn", "with no tower chosen, R takes Hymn in hand (%s)" % m.builder.held)
	click(m, second.tile)
	check(await until(func(): return second.hymn > 0.0, 3.0), "a click on a tower casts it there")
	check(m.builder.held == "", "the hand is empty after the cast")
	await Net.ask("switch_profile", {"name": "main"}).done


## An undefended Tristram: the first monster to reach the end of its road walks up to the shrine's gate, strikes it,
## and the shrine's light obliterates it; a life is lost.
func test_a_monster_at_the_shrine_strikes_it_and_is_gone() -> void:
	var m := await start()
	var w: World = m.world
	Engine.time_scale = 4.0
	var leaks := []
	w.happened.connect(func(e: Array): if e[0] == "leak": leaks.append(int(e[1])))
	await w.order("call_wave")
	check(await until(func(): return not leaks.is_empty(), 300.0), "a monster reaches the shrine")
	if leaks.is_empty():
		return
	Engine.time_scale = 1.0
	var striker: Monster = w.monsters.get(leaks[0])
	check(striker != null and not striker.alive(), "it stops being a living foe at once")
	if striker == null:
		return
	check(w.lives < w.start_lives, "a life is lost (%d)" % w.lives)
	check(await until(func(): return striker._struck, 5.0), "it strikes the gate and the light answers")
	check(await until(func(): return not w.monsters.has(leaks[0]), 3.0), "then it is gone")


## The mouse on a monster shows its plate: its name and life, its armor, its tags, and the hit each tower of the
## arsenal deals it at each rank, as the server's table says. The Catacombs bring armored Overlords.
func test_the_plate_of_a_monster_under_the_mouse() -> void:
	var m := await start({"demo": "", "player": "ordinary", "location": "catacombs"})
	m.rig.user_control = false   # the virtual cursor would pan the camera at the screen's edge
	var w: World = m.world
	Engine.time_scale = 8.0
	var visible := func() -> Monster:
		for mon in w.living():
			if mon._age > Monster.EMERGE and m.rig.cam.is_position_in_frustum(mon.chest()):
				return mon
		return null
	var ok := await until(func(): return visible.call() != null, 300.0)
	check(ok, "a monster walks in sight")
	Engine.time_scale = 1.0
	w.set_paused(true)
	await frames(2)
	var mon: Monster = visible.call()
	if mon == null:
		return
	move_mouse(m, mon.chest())
	await frames(2)
	check(m.hud.hovered() == mon, "the plate is the monster's under the mouse")
	var text: String = m.hud.hover_text()
	var table: Dictionary = mon.stats
	check(mon.title() in text, "it names the monster (%s)" % text)
	var armor := int(table["armor"])
	check(text.contains("Armor %d" % armor) if armor > 0 else not text.contains("Armor"), "it says its armor (%d)" % armor)
	for e in table["protected"]:
		check(String(e).capitalize() in text, "it names its protection from %s" % e)
	var hits: Dictionary = table["hits"]
	check(not hits.is_empty(), "the server tells the hits it takes")
	for kind in hits:
		var row := "%s %d %d %d" % [w.tower_table(kind)["name"], int(hits[kind][0]), int(hits[kind][1]), int(hits[kind][2])]
		check(row in text, "its row for the %s: %s" % [kind, row])
	move_mouse(m, mon.chest() + Vector3(0, 30, 0))
	await frames(2)
	check(m.hud.hovered() == null, "the plate goes when the mouse leaves it")



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
	var built := [0]   # towers raised: the bot sells those the last monsters have passed
	w.happened.connect(func(e: Array): if e[0] == "built": built[0] += 1)
	var largest := [""]
	var keep := func(f: Dictionary):
		var text := JSON.stringify(f)
		if text.length() > largest[0].length():
			largest[0] = text
	Net.frame.connect(keep)
	check(await play_out(w, 900.0), "the watched defence ends")
	Net.frame.disconnect(keep)
	var started := Time.get_ticks_usec()
	for i in 100:
		JSON.parse_string(largest[0])
	var parse := (Time.get_ticks_usec() - started) / 100.0
	print("   largest frame %d bytes, parsed in %.0f us" % [largest[0].length(), parse])
	check(parse < 500.0, "the client parses the largest frame in under half a millisecond (%.0f us)" % parse)
	check(w.outcome == "victory", "the scripted defence wins (outcome '%s', wave %d, lives %d)" % [w.outcome, w.wave + 1, w.lives])
	check(built[0] >= 4, "it built a defence (%d towers)" % built[0])
	check(Sfx.music_name() == "title", "the title's music plays after the victory (%s)" % Sfx.music_name())


## The campaign's ways, against the real server: the title, a new profile, the prologue, the map (the lantern walks
## to Tristram), its before page, the briefing, the skill tree, a defence (lost: no towers), the reckoning, the map
## again and the title. Keys and clicks as a player gives them.
func test_a_campaign_walk_through_every_screen() -> void:
	var game: Game = load("res://scenes/game.tscn").instantiate()
	_main = game
	var seen: Array = []
	game.shown.connect(func(s: Screen): seen.append(s.get_script().get_global_name()))
	add_child(game)
	var vp := game.get_viewport()
	check(await until(func(): return _showing(seen, "TitleScreen"), 10.0), "the title shows (%s)" % [seen])
	await frames(20)
	press(vp, KEY_P)
	check(await until(func(): return _showing(seen, "ProfilesScreen"), 5.0), "P opens the profiles (%s)" % [seen])
	var made = await game.ask("create_profile", {"name": "walker"})
	check(made != null and made["current"] == "walker", "a new profile is made and chosen")
	game.close(game._overlays.back())
	await frames(20)
	press(vp, KEY_ENTER)
	check(await until(func(): return _showing(seen, "PrologueScreen"), 5.0), "Descend on a new campaign plays the prologue (%s)" % [seen])
	await frames(20)
	press(vp, KEY_ESCAPE)
	check(await until(func(): return _showing(seen, "MapScreen"), 5.0), "Esc ends it on the map (%s)" % [seen])
	check(await until(func(): return _showing(seen, "StoryScreen"), 10.0), "the lantern walks to Tristram and its before page is told (%s)" % [seen])
	await frames(20)
	press(vp, KEY_ESCAPE)
	check(await until(func(): return _showing(seen, "BriefingScreen"), 5.0), "then its intro (%s)" % [seen])
	await frames(20)
	press(vp, KEY_K)
	check(await until(func(): return _showing(seen, "SkillsScreen"), 5.0), "K opens the skill tree (%s)" % [seen])
	await frames(20)
	press(vp, KEY_ESCAPE)
	await frames(20)
	check(game._overlays.is_empty(), "Esc closes it over the intro")
	press(vp, KEY_ENTER)
	check(await until(func(): return game.battle != null and game.battle.world != null, 10.0), "Defend starts the battle")
	if game.battle == null:
		return
	var w: World = game.battle.world
	Engine.time_scale = 8.0
	check(await until(func():
		if w.can_call():
			w.order("call_wave")
		return _showing(seen, "ReckoningScreen"), 600.0), "an undefended Tristram falls to the reckoning (%s)" % [seen])
	Engine.time_scale = 1.0
	await frames(40)
	press(vp, KEY_ESCAPE)
	check(await until(func(): return _showing(seen, "MapScreen") and game.battle == null, 10.0), "To the map leaves the battle (%s)" % [seen])
	await frames(20)
	press(vp, KEY_ESCAPE)
	check(await until(func(): return _showing(seen, "TitleScreen"), 5.0), "and Esc goes back to the title (%s)" % [seen])
	var view = await game.ask("campaign")
	check(view["profile"] == "walker" and int(view["sigils"]) == 0, "the walker's campaign holds no sigils after a fall")


## A run end to end: R on the title begins the Long Night at the camp, Continue walks into the wagered intro,
## Defend starts the battle (the run's goals stand over it), an undefended Tristram falls to a reckoning that
## names the goals met and missed, and Onward lays the lost run down at its summary, back to the title.
func test_a_run_from_the_long_night_to_its_laying_down() -> void:
	var game: Game = load("res://scenes/game.tscn").instantiate()
	_main = game
	var seen: Array = []
	var faced := [null]
	game.shown.connect(func(s: Screen):
		seen.append(s.get_script().get_global_name())
		faced[0] = s)
	add_child(game)
	var made = await game.ask("create_profile", {"name": "runner"})
	check(made != null and made["current"] == "runner", "a runner's profile is made and chosen")
	var vp := game.get_viewport()
	check(await until(func(): return _showing(seen, "TitleScreen"), 10.0), "the title shows (%s)" % [seen])
	await frames(20)
	press(vp, KEY_R)
	check(await until(func(): return _showing(seen, "CampScreen"), 10.0), "R begins the Long Night at the camp (%s)" % [seen])
	await frames(20)
	press(vp, KEY_ENTER)
	check(await until(func(): return _showing(seen, "StoryScreen"), 10.0), "Continue walks into the place's before page (%s)" % [seen])
	await frames(20)
	press(vp, KEY_ESCAPE)
	check(await until(func(): return _showing(seen, "BriefingScreen"), 5.0), "then its intro (%s)" % [seen])
	await frames(20)
	press(vp, KEY_ENTER)
	check(await until(func(): return game.battle != null and game.battle.world != null, 10.0), "Defend starts the battle")
	if game.battle == null:
		return
	var w: World = game.battle.world
	check(not w.goals.is_empty(), "the run's goals are wagered on the battle (%d)" % w.goals.size())
	await frames(2)
	check(game.battle.hud._goals_box.visible, "and their lines stand over it")
	Engine.time_scale = 8.0
	check(await until(func():
		if w.can_call():
			w.order("call_wave")
		return _showing(seen, "ReckoningScreen"), 600.0), "an undefended Tristram falls to the reckoning (%s)" % [seen])
	Engine.time_scale = 1.0
	check(faced[0] != null and (faced[0] as Screen).data.has("run"), "the reckoning carries the run")
	await frames(40)
	press(vp, KEY_ENTER)
	check(await until(func(): return _showing(seen, "SummaryScreen") or _showing(seen, "CampScreen"), 10.0),
		"Onward lays the run down (%s)" % [seen])
	await frames(20)
	press(vp, KEY_ENTER)
	check(await until(func(): return _showing(seen, "TitleScreen"), 10.0), "and it ends back at the title (%s)" % [seen])
	var view = await game.ask("campaign")
	check(view != null and int(view["runs_lost"]) >= 1, "the runner's campaign counts the lost run")
	await Net.ask("switch_profile", {"name": "main"}).done


## A run's relic: the camp after a held Tristram offers three, and the first key takes one into the run.
func test_the_camp_offers_relics_and_one_is_taken() -> void:
	await Net.ask("create_profile", {"name": "relic"}).done
	var started: Dictionary = await Net.ask("start_run", {"seed": 11}).done
	check(bool(started["data"]["active"]), "a run starts")
	check(await win("tristram", "adaptive"), "the campaign's scripted player holds Tristram in the run")
	await Net.ask("leave", {"again": true}).done   # the reckoning's Onward: the camp may take relics now
	var view: Dictionary = (await Net.ask("run").done)["data"]
	check((view["offer"] as Array).size() == 3, "the camp offers three relics")
	var game: Game = load("res://scenes/game.tscn").instantiate()
	_main = game
	var seen: Array = []
	game.shown.connect(func(s: Screen): seen.append(s.get_script().get_global_name()))
	add_child(game)
	check(await until(func(): return _showing(seen, "TitleScreen"), 10.0), "the title shows")
	game.camp()
	check(await until(func(): return _showing(seen, "CampScreen"), 10.0), "the camp shows (%s)" % [seen])
	await frames(20)
	var held := 0
	for i in 150:   # the camp lays out after its own ask: knock until it answers
		press(game.get_viewport(), KEY_1)
		await frames(2)
		var after = await game.ask("run")
		if after != null and (after["relics"] as Array).size() == 1 and (after["offer"] as Array).is_empty():
			held = 1
			break
	check(held == 1, "the first key takes one into the run")
	await Net.ask("switch_profile", {"name": "main"}).done


## The grind's skip on the bar: no button without the server's offer, the button with its bonus with one,
## and G sends the skip as an order (refused here: the offer is this test's, not a live wave's).
func test_the_bar_offers_the_grind_and_g_skips_it() -> void:
	var m := await start()
	m.rig.user_control = false
	var w: World = m.world
	check(not m.hud._skip.visible, "no offer on the break: no button")
	w.state["skip_offer"] = {"wave": 0, "bonus": 12}
	m.hud.refresh()
	check(m.hud._skip.visible and "+12" in m.hud._skip.text, "the button shows the offer's bonus")
	var why := []
	w.refused.connect(func(text: String): why.append(text))
	press(m.get_viewport(), KEY_G)
	check(await until(func(): return not why.is_empty(), 3.0), "G sends the skip as an order")
	check(why.size() > 0 and "surely clean" in why[0], "refused: no live wave is surely clean (%s)" % [why])


## Strategies on the card and in the forge: no button with only Foremost taught, the aim's button with two,
## and M sends the teaching as an order (refused here: the profile taught nothing); the forge's last slot sells
## the four aims and the attunement for salvage.
func test_the_card_teaches_strategies_sold_in_the_forge() -> void:
	var m := await start()
	m.rig.user_control = false
	var w: World = m.world
	var tile: Vector2i = lane_side(m.level, 1)[0]
	await w.order("build", {"kind": "arrow", "tile": [tile.x, tile.y]})
	var tower: Tower = w.tower_at(tile)
	m.builder.choose(tower)
	await frames(2)
	check(not m.hud._mode.visible, "only Foremost taught: no button on the card")
	w.start["modes"] = [{"key": "first", "name": "Foremost", "words": ""},
		{"key": "strong", "name": "Strongest", "words": ""}]
	m.hud.refresh()
	check(m.hud._mode.visible and "FOREMOST" in m.hud._mode.text, "with two taught, the card names the aim")
	var why := []
	w.refused.connect(func(text: String): why.append(text))
	press(m.get_viewport(), KEY_M)
	check(await until(func(): return not why.is_empty(), 3.0), "M sends the teaching as an order")
	check(why.size() > 0 and "not taught" in why[0], "refused: the profile taught nothing (%s)" % [why])
	check(not m.hud._attune.visible, "attunement untaught: no button on the card")
	w.start["attune"] = {"unlocked": true, "gold": 25}
	m.hud.refresh()
	check(m.hud._attune.visible and "25" in m.hud._attune.text, "taught, the card offers it for its price")
	why.clear()
	press(m.get_viewport(), KEY_T)
	check(await until(func(): return not why.is_empty(), 3.0), "T sends the attunement as an order")
	check(why.size() > 0 and "not taught" in why[0], "refused: the profile taught nothing (%s)" % [why])
	_main.queue_free()
	await frames(2)
	_main = null
	var game: Game = load("res://scenes/game.tscn").instantiate()
	_main = game
	var seen: Array = []
	game.shown.connect(func(s: Screen): seen.append(s.get_script().get_global_name()))
	add_child(game)
	check(await until(func(): return _showing(seen, "TitleScreen"), 10.0), "the title shows (%s)" % [seen])
	game.forge()
	check(await until(func(): return _showing(seen, "ForgeScreen"), 10.0), "the forge opens (%s)" % [seen])
	await frames(20)
	var poor := 0
	var forge: Screen = game._overlays.back()
	for b in forge.find_children("*", "Button", true, false):
		if (b as Button).text == "Need more salvage":
			poor += 1
	check(poor == 5, "its last slot sells the four aims and the attunement (%d)" % poor)


## Every location of both acts lays out (its scenery, its arsenal on the bar) and its battle runs a few seconds,
## a scripted player defending: a script error anywhere fails the suite (tools/test.sh).
func test_every_location_lays_out_and_plays() -> void:
	var view: Dictionary = (await Net.ask("campaign").done)["data"]
	var seen := {}   # the kinds whose bodies are checked (check_bodies), over every location's battle
	for act in view["acts"]:
		for place in act["places"]:
			var key := String(place["key"])
			var m := await start({"demo": "", "player": "ordinary", "location": key})
			var w: World = m.world
			Engine.time_scale = 8.0
			await seconds(4)
			Engine.time_scale = 1.0
			var arsenal: Dictionary = w.start["arsenal"]
			var bar: int = arsenal["towers"].size() + (1 if bool(arsenal["gates"]) else 0)
			check(m.hud.slots().size() == bar, "%s: the bar holds its arsenal (%d of %d)" % [key, m.hud.slots().size(), bar])
			check(w.time > 5.0 and w.outcome == "", "%s: its battle runs (%.0f s)" % [key, w.time])
			check(w.level.portals.size() >= 1 and m.has_node("Dressing"), "%s: its scenery stands" % key)
			await check_bodies(w, seen)
			_main.queue_free()
			await frames(2)


func _showing(seen: Array, screen: String) -> bool:
	return not seen.is_empty() and seen.back() == screen


## Every monster and tower kind of a battle not `seen` before, dressed as the battle dresses it: its model
## instantiates with the library's materials (none left untextured), a monster plays every clip monster.gd asks of
## it (and a leader its cast) without its bones going wild, and a tower of every rank stands with the anchors its
## effects hang on.
func check_bodies(w: World, seen: Dictionary) -> void:
	for kind in w.start["monsters"]:
		if seen.has("m:" + kind):
			continue
		seen["m:" + kind] = true
		var own := ResourceLoader.exists("res://assets/models/mon_%s.glb" % kind)
		var base := String(kind) if own else String(Monster.STAND_INS.get(kind, ["?"])[0])
		check(own or Monster.STAND_INS.has(kind), "%s: a model or a stand-in" % kind)
		if not ResourceLoader.exists("res://assets/models/mon_%s.glb" % base):
			continue
		var body := Models.make("mon_" + base)
		add_child(body)
		var player := Models.player(body)
		var clips := ["idle", "walk", "attack", "die", "die2"]
		if w.start["monsters"][kind]["leader"] != null:
			clips.append("cast")
		for clip in clips:
			var name := Models.anim_name(player, clip)
			check(name != "", "%s: has its %s clip" % [kind, clip])
			if name == "":
				continue
			player.play(name)
			player.seek(player.get_animation(name).length * 0.5, true)
			await frames(1)
			var box := AABB()
			for mi in body.find_children("*", "MeshInstance3D", true, false):
				box = box.merge((mi as MeshInstance3D).get_aabb())
			check(box.size.length() < 12.0, "%s %s: its bones stay together (bounds %.1f m)" % [kind, clip, box.size.length()])
		for mi in body.find_children("*", "MeshInstance3D", true, false):
			for i in (mi as MeshInstance3D).mesh.get_surface_count():
				var mat := (mi as MeshInstance3D).get_active_material(i)
				check(mat is BaseMaterial3D and ((mat as BaseMaterial3D).albedo_texture != null
					or (mat as BaseMaterial3D).emission_enabled or (mat as BaseMaterial3D).albedo_color != Color.WHITE),
					"%s: surface %d of %s is dressed by the library" % [kind, i, mi.name])
		body.queue_free()
	for kind in w.start["towers"]:
		if seen.has("t:" + kind):
			continue
		seen["t:" + kind] = true
		for rank in 3:
			var model := Tower.model_name(kind, rank)
			check(model == "tower_%s_%d" % [kind, rank + 1] and ResourceLoader.exists("res://assets/models/%s.glb" % model),
				"%s rank %d: its own model is built (%s)" % [kind, rank + 1, model])
			var body := Models.make(model)
			add_child(body)
			check(Models.node(body, "fx_muzzle") != null or Models.node(body, "fx_fire") != null,
				"%s rank %d: has an anchor its shots leave from" % [kind, rank + 1])
			body.queue_free()
