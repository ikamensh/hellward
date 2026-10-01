shader_type canvas_item;
// Darkened corners over the 3D scene, under the HUD.

void fragment() {
	vec2 d = (UV - 0.5) * vec2(1.5, 1.0);
	COLOR = vec4(0.0, 0.0, 0.01, smoothstep(0.35, 0.95, length(d)) * 0.75);
}
