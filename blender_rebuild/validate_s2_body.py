import argparse
import importlib.util
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


SCRIPT_DIR = Path(__file__).resolve().parent
S1C_VALIDATOR_PATH = SCRIPT_DIR / "validate_s1c.py"
S1C_SPEC = importlib.util.spec_from_file_location("nomadhub_validate_s1c", S1C_VALIDATOR_PATH)
if S1C_SPEC is None or S1C_SPEC.loader is None:
    raise RuntimeError(f"unable to load S1C validator: {S1C_VALIDATOR_PATH}")
s1c = importlib.util.module_from_spec(S1C_SPEC)
S1C_SPEC.loader.exec_module(s1c)


BODY_NAME = "BODY_S2_CONTROL_CAGE"
WIRE_NAME = "BODY_S2_WIREFRAME"
EXPECTED_MODIFIERS = ("SUBSURF", "BOOLEAN", "BOOLEAN", "BEVEL")
EXPECTED_LENGTH_M = 8.990
EXPECTED_SOURCE_WIDTH_M = 2.300
DIMENSION_TOLERANCE_M = 0.015
POSITION_TOLERANCE_M = 0.002
ROUNDTRIP_TOLERANCE_M = 0.010
MIN_QUAD_RATIO = 0.995
REQUIRED_RING_XS = (
    -4.495, -4.430, -4.300, -4.080, -3.900, -3.800, -3.750,
    -3.245, -2.710, -2.600, -2.500, -2.475, -1.950, -1.425,
    -0.880, -0.820, -0.040, 0.020, 0.225, 0.750, 1.275, 1.340,
    1.370, 1.905, 2.440, 2.500, 2.525, 3.050, 3.575, 4.350, 4.495,
)
# Only objects whose origins are the frozen engineering anchors belong here.
# Wheel-arch objects were built from world-space curve points and retain an
# origin at zero, so their centers are validated by the inherited S1C bounds
# check instead of this origin check.
EXPECTED_FROZEN_ROOT_X = {
    "WHEEL_FL_ROOT": -3.245,
    "WHEEL_FR_ROOT": -3.245,
    "WHEEL_RL_ROOT": 1.905,
    "WHEEL_RR_ROOT": 1.905,
    "DOOR_DRIVER_L_ROOT": -4.020,
    "DOOR_PASSENGER_R_ROOT": -4.020,
    "DOOR_LIVING_R_ROOT": -0.820,
    "HATCH_L_1_ROOT": -1.950,
    "HATCH_L_2_ROOT": 0.350,
    "HATCH_L_3_ROOT": 3.050,
    "HATCH_R_1_ROOT": -1.950,
    "HATCH_R_2_ROOT": 0.750,
    "HATCH_R_3_ROOT": 3.050,
}
WHEEL_TIRES = (
    "WHEEL_FL_TIRE", "WHEEL_FR_TIRE", "WHEEL_RL_TIRE", "WHEEL_RR_TIRE",
)
S2_STATIC_COLLISION_OBJECTS = (
    BODY_NAME,
    "FRONT_BUMPER", "REAR_BUMPER",
    "SIDE_SKIRT_L_FRONT", "SIDE_SKIRT_L_MID", "SIDE_SKIRT_L_REAR",
    "SIDE_SKIRT_R_FRONT", "SIDE_SKIRT_R_MID", "SIDE_SKIRT_R_REAR",
    "WHEEL_ARCH_FL", "WHEEL_ARCH_FR", "WHEEL_ARCH_RL", "WHEEL_ARCH_RR",
    "WHEEL_FL_TIRE", "WHEEL_FR_TIRE", "WHEEL_RL_TIRE", "WHEEL_RR_TIRE",
)


def parse_args():
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", required=True)
    parser.add_argument("--clearance", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(raw)


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
        points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    minimum = Vector(tuple(min(getattr(point, axis) for point in points) for axis in "xyz"))
    maximum = Vector(tuple(max(getattr(point, axis) for point in points) for axis in "xyz"))
    return {
        "min_m": list(minimum),
        "max_m": list(maximum),
        "dimensions_m": list(maximum - minimum),
    }


def polygon_statistics(mesh):
    sizes = [len(polygon.vertices) for polygon in mesh.polygons]
    quads = sum(size == 4 for size in sizes)
    return {
        "vertices": len(mesh.vertices),
        "edges": len(mesh.edges),
        "faces": len(mesh.polygons),
        "triangles": sum(size == 3 for size in sizes),
        "quads": quads,
        "ngons": sum(size > 4 for size in sizes),
        "quad_ratio": quads / len(sizes) if sizes else 0.0,
        "non_quad_face_sizes": [size for size in sizes if size != 4],
    }


def topology_connectivity(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    adjacency = defaultdict(set)
    for edge in bm.edges:
        a, b = edge.verts
        adjacency[a.index].add(b.index)
        adjacency[b.index].add(a.index)
    unseen = set(range(len(bm.verts)))
    component_sizes = []
    while unseen:
        start = unseen.pop()
        queue = deque([start])
        size = 1
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
                    size += 1
        component_sizes.append(size)
    result = {
        "connected_components": len(component_sizes),
        "component_vertex_counts": sorted(component_sizes, reverse=True),
        "non_manifold_edges": sum(1 for edge in bm.edges if len(edge.link_faces) != 2),
        "loose_vertices": sum(1 for vertex in bm.verts if not vertex.link_edges),
    }
    bm.free()
    return result


def symmetry_errors(mesh, tolerance=1e-6):
    coordinates = {
        (
            round(vertex.co.x / tolerance),
            round(vertex.co.y / tolerance),
            round(vertex.co.z / tolerance),
        )
        for vertex in mesh.vertices
    }
    errors = []
    for vertex in mesh.vertices:
        counterpart = (
            round(vertex.co.x / tolerance),
            round(-vertex.co.y / tolerance),
            round(vertex.co.z / tolerance),
        )
        if counterpart not in coordinates:
            errors.append(vertex.index)
    return errors


def control_ring_values(body):
    stored = body.get("s2_ring_x_m")
    if isinstance(stored, str):
        return [float(value) for value in json.loads(stored)]
    return sorted({round(vertex.co.x, 6) for vertex in body.data.vertices})


def world_bvh(obj, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        if not mesh.vertices or not mesh.polygons:
            return None
        vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        polygons = [tuple(polygon.vertices) for polygon in mesh.polygons]
        return BVHTree.FromPolygons(vertices, polygons, all_triangles=False, epsilon=1e-6)
    finally:
        evaluated.to_mesh_clear()


def wheel_body_clearance():
    scene = bpy.context.scene
    scene.frame_set(1)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    body = bpy.data.objects.get(BODY_NAME)
    failures, rows = [], []
    if body is None:
        return {"result": "FAIL", "rows": [], "failures": [f"{BODY_NAME} missing"]}
    body_bvh = world_bvh(body, depsgraph)
    for tire_name in WHEEL_TIRES:
        tire = bpy.data.objects.get(tire_name)
        if tire is None:
            failures.append(f"{tire_name} missing")
            continue
        tire_bvh = world_bvh(tire, depsgraph)
        overlap = body_bvh.overlap(tire_bvh) if body_bvh and tire_bvh else []
        rows.append({"tire": tire_name, "triangle_overlap_pairs": len(overlap)})
        if overlap:
            failures.append(f"{tire_name} intersects evaluated S2 body")
    return {"result": "PASS" if not failures else "FAIL", "rows": rows, "failures": failures}


def frozen_position_report():
    failures, values = [], {}
    for name, expected_x in EXPECTED_FROZEN_ROOT_X.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"frozen object missing: {name}")
            continue
        actual_x = float(obj.matrix_world.translation.x)
        values[name] = actual_x
        if abs(actual_x - expected_x) > POSITION_TOLERANCE_M:
            failures.append(f"{name} x={actual_x:.6f}, expected {expected_x:.6f}")
    for side, front, rear in (
        ("left", "WHEEL_FL_ROOT", "WHEEL_RL_ROOT"),
        ("right", "WHEEL_FR_ROOT", "WHEEL_RR_ROOT"),
    ):
        if front in values and rear in values:
            wheelbase = values[rear] - values[front]
            values[f"wheelbase_{side}_m"] = wheelbase
            if abs(wheelbase - 5.150) > POSITION_TOLERANCE_M:
                failures.append(f"{side} wheelbase {wheelbase:.6f} != 5.150")
    return {"result": "PASS" if not failures else "FAIL", "values_m": values, "failures": failures}


def collect_body(label, check_source_topology):
    failures = []
    body = bpy.data.objects.get(BODY_NAME)
    if body is None or body.type != "MESH":
        return {"label": label, "result": "FAIL", "failures": [f"{BODY_NAME} missing or not a mesh"]}

    evaluated_bounds = object_bounds(body, evaluated=True)
    result = {"label": label, "body_name": body.name, "evaluated_bounds": evaluated_bounds}
    if evaluated_bounds["dimensions_m"][0] < 8.80:
        failures.append("evaluated continuous body length is unexpectedly short")

    if check_source_topology:
        topology = polygon_statistics(body.data)
        connectivity = topology_connectivity(body.data)
        symmetry = symmetry_errors(body.data)
        source_bounds = object_bounds(body, evaluated=False)
        rings = control_ring_values(body)
        missing_rings = [
            expected for expected in REQUIRED_RING_XS
            if not any(abs(expected - actual) <= 1e-6 for actual in rings)
        ]
        modifier_types = tuple(modifier.type for modifier in body.modifiers)
        result.update({
            "source_bounds": source_bounds,
            "topology": topology,
            "connectivity": connectivity,
            "symmetry_error_count": len(symmetry),
            "symmetry_vertex_indices": symmetry[:30],
            "control_ring_x_m": rings,
            "missing_required_ring_x_m": missing_rings,
            "modifier_types": list(modifier_types),
        })
        source_length, source_width, _ = source_bounds["dimensions_m"]
        if abs(source_length - EXPECTED_LENGTH_M) > DIMENSION_TOLERANCE_M:
            failures.append(f"source body length {source_length:.6f} differs from 8.990")
        if abs(source_width - EXPECTED_SOURCE_WIDTH_M) > DIMENSION_TOLERANCE_M:
            failures.append(f"source body width {source_width:.6f} differs from 2.300")
        if topology["quad_ratio"] < MIN_QUAD_RATIO:
            failures.append(f"source quad ratio {topology['quad_ratio']:.6f} < {MIN_QUAD_RATIO:.3f}")
        if topology["triangles"] != 0:
            failures.append(f"source cage contains {topology['triangles']} triangles")
        if topology["ngons"] != 2:
            failures.append(f"source cage must have exactly 2 cap n-gons, found {topology['ngons']}")
        if connectivity["connected_components"] != 1:
            failures.append(f"source cage has {connectivity['connected_components']} components")
        if connectivity["non_manifold_edges"] != 0:
            failures.append(f"source cage has {connectivity['non_manifold_edges']} non-manifold edges")
        if connectivity["loose_vertices"] != 0:
            failures.append(f"source cage has {connectivity['loose_vertices']} loose vertices")
        if symmetry:
            failures.append(f"source cage has {len(symmetry)} symmetry errors")
        if missing_rings:
            failures.append(f"required control rings missing: {missing_rings}")
        if modifier_types != EXPECTED_MODIFIERS:
            failures.append(f"modifier order {modifier_types}, expected {EXPECTED_MODIFIERS}")

        wire = bpy.data.objects.get(WIRE_NAME)
        if wire is None or not bool(wire.get("s2_proof_only")):
            failures.append(f"{WIRE_NAME} proof object missing or unmarked")
        for reference_name in ("S1C_BODY_MAIN_REFERENCE", "S1C_BODY_CAB_REFERENCE"):
            reference = bpy.data.objects.get(reference_name)
            if reference is None:
                failures.append(f"frozen reference missing: {reference_name}")
            elif not reference.hide_render:
                failures.append(f"frozen reference is still renderable: {reference_name}")
        for cutter_name in ("S2_CUTTER_ARCH_FRONT", "S2_CUTTER_ARCH_REAR"):
            cutter = bpy.data.objects.get(cutter_name)
            if cutter is None:
                failures.append(f"wheel-arch cutter missing: {cutter_name}")
            elif not cutter.hide_render:
                failures.append(f"wheel-arch cutter is renderable: {cutter_name}")

    frozen = frozen_position_report()
    wheel_clearance = wheel_body_clearance()
    failures.extend(frozen["failures"])
    failures.extend(wheel_clearance["failures"])
    result.update({
        "frozen_positions": frozen,
        "wheel_body_clearance": wheel_clearance,
        "objects": len(bpy.data.objects),
        "meshes": len(bpy.data.meshes),
        "actions": len(bpy.data.actions),
        "failures": failures,
        "result": "PASS" if not failures else "FAIL",
    })
    return result


def collect_s1c_compatibility(label):
    original_static = s1c.STATIC_COLLISION_OBJECTS
    try:
        s1c.STATIC_COLLISION_OBJECTS = S2_STATIC_COLLISION_OBJECTS
        return s1c.collect_scene_metrics(label)
    finally:
        s1c.STATIC_COLLISION_OBJECTS = original_static


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def compare_body_roundtrip(blend_body, glb_body):
    failures = []
    blend_bounds = blend_body.get("evaluated_bounds", {})
    glb_bounds = glb_body.get("evaluated_bounds", {})
    for key in ("min_m", "max_m", "dimensions_m"):
        blend_values, glb_values = blend_bounds.get(key, []), glb_bounds.get(key, [])
        if len(blend_values) != 3 or len(glb_values) != 3:
            failures.append(f"roundtrip body metric missing: {key}")
            continue
        for axis, (blend_value, glb_value) in enumerate(zip(blend_values, glb_values)):
            delta = abs(blend_value - glb_value)
            if delta > ROUNDTRIP_TOLERANCE_M:
                failures.append(f"body {key}[{axis}] roundtrip delta {delta:.6f} > 0.010")
    return failures


def main():
    args = parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    clearance = json.loads(Path(args.clearance).read_text(encoding="utf-8"))

    blend_body = collect_body("blend", True)
    blend_s1c = collect_s1c_compatibility("blend_s2_compatibility")

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=args.glb)
    glb_body = collect_body("glb_roundtrip", False)
    glb_s1c = collect_s1c_compatibility("glb_s2_compatibility")

    roundtrip_failures = compare_body_roundtrip(blend_body, glb_body)
    roundtrip_failures.extend(s1c.compare_roundtrip(blend_s1c, glb_s1c))
    failures = []
    if clearance.get("result") != "PASS":
        failures.append("inherited S1C clearance report is not PASS")
    failures.extend(blend_body.get("failures", []))
    failures.extend(glb_body.get("failures", []))
    failures.extend(blend_s1c.get("failures", []))
    failures.extend(glb_s1c.get("failures", []))
    failures.extend(roundtrip_failures)
    if manifest.get("stage") != "S2" or manifest.get("iteration") != "R1":
        failures.append("manifest stage/iteration mismatch")
    if manifest.get("body_object") != BODY_NAME:
        failures.append("manifest body object mismatch")

    report = {
        "schema": "nomadhub-s2-r1-verification-v4",
        "stage": "S2",
        "iteration": "R1",
        "status": "PASS" if not failures else "FAIL",
        "s2_r1_ready_for_visual_review": not failures,
        "s2_accepted": False,
        "blend_body": blend_body,
        "glb_body": glb_body,
        "blend_s1c_compatibility": blend_s1c,
        "glb_s1c_compatibility": glb_s1c,
        "roundtrip_failures": roundtrip_failures,
        "failures": failures,
        "scope_note": (
            "PASS means the S2-R1 continuous cage, evaluated wheel-arch openings, "
            "inherited S1C coordinates/animations and GLB roundtrip are technically "
            "reviewable. It does not accept final S2 topology or surfacing."
        ),
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if failures:
        raise RuntimeError("S2-R1 verification failed")


if __name__ == "__main__":
    main()
