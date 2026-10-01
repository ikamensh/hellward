class_name SettingsScreen
extends Screen
## Settings (stub: being built).


func build() -> void:
	add_child(Ui.backdrop("", 0.0))
	var t := Ui.title("Settings")
	t.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	add_child(t)
