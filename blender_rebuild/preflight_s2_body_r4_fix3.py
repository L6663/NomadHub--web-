"""Fail-fast gate for the R4-F3 opening-matched visual repair."""

import importlib.util
import math
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PREFLIGHT_PATH = SCRIPT_DIR / "preflight_s2_body_r4.py"
PREFLIGHT_SPEC = importlib.util.spec_from_file_location(
    "nomadhub_s2_r4_preflight", PREFLIGHT_PATH
)
if PREFLIGHT_SPEC is None or PREFLIGHT_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4 preflight: {PREFLIGHT_PATH}")
preflight_r4 = importlib.util.module_from_spec(PREFLIGHT_SPEC)
PREFLIGHT_SPEC.loader.exec_module(preflight_r4)

FIX_PATH = SCRIPT_DIR / "build_s2_body_r4_fix3.py"
FIX_SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix3", FIX_PATH)
if FIX_SPEC is None or FIX_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F3 builder: {FIX_PATH}")
fixed = importlib.util.module_from_spec(FIX_SPEC)
FIX_SPEC.loader.exec_module(fixed)
r4 = fixed.r4

# Rebind every nested preflight layer to the F3 builder.
preflight_r4.r4_fixed = fixed
preflight_r4.r4 = r4
preflight_r4.preflight.fixed = fixed
preflight_r4.preflight.base.r3 = r4
preflight_r4.preflight.base.builder = r4.builder
preflight_r4.preflight.base.entry = r4.entry


def animation_preflight_f3():
    # preflight_r4 -> R3 repair preflight -> R3 base preflight -> R2 validator
    # -> S2 base validator -> S1C validator. Use the real nested module path;
    # validator.s1c does not exist at this layer.
    s1c = preflight_r4.preflight.base.validator.base.s1c
    original_static = s1c.STATIC_COLLISION_OBJECTS
    try:
        s1c.STATIC_COLLISION_OBJECTS = (
            preflight_r4.preflight.base.validator.BODY_NAME,
            "FRONT_BUMPER",
            "REAR_BUMPER",
            "SIDE_SKIRT_L_FRONT",
            "SIDE_SKIRT_L_MID",
            "SIDE_SKIRT_L_REAR",
            "SIDE_SKIRT_R_FRONT",
            "SIDE_SKIRT_R_MID",
            "SIDE_SKIRT_R_REAR",
            "WHEEL_ARCH_FL",
            "WHEEL_ARCH_FR",
            "WHEEL_ARCH_RL",
            "WHEEL_ARCH_RR",
            "R4_WHEEL_LIP_FL",
            "R4_WHEEL_LIP_FR",
            "R4_WHEEL_LIP_RL",
            "R4_WHEEL_LIP_RR",
            "WHEEL_FL_TIRE",
            "WHEEL_FR_TIRE",
            "WHEEL_RL_TIRE",
            "WHEEL_RR_TIRE",
            "R4_WINDSHIELD_SURROUND",
            "R4_WINDSHIELD_TRIM",
            "R4_CAB_RING_L",
            "R4_CAB_RING_R",
            "R4_CAB_SEAM_L",
            "R4_CAB_SEAM_R",
        )
        return s1c.animation_collision_sweep()
    finally:
        s1c.STATIC_COLLISION_OBJECTS = original_static


preflight_r4.r4_animation_preflight = animation_preflight_f3
preflight_r4.preflight.animation_preflight = animation_preflight_f3

ORIGINAL_VISUAL_CONTRACT = preflight_r4.r4_visual_contract


def visual_contract_f3():
    report = ORIGINAL_VISUAL_CONTRACT()
    failures = list(report["failures"])
    bpy = preflight_r4.preflight.base.bpy

    required_roles = {
        "R4_CAB_RING_L": "surface_aligned_body_surround",
        "R4_CAB_RING_R": "surface_aligned_body_surround",
        "R4_CAB_SEAM_L": "surface_aligned_inner_seam",
        "R4_CAB_SEAM_R": "surface_aligned_inner_seam",
    }
    for name, role in required_roles.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"R4-F3 surface object missing: {name}")
            continue
        if not bool(obj.get("s2_r4_web_surface")):
            failures.append(f"R4-F3 Web-surface marker missing: {name}")
        if obj.get("s2_r4_f2_surface_role") != role:
            failures.append(f"R4-F3 surface role mismatch: {name}")
        if not bool(obj.get("s2_r4_f3_source_edge_mask")):
            failures.append(f"R4-F3 source-edge mask marker missing: {name}")

    surround = bpy.data.objects.get("R4_WINDSHIELD_SURROUND")
    trim = bpy.data.objects.get("R4_WINDSHIELD_TRIM")
    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    for name, obj in (
        ("R4_WINDSHIELD_SURROUND", surround),
        ("R4_WINDSHIELD_TRIM", trim),
        ("GLASS_WINDSHIELD", glass),
    ):
        if obj is None or not bool(obj.get("s2_r4_f3_opening_matched")):
            failures.append(f"R4-F3 opening-match marker missing: {name}")
    if glass is not None:
        angle_deg = math.degrees(float(glass.rotation_euler.y))
        if abs(angle_deg - math.degrees(fixed.WINDSHIELD_ROTATION_Y)) > 0.05:
            failures.append(
                f"R4-F3 windshield angle {angle_deg:.4f} does not match source opening"
            )
        dims = tuple(float(value) for value in glass.dimensions)
        expected = (0.028, 1.740, 0.500)
        if any(abs(actual - target) > 0.015 for actual, target in zip(dims, expected)):
            failures.append(f"R4-F3 windshield dimensions {dims} outside tolerance")

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
            failures.append(f"R4-F3 wheel compatibility node missing: {name}")
        elif obj.get("s2_r4_f3_visual_role") != "invisible_compatibility_reference":
            failures.append(f"R4-F3 invisible wheel marker missing: {name}")
        else:
            hidden_wheel_nodes.append(name)

    report["surface_aligned_objects"] = list(required_roles)
    report["opening_matched_windshield_angle_deg"] = round(
        math.degrees(fixed.WINDSHIELD_ROTATION_Y), 6
    )
    report["invisible_auxiliary_wheel_nodes"] = hidden_wheel_nodes
    report["failures"] = failures
    report["result"] = "PASS" if not failures else "FAIL"
    return report


preflight_r4.r4_visual_contract = visual_contract_f3


if __name__ == "__main__":
    preflight_r4.main()
