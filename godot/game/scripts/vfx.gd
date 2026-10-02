class_name Vfx
extends RefCounted
## Battle effects: impacts, explosions, lightning, the leaders' curses, blood, dust, gold, health bars.
## Each makes its nodes under `parent` and frees them when they are done.

const BOLT_HALO := Color(0.3, 0.45, 1.0, 0.55)    # lightning: the blue glow round a strike
const BOLT_CORE := Color(0.85, 0.92, 1.0, 1.0)    # and its white-hot thread
const BEAM_HEIGHT := 14.0                         # Cleanse's pillar of light, metres


static func _one_shot(parent: Node, node: Node3D, at: Vector3, life: float) -> Node3D:
	parent.add_child(node)
	node.global_position = at
	parent.get_tree().create_timer(life).timeout.connect(node.queue_free)
	return node


static func _flash_light(parent: Node, at: Vector3, color: Color, energy: float, reach: float, life: float) -> void:
	var l := OmniLight3D.new()
	l.light_color = color
	l.light_energy = energy
	l.omni_range = reach
	_one_shot(parent, l, at, life)
	l.create_tween().tween_property(l, "light_energy", 0.0, life)


static func impact(parent: Node, at: Vector3, color: Color, amount: int) -> void:
	var s := Fx.sparks(color, amount, 3.0)
	parent.add_child(s)
	s.global_position = at


static func burst(parent: Node, at: Vector3, color: Color, amount: int) -> void:
	var s := Fx.sparks(color, amount, 6.0)
	parent.add_child(s)
	s.global_position = at
	_flash_light(parent, at, color, 4.0, 8.0, 0.5)


## A firebolt bursting: a white-hot flash, a ball of flame thrown out and stopped short, smoke, sparks, light.
static func explosion(parent: Node, at: Vector3, color: Color, ground := true) -> void:
	var flash := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2.ONE
	flash.mesh = q
	var m := Fx.billboard(Fx.dot_texture(), true)
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.billboard_keep_scale = true
	m.vertex_color_use_as_albedo = false
	m.albedo_color = Color(4.0, 2.6, 1.4)
	flash.material_override = m
	flash.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_one_shot(parent, flash, at, 0.3)
	flash.scale = Vector3.ONE * 0.4
	var tw := flash.create_tween()
	tw.tween_property(flash, "scale", Vector3.ONE * 2.2, 0.25).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.parallel().tween_property(m, "albedo_color", Color(0.6, 0.2, 0.05, 0.0), 0.25).set_ease(Tween.EASE_IN)
	var ball := Fx.fireball(1.0)
	parent.add_child(ball)
	ball.global_position = at
	var smoke := Fx.puff(1.0)
	parent.add_child(smoke)
	smoke.global_position = at + Vector3(0, 0.3, 0)
	var s := Fx.sparks(color, 26, 7.0)
	parent.add_child(s)
	s.global_position = at
	_flash_light(parent, at, color, 8.0, 9.0, 0.4)
	if ground:
		scorch(parent, at, 1.2)


static func frost_burst(parent: Node, at: Vector3) -> void:
	impact(parent, at, Color(0.5, 0.8, 1.0), 26)
	_flash_light(parent, at, Color(0.45, 0.75, 1.0), 3.0, 6.0, 0.3)


static func dust(parent: Node, at: Vector3, size: float, color := Color(0.35, 0.3, 0.25)) -> void:
	var p := GPUParticles3D.new()
	p.amount = 24
	p.lifetime = 1.6
	p.one_shot = true
	p.explosiveness = 0.9
	p.local_coords = false
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_RING
	pm.emission_ring_axis = Vector3.UP
	pm.emission_ring_radius = size
	pm.emission_ring_inner_radius = size * 0.6
	pm.emission_ring_height = 0.2
	pm.direction = Vector3.UP
	pm.spread = 60.0
	pm.initial_velocity_min = 1.0
	pm.initial_velocity_max = 2.5
	pm.gravity = Vector3(0, -0.5, 0)
	pm.damping_min = 1.0
	pm.damping_max = 2.0
	pm.scale_curve = Fx.curve([[0.0, 0.4], [1.0, 1.0]])
	pm.anim_offset_max = 1.0
	pm.color_ramp = Fx.ramp([[0.0, Color(color, 0.0)], [0.15, Color(color, 0.6)], [1.0, Color(color * 0.88, 0.0)]])
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(1.6, 1.6)
	q.material = Fx.billboard(load("res://assets/fx/smoke_sheet.png"), false, true, 4)
	p.draw_pass_1 = q
	p.emitting = true
	_one_shot(parent, p, at + Vector3(0, 0.3, 0), 2.0)


## The material ribbons are drawn with: additive light, vertex-coloured, soft across their width (the dot
## texture's middle row), `energy` lifting them into glow.
static func ribbon_material(energy: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
	m.vertex_color_use_as_albedo = true
	m.albedo_texture = Fx.dot_texture()
	m.albedo_color = Color(energy, energy, energy)
	m.disable_fog = true
	return m


## A camera-facing ribbon through `pts` into an ImmediateMesh surface being built (triangles): each point has
## its own half-width and colour, so a ribbon can taper and fade along its length.
static func ribbon(im: ImmediateMesh, pts: PackedVector3Array, widths: PackedFloat32Array, colors: PackedColorArray, eye: Vector3) -> void:
	var n := pts.size()
	var sides := PackedVector3Array()
	sides.resize(n)
	for i in n:
		var along := pts[mini(i + 1, n - 1)] - pts[maxi(i - 1, 0)]
		sides[i] = along.cross(eye - pts[i]).normalized() * widths[i]
	for i in n - 1:
		for v in [[i, -1.0], [i, 1.0], [i + 1, 1.0], [i, -1.0], [i + 1, 1.0], [i + 1, -1.0]]:
			var k: int = v[0]
			im.surface_set_color(colors[k])
			im.surface_set_uv(Vector2(0.5 + 0.5 * v[1], 0.5))
			im.surface_add_vertex(pts[k] + sides[k] * v[1])


## A round glow `size` metres across at `at`, facing the camera, into the same kind of surface.
static func flare(im: ImmediateMesh, at: Vector3, size: float, color: Color, cam: Camera3D) -> void:
	var r := cam.global_basis.x * size * 0.5
	var u := cam.global_basis.y * size * 0.5
	for c in [[-1, -1], [1, -1], [1, 1], [-1, -1], [1, 1], [-1, 1]]:
		im.surface_set_color(color)
		im.surface_set_uv(Vector2(0.5 + 0.5 * c[0], 0.5 - 0.5 * c[1]))
		im.surface_add_vertex(at + r * c[0] + u * c[1])


## A jagged bolt of lightning through `points`, striking and re-striking for a moment: a blue halo round a
## white-hot core, forking as it goes.
static func lightning(parent: Node, points: Array) -> void:
	var mi := MeshInstance3D.new()
	var im := ImmediateMesh.new()
	mi.mesh = im
	mi.material_override = ribbon_material(1.3)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.top_level = true
	parent.add_child(mi)
	mi.global_transform = Transform3D.IDENTITY
	var cam := parent.get_viewport().get_camera_3d()
	var rng := RandomNumberGenerator.new()
	rng.randomize()
	_draw_bolt(im, points, cam, rng, 1.0)
	for i in range(1, points.size()):
		_flash_light(parent, points[i], Color(0.5, 0.65, 1.0), 6.0, 7.0, 0.3)
		impact(parent, points[i], Color(0.6, 0.75, 1.0), 14)
	var tw := mi.create_tween()
	for k in [0.75, 1.0, 0.55, 0.3]:
		tw.tween_callback(func(): _draw_bolt(im, points, cam, rng, k)).set_delay(0.055)
	tw.tween_callback(mi.queue_free).set_delay(0.06)


static func _draw_bolt(im: ImmediateMesh, points: Array, cam: Camera3D, rng: RandomNumberGenerator, strength: float) -> void:
	var eye := cam.global_position
	im.clear_surfaces()
	im.surface_begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in range(points.size() - 1):
		var path := _jagged(points[i], points[i + 1], rng)
		_bolt_leg(im, path, eye, 1.0, strength)
		for f in rng.randi_range(1, 3):
			var j := rng.randi_range(1, path.size() - 2)
			var dir := (path[j + 1] - path[j - 1]).normalized()
			var off := Vector3(rng.randf_range(-1, 1), rng.randf_range(-0.6, 1), rng.randf_range(-1, 1))
			var end := path[j] + (dir + off).normalized() * rng.randf_range(0.5, 1.4)
			_bolt_leg(im, _jagged(path[j], end, rng), eye, 0.5, strength * 0.8, true)
		flare(im, points[i + 1], 1.3, Color(BOLT_HALO, 0.5 * strength), cam)
	flare(im, points[0], 1.0, Color(BOLT_HALO, 0.6 * strength), cam)
	im.surface_end()


## One leg drawn twice: the wide blue halo, then the thin white core over it. A fork tapers to its tip.
static func _bolt_leg(im: ImmediateMesh, path: PackedVector3Array, eye: Vector3, width: float, strength: float, fork := false) -> void:
	var n := path.size()
	for pass_ in [[0.22, BOLT_HALO], [0.04, BOLT_CORE]]:
		var widths := PackedFloat32Array()
		var colors := PackedColorArray()
		var c: Color = pass_[1]
		for i in n:
			var t := float(i) / (n - 1)
			var taper := 1.0 - t * 0.85 if fork else 1.0
			widths.append(float(pass_[0]) * width * taper)
			colors.append(Color(c, c.a * strength * (1.0 - t * 0.6 if fork else 1.0)))
		ribbon(im, path, widths, colors, eye)


## A crooked line from `a` to `b` by midpoint displacement: each halving bends the middle less.
static func _jagged(a: Vector3, b: Vector3, rng: RandomNumberGenerator) -> PackedVector3Array:
	var pts := PackedVector3Array([a, b])
	var sway := a.distance_to(b) * 0.2
	while (pts.size() < 3 or pts[0].distance_to(pts[1]) > 0.25) and pts.size() < 64:   # forks need an inner point
		var next := PackedVector3Array()
		for i in pts.size() - 1:
			next.append(pts[i])
			var jolt := Vector3(rng.randf_range(-1, 1), rng.randf_range(-1, 1), rng.randf_range(-1, 1))
			next.append((pts[i] + pts[i + 1]) * 0.5 + jolt * sway)
		next.append(pts[pts.size() - 1])
		pts = next
		sway *= 0.6
	return pts


## The leader's chant: a violet beam from its staff to the tower, pulsing, until the curse lands or breaks.
static func curse_beam(parent: Node, from: Node3D, to: Node3D) -> Node3D:
	var beam := CurseBeam.new()
	beam.from = from
	beam.to = to
	parent.add_child(beam)
	return beam


## A rune circle growing at a tower's foot for `seconds`: where the curse will fall. A short projection box and
## a normal fade keep it on the ground, off the tower and the monsters standing in it.
static func rune_circle(tower: Node3D, radius: float, seconds: float) -> Node3D:
	var d := _rune_decal(1.2)
	d.size = Vector3(0.1, 1.6, 0.1)
	tower.add_child(d)
	var tw := d.create_tween()
	tw.tween_property(d, "size", Vector3(radius * 2.0, 1.6, radius * 2.0), seconds).set_trans(Tween.TRANS_QUAD)
	tw.parallel().tween_property(d, "rotation:y", PI * 0.5, seconds)
	tw.tween_property(d, "modulate:a", 0.0, 0.4)
	tw.tween_callback(d.queue_free)
	return d


## A rune circle growing on the ground at `at` for `seconds`: where a chanted curse will fall.
static func rune_circle_at(parent: Node, at: Vector3, radius: float, seconds: float) -> Node3D:
	var root := Node3D.new()
	parent.add_child(root)
	root.global_position = at
	var d := rune_circle(root, radius, seconds)
	d.tree_exited.connect(root.queue_free)
	return root


## A meteor called down: a fireball falling from high over `at`, landing after `delay` seconds.
static func meteor(parent: Node, at: Vector3, delay: float) -> void:
	var rock := Fx.fireball(1.4)
	parent.add_child(rock)
	var sky := at + Vector3(-6.0, 34.0, 4.0)
	rock.global_position = sky
	var light := Fx.fire_light(6.0, 14.0)
	rock.add_child(light)
	var tw := rock.create_tween()
	tw.tween_property(rock, "global_position", at + Vector3(0, 0.8, 0), delay).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tw.tween_callback(rock.queue_free)
	rune_circle_at(parent, at, 2.8, delay)


## A cursed tower's lasting mark: a dim rune circle turning at its foot and violet light.
static func curse_mark(tower: Node3D) -> Node3D:
	var root := Node3D.new()
	tower.add_child(root)
	var d := _rune_decal(0.7)
	d.size = Vector3(2.6, 1.6, 2.6)
	root.add_child(d)
	root.create_tween().set_loops().tween_property(d, "rotation:y", TAU, 12.0).from(0.0)
	var l := OmniLight3D.new()
	l.light_color = Color(0.6, 0.2, 1.0)
	l.light_energy = 2.0
	l.omni_range = 5.0
	l.position = Vector3(0, 2.0, 0)
	root.add_child(l)
	return root


static func _rune_decal(glow: float) -> Decal:
	var d := Decal.new()
	d.texture_albedo = load("res://assets/fx/rune_circle.png")
	d.texture_emission = load("res://assets/fx/rune_circle.png")
	d.emission_energy = glow
	d.normal_fade = 0.5
	d.cull_mask = 1
	d.position = Vector3(0, 0.3, 0)
	return d


## Cleanse: a pillar of golden light slams down, holds, and thins away.
static func holy(parent: Node, at: Vector3) -> void:
	burst(parent, at + Vector3(0, 1.5, 0), Color(1.0, 0.85, 0.5), 60)
	var col := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 1.0
	cm.bottom_radius = 1.0
	cm.height = BEAM_HEIGHT
	cm.radial_segments = 32
	cm.rings = 1
	cm.cap_top = false
	cm.cap_bottom = false
	col.mesh = cm
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/beam.gdshader")
	m.set_shader_parameter("height", BEAM_HEIGHT)
	col.material_override = m
	col.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_one_shot(parent, col, at + Vector3(0, BEAM_HEIGHT * 0.5, 0), 1.4)
	col.scale = Vector3(0.15, 1.0, 0.15)
	var tw := col.create_tween()
	tw.tween_property(col, "scale", Vector3(1.1, 1.0, 1.1), 0.18).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.tween_interval(0.35)
	tw.tween_property(col, "scale", Vector3(0.05, 1.0, 0.05), 0.8).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tw.parallel().tween_method(func(v: float): m.set_shader_parameter("fade", v), 1.0, 0.0, 0.8)
	_flash_light(parent, at + Vector3(0, 2.5, 0), Color(1.0, 0.85, 0.55), 6.0, 10.0, 1.2)


## A leader pondering: three violet motes circling over its head.
static func ponder(m: Node3D) -> void:
	var root := Node3D.new()
	m.add_child(root)
	root.position = Vector3(0, m.height + 0.6, 0)
	for i in 3:
		var dot := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 0.16
		sm.height = 0.32
		dot.mesh = sm
		dot.material_override = Mats.glow(Color(0.7, 0.3, 1.0), 6.0)
		dot.position = Vector3(cos(i * TAU / 3) * 0.5, 0, sin(i * TAU / 3) * 0.5)
		root.add_child(dot)
	var tw := root.create_tween()
	tw.tween_property(root, "rotation:y", TAU * 1.5, 1.1)
	tw.tween_callback(root.queue_free)


static func blood(parent: Node, at: Vector3, size: float, tint := Color.WHITE) -> void:
	var d := Decal.new()
	d.texture_albedo = load("res://assets/fx/blood_decal.png")
	d.modulate = tint
	d.size = Vector3(size * 2.0, 0.6, size * 2.0)
	d.normal_fade = 0.5
	d.cull_mask = 1
	d.rotation.y = randf() * TAU
	parent.add_child(d)
	d.global_position = at + Vector3(0, 0.1, 0)
	var tw := d.create_tween()
	tw.tween_interval(12.0)
	tw.tween_property(d, "modulate:a", 0.0, 4.0)
	tw.tween_callback(d.queue_free)


static func scorch(parent: Node, at: Vector3, size: float) -> void:
	var d := Decal.new()
	d.texture_albedo = load("res://assets/fx/scorch_decal.png")
	d.texture_orm = load("res://assets/fx/scorch_orm.png")
	d.texture_emission = load("res://assets/fx/scorch_glow.png")
	d.emission_energy = 4.0
	d.size = Vector3(size * 2.0, 0.8, size * 2.0)
	d.normal_fade = 0.5
	d.cull_mask = 1
	d.rotation.y = randf() * TAU
	parent.add_child(d)
	d.global_position = Vector3(at.x, 0.3, at.z)
	d.create_tween().tween_property(d, "emission_energy", 0.0, 2.5).set_ease(Tween.EASE_IN)   # the embers cool
	var tw := d.create_tween()
	tw.tween_interval(8.0)
	tw.tween_property(d, "modulate:a", 0.0, 3.0)
	tw.tween_callback(d.queue_free)


## "+N" in gold, rising from a kill.
static func coin(parent: Node, at: Vector3, amount: int) -> void:
	var l := Label3D.new()
	l.text = "+%d" % amount
	l.font = Style.title_font()
	l.font_size = 64
	l.pixel_size = 0.006
	l.modulate = Color(1.0, 0.82, 0.3)
	l.outline_modulate = Color(0.1, 0.05, 0.0)
	l.outline_size = 12
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	_one_shot(parent, l, at, 1.2)
	var tw := l.create_tween()
	tw.tween_property(l, "position:y", at.y + 1.2, 1.2).set_ease(Tween.EASE_OUT)
	tw.parallel().tween_property(l, "modulate:a", 0.0, 1.2).set_delay(0.5)


static func health_bar(width: float) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2(width, 0.16)
	mi.mesh = q
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/bar.gdshader")
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi

