"""doodlerig: photo of a hand-drawn character -> a rigged 2D puppet any renderer can animate."""
from .joints import NAMES, PARENT, SKELETON, heuristic_joints
from .rig import JointProvider, Rig, build_rig, rig_from_mask

__all__ = ["Rig", "build_rig", "rig_from_mask", "JointProvider", "SKELETON", "NAMES", "PARENT",
           "heuristic_joints"]
__version__ = "0.1.0"
