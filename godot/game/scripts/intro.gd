class_name Intro
extends Node
## The opening: a flight over the field to the portal with the title, to the title music, then down to the battle
## camera as the HUD slides in and the location's battle music starts. Played, any key or click skips it;
## filmed (demo.gd), it runs through and the director takes the camera when it lands.

signal landed

var main: Node
var filmed := false
var _done := false
var _tw: Tween


func play(m: Node, film := false) -> void:
	main = m
	filmed = film
	Sfx.music("title", -6.0, 0.01)
	var lv: Level = main.level
	main.rig.user_control = false
	main.hud.cinematic(true, 0.01)
	main.rig.snap(lv.centre() + Vector3(-12, 0, 14), 35.0, 24.0, 78.0)
	main.rig.glide(lv.portal_pos + Vector3(7, 0, 1), 70.0, 16.0, 17.0, 7.0)
	_tw = create_tween()
	var place: Dictionary = main.battle["location"]
	_tw.tween_callback(func(): main.hud.title_card("Hellward", String(place["name"]), 2.6)).set_delay(0.6)
	_tw.tween_callback(func(): main.hud.title_card(String(place["name"]), "Hold the sanctuary until the last wave breaks.", 2.2)).set_delay(5.0)
	_tw.tween_callback(_land).set_delay(1.6)


func _land() -> void:
	if _done:
		return
	_done = true
	_tw.kill()
	Sfx.music(main.music(), -8.0, 3.0)
	var lv: Level = main.level
	main.rig.glide(lv.centre() + Vector3(2, 0, 3), 0.0, 55.0, 52.0, 3.0)
	main.hud.cinematic(false, 1.5)
	if filmed:
		get_tree().create_timer(3.0).timeout.connect(landed.emit)
	else:
		get_tree().create_timer(3.0).timeout.connect(func(): main.rig.user_control = true)


func _input(event: InputEvent) -> void:
	if _done or filmed:
		return
	if (event is InputEventKey and event.pressed) or (event is InputEventMouseButton and event.pressed):
		get_viewport().set_input_as_handled()
		_land()
