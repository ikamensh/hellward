class_name Atmosphere
extends RefCounted
## The night over Tristram: sky, a cold dim ambient and moon, fog the fires glow through, glow, the grade.
## The game (main.gd) and the model previews (preview.gd) share it, so a model sheet shows the in-game look.


## Add the environment and the moon under `parent`; returns the environment.
static func night(parent: Node) -> Environment:
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var pano := PanoramaSkyMaterial.new()
	pano.panorama = load("res://assets/textures/sky.png")
	pano.energy_multiplier = 0.4
	sky.sky_material = pano
	env.sky = sky
	env.sky_rotation = Vector3(0, deg_to_rad(200), 0)
	# a night lit by its fires: dim cold ambient and moon, the exposure carried by the firelit pools
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.13, 0.17, 0.26)
	env.ambient_light_energy = 0.9
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.7
	env.tonemap_agx_contrast = 1.45
	env.glow_enabled = true
	env.glow_intensity = 0.7
	env.glow_strength = 1.0
	env.glow_bloom = 0.0
	env.glow_hdr_threshold = 1.0
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SCREEN
	for i in 7:
		env.set_glow_level(i, [0.0, 0.5, 1.0, 0.8, 0.6, 0.35, 0.0][i])
	env.ssao_enabled = true
	env.ssao_radius = 1.2
	env.ssao_intensity = 2.5
	env.ssr_enabled = true
	env.ssr_max_steps = 48
	env.ssr_fade_in = 0.2
	env.ssr_fade_out = 2.0
	env.ssil_enabled = true
	env.ssil_intensity = 1.2
	env.fog_enabled = true
	env.fog_light_color = Color(0.03, 0.035, 0.05)
	env.fog_light_energy = 1.0
	env.fog_density = 0.004
	env.fog_sky_affect = 0.3
	env.fog_height = 1.0
	env.fog_height_density = 0.015
	# fog the lights glow through, not a grey veil
	env.volumetric_fog_enabled = true
	env.volumetric_fog_density = 0.007
	env.volumetric_fog_albedo = Color(0.7, 0.72, 0.8)
	env.volumetric_fog_emission = Color(0, 0, 0)
	env.volumetric_fog_anisotropy = 0.6
	env.volumetric_fog_length = 120.0
	env.volumetric_fog_ambient_inject = 0.0
	env.volumetric_fog_gi_inject = 0.0
	env.adjustment_enabled = true
	env.adjustment_contrast = 1.0
	env.adjustment_saturation = 1.05
	env.adjustment_color_correction = grade()
	var we := WorldEnvironment.new()
	we.environment = env
	parent.add_child(we)
	var moon := DirectionalLight3D.new()
	moon.name = "Moon"
	moon.light_color = Color(0.5, 0.66, 0.9)
	moon.light_energy = 1.4
	moon.shadow_enabled = true
	moon.directional_shadow_max_distance = 140.0
	moon.light_volumetric_fog_energy = 0.2
	moon.rotation_degrees = Vector3(-58, -150, 0)
	moon.light_angular_distance = 1.2
	moon.shadow_opacity = 1.0
	parent.add_child(moon)
	return env


## The grade: cool shadows, neutral middle, warm highlights.
static func grade() -> GradientTexture1D:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.08, 0.25, 0.5, 0.75, 1.0])
	g.colors = PackedColorArray([Color(0, 0, 0), Color(0.05, 0.065, 0.085), Color(0.21, 0.235, 0.265),
		Color(0.51, 0.5, 0.48), Color(0.79, 0.75, 0.69), Color(1.0, 0.97, 0.91)])
	var t := GradientTexture1D.new()
	t.gradient = g
	t.width = 256
	return t


