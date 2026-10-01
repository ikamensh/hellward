class_name Sfx
extends RefCounted
## The 2D game's sound cues and music (game/assets/audio, made by tools/export_audio.py).
## `play` picks one of a cue's takes; a cue already sounding VOICES times is skipped, so a volley of
## arrows does not become a roar. While recording (tools/record.sh) every cue played is logged with its
## frame, and the recorder mixes the soundtrack from that log.

const DIR := "res://assets/audio/"
const VOICES := 4
const GAIN := {"arrow_cast": -9.0, "arrow_hit": -10.0, "fire_cast": -6.0, "fireball": -4.0,
	"frost": -6.0, "lightning": -4.0, "gold": -14.0, "build": -3.0, "death_fallen": -6.0, "death_zombie": -4.0,
	"death_skeleton": -5.0, "death_shaman": -2.0}

static var _takes: Dictionary = {}       # cue -> Array of streams
static var _sounding: Dictionary = {}    # cue -> players still playing
static var _log: FileAccess
static var _frame := 0
static var _root: Node
static var _music: AudioStreamPlayer


static func setup(root: Node, log_path: String) -> void:
	_root = root
	if log_path != "":
		_log = FileAccess.open(log_path, FileAccess.WRITE)


## Called once a frame by whoever records (main.gd), so logged cues carry the frame they sound on.
static func tick(frame: int) -> void:
	_frame = frame


static func _streams(cue: String) -> Array:
	if not _takes.has(cue):
		var found: Array = []
		var i := 0
		while ResourceLoader.exists("%s%s_%d.wav" % [DIR, cue, i]):
			found.append("%s_%d" % [cue, i])
			i += 1
		if found.is_empty():
			found.append(cue)
		_takes[cue] = found
	return _takes[cue]


static func play(cue: String, at = null) -> void:
	var live: Array = _sounding.get(cue, []).filter(func(p): return is_instance_valid(p) and p.playing)
	if live.size() >= VOICES:
		return
	var stems := _streams(cue)
	var stem: String = stems[randi() % stems.size()]
	var gain: float = GAIN.get(cue, 0.0)
	var player: Node
	if at is Vector3:
		var p3 := AudioStreamPlayer3D.new()
		p3.unit_size = 28.0
		p3.max_distance = 220.0
		p3.volume_db = gain
		_root.add_child(p3)
		p3.global_position = at
		p3.stream = load(DIR + stem + ".wav")
		p3.play()
		p3.finished.connect(p3.queue_free)
		player = p3
	else:
		var p2 := AudioStreamPlayer.new()
		p2.volume_db = gain
		_root.add_child(p2)
		p2.stream = load(DIR + stem + ".wav")
		p2.play()
		p2.finished.connect(p2.queue_free)
		player = p2
	live.append(player)
	_sounding[cue] = live
	if _log:
		var cam := _root.get_viewport().get_camera_3d()
		var pan := 0.0
		if at is Vector3 and cam:
			pan = clamp(cam.global_transform.basis.x.dot((at as Vector3) - cam.global_position) / 30.0, -0.8, 0.8)
		_log.store_line("%d %s %.1f %.2f" % [_frame, stem, gain, pan])
		_log.flush()


## Play a looping track (title, battle_tristram) in place of the current one, which fades out over `fade` s.
static func music(name: String, volume_db := -8.0, fade := 2.0) -> void:
	_fade_out(fade)
	var stream: AudioStreamMP3 = load(DIR + "music_" + name + ".mp3")
	stream.loop = true
	_music = AudioStreamPlayer.new()
	_music.stream = stream
	_music.volume_db = volume_db
	_root.add_child(_music)
	_music.play()
	_note("music_" + name, volume_db, fade)


## Let the current track fade to silence.
static func stop_music(fade := 2.0) -> void:
	_fade_out(fade)
	_note("music_stop", 0.0, fade)


static func _fade_out(fade: float) -> void:
	if is_instance_valid(_music):
		var old := _music
		var tw := old.create_tween()
		tw.tween_property(old, "volume_db", -60.0, fade)
		tw.tween_callback(old.queue_free)
	_music = null


## Music changes go in the recording's log as "frame stem gain fade" (tools/mixdown.py).
static func _note(stem: String, gain: float, fade: float) -> void:
	if _log:
		_log.store_line("%d %s %.1f %.1f" % [_frame, stem, gain, fade])
		_log.flush()
