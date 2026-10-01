class_name PrologueScreen
extends Screen
## The prologue (stub: being built).


func build() -> void:
	add_child(Ui.backdrop("", 0.0))
	var t := Ui.title("The prologue")
	t.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	add_child(t)
