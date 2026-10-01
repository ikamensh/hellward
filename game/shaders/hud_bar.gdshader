shader_type canvas_item;
// A gauge: a dark sunken well filled to `fill` with `color`, glossy on top, its leading edge bright, slowly
// shimmering, in a thin gold rim. Drawn in pixels (`size`).

uniform vec4 color : source_color = vec4(0.8, 0.1, 0.06, 1.0);
uniform float fill : hint_range(0.0, 1.0) = 1.0;
uniform vec2 size = vec2(400.0, 14.0);

void fragment() {
	vec2 px = UV * size;
	float border = min(min(px.x, size.x - px.x), min(px.y, size.y - px.y));
	vec3 well = vec3(0.02, 0.018, 0.02) + vec3(0.05) * UV.y;
	float gloss = 1.0 + 0.55 * smoothstep(0.55, 0.0, UV.y) - 0.45 * smoothstep(0.45, 1.0, UV.y);
	float shimmer = 0.88 + 0.12 * sin(px.x * 0.06 - TIME * 2.5);
	vec3 bar = color.rgb * gloss * shimmer;
	float head = fill * size.x;
	vec3 col = px.x < head ? bar : well;
	col += mix(color.rgb, vec3(1.0), 0.4) * smoothstep(4.0, 0.0, head - px.x) * step(px.x, head) * step(0.002, fill) * 0.8;
	col = mix(col, vec3(0.7, 0.53, 0.27) * (0.65 + 0.6 * (1.0 - UV.y)), step(border, 2.0));
	col = mix(col, vec3(0.0), step(border, 1.0));
	COLOR = vec4(col, 1.0);
}
