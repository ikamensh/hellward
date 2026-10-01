class_name Intro
extends Node
## The opening when the game is played: a flight over the burning village to the hell gate with the title,
## then down to the battle camera as the HUD slides in. Any key or click skips it.

const LENGTH := 11.0

var main: Node
var _t := 0.0
var _done := false


func play(m: Node) -> void:
	main = m
	var lv: Level = main.level
	main.rig.user_control = false
	main.hud.cinematic(true, 0.01)
	main.rig.snap(lv.centre() + Vector3(-12, 0, 14), 35.0, 24.0, 78.0)
	main.rig.glide(lv.portal_pos + Vector3(7, 0, 1), 70.0, 16.0, 17.0, 7.0)
	var tw := create_tween()
	tw.tween_callback(func(): main.hud.title_card("Hellward", "Tristram burns", 2.6)).set_delay(0.6)
	tw.tween_callback(func(): main.hud.title_card("Tristram", "Hold the cathedral until the last wave breaks.", 2.2)).set_delay(5.0)
	tw.tween_callback(_land).set_delay(1.6)


func _land() -> void:
	if _done:
		return
	_done = true
	var lv: Level = main.level
	main.rig.glide(lv.centre() + Vector3(2, 0, 3), 0.0, 55.0, 52.0, 3.0)
	main.hud.cinematic(false, 1.5)
	get_tree().create_timer(3.0).timeout.connect(func(): main.rig.user_control = true)


func _input(event: InputEvent) -> void:
	if _done:
		return
	if (event is InputEventKey and event.pressed) or (event is InputEventMouseButton and event.pressed):
		get_viewport().set_input_as_handled()
		_land()
