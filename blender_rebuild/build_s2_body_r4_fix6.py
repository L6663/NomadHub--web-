"""R4-F6 visual repair: narrow cab seals and a source-shaped windshield.

F6 preserves the accepted source topology, 17 true openings, frozen anchors,
semantic names and 13 actions. It replaces the remaining broad presentation
frames with geometry that reads as part of the vehicle body:

- narrow, surface-following cab rings around the animated panels;
- separate body-colour header patches, flush with the side skin, that cover the
  subdivided cab-opening ripple without looking like a complete external frame;
- a trapezoidal windshield surround/trim/glass assembly whose upper edge is
  wider than its lower edge, matching the front section growth from x=-4.30 m
  to x=-3.86 m.
"""

import importlib.util
import json
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


SCRIPT_DIR = Path(__file__).resolve().parent
F5_PATH = SCRIPT_DIR / "build_s2_body_r4_fix5.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix5", F5_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F5 builder: {F5_PATH}")
f5 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f5)

f4 = f5.f4
f3 = f5.f3
fix2 = f5.fix2
r4 = f5.r4
builder = f5.builder
entry = f5.entry
clearance = f5.clearance
WINDSHIELD_ROTATION_Y = f5.WINDSHIELD_ROTATION_Y
WINDSHIELD_PLANE_HEIGHT_M = f5.WINDSHIELD_PLANE_HEIGHT_M
WINDSHIELD_CENTER = f5.WINDSHIELD_CENTER

ORIGINAL_APPLY = r4.apply_r4_surface_repairs


def make_local_trapezoid_ring(
    name,
    outer_bottom_width,
    outer_top_width,
    outer_height,
    inner_bottom_width,
    inner_top_width,
    inner_height,
    depth,
    material,
    parent,
    bevel_width,
    role,
):
    r4.remove_object(name)
    x_front = -depth / 2.0
    x_back = depth / 2.0

    def loop(x, bottom_width, top_width, height):
        return [
            (x, -bottom_width / 2.0, -height / 2.0),
            (x, bottom_width / 2.0, -height / 2.0),
            (x, top_width / 2.0, height / 2.0),
            (x, -top_width / 2.0, height / 2.0),
        ]

    vertices = (
        loop(x_front, outer_bottom_width, outer_top_width, outer_height)
        + loop(x_front, inner_bottom_width, inner_top_width, inner_height)
        + loop(x_back, outer_bottom_width, outer_top_width, outer_height)
        + loop(x_back, inner_bottom_width, inner_top_width, inner_height)
    )
    faces = []
    for offset, reverse in ((0, False), (8, True)):
        outer = [offset + index for index in range(4)]
        inner = [offset + 4 + index for index in range(4)]
        for index in range(4):
            nxt = (index + 1) % 4
            quad = (outer[index], outer[nxt], inner[nxt], inner[index])
            faces.append(tuple(reversed(quad)) if reverse else quad)
    for index in range(4):
        nxt = (index + 1) % 4
        faces.append((index, 8 + index, 8 + nxt, nxt))
        faces.append((4 + index, 4 + nxt, 12 + nxt, 12 + index))

    mesh = bpy.data.meshes.new(f"{name}_F6_TRAPEZOID_MESH")
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
    obj.location = WINDSHIELD_CENTER
    obj.rotation_euler = (0.0, WINDSHIELD_ROTATION_Y, 0.0)
    mesh.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    bevel = obj.modifiers.new("R4_F6_Trapezoid_Bevel", "BEVEL")
    bevel.width = bevel_width
    bevel.segments = 3
    bevel.limit_method = "ANGLE"
    obj["nomadhub_semantic_node"] = name
    obj["s2_r4_web_surface"] = True
    obj["s2_r4_visual_role"] = role
    obj["s2_r4_f2_surface_aligned"] = True
    obj["s2_r4_f3_opening_matched"] = True
    obj["s2_r4_f5_thin_flush_ring"] = True
    obj["s2_r4_f6_trapezoid_ring"] = True
    obj["s2_r4_f6_bottom_width_m"] = outer_bottom_width
    obj["s2_r4_f6_top_width_m"] = outer_top_width
    return obj


def replace_glass_with_trapezoid(obj, material):
    depth = 0.028
    height = 0.500
    bottom_width = 1.700
    top_width = 1.740
    x_front = -depth / 2.0
    x_back = depth / 2.0
    z_bottom = -height / 2.0
    z_top = height / 2.0
    vertices = (
        (x_front, -bottom_width / 2.0, z_bottom),
        (x_front, bottom_width / 2.0, z_bottom),
        (x_front, top_width / 2.0, z_top),
        (x_front, -top_width / 2.0, z_top),
        (x_back, -bottom_width / 2.0, z_bottom),
        (x_back, bottom_width / 2.0, z_bottom),
        (x_back, top_width / 2.0, z_top),
        (x_back, -top_width / 2.0, z_top),
    )
    faces = (
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    )
    old_mesh = obj.data
    mesh = bpy.data.meshes.new("GLASS_WINDSHIELD_R4_F6_TRAPEZOID_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=True)
    mesh.update(calc_edges=True)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()

    obj.data = mesh
    obj.location = WINDSHIELD_CENTER
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = (0.0, WINDSHIELD_ROTATION_Y, 0.0)
    obj.scale = (1.0, 1.0, 1.0)
    mesh.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    if old_mesh is not None and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    obj["s2_r4_f2_rebuilt_mesh"] = True
    obj["s2_r4_f3_opening_matched"] = True
    obj["s2_r4_f5_flush_inset"] = True
    obj["s2_r4_f6_trapezoid_glass"] = True
    obj["s2_r4_f6_bottom_width_m"] = bottom_width
    obj["s2_r4_f6_top_width_m"] = top_width


def make_side_header_patch(
    name,
    side_sign,
    x_min,
    x_max,
    z_min,
    z_max,
    front_offset,
    back_offset,
    material,
    parent,
):
    r4.remove_object(name)
    segments = 13
    vertices = []
    for offset in (front_offset, back_offset):
        for index in range(segments):
            t = index / (segments - 1)
            x = x_min + (x_max - x_min) * t
            y = (
                side_sign * builder.section_dimensions(x)[0] / 2.0
                + side_sign * offset
            )
            vertices.extend(((x, y, z_min), (x, y, z_max)))

    layer_stride = segments * 2
    faces = []
    for index in range(segments - 1):
        a = index * 2
        b = (index + 1) * 2
        faces.append((a, b, b + 1, a + 1))
        faces.append(
            (
                layer_stride + a + 1,
                layer_stride + b + 1,
                layer_stride + b,
                layer_stride + a,
            )
        )
        faces.append((a, layer_stride + a, layer_stride + b, b))
        faces.append(
            (a + 1, b + 1, layer_stride + b + 1, layer_stride + a + 1)
        )
    faces.append((0, 1, layer_stride + 1, layer_stride))
    last = (segments - 1) * 2
    faces.append(
        (last + 1, last, layer_stride + last, layer_stride + last + 1)
    )

    mesh = bpy.data.meshes.new(f"{name}_F6_HEADER_MESH")
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
    bevel = obj.modifiers.new("R4_F6_Header_Bevel", "BEVEL")
    bevel.width = 0.002
    bevel.segments = 2
    bevel.limit_method = "ANGLE"
    obj["nomadhub_semantic_node"] = name
    obj["s2_r4_web_surface"] = True
    obj["s2_r4_f6_flush_header_patch"] = True
    obj["s2_r4_f6_side"] = "L" if side_sign < 0 else "R"
    obj["s2_r4_f6_z_min_m"] = z_min
    obj["s2_r4_f6_z_max_m"] = z_max
    return obj


def rebuild_trapezoid_windshield(body_root, body_material, trim_material):
    surround = make_local_trapezoid_ring(
        "R4_WINDSHIELD_SURROUND",
        1.900,
        1.960,
        0.620,
        1.780,
        1.840,
        0.560,
        0.012,
        body_material,
        body_root,
        0.003,
        "continuous_windshield_surround",
    )
    trim = make_local_trapezoid_ring(
        "R4_WINDSHIELD_TRIM",
        1.780,
        1.840,
        0.560,
        1.710,
        1.770,
        0.515,
        0.014,
        trim_material,
        body_root,
        0.0015,
        "continuous_windshield_inner_trim",
    )
    surround["s2_r4_f6_source_section_growth_m"] = 0.060
    trim["s2_r4_f6_source_section_growth_m"] = 0.060

    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    if glass is None:
        raise RuntimeError("GLASS_WINDSHIELD missing during R4-F6")
    glass_material = bpy.data.materials.get("MAT_WINDSHIELD_R4_F2")
    if glass_material is None:
        glass_material = fix2.make_windshield_material()
    replace_glass_with_trapezoid(glass, glass_material)


def rebuild_narrow_cab_surfaces(body_root, body_material, trim_material):
    for name in (
        "R4_CAB_RING_L",
        "R4_CAB_RING_R",
        "R4_CAB_SEAM_L",
        "R4_CAB_SEAM_R",
        "R4_CAB_HEADER_L",
        "R4_CAB_HEADER_R",
    ):
        r4.remove_object(name)

    outer = (-4.425, -3.855, 0.410, 2.200)
    body_inner = (-4.385, -3.895, 0.480, 2.140)
    seam_outer = body_inner
    seam_inner = (-4.372, -3.908, 0.495, 2.125)
    for side, side_sign in (("L", -1.0), ("R", 1.0)):
        ring = f5.make_segmented_side_ring(
            f"R4_CAB_RING_{side}",
            side_sign,
            outer,
            body_inner,
            0.006,
            -0.006,
            body_material,
            body_root,
            0.0025,
            "surface_aligned_body_surround",
        )
        seam = f5.make_segmented_side_ring(
            f"R4_CAB_SEAM_{side}",
            side_sign,
            seam_outer,
            seam_inner,
            0.011,
            0.007,
            trim_material,
            body_root,
            0.001,
            "surface_aligned_inner_seam",
        )
        ring["s2_r4_f5_source_boundary_cover"] = True
        seam["s2_r4_f5_source_boundary_cover"] = True
        ring["s2_r4_f6_narrow_ring"] = True
        seam["s2_r4_f6_narrow_ring"] = True

        make_side_header_patch(
            f"R4_CAB_HEADER_{side}",
            side_sign,
            -4.450,
            -3.810,
            2.125,
            2.320,
            0.004,
            -0.008,
            body_material,
            body_root,
        )


def apply_r4_f6_surface_repairs():
    ORIGINAL_APPLY()
    body_root = bpy.data.objects.get("BODY")
    body_material = bpy.data.materials.get("MAT_BODY_SILVER")
    trim_material = bpy.data.materials.get("MAT_TRIM")
    if body_root is None or body_material is None or trim_material is None:
        raise RuntimeError("R4-F6 roots/materials missing")

    rebuild_trapezoid_windshield(body_root, body_material, trim_material)
    rebuild_narrow_cab_surfaces(body_root, body_material, trim_material)


r4.apply_r4_surface_repairs = apply_r4_f6_surface_repairs


def patch_fix6_manifest(path):
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    repairs = payload.setdefault("r4_visual_repairs", {})
    repairs.update(
        {
            "cab_narrow_surface_rings": 2,
            "cab_narrow_seam_rings": 2,
            "cab_flush_header_patches": 2,
            "cab_ring_front_offset_m": 0.006,
            "cab_ring_back_offset_m": -0.006,
            "cab_header_z_range_m": [2.125, 2.320],
            "windshield_trapezoid_surround": True,
            "windshield_trapezoid_trim": True,
            "windshield_trapezoid_glass": True,
            "windshield_outer_width_bottom_top_m": [1.900, 1.960],
            "windshield_glass_width_bottom_top_m": [1.700, 1.740],
            "source_openings_unchanged": True,
            "web_node_and_animation_contract_preserved": True,
        }
    )
    payload["stage_status"] = "R4_F6_INTEGRATED_CAB_AND_TRAPEZOID_WINDSHIELD_CANDIDATE"
    payload["r4_fix_iteration"] = "F6"
    payload["scope_note"] = (
        "R4-F6 keeps the validated source cage, 17 true openings, frozen roots "
        "and 13 actions. Broad cab frames are replaced by narrow seals plus flush "
        "body-colour header patches, and the windshield assembly becomes a "
        "front-section-matched trapezoid instead of an equal-width rectangle."
    )
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    f5.main()
    args = builder.parse_args()
    patch_fix6_manifest(args.manifest)
    print("NOMADHUB_S2_R4_F6_INTEGRATED_SURFACE_REPAIR_OK")


if __name__ == "__main__":
    main()
