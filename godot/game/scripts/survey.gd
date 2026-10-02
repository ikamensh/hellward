extends Node3D
## Everything of a kind the rules have, side by side under the game's night (tools/survey.sh drives it), so a
## glance shows what is built and what still wears a stand-in: `what=towers` every tower kind at each rank (a
## column a kind, its ranks from back to front, as tower.gd dresses them); `what=monsters` every monster kind in the rules,
## in its own model with its kind's rim or its tinted stand-in (as monster.gd wears them), a stand-in marked by a red
## post, a flyer off the ground (lower than in battle, to keep the row behind it in sight). The frame is saved to
## `out`, then the run quits.
## User args: what=towers|monsters out=PNG kinds=a,b,c flying=a,b (the rules' kinds, from the server's tables)
## [anim=idle]

const SKIP := 8

var _args := {}
var _frame := 0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=", true, 1)
		_args[kv[0]] = kv[1] if kv.size() > 1 else ""
	Atmosphere.night(self)
	var floor := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(80, 80)
	floor.mesh = pm
	var m := Mats.textured("cobbles")
	m.uv1_scale = Vector3(80, 80, 1)
	floor.material_override = m
	add_child(floor)
	var kinds: PackedStringArray = String(_args.get("kinds", "")).split(",", false)
	var cam := Camera3D.new()
	cam.fov = 40
	add_child(cam)
	if _args.get("what", "monsters") == "towers":
		for i in kinds.size():
			for rank in 3:
				var body := Models.make(Tower.model_name(kinds[i], rank))
				if not Tower.model_name(kinds[i], rank).ends_with("_%d" % (rank + 1)):
					body.scale = Vector3.ONE * (1.0 + 0.14 * rank)
				body.position = Vector3((i - (kinds.size() - 1) * 0.5) * 3.4, 0, (rank - 1) * 4.6)
				add_child(body)
				Tower.dress_fx(body, kinds[i], rank)
		var span := kinds.size() * 3.4
		cam.position = Vector3(0, span * 0.55, span * 0.95)
		cam.look_at(Vector3(0, 1.5, 0))
	else:
		var cols := 7
		var flying: PackedStringArray = String(_args.get("flying", "")).split(",", false)
		for i in kinds.size():
			var kind := kinds[i]
			var own := ResourceLoader.exists("res://assets/models/mon_%s.glb" % kind)
			var base := kind if own else String(Monster.STAND_INS.get(kind, ["fallen"])[0])
			var body := Models.make("mon_" + base)
			body.scale = Vector3.ONE * Monster.BODY
			body.position = Vector3((i % cols - (cols - 1) * 0.5) * 3.0, 1.2 if kind in flying else 0.0, (i / cols) * 3.4)
			body.rotation.y = deg_to_rad(155)
			add_child(body)
			var player := Models.player(body)
			var anim := Models.anim_name(player, String(_args.get("anim", "idle")))
			if anim != "":
				player.play(anim)
				player.seek(player.get_animation(anim).length * 0.3, true)
				player.pause()
			if own:
				var rim := Monster.overlay(Monster.RIM[kind])
				for mi in body.find_children("*", "MeshInstance3D", true, false):
					(mi as MeshInstance3D).material_overlay = rim
			else:   # a stand-in: its tint, as the battle shows it, and a red post beside it
				var overlay := Monster.overlay(Color.BLACK)
				overlay.set_shader_parameter("tint", Monster.STAND_INS[kind][1])
				for mi in body.find_children("*", "MeshInstance3D", true, false):
					(mi as MeshInstance3D).material_overlay = overlay
				var post := MeshInstance3D.new()
				var cyl := CylinderMesh.new()
				cyl.top_radius = 0.06
				cyl.bottom_radius = 0.06
				cyl.height = 0.6
				post.mesh = cyl
				post.material_override = Mats.glow(Color(1.0, 0.1, 0.05), 3.0)
				post.position = Vector3(body.position.x + 1.1, 0.3, body.position.z)
				add_child(post)
		var rows := ceili(kinds.size() / float(cols))
		cam.position = Vector3(0, 9.0 + rows * 1.5, rows * 3.4 + 9.0)
		cam.look_at(Vector3(0, 1.0, (rows - 1) * 1.7))
	for side in [-1.0, 1.0]:
		var fire := Fx.fire_light(8.0, 16.0, false)
		fire.position = Vector3(side * 9.0, 2.0, 6.0)
		add_child(fire)


func _process(_delta: float) -> void:
	_frame += 1
	if _frame == SKIP:
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(_args["out"])
		get_tree().quit()
