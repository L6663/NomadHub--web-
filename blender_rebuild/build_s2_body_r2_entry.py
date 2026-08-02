"""S2-R2 true-opening and source-wheel-arch entrypoint.

The base R2 builder establishes a dense all-quad longitudinal cage. This
entrypoint upgrades it from inset guides to actual source-mesh openings:
- 3 door openings
- 6 service-hatch openings
- 7 living-window openings
- 1 sloped windshield opening

The openings are produced by omitting aligned source quads, not by Boolean
modifiers. Their boundary edges are creased so Catmull-Clark evaluation keeps
usable frame shapes. Wheel arches remain part of the source topology.
"""

import importlib.util
import json
import sys
from pathlib import Path

import bmesh
import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
BUILDER_PATH = SCRIPT_DIR / "build_s2_body_r2.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r2_builder", BUILDER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load S2 R2 builder: {BUILDER_PATH}")

builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

builder.ARCH_RADIUS_M = 0.620
builder.WHEEL_WELL_HALF_WIDTH_M = 0.620

SIDE_OPENINGS = tuple(
    {
        "name": name,
        "kind": "side",
        "side": side,
        "x_min_m": x_min,
        "x_max_m": x_max,
        "z_min_m": z_min,
        "z_max_m": z_max,
    }
    for name, side, x_min, x_max, z_min, z_max, _ in builder.OPENINGS
)
WINDSHIELD_OPENING = {
    "name": "WINDSHIELD",
    "kind": "windshield",
    "side": "FRONT",
    "x_min_m": -4.300,
    "x_max_m": -3.860,
    "y_min_m": -0.920,
    "y_max_m": 0.920,
    "z_center_m": 2.520,
}
TRUE_OPENINGS = SIDE_OPENINGS + (WINDSHIELD_OPENING,)


def corrected_vertical_levels():
    values = set(round(value, 3) for value in builder.STANDARD_Z_LEVELS)
    for opening in SIDE_OPENINGS:
        for edge in (opening["z_min_m"], opening["z_max_m"]):
            for offset in (-0.035, 0.0, 0.035):
                value = edge + offset
                if 0.280 <= value <= 2.760:
                    values.add(round(value, 3))
    values.update((0.280, 2.760))
    return tuple(sorted(values))


builder.STANDARD_Z_LEVELS = corrected_vertical_levels()
builder.GRID_N = len(builder.STANDARD_Z_LEVELS)
builder.RING_SIZE = 4 * (builder.GRID_N - 1)
builder.opening_depth = lambda _x, _z, _side: 0.0


def corrected_expanded_ring_xs():
    values = set(round(value, 3) for value in builder.BASE_RING_XS)
    for opening in SIDE_OPENINGS:
        x_min = opening["x_min_m"]
        x_max = opening["x_max_m"]
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

    for value in (
        WINDSHIELD_OPENING["x_min_m"] - 0.040,
        WINDSHIELD_OPENING["x_min_m"],
        WINDSHIELD_OPENING["x_min_m"] + 0.040,
        (WINDSHIELD_OPENING["x_min_m"] + WINDSHIELD_OPENING["x_max_m"]) / 2,
        WINDSHIELD_OPENING["x_max_m"] - 0.040,
        WINDSHIELD_OPENING["x_max_m"],
        WINDSHIELD_OPENING["x_max_m"] + 0.040,
    ):
        values.add(round(value, 3))

    for center in (builder.FRONT_AXLE_X_M, builder.REAR_AXLE_X_M):
        for offset in (
            -0.660,
            -0.620,
            -0.580,
            -0.500,
            -0.400,
            -0.250,
            0.000,
            0.250,
            0.400,
            0.500,
            0.580,
            0.620,
            0.660,
        ):
            values.add(round(center + offset, 3))
    values.update((-4.495, 4.495))
    return tuple(sorted(values))


def corrected_boundary_index(i, j):
    last = builder.GRID_N - 1
    if j == 0:
        return i
    if i == last:
        return last + j
    if j == last:
        return (2 * last + 1) + (last - 1 - i)
    if i == 0:
        return (3 * last + 1) + (last - 1 - j)
    return None


builder.RING_XS = corrected_expanded_ring_xs()
builder.boundary_index = corrected_boundary_index


def side_opening_at(side, x_mid, z_mid):
    for opening in SIDE_OPENINGS:
        if opening["side"] != side:
            continue
        if (
            opening["x_min_m"] < x_mid < opening["x_max_m"]
            and opening["z_min_m"] < z_mid < opening["z_max_m"]
        ):
            return opening["name"]
    return None


def windshield_opening_at(x_mid, y_mid):
    return (
        WINDSHIELD_OPENING["x_min_m"] < x_mid < WINDSHIELD_OPENING["x_max_m"]
        and WINDSHIELD_OPENING["y_min_m"] < y_mid < WINDSHIELD_OPENING["y_max_m"]
    )


def build_true_opening_cage(parent, material):
    vertices = []
    section_cache = {}
    for x in builder.RING_XS:
        width, z_low, z_top = builder.section_dimensions(x)
        section_cache[x] = (width, z_low, z_top)
        vertices.extend(builder.grid_boundary_points(x, width, z_low, z_top))

    faces = []
    omitted_cells = {opening["name"]: 0 for opening in TRUE_OPENINGS}
    last = builder.GRID_N - 1
    ring_size = builder.RING_SIZE

    for ring_index in range(len(builder.RING_XS) - 1):
        current = ring_index * ring_size
        following = (ring_index + 1) * ring_size
        x_mid = (builder.RING_XS[ring_index] + builder.RING_XS[ring_index + 1]) / 2

        for point_index in range(ring_size):
            nxt = (point_index + 1) % ring_size
            quad = (
                current + point_index,
                following + point_index,
                following + nxt,
                current + nxt,
            )
            points = [vertices[index] for index in quad]
            z_mid = sum(point[2] for point in points) / 4
            y_mid = sum(point[1] for point in points) / 4
            opening_name = None

            if last <= point_index < 2 * last:
                opening_name = side_opening_at("R", x_mid, z_mid)
            elif 3 * last <= point_index < 4 * last:
                opening_name = side_opening_at("L", x_mid, z_mid)
            elif 2 * last <= point_index < 3 * last and windshield_opening_at(x_mid, y_mid):
                opening_name = WINDSHIELD_OPENING["name"]

            if opening_name is not None:
                omitted_cells[opening_name] += 1
                continue
            faces.append(quad)

    front_x = builder.RING_XS[0]
    rear_x = builder.RING_XS[-1]
    builder.append_quad_cap(
        vertices,
        faces,
        0,
        front_x,
        *section_cache[front_x],
        reverse=True,
    )
    builder.append_quad_cap(
        vertices,
        faces,
        (len(builder.RING_XS) - 1) * ring_size,
        rear_x,
        *section_cache[rear_x],
        reverse=False,
    )

    missing = [name for name, count in omitted_cells.items() if count == 0]
    if missing:
        raise RuntimeError(f"true opening cells were not generated: {missing}")

    mesh = bpy.data.meshes.new("BODY_S2_CONTROL_CAGE_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=True)
    mesh.update(calc_edges=True)

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    loose = [vertex for vertex in bm.verts if not vertex.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update(calc_edges=True)

    crease = mesh.attributes.get("crease_edge")
    if crease is None:
        crease = mesh.attributes.new("crease_edge", "FLOAT", "EDGE")
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()
    boundary_indices = [edge.index for edge in bm.edges if len(edge.link_faces) == 1]
    invalid_nonmanifold = [
        edge.index for edge in bm.edges if len(edge.link_faces) not in (1, 2)
    ]
    bm.free()
    if invalid_nonmanifold:
        raise RuntimeError(f"invalid non-manifold source edges: {invalid_nonmanifold[:20]}")
    for edge_index in boundary_indices:
        crease.data[edge_index].value = 0.82

    body = bpy.data.objects.new("BODY_S2_CONTROL_CAGE", mesh)
    bpy.context.scene.collection.objects.link(body)
    body.parent = parent
    body.data.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = True

    body["nomadhub_semantic_node"] = "BODY_S2_CONTROL_CAGE"
    body["s2_stage"] = "S2_R2_TRUE_OPENINGS"
    body["s2_ring_count"] = len(builder.RING_XS)
    body["s2_ring_size"] = builder.RING_SIZE
    body["s2_ring_x_m"] = json.dumps(list(builder.RING_XS))
    body["s2_opening_guides"] = json.dumps([opening["name"] for opening in SIDE_OPENINGS])
    body["s2_true_openings"] = json.dumps([opening["name"] for opening in TRUE_OPENINGS])
    body["s2_expected_opening_count"] = len(TRUE_OPENINGS)
    body["s2_all_quad_caps"] = True
    body["s2_source_wheel_arch_topology"] = True
    body["s2_source_true_openings"] = True
    body["s1c_frozen_wheelbase_m"] = builder.WHEELBASE_M
    body["s1c_frozen_front_axle_x_m"] = builder.FRONT_AXLE_X_M
    body["s1c_frozen_rear_axle_x_m"] = builder.REAR_AXLE_X_M

    subdivision = body.modifiers.new("S2_Subdivision", "SUBSURF")
    subdivision.subdivision_type = "CATMULL_CLARK"
    subdivision.levels = 2
    subdivision.render_levels = 2
    subdivision.show_only_control_edges = True
    bevel = body.modifiers.new("S2_Support_Bevel", "BEVEL")
    bevel.width = 0.008
    bevel.segments = 2
    bevel.limit_method = "ANGLE"
    return body


builder.build_control_cage = build_true_opening_cage


def patch_manifest(path):
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["stage_status"] = "R2_TRUE_OPENING_CANDIDATE_REVIEW_REQUIRED"
    payload["true_openings"] = list(TRUE_OPENINGS)
    payload["true_opening_count"] = len(TRUE_OPENINGS)
    payload["source_true_openings"] = True
    payload["topology"]["ring_size"] = builder.RING_SIZE
    payload["topology"]["vertical_level_count"] = builder.GRID_N
    payload["topology"]["vertical_levels_m"] = list(builder.STANDARD_Z_LEVELS)
    payload["scope_note"] = (
        "S2-R2 contains all-quad front/rear caps, source-topology wheel arches and "
        "17 actual source-mesh openings with creased boundary loops. It remains a "
        "grey-model topology candidate pending automated and visual curvature review."
    )
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    args = builder.parse_args()
    builder.main()
    patch_manifest(args.manifest)
