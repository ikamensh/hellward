class_name World
extends Node3D
## One defence of Tristram: gold, lives, mana, the waves, and every monster, tower and missile in play.
## The numbers come from the 2D game's rules (data/tristram.json); this is a lighter simulation of them,
## enough to show the fight. Ranges and speeds are in tiles there and in metres here (Level.TILE).

signal changed                       # gold, lives, mana or the wave moved: the HUD redraws
signal announce(title: String, line: String)
signal finished(won: bool)

const START_LIVES := 20
const MANA_MAX := 100.0
const MANA_REGEN := 1.5
const CLEANSE_COST := 35.0
const EARLY_BONUS := 2               # gold for calling a wave before the field is clear
# the demo offers the families the campaign opens later; Storm gets a forged coil's leap to show it off
const STORM_LEAPS := 2
# skeletons join the later waves: the demo shows the first four kinds
const EXTRA := {3: [{"kind": "skeleton", "count": 4, "interval": 2.0, "start": 6.0}],
	4: [{"kind": "skeleton", "count": 6, "interval": 1.6, "start": 5.0}]}

var level: Level
var data: Dictionary
var gold := 0
var lives := START_LIVES
var mana := 60.0
var wave := -1                       # the latest wave called; -1 before the first
var paid := -1                       # the latest wave whose clear bonus was paid
var slain := {}                      # wave index -> monsters of that wave killed (leaks are not slain)
var spawners: Array = []             # {kind, left, interval, next, life}
var monsters: Array = []
var towers: Array = []
var outcome := ""
var time := 0.0
var rng := RandomNumberGenerator.new()


func setup(lvl: Level) -> void:
	level = lvl
	data = lvl.data
	gold = int(data["start_gold"])
	rng.seed = 4


func waves() -> Array:
	return data["waves"]


## Monsters still to come or still on their feet; corpses fading away do not hold a wave open.
func wave_active() -> bool:
	return not spawners.is_empty() or not living().is_empty()


## Every group a wave sends: the 2D game's, and the demo's extra skeletons.
func roster(i: int) -> Array:
	return waves()[i]["groups"] + EXTRA.get(i, [])


func tower_at(tile: Vector2i) -> Tower:
	for t in towers:
		if t.tile == tile and not t.removed:
			return t
	return null


## What selling `t` gives back.
func refund(t: Tower) -> int:
	return int(t.spent * 0.7)


func can_call() -> bool:
	return outcome == "" and wave + 1 < waves().size()


func call_wave() -> void:
	if not can_call():
		return
	if wave_active():
		gold += EARLY_BONUS
	wave += 1
	var w: Dictionary = waves()[wave]
	for g in roster(wave):
		spawners.append({"kind": g["kind"], "left": int(g["count"]), "interval": float(g["interval"]),
			"next": time + float(g["start"]), "life": float(w["life"]), "wave": wave})
	announce.emit("Wave %d of %d" % [wave + 1, waves().size()], w["name"])
	Sfx.play("wave")
	changed.emit()


func tower_cost(kind: String, rank: int) -> int:
	return int(data["towers"][kind]["levels"][rank]["cost"])


func build(kind: String, tile: Vector2i) -> Tower:
	var cost := tower_cost(kind, 0)
	if gold < cost or not level.buildable(tile) or outcome != "":
		return null
	gold -= cost
	var t := Tower.new()
	t.setup(self, kind, tile)
	add_child(t)
	towers.append(t)
	level.occupied[tile] = true
	Sfx.play("build", level.tile_pos(tile))
	changed.emit()
	return t


func upgrade(t: Tower) -> bool:
	if t.rank >= 2:
		return false
	var cost := tower_cost(t.kind, t.rank + 1)
	if gold < cost:
		return false
	gold -= cost
	t.promote()
	Sfx.play("upgrade", t.global_position)
	changed.emit()
	return true


## Sell `t` for its refund; a cursed tower can't be sold.
func sell(t: Tower) -> bool:
	if t.cursed > 0.0:
		Sfx.play("refuse")
		return false
	gold += refund(t)
	Sfx.play("sell", t.global_position)
	level.occupied.erase(t.tile)
	towers.erase(t)
	t.dismantle()
	changed.emit()
	return true


func cleanse(t: Tower) -> bool:
	if mana < CLEANSE_COST or t.cursed <= 0.0:
		return false
	mana -= CLEANSE_COST
	t.lift_curse()
	Vfx.holy(self, t.global_position)
	Sfx.play("cleanse", t.global_position)
	changed.emit()
	return true


func _process(delta: float) -> void:
	if outcome != "":
		return
	time += delta
	mana = min(MANA_MAX, mana + MANA_REGEN * delta)
	for sp in spawners.duplicate():
		while sp["left"] > 0 and time >= sp["next"]:
			_spawn(sp["kind"], sp["life"], sp["wave"])
			sp["left"] -= 1
			sp["next"] += sp["interval"]
		if sp["left"] <= 0:
			spawners.erase(sp)
	for m in monsters.duplicate():
		if m.gone:
			monsters.erase(m)
			m.queue_free()
	if wave > paid and not wave_active():
		var bonus := 0
		while paid < wave:   # a wave called early is paid when the field clears too
			paid += 1
			bonus += int(waves()[paid]["clear_bonus"])
		gold += bonus
		if wave == waves().size() - 1:
			outcome = "won"
			announce.emit("Tristram holds", "The last wave is broken. The lamp still burns.")
			Sfx.play("victory")
			finished.emit(true)
		else:
			announce.emit("Wave cleared", "+%d gold. Build, then summon the next wave." % bonus)
			Sfx.play("cleared")
		changed.emit()


func _spawn(kind: String, life: float, of_wave: int) -> void:
	var m := Monster.new()
	var stats: Dictionary = data["monsters"][kind]
	var route: PackedVector3Array = level.routes[rng.randi() % level.routes.size()]
	m.setup(self, kind, stats, route, life, rng.randi())
	m.wave = of_wave
	add_child(m)
	monsters.append(m)


func living() -> Array:
	return monsters.filter(func(m): return m.alive())


## A monster reached the cathedral.
func breached(m: Monster) -> void:
	lives = max(0, lives - int(m.stats["lives"]))
	changed.emit()
	if lives == 0 and outcome == "":
		outcome = "lost"
		announce.emit("The lamp goes out", "Tristram falls to the Fallen.")
		Sfx.play("defeat")
		for n in monsters + towers:   # the battle stops where it stands
			n.process_mode = Node.PROCESS_MODE_DISABLED
		finished.emit(false)


func killed(m: Monster) -> void:
	if outcome != "":
		return
	slain[m.wave] = slain.get(m.wave, 0) + 1
	gold += int(m.stats["bounty"])
	Vfx.coin(self, m.global_position + Vector3(0, m.height + 0.3, 0), int(m.stats["bounty"]))
	Sfx.play("gold", m.global_position)
	changed.emit()


## Monsters within `reach` metres of `p`, on the ground plane.
func near(p: Vector3, reach: float) -> Array:
	var out: Array = []
	if outcome != "":
		return out
	for m in monsters:
		if m.alive():
			var d := Vector2(m.global_position.x - p.x, m.global_position.z - p.z).length()
			if d <= reach:
				out.append(m)
	return out
