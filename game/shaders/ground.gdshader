shader_type spatial;
// The village floor: cobbled lanes where monsters walk, trampled earth and dry grass around them, scorch
// near fires. `mask` covers the battlefield rect: r = lane, g = bare earth, b = scorch. Outside it, grass.

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

uniform float cob_scale = 2.2;     // metres per repeat
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
	vec2 cuv = p / cob_scale;
	float ch = texture(cob_h, cuv).r;
	// stones poke out at the lane's edge: the height decides which side of the boundary each pixel takes
	float lane = smoothstep(0.42, 0.58, m.r + (ch - 0.5) * 0.55 + (n2 - 0.5) * 0.25);
	float earth = clamp(m.g + (n - 0.45) * 1.2, 0.0, 1.0);
	earth = max(earth, smoothstep(0.0, 0.25, m.r) * 0.85);

	vec3 ga = untiled(grass_a, p / grass_scale, n).rgb;
	vec3 gn = untiled(grass_n, p / grass_scale, n).rgb;
	vec3 ea = untiled(earth_a, p / earth_scale, n2).rgb;
	vec3 en = untiled(earth_n, p / earth_scale, n2).rgb;
	// far away the setts blur into an even grey-brown instead of shimmering noise
	float far = smoothstep(18.0, 60.0, length(VERTEX));
	vec3 ca = mix(texture(cob_a, cuv).rgb, textureLod(cob_a, cuv, 8.0).rgb, far * 0.6);
	vec3 cn = mix(texture(cob_n, cuv).rgb, vec3(0.5, 0.5, 1.0), far * 0.5);

	// worn lanes: patches where the setts are gone and the mud shows, and puddles that catch the fire
	float n3 = texture(noise, p * 0.06 + 3.1).r;
	float n4 = texture(noise, p * 0.09 + 7.7).r;
	float worn = smoothstep(0.76, 0.82, n3 + (0.5 - ch) * 0.15) * lane;
	float puddle = smoothstep(0.7, 0.74, n4) * lane * (1.0 - worn) * (1.0 - far);
	vec3 col = mix(ga, ea, earth);
	vec3 nrm = mix(gn, en, earth);
	col = mix(col, ca * vec3(0.9, 0.84, 0.76), lane);
	nrm = mix(nrm, cn, lane);
	col = mix(col, ea * 0.8, worn);
	nrm = mix(nrm, en, worn);
	col *= mix(1.0, 0.45, puddle * smoothstep(0.35, 0.6, 1.0 - ch));
	float scorch = clamp(m.b + (n2 - 0.5) * 0.6, 0.0, 1.0);
	col *= mix(1.0, 0.25, scorch);
	col *= 0.85 + 0.3 * n;   // large, soft variation in brightness
	ALBEDO = col;
	nrm = mix(nrm, vec3(0.5, 0.5, 1.0), puddle * 0.85);
	NORMAL_MAP = nrm;
	ROUGHNESS = mix(mix(0.92, 0.75, lane), 0.3, puddle);
	SPECULAR = mix(0.35, 0.2, puddle);
}
