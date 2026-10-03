class_name World
extends Node3D
## One defence as the server plays it: this side keeps the clock and shows what each step brings.
##
## The rules run in the server (hellward/sim through hellward/server). Each frame of the game this node counts
## the time that passed (Engine.time_scale is the pace) and asks for the whole steps it adds up to; each step comes
## back as a frame: its events, the purse, and every monster, tower and gate as they stand. Monsters and towers here
## are pictures of the server's, kept by id; between two steps they glide (`alpha`). Orders go to the server
## (`order`) and come back accepted, with their events, or refused with the reason the HUD shows.

signal changed                       # the purse, the clocks or a tower moved: the HUD redraws
signal announce(title: String, line: String)
signal finished(won: bool)
signal refused(why: String)
signal happened(e: Array)            # every event, after this side has shown it (the film director, the chronicle)
signal towers_changed                # a tower was sold

const MAX_AHEAD := 4                 # steps asked for and not yet back before the clock waits (a slow planner)

var level: Level
var dressing: Dressing               # the scenery: it shows each arch's gate as the server says
var start: Dictionary                # the battle message: map, waves, tables
var state: Dictionary                # the latest frame's purse and clocks
var monsters := {}                   # id -> Monster
var towers := {}                     # id -> Tower
var doors: Array = []                # [index, hp, built, rubble]
var hazards: Array = []
var gold := 0
var lives := 20
var start_lives := 20
var mana := 0.0
var mana_max := 100.0
var wave := -1
var outcome := ""                    # "victory" or "defeat"
var result: Dictionary = {}          # the reckoning the server made of a person's decided defence
var time := 0.0
var step := 0
var alpha := 1.0                     # how far between the last two steps the picture is
var slain := {}                      # wave -> its monsters killed, counted from deaths (the HUD's tally)
var goals: Array = []                # the run's wager here: [{key, arg, line, verdict}], kept live
var xp := 0.0
var xp_level := 1
var xp_next := 0.0
var demo := false                    # a scripted player plays (the demo, or a playtest): this side only watches
var minds := true                    # say what the leaders weighed (the settings' "leaders' minds")
var paused := false
var dt := 0.05

var _acc := 0.0
var _ahead := 0
var _seen_steps := 0


func setup(lvl: Level, battle: Dictionary) -> void:
	level = lvl
	start = battle
	dt = float(battle["sim_dt"])
	demo = bool(battle["scripted"])
	goals = (battle.get("goals", []) as Array).duplicate(true)
	_take_state(battle["state"])
	start_lives = lives
	Net.frame.connect(_on_frame)


## A boss walks the map: its strikes at the shrine cost boss_strike_lives each.
func boss_out() -> bool:
	for m in living():
		if bool(monster_table(m.kind)["boss"]):
			return true
	return false


func _exit_tree() -> void:
	if Net.frame.is_connected(_on_frame):
		Net.frame.disconnect(_on_frame)


# -- What the HUD asks -----------------------------------------------------------------------------

func waves() -> Array:
	return start["waves"]


func roster(i: int) -> Array:
	return waves()[i]["groups"]


func can_call() -> bool:
	return bool(state["can_call"])


func tower_cost(kind: String) -> int:
	return int(state["cost"].get(kind, 0))


func spell_cost(key: String) -> float:
	return float(state["spell_cost"].get(key, 0.0))


func recharge(key: String) -> float:
	return float(state["recharge"].get(key, 0.0))


func offers(thing: String) -> bool:
	var arsenal: Dictionary = start["arsenal"]
	return thing in arsenal["towers"] or thing in arsenal["spells"] or (thing == "gate" and bool(arsenal["gates"]))


func tower_table(kind: String) -> Dictionary:
	return start["towers"][kind]


func monster_table(kind: String) -> Dictionary:
	return start["monsters"][kind]


func tower_at(tile: Vector2i) -> Tower:
	for t in towers.values():
		if t.tile == tile and not t.removed:
			return t
	return null


func living() -> Array:
	return monsters.values().filter(func(m): return m.alive())


## A point of the rules (tiles) on the ground here.
func ground(xy: Array) -> Vector3:
	return Level.point(xy)


# -- Orders ----------------------------------------------------------------------------------------

## An order to the server; whether it was accepted (a refusal is played and announced as `refused`).
func order(name: String, args := {}) -> bool:
	var reply: Dictionary = await Net.order(name, args).done
	if not bool(reply["ok"]):
		Sfx.play("refuse")
		refused.emit(String(reply["why"]))
		return false
	return true


func set_paused(on: bool) -> void:
	paused = on
	if not demo:
		Net.order("pause", {"paused": on})


# -- The clock -------------------------------------------------------------------------------------

func _process(delta: float) -> void:
	if outcome != "" or paused:
		alpha = 1.0
		return
	_acc = min(_acc + delta, dt * (MAX_AHEAD + 1))
	var n := 0
	while _acc >= dt and _ahead + n < MAX_AHEAD:
		_acc -= dt
		n += 1
	if n > 0:
		_ahead += n
		Net.advance(n)
	alpha = clamp(_acc / dt, 0.0, 1.0) if _ahead == 0 else 1.0


func _on_frame(m: Dictionary) -> void:
	var stepped := int(m["step"]) > step
	if stepped:
		_ahead = max(0, _ahead - (int(m["step"]) - step))
		step = int(m["step"])
		time = float(m["time"])
	for e in m["events"]:
		_event(e)
	_take_state(m["state"])
	for d in m["doors"]:   # a gate losing life: the monsters at it are battering it
		for was in doors:
			if int(was[0]) == int(d[0]) and float(d[1]) < float(was[1]) and bool(d[2]):
				Sfx.play("door_hit", level.tile_pos(_arch(int(d[0]))))
	doors = m["doors"]
	if dressing:
		var life: float = float(start["gate"]["life"]) if start["gate"] != null else 1.0
		for d in doors:
			dressing.gate(int(d[0]), bool(d[2]), bool(d[3]), float(d[1]) / max(life, 1.0))
	hazards = m["hazards"]
	var alive := {}
	for entry in m["monsters"]:
		var id := int(entry[0])
		alive[id] = true
		var mon: Monster = monsters.get(id)
		if mon != null:
			mon.sync(entry, stepped)
	for id in monsters.keys():
		var mon: Monster = monsters[id]
		if not alive.has(id) and mon.alive():
			mon.vanish()   # gone from the rules without a death or a leak we saw: let it fade
		if mon.gone:
			monsters.erase(id)
			mon.queue_free()
	for entry in m["towers"]:
		var t: Tower = towers.get(int(entry[0]))
		if t != null:
			t.sync(entry)
	if m.has("result"):
		result = m["result"]
	changed.emit()


func _take_state(s: Dictionary) -> void:
	state = s
	gold = int(s["gold"])
	lives = int(s["lives"])
	mana = float(s["mana"])
	mana_max = float(s["mana_max"])
	xp = float(s.get("xp", 0.0))
	xp_level = int(s.get("xp_level", 1))
	xp_next = float(s.get("xp_next", 0.0))
	wave = int(s["wave"])
	var was := outcome
	outcome = "" if s["outcome"] == null else String(s["outcome"])
	if was == "" and outcome != "":
		_decided()


func _decided() -> void:
	var won := outcome == "victory"
	if won:
		announce.emit("%s holds" % start["location"]["name"], "The last wave is broken. The lamp still burns.")
		Sfx.play("victory")
	else:
		announce.emit("The lamp goes out", "%s falls." % start["location"]["name"])
		Sfx.play("defeat")
		for n in monsters.values() + towers.values():   # the battle stops where it stands
			n.process_mode = Node.PROCESS_MODE_DISABLED
	finished.emit(won)


# -- Events: what each step shows ------------------------------------------------------------------

func _event(e: Array) -> void:
	var kind := String(e[0])
	match kind:
		"spawn":
			if e[2] != null:
				_spawn(int(e[1]), e[2])
		"breach_elite":
			announce.emit(String(e[2]), "An elite comes from the side entrance.")
		"built":
			_built(int(e[1]), e[2])
		"upgraded":
			var t: Tower = towers.get(int(e[1]))
			if t:
				t.promote(int(e[2]["level"]), int(e[2]["spent"]))
				Sfx.play("upgrade", t.global_position)
		"sold":
			var t: Tower = towers.get(int(e[1]))
			if t:
				towers.erase(int(e[1]))
				t.dismantle()
				Sfx.play("sell", t.global_position)
				towers_changed.emit()
		"salvage_sold":
			Sfx.play("gold")
		"door_built":
			Sfx.play("door_build", level.tile_pos(_arch(int(e[1]))))
		"door_broken":
			Vfx.dust(self, level.tile_pos(_arch(int(e[1]))), 2.5)
			Sfx.play("door_break", level.tile_pos(_arch(int(e[1]))))
		"hymn":
			var t: Tower = towers.get(int(e[1]))
			if t:
				t.hymned()
				Sfx.play("hymn", t.global_position)
		"smite":
			var at := ground(e[2])
			Vfx.lightning(self, [at + Vector3(0, 22, 0), at + Vector3(0, 1.0, 0)])
			Vfx.holy(self, at)
			Sfx.play("smite", at)
		"meteor_cast":
			Vfx.meteor(self, ground([e[1], e[2]]), float(e[3]))
			Sfx.play("meteor_fall", ground([e[1], e[2]]))
		"meteor":
			var at := ground([e[1], e[2]])
			Vfx.explosion(self, at, Color(1.0, 0.45, 0.1), true)
			Vfx.scorch(self, at, 3.0)
			Sfx.play("meteor", at)
		"orb":
			var at := ground([e[1], e[2]])
			Vfx.frost_burst(self, at + Vector3(0, 1.0, 0))
			Vfx.burst(self, at + Vector3(0, 1.0, 0), Color(0.5, 0.75, 1.0), 80)
			Sfx.play("orb", at)
		"wave":
			wave = int(e[1])
			var w: Dictionary = waves()[wave]
			var n: int = waves().size()
			announce.emit("Wave %d of %d" % [wave + 1, n], String(w["name"]))
			Sfx.play("wave")
			if wave == n - 1 and _has_boss(w):
				Sfx.music("boss", -6.0, 2.0)
		"cleared":
			var bonus := int(e[2])
			if outcome == "":
				announce.emit("The wave is broken", "+%d gold. Build, then summon the next wave." % bonus)
				Sfx.play("cleared")
		"ponder":
			var m: Monster = monsters.get(int(e[1]))
			if m:
				m.ponder()
		"chant", "mark":
			var m: Monster = monsters.get(int(e[1]))
			if m:
				m.chant(String(e[2]), Vector2i(int(e[3][0]), int(e[3][1])), kind == "mark")
		"fizzle":
			var m: Monster = monsters.get(int(e[1]))
			if m:
				m.stop_chant()
			Sfx.play("fizzle", level.tile_pos(Vector2i(int(e[2][0]), int(e[2][1]))))
		"cursed":
			_cursed(int(e[1]), Vector2i(int(e[2][0]), int(e[2][1])), String(e[3]), e[4])
		"curse_ended":
			var t: Tower = towers.get(int(e[1]))
			if t:
				t.curse_ends(String(e[2]))
		"burned":
			announce.emit("", "The curse burns %d mana." % int(e[2]))
		"leak":
			var m: Monster = monsters.get(int(e[1]))
			if m:
				m.leak()
			Sfx.play("leak")
		"returned":
			var m: Monster = monsters.get(int(e[1]))
			if m:
				m.returned(int(e[4]))
				Sfx.play("returned", level.door_pos)
				announce.emit("", "%s strikes the shrine for %d lives and is cast back to its portal." % [m.title(), int(e[3])])
		"hook":
			var t: Tower = towers.get(int(e[1]))
			var m: Monster = monsters.get(int(e[2]))
			if t and m:
				t.hook(m, float(e[3]))
		"bolt":
			var b: Dictionary = e[1]
			var t: Tower = towers.get(int(b["tower"]))
			if t:
				t.fire(b, monsters.get(int(b["target"])))
		"impact":
			var b: Dictionary = e[1]
			Tower.impact(self, b, ground(e[2]), monsters.get(int(b["target"])))
		"chain":
			var t: Tower = towers.get(int(e[1]))
			if t:
				var points: Array = [t.muzzle()]
				for i in e[2].size():
					var m: Monster = monsters.get(int(e[2][i]))
					points.append(m.chest() if m else ground(e[3][i]) + Vector3(0, 1.2, 0))
				t.strike(points)
		"nova":
			var t: Tower = towers.get(int(e[1]))
			if t:
				t.nova()
		"twister":
			var t: Tower = towers.get(int(e[1]))
			var m: Monster = monsters.get(int(e[2]))
			if t and m:
				Vfx.burst(self, m.chest(), Color(0.55, 0.9, 0.4), 40)
		"amplify":
			var t: Tower = towers.get(int(e[1]))
			if t:
				t.nova()
		"hit":
			var m: Monster = monsters.get(int(e[1]))
			if m:
				m.hit("" if e[2] == null else String(e[2]))
		"raised":
			var m: Monster = monsters.get(int(e[1]))
			if m:
				Vfx.burst(self, m.chest(), Color(0.6, 0.9, 0.5), 30)
		"death":
			var m: Monster = monsters.get(int(e[1]))
			if m:
				slain[m.wave] = slain.get(m.wave, 0) + 1
				m.die("" if e[3] == null else String(e[3]), int(e[5]))
		"salvage":
			Vfx.coin(self, ground(e[2]) + Vector3(0, 1.0, 0), 0)
		"shatter":
			Vfx.frost_burst(self, ground(e[2]) + Vector3(0, 1.0, 0))
		"corpse_explosion":
			Vfx.explosion(self, ground([e[1], e[2]]), Color(0.7, 0.9, 0.3), true)
		"contagion":
			var m: Monster = monsters.get(int(e[2]))
			if m:
				Vfx.burst(self, m.chest(), Color(0.5, 0.9, 0.2), 20)
		"breach_choice":
			announce.emit("", "The side entrance: %s." % String(e[1]))
		"breach_cleared":
			announce.emit("The side pack is broken", "The breach is cleared.")
		"breach_failed":
			announce.emit("", "The side pack got through.")
		"breach_cash":
			announce.emit("", "The side cache pays %d gold." % int(e[1]))
			Sfx.play("gold")
		"plan":
			if minds:
				_thought(monsters.get(int(e[1])), e[2])
		"victory", "defeat":
			pass
		"step":
			pass   # the save's second mark: nothing to show
		"goal":
			var line := ""
			for g in goals:
				if String(g["key"]) == String(e[1]):
					g["verdict"] = String(e[2])
					line = String(g["line"])
			if String(e[2]) == "met":
				announce.emit("Wager met", line)
				Sfx.play("cleared")
			else:
				announce.emit("Wager missed", line)
				Sfx.play("fizzle")
		"level_up":
			announce.emit("Level %d" % int(e[1]), "A skill point waits at the camp.")
			Sfx.play("upgrade")
		"bonus":
			if String(e[2]) == "cleared":
				announce.emit("The wager pays", "The bonus pack is broken.")
				Sfx.play("gold")
			else:
				announce.emit("The wager fails", "The bonus pack got through.")
		_:
			push_warning("an event this client does not show: %s" % kind)
	happened.emit(e)


func _spawn(id: int, facts: Dictionary) -> void:
	var m := Monster.new()
	m.setup(self, id, facts, monster_table(String(facts["kind"])))
	add_child(m)
	monsters[id] = m


func _built(id: int, facts: Dictionary) -> void:
	var t := Tower.new()
	t.setup(self, id, facts)
	add_child(t)
	towers[id] = t
	Sfx.play("build", level.tile_pos(t.tile))


func _cursed(leader_id: int, spot: Vector2i, curse: String, caught: Array) -> void:
	var leader: Monster = monsters.get(leader_id)
	if leader:
		leader.stop_chant()
	var names := []
	for id in caught:
		var t: Tower = towers.get(int(id))
		if t:
			t.curse(curse)
			names.append(t.title())
	var at := level.tile_pos(spot)
	Vfx.burst(self, at + Vector3(0, 1.0, 0), Color(0.7, 0.2, 1.0), 60)
	Sfx.play("curse", at)
	var who := leader.title() if leader else "A leader"
	var curse_name := String(start["curses"][curse]["name"])
	if names.is_empty():
		announce.emit("", "%s's %s falls on bare ground." % [who, curse_name])
	else:
		announce.emit("", "%s lays %s on the %s." % [who, curse_name, " and the ".join(names)])


## What a leader weighed, as the chronicle tells it: the curse it chose and the life it saves its pack, or why it holds.
func _thought(leader: Monster, decision: Dictionary) -> void:
	if leader == null or decision["options"].is_empty():
		return
	var best: Array = decision["options"][0]
	var curse := String(start["curses"][String(best[0])]["name"])
	if decision["cast"] != null:
		announce.emit("", "%s weighs %d futures: %s, %+d life for its pack." % [leader.title(), int(decision["rollouts"]),
			curse, int(round(float(best[3])))])
	elif float(best[2]) > 0.0:
		announce.emit("", "%s waits: in %d s its %s is worth more." % [leader.title(), int(best[2]), curse])


func _arch(index: int) -> Vector2i:
	for a in level.arches:
		if int(a[0]) == index:
			return a[1]
	return Vector2i.ZERO


func _has_boss(w: Dictionary) -> bool:
	for g in w["groups"]:
		if bool(monster_table(String(g["kind"]))["boss"]):
			return true
	return false
