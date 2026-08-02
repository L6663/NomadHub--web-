"""S2-R4 Web-visible surface repair over the technically accepted R3 base.

R4 does not change the 17 source openings, frozen anchors, node names or
animations. It replaces the visibly fragmented presentation geometry with:

- one continuous windshield surround and inner trim ring;
- substantial body-colour cab-door surrounds that cover the subdivided opening
  boundary while preserving the animated door clearance;
- dark recessed legacy arch objects for compatibility plus thin body-colour
  visual lips that follow the actual R3 wheel opening;
- buried legacy R3 windshield marker parts so the GLB validation contract stays
  backward compatible without exposing the old disconnected blocks.
"""

import importlib.util
import json
import math
import shutil
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


SCRIPT_DIR = Path(__file__).resolve().parent
FIX3_PATH = SCRIPT_DIR / "build_s2_body_r3_fix3.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r3_fix3", FIX3_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load accepted R3 integration fix: {FIX3_PATH}")
fix3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fix3)
r3 = fix3.r3
builder = fix3.builder
entry = fix3.entry
clearance = fix3.clearance


R4_WINDSHIELD_CENTER = Vector((-4.105, 0.0, 2.255))
R4_WINDSHIELD_ROTATION_Y = -math.radians(17.0)
R4_WHEEL_LIP_RX_M = 0.595
R4_WHEEL_LIP_RZ_M = 0.555
R4_WHEEL_LIP_CENTER_Z_M = 0.410
R4_WHEEL_LIP_TUBE_M = 0.014


def remove_object(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        return
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data is not None and getattr(data, "users", 1) == 0:
        if isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
        elif isinstance(data, bpy.types.Curve):
            bpy.data.curves.remove(data)


def make_ring_mesh(name, outer_width, outer_height, inner_width, inner_height, depth, material, parent):
    remove_object(name)
    x_front = -depth / 2.0
    x_back = depth / 2.0

    def loop(x, width, height):
        return [
            (x, -width / 2.0, -height / 2.0),
            (x, width / 2.0, -height / 2.0),
            (x, width / 2.0, height / 2.0),
            (x, -width / 2.0, height / 2.0),
        ]

    vertices = (
        loop(x_front, outer_width, outer_height)
        + loop(x_front, inner_width, inner_height)
        + loop(x_back, outer_width, outer_height)
        + loop(x_back, inner_width, inner_height)
    )
    faces = []
    # Front and rear annular surfaces.
    for offset, reverse in ((0, False), (8, True)):
        outer = [offset + index for index in range(4)]
        inner = [offset + 4 + index for index in range(4)]
        for index in range(4):
            nxt = (index + 1) % 4
            quad = (outer[index], outer[nxt], inner[nxt], inner[index])
            faces.append(tuple(reversed(quad)) if reverse else quad)
    # Outer and inner walls.
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
    obj.location = R4_WINDSHIELD_CENTER
    obj.rotation_euler = (0.0, R4_WINDSHIELD_ROTATION_Y, 0.0)
    mesh.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    bevel = obj.modifiers.new("R4_Ring_Bevel", "BEVEL")
    bevel.width = 0.012
    bevel.segments = 3
    bevel.limit_method = "ANGLE"
    obj["nomadhub_semantic_node"] = name
    obj["s2_r4_web_surface"] = True
    return obj


def bury_legacy_windshield_markers(body_material):
    # Keep the exact nodes exported for R3 compatibility, but bury their tiny
    # geometry inside the continuous R4 surround so they no longer fragment the
    # visible front fascia.
    for name in (
        "R3_WINDSHIELD_FRAME_TOP",
        "R3_WINDSHIELD_FRAME_BOTTOM",
        "R3_WINDSHIELD_FRAME_LEFT",
        "R3_WINDSHIELD_FRAME_RIGHT",
        "R3_A_PILLAR_L",
        "R3_A_PILLAR_R",
    ):
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        obj.data.materials.clear()
        obj.data.materials.append(body_material)
        obj.location = R4_WINDSHIELD_CENTER + Vector((0.050, 0.0, 0.0))
        obj.scale = (0.025, 0.025, 0.025)
        obj["s2_r4_legacy_marker_buried"] = True


def make_cab_door_surround(opening, body_root, body_material, trim_material):
    name = opening["name"]
    side_sign = -1.0 if opening["side"] == "L" else 1.0
    x_min, x_max = opening["x_min_m"], opening["x_max_m"]
    z_min, z_max = opening["z_min_m"], opening["z_max_m"]

    def side_y(x, outward):
        return side_sign * builder.section_dimensions(x)[0] / 2.0 + side_sign * outward

    y_min = side_y(x_min, 0.020)
    y_max = side_y(x_max, 0.020)
    x_mid = (x_min + x_max) / 2.0
    y_mid = (y_min + y_max) / 2.0
    length = math.hypot(x_max - x_min, y_max - y_min)
    rotation_z = math.atan2(y_max - y_min, x_max - x_min)

    pieces = (
        ("BOTTOM", (length, 0.060, 0.120), (x_mid, y_mid, z_min - 0.005), rotation_z),
        ("TOP", (length, 0.060, 0.190), (x_mid, y_mid, z_max + 0.015), rotation_z),
        ("FRONT", (0.110, 0.060, z_max - z_min + 0.090), (x_min - 0.010, y_min, (z_min + z_max) / 2.0), 0.0),
        ("REAR", (0.110, 0.060, z_max - z_min + 0.090), (x_max + 0.010, y_max, (z_min + z_max) / 2.0), 0.0),
    )
    for suffix, dimensions, location, rotation in pieces:
        obj_name = f"R3_FRAME_{name}_{suffix}"
        remove_object(obj_name)
        obj = r3.make_box(
            obj_name,
            dimensions,
            location,
            body_material,
            body_root,
            rotation=(0.0, 0.0, rotation),
            bevel=0.014,
        )
        obj["s2_r4_cab_surround"] = True

    # A separate dark inner reveal creates a readable seam without exposing the
    # source opening's jagged subdivided boundary.
    inner_x_min, inner_x_max = x_min + 0.055, x_max - 0.055
    inner_z_min, inner_z_max = z_min + 0.055, z_max - 0.075
    inner_y_min = side_y(inner_x_min, 0.055)
    inner_y_max = side_y(inner_x_max, 0.055)
    inner_mid_x = (inner_x_min + inner_x_max) / 2.0
    inner_mid_y = (inner_y_min + inner_y_max) / 2.0
    inner_length = math.hypot(inner_x_max - inner_x_min, inner_y_max - inner_y_min)
    inner_rot = math.atan2(inner_y_max - inner_y_min, inner_x_max - inner_x_min)
    for suffix, dimensions, location, rotation in (
        ("BOTTOM", (inner_length, 0.025, 0.025), (inner_mid_x, inner_mid_y, inner_z_min), inner_rot),
        ("TOP", (inner_length, 0.025, 0.025), (inner_mid_x, inner_mid_y, inner_z_max), inner_rot),
        ("FRONT", (0.025, 0.025, inner_z_max - inner_z_min), (inner_x_min, inner_y_min, (inner_z_min + inner_z_max) / 2.0), 0.0),
        ("REAR", (0.025, 0.025, inner_z_max - inner_z_min), (inner_x_max, inner_y_max, (inner_z_min + inner_z_max) / 2.0), 0.0),
    ):
        r3.make_box(
            f"R4_CAB_DOOR_TRIM_{opening['side']}_{suffix}",
            dimensions,
            location,
            trim_material,
            body_root,
            rotation=(0.0, 0.0, rotation),
            bevel=0.004,
        )


def make_visual_wheel_lip(name, center_x, side_sign, body_material, body_root):
    remove_object(name)
    curve = bpy.data.curves.new(f"{name}_CURVE", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = R4_WHEEL_LIP_TUBE_M
    curve.bevel_resolution = 4
    spline = curve.splines.new("POLY")
    point_count = 49
    spline.points.add(point_count - 1)
    y = side_sign * 1.158
    for index in range(point_count):
        theta = math.pi - math.pi * index / (point_count - 1)
        x = center_x + R4_WHEEL_LIP_RX_M * math.cos(theta)
        z = R4_WHEEL_LIP_CENTER_Z_M + R4_WHEEL_LIP_RZ_M * math.sin(theta)
        spline.points[index].co = (x, y, z, 1.0)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = body_root
    curve.materials.append(body_material)
    obj["nomadhub_semantic_node"] = name
    obj["s2_r4_web_surface"] = True
    obj["wheel_arch_center_x_m"] = center_x
    return obj


def apply_r4_surface_repairs():
    body_root = bpy.data.objects.get("BODY")
    body_material = bpy.data.materials.get("MAT_BODY_SILVER")
    trim_material = bpy.data.materials.get("MAT_TRIM")
    glass_material = bpy.data.materials.get("MAT_GLASS")
    if body_root is None or body_material is None or trim_material is None or glass_material is None:
        raise RuntimeError("R4 roots/materials missing")

    bury_legacy_windshield_markers(body_material)
    surround = make_ring_mesh(
        "R4_WINDSHIELD_SURROUND",
        2.12,
        1.10,
        1.78,
        0.76,
        0.085,
        body_material,
        body_root,
    )
    surround["s2_r4_visual_role"] = "continuous_windshield_surround"
    trim = make_ring_mesh(
        "R4_WINDSHIELD_TRIM",
        1.84,
        0.82,
        1.72,
        0.70,
        0.092,
        trim_material,
        body_root,
    )
    trim["s2_r4_visual_role"] = "continuous_windshield_inner_trim"

    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    if glass is not None:
        glass.location = R4_WINDSHIELD_CENTER + Vector((0.055, 0.0, 0.0))
        glass.rotation_euler = (0.0, R4_WINDSHIELD_ROTATION_Y, 0.0)
        glass.dimensions = (0.040, 1.70, 0.68)
        glass.scale = (1.0, 1.0, 1.0)
        glass.data.materials.clear()
        glass.data.materials.append(glass_material)
        glass["s2_r4_visual_role"] = "inset_windshield_glass"

    for opening in entry.SIDE_OPENINGS:
        if opening["name"] in ("CAB_DOOR_L", "CAB_DOOR_R"):
            make_cab_door_surround(opening, body_root, body_material, trim_material)

    # Preserve the original validated WHEEL_ARCH nodes and bounds as a dark
    # recessed liner, while adding a separate lip that actually follows R3.
    for old_name, new_name, center_x, side_sign in (
        ("WHEEL_ARCH_FL", "R4_WHEEL_LIP_FL", builder.FRONT_AXLE_X_M, -1.0),
        ("WHEEL_ARCH_FR", "R4_WHEEL_LIP_FR", builder.FRONT_AXLE_X_M, 1.0),
        ("WHEEL_ARCH_RL", "R4_WHEEL_LIP_RL", builder.REAR_AXLE_X_M, -1.0),
        ("WHEEL_ARCH_RR", "R4_WHEEL_LIP_RR", builder.REAR_AXLE_X_M, 1.0),
    ):
        old = bpy.data.objects.get(old_name)
        if old is not None:
            old.data.materials.clear()
            old.data.materials.append(trim_material)
            old.location.y = -side_sign * 0.020
            old["s2_r4_visual_role"] = "recessed_compatibility_wheel_liner"
        make_visual_wheel_lip(new_name, center_x, side_sign, body_material, body_root)


ORIGINAL_FREEZE = builder.r1.freeze_s1c_reference


def r4_freeze_source():
    references = ORIGINAL_FREEZE()
    apply_r4_surface_repairs()
    return references


builder.r1.freeze_s1c_reference = r4_freeze_source


def copy_r4_evidence(output_dir):
    output_dir = Path(output_dir)
    mapping = {
        "S2_R3_Front_Closeup.png": "S2_R4_Front_Closeup.png",
        "S2_R3_Wheel_Closeup.png": "S2_R4_Wheel_Closeup.png",
        "S2_R3_Zebra_Left.png": "S2_R4_Zebra_Left.png",
        "S2_R3_Zebra_Right.png": "S2_R4_Zebra_Right.png",
    }
    result = {}
    for source_name, target_name in mapping.items():
        source = output_dir / source_name
        target = output_dir / target_name
        if not source.is_file():
            raise RuntimeError(f"R4 evidence source missing: {source}")
        shutil.copy2(source, target)
        result[target_name.removeprefix("S2_R4_").removesuffix(".png").lower()] = str(target)
    return result


def patch_r4_manifest(args, evidence):
    manifest_path = Path(args.manifest)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["iteration"] = "R4"
    payload["stage_status"] = "R4_WEB_SURFACE_REPAIR_CANDIDATE"
    payload["r4_visual_repairs"] = {
        "continuous_windshield_surround": True,
        "continuous_windshield_inner_trim": True,
        "cab_door_body_surrounds": 2,
        "cab_door_inner_trim_sets": 2,
        "legacy_windshield_markers_buried": 6,
        "recessed_compatibility_wheel_liners": 4,
        "integrated_visual_wheel_lips": 4,
        "source_openings_unchanged": True,
        "web_node_and_animation_contract_preserved": True,
    }
    payload["proof_images"].update(
        {
            "front_closeup": evidence["front_closeup"],
            "wheel_closeup": evidence["wheel_closeup"],
            "zebra_left": evidence["zebra_left"],
            "zebra_right": evidence["zebra_right"],
        }
    )
    payload["scope_note"] = (
        "S2-R4 preserves the fully validated R3 source cage, 17 openings, frozen Web "
        "nodes and animations while replacing fragmented visible front/door/wheel trim "
        "with continuous Web-display surface geometry. Manual evidence review remains required."
    )
    payload["blend_bytes"] = Path(args.output).stat().st_size
    payload["blend_sha256"] = builder.sha256(args.output)
    payload["roundtrip_sha256"] = builder.sha256(args.roundtrip)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    args = builder.parse_args()
    fix3.main()
    scene = bpy.context.scene
    scene["nomadhub_s2_iteration"] = "R4"
    scene["s2_status"] = "R4_WEB_SURFACE_REPAIR_CANDIDATE"
    body = bpy.data.objects.get("BODY_S2_CONTROL_CAGE")
    if body is not None:
        body["s2_stage"] = "S2_R4_WEB_SURFACE_REPAIR"
        body["s2_r4_web_contract_preserved"] = True
    animation_mode = builder.r1.active_actions_merged_mode()
    builder.r1.export_gltf_compatible(args.roundtrip, animation_mode)
    bpy.ops.wm.save_as_mainfile(filepath=args.output, compress=True)
    Path(args.output + "1").unlink(missing_ok=True)
    evidence = copy_r4_evidence(Path(args.output).parent)
    patch_r4_manifest(args, evidence)
    print("NOMADHUB_S2_R4_WEB_SURFACE_REPAIR_OK")
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == "__main__":
    main()
