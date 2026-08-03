"""Extended R3 preflight with moving-door and hatch collision checks."""

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
BASE_PATH = SCRIPT_DIR / "preflight_s2_body_r3.py"
BASE_SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r3_preflight_base", BASE_PATH)
if BASE_SPEC is None or BASE_SPEC.loader is None:
    raise RuntimeError(f"unable to load R3 preflight: {BASE_PATH}")
base = importlib.util.module_from_spec(BASE_SPEC)
BASE_SPEC.loader.exec_module(base)

FIX_PATH = SCRIPT_DIR / "build_s2_body_r3_fix.py"
FIX_SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r3_fixed_builder", FIX_PATH)
if FIX_SPEC is None or FIX_SPEC.loader is None:
    raise RuntimeError(f"unable to load fixed R3 builder: {FIX_PATH}")
fixed = importlib.util.module_from_spec(FIX_SPEC)
FIX_SPEC.loader.exec_module(fixed)

# Rebind the base preflight to the corrected builder module. Its helper
# functions resolve these globals at call time.
base.r3 = fixed.r3
base.builder = fixed.builder
base.entry = fixed.entry


def animation_preflight():
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
            "WHEEL_ARCH_FL",
            "WHEEL_ARCH_FR",
            "WHEEL_ARCH_RL",
            "WHEEL_ARCH_RR",
            "WHEEL_FL_TIRE",
            "WHEEL_FR_TIRE",
            "WHEEL_RL_TIRE",
            "WHEEL_RR_TIRE",
        )
        return s1c.animation_collision_sweep()
    finally:
        s1c.STATIC_COLLISION_OBJECTS = original_static


def main():
    # Run the existing topology/wheel/visual-contract gate first. It writes the
    # report and raises immediately if those cheap checks fail.
    base.main()
    args = base.parse_args()
    report_path = Path(args.report)
    report = json.loads(report_path.read_text(encoding="utf-8"))

    sweep = animation_preflight()
    report["animation_collision_sweep"] = sweep
    if sweep["result"] != "PASS":
        for missing in sweep["missing_objects"]:
            report["failures"].append(f"animation preflight missing: {missing}")
        for collision in sweep["collisions"]:
            report["failures"].append(
                "animation preflight collision "
                f"frame={collision['frame']} moving={collision['moving_mesh']} "
                f"static={collision['static_mesh']} pairs={collision['triangle_overlap_pairs']}"
            )
    report["status"] = "PASS" if not report["failures"] else "FAIL"
    report["purpose"] = (
        "fail-fast topology, wheel clearance, visual contract and moving-panel collision gate"
    )
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if report["failures"]:
        raise RuntimeError("S2 R3 animation preflight failed; evidence rendering was skipped")
    print("S2_R3_EXTENDED_PREFLIGHT_PASS")


if __name__ == "__main__":
    main()
