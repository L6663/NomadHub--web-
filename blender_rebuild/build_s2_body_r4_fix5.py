"""R4-F5 visual integration repair for the cab and windshield.

F5 keeps the accepted source cage, all 17 true openings, frozen engineering
anchors and 13 Web actions. It changes only presentation geometry:

- cab surrounds become segmented annular meshes that follow the changing side
  surface instead of a four-corner planar frame;
- the top body-colour band is extended above the true cab-door boundary to mask
  the remaining subdivided saw-tooth edge;
- both cab rings are moved back close to the body skin, leaving the animated
  door panel outside them rather than producing a floating external frame;
- the windshield body surround and inner trim are reduced to thin, shallow
  opening-matched rings.
"""

import importlib.util
import json
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector


SCRIPT_DIR = Path(__file__).resolve().parent
F4_PATH = SCRIPT_DIR / "build_s2_body_r4_fix4.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix4", F4_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F4 builder: {F4_PATH}")
f4 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f4)

f3 = f4.f3
fix2 = f3.fix2
r4 = f4.r4
builder = f4.builder
entry = f4.entry
clearance = f4.clearance
WINDSHIELD_ROTATION_Y = f4.WINDSHIELD_ROTATION_Y
WINDSHIELD_PLANE_HEIGHT_M = f4.WINDSHIELD_PLANE_HEIGHT_M
WINDSHIELD_CENTER = f4.WINDSHIELD_CENTER

ORIGINAL_APPLY = r4.apply_r4_surface_repairs


def side_surface_y(x, side_sign, outward_offset):
    return (
        side_sign * builder.section_dimensions(x)[0] / 2.0
        + side_sign * outward_offset
    )


def rectangle_perimeter(bounds, side_sign, outward_offset, x_segments=11, z_segments=7):
    """Return one closed, corner-deduplicated perimeter following side y(x)."""

    x0, x1, z0, z1 = bounds
    points = []

    for index in range(x_segments):
        t = index / (x_segments - 1)
        x = x0 + (x1 - x0) * t
        points.append((x, side_surface_y(x, side_sign, outward_offset), z0))

    for index in range(1, z_segments):
        t = index / (z_segments - 1)
        z = z0 + (z1 - z0) * t
        points.append((x1, side_surface_y(x1, side_sign, outward_offset), z))

    for index in range(1, x_segments):
        t = index / (x_segments - 1)
        x = x1 - (x1 - x0) * t
        points.append((x, side_surface_y(x, side_sign, outward_offset), z1))

    for index in range(1, z_segments - 1):
        t = index / (z_segments - 1)
        z = z1 - (z1 - z0) * t
        points.append((x0, side_surface_y(x0, side_sign, outward_offset), z))

    return points


def make_segmented_side_ring(
    name,
    side_sign,
    outer_bounds,
    inner_bounds,
    front_offset,
    back_offset,
    material,
    parent,
    bevel_width,
    role,
):
    r4.remove_object(name)
    outer_front = rectangle_perimeter(outer_bounds, side_sign, front_offset)
    inner_front = rectangle_perimeter(inner_bounds, side_sign, front_offset)
    outer_back = rectangle_perimeter(outer_bounds, side_sign, back_offset)
    inner_back = rectangle_perimeter(inner_bounds, side_sign, back_offset)
    count = len(outer_front)
    if not (len(inner_front) == len(outer_back) == len(inner_back) == count):
        raise RuntimeError(f"segmented ring loop mismatch: {name}")

    vertices = outer_front + inner_front + outer_back + inner_back
    faces = []
    of = 0
    inf = count
    ob = count * 2
    inb = count * 3
    for index in range(count):
        nxt = (index + 1) % count
        faces.append((of + index, of + nxt, inf + nxt, inf + index))
        faces.append((ob + nxt, ob + index, inb + index, inb + nxt))
        faces.append((of + index, ob + index, ob + nxt, of + nxt))
        faces.append((inf + nxt, inb + nxt, inb + index, inf + index))

    mesh = bpy.data.meshes.new(f"{name}_F5_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=True)
    mesh.update(calc_edges=True)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    mesh.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    bevel = obj.modifiers.new("R4_F5_Surface_Bevel", "BEVEL")
    bevel.width = bevel_width
    bevel.segments = 3
    bevel.limit_method = "ANGLE"
    obj["nomadhub_semantic_node"] = name
    obj["s2_r4_web_surface"] = True
    obj["s2_r4_f2_surface_role"] = role
    obj["s2_r4_f3_source_edge_mask"] = True
    obj["s2_r4_f5_segmented_surface"] = True
    obj["s2_r4_f5_side"] = "L" if side_sign < 0 else "R"
    obj["s2_r4_f5_perimeter_vertices"] = count
    return obj


def set_ring_bevel(obj, width):
    for modifier in obj.modifiers:
        if modifier.type == "BEVEL":
            modifier.width = width
            modifier.segments = 3


def rebuild_thin_windshield(body_root, body_material, trim_material):
    normal = Matrix.Rotation(WINDSHIELD_ROTATION_Y, 4, "Y") @ Vector(
        (1.0, 0.0, 0.0)
    )
    surround = r4.make_ring_mesh(
        "R4_WINDSHIELD_SURROUND",
        1.900,
        0.640,
        1.800,
        0.560,
        0.016,
        body_material,
        body_root,
    )
    surround.location = WINDSHIELD_CENTER - normal * 0.006
    set_ring_bevel(surround, 0.004)
    surround["s2_r4_visual_role"] = "continuous_windshield_surround"
    surround["s2_r4_f2_surface_aligned"] = True
    surround["s2_r4_f3_opening_matched"] = True
    surround["s2_r4_f5_thin_flush_ring"] = True

    trim = r4.make_ring_mesh(
        "R4_WINDSHIELD_TRIM",
        1.810,
        0.570,
        1.750,
        0.515,
        0.020,
        trim_material,
        body_root,
    )
    trim.location = WINDSHIELD_CENTER - normal * 0.003
    set_ring_bevel(trim, 0.002)
    trim["s2_r4_visual_role"] = "continuous_windshield_inner_trim"
    trim["s2_r4_f2_surface_aligned"] = True
    trim["s2_r4_f3_opening_matched"] = True
    trim["s2_r4_f5_thin_flush_ring"] = True

    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    if glass is None:
        raise RuntimeError("GLASS_WINDSHIELD missing during R4-F5")
    glass.location = WINDSHIELD_CENTER + normal * 0.012
    glass["s2_r4_f5_flush_inset"] = True


def rebuild_segmented_cab_surfaces(body_root, body_material, trim_material):
    for name in (
        "R4_CAB_RING_L",
        "R4_CAB_RING_R",
        "R4_CAB_SEAM_L",
        "R4_CAB_SEAM_R",
    ):
        r4.remove_object(name)

    # The evaluated source boundary reaches z~=2.259 m. The 2.32 m outer top
    # masks that edge while the 2.12 m inner top remains above the animated door
    # panel (z max 2.095 m), producing a continuous integrated header band.
    outer = (-4.460, -3.800, 0.350, 2.320)
    body_inner = (-4.350, -3.940, 0.500, 2.120)
    seam_outer = body_inner
    seam_inner = (-4.335, -3.955, 0.515, 2.105)

    for side, side_sign in (("L", -1.0), ("R", 1.0)):
        ring = make_segmented_side_ring(
            f"R4_CAB_RING_{side}",
            side_sign,
            outer,
            body_inner,
            0.012,
            -0.010,
            body_material,
            body_root,
            0.004,
            "surface_aligned_body_surround",
        )
        seam = make_segmented_side_ring(
            f"R4_CAB_SEAM_{side}",
            side_sign,
            seam_outer,
            seam_inner,
            0.018,
            0.013,
            trim_material,
            body_root,
            0.0015,
            "surface_aligned_inner_seam",
        )
        ring["s2_r4_f5_source_boundary_cover"] = True
        seam["s2_r4_f5_source_boundary_cover"] = True


def apply_r4_f5_surface_repairs():
    ORIGINAL_APPLY()
    body_root = bpy.data.objects.get("BODY")
    body_material = bpy.data.materials.get("MAT_BODY_SILVER")
    trim_material = bpy.data.materials.get("MAT_TRIM")
    if body_root is None or body_material is None or trim_material is None:
        raise RuntimeError("R4-F5 roots/materials missing")

    rebuild_thin_windshield(body_root, body_material, trim_material)
    rebuild_segmented_cab_surfaces(body_root, body_material, trim_material)


r4.apply_r4_surface_repairs = apply_r4_f5_surface_repairs


def patch_fix5_manifest(path):
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    repairs = payload.setdefault("r4_visual_repairs", {})
    repairs.update(
        {
            "cab_segmented_surface_rings": 2,
            "cab_segmented_seam_rings": 2,
            "cab_ring_front_offset_m": 0.012,
            "cab_ring_back_offset_m": -0.010,
            "cab_header_outer_z_m": 2.320,
            "cab_header_inner_z_m": 2.120,
            "windshield_surround_depth_m": 0.016,
            "windshield_trim_depth_m": 0.020,
            "source_openings_unchanged": True,
            "web_node_and_animation_contract_preserved": True,
        }
    )
    payload["stage_status"] = "R4_F5_FLUSH_SEGMENTED_VISUAL_CANDIDATE"
    payload["r4_fix_iteration"] = "F5"
    payload["scope_note"] = (
        "R4-F5 preserves the accepted source topology, 17 openings, frozen roots "
        "and 13 actions. It replaces planar floating cab frames with segmented "
        "surface-following rings, extends the integrated cab header over the "
        "remaining source-edge ripple, and reduces the windshield surround depth."
    )
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    f4.main()
    args = builder.parse_args()
    patch_fix5_manifest(args.manifest)
    print("NOMADHUB_S2_R4_F5_FLUSH_SEGMENTED_REPAIR_OK")


if __name__ == "__main__":
    main()
