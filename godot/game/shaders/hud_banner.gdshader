shader_type canvas_item;
// A banner's backing: a band of dark drifting smoke behind the words, warmed faintly by the event's colour,
// thinning out towards the screen's edges and above and below.

uniform vec4 tint : source_color = vec4(0.93, 0.76, 0.42, 1.0);
uniform sampler2D noise : repeat_enable, filter_linear;

void fragment() {
	float t = TIME;
	float s1 = texture(noise, vec2(UV.x * 1.4 + t * 0.012, UV.y * 0.5 - t * 0.008)).r;
	float s2 = texture(noise, vec2(UV.x * 3.2 - t * 0.02, UV.y * 1.1 + t * 0.015 + s1 * 0.2)).r;
	float smoke = 0.55 * s1 + 0.45 * s2;
	float across = smoothstep(0.0, 0.34, UV.x) * smoothstep(1.0, 0.66, UV.x);
	float band = exp(-pow((UV.y - 0.5) / 0.27, 2.0));
	float a = across * band * (0.5 + 0.75 * smoke);
	vec3 col = tint.rgb * 0.16 * smoothstep(0.45, 0.8, smoke) * band;
	COLOR = vec4(col, clamp(a * 0.92, 0.0, 0.9));
}
