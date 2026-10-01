extends Node
## Captures render here (scenes/capture.tscn, run by tools/godot-capture.sh): the scene named by `scene=` runs
## inside an offscreen SubViewport and the window itself draws nothing. macOS stops handing a hidden window
## (or any window, once the screen is locked) its drawables, which slowed windowed renders to a frame a second;
## a SubViewport never asks for one. `res=WxH` sets the size (1920x1080).

func _ready() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else ""
	var res: PackedStringArray = args.get("res", "1920x1080").split("x")
	var view := SubViewport.new()
	view.size = Vector2i(int(res[0]), int(res[1]))
	view.msaa_3d = Viewport.MSAA_2X
	view.screen_space_aa = Viewport.SCREEN_SPACE_AA_FXAA
	view.positional_shadow_atlas_size = 8192
	view.anisotropic_filtering_level = Viewport.ANISOTROPY_4X
	view.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(view)
	RenderingServer.viewport_set_update_mode(get_tree().root.get_viewport_rid(), RenderingServer.VIEWPORT_UPDATE_DISABLED)
	get_window().size = Vector2i(64, 64)
	var scene: PackedScene = load(args["scene"])
	if scene == null:
		push_error("capture: cannot load %s" % args["scene"])
		get_tree().quit(1)
		return
	view.add_child(scene.instantiate())
	if args.has("perf"):
		_profile(view)
	if args.has("off"):
		await get_tree().process_frame
		_switch_off(view, args["off"].split(","))
	# a capture that hangs (a script error leaves the scene idle) must not run forever
	get_tree().create_timer(float(args.get("timeout", "600")), true, false, true).timeout.connect(func():
		push_error("capture: timed out")
		get_tree().quit(2))



## `perf`: every 150 frames, print the mean frame, GPU and CPU render times of the scene's viewport (ms).
func _profile(view: SubViewport) -> void:
	var rid := view.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(rid, true)
	var gpu := 0.0
	var cpu := 0.0
	var n := 0
	var t0 := Time.get_ticks_usec()
	while true:
		await RenderingServer.frame_post_draw
		gpu += RenderingServer.viewport_get_measured_render_time_gpu(rid)
		cpu += RenderingServer.viewport_get_measured_render_time_cpu(rid)
		n += 1
		if n == 150:
			var frame := (Time.get_ticks_usec() - t0) / 1000.0 / n
			print("perf: frame %.1f ms, gpu %.1f ms, render cpu %.1f ms, draw calls %d, objects %d" % [frame, gpu / n, cpu / n,
				RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
				RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME)])
			gpu = 0.0
			cpu = 0.0
			n = 0
			t0 = Time.get_ticks_usec()


## `off=a,b`: switch features off to see what a frame's time goes to (with `perf`): vol, ssr, ssil, ssao, glow,
## omnishadow, sun (shadows), particles, grass (every MultiMesh), msaa, half (3D at half resolution).
func _switch_off(view: SubViewport, what: PackedStringArray) -> void:
	var we: WorldEnvironment = view.find_children("*", "WorldEnvironment", true, false)[0]
	var env := we.environment
	for w in what:
		match w:
			"vol": env.volumetric_fog_enabled = false
			"ssr": env.ssr_enabled = false
			"ssil": env.ssil_enabled = false
			"ssao": env.ssao_enabled = false
			"glow": env.glow_enabled = false
			"omnishadow":
				for l in view.find_children("*", "OmniLight3D", true, false): (l as OmniLight3D).shadow_enabled = false
				for l in view.find_children("*", "SpotLight3D", true, false): (l as SpotLight3D).shadow_enabled = false
			"sun": for l in view.find_children("*", "DirectionalLight3D", true, false): (l as DirectionalLight3D).shadow_enabled = false
			"particles": for pp in view.find_children("*", "GPUParticles3D", true, false): (pp as GPUParticles3D).visible = false
			"grass": for mm in view.find_children("*", "MultiMeshInstance3D", true, false): (mm as MultiMeshInstance3D).visible = false
			"msaa": view.msaa_3d = Viewport.MSAA_DISABLED
			"half": view.scaling_3d_scale = 0.5
	print("perf: switched off ", what)
