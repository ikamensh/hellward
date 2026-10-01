class_name Monster
extends Node3D
## A monster walking its route from the portal to the cathedral. A Fallen Shaman is a leader: now and
## then it stops, ponders, and chants a curse at the tower hurting its pack most.

const HEIGHTS := {"fallen": 1.15, "shaman": 1.5, "zombie": 1.9, "skeleton": 1.85}
# how fast each walk cycle carries the body at speed_scale 1 (m/s): the walk plays faster as the body speeds up
const WALK := {"fallen": 0.67, "shaman": 0.72, "zombie": 0.75, "skeleton": 0.81}
const MAX_STRIDE := 2.4             # beyond this the legs blur; the feet slide a little instead
# 3D bodies walk at 0.6 of the 2D game's pace: a 1.1 m imp at 2.7 m/s is a blur, not a Fallen
const PACE := 0.6
const LANE := 1.7                    # how far from the route's centre line a monster may wander, metres
const CURSE_REACH := 7.0             # a leader curses towers within this many metres
const CURSE_RADIUS := 3.0            # and every tower this close to the one it picked
const CURSE_TIME := 14.0

var world: World
var kind: String
var stats: Dictionary
var hp := 1.0
var max_hp := 1.0
var height := 1.5
var leader := false
var gone := false                   # dead and faded, or inside the cathedral: the world frees it
var progress := 0.0                 # 0..1 along the route, for targeting

var _route: PackedVector3Array
var _cum: PackedFloat32Array
var _s := 0.0
var _lateral := 0.0
var _lateral_goal := 0.0
var _speed := 1.0                   # metres per second
var _chill := 0.0
var _chill_left := 0.0
var _state := "walk"                # walk, ponder, chant, door, dead
var _state_t := 0.0
var _curse_clock := 0.0
var _curse_target: Tower
var _beam: Node3D
var _rng := RandomNumberGenerator.new()

var _model: Node3D
var _anim: AnimationPlayer
var _overlay: ShaderMaterial
var _bar: MeshInstance3D
var _flash := 0.0


func setup(w: World, k: String, st: Dictionary, route: PackedVector3Array, life: float, seed: int) -> void:
	world = w
	kind = k
	stats = st
	_rng.seed = seed
	max_hp = float(st["hp"]) * life
	hp = max_hp
	height = HEIGHTS[k]
	leader = k == "shaman"
	_speed = float(st["speed"]) * Level.TILE * PACE
	_route = route
	_cum = PackedFloat32Array([0.0])
	for i in range(1, route.size()):
		_cum.append(_cum[i - 1] + route[i].distance_to(route[i - 1]))
	_lateral = _rng.randf_range(-LANE, LANE)
	_lateral_goal = _lateral
	_curse_clock = _rng.randf_range(4.0, 7.0)


func _ready() -> void:
	_model = Models.make("mon_" + kind)
	add_child(_model)
	_anim = Models.player(_model)
	for n in ["walk", "idle", "cast"]:
		var found := Models.anim_name(_anim, n)
		if found != "":
			_anim.get_animation(found).loop_mode = Animation.LOOP_LINEAR
	_play("walk", _rng.randf())
	_overlay = ShaderMaterial.new()
	_overlay.shader = preload("res://shaders/overlay.gdshader")
	for mi in _model.find_children("*", "MeshInstance3D", true, false):
		(mi as MeshInstance3D).material_overlay = _overlay
	_bar = Vfx.health_bar(0.9 if height < 1.6 else 1.2)
	_bar.position = Vector3(0, height + 0.35, 0)
	add_child(_bar)
	_bar.visible = false
	global_position = _place(0.0)


func alive() -> bool:
	return _state != "dead" and _state != "door"


func chest() -> Vector3:
	return global_position + Vector3(0, height * 0.6, 0)


func head() -> Vector3:
	return global_position + Vector3(0, height + 0.1, 0)


func hurt(amount: float, element: String) -> void:
	if not alive():
		return
	var resist: float = stats["resist"].get(element, 0.0)
	hp -= amount * (1.0 - resist)
	_flash = 1.0
	_bar.visible = true
	_bar.set_instance_shader_parameter("fill", max(hp, 0.0) / max_hp)
	if hp <= 0.0:
		_die()


func chill(slow: float, seconds: float) -> void:
	_chill = max(_chill, slow * (1.0 - float(stats["resist"].get("cold", 0.0))))
	_chill_left = max(_chill_left, seconds)


func _process(delta: float) -> void:
	_flash = max(0.0, _flash - delta * 7.0)
	_chill_left = max(0.0, _chill_left - delta)
	if _chill_left <= 0.0:
		_chill = 0.0
	_overlay.set_shader_parameter("flash", _flash)
	_overlay.set_shader_parameter("chill", 1.0 if _chill > 0.0 else 0.0)
	_state_t += delta
	match _state:
		"walk":
			_walk(delta)
			if leader:
				_curse_clock -= delta
				if _curse_clock <= 0.0:
					_ponder()
		"ponder":
			if _state_t > 1.1:
				_chant()
		"chant":
			if not is_instance_valid(_curse_target) or _curse_target.removed:
				_resume()
			elif _state_t > 1.9:
				_curse_lands()
		"door":
			if _state_t > 1.4:
				gone = true
		"dead":
			if _state_t > 3.0:
				position.y -= delta * 0.5
			if _state_t > 5.0:
				gone = true


func _walk(delta: float) -> void:
	var pace := _speed * (1.0 - _chill)
	_anim.speed_scale = min(pace / WALK[kind], MAX_STRIDE)
	_s += pace * delta
	if _rng.randf() < delta * 0.25:
		_lateral_goal = _rng.randf_range(-LANE, LANE)
	_lateral = move_toward(_lateral, _lateral_goal, delta * 0.6)
	var total := _cum[_cum.size() - 1]
	progress = _s / total
	if _s >= total - 0.5:
		_enter_door()
		return
	var p := _place(_s)
	var step := p - global_position
	if Vector2(step.x, step.z).length() > 0.001:
		rotation.y = lerp_angle(rotation.y, atan2(-step.x, -step.z), min(1.0, delta * 8.0))
	global_position = p


## The point `s` metres along the route, pushed `_lateral` metres to its side.
func _place(s: float) -> Vector3:
	var i := _cum.bsearch(s) - 1
	i = clamp(i, 0, _route.size() - 2)
	var a := _route[i]
	var b := _route[i + 1]
	var seg := _cum[i + 1] - _cum[i]
	var t: float = 0.0 if seg <= 0.0 else clamp((s - _cum[i]) / seg, 0.0, 1.0)
	var dir := (b - a).normalized()
	var side := Vector3(-dir.z, 0, dir.x)
	# no wandering in the portal's mouth or the cathedral's door
	var squeeze: float = clamp(min(s, _cum[_cum.size() - 1] - s) / 8.0, 0.0, 1.0)
	return a.lerp(b, t) + side * _lateral * squeeze


func _play(action: String, at := 0.0) -> void:
	var n := Models.anim_name(_anim, action)
	if n == "":
		return
	_anim.play(n, 0.15)
	if at > 0.0:
		_anim.seek(_anim.current_animation_length * at, true)


func _die() -> void:
	_state = "dead"
	_state_t = 0.0
	_anim.speed_scale = 1.0
	_play("die")
	_bar.visible = false
	_drop_beam()
	world.killed(self)
	Vfx.blood(world, global_position, 0.5 + height * 0.25)
	if leader:
		Vfx.burst(world, chest(), Color(0.7, 0.2, 1.0), 40)


func _enter_door() -> void:
	_state = "door"
	_state_t = 0.0
	_anim.speed_scale = 1.0
	_play("attack")
	_drop_beam()
	world.breached(self)
	var tw := create_tween()
	tw.tween_interval(0.6)
	tw.tween_property(self, "scale", Vector3(0.01, 0.01, 0.01), 0.8)


# a leader's curse: ponder, chant at the tower that hurts the pack most, and the curse lands on it and its neighbours
func _ponder() -> void:
	var best: Tower = null
	for t in world.towers:
		if t.removed or t.cursed > 0.0:
			continue
		if Vector2(t.global_position.x - global_position.x, t.global_position.z - global_position.z).length() > CURSE_REACH:
			continue
		if best == null or t.threat() > best.threat():
			best = t
	if best == null:
		_curse_clock = 1.5
		return
	_curse_target = best
	_state = "ponder"
	_state_t = 0.0
	_anim.speed_scale = 1.0
	_play("idle")
	Vfx.ponder(self)


func _chant() -> void:
	_state = "chant"
	_state_t = 0.0
	_play("cast")
	var to := _curse_target.global_position - global_position
	rotation.y = atan2(-to.x, -to.z)
	var tip := Models.node(_model, "fx_cast")
	_beam = Vfx.curse_beam(world, tip if tip else self, _curse_target)
	_curse_target.chanted_at(1.9)


func _curse_lands() -> void:
	for t in world.towers:
		if not t.removed and t.global_position.distance_to(_curse_target.global_position) <= CURSE_RADIUS:
			t.curse(CURSE_TIME)
	Vfx.burst(world, _curse_target.global_position + Vector3(0, 1.0, 0), Color(0.7, 0.2, 1.0), 60)
	world.announce.emit("", "The Fallen Shaman curses the %s." % _curse_target.title())
	_resume()


func _resume() -> void:
	_drop_beam()
	_state = "walk"
	_state_t = 0.0
	_curse_clock = _rng.randf_range(9.0, 13.0)
	_play("walk")


func _drop_beam() -> void:
	if is_instance_valid(_beam):
		_beam.queue_free()
	_beam = null
