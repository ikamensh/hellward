class_name CameraRig
extends Node3D
## The battle camera: it orbits a target on the ground. WASD, the arrow keys or the window's edges pan; Q and E or
## the wheel zoom; drag with the middle mouse to turn. The keys are read by their place on the keyboard (WASD is the
## same shape on any layout). Pans and zooms ease in and out. While `hold_mouse` is set (a live defence: the battle
## scene decides) the cursor is kept in the window, so its edges pan even with another display beyond them; while
## `frozen` (paused, or decided) the hand moves nothing. A script may drive it (`snap`, `glide`, `follow`).

var target := Vector3.ZERO
var yaw := 0.0          # degrees; 0 looks north (-Z)
var pitch := 52.0       # degrees below the horizon
var distance := 48.0
var bounds := AABB(Vector3(-10, 0, -10), Vector3(90, 0, 60))
var user_control := true
var hold_mouse := false     # keep the cursor in the window (released whenever the window loses focus)
var frozen := false         # the keys and edges move nothing: an overlay's keys are its own

const NEAR := 14.0          # the zoom's range, metres from the target
const FAR := 90.0
const EDGE := 8.0           # points from the window's edge that pan

var cam: Camera3D
var follow: Node3D          # when set, the target keeps to this node (a monster being filmed)
var _turning := false
var _glide: Tween
var _pan := Vector3.ZERO    # the pan's velocity, eased towards what the keys and edges ask
var _zoom := 48.0           # the distance the wheel and Q/E ask for; `distance` eases towards it
var _holding := false       # the cursor was kept in the window last frame


func _ready() -> void:
	cam = Camera3D.new()
	cam.fov = 38.0
	cam.far = 600.0
	cam.near = 0.3
	add_child(cam)
	cam.make_current()
	_apply()


## A filmed move: ease from here to there over `seconds`, both ends at rest.
func glide(t: Vector3, y: float, p: float, d: float, seconds: float) -> void:
	if _glide:
		_glide.kill()
	_glide = create_tween().set_parallel().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_glide.tween_property(self, "target", t, seconds)
	_glide.tween_property(self, "yaw", y, seconds)
	_glide.tween_property(self, "pitch", p, seconds)
	_glide.tween_property(self, "distance", d, seconds)


func snap(t: Vector3, y: float, p: float, d: float) -> void:
	target = t; yaw = y; pitch = p; distance = d; _zoom = d
	_pan = Vector3.ZERO
	_apply()


func _process(game_delta: float) -> void:
	var delta := game_delta / maxf(Engine.time_scale, 0.001)   # the hand's time: F's doubled pace pans no faster
	_keep_mouse(hold_mouse and user_control and DisplayServer.window_is_focused())
	if _glide and _glide.is_running():
		_zoom = distance   # a scripted move zooms; the eased zoom follows it
	if user_control and not frozen:
		var want := _asked() * distance * 0.9
		if want != Vector3.ZERO and _glide:
			_glide.kill()   # the player's hand wins over a scripted move
		_pan = _pan.lerp(want, 1.0 - exp(-delta * 12.0))
		if _pan.length() > 0.01:
			target = (target + Basis(Vector3.UP, deg_to_rad(yaw)) * _pan * delta).clamp(bounds.position, bounds.end)
		var zoom := _held(KEY_E) - _held(KEY_Q)   # Q closer, E further
		if zoom != 0.0:
			if _glide:
				_glide.kill()
			_zoom = clampf(_zoom * exp(zoom * delta * 1.6), NEAR, FAR)
	else:
		_pan = Vector3.ZERO
	distance = lerpf(distance, _zoom, 1.0 - exp(-delta * 10.0))
	if is_instance_valid(follow):
		var k_follow: float = 1.0 - exp(-delta * 2.5)
		target = target.lerp(follow.global_position, k_follow)
	_apply()


## Where the keys and the window's edges ask to pan: x east, z south, each -1..1, in the camera's frame.
func _asked() -> Vector3:
	var move := Vector3(_held(KEY_D) + _held(KEY_RIGHT) - _held(KEY_A) - _held(KEY_LEFT), 0.0,
		_held(KEY_S) + _held(KEY_DOWN) - _held(KEY_W) - _held(KEY_UP))
	if DisplayServer.window_is_focused() and not _turning:   # a turn reaching the edge turns, it does not pan
		# the cursor as the system has it, not the last motion event: a quick flick past the edge sends none there
		var at := DisplayServer.mouse_get_position() - DisplayServer.window_get_position()
		var size := DisplayServer.window_get_size()
		var edge := EDGE * DisplayServer.screen_get_scale()
		if at.y > -edge and at.y < size.y + edge:
			if at.x < edge and at.x > -edge: move.x -= 1.0
			if at.x >= size.x - edge and at.x < size.x + edge: move.x += 1.0
		if at.x > -edge and at.x < size.x + edge:
			if at.y < edge and at.y > -edge: move.z -= 1.0
			if at.y >= size.y - edge and at.y < size.y + edge: move.z += 1.0
	return move.limit_length(1.0)


## 1 while the camera key at that place is down and no command key with it (Cmd-Q quits, Cmd-W closes), else 0.
func _held(key: Key) -> float:
	if Input.is_key_pressed(KEY_META) or Input.is_key_pressed(KEY_CTRL):
		return 0.0
	return 1.0 if Input.is_physical_key_pressed(key) else 0.0


## Keep the cursor in the window. Elsewhere the system confines it; on macOS Godot's confining moves the cursor itself
## once a frame (it lags, and stops in a hitch), so there it stays the system's and is put back on the edge it left by.
func _keep_mouse(on: bool) -> void:
	var size := DisplayServer.window_get_size()
	var at := DisplayServer.mouse_get_position() - DisplayServer.window_get_position()
	if on and not _holding and at != at.clamp(Vector2i.ZERO, size - Vector2i.ONE):
		DisplayServer.warp_mouse(size / 2)   # resumed, refocused or handed over with the cursor away: start mid-window
		at = size / 2
	_holding = on
	var native := on and OS.get_name() != "macOS"
	var mode := Input.MOUSE_MODE_CONFINED if native else Input.MOUSE_MODE_VISIBLE
	if Input.mouse_mode != mode:
		Input.mouse_mode = mode
	if on and not native:
		var inside := at.clamp(Vector2i.ZERO, size - Vector2i.ONE)
		if inside != at:
			DisplayServer.warp_mouse(inside)


func _exit_tree() -> void:
	_keep_mouse(false)


func _unhandled_input(event: InputEvent) -> void:
	if not user_control:
		return
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP and mb.pressed:
			_zoom = maxf(_zoom * 0.85, NEAR)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN and mb.pressed:
			_zoom = minf(_zoom / 0.85, FAR)
		elif mb.button_index == MOUSE_BUTTON_MIDDLE:
			_turning = mb.pressed
	elif event is InputEventMouseMotion and _turning:
		var mm := event as InputEventMouseMotion
		yaw -= mm.relative.x * 0.25
		pitch = clamp(pitch + mm.relative.y * 0.2, 20.0, 80.0)


func _apply() -> void:
	var p := deg_to_rad(pitch)
	var y := deg_to_rad(yaw)
	var back := Vector3(sin(y) * cos(p), sin(p), cos(y) * cos(p))
	if cam:
		cam.fov = lerp(40.0, 30.0, clamp((distance - 16.0) / 40.0, 0.0, 1.0))   # a longer lens far out
		cam.global_position = target + back * distance
		cam.look_at(target)
