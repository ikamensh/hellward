extends Node3D
## Hellward's battle: the map in 3D, a defence the server plays, the HUD and the player's hands.
## The game's shell (game.gd) sets `battle` (the server's start message) before adding the scene; run on its own
## (captures, tests, `godot --path game`), it asks the server for one itself: `demo` watches a scripted player
## (`player=NAME`, `location=KEY`), else the player defends (`location=KEY`, Tristram by default).
## `film` also directs the camera; captures (tools/shot.sh, gallery.sh, record.sh) pass `shot=VIEW`, `snap=PNG`,
## `gallery=V,V out=DIR`, `record=DIR every=N` with `frames=N`; `nointro` skips the opening (tests).

signal started                       # the battle is laid out and running
signal menu                          # the player asked for the pause menu
signal ended(result: Dictionary)     # three seconds after the defence was decided: the reckoning's turn

var level: Level
var world: World
var hud: Hud
var builder: Builder
var rig: CameraRig
var env: Environment
var args = null   # the user args as a Dictionary; a test sets them before adding the scene
var prefs: Prefs  # the shell's (the settings change it live); alone, the scene reads the saved ones
var battle := {}  # the server's battle message; the shell sets it, or the scene asks for one


func _ready() -> void:
	if args == null:
		args = {}
		for a in OS.get_cmdline_user_args():
			var kv := a.split("=", true, 1)
			args[kv[0]] = kv[1] if kv.size() > 1 else ""
	Sfx.setup(self, args["record"] + "/sound.log" if args.has("record") else "")
	if battle.is_empty():
		if not await Net.wait_ready():
			push_error("no server: " + Net.error)
			return
		var location: String = args.get("location", "tristram")
		var request := {"location": location}
		if args.has("demo"):
			request["player"] = args.get("player", "adaptive")
		var reply: Dictionary = await Net.ask("demo" if args.has("demo") else "defend", request).done
		if not bool(reply["ok"]):
			push_error("the server refused the battle: " + String(reply["why"]))
			return
		battle = reply["data"]
	_build()


func _build() -> void:
	if prefs == null:
		prefs = Prefs.load_saved()
	level = Level.new()
	level.name = "Level"
	add_child(level)
	level.load_battle(battle)
	_environment()
	_fit_resolution()
	get_viewport().size_changed.connect(_fit_resolution)
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
	rig.bounds = AABB(Vector3(-10, 0, -10), Vector3(level.width * Level.TILE + 20, 0, level.height * Level.TILE + 20))
	rig.snap(c + Vector3(2, 0, 3), 0.0, 55.0, 52.0)
	world = World.new()
	world.name = "World"
	add_child(world)
	world.setup(level, battle)
	world.dressing = dressing
	hud = Hud.new()
	hud.prefs = prefs
	add_child(hud)
	hud.setup(world)
	builder = Builder.new()
	builder.name = "Builder"
	add_child(builder)
	builder.setup(world, hud, rig)
	builder.menu.connect(func(): menu.emit())
	hud.order.connect(func(n: String): if n == "menu": menu.emit())
	var staged: bool = args.has("shot") or args.has("gallery") or args.has("snap") or args.has("record") or args.has("nointro")
	if args.has("film") or (world.demo and not staged):
		var d := Demo.new()
		d.name = "Demo"
		add_child(d)
		d.setup(self)
	elif not staged:
		var intro := Intro.new()
		intro.name = "Intro"
		add_child(intro)
		intro.play(self)
	else:
		world.announce.emit(String(battle["location"]["name"]), "Hold the sanctuary. The first wave comes soon.")
		Sfx.music(music(), -8.0, 0.01)
	# as in the 2D game: the title's music after a victory, silence under the defeat
	world.finished.connect(func(won: bool):
		if won:
			Sfx.music("title", -6.0, 4.0)
		else:
			Sfx.stop_music(4.0)
		get_tree().create_timer(3.0, false).timeout.connect(func(): ended.emit(world.result)))
	if args.has("shot"):
		Shots.frame(self, args["shot"])
	if args.has("snap"):
		_snap_after(int(args.get("frames", "40")), args["snap"])
	if args.has("record"):
		_record(int(args.get("frames", "900")), int(args.get("every", "1")), args["record"])
	if args.has("gallery"):
		_gallery(int(args.get("frames", "40")), args["gallery"].split(","), args["out"])
	started.emit()


## A live defence keeps the cursor in the window, so the window's edges pan; paused, decided or watched, it lets go.
## Paused or decided, the camera stays where it is: the pause menu's and the reckoning's keys are theirs.
func _process(_delta: float) -> void:
	if rig and world:
		var live := not world.paused and world.outcome == ""
		rig.hold_mouse = prefs.hold_mouse and not world.demo and live
		rig.frozen = not live


## The location's battle music.
func music() -> String:
	return "battle_" + String(battle["location"]["key"])


## Save every `every`-th frame as DIR/NNNNN.jpg for up to `frames` frames, or until 14 s after the battle ends
## (the closing shot), then quit (tools/record.sh).
func _record(frames: int, every: int, dir: String) -> void:
	var ended := -1
	var saving: Array[int] = []
	for i in frames:
		Sfx.tick(i)
		await RenderingServer.frame_post_draw
		if i % every == 0:
			# the readback must happen now; the encoding goes to a worker so the next frame renders meanwhile
			var img := get_viewport().get_texture().get_image()
			var path := "%s/%05d.jpg" % [dir, i / every]
			saving.append(WorkerThreadPool.add_task(func(): img.save_jpg(path, 0.92)))
			while saving.size() > 8:
				WorkerThreadPool.wait_for_task_completion(saving.pop_front())
		if world.outcome != "" and ended < 0:
			ended = i
		if ended >= 0 and i - ended > 14 * 30:
			break
	for task in saving:
		WorkerThreadPool.wait_for_task_completion(task)
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
	env = Atmosphere.night(self)
	_ground_mist()
	_vignette()


## 3D renders at no more than a 1080p frame's worth of pixels, upscaled with FSR: a Retina window would
## otherwise draw four times the pixels for little visible gain. The HUD stays sharp at full resolution.
func _fit_resolution() -> void:
	var vp := get_viewport()
	var px: Vector2 = Vector2(get_window().size) if vp == get_tree().root else Vector2((vp as SubViewport).size)
	var scale: float = clamp(sqrt(1920.0 * 1080.0 / max(px.x * px.y, 1.0)), 0.5, 1.0)
	vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR if scale < 1.0 else Viewport.SCALING_3D_MODE_BILINEAR
	vp.scaling_3d_scale = scale
	vp.fsr_sharpness = 0.4


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
