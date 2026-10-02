class_name BattleScreen
extends Screen
## Stands for the battle in the shell's screen stack: it draws nothing and takes no input, so the battle scene gets
## every click and key; the pause menu and the reckoning open over it.


func _init() -> void:
	super()
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_process_input(false)
