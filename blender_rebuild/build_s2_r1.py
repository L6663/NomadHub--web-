"""S2-R1 build entrypoint with continuous-body windshield projection.

The accepted S1C windshield was positioned against the old box/prism body and
is occluded by the new continuous S2 cage. This entrypoint keeps that object as
a hidden reference and projects a new editable windshield panel directly onto
the evaluated S2 front surface before the standard proof renders and GLB export.
"""

import importlib.util
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


SCRIPT_DIR = Path(__file__).resolve().parent
CORE_PATH = SCRIPT_DIR / "build_s2_body.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_build_s2_body", CORE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load S2 builder core: {CORE_PATH}")
core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(core)

ORIGINAL_BUILD_CONTROL_CAGE = core.build_control_cage
WINDSHIELD_Y = (-0.96, -0.48, 0.0, 0.48, 0.96)
WINDSHIELD_Z = (1.70, 1.92, 2.14, 2.36, 2.58)
SURFACE_OFFSET_M = 0.012


def remove_object(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        return
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data is not None and data.users == 0 and isinstance(data, bpy.types.Mesh):
        bpy.data.meshes.remove(data)


def evaluated_world_bvh(obj):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        polygons = [tuple(polygon.vertices) for polygon in mesh.polygons]
        return BVHTree.FromPolygons(
            vertices,
            polygons,
            all_triangles=False,
            epsilon=1e-6,
        )
    finally:
        evaluated.to_mesh_clear()


def project_front_surface(body):
    bvh = evaluated_world_bvh(body)
    vertices = []
    projection_rows = []
    for z in WINDSHIELD_Z:
        row = []
        for y in WINDSHIELD_Y:
            origin = Vector((-6.0, y, z))
            location, normal, _, distance = bvh.ray_cast(
                origin,
                Vector((1.0, 0.0, 0.0)),
                4.0,
            )
            if location is None or normal is None:
                raise RuntimeError(
                    f"windshield projection missed S2 body at y={y:.3f}, z={z:.3f}"
                )
            if normal.x > 0:
                normal.negate()
            projected = location + normal.normalized() * SURFACE_OFFSET_M
            vertices.append(tuple(projected))
            row.append(
                {
                    "y_m": round(y, 6),
                    "z_m": round(z, 6),
                    "x_m": round(projected.x, 6),
                    "ray_distance_m": round(distance, 6),
                }
            )
        projection_rows.append(row)
    return vertices, projection_rows


def create_projected_windshield(body):
    old = bpy.data.objects.get("GLASS_WINDSHIELD")
    remove_object("S1C_GLASS_WINDSHIELD_REFERENCE")
    if old is not None:
        old.name = "S1C_GLASS_WINDSHIELD_REFERENCE"
        old.hide_render = True
        old.hide_viewport = True
        old.hide_set(True)
        old["s1c_frozen_reference"] = True

    vertices, projection_rows = project_front_surface(body)
    columns = len(WINDSHIELD_Y)
    rows = len(WINDSHIELD_Z)
    faces = []
    for row in range(rows - 1):
        for column in range(columns - 1):
            lower_left = row * columns + column
            lower_right = lower_left + 1
            upper_left = (row + 1) * columns + column
            upper_right = upper_left + 1
            # Ordering points the front panel normal toward negative X.
            faces.append((lower_left, upper_left, upper_right, lower_right))

    mesh = bpy.data.meshes.new("GLASS_WINDSHIELD_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=True)
    mesh.update(calc_edges=True)

    windshield = bpy.data.objects.new("GLASS_WINDSHIELD", mesh)
    bpy.context.scene.collection.objects.link(windshield)
    glass_root = bpy.data.objects.get("GLASS")
    if glass_root is None:
        raise RuntimeError("GLASS hierarchy root missing")
    windshield.parent = glass_root

    material = bpy.data.materials.get("MAT_GLASS")
    if material is None:
        raise RuntimeError("MAT_GLASS missing")
    mesh.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = True

    solidify = windshield.modifiers.new("S2_Windshield_Thickness", "SOLIDIFY")
    solidify.thickness = 0.008
    solidify.offset = 0.0
    bevel = windshield.modifiers.new("S2_Windshield_Edge", "BEVEL")
    bevel.width = 0.010
    bevel.segments = 2
    bevel.limit_method = "ANGLE"

    windshield["nomadhub_semantic_node"] = "GLASS_WINDSHIELD"
    windshield["s2_visual_role"] = "PROJECTED_CONTINUOUS_BODY_WINDSHIELD"
    windshield["s2_projection_rows"] = rows
    windshield["s2_projection_columns"] = columns
    windshield["s2_surface_offset_m"] = SURFACE_OFFSET_M
    windshield["s2_projection_data"] = str(projection_rows)
    return windshield


def build_control_cage_with_windshield(parent, material):
    body = ORIGINAL_BUILD_CONTROL_CAGE(parent, material)
    create_projected_windshield(body)
    return body


core.build_control_cage = build_control_cage_with_windshield


if __name__ == "__main__":
    core.main()
