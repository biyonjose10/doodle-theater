"""The JavaScript renderer must pose vertices exactly like the Python reference."""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from doodlerig import Rig
from doodlerig.pose import motions
from doodlerig.render import posed_vertices

ROOT = Path(__file__).parent.parent
NODE = shutil.which("node")

SCRIPT = """
import { prepareRig, sampleMotion, skinMatrices, skinVertices } from "%s";
import { readFileSync } from "node:fs";
const rigJson = JSON.parse(readFileSync(process.argv[2], "utf8"));
const motions = JSON.parse(readFileSync(process.argv[3], "utf8")).motions;
const cases = JSON.parse(readFileSync(process.argv[4], "utf8"));
const rig = prepareRig(rigJson, null);
const out = cases.map(([name, t]) => {
  const { angles, root } = sampleMotion(motions, name, t);
  return Array.from(skinVertices(rig, skinMatrices(rig, angles, root), new Float32Array(rig.verts.length)));
});
process.stdout.write(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_js_matches_python(tmp_path):
    rig = Rig.load(ROOT / "examples" / "char1")
    cases = [[name, round(m["duration"] * f, 3)] for name, m in motions().items() for f in (0.2, 0.55)]
    (tmp_path / "cases.json").write_text(json.dumps(cases))
    script = tmp_path / "parity.mjs"
    script.write_text(SCRIPT % (ROOT / "web" / "doodlerig.js").as_uri())
    res = subprocess.run([NODE, str(script), str(ROOT / "examples" / "char1" / "rig.json"),
                          str(ROOT / "doodlerig" / "motions.json"), str(tmp_path / "cases.json")],
                         capture_output=True, text=True, check=True)
    js = json.loads(res.stdout)
    # The saved rig rounds coordinates to 0.01 px, so compare against the reloaded rig.
    for (name, t), got in zip(cases, js):
        want = posed_vertices(rig, name, t)
        assert np.abs(np.array(got).reshape(-1, 2) - want).max() < 0.05, (name, t)
