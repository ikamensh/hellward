shader_type spatial;
// Drawn over a monster or tower: a warm rim when hit, a frost rim when chilled, a violet pulse when cursed, and
// far from the camera a rim in the monster's own colour so the kinds tell apart from overhead. With `xray`, the
// parts of a monster hidden behind a tower or a house show as a faint outline in that colour; parts hidden only by
// the body's own folds draw nothing.
render_mode blend_add, unshaded, fog_disabled, depth_draw_never, depth_test_disabled, cull_back;

uniform float flash = 0.0;
uniform vec3 flash_color = vec3(1.0, 0.55, 0.35);   // the blow's colour: warm for steel, its element's otherwise
uniform float chill = 0.0;
uniform float curse = 0.0;
uniform vec3 kind_rim = vec3(0.0);
uniform float xray = 0.0;
uniform float moonrim = 0.0;   // a cool rim from above at every distance, so dark bodies keep their shape
uniform vec3 tint = vec3(0.0);   // a stand-in's colour wash, while its kind borrows another's model
uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;

void fragment() {
	float edge = 1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	vec4 seen = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, texture(depth_tex, SCREEN_UV).r, 1.0);
	float behind = -VERTEX.z + seen.z / seen.w;   // how far behind what the camera sees here
	// hidden by less than a body's depth (its own other arm, its weapon, its cloth): nothing; deeper than that it is
	// behind a tower or a house, and shows through as the x-ray
	if (behind > 0.03 && behind <= 1.5) {
		discard;
	}
	if (behind > 1.5) {
		ALBEDO = kind_rim * (0.15 + pow(edge, 2.0) * 0.6) * 0.5 * xray;
	} else {
		float rim = pow(edge, 2.5);
		float pulse = 0.6 + 0.4 * sin(TIME * 5.0);
		vec3 c = flash_color * flash * (0.15 + rim * 1.4);
		c += vec3(0.25, 0.6, 1.0) * chill * (0.12 + rim * 1.2);
		c += vec3(0.6, 0.15, 1.0) * curse * (0.08 + rim * 1.6) * pulse;
		float far = smoothstep(14.0, 34.0, length(VERTEX));
		c += kind_rim * pow(edge, 5.0) * 0.3 * far;   // a hint of the kind, not a neon outline on detailed bodies
		float up = clamp((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).y * 0.6 + 0.4, 0.0, 1.0);
		c += vec3(0.32, 0.45, 0.75) * moonrim * rim * up;
		c += tint * (0.12 + rim * 0.5);
		ALBEDO = c;
	}
}
