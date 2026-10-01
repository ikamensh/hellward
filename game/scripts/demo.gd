class_name Demo
extends Node
## A scripted defender for showing the demo (`-- demo`): it builds, upgrades, cleanses and calls the waves.
## With `film` it also directs the camera: an opening flight over the burning village with the title, then
## cuts the battle's events call for (a leader's chant, a curse landing), and between them it follows the
## pack, visits the towers and watches the field; the ending pulls back over the village.

# what to build, in order, each as soon as the gold allows: [kind, tile] or ["upgrade", tile]
const PLAN := [
	["arrow", Vector2i(16, 7)], ["arrow", Vector2i(11, 10)], ["arrow", Vector2i(22, 5)],
	["pyre", Vector2i(13, 6)], ["frost", Vector2i(18, 11)], ["upgrade", Vector2i(16, 7)],
	["storm", Vector2i(28, 6)], ["arrow", Vector2i(29, 11)], ["upgrade", Vector2i(11, 10)],
	["pyre", Vector2i(25, 5)], ["upgrade", Vector2i(22, 5)], ["frost", Vector2i(9, 6)],
	["upgrade", Vector2i(16, 7)], ["storm", Vector2i(14, 11)], ["upgrade", Vector2i(13, 6)],
	["upgrade", Vector2i(28, 6)], ["upgrade", Vector2i(18, 11)], ["arrow", Vector2i(31, 7)],
]

const DEMO_GOLD := 90   # a showcase, not a test: the scripted defender starts with a fuller purse

var main: Node
var world: World
var rig: CameraRig
var film := false
var _step := 0
var _quiet := 0.0
var _t := 0.0
var _shot_t := 0.0
var _shot := -1
var _focus: Node3D
var _over := false

const OPENING := 13.0   # seconds of the opening flight before a filmed defence begins


func setup(m: Node, filming: bool) -> void:
	main = m
	world = m.world
	rig = m.rig
	film = filming
	world.gold += DEMO_GOLD
	if film:
		rig.user_control = false
		main.hud.cinematic(true, 0.01)
		world.finished.connect(_ending)
		_opening()


func _process(delta: float) -> void:
	_t += delta
	if film and _t < OPENING:
		return
	_build()
	_cleanse()
	_call_waves(delta)
	if film:
		_direct(delta)


func _build() -> void:
	while _step < PLAN.size():
		var p: Array = PLAN[_step]
		var tile: Vector2i = p[1]
		if p[0] == "upgrade":
			var t := _tower_at(tile)
			if t == null or t.rank >= 2:
				_step += 1
				continue
			if world.gold < world.tower_cost(t.kind, t.rank + 1):
				return
			world.upgrade(t)
		else:
			if world.gold < world.tower_cost(p[0], 0):
				return
			world.build(p[0], tile)
		_step += 1
		return


func _tower_at(tile: Vector2i) -> Tower:
	for t in world.towers:
		if t.tile == tile and not t.removed:
			return t
	return null


func _cleanse() -> void:
	for t in world.towers:
		if t.cursed > 0.0 and t.cursed < Monster.CURSE_TIME - 1.5 and world.mana >= World.CLEANSE_COST:
			world.cleanse(t)
			return


func _call_waves(delta: float) -> void:
	var thin := film and world.spawners.is_empty() and world.living().size() <= 3 and world.wave >= 0
	if world.wave_active() and not thin:
		_quiet = 0.0
		return
	_quiet += delta
	var wait := 7.0 if world.wave < 0 else 5.0
	if _quiet > wait and world.can_call():
		world.call_wave()
		_quiet = 0.0


func _opening() -> void:
	var lv := world.level
	rig.snap(lv.centre() + Vector3(-12, 0, 14), 35.0, 24.0, 78.0)
	rig.glide(lv.portal_pos + Vector3(7, 0, 1), 70.0, 16.0, 17.0, 8.0)
	var tw := create_tween()
	tw.tween_callback(func(): main.hud.title_card("Hellward", "Tristram burns", 3.0)).set_delay(0.8)
	tw.tween_callback(func(): main.hud.title_card("Tristram", "Hold the cathedral until the last wave breaks.", 2.5)).set_delay(6.0)
	tw.tween_callback(func():
		rig.glide(lv.centre() + Vector3(2, 0, 3), 0.0, 55.0, 52.0, 4.0)
		main.hud.cinematic(false, 2.0)).set_delay(1.5)


func _ending(_won: bool) -> void:
	_over = true
	rig.follow = null
	var lv := world.level
	rig.glide(lv.door_pos + Vector3(-14, 0, 2), -62.0, 20.0, 30.0, 4.0)
	var tw := create_tween()
	tw.tween_callback(func(): main.hud.cinematic(true, 1.5)).set_delay(2.5)
	tw.tween_callback(func(): rig.glide(lv.centre() + Vector3(-6, 0, 10), 25.0, 30.0, 80.0, 9.0)).set_delay(2.0)


# the director: a leader's chant takes the camera; otherwise it moves between the field, the pack and the towers
func _direct(delta: float) -> void:
	if _over:
		return
	_shot_t -= delta
	for m in world.monsters:
		if m.alive() and m.leader and m._state in ["ponder", "chant"] and _focus != m:
			_focus = m
			_shot_t = 5.0
			rig.follow = m
			rig.glide(m.global_position, rig.yaw + 25.0, 30.0, 13.0, 1.2)
			return
	if _shot_t > 0.0:
		return
	_focus = null
	rig.follow = null
	_shot = (_shot + 1) % 5
	_shot_t = 7.0
	match _shot:
		0:
			rig.glide(world.level.centre() + Vector3(2, 0, 3), 0.0, 55.0, 52.0, 2.5)
		1:
			var lead := _leading()
			if lead:
				rig.follow = lead
				rig.glide(lead.global_position, -30.0, 30.0, 15.0, 2.0)
			else:
				rig.glide(world.level.portal_pos + Vector3(7, 0, 1), 70.0, 18.0, 19.0, 2.5)
		2:
			var t := _busiest()
			if t:
				rig.glide(t.global_position, clamp(rig.yaw - 30.0, -35.0, 35.0), 32.0, 17.0, 2.5)
		3:
			rig.glide(world.level.portal_pos + Vector3(9, 0, 0), 62.0, 22.0, 22.0, 2.5)
		4:
			rig.glide(world.level.door_pos + Vector3(-12, 0, 1), -66.0, 22.0, 28.0, 2.5)


## The tower that has done the most lately: where the fighting is.
func _busiest() -> Tower:
	var best: Tower = null
	for t in world.towers:
		if best == null or t.threat() > best.threat():
			best = t
	return best


func _leading() -> Monster:
	var best: Monster = null
	for m in world.monsters:
		if m.alive() and (best == null or m.progress > best.progress):
			best = m
	return best
