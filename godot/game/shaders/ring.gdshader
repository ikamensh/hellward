shader_type spatial;
// A flat marker on the ground: a tower's reach as a ring (`radius`, metres) or a tile's square outline.
render_mode unshaded, fog_disabled, cull_disabled, depth_draw_never, shadows_disabled;

uniform vec4 color : source_color = vec4(1.0, 0.8, 0.4, 1.0);
uniform float radius = 5.0;
uniform bool square = false;

varying vec2 local;

void vertex() {
	local = VERTEX.xz;
}

void fragment() {
	float pulse = 0.93 + 0.07 * sin(TIME * 2.5);
	float a;
	if (square) {
		vec2 d = abs(local);
		float e = max(d.x, d.y);
		float edge = smoothstep(0.78, 0.85, e) * (1.0 - smoothstep(0.995, 1.0, e));
		a = edge * 0.95 + 0.22 * (1.0 - smoothstep(0.9, 1.0, e));
	} else {
		float r = length(local);
		a = smoothstep(radius - 0.12, radius - 0.03, r) * smoothstep(radius + 0.06, radius - 0.02, r);
		a += 0.07 * step(r, radius);
		a *= 0.75 + 0.25 * sin(atan(local.y, local.x) * 24.0 + TIME * 2.0);
	}
	ALBEDO = color.rgb * 1.6;
	ALPHA = a * color.a * pulse;
}
