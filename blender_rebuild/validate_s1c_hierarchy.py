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


def iter_nla_tracks():
    for obj in bpy.data.objects:
        animation_data = obj.animation_data
        if animation_data is None:
            continue
        for track in animation_data.nla_tracks:
            yield obj, track


def snapshot_nla_state():
    return [
        (track, bool(track.is_solo), bool(track.mute))
        for _, track in iter_nla_tracks()
    ]


def restore_nla_state(snapshot):
    for track, is_solo, mute in snapshot:
        track.is_solo = is_solo
        track.mute = mute
    bpy.context.view_layer.update()


def activate_imported_animation(track_name):
    """Replicate Blender glTF importer's NLA Solo workflow.

    Blender imports only the first glTF animation as the automatically playing
    animation. Remaining animations are stashed on NLA tracks and must be
    selected by soloing every track with the matching glTF animation name.
    """
    matched = 0
    for _, track in iter_nla_tracks():
        selected = track.name == track_name
        track.is_solo = selected
        track.mute = False
        if selected:
            matched += 1
    bpy.context.view_layer.update()
    return matched


def candidate_track_names(root):
    animation_data = root.animation_data
    if animation_data is None:
        return []
    return list(dict.fromkeys(track.name for track in animation_data.nla_tracks))


def sample_world_location(obj, frame):
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    return obj.matrix_world.translation.copy()


def select_best_animation(root_name, moving_name):
    root = bpy.data.objects.get(root_name)
    moving = bpy.data.objects.get(moving_name)
    if root is None or moving is None:
        return {
            "mode": "missing",
            "track_name": None,
            "matched_tracks": 0,
            "closed": None,
            "opened": None,
            "delta_m": 0.0,
            "candidates": [],
        }

    snapshot = snapshot_nla_state()
    candidates = []
    try:
        closed = sample_world_location(moving, 1)
        opened = sample_world_location(moving, 48)
        candidates.append(
            {
                "mode": "current",
                "track_name": None,
                "matched_tracks": 0,
                "closed": closed,
                "opened": opened,
                "delta_m": (opened - closed).length,
            }
        )

        for track_name in candidate_track_names(root):
            matched = activate_imported_animation(track_name)
            closed = sample_world_location(moving, 1)
            opened = sample_world_location(moving, 48)
            candidates.append(
                {
                    "mode": "nla_solo",
                    "track_name": track_name,
                    "matched_tracks": matched,
                    "closed": closed,
                    "opened": opened,
                    "delta_m": (opened - closed).length,
                }
            )
    finally:
        restore_nla_state(snapshot)
        bpy.context.scene.frame_set(1)

    best = max(candidates, key=lambda item: item["delta_m"])
    return {
        "mode": best["mode"],
        "track_name": best["track_name"],
        "matched_tracks": best["matched_tracks"],
        "closed": best["closed"],
        "opened": best["opened"],
        "delta_m": best["delta_m"],
        "candidates": [
            {
                "mode": item["mode"],
                "track_name": item["track_name"],
                "matched_tracks": item["matched_tracks"],
                "delta_m": item["delta_m"],
            }
            for item in candidates
        ],
    }


def apply_selection(selection):
    if selection["mode"] == "nla_solo" and selection["track_name"]:
        return activate_imported_animation(selection["track_name"])
    return 0


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


def collision_sweep(selections):
    scene = bpy.context.scene
    collisions = []
    missing = []
    checked_pairs = 0
    per_animation = {}
    snapshot = snapshot_nla_state()

    try:
        for glass_name, root_name in EXPECTED.items():
            glass_obj = bpy.data.objects.get(glass_name)
            if glass_obj is None:
                missing.append(glass_name)
                continue
            selection = selections.get(glass_name)
            if selection is None:
                missing.append(f"animation-selection:{glass_name}")
                continue

            apply_selection(selection)
            animation_checks = 0
            animation_collisions = []
            for frame in ANIMATION_SAMPLE_FRAMES:
                scene.frame_set(frame)
                bpy.context.view_layer.update()
                depsgraph = bpy.context.evaluated_depsgraph_get()
                glass_bvh = world_bvh(glass_obj, depsgraph)
                if glass_bvh is None:
                    continue

                for static_name in STATIC_COLLISION_OBJECTS:
                    static_obj = bpy.data.objects.get(static_name)
                    if static_obj is None:
                        missing.append(static_name)
                        continue
                    static_bvh = world_bvh(static_obj, depsgraph)
                    if static_bvh is None:
                        continue
                    checked_pairs += 1
                    animation_checks += 1
                    overlap = glass_bvh.overlap(static_bvh)
                    if overlap:
                        collision = {
                            "frame": frame,
                            "root": root_name,
                            "animation_mode": selection["mode"],
                            "track_name": selection["track_name"],
                            "moving_glass": glass_name,
                            "static_mesh": static_name,
                            "triangle_overlap_pairs": len(overlap),
                        }
                        collisions.append(collision)
                        animation_collisions.append(collision)

            per_animation[glass_name] = {
                "root": root_name,
                "mode": selection["mode"],
                "track_name": selection["track_name"],
                "matched_tracks": selection["matched_tracks"],
                "checked_pairs": animation_checks,
                "collisions": animation_collisions,
                "result": "PASS" if not animation_collisions else "FAIL",
            }
    finally:
        restore_nla_state(snapshot)
        scene.frame_set(1)

    return {
        "sample_frames": list(ANIMATION_SAMPLE_FRAMES),
        "checked_pairs": checked_pairs,
        "per_animation": per_animation,
        "missing_objects": sorted(set(missing)),
        "collisions": collisions,
        "result": "PASS" if not collisions and not missing else "FAIL",
    }


def collect(label):
    scene = bpy.context.scene
    failures = []
    entries = {}
    selections = {}

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

        selection = select_best_animation(parent_name, glass_name)
        selections[glass_name] = selection
        entries[glass_name] = {
            "parent": actual_parent,
            "animation_mode": selection["mode"],
            "track_name": selection["track_name"],
            "matched_tracks": selection["matched_tracks"],
            "closed_world_location": list(selection["closed"])
            if selection["closed"] is not None
            else None,
            "open_world_location": list(selection["opened"])
            if selection["opened"] is not None
            else None,
            "translation_delta_m": selection["delta_m"],
            "candidate_tracks": selection["candidates"],
        }
        if selection["delta_m"] < MIN_OPEN_TRANSLATION_M:
            failures.append(
                f"{glass_name} animation delta {selection['delta_m']:.6f} "
                f"< {MIN_OPEN_TRANSLATION_M:.3f}"
            )

    for name in FORBIDDEN_STATIC:
        if bpy.data.objects.get(name) is not None:
            failures.append(f"obsolete static glass remains: {name}")

    sweep = collision_sweep(selections)
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
