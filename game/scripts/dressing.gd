class_name Dressing
extends Node3D
## Everything around the battle: the burning village, the portal, the cathedral, props, fires and lights.
## Positions are in metres on the 66 x 36 m field (x east, z south); houses ring it outside the walls.

const MODELS := "res://assets/models/"

# model, x, z, facing (degrees, 0 = the model's front toward -z / north), burning
const HOUSES := [
	["house_a", 6.0, -7.5, 180.0, true], ["house_c", 16.0, -8.0, 175.0, false], ["house_b", 27.0, -8.5, 185.0, true],
	["house_ruin", 38.0, -7.0, 180.0, true], ["house_d", 48.0, -8.0, 178.0, false], ["house_a", 59.0, -7.5, 182.0, true],
	["house_c", -6.0, -4.0, 120.0, true], ["house_ruin", -10.0, 34.0, 60.0, true],
	["house_b", 8.0, 43.5, 0.0, false], ["house_ruin", 20.0, 42.5, 4.0, true], ["house_d", 31.0, 44.0, -3.0, true],
	["house_a", 43.0, 43.0, 2.0, false], ["house_c", 54.0, 43.5, -4.0, true],
	["house_b", 70.0, -2.0, 200.0, false], ["house_d", 71.0, 40.0, -20.0, true],
	["house_a", -4.0, 46.0, 30.0, false], ["house_c", 84.0, 2.0, 230.0, true],
]
# the obstacles in the grid, and props on the field's edges
const PROPS := [
	["well", 7.0, 5.0, 0.0], ["cart", 33.0, 5.0, 30.0], ["haystack", 57.0, 7.0, 0.0],
	["wayside_shrine", 9.0, 31.0, 0.0], ["dead_tree", 55.0, 29.0, 0.0], ["gravestone_a", 33.0, 31.0, 10.0],
	["gravestone_b", 31.5, 31.6, -15.0], ["barrel", 2.5, 3.0, 0.0], ["barrel", 3.3, 2.2, 0.0], ["crate", 4.2, 3.4, 20.0],
	["market_stall", 21.0, 2.6, 180.0], ["barrel", 63.0, 3.0, 0.0], ["crate", 62.0, 4.0, 10.0],
	["lamppost", 13.0, 1.3, 0.0], ["lamppost", 47.0, 1.3, 0.0], ["lamppost", 22.0, 34.7, 0.0], ["lamppost", 44.0, 34.7, 0.0],
	["rubble", 40.0, 33.0, 0.0], ["dead_tree", 3.0, 33.5, 90.0], ["fence", 13.0, -1.2, 0.0], ["fence", 51.0, -1.2, 0.0],
	["fence", 28.0, 37.2, 0.0], ["fence", 60.0, 37.2, 0.0], ["haystack", 64.0, 33.0, 0.0], ["crate", 47.0, 32.5, 45.0],
	["dead_tree", -14.0, 8.0, 0.0], ["dead_tree", -12.0, 27.0, 40.0], ["rubble", -3.0, 12.0, 0.0], ["rubble", -2.0, 23.0, 90.0],
]

var level: Level
var footprints: Array = []   # [centre, radius] the clutter keeps clear of
var _burning := 0


func build(lvl: Level, scorch: Array) -> void:
	level = lvl
	for h in HOUSES:
		var pos := Vector3(h[1], 0.0, h[2])
		var node := _place(h[0], pos, h[3])
		if h[4]:
			_burn(node, pos)
			scorch.append([pos, 7.0])
	for p in PROPS:
		_place(p[0], Vector3(p[1], 0.0, p[2]), p[3])
	_portal()
	_cathedral()
	scorch.append([level.portal_pos, 9.0])


func _place(model: String, pos: Vector3, facing: float) -> Node3D:
	var node := Models.make(model)
	footprints.append([pos, 6.0 if model.begins_with("house") else 1.6])
	node.position = pos
	node.rotation_degrees.y = facing
	add_child(node)
	for fx in node.find_children("fx_light*", "", true, false):
		(fx as Node3D).add_child(Fx.fire_light(1.2, 6.0))
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
	node.position = level.door_pos - (door.global_position - node.global_position)
	footprints.append([node.position, 16.0])
	var glow := SpotLight3D.new()
	glow.light_color = Color(1.0, 0.75, 0.45)
	glow.light_energy = 12.0
	glow.spot_range = 22.0
	glow.spot_angle = 38.0
	glow.shadow_enabled = true
	glow.light_volumetric_fog_energy = 2.0
	door.add_child(glow)
	glow.position = Vector3(0, 3.5, 2.5)
	glow.rotation_degrees = Vector3(-18, 0, 0)
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
		m.add_child(Fx.fire(1.6 if i % 2 == 0 else 1.1))
		if i == 0:
			var smoke := Fx.smoke(3.0, 18.0)
			smoke.position = Vector3(0, 1.5, 0)
			m.add_child(smoke)
	var embers := Fx.embers(Vector3(8, 4, 8), 60)
	embers.position = pos + Vector3(0, 3, 0)
	add_child(embers)
	_burning += 1
	var light := Fx.fire_light(18.0, 15.0, _burning % 3 == 1)   # shadows from every third fire: each costs six passes
	light.position = pos + Vector3(0, 3.5, 3.0 if pos.z < 18.0 else -3.0)
	add_child(light)
