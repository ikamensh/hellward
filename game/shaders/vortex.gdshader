shader_type spatial;
// The hell gate's mouth: the painted fire swirl pouring inward without end. Two copies of it shrink toward the
// centre half a cycle apart, each faded in and out by sin(t*PI), so the flow never visibly restarts; a third,
// dimmer, turns against them. The middle is a dark throat with a red heart beating in it. Premultiplied alpha:
// the swirl adds light, and the throat hides what is behind the gate.
render_mode unshaded, blend_premul_alpha, cull_disabled, depth_draw_never, shadows_disabled;

uniform sampler2D swirl : source_color, filter_linear_mipmap, repeat_disable;
uniform float energy = 1.3;
uniform float pour = 0.18;    // inward cycles per second

vec2 turn(vec2 p, float a) {
	float s = sin(a), c = cos(a);
	return vec2(c * p.x - s * p.y, s * p.x + c * p.y);
}

// one copy of the swirl, `phase` of the way through its pour: it starts large and faint, shrinks inward
// turning as it goes, and fades out small
vec3 layer(vec2 p, float r, float phase) {
	float zoom = exp(mix(log(0.6), log(1.7), phase));
	vec2 q = turn(p, -phase * 2.2 - TIME * 0.35 + r * 1.2) * zoom;
	return texture(swirl, q + 0.5).rgb;
}

void fragment() {
	vec2 p = UV - 0.5;
	float r = length(p) * 2.0;
	float t = TIME * pour;
	float p1 = fract(t);
	float p2 = fract(t + 0.5);
	float w1 = sin(p1 * PI);
	float w2 = sin(p2 * PI);
	vec3 flow = (layer(p, r, p1) * w1 + layer(p, r, p2) * w2) / (w1 + w2);
	vec3 back = texture(swirl, turn(p, TIME * 0.5 - r * 2.0) * 0.85 + 0.5).rgb * vec3(1.0, 0.4, 0.25);
	vec3 col = flow + back * 0.35;
	col *= pow(smoothstep(0.06, 0.7, r), 1.4);
	float beat = 0.75 + 0.25 * sin(TIME * 3.0) * sin(TIME * 1.3 + 1.0);
	col += vec3(0.9, 0.06, 0.01) * exp(-r * r * 30.0) * beat * 0.7;
	float disc = smoothstep(1.0, 0.86, r);
	ALBEDO = col * energy * disc;
	ALPHA = disc * mix(0.97, 0.75, smoothstep(0.3, 0.9, r));
}
