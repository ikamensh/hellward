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


## Lay out a battle from the server's message.
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


## The floor of every location but Tristram (which keeps the village's own shaders/ground.gdshader), by theme:
## [texture, tint, metres per repeat] for the lanes the monsters walk, their verges, the rest of the ground and the
## sanctuary's forecourt, and `cliff` (if given) for the land where it climbs steeply; `wet` puddles the ruts and
## verges, `cracks` glows through all the ground, `land` shapes what lies beyond the field (hills, flat floor,
## cave walls, a shore, a sunken swamp, hell's lava basins).
const FLOORS := {
	"village": {"lane": ["cobbles", Color(0.62, 0.58, 0.54), 1.4], "mud": ["earth", Color(1, 1, 1), 5.0],
		"outer": ["grass", Color(1, 1, 1), 4.0], "court": ["flagstones", Color(0.85, 0.82, 0.78), 3.0],
		"wet": 1.0, "cracks": 0.0, "land": "hills"},
	"graveyard": {"lane": ["cobbles", Color(0.6, 0.62, 0.66), 1.5], "mud": ["earth", Color(0.62, 0.62, 0.62), 5.0],
		"outer": ["grass", Color(0.55, 0.64, 0.55), 4.0], "court": ["flagstones", Color(0.75, 0.78, 0.82), 3.0],
		"wet": 0.8, "cracks": 0.0, "land": "hills"},
	"cathedral": {"lane": ["flagstones", Color(0.9, 0.86, 0.8), 2.6], "mud": ["flagstones", Color(0.55, 0.52, 0.5), 3.2],
		"outer": ["stone", Color(0.5, 0.47, 0.45), 2.4], "court": ["basalt", Color(0.85, 0.8, 0.75), 3.0],
		"wet": 0.35, "cracks": 0.0, "land": "flat"},
	"catacombs": {"lane": ["flagstones", Color(0.82, 0.78, 0.72), 2.4], "mud": ["earth", Color(0.42, 0.4, 0.38), 4.0],
		"outer": ["stone", Color(0.4, 0.38, 0.36), 2.2], "court": ["flagstones", Color(0.6, 0.58, 0.55), 3.0],
		"cliff": ["stone", Color(0.45, 0.43, 0.42), 4.0], "wet": 0.25, "cracks": 0.0, "land": "cave"},
	"caves": {"lane": ["earth", Color(1.45, 1.15, 0.9), 4.0], "mud": ["earth", Color(0.85, 0.72, 0.6), 5.0],
		"outer": ["basalt", Color(0.95, 0.82, 0.75), 6.0], "court": ["flagstones", Color(0.6, 0.55, 0.5), 3.0],
		"cliff": ["stone", Color(0.5, 0.42, 0.38), 5.0],
		"wet": 0.0, "cracks": 0.0, "land": "cave"},
	"hell": {"lane": ["basalt", Color(1.25, 1.12, 1.05), 3.0], "mud": ["basalt", Color(0.5, 0.42, 0.4), 4.0],
		"outer": ["demon_skin", Color(0.42, 0.24, 0.2), 4.0], "court": ["basalt", Color(0.8, 0.7, 0.65), 2.5],
		"cliff": ["basalt", Color(0.5, 0.42, 0.4), 5.0],
		"wet": 0.0, "cracks": 1.0, "land": "hell"},
	"docks": {"lane": ["planks", Color(0.72, 0.62, 0.52), 2.5], "mud": ["cobbles", Color(0.5, 0.5, 0.5), 1.6],
		"outer": ["flagstones", Color(0.6, 0.64, 0.66), 3.0], "court": ["flagstones", Color(0.75, 0.75, 0.75), 3.0],
		"wet": 1.6, "cracks": 0.0, "land": "shore"},
	"spider_forest": {"lane": ["earth", Color(0.95, 0.88, 0.78), 4.0], "mud": ["earth", Color(0.6, 0.6, 0.55), 5.0],
		"outer": ["grass", Color(0.45, 0.6, 0.42), 4.0], "court": ["flagstones", Color(0.6, 0.7, 0.6), 3.0],
		"wet": 0.9, "cracks": 0.0, "land": "hills"},
	"jungle": {"lane": ["earth", Color(1.0, 0.72, 0.52), 4.0], "mud": ["earth", Color(0.6, 0.5, 0.4), 5.0],
		"outer": ["grass", Color(0.42, 0.72, 0.32), 3.5], "court": ["flagstones", Color(0.6, 0.75, 0.55), 3.0],
		"wet": 1.3, "cracks": 0.0, "land": "hills"},
	"drowned_city": {"lane": ["cobbles", Color(0.55, 0.6, 0.6), 1.5], "mud": ["earth", Color(0.42, 0.48, 0.42), 5.0],
		"outer": ["flagstones", Color(0.45, 0.56, 0.5), 3.0], "court": ["flagstones", Color(0.7, 0.75, 0.72), 3.0],
		"wet": 1.8, "cracks": 0.0, "land": "swamp"},
	"travincal": {"lane": ["flagstones", Color(1.05, 0.88, 0.66), 3.0], "mud": ["stone", Color(0.7, 0.62, 0.52), 2.5],
		"outer": ["grass", Color(0.45, 0.62, 0.36), 3.5], "court": ["basalt", Color(0.9, 0.8, 0.65), 2.5],
		"wet": 0.6, "cracks": 0.0, "land": "hills"},
	"temple": {"lane": ["flagstones", Color(1.0, 0.9, 0.7), 2.8], "mud": ["stone", Color(0.62, 0.56, 0.48), 2.4],
		"outer": ["basalt", Color(0.62, 0.56, 0.5), 3.0], "court": ["flagstones", Color(1.1, 0.95, 0.7), 3.0],
		"wet": 0.3, "cracks": 0.0, "land": "flat"},
}

var _door_out := Vector3.ZERO


## The theme's floor, or the village's for a theme this client does not know.
func floor_look() -> Dictionary:
	return FLOORS.get(theme, FLOORS["village"])


## Out of the field through the sanctuary's door: the way the cathedral faces away from.
func door_outward() -> Vector3:
	if _door_out == Vector3.ZERO:
		var first: Array = data["routes"][0]["points"]
		var last: Array = first[first.size() - 1]
		_door_out = _outward(Vector2i(int(last[0]), int(last[1])))
	return _door_out


## Out of the field at a portal (one of `portals`): the way it faces away from.
func portal_outward(p: Vector3) -> Vector3:
	if p.x < 0.0:
		return Vector3(-1, 0, 0)
	if p.x > width * TILE:
		return Vector3(1, 0, 0)
	return Vector3(0, 0, -1) if p.z < 0.0 else Vector3(0, 0, 1)


## The floor mask, a pixel per metre, smoothed: r = the cobbled street along each route (5 m wide, room for
## the monsters' wander), g = trampled mud (the rest of the 2D game's monster halls, the verges), b = scorch,
## a = the cathedral's flagstone forecourt.
func floor_mask(scorch_points: Array) -> ImageTexture:
	var w := int(MASK_SIZE.x)
	var h := int(MASK_SIZE.y)
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	var out := door_outward()
	var side := Vector3(-out.z, 0, out.x)
	for y in h:
		for x in w:
			var world_xz := Vector2(x + 0.5, y + 0.5) + MASK_ORIGIN
			var d := _road[y * w + x]
			var t := tile_at(Vector3(world_xz.x, 0, world_xz.y))
			var lane := 1.0 - smoothstep(2.2, 3.0, d)
			var mud: float = max(0.55 if cell(t) == "P" else 0.0, 1.0 - smoothstep(3.0, 5.5, d))
			# the forecourt before the door, and the flagged path down its middle, in the door's own frame
			var rel := Vector3(world_xz.x, 0, world_xz.y) - door_pos
			var u := rel.dot(out)
			var v := rel.dot(side)
			var flag := 0.0
			if (u >= -9.0 and u < 4.0 and v >= -7.0 and v < 7.0) or (u > -16.0 and abs(v) < 1.6):
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
	var out := door_outward()
	var rel := p - door_pos
	if abs(rel.dot(Vector3(-out.z, 0, out.x))) > 4.5:
		return 0.0
	return clamp((rel.dot(out) + 3.6) / 3.6, 0.0, 1.0) * 0.54


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


## Level a plot of `radius` metres at (x, z), at the land's own height there or at `at`, and return its height.
func pad(x: float, z: float, radius: float, at := INF) -> float:
	var y := _terrain(x, z) if at == INF else at
	pads.append([Vector2(x, z), radius, y])
	return y


func _terrain(x: float, z: float) -> float:
	var c := centre()
	var dx: float = max(abs(x - c.x) - width * TILE * 0.5 - 6.0, 0.0)
	var dz: float = max(abs(z - c.z) - height * TILE * 0.5 - 4.0, 0.0)
	var d := sqrt(dx * dx + dz * dz)
	if key == "tristram":
		return _rolling(x, z, d)
	# elsewhere the roads in from the portals and on to the sanctuary stay level: monsters walk them at 0
	var keep: float = smoothstep(4.0, 9.0, road_distance(Vector3(x, 0, z)))
	var n := _hills.get_noise_2d(x, z)
	var n3 := _hills.get_noise_2d(x * 3.0, z * 3.0)
	var ring: float = clamp((d - 60.0) / 140.0, 0.0, 1.0)
	var far := ring * ring * (26.0 + 18.0 * _hills.get_noise_2d(x * 0.5, z * 0.5))
	match String(floor_look()["land"]):
		"flat":   # a floor under a roof that is gone: level as far as the walls, the hills far off
			return far
		"cave":   # rock walls close round the field, lower to the south where the cameras look from
			var wall: float = smoothstep(2.0, 16.0, d + 4.0 * n3)
			var south: float = lerp(1.0, 0.3, smoothstep(height * TILE, height * TILE + 6.0, z))
			return keep * (wall * wall * (18.0 + 9.0 * n) * south + wall * 3.5 * n3) + far
		"shore":  # the harbour: the land drops into the sea south of the quay
			var sea: float = smoothstep(height * TILE + 0.5, height * TILE + 4.0, z)
			return lerp(_rolling(x, z, d) * keep, -3.2, sea)
		"swamp":  # the sunken city: black water round islands of rubble
			var sunk: float = smoothstep(0.0, 6.0, d) * (1.0 - smoothstep(0.15, 0.35, n))
			return keep * (lerp(0.0, -1.6, sunk) + smoothstep(0.35, 0.6, n) * 0.6 * smoothstep(0.0, 8.0, d)) + far
		"hell":   # scorched ridges round basins where the lava lies
			var rise: float = clamp(d / 26.0, 0.0, 1.0)
			return keep * (rise * (11.0 * n + 3.0 * n3 - 1.5) + rise * rise * 6.0) + far
	return _rolling(x, z, d) * keep


## The village's land: flat round the field, low hills beyond and a ring of hills closing the horizon.
func _rolling(x: float, z: float, d: float) -> float:
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
	if key == "tristram":
		mat.shader = load("res://shaders/ground.gdshader")
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
	else:
		var look := floor_look()
		var shader := Shader.new()
		shader.code = THEMED_FLOOR
		mat.shader = shader
		var scales := Vector4.ZERO
		var cliff: Array = look.get("cliff", look["outer"])
		mat.set_shader_parameter("cliff_a", load(tex + String(cliff[0]) + "_albedo.png"))
		mat.set_shader_parameter("cliff_n", load(tex + String(cliff[0]) + "_normal.png"))
		var ct: Color = cliff[1]
		mat.set_shader_parameter("cliff_tint", Vector3(ct.r, ct.g, ct.b))
		mat.set_shader_parameter("cliff_scale", float(cliff[2]))
		for i in 4:
			var layer: String = ["lane", "mud", "outer", "court"][i]
			var spec: Array = look[layer]
			mat.set_shader_parameter(layer + "_a", load(tex + String(spec[0]) + "_albedo.png"))
			mat.set_shader_parameter(layer + "_n", load(tex + String(spec[0]) + "_normal.png"))
			var tint: Color = spec[1]
			mat.set_shader_parameter(layer + "_tint", Vector3(tint.r, tint.g, tint.b))
			scales[i] = float(spec[2])
		mat.set_shader_parameter("lane_h", load(tex + String(look["lane"][0]) + "_height.png"))
		mat.set_shader_parameter("scales", scales)
		mat.set_shader_parameter("wet", float(look["wet"]))
		mat.set_shader_parameter("cracks", float(look["cracks"]))
		var gates := PackedVector2Array()
		for i in 3:
			var p: Vector3 = portals[i] if i < portals.size() else Vector3(1e5, 0, 1e5)
			gates.append(Vector2(p.x, p.z))
		mat.set_shader_parameter("portals", gates)
	mi.material_override = mat
	mi.name = "Floor"
	add_child(mi)
	return mi


## The floor of the locations after Tristram: shaders/ground.gdshader's layers (mask r lane, g verge, b scorch,
## a forecourt), each layer's texture tinted and scaled by the theme, hell-cracks round every portal, the
## ground beyond the field textured from the side where it climbs into walls, and fissures through all of it
## where the theme burns.
const THEMED_FLOOR := """
shader_type spatial;

uniform sampler2D mask : filter_linear, repeat_disable;
uniform vec4 mask_rect;
uniform sampler2D noise : filter_linear, repeat_enable;
uniform sampler2D lane_a : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D lane_n : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D lane_h : filter_linear_mipmap, repeat_enable;
uniform sampler2D mud_a : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D mud_n : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D outer_a : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D outer_n : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D court_a : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D court_n : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec3 lane_tint;
uniform vec3 mud_tint;
uniform vec3 outer_tint;
uniform vec3 court_tint;
uniform sampler2D cliff_a : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D cliff_n : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec3 cliff_tint;
uniform float cliff_scale;
uniform vec4 scales;      // metres per repeat: lane, verge, ground, forecourt
uniform float wet;
uniform float cracks;
uniform vec2 portals[3];

varying vec3 wpos;
varying vec3 wnrm;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

vec4 untiled(sampler2D t, vec2 uv, float n) {
	vec2 uv2 = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8)) * uv * 0.87 + vec2(0.37, 0.71);
	return mix(texture(t, uv), texture(t, uv2), smoothstep(0.35, 0.65, n));
}

// the ground on a slope or a cave wall, sampled from the side instead of stretched
vec3 sides(sampler2D t, vec3 p, vec3 w, float s, float n) {
	return texture(t, p.zy / s).rgb * w.x + untiled(t, p.xz / s, n).rgb * w.y + texture(t, p.xy / s).rgb * w.z;
}

void fragment() {
	vec2 p = wpos.xz;
	float n = texture(noise, p * 0.035).r;
	float n2 = texture(noise, p * 0.11 + 0.5).r;
	vec2 muv = (p - mask_rect.xy) / mask_rect.zw;
	vec4 m = vec4(0.0);
	if (muv.x >= 0.0 && muv.x <= 1.0 && muv.y >= 0.0 && muv.y <= 1.0) {
		m = texture(mask, muv);
	}
	float dp = 1e6;
	for (int i = 0; i < 3; i++) {
		dp = min(dp, distance(p, portals[i]));
	}
	dp += (n - 0.5) * 5.0;
	float hell = 1.0 - smoothstep(4.0, 12.0, dp);
	vec2 luv = p / scales.x;
	float lh = texture(lane_h, luv).r;
	float lane = smoothstep(0.42, 0.58, m.r + (lh - 0.5) * 0.55 + (n2 - 0.5) * 0.25) * smoothstep(5.0, 9.0, dp);
	float mud = clamp(m.g + (n - 0.45) * 1.2, 0.0, 1.0);
	mud = max(mud, smoothstep(0.0, 0.25, m.r) * 0.85);
	mud = max(mud, hell);
	float court = smoothstep(0.35, 0.65, m.a + (n2 - 0.5) * 0.5);

	vec3 w = pow(abs(wnrm), vec3(4.0));
	w /= w.x + w.y + w.z;
	vec3 oa = sides(outer_a, wpos, w, scales.z, n) * outer_tint;
	vec3 on = sides(outer_n, wpos, w, scales.z, n);
	float steep = 1.0 - smoothstep(0.72, 0.9, wnrm.y + (n2 - 0.5) * 0.2);
	oa = mix(oa, sides(cliff_a, wpos, w, cliff_scale, n) * cliff_tint, steep);
	on = mix(on, sides(cliff_n, wpos, w, cliff_scale, n), steep);
	vec3 ma = untiled(mud_a, p / scales.y, n2).rgb * mud_tint;
	vec3 mn = untiled(mud_n, p / scales.y, n2).rgb;
	float far = smoothstep(18.0, 60.0, length(VERTEX));
	vec3 la = mix(texture(lane_a, luv).rgb, textureLod(lane_a, luv, 8.0).rgb, far * 0.6) * lane_tint;
	vec3 ln = mix(texture(lane_n, luv).rgb, vec3(0.5, 0.5, 1.0), far * 0.5);
	vec3 ca = texture(court_a, p / scales.w).rgb * court_tint;
	vec3 cn = texture(court_n, p / scales.w).rgb;

	float n3 = texture(noise, p * 0.06 + 3.1).r;
	float n4 = texture(noise, p * 0.09 + 7.7).r;
	float worn = smoothstep(0.82, 0.88, n3 + (0.5 - lh) * 0.15) * lane;
	float damp = clamp(lane * 0.3 + m.g * (1.0 - lane) * 0.9, 0.0, 1.0) * (1.0 - court) * (1.0 - hell);
	float puddle = smoothstep(0.74 - 0.06 * wet, 0.78 - 0.06 * wet, n4 + (0.5 - lh) * 0.12 * lane) * damp * min(wet, 1.0);
	vec3 col = mix(oa, ma, mud);
	vec3 nrm = mix(on, mn, mud);
	col = mix(col, la, lane);
	nrm = mix(nrm, ln, lane);
	col = mix(col, ma * 0.6, worn);
	nrm = mix(nrm, mn, worn);
	col = mix(col, ca, court);
	nrm = mix(nrm, cn, court);
	col = mix(col, col * 0.3, puddle);
	float scorch = clamp(m.b + (n2 - 0.5) * 0.6, 0.0, 1.0);
	col *= mix(1.0, 0.25, scorch);
	col = mix(col, col * 0.2, hell);
	col *= 0.85 + 0.3 * n;

	nrm = mix(nrm, vec3(0.5, 0.5, 1.0), puddle);
	NORMAL_MAP = nrm;
	float sheen = clamp(wet - 1.0, 0.0, 1.0) * mud * (1.0 - lane);   // the wettest places glisten all over
	ROUGHNESS = mix(mix(mix(0.92, mix(0.58, 0.82, lh), lane), 0.7, court), 0.3, max(puddle, sheen * 0.6));
	SPECULAR = mix(0.35, 0.08, puddle);
	float n5 = texture(noise, p * 0.32 + 9.1).r;
	float n6 = texture(noise, p * 0.13 + 4.3).r;
	float fissure = (1.0 - smoothstep(0.0, 0.022, abs(n6 - 0.5))) * hell;
	// the burning ground: a few long cracks meandering through it, none under the lanes, pulsing slowly
	float c1 = texture(noise, p * 0.021 + vec2(1.7, 0.3)).r;
	float c2 = texture(noise, p * 0.043 + vec2(6.1, 2.9)).r;
	float seam = (1.0 - smoothstep(0.006, 0.018, abs(c1 - 0.5))) * smoothstep(0.35, 0.55, c2);
	seam *= cracks * (1.0 - lane) * (1.0 - court);
	ALBEDO = mix(col, vec3(0.02, 0.005, 0.0), clamp(seam * 2.0, 0.0, 1.0));
	EMISSION = vec3(1.0, 0.2, 0.03) * fissure * (2.0 + 1.2 * sin(TIME * 1.6 - dp * 0.7));
	EMISSION += vec3(1.0, 0.24, 0.04) * seam * (1.4 + 0.6 * sin(TIME * 0.9 + n5 * 6.0));
	EMISSION += vec3(1.0, 0.32, 0.06) * smoothstep(0.85, 0.98, m.b) * pow(n5, 8.0) * 4.0;
}
"""
