class_name Game
extends Node
## Hellward's shell: the ways between the screens (the 2D game's ui/flow.py), every answer from the server.
##
## Title -> (the prologue on a new campaign) -> the world map (an owed story first) -> a location's intro (its
## before page on the first arrival) -> the defence -> the reckoning -> (an after page or an act's ending) -> the
## map, or the location again. The skill tree, the forge, settings, profiles and the pause menu open over whatever
## is showing. The server keeps the campaign; this side asks what to show and says what the player did.
## `screen=NAME` (title, profiles, map, briefing, skills, forge, chronicle, settings; `location=KEY`, `act=N`)
## opens one screen at once, for captures and tests.

signal shown(screen: Screen)          # a screen or overlay is on (tests)

const MAIN := "res://scenes/main.tscn"
# a won defence's reckoning as the server sends it, for `screen=reckoning` captures
const SAMPLE_RECKONING := {"won": true, "title": "The Sanctuary Holds", "location": "Tristram", "earned": 2, "gained": 2,
	"lines": ["Waves withstood: 5 of 5", "Monsters slain: 118", "Life kept: 14 of 20",
		"Curses the leaders laid on your towers: 4."],
	"note": "2 new sigils: spend them on skills.", "extra": [["holy", "The way down to the Graveyard is open."],
		["gold", "+2 salvage banked for the tower forge."]]}

var args := {}
var prefs: Prefs
var battle: Node                      # the battle scene (main.tscn) while one is on
var location := ""                    # the location of the battle on, or the last intro
var _layer: CanvasLayer
var _screen: Screen
var _overlays: Array = []
var _notice: Label


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else ""
	Sfx.setup(self, "")
	prefs = Prefs.load_saved()
	prefs.apply(get_window())
	_layer = CanvasLayer.new()
	_layer.layer = 10
	add_child(_layer)
	_notice = Ui.label("", 24, Color(1.0, 0.65, 0.45))
	_notice.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_notice.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	_notice.position.y = 24
	var top := CanvasLayer.new()
	top.layer = 20
	add_child(top)
	top.add_child(_notice)
	Net.failed.connect(_failed)
	Net.start()
	if args.has("snap"):
		_snap_after(int(args.get("frames", "60")), String(args["snap"]), int(args.get("run", "1")))
	if args.has("screen"):
		await _open_named(String(args["screen"]))
	else:
		title()


## Save the frame drawn `frames` frames after the first screen shows to `path`, and with `run` > 1 the frames after
## it beside it (NAME-1.png, NAME-2.png...: motion), then quit (captures of a screen).
func _snap_after(frames: int, path: String, run: int) -> void:
	await shown
	for i in frames:
		await get_tree().process_frame
	for k in run:
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(path if k == 0 else "%s-%d.png" % [path.get_basename(), k])
	Net.stop()
	get_tree().quit()


# -- Screens and overlays ---------------------------------------------------------------------------

## Show a screen in place of everything (the battle too).
func show_screen(screen: Screen, with := {}) -> Screen:
	_end_battle()
	for o in _overlays:
		o.queue_free()
	_overlays.clear()
	if is_instance_valid(_screen):
		_screen.queue_free()
	_screen = screen
	_mount(screen, with)
	return screen


## Open a screen over what is showing (the skill tree, the forge, the pause menu...).
func overlay(screen: Screen, with := {}) -> Screen:
	_overlays.append(screen)
	_mount(screen, with)
	return screen


func is_overlay(screen: Screen) -> bool:
	return _overlays.has(screen)


## Close an overlay; the screen under it shows what may have changed.
func close(screen: Screen) -> void:
	_overlays.erase(screen)
	screen.queue_free()
	var under: Screen = _overlays.back() if not _overlays.is_empty() else _screen
	if is_instance_valid(under):
		under.reload()


func _mount(screen: Screen, with: Dictionary) -> void:
	screen.game = self
	screen.data = with
	_layer.add_child(screen)
	screen.build()
	shown.emit(screen)


## A line at the top of the screen for a moment: what the server refused, and why.
func notice(text: String) -> void:
	_notice.text = text
	_notice.modulate.a = 1.0
	var tw := _notice.create_tween()
	tw.tween_interval(3.0)
	tw.tween_property(_notice, "modulate:a", 0.0, 1.0)


## Ask the server; the reply's data, or null after a notice of why it refused.
func ask(kind: String, with := {}):
	var reply: Dictionary = await Net.ask(kind, with).done
	if not bool(reply["ok"]):
		Sfx.play("refuse")
		notice(String(reply["why"]))
		return null
	return reply["data"]


func _failed(why: String) -> void:
	var s := ErrorScreen.new()
	overlay(s, {"why": why})


# -- The ways between them (flow.py) ---------------------------------------------------------------

func title() -> void:
	show_screen(TitleScreen.new())
	if Sfx.music_name() != "title":
		Sfx.music("title", -6.0, 2.0)


func profiles() -> void:
	var data = await ask("profiles")
	if data != null:
		overlay(ProfilesScreen.new(), data)


func settings() -> void:
	overlay(SettingsScreen.new())


## The title's Descend: the prologue on a new campaign, then the map, the lantern walking straight on to
## Tristram when nothing is won yet.
func descend() -> void:
	var view = await ask("campaign")
	if view == null:
		return
	if bool(view["prologue"]):
		await ask("seen", {"key": "prologue"})
		show_screen(PrologueScreen.new(), {"then": func(): _descend(view)})
	else:
		_descend(view)


func _descend(view: Dictionary) -> void:
	if int(view["sigils"]) == 0:
		open_map(1, true)
	else:
		world_map()


## The map, after the story it owes first, if any.
func world_map() -> void:
	var view = await ask("campaign")
	if view == null:
		return
	if view["due"] != null:
		var tale: Dictionary = view["due"]
		await ask("seen", {"key": tale["key"]})
		story(tale, func(): _after(String(tale["key"])))
	else:
		open_map(int(view["act"]), false, view)


## Where a story leaves the map: after Act I's ending, on Act II's map, the lantern walking to the Docks.
func _after(key: String) -> void:
	if key == "act1/end":
		open_map(2, true)
	else:
		open_map(0, false)


func open_map(act: int, first: bool, view = null) -> void:
	if view == null:
		view = await ask("campaign")
		if view == null:
			return
	var with: Dictionary = view.duplicate()
	with["act"] = act if act > 0 else int(view["act"])
	with["first"] = first
	show_screen(MapScreen.new(), with)
	if Sfx.music_name() != "title":
		Sfx.music("title", -6.0, 2.0)


## A location's before page on the first arrival, then its intro.
func intro(key: String) -> void:
	var brief = await ask("briefing", {"location": key})
	if brief == null:
		return
	location = key
	if brief["story"] != null:
		await ask("seen", {"key": brief["story"]["key"]})
		story(brief["story"], func(): _open_intro(brief))
	else:
		_open_intro(brief)


func _open_intro(brief: Dictionary) -> void:
	show_screen(BriefingScreen.new(), brief)
	var track := "battle_" + String(brief["key"])
	if Sfx.music_name() != track:
		Sfx.music(track, -8.0, 2.0)


## The intro's Story: its before page again, back to the intro.
func retell(brief: Dictionary) -> void:
	if brief["before"] == null:
		return
	await ask("seen", {"key": brief["before"]["key"]})
	story(brief["before"], func(): intro(String(brief["key"])))


func story(tale: Dictionary, then: Callable) -> void:
	show_screen(StoryScreen.new(), {"pages": tale["pages"], "then": then})


func chronicle() -> void:
	var data = await ask("chronicle")
	if data == null:
		return
	await ask("seen", {"key": "prologue"})
	show_screen(PrologueScreen.new(), {"then": func(): _chronicle(data["stories"], 0), "skip": title})


func _chronicle(stories: Array, i: int) -> void:
	if i >= stories.size():
		title()
		return
	await ask("seen", {"key": stories[i]["key"]})
	show_screen(StoryScreen.new(), {"pages": stories[i]["pages"], "then": func(): _chronicle(stories, i + 1),
		"skip": title})


func skills(at := "") -> void:
	var data = await ask("skills", {"location": at} if at != "" else {})
	if data != null:
		var with: Dictionary = data
		with["location"] = at
		overlay(SkillsScreen.new(), with)


func forge() -> void:
	var data = await ask("forge_view")
	if data != null:
		overlay(ForgeScreen.new(), data)


# -- Battles -----------------------------------------------------------------------------------------

func defend(key: String) -> void:
	var start = await ask("defend", {"location": key})
	if start != null:
		location = key
		_battle(start)


## The title's "Watch the leaders at work": the server's strongest scripted player defends the Cathedral.
func demo() -> void:
	var start = await ask("demo")
	if start != null:
		_battle(start)


func _battle(start: Dictionary) -> void:
	show_screen(BattleScreen.new())
	battle = load(MAIN).instantiate()
	battle.battle = start
	battle.args = {"film": ""} if bool(start["scripted"]) else {}
	battle.prefs = prefs
	add_child(battle)
	battle.menu.connect(pause)
	battle.ended.connect(_ended)
	battle.started.connect(func(): battle.world.minds = prefs.minds)


func _end_battle() -> void:
	if is_instance_valid(battle):
		battle.queue_free()
	battle = null
	Engine.time_scale = 1.0


func pause() -> void:
	if battle == null or not _overlays.is_empty():
		return
	if bool(battle.battle["demo"]):
		await ask("abandon")
		title()
		return
	battle.world.set_paused(true)
	overlay(PauseScreen.new())


func resume(screen: Screen) -> void:
	_overlays.erase(screen)
	screen.queue_free()
	if battle != null:
		battle.world.set_paused(false)


func _ended(result: Dictionary) -> void:
	if bool(battle.battle["demo"]):
		await ask("abandon")
		title()
		return
	overlay(ReckoningScreen.new(), result)


## Leaving the reckoning: an after page or an act's ending first when one is due, then `again` (the location's
## intro) or the map.
func leave_reckoning(again: bool) -> void:
	var way = await ask("leave", {"again": again})
	if way == null:
		return
	var then := func():
		match String(way["then"]):
			"intro": intro(String(way["location"]))
			"act2": open_map(2, true)
			_: world_map()
	if way["story"] != null:
		story(way["story"], then)
	else:
		then.call()


## The pause menu's ways out of a defence: it is abandoned (nothing is kept, no replay is written).
func restart() -> void:
	await ask("abandon")
	defend(location)


func to_map() -> void:
	await ask("abandon")
	world_map()


func to_title() -> void:
	await ask("abandon")
	title()


func leave() -> void:
	Net.stop()
	get_tree().quit()


# -- One screen at once (captures, tests) ------------------------------------------------------------

func _open_named(name: String) -> void:
	if not await Net.wait_ready():
		return
	var at: String = args.get("location", "tristram")
	match name:
		"title": title()
		"profiles":
			title()
			profiles()
		"settings":
			title()
			settings()
		"map": open_map(int(args.get("act", "0")), false)
		"briefing": intro(at)
		"skills": skills(at if args.has("location") else "")
		"forge": forge()
		"chronicle": chronicle()
		"defend": defend(at)
		"demo": demo()
		"story":
			var brief = await ask("briefing", {"location": at})
			story(brief["before"], title)
		"prologue": show_screen(PrologueScreen.new(), {"then": title})
		"pause":
			title()
			overlay(PauseScreen.new())
		"reckoning":
			title()
			overlay(ReckoningScreen.new(), SAMPLE_RECKONING)
		_: push_error("no screen %s" % name)
