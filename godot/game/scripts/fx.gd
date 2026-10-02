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


static func billboard(tex: Texture2D, additive: bool, shaded := false, frames := 1) -> StandardMaterial3D:
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
	# fog mixed into an additive sprite tints it and shows its quad: light shines through the haze instead
	m.disable_fog = additive
	return m


## A colour ramp over a particle's life; `hdr` keeps values above 1, so glow picks them up.
static func ramp(stops: Array, hdr := false) -> GradientTexture1D:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array(stops.map(func(s): return s[0]))
	g.colors = PackedColorArray(stops.map(func(s): return s[1]))
	var t := GradientTexture1D.new()
	t.gradient = g
	t.use_hdr = hdr
	return t


static func curve(points: Array) -> CurveTexture:
	var c := Curve.new()
	for p in points:
		c.add_point(Vector2(p[0], p[1]))
	var t := CurveTexture.new()
	t.curve = c
	return t


## Flames `size` metres across, rooted where they burn and licking upward; additive, so glow turns them into light.
static func fire(size: float, intensity := 1.0, tint := Color.WHITE) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = int(clamp(13 * size, 10, 40))   # more overlapping additive flames sum to white
	p.lifetime = 0.9
	p.preprocess = 1.0
	p.local_coords = false
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	pm.emission_sphere_radius = size * 0.28
	pm.direction = Vector3.UP
	pm.spread = 6.0
	pm.initial_velocity_min = 0.1 * size
	pm.initial_velocity_max = 0.35 * size
	pm.gravity = Vector3(0, 0.75 * size, 0)
	pm.damping_min = 0.2
	pm.damping_max = 0.5
	pm.scale_min = 0.8
	pm.scale_max = 1.25
	pm.scale_curve = curve([[0.0, 0.75], [0.25, 1.0], [1.0, 0.25]])
	pm.angle_min = -8.0
	pm.angle_max = 8.0
	pm.anim_offset_min = 0.0
	pm.anim_offset_max = 0.5
	pm.anim_speed_min = 1.0   # each flame plays through the painted shapes as it rises
	pm.anim_speed_max = 1.0
	pm.turbulence_enabled = true
	pm.turbulence_noise_strength = 0.4
	pm.turbulence_noise_scale = 2.5
	pm.turbulence_influence_min = 0.02
	pm.turbulence_influence_max = 0.07
	# overlapping additive flames sum: each stays faint, so the heart of a big fire is orange, not white
	var k := intensity
	# `tint` multiplies it (the Bone Altar's cauldron burns green)
	pm.color_ramp = ramp([[0.0, Color(k, k * 0.8, k * 0.55, 0.0) * tint], [0.1, Color(k, k * 0.75, k * 0.45, 0.5) * tint],
		[0.45, Color(k * 0.95, k * 0.5, k * 0.25, 0.4) * tint], [0.8, Color(0.7, 0.22, 0.07, 0.2) * tint],
		[1.0, Color(0.35, 0.1, 0.04, 0.0) * tint]])
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(size * 0.85, size * 1.2)
	q.center_offset = Vector3(0, size * 0.4, 0)
	q.material = billboard(load("res://assets/fx/fire_sheet.png"), true, false, 4)
	p.draw_pass_1 = q
	p.visibility_aabb = AABB(Vector3(-size * 2, -1, -size * 2), Vector3(size * 4, size * 5, size * 4))
	return p


## Dark smoke rising `height` metres and spreading, lit warm by the fire beneath it and grey above, so a
## column reads against the night sky.
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
	pm.scale_curve = curve([[0.0, 0.15], [1.0, 1.0]])   # a thin root, gathering as it rises
	pm.angle_min = 0.0
	pm.angle_max = 360.0
	pm.angular_velocity_min = -12.0
	pm.angular_velocity_max = 12.0
	pm.turbulence_enabled = true
	pm.turbulence_noise_strength = 0.4
	pm.turbulence_noise_scale = 6.0
	pm.anim_offset_min = 0.0
	pm.anim_offset_max = 1.0
	pm.color_ramp = ramp([[0.0, Color(0.4, 0.18, 0.07, 0.0)], [0.1, Color(0.3, 0.16, 0.09, 0.28)],
		[0.3, Color(0.19, 0.15, 0.13, 0.5)], [0.65, Color(0.13, 0.12, 0.12, 0.38)], [1.0, Color(0.1, 0.1, 0.11, 0.0)]])
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(size * 2.4, size * 2.4)
	q.material = billboard(load("res://assets/fx/smoke_sheet.png"), false, false, 4)
	p.draw_pass_1 = q
	p.visibility_aabb = AABB(Vector3(-height, -2, -height), Vector3(height * 2, height * 1.6, height * 2))
	return p


## A fireball bursting once, `size` metres across: flames thrown outward and stopped short by the air.
static func fireball(size: float) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = 36
	p.lifetime = 0.7
	p.one_shot = true
	p.explosiveness = 1.0
	p.local_coords = false
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	pm.emission_sphere_radius = size * 0.15
	pm.direction = Vector3.UP
	pm.spread = 180.0
	pm.initial_velocity_min = 0.6 * size
	pm.initial_velocity_max = 5.0 * size
	pm.damping_min = 10.0 * size
	pm.damping_max = 14.0 * size
	pm.gravity = Vector3(0, 1.5, 0)
	pm.scale_min = 0.8
	pm.scale_max = 1.3
	pm.scale_curve = curve([[0.0, 0.45], [0.25, 1.0], [1.0, 1.25]])
	pm.angle_min = 0.0
	pm.angle_max = 360.0
	pm.anim_offset_min = 0.0
	pm.anim_offset_max = 1.0
	pm.color_ramp = ramp([[0.0, Color(2.6, 2.3, 1.8, 1.0)], [0.15, Color(2.4, 1.4, 0.6, 0.95)],
		[0.5, Color(1.1, 0.4, 0.1, 0.6)], [1.0, Color(0.15, 0.05, 0.02, 0.0)]], true)
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(size * 1.1, size * 1.1)
	q.material = billboard(load("res://assets/fx/fire_sheet.png"), true, false, 4)
	p.draw_pass_1 = q
	p.emitting = true
	p.finished.connect(p.queue_free)
	return p


## A puff of dark smoke, once, rolling up and out of a blast.
static func puff(size: float) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = 9
	p.lifetime = 1.8
	p.one_shot = true
	p.explosiveness = 0.85
	p.local_coords = false
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	pm.emission_sphere_radius = size * 0.3
	pm.direction = Vector3.UP
	pm.spread = 70.0
	pm.initial_velocity_min = 1.0 * size
	pm.initial_velocity_max = 2.4 * size
	pm.damping_min = 1.5
	pm.damping_max = 2.5
	pm.gravity = Vector3(0, 0.6, 0)
	pm.scale_curve = curve([[0.0, 0.4], [1.0, 1.3]])
	pm.angle_min = 0.0
	pm.angle_max = 360.0
	pm.angular_velocity_min = -30.0
	pm.angular_velocity_max = 30.0
	pm.anim_offset_min = 0.0
	pm.anim_offset_max = 1.0
	pm.color_ramp = ramp([[0.0, Color(0.45, 0.2, 0.08, 0.0)], [0.12, Color(0.3, 0.17, 0.1, 0.6)],
		[0.5, Color(0.13, 0.12, 0.12, 0.45)], [1.0, Color(0.1, 0.1, 0.1, 0.0)]])
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(size * 1.8, size * 1.8)
	q.material = billboard(load("res://assets/fx/smoke_sheet.png"), false, false, 4)
	p.draw_pass_1 = q
	p.emitting = true
	p.finished.connect(p.queue_free)
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
	pm.color_ramp = ramp([[0.0, Color(1.0, 0.6, 0.2, 0.0)], [0.1, Color(1.0, 0.55, 0.15) * 4.0],
		[0.7, Color(1.0, 0.3, 0.05) * 2.0], [1.0, Color(0.6, 0.1, 0.0, 0.0)]])
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(0.09, 0.09)
	q.material = billboard(dot_texture(), true)
	p.draw_pass_1 = q
	p.visibility_aabb = AABB(-extent - Vector3(5, 0, 5), extent * 2 + Vector3(10, 15, 10))
	return p


## A burst of sparks, once: hits and deaths. Thin streaks drawn along their flight.
static func sparks(color: Color, amount := 24, speed := 4.0) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = amount
	p.lifetime = 0.55
	p.one_shot = true
	p.explosiveness = 0.95
	p.local_coords = false
	p.transform_align = GPUParticles3D.TRANSFORM_ALIGN_Z_BILLBOARD_Y_TO_VELOCITY
	var pm := ParticleProcessMaterial.new()
	pm.direction = Vector3.UP
	pm.spread = 180.0
	pm.initial_velocity_min = speed * 0.4
	pm.initial_velocity_max = speed
	pm.gravity = Vector3(0, -9.0, 0)
	pm.damping_min = 1.0
	pm.damping_max = 3.0
	pm.scale_min = 0.6
	pm.scale_max = 1.2
	pm.scale_curve = curve([[0.0, 1.0], [1.0, 0.3]])
	pm.color_ramp = ramp([[0.0, color * 3.0], [0.5, color * 1.6], [1.0, Color(color.r, color.g, color.b, 0.0)]], true)
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(0.035, 0.32)
	var m := billboard(dot_texture(), true)
	m.billboard_mode = BaseMaterial3D.BILLBOARD_DISABLED
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	q.material = m
	p.draw_pass_1 = q
	p.emitting = true
	p.finished.connect(p.queue_free)
	return p


## Specks of light shed behind something moving: frost glints, cinders off a firebolt.
static func shed(color: Color, amount: int, size: float, seconds: float, fall := 0.0) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = amount
	p.lifetime = seconds
	p.local_coords = false
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	pm.emission_sphere_radius = 0.08
	pm.direction = Vector3.UP
	pm.spread = 180.0
	pm.initial_velocity_min = 0.2
	pm.initial_velocity_max = 0.8
	pm.gravity = Vector3(0, -fall, 0)
	pm.damping_min = 0.5
	pm.damping_max = 1.0
	pm.scale_min = 0.5
	pm.scale_max = 1.2
	pm.scale_curve = curve([[0.0, 1.0], [1.0, 0.0]])
	pm.color_ramp = ramp([[0.0, color * 2.5], [0.5, color * 1.5], [1.0, Color(color.r, color.g, color.b, 0.0)]], true)
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(size, size)
	q.material = billboard(dot_texture(), true)
	p.draw_pass_1 = q
	return p


## An omni light that flickers like firelight (Flicker drives it).
static func fire_light(energy: float, reach: float, shadows := false, color := Color(1.0, 0.5, 0.18)) -> OmniLight3D:
	var l := OmniLight3D.new()
	l.light_color = color
	l.light_energy = energy
	l.omni_range = reach
	l.omni_attenuation = 1.0
	l.shadow_enabled = shadows
	l.light_volumetric_fog_energy = 1.0   # every fire a halo of lit smoke
	l.set_script(load("res://scripts/flicker.gd"))
	return l
