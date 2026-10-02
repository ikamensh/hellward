extends Node3D
## Renders one model for review under the game's night lighting (tools/preview.sh drives it).
## User args: model=/abs/file.glb out=DIR [anim=walk] [views=8] [dist=0 (auto)] [pitch=25] [yaw=35] [focus=Y]
## Without anim: a turntable of `views` frames. With anim: `views` samples across the animation from `yaw`.
## Each view is saved as DIR/fNN.png, then the run quits.

const SKIP := 3   # frames rendered before the first kept one, while shaders settle

var _args := {}
var _model: Node3D
var _player: AnimationPlayer
var _cam: Camera3D
var _frame := 0
var _centre := Vector3.ZERO
var _radius := 1.0
var _dying: Array[ORMMaterial3D] = []   # a death's eyes go out as they do in a battle (Mats.eyes_out)


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
	var kind := String(_args["model"]).get_file().get_basename().trim_prefix("mon_")
	if Monster.RIM.has(kind):   # a monster wears its battle overlay (its kind's rim)
		var dead := String(_args.get("anim", "")).begins_with("die")
		var overlay := Monster.overlay(Color.BLACK if dead else Monster.RIM[kind])   # the dead lose their rim
		for mi in _model.find_children("*", "MeshInstance3D", true, false):
			(mi as MeshInstance3D).material_overlay = overlay
	var players := _model.find_children("*", "AnimationPlayer", true, false)
	if players.size() > 0:
		_player = players[0]
		print("animations: ", _player.get_animation_list())
	if String(_args.get("anim", "")).begins_with("die"):
		_dying = Mats.own(_model)
	var box := _bounds(_model)
	_centre = box.get_center()
	_radius = max(box.size.length() * 0.5, 0.3)
	if _args.has("focus"):   # a close-up: look at this height, from `dist`
		_centre.y = float(_args["focus"])
	print("bounds: ", box)
	_cam = Camera3D.new()
	_cam.fov = 30
	add_child(_cam)
	_place_camera(0)


func _process(_delta: float) -> void:
	_frame += 1
	var i: int = _frame - SKIP
	var views := int(_args.get("views", "8"))
	if i < 0 or i > views:   # quit() takes effect after the frame it is called in
		return
	if i > 0:
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("%s/f%02d.png" % [_args["out"], i - 1])
	if i == views:
		get_tree().quit()
		return
	_place_camera(i)


func _place_camera(i: int) -> void:
	var views := int(_args.get("views", "8"))
	var yaw := float(_args.get("yaw", "35"))
	if _args.has("anim") and _player != null:
		var anim := _player.get_animation(_args["anim"])
		_player.play(_args["anim"])
		_player.seek(anim.length * float(i % views) / views, true)
		_player.pause()
		Mats.eyes_out(_dying, anim.length * float(i % views) / views)
	else:
		yaw += 360.0 * float(i % views) / views
		var idle := Models.anim_name(_player, "idle") if _player != null else ""
		if idle != "":   # a turntable shows the body as the game does, in its idle stance, never the bind pose
			_player.play(idle)
			_player.seek(0.0, true)
			_player.pause()
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
	Atmosphere.night(self)   # the game's own night, so a sheet shows the in-game look
	var fire := Fx.fire_light(9.0, 11.0, true)   # and a brazier's light, as most things stand near one,
	var side := deg_to_rad(float(_args.get("yaw", "35")) + 10.0)   # a little to the camera's side
	fire.position = Vector3(sin(side) * 3.5, 1.6, cos(side) * 3.5)
	add_child(fire)
	var floor := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(12, 12)
	floor.mesh = pm
	var m := Mats.textured("cobbles")
	m.uv1_scale = Vector3(6, 6, 1)
	floor.material_override = m
	add_child(floor)
