class_name Shots
extends RefCounted
## Named camera framings for captures (main.gd `shot=NAME`): the same views every time, to compare looks.

const VIEWS := {
	"overview": [Vector3(35, 0, 21), 0.0, 55.0, 52.0],
	"wide": [Vector3(34, 0, 18), 0.0, 52.0, 66.0],
	"portal": [Vector3(4, 0, 17), 60.0, 30.0, 22.0],
	"cathedral": [Vector3(66, 0, 19), -70.0, 22.0, 34.0],
	"lane": [Vector3(26, 0, 16), 20.0, 38.0, 20.0],
	"close": [Vector3(30, 0, 16), -25.0, 28.0, 12.0],
	"entry": [Vector3(14, 0, 15), 10.0, 34.0, 16.0],
	"north": [Vector3(30, 0, -2), 0.0, 35.0, 30.0],
	"fire": [Vector3(6, 2, -5), 10.0, 25.0, 14.0],
	"opening": [Vector3(21, 0, 32), 35.0, 24.0, 78.0],
	"skyline": [Vector3(34, 0, 18), 180.0, 18.0, 60.0],
}


static func frame(main: Node, name: String) -> void:
	var v: Array = VIEWS[name]
	main.rig.user_control = false
	main.rig.snap(v[0], v[1], v[2], v[3])
