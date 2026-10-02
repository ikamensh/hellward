class_name Chain
extends Node3D
## A Hook Tower's throw: an iron chain flies from the muzzle to a monster (`Monster.HOOK_FLIGHT`), holds while the
## monster is dragged back (`Monster.DRAG`), then rattles back in. Its links are one MultiMesh, laid along the line
## each frame, every other one turned a quarter so it reads as a chain.

const PITCH := 0.13                  # metres from one link to the next
const RETRACT := 0.16                # seconds the chain takes to come back in

var _from: Node3D
var _to: Monster
var _end := Vector3.ZERO             # where the hook last held: the chain comes back from there if the monster is gone
var _t := 0.0
var _links: MultiMesh
var _hook: MeshInstance3D


static func throw(world: Node, from: Node3D, to: Monster) -> Chain:
	var c := Chain.new()
	c._from = from
	c._to = to
	c._end = to.chest()
	world.add_child(c)
	return c


func _ready() -> void:
	var torus := TorusMesh.new()
	torus.inner_radius = 0.028
	torus.outer_radius = 0.062
	torus.rings = 8
	torus.ring_segments = 6
	_links = MultiMesh.new()
	_links.transform_format = MultiMesh.TRANSFORM_3D
	_links.mesh = torus
	_links.instance_count = 160
	_links.visible_instance_count = 0
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = _links
	mmi.material_override = Mats.named("iron")
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mmi)
	_hook = MeshInstance3D.new()
	var barb := PrismMesh.new()
	barb.size = Vector3(0.34, 0.42, 0.08)
	_hook.mesh = barb
	_hook.material_override = Mats.named("iron")
	add_child(_hook)
	top_level = true
	global_transform = Transform3D.IDENTITY


func _process(delta: float) -> void:
	_t += delta
	if is_instance_valid(_to) and not _to.gone:
		_end = _to.chest()
	if not is_instance_valid(_from):
		queue_free()
		return
	var start := _from.global_position
	var reach: float
	var held := Monster.HOOK_FLIGHT + Monster.DRAG
	if _t < Monster.HOOK_FLIGHT:
		reach = _t / Monster.HOOK_FLIGHT
	elif _t < held:
		reach = 1.0
	else:
		reach = 1.0 - (_t - held) / RETRACT
	if reach <= 0.0:
		queue_free()
		return
	var end := start.lerp(_end, reach)
	_lay(start, end)


## Links from `a` to `b`, a slight sag in the middle while it is slack (flying out and coming back).
func _lay(a: Vector3, b: Vector3) -> void:
	var length := a.distance_to(b)
	var n: int = mini(int(length / PITCH), _links.instance_count)
	var taut := _t >= Monster.HOOK_FLIGHT and _t < Monster.HOOK_FLIGHT + Monster.DRAG
	var sag := 0.0 if taut else length * 0.06
	var dir := (b - a).normalized() if length > 0.001 else Vector3.FORWARD
	var up := Vector3.UP if absf(dir.dot(Vector3.UP)) < 0.95 else Vector3.RIGHT
	for i in n:
		var f := (i + 0.5) / maxf(n, 1)
		var p := a.lerp(b, f) - Vector3(0, sag * 4.0 * f * (1.0 - f), 0)
		var basis := Basis.looking_at(dir, up)
		basis = basis * Basis(Vector3.FORWARD, PI * 0.5 * (i % 2))   # every other link a quarter turned about the chain
		basis = basis.scaled_local(Vector3(1.0, 1.0, 1.7))           # a ring lying along the chain, drawn out long
		_links.set_instance_transform(i, Transform3D(basis, p))
	_links.visible_instance_count = n
	_hook.global_transform = Transform3D(Basis.looking_at(dir, up) * Basis(Vector3.RIGHT, -PI * 0.5), b)
