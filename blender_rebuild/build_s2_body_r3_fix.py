"""Integration fixes for the S2-R3 curvature candidate.

This wrapper keeps the successful R3 source surface and evidence generation,
while fixing three validation defects found after the first full build:

- keep the door-panel object origin away from the hinge so rotation produces a
  measurable world-space translation;
- move service-hatch covers slightly outward instead of into the body skin;
- apply the strict true-opening and wheel-profile manifest patches before the
  final R3 metadata patch.
"""

import importlib.util
import json
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


SCRIPT_DIR = Path(__file__).resolve().parent
CORE_PATH = SCRIPT_DIR / "build_s2_body_r3.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r3_core", CORE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R3 core builder: {CORE_PATH}")
r3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r3)
builder = r3.builder
entry = r3.entry
clearance = r3.clearance


ORIGINAL_INSET_EXISTING_PANELS = r3.inset_existing_panels


def corrected_replace_cab_door_panel(name, side_sign):
    obj = bpy.data.objects.get(name)
    if obj is None or obj.parent is None:
        raise RuntimeError(f"missing cab door panel: {name}")
    root = obj.parent
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()

    x_min, x_max = -4.385, -3.895
    z_min, z_max = 0.465, 2.155
    outer_offset = side_sign * 0.010
    inner_offset = -side_sign * 0.030

    def side_y(x, offset):
        return side_sign * builder.section_dimensions(x)[0] / 2.0 + offset

    world_outer = (
        Vector((x_min, side_y(x_min, outer_offset), z_min)),
        Vector((x_max, side_y(x_max, outer_offset), z_min)),
        Vector((x_max, side_y(x_max, outer_offset), z_max)),
        Vector((x_min, side_y(x_min, outer_offset), z_max)),
    )
    world_inner = (
        Vector((x_min, side_y(x_min, inner_offset), z_min)),
        Vector((x_max, side_y(x_max, inner_offset), z_min)),
        Vector((x_max, side_y(x_max, inner_offset), z_max)),
        Vector((x_min, side_y(x_min, inner_offset), z_max)),
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
    mesh = bpy.data.meshes.new(f"{name}_R3_MESH")
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
    body_material = bpy.data.materials.get("MAT_BODY_SILVER")
    if body_material is not None:
        mesh.materials.append(body_material)
    if old_mesh is not None and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    obj["s2_r3_tapered_cab_panel"] = True
    obj["s2_r3_moving_origin_centered"] = True


def corrected_inset_existing_panels():
    ORIGINAL_INSET_EXISTING_PANELS()
    # Root Y is already outside the body at +/-1.18 m. A small local outward
    # offset preserves the visible frame reveal without embedding the cover in
    # the evaluated body surface near the rear wheel-well transition.
    for name in (
        "HATCH_L_1",
        "HATCH_L_2",
        "HATCH_L_3",
        "HATCH_R_1",
        "HATCH_R_2",
        "HATCH_R_3",
    ):
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        side_sign = -1.0 if "_L_" in name else 1.0
        obj.location.y = side_sign * 0.012
        obj["s2_r3_panel_outward_clearance_m"] = 0.012


r3.replace_cab_door_panel = corrected_replace_cab_door_panel
r3.inset_existing_panels = corrected_inset_existing_panels


def finalize_manifest(args, evidence):
    # The imported R2 entry/clearance modules normally patch their manifest
    # only when executed as scripts. R3 invokes the shared builder directly,
    # so apply those patches explicitly before adding R3 metadata.
    entry.patch_manifest(args.manifest)
    clearance.patch_clearance_manifest(args.manifest)
    r3.patch_manifest(args, evidence)

    manifest_path = Path(args.manifest)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["iteration"] = "R3"
    payload["true_openings"] = list(entry.TRUE_OPENINGS)
    payload["true_opening_count"] = len(entry.TRUE_OPENINGS)
    payload["source_true_openings"] = True
    payload["wheel_well_source_profile"] = {
        "visible_arch_radius_m": r3.R3_CORE_ARCH_RADIUS_M,
        "outer_blend_radius_m": r3.R3_OUTER_BLEND_RADIUS_M,
        "inner_half_width_m": r3.R3_WELL_HALF_WIDTH_M,
        "clearance_profile_radius_m": r3.R3_CLEARANCE_RADIUS_M,
        "clearance_blend_radius_m": r3.R3_CLEARANCE_BLEND_RADIUS_M,
        "tire_center_z_m": r3.R3_TIRE_CENTER_Z_M,
        "clearance_margin_m": r3.R3_CLEARANCE_MARGIN_M,
        "method": "source_topology_smooth_local_raised_floor",
    }
    payload["r3_visual_repairs"]["cab_door_moving_origins_centered"] = True
    payload["r3_visual_repairs"]["hatch_outward_clearance_m"] = 0.012
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    args = builder.parse_args()
    builder.main()
    scene = bpy.context.scene
    scene["nomadhub_s2_iteration"] = "R3"
    scene["s2_status"] = "R3_LOCAL_CURVATURE_REPAIR_CANDIDATE"
    evidence = r3.render_r3_evidence(args)
    animation_mode = builder.r1.active_actions_merged_mode()
    builder.r1.export_gltf_compatible(args.roundtrip, animation_mode)
    bpy.ops.wm.save_as_mainfile(filepath=args.output, compress=True)
    Path(args.output + "1").unlink(missing_ok=True)
    finalize_manifest(args, evidence)
    print("NOMADHUB_S2_R3_INTEGRATION_FIX_OK")
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == "__main__":
    main()
