"""R4-F9 final cab integration polish.

F9 leaves the validated F8 windshield, native source cage, 17 opening loops,
frozen roots and 13 actions unchanged. It only improves the two cab-door edges:

- panel reveal is reduced to 12 mm on every opening side;
- panel shell thickness is reduced from 20 mm to 8 mm while its inner face
  remains 50 mm outside the body skin;
- the visible dark native-opening seal is reduced to 9 mm and leaves a small
  6 mm neutral gap to the moving panel.
"""

import importlib.util
import json
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


SCRIPT_DIR = Path(__file__).resolve().parent
F8_PATH = SCRIPT_DIR / "build_s2_body_r4_fix8.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix8", F8_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F8 builder: {F8_PATH}")
f8 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f8)

f7b = f8.f7b
f7 = f8.f7
f6 = f7.f6
f5 = f6.f5
r4 = f8.r4
r3 = f8.r3
builder = f8.builder
entry = f8.entry
clearance = f8.clearance
WINDSHIELD_ROTATION_Y = f8.WINDSHIELD_ROTATION_Y
WINDSHIELD_PLANE_HEIGHT_M = f8.WINDSHIELD_PLANE_HEIGHT_M
WINDSHIELD_CENTER = f8.WINDSHIELD_CENTER

CAB_PANEL_X_MIN = -4.388
CAB_PANEL_X_MAX = -3.892
CAB_PANEL_Z_MIN = 0.462
CAB_PANEL_Z_MAX = 2.158
CAB_PANEL_REVEAL_M = 0.012
CAB_PANEL_OUTER_OFFSET_M = 0.058
CAB_PANEL_INNER_OFFSET_M = 0.050
CAB_PANEL_THICKNESS_M = CAB_PANEL_OUTER_OFFSET_M - CAB_PANEL_INNER_OFFSET_M
CAB_SEAL_WIDTH_M = 0.009

ORIGINAL_APPLY = r4.apply_r4_surface_repairs


def tight_cab_door_panel(name, side_sign):
    obj = bpy.data.objects.get(name)
    if obj is None or obj.parent is None:
        raise RuntimeError(f"R4-F9 missing cab door panel: {name}")
    root = obj.parent
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()

    def side_y(x, outward_m):
        return (
            side_sign * builder.section_dimensions(x)[0] / 2.0
            + side_sign * outward_m
        )

    world_outer = (
        Vector((CAB_PANEL_X_MIN, side_y(CAB_PANEL_X_MIN, CAB_PANEL_OUTER_OFFSET_M), CAB_PANEL_Z_MIN)),
        Vector((CAB_PANEL_X_MAX, side_y(CAB_PANEL_X_MAX, CAB_PANEL_OUTER_OFFSET_M), CAB_PANEL_Z_MIN)),
        Vector((CAB_PANEL_X_MAX, side_y(CAB_PANEL_X_MAX, CAB_PANEL_OUTER_OFFSET_M), CAB_PANEL_Z_MAX)),
        Vector((CAB_PANEL_X_MIN, side_y(CAB_PANEL_X_MIN, CAB_PANEL_OUTER_OFFSET_M), CAB_PANEL_Z_MAX)),
    )
    world_inner = (
        Vector((CAB_PANEL_X_MIN, side_y(CAB_PANEL_X_MIN, CAB_PANEL_INNER_OFFSET_M), CAB_PANEL_Z_MIN)),
        Vector((CAB_PANEL_X_MAX, side_y(CAB_PANEL_X_MAX, CAB_PANEL_INNER_OFFSET_M), CAB_PANEL_Z_MIN)),
        Vector((CAB_PANEL_X_MAX, side_y(CAB_PANEL_X_MAX, CAB_PANEL_INNER_OFFSET_M), CAB_PANEL_Z_MAX)),
        Vector((CAB_PANEL_X_MIN, side_y(CAB_PANEL_X_MIN, CAB_PANEL_INNER_OFFSET_M), CAB_PANEL_Z_MAX)),
    )
    inverse = root.matrix_world.inverted()
    local_points = [inverse @ point for point in world_outer + world_inner]
    centroid = sum(local_points, Vector()) / len(local_points)
    vertices = [tuple(point - centroid) for point in local_points]
    faces = (
        (0, 1, 2, 3),
        (7, 6, 5, 4),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    )

    old_mesh = obj.data
    mesh = bpy.data.meshes.new(f"{name}_R4_F9_TIGHT_REVEAL_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=True)
    mesh.update(calc_edges=True)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()

    obj.data = mesh
    obj.location = centroid
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)
    mesh.materials.clear()
    body_material = bpy.data.materials.get("MAT_BODY_SILVER")
    if body_material is not None:
        mesh.materials.append(body_material)
    if old_mesh is not None and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)

    # Preserve every inherited structural marker expected by R3/F8 consumers.
    obj["s2_r3_tapered_cab_panel"] = True
    obj["s2_r3_moving_origin_centered"] = True
    obj["s2_r3_closed_boundary_clearance_fix"] = True
    obj["s2_r4_f8_integrated_cab_panel"] = True
    obj["s2_r4_f8_panel_x_min_m"] = CAB_PANEL_X_MIN
    obj["s2_r4_f8_panel_x_max_m"] = CAB_PANEL_X_MAX
    obj["s2_r4_f8_panel_z_min_m"] = CAB_PANEL_Z_MIN
    obj["s2_r4_f8_panel_z_max_m"] = CAB_PANEL_Z_MAX
    obj["s2_r4_f8_horizontal_reveal_m"] = CAB_PANEL_REVEAL_M
    obj["s2_r4_f8_vertical_reveal_m"] = CAB_PANEL_REVEAL_M
    obj["s2_r4_f8_outer_offset_m"] = CAB_PANEL_OUTER_OFFSET_M
    obj["s2_r4_f8_inner_offset_m"] = CAB_PANEL_INNER_OFFSET_M
    obj["s2_r4_f9_tight_reveal_panel"] = True
    obj["s2_r4_f9_reveal_m"] = CAB_PANEL_REVEAL_M
    obj["s2_r4_f9_shell_thickness_m"] = CAB_PANEL_THICKNESS_M
    obj["s2_r4_f9_outer_offset_m"] = CAB_PANEL_OUTER_OFFSET_M
    obj["s2_r4_f9_inner_offset_m"] = CAB_PANEL_INNER_OFFSET_M


r3.replace_cab_door_panel = tight_cab_door_panel


def rebuild_tight_cab_seals(body_root, trim_material):
    for side, side_sign in (("L", -1.0), ("R", 1.0)):
        seal = f5.make_segmented_side_ring(
            f"R4_CAB_SEAM_{side}",
            side_sign,
            (-4.403, -3.877, 0.447, 2.173),
            (-4.394, -3.886, 0.456, 2.164),
            0.005,
            0.001,
            trim_material,
            body_root,
            0.0008,
            "native_opening_dark_seal",
        )
        seal["s2_r4_f3_source_edge_mask"] = True
        seal["s2_r4_f5_source_boundary_cover"] = True
        seal["s2_r4_f6_narrow_ring"] = True
        seal["s2_r4_f7_native_opening_seal"] = True
        seal["s2_r4_f7_seal_width_m"] = CAB_SEAL_WIDTH_M
        seal["s2_r4_f9_tight_reveal_seal"] = True
        seal["s2_r4_f9_seal_width_m"] = CAB_SEAL_WIDTH_M
        seal["s2_r4_f9_panel_gap_m"] = 0.006


def apply_r4_f9_surface_repairs():
    ORIGINAL_APPLY()
    body_root = bpy.data.objects.get("BODY")
    trim_material = bpy.data.materials.get("MAT_TRIM")
    if body_root is None or trim_material is None:
        raise RuntimeError("R4-F9 body root or trim material missing")
    rebuild_tight_cab_seals(body_root, trim_material)


r4.apply_r4_surface_repairs = apply_r4_f9_surface_repairs


def patch_fix9_manifest(path):
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload.setdefault("r4_visual_repairs", {}).update(
        {
            "tight_cab_panels": 2,
            "cab_panel_x_range_m": [CAB_PANEL_X_MIN, CAB_PANEL_X_MAX],
            "cab_panel_z_range_m": [CAB_PANEL_Z_MIN, CAB_PANEL_Z_MAX],
            "cab_panel_reveal_m": CAB_PANEL_REVEAL_M,
            "cab_panel_shell_thickness_m": CAB_PANEL_THICKNESS_M,
            "cab_panel_outer_offset_m": CAB_PANEL_OUTER_OFFSET_M,
            "cab_panel_inner_offset_m": CAB_PANEL_INNER_OFFSET_M,
            "tight_cab_dark_seals": 2,
            "cab_seal_width_m": CAB_SEAL_WIDTH_M,
            "cab_seal_to_panel_gap_m": 0.006,
            "windshield_f8_glass_hugging_seal_preserved": True,
            "source_opening_topology_unchanged": True,
            "source_openings_unchanged": True,
            "web_node_and_animation_contract_preserved": True,
        }
    )
    payload["stage_status"] = "R4_F9_TIGHT_CAB_REVEAL_CANDIDATE"
    payload["r4_fix_iteration"] = "F9"
    payload["scope_note"] = (
        "R4-F9 preserves the validated F8 windshield and F7b native source "
        "boundaries. Cab panels now use 12 mm reveals and 8 mm shell edges, with "
        "9 mm native-opening seals and a 6 mm neutral moving gap."
    )
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    f8.main()
    args = builder.parse_args()
    patch_fix9_manifest(args.manifest)
    print("NOMADHUB_S2_R4_F9_TIGHT_CAB_REVEAL_OK")


if __name__ == "__main__":
    main()
