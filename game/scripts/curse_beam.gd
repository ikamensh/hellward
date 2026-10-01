class_name CurseBeam
extends Node3D
## A leader's chant made visible: a violet beam from its staff to the tower it curses, knots of power running
## along it to the tower (shaders/curse_beam.gdshader).

const RADIUS := 0.22

var from: Node3D
var to: Node3D
var _mesh: MeshInstance3D
var _mat: ShaderMaterial
var _light: OmniLight3D
var _t := 0.0


func _ready() -> void:
	_mesh = MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = RADIUS
	cm.bottom_radius = RADIUS
	cm.height = 1.0
	cm.radial_segments = 16
	cm.rings = 8
	cm.cap_top = false
	cm.cap_bottom = false
	_mesh.mesh = cm
	_mat = ShaderMaterial.new()
	_mat.shader = preload("res://shaders/curse_beam.gdshader")
	_mesh.material_override = _mat
	_mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_mesh)
	_light = OmniLight3D.new()
	_light.light_color = Color(0.65, 0.2, 1.0)
	_light.light_energy = 3.0
	_light.omni_range = 6.0
	add_child(_light)


func _process(delta: float) -> void:
	if not is_instance_valid(from) or not is_instance_valid(to):
		queue_free()
		return
	_t += delta
	var a := from.global_position
	var b := to.global_position + Vector3(0, 2.2, 0)
	var length := a.distance_to(b)
	global_position = (a + b) * 0.5
	if length > 0.01:
		var up := (b - a) / length
		var x := up.cross(Vector3.FORWARD if abs(up.dot(Vector3.FORWARD)) < 0.9 else Vector3.RIGHT).normalized()
		var r := 1.0 + 0.12 * sin(_t * 14.0)
		_mesh.global_basis = Basis(x * r, up * length, x.cross(up) * r)
		_mat.set_shader_parameter("span", length)
	_light.global_position = b
	_light.light_energy = 3.0 + 0.8 * sin(_t * 14.0)
