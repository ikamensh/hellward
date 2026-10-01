class_name Builder
extends Node3D
## The player's hands: hold a tower (1-4 or a slot) and click buildable ground to raise it; click a tower to
## choose it, then U upgrades, S sells, C cleanses. Space summons a wave, F doubles the pace, Esc lets go.

var world: World
var hud: Hud
var rig: CameraRig
var held := ""
var chosen: Tower

var _ghost: Node3D
var _ghost_mat: StandardMaterial3D
var _tile_mark: MeshInstance3D
var _reach_mark: MeshInstance3D
var _hover := Vector2i(-99, -99)


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


func hold(kind: String) -> void:
	choose(null)
	held = kind
	if _ghost:
		_ghost.queue_free()
	_ghost = Models.make("tower_arrow_1" if kind == "arrow" else "tower_" + kind)
	for mi in _ghost.find_children("*", "MeshInstance3D", true, false):
		(mi as MeshInstance3D).material_override = _ghost_mat
		(mi as MeshInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for n in _ghost.find_children("fx_*", "", true, false):
		n.queue_free()
	add_child(_ghost)
	_ghost.visible = false


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
		_show_reach(t.global_position, t.reach(), Color(1.0, 0.8, 0.45, 0.9))
	else:
		_reach_mark.visible = false


func _show_reach(at: Vector3, reach: float, color: Color) -> void:
	_reach_mark.visible = true
	_reach_mark.global_position = Vector3(at.x, 0.08, at.z)
	(_reach_mark.mesh as PlaneMesh).size = Vector2(reach * 2 + 0.6, reach * 2 + 0.6)
	var m := _reach_mark.material_override as ShaderMaterial
	m.set_shader_parameter("radius", reach)
	m.set_shader_parameter("color", color)


## The tile under a point on the screen, from a ray onto the ground plane.
func _tile_at(screen: Vector2) -> Vector2i:
	var origin := rig.cam.project_ray_origin(screen)
	var dir := rig.cam.project_ray_normal(screen)
	if abs(dir.y) < 0.001:
		return Vector2i(-99, -99)
	var t := -origin.y / dir.y
	return world.level.tile_at(origin + dir * t)


func _process(_delta: float) -> void:
	if held == "":
		return
	var tile := _tile_at(get_viewport().get_mouse_position())
	var ok := world.level.buildable(tile) and world.gold >= world.tower_cost(held, 0)
	var at := world.level.tile_pos(tile)
	_ghost.visible = world.level.cell(tile) != "#"
	_ghost.global_position = at
	_ghost_mat.albedo_color = Color(0.5, 1.0, 0.6, 0.35) if ok else Color(1.0, 0.3, 0.25, 0.35)
	_tile_mark.visible = _ghost.visible
	_tile_mark.global_position = at + Vector3(0, 0.06, 0)
	var colour := Color(0.5, 1.0, 0.6, 0.9) if ok else Color(1.0, 0.35, 0.3, 0.9)
	(_tile_mark.material_override as ShaderMaterial).set_shader_parameter("color", colour)
	_show_reach(at, float(world.data["towers"][held]["levels"][0]["range"]) * Level.TILE, colour)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_LEFT:
			_click(mb.position)
		elif mb.button_index == MOUSE_BUTTON_RIGHT:
			let_go()
			choose(null)
	elif event is InputEventKey and event.pressed and not event.echo:
		var k := (event as InputEventKey).keycode
		match k:
			KEY_1, KEY_2, KEY_3, KEY_4:
				hold(Hud.SLOTS[k - KEY_1])
			KEY_U: _order("upgrade")
			KEY_S: _order("sell")
			KEY_C: _order("cleanse")
			KEY_SPACE: _order("wave")
			KEY_F: _order("pace")
			KEY_ESCAPE:
				let_go()
				choose(null)


func _click(screen: Vector2) -> void:
	var tile := _tile_at(screen)
	if held != "":
		var t := world.build(held, tile)
		if t and not Input.is_key_pressed(KEY_SHIFT):
			let_go()
		return
	for t in world.towers:
		if t.tile == tile and not t.removed:
			choose(t)
			return
	choose(null)


func _order(name: String) -> void:
	match name:
		"wave": world.call_wave()
		"pace":
			Engine.time_scale = 1.0 if Engine.time_scale > 1.0 else 2.0
			hud.set_pace(Engine.time_scale > 1.0)
		"upgrade":
			if chosen:
				world.upgrade(chosen)
				choose(chosen)
		"sell":
			if chosen:
				world.sell(chosen)
				choose(null)
		"cleanse":
			if chosen:
				world.cleanse(chosen)
				hud.select(chosen)
