"""Strict native/GLB validator for the R4-F8 integration polish."""

import importlib.util
from pathlib import Path

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
F7_PATH = SCRIPT_DIR / "validate_s2_body_r4_fix7.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_f7_validator", F7_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F7 validator: {F7_PATH}")
f7 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f7)
base = f7.base

ORIGINAL_VISUAL_REPORT = base.r4_visual_contract_report


def visual_report_f8(label):
    report = ORIGINAL_VISUAL_REPORT(label)
    # F7 intentionally changed the cab-seam role from the transitional F2 role
    # to a native-opening seal. Remove only that obsolete metadata assertion.
    failures = [
        failure
        for failure in report["failures"]
        if "R4-F2 role mismatch R4_CAB_SEAM_" not in failure
    ]

    panels = {}
    expected = {
        "s2_r4_f8_panel_x_min_m": -4.375,
        "s2_r4_f8_panel_x_max_m": -3.905,
        "s2_r4_f8_panel_z_min_m": 0.480,
        "s2_r4_f8_panel_z_max_m": 2.140,
        "s2_r4_f8_horizontal_reveal_m": 0.025,
        "s2_r4_f8_vertical_reveal_m": 0.030,
        "s2_r4_f8_outer_offset_m": 0.060,
        "s2_r4_f8_inner_offset_m": 0.040,
    }
    for name in ("DOOR_DRIVER_L", "DOOR_PASSENGER_R"):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{label}: R4-F8 cab panel missing {name}")
            continue
        if not bool(obj.get("s2_r4_f8_integrated_cab_panel")):
            failures.append(f"{label}: R4-F8 cab panel marker missing {name}")
        row = {}
        for key, target in expected.items():
            actual = float(obj.get(key, 0.0))
            row[key] = actual
            if abs(actual - target) > 0.001:
                failures.append(
                    f"{label}: R4-F8 panel metadata {name} {key}={actual:.6f}"
                )
        panels[name] = row

    trim = bpy.data.objects.get("R4_WINDSHIELD_TRIM")
    trim_report = None
    if trim is None:
        failures.append(f"{label}: R4-F8 windshield trim missing")
    else:
        if not bool(trim.get("s2_r4_f8_glass_hugging_seal")):
            failures.append(f"{label}: R4-F8 glass-hugging seal marker missing")
        trim_report = {
            "seal_width_m": float(trim.get("s2_r4_f8_seal_radial_width_m", 0.0)),
            "inner_bottom_width_m": float(trim.get("s2_r4_f8_inner_bottom_width_m", 0.0)),
            "inner_top_width_m": float(trim.get("s2_r4_f8_inner_top_width_m", 0.0)),
            "inner_height_m": float(trim.get("s2_r4_f8_inner_height_m", 0.0)),
        }
        for key, target in (
            ("seal_width_m", 0.015),
            ("inner_bottom_width_m", 1.700),
            ("inner_top_width_m", 1.740),
            ("inner_height_m", 0.500),
        ):
            if abs(trim_report[key] - target) > 0.001:
                failures.append(
                    f"{label}: R4-F8 windshield seal {key}={trim_report[key]:.6f}"
                )

    report["r4_f8_integrated_cab_panels"] = panels
    report["r4_f8_windshield_seal"] = trim_report
    report["failures"] = failures
    report["result"] = "PASS" if not failures else "FAIL"
    return report


base.r4_visual_contract_report = visual_report_f8


if __name__ == "__main__":
    base.main()
