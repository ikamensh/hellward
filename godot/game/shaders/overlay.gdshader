shader_type spatial;
// Drawn over a monster or tower: a warm rim when hit, a frost rim when chilled, a violet pulse when cursed, and
// far from the camera a rim in the monster's own colour so the kinds tell apart from overhead. With `xray`, the
// parts of a monster hidden behind a tower or a house show as a faint outline in that colour.
render_mode blend_add, unshaded, fog_disabled, depth_draw_never, depth_test_disabled, cull_back;

uniform float flash = 0.0;
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
	bool hidden = -VERTEX.z > -seen.z / seen.w + 0.8;
	if (hidden) {
		ALBEDO = kind_rim * (0.15 + pow(edge, 2.0) * 0.6) * 0.5 * xray;
	} else {
		float rim = pow(edge, 2.5);
		float pulse = 0.6 + 0.4 * sin(TIME * 5.0);
		vec3 c = vec3(1.0, 0.55, 0.35) * flash * (0.15 + rim * 1.4);
		c += vec3(0.25, 0.6, 1.0) * chill * (0.12 + rim * 1.2);
		c += vec3(0.6, 0.15, 1.0) * curse * (0.08 + rim * 1.6) * pulse;
		float far = smoothstep(14.0, 34.0, length(VERTEX));
		c += kind_rim * pow(edge, 4.5) * 0.6 * far;
		float up = clamp((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).y * 0.6 + 0.4, 0.0, 1.0);
		c += vec3(0.32, 0.45, 0.75) * moonrim * rim * up;
		c += tint * (0.12 + rim * 0.5);
		ALBEDO = c;
	}
}
