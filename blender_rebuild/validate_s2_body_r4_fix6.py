"""Strict native/GLB validator for the R4-F6 integrated repair."""

import importlib.util
from pathlib import Path

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
F5_PATH = SCRIPT_DIR / "validate_s2_body_r4_fix5.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_f5_validator", F5_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F5 validator: {F5_PATH}")
f5 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f5)
base = f5.base

ORIGINAL_VISUAL_REPORT = base.r4_visual_contract_report


def visual_report_f6(label):
    report = ORIGINAL_VISUAL_REPORT(label)
    failures = list(report["failures"])

    headers = []
    for name in ("R4_CAB_HEADER_L", "R4_CAB_HEADER_R"):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{label}: R4-F6 cab header missing {name}")
            continue
        if not bool(obj.get("s2_r4_f6_flush_header_patch")):
            failures.append(f"{label}: R4-F6 header marker missing {name}")
        z_min = float(obj.get("s2_r4_f6_z_min_m", 0.0))
        z_max = float(obj.get("s2_r4_f6_z_max_m", 0.0))
        if z_min > 2.130 or z_max < 2.300:
            failures.append(
                f"{label}: R4-F6 header range invalid {name}={z_min:.3f}..{z_max:.3f}"
            )
        headers.append(name)

    narrow_surfaces = []
    for name in (
        "R4_CAB_RING_L",
        "R4_CAB_RING_R",
        "R4_CAB_SEAM_L",
        "R4_CAB_SEAM_R",
    ):
        obj = bpy.data.objects.get(name)
        if obj is None or not bool(obj.get("s2_r4_f6_narrow_ring")):
            failures.append(f"{label}: R4-F6 narrow-ring marker missing {name}")
        else:
            narrow_surfaces.append(name)

    trapezoids = {}
    for name in ("R4_WINDSHIELD_SURROUND", "R4_WINDSHIELD_TRIM"):
        obj = bpy.data.objects.get(name)
        if obj is None or not bool(obj.get("s2_r4_f6_trapezoid_ring")):
            failures.append(f"{label}: R4-F6 trapezoid ring missing {name}")
            continue
        bottom = float(obj.get("s2_r4_f6_bottom_width_m", 0.0))
        top = float(obj.get("s2_r4_f6_top_width_m", 0.0))
        if top - bottom < 0.040:
            failures.append(
                f"{label}: R4-F6 ring section growth invalid {name}={bottom}->{top}"
            )
        trapezoids[name] = [bottom, top]

    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    glass_widths = None
    if glass is None or not bool(glass.get("s2_r4_f6_trapezoid_glass")):
        failures.append(f"{label}: R4-F6 trapezoid glass marker missing")
    else:
        bottom = float(glass.get("s2_r4_f6_bottom_width_m", 0.0))
        top = float(glass.get("s2_r4_f6_top_width_m", 0.0))
        glass_widths = [bottom, top]
        if top <= bottom:
            failures.append(f"{label}: R4-F6 glass is not wider at top")

    report["r4_f6_headers"] = headers
    report["r4_f6_narrow_cab_surfaces"] = narrow_surfaces
    report["r4_f6_trapezoid_rings"] = trapezoids
    report["r4_f6_glass_widths_m"] = glass_widths
    report["failures"] = failures
    report["result"] = "PASS" if not failures else "FAIL"
    return report


base.r4_visual_contract_report = visual_report_f6


def collect_s1c_f6(label):
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
            "R4_CAB_RING_L",
            "R4_CAB_RING_R",
            "R4_CAB_SEAM_L",
            "R4_CAB_SEAM_R",
            "R4_CAB_HEADER_L",
            "R4_CAB_HEADER_R",
            *base.CAB_SURROUNDS,
            *base.CAB_TRIMS,
        )
        return base.validator.collect_s1c_compatibility(label)
    finally:
        s1c.STATIC_COLLISION_OBJECTS = original_static


base.collect_s1c_compatibility_with_r4 = collect_s1c_f6


if __name__ == "__main__":
    base.main()
