extends Node3D
## Renders one model for review under the game's night lighting (tools/preview.sh drives it).
## User args: model=/abs/file.glb [anim=walk] [views=8] [dist=0 (auto)] [pitch=25] [yaw=35]
## Without anim: a turntable of `views` frames. With anim: `views` samples across the animation from `yaw`.

const SKIP := 3   # frames rendered before the first kept one, while shaders settle

var _args := {}
var _model: Node3D
var _player: AnimationPlayer
var _cam: Camera3D
var _frame := 0
var _centre := Vector3.ZERO
var _radius := 1.0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=", true, 1)
		_args[kv[0]] = kv[1] if kv.size() > 1 else ""
	_build_stage()
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_file(_args["model"], state)
	assert(err == OK, "cannot read %s" % _args["model"])
	_model = doc.generate_scene(state)
	add_child(_model)
	Mats.apply(_model)
	var players := _model.find_children("*", "AnimationPlayer", true, false)
	if players.size() > 0:
		_player = players[0]
		print("animations: ", _player.get_animation_list())
	var box := _bounds(_model)
	_centre = box.get_center()
	_radius = max(box.size.length() * 0.5, 0.3)
	print("bounds: ", box)
	_cam = Camera3D.new()
	_cam.fov = 30
	add_child(_cam)
	_place_camera(0)


func _process(_delta: float) -> void:
	_frame += 1
	var i: int = max(_frame - SKIP, 0)
	_place_camera(i)


func _place_camera(i: int) -> void:
	var views := int(_args.get("views", "8"))
	var yaw := float(_args.get("yaw", "35"))
	if _args.has("anim") and _player != null:
		var anim := _player.get_animation(_args["anim"])
		_player.play(_args["anim"])
		_player.seek(anim.length * float(i % views) / views, true)
		_player.pause()
	else:
		yaw += 360.0 * float(i % views) / views
	var pitch := deg_to_rad(float(_args.get("pitch", "25")))
	var dist := float(_args.get("dist", "0"))
	if dist <= 0.0:
		dist = _radius / tan(deg_to_rad(_cam.fov * 0.5)) * 1.15
	var dir := Vector3(sin(deg_to_rad(yaw)) * cos(pitch), sin(pitch), cos(deg_to_rad(yaw)) * cos(pitch))
	_cam.position = _centre + dir * dist
	_cam.look_at(_centre)


func _bounds(root: Node) -> AABB:
	var box := AABB()
	var first := true
	for node in root.find_children("*", "VisualInstance3D", true, false):
		var vi := node as VisualInstance3D
		var b := vi.global_transform * vi.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box


func _build_stage() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.05, 0.05, 0.07)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.35, 0.4, 0.55)
	env.ambient_light_energy = 0.6
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.glow_enabled = true
	env.ssao_enabled = true
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var moon := DirectionalLight3D.new()
	moon.light_color = Color(0.6, 0.7, 1.0)
	moon.light_energy = 0.8
	moon.shadow_enabled = true
	moon.rotation_degrees = Vector3(-50, -40, 0)
	add_child(moon)
	var key := DirectionalLight3D.new()
	key.light_color = Color(1.0, 0.7, 0.45)
	key.light_energy = 1.4
	key.rotation_degrees = Vector3(-30, 140, 0)
	add_child(key)
	var floor := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(12, 12)
	floor.mesh = pm
	var m := Mats.textured("cobbles")
	m.uv1_scale = Vector3(6, 6, 1)
	floor.material_override = m
	add_child(floor)
