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
	for i in 26000:
		var p := Vector3(_rng.randf_range(area.position.x, area.end.x), 0.0, _rng.randf_range(area.position.y, area.end.y))
		var lane := _lane_weight(p)
		if lane > 0.35 or _cleared(p, keep_clear):
			continue
		if _rng.randf() < lane * 2.0:
			continue
		tufts.append(p)
	for i in 2600:
		var p := Vector3(_rng.randf_range(area.position.x, area.end.x), 0.0, _rng.randf_range(area.position.y, area.end.y))
		if not _cleared(p, keep_clear):
			stones.append(p)
	add_child(_tufts(tufts))
	add_child(_stones(stones))


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
	return mi
