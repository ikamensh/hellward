class_name Level
extends Node3D
## The battlefield: the 2D game's grid (game/data/<key>.json) laid out in metres, its floor, its routes as
## world paths, and the questions the rules ask of it (is a tile buildable, where is a tile).

const TILE := 2.0
const MASK_ORIGIN := Vector2(-24.0, -14.0)   # the floor mask covers the field and its approaches
const MASK_SIZE := Vector2(116.0, 64.0)

var data: Dictionary
var width: int
var height: int
var grid: PackedStringArray
var routes: Array = []        # Array of PackedVector3Array, portal to sanctuary, in metres
var portal_pos: Vector3
var door_pos: Vector3
var occupied: Dictionary = {}  # Vector2i -> true where a tower stands


func load_location(key: String) -> void:
	var text := FileAccess.get_file_as_string("res://data/%s.json" % key)
	data = JSON.parse_string(text)
	width = int(data["width"])
	height = int(data["height"])
	grid = PackedStringArray(data["grid"])
	var first: Array = data["routes"][0]["points"]
	var last: Array = first[first.size() - 1]
	portal_pos = tile_pos(Vector2i(first[0][0], first[0][1])) + Vector3(-9.0, 0, 0)
	door_pos = tile_pos(Vector2i(last[0], last[1])) + Vector3(9.0, 0, 0)
	for r in data["routes"]:
		routes.append(_route_path(r["points"]))


func tile_pos(t: Vector2i) -> Vector3:
	return Vector3(t.x * TILE + TILE * 0.5, 0.0, t.y * TILE + TILE * 0.5)


func tile_at(p: Vector3) -> Vector2i:
	return Vector2i(floori(p.x / TILE), floori(p.z / TILE))


func cell(t: Vector2i) -> String:
	if t.x < 0 or t.y < 0 or t.x >= width or t.y >= height:
		return "#"
	return grid[t.y][t.x]


func buildable(t: Vector2i) -> bool:
	return cell(t) == "." and not occupied.has(t)


func centre() -> Vector3:
	return Vector3(width * TILE * 0.5, 0.0, height * TILE * 0.5)


## A route through tile centres, led in from the portal and on into the cathedral, its corners rounded.
func _route_path(points: Array) -> PackedVector3Array:
	var raw := PackedVector3Array()
	raw.append(portal_pos)
	for p in points:
		raw.append(tile_pos(Vector2i(p[0], p[1])))
	raw.append(door_pos)
	# Chaikin corner cutting, twice: lanes curve instead of kinking
	for _pass in 2:
		var cut := PackedVector3Array()
		cut.append(raw[0])
		for i in raw.size() - 1:
			var a := raw[i]
			var b := raw[i + 1]
			if i > 0:
				cut.append(a.lerp(b, 0.25))
			if i < raw.size() - 2:
				cut.append(a.lerp(b, 0.75))
		cut.append(raw[raw.size() - 1])
		raw = cut
	return raw


## The floor mask, a pixel per metre, smoothed: r = the cobbled street along each route (5 m wide, room for
## the monsters' wander), g = trampled mud (the rest of the 2D game's monster halls, the verges), b = scorch,
## a = the cathedral's flagstone forecourt.
func floor_mask(scorch_points: Array) -> ImageTexture:
	var w := int(MASK_SIZE.x)
	var h := int(MASK_SIZE.y)
	var road := PackedFloat32Array()
	road.resize(w * h)
	road.fill(99.0)
	for route in routes:
		for i in route.size() - 1:
			var n := int(ceil(route[i].distance_to(route[i + 1]) / 0.5))
			for k in n:
				var q: Vector3 = route[i].lerp(route[i + 1], float(k) / n)
				var c := Vector2(q.x - MASK_ORIGIN.x, q.z - MASK_ORIGIN.y)
				for y in range(int(c.y) - 6, int(c.y) + 7):
					for x in range(int(c.x) - 6, int(c.x) + 7):
						if x >= 0 and y >= 0 and x < w and y < h:
							road[y * w + x] = min(road[y * w + x], Vector2(x + 0.5, y + 0.5).distance_to(c))
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	var court := Rect2(door_pos.x - 9.0, door_pos.z - 7.0, 13.0, 14.0)
	for y in h:
		for x in w:
			var world_xz := Vector2(x + 0.5, y + 0.5) + MASK_ORIGIN
			var d := road[y * w + x]
			var t := tile_at(Vector3(world_xz.x, 0, world_xz.y))
			var lane := 1.0 - smoothstep(2.2, 3.0, d)
			var mud: float = max(0.55 if cell(t) == "P" else 0.0, 1.0 - smoothstep(3.0, 5.5, d))
			var flag := 0.0
			if court.has_point(world_xz) or (world_xz.x > door_pos.x - 16.0 and abs(world_xz.y - door_pos.z) < 1.6):
				flag = 1.0
			img.set_pixel(x, y, Color(lane, mud, 0.0, flag))
	for sp in scorch_points:
		var at: Vector3 = sp[0]
		var radius: float = sp[1]
		var c := Vector2(at.x - MASK_ORIGIN.x, at.z - MASK_ORIGIN.y)
		for y in range(int(c.y - radius) - 1, int(c.y + radius) + 2):
			for x in range(int(c.x - radius) - 1, int(c.x + radius) + 2):
				if x < 0 or y < 0 or x >= w or y >= h:
					continue
				var k: float = clamp(1.0 - Vector2(x + 0.5, y + 0.5).distance_to(c) / radius, 0.0, 1.0)
				var px := img.get_pixel(x, y)
				px.b = max(px.b, k)
				px.g = max(px.g, k * 0.8)
				img.set_pixel(x, y, px)
	img.resize(w * 4, h * 4, Image.INTERPOLATE_CUBIC)
	return ImageTexture.create_from_image(img)


## Ground height: flat on the field and its approaches, rolling into low hills beyond.
func ground_height(x: float, z: float, noise: FastNoiseLite) -> float:
	var c := centre()
	var dx: float = max(abs(x - c.x) - width * TILE * 0.5 - 6.0, 0.0)
	var dz: float = max(abs(z - c.z) - height * TILE * 0.5 - 4.0, 0.0)
	var d := sqrt(dx * dx + dz * dz)
	var rise: float = clamp(d / 30.0, 0.0, 1.0)
	var near := rise * rise * (6.0 + 9.0 * noise.get_noise_2d(x, z)) + rise * 3.0 * noise.get_noise_2d(x * 3.0, z * 3.0)
	# far off, the land climbs into a ring of hills that closes the horizon
	var ring: float = clamp((d - 60.0) / 140.0, 0.0, 1.0)
	return near + ring * ring * (26.0 + 18.0 * noise.get_noise_2d(x * 0.5, z * 0.5))


func build_floor(scorch_points: Array) -> MeshInstance3D:
	var noise := FastNoiseLite.new()
	noise.seed = 7
	noise.frequency = 0.012
	var c := centre()
	var size := Vector2(640.0, 520.0)
	var steps := Vector2i(256, 208)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var origin := Vector2(c.x - size.x * 0.5, c.z - size.y * 0.5)
	for j in steps.y + 1:
		for i in steps.x + 1:
			var x := origin.x + size.x * i / steps.x
			var z := origin.y + size.y * j / steps.y
			st.set_uv(Vector2(x, z))
			st.add_vertex(Vector3(x, ground_height(x, z, noise), z))
	for j in steps.y:
		for i in steps.x:
			var a := j * (steps.x + 1) + i
			var b := a + 1
			var d := a + steps.x + 1
			var e := d + 1
			st.add_index(a); st.add_index(b); st.add_index(d)
			st.add_index(b); st.add_index(e); st.add_index(d)
	st.generate_normals()
	st.generate_tangents()
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/ground.gdshader")
	mat.set_shader_parameter("mask", floor_mask(scorch_points))
	mat.set_shader_parameter("mask_rect", Vector4(MASK_ORIGIN.x, MASK_ORIGIN.y, MASK_SIZE.x, MASK_SIZE.y))
	var nt := NoiseTexture2D.new()
	nt.seamless = true
	nt.width = 256
	nt.height = 256
	var fn := FastNoiseLite.new()
	fn.frequency = 0.02
	nt.noise = fn
	mat.set_shader_parameter("noise", nt)
	var tex := "res://assets/textures/"
	mat.set_shader_parameter("cob_a", load(tex + "cobbles_albedo.png"))
	mat.set_shader_parameter("cob_n", load(tex + "cobbles_normal.png"))
	mat.set_shader_parameter("cob_h", load(tex + "cobbles_height.png"))
	mat.set_shader_parameter("earth_a", load(tex + "earth_albedo.png"))
	mat.set_shader_parameter("earth_n", load(tex + "earth_normal.png"))
	mat.set_shader_parameter("grass_a", load(tex + "grass_albedo.png"))
	mat.set_shader_parameter("grass_n", load(tex + "grass_normal.png"))
	mat.set_shader_parameter("flag_a", load(tex + "flagstones_albedo.png"))
	mat.set_shader_parameter("flag_n", load(tex + "flagstones_normal.png"))
	mat.set_shader_parameter("portal_xz", Vector2(portal_pos.x, portal_pos.z))
	mi.material_override = mat
	mi.name = "Floor"
	add_child(mi)
	return mi
