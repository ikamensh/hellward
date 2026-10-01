shader_type spatial;
// A leader's chant: a violet beam from its staff to the tower it curses, on a one-unit open cylinder stretched
// between them. Knots of power travel along it to the tower, a thread twists round it, its halo is soft, and it
// fades in at both ends.
render_mode unshaded, blend_add, cull_disabled, depth_draw_never, shadows_disabled, fog_disabled;

uniform vec3 color : source_color = vec3(0.7, 0.25, 1.0);
uniform float energy = 1.4;
uniform float span = 6.0;     // metres from staff to tower, so knots and twists keep their size

varying float along;
varying float around;

void vertex() {
	along = VERTEX.y + 0.5;                   // 0 at the staff, 1 at the tower
	around = atan(VERTEX.z, VERTEX.x) / TAU;
}

void fragment() {
	float facing = abs(dot(NORMAL, VIEW));
	float halo = pow(facing, 1.5) * 0.3;
	float core = pow(facing, 9.0);
	float m = along * span;
	float knots = pow(0.5 + 0.5 * sin((m - TIME * 6.0) * 1.6), 12.0);
	float twist = fract(around * 2.0 + m * 0.7 - TIME * 2.5);
	float thread = 1.0 - smoothstep(0.0, 0.07, abs(twist - 0.5));
	float ends = smoothstep(0.0, 0.08, along) * smoothstep(1.0, 0.92, along);
	vec3 hot = mix(color, vec3(1.0, 0.85, 1.0), 0.35);
	vec3 c = color * halo + hot * core * (0.7 + knots * 1.6) + color * knots * 0.9 * facing + hot * thread * 0.7;
	ALBEDO = c * energy * ends;
}
