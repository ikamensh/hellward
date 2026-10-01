class_name Tower
extends Node3D
## A tower as the server plays it: built, raised a rank, cursed, cleansed and sold by events; its shots are the
## server's too (a bolt with its flight time, a chain of lightning, a nova), shown from its muzzle. It turns to
## face what it last shot at.

const NAMES := {"arrow": "Arrow Tower", "pyre": "Pyre", "frost": "Frost Shrine", "storm": "Storm Obelisk",
	"plague": "Plague Totem", "altar": "Bone Altar", "grove": "Druid Grove"}
# a family without a model of its own wears another's, tinted, until it has one
const STAND_INS := {"plague": ["frost", Color(0.45, 0.85, 0.3)], "altar": ["storm", Color(0.9, 0.85, 0.7)],
	"grove": ["pyre", Color(0.4, 0.8, 0.35)]}
const LOOKS := {"arrow": "arrow", "pyre": "fire", "frost": "frost", "plague": "frost", "altar": "fire", "grove": "fire"}

var world: World
var id := 0
var kind: String
var tile: Vector2i
var rank := 0
var spent := 0
var curses := {}                     # curse -> seconds left, from the server
var reach := 0.0                     # tiles
var ward := 0.0
var upgrade_cost = null              # int, or null at the top rank
var needs = null                     # the skill the next rank needs, or null
var refund := 0
var removed := false

var _threat := 0.0
var _model: Node3D
var _turret: Node3D
var _muzzle: Node3D
var _crystal: Node3D
var _overlay: ShaderMaterial
var _curse_fx: Node3D
var _t := 0.0
var _aim: Node3D


func setup(w: World, ident: int, facts: Dictionary) -> void:
	world = w
	id = ident
	kind = String(facts["kind"])
	tile = Vector2i(int(facts["tile"][0]), int(facts["tile"][1]))
	rank = int(facts["level"])
	spent = int(facts["spent"])
	reach = float(world.tower_table(kind)["levels"][rank]["range"])


func _ready() -> void:
	position = world.level.tile_pos(tile)
	_dress()
	# it rises out of the ground in a cloud of dust
	_model.position.y = -6.0
	create_tween().set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT) \
		.tween_property(_model, "position:y", 0.0, 0.7)
	Vfx.dust(world, global_position, 1.6)


## The model a tower of `kind` and `rank` (0..2) wears: Arrow Towers have one per rank, the others grow.
static func model_name(kind: String, rank: int) -> String:
	var base: String = STAND_INS[kind][0] if STAND_INS.has(kind) else kind
	return "tower_arrow_%d" % (rank + 1) if base == "arrow" else "tower_" + base


func title() -> String:
	return NAMES.get(kind, kind.capitalize())


func level() -> Dictionary:
	return world.tower_table(kind)["levels"][rank]


func cursed() -> bool:
	return not curses.is_empty()


## The longest curse on it, in seconds.
func curse_left() -> float:
	var most := 0.0
	for c in curses:
		most = max(most, float(curses[c]))
	return most


func threat() -> float:
	return _threat


func _dress() -> void:
	if _model:
		_model.queue_free()
	_model = Models.make(model_name(kind, rank))
	add_child(_model)
	if model_name(kind, rank).begins_with("tower_arrow") == false:
		_model.scale = Vector3.ONE * (1.0 + 0.14 * rank)
	_turret = Models.node(_model, "turret")
	_muzzle = Models.node(_model, "fx_muzzle")
	_crystal = Models.node(_model, "crystal")
	_overlay = ShaderMaterial.new()
	_overlay.shader = preload("res://shaders/overlay.gdshader")
	if STAND_INS.has(kind):
		_overlay.set_shader_parameter("tint", STAND_INS[kind][1])
	for mi in _model.find_children("*", "MeshInstance3D", true, false):
		(mi as MeshInstance3D).material_overlay = _overlay
		(mi as MeshInstance3D).layers = 2   # decals (cull_mask 1) never land on a tower
	if kind == "arrow":   # the others carry their own fire or glow
		var lantern := OmniLight3D.new()
		lantern.light_color = Color(1.0, 0.75, 0.45)
		lantern.light_energy = 1.2 + 0.4 * rank
		lantern.omni_range = 5.0
		lantern.position = Vector3(0, 4.2, 0)
		_model.add_child(lantern)
	dress_fx(_model, kind, rank)
	_overlay.set_shader_parameter("curse", 1.0 if cursed() else 0.0)


## A tower model's own fire and glow: the Pyre's flame, the shrine's and the obelisk's light. The HUD's
## portraits of the towers wear them too.
static func dress_fx(model: Node3D, kind: String, rank: int) -> void:
	var base: String = STAND_INS[kind][0] if STAND_INS.has(kind) else kind
	var tint: Color = STAND_INS[kind][1] if STAND_INS.has(kind) else Color.WHITE
	var light: OmniLight3D = null
	match base:
		"pyre":
			var f := Models.node(model, "fx_fire")
			f.add_child(Fx.fire(0.9 + 0.15 * rank, 1.1))
			light = Fx.fire_light(3.0 + rank, 9.0)
			light.light_color = light.light_color * tint
			f.add_child(light)
		"frost":
			light = OmniLight3D.new()
			light.light_color = Color(0.4, 0.7, 1.0) * tint
			light.light_energy = 2.0 + 0.5 * rank
			light.omni_range = 7.0
			Models.node(model, "fx_glow").add_child(light)
		"storm":
			light = OmniLight3D.new()
			light.light_color = Color(0.45, 0.6, 1.0) * tint
			light.light_energy = 2.0 + 0.5 * rank
			light.omni_range = 8.0
			var crystal := Models.node(model, "crystal")
			(crystal if crystal else Models.node(model, "fx_muzzle")).add_child(light)


## The server's word on it this step: [id, level, reach, curses, ward, upgrade cost, needs, refund].
func sync(entry: Array) -> void:
	reach = float(entry[2])
	curses = entry[3]
	ward = float(entry[4])
	upgrade_cost = entry[5]
	needs = entry[6]
	refund = int(entry[7])


func promote(to: int, total: int) -> void:
	rank = to
	spent = total
	_dress()
	Vfx.burst(world, global_position + Vector3(0, 2.5, 0), Color(1.0, 0.8, 0.4), 50)
	Vfx.dust(world, global_position, 1.2)


func dismantle() -> void:
	removed = true
	Vfx.dust(world, global_position, 2.0)
	var tw := create_tween()
	tw.tween_property(_model, "position:y", -7.0, 0.6).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tw.tween_callback(queue_free)


func curse(which: String) -> void:
	curses[which] = float(world.start["curses"][which]["duration"])
	_overlay.set_shader_parameter("curse", 1.0)
	if not is_instance_valid(_curse_fx):
		_curse_fx = Vfx.curse_mark(self)


func curse_ends(which: String) -> void:
	curses.erase(which)
	if curses.is_empty():
		lift_curse()


func lift_curse() -> void:
	curses = {}
	_overlay.set_shader_parameter("curse", 0.0)
	if is_instance_valid(_curse_fx):
		_curse_fx.queue_free()


func muzzle() -> Vector3:
	return _muzzle.global_position if _muzzle else global_position + Vector3(0, 4.0, 0)


func _process(delta: float) -> void:
	if removed:
		return
	_t += delta
	_threat *= exp(-delta / 8.0)
	if _crystal:
		_crystal.position.y = sin(_t * 1.7) * 0.12
		_crystal.rotate_y(delta * 0.8)
	if _turret and is_instance_valid(_aim):
		var to := _aim.global_position - _turret.global_position
		var want := atan2(-to.x, -to.z) - global_rotation.y
		_turret.rotation.y = lerp_angle(_turret.rotation.y, want, min(1.0, delta * 10.0))


## A bolt the server launched: it flies from the muzzle to its target in the bolt's own flight time.
func fire(bolt: Dictionary, target: Monster) -> void:
	_threat += float(level()["damage"])
	_aim = target
	var look: String = LOOKS.get(kind, "arrow")
	var flight: float = max(float(bolt["left"]), 0.05)
	var to := target.chest() if target else world.ground(bolt["last"]) + Vector3(0, 1.0, 0)
	var speed := muzzle().distance_to(to) / flight
	match look:
		"arrow":
			Sfx.play("arrow_cast", muzzle())
			if _turret:
				var kick := create_tween()
				kick.tween_property(_turret, "scale", Vector3(1.0, 1.0, 0.92), 0.05)
				kick.tween_property(_turret, "scale", Vector3.ONE, 0.25)
		"fire":
			Sfx.play("fire_cast", muzzle())
	Bolt.launch(world, look, muzzle(), target, speed, func(_m, _at: Vector3): pass, to)


## Where a bolt lands, as the server says: the blast, the hit and its sound.
static func impact(w: World, bolt: Dictionary, at: Vector3, target: Monster) -> void:
	var where := target.chest() if target and target.alive() else at + Vector3(0, 1.0, 0)
	match LOOKS.get(String(bolt["kind"]), "arrow"):
		"arrow":
			Sfx.play("arrow_hit", where)
			Vfx.impact(w, where, Color(1.0, 0.85, 0.6), 12)
		"fire":
			Sfx.play("fireball", where)
			Vfx.explosion(w, where, Color(1.0, 0.45, 0.1), float(bolt["splash"]) > 0.0)
		"frost":
			Sfx.play("frost", where)
			Vfx.frost_burst(w, where)


## Lightning through the points of a chain, from the muzzle.
func strike(points: Array) -> void:
	_threat += float(level()["damage"])
	Vfx.lightning(world, points)
	Sfx.play("lightning", points[1] if points.size() > 1 else muzzle())


## A frost nova (or an altar's pulse): a ring of cold round the tower.
func nova() -> void:
	_threat += float(level()["damage"])
	Vfx.frost_burst(world, global_position + Vector3(0, 1.0, 0))
	Sfx.play("frost", global_position)
