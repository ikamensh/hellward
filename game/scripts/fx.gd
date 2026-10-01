class_name Fx
extends RefCounted
## Procedural effects: flames, smoke, embers, flickering lights, sparks. Textures are drawn once at startup.

static var _dot: Texture2D


## A soft round dot: embers and sparks.
static func dot_texture() -> Texture2D:
	if _dot == null:
		var size := 32
		var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
		for y in size:
			for x in size:
				var d := Vector2(x + 0.5 - size * 0.5, y + 0.5 - size * 0.5).length() / (size * 0.5)
				var a: float = clamp(1.0 - d, 0.0, 1.0)
				img.set_pixel(x, y, Color(1, 1, 1, a * a))
		img.generate_mipmaps()
		_dot = ImageTexture.create_from_image(img)
	return _dot


static func _billboard(tex: Texture2D, additive: bool, shaded := false, frames := 1) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.particles_anim_h_frames = frames
	m.particles_anim_v_frames = frames
	m.particles_anim_loop = false
	m.albedo_texture = tex
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD if additive else BaseMaterial3D.BLEND_MODE_MIX
	m.shading_mode = BaseMaterial3D.SHADING_MODE_PER_VERTEX if shaded else BaseMaterial3D.SHADING_MODE_UNSHADED
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
	m.proximity_fade_enabled = true
	m.proximity_fade_distance = 0.6
	return m


static func _ramp(stops: Array) -> GradientTexture1D:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array(stops.map(func(s): return s[0]))
	g.colors = PackedColorArray(stops.map(func(s): return s[1]))
	var t := GradientTexture1D.new()
	t.gradient = g
	return t


static func _curve(points: Array) -> CurveTexture:
	var c := Curve.new()
	for p in points:
		c.add_point(Vector2(p[0], p[1]))
	var t := CurveTexture.new()
	t.curve = c
	return t


## Flames `size` metres across, licking upward; additive, so glow turns them into light.
static func fire(size: float, intensity := 1.0) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = int(clamp(16 * size, 10, 48))
	p.lifetime = 1.0
	p.preprocess = 1.0
	p.local_coords = false
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	pm.emission_sphere_radius = size * 0.3
	pm.direction = Vector3.UP
	pm.spread = 8.0
	pm.initial_velocity_min = 0.4 * size
	pm.initial_velocity_max = 1.0 * size
	pm.gravity = Vector3(0, 1.6 * size, 0)
	pm.damping_min = 0.5
	pm.damping_max = 1.0
	pm.scale_min = 0.8
	pm.scale_max = 1.3
	pm.scale_curve = _curve([[0.0, 0.55], [0.3, 1.0], [1.0, 0.35]])
	pm.angle_min = -10.0
	pm.angle_max = 10.0
	pm.anim_offset_min = 0.0
	pm.anim_offset_max = 1.0
	pm.turbulence_enabled = true
	pm.turbulence_noise_strength = 0.5
	pm.turbulence_noise_scale = 2.5
	pm.turbulence_influence_min = 0.03
	pm.turbulence_influence_max = 0.1
	var k := 1.5 * intensity
	pm.color_ramp = _ramp([[0.0, Color(k, k, k, 0.0)], [0.12, Color(k, k * 0.95, k * 0.9, 0.85)],
		[0.55, Color(k * 0.9, k * 0.6, k * 0.4, 0.55)], [1.0, Color(0.5, 0.2, 0.1, 0.0)]])
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(size * 0.85, size * 1.2)
	q.center_offset = Vector3(0, size * 0.4, 0)
	q.material = _billboard(load("res://assets/fx/fire_sheet.png"), true, false, 4)
	p.draw_pass_1 = q
	p.visibility_aabb = AABB(Vector3(-size * 2, -1, -size * 2), Vector3(size * 4, size * 5, size * 4))
	return p


## Dark smoke rising `height` metres and spreading, lit by whatever burns beneath it.
static func smoke(size: float, height := 14.0) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = 28
	p.lifetime = 7.0
	p.preprocess = 7.0
	p.local_coords = false
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	pm.emission_sphere_radius = size * 0.4
	pm.direction = Vector3(0.15, 1, 0.05)
	pm.spread = 10.0
	pm.initial_velocity_min = height / 7.0 * 0.7
	pm.initial_velocity_max = height / 7.0 * 1.2
	pm.gravity = Vector3(0.25, 0.1, 0.05)
	pm.scale_min = 1.0
	pm.scale_max = 1.6
	pm.scale_curve = _curve([[0.0, 0.3], [1.0, 1.0]])
	pm.angle_min = 0.0
	pm.angle_max = 360.0
	pm.angular_velocity_min = -12.0
	pm.angular_velocity_max = 12.0
	pm.turbulence_enabled = true
	pm.turbulence_noise_strength = 0.4
	pm.turbulence_noise_scale = 6.0
	pm.anim_offset_min = 0.0
	pm.anim_offset_max = 1.0
	pm.color_ramp = _ramp([[0.0, Color(0.16, 0.14, 0.13, 0.0)], [0.12, Color(0.16, 0.14, 0.13, 0.7)],
		[0.6, Color(0.11, 0.105, 0.105, 0.45)], [1.0, Color(0.08, 0.08, 0.09, 0.0)]])
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(size * 2.4, size * 2.4)
	q.material = _billboard(load("res://assets/fx/smoke_sheet.png"), false, true, 4)
	p.draw_pass_1 = q
	p.visibility_aabb = AABB(Vector3(-height, -2, -height), Vector3(height * 2, height * 1.6, height * 2))
	return p


## Embers drifting up out of an area `extent` metres across.
static func embers(extent: Vector3, amount := 120) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = amount
	p.lifetime = 5.0
	p.preprocess = 5.0
	p.local_coords = false
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	pm.emission_box_extents = extent * 0.5
	pm.direction = Vector3.UP
	pm.spread = 25.0
	pm.initial_velocity_min = 0.6
	pm.initial_velocity_max = 2.0
	pm.gravity = Vector3(0.3, 0.5, 0.0)
	pm.scale_min = 0.5
	pm.scale_max = 1.3
	pm.turbulence_enabled = true
	pm.turbulence_noise_strength = 1.2
	pm.turbulence_noise_scale = 3.0
	pm.turbulence_influence_min = 0.1
	pm.turbulence_influence_max = 0.3
	pm.color_ramp = _ramp([[0.0, Color(1.0, 0.6, 0.2, 0.0)], [0.1, Color(1.0, 0.55, 0.15) * 4.0],
		[0.7, Color(1.0, 0.3, 0.05) * 2.0], [1.0, Color(0.6, 0.1, 0.0, 0.0)]])
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(0.09, 0.09)
	q.material = _billboard(dot_texture(), true)
	p.draw_pass_1 = q
	p.visibility_aabb = AABB(-extent - Vector3(5, 0, 5), extent * 2 + Vector3(10, 15, 10))
	return p


## A burst of sparks, once: hits and deaths.
static func sparks(color: Color, amount := 24, speed := 4.0) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = amount
	p.lifetime = 0.6
	p.one_shot = true
	p.explosiveness = 0.95
	p.local_coords = false
	var pm := ParticleProcessMaterial.new()
	pm.direction = Vector3.UP
	pm.spread = 180.0
	pm.initial_velocity_min = speed * 0.4
	pm.initial_velocity_max = speed
	pm.gravity = Vector3(0, -9.0, 0)
	pm.scale_min = 0.5
	pm.scale_max = 1.2
	pm.color_ramp = _ramp([[0.0, color * 4.0], [0.6, color * 2.0], [1.0, Color(color.r, color.g, color.b, 0.0)]])
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(0.12, 0.12)
	q.material = _billboard(dot_texture(), true)
	p.draw_pass_1 = q
	p.emitting = true
	p.finished.connect(p.queue_free)
	return p


## An omni light that flickers like firelight (Flicker drives it).
static func fire_light(energy: float, reach: float, shadows := false, color := Color(1.0, 0.5, 0.18)) -> OmniLight3D:
	var l := OmniLight3D.new()
	l.light_color = color
	l.light_energy = energy
	l.omni_range = reach
	l.omni_attenuation = 1.0
	l.shadow_enabled = shadows
	l.light_volumetric_fog_energy = 0.25
	l.set_script(load("res://scripts/flicker.gd"))
	return l
