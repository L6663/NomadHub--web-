import argparse
import hashlib
import json
import math
import sys
import traceback
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


OVERALL_LENGTH_M = 8.990
OVERALL_WIDTH_M = 2.350
OVERALL_HEIGHT_M = 3.050
FRONT_AXLE_X_M = -3.245
REAR_AXLE_X_M = 1.905
WHEELBASE_M = 5.150

# The exact frozen X coordinates are deliberately represented by control rings.
RING_XS = (
    -4.495,
    -4.430,
    -4.300,
    -4.080,
    -3.900,
    -3.800,
    -3.750,
    -3.245,
    -2.710,
    -2.600,
    -2.500,
    -2.475,
    -1.950,
    -1.425,
    -0.880,
    -0.820,
    -0.040,
    0.020,
    0.225,
    0.750,
    1.275,
    1.340,
    1.370,
    1.905,
    2.440,
    2.500,
    2.525,
    3.050,
    3.575,
    4.350,
    4.495,
)

DOOR_GLASS = (
    (
        "DOOR_DRIVER_L_GLASS",
        "DOOR_DRIVER_L_ROOT",
        (0.36, 0.025, 0.58),
        (0.26, -0.040, 1.36),
    ),
    (
        "DOOR_PASSENGER_R_GLASS",
        "DOOR_PASSENGER_R_ROOT",
        (0.36, 0.025, 0.58),
        (0.26, 0.040, 1.36),
    ),
    (
        "DOOR_LIVING_R_GLASS",
        "DOOR_LIVING_R_ROOT",
        (0.54, 0.025, 0.58),
        (0.39, 0.040, 1.48),
    ),
)
STATIC_GLASS_TO_REMOVE = (
    "GLASS_CAB_L",
    "GLASS_CAB_R",
    "GLASS_LIVING_R_02",
)


def parse_args():
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--glb", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--preview", required=True)
    parser.add_argument("--left", required=True)
    parser.add_argument("--wireframe", required=True)
    return parser.parse_args(raw)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def remove_object(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        return
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data is not None and data.users == 0:
        if isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
        elif isinstance(data, bpy.types.Curve):
            bpy.data.curves.remove(data)


def make_door_glass(name, parent_name, dimensions, local_location, material):
    remove_object(name)
    parent = bpy.data.objects.get(parent_name)
    if parent is None:
        raise RuntimeError(f"missing S1C door root: {parent_name}")
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}_MESH"
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.parent = parent
    obj.location = local_location
    obj.data.materials.append(material)
    obj["nomadhub_semantic_node"] = name
    obj["s1c_parent_gate"] = parent_name
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    bevel = obj.modifiers.new("NH_Bevel", "BEVEL")
    bevel.width = 0.025
    bevel.segments = 2
    bevel.limit_method = "ANGLE"
    return obj


def finalize_door_glass_hierarchy():
    glass_material = bpy.data.materials.get("MAT_GLASS")
    if glass_material is None:
        raise RuntimeError("MAT_GLASS missing from S1C base")
    for name in STATIC_GLASS_TO_REMOVE:
        remove_object(name)
    for name, parent_name, dimensions, local_location in DOOR_GLASS:
        make_door_glass(
            name,
            parent_name,
            dimensions,
            local_location,
            glass_material,
        )


def interpolate(x, a, b):
    ax, aw, az0, az1 = a
    bx, bw, bz0, bz1 = b
    if abs(bx - ax) < 1e-9:
        return aw, az0, az1
    t = (x - ax) / (bx - ax)
    return (
        aw + (bw - aw) * t,
        az0 + (bz0 - az0) * t,
        az1 + (bz1 - az1) * t,
    )


def section_dimensions(x):
    front_keys = (
        (-4.495, 2.050, 0.300, 1.650),
        (-4.430, 2.200, 0.290, 2.100),
        (-4.300, 2.250, 0.285, 2.400),
        (-4.080, 2.280, 0.280, 2.660),
        (-3.900, 2.300, 0.280, 2.760),
    )
    rear_keys = (
        (4.350, 2.300, 0.280, 2.760),
        (4.495, 2.260, 0.300, 2.580),
    )
    if x <= front_keys[-1][0]:
        for first, second in zip(front_keys, front_keys[1:]):
            if first[0] <= x <= second[0]:
                return interpolate(x, first, second)
        return front_keys[0][1:]
    if x >= rear_keys[0][0]:
        return interpolate(x, rear_keys[0], rear_keys[1])
    return 2.300, 0.280, 2.760


def cross_section(width, z_low, z_top):
    half = width / 2
    roof_corner = min(0.18, half * 0.18)
    lower_corner = min(0.12, half * 0.12)
    return (
        (-half + lower_corner, z_low),
        (-0.35 * half, z_low),
        (0.35 * half, z_low),
        (half - lower_corner, z_low),
        (half, z_low + lower_corner),
        (half, z_low + 0.60),
        (half, z_top - 0.55),
        (half - 0.03, z_top - 0.22),
        (half - roof_corner, z_top),
        (0.35 * half, z_top),
        (-0.35 * half, z_top),
        (-half + roof_corner, z_top),
        (-half + 0.03, z_top - 0.22),
        (-half, z_top - 0.55),
        (-half, z_low + 0.60),
        (-half, z_low + lower_corner),
    )


def build_control_cage(material):
    vertices = []
    ring_size = 16
    for x in RING_XS:
        width, z_low, z_top = section_dimensions(x)
        vertices.extend((x, y, z) for y, z in cross_section(width, z_low, z_top))

    faces = []
    for ring_index in range(len(RING_XS) - 1):
        current = ring_index * ring_size
        following = (ring_index + 1) * ring_size
        for point_index in range(ring_size):
            nxt = (point_index + 1) % ring_size
            faces.append(
                (
                    current + point_index,
                    following + point_index,
                    following + nxt,
                    current + nxt,
                )
            )
    faces.append(tuple(range(ring_size - 1, -1, -1)))
    rear_start = (len(RING_XS) - 1) * ring_size
    faces.append(tuple(rear_start + index for index in range(ring_size)))

    mesh = bpy.data.meshes.new("BODY_S2_CONTROL_CAGE_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=True)
    mesh.update()

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new("BODY_S2_CONTROL_CAGE", mesh)
    bpy.context.scene.collection.objects.link(obj)
    body_parent = bpy.data.objects.get("BODY")
    if body_parent is None:
        raise RuntimeError("BODY root missing from S1C base")
    obj.parent = body_parent
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True

    obj["nomadhub_semantic_node"] = "BODY_S2_CONTROL_CAGE"
    obj["s2_stage"] = "S2_R1_CONTINUOUS_CAGE"
    obj["s2_ring_count"] = len(RING_XS)
    obj["s2_ring_size"] = ring_size
    obj["s2_frozen_wheelbase_m"] = WHEELBASE_M
    obj["s2_topology_scope"] = (
        "Single closed quad-dominant cage with front/rear cap ngons; "
        "door/window local retopology remains S2 work."
    )

    subdivision = obj.modifiers.new("S2_Subdivision", "SUBSURF")
    subdivision.subdivision_type = "CATMULL_CLARK"
    subdivision.levels = 2
    subdivision.render_levels = 2
    subdivision.show_only_control_edges = True

    return obj


def create_arch_cutter(name, x, parent):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64,
        radius=0.560,
        depth=2.700,
        location=(x, 0, 0.430),
        rotation=(math.pi / 2, 0, 0),
    )
    cutter = bpy.context.object
    cutter.name = name
    cutter.data.name = f"{name}_MESH"
    cutter.parent = parent
    cutter["s2_boolean_role"] = "WHEEL_ARCH_PLACEHOLDER"
    cutter.hide_render = True
    cutter.hide_viewport = True
    cutter.hide_set(True)
    return cutter


def add_arch_booleans(body):
    body_parent = bpy.data.objects.get("BODY")
    front = create_arch_cutter("S2_CUTTER_ARCH_FRONT", FRONT_AXLE_X_M, body_parent)
    rear = create_arch_cutter("S2_CUTTER_ARCH_REAR", REAR_AXLE_X_M, body_parent)
    for label, cutter in (("Front", front), ("Rear", rear)):
        modifier = body.modifiers.new(f"S2_{label}_Arch", "BOOLEAN")
        modifier.operation = "DIFFERENCE"
        modifier.solver = "EXACT"
        modifier.object = cutter
    bevel = body.modifiers.new("S2_Arch_Edge_Bevel", "BEVEL")
    bevel.width = 0.018
    bevel.segments = 2
    bevel.limit_method = "ANGLE"
    return front, rear


def freeze_s1c_reference():
    reference_names = []
    for source_name in ("BODY_MAIN", "BODY_CAB"):
        obj = bpy.data.objects.get(source_name)
        if obj is None:
            raise RuntimeError(f"S1C reference body missing: {source_name}")
        reference_name = f"S1C_{source_name}_REFERENCE"
        obj.name = reference_name
        obj.hide_render = True
        obj.hide_viewport = True
        obj.hide_set(True)
        obj["s1c_frozen_reference"] = True
        reference_names.append(reference_name)
    return reference_names


def make_wireframe_copy(body, material):
    wire = body.copy()
    wire.data = body.data.copy()
    wire.name = "BODY_S2_CONTROL_CAGE_WIREFRAME"
    wire.data.name = "BODY_S2_CONTROL_CAGE_WIREFRAME_MESH"
    bpy.context.scene.collection.objects.link(wire)
    wire.parent = body.parent
    wire.data.materials.clear()
    wire.data.materials.append(material)
    wire.modifiers.clear()
    modifier = wire.modifiers.new("S2_Control_Wire", "WIREFRAME")
    modifier.thickness = 0.008
    modifier.use_replace = True
    wire.hide_render = True
    wire["s2_proof_only"] = True
    return wire


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def render(scene, camera, path, location, target, ortho_scale=None):
    scene.frame_set(1)
    camera.location = location
    camera.data.type = "ORTHO" if ortho_scale is not None else "PERSP"
    if ortho_scale is not None:
        camera.data.ortho_scale = ortho_scale
    else:
        camera.data.lens = 55
    look_at(camera, target)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def active_actions_merged_mode():
    properties = bpy.ops.export_scene.gltf.get_rna_type().properties
    mode_property = properties.get("export_animation_mode")
    if mode_property is None:
        raise RuntimeError("glTF exporter does not expose export_animation_mode")
    for item in mode_property.enum_items:
        searchable = f"{item.identifier} {item.name} {item.description}".lower()
        if "active" in searchable and "merged" in searchable:
            return item.identifier
    raise RuntimeError("Active Actions Merged mode unavailable")


def export_gltf_compatible(filepath, animation_mode):
    properties = bpy.ops.export_scene.gltf.get_rna_type().properties
    kwargs = {
        "filepath": filepath,
        "export_format": "GLB",
        "export_animations": True,
        "export_animation_mode": animation_mode,
        "export_apply": True,
        "export_extras": True,
    }
    if properties.get("use_visible") is not None:
        kwargs["use_visible"] = True
    elif properties.get("export_visible") is not None:
        kwargs["export_visible"] = True
    elif properties.get("use_selection") is not None:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in bpy.context.scene.objects:
            excluded = (
                obj.hide_get()
                or obj.hide_viewport
                or obj.hide_render
                or bool(obj.get("s2_proof_only", False))
            )
            if not excluded:
                obj.select_set(True)
        kwargs["use_selection"] = True
    else:
        raise RuntimeError(
            "Blender glTF exporter exposes no compatible visible/selection filter"
        )
    bpy.ops.export_scene.gltf(**kwargs)


def polygon_statistics(mesh):
    counts = {"triangles": 0, "quads": 0, "ngons": 0}
    for polygon in mesh.polygons:
        vertex_count = len(polygon.vertices)
        if vertex_count == 3:
            counts["triangles"] += 1
        elif vertex_count == 4:
            counts["quads"] += 1
        else:
            counts["ngons"] += 1
    total = len(mesh.polygons)
    counts["total"] = total
    counts["quad_ratio"] = counts["quads"] / total if total else 0
    return counts


def main():
    args = parse_args()
    scene = bpy.context.scene
    output_dir = Path(args.output).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    finalize_door_glass_hierarchy()
    references = freeze_s1c_reference()

    silver = bpy.data.materials.get("MAT_BODY_SILVER")
    cyan = bpy.data.materials.get("MAT_ACCENT_CYAN")
    if silver is None or cyan is None:
        raise RuntimeError("S1C materials missing")

    body = build_control_cage(silver)
    cutters = add_arch_booleans(body)
    wire = make_wireframe_copy(body, cyan)

    scene["nomadhub_stage"] = "S2_R1"
    scene["s2_status"] = "IN_PROGRESS"
    scene["s2_continuous_body"] = "BODY_S2_CONTROL_CAGE"
    scene["s2_frozen_source"] = "S1C_ACCEPTED"
    scene["wheelbase_m"] = WHEELBASE_M

    camera = bpy.data.objects.get("Camera")
    if camera is None or camera.type != "CAMERA":
        raise RuntimeError("Camera missing from S1C base")
    scene.camera = camera
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    body.hide_render = False
    wire.hide_render = True
    render(scene, camera, args.preview, (-11, -10, 7.2), (0, 0, 1.35))
    render(scene, camera, args.left, (0, -14, 1.55), (0, 0, 1.45), 10.5)

    body.hide_render = True
    wire.hide_render = False
    render(scene, camera, args.wireframe, (-11, -10, 7.2), (0, 0, 1.35))
    body.hide_render = False
    wire.hide_render = True
    wire.hide_viewport = True
    wire.hide_set(True)
    scene.frame_set(1)

    bpy.ops.wm.save_as_mainfile(filepath=args.output, compress=True)
    Path(args.output + "1").unlink(missing_ok=True)

    animation_mode = active_actions_merged_mode()
    export_gltf_compatible(args.glb, animation_mode)
    bpy.ops.wm.save_as_mainfile(filepath=args.output, compress=True)
    Path(args.output + "1").unlink(missing_ok=True)

    topology = polygon_statistics(body.data)
    manifest = {
        "artifact_type": "genuine_blender_native_project",
        "project": "NomadHub General3",
        "version": "V1.7",
        "stage": "S2_R1",
        "stage_status": "IN_PROGRESS_PENDING_VALIDATION",
        "scope": "continuous_body_control_cage",
        "blender_version": bpy.app.version_string,
        "blend": args.output,
        "blend_bytes": Path(args.output).stat().st_size,
        "blend_sha256": sha256(args.output),
        "glb": args.glb,
        "glb_bytes": Path(args.glb).stat().st_size,
        "glb_sha256": sha256(args.glb),
        "preview": args.preview,
        "left_orthographic": args.left,
        "wireframe": args.wireframe,
        "objects": len(bpy.data.objects),
        "meshes": len(bpy.data.meshes),
        "materials": len(bpy.data.materials),
        "actions": len(bpy.data.actions),
        "body_object": body.name,
        "body_vertices": len(body.data.vertices),
        "body_edges": len(body.data.edges),
        "body_topology": topology,
        "control_ring_count": len(RING_XS),
        "control_ring_size": 16,
        "control_ring_x_m": list(RING_XS),
        "modifiers": [modifier.type for modifier in body.modifiers],
        "boolean_cutters": [cutter.name for cutter in cutters],
        "frozen_references": references,
        "frozen_geometry": {
            "overall_length_m": OVERALL_LENGTH_M,
            "overall_width_m": OVERALL_WIDTH_M,
            "overall_height_m": OVERALL_HEIGHT_M,
            "front_axle_x_m": FRONT_AXLE_X_M,
            "rear_axle_x_m": REAR_AXLE_X_M,
            "wheelbase_m": WHEELBASE_M,
        },
        "glb_animation_export_mode": animation_mode,
        "scope_limit": (
            "S2-R1 starts a single quad-dominant continuous body cage and non-destructive "
            "wheel-arch placeholders. Door/window local topology, production retopology, "
            "formal UV and product-grade surfacing are not accepted in this revision."
        ),
    }
    Path(args.manifest).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("NOMADHUB_S2_R1_BUILD_OK")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
