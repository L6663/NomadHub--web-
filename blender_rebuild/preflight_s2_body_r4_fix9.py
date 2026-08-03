"""Fail-fast gate for the R4-F9 tight cab reveal repair."""

import importlib.util
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PREFLIGHT_PATH = SCRIPT_DIR / "preflight_s2_body_r4_fix8.py"
PREFLIGHT_SPEC = importlib.util.spec_from_file_location(
    "nomadhub_s2_r4_f8_preflight", PREFLIGHT_PATH
)
if PREFLIGHT_SPEC is None or PREFLIGHT_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F8 preflight: {PREFLIGHT_PATH}")
preflight8 = importlib.util.module_from_spec(PREFLIGHT_SPEC)
PREFLIGHT_SPEC.loader.exec_module(preflight8)

FIX_PATH = SCRIPT_DIR / "build_s2_body_r4_fix9.py"
FIX_SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix9", FIX_PATH)
if FIX_SPEC is None or FIX_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F9 builder: {FIX_PATH}")
fixed = importlib.util.module_from_spec(FIX_SPEC)
FIX_SPEC.loader.exec_module(fixed)

# Rebind the complete inherited F8/F7b/F7/F6/F5/F3/R4/R3 stack to F9.
preflight8.fixed = fixed
preflight7b = preflight8.preflight7b
preflight7b.fixed = fixed
preflight7 = preflight8.preflight7
preflight7.fixed = fixed.f7
preflight6 = preflight8.preflight6
preflight6.fixed = fixed
preflight5 = preflight8.preflight5
preflight5.fixed = fixed
preflight3 = preflight8.preflight3
preflight3.fixed = fixed
preflight3.r4 = fixed.r4
preflight_r4 = preflight8.preflight_r4
preflight_r4.r4_fixed = fixed
preflight_r4.r4 = fixed.r4
preflight_r4.preflight.fixed = fixed
preflight_r4.preflight.base.r3 = fixed.r4
preflight_r4.preflight.base.builder = fixed.builder
preflight_r4.preflight.base.entry = fixed.entry

ORIGINAL_VISUAL_CONTRACT = preflight_r4.r4_visual_contract


def visual_contract_f9():
    report = ORIGINAL_VISUAL_CONTRACT()
    # F8 hard-coded the transitional 25/30 mm reveal. F9 intentionally tightens
    # both to 12 mm; retain every other inherited check.
    failures = [
        failure
        for failure in report["failures"]
        if not (
            "R4-F8 horizontal reveal mismatch" in failure
            or "R4-F8 vertical reveal mismatch" in failure
        )
    ]
    bpy = preflight_r4.preflight.base.bpy

    panels = {}
    for name in ("DOOR_DRIVER_L", "DOOR_PASSENGER_R"):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"R4-F9 cab panel missing: {name}")
            continue
        if not bool(obj.get("s2_r4_f9_tight_reveal_panel")):
            failures.append(f"R4-F9 panel marker missing: {name}")
        row = {
            "x_min_m": float(obj.get("s2_r4_f8_panel_x_min_m", 0.0)),
            "x_max_m": float(obj.get("s2_r4_f8_panel_x_max_m", 0.0)),
            "z_min_m": float(obj.get("s2_r4_f8_panel_z_min_m", 0.0)),
            "z_max_m": float(obj.get("s2_r4_f8_panel_z_max_m", 0.0)),
            "reveal_m": float(obj.get("s2_r4_f9_reveal_m", 0.0)),
            "shell_thickness_m": float(obj.get("s2_r4_f9_shell_thickness_m", 0.0)),
            "outer_offset_m": float(obj.get("s2_r4_f9_outer_offset_m", 0.0)),
            "inner_offset_m": float(obj.get("s2_r4_f9_inner_offset_m", 0.0)),
        }
        panels[name] = row
        for key, target in (
            ("x_min_m", fixed.CAB_PANEL_X_MIN),
            ("x_max_m", fixed.CAB_PANEL_X_MAX),
            ("z_min_m", fixed.CAB_PANEL_Z_MIN),
            ("z_max_m", fixed.CAB_PANEL_Z_MAX),
            ("reveal_m", fixed.CAB_PANEL_REVEAL_M),
            ("shell_thickness_m", fixed.CAB_PANEL_THICKNESS_M),
            ("outer_offset_m", fixed.CAB_PANEL_OUTER_OFFSET_M),
            ("inner_offset_m", fixed.CAB_PANEL_INNER_OFFSET_M),
        ):
            if abs(row[key] - target) > 0.001:
                failures.append(
                    f"R4-F9 panel mismatch {name} {key}={row[key]:.6f}"
                )

    seals = {}
    for name in ("R4_CAB_SEAM_L", "R4_CAB_SEAM_R"):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"R4-F9 cab seal missing: {name}")
            continue
        if not bool(obj.get("s2_r4_f9_tight_reveal_seal")):
            failures.append(f"R4-F9 tight-seal marker missing: {name}")
        row = {
            "seal_width_m": float(obj.get("s2_r4_f9_seal_width_m", 0.0)),
            "panel_gap_m": float(obj.get("s2_r4_f9_panel_gap_m", 0.0)),
        }
        seals[name] = row
        if abs(row["seal_width_m"] - fixed.CAB_SEAL_WIDTH_M) > 0.001:
            failures.append(f"R4-F9 seal width mismatch: {name}")
        if abs(row["panel_gap_m"] - 0.006) > 0.001:
            failures.append(f"R4-F9 panel gap mismatch: {name}")

    report["r4_f9_tight_cab_panels"] = panels
    report["r4_f9_tight_cab_seals"] = seals
    report["failures"] = failures
    report["result"] = "PASS" if not failures else "FAIL"
    return report


preflight_r4.r4_visual_contract = visual_contract_f9


if __name__ == "__main__":
    preflight_r4.main()
