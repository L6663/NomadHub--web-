"""Final R3 integration correction for closed cab-door boundary clearance."""

import importlib.util
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


SCRIPT_DIR = Path(__file__).resolve().parent
FIX2_PATH = SCRIPT_DIR / "build_s2_body_r3_fix2.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r3_fix2", FIX2_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load second R3 fix: {FIX2_PATH}")
fix2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fix2)
r3 = fix2.r3
builder = fix2.builder
entry = fix2.entry
clearance = fix2.clearance


def boundary_clear_cab_door_panel(name, side_sign):
    obj = bpy.data.objects.get(name)
    if obj is None or obj.parent is None:
        raise RuntimeError(f"missing cab door panel: {name}")
    root = obj.parent
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()

    # The true opening is x[-4.400,-3.880], z[0.450,2.170]. The second
    # correction left one triangle touching the subdivided boundary at each
    # closed door. Increase the reveal by 15-20 mm and move the complete inner
    # skin farther outside the body; frozen hinge/root coordinates are unchanged.
    x_min, x_max = -4.335, -3.945
    z_min, z_max = 0.525, 2.095
    outer_offset = side_sign * 0.055
    inner_offset = side_sign * 0.025

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
    mesh = bpy.data.meshes.new(f"{name}_R3_BOUNDARY_CLEAR_MESH")
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
    obj["s2_r3_sweep_clear_reveal_m"] = 0.065
    obj["s2_r3_min_outward_offset_m"] = 0.025
    obj["s2_r3_closed_boundary_clearance_fix"] = True


r3.replace_cab_door_panel = boundary_clear_cab_door_panel


def main():
    fix2.main()


if __name__ == "__main__":
    main()
