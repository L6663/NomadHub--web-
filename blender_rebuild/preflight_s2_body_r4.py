"""Fail-fast S2-R4 source, animation and Web-surface presentation gate."""

import importlib.util
import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PREFLIGHT_PATH = SCRIPT_DIR / "preflight_s2_body_r3_fix.py"
PREFLIGHT_SPEC = importlib.util.spec_from_file_location(
    "nomadhub_s2_r3_extended_preflight", PREFLIGHT_PATH
)
if PREFLIGHT_SPEC is None or PREFLIGHT_SPEC.loader is None:
    raise RuntimeError(f"unable to load extended R3 preflight: {PREFLIGHT_PATH}")
preflight = importlib.util.module_from_spec(PREFLIGHT_SPEC)
PREFLIGHT_SPEC.loader.exec_module(preflight)

R4_PATH = SCRIPT_DIR / "build_s2_body_r4_fix.py"
R4_SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fixed", R4_PATH)
if R4_SPEC is None or R4_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4 builder: {R4_PATH}")
r4_fixed = importlib.util.module_from_spec(R4_SPEC)
R4_SPEC.loader.exec_module(r4_fixed)
r4 = r4_fixed.r4

preflight.fixed = r4_fixed
preflight.base.r3 = r4
preflight.base.builder = r4.builder
preflight.base.entry = r4.entry


def r4_animation_preflight():
    s1c = preflight.base.validator.s1c
    original_static = s1c.STATIC_COLLISION_OBJECTS
    cab_surrounds = tuple(
        f"R3_FRAME_CAB_DOOR_{side}_{suffix}"
        for side in ("L", "R")
        for suffix in ("BOTTOM", "TOP", "FRONT", "REAR")
    )
    cab_trims = tuple(
        f"R4_CAB_DOOR_TRIM_{side}_{suffix}"
        for side in ("L", "R")
        for suffix in ("BOTTOM", "TOP", "FRONT", "REAR")
    )
    try:
        s1c.STATIC_COLLISION_OBJECTS = (
            preflight.base.validator.BODY_NAME,
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
            "WHEEL_FL_TIRE",
            "WHEEL_FR_TIRE",
            "WHEEL_RL_TIRE",
            "WHEEL_RR_TIRE",
            "R4_WINDSHIELD_SURROUND",
            "R4_WINDSHIELD_TRIM",
            *cab_surrounds,
            *cab_trims,
        )
        return s1c.animation_collision_sweep()
    finally:
        s1c.STATIC_COLLISION_OBJECTS = original_static


preflight.animation_preflight = r4_animation_preflight


def r4_visual_contract():
    failures = []
    required = (
        "R4_WINDSHIELD_SURROUND",
        "R4_WINDSHIELD_TRIM",
        "R4_WHEEL_LIP_FL",
        "R4_WHEEL_LIP_FR",
        "R4_WHEEL_LIP_RL",
        "R4_WHEEL_LIP_RR",
    )
    for name in required:
        obj = preflight.base.bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"R4 object missing: {name}")
        elif not bool(obj.get("s2_r4_web_surface")):
            failures.append(f"R4 Web-surface marker missing: {name}")

    surrounds = [
        obj
        for obj in preflight.base.bpy.data.objects
        if bool(obj.get("s2_r4_cab_surround"))
    ]
    if len(surrounds) != 8:
        failures.append(f"R4 cab-surround piece count {len(surrounds)} != 8")

    buried = [
        obj
        for obj in preflight.base.bpy.data.objects
        if bool(obj.get("s2_r4_legacy_marker_buried"))
    ]
    if len(buried) != 6:
        failures.append(f"R4 buried legacy marker count {len(buried)} != 6")

    glass = preflight.base.bpy.data.objects.get("GLASS_WINDSHIELD")
    if glass is None or not bool(glass.get("s2_r4_dimensions_baked")):
        failures.append("R4 windshield baked-dimension marker missing")

    liners = [
        preflight.base.bpy.data.objects.get(name)
        for name in ("WHEEL_ARCH_FL", "WHEEL_ARCH_FR", "WHEEL_ARCH_RL", "WHEEL_ARCH_RR")
    ]
    if any(obj is None or obj.get("s2_r4_visual_role") != "recessed_compatibility_wheel_liner" for obj in liners):
        failures.append("R4 recessed compatibility wheel-liner contract missing")

    return {
        "required_objects": list(required),
        "cab_surround_piece_count": len(surrounds),
        "buried_legacy_marker_count": len(buried),
        "failures": failures,
        "result": "PASS" if not failures else "FAIL",
    }


def main():
    preflight.main()
    args = preflight.base.parse_args()
    report_path = Path(args.report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    visual = r4_visual_contract()
    report["schema"] = "nomadhub-s2-r4-preflight-v1"
    report["iteration"] = "R4"
    report["r4_visual_contract"] = visual
    report["failures"].extend(visual["failures"])
    report["status"] = "PASS" if not report["failures"] else "FAIL"
    report["purpose"] = (
        "fail-fast source topology, wheel clearance, moving-panel sweep and R4 Web-surface gate"
    )
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if report["failures"]:
        raise RuntimeError("S2 R4 preflight failed; evidence rendering was skipped")
    print("S2_R4_EXTENDED_PREFLIGHT_PASS")


if __name__ == "__main__":
    main()
