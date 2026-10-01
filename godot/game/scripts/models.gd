class_name Models
extends RefCounted
## Instancing the built models (game/assets/models/*.glb) with the material library applied.

static var _scenes: Dictionary = {}


static func make(name: String) -> Node3D:
	if not _scenes.has(name):
		_scenes[name] = load("res://assets/models/%s.glb" % name)
	var node: Node3D = (_scenes[name] as PackedScene).instantiate()
	Mats.apply(node)
	return node


static func node(root: Node, name: String) -> Node3D:
	return root.find_child(name, true, false) as Node3D


static func player(root: Node) -> AnimationPlayer:
	var found := root.find_children("*", "AnimationPlayer", true, false)
	return found[0] as AnimationPlayer if found.size() > 0 else null


## The animation in `player` named `action`, or ending with "|action" as Blender's exporter may name it.
static func anim_name(player: AnimationPlayer, action: String) -> String:
	for n in player.get_animation_list():
		if n == action or n.ends_with("|" + action) or n.ends_with("_" + action):
			return n
	return ""
