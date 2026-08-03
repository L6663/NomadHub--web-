"""Fail-fast gate for the R4-F2 surface-aligned visual repair."""

import importlib.util
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PREFLIGHT_PATH = SCRIPT_DIR / "preflight_s2_body_r4.py"
PREFLIGHT_SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_preflight", PREFLIGHT_PATH)
if PREFLIGHT_SPEC is None or PREFLIGHT_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4 preflight: {PREFLIGHT_PATH}")
preflight_r4 = importlib.util.module_from_spec(PREFLIGHT_SPEC)
PREFLIGHT_SPEC.loader.exec_module(preflight_r4)

FIX_PATH = SCRIPT_DIR / "build_s2_body_r4_fix2.py"
FIX_SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix2", FIX_PATH)
if FIX_SPEC is None or FIX_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F2 builder: {FIX_PATH}")
fixed = importlib.util.module_from_spec(FIX_SPEC)
FIX_SPEC.loader.exec_module(fixed)
r4 = fixed.r4

# Rebind every nested preflight layer to the final builder. The helpers resolve
# these module globals at call time.
preflight_r4.r4_fixed = fixed
preflight_r4.r4 = r4
preflight_r4.preflight.fixed = fixed
preflight_r4.preflight.base.r3 = r4
preflight_r4.preflight.base.builder = r4.builder
preflight_r4.preflight.base.entry = r4.entry


def animation_preflight_f2():
    s1c = preflight_r4.preflight.base.validator.s1c
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


preflight_r4.r4_animation_preflight = animation_preflight_f2
preflight_r4.preflight.animation_preflight = animation_preflight_f2

ORIGINAL_VISUAL_CONTRACT = preflight_r4.r4_visual_contract


def visual_contract_f2():
    report = ORIGINAL_VISUAL_CONTRACT()
    failures = list(report["failures"])
    required = {
        "R4_CAB_RING_L": "surface_aligned_body_surround",
        "R4_CAB_RING_R": "surface_aligned_body_surround",
        "R4_CAB_SEAM_L": "surface_aligned_inner_seam",
        "R4_CAB_SEAM_R": "surface_aligned_inner_seam",
    }
    bpy = preflight_r4.preflight.base.bpy
    for name, role in required.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"R4-F2 surface object missing: {name}")
            continue
        if not bool(obj.get("s2_r4_web_surface")):
            failures.append(f"R4-F2 Web-surface marker missing: {name}")
        if obj.get("s2_r4_f2_surface_role") != role:
            failures.append(f"R4-F2 surface role mismatch: {name}")

    surround = bpy.data.objects.get("R4_WINDSHIELD_SURROUND")
    trim = bpy.data.objects.get("R4_WINDSHIELD_TRIM")
    if surround is None or not bool(surround.get("s2_r4_f2_surface_aligned")):
        failures.append("R4-F2 aligned windshield surround marker missing")
    if trim is None or not bool(trim.get("s2_r4_f2_surface_aligned")):
        failures.append("R4-F2 aligned windshield trim marker missing")

    report["surface_aligned_objects"] = list(required)
    report["failures"] = failures
    report["result"] = "PASS" if not failures else "FAIL"
    return report


preflight_r4.r4_visual_contract = visual_contract_f2


if __name__ == "__main__":
    preflight_r4.main()
