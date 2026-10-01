class_name Demo
extends Node
## The film director for a watched defence (`-- demo film`, the title's demo): the server's scripted player
## defends; this only moves the camera. An opening flight over the field with the title, then cuts the battle's
## events call for (a leader pondering or chanting), and between them it follows the pack, visits the towers and
## watches the field; the ending pulls back over the field.

var main: Node
var world: World
var rig: CameraRig
var _shot_t := 0.0
var _shot := -1
var _focus: Node3D
var _over := false
var _rolling := false   # the director waits for the opening flight to land


func setup(m: Node) -> void:
	main = m
	world = m.world
	rig = m.rig
	world.finished.connect(_ending)
	var intro := Intro.new()
	add_child(intro)
	intro.play(main, true)
	intro.landed.connect(func(): _rolling = true)


func _process(delta: float) -> void:
	if _rolling:
		_direct(delta)


func _ending(_won: bool) -> void:
	_over = true
	rig.follow = null
	var lv := world.level
	rig.glide(lv.door_pos + Vector3(-14, 0, 2), -62.0, 20.0, 30.0, 4.0)
	var tw := create_tween()
	tw.tween_callback(func(): main.hud.cinematic(true, 1.5)).set_delay(2.5)
	tw.tween_callback(func(): rig.glide(lv.centre() + Vector3(-6, 0, 10), 25.0, 30.0, 80.0, 9.0)).set_delay(2.0)


# the director: a leader's curse takes the camera; otherwise it moves between the field, the pack and the towers
func _direct(delta: float) -> void:
	if _over:
		return
	_shot_t -= delta
	for m in world.monsters.values():
		if m.alive() and m.leader and m.casting() >= 0.0 and _focus != m:
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
	for t in world.towers.values():
		if best == null or t.threat() > best.threat():
			best = t
	return best


func _leading() -> Monster:
	var best: Monster = null
	for m in world.monsters.values():
		if m.alive() and (best == null or m.progress > best.progress):
			best = m
	return best
