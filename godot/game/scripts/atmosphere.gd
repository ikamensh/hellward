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




## How each location's night differs from Tristram's: the sky (the night panorama, a dark vault underground,
## hell's red), the moon, the ambient, the fog and the mist the fires glow through, and the grade. Tristram keeps
## night() as it is; a theme not listed here does too.
const THEMES := {
	"graveyard": {"sky": "night", "sky_energy": 0.42, "moon": [Color(0.58, 0.74, 0.95), 2.3], "ambient": [Color(0.13, 0.18, 0.24), 1.15],
		"fog": [Color(0.03, 0.045, 0.05), 0.005], "vol": [Color(0.6, 0.78, 0.76), 0.011, Color(0, 0, 0)],
		"mist": [Color(0.5, 0.72, 0.66), 0.04], "grade": [Color(0.72, 1.02, 1.0), Color(0.98, 1.0, 0.92)], "saturation": 0.85, "exposure": 1.8},
	"cathedral": {"sky": "night", "sky_energy": 0.3, "moon": [Color(0.55, 0.64, 0.95), 1.9], "ambient": [Color(0.15, 0.15, 0.19), 1.05],
		"fog": [Color(0.03, 0.03, 0.04), 0.004], "vol": [Color(0.75, 0.72, 0.7), 0.012, Color(0, 0, 0)],
		"mist": [Color(0.6, 0.58, 0.56), 0.02], "grade": [Color(0.85, 0.9, 1.15), Color(1.05, 0.95, 0.82)], "saturation": 1.0, "exposure": 1.8},
	"catacombs": {"sky": "dark", "sky_color": Color(0.01, 0.009, 0.008), "moon": [Color(0.68, 0.7, 0.76), 1.8, Vector3(-75, -160, 0)],
		"ambient": [Color(0.2, 0.17, 0.15), 1.25], "fog": [Color(0.02, 0.017, 0.015), 0.006],
		"vol": [Color(0.65, 0.6, 0.55), 0.012, Color(0, 0, 0)], "mist": [Color(0.55, 0.5, 0.45), 0.025],
		"grade": [Color(0.95, 0.92, 0.9), Color(1.05, 0.95, 0.82)], "saturation": 0.9, "exposure": 1.9},
	"caves": {"sky": "dark", "sky_color": Color(0.012, 0.006, 0.004), "moon": [Color(0.82, 0.7, 0.64), 2.2, Vector3(-72, -140, 0)],
		"ambient": [Color(0.19, 0.15, 0.14), 1.3], "fog": [Color(0.03, 0.012, 0.006), 0.006],
		"vol": [Color(0.8, 0.6, 0.5), 0.01, Color(0.008, 0.002, 0.0)], "mist": [Color(0.62, 0.46, 0.36), 0.022],
		"grade": [Color(0.9, 0.85, 0.92), Color(1.1, 0.92, 0.76)], "saturation": 1.05, "exposure": 1.9},
	"hell": {"sky": "red", "moon": [Color(1.0, 0.66, 0.52), 1.8], "ambient": [Color(0.19, 0.12, 0.11), 1.1],
		"fog": [Color(0.08, 0.02, 0.01), 0.004], "vol": [Color(0.85, 0.5, 0.4), 0.006, Color(0.005, 0.001, 0.0)],
		"mist": [Color(0.55, 0.32, 0.25), 0.018], "grade": [Color(1.02, 0.88, 0.88), Color(1.06, 0.95, 0.85)], "saturation": 1.0, "exposure": 1.8},
	"docks": {"sky": "night", "sky_energy": 0.45, "moon": [Color(0.58, 0.74, 0.95), 2.3], "ambient": [Color(0.12, 0.17, 0.23), 1.2],
		"fog": [Color(0.03, 0.05, 0.06), 0.005], "vol": [Color(0.65, 0.78, 0.85), 0.011, Color(0, 0, 0)],
		"mist": [Color(0.5, 0.66, 0.72), 0.03], "grade": [Color(0.75, 1.0, 1.12), Color(1.02, 0.98, 0.9)], "saturation": 1.0, "exposure": 1.8},
	"spider_forest": {"sky": "night", "sky_energy": 0.32, "moon": [Color(0.55, 0.74, 0.7), 2.1], "ambient": [Color(0.11, 0.17, 0.15), 1.2],
		"fog": [Color(0.02, 0.04, 0.035), 0.006], "vol": [Color(0.6, 0.76, 0.66), 0.013, Color(0, 0, 0)],
		"mist": [Color(0.5, 0.7, 0.56), 0.04], "grade": [Color(0.78, 1.04, 0.95), Color(0.98, 1.0, 0.88)], "saturation": 0.95, "exposure": 1.9},
	"jungle": {"sky": "night", "sky_energy": 0.38, "moon": [Color(0.62, 0.8, 0.68), 2.2], "ambient": [Color(0.11, 0.18, 0.13), 1.2],
		"fog": [Color(0.025, 0.05, 0.03), 0.006], "vol": [Color(0.66, 0.86, 0.66), 0.013, Color(0, 0, 0)],
		"mist": [Color(0.55, 0.76, 0.55), 0.04], "grade": [Color(0.78, 1.08, 0.86), Color(1.0, 1.02, 0.88)], "saturation": 1.05, "exposure": 1.9},
	"drowned_city": {"sky": "night", "sky_energy": 0.38, "moon": [Color(0.58, 0.76, 0.86), 2.2], "ambient": [Color(0.11, 0.16, 0.18), 1.2],
		"fog": [Color(0.025, 0.045, 0.05), 0.006], "vol": [Color(0.55, 0.72, 0.72), 0.014, Color(0, 0, 0)],
		"mist": [Color(0.45, 0.66, 0.62), 0.045], "grade": [Color(0.74, 1.04, 1.04), Color(0.98, 1.0, 0.94)], "saturation": 0.95, "exposure": 1.9},
	"travincal": {"sky": "night", "sky_energy": 0.42, "moon": [Color(0.58, 0.74, 0.82), 1.9], "ambient": [Color(0.12, 0.15, 0.15), 1.05],
		"fog": [Color(0.03, 0.045, 0.045), 0.005], "vol": [Color(0.75, 0.75, 0.66), 0.01, Color(0, 0, 0)],
		"mist": [Color(0.6, 0.7, 0.6), 0.03], "grade": [Color(0.82, 1.0, 1.0), Color(1.08, 0.97, 0.82)], "saturation": 1.05, "exposure": 1.8},
	"temple": {"sky": "dark", "sky_color": Color(0.012, 0.01, 0.008), "moon": [Color(0.75, 0.7, 0.65), 1.0, Vector3(-70, -170, 0)],
		"ambient": [Color(0.18, 0.15, 0.12), 1.15], "fog": [Color(0.03, 0.025, 0.02), 0.005],
		"vol": [Color(0.9, 0.82, 0.66), 0.009, Color(0, 0, 0)], "mist": [Color(0.7, 0.62, 0.5), 0.018],
		"grade": [Color(0.95, 0.92, 0.98), Color(1.1, 0.98, 0.78)], "saturation": 1.0, "exposure": 1.85},
}


## Turn the night that night() made under `parent` into the location's own; Tristram's ("village") stays.
static func theme(parent: Node, key: String) -> void:
	if not THEMES.has(key):
		return
	var t: Dictionary = THEMES[key]
	var env: Environment = (parent.find_children("*", "WorldEnvironment", false, false)[0] as WorldEnvironment).environment
	match String(t["sky"]):
		"night":
			(env.sky.sky_material as PanoramaSkyMaterial).energy_multiplier = float(t["sky_energy"])
		"dark":   # underground: a black vault, nothing reflected from a sky
			env.background_mode = Environment.BG_COLOR
			env.background_color = t["sky_color"]
			env.reflected_light_source = Environment.REFLECTION_SOURCE_DISABLED
		"red":
			var sky := ProceduralSkyMaterial.new()
			sky.sky_top_color = Color(0.05, 0.006, 0.004)
			sky.sky_horizon_color = Color(0.55, 0.09, 0.02)
			sky.sky_curve = 0.08
			sky.ground_bottom_color = Color(0.02, 0.004, 0.002)
			sky.ground_horizon_color = Color(0.45, 0.07, 0.02)
			sky.sun_angle_max = 0.0
			sky.energy_multiplier = 1.0
			env.sky.sky_material = sky
	var moon := parent.get_node("Moon") as DirectionalLight3D
	moon.light_color = t["moon"][0]
	moon.light_energy = float(t["moon"][1])
	if t["moon"].size() > 2:   # underground: a light from high above stands in for the moon, for the lanes' sake
		moon.rotation_degrees = t["moon"][2]
	env.ambient_light_color = t["ambient"][0]
	env.ambient_light_energy = float(t["ambient"][1])
	env.fog_light_color = t["fog"][0]
	env.fog_density = float(t["fog"][1])
	env.volumetric_fog_albedo = t["vol"][0]
	env.volumetric_fog_density = float(t["vol"][1])
	env.volumetric_fog_emission = t["vol"][2]
	env.adjustment_saturation = float(t["saturation"])
	env.tonemap_exposure = float(t["exposure"])
	env.adjustment_color_correction = tinted_grade(t["grade"][0], t["grade"][1])
	for mist in parent.find_children("*", "FogVolume", false, false):   # main.gd's ground mist
		var fm := (mist as FogVolume).material as FogMaterial
		fm.albedo = t["mist"][0]
		fm.density = float(t["mist"][1])


## A grade like grade()'s, its shadows tinted `shadow` and its highlights `light`.
static func tinted_grade(shadow: Color, light: Color) -> GradientTexture1D:
	var g := Gradient.new()
	var stops := PackedFloat32Array([0.0, 0.08, 0.25, 0.5, 0.75, 1.0])
	var values := [0.0, 0.067, 0.237, 0.5, 0.743, 0.96]
	var colors := PackedColorArray()
	for i in stops.size():
		var tint := shadow.lerp(light, smoothstep(0.1, 0.9, stops[i]))
		var v: float = values[i]
		colors.append(Color(v * tint.r, v * tint.g, v * tint.b))
	g.offsets = stops
	g.colors = colors
	var t := GradientTexture1D.new()
	t.gradient = g
	t.width = 256
	return t
