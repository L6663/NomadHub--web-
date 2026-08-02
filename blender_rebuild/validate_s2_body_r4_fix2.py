"""Strict native/GLB validator for the R4-F2 surface-aligned repair."""

import importlib.util
from pathlib import Path

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
BASE_PATH = SCRIPT_DIR / "validate_s2_body_r4.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_validator", BASE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R4 validator: {BASE_PATH}")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


F2_SURFACES = (
    "R4_CAB_RING_L",
    "R4_CAB_RING_R",
    "R4_CAB_SEAM_L",
    "R4_CAB_SEAM_R",
)

ORIGINAL_VISUAL_REPORT = base.r4_visual_contract_report


def visual_report_f2(label):
    report = ORIGINAL_VISUAL_REPORT(label)
    failures = list(report["failures"])
    expected_roles = {
        "R4_CAB_RING_L": "surface_aligned_body_surround",
        "R4_CAB_RING_R": "surface_aligned_body_surround",
        "R4_CAB_SEAM_L": "surface_aligned_inner_seam",
        "R4_CAB_SEAM_R": "surface_aligned_inner_seam",
    }
    for name, role in expected_roles.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{label}: R4-F2 surface missing {name}")
            continue
        if not bool(obj.get("s2_r4_web_surface")):
            failures.append(f"{label}: R4-F2 Web marker missing {name}")
        if obj.get("s2_r4_f2_surface_role") != role:
            failures.append(f"{label}: R4-F2 role mismatch {name}")

    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    if glass is None or not bool(glass.get("s2_r4_f2_rebuilt_mesh")):
        failures.append(f"{label}: rebuilt windshield mesh marker missing")

    surround = bpy.data.objects.get("R4_WINDSHIELD_SURROUND")
    trim = bpy.data.objects.get("R4_WINDSHIELD_TRIM")
    if surround is None or not bool(surround.get("s2_r4_f2_surface_aligned")):
        failures.append(f"{label}: aligned windshield surround marker missing")
    if trim is None or not bool(trim.get("s2_r4_f2_surface_aligned")):
        failures.append(f"{label}: aligned windshield trim marker missing")

    report["r4_f2_surface_count"] = sum(bpy.data.objects.get(name) is not None for name in F2_SURFACES)
    report["failures"] = failures
    report["result"] = "PASS" if not failures else "FAIL"
    return report


base.r4_visual_contract_report = visual_report_f2


def collect_s1c_f2(label):
    s1c = base.validator.s1c
    original_static = s1c.STATIC_COLLISION_OBJECTS
    try:
        s1c.STATIC_COLLISION_OBJECTS = (
            base.validator.BODY_NAME,
            "FRONT_BUMPER",
            "REAR_BUMPER",
            "SIDE_SKIRT_L_FRONT",
            "SIDE_SKIRT_L_MID",
            "SIDE_SKIRT_L_REAR",
            "SIDE_SKIRT_R_FRONT",
            "SIDE_SKIRT_R_MID",
            "SIDE_SKIRT_R_REAR",
            *base.LEGACY_WHEEL_ARCHES,
            *base.R4_WHEEL_LIPS,
            "WHEEL_FL_TIRE",
            "WHEEL_FR_TIRE",
            "WHEEL_RL_TIRE",
            "WHEEL_RR_TIRE",
            "R4_WINDSHIELD_SURROUND",
            "R4_WINDSHIELD_TRIM",
            *F2_SURFACES,
            *base.CAB_SURROUNDS,
            *base.CAB_TRIMS,
        )
        return base.validator.collect_s1c_compatibility(label)
    finally:
        s1c.STATIC_COLLISION_OBJECTS = original_static


base.collect_s1c_compatibility_with_r4 = collect_s1c_f2


if __name__ == "__main__":
    base.main()
