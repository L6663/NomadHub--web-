import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


SCRIPT_DIR = Path(__file__).resolve().parent
R1_PATH = SCRIPT_DIR / "build_s2_body.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r1_builder", R1_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load S2 R1 builder: {R1_PATH}")
r1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r1)


OVERALL_LENGTH_M = 8.990
OVERALL_WIDTH_M = 2.350
OVERALL_HEIGHT_M = 3.050
FRONT_AXLE_X_M = -3.245
REAR_AXLE_X_M = 1.905
WHEELBASE_M = 5.150
BODY_HALF_WIDTH_M = 1.150
GRID_N = 13
RING_SIZE = 4 * (GRID_N - 1)
ARCH_RADIUS_M = 0.560
ARCH_CENTER_Z_M = 0.430
WHEEL_WELL_HALF_WIDTH_M = 0.700
RECESS_DEPTH_M = 0.035

STANDARD_Z_LEVELS = (
    0.280,
    0.380,
    0.650,
    0.920,
    1.150,
    1.520,
    1.740,
    1.930,
    2.100,
    2.420,
    2.540,
    2.650,
    2.760,
)

BASE_RING_XS = (
    -4.495, -4.430, -4.400, -4.300, -4.080, -3.900, -3.880, -3.800,
    -3.750, -3.245, -2.710, -2.600, -2.500, -2.475, -1.950,
    -1.425, -0.880, -0.820, -0.040, 0.020, 0.225, 0.750, 1.275,
    1.340, 1.370, 1.905, 2.440, 2.500, 2.525, 3.050, 3.575,
    4.350, 4.495,
)

OPENINGS = (
    ("CAB_DOOR_L", "L", -4.400, -3.880, 0.450, 2.170, 0.024),
    ("CAB_DOOR_R", "R", -4.400, -3.880, 0.450, 2.170, 0.024),
    ("LIVING_DOOR_R", "R", -0.820, -0.040, 0.340, 2.300, 0.026),
    ("HATCH_L_1", "L", -2.475, -1.425, 0.370, 0.920, 0.030),
    ("HATCH_L_2", "L", -0.175, 0.875, 0.370, 0.920, 0.030),
    ("HATCH_L_3", "L", 2.525, 3.575, 0.370, 0.920, 0.030),
    ("HATCH_R_1", "R", -2.475, -1.425, 0.370, 0.920, 0.030),
    ("HATCH_R_2", "R", 0.225, 1.275, 0.370, 0.920, 0.030),
    ("HATCH_R_3", "R", 2.525, 3.575, 0.370, 0.920, 0.030),
    ("WINDOW_L_1", "L", -2.275, -1.225, 1.740, 2.420, RECESS_DEPTH_M),
    ("WINDOW_L_2", "L", -0.875, 0.175, 1.740, 2.420, RECESS_DEPTH_M),
    ("WINDOW_L_3", "L", 0.800, 2.100, 1.740, 2.420, RECESS_DEPTH_M),
    ("WINDOW_L_4", "L", 2.650, 3.550, 1.740, 2.420, RECESS_DEPTH_M),
    ("WINDOW_R_1", "R", -2.275, -1.225, 1.740, 2.420, RECESS_DEPTH_M),
    ("WINDOW_R_3", "R", 0.800, 2.100, 1.740, 2.420, RECESS_DEPTH_M),
    ("WINDOW_R_4", "R", 2.650, 3.550, 1.740, 2.420, RECESS_DEPTH_M),
)


def parse_args():
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--roundtrip", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--preview", required=True)
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    parser.add_argument("--top", required=True)
    parser.add_argument("--wire-left", required=True)
    parser.add_argument("--wire-right", required=True)
    return parser.parse_args(raw)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expanded_ring_xs():
    values = set(round(value, 3) for value in BASE_RING_XS)
    for _, _, x_min, x_max, _, _, _ in OPENINGS:
        center = (x_min + x_max) / 2
        for value in (
            x_min - 0.040,
            x_min,
            x_min + 0.040,
            center,
            x_max - 0.040,
            x_max,
            x_max + 0.040,
        ):
            if -4.495 < value < 4.495:
                values.add(round(value, 3))
    for center in (FRONT_AXLE_X_M, REAR_AXLE_X_M):
        for offset in (-0.600, -0.560, -0.500, 0.0, 0.500, 0.560, 0.600):
            values.add(round(center + offset, 3))
    values.add(-4.495)
    values.add(4.495)
    return tuple(sorted(values))


RING_XS = expanded_ring_xs()


def section_dimensions(x):
    front_keys = (
        (-4.495, 1.850, 0.300, 1.400),
        (-4.430, 2.030, 0.295, 1.820),
        (-4.300, 2.180, 0.288, 2.350),
        (-4.080, 2.270, 0.282, 2.670),
        (-3.880, 2.300, 0.280, 2.760),
    )
    rear_keys = (
        (4.350, 2.300, 0.280, 2.760),
        (4.495, 2.230, 0.300, 2.560),
    )
    if x <= front_keys[-1][0]:
        for first, second in zip(front_keys, front_keys[1:]):
            if first[0] <= x <= second[0]:
                return r1.interpolate(x, first, second)
        return front_keys[0][1:]
    if x >= rear_keys[0][0]:
        return r1.interpolate(x, rear_keys[0], rear_keys[1])
    return 2.300, 0.280, 2.760


def remapped_z_levels(z_low, z_top):
    standard_span = STANDARD_Z_LEVELS[-1] - STANDARD_Z_LEVELS[0]
    return tuple(
        z_low + ((value - STANDARD_Z_LEVELS[0]) / standard_span) * (z_top - z_low)
        for value in STANDARD_Z_LEVELS
    )


def opening_depth(x, z, side):
    depth = 0.0
    for _, opening_side, x_min, x_max, z_min, z_max, candidate in OPENINGS:
        if opening_side != side:
            continue
        if x_min + 0.020 < x < x_max - 0.020 and z_min + 0.015 < z < z_max - 0.015:
            depth = max(depth, candidate)
    return depth


def wheel_arch_height(x):
    result = None
    for center in (FRONT_AXLE_X_M, REAR_AXLE_X_M):
        dx = x - center
        if abs(dx) <= ARCH_RADIUS_M:
            height = ARCH_CENTER_Z_M + math.sqrt(max(0.0, ARCH_RADIUS_M ** 2 - dx ** 2))
            result = height if result is None else max(result, height)
    return result


def grid_boundary_points(x, width, z_low, z_top):
    half = width / 2
    lower_corner = min(0.120, half * 0.12)
    roof_corner = min(0.180, half * 0.18)
    levels = list(remapped_z_levels(z_low, z_top))
    arch_height = wheel_arch_height(x)
    if arch_height is not None:
        levels[1] = max(levels[1], arch_height)
        levels[2] = max(levels[2], arch_height + 0.040)
        levels[3] = max(levels[3], arch_height + 0.080)
        for index in range(1, len(levels)):
            levels[index] = max(levels[index], levels[index - 1] + 0.015)
        levels[-1] = z_top

    points = []
    bottom_left = -half + lower_corner
    bottom_right = half - lower_corner
    if arch_height is not None:
        bottom_left = -WHEEL_WELL_HALF_WIDTH_M
        bottom_right = WHEEL_WELL_HALF_WIDTH_M
    for i in range(GRID_N):
        factor = i / (GRID_N - 1)
        points.append((x, bottom_left + (bottom_right - bottom_left) * factor, z_low))

    for j in range(1, GRID_N):
        z = levels[j]
        y = half - opening_depth(x, z, "R")
        if j == GRID_N - 1:
            y = half - roof_corner
        points.append((x, y, z))

    roof_right = half - roof_corner
    roof_left = -half + roof_corner
    for i in range(GRID_N - 2, -1, -1):
        factor = i / (GRID_N - 1)
        points.append((x, roof_left + (roof_right - roof_left) * factor, z_top))

    for j in range(GRID_N - 2, 0, -1):
        z = levels[j]
        y = -half + opening_depth(x, z, "L")
        points.append((x, y, z))

    if len(points) != RING_SIZE:
        raise RuntimeError(f"R2 ring size {len(points)} != {RING_SIZE}")
    return points


def boundary_index(i, j):
    last = GRID_N - 1
    if j == 0:
        return i
    if i == last:
        return last + j
    if j == last:
        return last + last + (last - 1 - i)
    if i == 0:
        return last + last + last + (last - 1 - j)
    return None


def cap_grid_positions(x, width, z_low, z_top):
    half = width / 2
    lower_corner = min(0.120, half * 0.12)
    roof_corner = min(0.180, half * 0.18)
    levels = remapped_z_levels(z_low, z_top)
    rows = []
    for j in range(GRID_N):
        z = levels[j]
        if j == 0:
            left, right = -half + lower_corner, half - lower_corner
        elif j == GRID_N - 1:
            left, right = -half + roof_corner, half - roof_corner
        else:
            left, right = -half, half
        row = []
        for i in range(GRID_N):
            factor = i / (GRID_N - 1)
            row.append((x, left + (right - left) * factor, z))
        rows.append(row)
    return rows


def append_quad_cap(vertices, faces, ring_start, x, width, z_low, z_top, reverse):
    grid = cap_grid_positions(x, width, z_low, z_top)
    mapping = {}
    for j in range(GRID_N):
        for i in range(GRID_N):
            boundary = boundary_index(i, j)
            if boundary is not None:
                mapping[(i, j)] = ring_start + boundary
            else:
                mapping[(i, j)] = len(vertices)
                vertices.append(grid[j][i])

    for j in range(GRID_N - 1):
        for i in range(GRID_N - 1):
            quad = (
                mapping[(i, j)],
                mapping[(i + 1, j)],
                mapping[(i + 1, j + 1)],
                mapping[(i, j + 1)],
            )
            faces.append(tuple(reversed(quad)) if reverse else quad)


def build_control_cage(parent, material):
    vertices = []
    section_cache = {}
    for x in RING_XS:
        width, z_low, z_top = section_dimensions(x)
        section_cache[x] = (width, z_low, z_top)
        vertices.extend(grid_boundary_points(x, width, z_low, z_top))

    faces = []
    for ring_index in range(len(RING_XS) - 1):
        current = ring_index * RING_SIZE
        following = (ring_index + 1) * RING_SIZE
        for point_index in range(RING_SIZE):
            nxt = (point_index + 1) % RING_SIZE
            faces.append((current + point_index, following + point_index, following + nxt, current + nxt))

    front_x = RING_XS[0]
    rear_x = RING_XS[-1]
    append_quad_cap(vertices, faces, 0, front_x, *section_cache[front_x], reverse=True)
    append_quad_cap(
        vertices,
        faces,
        (len(RING_XS) - 1) * RING_SIZE,
        rear_x,
        *section_cache[rear_x],
        reverse=False,
    )

    mesh = bpy.data.meshes.new("BODY_S2_CONTROL_CAGE_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=True)
    mesh.update(calc_edges=True)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update(calc_edges=True)

    body = bpy.data.objects.new("BODY_S2_CONTROL_CAGE", mesh)
    bpy.context.scene.collection.objects.link(body)
    body.parent = parent
    body.data.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = True

    body["nomadhub_semantic_node"] = "BODY_S2_CONTROL_CAGE"
    body["s2_stage"] = "S2_R2_SOURCE_TOPOLOGY"
    body["s2_ring_count"] = len(RING_XS)
    body["s2_ring_size"] = RING_SIZE
    body["s2_ring_x_m"] = json.dumps(list(RING_XS))
    body["s2_opening_guides"] = json.dumps([item[0] for item in OPENINGS])
    body["s2_all_quad_caps"] = True
    body["s2_source_wheel_arch_topology"] = True
    body["s1c_frozen_wheelbase_m"] = WHEELBASE_M
    body["s1c_frozen_front_axle_x_m"] = FRONT_AXLE_X_M
    body["s1c_frozen_rear_axle_x_m"] = REAR_AXLE_X_M

    subdivision = body.modifiers.new("S2_Subdivision", "SUBSURF")
    subdivision.subdivision_type = "CATMULL_CLARK"
    subdivision.levels = 2
    subdivision.render_levels = 2
    subdivision.show_only_control_edges = True
    bevel = body.modifiers.new("S2_Support_Bevel", "BEVEL")
    bevel.width = 0.010
    bevel.segments = 2
    bevel.limit_method = "ANGLE"
    return body


def topology_metrics(mesh):
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
        "ring_count": len(RING_XS),
        "ring_size": RING_SIZE,
        "ring_x_m": list(RING_XS),
        "cap_grid_size": GRID_N,
    }


def main():
    args = parse_args()
    scene = bpy.context.scene
    body_parent = bpy.data.objects.get("BODY")
    body_material = bpy.data.materials.get("MAT_BODY_SILVER")
    if body_parent is None or body_material is None:
        raise RuntimeError("accepted S1C body root or material missing")

    for name in (
        "BODY_S2_CONTROL_CAGE",
        "BODY_S2_WIREFRAME",
        "S2_CUTTER_ARCH_FRONT",
        "S2_CUTTER_ARCH_REAR",
    ):
        r1.remove_object(name)

    references = r1.freeze_s1c_reference()
    body = build_control_cage(body_parent, body_material)
    wire = r1.make_wireframe_copy(body, r1.make_wire_material())

    scene["nomadhub_stage"] = "S2"
    scene["nomadhub_s2_iteration"] = "R2"
    scene["s2_status"] = "R2_CANDIDATE_REVIEW_REQUIRED"
    scene["s2_source_stage"] = "S1C_ACCEPTED"
    scene["wheelbase_m"] = WHEELBASE_M

    camera = bpy.data.objects.get("Camera")
    if camera is None or camera.type != "CAMERA":
        raise RuntimeError("Camera missing")
    scene.camera = camera
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    output_dir = Path(args.output).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    r1.set_wire_visibility(wire, False)
    bpy.ops.wm.save_as_mainfile(filepath=args.output, compress=True)
    Path(args.output + "1").unlink(missing_ok=True)

    r1.render(scene, camera, args.preview, (-11.0, -10.0, 7.2), (0, 0, 1.35))
    r1.render(scene, camera, args.left, (0, -14, 1.55), (0, 0, 1.45), 10.5)
    r1.render(scene, camera, args.right, (0, 14, 1.55), (0, 0, 1.45), 10.5)
    r1.render(scene, camera, args.top, (0, 0, 14), (0, 0, 0), 10.5)

    body.hide_render = True
    r1.set_wire_visibility(wire, True)
    r1.render(scene, camera, args.wire_left, (0, -14, 1.55), (0, 0, 1.45), 10.5)
    r1.render(scene, camera, args.wire_right, (0, 14, 1.55), (0, 0, 1.45), 10.5)
    body.hide_render = False
    r1.set_wire_visibility(wire, False)
    scene.frame_set(1)

    animation_mode = r1.active_actions_merged_mode()
    r1.export_gltf_compatible(args.roundtrip, animation_mode)
    bpy.ops.wm.save_as_mainfile(filepath=args.output, compress=True)
    Path(args.output + "1").unlink(missing_ok=True)

    source_manifest = {}
    manifest_path = Path(args.manifest)
    if manifest_path.exists():
        source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    payload = {
        "artifact_type": "genuine_blender_native_project",
        "project": "NomadHub General3",
        "version": "V1.7",
        "stage": "S2",
        "iteration": "R2",
        "stage_status": "R2_CANDIDATE_REVIEW_REQUIRED",
        "source_stage": "S1C_ACCEPTED",
        "source_blend_sha256": source_manifest.get("blend_sha256"),
        "blender_version": bpy.app.version_string,
        "blend": args.output,
        "blend_bytes": Path(args.output).stat().st_size,
        "blend_sha256": sha256(args.output),
        "roundtrip_glb": args.roundtrip,
        "roundtrip_sha256": sha256(args.roundtrip),
        "preview": args.preview,
        "proof_images": {
            "left_orthographic": args.left,
            "right_orthographic": args.right,
            "top_orthographic": args.top,
            "left_wireframe": args.wire_left,
            "right_wireframe": args.wire_right,
        },
        "objects": len(bpy.data.objects),
        "meshes": len(bpy.data.meshes),
        "materials": len(bpy.data.materials),
        "actions": len(bpy.data.actions),
        "units": "meters",
        "body_object": body.name,
        "topology": topology_metrics(body.data),
        "modifier_types": [modifier.type for modifier in body.modifiers],
        "opening_guides": [
            {
                "name": name,
                "side": side,
                "x_min_m": x_min,
                "x_max_m": x_max,
                "z_min_m": z_min,
                "z_max_m": z_max,
                "recess_depth_m": depth,
            }
            for name, side, x_min, x_max, z_min, z_max, depth in OPENINGS
        ],
        "source_wheel_arch_topology": True,
        "all_quad_caps": True,
        "frozen_references": references,
        "frozen_geometry": {
            "overall_length_m": OVERALL_LENGTH_M,
            "overall_width_m": OVERALL_WIDTH_M,
            "overall_height_m": OVERALL_HEIGHT_M,
            "front_axle_x_m": FRONT_AXLE_X_M,
            "rear_axle_x_m": REAR_AXLE_X_M,
            "wheelbase_m": WHEELBASE_M,
        },
        "glb_animation_export_mode": animation_mode,
        "scope_note": (
            "S2-R2 replaces cap n-gons and Boolean wheel arches with all-quad source "
            "topology, adds door/window/hatch-aligned support rings and inset guides, "
            "and remains a review candidate rather than final Class-A surfacing."
        ),
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("NOMADHUB_S2_R2_SOURCE_TOPOLOGY_OK")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
