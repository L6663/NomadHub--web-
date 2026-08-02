import argparse
import json
import math
import sys
from collections import deque
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


BODY_NAME = "BODY_S2_CONTROL_CAGE"
EXPECTED_MODIFIERS = ("SUBSURF", "BOOLEAN", "BOOLEAN", "BEVEL")
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
EXPECTED_DOORS = {
    "DOOR_DRIVER_L_ROOT": -4.40,
    "DOOR_PASSENGER_R_ROOT": -4.40,
    "DOOR_LIVING_R_ROOT": -0.82,
}
EXPECTED_DOOR_GLASS = {
    "DOOR_DRIVER_L_GLASS": "DOOR_DRIVER_L_ROOT",
    "DOOR_PASSENGER_R_GLASS": "DOOR_PASSENGER_R_ROOT",
    "DOOR_LIVING_R_GLASS": "DOOR_LIVING_R_ROOT",
}
REQUIRED_RING_XS = (
    -4.495,
    -4.430,
    -4.300,
    -4.080,
    -3.900,
    -3.800,
    -3.750,
    -3.245,
    -2.710,
    -2.600,
    -2.500,
    -2.475,
    -1.950,
    -1.425,
    -0.880,
    -0.820,
    -0.040,
    0.020,
    0.225,
    0.750,
    1.275,
    1.340,
    1.370,
    1.905,
    2.440,
    2.500,
    2.525,
    3.050,
    3.575,
    4.350,
    4.495,
)
MOVING_MESHES = (
    "DOOR_DRIVER_L",
    "MIRROR_L_HOUSING",
    "MIRROR_L_GLASS",
    "DOOR_DRIVER_L_GLASS",
    "DOOR_PASSENGER_R",
    "MIRROR_R_HOUSING",
    "MIRROR_R_GLASS",
    "DOOR_PASSENGER_R_GLASS",
    "DOOR_LIVING_R",
    "DOOR_LIVING_R_GLASS",
    "HATCH_L_1",
    "HATCH_L_2",
    "HATCH_L_3",
    "HATCH_R_1",
    "HATCH_R_2",
    "HATCH_R_3",
)
WHEEL_TIRES = (
    "WHEEL_FL_TIRE",
    "WHEEL_FR_TIRE",
    "WHEEL_RL_TIRE",
    "WHEEL_RR_TIRE",
)
SAMPLE_FRAMES = (1, 24, 48, 72, 96)
POSITION_TOLERANCE_M = 0.002
ROUNDTRIP_TOLERANCE_M = 0.010
MIN_QUAD_RATIO = 0.995


def parse_args():
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(raw)


def world_x(obj):
    return float(obj.matrix_world.translation.x)


def object_bounds(obj, evaluated=False):
    if evaluated:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated_obj = obj.evaluated_get(depsgraph)
        mesh = evaluated_obj.to_mesh()
        try:
            points = [evaluated_obj.matrix_world @ vertex.co for vertex in mesh.vertices]
        finally:
            evaluated_obj.to_mesh_clear()
    else:
        points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return {
        "x_min": min(point.x for point in points),
        "x_max": max(point.x for point in points),
        "y_min": min(point.y for point in points),
        "y_max": max(point.y for point in points),
        "z_min": min(point.z for point in points),
        "z_max": max(point.z for point in points),
    }


def polygon_statistics(mesh):
    counts = {"triangles": 0, "quads": 0, "ngons": 0}
    for polygon in mesh.polygons:
        size = len(polygon.vertices)
        if size == 3:
            counts["triangles"] += 1
        elif size == 4:
            counts["quads"] += 1
        else:
            counts["ngons"] += 1
    counts["total"] = len(mesh.polygons)
    counts["quad_ratio"] = (
        counts["quads"] / counts["total"] if counts["total"] else 0
    )
    return counts


def topology_connectivity(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    non_manifold_edges = sum(1 for edge in bm.edges if len(edge.link_faces) != 2)
    loose_vertices = sum(1 for vertex in bm.verts if not vertex.link_edges)

    adjacency = {vertex.index: set() for vertex in bm.verts}
    for edge in bm.edges:
        a, b = edge.verts
        adjacency[a.index].add(b.index)
        adjacency[b.index].add(a.index)
    components = 0
    unseen = set(adjacency)
    while unseen:
        components += 1
        start = unseen.pop()
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
    bm.free()
    return {
        "non_manifold_edges": non_manifold_edges,
        "loose_vertices": loose_vertices,
        "connected_components": components,
    }


def symmetry_failures(mesh, tolerance=1e-6):
    coordinates = {
        (
            round(vertex.co.x / tolerance),
            round(vertex.co.y / tolerance),
            round(vertex.co.z / tolerance),
        )
        for vertex in mesh.vertices
    }
    failures = []
    for vertex in mesh.vertices:
        counterpart = (
            round(vertex.co.x / tolerance),
            round(-vertex.co.y / tolerance),
            round(vertex.co.z / tolerance),
        )
        if counterpart not in coordinates:
            failures.append(vertex.index)
    return failures


def ring_x_values(mesh):
    return sorted({round(vertex.co.x, 6) for vertex in mesh.vertices})


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


def collision_sweep(body_name):
    scene = bpy.context.scene
    collisions = []
    missing = []
    checked_pairs = 0
    for frame in SAMPLE_FRAMES:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        body = bpy.data.objects.get(body_name)
        if body is None:
            missing.append(body_name)
            break
        body_bvh = world_bvh(body, depsgraph)
        if body_bvh is None:
            missing.append(body_name)
            break
        for moving_name in MOVING_MESHES:
            moving = bpy.data.objects.get(moving_name)
            if moving is None:
                missing.append(moving_name)
                continue
            moving_bvh = world_bvh(moving, depsgraph)
            if moving_bvh is None:
                continue
            checked_pairs += 1
            overlap = body_bvh.overlap(moving_bvh)
            if overlap:
                collisions.append(
                    {
                        "frame": frame,
                        "moving_mesh": moving_name,
                        "triangle_overlap_pairs": len(overlap),
                    }
                )
    scene.frame_set(1)
    return {
        "sample_frames": list(SAMPLE_FRAMES),
        "checked_pairs": checked_pairs,
        "missing_objects": sorted(set(missing)),
        "collisions": collisions,
        "result": "PASS" if not collisions and not missing else "FAIL",
    }


def wheel_clearance(body_name):
    scene = bpy.context.scene
    scene.frame_set(1)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    body = bpy.data.objects.get(body_name)
    failures = []
    rows = []
    if body is None:
        return {"result": "FAIL", "failures": [f"{body_name} missing"], "rows": []}
    body_bvh = world_bvh(body, depsgraph)
    for tire_name in WHEEL_TIRES:
        tire = bpy.data.objects.get(tire_name)
        if tire is None:
            failures.append(f"{tire_name} missing")
            continue
        tire_bvh = world_bvh(tire, depsgraph)
        overlap = body_bvh.overlap(tire_bvh) if body_bvh and tire_bvh else []
        rows.append(
            {
                "tire": tire_name,
                "triangle_overlap_pairs": len(overlap),
            }
        )
        if overlap:
            failures.append(f"{tire_name} intersects evaluated S2 body")
    return {
        "rows": rows,
        "failures": failures,
        "result": "PASS" if not failures else "FAIL",
    }


def validate_frozen_positions(failures):
    results = {}
    for group_name, expected in (
        ("wheels", EXPECTED_WHEELS),
        ("arches", EXPECTED_ARCHES),
        ("hatches", EXPECTED_HATCHES),
        ("doors", EXPECTED_DOORS),
    ):
        group = {}
        for name, expected_x in expected.items():
            obj = bpy.data.objects.get(name)
            if obj is None:
                failures.append(f"frozen object missing: {name}")
                continue
            actual_x = world_x(obj)
            group[name] = actual_x
            if abs(actual_x - expected_x) > POSITION_TOLERANCE_M:
                failures.append(
                    f"{name} x={actual_x:.6f}, expected {expected_x:.6f}"
                )
        results[group_name] = group
    if all(name in results["wheels"] for name in EXPECTED_WHEELS):
        left = results["wheels"]["WHEEL_RL_ROOT"] - results["wheels"]["WHEEL_FL_ROOT"]
        right = results["wheels"]["WHEEL_RR_ROOT"] - results["wheels"]["WHEEL_FR_ROOT"]
        results["wheelbase_left_m"] = left
        results["wheelbase_right_m"] = right
        if abs(left - 5.150) > POSITION_TOLERANCE_M:
            failures.append(f"left wheelbase {left:.6f} != 5.150")
        if abs(right - 5.150) > POSITION_TOLERANCE_M:
            failures.append(f"right wheelbase {right:.6f} != 5.150")
    return results


def validate_door_glass(failures):
    scene = bpy.context.scene
    scene.frame_set(1)
    bpy.context.view_layer.update()
    closed = {}
    rows = {}
    for name, parent_name in EXPECTED_DOOR_GLASS.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{name} missing")
            continue
        actual_parent = obj.parent.name if obj.parent else None
        if actual_parent != parent_name:
            failures.append(f"{name} parent={actual_parent}, expected {parent_name}")
        closed[name] = obj.matrix_world.translation.copy()
        rows[name] = {"parent": actual_parent}
    scene.frame_set(48)
    bpy.context.view_layer.update()
    for name in EXPECTED_DOOR_GLASS:
        obj = bpy.data.objects.get(name)
        if obj is None or name not in closed:
            continue
        delta = (obj.matrix_world.translation - closed[name]).length
        rows[name]["translation_delta_m"] = delta
        if delta < 0.10:
            failures.append(f"{name} frame 1->48 delta {delta:.6f} < 0.100")
    scene.frame_set(1)
    return rows


def collect(label, check_source_topology):
    failures = []
    body = bpy.data.objects.get(BODY_NAME)
    result = {"label": label}
    if body is None or body.type != "MESH":
        failures.append(f"{BODY_NAME} missing or not a mesh")
        result["failures"] = failures
        result["result"] = "FAIL"
        return result

    evaluated_bounds = object_bounds(body, evaluated=True)
    result["evaluated_bounds_m"] = evaluated_bounds
    if evaluated_bounds["x_max"] - evaluated_bounds["x_min"] < 8.80:
        failures.append("evaluated continuous body length is unexpectedly short")

    if check_source_topology:
        topology = polygon_statistics(body.data)
        connectivity = topology_connectivity(body.data)
        asymmetric_vertices = symmetry_failures(body.data)
        actual_rings = ring_x_values(body.data)
        missing_rings = [
            x for x in REQUIRED_RING_XS if not any(abs(x - actual) <= 1e-6 for actual in actual_rings)
        ]
        modifier_types = tuple(modifier.type for modifier in body.modifiers)
        source_bounds = object_bounds(body, evaluated=False)
        result.update(
            {
                "source_bounds_m": source_bounds,
                "topology": topology,
                "connectivity": connectivity,
                "asymmetric_vertex_indices": asymmetric_vertices,
                "control_ring_x_m": actual_rings,
                "missing_required_ring_x_m": missing_rings,
                "modifier_types": list(modifier_types),
            }
        )
        if topology["quad_ratio"] < MIN_QUAD_RATIO:
            failures.append(
                f"source quad ratio {topology['quad_ratio']:.6f} < {MIN_QUAD_RATIO:.3f}"
            )
        if topology["triangles"] != 0:
            failures.append(f"source cage contains {topology['triangles']} triangles")
        if topology["ngons"] != 2:
            failures.append(f"source cage must contain exactly 2 cap ngons, found {topology['ngons']}")
        if connectivity["non_manifold_edges"] != 0:
            failures.append(
                f"source cage has {connectivity['non_manifold_edges']} non-manifold edges"
            )
        if connectivity["loose_vertices"] != 0:
            failures.append(f"source cage has {connectivity['loose_vertices']} loose vertices")
        if connectivity["connected_components"] != 1:
            failures.append(
                f"source cage has {connectivity['connected_components']} components"
            )
        if asymmetric_vertices:
            failures.append(f"source cage has {len(asymmetric_vertices)} asymmetric vertices")
        if missing_rings:
            failures.append(f"required control rings missing: {missing_rings}")
        if modifier_types != EXPECTED_MODIFIERS:
            failures.append(
                f"modifier order {modifier_types}, expected {EXPECTED_MODIFIERS}"
            )
        if abs(source_bounds["x_min"] + 4.495) > 1e-6 or abs(source_bounds["x_max"] - 4.495) > 1e-6:
            failures.append("source cage does not preserve the 8.990 m longitudinal envelope")
        for reference_name in ("S1C_BODY_MAIN_REFERENCE", "S1C_BODY_CAB_REFERENCE"):
            reference = bpy.data.objects.get(reference_name)
            if reference is None:
                failures.append(f"frozen reference missing: {reference_name}")
            elif not reference.hide_render:
                failures.append(f"frozen reference remains renderable: {reference_name}")

    result["frozen_positions"] = validate_frozen_positions(failures)
    result["door_glass"] = validate_door_glass(failures)
    result["moving_body_collision_sweep"] = collision_sweep(BODY_NAME)
    result["wheel_body_clearance"] = wheel_clearance(BODY_NAME)
    if result["moving_body_collision_sweep"]["result"] != "PASS":
        failures.append("moving component collision sweep against S2 body failed")
    if result["wheel_body_clearance"]["result"] != "PASS":
        failures.extend(result["wheel_body_clearance"]["failures"])

    result["objects"] = len(bpy.data.objects)
    result["meshes"] = len(bpy.data.meshes)
    result["actions"] = len(bpy.data.actions)
    if result["actions"] < 1:
        failures.append("no animation actions found")
    result["failures"] = failures
    result["result"] = "PASS" if not failures else "FAIL"
    return result


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def compare_roundtrip(blend_result, glb_result):
    failures = []
    blend_bounds = blend_result.get("evaluated_bounds_m", {})
    glb_bounds = glb_result.get("evaluated_bounds_m", {})
    for key in ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max"):
        if key not in blend_bounds or key not in glb_bounds:
            failures.append(f"roundtrip body bound missing: {key}")
            continue
        delta = abs(blend_bounds[key] - glb_bounds[key])
        if delta > ROUNDTRIP_TOLERANCE_M:
            failures.append(f"roundtrip body {key} delta {delta:.6f} > 0.010")
    return failures


def main():
    args = parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    blend_result = collect("blend", check_source_topology=True)

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=args.glb)
    glb_result = collect("glb_roundtrip", check_source_topology=False)

    roundtrip_failures = compare_roundtrip(blend_result, glb_result)
    failures = []
    failures.extend(blend_result["failures"])
    failures.extend(glb_result["failures"])
    failures.extend(roundtrip_failures)
    if manifest.get("stage") != "S2_R1":
        failures.append("manifest stage is not S2_R1")
    if manifest.get("body_object") != BODY_NAME:
        failures.append("manifest body object mismatch")

    report = {
        "schema": "nomadhub-s2-r1-verification-v1",
        "stage": "S2_R1",
        "status": "PASS" if not failures else "FAIL",
        "s2_r1_ready_for_visual_review": not failures,
        "blend": blend_result,
        "glb_roundtrip": glb_result,
        "roundtrip_failures": roundtrip_failures,
        "failures": failures,
        "scope_limit": (
            "A PASS validates the first continuous quad-dominant body cage, frozen S1C "
            "coordinates, wheel cutout placeholders, dynamic clearance and GLB roundtrip. "
            "It does not accept final door/window topology, production surfacing or UV."
        ),
    }
    Path(args.report).write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    if failures:
        raise RuntimeError("S2-R1 validation failed")


if __name__ == "__main__":
    main()
