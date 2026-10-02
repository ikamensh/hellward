shader_type spatial;
// Drawn over a monster or tower: a rim in the blow's colour when hit, a frost rim when chilled, a violet pulse when
// cursed, a quick gold pulse under Battle Hymn, a cool moon rim so dark bodies keep their shape (kinds tell apart by their glowing eyes). With `xray`, the
// parts of a monster hidden behind a tower or a house show as a faint outline in that colour; parts hidden only by
// the body's own folds draw nothing.
render_mode blend_add, unshaded, fog_disabled, depth_draw_never, depth_test_disabled, cull_back;

uniform float flash = 0.0;
uniform vec3 flash_color = vec3(1.0, 0.55, 0.35);   // the blow's colour: warm for steel, its element's otherwise
uniform float chill = 0.0;
uniform float curse = 0.0;
uniform float hymn = 0.0;
uniform vec3 kind_rim = vec3(0.0);
uniform float xray = 0.0;
uniform float moonrim = 0.0;   // a cool rim from above at every distance, so dark bodies keep their shape
uniform float kindglow = 0.0;  // a faint rim in the kind's own colour, at range: a red hide stays red under the moon
uniform vec3 tint = vec3(0.0);   // a stand-in's colour wash, while its kind borrows another's model
uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;

void fragment() {
	float edge = 1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	// how far behind what the camera sees here: the fragment's own depth and the depth buffer's, both taken back to
	// view space the same way (VERTEX against the buffer drifted with distance, a metre and more at 20 m)
	vec4 seen = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, texture(depth_tex, SCREEN_UV).r, 1.0);
	vec4 here = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, FRAGCOORD.z, 1.0);
	float behind = seen.z / seen.w - here.z / here.w;
	// hidden by less than a body's depth (its own other arm, its weapon, its cloth): nothing; deeper than that it is
	// behind a tower or a house, and shows through as the x-ray
	// the depth texture's error grows with distance (1.7 m at 48 m was measured), so the bar does too
	float body = 1.5 + 0.05 * length(VERTEX);
	if (behind > 0.03 && behind <= body) {
		discard;
	}
	if (behind > body) {
		ALBEDO = kind_rim * (0.15 + pow(edge, 2.0) * 0.6) * 0.5 * xray;
	} else {
		float rim = pow(edge, 2.5);
		float pulse = 0.6 + 0.4 * sin(TIME * 5.0);
		vec3 c = flash_color * flash * (0.15 + rim * 1.4);
		c += vec3(0.25, 0.6, 1.0) * chill * (0.12 + rim * 1.2);
		c += vec3(0.6, 0.15, 1.0) * curse * (0.08 + rim * 1.6) * pulse;
		c += vec3(1.0, 0.72, 0.25) * hymn * (0.06 + rim * 1.4) * (0.7 + 0.3 * sin(TIME * 10.0));
		float up = clamp((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).y * 0.6 + 0.4, 0.0, 1.0);
		c += vec3(0.32, 0.45, 0.75) * moonrim * rim * up;
		// from the battle camera only: close up the body's own light and maps carry its colour
		c += kind_rim * kindglow * rim * (0.6 + 0.4 * up) * smoothstep(5.0, 16.0, length(VERTEX));
		c += tint * (0.12 + rim * 0.5);
		ALBEDO = c;
	}
}
