# Third-party material

**Meta AnimatedDrawings** (https://github.com/facebookresearch/AnimatedDrawings), MIT License,
Copyright (c) Meta Platforms, Inc. and affiliates.

- `doodlerig/segment.py`'s flood-fill segmentation follows the approach in AnimatedDrawings'
  `image_to_annotations.py`.
- The joint names and hierarchy match AnimatedDrawings' `char_cfg.yaml`, so annotations are
  interchangeable.
- The drawings in `tests/fixtures/` and the rigs built from them in `examples/` come from
  AnimatedDrawings' `examples/` folder, used under its MIT License.
