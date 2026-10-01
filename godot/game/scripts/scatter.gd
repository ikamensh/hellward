class_name Scatter
extends Node3D
## Ground clutter: grass tufts swaying in the wind off the lanes, stones everywhere, the forest on the hills and
## dead wood, as MultiMeshes. Tristram has its own (`_village`); every other location's comes from its theme.

## Per theme: `grass` the tufts' colours, dry to fresh, and their height (none indoors or underground), `stones`
## the pebbles' material, `trees` the forest round the field (pines, jungle, none), `dead` how many dead trees.
const GROUND := {
	"village": {"grass": [Color(0.17, 0.17, 0.08), Color(0.3, 0.24, 0.12), 1.0], "stones": "stone", "trees": "pine", "dead": 70},
	"graveyard": {"grass": [Color(0.14, 0.16, 0.11), Color(0.26, 0.26, 0.18), 1.0], "stones": "stone", "trees": "pine", "dead": 90},
	"cathedral": {"grass": [], "stones": "stone", "trees": "none", "dead": 0},
	"catacombs": {"grass": [], "stones": "bone", "trees": "none", "dead": 0},
	"caves": {"grass": [], "stones": "basalt", "trees": "none", "dead": 0},
	"hell": {"grass": [], "stones": "basalt", "trees": "none", "dead": 40},
	"docks": {"grass": [Color(0.1, 0.16, 0.07), Color(0.2, 0.24, 0.1), 0.8], "stones": "stone", "trees": "jungle", "dead": 0},
	"spider_forest": {"grass": [Color(0.06, 0.12, 0.06), Color(0.14, 0.2, 0.1), 1.1], "stones": "stone", "trees": "pine", "dead": 110},
	"jungle": {"grass": [Color(0.07, 0.2, 0.05), Color(0.16, 0.32, 0.08), 1.5], "stones": "stone", "trees": "jungle", "dead": 0},
	"drowned_city": {"grass": [Color(0.09, 0.14, 0.07), Color(0.2, 0.22, 0.12), 1.3], "stones": "stone", "trees": "jungle", "dead": 50},
	"travincal": {"grass": [Color(0.08, 0.18, 0.06), Color(0.16, 0.28, 0.09), 1.0], "stones": "stone", "trees": "jungle", "dead": 0},
	"temple": {"grass": [], "stones": "basalt", "trees": "none", "dead": 0},
}

var level: Level
var _rng := RandomNumberGenerator.new()


func build(lvl: Level, keep_clear: Array) -> void:
	level = lvl
	if level.key == "tristram":
		_village(keep_clear)
	else:
		_themed(keep_clear)


## Tristram's clutter, laid out as it always has been.
func _village(keep_clear: Array) -> void:
	_rng.seed = 11
	var tufts: Array = []
	var stones: Array = []
	var c := level.centre()
	var area := Rect2(-30.0, -24.0, 130.0, 90.0)
	var clump := FastNoiseLite.new()
	clump.seed = 13
	clump.frequency = 0.08
	for i in 50000:
		var p := Vector3(_rng.randf_range(area.position.x, area.end.x), 0.0, _rng.randf_range(area.position.y, area.end.y))
		var lane := _lane_weight(p)
		if lane > 0.35 or _cleared(p, keep_clear):
			continue
		if _rng.randf() < lane * 2.0:
			continue
		if _rng.randf() > smoothstep(0.3, 0.7, clump.get_noise_2d(p.x, p.z) * 0.5 + 0.5) + 0.12:
			continue   # grass grows in clumps, with bare earth between
		p.y = level.ground_height(p.x, p.z)
		tufts.append(p)
	for i in 2600:
		var p := Vector3(_rng.randf_range(area.position.x, area.end.x), 0.0, _rng.randf_range(area.position.y, area.end.y))
		if not _cleared(p, keep_clear) and _lane_weight(p) < 0.2:   # a stone on the street looks like a monster
			p.y = level.ground_height(p.x, p.z)
			stones.append(p)
	add_child(_tufts(tufts))
	add_child(_stones(stones))
	add_child(_forest())
	_dead_wood(keep_clear)


func _lane_weight(p: Vector3) -> float:
	var t := level.tile_at(p)
	var w := 0.0
	for dy in range(-1, 2):
		for dx in range(-1, 2):
			if level.cell(t + Vector2i(dx, dy)) == "P":
				var q := level.tile_pos(t + Vector2i(dx, dy))
				w = max(w, 1.0 - Vector2(p.x - q.x, p.z - q.z).length() / 2.6)
	for route in level.routes:   # the approaches outside the grid
		for i in range(0, route.size(), 2):
			var r: Vector3 = route[i]
			var outside := r.x < 0.0 or r.x > level.width * Level.TILE or r.z < 0.0 or r.z > level.height * Level.TILE
			if outside and Vector2(p.x - r.x, p.z - r.z).length() < 3.5:
				w = 1.0
	return w


func _cleared(p: Vector3, keep_clear: Array) -> bool:
	for k in keep_clear:
		var at: Vector3 = k[0]
		if Vector2(p.x - at.x, p.z - at.z).length() < float(k[1]):
			return true
	return false


func _tufts(points: Array, dry_color := Color(0.17, 0.17, 0.08), fresh := Color(0.3, 0.24, 0.12), tall := 1.0) -> MultiMeshInstance3D:
	var mesh := _tuft_mesh()
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = mesh
	mm.instance_count = points.size()
	for i in points.size():
		var s := _rng.randf_range(0.6, 1.4)
		var b := Basis(Vector3.UP, _rng.randf() * TAU).scaled(Vector3(s, s * _rng.randf_range(0.8, 1.3) * tall, s))
		mm.set_instance_transform(i, Transform3D(b, points[i]))
		var dry := _rng.randf()
		mm.set_instance_color(i, dry_color.lerp(fresh, dry))
	var mi := MultiMeshInstance3D.new()
	mi.multimesh = mm
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/grass.gdshader")
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi


## A tuft: a dozen tapering blades leaning out from one root.
func _tuft_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var rng := RandomNumberGenerator.new()
	rng.seed = 3
	for b in 12:
		var a := rng.randf() * TAU
		var lean := rng.randf_range(0.1, 0.45)
		var h := rng.randf_range(0.25, 0.55)
		var w := 0.035
		var dir := Vector3(cos(a), 0, sin(a))
		var side := Vector3(-dir.z, 0, dir.x) * w
		var root := dir * rng.randf_range(0.0, 0.08)
		var tip := root + dir * lean * h + Vector3(0, h, 0)
		st.set_color(Color.WHITE)
		st.set_uv(Vector2(0, 1))
		st.add_vertex(root - side)
		st.set_uv(Vector2(1, 1))
		st.add_vertex(root + side)
		st.set_uv(Vector2(0.5, 0))
		st.add_vertex(tip)
	st.generate_normals()
	return st.commit()


func _stones(points: Array, material := "stone") -> MultiMeshInstance3D:
	var sm := SphereMesh.new()
	sm.radius = 0.12
	sm.height = 0.14
	sm.radial_segments = 7
	sm.rings = 3
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = sm
	mm.instance_count = points.size()
	for i in points.size():
		var s := _rng.randf_range(0.5, 2.2)
		var b := Basis(Vector3(_rng.randf(), 1, _rng.randf()).normalized(), _rng.randf() * TAU).scaled(
			Vector3(s, s * _rng.randf_range(0.4, 0.8), s * _rng.randf_range(0.7, 1.2)))
		mm.set_instance_transform(i, Transform3D(b, points[i]))
	var mi := MultiMeshInstance3D.new()
	mi.multimesh = mm
	mi.material_override = Mats.named(material)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF   # pebbles: their shadows cost four cascades
	return mi


## A dark pine forest on the hills around the village: a silhouette against the burning sky.
func _forest() -> MultiMeshInstance3D:
	var c := level.centre()
	var points: Array = []
	for i in 2400:
		var a := _rng.randf() * TAU
		var r := _rng.randf_range(62.0, 230.0)
		var p := c + Vector3(cos(a) * r * 1.25, 0.0, sin(a) * r)
		if abs(p.z - c.z) < 30.0 and (p.x < -20.0 or p.x > 85.0) and abs(p.x - c.x) < 95.0:
			continue   # keep the portal's field and the cathedral's approach open
		if p.z > c.z and r < 125.0:
			continue   # the cameras look from the south: no trunks in front of the lens
		p.y = level.ground_height(p.x, p.z) - 0.3
		points.append(p)
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = _pine_mesh()
	mm.instance_count = points.size()
	for i in points.size():
		var s := _rng.randf_range(0.7, 1.5)
		var b := Basis(Vector3.UP, _rng.randf() * TAU).scaled(Vector3(s, s * _rng.randf_range(0.9, 1.3), s))
		mm.set_instance_transform(i, Transform3D(b, points[i]))
		mm.set_instance_color(i, Color(0.05, 0.07, 0.05).lerp(Color(0.09, 0.1, 0.07), _rng.randf()))
	var mi := MultiMeshInstance3D.new()
	mi.multimesh = mm
	var m := StandardMaterial3D.new()
	m.vertex_color_use_as_albedo = true
	m.roughness = 0.95
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF   # far beyond the battle; shadows here cost a lot
	return mi


## A pine: a trunk and four stacked, drooping cones, about 11 m tall.
func _pine_mesh() -> ArrayMesh:
	if _pine_mesh_cache != null:
		return _pine_mesh_cache
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	st.set_color(Color.WHITE)
	_cone(st, 0.0, 3.0, 0.25, 0.2, 6)
	var tiers := [[2.0, 5.5, 3.0], [4.0, 7.5, 2.4], [6.0, 9.4, 1.8], [8.0, 11.2, 1.1]]
	for t in tiers:
		_cone(st, t[0], t[1], t[2], 0.0, 9)
	st.generate_normals()
	_pine_mesh_cache = st.commit()
	return _pine_mesh_cache


func _cone(st: SurfaceTool, y0: float, y1: float, r0: float, r1: float, sides: int) -> void:
	for i in sides:
		var a0 := TAU * i / sides
		var a1 := TAU * (i + 1) / sides
		var p0 := Vector3(cos(a0) * r0, y0, sin(a0) * r0)
		var p1 := Vector3(cos(a1) * r0, y0, sin(a1) * r0)
		var q0 := Vector3(cos(a0) * r1, y1, sin(a0) * r1)
		var q1 := Vector3(cos(a1) * r1, y1, sin(a1) * r1)
		st.add_vertex(p0); st.add_vertex(q0); st.add_vertex(p1)
		st.add_vertex(p1); st.add_vertex(q0); st.add_vertex(q1)


## Dead trees in a loose band round the village, between the houses and the pines.
func _dead_wood(keep_clear: Array, count := 70) -> void:
	var c := level.centre()
	var transforms: Array = []
	for i in 600:
		if transforms.size() >= count:
			break
		var p := Vector3(_rng.randf_range(-40.0, 106.0), 0.0, _rng.randf_range(-40.0, 76.0))
		var outside_x: float = max(-p.x, p.x - 66.0)
		var outside_z: float = max(-p.z, p.z - 36.0)
		var out: float = max(outside_x, outside_z)
		if out < 12.0 or out > 40.0 or _cleared(p, keep_clear) or (p.z > c.z and out < 25.0):
			continue
		p.y = level.ground_height(p.x, p.z) - 0.2
		var s := _rng.randf_range(1.2, 2.4)
		var b := Basis(Vector3.UP, _rng.randf() * TAU) * Basis(Vector3.RIGHT, deg_to_rad(_rng.randf_range(-6, 6)))
		transforms.append(Transform3D(b.scaled(Vector3.ONE * s), p))
	var tree := Models.make("dead_tree")
	for node in tree.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		var mesh: Mesh = mi.mesh.duplicate()
		for k in mesh.get_surface_count():
			var m := mi.get_surface_override_material(k)
			if m:
				mesh.surface_set_material(k, m)
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = mesh
		mm.instance_count = transforms.size()
		var local := _relative(mi, tree)
		for k in transforms.size():
			mm.set_instance_transform(k, transforms[k] * local)
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mmi)
	tree.free()


func _relative(node: Node3D, root: Node3D) -> Transform3D:
	var t := node.transform
	var parent := node.get_parent()
	while parent != root and parent is Node3D:
		t = (parent as Node3D).transform * t
		parent = parent.get_parent()
	return t


# --- Every other location ---

func _themed(keep_clear: Array) -> void:
	_rng.seed = hash(level.key) + 11
	var look: Dictionary = GROUND.get(level.theme, GROUND["village"])
	var area := Rect2(-30.0, -24.0, 130.0, 90.0)
	var grass: Array = look["grass"]
	if not grass.is_empty():
		var tufts: Array = []
		var clump := FastNoiseLite.new()
		clump.seed = 13
		clump.frequency = 0.08
		var tries := 70000 if level.theme == "jungle" else 50000
		for i in tries:
			var p := Vector3(_rng.randf_range(area.position.x, area.end.x), 0.0, _rng.randf_range(area.position.y, area.end.y))
			var lane := _lane_weight(p)
			if lane > 0.35 or _cleared(p, keep_clear) or _wet(p):
				continue
			if _rng.randf() < lane * 2.0:
				continue
			if _rng.randf() > smoothstep(0.3, 0.7, clump.get_noise_2d(p.x, p.z) * 0.5 + 0.5) + 0.12:
				continue
			p.y = level.ground_height(p.x, p.z)
			tufts.append(p)
		add_child(_tufts(tufts, grass[0], grass[1], float(grass[2])))
	var stones: Array = []
	for i in 2600:
		var p := Vector3(_rng.randf_range(area.position.x, area.end.x), 0.0, _rng.randf_range(area.position.y, area.end.y))
		if not _cleared(p, keep_clear) and _lane_weight(p) < 0.2 and not _wet(p):
			p.y = level.ground_height(p.x, p.z)
			stones.append(p)
	add_child(_stones(stones, String(look["stones"])))
	match String(look["trees"]):
		"pine":
			add_child(_ring_of(_pine_mesh(), 2400, 0.7, 1.5, Color(0.05, 0.07, 0.05), Color(0.09, 0.1, 0.07),
				42.0 if level.theme == "spider_forest" else 62.0))
		"jungle":
			add_child(_ring_of(palm_mesh(), 900, 0.9, 1.6, Color(0.7, 0.8, 0.7), Color(1.0, 1.0, 0.9), 48.0))
			add_child(_ring_of(broadleaf_mesh(), 1100, 0.9, 1.7, Color(0.6, 0.75, 0.6), Color(1.0, 1.0, 0.9), 52.0))
	if int(look["dead"]) > 0:
		_dead_wood(keep_clear, int(look["dead"]))


## Under water or lava: the land's basins where the theme floods them.
func _wet(p: Vector3) -> bool:
	return level.cell(level.tile_at(p)) == "~" or level.ground_height(p.x, p.z) < -0.25


## A forest of `mesh` on the land round the field from `inner` metres out: none in front of the battle camera,
## none on the roads in from the portals or before the sanctuary, none in the water.
func _ring_of(mesh: Mesh, count: int, smallest: float, largest: float, dark: Color, light: Color, inner: float) -> MultiMeshInstance3D:
	var c := level.centre()
	var gates: Array = level.portals.duplicate()
	gates.append(level.door_pos + level.door_outward() * 14.0)
	var points: Array = []
	for i in count:
		var a := _rng.randf() * TAU
		var r := _rng.randf_range(inner, 230.0)
		var p := c + Vector3(cos(a) * r * 1.25, 0.0, sin(a) * r)
		if p.z > c.z and r < 125.0:
			continue   # the cameras look from the south: no trunks in front of the lens
		if gates.any(func(g): return Vector2(p.x - g.x, p.z - g.z).length() < 26.0) or _wet(p):
			continue
		p.y = level.ground_height(p.x, p.z) - 0.3
		points.append(p)
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = mesh
	mm.instance_count = points.size()
	for i in points.size():
		var s := _rng.randf_range(smallest, largest)
		var b := Basis(Vector3.UP, _rng.randf() * TAU).scaled(Vector3(s, s * _rng.randf_range(0.9, 1.3), s))
		mm.set_instance_transform(i, Transform3D(b, points[i]))
		mm.set_instance_color(i, dark.lerp(light, _rng.randf()))
	var mi := MultiMeshInstance3D.new()
	mi.multimesh = mm
	if mesh == _pine_mesh_cache:
		var m := StandardMaterial3D.new()
		m.vertex_color_use_as_albedo = true
		m.roughness = 0.95
		mi.material_override = m
	else:
		mi.material_override = foliage_material()
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi


static var _pine_mesh_cache: ArrayMesh
static var _palm: ArrayMesh
static var _broadleaf: ArrayMesh
static var _foliage: StandardMaterial3D


## Leaves and bark coloured by their vertices, both sides of a frond lit.
static func foliage_material() -> StandardMaterial3D:
	if _foliage == null:
		_foliage = StandardMaterial3D.new()
		_foliage.vertex_color_use_as_albedo = true
		_foliage.cull_mode = BaseMaterial3D.CULL_DISABLED
		_foliage.roughness = 0.8
		# clumps of leaves over the crowns' facets, from cellular noise mapped from the world
		var fn := FastNoiseLite.new()
		fn.noise_type = FastNoiseLite.TYPE_CELLULAR
		fn.frequency = 0.06
		fn.cellular_return_type = FastNoiseLite.RETURN_DISTANCE2_SUB
		var leaves := NoiseTexture2D.new()
		leaves.seamless = true
		leaves.width = 256
		leaves.height = 256
		leaves.noise = fn
		var ramp := Gradient.new()
		ramp.colors = PackedColorArray([Color(0.35, 0.35, 0.35), Color(1.6, 1.6, 1.6)])
		leaves.color_ramp = ramp
		_foliage.albedo_texture = leaves
		var bumps := NoiseTexture2D.new()
		bumps.seamless = true
		bumps.width = 256
		bumps.height = 256
		bumps.noise = fn
		bumps.as_normal_map = true
		bumps.bump_strength = 6.0
		_foliage.normal_enabled = true
		_foliage.normal_texture = bumps
		_foliage.uv1_triplanar = true
		_foliage.uv1_world_triplanar = true
		_foliage.uv1_scale = Vector3.ONE * 0.9
	return _foliage


## A palm about 9 m tall: a leaning, ringed trunk and a crown of drooping fronds.
static func palm_mesh() -> ArrayMesh:
	if _palm == null:
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		var bark := Color(0.12, 0.1, 0.07)
		var lean := Vector3(0.9, 0.0, 0.3)
		var prev := Vector3.ZERO
		for k in 8:
			var t0 := k / 8.0
			var t1 := (k + 1) / 8.0
			var a := lean * t0 * t0 + Vector3(0, t0 * 8.5, 0)
			var b := lean * t1 * t1 + Vector3(0, t1 * 8.5, 0)
			_tube(st, a, b, lerp(0.28, 0.17, t0), lerp(0.28, 0.17, t1), 6, bark.lightened(0.08 * (k % 2)))
			prev = b
		var leaf := Color(0.04, 0.09, 0.03)
		for f in 9:
			var dir := Vector3(cos(TAU * f / 9.0 + 0.3), 0, sin(TAU * f / 9.0 + 0.3))
			var side := Vector3(-dir.z, 0, dir.x)
			var last := prev
			for k in 6:
				var t := (k + 1) / 6.0
				var p := prev + dir * t * 3.6 + Vector3(0, 0.9 * t - 2.6 * t * t, 0)
				var w0 := sin(PI * (k / 6.0)) * 0.55 + 0.05
				var w1 := sin(PI * t) * 0.55 + 0.05
				_leaf_quad(st, last - side * w0, last + side * w0, p + side * w1, p - side * w1, leaf.lightened(0.05 * (f % 3)))
				last = p
		st.generate_normals()
		_palm = st.commit()
	return _palm


## A broad tree about 10 m tall: a trunk forking into a few boughs, each under a lumpy mass of leaves.
static func broadleaf_mesh() -> ArrayMesh:
	if _broadleaf == null:
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		var bark := Color(0.11, 0.09, 0.07)
		_tube(st, Vector3.ZERO, Vector3(0, 5.0, 0), 0.45, 0.32, 7, bark)
		var fn := FastNoiseLite.new()
		fn.frequency = 0.6
		var crowns := [Vector3(1.8, 7.5, 0.4), Vector3(-1.5, 8.0, -0.8), Vector3(0.2, 9.2, 1.4), Vector3(-0.3, 8.6, -0.2)]
		for i in crowns.size():
			var c: Vector3 = crowns[i]
			_tube(st, Vector3(0, 4.6, 0), c - Vector3(0, 1.0, 0), 0.25, 0.12, 5, bark)
			var sphere := SphereMesh.new()
			sphere.radius = 2.4 - 0.25 * i
			sphere.height = (2.4 - 0.25 * i) * 1.4
			sphere.radial_segments = 9
			sphere.rings = 5
			var arrays := sphere.get_mesh_arrays()
			var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
			for k in range(0, idx.size(), 3):
				var shade := 0.6 + 0.4 * fn.get_noise_3dv(verts[idx[k]] * 3.0 + c) + 0.25 * sin(k * 12.9898)
				var leaf := Color(0.035, 0.075 + 0.012 * i, 0.03) * shade
				for j in 3:
					var v := verts[idx[k + j]]
					v *= 1.0 + 0.3 * fn.get_noise_3dv(v + c)
					st.set_color(leaf)
					st.add_vertex(c + v)
		st.generate_normals()
		_broadleaf = st.commit()
	return _broadleaf


static func _tube(st: SurfaceTool, a: Vector3, b: Vector3, ra: float, rb: float, sides: int, color: Color) -> void:
	for i in sides:
		var a0 := TAU * i / sides
		var a1 := TAU * (i + 1) / sides
		var p0 := a + Vector3(cos(a0) * ra, 0, sin(a0) * ra)
		var p1 := a + Vector3(cos(a1) * ra, 0, sin(a1) * ra)
		var q0 := b + Vector3(cos(a0) * rb, 0, sin(a0) * rb)
		var q1 := b + Vector3(cos(a1) * rb, 0, sin(a1) * rb)
		for p in [p0, q0, p1, p1, q0, q1]:
			st.set_color(color)
			st.add_vertex(p)


static func _leaf_quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3, color: Color) -> void:
	for p in [a, b, c, a, c, d]:
		st.set_color(color)
		st.add_vertex(p)
