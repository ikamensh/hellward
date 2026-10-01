shader_type spatial;
// Dry grass: blades darker at the root, swaying in a slow wind that rolls across the field.
// COLOR is the tuft's colour (MultiMesh instance colour); UV.y runs from the tip (0) to the root (1).
render_mode cull_disabled;

varying float tipness;

void vertex() {
	tipness = 1.0 - UV.y;
	vec3 world = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	float gust = sin(world.x * 0.15 + TIME * 1.3) * 0.5 + 0.5;
	float sway = sin(TIME * 2.4 + world.x * 0.7 + world.z * 0.5) * (0.06 + 0.1 * gust);
	VERTEX.x += sway * tipness * tipness;
	VERTEX.z += sway * 0.5 * tipness * tipness;
}

void fragment() {
	vec3 base = COLOR.rgb;
	ALBEDO = mix(base * 0.35, base * 1.1, tipness);
	ROUGHNESS = 0.9;
	SPECULAR = 0.2;
	BACKLIGHT = vec3(0.12, 0.1, 0.04);
}
