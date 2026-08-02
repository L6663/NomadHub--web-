import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


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


def parse_args():
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(raw)


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

    scene.frame_set(1)
    return {
        "label": label,
        "entries": entries,
        "forbidden_static_absent": all(
            bpy.data.objects.get(name) is None for name in FORBIDDEN_STATIC
        ),
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
