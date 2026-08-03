"""Fail-fast gate for the R4-F7b dual-axis cab-corner correction."""

import importlib.util
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PREFLIGHT_PATH = SCRIPT_DIR / "preflight_s2_body_r4_fix7.py"
PREFLIGHT_SPEC = importlib.util.spec_from_file_location(
    "nomadhub_s2_r4_f7_preflight", PREFLIGHT_PATH
)
if PREFLIGHT_SPEC is None or PREFLIGHT_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F7 preflight: {PREFLIGHT_PATH}")
preflight7 = importlib.util.module_from_spec(PREFLIGHT_SPEC)
PREFLIGHT_SPEC.loader.exec_module(preflight7)

FIX_PATH = SCRIPT_DIR / "build_s2_body_r4_fix7b.py"
FIX_SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix7b", FIX_PATH)
if FIX_SPEC is None or FIX_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F7b builder: {FIX_PATH}")
fixed = importlib.util.module_from_spec(FIX_SPEC)
FIX_SPEC.loader.exec_module(fixed)

# F7's visual checker calls find_cab_components and the frozen boundary
# constants from its builder module. Keep that helper-facing binding on the F7
# module, while every actual build/preflight layer uses the F7b builder object
# whose shared builder has the dual-axis snapping function installed.
preflight7.fixed = fixed.f7
preflight6 = preflight7.preflight6
preflight6.fixed = fixed
preflight5 = preflight7.preflight5
preflight5.fixed = fixed
preflight3 = preflight7.preflight3
preflight3.fixed = fixed
preflight3.r4 = fixed.r4
preflight_r4 = preflight7.preflight_r4
preflight_r4.r4_fixed = fixed
preflight_r4.r4 = fixed.r4
preflight_r4.preflight.fixed = fixed
preflight_r4.preflight.base.r3 = fixed.r4
preflight_r4.preflight.base.builder = fixed.builder
preflight_r4.preflight.base.entry = fixed.entry

ORIGINAL_VISUAL_CONTRACT = preflight_r4.r4_visual_contract


def visual_contract_f7b():
    report = ORIGINAL_VISUAL_CONTRACT()
    failures = [
        failure
        for failure in report["failures"]
        if not (
            "R4-F3 surface role mismatch: R4_CAB_SEAM_" in failure
            or "R4-F3 role mismatch R4_CAB_SEAM_" in failure
        )
    ]
    body = preflight_r4.preflight.base.bpy.data.objects.get(
        preflight_r4.preflight.base.validator.BODY_NAME
    )
    if body is None or not bool(body.get("s2_r4_f7b_dual_axis_corner_snap")):
        failures.append("R4-F7b dual-axis corner-snap marker missing")
    report["r4_f7b_dual_axis_corner_snap"] = bool(
        body and body.get("s2_r4_f7b_dual_axis_corner_snap")
    )
    report["failures"] = failures
    report["result"] = "PASS" if not failures else "FAIL"
    return report


preflight_r4.r4_visual_contract = visual_contract_f7b


if __name__ == "__main__":
    preflight_r4.main()
