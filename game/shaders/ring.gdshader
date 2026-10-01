shader_type spatial;
// A flat marker on the ground: a tower's reach as a ring (`radius`, metres) or a tile's square outline.
render_mode unshaded, cull_disabled, depth_draw_never, shadows_disabled;

uniform vec4 color : source_color = vec4(1.0, 0.8, 0.4, 1.0);
uniform float radius = 5.0;
uniform bool square = false;

varying vec2 local;

void vertex() {
	local = VERTEX.xz;
}

void fragment() {
	float a;
	if (square) {
		vec2 d = abs(local);
		float e = max(d.x, d.y);
		a = smoothstep(0.82, 0.95, e) * step(e, 1.0) * 0.9 + 0.12;
	} else {
		float r = length(local);
		a = smoothstep(radius - 0.12, radius - 0.03, r) * smoothstep(radius + 0.06, radius - 0.02, r);
		a += 0.07 * step(r, radius);
		a *= 0.75 + 0.25 * sin(atan(local.y, local.x) * 24.0 + TIME * 2.0);
	}
	ALBEDO = color.rgb * 1.6;
	ALPHA = a * color.a;
}
