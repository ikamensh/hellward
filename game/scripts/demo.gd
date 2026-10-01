class_name Demo
extends Node
## A scripted defender for showing the demo (`-- demo`): it builds, upgrades, cleanses and calls the waves.
## With `film` it also directs the camera: it cuts to a leader's chant, follows the pack, visits the towers.

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


func setup(m: Node, filming: bool) -> void:
	main = m
	world = m.world
	rig = m.rig
	film = filming
	world.gold += DEMO_GOLD
	if film:
		rig.user_control = false
		rig.snap(world.level.portal_pos + Vector3(6, 0, 0), 75.0, 22.0, 26.0)


func _process(delta: float) -> void:
	_t += delta
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
	if world.wave_active():
		_quiet = 0.0
		return
	_quiet += delta
	var wait := 7.0 if world.wave < 0 else 5.0
	if _quiet > wait and world.can_call():
		world.call_wave()
		_quiet = 0.0


# the director: a leader's chant takes the camera; otherwise it moves between the field, the pack and the towers
func _direct(delta: float) -> void:
	_shot_t -= delta
	for m in world.monsters:
		if m.alive() and m.leader and m._state in ["ponder", "chant"] and _focus != m:
			_focus = m
			_shot_t = 4.5
			var at: Vector3 = m.global_position
			rig.fly_to(at + Vector3(2, 0, 1), rig.yaw + 20.0, 32.0, 13.0)
			return
	if _shot_t > 0.0:
		return
	_focus = null
	_shot = (_shot + 1) % 4
	_shot_t = 7.0
	match _shot:
		0:
			rig.fly_to(world.level.centre() + Vector3(2, 0, 4), 0.0, 50.0, 50.0)
		1:
			var lead := _leading()
			if lead:
				rig.fly_to(lead.global_position, -25.0, 34.0, 16.0)
			else:
				rig.fly_to(world.level.portal_pos + Vector3(8, 0, 0), 60.0, 28.0, 20.0)
		2:
			if world.towers.size() > 0:
				var t: Tower = world.towers[int(_t) % world.towers.size()]
				rig.fly_to(t.global_position, rig.yaw - 35.0, 26.0, 14.0)
		3:
			rig.fly_to(world.level.door_pos + Vector3(-10, 0, 0), -60.0, 24.0, 26.0)


func _leading() -> Monster:
	var best: Monster = null
	for m in world.monsters:
		if m.alive() and (best == null or m.progress > best.progress):
			best = m
	return best
