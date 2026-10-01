shader_type spatial;
// Drawn over a monster or tower: a white flash when hit, a frost rim when chilled, a violet pulse when cursed.
render_mode blend_add, unshaded, depth_draw_never, cull_back;

uniform float flash = 0.0;
uniform float chill = 0.0;
uniform float curse = 0.0;

void fragment() {
	float rim = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 2.5);
	float pulse = 0.6 + 0.4 * sin(TIME * 5.0);
	vec3 c = vec3(1.0, 0.85, 0.75) * flash * 0.9;
	c += vec3(0.25, 0.6, 1.0) * chill * (0.12 + rim * 1.2);
	c += vec3(0.6, 0.15, 1.0) * curse * (0.08 + rim * 1.6) * pulse;
	ALBEDO = c;
}
