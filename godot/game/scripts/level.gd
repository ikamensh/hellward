class_name Level
extends Node3D
## The battlefield: the server's grid (the battle message) laid out in metres, its floor, its routes as world
## paths, and where a monster stands at a distance `s` along its route. One map tile is TILE metres; a point
## (x, y) of the rules, in tiles, is (x * TILE, y * TILE) here.

const TILE := 2.0
const MASK_ORIGIN := Vector2(-24.0, -14.0)   # the floor mask covers the field and its approaches
const MASK_SIZE := Vector2(116.0, 64.0)
const APPROACH := 9.0                        # metres from the map's edge to a portal and to the sanctuary's door

var data: Dictionary
var key := ""
var theme := ""
var width: int
var height: int
var grid: PackedStringArray
var routes: Array = []        # Array of PackedVector3Array, portal to sanctuary, in metres, corners rounded (the look)
var route_keys: Array = []
var portal_pos: Vector3       # the first route's portal; `portals` holds every entrance's
var portals: Array = []       # Vector3, one per entrance
var door_pos: Vector3
var arches: Array = []        # [index, tile Vector2i]: the gate sockets
var _paths := {}              # route key -> {"pts": PackedVector3Array (the rules' polyline, metres), "cum": lengths}
var pads: Array = []           # [Vector2 centre, radius, height]: levelled plots for buildings on the slopes
var _road: PackedFloat32Array   # metres to the nearest route centre line, a sample per metre over the floor mask
var _hills := FastNoiseLite.new()


## Lay out a battle from the server's message (or a location exported to res://data/<key>.json, for previews).
func load_battle(battle: Dictionary) -> void:
	data = battle
	_hills.seed = 7
	_hills.frequency = 0.012
	key = String(battle["location"]["key"]) if battle.has("location") else String(battle["key"])
	theme = String(battle["location"]["theme"]) if battle.has("location") else "village"
	width = int(battle["width"])
	height = int(battle["height"])
	grid = PackedStringArray(battle["grid"])
	var seen := {}
	for r in battle["routes"]:
		var pts: Array = r["points"]
		var entry := Vector2i(int(pts[0][0]), int(pts[0][1]))
		if not seen.has(entry):
			seen[entry] = true
			portals.append(tile_pos(entry) + _outward(entry) * APPROACH)
	var first: Array = battle["routes"][0]["points"]
	var last: Array = first[first.size() - 1]
	var exit := Vector2i(int(last[0]), int(last[1]))
	portal_pos = portals[0]
	door_pos = tile_pos(exit) + _outward(exit) * APPROACH
	for r in battle["routes"]:
		route_keys.append(String(r["key"]))
		routes.append(_route_path(r["points"]))
		var cum := PackedFloat32Array([0.0])
		var pts: Array = r["points"]
		for i in range(1, pts.size()):
			var a := Vector2(float(pts[i - 1][0]), float(pts[i - 1][1]))
			cum.append(cum[i - 1] + a.distance_to(Vector2(float(pts[i][0]), float(pts[i][1]))) * TILE)
		var look: PackedVector3Array = routes[routes.size() - 1]
		var look_cum := PackedFloat32Array([0.0])
		for i in range(1, look.size()):
			look_cum.append(look_cum[i - 1] + look[i].distance_to(look[i - 1]))
		_paths[String(r["key"])] = {"cum": cum, "look": look, "look_cum": look_cum}
	for d in battle.get("doors", []):
		arches.append([int(d["index"]), Vector2i(int(d["tile"][0]), int(d["tile"][1]))])
	_road = _road_field()


func load_location(location: String) -> void:
	load_battle(JSON.parse_string(FileAccess.get_file_as_string("res://data/%s.json" % location)))


## Away from the field, at an edge tile: where its portal or the sanctuary stands.
func _outward(t: Vector2i) -> Vector3:
	if t.x <= 0:
		return Vector3(-1, 0, 0)
	if t.x >= width - 1:
		return Vector3(1, 0, 0)
	if t.y <= 0:
		return Vector3(0, 0, -1)
	return Vector3(0, 0, 1)


## Where a monster `s` tiles along `route` stands, pushed `lateral` metres to its side: on the route's rounded
## look, at the same fraction of its length as the rules' polyline (corners are cut a little, never the reach).
## Below 0 it is still in the portal's approach, past the route's length on the steps to the sanctuary's door.
func place(route: String, s: float, lateral: float) -> Vector3:
	var p: Dictionary = _paths[route]
	var cum: PackedFloat32Array = p["cum"]
	return _along(p["look"], p["look_cum"], s * TILE / cum[cum.size() - 1], lateral)


## A route's length in the rules' tiles.
func route_length(route: String) -> float:
	var cum: PackedFloat32Array = _paths[route]["cum"]
	return cum[cum.size() - 1] / TILE


## The route's look from its portal to the sanctuary's door, as a fraction 0..1 of the rules' part of it: the
## approach from the portal and on to the door lie outside 0..1.
static func _along(look: PackedVector3Array, lengths: PackedFloat32Array, f: float, lateral: float) -> Vector3:
	var total := lengths[lengths.size() - 1]
	# the look includes the approaches: the rules' route spans from APPROACH to total - APPROACH
	var d: float = APPROACH + f * (total - 2.0 * APPROACH)
	var i := lengths.bsearch(d) - 1
	i = clamp(i, 0, look.size() - 2)
	var seg := lengths[i + 1] - lengths[i]
	var t: float = 0.0 if seg <= 0.0 else clamp((d - lengths[i]) / seg, 0.0, 1.0)
	var a := look[i]
	var b := look[i + 1]
	var dir := (b - a).normalized()
	var side := Vector3(-dir.z, 0, dir.x)
	var squeeze: float = clamp(min(d, total - d) / 8.0, 0.0, 1.0)   # no wandering in a portal's mouth or the door
	return a.lerp(b, t) + side * lateral * squeeze


## A point of the rules, in tiles, on the ground here.
static func point(xy: Array) -> Vector3:
	return Vector3(float(xy[0]) * TILE, 0.0, float(xy[1]) * TILE)


## Distance to the nearest route centre line at every metre of the floor mask.
func _road_field() -> PackedFloat32Array:
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
	return road


func tile_pos(t: Vector2i) -> Vector3:
	return Vector3(t.x * TILE + TILE * 0.5, 0.0, t.y * TILE + TILE * 0.5)


func tile_at(p: Vector3) -> Vector2i:
	return Vector2i(floori(p.x / TILE), floori(p.z / TILE))


func cell(t: Vector2i) -> String:
	if t.x < 0 or t.y < 0 or t.x >= width or t.y >= height:
		return "#"
	return grid[t.y][t.x]


## Bare floor: where a tower may stand, as far as the map says (the server decides).
func buildable(t: Vector2i) -> bool:
	return cell(t) == "."


func centre() -> Vector3:
	return Vector3(width * TILE * 0.5, 0.0, height * TILE * 0.5)


## A route through tile centres, led in from the portal and on into the cathedral, its corners rounded.
func _route_path(points: Array) -> PackedVector3Array:
	var raw := PackedVector3Array()
	var entry := Vector2i(int(points[0][0]), int(points[0][1]))
	raw.append(tile_pos(entry) + _outward(entry) * APPROACH)
	for p in points:
		raw.append(tile_pos(Vector2i(int(p[0]), int(p[1]))))
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
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	var court := Rect2(door_pos.x - 9.0, door_pos.z - 7.0, 13.0, 14.0)
	for y in h:
		for x in w:
			var world_xz := Vector2(x + 0.5, y + 0.5) + MASK_ORIGIN
			var d := _road[y * w + x]
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


## The cathedral's steps under a monster walking up to the door: 0 at their foot, 0.54 m at the threshold.
func step_height(p: Vector3) -> float:
	if abs(p.z - door_pos.z) > 4.5:
		return 0.0
	return clamp((p.x - (door_pos.x - 3.6)) / 3.6, 0.0, 1.0) * 0.54


## How far `p` is from the nearest route's centre line (metres; the streets are about 2.6 m to each side).
func road_distance(p: Vector3) -> float:
	var x := int(p.x - MASK_ORIGIN.x)
	var y := int(p.z - MASK_ORIGIN.y)
	if x < 0 or y < 0 or x >= int(MASK_SIZE.x) or y >= int(MASK_SIZE.y):
		return 99.0
	return _road[y * int(MASK_SIZE.x) + x]


## Ground height: flat on the field and its approaches, rolling into low hills beyond and climbing into a
## ring of hills that closes the horizon; levelled where a pad holds a building.
func ground_height(x: float, z: float) -> float:
	var h := _terrain(x, z)
	for pad in pads:
		var k := 1.0 - smoothstep(float(pad[1]), float(pad[1]) + 4.0, Vector2(x, z).distance_to(pad[0]))
		h = lerp(h, float(pad[2]), k)
	return h


## Level a plot of `radius` metres at (x, z) and return its height.
func pad(x: float, z: float, radius: float) -> float:
	var y := _terrain(x, z)
	pads.append([Vector2(x, z), radius, y])
	return y


func _terrain(x: float, z: float) -> float:
	var c := centre()
	var dx: float = max(abs(x - c.x) - width * TILE * 0.5 - 6.0, 0.0)
	var dz: float = max(abs(z - c.z) - height * TILE * 0.5 - 4.0, 0.0)
	var d := sqrt(dx * dx + dz * dz)
	var rise: float = clamp(d / 30.0, 0.0, 1.0)
	var near := rise * rise * (6.0 + 9.0 * _hills.get_noise_2d(x, z)) + rise * 3.0 * _hills.get_noise_2d(x * 3.0, z * 3.0)
	var ring: float = clamp((d - 60.0) / 140.0, 0.0, 1.0)
	return near + ring * ring * (26.0 + 18.0 * _hills.get_noise_2d(x * 0.5, z * 0.5))


func build_floor(scorch_points: Array) -> MeshInstance3D:
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
			st.add_vertex(Vector3(x, ground_height(x, z), z))
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
