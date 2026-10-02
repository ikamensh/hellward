shader_type spatial;
// Holy light (Smite, the shrine): a column of holy light on an open cylinder. Soft at its silhouette, bright down its middle, bands of
// light streaming up it, faded into the ground and away into the sky. `fade` takes it out.
render_mode unshaded, blend_add, cull_disabled, depth_draw_never, shadows_disabled, fog_disabled;

uniform vec3 color : source_color = vec3(1.0, 0.72, 0.32);
uniform float energy = 1.2;
uniform float height = 14.0;
uniform float fade = 1.0;

varying float up;

void vertex() {
	up = VERTEX.y / height + 0.5;   // 0 at the ground, 1 at the top
}

void fragment() {
	float facing = abs(dot(NORMAL, VIEW));        // 1 down the column's middle, 0 at its edges
	float soft = pow(facing, 2.5);
	float core = pow(facing, 14.0);
	float y = up * height;
	// shafts of light running up the column, drifting round it, and bright bands streaming up through them
	float rays = pow(0.5 + 0.5 * sin(UV.x * TAU * 7.0 + y * 0.15 + TIME * 1.5), 3.0)
		+ pow(0.5 + 0.5 * sin(UV.x * TAU * 13.0 - y * 0.25 - TIME * 2.3), 3.0);
	float bands = pow(0.5 + 0.5 * sin(y * 1.6 - TIME * 12.0), 6.0);
	float ends = smoothstep(0.0, 0.05, up) * pow(1.0 - up, 1.2);
	vec3 c = color * soft * (0.15 + 0.6 * rays + 0.5 * bands) + mix(color, vec3(1.0), 0.6) * core * 0.9;
	ALBEDO = c * energy * ends * fade;
}
