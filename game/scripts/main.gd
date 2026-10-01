extends Node3D

func _ready() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.02, 0.02, 0.04)
	e.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.environment = e
	add_child(env)
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = load("res://assets/textures/cobbles_albedo.png")
	mat.normal_enabled = true
	mat.normal_texture = load("res://assets/textures/cobbles_normal.png")
	mat.uv1_scale = Vector3(4, 4, 1)
	var plane := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(20, 20)
	plane.mesh = pm
	plane.material_override = mat
	add_child(plane)
	var light := OmniLight3D.new()
	light.position = Vector3(0, 3, 0)
	light.light_color = Color(1.0, 0.6, 0.3)
	light.light_energy = 4.0
	light.omni_range = 15
	add_child(light)
	var cam := Camera3D.new()
	cam.position = Vector3(0, 8, 10)
	add_child(cam)
	cam.look_at(Vector3.ZERO)
