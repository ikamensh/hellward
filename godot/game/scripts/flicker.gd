extends OmniLight3D
## Firelight: the energy wanders with layered noise around the energy it started with.

var base := 0.0
var _t := 0.0
var _seed := 0.0


func _ready() -> void:
	base = light_energy
	_seed = randf() * 100.0


func _process(delta: float) -> void:
	_t += delta
	var n := sin(_t * 7.3 + _seed) * 0.5 + sin(_t * 13.1 + _seed * 2.0) * 0.3 + sin(_t * 23.7 + _seed * 3.0) * 0.2
	light_energy = base * (0.82 + 0.18 * n)
