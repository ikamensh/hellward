class_name ErrorScreen
extends Screen
## The server stopped or said something this client cannot follow: say so plainly, and the way out.


func build() -> void:
	add_child(Ui.backdrop("", 0.0))
	var col := VBoxContainer.new()
	col.set_anchors_preset(Control.PRESET_CENTER)
	col.alignment = BoxContainer.ALIGNMENT_CENTER
	col.add_theme_constant_override("separation", 24)
	col.position = Vector2(Ui.W / 2 - 600, Ui.H / 2 - 220)
	col.custom_minimum_size = Vector2(1200, 440)
	add_child(col)
	col.add_child(Ui.title("The game's rules stopped", 56, Style.BLOOD))
	col.add_child(Ui.paragraph(String(data.get("why", "")), 20, Style.BONE, 1200, HORIZONTAL_ALIGNMENT_CENTER))
	var leave := Ui.button("Leave the game", "Esc", 320)
	leave.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	leave.pressed.connect(game.leave)
	col.add_child(leave)
