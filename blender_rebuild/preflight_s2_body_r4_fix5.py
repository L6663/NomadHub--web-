"""Fail-fast gate for the R4-F5 flush segmented visual repair."""

import importlib.util
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PREFLIGHT_PATH = SCRIPT_DIR / "preflight_s2_body_r4_fix4.py"
PREFLIGHT_SPEC = importlib.util.spec_from_file_location(
    "nomadhub_s2_r4_f4_preflight", PREFLIGHT_PATH
)
if PREFLIGHT_SPEC is None or PREFLIGHT_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F4 preflight: {PREFLIGHT_PATH}")
preflight4 = importlib.util.module_from_spec(PREFLIGHT_SPEC)
PREFLIGHT_SPEC.loader.exec_module(preflight4)

FIX_PATH = SCRIPT_DIR / "build_s2_body_r4_fix5.py"
FIX_SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix5", FIX_PATH)
if FIX_SPEC is None or FIX_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F5 builder: {FIX_PATH}")
fixed = importlib.util.module_from_spec(FIX_SPEC)
FIX_SPEC.loader.exec_module(fixed)

# Rebind the complete nested preflight stack to the F5 builder. The imported
# F4 wrapper contains the F3 visual contract and the original R4/R3 gates.
preflight3 = preflight4.preflight
preflight_r4 = preflight3.preflight_r4
preflight3.fixed = fixed
preflight3.r4 = fixed.r4
preflight_r4.r4_fixed = fixed
preflight_r4.r4 = fixed.r4
preflight_r4.preflight.fixed = fixed
preflight_r4.preflight.base.r3 = fixed.r4
preflight_r4.preflight.base.builder = fixed.builder
preflight_r4.preflight.base.entry = fixed.entry

ORIGINAL_VISUAL_CONTRACT = preflight_r4.r4_visual_contract


def local_mesh_depth(obj):
    if obj is None or obj.type != "MESH" or not obj.data.vertices:
        return None
    values = [float(vertex.co.x) for vertex in obj.data.vertices]
    return max(values) - min(values)


def ring_world_report(obj, side_sign):
    if obj is None or obj.type != "MESH":
        return None
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    if not points:
        return None
    outward = []
    for point in points:
        surface_y = (
            side_sign * fixed.builder.section_dimensions(float(point.x))[0] / 2.0
        )
        outward.append(side_sign * (float(point.y) - surface_y))
    return {
        "vertex_count": len(points),
        "z_min_m": min(float(point.z) for point in points),
        "z_max_m": max(float(point.z) for point in points),
        "outward_min_m": min(outward),
        "outward_max_m": max(outward),
    }


def visual_contract_f5():
    report = ORIGINAL_VISUAL_CONTRACT()
    failures = list(report["failures"])
    bpy = preflight_r4.preflight.base.bpy

    segmented = {}
    for side, side_sign in (("L", -1.0), ("R", 1.0)):
        for kind in ("RING", "SEAM"):
            name = f"R4_CAB_{kind}_{side}"
            obj = bpy.data.objects.get(name)
            if obj is None:
                failures.append(f"R4-F5 segmented cab surface missing: {name}")
                continue
            if not bool(obj.get("s2_r4_f5_segmented_surface")):
                failures.append(f"R4-F5 segmented marker missing: {name}")
            perimeter_vertices = int(obj.get("s2_r4_f5_perimeter_vertices", 0))
            if perimeter_vertices < 24:
                failures.append(
                    f"R4-F5 perimeter density too low: {name}={perimeter_vertices}"
                )
            geometry = ring_world_report(obj, side_sign)
            segmented[name] = geometry
            if geometry is None:
                failures.append(f"R4-F5 geometry unavailable: {name}")
                continue
            # Ring/seam layers must remain close to the source skin. The old
            # floating frames sat around 42-55 mm outside the body.
            if geometry["outward_max_m"] > 0.026:
                failures.append(
                    f"R4-F5 surface floats outside body: {name} "
                    f"{geometry['outward_max_m']:.4f}m"
                )
            if geometry["outward_min_m"] < -0.016:
                failures.append(
                    f"R4-F5 surface buried too deeply: {name} "
                    f"{geometry['outward_min_m']:.4f}m"
                )
            if kind == "RING" and geometry["z_max_m"] < 2.300:
                failures.append(
                    f"R4-F5 header does not cover source edge: {name} "
                    f"zmax={geometry['z_max_m']:.4f}m"
                )

    windshield = {}
    for name, maximum_depth in (
        ("R4_WINDSHIELD_SURROUND", 0.020),
        ("R4_WINDSHIELD_TRIM", 0.024),
    ):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"R4-F5 windshield surface missing: {name}")
            continue
        if not bool(obj.get("s2_r4_f5_thin_flush_ring")):
            failures.append(f"R4-F5 thin-ring marker missing: {name}")
        depth = local_mesh_depth(obj)
        windshield[name] = {"local_depth_m": depth}
        if depth is None or depth > maximum_depth + 0.001:
            failures.append(
                f"R4-F5 windshield ring too deep: {name} depth={depth}"
            )

    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    if glass is None or not bool(glass.get("s2_r4_f5_flush_inset")):
        failures.append("R4-F5 flush windshield glass marker missing")

    report["r4_f5_segmented_cab_surfaces"] = segmented
    report["r4_f5_windshield_surfaces"] = windshield
    report["failures"] = failures
    report["result"] = "PASS" if not failures else "FAIL"
    return report


preflight_r4.r4_visual_contract = visual_contract_f5


if __name__ == "__main__":
    preflight_r4.main()
