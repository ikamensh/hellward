shader_type canvas_item;
// A Diablo orb: a glass sphere filled to `level` with a churning liquid, deep and dark towards the glass, two
// layers of swirl turning at different speeds, small bubbles rising. The sculpted frame drawn over it hides the
// rim, so the sphere fills the whole rect.

uniform vec4 liquid : source_color = vec4(0.75, 0.06, 0.04, 1.0);
uniform vec4 glow : source_color = vec4(1.0, 0.4, 0.2, 1.0);     // the lit core, the streaks and the meniscus
uniform float level : hint_range(0.0, 1.0) = 1.0;
uniform sampler2D noise : repeat_enable, filter_linear;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

// bubbles rising through the liquid: at most one per cell of a grid that drifts upward, each wobbling as it goes
float bubbles(vec2 p, float scale, float speed, float t) {
	vec2 q = p * scale + vec2(0.0, t * speed);
	vec2 cell = floor(q);
	vec2 f = fract(q);
	float h = hash(cell);
	if (h < 0.55) {
		return 0.0;
	}
	vec2 centre = vec2(0.25 + 0.5 * hash(cell + 7.3) + 0.08 * sin(t * 2.0 + h * 40.0), 0.5);
	float r = 0.08 + 0.08 * hash(cell + 3.1);
	float d = length(f - centre);
	float ring = smoothstep(r, r - 0.035, d) * smoothstep(r - 0.08, r - 0.035, d);
	float glint = smoothstep(r * 0.5, 0.0, length(f - centre + vec2(r * 0.35, r * 0.35)));
	return ring * 0.8 + glint;
}

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	float z = sqrt(max(0.0, 1.0 - min(r, 1.0) * min(r, 1.0)));
	vec3 n = normalize(vec3(p.x, -p.y, z + 0.001));
	float t = TIME;

	// the liquid: two swirls, the second larger, slower and turning the other way, warped by the first
	vec2 warp = 0.12 * vec2(sin(t * 0.31 + p.y * 2.0), cos(t * 0.27 + p.x * 2.0));
	float s1 = texture(noise, p * 0.42 + vec2(t * 0.022, -t * 0.034) + warp).r;
	mat2 turn = mat2(vec2(cos(t * 0.05), sin(t * 0.05)), vec2(-sin(t * 0.05), cos(t * 0.05)));
	float s2 = texture(noise, turn * p * 0.22 + vec2(0.5 - t * 0.006, 0.3 + t * 0.011) + s1 * 0.18).r;
	float depth = 0.12 + 0.95 * pow(z, 1.6);                    // dark towards the glass
	vec3 inside = liquid.rgb * depth * (0.55 + 0.75 * s1);
	inside += glow.rgb * smoothstep(0.52, 0.78, s2) * 0.45 * depth;       // bright streaks of the slow swirl
	inside += glow.rgb * 0.35 * pow(max(0.0, 1.0 - length(p - vec2(0.0, 0.25)) * 1.25), 2.0);  // the lit core
	inside = mix(inside, inside * 0.35, smoothstep(0.55, 1.0, r));      // the deep, shadowed rim

	float surface = 1.0 - 2.0 * level + 0.025 * sin(p.x * 9.0 + t * 2.2) + 0.015 * sin(p.x * 17.0 - t * 3.1);
	float below = p.y - surface;                                          // > 0 inside the liquid
	float bub = bubbles(p, 7.0, 0.55, t) + 0.7 * bubbles(p + 0.37, 12.0, 0.8, t);
	inside += mix(glow.rgb, vec3(1.0), 0.4) * bub * 0.75 * depth * smoothstep(0.0, 0.08, below);
	inside += glow.rgb * smoothstep(0.035, 0.0, abs(below)) * 1.3;        // the meniscus
	inside += glow.rgb * 0.25 * smoothstep(0.25, 0.0, below) * step(0.0, below);   // the surface seen from below

	// the empty glass above it: smoky dark, faintly lit by the liquid
	float haze = texture(noise, p * 0.6 + vec2(t * 0.01, t * 0.02)).r;
	vec3 empty = vec3(0.018, 0.016, 0.022) * (0.6 + z) + liquid.rgb * 0.05 * haze;
	empty += liquid.rgb * 0.18 * smoothstep(-0.35, 0.0, below);
	vec3 col = below > 0.0 ? inside : empty;

	// the glass: a soft broad highlight upper left, a sharp one inside it, a cool rim, light caught below
	vec3 l = normalize(vec3(-0.5, 0.6, 0.65));
	col += pow(max(0.0, dot(n, l)), 18.0) * 0.32;
	col += pow(max(0.0, dot(n, l)), 120.0) * 0.9;
	float fres = pow(1.0 - z, 3.0);
	col += vec3(0.5, 0.55, 0.65) * fres * 0.18;
	col += glow.rgb * 0.25 * smoothstep(0.75, 0.95, r) * smoothstep(0.2, 0.7, p.y) * step(0.0, below);
	COLOR = vec4(col, smoothstep(1.0, 0.985, r));
}
