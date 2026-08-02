"""Blender 4.2 measurement adapter for the S2-R1 validator.

The base validator is intentionally kept unchanged. This adapter corrects two
Blender-specific measurement semantics:
1. Converted wheel-arch meshes keep a world-origin object transform, so their
   frozen X coordinate must be measured from geometry bounds, not object origin.
2. Source-cage envelope checks must read raw mesh vertices, not an object
   bounding box that can reflect evaluated modifier state.
"""

import sys
import traceback
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import validate_s2_continuous_body as base


def raw_mesh_bounds(obj):
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    if not points:
        raise RuntimeError(f"{obj.name} has no source vertices")
    return {
        "x_min": min(point.x for point in points),
        "x_max": max(point.x for point in points),
        "y_min": min(point.y for point in points),
        "y_max": max(point.y for point in points),
        "z_min": min(point.z for point in points),
        "z_max": max(point.z for point in points),
    }


def blender42_object_bounds(obj, evaluated=False):
    if evaluated:
        depsgraph = base.bpy.context.evaluated_depsgraph_get()
        evaluated_obj = obj.evaluated_get(depsgraph)
        mesh = evaluated_obj.to_mesh()
        try:
            points = [evaluated_obj.matrix_world @ vertex.co for vertex in mesh.vertices]
        finally:
            evaluated_obj.to_mesh_clear()
        if not points:
            raise RuntimeError(f"{obj.name} has no evaluated vertices")
        return {
            "x_min": min(point.x for point in points),
            "x_max": max(point.x for point in points),
            "y_min": min(point.y for point in points),
            "y_max": max(point.y for point in points),
            "z_min": min(point.z for point in points),
            "z_max": max(point.z for point in points),
        }
    return raw_mesh_bounds(obj)


def geometry_center_x(obj):
    bounds = raw_mesh_bounds(obj)
    return (bounds["x_min"] + bounds["x_max"]) / 2.0


def blender42_validate_frozen_positions(failures):
    results = {}
    groups = (
        ("wheels", base.EXPECTED_WHEELS, "origin"),
        ("arches", base.EXPECTED_ARCHES, "geometry_center"),
        ("hatches", base.EXPECTED_HATCHES, "origin"),
        ("doors", base.EXPECTED_DOORS, "origin"),
    )
    for group_name, expected, measurement in groups:
        group = {}
        for name, expected_x in expected.items():
            obj = base.bpy.data.objects.get(name)
            if obj is None:
                failures.append(f"frozen object missing: {name}")
                continue
            actual_x = (
                geometry_center_x(obj)
                if measurement == "geometry_center"
                else base.world_x(obj)
            )
            group[name] = actual_x
            if abs(actual_x - expected_x) > base.POSITION_TOLERANCE_M:
                failures.append(
                    f"{name} x={actual_x:.6f}, expected {expected_x:.6f}"
                )
        results[group_name] = group

    if all(name in results["wheels"] for name in base.EXPECTED_WHEELS):
        left = (
            results["wheels"]["WHEEL_RL_ROOT"]
            - results["wheels"]["WHEEL_FL_ROOT"]
        )
        right = (
            results["wheels"]["WHEEL_RR_ROOT"]
            - results["wheels"]["WHEEL_FR_ROOT"]
        )
        results["wheelbase_left_m"] = left
        results["wheelbase_right_m"] = right
        if abs(left - 5.150) > base.POSITION_TOLERANCE_M:
            failures.append(f"left wheelbase {left:.6f} != 5.150")
        if abs(right - 5.150) > base.POSITION_TOLERANCE_M:
            failures.append(f"right wheelbase {right:.6f} != 5.150")
    return results


base.object_bounds = blender42_object_bounds
base.validate_frozen_positions = blender42_validate_frozen_positions


if __name__ == "__main__":
    try:
        base.main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
