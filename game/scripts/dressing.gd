class_name Dressing
extends Node3D
## Everything around the battle: the burning village, the portal, the cathedral, props, fires and lights.
## Positions are in metres on the 66 x 36 m field (x east, z south); houses ring it outside the walls.

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
	for f in FARMS:
		var pos := Vector3(f.x, 0.0, f.y)
		pos.y = level.pad(f.x, f.y, 5.0)
		var node := _place("house_ruin", pos, randf() * 360.0)
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
	_portal()
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
	light.position = pos + Vector3(0, 1.5, 0)
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
func _street_braziers() -> void:
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
				if at.x < 3.0 or at.x > 63.0 or level.cell(t) != "P" or level.road_distance(at) < 2.7:
					continue
				if placed.any(func(q): return (q as Vector3).distance_to(at) < 6.0):
					continue
				placed.append(at)
				var brazier := _place("brazier", at, randf() * 360.0)
				var coals := Models.node(brazier, "fx_fire_1")
				coals.add_child(Fx.fire(0.8))
				var light := Fx.fire_light(9.0, 11.0)
				light.position = Vector3(0, 0.8, 0)
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


## The hell gate the monsters pour from, facing the field: a turning vortex, red light, embers and smoke.
func _portal() -> void:
	var node := _place("portal", level.portal_pos, -90.0)
	footprints.append([level.portal_pos, 5.0])
	var vortex := Models.node(node, "vortex") as MeshInstance3D
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/vortex.gdshader")
	m.set_shader_parameter("swirl", load("res://assets/fx/portal_swirl.png"))
	vortex.material_override = m
	var heart := Models.node(node, "fx_portal")
	var light := Fx.fire_light(9.0, 18.0, true, Color(1.0, 0.18, 0.06))
	heart.add_child(light)
	var embers := Fx.embers(Vector3(4, 4, 4), 90)
	heart.add_child(embers)
	var smoke := Fx.smoke(2.5, 12.0)
	smoke.position = Vector3(0, 2.0, 0)
	heart.add_child(smoke)


## The cathedral the monsters march on, its doors open and lit: the lamp still burns inside.
func _cathedral() -> void:
	var node := Models.make("cathedral")
	node.rotation_degrees.y = 90.0
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
		var pos := level.door_pos + Vector3(at.x, 0.0, at.y)
		var brazier := _place("brazier", pos, 90.0)
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
	var light := Fx.fire_light(11.0, 15.0, _burning % 3 == 1)   # shadows from every third fire: each costs six passes
	light.position = pos + Vector3(0, 3.5, 3.0 if pos.z < 18.0 else -3.0)
	add_child(light)
