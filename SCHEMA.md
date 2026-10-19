# doodlerig file formats

## `rig.json` (version 1)

A rig is a folder holding `rig.json` and `texture.png` (RGBA, the character on a transparent
background). All coordinates are **texture pixels**, origin top-left, **y down**.

| Field | Meaning |
|---|---|
| `format`, `version` | `"doodlerig"`, `1` |
| `texture`, `width`, `height` | texture file name and size |
| `ground_y` | y of the feet; the pivot for `root.sx` / `root.sy` squash and stretch |
| `skeleton` | 16 joints, **parents before children**: `{name, parent, x, y}` |
| `vertices` | flat `[x0, y0, x1, y1, ...]`, the mesh at rest; also its texture coordinates (÷ width/height) |
| `triangles` | flat vertex indices, three per triangle, **already in draw order** (legs, body, arms) |
| `influences.joints` | flat, two per vertex: the skeleton indices of the joints that move it |
| `influences.weights` | flat, two per vertex, each pair sums to 1 |
| `description` | optional free text (e.g. a vision model's one-line description) |

Joint names follow Meta AnimatedDrawings: `root, hip, torso, neck, right_shoulder, right_elbow,
right_hand, left_shoulder, left_elbow, left_hand, right_hip, right_knee, right_foot, left_hip,
left_knee, left_foot`. `right_*` is the character's right, which is the **left of the image**.

## Posing (what every renderer implements)

Given per-joint angles `a[j]` (degrees, positive = clockwise on screen) and root channels
`root.x`, `root.y` (fractions of the character's height), `root.sx`, `root.sy`:

```
H        = height of the rest mesh
world[0] = T(rest[0].x + root.x*H, ground_y + root.y*H) · S(root.sx, root.sy) · T(0, rest[0].y - ground_y) · R(a[0])
world[j] = world[parent[j]] · T(rest[j] - rest[parent[j]]) · R(a[j])
skin[j]  = world[j] · T(-rest[j])
v'       = Σ_k  w_k · skin[joint_k] · v          (two influences per vertex)
```

`doodlerig/pose.py` is the reference; `web/doodlerig.js` is a tested port
(`tests/test_js_parity.py` checks the two agree to 0.05 px).

## `motions.json`

Named motions, each `{duration, loop, channels}`. A channel is a joint name (rotation) or
`root.x | root.y | root.sx | root.sy`, and its value is one curve:

- `{"sin": [amp, cycles, phase, offset]}` → `offset + amp·sin(2π(cycles·t/duration + phase))`
- `{"abs_sin": [...]}`: the same with `|sin|` (bounces)
- `{"pos_sin": [...]}`: the same with `max(0, sin)` (alternating legs)
- `{"keys": [[t, v], ...]}`: smoothstep between keys (t in seconds), held at both ends

Non-looping motions end at their rest values, so they can chain into anything.
