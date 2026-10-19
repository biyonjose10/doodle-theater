// doodlerig.js: animate a doodlerig puppet in the browser with WebGL. No dependencies.
// A line-for-line port of doodlerig/pose.py; the Python tests pin down the maths.

const NAMES = [
  "root", "hip", "torso", "neck",
  "right_shoulder", "right_elbow", "right_hand",
  "left_shoulder", "left_elbow", "left_hand",
  "right_hip", "right_knee", "right_foot",
  "left_hip", "left_knee", "left_foot",
];

export async function loadRig(baseUrl) {
  const base = baseUrl.endsWith("/") ? baseUrl : baseUrl + "/";
  const json = await (await fetch(base + "rig.json")).json();
  if (json.format !== "doodlerig" || json.version !== 1) throw new Error("not a doodlerig v1 rig");
  const image = new Image();
  image.crossOrigin = "anonymous";
  image.src = base + json.texture;
  await image.decode();
  return prepareRig(json, image);
}

export function prepareRig(json, image) {
  const parent = json.skeleton.map((j) => (j.parent === null ? -1 : NAMES.indexOf(j.parent)));
  const rest = new Float64Array(NAMES.length * 2);
  json.skeleton.forEach((j) => {
    const i = NAMES.indexOf(j.name);
    rest[2 * i] = j.x;
    rest[2 * i + 1] = j.y;
  });
  const verts = Float32Array.from(json.vertices);
  let minY = Infinity, maxY = -Infinity;
  for (let i = 1; i < verts.length; i += 2) { minY = Math.min(minY, verts[i]); maxY = Math.max(maxY, verts[i]); }
  return {
    json, image, parent, rest, verts,
    tris: Uint16Array.from(json.triangles),
    joints: Uint8Array.from(json.influences.joints),
    weights: Float32Array.from(json.influences.weights),
    groundY: json.ground_y,
    height: maxY - minY,
    width: json.width,
    texHeight: json.height,
  };
}

export async function loadMotions(url) {
  return (await (await fetch(url)).json()).motions;
}

const smooth = (a) => a * a * (3 - 2 * a);

function evalCurve(c, t, d) {
  if (c.keys) {
    const k = c.keys;
    if (t <= k[0][0]) return k[0][1];
    for (let i = 0; i < k.length - 1; i++) {
      const [t0, v0] = k[i], [t1, v1] = k[i + 1];
      if (t <= t1) return v0 + (v1 - v0) * smooth((t - t0) / Math.max(t1 - t0, 1e-9));
    }
    return k[k.length - 1][1];
  }
  const kind = Object.keys(c)[0];
  const [amp, cycles, phase, offset] = c[kind];
  let s = Math.sin(2 * Math.PI * ((cycles * t) / d + phase));
  if (kind === "abs_sin") s = Math.abs(s);
  else if (kind === "pos_sin") s = Math.max(0, s);
  return offset + amp * s;
}

export function sampleMotion(motions, name, t) {
  const m = motions[name];
  const d = m.duration;
  t = m.loop ? ((t % d) + d) % d : Math.min(Math.max(t, 0), d);
  const angles = new Float64Array(NAMES.length);
  const root = { "root.x": 0, "root.y": 0, "root.sx": 1, "root.sy": 1 };
  for (const [ch, curve] of Object.entries(m.channels)) {
    const v = evalCurve(curve, t, d);
    if (ch in root) root[ch] = v;
    else angles[NAMES.indexOf(ch)] = v;
  }
  return { angles, root };
}

// 2x3 affine matrices stored as [a, b, c, d, e, f]: x' = a x + c y + e, y' = b x + d y + f
const mul = (m, n) => [
  m[0] * n[0] + m[2] * n[1], m[1] * n[0] + m[3] * n[1],
  m[0] * n[2] + m[2] * n[3], m[1] * n[2] + m[3] * n[3],
  m[0] * n[4] + m[2] * n[5] + m[4], m[1] * n[4] + m[3] * n[5] + m[5],
];
const T = (x, y) => [1, 0, 0, 1, x, y];
const S = (sx, sy) => [sx, 0, 0, sy, 0, 0];
const R = (deg) => {
  const r = (deg * Math.PI) / 180, c = Math.cos(r), s = Math.sin(r);
  return [c, s, -s, c, 0, 0];
};

export function skinMatrices(rig, angles, root) {
  const { rest, parent, groundY, height } = rig;
  const world = new Array(NAMES.length);
  const rx = rest[0], ry = rest[1];
  world[0] = mul(mul(mul(T(rx + root["root.x"] * height, groundY + root["root.y"] * height),
    S(root["root.sx"], root["root.sy"])), T(0, ry - groundY)), R(angles[0]));
  for (let j = 1; j < NAMES.length; j++) {
    const p = parent[j];
    world[j] = mul(mul(world[p], T(rest[2 * j] - rest[2 * p], rest[2 * j + 1] - rest[2 * p + 1])), R(angles[j]));
  }
  return world.map((w, j) => mul(w, T(-rest[2 * j], -rest[2 * j + 1])));
}

export function skinVertices(rig, mats, out) {
  const { verts, joints, weights } = rig;
  for (let i = 0, n = verts.length / 2; i < n; i++) {
    const x = verts[2 * i], y = verts[2 * i + 1];
    let ox = 0, oy = 0;
    for (let k = 0; k < 2; k++) {
      const w = weights[2 * i + k];
      if (w === 0) continue;
      const m = mats[joints[2 * i + k]];
      ox += w * (m[0] * x + m[2] * y + m[4]);
      oy += w * (m[1] * x + m[3] * y + m[5]);
    }
    out[2 * i] = ox;
    out[2 * i + 1] = oy;
  }
  return out;
}

const VS = `attribute vec2 aPos; attribute vec2 aUv; uniform vec2 uView; uniform vec3 uPlace;
varying vec2 vUv;
void main() {
  vec2 p = aPos * uPlace.z + uPlace.xy;
  gl_Position = vec4(p.x / uView.x * 2.0 - 1.0, 1.0 - p.y / uView.y * 2.0, 0.0, 1.0);
  vUv = aUv;
}`;
const FS = `precision mediump float; varying vec2 vUv; uniform sampler2D uTex;
void main() { vec4 c = texture2D(uTex, vUv); if (c.a < 0.02) discard; gl_FragColor = vec4(c.rgb * c.a, c.a); }`;

// A stage draws any number of puppets onto one canvas.
export class Stage {
  constructor(canvas, motions) {
    this.canvas = canvas;
    this.motions = motions;
    const gl = canvas.getContext("webgl", { premultipliedAlpha: true, alpha: true, antialias: true });
    if (!gl) throw new Error("WebGL is not available");
    this.gl = gl;
    const prog = gl.createProgram();
    for (const [type, src] of [[gl.VERTEX_SHADER, VS], [gl.FRAGMENT_SHADER, FS]]) {
      const s = gl.createShader(type);
      gl.shaderSource(s, src);
      gl.compileShader(s);
      gl.attachShader(prog, s);
    }
    gl.linkProgram(prog);
    gl.useProgram(prog);
    this.loc = {
      pos: gl.getAttribLocation(prog, "aPos"), uv: gl.getAttribLocation(prog, "aUv"),
      view: gl.getUniformLocation(prog, "uView"), place: gl.getUniformLocation(prog, "uPlace"),
    };
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    this.actors = [];
  }

  add(rig, { x = 0.5, scale = 0.6, motion = "idle" } = {}) {
    const gl = this.gl;
    const uv = new Float32Array(rig.verts.length);
    for (let i = 0; i < rig.verts.length; i += 2) {
      uv[i] = rig.verts[i] / rig.width;
      uv[i + 1] = rig.verts[i + 1] / rig.texHeight;
    }
    const a = {
      rig, x, scale, motion, start: performance.now(),
      posed: new Float32Array(rig.verts.length),
      pos: gl.createBuffer(), uv: gl.createBuffer(), idx: gl.createBuffer(), tex: gl.createTexture(),
    };
    gl.bindBuffer(gl.ARRAY_BUFFER, a.uv);
    gl.bufferData(gl.ARRAY_BUFFER, uv, gl.STATIC_DRAW);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, a.idx);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, rig.tris, gl.STATIC_DRAW);
    gl.bindTexture(gl.TEXTURE_2D, a.tex);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, rig.image);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    this.actors.push(a);
    return a;
  }

  play(actor, motion) {
    actor.motion = motion;
    actor.start = performance.now();
  }

  frame(now = performance.now()) {
    const { gl, canvas, loc } = this;
    const dpr = window.devicePixelRatio || 1;
    const w = Math.round(canvas.clientWidth * dpr), h = Math.round(canvas.clientHeight * dpr);
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
    gl.viewport(0, 0, w, h);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.uniform2f(loc.view, w, h);
    for (const a of this.actors) {
      const { angles, root } = sampleMotion(this.motions, a.motion, (now - a.start) / 1000);
      skinVertices(a.rig, skinMatrices(a.rig, angles, root), a.posed);
      const s = (a.scale * h) / a.rig.height;
      gl.uniform3f(loc.place, a.x * w - a.rig.rest[0] * s, h * 0.92 - a.rig.groundY * s, s);
      gl.bindBuffer(gl.ARRAY_BUFFER, a.pos);
      gl.bufferData(gl.ARRAY_BUFFER, a.posed, gl.DYNAMIC_DRAW);
      gl.enableVertexAttribArray(loc.pos);
      gl.vertexAttribPointer(loc.pos, 2, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, a.uv);
      gl.enableVertexAttribArray(loc.uv);
      gl.vertexAttribPointer(loc.uv, 2, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, a.idx);
      gl.bindTexture(gl.TEXTURE_2D, a.tex);
      gl.drawElements(gl.TRIANGLES, a.rig.tris.length, gl.UNSIGNED_SHORT, 0);
    }
  }

  run() {
    const tick = (now) => { this.frame(now); this._raf = requestAnimationFrame(tick); };
    this._raf = requestAnimationFrame(tick);
  }

  stop() { cancelAnimationFrame(this._raf); }
}

export { NAMES };
