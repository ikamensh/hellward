class_name Builder
extends Node3D
## The player's hands: hold a tower (1-8 or a slot) and click bare ground to raise it; click a tower to choose it,
## then U upgrades, Delete (or Backspace) sells, M teaches the next owned strategy. Z, X and C pick Smite,
## Meteor and Frozen Orb, aimed with a click; R sings Battle Hymn over the chosen tower, or with none chosen
## picks it to aim at one. Hold the gate
## and click an arch to ward it. Space summons a wave, F doubles the pace, V sells a salvage drop, H hides the
## HUD, G skips a surely clean wave for its bonus, Esc lets go. WASD, Q and E are the camera's (CameraRig).
## Keys are read by their place on the keyboard, as
## the camera reads its own (the labels name a QWERTY keyboard's letters): any layout, Cyrillic too, gives the
## same keys. The monster under the mouse shows its plate (Hud.hover).
## Everything is an order to the server; the ghost and the marks are only this side's guesses.

signal menu                          # Esc with nothing to let go of

const SPELL_KEYS := {KEY_Z: "smite", KEY_X: "meteor", KEY_C: "orb", KEY_R: "hymn"}
const HOVER := 46.0                  # pixels from a monster's body within which the mouse is on it

var world: World
var hud: Hud
var rig: CameraRig
var held := ""                       # a tower kind, "gate", or "spell:<key>"
var chosen: Tower

var _ghost: Node3D
var _ghost_mat: StandardMaterial3D
var _tile_mark: MeshInstance3D
var _reach_mark: MeshInstance3D
var _mouse := Vector2(-1, -1)        # the mouse in the viewport's pixels, as its last motion put it


func setup(w: World, h: Hud, r: CameraRig) -> void:
	world = w
	hud = h
	rig = r
	hud.slot_pressed.connect(hold)
	hud.order.connect(_order)
	_tile_mark = _marker(true)
	_reach_mark = _marker(false)
	_ghost_mat = StandardMaterial3D.new()
	_ghost_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_ghost_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_ghost_mat.albedo_color = Color(0.5, 1.0, 0.6, 0.35)
	world.towers_changed.connect(_forget_gone)


func _marker(square: bool) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(2, 2) if square else Vector2(1, 1)
	mi.mesh = pm
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/ring.gdshader")
	m.set_shader_parameter("square", square)
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.visible = false
	add_child(mi)
	return mi


## Hold a tower kind, the gate, or a spell ("spell:meteor") for the next click; holding it again lets go.
func hold(what: String) -> void:
	if world.demo:
		return
	if what.begins_with("spell:"):
		_spell(what.substr(6))
		return
	if held == what:
		let_go()
		return
	if what != "gate" and not world.offers(what):
		Sfx.play("refuse")
		world.refused.emit("Not offered in %s." % world.start["location"]["called"])
		return
	choose(null)
	let_go()
	held = what
	if what == "gate":
		return
	_ghost = Models.make(Tower.model_name(what, 0))
	for mi in _ghost.find_children("*", "MeshInstance3D", true, false):
		(mi as MeshInstance3D).material_override = _ghost_mat
		(mi as MeshInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for n in _ghost.find_children("fx_*", "", true, false):
		n.queue_free()
	add_child(_ghost)
	_ghost.visible = false
	Sfx.play("click")


func let_go() -> void:
	held = ""
	if _ghost:
		_ghost.queue_free()
		_ghost = null
	_tile_mark.visible = false
	_reach_mark.visible = false


func choose(t: Tower) -> void:
	chosen = t
	hud.select(t)
	if t:
		_show_reach(t.global_position, t.reach * Level.TILE, Color(1.0, 0.8, 0.45, 0.9))
	else:
		_reach_mark.visible = false


func _forget_gone() -> void:
	if chosen and (not is_instance_valid(chosen) or chosen.removed):
		choose(null)


func _show_reach(at: Vector3, reach: float, color: Color) -> void:
	_reach_mark.visible = true
	_reach_mark.global_position = Vector3(at.x, 0.08, at.z)
	(_reach_mark.mesh as PlaneMesh).size = Vector2(reach * 2 + 0.6, reach * 2 + 0.6)
	var m := _reach_mark.material_override as ShaderMaterial
	m.set_shader_parameter("radius", reach)
	m.set_shader_parameter("color", color)


## The point on the ground under a point on the screen.
func _ground_at(screen: Vector2) -> Vector3:
	var origin := rig.cam.project_ray_origin(screen)
	var dir := rig.cam.project_ray_normal(screen)
	if abs(dir.y) < 0.001:
		return Vector3(-999, 0, -999)
	return origin + dir * (-origin.y / dir.y)


func _process(_delta: float) -> void:
	var p := _ground_at(_mouse)
	var tile := world.level.tile_at(p)
	hud.hover(null if held != "" and not held.begins_with("spell:") else monster_at(_mouse), _mouse)
	if held == "" or held == "gate":
		_tile_mark.visible = held == "gate" and _arch_at(tile) >= 0
		if _tile_mark.visible:
			_tile_mark.global_position = world.level.tile_pos(tile) + Vector3(0, 0.06, 0)
		_hover(tile)
		return
	if held.begins_with("spell:"):
		var spell: Dictionary = world.start["spells"][held.substr(6)]
		if String(spell["aim"]) == "tower":   # the tower under the mouse lights up, its tile marked
			var t := world.tower_at(tile)
			_tile_mark.visible = t != null
			_reach_mark.visible = false
			if t:
				_tile_mark.global_position = world.level.tile_pos(tile) + Vector3(0, 0.06, 0)
				(_tile_mark.material_override as ShaderMaterial).set_shader_parameter("color", Color(Hud.SPELL_TONES[held.substr(6)], 0.95))
			return
		var radius: float = max(float(spell["radius"]), 0.6) * Level.TILE
		_show_reach(Vector3(p.x, 0, p.z), radius, Color(0.6, 0.8, 1.0, 0.9))
		return
	var ok := world.level.buildable(tile) and world.tower_at(tile) == null and world.gold >= world.tower_cost(held)
	var at := world.level.tile_pos(tile)
	_ghost.visible = world.level.cell(tile) != "#"
	_ghost.global_position = at
	_ghost_mat.albedo_color = Color(0.5, 1.0, 0.6, 0.35) if ok else Color(1.0, 0.3, 0.25, 0.35)
	_tile_mark.visible = _ghost.visible
	_tile_mark.global_position = at + Vector3(0, 0.06, 0)
	var colour := Color(0.5, 1.0, 0.6, 0.9) if ok else Color(1.0, 0.35, 0.3, 0.9)
	(_tile_mark.material_override as ShaderMaterial).set_shader_parameter("color", colour)
	_show_reach(at, float(world.tower_table(held)["levels"][0]["range"]) * Level.TILE, colour)


## With nothing held, the tower under the mouse shows its reach faintly; the chosen tower's stays bright.
func _hover(tile: Vector2i) -> void:
	if chosen and is_instance_valid(chosen) and not chosen.removed:
		return
	var t := world.tower_at(tile)
	_reach_mark.visible = t != null
	if t:
		_show_reach(t.global_position, t.reach * Level.TILE, Color(1.0, 0.8, 0.45, 0.5))


## The living monster whose body is nearest `screen` (viewport pixels), within HOVER of it; or null.
func monster_at(screen: Vector2) -> Monster:
	var best: Monster = null
	var nearest := HOVER
	for m in world.monsters.values():
		if not m.alive() or not rig.cam.is_position_in_frustum(m.chest()):
			continue
		var feet := rig.cam.unproject_position(m.global_position)
		var head := rig.cam.unproject_position(m.head())
		var d := Geometry2D.get_closest_point_to_segment(screen, feet, head).distance_to(screen)
		if d < nearest:
			best = m
			nearest = d
	return best


func _input(event: InputEvent) -> void:
	if event is InputEventMouse:
		_mouse = (event as InputEventMouse).position


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_LEFT:
			_click(mb.position, mb.shift_pressed)
		elif mb.button_index == MOUSE_BUTTON_RIGHT:
			let_go()
			choose(null)
	elif event is InputEventKey and event.pressed and not event.echo:
		var key := event as InputEventKey
		if key.meta_pressed or key.ctrl_pressed:
			return   # the system's shortcuts (Cmd-Q, Cmd-W), not orders
		var k := key.physical_keycode
		if k >= KEY_1 and k <= KEY_8:
			var slots: Array = hud.slots()
			if k - KEY_1 < slots.size():
				hold(slots[k - KEY_1])
			return
		if SPELL_KEYS.has(k):
			hold("spell:" + SPELL_KEYS[k])
			return
		match k:
			KEY_U: _order("upgrade")
			KEY_DELETE, KEY_BACKSPACE: _order("sell")
			KEY_V: _order("salvage")
			KEY_G: _order("skip")
			KEY_SPACE: _order("wave")
			KEY_F: _order("pace")
			KEY_H: hud.toggle()
			KEY_M: hud.cycle_mode()
			KEY_ESCAPE:
				if held != "" or chosen:
					let_go()
					choose(null)
				else:
					menu.emit()


func _click(screen: Vector2, shift: bool) -> void:
	if world.demo:
		return
	var p := _ground_at(screen)
	var tile := world.level.tile_at(p)
	if held.begins_with("spell:"):
		_cast(held.substr(6), p, shift)
		return
	if held == "gate":
		var arch := _arch_at(tile)
		if arch >= 0 and await world.order("gate", {"door": arch}):
			let_go()
		return
	if held != "":
		var kind := held
		if await world.order("build", {"kind": kind, "tile": [tile.x, tile.y]}) and not shift:
			let_go()
		return
	choose(world.tower_at(tile))
	if chosen:
		Sfx.play("click")


func _arch_at(tile: Vector2i) -> int:
	for a in world.level.arches:
		if a[1] == tile:
			return int(a[0])
	return -1


## Z, X, C, R: pick a spell to aim. A spell aimed at a tower (Battle Hymn) falls on the chosen tower at once.
func _spell(key: String) -> void:
	if not world.offers(key):
		Sfx.play("refuse")
		world.refused.emit("%s is not yet yours." % key.capitalize())
		return
	if String(world.start["spells"][key]["aim"]) == "tower" and chosen and is_instance_valid(chosen) and not chosen.removed:
		await world.order(key, {"tower": chosen.id})
		return
	choose(null)
	let_go()
	held = "spell:" + key
	Sfx.play("click")


func _cast(key: String, p: Vector3, shift: bool) -> void:
	var ok := false
	var spell: Dictionary = world.start["spells"][key]
	if String(spell["aim"]) == "tower":
		var t := world.tower_at(world.level.tile_at(p))
		if t == null:
			Sfx.play("refuse")
			world.refused.emit("%s falls on a tower: click on one." % spell["name"])
			return
		ok = await world.order(key, {"tower": t.id})
	elif key == "smite":
		var best: Monster = null
		for m in world.monsters.values():
			if m.alive() and Vector2(m.global_position.x - p.x, m.global_position.z - p.z).length() < Level.TILE * 1.2 \
					and (best == null or m.global_position.distance_to(p) < best.global_position.distance_to(p)):
				best = m
		if best == null:
			Sfx.play("refuse")
			world.refused.emit("Smite strikes a monster: click on one.")
			return
		ok = await world.order("smite", {"monster": best.id})
	else:
		ok = await world.order(key, {"x": p.x / Level.TILE, "y": p.z / Level.TILE})
	if ok and not shift:
		let_go()


func _order(name: String) -> void:
	match name:
		"wave": world.order("call_wave")
		"skip": world.order("skip_grind")
		"pace":
			Engine.time_scale = 1.0 if Engine.time_scale > 1.0 else 2.0
			hud.set_pace(Engine.time_scale > 1.0)
		"salvage": world.order("sell_salvage")
		"upgrade":
			if chosen:
				await world.order("upgrade", {"tower": chosen.id})
				choose(chosen if is_instance_valid(chosen) and not chosen.removed else null)
		"sell":
			if chosen:
				var t := chosen
				if await world.order("sell", {"tower": t.id}):
					choose(null)
		_:
			if name.begins_with("breach:"):
				world.order("breach", {"mode": name.substr(7)})
			elif name.begins_with("spell:"):
				hold(name)
			elif name.begins_with("mode:"):
				if chosen:
					world.order("set_mode", {"tower": chosen.id, "mode": name.substr(5)})
			elif name.begins_with("summon:"):
				world.order("summon", {"stake": int(name.substr(7))})
