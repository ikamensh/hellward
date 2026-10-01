extends Node
## Captures render here (scenes/capture.tscn, run by tools/godot-capture.sh): the scene named by `scene=` runs
## inside an offscreen SubViewport and the window itself draws nothing. macOS stops handing a hidden window
## (or any window, once the screen is locked) its drawables, which slowed windowed renders to a frame a second;
## a SubViewport never asks for one. `res=WxH` sets the size (1920x1080).

static var view: SubViewport


func _ready() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else ""
	var res: PackedStringArray = args.get("res", "1920x1080").split("x")
	view = SubViewport.new()
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
	# a capture that hangs (a script error leaves the scene idle) must not run forever
	get_tree().create_timer(float(args.get("timeout", "600")), true, false, true).timeout.connect(func():
		push_error("capture: timed out")
		get_tree().quit(2))


## The frame last drawn, as an image.
static func image() -> Image:
	return view.get_texture().get_image()
