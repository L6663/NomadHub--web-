"""Fail-fast gate for the R4-F8 integration polish."""

import importlib.util
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PREFLIGHT_PATH = SCRIPT_DIR / "preflight_s2_body_r4_fix7b.py"
PREFLIGHT_SPEC = importlib.util.spec_from_file_location(
    "nomadhub_s2_r4_f7b_preflight", PREFLIGHT_PATH
)
if PREFLIGHT_SPEC is None or PREFLIGHT_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F7b preflight: {PREFLIGHT_PATH}")
preflight7b = importlib.util.module_from_spec(PREFLIGHT_SPEC)
PREFLIGHT_SPEC.loader.exec_module(preflight7b)

FIX_PATH = SCRIPT_DIR / "build_s2_body_r4_fix8.py"
FIX_SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix8", FIX_PATH)
if FIX_SPEC is None or FIX_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F8 builder: {FIX_PATH}")
fixed = importlib.util.module_from_spec(FIX_SPEC)
FIX_SPEC.loader.exec_module(fixed)

# Rebind the complete inherited stack to F8. F7's helper-facing module remains
# the original F7 object so its loop finder/constants stay available.
preflight7b.fixed = fixed
preflight7 = preflight7b.preflight7
preflight7.fixed = fixed.f7b.f7
preflight6 = preflight7b.preflight6
preflight6.fixed = fixed
preflight5 = preflight7b.preflight5
preflight5.fixed = fixed
preflight3 = preflight7b.preflight3
preflight3.fixed = fixed
preflight3.r4 = fixed.r4
preflight_r4 = preflight7b.preflight_r4
preflight_r4.r4_fixed = fixed
preflight_r4.r4 = fixed.r4
preflight_r4.preflight.fixed = fixed
preflight_r4.preflight.base.r3 = fixed.r4
preflight_r4.preflight.base.builder = fixed.builder
preflight_r4.preflight.base.entry = fixed.entry

ORIGINAL_VISUAL_CONTRACT = preflight_r4.r4_visual_contract


def visual_contract_f8():
    report = ORIGINAL_VISUAL_CONTRACT()
    failures = list(report["failures"])
    bpy = preflight_r4.preflight.base.bpy

    panels = {}
    expected = {
        "x_min_m": fixed.CAB_PANEL_X_MIN,
        "x_max_m": fixed.CAB_PANEL_X_MAX,
        "z_min_m": fixed.CAB_PANEL_Z_MIN,
        "z_max_m": fixed.CAB_PANEL_Z_MAX,
    }
    for name in ("DOOR_DRIVER_L", "DOOR_PASSENGER_R"):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"R4-F8 cab panel missing: {name}")
            continue
        if not bool(obj.get("s2_r4_f8_integrated_cab_panel")):
            failures.append(f"R4-F8 cab panel marker missing: {name}")
        row = {
            "x_min_m": float(obj.get("s2_r4_f8_panel_x_min_m", 0.0)),
            "x_max_m": float(obj.get("s2_r4_f8_panel_x_max_m", 0.0)),
            "z_min_m": float(obj.get("s2_r4_f8_panel_z_min_m", 0.0)),
            "z_max_m": float(obj.get("s2_r4_f8_panel_z_max_m", 0.0)),
            "horizontal_reveal_m": float(obj.get("s2_r4_f8_horizontal_reveal_m", 0.0)),
            "vertical_reveal_m": float(obj.get("s2_r4_f8_vertical_reveal_m", 0.0)),
            "outer_offset_m": float(obj.get("s2_r4_f8_outer_offset_m", 0.0)),
            "inner_offset_m": float(obj.get("s2_r4_f8_inner_offset_m", 0.0)),
        }
        panels[name] = row
        for key, target in expected.items():
            if abs(row[key] - target) > 0.001:
                failures.append(
                    f"R4-F8 panel bound mismatch {name} {key}={row[key]:.6f}"
                )
        if abs(row["horizontal_reveal_m"] - 0.025) > 0.001:
            failures.append(f"R4-F8 horizontal reveal mismatch: {name}")
        if abs(row["vertical_reveal_m"] - 0.030) > 0.001:
            failures.append(f"R4-F8 vertical reveal mismatch: {name}")
        if row["inner_offset_m"] < 0.035:
            failures.append(f"R4-F8 inner panel face too close to body: {name}")

    trim = bpy.data.objects.get("R4_WINDSHIELD_TRIM")
    trim_report = None
    if trim is None:
        failures.append("R4-F8 windshield trim missing")
    else:
        trim_report = {
            "seal_width_m": float(trim.get("s2_r4_f8_seal_radial_width_m", 0.0)),
            "inner_bottom_width_m": float(trim.get("s2_r4_f8_inner_bottom_width_m", 0.0)),
            "inner_top_width_m": float(trim.get("s2_r4_f8_inner_top_width_m", 0.0)),
            "inner_height_m": float(trim.get("s2_r4_f8_inner_height_m", 0.0)),
        }
        if not bool(trim.get("s2_r4_f8_glass_hugging_seal")):
            failures.append("R4-F8 glass-hugging seal marker missing")
        for key, target in (
            ("seal_width_m", 0.015),
            ("inner_bottom_width_m", 1.700),
            ("inner_top_width_m", 1.740),
            ("inner_height_m", 0.500),
        ):
            if abs(trim_report[key] - target) > 0.001:
                failures.append(
                    f"R4-F8 windshield seal mismatch {key}={trim_report[key]:.6f}"
                )

    report["r4_f8_integrated_cab_panels"] = panels
    report["r4_f8_windshield_seal"] = trim_report
    report["failures"] = failures
    report["result"] = "PASS" if not failures else "FAIL"
    return report


preflight_r4.r4_visual_contract = visual_contract_f8


if __name__ == "__main__":
    preflight_r4.main()
