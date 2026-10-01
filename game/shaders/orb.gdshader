shader_type canvas_item;
// A Diablo orb: a glass sphere in a gold ring, filled to `level` with a slowly swirling liquid.

uniform vec4 liquid : source_color = vec4(0.75, 0.06, 0.04, 1.0);
uniform float level : hint_range(0.0, 1.0) = 1.0;
uniform sampler2D noise : repeat_enable, filter_linear;

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	float z = sqrt(max(0.0, 1.0 - min(r / 0.88, 1.0) * min(r / 0.88, 1.0)));
	float surface = 1.0 - 2.0 * level + 0.025 * sin(p.x * 9.0 + TIME * 2.2) + 0.015 * sin(p.x * 17.0 - TIME * 3.1);
	float swirl = texture(noise, vec2(p.x * 0.4 + TIME * 0.02, p.y * 0.4 - TIME * 0.035) + 0.15 * vec2(sin(TIME * 0.3), cos(TIME * 0.27))).r;
	vec3 inside = liquid.rgb * (0.35 + 0.9 * z) * (0.75 + 0.6 * swirl);
	inside += liquid.rgb * smoothstep(0.03, 0.0, abs(p.y - surface)) * 1.2;   // the bright meniscus
	vec3 empty = vec3(0.025, 0.02, 0.025) * (0.5 + z);
	vec3 col = p.y > surface ? inside : empty;
	vec3 n = vec3(p.x, -p.y, z);
	col += pow(max(0.0, dot(normalize(n), normalize(vec3(-0.45, 0.55, 0.7)))), 40.0) * 0.9 * step(r, 0.88);
	col += vec3(0.08) * smoothstep(0.5, 0.88, r) * step(r, 0.88);
	// the gold ring
	float ring = smoothstep(0.86, 0.89, r) * smoothstep(1.0, 0.97, r);
	float shade = 0.55 + 0.45 * dot(normalize(vec2(p.x, -p.y) + 0.001), normalize(vec2(-0.5, 0.7)));
	col = mix(col, vec3(0.78, 0.6, 0.3) * (0.4 + 0.8 * shade), ring);
	COLOR = vec4(col, smoothstep(1.0, 0.975, r));
}
