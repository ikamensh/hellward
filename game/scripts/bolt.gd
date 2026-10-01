class_name Bolt
extends Node3D
## A missile homing on a monster: a ballista bolt, a firebolt or a frost shard. When it arrives it calls
## `on_hit` with the monster, or with null if the monster died on the way.

var target: Monster
var speed := 20.0
var on_hit: Callable
var _aim := Vector3.ZERO


static func launch(world: World, look: String, from: Vector3, at: Monster, metres_per_s: float, hit: Callable) -> Bolt:
	var b := Bolt.new()
	b.target = at
	b.speed = metres_per_s
	b.on_hit = hit
	b._aim = at.chest()
	world.add_child(b)
	b.global_position = from
	match look:
		"arrow": b._arrow()
		"fire": b._firebolt()
		"frost": b._shard()
	b.look_at(b._aim, Vector3.UP)
	return b


func _process(delta: float) -> void:
	var alive := is_instance_valid(target) and target.alive()
	if alive:
		_aim = target.chest()
	var to := _aim - global_position
	var step := speed * delta
	if to.length() <= step:
		global_position = _aim
		on_hit.call(target if alive else null)
		_vanish()
		return
	global_position += to.normalized() * step
	if to.length() > 0.05:
		look_at(_aim, Vector3.UP)


## Trails linger after the head is gone: stop emitting, let them fade, then free.
func _vanish() -> void:
	set_process(false)
	for c in get_children():
		if c is GPUParticles3D:
			(c as GPUParticles3D).emitting = false
		elif c is VisualInstance3D or c is Light3D:
			c.visible = false
	get_tree().create_timer(1.2).timeout.connect(queue_free)


func _arrow() -> void:
	var shaft := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.035
	cm.bottom_radius = 0.035
	cm.height = 1.1
	shaft.mesh = cm
	shaft.rotation_degrees.x = 90
	shaft.material_override = Mats.named("planks")
	add_child(shaft)
	var tip := MeshInstance3D.new()
	var tm := CylinderMesh.new()
	tm.top_radius = 0.0
	tm.bottom_radius = 0.08
	tm.height = 0.22
	tip.mesh = tm
	tip.rotation_degrees.x = -90
	tip.position = Vector3(0, 0, -0.62)
	tip.material_override = Mats.named("iron")
	add_child(tip)
	add_child(Vfx.trail(Color(0.9, 0.85, 0.75) * 0.6, 0.06, 0.25))


func _firebolt() -> void:
	var core := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 0.22
	sm.height = 0.44
	core.mesh = sm
	core.material_override = Mats.glow(Color(1.0, 0.55, 0.15), 9.0)
	add_child(core)
	var flame := Fx.fire(0.55, 1.2)
	add_child(flame)
	var light := OmniLight3D.new()
	light.light_color = Color(1.0, 0.5, 0.15)
	light.light_energy = 3.0
	light.omni_range = 6.0
	add_child(light)


func _shard() -> void:
	var core := MeshInstance3D.new()
	var pm := PrismMesh.new()
	pm.size = Vector3(0.18, 0.7, 0.18)
	core.mesh = pm
	core.rotation_degrees.x = -90
	core.material_override = Mats.glow(Color(0.5, 0.85, 1.0), 6.0, Color(0.6, 0.85, 1.0))
	add_child(core)
	add_child(Vfx.trail(Color(0.4, 0.75, 1.0) * 2.0, 0.12, 0.5))
	var light := OmniLight3D.new()
	light.light_color = Color(0.45, 0.75, 1.0)
	light.light_energy = 1.5
	light.omni_range = 4.0
	add_child(light)
