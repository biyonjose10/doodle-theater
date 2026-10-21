# Sample stars

Three ready-made characters for trying Doodle Theater without a drawing to hand: on the TV's
Home screen choose **Try sample stars** (or `POST /api/cast/samples`). The server builds each
puppet from the drawing, its mask and the joints in `samples.json` through the same rig builder
a phone upload uses.

The drawings and masks are the AnimatedDrawings example characters already used in
`rig/tests/fixtures/` (char1, char2, char3), from **Meta AnimatedDrawings**
(https://github.com/facebookresearch/AnimatedDrawings), MIT License,
Copyright (c) Meta Platforms, Inc. and affiliates. The joints come from their `char_cfg.yaml`.
The names and descriptions are ours.
