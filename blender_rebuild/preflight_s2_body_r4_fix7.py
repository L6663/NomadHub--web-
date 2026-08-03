"""Fail-fast gate for the R4-F7 native opening-boundary repair."""

import importlib.util
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PREFLIGHT_PATH = SCRIPT_DIR / "preflight_s2_body_r4_fix6.py"
PREFLIGHT_SPEC = importlib.util.spec_from_file_location(
    "nomadhub_s2_r4_f6_preflight", PREFLIGHT_PATH
)
if PREFLIGHT_SPEC is None or PREFLIGHT_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F6 preflight: {PREFLIGHT_PATH}")
preflight6 = importlib.util.module_from_spec(PREFLIGHT_SPEC)
PREFLIGHT_SPEC.loader.exec_module(preflight6)

FIX_PATH = SCRIPT_DIR / "build_s2_body_r4_fix7.py"
FIX_SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix7", FIX_PATH)
if FIX_SPEC is None or FIX_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F7 builder: {FIX_PATH}")
fixed = importlib.util.module_from_spec(FIX_SPEC)
FIX_SPEC.loader.exec_module(fixed)

# Rebind the nested F6/F5/F3/R4/R3 stack to F7.
preflight6.fixed = fixed
preflight5 = preflight6.preflight5
preflight5.fixed = fixed
preflight3 = preflight6.preflight3
preflight3.fixed = fixed
preflight3.r4 = fixed.r4
preflight_r4 = preflight6.preflight_r4
preflight_r4.r4_fixed = fixed
preflight_r4.r4 = fixed.r4
preflight_r4.preflight.fixed = fixed
preflight_r4.preflight.base.r3 = fixed.r4
preflight_r4.preflight.base.builder = fixed.builder
preflight_r4.preflight.base.entry = fixed.entry

ORIGINAL_VISUAL_CONTRACT = preflight_r4.r4_visual_contract


def cab_boundary_geometry(body):
    rows = []
    try:
        matches = fixed.find_cab_components(body.data)
    except RuntimeError as exc:
        return {"rows": [], "failures": [str(exc)], "result": "FAIL"}

    failures = []
    for component, bounds in matches:
        side = "L" if bounds["y_mean"] < 0 else "R"
        row = {
            "side": side,
            "x_min_m": bounds["x_min"],
            "x_max_m": bounds["x_max"],
            "z_min_m": bounds["z_min"],
            "z_max_m": bounds["z_max"],
            "vertex_count": bounds["vertex_count"],
        }
        rows.append(row)
        for key, actual, expected in (
            ("x_min", bounds["x_min"], fixed.CAB_X_MIN),
            ("x_max", bounds["x_max"], fixed.CAB_X_MAX),
            ("z_min", bounds["z_min"], fixed.CAB_Z_MIN),
            ("z_max", bounds["z_max"], fixed.CAB_Z_MAX),
        ):
            if abs(actual - expected) > 0.002:
                failures.append(
                    f"R4-F7 {side} cab boundary {key}={actual:.6f} != {expected:.6f}"
                )
    return {"rows": rows, "failures": failures, "result": "PASS" if not failures else "FAIL"}


def visual_contract_f7():
    report = ORIGINAL_VISUAL_CONTRACT()
    # F5/F6 deliberately validated their broad visible ring/header geometry.
    # F7 replaces those parts with tiny exported compatibility markers, so only
    # those superseded geometry-position failures are removed here.
    failures = []
    for failure in report["failures"]:
        obsolete = (
            ("R4-F5 surface" in failure and "R4_CAB_RING_" in failure)
            or "R4-F6 cab header does not span source ripple" in failure
            or "R4-F6 cab header floats outside body" in failure
            or "R4-F6 cab header buried too deeply" in failure
        )
        if not obsolete:
            failures.append(failure)

    bpy = preflight_r4.preflight.base.bpy
    body = bpy.data.objects.get(preflight_r4.preflight.base.validator.BODY_NAME)
    boundary = {"rows": [], "failures": ["R4-F7 body missing"], "result": "FAIL"}
    if body is not None:
        if not bool(body.get("s2_r4_f7_native_cab_boundary_repair")):
            failures.append("R4-F7 native cab-boundary marker missing")
        if int(body.get("s2_r4_f7_cab_boundary_count", 0)) != 2:
            failures.append("R4-F7 native cab-boundary count is not two")
        boundary = cab_boundary_geometry(body)
        failures.extend(boundary["failures"])

    hidden = []
    for name in (
        "R4_CAB_RING_L",
        "R4_CAB_RING_R",
        "R4_CAB_HEADER_L",
        "R4_CAB_HEADER_R",
        "R4_WINDSHIELD_SURROUND",
    ):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"R4-F7 compatibility marker missing: {name}")
            continue
        if not bool(obj.get("s2_r4_f7_hidden_compatibility_marker")):
            failures.append(f"R4-F7 hidden marker flag missing: {name}")
        if max(abs(float(value)) for value in obj.scale) > 0.002:
            failures.append(f"R4-F7 compatibility marker remains visually large: {name}")
        hidden.append(name)

    visible_seals = []
    for name in ("R4_CAB_SEAM_L", "R4_CAB_SEAM_R", "R4_WINDSHIELD_TRIM"):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"R4-F7 visible native-opening seal missing: {name}")
            continue
        if not bool(obj.get("s2_r4_f7_native_opening_seal")):
            failures.append(f"R4-F7 native-opening seal marker missing: {name}")
        if max(abs(float(value)) for value in obj.scale) < 0.5:
            failures.append(f"R4-F7 visible seal was accidentally buried: {name}")
        visible_seals.append(name)

    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    if glass is None or not bool(glass.get("s2_r4_f7_native_opening_glass")):
        failures.append("R4-F7 native-opening windshield glass marker missing")

    report["r4_f7_native_cab_boundaries"] = boundary
    report["r4_f7_hidden_compatibility_markers"] = hidden
    report["r4_f7_visible_opening_seals"] = visible_seals
    report["failures"] = failures
    report["result"] = "PASS" if not failures else "FAIL"
    return report


preflight_r4.r4_visual_contract = visual_contract_f7


if __name__ == "__main__":
    preflight_r4.main()
