import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


EXPECTED_WHEELS = {
    "WHEEL_FL_ROOT": -3.245,
    "WHEEL_FR_ROOT": -3.245,
    "WHEEL_RL_ROOT": 1.905,
    "WHEEL_RR_ROOT": 1.905,
}
EXPECTED_ARCHES = {
    "WHEEL_ARCH_FL": -3.245,
    "WHEEL_ARCH_FR": -3.245,
    "WHEEL_ARCH_RL": 1.905,
    "WHEEL_ARCH_RR": 1.905,
}
EXPECTED_HATCHES = {
    "HATCH_L_1_ROOT": -1.95,
    "HATCH_L_2_ROOT": 0.35,
    "HATCH_L_3_ROOT": 3.05,
    "HATCH_R_1_ROOT": -1.95,
    "HATCH_R_2_ROOT": 0.75,
    "HATCH_R_3_ROOT": 3.05,
}
EXPECTED_ANIMATION_ROOTS = (
    "DOOR_DRIVER_L_ROOT",
    "DOOR_PASSENGER_R_ROOT",
    "DOOR_LIVING_R_ROOT",
    "HATCH_L_1_ROOT",
    "HATCH_L_2_ROOT",
    "HATCH_L_3_ROOT",
    "HATCH_R_1_ROOT",
    "HATCH_R_2_ROOT",
    "HATCH_R_3_ROOT",
    "WHEEL_FL_ROOT",
    "WHEEL_FR_ROOT",
    "WHEEL_RL_ROOT",
    "WHEEL_RR_ROOT",
)
TOLERANCE_M = 0.002
MIN_WHEEL_ARCH_CLEARANCE_M = 0.080
MIN_DOOR_SEAM_CLEARANCE_M = 0.060


def parse_args():
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", required=True)
    parser.add_argument("--clearance", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(raw)


def world_x(obj):
    return float(obj.matrix_world.translation.x)


def bounds_x(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return min(v.x for v in corners), max(v.x for v in corners)


def interval_distance(a_min, a_max, b_min, b_max):
    if a_max < b_min:
        return b_min - a_max
    if b_max < a_min:
        return a_min - b_max
    return -min(a_max, b_max) + max(a_min, b_min)


def collect_scene_metrics(label):
    bpy.context.scene.frame_set(1)
    failures = []
    values = {"label": label}

    if bpy.context.scene.unit_settings.system != "METRIC":
        failures.append("scene units are not METRIC")
    if bpy.data.objects.get("RV_ROOT") is None:
        failures.append("RV_ROOT missing")

    wheel_x = {}
    for name, expected_x in EXPECTED_WHEELS.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{name} missing")
            continue
        actual_x = world_x(obj)
        wheel_x[name] = actual_x
        if abs(actual_x - expected_x) > TOLERANCE_M:
            failures.append(f"{name} x={actual_x:.6f}, expected {expected_x:.6f}")

    if all(name in wheel_x for name in EXPECTED_WHEELS):
        wheelbase_left = wheel_x["WHEEL_RL_ROOT"] - wheel_x["WHEEL_FL_ROOT"]
        wheelbase_right = wheel_x["WHEEL_RR_ROOT"] - wheel_x["WHEEL_FR_ROOT"]
        values["wheelbase_left_m"] = wheelbase_left
        values["wheelbase_right_m"] = wheelbase_right
        if abs(wheelbase_left - 5.150) > TOLERANCE_M:
            failures.append(f"left wheelbase {wheelbase_left:.6f} != 5.150")
        if abs(wheelbase_right - 5.150) > TOLERANCE_M:
            failures.append(f"right wheelbase {wheelbase_right:.6f} != 5.150")

    arch_bounds = {}
    arch_centers = {}
    for name, expected_x in EXPECTED_ARCHES.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{name} missing")
            continue
        x_min, x_max = bounds_x(obj)
        center_x = (x_min + x_max) / 2
        arch_bounds[name] = (x_min, x_max)
        arch_centers[name] = center_x
        if abs(center_x - expected_x) > TOLERANCE_M:
            failures.append(f"{name} center={center_x:.6f}, expected {expected_x:.6f}")

    hatch_x = {}
    hatch_bounds = {}
    for root_name, expected_x in EXPECTED_HATCHES.items():
        root = bpy.data.objects.get(root_name)
        panel_name = root_name.replace("_ROOT", "")
        panel = bpy.data.objects.get(panel_name)
        if root is None:
            failures.append(f"{root_name} missing")
            continue
        if panel is None:
            failures.append(f"{panel_name} missing")
            continue
        actual_x = world_x(root)
        hatch_x[root_name] = actual_x
        hatch_bounds[root_name] = bounds_x(panel)
        if abs(actual_x - expected_x) > TOLERANCE_M:
            failures.append(f"{root_name} x={actual_x:.6f}, expected {expected_x:.6f}")

    door_bounds = {}
    for name in ("DOOR_DRIVER_L", "DOOR_PASSENGER_R", "DOOR_LIVING_R"):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{name} missing")
        else:
            door_bounds[name] = bounds_x(obj)

    clearance_rows = []
    for root_name, (hatch_min, hatch_max) in hatch_bounds.items():
        side = "L" if "_L_" in root_name else "R"
        relevant_arches = ("WHEEL_ARCH_FL", "WHEEL_ARCH_RL") if side == "L" else ("WHEEL_ARCH_FR", "WHEEL_ARCH_RR")
        relevant_doors = ("DOOR_DRIVER_L",) if side == "L" else ("DOOR_PASSENGER_R", "DOOR_LIVING_R")

        arch_gaps = {
            name: interval_distance(hatch_min, hatch_max, *arch_bounds[name])
            for name in relevant_arches
            if name in arch_bounds
        }
        door_gaps = {
            name: interval_distance(hatch_min, hatch_max, *door_bounds[name])
            for name in relevant_doors
            if name in door_bounds
        }
        nearest_arch_name = min(arch_gaps, key=arch_gaps.get) if arch_gaps else None
        nearest_door_name = min(door_gaps, key=door_gaps.get) if door_gaps else None
        nearest_arch_gap = arch_gaps.get(nearest_arch_name, -math.inf)
        nearest_door_gap = door_gaps.get(nearest_door_name, -math.inf)

        row = {
            "name": root_name,
            "nearest_wheel_arch": nearest_arch_name,
            "wheel_arch_clearance_m": nearest_arch_gap,
            "nearest_door": nearest_door_name,
            "door_seam_clearance_m": nearest_door_gap,
        }
        clearance_rows.append(row)
        if nearest_arch_gap < MIN_WHEEL_ARCH_CLEARANCE_M:
            failures.append(f"{root_name} wheel-arch clearance {nearest_arch_gap:.6f} < 0.080")
        if nearest_door_gap < MIN_DOOR_SEAM_CLEARANCE_M:
            failures.append(f"{root_name} door clearance {nearest_door_gap:.6f} < 0.060")

    missing_animation_roots = [name for name in EXPECTED_ANIMATION_ROOTS if bpy.data.objects.get(name) is None]
    failures.extend(f"{name} animation root missing" for name in missing_animation_roots)
    action_count = len(bpy.data.actions)
    if action_count < len(EXPECTED_ANIMATION_ROOTS):
        failures.append(f"action count {action_count} < {len(EXPECTED_ANIMATION_ROOTS)}")

    values.update(
        {
            "wheel_root_x_m": wheel_x,
            "wheel_arch_center_x_m": arch_centers,
            "service_hatch_root_x_m": hatch_x,
            "service_hatch_clearance": clearance_rows,
            "actions": action_count,
            "objects": len(bpy.data.objects),
            "meshes": len(bpy.data.meshes),
            "failures": failures,
            "result": "PASS" if not failures else "FAIL",
        }
    )
    return values


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def compare_roundtrip(blend_metrics, glb_metrics):
    failures = []
    for key in ("wheel_root_x_m", "wheel_arch_center_x_m", "service_hatch_root_x_m"):
        blend_values = blend_metrics.get(key, {})
        glb_values = glb_metrics.get(key, {})
        for name, blend_value in blend_values.items():
            if name not in glb_values:
                failures.append(f"{name} missing from GLB metric {key}")
                continue
            delta = abs(blend_value - glb_values[name])
            if delta > TOLERANCE_M:
                failures.append(f"{name} roundtrip delta {delta:.6f} > 0.002")
    if glb_metrics.get("actions", 0) < len(EXPECTED_ANIMATION_ROOTS):
        failures.append("GLB animation action count below 13")
    return failures


def main():
    args = parse_args()
    declared_clearance = json.loads(Path(args.clearance).read_text(encoding="utf-8"))
    blend_metrics = collect_scene_metrics("blend")

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=args.glb)
    glb_metrics = collect_scene_metrics("glb_roundtrip")

    roundtrip_failures = compare_roundtrip(blend_metrics, glb_metrics)
    failures = []
    if declared_clearance.get("result") != "PASS":
        failures.append("declared static clearance report is not PASS")
    failures.extend(blend_metrics["failures"])
    failures.extend(glb_metrics["failures"])
    failures.extend(roundtrip_failures)

    report = {
        "schema": "nomadhub-s1c-roundtrip-verification-v1",
        "stage": "S1C",
        "blend": blend_metrics,
        "glb_roundtrip": glb_metrics,
        "roundtrip_failures": roundtrip_failures,
        "result": "PASS" if not failures else "FAIL",
        "s2_ready": not failures,
        "failures": failures,
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if failures:
        raise RuntimeError("S1C round-trip verification failed")


if __name__ == "__main__":
    main()
