shader_type spatial;
// The village floor: cobbled streets where monsters walk, trampled mud and dry grass around them, scorch
// near fires, flagstones before the cathedral, and glowing hell-cracks round the portal. `mask` covers the
// battlefield and its approaches: r = street, g = mud, b = scorch, a = flagstones. Outside it, grass.

uniform sampler2D mask : filter_linear, repeat_disable;
uniform vec4 mask_rect;           // x, z of the mask's corner and its width, depth in metres
uniform sampler2D noise : filter_linear, repeat_enable;

uniform sampler2D cob_a : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D cob_n : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D cob_h : filter_linear_mipmap, repeat_enable;
uniform sampler2D earth_a : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D earth_n : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grass_a : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grass_n : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D flag_a : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D flag_n : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec2 portal_xz;

uniform float cob_scale = 1.4;     // metres per repeat
uniform float earth_scale = 5.0;
uniform float grass_scale = 4.0;

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

// sample a tiling texture twice, at two rotations, mixed by noise, so its repeat does not show
vec4 untiled(sampler2D t, vec2 uv, float n) {
	vec2 uv2 = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8)) * uv * 0.87 + vec2(0.37, 0.71);
	return mix(texture(t, uv), texture(t, uv2), smoothstep(0.35, 0.65, n));
}

void fragment() {
	vec2 p = wpos.xz;
	float n = texture(noise, p * 0.035).r;
	float n2 = texture(noise, p * 0.11 + 0.5).r;
	vec2 muv = (p - mask_rect.xy) / mask_rect.zw;
	vec4 m = vec4(0.0);
	if (muv.x >= 0.0 && muv.x <= 1.0 && muv.y >= 0.0 && muv.y <= 1.0) {
		m = texture(mask, muv);
	}
	// the hell gate tears up the road and cracks the ground around it
	float dp = distance(p, portal_xz) + (n - 0.5) * 5.0;
	float hell = 1.0 - smoothstep(4.0, 12.0, dp);
	vec2 cuv = p / cob_scale;
	float ch = texture(cob_h, cuv).r;
	// stones poke out at the street's edge: the height decides which side of the boundary each pixel takes
	float lane = smoothstep(0.42, 0.58, m.r + (ch - 0.5) * 0.55 + (n2 - 0.5) * 0.25) * smoothstep(5.0, 9.0, dp);
	float earth = clamp(m.g + (n - 0.45) * 1.2, 0.0, 1.0);
	earth = max(earth, smoothstep(0.0, 0.25, m.r) * 0.85);
	earth = max(earth, hell);
	float flag = smoothstep(0.35, 0.65, m.a + (n2 - 0.5) * 0.5);

	vec3 ga = untiled(grass_a, p / grass_scale, n).rgb;
	vec3 gn = untiled(grass_n, p / grass_scale, n).rgb;
	vec3 ea = untiled(earth_a, p / earth_scale, n2).rgb;
	vec3 en = untiled(earth_n, p / earth_scale, n2).rgb;
	// far away the setts blur into an even grey-brown instead of shimmering noise
	float far = smoothstep(18.0, 60.0, length(VERTEX));
	vec3 ca = mix(texture(cob_a, cuv).rgb, textureLod(cob_a, cuv, 8.0).rgb, far * 0.6);
	vec3 cn = mix(texture(cob_n, cuv).rgb, vec3(0.5, 0.5, 1.0), far * 0.5);
	vec3 fa = texture(flag_a, p / 3.0).rgb;
	vec3 fn = texture(flag_n, p / 3.0).rgb;

	// worn streets: patches where the setts are gone, and puddles in the ruts and the mud that catch the fire
	float n3 = texture(noise, p * 0.06 + 3.1).r;
	float n4 = texture(noise, p * 0.09 + 7.7).r;
	float worn = smoothstep(0.82, 0.88, n3 + (0.5 - ch) * 0.15) * lane;
	float wet = clamp(lane * 0.3 + m.g * (1.0 - lane) * 0.9, 0.0, 1.0) * (1.0 - flag) * (1.0 - hell);
	float puddle = smoothstep(0.7, 0.74, n4 + (0.5 - ch) * 0.12 * lane) * wet * (1.0 - worn * 0.5);
	vec3 col = mix(ga, ea, earth);
	vec3 nrm = mix(gn, en, earth);
	col = mix(col, ca * vec3(0.62, 0.58, 0.54), lane);
	nrm = mix(nrm, cn, lane);
	col = mix(col, ea * 0.5, worn);
	nrm = mix(nrm, en, worn);
	col = mix(col, fa * vec3(0.85, 0.82, 0.78), flag);
	nrm = mix(nrm, fn, flag);
	col = mix(col, col * 0.3, puddle);
	float scorch = clamp(m.b + (n2 - 0.5) * 0.6, 0.0, 1.0);
	col *= mix(1.0, 0.25, scorch);
	col = mix(col, col * 0.2, hell);
	col *= 0.85 + 0.3 * n;   // large, soft variation in brightness
	ALBEDO = col;
	nrm = mix(nrm, vec3(0.5, 0.5, 1.0), puddle);
	NORMAL_MAP = nrm;
	ROUGHNESS = mix(mix(mix(0.92, mix(0.58, 0.82, ch), lane), 0.7, flag), 0.3, puddle);
	SPECULAR = mix(0.35, 0.08, puddle);   // dark wet mud, not a mirror of the sky
	// meandering cracks that glow and pulse outward from the gate; ember beds under the burning houses
	float n5 = texture(noise, p * 0.32 + 9.1).r;
	float n6 = texture(noise, p * 0.13 + 4.3).r;   // a lower frequency: few, long cracks
	float fissure = (1.0 - smoothstep(0.0, 0.022, abs(n6 - 0.5))) * hell;
	EMISSION = vec3(1.0, 0.2, 0.03) * fissure * (2.0 + 1.2 * sin(TIME * 1.6 - dp * 0.7));
	EMISSION += vec3(1.0, 0.32, 0.06) * smoothstep(0.85, 0.98, m.b) * pow(n5, 8.0) * 4.0;
}
