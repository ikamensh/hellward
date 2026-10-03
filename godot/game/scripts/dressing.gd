class_name Dressing
extends Node3D
## Everything around the battle: the portals, the sanctuary, the arches and their gates, props, fires and lights.
## Tristram is a burning village laid out by hand (the constants below); every other location is dressed from its
## grid by its theme (`_themed`). Positions are in metres on the 66 x 36 m field (x east, z south).

const MODELS := "res://assets/models/"

# model, x, z, facing (degrees, 0 = the model's front toward -z / north), burning. Houses off the field's edge
# stand on levelled plots (Level.pad); every other one is mirrored, so five models make a varied street.
const HOUSES := [
	# the north street, facing the field, and the row behind it up the slope
	["house_a", 4.0, -6.5, 178.0, true], ["house_c", 12.5, -7.0, 186.0, false], ["house_b", 24.0, -7.5, 182.0, true],
	["house_ruin", 34.0, -6.0, 180.0, true], ["house_d", 44.5, -7.0, 176.0, false], ["house_a", 54.0, -6.5, 184.0, true],
	["house_c", 62.5, -7.0, 180.0, false],
	["house_d", -2.0, -18.0, 165.0, false], ["house_b", 10.0, -19.0, 195.0, true], ["house_ruin", 20.0, -17.0, 170.0, true],
	["house_a", 31.0, -20.0, 190.0, false], ["house_c", 41.0, -18.0, 172.0, true], ["house_b", 52.0, -19.0, 188.0, false],
	["house_d", 63.0, -18.0, 205.0, false], ["house_a", 73.0, -12.0, 215.0, true],
	# the south street and its back row
	["house_b", 6.0, 42.5, 0.0, false], ["house_ruin", 17.0, 41.5, 4.0, true], ["house_d", 28.0, 43.0, -3.0, true],
	["house_a", 40.0, 42.0, 2.0, false], ["house_c", 51.0, 42.5, -4.0, true], ["house_ruin", 61.0, 41.0, 8.0, true],
	["house_c", 0.0, 53.0, 15.0, false], ["house_a", 14.0, 54.0, -8.0, true], ["house_d", 34.0, 55.0, 6.0, false],
	["house_b", 47.0, 53.0, -12.0, true], ["house_c", 60.0, 52.0, 10.0, false],
	# round the portal and the cathedral
	["house_ruin", -8.0, 3.0, 120.0, true], ["house_ruin", -10.0, 34.0, 60.0, true], ["house_a", -6.0, 46.0, 30.0, false],
	["house_b", 70.0, -2.0, 200.0, false], ["house_d", 71.0, 40.0, -20.0, true], ["house_c", 84.0, 2.0, 230.0, true],
]
# the grid's obstacle tiles, then props in the yards outside the field and on its ring; [5] burns that big
const PROPS := [
	["well", 7.0, 5.0, 0.0], ["cart", 33.0, 5.0, 30.0, 1.3], ["haystack", 57.0, 7.0, 0.0, 2.0],
	["wayside_shrine", 9.0, 31.0, 0.0], ["dead_tree", 55.0, 29.0, 0.0], ["gravestone_a", 33.5, 31.4, 10.0],
	["gravestone_b", 32.6, 30.4, -15.0],
	["barrel", 2.5, -2.2, 0.0], ["barrel", 3.3, -3.0, 0.0], ["crate", 4.2, -1.9, 20.0], ["market_stall", 21.0, -2.6, 180.0],
	["barrel", 63.0, -2.0, 0.0], ["crate", 62.0, -3.0, 10.0], ["lamppost", 13.0, -1.0, 0.0], ["lamppost", 47.0, -1.0, 0.0],
	["fence", 13.0, -2.6, 0.0], ["fence", 51.0, -2.6, 0.0], ["fence", 30.0, -2.4, 3.0],
	["lamppost", 22.0, 37.0, 0.0], ["lamppost", 44.0, 37.0, 0.0], ["fence", 28.0, 38.5, 0.0], ["fence", 60.0, 38.5, 0.0],
	["rubble", 40.0, 37.8, 0.0], ["crate", 47.0, 37.6, 45.0], ["dead_tree", 0.5, 38.0, 90.0],
	["cart", 64.5, 33.0, 160.0, 1.4], ["rubble", 12.0, 35.3, 30.0, 1.2], ["rubble", 26.0, 35.3, -20.0, 1.2],
	["rubble", 50.0, 0.7, 70.0, 1.2],
	["dead_tree", -14.0, 8.0, 0.0], ["dead_tree", -12.0, 27.0, 40.0], ["rubble", -3.0, 12.0, 0.0], ["rubble", -2.0, 23.0, 90.0],
	["dead_tree", -5.0, 9.0, 200.0], ["rubble", -11.0, 15.0, 40.0], ["rubble", -10.0, 21.0, 160.0],
]
# farmsteads burning on the hills: warm points and smoke columns on every horizon
const FARMS := [Vector2(-35, -30), Vector2(30, -45), Vector2(95, -25), Vector2(110, 40), Vector2(20, 78), Vector2(-42, 58)]

var level: Level
var footprints: Array = []   # [centre, radius] the clutter keeps clear of
var _burning := 0


func build(lvl: Level, scorch: Array) -> void:
	level = lvl
	if level.key == "tristram":
		_tristram(scorch)
	else:
		_themed(scorch)


## Tristram: the burning village, its houses and props at fixed places on its own grid.
func _tristram(scorch: Array) -> void:
	for i in HOUSES.size():
		var h: Array = HOUSES[i]
		var pos := Vector3(h[1], 0.0, h[2])
		if abs(pos.z - level.centre().z) > 26.0 or pos.x < -4.0 or pos.x > 70.0:
			pos.y = level.pad(pos.x, pos.z, 6.5)
		var node := _place(h[0], pos, h[3])
		if i % 2 == 1:
			node.scale.x = -1.0
		if h[4]:
			_burn(node, pos)
			scorch.append([pos, 7.0])
	for p in PROPS:
		var pos := Vector3(p[1], 0.0, p[2])
		_place(p[0], pos, p[3])
		if p.size() > 4:
			_burn_prop(pos, p[4])
			scorch.append([pos, float(p[4]) * 2.0])
	for i in FARMS.size():
		var f: Vector2 = FARMS[i]
		var pos := Vector3(f.x, 0.0, f.y)
		pos.y = level.pad(f.x, f.y, 5.0)
		var node := _place("house_ruin", pos, i * 67.0)
		node.scale = Vector3.ONE * 0.85
		var flame := Fx.fire(3.0)
		flame.position = pos + Vector3(0, 2.0, 0)
		add_child(flame)
		var smoke := Fx.smoke(4.0, 26.0)
		smoke.position = pos + Vector3(0, 4.0, 0)
		add_child(smoke)
		var light := Fx.fire_light(10.0, 18.0)
		light.position = pos + Vector3(0, 4.0, 0)
		add_child(light)
	_churchyard()
	_street_braziers()
	_walls()
	_verges(scorch)
	_ash()
	_portal(level.portal_pos)
	_cathedral()
	scorch.append([level.portal_pos, 9.0])


## Something on the field burning: flames, a little smoke, its own light.
func _burn_prop(pos: Vector3, size: float) -> void:
	var flame := Fx.fire(size)
	flame.position = pos + Vector3(0, 0.5, 0)
	add_child(flame)
	var smoke := Fx.smoke(size, 14.0)
	smoke.position = pos + Vector3(0, size + 0.5, 0)
	add_child(smoke)
	var light := Fx.fire_light(5.0 * size, 8.0 + 2.0 * size, size >= 1.3)   # long tower shadows toward the camera
	light.position = pos + Vector3(0, 2.5, 0)
	light.omni_attenuation = 0.75
	add_child(light)


## A dry-stone wall round the field on its border ring, broken here and there, open where the road comes in
## from the portal and leaves for the cathedral, gapped by burning wreckage and the odd gate between piers.
func _walls() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 9
	var gaps := [Vector2(12, 35), Vector2(26, 35), Vector2(50, 1), Vector2(64.5, 33)]
	var runs := [  # start, end, facing: the north and south edges run along x, the west and east along z
		[Vector2(2, 1), Vector2(64, 1), 0.0], [Vector2(2, 35), Vector2(64, 35), 180.0],
		[Vector2(1, 2), Vector2(1, 13), 90.0], [Vector2(1, 22), Vector2(1, 34), 90.0],
		[Vector2(65, 2), Vector2(65, 15), -90.0], [Vector2(65, 24), Vector2(65, 34), -90.0],
	]
	for run in runs:
		var a: Vector2 = run[0]
		var b: Vector2 = run[1]
		var n := int(a.distance_to(b) / 4.0)
		for i in n:
			var c := a.lerp(b, (i + 0.5) / n)
			if gaps.any(func(g): return c.distance_to(g) < 3.0):
				continue
			if rng.randf() < 0.1:
				for side in [-1.0, 1.0]:
					var q: Vector2 = c + (b - a).normalized() * side * 1.6
					_place("wall_post", Vector3(q.x, 0, q.y), run[2])
				continue
			var kind := "wall_broken" if rng.randf() < 0.28 else "wall"
			var node := _place(kind, Vector3(c.x, 0, c.y), float(run[2]) + rng.randf_range(-2.0, 2.0))
			node.scale.x = a.distance_to(b) / n / 4.0 * (-1.0 if rng.randf() < 0.5 else 1.0)


## Ash drifting down over the whole village, swaying, lit by whatever burns near it.
func _ash() -> void:
	var p := GPUParticles3D.new()
	p.amount = 1600
	p.lifetime = 14.0
	p.preprocess = 14.0
	p.local_coords = false
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	pm.emission_box_extents = Vector3(60, 1, 42)
	pm.direction = Vector3.DOWN
	pm.spread = 20.0
	pm.initial_velocity_min = 0.4
	pm.initial_velocity_max = 0.9
	pm.gravity = Vector3(0.25, -0.35, 0.1)
	pm.damping_min = 0.3
	pm.damping_max = 0.6
	pm.turbulence_enabled = true
	pm.turbulence_noise_strength = 1.5
	pm.turbulence_noise_scale = 6.0
	pm.turbulence_influence_min = 0.05
	pm.turbulence_influence_max = 0.12
	pm.angle_min = 0.0
	pm.angle_max = 360.0
	pm.scale_min = 0.6
	pm.scale_max = 1.4
	var ramp := Gradient.new()
	ramp.offsets = PackedFloat32Array([0.0, 0.1, 0.85, 1.0])
	ramp.colors = PackedColorArray([Color(0.6, 0.58, 0.55, 0.0), Color(0.6, 0.58, 0.55, 0.8),
		Color(0.5, 0.48, 0.46, 0.7), Color(0.5, 0.48, 0.46, 0.0)])
	var rt := GradientTexture1D.new()
	rt.gradient = ramp
	pm.color_ramp = rt
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(0.07, 0.07)
	var m := StandardMaterial3D.new()
	m.albedo_texture = Fx.dot_texture()
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.shading_mode = BaseMaterial3D.SHADING_MODE_PER_VERTEX
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	q.material = m
	p.draw_pass_1 = q
	p.position = level.centre() + Vector3(0, 16, 0)
	p.visibility_aabb = AABB(Vector3(-70, -20, -50), Vector3(140, 40, 100))
	add_child(p)


## Braziers along the streets, alternating sides on the mud verge: the roads the monsters take are pools of
## firelight in the dark, as the lit paths of a Diablo town.
func _street_braziers(color := Color(1.0, 0.5, 0.18), energy := 7.0, verge := 2.7) -> void:
	var placed: Array = []
	for route in level.routes:
		var walked := 0.0
		var side := 1.0
		for i in route.size() - 1:
			var a: Vector3 = route[i]
			var b: Vector3 = route[i + 1]
			var seg := a.distance_to(b)
			var dir := (b - a).normalized()
			while walked < seg:
				var at := a + dir * walked + Vector3(-dir.z, 0, dir.x) * side * 2.9
				walked += 9.0
				side = -side
				var t := level.tile_at(at)
				if at.x < 3.0 or at.x > 63.0 or level.cell(t) != "P" or level.road_distance(at) < verge:
					continue
				if placed.any(func(q): return (q as Vector3).distance_to(at) < 6.0):
					continue
				placed.append(at)
				var brazier := _place("brazier", at, placed.size() * 47.0)
				var coals := Models.node(brazier, "fx_fire_1")
				coals.add_child(Fx.fire(0.8))
				var light := Fx.fire_light(energy, 13.0, false, color)
				light.position = Vector3(0, 1.4, 0)   # above the coals: the ground is not lit at grazing angles
				light.omni_attenuation = 0.75
				coals.add_child(light)
			walked -= seg


## The sacked village's leavings on the mud between the streets, where the monsters never walk:
## tipped barrels, crates, rubble, a broken cart, half of them scorched.
func _verges(scorch: Array) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 21
	var kinds := ["barrel", "barrel", "crate", "rubble", "crate", "barrel"]
	var placed := 0
	for i in 400:
		if placed >= 26:
			break
		var p := Vector3(rng.randf_range(2.0, 64.0), 0.0, rng.randf_range(2.0, 34.0))
		var t := level.tile_at(p)
		if level.cell(t) != "P" or level.road_distance(p) < 3.4:
			continue
		var kind: String = kinds[placed % kinds.size()]
		var node := _place(kind, p, rng.randf() * 360.0)
		node.scale = Vector3.ONE * rng.randf_range(0.6, 1.0)
		if kind == "barrel" and rng.randf() < 0.7:
			node.rotation_degrees.x = 88.0
			node.position.y = 0.3 * node.scale.y
		if rng.randf() < 0.5:
			scorch.append([p, rng.randf_range(1.5, 3.0)])
		placed += 1


## Gravestones in loose rows on either flank of the cathedral.
func _churchyard() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 5
	for side in [-1.0, 1.0]:
		for row in 3:
			for k in 5:
				var x: float = 66.0 + k * 2.6 + rng.randf_range(-0.4, 0.4)
				var z: float = level.door_pos.z + side * (9.5 + row * 2.4) + rng.randf_range(-0.3, 0.3)
				var stone := "gravestone_a" if rng.randf() < 0.5 else "gravestone_b"
				_place(stone, Vector3(x, 0.0, z), (90.0 if side < 0 else -90.0) + rng.randf_range(-12, 12))


func _place(model: String, pos: Vector3, facing: float) -> Node3D:
	var node := Models.make(model)
	footprints.append([pos, 6.0 if model.begins_with("house") else 1.6])
	node.position = pos
	node.rotation_degrees.y = facing
	add_child(node)
	for fx in node.find_children("fx_light*", "", true, false):
		(fx as Node3D).add_child(Fx.fire_light(3.0, 8.0))
	return node


## A hell gate the monsters pour from at `at`, facing the field: a turning vortex, red light, embers and smoke.
func _portal(at: Vector3, shadows := true) -> void:
	var node := _place("portal", at, _facing(level.portal_outward(at)))
	footprints.append([at, 5.0])
	var vortex := Models.node(node, "vortex") as MeshInstance3D
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/vortex.gdshader")
	m.set_shader_parameter("swirl", load("res://assets/fx/portal_swirl.png"))
	vortex.material_override = m
	var heart := Models.node(node, "fx_portal")
	var light := Fx.fire_light(9.0, 18.0, shadows, Color(1.0, 0.18, 0.06))
	heart.add_child(light)
	var embers := Fx.embers(Vector3(4, 4, 4), 90)
	heart.add_child(embers)
	var smoke := Fx.smoke(2.5, 12.0)
	smoke.position = Vector3(0, 2.0, 0)
	heart.add_child(smoke)


## The cathedral the monsters march on, its doors open and lit: the lamp still burns inside.
func _cathedral() -> void:
	var out := level.door_outward()
	var side := Vector3(-out.z, 0, out.x)
	var node := Models.make("cathedral")
	node.rotation_degrees.y = _facing(out)
	add_child(node)
	var door := Models.node(node, "fx_door")
	var offset := door.global_position - node.global_position
	node.position = level.door_pos - Vector3(offset.x, 0.0, offset.z)   # the door marker sits on the top step
	footprints.append([node.position, 16.0])
	var glow := SpotLight3D.new()
	glow.light_color = Color(1.0, 0.75, 0.45)
	glow.light_energy = 8.0
	glow.spot_range = 22.0
	glow.spot_angle = 38.0
	glow.shadow_enabled = true
	glow.light_volumetric_fog_energy = 2.0
	door.add_child(glow)
	glow.position = Vector3(0, 3.5, 2.5)
	glow.rotation_degrees = Vector3(-18, 0, 0)
	# braziers at the foot of the steps and at the forecourt's corners, lighting the west front
	for at in [Vector2(-4.6, -3.4), Vector2(-4.6, 3.4), Vector2(-11.0, -6.2), Vector2(-11.0, 6.2)]:
		var pos: Vector3 = level.door_pos + out * at.x + side * at.y
		var brazier := _place("brazier", pos, _facing(out))
		var coals := Models.node(brazier, "fx_fire_1")
		coals.add_child(Fx.fire(0.9))
		var light := Fx.fire_light(8.0, 12.0, abs(at.x) < 5.0)
		light.position = Vector3(0, 0.8, 0)
		coals.add_child(light)
	for fx in node.find_children("fx_light*", "", true, false):
		var inside := OmniLight3D.new()
		inside.light_color = Color(1.0, 0.8, 0.5)
		inside.light_energy = 4.0
		inside.omni_range = 9.0
		(fx as Node3D).add_child(inside)


## The yaw (degrees) that turns a model's front (-z) away from `out`, toward the field.
static func _facing(out: Vector3) -> float:
	return rad_to_deg(atan2(out.x, out.z))


## Set a house alight at its fx_fire marks: flames, smoke over the roof, light inside and out.
func _burn(node: Node3D, pos: Vector3) -> void:
	var marks := node.find_children("fx_fire*", "", true, false)
	for i in marks.size():
		var m := marks[i] as Node3D
		m.add_child(Fx.fire(2.6 if i % 2 == 0 else 1.8))
		if i == 0:
			var smoke := Fx.smoke(3.0, 18.0)
			smoke.position = Vector3(0, 1.5, 0)
			m.add_child(smoke)
	var embers := Fx.embers(Vector3(8, 4, 8), 60)
	embers.position = pos + Vector3(0, 3, 0)
	add_child(embers)
	var pall := FogVolume.new()
	pall.shape = RenderingServer.FOG_VOLUME_SHAPE_ELLIPSOID
	pall.size = Vector3(16, 9, 16)
	var fm := FogMaterial.new()
	fm.density = 0.035
	fm.albedo = Color(0.18, 0.16, 0.15)
	fm.emission = Color(0.9, 0.3, 0.08) * 0.25
	fm.height_falloff = 0.2
	fm.edge_fade = 0.5
	pall.material = fm
	pall.position = pos + Vector3(0, 8.0, 0)
	add_child(pall)
	_burning += 1
	var flames := node.find_children("fx_flame*", "", true, false)   # flames licking out of every other upper window
	for i in range(0, flames.size(), 2):
		(flames[i] as Node3D).add_child(Fx.fire(0.7))
	var light := Fx.fire_light(11.0, 15.0)   # no shadows: an omni light's shadow re-renders the scene six times
	light.light_volumetric_fog_energy = 0.35   # a warm haze, not a glowing ball swallowing the flames
	light.position = pos + Vector3(0, 3.5, 3.0 if pos.z < 18.0 else -3.0)
	add_child(light)



# --- Every other location: dressed from its grid by its theme ---------------------------------------------------

## Per theme: `stone` the masonry of arches, kerbs and walls [texture, tint]; `pool` how a '~' tile is drawn;
## `ring` what stands on the field's border ring; `fire` the colour of the braziers' light along the lanes.
const LOOKS := {
	"village": {"stone": ["stone", Color(0.8, 0.8, 0.78)], "pool": "pit", "ring": "drystone", "lights": ["brazier", 14.0], "crown": "gable", "litter": ["barrel", "crate", "rubble"],
		"fire": Color(1.0, 0.5, 0.18)},
	"graveyard": {"stone": ["stone", Color(0.62, 0.66, 0.68)], "pool": "grave", "ring": "drystone", "lights": ["lamp", 13.0], "crown": "gable", "litter": ["grave", "grave", "bones", "rubble"],
		"fire": Color(1.0, 0.5, 0.18)},
	"cathedral": {"stone": ["stone", Color(0.78, 0.74, 0.7)], "pool": "pit", "ring": "nave", "lights": ["brazier", 12.0], "crown": "merlons", "litter": ["rubble", "drum", "pew", "candles"],
		"fire": Color(1.0, 0.55, 0.22)},
	"catacombs": {"stone": ["stone", Color(0.6, 0.56, 0.5)], "pool": "pit", "ring": "crypt", "lights": ["brazier", 16.0], "crown": "merlons", "litter": ["bones", "bones", "rubble", "candles"],
		"fire": Color(1.0, 0.5, 0.2)},
	"caves": {"stone": ["basalt", Color(0.62, 0.52, 0.46)], "pool": "lava", "ring": "rock", "lights": ["torch", 11.0], "crown": "spikes", "litter": ["rock", "rock", "stalagmite"],
		"fire": Color(1.0, 0.45, 0.15)},
	"hell": {"stone": ["basalt", Color(0.55, 0.38, 0.36)], "pool": "lava", "ring": "rock", "lights": ["pyre", 13.0], "crown": "spikes", "litter": ["bones", "spire", "rock"],
		"fire": Color(1.0, 0.32, 0.08)},
	"docks": {"stone": ["stone", Color(0.6, 0.63, 0.64)], "pool": "water", "ring": "quay", "lights": ["lamp", 10.0], "crown": "gable", "litter": ["crate", "barrel", "barrel", "rope"],
		"fire": Color(1.0, 0.55, 0.22)},
	"spider_forest": {"stone": ["stone", Color(0.5, 0.58, 0.5)], "pool": "bog", "ring": "wood", "lights": ["torch", 11.0], "crown": "gable", "litter": ["cocoon", "rock", "bones"],
		"fire": Color(1.0, 0.5, 0.2)},
	"jungle": {"stone": ["stone", Color(0.58, 0.64, 0.5)], "pool": "bog", "ring": "wood", "lights": ["torch", 11.0], "crown": "thatch", "litter": ["ruin", "rock", "skulls"],
		"fire": Color(1.0, 0.55, 0.2)},
	"drowned_city": {"stone": ["stone", Color(0.5, 0.6, 0.56)], "pool": "water", "ring": "ruin", "lights": ["lamp", 11.0], "crown": "merlons", "litter": ["rubble", "drum", "barrel"],
		"fire": Color(1.0, 0.55, 0.25)},
	"travincal": {"stone": ["flagstones", Color(0.95, 0.82, 0.62)], "pool": "water", "ring": "balustrade", "lights": ["brazier", 14.0], "crown": "dome", "litter": ["urn", "urn", "rubble"],
		"fire": Color(1.0, 0.6, 0.25)},
	"temple": {"stone": ["basalt", Color(0.8, 0.72, 0.6)], "pool": "pit", "ring": "balustrade", "lights": ["brazier", 12.0], "crown": "dome", "litter": ["urn", "candles", "drum"],
		"fire": Color(1.0, 0.65, 0.3)},
}
const ARCH_R := 1.9         # an arch's opening: half its width, metres
const ARCH_SPRING := 3.0    # where the arch springs from its piers
const ARCH_W := 3.4         # half the frame's width: its piers fill the wall tiles either side of the socket
const ARCH_TOP := 5.7
const ARCH_DEPTH := 1.5     # along the lane

var _look: Dictionary
var _gates := {}            # arch index -> its gate's parts and last state (`_gate_parts`)
var _mats := {}
var _rng := RandomNumberGenerator.new()


func _themed(scorch: Array) -> void:
	_look = LOOKS.get(level.theme, LOOKS["village"])
	_rng.seed = hash(level.key)
	Atmosphere.theme(get_parent(), level.theme)
	for i in level.portals.size():
		var at: Vector3 = level.portals[i]
		level.pad(at.x, at.z, 7.0, 0.0)
		_portal(at, i == 0)   # one shadowed portal light: each omni shadow re-renders the scene six times
		scorch.append([at, 9.0])
	_sanctuary()
	_pools()
	_obstacles(scorch)
	_arches()
	_street_braziers(_look["fire"], 9.0, 2.35)
	_litter(_look["litter"], 22)
	_ring()
	_ring_lights(String(_look["lights"][0]), float(_look["lights"][1]))
	match level.theme:
		"graveyard": _graveyard()
		"cathedral": _nave()
		"catacombs": _crypt()
		"caves": _caves()
		"hell": _hell()
		"docks": _docks()
		"spider_forest": _spider_forest()
		"jungle": _jungle()
		"drowned_city": _drowned()
		"travincal": _travincal()
		"temple": _temple()
		_: _graveyard()


## The cathedral at the door, its body on level ground whatever the land does behind it.
func _sanctuary() -> void:
	var out := level.door_outward()
	for k in 4:
		var at := level.door_pos + out * (4.0 + k * 8.0)
		level.pad(at.x, at.z, 9.0, 0.0)
	_cathedral()


# --- Materials and shapes ---

## A textured material mapped from the world (triplanar), for shapes built here: `scale` repeats per metre.
func _tex(tex: String, tint: Color, scale := 0.45) -> StandardMaterial3D:
	var key := "%s %s %s" % [tex, tint, scale]
	if not _mats.has(key):
		var m := Mats.textured(tex, tint)
		m.uv1_triplanar = true
		m.uv1_world_triplanar = true
		m.uv1_scale = Vector3.ONE * scale
		m.uv1_triplanar_sharpness = 3.0
		_mats[key] = m
	return _mats[key]


## The theme's masonry.
func _stone(scale := 0.45) -> StandardMaterial3D:
	return _tex(String(_look["stone"][0]), _look["stone"][1], scale)


func _flat(color: Color, rough := 0.85, metal := 0.0) -> StandardMaterial3D:
	var key := "flat %s %s %s" % [color, rough, metal]
	if not _mats.has(key):
		_mats[key] = Mats.flat(color, rough, metal)
	return _mats[key]


func _xf(at: Vector3, yaw: float, scale: Vector3 = Vector3.ONE, tilt := Vector3.ZERO) -> Transform3D:
	var b := Basis.from_euler(Vector3(deg_to_rad(tilt.x), deg_to_rad(yaw), deg_to_rad(tilt.z)))
	return Transform3D(b.scaled_local(scale), at)


## One mesh at many transforms; `shadows` only for what stands near enough to matter.
func _batch(mesh: Mesh, transforms: Array, mat: Material, shadows := false, colors := PackedColorArray()) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = colors.size() > 0
	mm.mesh = mesh
	mm.instance_count = transforms.size()
	for i in transforms.size():
		mm.set_instance_transform(i, transforms[i])
		if mm.use_colors:
			mm.set_instance_color(i, colors[i])
	var mi := MultiMeshInstance3D.new()
	mi.multimesh = mm
	if mat:
		mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	return mi


## Many copies of a model, one MultiMesh per mesh in it: crowds of gravestones, crates, trees.
func _crowd(model: String, transforms: Array, shadows := false) -> void:
	if transforms.is_empty():
		return
	var src := Models.make(model)
	for node in src.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		var mesh: Mesh = mi.mesh.duplicate()
		for k in mesh.get_surface_count():
			var m := mi.get_surface_override_material(k)
			if m:
				mesh.surface_set_material(k, m)
		var local := Transform3D.IDENTITY
		var n: Node = mi
		while n != src:
			local = (n as Node3D).transform * local
			n = n.get_parent()
		var placed: Array = []
		for t in transforms:
			placed.append((t as Transform3D) * local)
		_batch(mesh, placed, null, shadows)
	src.free()


func _box(size: Vector3, at: Vector3, mat: Material, yaw := 0.0, shadows := true) -> MeshInstance3D:
	var b := BoxMesh.new()
	b.size = size
	return _mesh(b, at, mat, yaw, shadows)


func _cyl(bottom: float, top: float, height: float, at: Vector3, mat: Material, sides := 12, shadows := true) -> MeshInstance3D:
	var c := CylinderMesh.new()
	c.bottom_radius = bottom
	c.top_radius = top
	c.height = height
	c.radial_segments = sides
	c.rings = 1
	return _mesh(c, at + Vector3(0, height * 0.5, 0), mat, 0.0, shadows)


func _mesh(mesh: Mesh, at: Vector3, mat: Material, yaw := 0.0, shadows := true) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	mi.position = at
	mi.rotation_degrees.y = yaw
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	return mi


static var _unit_box: BoxMesh
static var _rocks: Array = []
static var _spire: ArrayMesh


static func unit_box() -> BoxMesh:
	if _unit_box == null:
		_unit_box = BoxMesh.new()
	return _unit_box


## A faceted boulder about 2 m across, one of four shapes.
static func rock_mesh(i: int) -> ArrayMesh:
	while _rocks.size() < 4:
		var sm := SphereMesh.new()
		sm.radial_segments = 7
		sm.rings = 5
		_rocks.append(_lumpy(sm.get_mesh_arrays(), 31 + _rocks.size() * 7, 0.55, 0.7, 1.7))
	return _rocks[i % 4]


## A jagged spire 1 m tall and 1 m across at its foot: stalagmites, hell's basalt teeth, a ruined column's stump.
static func spire_mesh() -> ArrayMesh:
	if _spire == null:
		var cm := CylinderMesh.new()
		cm.top_radius = 0.04
		cm.bottom_radius = 0.5
		cm.height = 1.0
		cm.radial_segments = 7
		cm.rings = 4
		var arrays := cm.get_mesh_arrays()
		var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		for k in verts.size():
			verts[k].y += 0.5
		arrays[Mesh.ARRAY_VERTEX] = verts
		_spire = _lumpy(arrays, 5, 0.25, 1.0)
	return _spire


## Displace a primitive by noise and shade it faceted: rough stone.
static func _lumpy(arrays: Array, noise_seed: int, amount: float, flatten: float, frequency := 0.9) -> ArrayMesh:
	var fn := FastNoiseLite.new()
	fn.seed = noise_seed
	fn.frequency = frequency
	var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	for k in verts.size():
		var v := verts[k]
		v *= 1.0 + amount * fn.get_noise_3dv(v * 1.3)
		v.y *= flatten
		verts[k] = v
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = null
	arrays[Mesh.ARRAY_TANGENT] = null
	var st := SurfaceTool.new()
	st.create_from_arrays(arrays)
	st.deindex()
	st.generate_normals()
	st.generate_tangents()
	return st.commit()


## Whether `p` is free for scenery of `radius`: off the roads, clear of the portals, the sanctuary and the rest.
func _free(p: Vector3, radius: float, road := 4.5) -> bool:
	if level.road_distance(p) < road + radius:
		return false
	for f in footprints:
		var at: Vector3 = f[0]
		if Vector2(p.x - at.x, p.z - at.z).length() < float(f[1]) + radius:
			return false
	return true


## Off the field and its border ring by at least `margin` metres.
func _outside(p: Vector3, margin := 0.0) -> bool:
	return p.x < -margin or p.z < -margin or p.x > level.width * Level.TILE + margin or p.z > level.height * Level.TILE + margin


## Points scattered over `area` (metres) outside the field, free for scenery of `radius`.
func _spots(area: Rect2, count: int, radius: float, margin := 1.0, tries := 30) -> Array:
	var found: Array = []
	for i in count * tries:
		if found.size() >= count:
			break
		var p := Vector3(_rng.randf_range(area.position.x, area.end.x), 0.0, _rng.randf_range(area.position.y, area.end.y))
		if not _outside(p, margin) or not _free(p, radius):
			continue
		if found.any(func(q): return (q as Vector3).distance_to(p) < radius * 2.0):
			continue
		p.y = level.ground_height(p.x, p.z)
		found.append(p)
	return found


# --- Pools ---

## The grid's pools as rectangles of tiles: runs along each row, merged down while they line up.
func _pool_rects() -> Array:
	var open: Array = []
	var done: Array = []
	for y in level.height:
		var runs: Array = []
		var x := 0
		while x < level.width:
			if level.cell(Vector2i(x, y)) == "~":
				var x0 := x
				while x < level.width and level.cell(Vector2i(x, y)) == "~":
					x += 1
				runs.append(Vector2i(x0, x - x0))
			else:
				x += 1
		var still: Array = []
		for r in open:
			var rect: Rect2i = r
			var grown := false
			for run in runs:
				if run.x == rect.position.x and run.y == rect.size.x:
					rect.size.y += 1
					runs.erase(run)
					grown = true
					break
			(still if grown else done).append(rect)
		for run in runs:
			still.append(Rect2i(run.x, y, run.y, 1))
		open = still
	done.append_array(open)
	return done


## '~' tiles: floor nothing stands on, sunk below the field by a shader that draws the hole's walls in perspective:
## lava, black water, bog, a dark pit; open graves in the graveyard.
func _pools() -> void:
	var kind: String = _look["pool"]
	for r in _pool_rects():
		var rect: Rect2i = r
		var lo := Vector3(rect.position.x * Level.TILE, 0, rect.position.y * Level.TILE)
		var hi := lo + Vector3(rect.size.x * Level.TILE, 0, rect.size.y * Level.TILE)
		if kind == "grave":
			for y in rect.size.y:
				for x in rect.size.x:
					_open_grave(level.tile_pos(rect.position + Vector2i(x, y)))
			continue
		var rim := 0.32
		_hole(lo + Vector3(rim, 0, rim), hi - Vector3(rim, 0, rim), kind)
		_kerb(lo, hi, rim, kind)
		footprints.append([(lo + hi) * 0.5, max(hi.x - lo.x, hi.z - lo.z) * 0.5])
		if kind == "lava":
			var n := int(ceil(max(hi.x - lo.x, hi.z - lo.z) / 7.0))
			for i in n:
				var light := Fx.fire_light(4.0, 9.0, false, Color(1.0, 0.36, 0.08))
				light.position = lo.lerp(hi, (i + 0.5) / n) + Vector3(0, 1.2, 0)
				light.light_volumetric_fog_energy = 0.15
				add_child(light)
			var embers := Fx.embers(Vector3(hi.x - lo.x, 1.0, hi.z - lo.z), int(clamp((hi.x - lo.x) * (hi.z - lo.z) * 1.5, 20, 120)))
			embers.position = (lo + hi) * 0.5
			add_child(embers)


## A hole in the floor from `lo` to `hi`: a quad over it whose shader shows the walls going down and what lies below.
func _hole(lo: Vector3, hi: Vector3, kind: String) -> MeshInstance3D:
	var q := PlaneMesh.new()
	q.size = Vector2(hi.x - lo.x, hi.z - lo.z)
	var mi := _mesh(q, (lo + hi) * 0.5 + Vector3(0, 0.012, 0), _pool_mat(kind), 0.0, false)
	mi.set_instance_shader_parameter("box", Vector4(lo.x, lo.z, hi.x, hi.z))
	return mi


func _pool_mat(kind: String) -> ShaderMaterial:
	var key := "pool " + kind
	if not _mats.has(key):
		var m := ShaderMaterial.new()
		var sh := Shader.new()
		sh.code = POOL_SHADER
		m.shader = sh
		var spec: Array = {
			"pit": [0, 3.5, "stone", Color(0.45, 0.42, 0.4)], "grave": [0, 1.3, "earth", Color(0.7, 0.62, 0.55)],
			"water": [1, 0.45, "stone", Color(0.35, 0.38, 0.38)], "bog": [3, 0.3, "earth", Color(0.4, 0.42, 0.32)],
			"lava": [2, 0.6, "basalt", Color(0.5, 0.35, 0.3)],
		}[kind]
		m.set_shader_parameter("kind", int(spec[0]))
		m.set_shader_parameter("depth", float(spec[1]))
		m.set_shader_parameter("wall", load("res://assets/textures/%s_albedo.png" % spec[2]))
		var tint: Color = spec[3]
		m.set_shader_parameter("wall_tint", Vector3(tint.r, tint.g, tint.b))
		var nt := NoiseTexture2D.new()
		nt.seamless = true
		nt.width = 256
		nt.height = 256
		var fn := FastNoiseLite.new()
		fn.frequency = 0.03
		nt.noise = fn
		m.set_shader_parameter("noise", nt)
		var rn := NoiseTexture2D.new()
		rn.seamless = true
		rn.as_normal_map = true
		rn.bump_strength = 1.5
		rn.width = 256
		rn.height = 256
		var rf := FastNoiseLite.new()
		rf.frequency = 0.06
		rn.noise = rf
		m.set_shader_parameter("ripples", rn)
		_mats[key] = m
	return _mats[key]


## The edge of a pool, inside its tiles: worn stones, timber on the docks, crusted basalt round the lava.
func _kerb(lo: Vector3, hi: Vector3, rim: float, kind: String) -> void:
	var mat: Material = _stone()
	var h := 0.16
	if level.theme == "docks":
		mat = _tex("planks", Color(0.6, 0.52, 0.44), 0.5)
		h = 0.22
	elif kind == "bog":
		mat = _tex("earth", Color(0.45, 0.45, 0.38), 0.4)
		h = 0.08
	var xs: Array = []
	for side in 4:
		var a: Vector3
		var b: Vector3
		match side:
			0: a = lo; b = Vector3(hi.x, 0, lo.z)
			1: a = Vector3(lo.x, 0, hi.z); b = hi
			2: a = lo; b = Vector3(lo.x, 0, hi.z)
			3: a = Vector3(hi.x, 0, lo.z); b = hi
		var along := b - a
		var n := int(max(1.0, round(along.length() / 1.0)))
		var inward := Vector3(0, 0, 1) if side == 0 else (Vector3(0, 0, -1) if side == 1 else (Vector3(1, 0, 0) if side == 2 else Vector3(-1, 0, 0)))
		for i in n:
			var c := a.lerp(b, (i + 0.5) / n) + inward * rim * 0.5
			var size := Vector3(along.length() / n * 0.97, h * _rng.randf_range(0.7, 1.3), rim)
			if side >= 2:
				size = Vector3(rim, size.y, along.length() / n * 0.97)
			xs.append(_xf(c + Vector3(0, size.y * 0.5 - 0.02, 0), _rng.randf_range(-3, 3), size))
	_batch(unit_box(), xs, mat, false)


## An open grave in the churchyard: the pit, the heap of earth thrown up beside it, its headstone.
func _open_grave(at: Vector3) -> void:
	var along := _rng.randf() < 0.5
	var half := Vector3(0.5, 0, 1.0) if along else Vector3(1.0, 0, 0.5)
	_hole(at - half, at + half, "grave")
	var mound := SphereMesh.new()
	mound.radius = 0.6
	mound.height = 0.5
	var side := Vector3(0.85, 0.0, 0.0) if along else Vector3(0.0, 0.0, 0.85)
	var heap := _mesh(mound, at + side * (1.0 if _rng.randf() < 0.5 else -1.0), _tex("earth", Color(0.55, 0.5, 0.45), 0.6), 0.0, true)
	heap.scale = Vector3(1.0, 1.0, 1.6) if along else Vector3(1.6, 1.0, 1.0)
	var head := (Vector3(0, 0, -1.15) if along else Vector3(-1.15, 0, 0))
	var stone := _place("gravestone_b" if _rng.randf() < 0.5 else "gravestone_a", at + head, (0.0 if along else 90.0) + _rng.randf_range(-12, 12))
	stone.rotation_degrees.x = _rng.randf_range(-8, 8)
	stone.scale = Vector3.ONE * 0.8


# --- Litter on the verges ---

## What lies about on the lanes' verges, where the monsters do not walk: Tristram's barrels and crates, the
## graveyard's toppled headstones and bones, the nave's broken drums and pews, the docks' cargo...
func _litter(kinds: Array, count: int) -> void:
	var placed := 0
	for i in 500:
		if placed >= count:
			break
		var p := Vector3(_rng.randf_range(2.0, 64.0), 0.0, _rng.randf_range(2.0, 34.0))
		if level.cell(level.tile_at(p)) != "P" or level.road_distance(p) < 3.4:
			continue
		if footprints.any(func(f): return Vector2(p.x - f[0].x, p.z - f[0].z).length() < float(f[1]) + 0.8):
			continue
		var yaw := _rng.randf() * 360.0
		match String(kinds[placed % kinds.size()]):
			"barrel":
				var b := _scaled("barrel", p, yaw, _rng.randf_range(0.7, 1.0))
				if _rng.randf() < 0.6:
					b.rotation_degrees.x = 88.0
					b.position.y = 0.3 * b.scale.y
			"crate":
				_scaled("crate", p, yaw, _rng.randf_range(0.7, 1.0))
			"rubble":
				_scaled("rubble", p, yaw, _rng.randf_range(0.4, 0.65))
			"grave":
				var g := _scaled("gravestone_a" if _rng.randf() < 0.5 else "gravestone_b", p, yaw, _rng.randf_range(0.6, 0.85))
				g.rotation_degrees.x = _rng.randf_range(-20, 20)
				g.rotation_degrees.z = _rng.randf_range(-12, 12)
			"bones":
				_bone_pile(p, _rng.randf_range(0.45, 0.7))
			"drum":
				_column_drum(p, yaw)
			"pew":
				var plank := _tex("planks", Color(0.5, 0.38, 0.3), 0.8)
				var seat := _box(Vector3(2.4, 0.1, 0.45), p + Vector3(0, 0.08, 0), plank, yaw)
				seat.rotation_degrees.z = _rng.randf_range(-4, 4)
				var back := _box(Vector3(2.4, 0.6, 0.08), p + Vector3(0, 0.05, 0.4).rotated(Vector3.UP, deg_to_rad(yaw)), plank, yaw)
				back.rotation_degrees.x = 80.0
			"candles":
				_candles(p)
			"rock":
				var r := _mesh(rock_mesh(_rng.randi()), p, _stone(0.35), yaw)
				r.scale = Vector3(1.0, 0.6, 0.9) * _rng.randf_range(0.35, 0.6)
			"stalagmite":
				_stalagmites(p, 0.45)
			"spire":
				_spires(p, 0.5)
			"rope":
				var coil := TorusMesh.new()
				coil.inner_radius = 0.18
				coil.outer_radius = 0.38
				var rope := _mesh(coil, p + Vector3(0, 0.08, 0), _tex("thatch", Color(0.75, 0.65, 0.48), 1.0), yaw)
				rope.scale = Vector3(1, 0.6, 1)
			"cocoon":
				var silk := SphereMesh.new()
				var body := _mesh(silk, p + Vector3(0, 0.25, 0), _flat(Color(0.75, 0.75, 0.7), 0.6), yaw)
				body.scale = Vector3(0.32, 0.3, 0.8)
			"ruin":
				_ruin_stones(p)
			"skulls":
				var xs: Array = []
				for k in 4:
					xs.append(_xf(p + Vector3(_rng.randf_range(-0.4, 0.4), 0.1, _rng.randf_range(-0.4, 0.4)), _rng.randf() * 360.0, Vector3(0.2, 0.22, 0.24)))
				_batch(SphereMesh.new(), xs, _tex("bone", Color(0.85, 0.8, 0.68), 1.5), true)
			"urn":
				_urn(p)
		footprints.append([p, 1.0])
		placed += 1


## A clay offering urn, sometimes knocked over.
func _urn(at: Vector3) -> void:
	var clay := _flat(Color(0.45, 0.22, 0.12), 0.7)
	var body := SphereMesh.new()
	body.radius = 0.32
	body.height = 0.7
	var mi := _mesh(body, at + Vector3(0, 0.35, 0), clay, _rng.randf() * 360.0)
	var neck := _cyl(0.12, 0.17, 0.25, at + Vector3(0, 0.62, 0), clay, 8)
	if _rng.randf() < 0.35:
		mi.position = at + Vector3(0, 0.28, 0)
		mi.rotation_degrees.z = 80.0
		neck.position = at + Vector3(0.45, 0.28, 0)
		neck.rotation_degrees.z = 80.0


# --- Obstacles ---

## 'o' tiles: something nothing walks through and nothing is built on, in the theme's terms.
func _obstacles(scorch: Array) -> void:
	var i := 0
	for y in level.height:
		for x in level.width:
			if level.cell(Vector2i(x, y)) != "o":
				continue
			var at := level.tile_pos(Vector2i(x, y))
			var yaw := _rng.randf() * 360.0
			match level.theme:
				"graveyard":
					match i % 3:
						0: _scaled("dead_tree", at, yaw, 0.8)
						1: _grave_cluster(at)
						2: _place("wayside_shrine", at, 180.0)
				"cathedral", "drowned_city":
					if i % 2 == 0:
						_broken_column(at, yaw)
					else:
						_scaled("rubble", at, yaw, 0.75)
						_column_drum(at + Vector3(0.4, 0, 0.3), yaw)
				"catacombs":
					if i % 2 == 0:
						_bone_pile(at, 1.0)
					else:
						_sarcophagus(at, 90.0 * (i % 2))
				"caves":
					_stalagmites(at, 1.0)
				"hell":
					if i % 2 == 0:
						_spires(at, 1.3)
					else:
						_bone_pile(at, 1.1)
						var flame := Fx.fire(1.0)
						flame.position = at + Vector3(0, 0.4, 0)
						add_child(flame)
						scorch.append([at, 2.2])
				"docks":
					match i % 3:
						0: _crates(at)
						1: _scaled("cart", at, yaw, 0.75)
						2: _barrels(at)
				"spider_forest":
					if i % 2 == 0:
						_scaled("dead_tree", at, yaw, 1.1)
						_web(at + Vector3(0, 2.2, 0), 2.4, yaw)
					else:
						_cocoons(at)
				"jungle":
					if i % 2 == 0:
						_palm(at, 0.7)
					else:
						_totem(at)
				"travincal", "temple":
					if i % 2 == 0:
						_statue(at, yaw)
					else:
						_great_brazier(at)
				_:
					_scaled("rubble", at, yaw, 0.75)
			footprints.append([at, 1.4])
			i += 1


func _scaled(model: String, at: Vector3, yaw: float, size: float) -> Node3D:
	var node := _place(model, at, yaw)
	node.scale = Vector3.ONE * size
	return node


func _grave_cluster(at: Vector3) -> void:
	for k in 3:
		var p := at + Vector3(_rng.randf_range(-0.7, 0.7), 0, _rng.randf_range(-0.6, 0.6))
		var g := _place("gravestone_a" if k % 2 == 0 else "gravestone_b", p, 180.0 + _rng.randf_range(-25, 25))
		g.scale = Vector3.ONE * 0.6
		g.rotation_degrees.z = _rng.randf_range(-10, 10)


func _broken_column(at: Vector3, yaw: float) -> void:
	var h := _rng.randf_range(1.6, 3.2)
	_cyl(0.75, 0.75, 0.35, at, _stone(), 10)
	_cyl(0.55, 0.52, h, at + Vector3(0, 0.35, 0), _stone(), 12)
	var cap := _mesh(spire_mesh(), at + Vector3(0, 0.3 + h, 0), _stone(), yaw, true)
	cap.scale = Vector3(1.1, 0.5, 1.1)
	_column_drum(at + Vector3(1.0, 0, 0.5).rotated(Vector3.UP, deg_to_rad(yaw)), yaw)


func _column_drum(at: Vector3, yaw: float) -> void:
	var c := CylinderMesh.new()
	c.top_radius = 0.52
	c.bottom_radius = 0.52
	c.height = 0.9
	c.radial_segments = 12
	var mi := _mesh(c, at + Vector3(0, 0.5, 0), _stone(), yaw, true)
	mi.rotation_degrees.z = 90.0


func _bone_pile(at: Vector3, size: float) -> void:
	var mound := _mesh(rock_mesh(_rng.randi()), at + Vector3(0, 0.1, 0), _tex("bone", Color(0.62, 0.56, 0.46), 0.8), _rng.randf() * 360.0)
	mound.scale = Vector3(0.75, 0.45, 0.7) * size
	var bones: Array = []
	for k in 26:
		var a := _rng.randf() * TAU
		var r := _rng.randf_range(0.2, 1.0) * size
		var p := at + Vector3(cos(a) * r, 0.0, sin(a) * r)
		p.y = (1.0 - r / size) * 0.55 * size + 0.08
		bones.append(_xf(p, _rng.randf() * 360.0, Vector3(0.07, 0.07, _rng.randf_range(0.35, 0.6)), Vector3(_rng.randf_range(-30, 30), 0, _rng.randf_range(-20, 20))))
	var skulls: Array = []
	for k in 5:
		var a := _rng.randf() * TAU
		var r := _rng.randf_range(0.0, 0.7) * size
		skulls.append(_xf(at + Vector3(cos(a) * r, (1.0 - r / size) * 0.6 * size + 0.12, sin(a) * r), _rng.randf() * 360.0, Vector3(0.2, 0.22, 0.24)))
	var bone := _tex("bone", Color(0.85, 0.8, 0.68), 1.5)
	_batch(unit_box(), bones, bone, true)
	var s := SphereMesh.new()
	s.radial_segments = 8
	s.rings = 5
	_batch(s, skulls, bone, true)


func _sarcophagus(at: Vector3, yaw: float) -> void:
	_box(Vector3(1.1, 0.8, 2.2), at + Vector3(0, 0.4, 0), _stone(0.6), yaw)
	var lid := _box(Vector3(1.25, 0.18, 2.35), at + Vector3(0.12, 0.88, 0.1), _stone(0.6), yaw + 8.0)
	lid.rotation_degrees.z = 4.0


func _stalagmites(at: Vector3, size: float) -> void:
	var xs: Array = []
	for k in 5:
		var p := at + Vector3(_rng.randf_range(-0.8, 0.8), -0.05, _rng.randf_range(-0.8, 0.8)) * size
		var h := _rng.randf_range(1.2, 3.6) * size * (1.4 if k == 0 else 1.0)
		xs.append(_xf(p, _rng.randf() * 360.0, Vector3(h * 0.38, h, h * 0.38), Vector3(_rng.randf_range(-6, 6), 0, _rng.randf_range(-6, 6))))
	_batch(spire_mesh(), xs, _stone(0.35), true)
	var boulder := _mesh(rock_mesh(_rng.randi()), at, _stone(0.35), _rng.randf() * 360.0)
	boulder.scale = Vector3(0.8, 0.5, 0.7) * size


func _spires(at: Vector3, size: float) -> void:
	var xs: Array = []
	for k in 4:
		var p := at + Vector3(_rng.randf_range(-0.7, 0.7), -0.05, _rng.randf_range(-0.7, 0.7)) * size
		var h := _rng.randf_range(2.0, 4.5) * size * (1.3 if k == 0 else 1.0)
		xs.append(_xf(p, _rng.randf() * 360.0, Vector3(h * 0.3, h, h * 0.3), Vector3(_rng.randf_range(-14, 14), 0, _rng.randf_range(-14, 14))))
	_batch(spire_mesh(), xs, _stone(0.35), true)


func _crates(at: Vector3) -> void:
	_place("crate", at + Vector3(-0.4, 0, -0.3), _rng.randf_range(-10, 10))
	_place("crate", at + Vector3(0.5, 0, 0.2), _rng.randf_range(0, 40))
	var top := _place("crate", at + Vector3(0.0, 1.0, -0.1), _rng.randf_range(0, 90))
	top.scale = Vector3.ONE * 0.85
	_place("barrel", at + Vector3(-0.6, 0, 0.7), 0.0)


func _barrels(at: Vector3) -> void:
	for k in 4:
		_place("barrel", at + Vector3(-0.4 + (k % 2) * 0.75, 0, -0.4 + (k / 2) * 0.75), _rng.randf() * 360.0)
	var lying := _place("barrel", at + Vector3(0.9, 0.3, 0.6), 30.0)
	lying.rotation_degrees.x = 88.0


## Silk-wrapped bodies hanging and lying in the spiders' larder, and their egg sacs.
func _cocoons(at: Vector3) -> void:
	var silk := _flat(Color(0.75, 0.75, 0.7), 0.6)
	var s := SphereMesh.new()
	s.radial_segments = 10
	s.rings = 6
	var xs: Array = []
	for k in 3:
		var p := at + Vector3(_rng.randf_range(-0.6, 0.6), 0.35, _rng.randf_range(-0.6, 0.6))
		xs.append(_xf(p, _rng.randf() * 360.0, Vector3(0.35, 0.35, 0.9), Vector3(0, 0, _rng.randf_range(-10, 10))))
	for k in 7:
		var p := at + Vector3(_rng.randf_range(-0.9, 0.9), 0.15, _rng.randf_range(-0.9, 0.9))
		xs.append(_xf(p, 0.0, Vector3.ONE * _rng.randf_range(0.18, 0.3)))
	_batch(s, xs, silk, true)
	_web(at + Vector3(0, 1.2, 0), 2.2, _rng.randf() * 360.0)


var _web_mat: StandardMaterial3D


## A spider's web `size` metres across, hung upright at `at`.
func _web(at: Vector3, size: float, yaw: float) -> void:
	if _web_mat == null:
		var n := 256
		var img := Image.create(n, n, false, Image.FORMAT_RGBA8)
		img.fill(Color(1, 1, 1, 0))
		var c := Vector2(n, n) * 0.5
		var spokes := 14
		for k in spokes:
			var a := TAU * k / spokes + 0.1 * sin(k * 3.7)
			_line(img, c, c + Vector2(cos(a), sin(a)) * n * 0.49, 0.9)
		for ring in range(4, 60, 5):
			for k in spokes:
				var a0 := TAU * k / spokes + 0.1 * sin(k * 3.7)
				var a1 := TAU * (k + 1) / spokes + 0.1 * sin((k + 1) * 3.7)
				var r := ring * n / 128.0 * (1.0 + 0.04 * sin(k * 1.9 + ring))
				_line(img, c + Vector2(cos(a0), sin(a0)) * r, c + Vector2(cos(a1), sin(a1)) * r, 0.6)
		img.generate_mipmaps()
		_web_mat = StandardMaterial3D.new()
		_web_mat.albedo_texture = ImageTexture.create_from_image(img)
		_web_mat.albedo_color = Color(0.85, 0.9, 0.9, 0.55)
		_web_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		_web_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
		_web_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		_web_mat.emission_enabled = false
	var q := QuadMesh.new()
	q.size = Vector2(size, size)
	var mi := _mesh(q, at, _web_mat, yaw, false)
	mi.rotation_degrees.x = _rng.randf_range(-35, -10)


static func _line(img: Image, a: Vector2, b: Vector2, alpha: float) -> void:
	var n := int(a.distance_to(b)) + 1
	for i in n + 1:
		var p := a.lerp(b, float(i) / n)
		var x := int(p.x)
		var y := int(p.y)
		if x >= 0 and y >= 0 and x < img.get_width() and y < img.get_height():
			img.set_pixel(x, y, Color(1, 1, 1, max(img.get_pixel(x, y).a, alpha)))


func _palm(at: Vector3, size: float) -> void:
	var tree := MeshInstance3D.new()
	tree.mesh = Scatter.palm_mesh()
	tree.material_override = Scatter.foliage_material()
	tree.position = at
	tree.rotation_degrees.y = _rng.randf() * 360.0
	tree.scale = Vector3.ONE * size
	add_child(tree)


func _jungle_tree(at: Vector3, size: float) -> void:
	var tree := MeshInstance3D.new()
	tree.mesh = Scatter.palm_mesh() if _rng.randf() < 0.5 else Scatter.broadleaf_mesh()
	tree.material_override = Scatter.foliage_material()
	tree.position = at
	tree.rotation_degrees.y = _rng.randf() * 360.0
	tree.scale = Vector3.ONE * size * _rng.randf_range(0.85, 1.15)
	add_child(tree)


## A Flayer's totem: a pole, crossed sticks, skulls and a guttering flame.
func _totem(at: Vector3) -> void:
	var wood := _tex("timber", Color(0.5, 0.42, 0.36), 0.8)
	_cyl(0.12, 0.09, 3.2, at, wood, 6)
	var bar := _box(Vector3(1.6, 0.1, 0.1), at + Vector3(0, 2.5, 0), wood, _rng.randf() * 180.0)
	bar.rotation_degrees.z = 8.0
	var bone := _tex("bone", Color(0.85, 0.8, 0.68), 1.5)
	var s := SphereMesh.new()
	var xs: Array = []
	for k in 3:
		xs.append(_xf(at + Vector3(0, 1.6 + k * 0.45, 0.12), _rng.randf_range(-30, 30), Vector3(0.22, 0.25, 0.26)))
	_batch(s, xs, bone, true)
	var flame := Fx.fire(0.5)
	flame.position = at + Vector3(0, 3.2, 0)
	add_child(flame)
	var light := Fx.fire_light(3.0, 7.0)
	light.position = at + Vector3(0, 3.0, 0)
	add_child(light)


## A gilded statue of the old faith on its plinth.
func _statue(at: Vector3, yaw: float) -> void:
	_box(Vector3(1.4, 0.9, 1.4), at + Vector3(0, 0.45, 0), _stone(0.6), yaw)
	var gold := Mats.named("gold")
	var body := _cyl(0.38, 0.26, 1.7, at + Vector3(0, 0.9, 0), gold, 10)
	body.rotation_degrees.y = yaw
	var head := SphereMesh.new()
	head.radius = 0.22
	head.height = 0.46
	_mesh(head, at + Vector3(0, 2.85, 0), gold, 0.0, true)
	var arms := _box(Vector3(1.3, 0.16, 0.2), at + Vector3(0, 2.25, 0), gold, yaw)
	arms.rotation_degrees.z = 0.0


## A tall brazier of the temples on a stone foot, burning big.
func _great_brazier(at: Vector3) -> void:
	_cyl(0.6, 0.45, 0.5, at, _stone(0.6), 8)
	var b := _place("brazier", at + Vector3(0, 0.5, 0), 0.0)
	b.scale = Vector3.ONE * 1.3
	var coals := Models.node(b, "fx_fire_1")
	coals.add_child(Fx.fire(1.2))
	var light := Fx.fire_light(7.0, 12.0, false, _look["fire"])
	light.position = Vector3(0, 1.2, 0)
	coals.add_child(light)


# --- Arches and their gates ---

func _arches() -> void:
	for a in level.arches:
		var index: int = a[0]
		var tile: Vector2i = a[1]
		var at := level.tile_pos(tile)
		var frame := _mesh(_arch_mesh(), at, _stone(0.5), 0.0, true)
		footprints.append([at, 3.6])
		_crown(at, String(_look["crown"]))
		for side in [-1.0, 1.0]:   # a torch on each pier, facing the camera: the gate is where the fight is held
			var flame := Fx.fire(0.35)
			flame.position = at + Vector3(side * 2.65, 3.05, ARCH_DEPTH * 0.5 + 0.25)
			add_child(flame)
		var sconce := Fx.fire_light(3.5, 8.0, false, _look["fire"])
		sconce.position = at + Vector3(0, 3.4, ARCH_DEPTH * 0.5 + 1.2)
		add_child(sconce)
		_gates[index] = _gate_parts(at)


## A gate for the arch at `at`, hidden until it is built: an iron portcullis over timber leaves, and the heap it
## leaves when it breaks. Its parts keep their whole transforms (`rest`) for `gate` to batter from.
func _gate_parts(at: Vector3) -> Dictionary:
	var iron := (Mats.named("iron") as StandardMaterial3D).duplicate() as StandardMaterial3D
	var wood := _tex("planks", Color(0.62, 0.5, 0.38), 0.7).duplicate() as StandardMaterial3D
	var holder := Node3D.new()
	holder.position = at
	holder.visible = false
	add_child(holder)
	var parts: Array = []   # 7 bars, 3 rails, 5 boards
	var bar := BoxMesh.new()
	bar.size = Vector3(0.15, 1.0, 0.15)
	for k in 7:
		var x := -ARCH_R + (k + 0.5) * ARCH_R * 2.0 / 7.0
		var h := ARCH_SPRING + sqrt(ARCH_R * ARCH_R - x * x) - 0.08
		parts.append(_part(holder, bar, iron, Vector3(x, h * 0.5, 0), Vector3(1, h, 1)))
	var rail := BoxMesh.new()
	rail.size = Vector3(1.0, 0.16, 0.2)
	for y in [0.45, 1.6, 2.8]:
		parts.append(_part(holder, rail, iron, Vector3(0, y, 0), Vector3(ARCH_R * 2.0 - 0.06, 1, 1)))
	var board := BoxMesh.new()
	board.size = Vector3(0.72, 1.0, 0.09)
	for k in 5:
		parts.append(_part(holder, board, wood, Vector3(-1.52 + k * 0.76, 0.95, -0.15), Vector3(1, 1.9, 1)))
	var heap := Node3D.new()
	heap.position = at
	heap.visible = false
	add_child(heap)
	for side in [-1.0, 1.0]:
		var r := Models.make("rubble")
		r.position = Vector3(side * 1.25, 0, side * 0.35)
		r.rotation_degrees.y = 70.0 * side
		r.scale = Vector3.ONE * 0.75
		heap.add_child(r)
	for k in 4:   # splintered boards and bent bars strewn through the arch
		var p := _part(heap, board, wood, Vector3(_rng.randf_range(-1.6, 1.6), 0.06, _rng.randf_range(-1.2, 1.2)),
			Vector3(1, _rng.randf_range(0.8, 1.6), 1))
		p.rotation_degrees = Vector3(90.0, _rng.randf() * 180.0, 0)
	for k in 3:
		var p := _part(heap, bar, iron, Vector3(_rng.randf_range(-1.5, 1.5), 0.08, _rng.randf_range(-1.0, 1.0)),
			Vector3(1, _rng.randf_range(1.8, 3.0), 1))
		p.rotation_degrees = Vector3(0, _rng.randf() * 180.0, 90.0 + _rng.randf_range(-8, 8))
	return {"parts": parts, "holder": holder, "heap": heap, "iron": iron, "wood": wood,
		"state": Vector3i(-1, -1, -1), "life": -1.0, "rest": parts.map(func(n): return (n as Node3D).transform)}


func _part(parent: Node3D, mesh: Mesh, mat: Material, at: Vector3, scale: Vector3) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	mi.position = at
	mi.scale = scale
	parent.add_child(mi)
	return mi


## The gate in arch `index` as the server says: standing (with its life 0..1), broken to rubble, or not built.
## A standing gate is battered a quarter of its life at a time: boards split and fall out of its leaves, bars bend
## and give way, rails drop; its timber chars and its iron darkens as the life goes.
func gate(index: int, built: bool, rubble: bool, life: float) -> void:
	if not _gates.has(index):
		return
	var g: Dictionary = _gates[index]
	life = clamp(life, 0.0, 1.0)
	var stage: int = min(3, 4 - int(ceil(life * 4.0))) if built else 0
	var state := Vector3i(int(built), int(rubble), stage)
	var was: Vector3i = g["state"]
	if state != was:
		g["state"] = state
		var holder: Node3D = g["holder"]
		holder.visible = built
		(g["heap"] as Node3D).visible = rubble and not built
		var parts: Array = g["parts"]
		var rest: Array = g["rest"]
		for k in parts.size():
			(parts[k] as Node3D).transform = rest[k]
			(parts[k] as Node3D).visible = true
		# 0..6 bars, 7..9 rails (low to high), 10..14 boards
		if stage >= 1:
			_split(parts[11], 0.55)
			_bend(parts[2], 0.2)
			_bend(parts[4], -0.14)
		if stage >= 2:
			parts[13].visible = false
			parts[3].visible = false
			_bend(parts[5], 0.32)
			_bend(parts[8], 0.14)
			(parts[8] as Node3D).position.y -= 0.3
		if stage >= 3:
			parts[12].visible = false
			_split(parts[10], 0.4)
			_split(parts[14], 0.3)
			_bend(parts[1], -0.38)
			_bend(parts[7], -0.1)
			(parts[9] as Node3D).scale.x *= 0.55
			(parts[9] as Node3D).position.x -= 0.8
		var at := holder.position
		if built and was.x == 1 and stage > was.z:   # a quarter of its life gone: splinters and sparks
			var sp := Fx.sparks(Color(1.0, 0.6, 0.25), 30, 5.0)
			sp.position = at + Vector3(0, 1.4, 0)
			add_child(sp)
		if rubble and was.y == 0:   # it gave way
			var puff := Fx.puff(2.4)
			puff.position = at + Vector3(0, 1.0, 0)
			add_child(puff)
			var sp := Fx.sparks(Color(1.0, 0.55, 0.2), 40, 6.0)
			sp.position = at + Vector3(0, 1.4, 0)
			add_child(sp)
	if built and abs(life - float(g["life"])) > 0.01:
		g["life"] = life
		var k: float = lerp(0.3, 1.0, life)
		(g["iron"] as StandardMaterial3D).albedo_color = Color(0.7 * k, 0.66 * k, 0.62 * k)
		var c: float = lerp(0.14, 1.0, life)   # the timber chars to black
		(g["wood"] as StandardMaterial3D).albedo_color = Color(0.62 * c, 0.5 * c, 0.38 * c)


## A board snapped off: only its lower `keep` stays, ragged.
static func _split(board: Node3D, keep: float) -> void:
	var h := board.scale.y
	board.scale.y = h * keep
	board.position.y -= h * (1.0 - keep) * 0.5
	board.rotate_object_local(Vector3(0, 0, 1), 0.06)


## What tops an arch: a slate or thatched gable (a lychgate), merlons, spikes, or a gilded dome.
func _crown(at: Vector3, kind: String) -> void:
	var top := at + Vector3(0, ARCH_TOP + 0.3, 0)
	match kind:
		"gable", "thatch":
			var roof := PrismMesh.new()
			roof.size = Vector3(ARCH_W * 2.0 + 0.9, 1.5, ARCH_DEPTH + 1.0)
			var mat := _tex("thatch", Color(0.7, 0.62, 0.48), 0.6) if kind == "thatch" else _tex("slate", Color(0.62, 0.65, 0.72), 0.6)
			var mi := _mesh(roof, top + Vector3(0, 0.75, 0), mat, 0.0, true)
			mi.rotation_degrees.y = 0.0
		"merlons":
			for k in 4:
				_box(Vector3(1.0, 0.85, ARCH_DEPTH + 0.3), top + Vector3(-2.7 + k * 1.8, 0.42, 0), _stone(0.5))
		"spikes":
			var xs: Array = []
			for k in 5:
				var h: float = 2.6 - abs(k - 2) * 0.6
				xs.append(_xf(top + Vector3(-2.8 + k * 1.4, -0.1, 0), k * 40.0, Vector3(h * 0.32, h, h * 0.32), Vector3(0, 0, (k - 2) * -9.0)))
			_batch(spire_mesh(), xs, _stone(0.35), true)
		"dome":
			var gold := Mats.named("gold")
			var dome := SphereMesh.new()
			dome.radius = 0.9
			dome.height = 0.9
			dome.is_hemisphere = true
			_box(Vector3(2.4, 0.4, ARCH_DEPTH + 0.2), top + Vector3(0, 0.2, 0), _stone(0.5))
			_mesh(dome, top + Vector3(0, 0.4, 0), gold, 0.0, true)
			for side in [-1.0, 1.0]:
				var ball := SphereMesh.new()
				ball.radius = 0.28
				ball.height = 0.56
				_mesh(ball, top + Vector3(side * 3.0, 0.28, 0), gold, 0.0, true)


static func _bend(bar: Node3D, angle: float) -> void:
	bar.rotate_object_local(Vector3(0, 0, 1), angle)
	bar.position.x += angle * 0.6


## The arch over a gate socket: piers on the wall tiles either side, a round arch over the lane, a cornice.
static func _arch_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var r := ARCH_R
	var y0 := ARCH_SPRING
	var w := ARCH_W
	var top := ARCH_TOP
	var d := ARCH_DEPTH * 0.5
	for s in [-1.0, 1.0]:
		_cube(st, Vector3(s * (r + w) * 0.5, y0 * 0.5, 0), Vector3(w - r, y0, ARCH_DEPTH))
		_cube(st, Vector3(s * (r + w) * 0.5, 0.2, 0), Vector3(w - r + 0.3, 0.4, ARCH_DEPTH + 0.3))   # plinth
		_cube(st, Vector3(s * (r + w) * 0.5, y0 - 0.1, 0), Vector3(w - r + 0.2, 0.25, ARCH_DEPTH + 0.2))   # impost
	var angles: Array = []
	for i in 17:
		angles.append(PI * i / 16.0)
	var corner := atan2(top - y0, w)
	angles.append(corner)
	angles.append(PI - corner)
	angles.sort()
	for i in angles.size() - 1:
		var a0: float = angles[i]
		var a1: float = angles[i + 1]
		var p0 := Vector2(cos(a0) * r, y0 + sin(a0) * r)
		var p1 := Vector2(cos(a1) * r, y0 + sin(a1) * r)
		var q0 := _frame_point(a0, w, top - y0) + Vector2(0, y0)
		var q1 := _frame_point(a1, w, top - y0) + Vector2(0, y0)
		for z in [d, -d]:
			_quad(st, Vector3(p0.x, p0.y, z), Vector3(q0.x, q0.y, z), Vector3(q1.x, q1.y, z), Vector3(p1.x, p1.y, z), Vector3(0, 0, sign(z)))
		var mid := ((p0 + p1) * 0.5 - Vector2(0, y0)).normalized()
		_quad(st, Vector3(p0.x, p0.y, -d), Vector3(p1.x, p1.y, -d), Vector3(p1.x, p1.y, d), Vector3(p0.x, p0.y, d), -Vector3(mid.x, mid.y, 0))
	_cube(st, Vector3(0, top + 0.15, 0), Vector3(w * 2.0 + 0.3, 0.3, ARCH_DEPTH + 0.3))   # cornice
	_cube(st, Vector3(0, y0 + r + 0.05, 0), Vector3(0.55, 0.75, ARCH_DEPTH + 0.12))   # keystone
	for s in [-1.0, 1.0]:   # the frame's outer sides above the piers
		_quad(st, Vector3(s * w, y0, -d), Vector3(s * w, top, -d), Vector3(s * w, top, d), Vector3(s * w, y0, d), Vector3(s, 0, 0))
	st.generate_tangents()
	return st.commit()


static func _frame_point(a: float, w: float, h: float) -> Vector2:
	var c := cos(a)
	var s := sin(a)
	var t := INF
	if abs(c) > 1e-5:
		t = w / abs(c)
	if s > 1e-5:
		t = min(t, h / s)
	return Vector2(c, s) * t


static func _cube(st: SurfaceTool, c: Vector3, size: Vector3) -> void:
	var h := size * 0.5
	for axis in 3:
		for s in [-1.0, 1.0]:
			var n := Vector3.ZERO
			n[axis] = s
			var u := Vector3.ZERO
			u[(axis + 1) % 3] = h[(axis + 1) % 3]
			var v := Vector3.ZERO
			v[(axis + 2) % 3] = h[(axis + 2) % 3]
			var f := c + n * h[axis]
			_quad(st, f - u - v, f + u - v, f + u + v, f - u + v, n)


## A quad with its normal, wound as Godot draws front faces (clockwise seen from the front).
static func _quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3, n: Vector3) -> void:
	if (b - a).cross(c - a).dot(n) > 0.0:
		var t := b
		b = d
		d = t
	for p in [a, b, c, a, c, d]:
		var q: Vector3 = p
		st.set_normal(n)
		st.set_uv(Vector2(q.x + q.z, q.y))
		st.add_vertex(q)


# --- The border ring ---

## The ring's wall tiles as straight runs: [from, to] (metres, the run's outer ends), facing (the wall models'),
## and which edge ("n", "s", "w", "e").
func _ring_runs() -> Array:
	var runs: Array = []
	var edges := [
		[Vector2i(0, 0), Vector2i(1, 0), level.width, 0.0, "n"],
		[Vector2i(0, level.height - 1), Vector2i(1, 0), level.width, 180.0, "s"],
		[Vector2i(0, 1), Vector2i(0, 1), level.height - 2, 90.0, "w"],
		[Vector2i(level.width - 1, 1), Vector2i(0, 1), level.height - 2, -90.0, "e"],
	]
	for e in edges:
		var start: Vector2i = e[0]
		var step: Vector2i = e[1]
		var count: int = e[2]
		var first := -1
		for i in count + 1:
			var wall := i < count and level.cell(start + step * i) == "#"
			if wall and first < 0:
				first = i
			elif not wall and first >= 0:
				var dir := Vector3(step.x, 0, step.y)
				var a := level.tile_pos(start + step * first) - dir * Level.TILE * 0.5
				var b := level.tile_pos(start + step * (i - 1)) + dir * Level.TILE * 0.5
				runs.append([a, b, float(e[3]), String(e[4])])
				first = -1
	return runs


## What stands on the field's border ring: kept low on the south edge, which the battle camera looks over.
func _ring() -> void:
	var style: String = _look["ring"]
	var blocks: Array = []
	var block_mat: Material = _stone()
	var rocks: Array = [[], [], [], []]
	var spikes: Array = []
	var posts: Array = []
	for run in _ring_runs():
		var a: Vector3 = run[0]
		var b: Vector3 = run[1]
		var facing: float = run[2]
		var edge: String = run[3]
		var low := edge == "s"
		var dir := (b - a).normalized()
		var length := a.distance_to(b)
		match style:
			"drystone", "ruin":
				var n: int = max(1, int(round(length / 4.0)))
				for i in n:
					var c := a.lerp(b, (i + 0.5) / n)
					var broken := _rng.randf() < (0.55 if style == "ruin" else 0.28)
					if style == "ruin" and _rng.randf() < 0.2:
						continue
					var node := _place("wall_broken" if broken else "wall", c, facing + _rng.randf_range(-2.0, 2.0))
					node.scale.x = length / n / 4.0 * (-1.0 if _rng.randf() < 0.5 else 1.0)
			"nave", "crypt":
				var h := 0.8 if low else (0.9 if style == "nave" else 2.6)
				var n: int = max(1, int(round(length / 2.0)))
				for i in n:
					var c := a.lerp(b, (i + 0.5) / n)
					var hh := h * _rng.randf_range(0.75, 1.05) if style == "nave" else h
					var size := Vector3(length / n + 0.02, hh, 1.2)
					blocks.append(_xf(c + Vector3(0, hh * 0.5, 0), facing, size))
				if style == "crypt" and not low:
					blocks.append(_xf((a + b) * 0.5 + Vector3(0, h + 0.15, 0), facing, Vector3(length, 0.3, 1.5)))
			"rock":
				var n := int(length / (1.4 if low else 1.8)) + 1
				for i in n:
					var c := a.lerp(b, (i + _rng.randf_range(0.2, 0.8)) / n) + Vector3(_rng.randf_range(-0.5, 0.5), 0, _rng.randf_range(-0.5, 0.5))
					var s := _rng.randf_range(0.45, 0.8) if low else _rng.randf_range(0.7, 1.4)
					c.y = -0.3 * s
					rocks[_rng.randi() % 4].append(_xf(c, _rng.randf() * 360.0, Vector3(s * _rng.randf_range(0.9, 1.4), s * (0.7 if low else 1.1), s), Vector3(_rng.randf_range(-15, 15), 0, _rng.randf_range(-15, 15))))
					if not low and _rng.randf() < 0.35:
						var h := _rng.randf_range(1.5, 3.5)
						spikes.append(_xf(c + Vector3(_rng.randf_range(-0.8, 0.8), 0, _rng.randf_range(-0.8, 0.8)), _rng.randf() * 360.0, Vector3(h * 0.35, h, h * 0.35), Vector3(_rng.randf_range(-10, 10), 0, _rng.randf_range(-10, 10))))
			"quay":
				blocks.append(_xf((a + b) * 0.5 + Vector3(0, 0.25, 0), facing, Vector3(length, 0.5, 1.4)))
				var n: int = max(1, int(round(length / 4.0)))
				for i in n:
					posts.append(_xf(a.lerp(b, (i + 0.5) / n) + Vector3(0, 0.5, 0), 0.0, Vector3(0.36, 0.7, 0.36)))
			"wood":
				var n: int = max(1, int(round(length / 5.0)))
				for i in n:
					if _rng.randf() < 0.25:
						continue
					var c := a.lerp(b, (i + 0.5) / n)
					var log := _cyl(0.32, 0.28, length / n * _rng.randf_range(0.8, 1.05), Vector3.ZERO, _tex("timber", Color(0.45, 0.4, 0.34), 0.7), 8)
					log.position = c + Vector3(0, 0.3, 0)
					log.basis = Basis(Vector3.UP, deg_to_rad(facing + _rng.randf_range(-6, 6))) * Basis(Vector3(0, 0, 1), PI * 0.5)
			"balustrade":
				blocks.append(_xf((a + b) * 0.5 + Vector3(0, 0.12, 0), facing, Vector3(length, 0.24, 0.8)))
				blocks.append(_xf((a + b) * 0.5 + Vector3(0, 0.95, 0), facing, Vector3(length, 0.16, 0.6)))
				var n := int(length / 0.45)
				for i in n:
					posts.append(_xf(a.lerp(b, (i + 0.5) / n) + Vector3(0, 0.555, 0), 0.0, Vector3(0.16, 0.63, 0.16)))
				var m: int = max(1, int(round(length / 4.0)))
				for i in m + 1:
					blocks.append(_xf(a.lerp(b, float(i) / m) + Vector3(0, 0.55, 0), facing, Vector3(0.5, 1.1, 0.7)))
	if not blocks.is_empty():
		_batch(unit_box(), blocks, block_mat, true)
	for k in 4:
		if not rocks[k].is_empty():
			_batch(rock_mesh(k), rocks[k], _stone(0.35), true)
	if not spikes.is_empty():
		_batch(spire_mesh(), spikes, _stone(0.35), true)
	if not posts.is_empty():
		var c := CylinderMesh.new()
		c.radial_segments = 8
		c.height = 1.0
		c.top_radius = 0.5
		c.bottom_radius = 0.5
		var post_mat: Material = _tex("timber", Color(0.42, 0.36, 0.3), 0.6) if style == "quay" else _stone(0.6)
		_batch(c, posts, post_mat, true)


## Lights just outside the field's border, `spacing` metres apart: the warm pools that frame the battle as the
## burning houses frame Tristram's. A brazier, a lamp on its post, a torch on a pole, or a pyre of bones.
func _ring_lights(kind: String, spacing: float) -> void:
	var w := level.width * Level.TILE
	var h := level.height * Level.TILE
	var corners := [Vector3(-2.4, 0, -2.4), Vector3(w + 2.4, 0, -2.4), Vector3(w + 2.4, 0, h + 2.4), Vector3(-2.4, 0, h + 2.4)]
	var fire: Color = _look["fire"]
	for k in 4:
		var a: Vector3 = corners[k]
		var b: Vector3 = corners[(k + 1) % 4]
		var n: int = max(1, int(a.distance_to(b) / spacing))
		for i in n:
			var p := a.lerp(b, (i + 0.5) / n)
			if not _free(p, 1.0, 3.0):
				continue
			footprints.append([p, 1.0])
			match kind:
				"brazier":
					var brazier := _place("brazier", p, _rng.randf() * 360.0)
					var coals := Models.node(brazier, "fx_fire_1")
					coals.add_child(Fx.fire(0.8))
					var light := Fx.fire_light(6.0, 12.0, false, fire)
					light.position = Vector3(0, 1.4, 0)
					coals.add_child(light)
				"lamp":
					_place("lamppost", p, _rng.randf() * 360.0)
					var light := Fx.fire_light(3.5, 10.0, false, fire)
					light.position = p + Vector3(0, 2.6, 0)
					add_child(light)
				"torch":
					_cyl(0.07, 0.05, 2.4, p, _tex("timber", Color(0.4, 0.34, 0.28), 0.8), 6)
					var flame := Fx.fire(0.55)
					flame.position = p + Vector3(0, 2.35, 0)
					add_child(flame)
					var light := Fx.fire_light(5.0, 11.0, false, fire)
					light.position = p + Vector3(0, 2.8, 0)
					add_child(light)
				"pyre":
					_bone_pile(p, 0.9)
					var flame := Fx.fire(1.3)
					flame.position = p + Vector3(0, 0.3, 0)
					add_child(flame)
					var light := Fx.fire_light(7.0, 13.0, false, fire)
					light.position = p + Vector3(0, 2.2, 0)
					light.light_volumetric_fog_energy = 0.3
					add_child(light)


# --- Particles in the air ---

## Specks drifting over the field: embers, dust, fireflies, the graveyard's wisps.
func _motes(amount: int, color: Color, size: float, glow: bool, drift: Vector3, height := 8.0, life := 10.0) -> void:
	var p := GPUParticles3D.new()
	p.amount = amount
	p.lifetime = life
	p.preprocess = life
	p.local_coords = false
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	pm.emission_box_extents = Vector3(48, height * 0.5, 30)
	pm.direction = drift.normalized() if drift.length() > 0.0 else Vector3.UP
	pm.spread = 40.0
	pm.initial_velocity_min = drift.length() * 0.5
	pm.initial_velocity_max = drift.length()
	pm.gravity = drift * 0.1
	pm.turbulence_enabled = true
	pm.turbulence_noise_strength = 1.5
	pm.turbulence_noise_scale = 5.0
	pm.turbulence_influence_min = 0.05
	pm.turbulence_influence_max = 0.15
	pm.scale_min = 0.6
	pm.scale_max = 1.3
	var c := color
	pm.color_ramp = Fx.ramp([[0.0, Color(c.r, c.g, c.b, 0.0)], [0.2, c], [0.8, c], [1.0, Color(c.r, c.g, c.b, 0.0)]], glow)
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(size, size)
	if glow:
		q.material = Fx.billboard(Fx.dot_texture(), true)
	else:
		var m := StandardMaterial3D.new()
		m.albedo_texture = Fx.dot_texture()
		m.vertex_color_use_as_albedo = true
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.shading_mode = BaseMaterial3D.SHADING_MODE_PER_VERTEX
		m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
		q.material = m
	p.draw_pass_1 = q
	p.position = level.centre() + Vector3(0, height * 0.5, 0)
	p.visibility_aabb = AABB(Vector3(-70, -20, -50), Vector3(140, 50, 100))
	add_child(p)


# --- The themes' surroundings ---

## The churchyard: rows of graves all round, mausoleums, dead trees, shrines with a candle, wisps over the stones.
func _graveyard() -> void:
	var stones_a: Array = []
	var stones_b: Array = []
	for row in 12:
		var z := -4.0 - row * 2.4
		_grave_row(stones_a, stones_b, Vector2(-30, 96), z, 180.0)
	for row in 10:
		var z := 39.5 + row * 2.4
		_grave_row(stones_a, stones_b, Vector2(-30, 96), z, 0.0)
	for col in 6:
		var x := -4.0 - col * 2.6
		for zz in range(0, 36, 2):
			var p := Vector3(x + _rng.randf_range(-0.3, 0.3), 0, zz + 1.0 + _rng.randf_range(-0.3, 0.3))
			if _free(p, 1.0):
				(stones_a if _rng.randf() < 0.5 else stones_b).append(_xf(p, 90.0 + _rng.randf_range(-15, 15), Vector3.ONE * _rng.randf_range(0.75, 1.0), Vector3(_rng.randf_range(-8, 8), 0, _rng.randf_range(-6, 6))))
	_crowd("gravestone_a", stones_a, false)
	_crowd("gravestone_b", stones_b, false)
	for at in [Vector3(10, 0, -13), Vector3(37, 0, -16), Vector3(58, 0, -12), Vector3(-14, 0, -6), Vector3(24, 0, 50), Vector3(52, 0, 54)]:
		var p: Vector3 = at
		if _free(p, 3.0, 3.0):
			_mausoleum(p, 180.0 if p.z < 18.0 else 0.0)
	for p in _spots(Rect2(-24, -16, 116, 72), 10, 2.0, 1.5):
		_scaled("dead_tree", p, _rng.randf() * 360.0, _rng.randf_range(0.9, 1.4))
	for p in _spots(Rect2(-6, -6, 78, 4), 3, 1.5, 0.5):
		_place("wayside_shrine", p, 180.0)
	_motes(40, Color(0.45, 1.0, 0.75) * 2.2, 0.18, true, Vector3(0.1, 0.25, 0.0), 3.0, 12.0)


func _grave_row(a: Array, b: Array, span: Vector2, z: float, facing: float) -> void:
	var x := span.x
	while x < span.y:
		x += _rng.randf_range(1.8, 2.8)
		var p := Vector3(x, 0, z + _rng.randf_range(-0.35, 0.35))
		if not _outside(p, 1.0) or not _free(p, 1.0) or _rng.randf() < 0.12:
			continue
		p.y = level.ground_height(p.x, p.z) - 0.05
		var t := _xf(p, facing + _rng.randf_range(-14, 14), Vector3.ONE * _rng.randf_range(0.75, 1.05), Vector3(_rng.randf_range(-9, 9), 0, _rng.randf_range(-7, 7)))
		(a if _rng.randf() < 0.5 else b).append(t)


## A family tomb: a stone house with a slate roof and a black doorway, columns either side.
func _mausoleum(at: Vector3, facing: float) -> void:
	var root := Node3D.new()
	root.position = at
	root.rotation_degrees.y = facing
	add_child(root)
	var stone := _stone(0.5)
	var parts := [[Vector3(4.8, 0.4, 6.4), Vector3(0, 0.2, 0)], [Vector3(4.0, 3.2, 5.4), Vector3(0, 2.0, 0.2)]]
	for pt in parts:
		var b := BoxMesh.new()
		b.size = pt[0]
		var mi := MeshInstance3D.new()
		mi.mesh = b
		mi.material_override = stone
		mi.position = pt[1]
		root.add_child(mi)
	var roof := PrismMesh.new()
	roof.size = Vector3(4.8, 1.7, 6.4)
	var rmi := MeshInstance3D.new()
	rmi.mesh = roof
	rmi.material_override = _tex("slate", Color(0.7, 0.72, 0.78), 0.6)
	rmi.position = Vector3(0, 4.45, 0.1)
	root.add_child(rmi)
	var door := BoxMesh.new()
	door.size = Vector3(1.3, 2.2, 0.1)
	var dmi := MeshInstance3D.new()
	dmi.mesh = door
	dmi.material_override = _flat(Color(0.01, 0.01, 0.012))
	dmi.position = Vector3(0, 1.5, -2.52)
	root.add_child(dmi)
	for s in [-1.0, 1.0]:
		var c := CylinderMesh.new()
		c.top_radius = 0.2
		c.bottom_radius = 0.24
		c.height = 3.2
		var cmi := MeshInstance3D.new()
		cmi.mesh = c
		cmi.material_override = stone
		cmi.position = Vector3(s * 1.5, 2.0, -2.95)
		root.add_child(cmi)
	footprints.append([at, 4.5])


## The desecrated nave, roofless: its north wall with the stained glass still in it, columns on the ring, pews
## tipped over, candles at the walls' feet and the moon falling through the windows in shafts.
func _nave() -> void:
	var stone := _stone(0.45)
	var x0 := -20.0
	var x1 := 82.0
	var z := -6.0
	var bay := 8.0
	var glass := Mats.named("stained_glass")
	var n := int((x1 - x0) / bay)
	var pane := QuadMesh.new()
	pane.size = Vector2(2.6, 6.0)
	for i in n + 1:
		var px := x0 + i * bay
		var broken := _rng.randf() < 0.3
		var top := _rng.randf_range(6.0, 8.5) if broken else _rng.randf_range(11.5, 13.5)
		_box(Vector3(2.0, top + 1.0, 2.2), Vector3(px, top * 0.5, z), stone)   # pier
		if i % 2 == 0:
			_banner(Vector3(px, 4.5, z + 1.15))
		if i == n:
			break
		var cx := px + bay * 0.5
		_box(Vector3(bay - 2.0, 3.0, 1.2), Vector3(cx, 1.5, z), stone)   # sill wall
		var jamb := 6.2 if not broken else _rng.randf_range(1.0, 3.5)
		for s2 in [-1.0, 1.0]:
			_box(Vector3(0.8, jamb, 1.0), Vector3(cx + s2 * 1.7, 3.0 + jamb * 0.5, z), stone)
		if not broken:
			_box(Vector3(bay - 2.0, top - 9.2, 1.2), Vector3(cx, 9.2 + (top - 9.2) * 0.5, z), stone)
			_mesh(pane, Vector3(cx, 6.1, z + 0.1), glass, 0.0, false)
	_box(Vector3(2.0, 12.0, 52.0), Vector3(-21.0, 6.0, 18.0), stone)   # the west front
	for p in _spots(Rect2(-14, -4.6, 92, 3.0), 7, 0.6, 0.0):
		_candles(p)
	# columns on the ring: whole along the north wall, broken stumps along the south
	for run in _ring_runs():
		var a: Vector3 = run[0]
		var b: Vector3 = run[1]
		var edge: String = run[3]
		if edge != "n" and edge != "s":
			continue
		var k := int(a.distance_to(b) / 8.0)
		for i in k:
			var c := a.lerp(b, (i + 0.5) / max(k, 1))
			var h := 9.0 if edge == "n" else _rng.randf_range(0.8, 2.4)
			_cyl(0.8, 0.8, 0.5, c, stone, 10)
			_cyl(0.55, 0.5, h, c + Vector3(0, 0.5, 0), stone, 12)
			if edge == "n":
				_box(Vector3(1.5, 0.5, 1.5), c + Vector3(0, h + 0.75, 0), stone)
	# the south aisle: pews, most tipped over, and the low broken south wall beyond
	var pews: Array = []
	var parts := [[Vector3(0, 0.45, 0), Vector3(2.4, 0.1, 0.45)], [Vector3(0, 0.78, 0.22), Vector3(2.4, 0.6, 0.08)],
		[Vector3(-1.15, 0.42, 0.05), Vector3(0.08, 0.84, 0.6)], [Vector3(1.15, 0.42, 0.05), Vector3(0.08, 0.84, 0.6)]]
	for row in 3:
		for x in range(-8, 76, 3):
			var p := Vector3(x + _rng.randf_range(-0.5, 0.5), 0.0, 39.0 + row * 1.8 + _rng.randf_range(-0.2, 0.2))
			if not _free(p, 1.0, 2.0) or _rng.randf() < 0.3:
				continue
			var tipped := _rng.randf() < 0.45
			var base := _xf(p + Vector3(0, 0.1 if tipped else 0.0, 0), _rng.randf_range(-12, 12), Vector3.ONE, Vector3(-90.0 if tipped else 0.0, 0, 0))
			for part in parts:
				pews.append(base * Transform3D(Basis.from_scale(part[1]), part[0]))
	_batch(unit_box(), pews, _tex("planks", Color(0.5, 0.38, 0.3), 0.8), true)
	for x in range(-18, 80, 6):
		var h := _rng.randf_range(1.0, 3.5)
		_box(Vector3(6.0, h, 1.2), Vector3(x + 3.0, h * 0.5, 47.0), stone, 0.0, false)
	for p in _spots(Rect2(-14, -5, 92, 4), 5, 1.5, 0.0):
		_place("rubble", p, _rng.randf() * 360.0)
	for i in 3:   # moonlight through the windows
		var shaft := SpotLight3D.new()
		shaft.light_color = Color(0.55, 0.65, 1.0)
		shaft.light_energy = 3.0
		shaft.spot_range = 40.0
		shaft.spot_angle = 9.0
		shaft.light_volumetric_fog_energy = 6.0
		shaft.shadow_enabled = false
		shaft.position = Vector3(8.0 + i * 24.0, 16.0, -12.0)
		add_child(shaft)
		shaft.look_at(Vector3(14.0 + i * 24.0, 0.0, 12.0 + 4.0 * i))
	_motes(500, Color(0.9, 0.85, 0.75, 0.35), 0.05, false, Vector3(0.05, -0.05, 0.02), 10.0, 16.0)


func _banner(at: Vector3) -> void:
	var q := QuadMesh.new()
	q.size = Vector2(1.3, 4.5)
	_mesh(q, at, Mats.named("banner"), 0.0, false)


## A cluster of candles burning on the floor.
func _candles(at: Vector3) -> void:
	var wax := _flat(Color(0.8, 0.75, 0.62), 0.6)
	var flame := Mats.glow(Color(1.0, 0.6, 0.25), 6.0)
	var c := CylinderMesh.new()
	c.top_radius = 0.05
	c.bottom_radius = 0.05
	c.height = 1.0
	c.radial_segments = 6
	var s := SphereMesh.new()
	s.radius = 0.035
	s.height = 0.09
	s.radial_segments = 6
	s.rings = 3
	var bodies: Array = []
	var tips: Array = []
	for k in 7:
		var p := at + Vector3(_rng.randf_range(-0.5, 0.5), 0, _rng.randf_range(-0.4, 0.4))
		var h := _rng.randf_range(0.15, 0.5)
		bodies.append(_xf(p + Vector3(0, h * 0.5, 0), 0.0, Vector3(1, h, 1)))
		tips.append(_xf(p + Vector3(0, h + 0.05, 0), 0.0))
	_batch(c, bodies, wax, false)
	_batch(s, tips, flame, false)
	var light := Fx.fire_light(1.6, 5.0, false, Color(1.0, 0.6, 0.3))
	light.position = at + Vector3(0, 0.7, 0)
	add_child(light)


## The catacombs: the bone halls' walls with skulls in their niches, sarcophagi and bone heaps in the corners,
## torches on the walls; beyond, the rock the halls were cut from.
func _crypt() -> void:
	for p in _spots(Rect2(-14, -8, 94, 52), 14, 1.6, 0.6):
		if _rng.randf() < 0.5:
			_bone_pile(p, _rng.randf_range(0.9, 1.4))
		else:
			_sarcophagus(p, _rng.randf_range(-10, 10) + (90.0 if _rng.randf() < 0.5 else 0.0))
	# skull niches along the inside of the north wall
	var skulls: Array = []
	for run in _ring_runs():
		var a: Vector3 = run[0]
		var b: Vector3 = run[1]
		var edge: String = run[3]
		if edge == "s":
			continue
		var inward := Vector3(0, 0, 1) if edge == "n" else (Vector3(1, 0, 0) if edge == "w" else Vector3(-1, 0, 0))
		var dir := (b - a).normalized()
		var n := int(a.distance_to(b) / 0.6)
		for i in n:
			for row in 3:
				if _rng.randf() < 0.25:
					continue
				var p := a + dir * (i + 0.5) * 0.6 + inward * 0.62 + Vector3(0, 0.55 + row * 0.62, 0)
				skulls.append(_xf(p, _rng.randf_range(-25, 25), Vector3(0.21, 0.24, 0.25)))
		var t := int(a.distance_to(b) / 10.0)
		for i in t:   # torches on the wall
			var p := a + dir * (i + 0.5) * a.distance_to(b) / t + inward * 0.8 + Vector3(0, 2.2, 0)
			var flame := Fx.fire(0.45)
			flame.position = p
			add_child(flame)
			var light := Fx.fire_light(3.5, 9.0, false, _look["fire"])
			light.position = p + inward * 0.6 + Vector3(0, 0.3, 0)
			add_child(light)
	var s := SphereMesh.new()
	s.radial_segments = 8
	s.rings = 5
	_batch(s, skulls, _tex("bone", Color(0.85, 0.8, 0.68), 1.5), false)
	_motes(400, Color(0.8, 0.75, 0.65, 0.3), 0.05, false, Vector3(0.03, -0.04, 0.0), 8.0, 16.0)


## The caves: rock walls close round the field (the floor itself rises into them), stalagmites at their feet,
## lava glowing in its pools, embers and dust in the air.
func _caves() -> void:
	for p in _spots(Rect2(-22, -14, 110, 64), 26, 1.2, 0.5):
		_stalagmites(p, _rng.randf_range(0.8, 1.6))
	var boulders: Array = [[], [], [], []]
	for p in _spots(Rect2(-24, -16, 114, 68), 40, 1.0, 0.5):
		var s := _rng.randf_range(0.6, 1.8)
		boulders[_rng.randi() % 4].append(_xf(p, _rng.randf() * 360.0, Vector3(s, s * 0.7, s)))
	for k in 4:
		if not boulders[k].is_empty():
			_batch(rock_mesh(k), boulders[k], _stone(0.35), true)
	_motes(300, Color(1.0, 0.45, 0.12) * 2.5, 0.06, true, Vector3(0.1, 0.5, 0.0), 6.0, 9.0)


## Hell's gate: basalt teeth and bone round a field of cracked, burning stone, lava in the basins, pyres burning.
func _hell() -> void:
	_lava_sea(-0.5)
	var spires: Array = []
	for p in _spots(Rect2(-40, -30, 146, 100), 70, 1.0, 1.0):
		var h := _rng.randf_range(3.0, 9.0)
		spires.append(_xf(p + Vector3(0, -0.3, 0), _rng.randf() * 360.0, Vector3(h * 0.32, h, h * 0.32), Vector3(_rng.randf_range(-12, 12), 0, _rng.randf_range(-12, 12))))
	_batch(spire_mesh(), spires, _stone(0.3), true)
	for p in _spots(Rect2(-18, -10, 102, 56), 8, 1.6, 0.5):
		_bone_pile(p, _rng.randf_range(1.0, 1.6))
	_motes(900, Color(1.0, 0.4, 0.1) * 3.0, 0.07, true, Vector3(0.2, 0.7, 0.05), 10.0, 9.0)


## A sheet of lava over the land's basins, at `y`.
func _lava_sea(y: float) -> void:
	var q := PlaneMesh.new()
	q.size = Vector2(640, 520)
	var mi := _mesh(q, level.centre() + Vector3(0, y, 0), _pool_mat("lava"), 0.0, false)
	mi.set_instance_shader_parameter("box", Vector4(-1e4, -1e4, 1e4, 1e4))


## Kurast's harbour: the sea south of the quay with piers and moored boats, warehouses and cargo to the north.
func _docks() -> void:
	_sea(-0.75, "water")
	var stone := _stone(0.45)
	var wood := _tex("planks", Color(0.55, 0.47, 0.4), 0.5)
	var timber := _tex("timber", Color(0.4, 0.35, 0.3), 0.7)
	_box(Vector3(200, 3.6, 1.4), Vector3(33, -1.75, level.height * Level.TILE + 0.6), stone, 0.0, false)   # the quay's face
	var posts: Array = []
	var deck: Array = []
	for x in [6.0, 26.0, 46.0, 62.0]:
		var length := _rng.randf_range(12.0, 20.0)
		deck.append(_xf(Vector3(x, 0.05, 37.0 + length * 0.5), _rng.randf_range(-2, 2), Vector3(3.0, 0.2, length)))
		for k in int(length / 3.0):
			for s in [-1.4, 1.4]:
				posts.append(_xf(Vector3(x + s, -1.0, 38.0 + k * 3.0), 0.0, Vector3(0.3, 2.5, 0.3)))
		_boat(Vector3(x + 5.0, -0.7, 40.0 + length * 0.6), _rng.randf_range(-15, 15))
	_batch(unit_box(), deck, wood, true)
	var c := CylinderMesh.new()
	c.radial_segments = 6
	_batch(c, posts, timber, false)
	var houses := ["house_a", "house_b", "house_c", "house_d"]
	var i := 0
	for x in range(-14, 84, 11):
		var p := Vector3(x + _rng.randf_range(-1, 1), 0, -9.0 + _rng.randf_range(-1, 1))
		if not _free(p, 5.0, 2.0):
			continue
		p.y = level.pad(p.x, p.z, 6.0)
		var h := _place(houses[i % 4], p, 180.0 + _rng.randf_range(-6, 6))
		if i % 2 == 1:
			h.scale.x = -1.0
		i += 1
	for p in _spots(Rect2(-16, -6, 98, 5), 9, 1.2, 0.3):
		match _rng.randi() % 3:
			0: _crates(p)
			1: _barrels(p)
			2: _place("market_stall", p, 180.0)
	for p in _spots(Rect2(-4, 34.5, 74, 2.0), 6, 0.8, -1.0):
		_scaled("lamppost", p, _rng.randf() * 360.0, 1.1)
	_motes(260, Color(0.7, 0.8, 0.9, 0.35), 0.05, false, Vector3(0.4, -0.8, 0.1), 10.0, 8.0)


## A low open boat moored, with a stub of mast.
func _boat(at: Vector3, yaw: float) -> void:
	var root := Node3D.new()
	root.position = at
	root.rotation_degrees.y = yaw
	add_child(root)
	var hull := CylinderMesh.new()
	hull.top_radius = 1.0
	hull.bottom_radius = 0.6
	hull.height = 0.9
	hull.radial_segments = 12
	var mi := MeshInstance3D.new()
	mi.mesh = hull
	mi.material_override = _tex("planks", Color(0.4, 0.33, 0.27), 0.7)
	mi.scale = Vector3(1.0, 1.0, 3.2)
	mi.position = Vector3(0, 0.25, 0)
	root.add_child(mi)
	var mast := CylinderMesh.new()
	mast.top_radius = 0.06
	mast.bottom_radius = 0.09
	mast.height = 6.0
	var m2 := MeshInstance3D.new()
	m2.mesh = mast
	m2.material_override = _tex("timber", Color(0.4, 0.35, 0.3), 0.7)
	m2.position = Vector3(0, 3.2, -0.6)
	root.add_child(m2)


## A sheet of water (or bog) over everything below `y`.
func _sea(y: float, kind: String) -> void:
	var q := PlaneMesh.new()
	q.size = Vector2(640, 520)
	var mi := _mesh(q, level.centre() + Vector3(0, y, 0), _pool_mat(kind), 0.0, false)
	mi.set_instance_shader_parameter("box", Vector4(-1e4, -1e4, 1e4, 1e4))


## The spiders' forest: the druids' ring of great oaks round the clearing, webs strung between them, silk-wrapped
## larders, pale fungus glowing at their roots.
func _spider_forest() -> void:
	var oaks := _spots(Rect2(-22, -18, 110, 72), 16, 3.0, 2.0)
	for p in oaks:
		_oak(p, _rng.randf_range(1.0, 1.4))
	for k in oaks.size():
		var a: Vector3 = oaks[k]
		var b: Vector3 = oaks[(k + 1) % oaks.size()]
		if a.distance_to(b) < 14.0:
			_web((a + b) * 0.5 + Vector3(0, 3.0, 0), min(a.distance_to(b) * 0.6, 6.0), rad_to_deg(atan2(b.x - a.x, b.z - a.z)) + 90.0)
	for p in _spots(Rect2(-16, -10, 98, 56), 7, 1.5, 0.5):
		_cocoons(p)
	for p in _spots(Rect2(-18, -12, 102, 60), 10, 1.0, 0.5):
		_fungus(p)
	for p in _spots(Rect2(-24, -16, 114, 68), 8, 2.0, 1.0):
		_scaled("dead_tree", p, _rng.randf() * 360.0, _rng.randf_range(1.0, 1.5))
	_motes(140, Color(0.6, 1.0, 0.5) * 2.0, 0.06, true, Vector3(0.1, 0.1, 0.0), 4.0, 10.0)


## A great oak: a thick trunk, roots, a dark crown of leaf masses.
func _oak(at: Vector3, size: float) -> void:
	var bark := _tex("timber", Color(0.36, 0.33, 0.28), 0.6)
	var trunk := _cyl(0.9 * size, 0.6 * size, 7.0 * size, at + Vector3(0, -0.2, 0), bark, 10)
	trunk.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	for k in 5:
		var a := TAU * k / 5.0 + _rng.randf() * 0.5
		var root := _cyl(0.35 * size, 0.1 * size, 2.4 * size, Vector3.ZERO, bark, 6)
		root.position = at + Vector3(cos(a), 0, sin(a)) * 0.9 * size
		root.basis = Basis(Vector3(-sin(a), 0, cos(a)), deg_to_rad(65)) * root.basis
	var crown := MeshInstance3D.new()
	crown.mesh = Scatter.broadleaf_mesh()
	crown.material_override = Scatter.foliage_material()
	crown.position = at + Vector3(0, 1.5 * size, 0)
	crown.rotation_degrees.y = _rng.randf() * 360.0
	crown.scale = Vector3.ONE * size * 1.35
	add_child(crown)
	footprints.append([at, 2.5 * size])


func _fungus(at: Vector3) -> void:
	var cap := SphereMesh.new()
	cap.radius = 0.5
	cap.height = 0.4
	cap.is_hemisphere = true
	var stalk := _flat(Color(0.7, 0.72, 0.65), 0.7)
	var glow := Mats.glow(Color(0.3, 1.0, 0.8), 1.6, Color(0.15, 0.3, 0.25))
	var caps: Array = []
	for k in 5:
		var p := at + Vector3(_rng.randf_range(-0.6, 0.6), 0, _rng.randf_range(-0.6, 0.6))
		var h := _rng.randf_range(0.15, 0.5)
		_cyl(0.04, 0.03, h, p, stalk, 5, false)
		caps.append(_xf(p + Vector3(0, h, 0), 0.0, Vector3.ONE * _rng.randf_range(0.25, 0.6)))
	_batch(cap, caps, glow, false)
	var light := OmniLight3D.new()
	light.light_color = Color(0.35, 1.0, 0.8)
	light.light_energy = 1.2
	light.omni_range = 4.0
	light.position = at + Vector3(0, 0.6, 0)
	add_child(light)


## The Flayer jungle: trees crowding the clearing, ruined stones of the old faith, totems with skulls, fireflies.
func _jungle() -> void:
	for p in _spots(Rect2(-22, -18, 110, 72), 34, 2.0, 1.0):
		_jungle_tree(p, _rng.randf_range(0.9, 1.5))
	for p in _spots(Rect2(-16, -10, 98, 56), 6, 1.0, 0.5):
		_totem(p)
	for p in _spots(Rect2(-18, -12, 102, 60), 6, 1.5, 0.5):
		_ruin_stones(p)
	_motes(220, Color(0.75, 1.0, 0.35) * 2.2, 0.06, true, Vector3(0.1, 0.1, 0.0), 5.0, 10.0)


func _ruin_stones(at: Vector3) -> void:
	var moss := _tex("stone", Color(0.55, 0.62, 0.48), 0.5)
	for k in 3:
		var size := Vector3(_rng.randf_range(0.8, 1.6), _rng.randf_range(0.5, 1.4), _rng.randf_range(0.8, 1.4))
		var b := _box(size, at + Vector3(_rng.randf_range(-0.8, 0.8), size.y * 0.5 - 0.1, _rng.randf_range(-0.8, 0.8)), moss, _rng.randf() * 360.0)
		b.rotation_degrees.z = _rng.randf_range(-8, 8)


## The drowned city: black water over the sunken streets, houses up to their windows in it, broken columns and
## dead trees standing in the swamp, a lamp still burning here and there.
func _drowned() -> void:
	_sea(-0.4, "water")
	var houses := ["house_ruin", "house_b", "house_d", "house_ruin", "house_a", "house_c"]
	var i := 0
	for p in _spots(Rect2(-30, -24, 126, 84), 16, 5.0, 3.0):
		var sunk := Vector3(p.x, _rng.randf_range(-2.4, -0.8), p.z)
		var h := _place(houses[i % houses.size()], sunk, _rng.randf() * 360.0)
		h.rotation_degrees.z = _rng.randf_range(-6, 6)
		h.rotation_degrees.x = _rng.randf_range(-4, 4)
		for node in h.find_children("*", "MeshInstance3D", true, false):   # nobody lives here: dark windows
			var mi := node as MeshInstance3D
			for k in mi.mesh.get_surface_count():
				var m := mi.get_surface_override_material(k)
				if m and m == Mats.named("glow_window"):
					mi.set_surface_override_material(k, _flat(Color(0.02, 0.025, 0.025)))
		i += 1
	for p in _spots(Rect2(-24, -16, 114, 68), 10, 1.0, 1.0):
		_broken_column(p + Vector3(0, -0.6, 0), _rng.randf() * 360.0)
	for p in _spots(Rect2(-26, -18, 118, 72), 9, 2.0, 1.5):
		_scaled("dead_tree", p + Vector3(0, -0.5, 0), _rng.randf() * 360.0, _rng.randf_range(0.9, 1.4))
	for p in _spots(Rect2(-6, -6, 78, 48), 5, 0.8, 1.0):
		_place("lamppost", p, _rng.randf() * 360.0)
	_motes(300, Color(0.65, 0.8, 0.8, 0.3), 0.05, false, Vector3(0.1, -0.2, 0.0), 6.0, 14.0)


## Travincal: the council's stepped temple north of the terrace under the mother lamp, gilded statues and great
## braziers along the terrace's edge, the jungle beyond.
func _travincal() -> void:
	var sand := _tex("flagstones", Color(0.95, 0.82, 0.62), 0.4)
	var dark := _tex("basalt", Color(0.6, 0.55, 0.5), 0.4)
	var c := Vector3(33.0, 0.0, -24.0)
	for k in 5:
		var w := 44.0 - k * 7.0
		var d := 18.0 - k * 2.6
		var h := 2.2
		_box(Vector3(w, h, d), c + Vector3(0, h * (k + 0.5), 0), sand if k % 2 == 0 else dark)
	for k in 10:   # the stair up its south face
		_box(Vector3(7.0, 1.1 * (k + 1), 1.2), c + Vector3(0, 0.55 * (k + 1), 14.0 - k * 1.2), sand)
	var lamp := SphereMesh.new()
	lamp.radius = 1.6
	lamp.height = 3.2
	_mesh(lamp, c + Vector3(0, 14.6, 0), Mats.glow(Color(1.0, 0.75, 0.35), 3.0, Color(0.6, 0.45, 0.2)), 0.0, false)
	_cyl(0.25, 0.25, 3.0, c + Vector3(0, 11.0, 0), Mats.named("gold"), 8)
	var mother := Fx.fire_light(6.0, 34.0, false, Color(1.0, 0.72, 0.38))
	mother.position = c + Vector3(0, 15.0, 6.0)
	mother.light_volumetric_fog_energy = 0.5
	add_child(mother)
	footprints.append([c, 24.0])
	for k in 5:
		var side := -1.0 if k % 2 == 0 else 1.0
		_great_brazier(c + Vector3(side * (20.0 - k * 3.5), 2.2 * (k + 1), 8.0 - k * 1.3))
	for p in _spots(Rect2(-10, -8, 86, 6), 6, 1.2, 0.5):
		_statue(p, 180.0)
	for p in _spots(Rect2(-12, 37, 90, 6), 5, 1.2, 0.5):
		_great_brazier(p)
	for p in _spots(Rect2(-26, -20, 118, 76), 18, 2.0, 2.0):
		_jungle_tree(p, _rng.randf_range(1.0, 1.5))
	_motes(160, Color(0.75, 1.0, 0.35) * 2.0, 0.06, true, Vector3(0.1, 0.1, 0.0), 5.0, 10.0)


## The Temple of Light: colonnades of gilded columns, the mother lamp hanging dim over the floor, gold braziers,
## banners, and dark beyond the columns.
func _temple() -> void:
	var stone := _stone(0.45)
	var gold := Mats.named("gold")
	for run in _ring_runs():
		var a: Vector3 = run[0]
		var b: Vector3 = run[1]
		var edge: String = run[3]
		var k := int(a.distance_to(b) / 6.0)
		for i in k:
			var c := a.lerp(b, (i + 0.5) / max(k, 1))
			var h := 12.0 if edge != "s" else _rng.randf_range(1.0, 2.6)
			_cyl(0.9, 0.9, 0.6, c, stone, 10)
			_cyl(0.6, 0.55, h, c + Vector3(0, 0.6, 0), stone, 14)
			if edge != "s":
				_cyl(0.6, 0.95, 0.9, c + Vector3(0, h + 0.6, 0), gold, 12)
	_box(Vector3(120, 18, 2.0), Vector3(33, 9.0, -10.0), stone)   # the north wall
	for x in range(-12, 80, 12):
		_banner(Vector3(x, 6.0, -8.9))
		_box(Vector3(2.4, 4.0, 0.3), Vector3(x + 6.0, 3.5, -8.95), _flat(Color(0.02, 0.018, 0.015)), 0.0, false)
		_cyl(0.3, 0.3, 0.1, Vector3(x + 6.0, 1.5, -8.6), gold, 8, false)
	var lamp := SphereMesh.new()
	lamp.radius = 1.8
	lamp.height = 3.6
	var at := Vector3(33.0, 15.0, 4.0)
	_mesh(lamp, at, Mats.glow(Color(1.0, 0.72, 0.3), 1.6, Color(0.5, 0.38, 0.18)), 0.0, false)
	for s in [-1.0, 1.0]:
		var chain := _cyl(0.05, 0.05, 30.0, at + Vector3(s * 1.2, 0.0, 0), gold, 6, false)
		chain.rotation_degrees.z = s * 4.0
	var light := Fx.fire_light(4.0, 30.0, false, Color(1.0, 0.72, 0.4))
	light.position = at + Vector3(0, -2.0, 0)
	light.light_volumetric_fog_energy = 0.3
	add_child(light)
	for p in _spots(Rect2(-12, -8, 90, 6), 6, 1.2, 0.5):
		_great_brazier(p)
	for p in _spots(Rect2(-12, 37, 90, 5), 4, 1.2, 0.5):
		_great_brazier(p)
	_motes(500, Color(1.0, 0.85, 0.6, 0.35), 0.05, false, Vector3(0.03, -0.04, 0.0), 12.0, 16.0)


## A pool's hole, drawn on a quad over it: the ray from the eye is followed down into a box under the quad, and
## what it meets is shaded (a wall darkening with depth, or the bottom: black, earth, water, bog or lava).
const POOL_SHADER := """
shader_type spatial;

uniform int kind = 0;      // 0 a dark pit, 1 water, 2 lava, 3 bog
uniform float depth = 2.0; // to the bottom, or to the surface of what fills it
uniform sampler2D wall : source_color, filter_linear_mipmap, repeat_enable;
uniform vec3 wall_tint;
uniform sampler2D noise : filter_linear, repeat_enable;
uniform sampler2D ripples : hint_normal, filter_linear, repeat_enable;
instance uniform vec4 box; // x0, z0, x1, z1 in metres

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec3 eye = INV_VIEW_MATRIX[3].xyz;
	vec3 dir = normalize(wpos - eye);
	float tb = depth / max(-dir.y, 1e-4);
	float tx = 1e6;
	if (abs(dir.x) > 1e-5) { tx = ((dir.x > 0.0 ? box.z : box.x) - wpos.x) / dir.x; }
	float tz = 1e6;
	if (abs(dir.z) > 1e-5) { tz = ((dir.z > 0.0 ? box.w : box.y) - wpos.z) / dir.z; }
	float t = min(tb, min(tx, tz));
	vec3 q = wpos + dir * t;
	float down = clamp((wpos.y - q.y) / max(depth, 0.01), 0.0, 1.0);
	vec3 n = vec3(0.0, 1.0, 0.0);
	vec3 col;
	vec3 glow = vec3(0.0);
	float rough = 0.9;
	float spec = 0.3;
	vec3 nmap = vec3(0.5, 0.5, 1.0);
	if (t < tb) {
		n = tx < tz ? vec3(-sign(dir.x), 0.0, 0.0) : vec3(0.0, 0.0, -sign(dir.z));
		vec2 uv = (tx < tz ? q.zy : q.xy) * 0.5;
		col = texture(wall, uv).rgb * wall_tint * mix(1.0, kind == 0 ? 0.04 : 0.35, down);
		if (kind == 2) {
			glow = vec3(1.0, 0.25, 0.03) * pow(down, 3.0) * 1.2;
		}
	} else {
		vec2 p = q.xz;
		if (kind == 0) {
			col = texture(wall, p * 0.5).rgb * wall_tint * 0.08;
		} else if (kind == 2) {
			// dark plates of crust drifting on the melt, bright veins between them, molten pools here and there
			vec2 flow = vec2(TIME * 0.02, TIME * 0.011);
			float a = texture(noise, p * 0.16 + flow).r;
			float b = texture(noise, p * 0.37 - flow * 1.6).r;
			float vein = 1.0 - smoothstep(0.0, 0.03, abs(a - 0.5) + (b - 0.5) * 0.05);
			float molten = 0.0;
			// the melt shows along the walls' feet, where the crust breaks on the stone
			vec2 edge = min(q.xz - box.xy, box.zw - q.xz);
			molten = max(molten, 1.0 - smoothstep(0.0, 0.45, min(edge.x, edge.y)));
			float hot = max(vein, molten);
			col = mix(vec3(0.03, 0.015, 0.012), vec3(0.08, 0.02, 0.005), hot);
			glow = mix(vec3(0.5, 0.04, 0.004) * (0.25 + 0.3 * b), vec3(1.0, 0.24, 0.025) * (0.9 + 0.8 * b), hot);
			rough = mix(0.95, 0.5, hot);
		} else {
			vec2 f1 = p * 0.18 + vec2(TIME * 0.02, TIME * 0.011);
			vec2 f2 = p * 0.11 - vec2(TIME * 0.013, -TIME * 0.017);
			nmap = normalize(mix(texture(ripples, f1).rgb, texture(ripples, f2).rgb, 0.5));
			if (kind == 1) {
				col = vec3(0.006, 0.013, 0.016);
				rough = 0.1;
				spec = 0.55;
				// still black water under a black sky: a faint fresnel sheen so it reads as water, not a hole
				float fres = pow(1.0 - clamp(-dir.y, 0.0, 1.0), 2.0);
				glow += vec3(0.035, 0.055, 0.07) * fres * (0.7 + 0.6 * nmap.r);
			} else {
				float scum = smoothstep(0.5, 0.7, texture(noise, p * 0.2 + vec2(TIME * 0.008, TIME * 0.005)).r);
				col = mix(vec3(0.01, 0.014, 0.008), vec3(0.06, 0.08, 0.03), scum);
				rough = mix(0.12, 0.8, scum);
				spec = 0.45;
			}
		}
	}
	ALBEDO = col;
	EMISSION = glow;
	ROUGHNESS = rough;
	SPECULAR = spec;
	NORMAL = normalize((VIEW_MATRIX * vec4(n, 0.0)).xyz);
	NORMAL_MAP = nmap;
}
"""
