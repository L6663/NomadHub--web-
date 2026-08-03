"""Fast S2-R2 source-geometry gate executed before proof rendering.

This preflight intentionally avoids six-view rendering and GLB export. It
constructs the exact final R2 source cage (including the raised wheel-well
floor), evaluates subdivision, and fails early on the defects that previously
consumed a full render cycle:

- non-quad or disconnected source topology;
- missing/merged/open door, hatch, window or windshield boundary loops;
- frozen axle/door/hatch anchor drift;
- tire/body intersection after the final modifier stack.
"""

import argparse
import importlib.util
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

import bmesh
import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
CLEARANCE_PATH = SCRIPT_DIR / "build_s2_body_r2_clearance.py"
CLEARANCE_SPEC = importlib.util.spec_from_file_location(
    "nomadhub_s2_r2_clearance_builder", CLEARANCE_PATH
)
if CLEARANCE_SPEC is None or CLEARANCE_SPEC.loader is None:
    raise RuntimeError(f"unable to load R2 clearance builder: {CLEARANCE_PATH}")
clearance = importlib.util.module_from_spec(CLEARANCE_SPEC)
CLEARANCE_SPEC.loader.exec_module(clearance)
entry = clearance.entry
builder = clearance.builder

VALIDATOR_PATH = SCRIPT_DIR / "validate_s2_body.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "nomadhub_s2_preflight_validator", VALIDATOR_PATH
)
if VALIDATOR_SPEC is None or VALIDATOR_SPEC.loader is None:
    raise RuntimeError(f"unable to load S2 validator: {VALIDATOR_PATH}")
validator = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(validator)


def parse_args():
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    return parser.parse_args(raw)


def boundary_loop_summary(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    boundary_edges = [edge for edge in bm.edges if len(edge.link_faces) == 1]
    invalid_edges = [
        edge for edge in bm.edges if len(edge.link_faces) == 0 or len(edge.link_faces) > 2
    ]
    adjacency = defaultdict(set)
    for edge in boundary_edges:
        first, second = edge.verts[0].index, edge.verts[1].index
        adjacency[first].add(second)
        adjacency[second].add(first)

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
        loops.append(
            {
                "vertices": len(component),
                "closed": all(len(adjacency[index]) == 2 for index in component),
            }
        )

    result = {
        "boundary_edges": len(boundary_edges),
        "invalid_edges": len(invalid_edges),
        "loop_count": len(loops),
        "closed_loop_count": sum(loop["closed"] for loop in loops),
        "loop_vertex_counts": sorted(loop["vertices"] for loop in loops),
    }
    bm.free()
    return result


def build_source_body():
    for name in (
        "BODY_S2_CONTROL_CAGE",
        "BODY_S2_WIREFRAME",
        "S2_CUTTER_ARCH_FRONT",
        "S2_CUTTER_ARCH_REAR",
    ):
        builder.r1.remove_object(name)

    body_parent = bpy.data.objects.get("BODY")
    body_material = bpy.data.materials.get("MAT_BODY_SILVER")
    if body_parent is None or body_material is None:
        raise RuntimeError("accepted S1C BODY root or body material missing")

    builder.r1.freeze_s1c_reference()
    body = entry.build_true_opening_cage(body_parent, body_material)
    bpy.context.view_layer.update()
    return body


def main():
    args = parse_args()
    body = build_source_body()
    topology = validator.polygon_statistics(body.data)
    connectivity = validator.topology_connectivity(body.data)
    loops = boundary_loop_summary(body.data)
    frozen = validator.frozen_position_report()
    wheel_clearance = validator.wheel_body_clearance()
    modifiers = [modifier.type for modifier in body.modifiers]
    expected_openings = len(entry.TRUE_OPENINGS)

    failures = []
    if topology["triangles"] != 0:
        failures.append(f"source contains {topology['triangles']} triangles")
    if topology["ngons"] != 0:
        failures.append(f"source contains {topology['ngons']} n-gons")
    if topology["quad_ratio"] != 1.0:
        failures.append(f"source quad ratio {topology['quad_ratio']:.6f} != 1.0")
    if connectivity["connected_components"] != 1:
        failures.append(
            f"source has {connectivity['connected_components']} connected components"
        )
    if connectivity["loose_vertices"] != 0:
        failures.append(f"source has {connectivity['loose_vertices']} loose vertices")
    if loops["invalid_edges"] != 0:
        failures.append(f"source has {loops['invalid_edges']} loose/over-connected edges")
    if loops["loop_count"] != expected_openings:
        failures.append(
            f"source opening loop count {loops['loop_count']} != {expected_openings}"
        )
    if loops["closed_loop_count"] != expected_openings:
        failures.append(
            f"closed opening loops {loops['closed_loop_count']} != {expected_openings}"
        )
    if modifiers != ["SUBSURF", "BEVEL"]:
        failures.append(f"modifier stack {modifiers} != ['SUBSURF', 'BEVEL']")
    if any(modifier.type == "BOOLEAN" for modifier in body.modifiers):
        failures.append("Boolean modifier remains in R2 source body")
    failures.extend(frozen["failures"])
    failures.extend(wheel_clearance["failures"])

    report = {
        "schema": "nomadhub-s2-r2-preflight-v1",
        "stage": "S2",
        "iteration": "R2",
        "status": "PASS" if not failures else "FAIL",
        "purpose": "fail-fast source topology and evaluated wheel-clearance gate",
        "topology": topology,
        "connectivity": connectivity,
        "opening_boundaries": loops,
        "expected_opening_count": expected_openings,
        "modifier_types": modifiers,
        "frozen_positions": frozen,
        "wheel_body_clearance": wheel_clearance,
        "failures": failures,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if failures:
        raise RuntimeError("S2 R2 fast preflight failed; proof rendering was skipped")
    print("S2_R2_FAST_PREFLIGHT_PASS")


if __name__ == "__main__":
    main()
