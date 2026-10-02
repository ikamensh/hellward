extends Node
## A staged moment of a battle, rendered for looking at (tools/stage.sh NAME OUT_DIR; the stage itself is written by
## the repository's tools/stages.py): the server's demo plays the stage's defence (a ghost's log or a scripted
## player), fast until just before the moment; when its event comes the camera frames it (the tower, the monster,
## both, or the shrine's door) and the frames `at` so many frames after it are saved as OUT/NAME_N.png.
## User args: stage=PATH.json out=DIR name=NAME.

const LEAD := 4.0                    # seconds of the fight's time before the moment that play slows to its own pace
const PACE := 8.0                    # how fast the fight runs until then

var _args := {}
var _spec: Dictionary
var _main: Node
var _world: World
var _seen: Array = []                # the moment's event, once it came


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=", true, 1)
		_args[kv[0]] = kv[1] if kv.size() > 1 else ""
	_spec = JSON.parse_string(FileAccess.get_file_as_string(String(_args["stage"])))
	Net.start()
	if not await Net.wait_ready():
		_fail("no server: " + Net.error)
		return
	var reply: Dictionary = await Net.ask("demo", _spec["request"]).done
	if not bool(reply["ok"]):
		_fail("the server refused the stage: " + String(reply["why"]))
		return
	_main = load("res://scenes/main.tscn").instantiate()
	_main.battle = reply["data"]
	_main.args = {"nointro": ""}
	add_child(_main)   # with its battle given, it lays the battle out at once
	_world = _main.world
	_world.minds = false
	_world.happened.connect(_watch)
	_main.hud.cinematic(not bool(_spec["hud"]), 0.01)
	Engine.time_scale = PACE
	while _seen.is_empty():
		if _world.time >= float(_spec["time"]) - LEAD:
			Engine.time_scale = 1.0
		if _world.outcome != "":
			_fail("the defence ended before its moment")
			return
		await get_tree().process_frame
	Engine.time_scale = 1.0
	_frame(_seen[0])
	var done := 0
	var at: Array = _spec["at"]
	for i in at.size():
		while done < int(at[i]):
			await get_tree().process_frame
			done += 1
		if String(_spec["hover"]) != "" and i == at.size() - 1:
			await _hover()
		await RenderingServer.frame_post_draw
		var path := "%s/%s_%d.png" % [_args["out"], _args.get("name", "stage"), i + 1]
		get_viewport().get_texture().get_image().save_png(path)
		print("stage: ", path)
	get_tree().quit()


func _watch(e: Array) -> void:
	if not _seen.is_empty() or String(e[0]) != String(_spec["event"]):
		return
	var key = e[1]["id"] if String(e[0]) == "bolt" else e[1]
	if str(key) == str(_spec["key"]):
		_seen.append(e)


## The camera on the moment: across the line from the tower to the monster (a `pair`), on one of them, or on the
## shrine's door, at the stage's pitch and distance.
func _frame(e: Array) -> void:
	var rig: CameraRig = _main.rig
	rig.user_control = false
	var tower: Tower = null
	var monster: Monster = null
	match String(e[0]):
		"bolt":
			tower = _world.towers.get(int(e[1]["tower"]))
			monster = _world.monsters.get(int(e[1]["target"]))
		"hook":
			tower = _world.towers.get(int(e[1]))
			monster = _world.monsters.get(int(e[2]))
		"hymn":
			tower = _world.towers.get(int(e[1]))
		"spawn", "returned", "leak":
			monster = _world.monsters.get(int(e[1]))
	var view: Array = _spec["view"]
	var centre: Vector3 = _main.level.door_pos
	var yaw := 0.0
	match String(_spec["frame"]):
		"tower":
			centre = tower.global_position + Vector3(0, 1.5, 0)
			yaw = 25.0
		"monster":
			centre = monster.global_position
			rig.follow = monster
			yaw = 15.0
		"pair":
			var a := tower.global_position
			var b := monster.global_position if monster else a
			centre = (a + b) / 2 + Vector3(0, 1.0, 0)
			var d := b - a
			yaw = rad_to_deg(atan2(-d.z, d.x))
			if cos(deg_to_rad(yaw)) < 0.0:   # from the south side, as the battle camera looks
				yaw += 180.0
		"door":
			centre = _main.level.door_pos - _main.level.door_outward() * 7.0
			var out: Vector3 = _main.level.door_outward()
			yaw = rad_to_deg(atan2(-out.z, out.x)) + 90.0 + 25.0   # beside the steps, looking up at the door
	rig.snap(centre, yaw, float(view[0]), float(view[1]))


## The fight held still and the mouse on the stage's monster kind nearest the camera's target: its plate shows.
func _hover() -> void:
	_world.set_paused(true)
	var best: Monster = null
	for m in _world.living():
		if m.kind == String(_spec["hover"]) and (best == null or m.global_position.distance_to(_main.rig.target)
				< best.global_position.distance_to(_main.rig.target)):
			best = m
	if best == null:
		return
	var vp := get_viewport()
	var ev := InputEventMouseMotion.new()
	ev.position = vp.get_final_transform() * _main.rig.cam.unproject_position(best.chest())
	vp.push_input(ev)
	for i in 3:
		await get_tree().process_frame


func _fail(why: String) -> void:
	push_error("stage: " + why)
	get_tree().quit(1)
