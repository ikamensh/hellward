class_name Vfx
extends RefCounted
## Battle effects: impacts, explosions, lightning, the leaders' curses, blood, dust, gold, health bars.
## Each makes its nodes under `parent` and frees them when they are done.


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


static func explosion(parent: Node, at: Vector3, color: Color) -> void:
	var f := Fx.fire(1.4, 1.4)
	f.one_shot = true
	f.explosiveness = 0.9
	f.preprocess = 0.0
	f.amount = 16
	_one_shot(parent, f, at, 1.5)
	impact(parent, at, color, 30)
	_flash_light(parent, at, color, 7.0, 9.0, 0.35)
	scorch(parent, at, 1.2)


static func frost_burst(parent: Node, at: Vector3) -> void:
	impact(parent, at, Color(0.5, 0.8, 1.0), 26)
	_flash_light(parent, at, Color(0.45, 0.75, 1.0), 3.0, 6.0, 0.3)


static func dust(parent: Node, at: Vector3, size: float) -> void:
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
	pm.scale_curve = Fx._curve([[0.0, 0.4], [1.0, 1.0]])
	pm.anim_offset_max = 1.0
	pm.color_ramp = Fx._ramp([[0.0, Color(0.35, 0.3, 0.25, 0.0)], [0.15, Color(0.35, 0.3, 0.25, 0.6)],
		[1.0, Color(0.3, 0.27, 0.24, 0.0)]])
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(1.6, 1.6)
	q.material = Fx._billboard(load("res://assets/fx/smoke_sheet.png"), false, true, 4)
	p.draw_pass_1 = q
	p.emitting = true
	_one_shot(parent, p, at + Vector3(0, 0.3, 0), 2.0)


## A ribbon of light following a moving node.
static func trail(color: Color, width: float, seconds: float) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = 40
	p.lifetime = seconds
	p.local_coords = false
	var pm := ParticleProcessMaterial.new()
	pm.gravity = Vector3.ZERO
	pm.scale_curve = Fx._curve([[0.0, 1.0], [1.0, 0.0]])
	pm.color_ramp = Fx._ramp([[0.0, color], [1.0, Color(color.r, color.g, color.b, 0.0)]])
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(width * 2.0, width * 2.0)
	q.material = Fx._billboard(Fx.dot_texture(), true)
	p.draw_pass_1 = q
	return p


## A jagged bolt of lightning through `points`, flickering for a moment.
static func lightning(parent: Node, points: Array) -> void:
	var mi := MeshInstance3D.new()
	var im := ImmediateMesh.new()
	mi.mesh = im
	mi.material_override = Mats.glow(Color(0.55, 0.7, 1.0), 14.0, Color(0.8, 0.9, 1.0))
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(mi)
	var cam := parent.get_viewport().get_camera_3d()
	var rng := RandomNumberGenerator.new()
	_draw_bolt(im, points, cam, rng, 0.07)
	for i in range(1, points.size()):
		_flash_light(parent, points[i], Color(0.5, 0.65, 1.0), 6.0, 7.0, 0.25)
		impact(parent, points[i], Color(0.6, 0.75, 1.0), 14)
	var tw := mi.create_tween()
	for k in 3:
		tw.tween_callback(func(): _draw_bolt(im, points, cam, rng, 0.07)).set_delay(0.05)
	tw.tween_callback(mi.queue_free).set_delay(0.06)


static func _draw_bolt(im: ImmediateMesh, points: Array, cam: Camera3D, rng: RandomNumberGenerator, width: float) -> void:
	im.clear_surfaces()
	im.surface_begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in range(points.size() - 1):
		var a: Vector3 = points[i]
		var b: Vector3 = points[i + 1]
		var steps := int(clamp(a.distance_to(b) / 0.5, 3, 30))
		var prev := a
		for s in range(1, steps + 1):
			var t := float(s) / steps
			var p := a.lerp(b, t)
			if s < steps:
				p += Vector3(rng.randf_range(-1, 1), rng.randf_range(-1, 1), rng.randf_range(-1, 1)) * 0.35
			_segment(im, prev, p, cam, width)
			prev = p


static func _segment(im: ImmediateMesh, a: Vector3, b: Vector3, cam: Camera3D, width: float) -> void:
	var view := (cam.global_position - (a + b) * 0.5).normalized()
	var side := (b - a).cross(view).normalized() * width
	im.surface_add_vertex(a - side)
	im.surface_add_vertex(a + side)
	im.surface_add_vertex(b + side)
	im.surface_add_vertex(a - side)
	im.surface_add_vertex(b + side)
	im.surface_add_vertex(b - side)


## The leader's chant: a violet beam from its staff to the tower, pulsing, until the curse lands or breaks.
static func curse_beam(parent: Node, from: Node3D, to: Node3D) -> Node3D:
	var beam := CurseBeam.new()
	beam.from = from
	beam.to = to
	parent.add_child(beam)
	return beam


## A rune circle growing at a tower's foot for `seconds`: where the curse will fall.
static func rune_circle(tower: Node3D, radius: float, seconds: float) -> Node3D:
	var d := Decal.new()
	d.texture_albedo = load("res://assets/fx/rune_circle.png")
	d.texture_emission = load("res://assets/fx/rune_circle.png")
	d.emission_energy = 3.0
	d.modulate = Color(1, 1, 1, 1)
	d.size = Vector3(0.1, 3.0, 0.1)
	d.cull_mask = 1
	tower.add_child(d)
	d.position = Vector3(0, 0.5, 0)
	var tw := d.create_tween()
	tw.tween_property(d, "size", Vector3(radius * 2.0, 3.0, radius * 2.0), seconds).set_trans(Tween.TRANS_QUAD)
	tw.parallel().tween_property(d, "rotation:y", PI * 0.5, seconds)
	tw.tween_property(d, "modulate:a", 0.0, 0.4)
	tw.tween_callback(d.queue_free)
	return d


## A cursed tower's lasting mark: a dim rune circle at its foot and violet light.
static func curse_mark(tower: Node3D) -> Node3D:
	var root := Node3D.new()
	tower.add_child(root)
	var d := Decal.new()
	d.texture_albedo = load("res://assets/fx/rune_circle.png")
	d.texture_emission = load("res://assets/fx/rune_circle.png")
	d.emission_energy = 1.6
	d.size = Vector3(2.6, 3.0, 2.6)
	d.position = Vector3(0, 0.5, 0)
	root.add_child(d)
	root.create_tween().set_loops().tween_property(d, "rotation:y", TAU, 12.0).from(0.0)
	var l := OmniLight3D.new()
	l.light_color = Color(0.6, 0.2, 1.0)
	l.light_energy = 2.0
	l.omni_range = 5.0
	l.position = Vector3(0, 2.0, 0)
	root.add_child(l)
	return root


## Cleanse: a pillar of golden light.
static func holy(parent: Node, at: Vector3) -> void:
	burst(parent, at + Vector3(0, 1.5, 0), Color(1.0, 0.85, 0.5), 60)
	var col := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 1.2
	cm.bottom_radius = 1.2
	cm.height = 12.0
	cm.cap_top = false
	cm.cap_bottom = false
	col.mesh = cm
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.albedo_color = Color(1.0, 0.8, 0.45, 0.6)
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	col.material_override = m
	_one_shot(parent, col, at + Vector3(0, 6.0, 0), 1.0)
	col.create_tween().tween_property(m, "albedo_color:a", 0.0, 1.0)


## A leader pondering: three violet motes circling over its head.
static func ponder(m: Node3D) -> void:
	var root := Node3D.new()
	m.add_child(root)
	root.position = Vector3(0, m.height + 0.6, 0)
	for i in 3:
		var dot := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 0.08
		sm.height = 0.16
		dot.mesh = sm
		dot.material_override = Mats.glow(Color(0.7, 0.3, 1.0), 6.0)
		dot.position = Vector3(cos(i * TAU / 3) * 0.35, 0, sin(i * TAU / 3) * 0.35)
		root.add_child(dot)
	var tw := root.create_tween()
	tw.tween_property(root, "rotation:y", TAU * 1.5, 1.1)
	tw.tween_callback(root.queue_free)


static func blood(parent: Node, at: Vector3, size: float) -> void:
	var d := Decal.new()
	d.texture_albedo = load("res://assets/fx/blood_decal.png")
	d.size = Vector3(size * 2.0, 1.0, size * 2.0)
	d.rotation.y = randf() * TAU
	parent.add_child(d)
	d.global_position = at + Vector3(0, 0.2, 0)
	var tw := d.create_tween()
	tw.tween_interval(12.0)
	tw.tween_property(d, "modulate:a", 0.0, 4.0)
	tw.tween_callback(d.queue_free)


static func scorch(parent: Node, at: Vector3, size: float) -> void:
	var d := Decal.new()
	d.texture_albedo = load("res://assets/fx/scorch_decal.png")
	d.size = Vector3(size * 2.0, 2.0, size * 2.0)
	d.rotation.y = randf() * TAU
	parent.add_child(d)
	d.global_position = Vector3(at.x, 0.3, at.z)
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
	q.size = Vector2(width, 0.11)
	mi.mesh = q
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/bar.gdshader")
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi
