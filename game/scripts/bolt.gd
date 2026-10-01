class_name Bolt
extends Node3D
## A missile homing on a monster: a ballista bolt, a firebolt or a frost shard, drawing a streak of light behind
## it. When it arrives it calls `on_hit` with the monster (null if the monster died on the way) and the point it
## reached; its streak then shrinks into that point before the bolt is freed.

var target: Monster
var speed := 20.0
var on_hit: Callable
var _aim := Vector3.ZERO
var _head: Node3D                    # the bolt itself, hidden on arrival
var _sheds: Array[GPUParticles3D] = []
var _im: ImmediateMesh
var _hist: Array = []                # [position, time], newest first: the streak's path
var _clock := 0.0
var _arrived := false
var _arrived_at := 0.0
var _linger := 0.0
var _streak_time := 0.1              # seconds of flight the streak spans
var _streak_width := 0.05            # its half-width at the head, metres
var _streak_color := Color.WHITE


static func launch(world: World, look: String, from: Vector3, at: Monster, metres_per_s: float, hit: Callable) -> Bolt:
	var b := Bolt.new()
	b.target = at
	b.speed = metres_per_s
	b.on_hit = hit
	b._aim = at.chest()
	world.add_child(b)
	b.global_position = from
	b._hist = [[from, 0.0]]
	b._head = Node3D.new()
	b.add_child(b._head)
	match look:
		"arrow": b._arrow()
		"fire": b._firebolt()
		"frost": b._shard()
	b._streak()
	b.look_at(b._aim, Vector3.UP)
	return b


func _process(delta: float) -> void:
	_clock += delta
	if _arrived:
		_hist[0][1] = _clock
		if _clock - _arrived_at > _linger:
			queue_free()
			return
	else:
		_fly(delta)
		_hist.push_front([global_position, _clock])
	_draw_streak()


func _fly(delta: float) -> void:
	var alive := is_instance_valid(target) and target.alive()
	if alive:
		_aim = target.chest()
	var to := _aim - global_position
	var step := speed * delta
	if to.length() <= step:
		global_position = _aim
		_arrive()
		on_hit.call(target if alive else null, global_position)
		return
	global_position += to.normalized() * step
	if to.length() > 0.05:
		look_at(_aim, Vector3.UP)


## The bolt is gone; its streak shrinks into the point it reached and its shed specks fade, then it is freed.
func _arrive() -> void:
	_arrived = true
	_arrived_at = _clock
	_head.visible = false
	_linger = _streak_time
	for p in _sheds:
		p.emitting = false
		_linger = maxf(_linger, p.lifetime)


## The streak: a ribbon through the last `_streak_time` seconds of flight, widest and brightest at the head,
## thinning and fading to the tail. After arrival the head stays put and the tail catches up with it.
func _draw_streak() -> void:
	var pts := PackedVector3Array()
	var ages := PackedFloat32Array()
	for i in _hist.size():
		var age := _clock - float(_hist[i][1])
		if age <= _streak_time:
			pts.append(_hist[i][0])
			ages.append(age)
			continue
		if i > 0:   # the tail ends exactly `_streak_time` back, between this point and the one before
			var prev_age := _clock - float(_hist[i - 1][1])
			var k := (_streak_time - prev_age) / maxf(age - prev_age, 0.0001)
			pts.append((_hist[i - 1][0] as Vector3).lerp(_hist[i][0], k))
			ages.append(_streak_time)
		_hist.resize(i + 1)
		break
	_im.clear_surfaces()
	# a missile stopped at its target has no length left to draw
	if pts.size() < 2 or pts[0].distance_to(pts[pts.size() - 1]) < 0.01:
		return
	var eye := get_viewport().get_camera_3d().global_position
	var widths := PackedFloat32Array()
	var colors := PackedColorArray()
	for i in pts.size():
		var t := ages[i] / _streak_time
		widths.append(_streak_width * (1.0 - 0.7 * t))
		colors.append(Color(_streak_color, _streak_color.a * pow(1.0 - t, 1.5)))
	_im.surface_begin(Mesh.PRIMITIVE_TRIANGLES)
	Vfx.ribbon(_im, pts, widths, colors, eye)
	_im.surface_end()


func _streak() -> void:
	var mi := MeshInstance3D.new()
	_im = ImmediateMesh.new()
	mi.mesh = _im
	mi.material_override = Vfx.ribbon_material(1.6)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.top_level = true
	add_child(mi)
	mi.global_transform = Transform3D.IDENTITY


func _glow(color: Color, size: float) -> MeshInstance3D:
	var g := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2(size, size)
	g.mesh = q
	var m := Fx.billboard(Fx.dot_texture(), true)
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.vertex_color_use_as_albedo = false
	m.albedo_color = color
	g.material_override = m
	g.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_head.add_child(g)
	return g


func _arrow() -> void:
	_head.scale = Vector3.ONE * 1.6
	var shaft := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.035
	cm.bottom_radius = 0.035
	cm.height = 1.1
	shaft.mesh = cm
	shaft.rotation_degrees.x = 90
	shaft.material_override = Mats.named("planks")
	_head.add_child(shaft)
	var tip := MeshInstance3D.new()
	var tm := CylinderMesh.new()
	tm.top_radius = 0.0
	tm.bottom_radius = 0.08
	tm.height = 0.22
	tip.mesh = tm
	tip.rotation_degrees.x = -90
	tip.position = Vector3(0, 0, -0.62)
	tip.material_override = Mats.glow(Color(1.0, 0.75, 0.45), 4.0, Color(0.3, 0.25, 0.2))
	_head.add_child(tip)
	_glow(Color(1.6, 1.1, 0.6), 0.35).position = Vector3(0, 0, -0.62)
	_streak_time = 0.1
	_streak_width = 0.07
	_streak_color = Color(1.0, 0.82, 0.6, 0.8)


func _firebolt() -> void:
	var core := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 0.13
	sm.height = 0.26
	core.mesh = sm
	core.material_override = Mats.glow(Color(1.0, 0.8, 0.45), 12.0, Color(1.0, 0.9, 0.7))
	core.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_head.add_child(core)
	_glow(Color(2.4, 1.0, 0.3), 0.9)
	_glow(Color(0.9, 0.25, 0.05, 0.8), 1.8)
	var cinders := Fx.shed(Color(1.0, 0.45, 0.1), 40, 0.12, 0.45, -0.5)
	add_child(cinders)
	_sheds.append(cinders)
	var light := OmniLight3D.new()
	light.light_color = Color(1.0, 0.5, 0.15)
	light.light_energy = 3.0
	light.omni_range = 6.0
	_head.add_child(light)
	_streak_time = 0.22
	_streak_width = 0.22
	_streak_color = Color(1.0, 0.5, 0.15, 0.9)


func _shard() -> void:
	var core := MeshInstance3D.new()
	var pm := PrismMesh.new()
	pm.size = Vector3(0.18, 0.7, 0.18)
	core.mesh = pm
	core.rotation_degrees.x = -90
	core.material_override = Mats.glow(Color(0.5, 0.85, 1.0), 6.0, Color(0.6, 0.85, 1.0))
	_head.add_child(core)
	_glow(Color(0.6, 1.0, 1.6), 0.7)
	var glints := Fx.shed(Color(0.6, 0.85, 1.0), 36, 0.07, 0.5, 1.5)
	add_child(glints)
	_sheds.append(glints)
	var light := OmniLight3D.new()
	light.light_color = Color(0.45, 0.75, 1.0)
	light.light_energy = 1.5
	light.omni_range = 4.0
	_head.add_child(light)
	_streak_time = 0.2
	_streak_width = 0.11
	_streak_color = Color(0.55, 0.85, 1.0, 0.9)
