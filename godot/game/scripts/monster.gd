class_name Monster
extends Node3D
## A monster as the server plays it: where it walks (its route and the distance along it), its life, the cold
## and poison on it, a leader's pondering and chanting. Between two steps it glides; its walk plays at the pace
## it moves. Its death, its leak into the sanctuary and a leader's curse come as events (World._event).

# kinds with a model of their own; the others wear the nearest one, tinted and sized (`STAND_INS`) until theirs exist
const HEIGHTS := {"fallen": 1.2, "shaman": 1.95, "zombie": 1.9, "skeleton": 1.85, "bat": 0.7, "drowned": 1.9,
	"gargoyle": 1.7}
const BODY := 1.3                    # bodies a size up from life, so they read from the battle camera
# each kind's rim (and its x-ray behind a tower): Fallen ember, Shaman crimson (the leader's violet is its skull's
# eyes and its ring, never on its hide), Zombie grave-green, Skeleton bone (dimmer: a bright rim on every thin bone
# shimmers at range); each later kind a hue of its own
const RIM := {"fallen": Color(1.3, 0.4, 0.12), "shaman": Color(1.25, 0.26, 0.22), "zombie": Color(0.5, 0.6, 0.38),
	"skeleton": Color(0.72, 0.68, 0.56), "bat": Color(1.1, 0.15, 0.2), "drowned": Color(0.35, 0.7, 0.75),
	"gargoyle": Color(0.5, 0.75, 0.6)}
const KINDGLOW := 0.25              # how strongly that rim lights a living body at any distance
# how fast each walk cycle carries the body at speed_scale 1 (m/s): the walk plays faster as the body speeds up
# (tools/blender/audit.py measures it off the feet); a flyer's wingbeat keeps its own rate
const WALK := {"fallen": 0.89, "shaman": 0.94, "zombie": 0.44, "skeleton": 0.89, "drowned": 0.6}
# a kind without a model: [the model it borrows, its tint]; its height follows its size in the rules
const STAND_INS := {
	"goatman": ["zombie", Color(0.55, 0.38, 0.22)], "overlord": ["zombie", Color(0.75, 0.2, 0.12)],
	"azazel": ["zombie", Color(0.6, 0.06, 0.05)], "priest": ["shaman", Color(0.85, 0.8, 0.65)],
	"witch": ["shaman", Color(0.8, 0.12, 0.2)], "flayer": ["fallen", Color(0.3, 0.45, 0.2)],
	"zealot": ["skeleton", Color(0.85, 0.7, 0.4)], "spider": ["fallen", Color(0.2, 0.18, 0.2)],
	"hulk": ["zombie", Color(0.35, 0.55, 0.2)],
	"fetish": ["shaman", Color(0.45, 0.65, 0.25)], "inquisitor": ["shaman", Color(0.95, 0.8, 0.45)],
	"bone_priest": ["shaman", Color(0.7, 0.55, 0.95)],
}
const MAX_STRIDE := 2.4             # beyond this the legs blur; the feet slide a little instead
const LANE := 6.0                    # the rules' lane (about ±0.28 tiles) spread to metres across the street
const FLY := 2.4                     # a flyer's height over the ground
const EMERGE := 1.2                  # seconds a newcomer takes to come out of its portal

var world: World
var id := 0
var kind: String
var stats: Dictionary                # the rules' table for its kind (the battle message)
var hp := 1.0
var max_hp := 1.0
var height := 1.5
var leader := false
var wave := -1
var gone := false                    # dead and faded, or inside the sanctuary: the world frees it
var progress := 0.0                  # 0..1 along its route, for the camera

var _route := "main"
var _lateral := 0.0
var _s0 := 0.0                       # the distance along the route at the last two steps
var _s1 := 0.0
var _flags := 0
var _frozen := false
var _chilled := false
var _state := "walk"                 # walk, ponder, chant, door, dead
var _state_t := 0.0
var _age := 0.0
var _chant_spot := Vector2i(-1, -1)
var _chant_time := 0.0               # how long the chant or mark lasts, from the rules' table
var _curse_target: Tower
var _beam: Node3D
var _circle: Node3D
var _base := "fallen"                # the model it wears
var _model: Node3D
var _anim: AnimationPlayer
var _overlay: ShaderMaterial
var _bar: MeshInstance3D
var _ring: MeshInstance3D            # a leader's violet ring on the ground
var _flash := 0.0
var _flinch: Flinch
var _zap := 0.0                      # lightning still crawling over a corpse, seconds
var _dying: Array[ORMMaterial3D] = []   # a corpse's own materials, its eyes going out
var _frozen_dead := false            # killed by cold: its rime keeps its colour
var _curse_glow: Array[ORMMaterial3D] = []   # a chanting Shaman's skull, flaring

# how each element marks a blow, and a death
const ELEMENT_FLASH := {"fire": Color(1.0, 0.45, 0.1), "cold": Color(0.45, 0.75, 1.0),
	"lightning": Color(0.75, 0.85, 1.0), "poison": Color(0.45, 0.9, 0.25)}
# what each body leaves when it dies: blood for the living, ichor for the dead flesh, bone dust for bones
const REMAINS := {"fallen": Color(1, 1, 1), "shaman": Color(1, 1, 1), "zombie": Color(0.32, 0.36, 0.2)}


func setup(w: World, ident: int, facts: Dictionary, table: Dictionary) -> void:
	world = w
	id = ident
	kind = String(facts["kind"])
	stats = table
	_route = String(facts["route"])
	_lateral = float(facts["lane"]) * LANE
	max_hp = float(facts["max_hp"])
	hp = max_hp
	wave = int(facts["wave"])
	leader = table["leader"] != null
	_base = kind if HEIGHTS.has(kind) else String(STAND_INS.get(kind, ["fallen"])[0])
	height = HEIGHTS[kind] * BODY if HEIGHTS.has(kind) else float(table["size"]) * 2.3 * BODY
	_s0 = 0.0
	_s1 = 0.0


## The overlay every living monster wears (shaders/overlay.gdshader), in its kind's colour `rim`: the review
## stages (preview.gd, lineup.gd) dress models in it too, so they show what a battle shows.
static func overlay(rim: Color) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/overlay.gdshader")
	m.set_shader_parameter("kind_rim", rim)
	m.set_shader_parameter("xray", 1.0)
	m.set_shader_parameter("moonrim", 0.12)   # a hint only: more washes a detailed body grey-blue
	m.set_shader_parameter("kindglow", KINDGLOW)
	return m


func title() -> String:
	return String(stats["name"])


func _ready() -> void:
	_model = Models.make("mon_" + _base)
	_model.scale = Vector3.ONE * BODY * (1.0 if HEIGHTS.has(kind) else height / (HEIGHTS[_base] * BODY))
	# a pack is not cloned: each a little larger or smaller (±6%) and one of three tints, fixed by its id
	_model.scale *= 1.0 + 0.06 * (float((id * 7919) % 101) / 50.0 - 1.0)
	if HEIGHTS.has(kind):
		Mats.vary(_model, id % Mats.VARIANTS.size())
	add_child(_model)
	_anim = Models.player(_model)
	for n in ["walk", "idle", "cast"]:
		var found := Models.anim_name(_anim, n)
		if found != "":
			_anim.get_animation(found).loop_mode = Animation.LOOP_LINEAR
	_play("walk", randf())
	_overlay = overlay(RIM.get(kind, STAND_INS.get(kind, [null, Color(0.9, 0.4, 0.3)])[1]))
	if STAND_INS.has(kind):
		_overlay.set_shader_parameter("tint", STAND_INS[kind][1])
	for mi in _model.find_children("*", "MeshInstance3D", true, false):
		(mi as MeshInstance3D).material_overlay = _overlay
		(mi as MeshInstance3D).layers = 2   # decals (cull_mask 1) never land on a body
	var skeletons := _model.find_children("*", "Skeleton3D", true, false)
	if skeletons.size() > 0:
		_flinch = Flinch.new()
		skeletons[0].add_child(_flinch)
	_bar = Vfx.health_bar(0.9 if height < 1.9 else 1.2)
	_bar.position = Vector3(0, height + 0.35, 0)
	add_child(_bar)
	_bar.visible = leader   # a leader's life always shows; the others' once they are hurt
	if leader:
		var ring := MeshInstance3D.new()
		var pm := PlaneMesh.new()
		pm.size = Vector2(2.6, 2.6)
		ring.mesh = pm
		var rm := ShaderMaterial.new()
		rm.shader = preload("res://shaders/ring.gdshader")
		rm.set_shader_parameter("radius", 1.0)
		rm.set_shader_parameter("color", Color(0.8, 0.3, 1.0, 1.0))
		ring.material_override = rm
		ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		ring.position.y = 0.06
		add_child(ring)
		_ring = ring
	global_position = _where(0.0)


## The server's word on it this step: [id, s, hp, flags, chill, frozen, poison stacks, door].
func sync(entry: Array, stepped: bool) -> void:
	if stepped:
		_s0 = _s1
	_s1 = float(entry[1])
	if hp != float(entry[2]):
		hp = float(entry[2])
		_bar.visible = true
		_bar.set_instance_shader_parameter("fill", max(hp, 0.0) / max_hp)
	_flags = int(entry[3])
	_chilled = float(entry[4]) > 0.0
	_frozen = float(entry[5]) > 0.0
	if _state == "ponder" and (_flags & 1) == 0 and (_flags & 2) == 0:
		_resume()   # its question was answered without a curse: it holds


func alive() -> bool:
	return _state != "dead" and _state != "door"


## How far a leader's curse has come, 0..1 from its pondering to the curse landing; -1 when it is not cursing.
func casting() -> float:
	if _state == "ponder":
		return min(_state_t, 0.5) / 0.5 * 0.3
	if _state == "chant":
		return 0.3 + 0.7 * clamp(_state_t / max(_chant_time, 0.1), 0.0, 1.0)
	return -1.0


func pondering() -> bool:
	return _state == "ponder"


## The tower a leader is cursing, while it chants; null otherwise.
func curse_target() -> Tower:
	return _curse_target if _state == "chant" and is_instance_valid(_curse_target) else null


func chest() -> Vector3:
	return global_position + Vector3(0, height * 0.6, 0)


func head() -> Vector3:
	return global_position + Vector3(0, height + 0.1, 0)


func _where(s: float) -> Vector3:
	var at := world.level.place(_route, s, _lateral)
	at.y = world.level.step_height(at) + (FLY if bool(stats["flying"]) else 0.0)
	return at


func _process(delta: float) -> void:
	_age += delta
	_flash = max(0.0, _flash - delta * 6.0)
	if _zap > 0.0:   # lightning crawls over the corpse a while: it flickers
		_zap -= delta
		_flash = 0.9 if fmod(_age * 23.0, 1.0) < 0.45 else 0.0
	_overlay.set_shader_parameter("flash", _flash)
	_overlay.set_shader_parameter("chill", 1.0 if _chilled or _frozen else 0.0)
	_state_t += delta
	match _state:
		"walk", "ponder", "chant":
			_walk(delta)
			if _state == "chant":   # the skull's eyes flare and throb with the curse
				for m in _curse_glow:
					m.emission_energy_multiplier = Mats.GLOW * (2.2 + 1.2 * sin(_state_t * 9.0))
		"door":
			_state_t = min(_state_t, 1.4)
			global_position = _where(world.level.route_length(_route) + _state_t * 3.0)
			if _state_t >= 1.4:
				gone = true
		"dead":
			Mats.eyes_out(_dying, _state_t, not _frozen_dead)
			if _state_t > 3.0:
				position.y -= delta * 0.5
			if _state_t > 5.0:
				gone = true


func _walk(delta: float) -> void:
	var s := lerpf(_s0, _s1, world.alpha)
	if _age < EMERGE:   # out of the portal: it comes from the portal's mouth to its place on the route
		s -= Level.APPROACH / Level.TILE * pow(1.0 - _age / EMERGE, 2.0)
	var p := _where(s)
	var step := p - global_position
	var pace: float = Vector2(step.x, step.z).length() / max(delta, 0.0001)
	if _state == "walk" and not bool(stats["flying"]):
		_anim.speed_scale = 0.0 if _frozen else min(pace / (WALK.get(_base, 0.7) * BODY), MAX_STRIDE)
	else:
		_anim.speed_scale = 0.0 if _frozen else 1.0
	if Vector2(step.x, step.z).length() > 0.001 and _state == "walk":
		rotation.y = lerp_angle(rotation.y, atan2(-step.x, -step.z), min(1.0, delta * 8.0))
	global_position = p
	progress = s / max(world.level.route_length(_route), 0.01)


func _play(action: String, at := 0.0) -> void:
	var n := Models.anim_name(_anim, action)
	if n == "":
		return
	_anim.play(n, 0.15)
	if at > 0.0:
		_anim.seek(_anim.current_animation_length * at, true)


func hit(element: String) -> void:
	if not alive():
		return
	_flash = 1.0
	_overlay.set_shader_parameter("flash_color", ELEMENT_FLASH.get(element, Color(1.0, 0.55, 0.35)))
	if _flinch:
		_flinch.kick(7.0 + randf() * 4.0, randf_range(-1.0, 1.0))


func die(element: String, bounty: int) -> void:
	if not alive():
		return
	_state = "dead"
	_state_t = 0.0
	_anim.speed_scale = 1.0
	# two deaths a kind where it has them, one or the other by its id
	_play("die2" if id % 2 == 1 and Models.anim_name(_anim, "die2") != "" else "die")
	_bar.visible = false
	if bool(stats["flying"]):   # a flyer's body drops out of the air as it dies
		var fall := create_tween()
		fall.tween_property(self, "position:y", position.y - FLY, 0.55).set_ease(Tween.EASE_IN) \
			.set_trans(Tween.TRANS_QUAD)
	_overlay.set_shader_parameter("kind_rim", Color.BLACK)   # the dead stop catching the eye
	_overlay.set_shader_parameter("xray", 0.0)
	if _ring:
		_ring.queue_free()
	_drop_beam()
	if bounty > 0:
		Vfx.coin(world, global_position + Vector3(0, height + 0.3, 0), bounty)
		Sfx.play("gold", global_position)
	Sfx.play("death_" + kind, chest())
	if REMAINS.has(_base):
		Vfx.blood(world, global_position, 0.5 + height * 0.25, REMAINS[_base])
	else:   # bones leave no blood: a puff of bone dust where it falls apart
		Vfx.dust(world, global_position, 0.6, Color(0.6, 0.56, 0.48))
	_mark_death(element)
	if element != "fire":   # a charred body's embers smoulder on
		_frozen_dead = element == "cold"
		_dying = Mats.own(_model)
	if leader:
		Vfx.burst(world, chest(), Color(0.7, 0.2, 1.0), 40)


## The element that killed it marks the corpse: fire chars it and leaves it smouldering, cold rimes it, lightning
## crawls over it, poison leaves it in a green fume.
func _mark_death(element: String) -> void:
	match element:
		"fire":
			Mats.burnt(_model)
			var flames := Fx.fire(0.6, 0.6)
			add_child(flames)
			flames.position = Vector3(0, 0.3, 0)
			var tw := flames.create_tween()
			tw.tween_interval(2.0)
			tw.tween_property(flames, "amount_ratio", 0.0, 1.0)
		"cold":
			Mats.frozen(_model)
			Vfx.frost_burst(world, chest())
		"lightning":
			_zap = 0.6
			Vfx.impact(world, chest(), Color(0.7, 0.85, 1.0), 30)
		"poison":
			Vfx.dust(world, global_position, 0.5, Color(0.35, 0.55, 0.2))


## Gone from the rules unseen (it died in the step it came): it fades where it stands.
func vanish() -> void:
	_state = "dead"
	_state_t = 3.0


func leak() -> void:
	if not alive():
		return
	_state = "door"
	_state_t = 0.0
	_anim.speed_scale = 1.0
	_play("attack")
	_drop_beam()
	var tw := create_tween()
	tw.tween_interval(0.6)
	tw.tween_property(self, "scale", Vector3(0.01, 0.01, 0.01), 0.8)


# -- A leader's curse: it ponders (asks its planner), then chants or marks a spot; the curse lands, breaks or fizzles

func ponder() -> void:
	if not alive():
		return
	_state = "ponder"
	_state_t = 0.0
	_play("idle")
	Vfx.ponder(self)
	Sfx.play("ponder", chest())


func chant(curse: String, spot: Vector2i, marking: bool) -> void:
	if not alive():
		return
	_state = "chant"
	_state_t = 0.0
	_chant_spot = spot
	var spec: Dictionary = stats["leader"]
	_chant_time = float(spec["mark"]) if marking and float(spec["mark"]) > 0.0 else float(spec["channel"])
	_play("cast")
	if _curse_glow.is_empty():
		_curse_glow = Mats.own(_model, "mon_skull")
	var at := world.level.tile_pos(spot)
	var to := at - global_position
	rotation.y = atan2(-to.x, -to.z)
	_curse_target = world.tower_at(spot)
	var radius := (float(world.start["curses"][curse]["radius"]) + float(spec["widen"])) * Level.TILE
	_drop_beam()
	var tip := Models.node(_model, "fx_cast")
	if _curse_target:
		_beam = Vfx.curse_beam(world, tip if tip else self, _curse_target)
	_circle = Vfx.rune_circle_at(world, at, radius, _chant_time)
	Sfx.play("chant", chest())


func broken() -> void:
	Vfx.burst(world, chest(), Color(1.0, 0.9, 0.6), 40)
	_resume()


func stop_chant() -> void:
	_resume()


func _resume() -> void:
	_drop_beam()
	if not alive():
		return
	_state = "walk"
	_state_t = 0.0
	_curse_target = null
	for m in _curse_glow:
		m.emission_energy_multiplier = Mats.GLOW
	_play("walk")


func _drop_beam() -> void:
	if is_instance_valid(_beam):
		_beam.queue_free()
	_beam = null
	if is_instance_valid(_circle):
		_circle.queue_free()
	_circle = null
