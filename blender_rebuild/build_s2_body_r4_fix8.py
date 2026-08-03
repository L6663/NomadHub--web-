"""R4-F8 integration polish for cab panels and windshield seal.

F8 preserves the accepted all-quad source cage, 17 native opening loops, frozen
roots and 13 actions. It addresses the last evidence-review defects:

- the two animated cab panels fill the corrected native opening with a uniform
  25 mm horizontal / 30 mm vertical reveal instead of exposing a broad grey
  recess around a much smaller panel;
- the windshield uses one 15 mm dark trapezoid seal whose inner boundary is
  coincident with the existing opening-matched glass, removing the detached
  double-line appearance below the glass.
"""

import importlib.util
import json
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


SCRIPT_DIR = Path(__file__).resolve().parent
F7B_PATH = SCRIPT_DIR / "build_s2_body_r4_fix7b.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix7b", F7B_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F7b builder: {F7B_PATH}")
f7b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f7b)

f7 = f7b.f7
f6 = f7.f6
r4 = f7.r4
r3 = r4.r3
builder = f7b.builder
entry = f7b.entry
clearance = f7b.clearance
WINDSHIELD_ROTATION_Y = f7b.WINDSHIELD_ROTATION_Y
WINDSHIELD_PLANE_HEIGHT_M = f7b.WINDSHIELD_PLANE_HEIGHT_M
WINDSHIELD_CENTER = f7b.WINDSHIELD_CENTER

CAB_PANEL_X_MIN = -4.375
CAB_PANEL_X_MAX = -3.905
CAB_PANEL_Z_MIN = 0.480
CAB_PANEL_Z_MAX = 2.140
CAB_PANEL_OUTER_OFFSET_M = 0.060
CAB_PANEL_INNER_OFFSET_M = 0.040

ORIGINAL_APPLY = r4.apply_r4_surface_repairs


def integrated_cab_door_panel(name, side_sign):
    obj = bpy.data.objects.get(name)
    if obj is None or obj.parent is None:
        raise RuntimeError(f"R4-F8 missing cab door panel: {name}")
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
    mesh = bpy.data.meshes.new(f"{name}_R4_F8_INTEGRATED_MESH")
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

    obj["s2_r3_tapered_cab_panel"] = True
    obj["s2_r3_moving_origin_centered"] = True
    obj["s2_r3_closed_boundary_clearance_fix"] = True
    obj["s2_r4_f8_integrated_cab_panel"] = True
    obj["s2_r4_f8_panel_x_min_m"] = CAB_PANEL_X_MIN
    obj["s2_r4_f8_panel_x_max_m"] = CAB_PANEL_X_MAX
    obj["s2_r4_f8_panel_z_min_m"] = CAB_PANEL_Z_MIN
    obj["s2_r4_f8_panel_z_max_m"] = CAB_PANEL_Z_MAX
    obj["s2_r4_f8_horizontal_reveal_m"] = 0.025
    obj["s2_r4_f8_vertical_reveal_m"] = 0.030
    obj["s2_r4_f8_outer_offset_m"] = CAB_PANEL_OUTER_OFFSET_M
    obj["s2_r4_f8_inner_offset_m"] = CAB_PANEL_INNER_OFFSET_M


r3.replace_cab_door_panel = integrated_cab_door_panel


def rebuild_glass_hugging_windshield_seal(body_root, trim_material):
    trim = f6.make_local_trapezoid_ring(
        "R4_WINDSHIELD_TRIM",
        1.730,
        1.770,
        0.530,
        1.700,
        1.740,
        0.500,
        0.004,
        trim_material,
        body_root,
        0.0008,
        "continuous_windshield_inner_trim",
    )
    trim["s2_r4_f7_native_opening_seal"] = True
    trim["s2_r4_f7_seal_width_m"] = 0.015
    trim["s2_r4_f8_glass_hugging_seal"] = True
    trim["s2_r4_f8_seal_radial_width_m"] = 0.015
    trim["s2_r4_f8_inner_bottom_width_m"] = 1.700
    trim["s2_r4_f8_inner_top_width_m"] = 1.740
    trim["s2_r4_f8_inner_height_m"] = 0.500


def apply_r4_f8_surface_repairs():
    ORIGINAL_APPLY()
    body_root = bpy.data.objects.get("BODY")
    trim_material = bpy.data.materials.get("MAT_TRIM")
    if body_root is None or trim_material is None:
        raise RuntimeError("R4-F8 body root or trim material missing")
    rebuild_glass_hugging_windshield_seal(body_root, trim_material)


r4.apply_r4_surface_repairs = apply_r4_f8_surface_repairs


def patch_fix8_manifest(path):
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload.setdefault("r4_visual_repairs", {}).update(
        {
            "integrated_cab_panels": 2,
            "cab_panel_x_range_m": [CAB_PANEL_X_MIN, CAB_PANEL_X_MAX],
            "cab_panel_z_range_m": [CAB_PANEL_Z_MIN, CAB_PANEL_Z_MAX],
            "cab_panel_horizontal_reveal_m": 0.025,
            "cab_panel_vertical_reveal_m": 0.030,
            "cab_panel_outer_offset_m": CAB_PANEL_OUTER_OFFSET_M,
            "cab_panel_inner_offset_m": CAB_PANEL_INNER_OFFSET_M,
            "windshield_single_glass_hugging_seal": True,
            "windshield_seal_radial_width_m": 0.015,
            "source_opening_topology_unchanged": True,
            "source_openings_unchanged": True,
            "web_node_and_animation_contract_preserved": True,
        }
    )
    payload["stage_status"] = "R4_F8_CAB_PANEL_AND_WINDSHIELD_SEAL_CANDIDATE"
    payload["r4_fix_iteration"] = "F8"
    payload["scope_note"] = (
        "R4-F8 preserves the validated F7b native opening boundaries and all "
        "technical contracts. Cab panels fill the openings with uniform 25-30 mm "
        "reveals, and one 15 mm trapezoid seal is coincident with the existing "
        "opening-matched windshield glass."
    )
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    f7b.main()
    args = builder.parse_args()
    patch_fix8_manifest(args.manifest)
    print("NOMADHUB_S2_R4_F8_INTEGRATION_POLISH_OK")


if __name__ == "__main__":
    main()
