import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils.bvhtree import BVHTree


EXPECTED = {
    "DOOR_DRIVER_L_GLASS": "DOOR_DRIVER_L_ROOT",
    "DOOR_PASSENGER_R_GLASS": "DOOR_PASSENGER_R_ROOT",
    "DOOR_LIVING_R_GLASS": "DOOR_LIVING_R_ROOT",
}
FORBIDDEN_STATIC = (
    "GLASS_CAB_L",
    "GLASS_CAB_R",
    "GLASS_LIVING_R_02",
)
MIN_OPEN_TRANSLATION_M = 0.10
ANIMATION_SAMPLE_FRAMES = (1, 12, 24, 36, 48, 60, 72, 84, 96)
STATIC_COLLISION_OBJECTS = (
    "BODY_MAIN",
    "BODY_CAB",
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


def parse_args():
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(raw)


def world_bvh(obj, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        if not mesh.vertices or not mesh.polygons:
            return None
        vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        polygons = [tuple(polygon.vertices) for polygon in mesh.polygons]
        return BVHTree.FromPolygons(
            vertices,
            polygons,
            all_triangles=False,
            epsilon=1e-6,
        )
    finally:
        evaluated.to_mesh_clear()


def collision_sweep():
    scene = bpy.context.scene
    collisions = []
    missing = []
    checked_pairs = 0

    for frame in ANIMATION_SAMPLE_FRAMES:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()

        static_bvhs = {}
        for static_name in STATIC_COLLISION_OBJECTS:
            static_obj = bpy.data.objects.get(static_name)
            if static_obj is None:
                missing.append(static_name)
                continue
            static_bvhs[static_name] = world_bvh(static_obj, depsgraph)

        for glass_name in EXPECTED:
            glass_obj = bpy.data.objects.get(glass_name)
            if glass_obj is None:
                missing.append(glass_name)
                continue
            glass_bvh = world_bvh(glass_obj, depsgraph)
            if glass_bvh is None:
                continue
            for static_name, static_bvh in static_bvhs.items():
                if static_bvh is None:
                    continue
                checked_pairs += 1
                overlap = glass_bvh.overlap(static_bvh)
                if overlap:
                    collisions.append(
                        {
                            "frame": frame,
                            "moving_glass": glass_name,
                            "static_mesh": static_name,
                            "triangle_overlap_pairs": len(overlap),
                        }
                    )

    scene.frame_set(1)
    return {
        "sample_frames": list(ANIMATION_SAMPLE_FRAMES),
        "checked_pairs": checked_pairs,
        "missing_objects": sorted(set(missing)),
        "collisions": collisions,
        "result": "PASS" if not collisions and not missing else "FAIL",
    }


def collect(label):
    scene = bpy.context.scene
    failures = []
    entries = {}

    scene.frame_set(1)
    bpy.context.view_layer.update()
    closed_locations = {}
    for glass_name, parent_name in EXPECTED.items():
        obj = bpy.data.objects.get(glass_name)
        if obj is None:
            failures.append(f"{glass_name} missing")
            continue
        actual_parent = obj.parent.name if obj.parent else None
        if actual_parent != parent_name:
            failures.append(
                f"{glass_name} parent={actual_parent}, expected {parent_name}"
            )
        closed_locations[glass_name] = obj.matrix_world.translation.copy()
        entries[glass_name] = {
            "parent": actual_parent,
            "closed_world_location": list(obj.matrix_world.translation),
        }

    for name in FORBIDDEN_STATIC:
        if bpy.data.objects.get(name) is not None:
            failures.append(f"obsolete static glass remains: {name}")

    scene.frame_set(48)
    bpy.context.view_layer.update()
    for glass_name in EXPECTED:
        obj = bpy.data.objects.get(glass_name)
        if obj is None or glass_name not in closed_locations:
            continue
        opened = obj.matrix_world.translation.copy()
        delta = (opened - closed_locations[glass_name]).length
        entries[glass_name]["open_world_location"] = list(opened)
        entries[glass_name]["translation_delta_m"] = delta
        if delta < MIN_OPEN_TRANSLATION_M:
            failures.append(
                f"{glass_name} animation delta {delta:.6f} < {MIN_OPEN_TRANSLATION_M:.3f}"
            )

    sweep = collision_sweep()
    for missing_name in sweep["missing_objects"]:
        failures.append(f"glass collision sweep object missing: {missing_name}")
    for collision in sweep["collisions"]:
        failures.append(
            "door-glass collision "
            f"frame={collision['frame']} glass={collision['moving_glass']} "
            f"static={collision['static_mesh']} "
            f"pairs={collision['triangle_overlap_pairs']}"
        )

    scene.frame_set(1)
    return {
        "label": label,
        "entries": entries,
        "forbidden_static_absent": all(
            bpy.data.objects.get(name) is None for name in FORBIDDEN_STATIC
        ),
        "animation_collision_sweep": sweep,
        "failures": failures,
        "result": "PASS" if not failures else "FAIL",
    }


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def main():
    args = parse_args()
    blend_result = collect("blend")

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=args.glb)
    glb_result = collect("glb_roundtrip")

    failures = blend_result["failures"] + glb_result["failures"]
    report_path = Path(args.report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["door_glass_hierarchy"] = {
        "blend": blend_result,
        "glb_roundtrip": glb_result,
        "result": "PASS" if not failures else "FAIL",
    }
    if failures:
        report["result"] = "FAIL"
        report["s2_ready"] = False
        report.setdefault("failures", []).extend(failures)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report["door_glass_hierarchy"], ensure_ascii=False))
    if failures:
        raise RuntimeError("S1C door-glass hierarchy validation failed")


if __name__ == "__main__":
    main()
