"""S2-R4 second visual integration repair.

R4-F2 replaces the oversized floating windshield frame and box-built cab-door
surrounds with thin, surface-aligned annular meshes. The accepted R3 source
cage, all 17 true openings, frozen roots, semantic nodes and 13 actions remain
unchanged.
"""

import importlib.util
import json
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector


SCRIPT_DIR = Path(__file__).resolve().parent
R4_FIX_PATH = SCRIPT_DIR / "build_s2_body_r4_fix.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix1", R4_FIX_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load first R4 fix: {R4_FIX_PATH}")
fix1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fix1)
r4 = fix1.r4
r3 = r4.r3
builder = r4.builder
entry = r4.entry
clearance = r4.clearance


# Match the actual windshield opening: lower edge is forward, upper edge is
# rearward. The previous -17 degree frame leaned in the opposite direction and
# sat roughly 300 mm too low.
r4.R4_WINDSHIELD_CENTER = Vector((-4.083, 0.0, 2.560))
r4.R4_WINDSHIELD_ROTATION_Y = math.radians(30.0)


def make_windshield_material():
    material = bpy.data.materials.get("MAT_WINDSHIELD_R4_F2")
    if material is None:
        material = bpy.data.materials.new("MAT_WINDSHIELD_R4_F2")
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.010, 0.035, 0.055, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.22
    if bsdf.inputs.get("Transmission Weight") is not None:
        bsdf.inputs["Transmission Weight"].default_value = 0.18
    if bsdf.inputs.get("Coat Weight") is not None:
        bsdf.inputs["Coat Weight"].default_value = 0.12
    return material


def replace_with_box_mesh(obj, dimensions, location, rotation, material):
    depth, width, height = dimensions
    x = depth / 2.0
    y = width / 2.0
    z = height / 2.0
    vertices = (
        (-x, -y, -z),
        (-x, y, -z),
        (-x, y, z),
        (-x, -y, z),
        (x, -y, -z),
        (x, y, -z),
        (x, y, z),
        (x, -y, z),
    )
    faces = (
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 4, 7, 3),
        (1, 2, 6, 5),
        (0, 1, 5, 4),
        (3, 7, 6, 2),
    )
    old_mesh = obj.data
    mesh = bpy.data.meshes.new("GLASS_WINDSHIELD_R4_F2_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=True)
    mesh.update(calc_edges=True)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()

    obj.data = mesh
    obj.location = location
    obj.rotation_euler = rotation
    obj.scale = (1.0, 1.0, 1.0)
    mesh.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    if old_mesh is not None and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    obj["s2_r4_dimensions_baked"] = True
    obj["s2_r4_visual_role"] = "inset_windshield_glass"
    obj["s2_r4_f2_rebuilt_mesh"] = True


def side_surface_y(x, side_sign):
    return side_sign * builder.section_dimensions(x)[0] / 2.0


def make_side_ring(
    name,
    side_sign,
    outer_bounds,
    inner_bounds,
    front_offset,
    back_offset,
    material,
    parent,
    bevel,
    role,
):
    r4.remove_object(name)
    ox0, ox1, oz0, oz1 = outer_bounds
    ix0, ix1, iz0, iz1 = inner_bounds

    def point(x, z, offset):
        return (x, side_surface_y(x, side_sign) + side_sign * offset, z)

    def loop(bounds, offset):
        x0, x1, z0, z1 = bounds
        return (
            point(x0, z0, offset),
            point(x1, z0, offset),
            point(x1, z1, offset),
            point(x0, z1, offset),
        )

    vertices = (
        list(loop(outer_bounds, front_offset))
        + list(loop(inner_bounds, front_offset))
        + list(loop(outer_bounds, back_offset))
        + list(loop(inner_bounds, back_offset))
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

    mesh = bpy.data.meshes.new(f"{name}_MESH")
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
    modifier = obj.modifiers.new("R4_F2_Surface_Bevel", "BEVEL")
    modifier.width = bevel
    modifier.segments = 3
    modifier.limit_method = "ANGLE"
    obj["nomadhub_semantic_node"] = name
    obj["s2_r4_web_surface"] = True
    obj["s2_r4_f2_surface_role"] = role
    obj["s2_r4_f2_side"] = "L" if side_sign < 0 else "R"
    return obj


def bury_old_cab_frame_markers(body_root, body_material, trim_material):
    # Preserve all legacy names used by the Web and validators, but remove their
    # visible box-frame appearance. They remain tiny semantic markers inside the
    # body and are not part of the rendered exterior.
    index = 0
    for side in ("L", "R"):
        for suffix in ("BOTTOM", "TOP", "FRONT", "REAR"):
            frame_name = f"R3_FRAME_CAB_DOOR_{side}_{suffix}"
            frame = bpy.data.objects.get(frame_name)
            if frame is None:
                raise RuntimeError(f"legacy cab frame missing: {frame_name}")
            frame.data.materials.clear()
            frame.data.materials.append(body_material)
            frame.location = (0.0, 0.0, 0.18 + index * 0.002)
            frame.rotation_euler = (0.0, 0.0, 0.0)
            frame.scale = (0.008, 0.008, 0.008)
            frame["s2_r4_cab_surround"] = True
            frame["s2_r4_f2_legacy_marker_buried"] = True

            trim_name = f"R4_CAB_DOOR_TRIM_{side}_{suffix}"
            r4.remove_object(trim_name)
            trim = r3.make_box(
                trim_name,
                (0.004, 0.004, 0.004),
                (0.0, 0.0, 0.20 + index * 0.002),
                trim_material,
                body_root,
                bevel=0.0,
            )
            trim["s2_r4_f2_legacy_marker_buried"] = True
            index += 1


def build_cab_surface_rings(body_root, body_material, trim_material):
    outer = (-4.440, -3.820, 0.380, 2.260)
    body_inner = (-4.370, -3.910, 0.490, 2.130)
    seam_outer = body_inner
    seam_inner = (-4.355, -3.925, 0.505, 2.115)
    for side, side_sign in (("L", -1.0), ("R", 1.0)):
        make_side_ring(
            f"R4_CAB_RING_{side}",
            side_sign,
            outer,
            body_inner,
            0.010,
            -0.012,
            body_material,
            body_root,
            0.010,
            "surface_aligned_body_surround",
        )
        make_side_ring(
            f"R4_CAB_SEAM_{side}",
            side_sign,
            seam_outer,
            seam_inner,
            0.014,
            0.009,
            trim_material,
            body_root,
            0.003,
            "surface_aligned_inner_seam",
        )


def apply_r4_f2_surface_repairs():
    body_root = bpy.data.objects.get("BODY")
    body_material = bpy.data.materials.get("MAT_BODY_SILVER")
    trim_material = bpy.data.materials.get("MAT_TRIM")
    if body_root is None or body_material is None or trim_material is None:
        raise RuntimeError("R4-F2 body root/materials missing")

    r4.bury_legacy_windshield_markers(body_material)
    surround = r4.make_ring_mesh(
        "R4_WINDSHIELD_SURROUND",
        1.98,
        0.86,
        1.78,
        0.72,
        0.050,
        body_material,
        body_root,
    )
    surround["s2_r4_visual_role"] = "continuous_windshield_surround"
    surround["s2_r4_f2_surface_aligned"] = True
    trim = r4.make_ring_mesh(
        "R4_WINDSHIELD_TRIM",
        1.82,
        0.76,
        1.70,
        0.68,
        0.054,
        trim_material,
        body_root,
    )
    trim["s2_r4_visual_role"] = "continuous_windshield_inner_trim"
    trim["s2_r4_f2_surface_aligned"] = True

    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    if glass is None:
        raise RuntimeError("GLASS_WINDSHIELD missing")
    normal = Matrix.Rotation(r4.R4_WINDSHIELD_ROTATION_Y, 4, "Y") @ Vector((1.0, 0.0, 0.0))
    glass_location = r4.R4_WINDSHIELD_CENTER + normal * 0.028
    replace_with_box_mesh(
        glass,
        (0.040, 1.700, 0.680),
        glass_location,
        (0.0, r4.R4_WINDSHIELD_ROTATION_Y, 0.0),
        make_windshield_material(),
    )

    bury_old_cab_frame_markers(body_root, body_material, trim_material)
    build_cab_surface_rings(body_root, body_material, trim_material)

    # Keep the validated compatibility liners and the R4 wheel lips.
    for old_name, new_name, center_x, side_sign in (
        ("WHEEL_ARCH_FL", "R4_WHEEL_LIP_FL", builder.FRONT_AXLE_X_M, -1.0),
        ("WHEEL_ARCH_FR", "R4_WHEEL_LIP_FR", builder.FRONT_AXLE_X_M, 1.0),
        ("WHEEL_ARCH_RL", "R4_WHEEL_LIP_RL", builder.REAR_AXLE_X_M, -1.0),
        ("WHEEL_ARCH_RR", "R4_WHEEL_LIP_RR", builder.REAR_AXLE_X_M, 1.0),
    ):
        old = bpy.data.objects.get(old_name)
        if old is None:
            raise RuntimeError(f"compatibility wheel liner missing: {old_name}")
        old.data.materials.clear()
        old.data.materials.append(trim_material)
        old.location.y = -side_sign * 0.020
        old["s2_r4_visual_role"] = "recessed_compatibility_wheel_liner"
        r4.make_visual_wheel_lip(new_name, center_x, side_sign, body_material, body_root)


r4.apply_r4_surface_repairs = apply_r4_f2_surface_repairs


def patch_fix2_manifest(path):
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    repairs = payload.setdefault("r4_visual_repairs", {})
    repairs.update(
        {
            "windshield_center_m": [-4.083, 0.0, 2.560],
            "windshield_rotation_y_deg": 30.0,
            "windshield_surface_aligned": True,
            "cab_surface_aligned_annular_rings": 2,
            "cab_surface_aligned_seam_rings": 2,
            "legacy_cab_box_frames_buried": 16,
        }
    )
    payload["stage_status"] = "R4_F2_SURFACE_ALIGNED_VISUAL_CANDIDATE"
    payload["scope_note"] = (
        "R4-F2 keeps the accepted source topology, 17 openings and frozen Web/animation "
        "contract while replacing the floating windshield and box-built cab frames with "
        "thin surface-aligned annular meshes. Manual evidence review remains required."
    )
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    r4.main()
    args = builder.parse_args()
    patch_fix2_manifest(args.manifest)
    print("NOMADHUB_S2_R4_F2_SURFACE_ALIGNED_REPAIR_OK")


if __name__ == "__main__":
    main()
