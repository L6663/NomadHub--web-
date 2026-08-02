import argparse
import hashlib
import json
import math
import sys
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

# Frozen S1C anchors plus additional control rings for the cab taper, wheel
# arches, doors and service-hatch regions. This is the editable S2-R1 cage,
# not a claim of final production surfacing.
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
RING_SIZE = 16


def parse_args():
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--roundtrip", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--preview", required=True)
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    parser.add_argument("--top", required=True)
    parser.add_argument("--wire-left", required=True)
    parser.add_argument("--wire-right", required=True)
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


def interpolate(x, first, second):
    ax, aw, az0, az1 = first
    bx, bw, bz0, bz1 = second
    if abs(bx - ax) < 1e-9:
        return aw, az0, az1
    factor = (x - ax) / (bx - ax)
    return (
        aw + (bw - aw) * factor,
        az0 + (bz0 - az0) * factor,
        az1 + (bz1 - az1) * factor,
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


def build_control_cage(parent, material):
    vertices = []
    for x in RING_XS:
        width, z_low, z_top = section_dimensions(x)
        vertices.extend((x, y, z) for y, z in cross_section(width, z_low, z_top))

    faces = []
    for ring_index in range(len(RING_XS) - 1):
        current = ring_index * RING_SIZE
        following = (ring_index + 1) * RING_SIZE
        for point_index in range(RING_SIZE):
            nxt = (point_index + 1) % RING_SIZE
            faces.append(
                (
                    current + point_index,
                    following + point_index,
                    following + nxt,
                    current + nxt,
                )
            )

    # R1 deliberately keeps two planar cap n-gons. All longitudinal faces are
    # quads. The caps must be converted to quad patches before final S2 pass.
    faces.append(tuple(range(RING_SIZE - 1, -1, -1)))
    rear_start = (len(RING_XS) - 1) * RING_SIZE
    faces.append(tuple(rear_start + index for index in range(RING_SIZE)))

    mesh = bpy.data.meshes.new("BODY_S2_CONTROL_CAGE_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=True)
    mesh.update(calc_edges=True)

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update(calc_edges=True)

    body = bpy.data.objects.new("BODY_S2_CONTROL_CAGE", mesh)
    bpy.context.scene.collection.objects.link(body)
    body.parent = parent
    body.data.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = True

    body["nomadhub_semantic_node"] = "BODY_S2_CONTROL_CAGE"
    body["s2_stage"] = "S2_R1_CONTINUOUS_CAGE"
    body["s2_ring_count"] = len(RING_XS)
    body["s2_ring_size"] = RING_SIZE
    body["s2_ring_x_m"] = json.dumps(list(RING_XS))
    body["s1c_frozen_wheelbase_m"] = WHEELBASE_M
    body["s1c_frozen_front_axle_x_m"] = FRONT_AXLE_X_M
    body["s1c_frozen_rear_axle_x_m"] = REAR_AXLE_X_M
    body["s2_scope_limit"] = (
        "Quad-dominant continuous control cage with two cap n-gons and "
        "non-destructive wheel-arch openings; local door/window topology remains pending."
    )

    subdivision = body.modifiers.new("S2_Subdivision", "SUBSURF")
    subdivision.subdivision_type = "CATMULL_CLARK"
    subdivision.levels = 2
    subdivision.render_levels = 2
    subdivision.show_only_control_edges = True
    return body


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
    cutter["s2_boolean_role"] = "WHEEL_ARCH_R1"
    cutter.hide_render = True
    cutter.hide_viewport = True
    cutter.hide_set(True)
    return cutter


def add_arch_modifiers(body, parent):
    cutters = (
        create_arch_cutter("S2_CUTTER_ARCH_FRONT", FRONT_AXLE_X_M, parent),
        create_arch_cutter("S2_CUTTER_ARCH_REAR", REAR_AXLE_X_M, parent),
    )
    for label, cutter in (("Front", cutters[0]), ("Rear", cutters[1])):
        modifier = body.modifiers.new(f"S2_{label}_Arch", "BOOLEAN")
        modifier.operation = "DIFFERENCE"
        modifier.solver = "EXACT"
        modifier.object = cutter

    bevel = body.modifiers.new("S2_Arch_Edge_Bevel", "BEVEL")
    bevel.width = 0.018
    bevel.segments = 2
    bevel.limit_method = "ANGLE"
    return cutters


def freeze_s1c_reference():
    references = []
    for source_name in ("BODY_MAIN", "BODY_CAB"):
        obj = bpy.data.objects.get(source_name)
        if obj is None:
            raise RuntimeError(f"accepted S1C source missing: {source_name}")
        reference_name = f"S1C_{source_name}_REFERENCE"
        existing = bpy.data.objects.get(reference_name)
        if existing is not None and existing != obj:
            remove_object(reference_name)
        obj.name = reference_name
        obj.hide_render = True
        obj.hide_viewport = True
        obj.hide_set(True)
        obj["s1c_frozen_reference"] = True
        references.append(reference_name)
    return references


def make_wireframe_copy(body, material):
    wire = body.copy()
    wire.data = body.data.copy()
    wire.name = "BODY_S2_WIREFRAME"
    wire.data.name = "BODY_S2_WIREFRAME_MESH"
    bpy.context.scene.collection.objects.link(wire)
    wire.parent = body.parent
    wire.data.materials.clear()
    wire.data.materials.append(material)
    wire.modifiers.clear()
    modifier = wire.modifiers.new("S2_Control_Wire", "WIREFRAME")
    modifier.thickness = 0.008
    modifier.use_replace = True
    modifier.offset = 1.0
    wire.hide_render = True
    wire.hide_viewport = True
    wire["s2_proof_only"] = True
    return wire


def make_wire_material():
    material = bpy.data.materials.get("MAT_S2_WIREFRAME")
    if material is None:
        material = bpy.data.materials.new("MAT_S2_WIREFRAME")
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.005, 0.015, 0.025, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.42
    bsdf.inputs["Metallic"].default_value = 0.0
    return material


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


def set_wire_visibility(wire, visible):
    wire.hide_render = not visible
    wire.hide_viewport = not visible
    wire.hide_set(not visible)


def active_actions_merged_mode():
    properties = bpy.ops.export_scene.gltf.get_rna_type().properties
    mode_property = properties.get("export_animation_mode")
    if mode_property is None:
        raise RuntimeError("glTF exporter does not expose export_animation_mode")
    for item in mode_property.enum_items:
        searchable = f"{item.identifier} {item.name} {item.description}".lower()
        if "active" in searchable and "merged" in searchable:
            return item.identifier
    raise RuntimeError("Active Actions Merged glTF mode unavailable")


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
    if properties.get("export_visible") is not None:
        kwargs["export_visible"] = True
    elif properties.get("use_visible") is not None:
        kwargs["use_visible"] = True
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
        raise RuntimeError("glTF exporter has no visible-object filter")
    bpy.ops.export_scene.gltf(**kwargs)


def topology_metrics(mesh):
    face_sizes = [len(polygon.vertices) for polygon in mesh.polygons]
    quad_count = sum(size == 4 for size in face_sizes)
    triangle_count = sum(size == 3 for size in face_sizes)
    ngon_count = sum(size > 4 for size in face_sizes)
    return {
        "vertices": len(mesh.vertices),
        "edges": len(mesh.edges),
        "faces": len(mesh.polygons),
        "triangles": triangle_count,
        "quads": quad_count,
        "ngons": ngon_count,
        "quad_ratio": quad_count / len(mesh.polygons) if mesh.polygons else 0.0,
        "ring_count": len(RING_XS),
        "ring_size": RING_SIZE,
        "ring_x_m": list(RING_XS),
    }


def main():
    args = parse_args()
    scene = bpy.context.scene
    body_parent = bpy.data.objects.get("BODY")
    if body_parent is None:
        raise RuntimeError("BODY root missing from accepted S1C source")
    body_material = bpy.data.materials.get("MAT_BODY_SILVER")
    if body_material is None:
        raise RuntimeError("MAT_BODY_SILVER missing")

    for name in (
        "BODY_S2_CONTROL_CAGE",
        "BODY_S2_WIREFRAME",
        "S2_CUTTER_ARCH_FRONT",
        "S2_CUTTER_ARCH_REAR",
    ):
        remove_object(name)

    references = freeze_s1c_reference()
    body = build_control_cage(body_parent, body_material)
    cutters = add_arch_modifiers(body, body_parent)
    wire = make_wireframe_copy(body, make_wire_material())

    scene["nomadhub_stage"] = "S2"
    scene["nomadhub_s2_iteration"] = "R1"
    scene["s2_status"] = "CANDIDATE_REVIEW_REQUIRED"
    scene["s2_source_stage"] = "S1C_ACCEPTED"
    scene["wheelbase_m"] = WHEELBASE_M

    camera = bpy.data.objects.get("Camera")
    if camera is None or camera.type != "CAMERA":
        raise RuntimeError("Camera missing")
    scene.camera = camera
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    output_dir = Path(args.output).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    set_wire_visibility(wire, False)
    bpy.ops.wm.save_as_mainfile(filepath=args.output, compress=True)
    Path(args.output + "1").unlink(missing_ok=True)

    render(scene, camera, args.preview, (-11.0, -10.0, 7.2), (0, 0, 1.35))
    render(scene, camera, args.left, (0, -14, 1.55), (0, 0, 1.45), 10.5)
    render(scene, camera, args.right, (0, 14, 1.55), (0, 0, 1.45), 10.5)
    render(scene, camera, args.top, (0, 0, 14), (0, 0, 0), 10.5)

    body.hide_render = True
    set_wire_visibility(wire, True)
    render(scene, camera, args.wire_left, (0, -14, 1.55), (0, 0, 1.45), 10.5)
    render(scene, camera, args.wire_right, (0, 14, 1.55), (0, 0, 1.45), 10.5)
    body.hide_render = False
    set_wire_visibility(wire, False)
    scene.frame_set(1)

    animation_mode = active_actions_merged_mode()
    export_gltf_compatible(args.roundtrip, animation_mode)
    bpy.ops.wm.save_as_mainfile(filepath=args.output, compress=True)
    Path(args.output + "1").unlink(missing_ok=True)

    source_manifest = {}
    manifest_path = Path(args.manifest)
    if manifest_path.exists():
        source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    payload = {
        "artifact_type": "genuine_blender_native_project",
        "project": "NomadHub General3",
        "version": "V1.7",
        "stage": "S2",
        "iteration": "R1",
        "stage_status": "CANDIDATE_REVIEW_REQUIRED",
        "source_stage": "S1C_ACCEPTED",
        "source_blend_sha256": source_manifest.get("blend_sha256"),
        "blender_version": bpy.app.version_string,
        "blend": args.output,
        "blend_bytes": Path(args.output).stat().st_size,
        "blend_sha256": sha256(args.output),
        "roundtrip_glb": args.roundtrip,
        "roundtrip_sha256": sha256(args.roundtrip),
        "preview": args.preview,
        "proof_images": {
            "left_orthographic": args.left,
            "right_orthographic": args.right,
            "top_orthographic": args.top,
            "left_wireframe": args.wire_left,
            "right_wireframe": args.wire_right,
        },
        "objects": len(bpy.data.objects),
        "meshes": len(bpy.data.meshes),
        "materials": len(bpy.data.materials),
        "actions": len(bpy.data.actions),
        "units": "meters",
        "body_object": body.name,
        "topology": topology_metrics(body.data),
        "modifier_types": [modifier.type for modifier in body.modifiers],
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
        "scope_note": (
            "S2-R1 creates one connected quad-dominant control cage with two cap n-gons "
            "and non-destructive wheel-arch openings. It is a technical/visual review "
            "candidate, not final S2 acceptance, Class-A surfacing, UV or final materials."
        ),
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("NOMADHUB_S2_R1_CONTROL_CAGE_OK")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
