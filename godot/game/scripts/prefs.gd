class_name Prefs
extends RefCounted
## This player's preferences, kept on this machine (user://settings.cfg), never on the server: the music's and the
## sounds' volume, fullscreen, and whether the leaders' minds show in the battle's chronicle.

const PATH := "user://settings.cfg"   # HELLWARD_PREFS moves it (tests and captures never touch the player's)

var music := 0.6
var sfx := 0.8
var fullscreen := false
var minds := true


static func load_saved() -> Prefs:
	var p := Prefs.new()
	var cfg := ConfigFile.new()
	if cfg.load(path()) == OK:
		p.music = clampf(float(cfg.get_value("audio", "music", p.music)), 0.0, 1.0)
		p.sfx = clampf(float(cfg.get_value("audio", "sfx", p.sfx)), 0.0, 1.0)
		p.fullscreen = bool(cfg.get_value("display", "fullscreen", p.fullscreen))
		p.minds = bool(cfg.get_value("battle", "minds", p.minds))
	return p


func save() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("audio", "music", music)
	cfg.set_value("audio", "sfx", sfx)
	cfg.set_value("display", "fullscreen", fullscreen)
	cfg.set_value("battle", "minds", minds)
	cfg.save(path())


## Set the buses' volumes and the window's mode.
func apply(window: Window) -> void:
	Sfx.volumes(music, sfx)
	if DisplayServer.get_name() != "headless":
		window.mode = Window.MODE_FULLSCREEN if fullscreen else Window.MODE_MAXIMIZED


static func path() -> String:
	var moved := OS.get_environment("HELLWARD_PREFS")
	return moved if moved != "" else PATH
