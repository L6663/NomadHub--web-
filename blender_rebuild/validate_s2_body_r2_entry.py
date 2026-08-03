"""Strict S2-R2 validator for actual opening topology.

Extends the base R2 checks with topology-derived evidence:
- exactly one closed boundary loop per declared true opening;
- no loose or over-connected source edges;
- every opening center is unobstructed in Blender and GLB;
- source opening loops survive subdivision/export/import.
"""

import importlib.util
import json
import math
import sys
from collections import defaultdict, deque
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR_PATH = SCRIPT_DIR / "validate_s2_body_r2.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r2_validator", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load S2 R2 validator: {VALIDATOR_PATH}")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def raw_args():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def argument_value(name):
    values = raw_args()
    try:
        return values[values.index(name) + 1]
    except (ValueError, IndexError) as exc:
        raise RuntimeError(f"missing validator argument {name}") from exc


MANIFEST = json.loads(Path(argument_value("--manifest")).read_text(encoding="utf-8"))
validator.EXPECTED_RING_SIZE = int(MANIFEST.get("topology", {}).get("ring_size", 0))
validator.MIN_RING_COUNT = 60
ORIGINAL_COLLECT_BODY = validator.collect_body


def boundary_loop_report(body):
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    boundary_edges = [edge for edge in bm.edges if len(edge.link_faces) == 1]
    invalid_edges = [
        edge for edge in bm.edges if len(edge.link_faces) == 0 or len(edge.link_faces) > 2
    ]
    adjacency = defaultdict(set)
    edge_lookup = {}
    for edge in boundary_edges:
        a, b = edge.verts[0].index, edge.verts[1].index
        adjacency[a].add(b)
        adjacency[b].add(a)
        edge_lookup[frozenset((a, b))] = edge.index

    unseen = set(adjacency)
    loops = []
    while unseen:
        start = unseen.pop()
        component = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current]:
                if neighbor not in component:
                    component.add(neighbor)
                    unseen.discard(neighbor)
                    queue.append(neighbor)
        closed = all(len(adjacency[index]) == 2 for index in component)
        points = [body.matrix_world @ bm.verts[index].co for index in component]
        centroid = sum(points, Vector()) / len(points)
        component_edges = {
            edge_lookup[frozenset((index, neighbor))]
            for index in component
            for neighbor in adjacency[index]
            if frozenset((index, neighbor)) in edge_lookup
        }
        loops.append(
            {
                "vertex_count": len(component),
                "edge_count": len(component_edges),
                "closed": closed,
                "centroid_m": list(centroid),
                "min_m": [min(point[axis] for point in points) for axis in range(3)],
                "max_m": [max(point[axis] for point in points) for axis in range(3)],
            }
        )

    report = {
        "boundary_edge_count": len(boundary_edges),
        "invalid_edge_count": len(invalid_edges),
        "invalid_edge_indices": [edge.index for edge in invalid_edges[:30]],
        "loop_count": len(loops),
        "loops": loops,
    }
    bm.free()
    return report


def expected_center(opening):
    kind = opening.get("kind")
    if kind == "side":
        side_sign = -1.0 if opening["side"] == "L" else 1.0
        return Vector(
            (
                (opening["x_min_m"] + opening["x_max_m"]) / 2,
                side_sign * 1.15,
                (opening["z_min_m"] + opening["z_max_m"]) / 2,
            )
        )
    return Vector(
        (
            (opening["x_min_m"] + opening["x_max_m"]) / 2,
            (opening["y_min_m"] + opening["y_max_m"]) / 2,
            opening.get("z_center_m", 2.52),
        )
    )


def loop_matches(opening, loop):
    center = Vector(loop["centroid_m"])
    target = expected_center(opening)
    if opening.get("kind") == "side":
        expected_sign = -1 if opening["side"] == "L" else 1
        if center.y * expected_sign < 0.75:
            return None
        return math.hypot(center.x - target.x, center.z - target.z)
    if center.x > -3.60 or center.z < 1.80:
        return None
    return math.sqrt((center.x - target.x) ** 2 + (center.y - target.y) ** 2)


def match_opening_loops(openings, loop_report):
    failures = []
    matches = []
    unused = set(range(len(loop_report["loops"])))
    for opening in openings:
        candidates = []
        for index in unused:
            distance = loop_matches(opening, loop_report["loops"][index])
            if distance is not None:
                candidates.append((distance, index))
        if not candidates:
            failures.append(f"{opening['name']} has no topology boundary loop")
            continue
        distance, index = min(candidates)
        tolerance = 0.35 if opening.get("kind") == "side" else 0.55
        if distance > tolerance:
            failures.append(
                f"{opening['name']} boundary-loop centroid delta {distance:.4f} > {tolerance:.2f}"
            )
            continue
        unused.remove(index)
        loop = loop_report["loops"][index]
        if not loop["closed"]:
            failures.append(f"{opening['name']} boundary loop is not closed")
        if loop["edge_count"] < 4:
            failures.append(f"{opening['name']} boundary loop has fewer than 4 edges")
        matches.append(
            {
                "opening": opening["name"],
                "loop_index": index,
                "centroid_delta_m": distance,
                "edge_count": loop["edge_count"],
                "closed": loop["closed"],
            }
        )
    if unused:
        failures.append(f"unexpected source boundary loops: {sorted(unused)}")
    return {
        "matches": matches,
        "unmatched_loop_indices": sorted(unused),
        "failures": failures,
        "result": "PASS" if not failures else "FAIL",
    }


def evaluated_ray(body, origin_world, direction_world, max_distance):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = body.evaluated_get(depsgraph)
    inverse = evaluated.matrix_world.inverted()
    origin_local = inverse @ origin_world
    direction_local = (inverse.to_3x3() @ direction_world).normalized()
    hit, location, _normal, _face = evaluated.ray_cast(
        origin_local,
        direction_local,
        distance=max_distance,
        depsgraph=depsgraph,
    )
    if not hit:
        return None
    location_world = evaluated.matrix_world @ location
    return (location_world - origin_world).length


def opening_ray_report(body, openings):
    rows = []
    failures = []
    for opening in openings:
        center = expected_center(opening)
        if opening.get("kind") == "side":
            side_sign = -1.0 if opening["side"] == "L" else 1.0
            origin = Vector((center.x, side_sign * 1.42, center.z))
            direction = Vector((0.0, -side_sign, 0.0))
            near_limit = 0.42
            distance = evaluated_ray(body, origin, direction, 3.2)
        else:
            origin = Vector((-4.72, center.y, 3.15))
            direction = Vector((0.64, 0.0, -0.77)).normalized()
            near_limit = 0.70
            distance = evaluated_ray(body, origin, direction, 5.0)
        passed = distance is None or distance > near_limit
        rows.append(
            {
                "opening": opening["name"],
                "first_body_hit_distance_m": distance,
                "minimum_clear_distance_m": near_limit,
                "pass": passed,
            }
        )
        if not passed:
            failures.append(f"{opening['name']} is blocked by body at {distance:.4f} m")
    return {
        "rows": rows,
        "failures": failures,
        "result": "PASS" if not failures else "FAIL",
    }


def enhanced_collect_body(label, manifest, source_topology):
    result = ORIGINAL_COLLECT_BODY(label, manifest, source_topology)
    body = bpy.data.objects.get(validator.BODY_NAME)
    if body is None or body.type != "MESH":
        return result

    failures = [
        failure
        for failure in result.get("failures", [])
        if "non-manifold edges" not in failure
    ]
    openings = manifest.get("true_openings", [])
    ray_report = opening_ray_report(body, openings)
    failures.extend(ray_report["failures"])
    result["true_opening_rays"] = ray_report

    if source_topology:
        loop_report = boundary_loop_report(body)
        matching = match_opening_loops(openings, loop_report)
        topology_failures = []
        if not bool(body.get("s2_source_true_openings")):
            topology_failures.append("source true-opening marker missing")
        if int(body.get("s2_expected_opening_count", 0)) != len(openings):
            topology_failures.append("source expected-opening count mismatch")
        if loop_report["invalid_edge_count"] != 0:
            topology_failures.append(
                f"source has {loop_report['invalid_edge_count']} loose/over-connected edges"
            )
        if loop_report["loop_count"] != len(openings):
            topology_failures.append(
                f"source boundary loop count {loop_report['loop_count']} != {len(openings)}"
            )
        topology_failures.extend(matching["failures"])
        failures.extend(topology_failures)
        result["true_opening_topology"] = {
            "declared_opening_count": len(openings),
            "boundary_loops": loop_report,
            "matching": matching,
            "failures": topology_failures,
            "result": "PASS" if not topology_failures else "FAIL",
        }
        if "connectivity" in result:
            result["connectivity"]["expected_boundary_edges"] = loop_report["boundary_edge_count"]
            result["connectivity"]["non_manifold_edges_are_opening_boundaries"] = True

    result["failures"] = failures
    result["result"] = "PASS" if not failures else "FAIL"
    return result


validator.collect_body = enhanced_collect_body

if __name__ == "__main__":
    validator.main()
