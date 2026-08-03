"""Strict native/GLB validator for the R4-F9 tight cab reveal repair."""

import importlib.util
from pathlib import Path

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
F8_PATH = SCRIPT_DIR / "validate_s2_body_r4_fix8.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_f8_validator", F8_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F8 validator: {F8_PATH}")
f8 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f8)
base = f8.base

ORIGINAL_VISUAL_REPORT = base.r4_visual_contract_report


def visual_report_f9(label):
    report = ORIGINAL_VISUAL_REPORT(label)
    # F8's panel metadata values describe the wider transitional reveal. F9
    # replaces every panel bound/reveal/offset value but preserves the F8
    # windshield contract and all F7 native-boundary checks.
    failures = [
        failure
        for failure in report["failures"]
        if "R4-F8 panel metadata" not in failure
    ]

    panels = {}
    expected = {
        "s2_r4_f8_panel_x_min_m": -4.388,
        "s2_r4_f8_panel_x_max_m": -3.892,
        "s2_r4_f8_panel_z_min_m": 0.462,
        "s2_r4_f8_panel_z_max_m": 2.158,
        "s2_r4_f8_horizontal_reveal_m": 0.012,
        "s2_r4_f8_vertical_reveal_m": 0.012,
        "s2_r4_f8_outer_offset_m": 0.058,
        "s2_r4_f8_inner_offset_m": 0.050,
        "s2_r4_f9_reveal_m": 0.012,
        "s2_r4_f9_shell_thickness_m": 0.008,
        "s2_r4_f9_outer_offset_m": 0.058,
        "s2_r4_f9_inner_offset_m": 0.050,
    }
    for name in ("DOOR_DRIVER_L", "DOOR_PASSENGER_R"):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{label}: R4-F9 cab panel missing {name}")
            continue
        if not bool(obj.get("s2_r4_f9_tight_reveal_panel")):
            failures.append(f"{label}: R4-F9 panel marker missing {name}")
        row = {}
        for key, target in expected.items():
            actual = float(obj.get(key, 0.0))
            row[key] = actual
            if abs(actual - target) > 0.001:
                failures.append(
                    f"{label}: R4-F9 panel metadata {name} {key}={actual:.6f}"
                )
        panels[name] = row

    seals = {}
    for name in ("R4_CAB_SEAM_L", "R4_CAB_SEAM_R"):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{label}: R4-F9 cab seal missing {name}")
            continue
        if not bool(obj.get("s2_r4_f9_tight_reveal_seal")):
            failures.append(f"{label}: R4-F9 tight-seal marker missing {name}")
        row = {
            "seal_width_m": float(obj.get("s2_r4_f9_seal_width_m", 0.0)),
            "panel_gap_m": float(obj.get("s2_r4_f9_panel_gap_m", 0.0)),
        }
        seals[name] = row
        if abs(row["seal_width_m"] - 0.009) > 0.001:
            failures.append(f"{label}: R4-F9 seal width mismatch {name}")
        if abs(row["panel_gap_m"] - 0.006) > 0.001:
            failures.append(f"{label}: R4-F9 panel gap mismatch {name}")

    report["r4_f9_tight_cab_panels"] = panels
    report["r4_f9_tight_cab_seals"] = seals
    report["failures"] = failures
    report["result"] = "PASS" if not failures else "FAIL"
    return report


base.r4_visual_contract_report = visual_report_f9


if __name__ == "__main__":
    base.main()
