"""Strict native/GLB validator for the R4-F5 flush segmented repair."""

import importlib.util
from pathlib import Path

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
F3_PATH = SCRIPT_DIR / "validate_s2_body_r4_fix3.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_f3_validator", F3_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F3 validator: {F3_PATH}")
f3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f3)
base = f3.base

ORIGINAL_VISUAL_REPORT = base.r4_visual_contract_report


def local_mesh_depth(obj):
    if obj is None or obj.type != "MESH" or not obj.data.vertices:
        return None
    values = [float(vertex.co.x) for vertex in obj.data.vertices]
    return max(values) - min(values)


def visual_report_f5(label):
    report = ORIGINAL_VISUAL_REPORT(label)
    failures = list(report["failures"])

    segmented = []
    for name in (
        "R4_CAB_RING_L",
        "R4_CAB_RING_R",
        "R4_CAB_SEAM_L",
        "R4_CAB_SEAM_R",
    ):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{label}: R4-F5 segmented surface missing {name}")
            continue
        if not bool(obj.get("s2_r4_f5_segmented_surface")):
            failures.append(f"{label}: R4-F5 segmented marker missing {name}")
        if not bool(obj.get("s2_r4_f5_source_boundary_cover")):
            failures.append(f"{label}: R4-F5 boundary-cover marker missing {name}")
        perimeter_vertices = int(obj.get("s2_r4_f5_perimeter_vertices", 0))
        if perimeter_vertices < 24:
            failures.append(
                f"{label}: R4-F5 perimeter density too low {name}={perimeter_vertices}"
            )
        segmented.append(name)

    windshield = {}
    for name, maximum_depth in (
        ("R4_WINDSHIELD_SURROUND", 0.020),
        ("R4_WINDSHIELD_TRIM", 0.024),
    ):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{label}: R4-F5 windshield surface missing {name}")
            continue
        if not bool(obj.get("s2_r4_f5_thin_flush_ring")):
            failures.append(f"{label}: R4-F5 thin-ring marker missing {name}")
        depth = local_mesh_depth(obj)
        windshield[name] = depth
        if depth is None or depth > maximum_depth + 0.001:
            failures.append(
                f"{label}: R4-F5 windshield ring depth {name}={depth}"
            )

    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    if glass is None or not bool(glass.get("s2_r4_f5_flush_inset")):
        failures.append(f"{label}: R4-F5 flush glass marker missing")

    report["r4_f5_segmented_surfaces"] = segmented
    report["r4_f5_windshield_local_depth_m"] = windshield
    report["failures"] = failures
    report["result"] = "PASS" if not failures else "FAIL"
    return report


base.r4_visual_contract_report = visual_report_f5


if __name__ == "__main__":
    base.main()
