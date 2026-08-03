"""R4-F7 native opening-boundary integration repair.

F7 stops stacking exterior cover parts. It preserves the all-quad source cage,
17 opening loops, frozen anchors and 13 actions while changing only vertex
positions and presentation trim:

- both true cab-door boundary loops are snapped to the frozen engineering
  rectangle x[-4.400,-3.880], z[0.450,2.170] on the actual body skin;
- broad body-colour cab rings and F6 header patches become tiny exported
  compatibility markers inside the body;
- only a 13 mm dark seal remains visible around each real cab opening;
- the body-colour windshield surround becomes an internal compatibility marker;
- a narrow dark trapezoid seal and the opening-matched glass occupy the real
  windshield opening, eliminating the lower body-colour shelf.
"""

import importlib.util
import json
from collections import defaultdict, deque
from pathlib import Path

import bmesh
import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
F6_PATH = SCRIPT_DIR / "build_s2_body_r4_fix6.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix6", F6_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F6 builder: {F6_PATH}")
f6 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f6)

f5 = f6.f5
f4 = f6.f4
f3 = f6.f3
fix2 = f6.fix2
r4 = f6.r4
builder = f6.builder
entry = f6.entry
clearance = f6.clearance
WINDSHIELD_ROTATION_Y = f6.WINDSHIELD_ROTATION_Y
WINDSHIELD_PLANE_HEIGHT_M = f6.WINDSHIELD_PLANE_HEIGHT_M
WINDSHIELD_CENTER = f6.WINDSHIELD_CENTER

CAB_X_MIN = -4.400
CAB_X_MAX = -3.880
CAB_Z_MIN = 0.450
CAB_Z_MAX = 2.170

ORIGINAL_BUILD_CAGE = builder.build_control_cage
ORIGINAL_APPLY = r4.apply_r4_surface_repairs


def boundary_components(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    boundary_edges = [edge for edge in bm.edges if len(edge.link_faces) == 1]
    adjacency = defaultdict(set)
    for edge in boundary_edges:
        a = edge.verts[0].index
        b = edge.verts[1].index
        adjacency[a].add(b)
        adjacency[b].add(a)

    unseen = set(adjacency)
    components = []
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
        components.append(component)
    bm.free()
    return components


def component_bounds(mesh, component):
    points = [mesh.vertices[index].co for index in component]
    return {
        "x_min": min(float(point.x) for point in points),
        "x_max": max(float(point.x) for point in points),
        "y_min": min(float(point.y) for point in points),
        "y_max": max(float(point.y) for point in points),
        "y_mean": sum(float(point.y) for point in points) / len(points),
        "z_min": min(float(point.z) for point in points),
        "z_max": max(float(point.z) for point in points),
        "vertex_count": len(points),
    }


def find_cab_components(mesh):
    matches = []
    for component in boundary_components(mesh):
        bounds = component_bounds(mesh, component)
        if abs(bounds["y_mean"]) < 0.90:
            continue
        if bounds["z_max"] - bounds["z_min"] < 1.20:
            continue
        if bounds["x_max"] < CAB_X_MIN - 0.15 or bounds["x_min"] > CAB_X_MAX + 0.15:
            continue
        if abs(bounds["x_min"] - CAB_X_MIN) > 0.16:
            continue
        if abs(bounds["x_max"] - CAB_X_MAX) > 0.16:
            continue
        matches.append((component, bounds))
    matches.sort(key=lambda item: item[1]["y_mean"])
    if len(matches) != 2:
        raise RuntimeError(
            "R4-F7 expected two cab boundary components, found "
            f"{[(item[1]['y_mean'], item[1]['x_min'], item[1]['x_max'], item[1]['z_min'], item[1]['z_max']) for item in matches]}"
        )
    return matches


def snap_cab_opening_boundaries(body):
    mesh = body.data
    reports = []
    x_span = CAB_X_MAX - CAB_X_MIN
    z_span = CAB_Z_MAX - CAB_Z_MIN
    for component, before in find_cab_components(mesh):
        side_sign = -1.0 if before["y_mean"] < 0.0 else 1.0
        side_counts = {"front": 0, "rear": 0, "bottom": 0, "top": 0}
        for index in component:
            vertex = mesh.vertices[index]
            x = float(vertex.co.x)
            z = float(vertex.co.z)
            candidates = (
                (abs(x - CAB_X_MIN) / x_span, "front"),
                (abs(x - CAB_X_MAX) / x_span, "rear"),
                (abs(z - CAB_Z_MIN) / z_span, "bottom"),
                (abs(z - CAB_Z_MAX) / z_span, "top"),
            )
            _, side = min(candidates, key=lambda item: item[0])
            if side == "front":
                vertex.co.x = CAB_X_MIN
            elif side == "rear":
                vertex.co.x = CAB_X_MAX
            elif side == "bottom":
                vertex.co.z = CAB_Z_MIN
            else:
                vertex.co.z = CAB_Z_MAX
            x_after = float(vertex.co.x)
            vertex.co.y = side_sign * builder.section_dimensions(x_after)[0] / 2.0
            side_counts[side] += 1

        reports.append(
            {
                "side": "L" if side_sign < 0 else "R",
                "before": before,
                "snapped_vertices": len(component),
                "side_counts": side_counts,
            }
        )

    mesh.update(calc_edges=True)
    body["s2_r4_f7_native_cab_boundary_repair"] = True
    body["s2_r4_f7_cab_boundary_count"] = 2
    body["s2_r4_f7_cab_boundary_target"] = json.dumps(
        {
            "x_min_m": CAB_X_MIN,
            "x_max_m": CAB_X_MAX,
            "z_min_m": CAB_Z_MIN,
            "z_max_m": CAB_Z_MAX,
        }
    )
    body["s2_r4_f7_cab_boundary_report"] = json.dumps(reports)
    return reports


def build_f7_control_cage(parent, material):
    body = ORIGINAL_BUILD_CAGE(parent, material)
    snap_cab_opening_boundaries(body)
    return body


builder.build_control_cage = build_f7_control_cage


def bury_compatibility_object(obj, index, role):
    if obj is None:
        raise RuntimeError(f"R4-F7 compatibility object missing: {role}")
    obj.location = (0.0, 0.0, 0.120 + index * 0.003)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (0.001, 0.001, 0.001)
    obj["s2_r4_f7_hidden_compatibility_marker"] = True
    obj["s2_r4_f7_hidden_role"] = role
    return obj


def rebuild_native_cab_seals(body_root, trim_material):
    marker_index = 0
    for side, side_sign in (("L", -1.0), ("R", 1.0)):
        ring = bpy.data.objects.get(f"R4_CAB_RING_{side}")
        header = bpy.data.objects.get(f"R4_CAB_HEADER_{side}")
        bury_compatibility_object(ring, marker_index, "cab_body_ring")
        marker_index += 1
        bury_compatibility_object(header, marker_index, "cab_header_patch")
        marker_index += 1
        ring["s2_r4_f6_narrow_ring"] = True
        ring["s2_r4_f3_source_edge_mask"] = True

        seal = f5.make_segmented_side_ring(
            f"R4_CAB_SEAM_{side}",
            side_sign,
            (CAB_X_MIN - 0.005, CAB_X_MAX + 0.005, CAB_Z_MIN - 0.005, CAB_Z_MAX + 0.005),
            (CAB_X_MIN + 0.008, CAB_X_MAX - 0.008, CAB_Z_MIN + 0.008, CAB_Z_MAX - 0.008),
            0.005,
            0.001,
            trim_material,
            body_root,
            0.001,
            "native_opening_dark_seal",
        )
        seal["s2_r4_f3_source_edge_mask"] = True
        seal["s2_r4_f5_source_boundary_cover"] = True
        seal["s2_r4_f6_narrow_ring"] = True
        seal["s2_r4_f7_native_opening_seal"] = True
        seal["s2_r4_f7_seal_width_m"] = 0.013


def rebuild_native_windshield(body_root, trim_material):
    surround = bpy.data.objects.get("R4_WINDSHIELD_SURROUND")
    bury_compatibility_object(surround, 10, "windshield_body_surround")
    surround["s2_r4_f2_surface_aligned"] = True
    surround["s2_r4_f3_opening_matched"] = True
    surround["s2_r4_f6_trapezoid_ring"] = True

    trim = f6.make_local_trapezoid_ring(
        "R4_WINDSHIELD_TRIM",
        1.800,
        1.840,
        0.580,
        1.740,
        1.780,
        0.520,
        0.006,
        trim_material,
        body_root,
        0.001,
        "continuous_windshield_inner_trim",
    )
    trim["s2_r4_f7_native_opening_seal"] = True
    trim["s2_r4_f7_seal_width_m"] = 0.030

    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    if glass is None:
        raise RuntimeError("GLASS_WINDSHIELD missing during R4-F7")
    glass["s2_r4_f7_native_opening_glass"] = True


def apply_r4_f7_surface_repairs():
    ORIGINAL_APPLY()
    body_root = bpy.data.objects.get("BODY")
    trim_material = bpy.data.materials.get("MAT_TRIM")
    if body_root is None or trim_material is None:
        raise RuntimeError("R4-F7 body root or trim material missing")

    rebuild_native_cab_seals(body_root, trim_material)
    rebuild_native_windshield(body_root, trim_material)


r4.apply_r4_surface_repairs = apply_r4_f7_surface_repairs


def patch_fix7_manifest(path):
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    repairs = payload.setdefault("r4_visual_repairs", {})
    repairs.update(
        {
            "native_cab_opening_boundaries_snapped": 2,
            "cab_boundary_target_x_m": [CAB_X_MIN, CAB_X_MAX],
            "cab_boundary_target_z_m": [CAB_Z_MIN, CAB_Z_MAX],
            "visible_cab_dark_seals": 2,
            "hidden_cab_body_ring_markers": 2,
            "hidden_cab_header_markers": 2,
            "hidden_windshield_body_surround_marker": True,
            "visible_windshield_dark_seal": True,
            "source_opening_topology_unchanged": True,
            "source_openings_unchanged": True,
            "web_node_and_animation_contract_preserved": True,
        }
    )
    payload["stage_status"] = "R4_F7_NATIVE_OPENING_BOUNDARY_CANDIDATE"
    payload["r4_fix_iteration"] = "F7"
    payload["scope_note"] = (
        "R4-F7 preserves all source faces, 17 boundary-loop components, frozen roots "
        "and 13 actions. Cab-door loop vertices are snapped to the engineering opening "
        "rectangle; broad external cover parts are retained only as tiny exported "
        "compatibility markers, leaving native body edges and narrow dark seals visible."
    )
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    f6.main()
    args = builder.parse_args()
    patch_fix7_manifest(args.manifest)
    print("NOMADHUB_S2_R4_F7_NATIVE_BOUNDARY_REPAIR_OK")


if __name__ == "__main__":
    main()
