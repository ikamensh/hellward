extends Node3D
## Hellward 3D: Tristram burns. Builds the world, then hands the battle to World and the screen to Hud.
## User args (after `--`): `demo` lets a scripted defender play, `film` also directs the camera; captures
## (tools/shot.sh, gallery.sh, record.sh) pass `shot=VIEW`, `snap=PNG`, `gallery=V,V out=DIR`,
## `record=DIR every=N` with `frames=N`; `nointro` skips the opening (tests).

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
	var scatter := Scatter.new()
	scatter.name = "Scatter"
	add_child(scatter)
	scatter.build(level, dressing.footprints)
	rig = CameraRig.new()
	rig.name = "Camera"
	add_child(rig)
	var c := level.centre()
	rig.snap(c + Vector3(2, 0, 3), 0.0, 55.0, 52.0)
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
	var staged: bool = args.has("shot") or args.has("gallery") or args.has("snap") or args.has("record") or args.has("nointro")
	if not args.has("demo") and not staged:
		var intro := Intro.new()
		intro.name = "Intro"
		add_child(intro)
		intro.play(self)
	elif not args.has("film"):
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


## Save every `every`-th frame as DIR/NNNNN.jpg for up to `frames` frames, or until 14 s after the battle ends
## (the closing shot), then quit (tools/record.sh).
func _record(frames: int, every: int, dir: String) -> void:
	var ended := -1
	for i in frames:
		Sfx.tick(i)
		await RenderingServer.frame_post_draw
		if i % every == 0:
			get_viewport().get_texture().get_image().save_jpg("%s/%05d.jpg" % [dir, i / every], 0.92)
		if world.outcome != "" and ended < 0:
			ended = i
		if ended >= 0 and i - ended > 14 * 30:
			break
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
	pano.energy_multiplier = 0.4
	sky.sky_material = pano
	env.sky = sky
	env.sky_rotation = Vector3(0, deg_to_rad(200), 0)
	# a night lit by its fires: dim cold ambient and moon, the exposure carried by the firelit pools
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.13, 0.17, 0.26)
	env.ambient_light_energy = 0.9
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.7
	env.tonemap_agx_contrast = 1.45
	env.glow_enabled = true
	env.glow_intensity = 0.7
	env.glow_strength = 1.0
	env.glow_bloom = 0.0
	env.glow_hdr_threshold = 1.0
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SCREEN
	for i in 7:
		env.set_glow_level(i, [0.0, 0.5, 1.0, 0.8, 0.6, 0.35, 0.0][i])
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
	env.fog_light_color = Color(0.03, 0.035, 0.05)
	env.fog_light_energy = 1.0
	env.fog_density = 0.004
	env.fog_sky_affect = 0.3
	env.fog_height = 1.0
	env.fog_height_density = 0.015
	# fog the lights glow through, not a grey veil
	env.volumetric_fog_enabled = true
	env.volumetric_fog_density = 0.007
	env.volumetric_fog_albedo = Color(0.7, 0.72, 0.8)
	env.volumetric_fog_emission = Color(0, 0, 0)
	env.volumetric_fog_anisotropy = 0.6
	env.volumetric_fog_length = 120.0
	env.volumetric_fog_ambient_inject = 0.0
	env.volumetric_fog_gi_inject = 0.0
	env.adjustment_enabled = true
	env.adjustment_contrast = 1.0
	env.adjustment_saturation = 1.05
	env.adjustment_color_correction = _grade()
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var moon := DirectionalLight3D.new()
	moon.name = "Moon"
	moon.light_color = Color(0.5, 0.66, 0.9)
	moon.light_energy = 1.4
	moon.shadow_enabled = true
	moon.directional_shadow_max_distance = 140.0
	moon.light_volumetric_fog_energy = 0.2
	moon.rotation_degrees = Vector3(-58, -150, 0)
	moon.light_angular_distance = 1.2
	moon.shadow_opacity = 1.0
	add_child(moon)
	_ground_mist()
	_vignette()


## The grade: cool shadows, neutral middle, warm highlights.
func _grade() -> GradientTexture1D:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.08, 0.25, 0.5, 0.75, 1.0])
	g.colors = PackedColorArray([Color(0, 0, 0), Color(0.05, 0.065, 0.085), Color(0.21, 0.235, 0.265),
		Color(0.51, 0.5, 0.48), Color(0.79, 0.75, 0.69), Color(1.0, 0.97, 0.91)])
	var t := GradientTexture1D.new()
	t.gradient = g
	t.width = 256
	return t


## A low, drifting mist over the field that the fires light from inside.
func _ground_mist() -> void:
	var mist := FogVolume.new()
	mist.size = Vector3(170, 1.6, 120)
	mist.position = level.centre() + Vector3(0, 0.3, 0)
	var fm := FogMaterial.new()
	fm.density = 0.025
	fm.albedo = Color(0.55, 0.6, 0.7)
	fm.height_falloff = 1.2
	fm.edge_fade = 0.3
	var nt := NoiseTexture3D.new()
	nt.width = 64
	nt.height = 16
	nt.depth = 64
	nt.seamless = true
	var fn := FastNoiseLite.new()
	fn.frequency = 0.05
	nt.noise = fn
	fm.density_texture = nt
	mist.material = fm
	add_child(mist)


## Darkened corners, under the HUD: the eye goes to the middle.
func _vignette() -> void:
	var layer := CanvasLayer.new()
	layer.layer = -1
	var rect := ColorRect.new()
	rect.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/vignette.gdshader")
	rect.material = m
	layer.add_child(rect)
	add_child(layer)
