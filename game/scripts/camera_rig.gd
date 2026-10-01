class_name CameraRig
extends Node3D
## The battle camera: it orbits a target on the ground. Drag with the middle mouse to turn, the arrow keys
## or screen edges to pan, the wheel to zoom. A script may drive it (`fly_to`).

var target := Vector3.ZERO
var yaw := 0.0          # degrees; 0 looks north (-Z)
var pitch := 52.0       # degrees below the horizon
var distance := 48.0
var bounds := AABB(Vector3(-10, 0, -10), Vector3(90, 0, 60))
var user_control := true

var cam: Camera3D
var _goal := {}
var _turning := false


func _ready() -> void:
	cam = Camera3D.new()
	cam.fov = 38.0
	cam.far = 600.0
	cam.near = 0.3
	add_child(cam)
	cam.make_current()
	_apply()


func fly_to(t: Vector3, y: float, p: float, d: float) -> void:
	_goal = {"target": t, "yaw": y, "pitch": p, "distance": d}


func snap(t: Vector3, y: float, p: float, d: float) -> void:
	target = t; yaw = y; pitch = p; distance = d
	_goal = {}
	_apply()


func _process(delta: float) -> void:
	if user_control:
		var move := Vector3.ZERO
		if Input.is_key_pressed(KEY_UP): move.z -= 1
		if Input.is_key_pressed(KEY_DOWN): move.z += 1
		if Input.is_key_pressed(KEY_LEFT): move.x -= 1
		if Input.is_key_pressed(KEY_RIGHT): move.x += 1
		var vp := get_viewport()
		var mouse := vp.get_mouse_position()
		var size := vp.get_visible_rect().size
		if DisplayServer.window_is_focused() and Rect2(Vector2.ZERO, size).has_point(mouse):
			if mouse.x < 4: move.x -= 1
			if mouse.x > size.x - 5: move.x += 1
			if mouse.y < 4: move.z -= 1
			if mouse.y > size.y - 5: move.z += 1
		if move != Vector3.ZERO:
			_goal = {}
			var basis_y := Basis(Vector3.UP, deg_to_rad(yaw))
			target += basis_y * move.normalized() * distance * 0.9 * delta
			target = target.clamp(bounds.position, bounds.end)
	if not _goal.is_empty():
		var k: float = 1.0 - exp(-delta * 1.6)
		target = target.lerp(_goal["target"], k)
		yaw = lerp(yaw, float(_goal["yaw"]), k)
		pitch = lerp(pitch, float(_goal["pitch"]), k)
		distance = lerp(distance, float(_goal["distance"]), k)
	_apply()


func _unhandled_input(event: InputEvent) -> void:
	if not user_control:
		return
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP and mb.pressed:
			distance = max(distance * 0.9, 12.0)
			_goal = {}
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN and mb.pressed:
			distance = min(distance * 1.1, 80.0)
			_goal = {}
		elif mb.button_index == MOUSE_BUTTON_MIDDLE:
			_turning = mb.pressed
	elif event is InputEventMouseMotion and _turning:
		var mm := event as InputEventMouseMotion
		yaw -= mm.relative.x * 0.25
		pitch = clamp(pitch + mm.relative.y * 0.2, 20.0, 80.0)
		_goal = {}


func _apply() -> void:
	var p := deg_to_rad(pitch)
	var y := deg_to_rad(yaw)
	var back := Vector3(sin(y) * cos(p), sin(p), cos(y) * cos(p))
	if cam:
		cam.global_position = target + back * distance
		cam.look_at(target)
