class_name Mats
extends RefCounted
## The material library. Models name their materials (tools/blender/lib.py COLORS); `apply` swaps each
## for the textured or glowing material of that name. Texture repeats come from the models' UVs.

const TEX := "res://assets/textures/"

static var _cache: Dictionary = {}


static func named(raw: String) -> Material:
	var key := raw.get_slice(".", 0)
	if not _cache.has(key):
		_cache[key] = _make(key)
	return _cache[key]


## Replace every surface's material under `root` by the library's material of the same name.
static func apply(root: Node) -> void:
	for node in root.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i)
			if m != null and m.resource_name != "":
				var lib := named(m.resource_name)
				if lib != null:
					mi.set_surface_override_material(i, lib)


static func textured(tex: String, tint := Color.WHITE, normal := 1.0, metallic := 0.0, rough_scale := 1.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_texture = load(TEX + tex + "_albedo.png")
	m.albedo_color = tint
	m.normal_enabled = true
	m.normal_texture = load(TEX + tex + "_normal.png")
	m.normal_scale = normal
	m.roughness_texture = load(TEX + tex + "_rough.png")
	m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	m.roughness = rough_scale
	m.metallic = metallic
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	return m


static func glow(color: Color, energy: float, albedo := Color.BLACK) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = albedo
	m.emission_enabled = true
	m.emission = color
	m.emission_energy_multiplier = energy
	return m


static func flat(color: Color, rough := 0.8, metallic := 0.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = rough
	m.metallic = metallic
	return m


static func _make(key: String) -> Material:
	match key:
		"plaster": return textured("plaster", Color(0.85, 0.8, 0.72))
		"timber": return textured("timber", Color(0.9, 0.85, 0.8), 1.2)
		"planks": return textured("planks", Color(0.8, 0.72, 0.62))
		"thatch": return textured("thatch", Color(0.85, 0.78, 0.65), 1.4)
		"stone": return textured("stone", Color(0.8, 0.8, 0.78), 1.2)
		"slate": return textured("slate", Color(0.75, 0.78, 0.85), 1.0)
		"iron": return textured("iron", Color(0.7, 0.68, 0.66), 1.0, 0.65)
		"copper": return textured("iron", Color(1.1, 0.55, 0.3), 1.0, 0.8, 0.6)
		"gold": return textured("iron", Color(1.4, 1.0, 0.4), 0.6, 1.0, 0.45)
		"demon_skin": return textured("demon_skin", Color(1.0, 0.85, 0.85), 1.2, 0.0, 0.9)
		"corpse_skin": return textured("corpse_skin", Color(0.85, 0.9, 0.8), 1.2)
		"bone": return textured("bone", Color(0.85, 0.8, 0.7), 0.8)
		"cloth": return textured("cloth")
		"leather": return textured("cloth", Color(0.45, 0.3, 0.22), 1.0, 0.0, 0.7)
		"rope": return textured("thatch", Color(0.9, 0.8, 0.6))
		"basalt": return textured("basalt", Color(0.9, 0.9, 1.0), 1.0, 0.1)
		"flagstones": return textured("flagstones")
		"cobbles": return textured("cobbles")
		"earth": return textured("earth")
		"charred": return textured("timber", Color(0.25, 0.2, 0.18), 1.4)
		"feather_red": return flat(Color(0.55, 0.03, 0.02), 0.6)
		"feather_gold": return flat(Color(0.75, 0.45, 0.05), 0.5)
		"hair": return flat(Color(0.04, 0.03, 0.025), 0.9)
		"blood": return flat(Color(0.18, 0.0, 0.0), 0.25)
		"banner": return flat(Color(0.35, 0.02, 0.02), 0.85)
		"ice": return _ice()
		"glass": return flat(Color(0.3, 0.2, 0.15), 0.1)
		"glow_fire": return glow(Color(1.0, 0.45, 0.12), 6.0)
		"glow_eye": return glow(Color(1.0, 0.75, 0.15), 8.0)
		"glow_frost": return glow(Color(0.35, 0.75, 1.0), 5.0)
		"glow_storm": return glow(Color(0.35, 0.55, 1.0), 6.0)
		"glow_curse": return glow(Color(0.65, 0.2, 1.0), 6.0)
		"glow_window": return glow(Color(1.0, 0.55, 0.2), 3.0)
		"glow_holy": return glow(Color(1.0, 0.82, 0.5), 5.0)
		"glow_portal": return glow(Color(1.0, 0.15, 0.04), 8.0)
	return null


static func _ice() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.55, 0.8, 1.0, 0.75)
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_DEPTH_PRE_PASS
	m.roughness = 0.08
	m.metallic = 0.2
	m.emission_enabled = true
	m.emission = Color(0.2, 0.55, 1.0)
	m.emission_energy_multiplier = 1.2
	m.rim_enabled = true
	m.rim = 1.0
	m.rim_tint = 0.2
	return m
