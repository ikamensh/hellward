extends Node3D
## Hellward 3D: Tristram burns. Builds the world, then hands the battle to World and the screen to Hud.
## User args (after `--`): `shot=NAME` frames a named view for captures; `demo` lets a scripted defender play.

var level: Level
var world: World
var hud: Hud
var builder: Builder
var rig: CameraRig
var env: Environment
var args = null   # the user args as a Dictionary; a test sets them before adding the scene


func _ready() -> void:
	if args == null:
		args = {}
		for a in OS.get_cmdline_user_args():
			var kv := a.split("=", true, 1)
			args[kv[0]] = kv[1] if kv.size() > 1 else ""
	Sfx.setup(self, args["record"] + "/sound.log" if args.has("record") else "")
	level = Level.new()
	level.name = "Level"
	add_child(level)
	level.load_location("tristram")
	_environment()
	var scorch: Array = []
	var dressing := Dressing.new()
	dressing.name = "Dressing"
	add_child(dressing)
	dressing.build(level, scorch)
	level.build_floor(scorch)
	if not args.has("noscatter"):
		var scatter := Scatter.new()
		scatter.name = "Scatter"
		add_child(scatter)
		scatter.build(level, dressing.footprints)
	rig = CameraRig.new()
	rig.name = "Camera"
	add_child(rig)
	var c := level.centre()
	rig.snap(c + Vector3(2, 0, 3), 0.0, 50.0, 44.0)
	world = World.new()
	world.name = "World"
	add_child(world)
	world.setup(level)
	hud = Hud.new()
	add_child(hud)
	hud.setup(world)
	builder = Builder.new()
	builder.name = "Builder"
	add_child(builder)
	builder.setup(world, hud, rig)
	if args.has("demo"):
		var d := Demo.new()
		d.name = "Demo"
		add_child(d)
		d.setup(self, args.has("film"))
	world.announce.emit("Tristram", "The village under the cathedral burns. Hold the sanctuary.")
	Sfx.music("battle_tristram")
	if args.has("shot"):
		Shots.frame(self, args["shot"])
	if args.has("snap"):
		_snap_after(int(args.get("frames", "40")), args["snap"])
	if args.has("record"):
		_record(int(args.get("frames", "900")), int(args.get("every", "1")), args["record"])
	if args.has("gallery"):
		_gallery(int(args.get("frames", "40")), args["gallery"].split(","), args["out"])


## Save every `every`-th frame of the first `frames` as DIR/NNNNN.jpg, then quit (tools/record.sh).
func _record(frames: int, every: int, dir: String) -> void:
	for i in frames:
		Sfx.tick(i)
		await RenderingServer.frame_post_draw
		if i % every == 0:
			get_viewport().get_texture().get_image().save_jpg("%s/%05d.jpg" % [dir, i / every], 0.92)
	get_tree().quit()


## After `frames` frames, frame each named view in turn and save it as OUT/NAME.png, then quit (tools/gallery.sh).
func _gallery(frames: int, views: PackedStringArray, out: String) -> void:
	for i in frames:
		await get_tree().process_frame
	for v in views:
		Shots.frame(self, v)
		for i in 4:
			await get_tree().process_frame
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("%s/%s.png" % [out, v])
	get_tree().quit()


## Save the frame drawn after `frames` frames to `path`, then quit (tools/shot.sh).
func _snap_after(frames: int, path: String) -> void:
	for i in frames:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(path)
	get_tree().quit()


func _environment() -> void:
	env = Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var pano := PanoramaSkyMaterial.new()
	pano.panorama = load("res://assets/textures/sky.png")
	pano.energy_multiplier = 0.55
	sky.sky_material = pano
	env.sky = sky
	env.sky_rotation = Vector3(0, deg_to_rad(200), 0)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 1.0
	env.ambient_light_sky_contribution = 0.35
	env.ambient_light_color = Color(0.22, 0.28, 0.45)
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.35
	env.glow_enabled = true
	env.glow_intensity = 0.55
	env.glow_strength = 1.0
	env.glow_bloom = 0.04
	env.glow_hdr_threshold = 1.3
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_ADDITIVE
	for i in 7:
		env.set_glow_level(i, [0.0, 1.0, 1.0, 0.6, 0.3, 0.0, 0.0][i])
	env.ssao_enabled = true
	env.ssao_radius = 1.2
	env.ssao_intensity = 2.5
	env.ssr_enabled = true
	env.ssr_max_steps = 48
	env.ssr_fade_in = 0.2
	env.ssr_fade_out = 2.0
	env.ssil_enabled = true
	env.ssil_intensity = 1.2
	env.fog_enabled = true
	env.fog_light_color = Color(0.05, 0.05, 0.07)
	env.fog_light_energy = 1.0
	env.fog_density = 0.0025
	env.fog_sky_affect = 0.15
	env.fog_height = 1.0
	env.fog_height_density = 0.015
	env.volumetric_fog_enabled = true
	env.volumetric_fog_density = 0.004
	env.volumetric_fog_albedo = Color(0.45, 0.5, 0.62)
	env.volumetric_fog_emission = Color(0.012, 0.01, 0.014)
	env.volumetric_fog_anisotropy = 0.5
	env.volumetric_fog_length = 140.0
	env.volumetric_fog_ambient_inject = 0.08
	env.adjustment_enabled = true
	env.adjustment_contrast = 1.08
	env.adjustment_saturation = 1.1
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var moon := DirectionalLight3D.new()
	moon.name = "Moon"
	moon.light_color = Color(0.52, 0.64, 1.0)
	moon.light_energy = 2.3
	moon.shadow_enabled = true
	moon.directional_shadow_max_distance = 140.0
	moon.light_volumetric_fog_energy = 0.6
	moon.rotation_degrees = Vector3(-58, -150, 0)
	moon.light_angular_distance = 1.2
	moon.shadow_opacity = 0.85
	add_child(moon)
