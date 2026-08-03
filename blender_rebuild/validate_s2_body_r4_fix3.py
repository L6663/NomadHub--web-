"""Strict native/GLB validator for the R4-F3 opening-matched repair."""

import importlib.util
import math
from pathlib import Path

import bpy
from mathutils import Vector


SCRIPT_DIR = Path(__file__).resolve().parent
F2_PATH = SCRIPT_DIR / "validate_s2_body_r4_fix2.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_f2_validator", F2_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F2 validator: {F2_PATH}")
f2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f2)
base = f2.base


EXPECTED_WINDSHIELD_DIMS = (0.028, 1.740, 0.500)
EXPECTED_WINDSHIELD_ANGLE_DEG = math.degrees(math.atan2(0.440, 0.410))
ORIGINAL_VISUAL_REPORT = base.r4_visual_contract_report


def windshield_world_angle_deg(obj):
    """Return the windshield height-axis slope in the world X/Z plane.

    Native Blender objects use Euler rotation in this project, while a glTF
    round trip commonly restores the same transform in quaternion mode. Reading
    ``rotation_euler.y`` therefore reports a false zero for valid imported GLB
    nodes. The transformed local Z axis is representation-independent and
    validates the actual spatial orientation carried by the object matrix.
    """

    height_axis = obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))
    if height_axis.length <= 1e-9:
        return None
    height_axis.normalize()
    return math.degrees(math.atan2(abs(height_axis.x), abs(height_axis.z)))


def visual_report_f3(label):
    report = ORIGINAL_VISUAL_REPORT(label)
    # The base R4 contract intentionally encoded the older 0.68 m windshield.
    # F3 matches the actual 0.60 m sloped source opening and therefore uses a
    # smaller inset glass. Replace only that obsolete dimensional failure.
    failures = [
        failure
        for failure in report["failures"]
        if "windshield dimensions" not in failure
    ]

    surround = bpy.data.objects.get("R4_WINDSHIELD_SURROUND")
    trim = bpy.data.objects.get("R4_WINDSHIELD_TRIM")
    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    for name, obj in (
        ("R4_WINDSHIELD_SURROUND", surround),
        ("R4_WINDSHIELD_TRIM", trim),
        ("GLASS_WINDSHIELD", glass),
    ):
        if obj is None or not bool(obj.get("s2_r4_f3_opening_matched")):
            failures.append(f"{label}: R4-F3 opening-match marker missing {name}")

    glass_dims = None
    glass_angle = None
    glass_rotation_mode = None
    if glass is not None:
        glass_dims = tuple(float(value) for value in glass.dimensions)
        glass_angle = windshield_world_angle_deg(glass)
        glass_rotation_mode = glass.rotation_mode
        if any(
            abs(actual - expected) > 0.015
            for actual, expected in zip(glass_dims, EXPECTED_WINDSHIELD_DIMS)
        ):
            failures.append(
                f"{label}: R4-F3 windshield dimensions {glass_dims} outside tolerance"
            )
        if glass_angle is None:
            failures.append(f"{label}: R4-F3 windshield world axis is degenerate")
        elif abs(glass_angle - EXPECTED_WINDSHIELD_ANGLE_DEG) > 0.05:
            failures.append(
                f"{label}: R4-F3 windshield world angle {glass_angle:.4f} != "
                f"{EXPECTED_WINDSHIELD_ANGLE_DEG:.4f}"
            )

    masked_cab_surfaces = []
    for name in (
        "R4_CAB_RING_L",
        "R4_CAB_RING_R",
        "R4_CAB_SEAM_L",
        "R4_CAB_SEAM_R",
    ):
        obj = bpy.data.objects.get(name)
        if obj is None or not bool(obj.get("s2_r4_f3_source_edge_mask")):
            failures.append(f"{label}: R4-F3 cab edge-mask marker missing {name}")
        else:
            masked_cab_surfaces.append(name)

    hidden_wheel_nodes = []
    for name in (
        "WHEEL_ARCH_FL",
        "WHEEL_ARCH_FR",
        "WHEEL_ARCH_RL",
        "WHEEL_ARCH_RR",
        "R4_WHEEL_LIP_FL",
        "R4_WHEEL_LIP_FR",
        "R4_WHEEL_LIP_RL",
        "R4_WHEEL_LIP_RR",
    ):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{label}: R4-F3 wheel compatibility node missing {name}")
        elif obj.get("s2_r4_f3_visual_role") != "invisible_compatibility_reference":
            failures.append(f"{label}: R4-F3 invisible wheel marker missing {name}")
        else:
            hidden_wheel_nodes.append(name)

    report["windshield_glass_dimensions_m"] = list(glass_dims) if glass_dims else None
    report["windshield_angle_deg"] = glass_angle
    report["windshield_rotation_mode"] = glass_rotation_mode
    report["cab_source_edge_mask_surfaces"] = masked_cab_surfaces
    report["invisible_auxiliary_wheel_nodes"] = hidden_wheel_nodes
    report["failures"] = failures
    report["result"] = "PASS" if not failures else "FAIL"
    return report


base.r4_visual_contract_report = visual_report_f3


if __name__ == "__main__":
    base.main()
