class_name Tower
extends Node3D
## A tower on its tile: it turns, aims and shoots the monster nearest the sanctuary within its reach.
## Arrow fires ballista bolts, Pyre firebolts, Frost chilling shards, Storm lightning that leaps.
## A leader's curse halves its blows and slows it until Cleanse lifts it.

const NAMES := {"arrow": "Arrow Tower", "pyre": "Pyre", "frost": "Frost Shrine", "storm": "Storm Obelisk"}
const ELEMENT := {"arrow": "physical", "pyre": "fire", "frost": "cold", "storm": "lightning"}

var world: World
var kind: String
var tile: Vector2i
var rank := 0
var spent := 0
var cursed := 0.0
var removed := false

var _levels: Array
var _cooldown := 0.5
var _threat := 0.0
var _model: Node3D
var _turret: Node3D
var _muzzle: Node3D
var _crystal: Node3D
var _overlay: ShaderMaterial
var _curse_fx: Node3D
var _telegraph: Node3D
var _t := 0.0


func setup(w: World, k: String, at: Vector2i) -> void:
	world = w
	kind = k
	tile = at
	_levels = w.data["towers"][k]["levels"]
	spent = int(_levels[0]["cost"])


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
	return "tower_arrow_%d" % (rank + 1) if kind == "arrow" else "tower_" + kind


func title() -> String:
	return NAMES[kind]


func level() -> Dictionary:
	return _levels[rank]


func reach() -> float:
	return float(level()["range"]) * Level.TILE


func threat() -> float:
	return _threat


func _dress() -> void:
	if _model:
		_model.queue_free()
	_model = Models.make(model_name(kind, rank))
	add_child(_model)
	if kind != "arrow":
		_model.scale = Vector3.ONE * (1.0 + 0.14 * rank)
	_turret = Models.node(_model, "turret")
	_muzzle = Models.node(_model, "fx_muzzle")
	_crystal = Models.node(_model, "crystal")
	_overlay = ShaderMaterial.new()
	_overlay.shader = preload("res://shaders/overlay.gdshader")
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
	_overlay.set_shader_parameter("curse", 1.0 if cursed > 0.0 else 0.0)


## A tower model's own fire and glow: the Pyre's flame, the shrine's and the obelisk's light. The HUD's
## portraits of the towers wear them too.
static func dress_fx(model: Node3D, kind: String, rank: int) -> void:
	var light: OmniLight3D = null
	match kind:
		"pyre":
			var f := Models.node(model, "fx_fire")
			f.add_child(Fx.fire(0.9 + 0.15 * rank, 1.1))
			light = Fx.fire_light(3.0 + rank, 9.0, true)
			f.add_child(light)
		"frost":
			light = OmniLight3D.new()
			light.light_color = Color(0.4, 0.7, 1.0)
			light.light_energy = 2.0 + 0.5 * rank
			light.omni_range = 7.0
			Models.node(model, "fx_glow").add_child(light)
		"storm":
			light = OmniLight3D.new()
			light.light_color = Color(0.45, 0.6, 1.0)
			light.light_energy = 2.0 + 0.5 * rank
			light.omni_range = 8.0
			var crystal := Models.node(model, "crystal")
			(crystal if crystal else Models.node(model, "fx_muzzle")).add_child(light)


func promote() -> void:
	rank += 1
	spent += int(_levels[rank]["cost"])
	_dress()
	Vfx.burst(world, global_position + Vector3(0, 2.5, 0), Color(1.0, 0.8, 0.4), 50)
	Vfx.dust(world, global_position, 1.2)


func dismantle() -> void:
	removed = true
	Vfx.dust(world, global_position, 2.0)
	var tw := create_tween()
	tw.tween_property(_model, "position:y", -7.0, 0.6).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tw.tween_callback(queue_free)


func chanted_at(seconds: float) -> void:
	if is_instance_valid(_telegraph):
		_telegraph.queue_free()
	_telegraph = Vfx.rune_circle(self, Monster.CURSE_RADIUS, seconds)


func curse(seconds: float) -> void:
	cursed = seconds
	_overlay.set_shader_parameter("curse", 1.0)
	if not is_instance_valid(_curse_fx):
		_curse_fx = Vfx.curse_mark(self)


func lift_curse() -> void:
	cursed = 0.0
	_overlay.set_shader_parameter("curse", 0.0)
	if is_instance_valid(_curse_fx):
		_curse_fx.queue_free()


func _process(delta: float) -> void:
	if removed:
		return
	_t += delta
	_threat *= exp(-delta / 8.0)
	if cursed > 0.0:
		cursed -= delta
		if cursed <= 0.0:
			lift_curse()
	if _crystal:
		_crystal.position.y = sin(_t * 1.7) * 0.12
		_crystal.rotate_y(delta * 0.8)
	var target := _pick()
	if target and _turret:
		var to := target.global_position - _turret.global_position
		var want := atan2(-to.x, -to.z) - global_rotation.y
		_turret.rotation.y = lerp_angle(_turret.rotation.y, want, min(1.0, delta * 10.0))
	_cooldown -= delta
	if _cooldown > 0.0 or target == null:
		return
	var slow := 1.4 if cursed > 0.0 else 1.0
	_cooldown = slow / float(level()["rate"])
	_fire(target)


func _pick() -> Monster:
	var best: Monster = null
	for m in world.near(global_position, reach()):
		if best == null or m.progress > best.progress:
			best = m
	return best


func _damage() -> float:
	return float(level()["damage"]) * (0.5 if cursed > 0.0 else 1.0)


func _muzzle_pos() -> Vector3:
	return _muzzle.global_position if _muzzle else global_position + Vector3(0, 4.0, 0)


func _fire(target: Monster) -> void:
	var dmg := _damage()
	var speed := float(world.data["towers"][kind]["bolt_speed"]) * Level.TILE
	_threat += dmg
	match kind:
		"arrow":
			Sfx.play("arrow_cast", _muzzle_pos())
			Bolt.launch(world, "arrow", _muzzle_pos(), target, speed * 1.4, func(m, at: Vector3):
				if m:
					m.hurt(dmg, "physical")
					Sfx.play("arrow_hit", at)
				Vfx.impact(world, at, Color(1.0, 0.85, 0.6), 12))
			if _turret:
				var kick := create_tween()
				kick.tween_property(_turret, "scale", Vector3(1.0, 1.0, 0.92), 0.05)
				kick.tween_property(_turret, "scale", Vector3.ONE, 0.25)
		"pyre":
			Sfx.play("fire_cast", _muzzle_pos())
			Bolt.launch(world, "fire", _muzzle_pos(), target, speed, func(m, at: Vector3):
				Sfx.play("fireball", at)
				if m: m.hurt(dmg, "fire")
				Vfx.explosion(world, at, Color(1.0, 0.45, 0.1), m != null))
		"frost":
			var lv := level()
			Bolt.launch(world, "frost", _muzzle_pos(), target, speed, func(m, at: Vector3):
				Sfx.play("frost", at)
				if m:
					m.hurt(dmg, "cold")
					m.chill(float(lv["chill"]), float(lv["chill_time"]))
				Vfx.frost_burst(world, at))
		"storm":
			var chain: Array = [target]
			var from: Monster = target
			for i in World.STORM_LEAPS:
				var next: Monster = null
				for m in world.near(from.global_position, 3.6):
					if not chain.has(m) and (next == null or m.global_position.distance_to(from.global_position) < next.global_position.distance_to(from.global_position)):
						next = m
				if next == null:
					break
				chain.append(next)
				from = next
			var points := [_muzzle_pos()]
			for i in chain.size():
				points.append(chain[i].chest())
			Vfx.lightning(world, points)
			Sfx.play("lightning", target.chest())
			for i in chain.size():
				chain[i].hurt(dmg * pow(0.7, i), "lightning")
