class_name Scatter
extends Node3D
## Ground clutter: dry grass tufts swaying in the wind off the lanes, and stones everywhere, as MultiMeshes.

var level: Level
var _rng := RandomNumberGenerator.new()


func build(lvl: Level, keep_clear: Array) -> void:
	level = lvl
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
			if (r.x < 0.0 or r.x > level.width * Level.TILE) and Vector2(p.x - r.x, p.z - r.z).length() < 3.5:
				w = 1.0
	return w


func _cleared(p: Vector3, keep_clear: Array) -> bool:
	for k in keep_clear:
		var at: Vector3 = k[0]
		if Vector2(p.x - at.x, p.z - at.z).length() < float(k[1]):
			return true
	return false


func _tufts(points: Array) -> MultiMeshInstance3D:
	var mesh := _tuft_mesh()
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = mesh
	mm.instance_count = points.size()
	for i in points.size():
		var s := _rng.randf_range(0.6, 1.4)
		var b := Basis(Vector3.UP, _rng.randf() * TAU).scaled(Vector3(s, s * _rng.randf_range(0.8, 1.3), s))
		mm.set_instance_transform(i, Transform3D(b, points[i]))
		var dry := _rng.randf()
		mm.set_instance_color(i, Color(0.17, 0.17, 0.08).lerp(Color(0.3, 0.24, 0.12), dry))
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


func _stones(points: Array) -> MultiMeshInstance3D:
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
	mi.material_override = Mats.named("stone")
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
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	st.set_color(Color.WHITE)
	_cone(st, 0.0, 3.0, 0.25, 0.2, 6)
	var tiers := [[2.0, 5.5, 3.0], [4.0, 7.5, 2.4], [6.0, 9.4, 1.8], [8.0, 11.2, 1.1]]
	for t in tiers:
		_cone(st, t[0], t[1], t[2], 0.0, 9)
	st.generate_normals()
	return st.commit()


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
func _dead_wood(keep_clear: Array) -> void:
	var c := level.centre()
	var transforms: Array = []
	for i in 600:
		if transforms.size() >= 70:
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
