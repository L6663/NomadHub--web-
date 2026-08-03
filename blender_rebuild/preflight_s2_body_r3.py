"""Fast S2-R3 gate before evidence rendering and GLB export."""

import argparse
import importlib.util
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

import bmesh
import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
BUILDER_PATH = SCRIPT_DIR / "build_s2_body_r3.py"
BUILDER_SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r3_builder", BUILDER_PATH)
if BUILDER_SPEC is None or BUILDER_SPEC.loader is None:
    raise RuntimeError(f"unable to load R3 builder: {BUILDER_PATH}")
r3 = importlib.util.module_from_spec(BUILDER_SPEC)
BUILDER_SPEC.loader.exec_module(r3)
builder = r3.builder
entry = r3.entry

VALIDATOR_PATH = SCRIPT_DIR / "validate_s2_body.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r3_base_validator", VALIDATOR_PATH)
if VALIDATOR_SPEC is None or VALIDATOR_SPEC.loader is None:
    raise RuntimeError(f"unable to load base validator: {VALIDATOR_PATH}")
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
    invalid_edges = [edge for edge in bm.edges if len(edge.link_faces) == 0 or len(edge.link_faces) > 2]
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
        loops.append({
            "vertices": len(component),
            "closed": all(len(adjacency[index]) == 2 for index in component),
        })
    result = {
        "boundary_edges": len(boundary_edges),
        "invalid_edges": len(invalid_edges),
        "loop_count": len(loops),
        "closed_loop_count": sum(loop["closed"] for loop in loops),
        "loop_vertex_counts": sorted(loop["vertices"] for loop in loops),
    }
    bm.free()
    return result


def visual_contract_report():
    failures = []
    frame_objects = [obj for obj in bpy.data.objects if bool(obj.get("s2_r3_visual_frame"))]
    expected_minimum = len(entry.SIDE_OPENINGS) * 4 + 4
    if len(frame_objects) < expected_minimum:
        failures.append(f"R3 frame object count {len(frame_objects)} < {expected_minimum}")
    for name in ("R3_A_PILLAR_L", "R3_A_PILLAR_R"):
        if bpy.data.objects.get(name) is None:
            failures.append(f"missing {name}")
    for name in ("DOOR_DRIVER_L", "DOOR_PASSENGER_R"):
        obj = bpy.data.objects.get(name)
        if obj is None or not bool(obj.get("s2_r3_tapered_cab_panel")):
            failures.append(f"{name} tapered-panel marker missing")
    for name in ("WHEEL_ARCH_FL", "WHEEL_ARCH_FR", "WHEEL_ARCH_RL", "WHEEL_ARCH_RR"):
        obj = bpy.data.objects.get(name)
        if obj is None or obj.get("s2_r3_visual_role") != "integrated_body_colour_wheel_lip":
            failures.append(f"{name} integrated wheel-lip marker missing")
    windshield = bpy.data.objects.get("GLASS_WINDSHIELD")
    if windshield is None or not bool(windshield.get("s2_r3_glass_inset")):
        failures.append("windshield inset marker missing")
    return {
        "frame_objects": len(frame_objects),
        "expected_minimum": expected_minimum,
        "failures": failures,
        "result": "PASS" if not failures else "FAIL",
    }


def build_source_body():
    for name in ("BODY_S2_CONTROL_CAGE", "BODY_S2_WIREFRAME", "S2_CUTTER_ARCH_FRONT", "S2_CUTTER_ARCH_REAR"):
        builder.r1.remove_object(name)
    body_parent = bpy.data.objects.get("BODY")
    body_material = bpy.data.materials.get("MAT_BODY_SILVER")
    if body_parent is None or body_material is None:
        raise RuntimeError("accepted S1C BODY root or material missing")
    builder.r1.freeze_s1c_reference()
    body = builder.build_control_cage(body_parent, body_material)
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
    visual_contract = visual_contract_report()
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
        failures.append(f"source has {connectivity['connected_components']} connected components")
    if connectivity["loose_vertices"] != 0:
        failures.append(f"source has {connectivity['loose_vertices']} loose vertices")
    if loops["invalid_edges"] != 0:
        failures.append(f"source has {loops['invalid_edges']} loose/over-connected edges")
    if loops["loop_count"] != expected_openings:
        failures.append(f"source opening loop count {loops['loop_count']} != {expected_openings}")
    if loops["closed_loop_count"] != expected_openings:
        failures.append(f"closed opening loops {loops['closed_loop_count']} != {expected_openings}")
    if modifiers != ["SUBSURF", "BEVEL"]:
        failures.append(f"modifier stack {modifiers} != ['SUBSURF', 'BEVEL']")
    failures.extend(frozen["failures"])
    failures.extend(wheel_clearance["failures"])
    failures.extend(visual_contract["failures"])

    report = {
        "schema": "nomadhub-s2-r3-preflight-v1",
        "stage": "S2",
        "iteration": "R3",
        "status": "PASS" if not failures else "FAIL",
        "purpose": "fail-fast source topology, wheel clearance and visual-contract gate",
        "topology": topology,
        "connectivity": connectivity,
        "opening_boundaries": loops,
        "expected_opening_count": expected_openings,
        "modifier_types": modifiers,
        "ring_count": len(builder.RING_XS),
        "frozen_positions": frozen,
        "wheel_body_clearance": wheel_clearance,
        "visual_contract": visual_contract,
        "failures": failures,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if failures:
        raise RuntimeError("S2 R3 fast preflight failed; evidence rendering was skipped")
    print("S2_R3_FAST_PREFLIGHT_PASS")


if __name__ == "__main__":
    main()
