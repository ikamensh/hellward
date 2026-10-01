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


## The floor mask: r = lane, g = bare earth, b = scorch; drawn a pixel per metre, then smoothed.
func floor_mask(scorch_points: Array) -> ImageTexture:
	var w := int(MASK_SIZE.x / TILE)
	var h := int(MASK_SIZE.y / TILE)
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 1))
	var ox := int(-MASK_ORIGIN.x / TILE)
	var oz := int(-MASK_ORIGIN.y / TILE)
	for y in h:
		for x in w:
			var t := Vector2i(x - ox, y - oz)
			var c := cell(t)
			var lane := 1.0 if c == "P" else 0.0
			var earth := 0.0
			for dy in range(-2, 3):
				for dx in range(-2, 3):
					if cell(t + Vector2i(dx, dy)) == "P":
						earth = max(earth, 0.6 - 0.12 * (abs(dx) + abs(dy)))
			img.set_pixel(x, y, Color(lane, earth, 0.0, 1.0))
	# the approaches outside the grid: from the portal and on to the cathedral door
	for route in routes:
		for p in route:
			var t := tile_at(p)
			if cell(t) == "#" and (t.x < 0 or t.x >= width):
				for dy in range(-1, 2):
					var q := Vector2i(t.x + ox, t.y + oz + dy)
					if q.x >= 0 and q.y >= 0 and q.x < w and q.y < h:
						img.set_pixel(q.x, q.y, Color(1.0, 0.8, 0.0, 1.0))
	for s in scorch_points:
		var sp: Vector3 = s[0]
		var radius: float = s[1]
		var c := Vector2((sp.x - MASK_ORIGIN.x) / TILE, (sp.z - MASK_ORIGIN.y) / TILE)
		var r := radius / TILE
		for y in range(int(c.y - r) - 1, int(c.y + r) + 2):
			for x in range(int(c.x - r) - 1, int(c.x + r) + 2):
				if x < 0 or y < 0 or x >= w or y >= h:
					continue
				var k: float = clamp(1.0 - Vector2(x + 0.5, y + 0.5).distance_to(c) / r, 0.0, 1.0)
				var px := img.get_pixel(x, y)
				px.b = max(px.b, k)
				px.g = max(px.g, k * 0.8)
				img.set_pixel(x, y, px)
	img.resize(w * 8, h * 8, Image.INTERPOLATE_CUBIC)
	return ImageTexture.create_from_image(img)


## Ground height: flat on the field and its approaches, rolling into low hills beyond.
func ground_height(x: float, z: float, noise: FastNoiseLite) -> float:
	var c := centre()
	var dx: float = max(abs(x - c.x) - width * TILE * 0.5 - 6.0, 0.0)
	var dz: float = max(abs(z - c.z) - height * TILE * 0.5 - 4.0, 0.0)
	var d := sqrt(dx * dx + dz * dz)
	var rise: float = clamp(d / 30.0, 0.0, 1.0)
	return rise * rise * (6.0 + 9.0 * noise.get_noise_2d(x, z)) + rise * 3.0 * noise.get_noise_2d(x * 3.0, z * 3.0)


func build_floor(scorch_points: Array) -> MeshInstance3D:
	var noise := FastNoiseLite.new()
	noise.seed = 7
	noise.frequency = 0.012
	var c := centre()
	var size := Vector2(320.0, 240.0)
	var steps := Vector2i(160, 120)
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
	mi.material_override = mat
	mi.name = "Floor"
	add_child(mi)
	return mi
