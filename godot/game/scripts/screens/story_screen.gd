class_name StoryScreen
extends Screen
## A story's pages (stub: being built).


func build() -> void:
	add_child(Ui.backdrop("", 0.0))
	var t := Ui.title("A story's pages")
	t.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	add_child(t)
