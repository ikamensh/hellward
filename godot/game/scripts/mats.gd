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
		"corpse_skin": return textured("corpse_skin", Color(0.8, 1.12, 1.05), 1.2)
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
		"stained_glass": return _picture("stained_glass", 2.2)
		"glass": return flat(Color(0.3, 0.2, 0.15), 0.1)
		"glow_fire": return glow(Color(1.0, 0.45, 0.12), 6.0)
		"glow_eye": return glow(Color(1.0, 0.75, 0.15), 8.0)
		"glow_frost": return glow(Color(0.35, 0.75, 1.0), 5.0)
		"glow_storm": return glow(Color(0.35, 0.55, 1.0), 6.0)
		"glow_curse": return glow(Color(0.65, 0.2, 1.0), 6.0)
		"glow_window": return glow(Color(1.0, 0.55, 0.2), 2.0)
		"glow_holy": return glow(Color(1.0, 0.7, 0.4), 1.6)
		"glow_portal": return glow(Color(1.0, 0.15, 0.04), 8.0)
		"glow_venom": return glow(Color(0.35, 1.0, 0.2), 4.0)
		"venom_pool": return glow(Color(0.25, 0.8, 0.12), 0.9, Color(0.05, 0.12, 0.03))
		"leaves": return flat(Color(0.1, 0.17, 0.06), 0.85)
		"mossy": return textured("stone", Color(0.62, 0.78, 0.55), 1.2)
	if key.begins_with("mon_"):
		return monster(key)
	return null


## A generated monster's own maps (assets/textures/<kind>/: albedo, normal, orm, emission; docs/monsters.md).
# the colour a monster's flesh shows lit from behind (the imps' thin ears and fingers glow red against a fire).
# Screen-space subsurface scattering looked softer but cost 2 ms with a wave on screen; the backlight is free.
const FLESH := {"mon_fallen": Color(0.16, 0.02, 0.01), "mon_shaman": Color(0.16, 0.02, 0.01),
	"mon_shaman_crest": Color(0.3, 0.08, 0.02),
	"mon_zombie": Color(0.16, 0.18, 0.1)}


# fine surface for a close look, laid over a generated body's own maps as a world-scaled triplanar detail normal:
# [library texture set, metres per repeat]
const GRAIN := {"mon_fallen": ["demon_skin", 0.12], "mon_shaman": ["demon_skin", 0.13],
	"mon_zombie": ["corpse_skin", 0.25], "mon_skeleton": ["bone", 0.15]}


static func monster(kind: String) -> ORMMaterial3D:
	var dir := TEX + kind + "/"
	var m := ORMMaterial3D.new()
	m.resource_name = kind
	if GRAIN.has(kind) and OS.get_environment("HW_NOGRAIN") == "":
		m.detail_enabled = true
		m.detail_uv_layer = BaseMaterial3D.DETAIL_UV_2
		m.uv2_triplanar = true
		m.uv2_scale = Vector3.ONE / float(GRAIN[kind][1])
		m.detail_normal = load(TEX + String(GRAIN[kind][0]) + "_normal.png")
		m.detail_albedo = _flat_texture(Color.WHITE)   # the colour left as it is (multiplied by white)
		m.detail_blend_mode = BaseMaterial3D.BLEND_MODE_MUL
		# the grain under the body's own forms, not instead; a hide's wrinkles and veins show more than bone's
		var share := 0.55 if kind in ["mon_fallen", "mon_shaman"] else 0.45
		m.detail_mask = _flat_texture(Color(share, share, share))
	if FLESH.has(kind):
		m.backlight_enabled = true
		m.backlight = FLESH[kind]
	m.albedo_texture = load(dir + "albedo.webp")
	m.normal_enabled = true
	m.normal_texture = load(dir + "normal.webp")
	m.orm_texture = load(dir + "orm.webp")
	m.metallic = 1.0   # the map's metal channel is multiplied by this: left at 0, no iron or steel was ever metal
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	if ResourceLoader.exists(dir + "emission.webp"):   # eyes, embers
		m.emission_enabled = true
		m.emission_texture = load(dir + "emission.webp")
		m.emission_energy_multiplier = GLOW
	return m


const GLOW := 5.0        # a monster's eyes: bright enough to bloom a little, as they read from the battle camera
const GLOW_OUT := 0.45   # seconds a dead monster's eyes take to go out


## One monster's own copies of its glowing materials (all, or only the one named `only`), so their glow can
## change on it alone: a dead body's eyes going out (`eyes_out`), a chanting Shaman's skull flaring.
static func own(root: Node, only := "") -> Array[ORMMaterial3D]:
	var mats: Array[ORMMaterial3D] = []
	for node in root.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		for i in mi.mesh.get_surface_count():
			var m := mi.get_surface_override_material(i) as ORMMaterial3D
			if m != null and m.resource_name.begins_with("mon_") and m.emission_enabled \
					and (only == "" or m.resource_name == only):
				m = m.duplicate() as ORMMaterial3D
				mi.set_surface_override_material(i, m)
				mats.append(m)
	return mats


const DEAD := Color(0.55, 0.52, 0.5)   # what a corpse's colour sinks to (a bright red dead Fallen read as alive)


## A body `t` seconds after it died: the glow in its eyes gone after GLOW_OUT, quickest at first, and with `pale`
## its colour sinking to DEAD over a second (not for a frozen one, whose rime is its colour).
static func eyes_out(mats: Array[ORMMaterial3D], t: float, pale := true) -> void:
	for m in mats:
		m.emission_energy_multiplier = GLOW * pow(clampf(1.0 - t / GLOW_OUT, 0.0, 1.0), 2.0)
		if pale:
			if not m.has_meta("alive"):
				m.set_meta("alive", m.albedo_color)
			m.albedo_color = (m.get_meta("alive") as Color) * Color.WHITE.lerp(DEAD, clampf(t, 0.0, 1.0))


# a pack is not cloned: each monster wears one of these tints of its kind's maps (Mats.vary)
const VARIANTS := [Color(1.0, 1.0, 1.0), Color(0.86, 0.88, 0.92), Color(1.1, 1.02, 0.94)]


## Give every monster material under `root` the tint of variant `n` (one of VARIANTS).
static func vary(root: Node, n: int) -> void:
	restyle(root, str(n), func(m: ORMMaterial3D) -> void: m.albedo_color = VARIANTS[n % VARIANTS.size()])


## A corpse a fire killed: charred black, embers glowing in its cracks.
static func burnt(root: Node) -> void:
	restyle(root, "burnt", func(m: ORMMaterial3D) -> void:
		m.albedo_color = Color(0.13, 0.1, 0.09)
		m.roughness = 1.0
		m.emission_enabled = true
		m.emission = Color(1.0, 0.3, 0.05)
		m.emission_energy_multiplier = 0.35
		m.emission_texture = m.orm_texture)


## A corpse the cold killed: rimed white-blue and glassy.
static func frozen(root: Node) -> void:
	restyle(root, "frozen", func(m: ORMMaterial3D) -> void:
		m.albedo_color = Color(0.85, 1.0, 1.25)
		m.roughness = 0.25
		m.rim_enabled = true
		m.rim = 0.8
		m.rim_tint = 0.0)


## Every monster material under `root` swapped for its variant `tag`, made once by `change` on a copy.
static func restyle(root: Node, tag: String, change: Callable) -> void:
	for node in root.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		for i in mi.mesh.get_surface_count():
			var m := mi.get_surface_override_material(i) as ORMMaterial3D
			if m == null or not m.resource_name.begins_with("mon_"):
				continue
			var key := "%s~%s" % [m.resource_name, tag]
			if not _cache.has(key):
				var copy := m.duplicate() as ORMMaterial3D
				change.call(copy)
				_cache[key] = copy
			mi.set_surface_override_material(i, _cache[key])


static func _flat_texture(c: Color) -> ImageTexture:
	var img := Image.create(4, 4, false, Image.FORMAT_RGBA8)
	img.fill(c)
	return ImageTexture.create_from_image(img)


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


## A painted picture on 0..1 UVs, cut out where the painting is black, glowing by `energy`.
static func _picture(tex: String, energy: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	var t: Texture2D = load(TEX + tex + ".png")
	m.albedo_texture = t
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	m.alpha_scissor_threshold = 0.5
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.roughness = 0.85
	m.emission_enabled = true
	m.emission_texture = t
	m.emission_energy_multiplier = energy
	m.albedo_color = Color(0.2, 0.2, 0.2)
	return m
