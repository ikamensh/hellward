extends Node3D
## The monsters side by side as a battle shows them (tools/lineup.sh drives it): each at its in-game size with the
## overlay the battle gives it, walking (or playing `anim`) a little out of step, on cobbles under the game's night
## with two braziers, seen from the battle camera's angle. `silhouette` draws them flat black on flat grey: which
## kind is which by outline alone. The frame is saved to `out`, then the run quits.
## User args: kinds=fallen,shaman,zombie,skeleton out=PNG [anim=walk] [at=0.4] [dist=48] [pitch=52] [yaw=0]
## [gap=2.6] [turn=150] [silhouette] [crowd=N frames=F]
## `crowd` fills a 20 m street with N of the kinds, every one playing its walk out of step, and saves the frame
## after `frames` frames (with `perf`, capture.gd prints the frame time meanwhile): the cost of a full wave.

const SKIP := 6   # frames rendered before the kept one, while shaders settle

var _args := {}
var _frame := 0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=", true, 1)
		_args[kv[0]] = kv[1] if kv.size() > 1 else ""
	var flat := _args.has("silhouette")
	if flat:
		var env := WorldEnvironment.new()
		env.environment = Environment.new()
		env.environment.background_mode = Environment.BG_COLOR
		env.environment.background_color = Color(0.55, 0.55, 0.55)
		add_child(env)
	else:
		Atmosphere.night(self)
		for side in [-1.0, 1.0]:
			var fire := Fx.fire_light(9.0, 11.0, true)
			fire.position = Vector3(side * 5.0, 1.6, 3.0)
			add_child(fire)
	var floor := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(40, 40)
	floor.mesh = pm
	if flat:
		var m := StandardMaterial3D.new()
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.albedo_color = Color(0.55, 0.55, 0.55)
		floor.material_override = m
	else:
		var m := Mats.textured("cobbles")
		m.uv1_scale = Vector3(40, 40, 1)
		floor.material_override = m
	add_child(floor)
	var kinds: PackedStringArray = _args.get("kinds", "fallen,shaman,zombie,skeleton").split(",")
	var gap := float(_args.get("gap", "2.6"))
	var crowd := int(_args.get("crowd", "0"))
	var count := crowd if crowd > 0 else kinds.size()
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	for i in count:
		var kind := kinds[i % kinds.size()]
		var body := Models.make("mon_" + kind)
		body.scale = Vector3.ONE * Monster.BODY
		if crowd > 0:   # as monster.gd varies a pack: size and tint by id
			body.position = Vector3(rng.randf_range(-10, 10), 0, rng.randf_range(-4, 4))
			body.scale *= 1.0 + 0.06 * (float((i * 7919) % 101) / 50.0 - 1.0)
			Mats.vary(body, i % Mats.VARIANTS.size())
		else:
			body.position = Vector3((i - (kinds.size() - 1) * 0.5) * gap, 0, 0)
		body.rotation.y = deg_to_rad(float(_args.get("turn", "150")))   # three-quarters toward the camera
		add_child(body)
		for mi in body.find_children("*", "MeshInstance3D", true, false):
			if _args.has("nolod"):
				(mi as MeshInstance3D).lod_bias = 1000.0
			if _args.has("noshadow"):
				(mi as MeshInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			if flat:
				var black := StandardMaterial3D.new()
				black.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
				black.albedo_color = Color.BLACK
				(mi as MeshInstance3D).material_override = black
			else:
				var overlay := ShaderMaterial.new()
				overlay.shader = preload("res://shaders/overlay.gdshader")
				overlay.set_shader_parameter("kind_rim", Monster.RIM[kind])
				overlay.set_shader_parameter("xray", 0.0 if _args.has("noxray") else 1.0)
				overlay.set_shader_parameter("moonrim", float(_args.get("moonrim", "0.12")))
				(mi as MeshInstance3D).material_overlay = overlay
		var player := Models.player(body)
		var anim := Models.anim_name(player, _args.get("anim", "walk"))
		if anim == "":   # a kind without that clip walks
			anim = Models.anim_name(player, "walk")
		player.play(anim)
		player.seek(player.get_animation(anim).length * fmod(float(_args.get("at", "0.4")) + i * 0.27, 1.0), true)
		if crowd > 0:
			player.get_animation(anim).loop_mode = Animation.LOOP_LINEAR
		else:
			player.pause()
	var cam := Camera3D.new()
	var dist := float(_args.get("dist", "48"))
	cam.fov = lerp(40.0, 30.0, clamp((dist - 16.0) / 40.0, 0.0, 1.0))   # the battle camera's lens
	var p := deg_to_rad(float(_args.get("pitch", "52")))
	var y := deg_to_rad(float(_args.get("yaw", "0")))
	add_child(cam)
	cam.position = Vector3(sin(y) * cos(p), sin(p), cos(y) * cos(p)) * dist + Vector3(0, 0.8, 0)
	cam.look_at(Vector3(0, 0.8, 0))


func _process(_delta: float) -> void:
	_frame += 1
	if _frame == int(_args.get("frames", str(SKIP))):
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(_args["out"])
		get_tree().quit()
