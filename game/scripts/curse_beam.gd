class_name CurseBeam
extends Node3D
## A leader's chant made visible: a pulsing violet beam from its staff to the tower it curses.

var from: Node3D
var to: Node3D
var _mesh: MeshInstance3D
var _light: OmniLight3D
var _t := 0.0


func _ready() -> void:
	_mesh = MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.06
	cm.bottom_radius = 0.06
	cm.height = 1.0
	cm.radial_segments = 8
	_mesh.mesh = cm
	_mesh.material_override = Mats.glow(Color(0.7, 0.25, 1.0), 10.0, Color(0.9, 0.6, 1.0))
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
	var mid := (a + b) * 0.5
	var length := a.distance_to(b)
	global_position = mid
	if length > 0.01:
		var up := (b - a) / length
		var x := up.cross(Vector3.FORWARD if abs(up.dot(Vector3.FORWARD)) < 0.9 else Vector3.RIGHT).normalized()
		var r := 1.0 + 0.4 * sin(_t * 18.0)
		_mesh.global_basis = Basis(x * r, up * length, x.cross(up) * r)
	_light.global_position = b
