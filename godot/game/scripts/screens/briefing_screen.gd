class_name BriefingScreen
extends Screen
## A location's intro (stub: being built).


func build() -> void:
	add_child(Ui.backdrop("", 0.0))
	var t := Ui.title("A location's intro")
	t.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	add_child(t)
