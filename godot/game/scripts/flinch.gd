class_name Flinch
extends SkeletonModifier3D
## A struck monster's flinch, layered over whatever clip it plays (the walk goes on under it): the spine, chest,
## neck and head are thrown back and a little aside, and spring back. Each `kick` adds to the swing.

const BONES := {"spine": 0.35, "chest": 0.6, "neck": 0.5, "head": 0.8}   # how much of the swing each bone takes
const STIFF := 180.0                 # the spring (1/s²); its damping ratio is DAMP
const DAMP := 0.38

var _angle := Vector2.ZERO           # back (x) and aside (y), radians
var _speed := Vector2.ZERO
var _ids := {}


func _ready() -> void:
	var skeleton := get_skeleton()
	for name in BONES:
		var i := skeleton.find_bone(name)
		if i >= 0:
			_ids[i] = float(BONES[name])


## A blow: thrown back by `strength` (radians a second at the chest) and aside by `side` (-1..1).
func kick(strength := 9.0, side := 0.0) -> void:
	_speed += Vector2(strength, strength * 0.5 * side)


func _process(delta: float) -> void:
	# in steps of at most 1/60 s: a fast-forwarded battle hands over long frames, which a stiff spring cannot take
	var left := minf(delta, 0.5)
	while left > 0.0:
		var dt := minf(left, 1.0 / 60.0)
		left -= dt
		var accel := -_angle * STIFF - _speed * (2.0 * DAMP * sqrt(STIFF))
		_speed += accel * dt
		_angle += _speed * dt
	_angle = _angle.limit_length(0.7)


func _process_modification() -> void:
	if _angle.length() < 0.002:
		return
	var skeleton := get_skeleton()
	for i in _ids:
		var share: float = _ids[i]
		var q := Quaternion(Vector3.RIGHT, -_angle.x * share) * Quaternion(Vector3.FORWARD, _angle.y * share)
		skeleton.set_bone_pose_rotation(i, skeleton.get_bone_pose_rotation(i) * q)
