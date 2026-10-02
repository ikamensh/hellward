extends Node
## The link to Hellward's server (autoload `Net`): it starts `python -m hellward.server` as a child, which connects
## back to this loopback port, and they exchange newline-delimited JSON (hellward/server/protocol.py).
## The server is the authority: battles, the campaign and the saves live there; this side asks and shows.
##
##     var reply: Dictionary = await Net.ask("campaign").done   # {ok, data} or {ok: false, why}
##     Net.frame.connect(...)                                    # a battle step
##
## The server lives exactly as long as this process; either side failing is reported (`failed`), never swallowed.

signal status(text: String)          # the server is starting: what it is doing
signal connected                      # the server answers requests
signal failed(why: String)            # the server stopped or said something this client cannot follow
signal frame(message: Dictionary)     # a battle step, or what an order did

const PROTOCOL := 3

var is_ready := false
var compiled := false
var error := ""

var _listener: TCPServer
var _peer: StreamPeerTCP
var _pid := -1
var _token := ""
var _buffer := PackedByteArray()
var _next_id := 0
var _pending := {}                    # id -> Pending
var _started := false


class Pending:
	extends RefCounted
	signal done(reply: Dictionary)


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS   # replies arrive while the game is paused


## Start the server, once: the title shows at once and the link comes up in the background.
func start() -> void:
	if _started:
		return
	_started = true
	_listener = TCPServer.new()
	var err := _listener.listen(0, "127.0.0.1")
	if err != OK:
		_fail("cannot listen on a loopback port: %s" % error_string(err))
		return
	_token = "%x%x" % [randi(), randi()]
	var cmd := server_command()
	var args: PackedStringArray = cmd.slice(1)
	args.append_array(["--connect", str(_listener.get_local_port()), "--token", _token])
	var data_dir := OS.get_environment("HELLWARD_DATA")
	if data_dir != "":
		args.append_array(["--data", data_dir])
	# the capture shim (tools/godot-capture.sh) is for this process only, never the server's
	OS.unset_environment("DYLD_INSERT_LIBRARIES")
	_pid = OS.create_process(cmd[0], args)
	if _pid <= 0:
		_fail("cannot start the server: %s" % " ".join(cmd))


## The server's command line: HELLWARD_SERVER (a full command, for tools), a release's bundled Python beside the
## game (Hellward.app/Contents/Resources/server, or server\ next to Hellward.exe: python, the hellward package and
## its compiled build), or the checkout's virtual environment two levels above this project.
static func server_command() -> PackedStringArray:
	var override := OS.get_environment("HELLWARD_SERVER")
	if override != "":
		return PackedStringArray(override.split(" ", false))
	var exe_dir := OS.get_executable_path().get_base_dir()
	for server in [exe_dir.path_join("../Resources/server").simplify_path(), exe_dir.path_join("server")]:
		# pythonw on Windows: the server's process must not open a console window
		for python in [server.path_join("python/bin/python3"), server.path_join("python/pythonw.exe")]:
			if FileAccess.file_exists(python):
				if OS.get_name() == "macOS":
					# a downloaded app's files carry the quarantine mark; the player opened the app itself, so its own
					# server may run without macOS asking again (a read-only, translocated copy keeps the mark)
					OS.execute("/usr/bin/xattr", ["-dr", "com.apple.quarantine", server])
				OS.set_environment("PYTHONPATH", server)
				OS.set_environment("HELLWARD_BUILDS", server.path_join("build"))
				OS.set_environment("PYTHONDONTWRITEBYTECODE", "1")
				return PackedStringArray([python, "-m", "hellward.server"])
	var repo := ProjectSettings.globalize_path("res://").path_join("../..").simplify_path()
	for venv in [repo.path_join(".venv/bin/python"), repo.path_join(".venv/Scripts/python.exe")]:
		if FileAccess.file_exists(venv):
			return PackedStringArray([venv, "-m", "hellward.server"])
	return PackedStringArray(["uv", "run", "--project", repo, "python", "-m", "hellward.server"])


func _process(_delta: float) -> void:
	if _listener == null:
		return
	if _peer == null:
		if _listener.is_connection_available():
			_peer = _listener.take_connection()
			_peer.set_no_delay(true)
			_listener.stop()
		elif _pid > 0 and not OS.is_process_running(_pid):
			_fail("the server exited before it connected (code %d)" % OS.get_process_exit_code(_pid))
		return
	pump()


## Read what has arrived and handle every whole line. Called each frame, and by `wait_frames` in a hurry.
func pump() -> void:
	if _peer == null:
		return
	_peer.poll()
	var state := _peer.get_status()
	if state != StreamPeerTCP.STATUS_CONNECTED:
		if error == "":
			_fail("the server closed the connection")
		return
	var n := _peer.get_available_bytes()
	if n > 0:
		var got: Array = _peer.get_partial_data(n)
		if got[0] != OK:
			_fail("the link broke: %s" % error_string(got[0]))
			return
		_buffer.append_array(got[1])
	while true:
		var end := _buffer.find(10)
		if end < 0:
			break
		var line := _buffer.slice(0, end).get_string_from_utf8()
		_buffer = _buffer.slice(end + 1)
		var message = JSON.parse_string(line)
		if typeof(message) != TYPE_DICTIONARY:
			_fail("the server sent something that is not a message: %s" % line.left(200))
			return
		_handle(message)


func _handle(m: Dictionary) -> void:
	match String(m["t"]):
		"hello":
			if int(m["protocol"]) != PROTOCOL or String(m["token"]) != _token:
				_fail("the server speaks protocol %d, this client %d" % [int(m["protocol"]), PROTOCOL])
				return
			send({"t": "hello", "protocol": PROTOCOL})
		"status":
			status.emit(String(m["text"]))
		"ready":
			is_ready = true
			compiled = bool(m["compiled"])
			connected.emit()
		"frame":
			frame.emit(m)
		"reply":
			var p: Pending = _pending.get(int(m["id"]))
			_pending.erase(int(m["id"]))
			if p != null:
				p.done.emit(m)
		"error":
			_fail(String(m["message"]))
		_:
			_fail("unknown message %s" % m["t"])


func send(message: Dictionary) -> void:
	if _peer == null or error != "":
		return
	_peer.put_data((JSON.stringify(message) + "\n").to_utf8_buffer())


## A request; await its `done` for the reply: {"ok": true, "data": ...} or {"ok": false, "why": ...}.
func ask(kind: String, args := {}) -> Pending:
	_next_id += 1
	var message := args.duplicate()
	message["t"] = kind
	message["id"] = _next_id
	var p := Pending.new()
	_pending[_next_id] = p
	send(message)
	return p


## A battle order (build, upgrade, sell, smite, hymn, meteor, orb, gate, call_wave, breach,
## sell_salvage, pause): its frame arrives on `frame`, then the reply says whether it was accepted and why not.
func order(name: String, args := {}) -> Pending:
	var a := args.duplicate()
	a["name"] = name
	return ask("order", a)


func advance(steps: int) -> void:
	send({"t": "advance", "steps": steps})


## Wait for the link: true when the server is ready, false when it failed.
func wait_ready() -> bool:
	start()
	while not is_ready and error == "":
		await get_tree().process_frame
	return is_ready


func _fail(why: String) -> void:
	if error != "":
		return
	error = why
	push_error("hellward server: " + why)
	failed.emit(why)
	for id in _pending:
		(_pending[id] as Pending).done.emit({"ok": false, "why": "The server stopped: " + why})
	_pending.clear()


func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE or what == NOTIFICATION_WM_CLOSE_REQUEST:
		stop()


## End the server: say quit, close the link; the server also ends on its own when the link closes.
func stop() -> void:
	if _peer != null and _peer.get_status() == StreamPeerTCP.STATUS_CONNECTED:
		send({"t": "quit"})
		_peer.disconnect_from_host()
	_peer = null
	for i in 50:   # it closes its worker processes on the way out; a second at most, then it is ended
		if _pid <= 0 or not OS.is_process_running(_pid):
			break
		OS.delay_msec(20)
	if _pid > 0 and OS.is_process_running(_pid):
		OS.kill(_pid)
	_pid = -1
