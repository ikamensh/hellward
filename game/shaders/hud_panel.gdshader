shader_type canvas_item;
// The bottom bar, and the chosen tower's card: hammered black iron in a bevelled gold trim (violet as `curse`
// rises), its top corners cut, rivets along engraved lines inside the trim (`engraved`). Drawn in pixels
// (`size`) so the trim stays crisp whatever the size.

uniform vec2 size = vec2(1240.0, 112.0);
uniform float chamfer = 22.0;
uniform float trim = 6.0;
uniform float spacing = 90.0;
uniform float rivet_from = 0.0;
uniform bool engraved = true;
uniform float curse : hint_range(0.0, 1.0) = 0.0;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0)), f.x), f.y);
}

float fbm(vec2 p) {
	float v = 0.0;
	float a = 0.5;
	for (int i = 0; i < 5; i++) {
		v += a * vnoise(p);
		p = p * 2.03 + vec2(17.1, 9.2);
		a *= 0.5;
	}
	return v;
}

// how far inside the bar's outline a pixel is
float inset(vec2 px) {
	float d = min(min(px.x, size.x - px.x), min(px.y, size.y - px.y));
	float c1 = (px.x + px.y - chamfer) * 0.7071;
	float c2 = (size.x - px.x + px.y - chamfer) * 0.7071;
	return min(d, min(c1, c2));
}

vec3 gold(vec2 px, float lit) {
	float wear = fbm(px * 0.09);
	vec3 g = mix(vec3(0.42, 0.28, 0.12), vec3(0.86, 0.66, 0.34), clamp(lit, 0.0, 1.2));
	g = mix(g, mix(vec3(0.28, 0.1, 0.48), vec3(0.82, 0.56, 1.0), clamp(lit, 0.0, 1.2)), curse);
	g = mix(g, g * 0.55, smoothstep(0.55, 0.8, wear));
	return g + vec3(1.0, 0.85, 0.55) * pow(clamp(lit, 0.0, 1.0), 6.0) * 0.35;
}

void fragment() {
	vec2 px = UV * size;
	float d = inset(px);
	vec2 e = vec2(1.0, 0.0);
	vec2 inward = normalize(vec2(inset(px + e.xy) - inset(px - e.xy), inset(px + e.yx) - inset(px - e.yx)) + 1e-4);
	vec2 light = normalize(vec2(-0.35, -1.0));   // from above, a little left

	// hammered iron, lit by the dents' slopes, a little brighter towards the top
	float h0 = fbm(px * 0.06);
	float hx = fbm((px + e.xy) * 0.06) - h0;
	float hy = fbm((px + e.yx) * 0.06) - h0;
	float dent = clamp(0.5 - 9.0 * dot(vec2(hx, hy), light), 0.0, 1.0);
	vec3 col = mix(vec3(0.035, 0.032, 0.036), vec3(0.13, 0.12, 0.12), 0.35 * fbm(px * 0.012) + 0.45 * dent);
	col *= 1.12 - 0.42 * (px.y / size.y);
	col = mix(col, col * 0.55, smoothstep(0.55, 0.85, fbm(px * 0.025 + 40.0)));   // soot

	// engraved lines just inside the trim, top and bottom: a dark groove with its lower lip catching the light
	float line_y = trim + 5.5;
	float gl = min(abs(px.y - line_y), abs(px.y - (size.y - line_y)));
	float along = step(chamfer + trim, px.x) * step(px.x, size.x - chamfer - trim) * (engraved ? 1.0 : 0.0);
	col = mix(col, vec3(0.01), smoothstep(1.2, 0.2, gl) * along * 0.8);
	col += vec3(0.6, 0.45, 0.25) * 0.12 * smoothstep(1.5, 0.5, abs(px.y - line_y - 1.5)) * along;

	// the bevelled gold trim: outer half faces out, inner half faces in
	if (d < trim) {
		float t = d / trim;
		vec2 facing = t < 0.5 ? -inward : inward;
		float lit = 0.62 + 0.55 * dot(facing, -light) * (1.0 - abs(t - 0.5) * 1.2);
		col = gold(px, lit);
	}
	col = mix(col, vec3(0.0), smoothstep(trim + 2.5, trim, d) * step(trim, d) * 0.85);   // the groove below the trim

	// rivets on the engraved lines, `spacing` apart from `rivet_from`: the gaps between the slots
	float cell = mod(px.x - rivet_from + spacing * 0.5, spacing) - spacing * 0.5;
	for (int row = 0; row < 2; row++) {
		vec2 q = vec2(cell, px.y - (row == 0 ? line_y : size.y - line_y));
		float rr = length(q);
		if (along > 0.5 && rr < 3.6) {
			vec3 rn = normalize(vec3(q / 3.6, sqrt(max(0.0, 1.0 - rr * rr / 12.96))));
			float shine = max(0.0, dot(rn, normalize(vec3(-0.35, -1.0, 0.8))));
			col = mix(vec3(0.06, 0.05, 0.04), vec3(0.7, 0.55, 0.32), shine * shine) + pow(shine, 24.0) * 0.6;
		} else if (along > 0.5 && rr < 5.0) {
			col *= 0.4;
		}
	}

	float alpha = smoothstep(-0.5, 0.8, d);
	COLOR = vec4(col, alpha);
}
