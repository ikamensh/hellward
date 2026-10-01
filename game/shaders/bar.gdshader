shader_type spatial;
// A monster's life over its head, always facing the camera and drawn over the scene.
render_mode unshaded, depth_test_disabled, cull_disabled, shadows_disabled;

instance uniform float fill = 1.0;

void vertex() {
	// near-constant size on screen: the bar grows with the camera's distance, from 24 m out
	float d = length(INV_VIEW_MATRIX[3].xyz - MODEL_MATRIX[3].xyz);
	VERTEX *= clamp(d / 24.0, 1.0, 3.0);
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
}

void fragment() {
	vec2 uv = UV;
	float border = step(uv.x, 0.03) + step(0.97, uv.x) + step(uv.y, 0.12) + step(0.88, uv.y);
	vec3 life = mix(vec3(0.9, 0.08, 0.05), vec3(0.95, 0.75, 0.15), smoothstep(0.6, 1.0, fill)) * (0.8 + 0.4 * (1.0 - uv.y));
	vec3 c = uv.x < fill ? life : vec3(0.08, 0.02, 0.02);
	ALBEDO = border > 0.0 ? vec3(0.02) : c;
	ALPHA = 0.92;
}
