class_name ReckoningScreen
extends Screen
## The reckoning (stub: being built).


func build() -> void:
	add_child(Ui.backdrop("", 0.0))
	var t := Ui.title("The reckoning")
	t.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	add_child(t)
