class_name Tower
extends Node3D
## A tower as the server plays it: built, raised a rank, cursed, quickened by Battle Hymn and sold by events; its
## shots are the server's too (a bolt with its flight time, a chain of lightning, a nova, a hook on its chain),
## shown from its muzzle. It turns to face what it last shot at.

# a family without a model of its own wears another's, tinted, until it has one
const STAND_INS := {}   # kind -> [the model it borrows, its tint], while its own is not built
const LOOKS := {"arrow": "arrow", "ballista": "ballista", "knife": "knife", "pyre": "fire", "frost": "frost",
	"plague": "frost", "altar": "fire", "grove": "fire"}
const CASTS := {"arrow": "arrow_cast", "ballista": "ballista_cast", "knife": "knife_cast", "pyre": "fire_cast",
	"plague": "venom_cast", "altar": "fire_cast"}
const PHYSICAL := ["arrow", "ballista", "hook", "knife"]   # no fire or glow of their own: a lantern lights them
const HYMN := Color(1.0, 0.78, 0.3)  # Battle Hymn's gold

var world: World
var id := 0
var kind: String
var mode := "first"               # its strategy, from its facts and the mode event
var attuned := false              # whether it holds charges, from its frames
var charges := 0.0
var tile: Vector2i
var rank := 0
var spent := 0
var curses := {}                     # curse -> seconds left, from the server
var reach := 0.0                     # tiles
var hymn := 0.0                      # Battle Hymn's seconds left, from the server
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
var _aura: Node3D                    # Battle Hymn's gold round it while the hymn lasts


func setup(w: World, ident: int, facts: Dictionary) -> void:
	world = w
	id = ident
	kind = String(facts["kind"])
	tile = Vector2i(int(facts["tile"][0]), int(facts["tile"][1]))
	rank = int(facts["level"])
	spent = int(facts["spent"])
	mode = String(facts.get("mode", "first"))
	reach = float(world.tower_table(kind)["levels"][rank]["range"])


func _ready() -> void:
	position = world.level.tile_pos(tile)
	_dress()
	# it rises out of the ground in a cloud of dust
	_model.position.y = -6.0
	create_tween().set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT) \
		.tween_property(_model, "position:y", 0.0, 0.7)
	Vfx.dust(world, global_position, 1.6)


## The model a tower of `kind` and `rank` (0..2) wears: its rank's own (tower_<kind>_<rank>) where one is built,
## else its one model, grown a size a rank (`ranked` says which).
static func model_name(kind: String, rank: int) -> String:
	var base: String = STAND_INS[kind][0] if STAND_INS.has(kind) else kind
	var own := "tower_%s_%d" % [base, rank + 1]
	return own if ranked(own) else "tower_" + base


static func ranked(model: String) -> bool:
	return ResourceLoader.exists("res://assets/models/%s.glb" % model)


func title() -> String:
	return String(world.tower_table(kind)["name"])


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
	if not model_name(kind, rank).ends_with("_%d" % (rank + 1)):   # one model for every rank: it grows
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
	if kind in PHYSICAL:   # the others carry their own fire or glow
		var lantern := OmniLight3D.new()
		lantern.light_color = Color(1.0, 0.75, 0.45)
		lantern.light_energy = 1.2 + 0.4 * rank
		lantern.omni_range = 5.0
		lantern.position = Vector3(0, minf(Hud._bounds(_model).end.y * 0.85, 4.2), 0)
		_model.add_child(lantern)
	dress_fx(_model, kind, rank)
	_overlay.set_shader_parameter("curse", 1.0 if cursed() else 0.0)
	_overlay.set_shader_parameter("hymn", 1.0 if hymn > 0.0 else 0.0)


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
		"plague", "grove":   # a venom-green glow from the pool, the grove's runes
			light = OmniLight3D.new()
			light.light_color = Color(0.4, 1.0, 0.3) * tint
			light.light_energy = 1.6 + 0.4 * rank
			light.omni_range = 6.0
			Models.node(model, "fx_glow").add_child(light)
		"altar":   # the cauldron's sickly fire
			var f := Models.node(model, "fx_fire")
			f.add_child(Fx.fire(0.7 + 0.15 * rank, 1.0, Color(0.45, 1.0, 0.4)))
			light = Fx.fire_light(2.5 + rank, 8.0)
			light.light_color = Color(0.55, 1.0, 0.4)
			f.add_child(light)
		"storm":
			light = OmniLight3D.new()
			light.light_color = Color(0.45, 0.6, 1.0) * tint
			light.light_energy = 2.0 + 0.5 * rank
			light.omni_range = 8.0
			var crystal := Models.node(model, "crystal")
			(crystal if crystal else Models.node(model, "fx_muzzle")).add_child(light)


## The server's word on it this step: [id, level, reach, curses, Battle Hymn's seconds left, upgrade cost, needs,
## refund].
func sync(entry: Array) -> void:
	reach = float(entry[2])
	curses = entry[3]
	hymn = float(entry[4])
	upgrade_cost = entry[5]
	needs = entry[6]
	refund = int(entry[7])
	attuned = bool(entry[8])
	charges = float(entry[9])
	_sing(hymn > 0.0)


## Battle Hymn falls on it: a ring of gold bursts from its foot (the aura follows the server's seconds, `sync`).
func hymned() -> void:
	Vfx.burst(world, global_position + Vector3(0, 2.0, 0), HYMN, 50)
	Vfx.impact(world, global_position + Vector3(0, 0.4, 0), HYMN, 40)
	_sing(true)


## The hymn's aura: a gold rim pulsing on the tower at the doubled tempo, gold motes rising round it, a gold ring
## turning at its foot, a warm light.
func _sing(on: bool) -> void:
	_overlay.set_shader_parameter("hymn", 1.0 if on else 0.0)
	if on == is_instance_valid(_aura):
		return
	if not on:
		var fading := _aura
		_aura = null
		for p in fading.find_children("*", "GPUParticles3D", true, false):
			(p as GPUParticles3D).emitting = false
		var tw := fading.create_tween()
		tw.tween_property(fading.get_node("Light"), "light_energy", 0.0, 0.6)
		tw.tween_interval(1.4)
		tw.tween_callback(fading.queue_free)
		return
	_aura = Node3D.new()
	add_child(_aura)
	var top := Hud._bounds(_model).end.y
	var column := MeshInstance3D.new()   # a faint column of gold round it, bands of light streaming up
	var cm := CylinderMesh.new()
	cm.top_radius = 1.25
	cm.bottom_radius = 1.6
	cm.height = top + 2.0
	cm.cap_top = false
	cm.cap_bottom = false
	column.mesh = cm
	var bm := ShaderMaterial.new()
	bm.shader = preload("res://shaders/beam.gdshader")
	bm.set_shader_parameter("color", HYMN)
	bm.set_shader_parameter("height", cm.height)
	bm.set_shader_parameter("energy", 0.35)
	column.material_override = bm
	column.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	column.position.y = cm.height * 0.5
	_aura.add_child(column)
	var motes := Fx.shed(HYMN, 90, 0.2, 2.0, -1.0)
	var pm := motes.process_material as ParticleProcessMaterial
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_RING
	pm.emission_ring_axis = Vector3.UP
	pm.emission_ring_radius = 1.3
	pm.emission_ring_inner_radius = 0.9
	pm.emission_ring_height = 0.3
	pm.initial_velocity_min = 0.6
	pm.initial_velocity_max = 1.4
	motes.local_coords = true
	motes.position = Vector3(0, 0.3, 0)
	motes.emitting = true
	_aura.add_child(motes)
	var ring := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(3.4, 3.4)
	ring.mesh = plane
	var rm := ShaderMaterial.new()
	rm.shader = preload("res://shaders/ring.gdshader")
	rm.set_shader_parameter("radius", 1.45)
	rm.set_shader_parameter("color", Color(HYMN, 1.0))
	ring.material_override = rm
	ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	ring.position.y = 0.1
	_aura.add_child(ring)
	ring.create_tween().set_loops().tween_property(ring, "rotation:y", TAU, 6.0).from(0.0)
	var light := OmniLight3D.new()
	light.name = "Light"
	light.light_color = HYMN
	light.light_energy = 2.4
	light.omni_range = 6.0
	light.position = Vector3(0, top * 0.6, 0)
	_aura.add_child(light)


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
	if CASTS.has(kind):
		Sfx.play(CASTS[kind], muzzle())
	if look in ["arrow", "ballista", "knife"] and _turret:
		var kick := create_tween()
		kick.tween_property(_turret, "scale", Vector3(1.0, 1.0, 0.92), 0.05)
		kick.tween_property(_turret, "scale", Vector3.ONE, 0.25)
	Bolt.launch(world, look, muzzle(), target, speed, func(_m, _at: Vector3): pass, to)


## Where a bolt lands, as the server says: the blast, the hit and its sound.
static func impact(w: World, bolt: Dictionary, at: Vector3, target: Monster) -> void:
	var where := target.chest() if target and target.alive() else at + Vector3(0, 1.0, 0)
	var kind := String(bolt["kind"])
	var splash := float(bolt["splash"]) > 0.0
	match LOOKS.get(kind, "arrow"):
		"arrow":
			Sfx.play("arrow_hit", where)
			Vfx.impact(w, where, Color(1.0, 0.85, 0.6), 12)
		"ballista":   # an iron head driven home: a spray of sparks and splinters, dust off the body
			Sfx.play("ballista_hit", where)
			Vfx.impact(w, where, Color(1.0, 0.8, 0.5), 34)
			Vfx.dust(w, where - Vector3(0, 1.0, 0), 0.5, Color(0.45, 0.38, 0.3))
		"knife":
			Sfx.play("knife_hit", where)
			Vfx.impact(w, where, Color(0.85, 0.9, 1.0), 10)
		"fire":
			Sfx.play("fireball" if splash else "fire_hit", where)
			Vfx.explosion(w, where, Color(1.0, 0.45, 0.1), splash)
		"frost":
			Sfx.play("venom_hit" if kind == "plague" else "frost", where)
			if kind == "plague":
				Vfx.burst(w, where, Color(0.5, 0.9, 0.2), 24)
			else:
				Vfx.frost_burst(w, where)


## A hook thrown at a monster the server has already hauled back from `from_s`: the hook hanging from the crane
## flies out on its chain, bites, drags it back over Monster.DRAG and is reeled in.
func hook(target: Monster, from_s: float) -> void:
	_threat += float(level()["damage"])
	_aim = target
	target.drag(from_s)
	var hanging := Models.node(_model, "hook")   # the crane's own hook, hung from its sheave
	Chain.throw(world, hanging if hanging else (_muzzle if _muzzle else self), target)
	Sfx.play("hook", muzzle())
	if hanging:
		hanging.visible = false
		get_tree().create_timer(Monster.HOOK_FLIGHT + Monster.DRAG + Chain.RETRACT).timeout.connect(func():
			if is_instance_valid(hanging):
				hanging.visible = true)


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
