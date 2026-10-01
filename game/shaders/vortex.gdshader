shader_type spatial;
// The hell gate's mouth: two layers of the painted fire swirl turning against each other, drawn inward.
render_mode unshaded, blend_add, cull_disabled, depth_draw_never, shadows_disabled;

uniform sampler2D swirl : source_color, filter_linear_mipmap;
uniform float energy = 3.0;

vec2 turn(vec2 uv, float a, float zoom) {
	vec2 p = (uv - 0.5) * zoom;
	float s = sin(a), c = cos(a);
	return vec2(c * p.x - s * p.y, s * p.x + c * p.y) + 0.5;
}

void fragment() {
	vec2 p = UV - 0.5;
	float r = length(p) * 2.0;
	float pull = 0.85 + 0.15 * fract(TIME * 0.25);
	vec3 a = texture(swirl, turn(UV, TIME * 0.9 + r * 1.5, 1.0)).rgb;
	vec3 b = texture(swirl, turn(UV, -TIME * 0.5 - r * 2.0, 0.8 * pull)).rgb;
	vec3 col = a * 0.8 + b * 0.55;
	col *= smoothstep(1.0, 0.85, r);
	col += vec3(0.6, 0.05, 0.0) * smoothstep(0.35, 0.0, r) * (0.7 + 0.3 * sin(TIME * 3.0));
	ALBEDO = col * energy;
}
