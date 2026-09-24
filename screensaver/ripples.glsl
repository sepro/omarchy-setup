// Koi Pond screensaver: the wallpaper as a pond surface. A slow swell moves the
// whole picture, and now and then a drop of water falls and sends out rings.
// An mpv user shader; tune it with --glsl-shader-opts=name=value.

//!PARAM swell
//!DESC Strength of the slow wavy distortion of the whole surface (0 = still)
//!TYPE float
//!MINIMUM 0.0
//!MAXIMUM 4.0
1.0

//!PARAM drop_interval
//!DESC Average seconds between falling drops (0 = no drops)
//!TYPE float
//!MINIMUM 0.0
//!MAXIMUM 120.0
10.0

//!PARAM drop_strength
//!DESC How strongly the drop rings bend the picture
//!TYPE float
//!MINIMUM 0.0
//!MAXIMUM 4.0
1.0

//!PARAM fps
//!DESC Frame rate of the input, to turn the frame counter into seconds
//!TYPE float
30.0

//!HOOK MAIN
//!BIND HOOKED
//!DESC koi pond ripples

#define SLOTS 4          // drops that can be on screen at once
#define LIFE 7.0         // seconds a ring train lives
#define SPEED 110.0      // ring speed, px/s
#define WAVELEN 44.0     // distance between rings, px

const vec2 LIGHT = vec2(-0.6, -0.8);

float hash11(float p) {
    p = fract(p * 0.1031);
    p *= p + 33.33;
    p *= p + p;
    return fract(p);
}

// Slow swell: a few crossing sine waves over the whole picture.
float swell_height(vec2 p, float t) {
    vec2 q = p / 1080.0;
    return swell * 2.9 * (
          sin(dot(q, vec2(9.0, 4.0)) + t * 0.9)
        + sin(dot(q, vec2(-5.0, 11.0)) - t * 0.7)
        + 0.6 * sin(dot(q, vec2(17.0, -13.0)) + t * 1.4));
}

// Drop rings. Returns the height, and in splash the brightness of the impact.
float drop_height(vec2 p, float t, out float splash) {
    splash = 0.0;
    float h = 0.0;
    if (drop_interval <= 0.0) return 0.0;

    // Each slot drops once per period, at a random moment and place in it.
    float period = max(SLOTS * drop_interval, LIFE + 1.0);
    float k = 6.2831853 / WAVELEN;
    for (int i = 0; i < SLOTS; i++) {
        float fi = float(i);
        float tt = t + hash11(fi * 7.13 + 1.0) * period;
        float cycle = floor(tt / period);
        float seed = cycle * 13.7 + fi * 3.1;
        float age = tt - cycle * period - hash11(seed + 0.9) * (period - LIFE);
        if (age < 0.0 || age > LIFE) continue;

        vec2 c = (vec2(0.06) + 0.88 * vec2(hash11(seed), hash11(seed + 0.5))) * HOOKED_size;
        float d = length(p - c);

        // Impact: a small bright spot that flashes and shrinks away.
        float s = 1.0 - age / 0.5;
        if (s > 0.0) splash += s * s * exp(-d * d / (2.0 * 11.0 * 11.0));

        // A train of rings behind the leading edge; fades as it spreads and ages.
        float front = age * SPEED;
        float x = d - front;
        if (x > 12.0) continue;
        float env = exp(-x * x / (2.0 * 70.0 * 70.0)) * smoothstep(12.0, 0.0, x);
        float fade = 1.0 - age / LIFE;
        fade = sqrt(fade) * fade / (1.0 + front / 700.0);
        h += 1.1 * env * fade * sin(k * x);
    }
    return h;
}

vec4 hook() {
    float t = float(frame) / fps;
    vec2 p = HOOKED_pos * HOOKED_size;

    // Surface slope by central differences.
    float e = 1.5, splash, dummy;
    vec2 gs = vec2(
        swell_height(p + vec2(e, 0.0), t) - swell_height(p - vec2(e, 0.0), t),
        swell_height(p + vec2(0.0, e), t) - swell_height(p - vec2(0.0, e), t)) / (2.0 * e);
    vec2 gd = vec2(
        drop_height(p + vec2(e, 0.0), t, dummy) - drop_height(p - vec2(e, 0.0), t, dummy),
        drop_height(p + vec2(0.0, e), t, dummy) - drop_height(p - vec2(0.0, e), t, dummy)) / (2.0 * e);
    drop_height(p, t, splash);
    gd *= drop_strength;

    // Refraction: read the wallpaper a few pixels away along the slope.
    vec2 offset = (gs + gd) * 100.0;
    vec2 uv = (p + offset) * HOOKED_pt;
    vec4 col = HOOKED_tex(clamp(uv, HOOKED_pt, 1.0 - HOOKED_pt));

    // Light catches one side of each ring and the swell crests.
    float kmax = 6.2831853 / WAVELEN;
    col.rgb += 0.08 * clamp(dot(gd, LIGHT) / kmax, -1.5, 1.5);
    col.rgb += 0.05 * clamp(dot(gs, LIGHT) * 20.0, -1.0, 1.0);
    col.rgb += 0.35 * splash;
    return col;
}
