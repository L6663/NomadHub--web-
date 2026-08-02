import argparse
import json
import math
import sys
from collections import defaultdict, deque
from pathlib import Path

import bpy
from mathutils import Vector

import validate_s1c as s1c


BODY_NAME = "BODY_S2_CONTROL_CAGE"
WIRE_NAME = "BODY_S2_WIREFRAME"
EXPECTED_LENGTH_M = 8.99
EXPECTED_WIDTH_M = 2.30
DIMENSION_TOLERANCE_M = 0.015
ROUNDTRIP_TOLERANCE_M = 0.005
MIN_QUAD_RATIO = 0.98
MAX_NON_QUADS = 2
EXPECTED_RING_SIZE = 12
EXPECTED_STATIONS = (
    -4.495,
    -4.400,
    -4.100,
    -3.780,
    -3.245,
    -2.710,
    -2.475,
    -1.345,
    -0.820,
    -0.040,
    0.225,
    1.275,
    1.370,
    1.905,
    2.440,
    2.525,
    3.575,
    4.495,
)
S2_STATIC_COLLISION_OBJECTS = (
    BODY_NAME,
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
    parser.add_argument("--clearance", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(raw)


def world_vertices(obj):
    return [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]


def bounds(obj):
    vertices = world_vertices(obj)
    minimum = Vector(
        (
            min(vertex.x for vertex in vertices),
            min(vertex.y for vertex in vertices),
            min(vertex.z for vertex in vertices),
        )
    )
    maximum = Vector(
        (
            max(vertex.x for vertex in vertices),
            max(vertex.y for vertex in vertices),
            max(vertex.z for vertex in vertices),
        )
    )
    return minimum, maximum


def connected_components(mesh):
    adjacency = defaultdict(set)
    for edge in mesh.edges:
        a, b = edge.vertices
        adjacency[a].add(b)
        adjacency[b].add(a)

    remaining = set(range(len(mesh.vertices)))
    components = []
    while remaining:
        start = next(iter(remaining))
        queue = deque([start])
        component = set()
        while queue:
            current = queue.popleft()
            if current in component:
                continue
            component.add(current)
            remaining.discard(current)
            queue.extend(adjacency[current] - component)
        components.append(component)
    return components


def edge_face_counts(mesh):
    counts = defaultdict(int)
    for polygon in mesh.polygons:
        for edge_key in polygon.edge_keys:
            counts[tuple(sorted(edge_key))] += 1
    return counts


def symmetry_errors(obj, tolerance=0.0005):
    vertices = world_vertices(obj)
    errors = []
    for index, vertex in enumerate(vertices):
        mirrored = Vector((vertex.x, -vertex.y, vertex.z))
        nearest = min((candidate - mirrored).length for candidate in vertices)
        if nearest > tolerance:
            errors.append(
                {
                    "vertex": index,
                    "coordinate": list(vertex),
                    "nearest_mirror_error_m": nearest,
                }
            )
    return errors


def parse_station_property(obj):
    value = obj.get("s2_station_x_m")
    if value is None:
        return []
    if isinstance(value, str):
        return [float(item) for item in json.loads(value)]
    return [float(item) for item in value]


def topology_metrics(obj):
    mesh = obj.data
    face_sizes = [len(polygon.vertices) for polygon in mesh.polygons]
    quad_count = sum(size == 4 for size in face_sizes)
    non_quad_sizes = [size for size in face_sizes if size != 4]
    components = connected_components(mesh)
    edge_counts = edge_face_counts(mesh)
    non_manifold = [edge for edge, count in edge_counts.items() if count != 2]
    minimum, maximum = bounds(obj)
    dimensions = maximum - minimum
    station_values = parse_station_property(obj)
    station_errors = []
    for expected in EXPECTED_STATIONS:
        nearest = min((abs(actual - expected) for actual in station_values), default=math.inf)
        if nearest > 0.0005:
            station_errors.append({"expected_x_m": expected, "nearest_error_m": nearest})

    symmetry = symmetry_errors(obj)
    return {
        "vertices": len(mesh.vertices),
        "edges": len(mesh.edges),
        "faces": len(mesh.polygons),
        "quads": quad_count,
        "non_quads": len(non_quad_sizes),
        "non_quad_face_sizes": non_quad_sizes,
        "quad_ratio": quad_count / len(mesh.polygons) if mesh.polygons else 0.0,
        "connected_components": len(components),
        "component_vertex_counts": sorted((len(component) for component in components), reverse=True),
        "non_manifold_edges": len(non_manifold),
        "bounds_min_m": list(minimum),
        "bounds_max_m": list(maximum),
        "dimensions_m": list(dimensions),
        "station_x_m": station_values,
        "station_errors": station_errors,
        "symmetry_error_count": len(symmetry),
        "symmetry_errors": symmetry[:20],
    }


def validate_topology(metrics):
    failures = []
    length, width, _ = metrics["dimensions_m"]
    if abs(length - EXPECTED_LENGTH_M) > DIMENSION_TOLERANCE_M:
        failures.append(
            f"body length {length:.6f} differs from {EXPECTED_LENGTH_M:.3f}"
        )
    if abs(width - EXPECTED_WIDTH_M) > DIMENSION_TOLERANCE_M:
        failures.append(
            f"body width {width:.6f} differs from {EXPECTED_WIDTH_M:.3f}"
        )
    if metrics["quad_ratio"] < MIN_QUAD_RATIO:
        failures.append(
            f"quad ratio {metrics['quad_ratio']:.6f} < {MIN_QUAD_RATIO:.2f}"
        )
    if metrics["non_quads"] > MAX_NON_QUADS:
        failures.append(
            f"non-quad faces {metrics['non_quads']} > {MAX_NON_QUADS}"
        )
    if metrics["connected_components"] != 1:
        failures.append(
            f"connected components {metrics['connected_components']} != 1"
        )
    if metrics["non_manifold_edges"] != 0:
        failures.append(
            f"non-manifold edges {metrics['non_manifold_edges']} != 0"
        )
    if metrics["station_errors"]:
        failures.append("one or more frozen control-ring stations are missing")
    if metrics["symmetry_error_count"] != 0:
        failures.append(
            f"body symmetry errors {metrics['symmetry_error_count']} != 0"
        )
    return failures


def collect_body(label, require_control_topology):
    failures = []
    body = bpy.data.objects.get(BODY_NAME)
    if body is None or body.type != "MESH":
        return {
            "label": label,
            "result": "FAIL",
            "failures": [f"{BODY_NAME} missing or not a mesh"],
        }

    if bpy.data.objects.get("BODY_MAIN") is not None:
        failures.append("legacy BODY_MAIN still present")
    if bpy.data.objects.get("BODY_CAB") is not None:
        failures.append("legacy BODY_CAB still present")

    minimum, maximum = bounds(body)
    dimensions = maximum - minimum
    result = {
        "label": label,
        "body_name": body.name,
        "bounds_min_m": list(minimum),
        "bounds_max_m": list(maximum),
        "dimensions_m": list(dimensions),
        "legacy_body_absent": (
            bpy.data.objects.get("BODY_MAIN") is None
            and bpy.data.objects.get("BODY_CAB") is None
        ),
    }

    if require_control_topology:
        metrics = topology_metrics(body)
        result["topology"] = metrics
        failures.extend(validate_topology(metrics))
        wire = bpy.data.objects.get(WIRE_NAME)
        if wire is None:
            failures.append(f"{WIRE_NAME} proof object missing")
        elif not bool(wire.get("s2_proof_only")):
            failures.append(f"{WIRE_NAME} is not marked proof-only")

    result["failures"] = failures
    result["result"] = "PASS" if not failures else "FAIL"
    return result


def compare_body_bounds(blend_body, glb_body):
    failures = []
    for key in ("bounds_min_m", "bounds_max_m", "dimensions_m"):
        for axis, (blend_value, glb_value) in enumerate(
            zip(blend_body[key], glb_body[key])
        ):
            delta = abs(blend_value - glb_value)
            if delta > ROUNDTRIP_TOLERANCE_M:
                failures.append(
                    f"body {key}[{axis}] roundtrip delta {delta:.6f} "
                    f"> {ROUNDTRIP_TOLERANCE_M:.3f}"
                )
    return failures


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def collect_s1c_compatibility(label):
    original_static = s1c.STATIC_COLLISION_OBJECTS
    try:
        s1c.STATIC_COLLISION_OBJECTS = S2_STATIC_COLLISION_OBJECTS
        return s1c.collect_scene_metrics(label)
    finally:
        s1c.STATIC_COLLISION_OBJECTS = original_static


def main():
    args = parse_args()
    clearance = json.loads(Path(args.clearance).read_text(encoding="utf-8"))

    blend_body = collect_body("blend", require_control_topology=True)
    blend_s1c = collect_s1c_compatibility("blend_s2_compatibility")

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=args.glb)
    glb_body = collect_body("glb_roundtrip", require_control_topology=False)
    glb_s1c = collect_s1c_compatibility("glb_s2_compatibility")

    roundtrip_failures = []
    if blend_body.get("result") == "PASS" and glb_body.get("result") == "PASS":
        roundtrip_failures.extend(compare_body_bounds(blend_body, glb_body))
    else:
        roundtrip_failures.append("body metrics unavailable for roundtrip comparison")
    roundtrip_failures.extend(s1c.compare_roundtrip(blend_s1c, glb_s1c))

    failures = []
    if clearance.get("result") != "PASS":
        failures.append("inherited S1C clearance report is not PASS")
    failures.extend(blend_body.get("failures", []))
    failures.extend(glb_body.get("failures", []))
    failures.extend(blend_s1c.get("failures", []))
    failures.extend(glb_s1c.get("failures", []))
    failures.extend(roundtrip_failures)

    report = {
        "schema": "nomadhub-s2-r1-verification-v1",
        "stage": "S2",
        "iteration": "R1",
        "status": "CANDIDATE_REVIEW_REQUIRED",
        "blend_body": blend_body,
        "glb_body": glb_body,
        "blend_s1c_compatibility": blend_s1c,
        "glb_s1c_compatibility": glb_s1c,
        "roundtrip_failures": roundtrip_failures,
        "result": "PASS" if not failures else "FAIL",
        "s2_accepted": False,
        "failures": failures,
        "scope_note": (
            "A PASS result means the S2 R1 control-cage candidate is connected, "
            "predominantly quad-based, symmetric, round-trip stable and preserves "
            "S1C geometry/animation gates. It does not accept final S2 surfacing."
        ),
    }
    Path(args.report).write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    if failures:
        raise RuntimeError("S2 R1 verification failed")


if __name__ == "__main__":
    main()
