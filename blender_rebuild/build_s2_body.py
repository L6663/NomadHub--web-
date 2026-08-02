import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


# Longitudinal control rings deliberately include the frozen S1C axle,
# wheel-arch, main-door and service-hatch boundary regions.  They are not a
# claim of final Class-A surfacing; they are the editable S2 R1 control cage.
STATIONS = (
    (-4.495, 0.78, 1.20),
    (-4.400, 0.90, 1.62),
    (-4.100, 1.08, 2.28),
    (-3.780, 1.15, 2.76),
    (-3.245, 1.15, 2.76),
    (-2.710, 1.15, 2.76),
    (-2.475, 1.15, 2.76),
    (-1.345, 1.15, 2.76),
    (-0.820, 1.15, 2.76),
    (-0.040, 1.15, 2.76),
    (0.225, 1.15, 2.76),
    (1.275, 1.15, 2.76),
    (1.370, 1.15, 2.76),
    (1.905, 1.15, 2.76),
    (2.440, 1.15, 2.76),
    (2.525, 1.15, 2.76),
    (3.575, 1.15, 2.76),
    (4.495, 1.14, 2.74),
)
RING_SIZE = 12
BASE_Z = 0.28
EXPECTED_LENGTH_M = 8.99
EXPECTED_BODY_WIDTH_M = 2.30


def parse_args():
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--roundtrip", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--preview", required=True)
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    parser.add_argument("--wire-left", required=True)
    parser.add_argument("--wire-right", required=True)
    return parser.parse_args(raw)


def remove_object(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        return
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data is not None and data.users == 0 and isinstance(data, bpy.types.Mesh):
        bpy.data.meshes.remove(data)


def ring_points(x, half_width, roof_z):
    shoulder_z = roof_z - 0.34
    upper_side_z = roof_z - 0.72
    lower_side_z = BASE_Z + 0.62
    sill_z = BASE_Z + 0.16
    return [
        (x, -0.58 * half_width, BASE_Z),
        (x, -half_width, sill_z),
        (x, -half_width, lower_side_z),
        (x, -half_width, upper_side_z),
        (x, -0.92 * half_width, shoulder_z),
        (x, -0.52 * half_width, roof_z),
        (x, 0.52 * half_width, roof_z),
        (x, 0.92 * half_width, shoulder_z),
        (x, half_width, upper_side_z),
        (x, half_width, lower_side_z),
        (x, half_width, sill_z),
        (x, 0.58 * half_width, BASE_Z),
    ]


def build_control_cage(parent, material):
    vertices = []
    for x, half_width, roof_z in STATIONS:
        vertices.extend(ring_points(x, half_width, roof_z))

    faces = []
    ring_count = len(STATIONS)
    for ring_index in range(ring_count - 1):
        current = ring_index * RING_SIZE
        nxt = (ring_index + 1) * RING_SIZE
        for point_index in range(RING_SIZE):
            point_next = (point_index + 1) % RING_SIZE
            faces.append(
                (
                    current + point_index,
                    current + point_next,
                    nxt + point_next,
                    nxt + point_index,
                )
            )

    # Two planar end caps remain n-gons in R1.  All longitudinal surface faces
    # are quads; later S2 refinement may replace the caps with quad patches.
    faces.append(tuple(range(RING_SIZE - 1, -1, -1)))
    rear_start = (ring_count - 1) * RING_SIZE
    faces.append(tuple(rear_start + index for index in range(RING_SIZE)))

    mesh = bpy.data.meshes.new("BODY_S2_CONTROL_CAGE_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=True)
    mesh.update(calc_edges=True)

    obj = bpy.data.objects.new("BODY_S2_CONTROL_CAGE", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    obj.data.materials.append(material)
    obj["nomadhub_semantic_node"] = "BODY_S2_CONTROL_CAGE"
    obj["s2_stage"] = "R1_CONTROL_CAGE"
    obj["s2_ring_count"] = ring_count
    obj["s2_ring_size"] = RING_SIZE
    obj["s2_station_x_m"] = json.dumps([station[0] for station in STATIONS])
    obj["s1c_frozen_wheelbase_m"] = 5.15
    obj["s1c_frozen_front_axle_x_m"] = -3.245
    obj["s1c_frozen_rear_axle_x_m"] = 1.905

    for polygon in mesh.polygons:
        polygon.use_smooth = True

    bevel = obj.modifiers.new("S2_Surface_Bevel", "BEVEL")
    bevel.width = 0.025
    bevel.segments = 2
    bevel.limit_method = "ANGLE"

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.select_set(False)
    return obj


def create_wire_overlay(body, material):
    wire = body.copy()
    wire.data = body.data.copy()
    wire.name = "BODY_S2_WIREFRAME"
    wire.data.name = "BODY_S2_WIREFRAME_MESH"
    bpy.context.scene.collection.objects.link(wire)
    wire.parent = body.parent
    wire.data.materials.clear()
    wire.data.materials.append(material)
    wire.modifiers.clear()
    modifier = wire.modifiers.new("S2_Wireframe", "WIREFRAME")
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
    bsdf.inputs["Base Color"].default_value = (0.008, 0.012, 0.018, 1.0)
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


def hash_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def topology_metrics(mesh):
    face_sizes = [len(polygon.vertices) for polygon in mesh.polygons]
    quad_count = sum(size == 4 for size in face_sizes)
    return {
        "vertices": len(mesh.vertices),
        "edges": len(mesh.edges),
        "faces": len(mesh.polygons),
        "quads": quad_count,
        "non_quads": len(mesh.polygons) - quad_count,
        "quad_ratio": quad_count / len(mesh.polygons) if mesh.polygons else 0.0,
        "ring_count": len(STATIONS),
        "ring_size": RING_SIZE,
        "station_x_m": [station[0] for station in STATIONS],
    }


def main():
    args = parse_args()
    scene = bpy.context.scene
    body_parent = bpy.data.objects.get("BODY")
    if body_parent is None:
        raise RuntimeError("BODY parent missing from accepted S1C source")
    body_material = bpy.data.materials.get("MAT_BODY_SILVER")
    if body_material is None:
        raise RuntimeError("MAT_BODY_SILVER missing")

    remove_object("BODY_MAIN")
    remove_object("BODY_CAB")
    remove_object("BODY_S2_CONTROL_CAGE")
    remove_object("BODY_S2_WIREFRAME")

    body = build_control_cage(body_parent, body_material)
    wire = create_wire_overlay(body, make_wire_material())

    camera = bpy.data.objects.get("Camera")
    if camera is None or camera.type != "CAMERA":
        raise RuntimeError("Camera missing")

    scene["nomadhub_stage"] = "S2"
    scene["nomadhub_s2_iteration"] = "R1"
    scene["s2_status"] = "CANDIDATE_REVIEW_REQUIRED"
    scene["s2_source_stage"] = "S1C_ACCEPTED"

    output_dir = Path(args.output).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    set_wire_visibility(wire, False)
    bpy.ops.wm.save_as_mainfile(filepath=args.output, compress=True)

    render(scene, camera, args.preview, (-11.5, -10.5, 7.0), (0, 0, 1.42))
    render(scene, camera, args.left, (0, -14, 1.55), (0, 0, 1.45), 6.3)
    render(scene, camera, args.right, (0, 14, 1.55), (0, 0, 1.45), 6.3)

    set_wire_visibility(wire, True)
    render(scene, camera, args.wire_left, (0, -14, 1.55), (0, 0, 1.45), 6.3)
    render(scene, camera, args.wire_right, (0, 14, 1.55), (0, 0, 1.45), 6.3)
    set_wire_visibility(wire, False)

    bpy.ops.export_scene.gltf(
        filepath=args.roundtrip,
        export_format="GLB",
        export_animations=True,
        export_apply=True,
        export_extras=True,
        use_visible=True,
    )
    bpy.ops.wm.save_as_mainfile(filepath=args.output, compress=True)

    base_manifest = {}
    manifest_path = Path(args.manifest)
    if manifest_path.exists():
        base_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    metrics = topology_metrics(body.data)
    payload = {
        "artifact_type": "genuine_blender_native_project",
        "stage": "S2",
        "iteration": "R1",
        "stage_status": "CANDIDATE_REVIEW_REQUIRED",
        "source_stage": "S1C_ACCEPTED",
        "source_blend_sha256": base_manifest.get("blend_sha256"),
        "blender_version": bpy.app.version_string,
        "blend": args.output,
        "blend_bytes": Path(args.output).stat().st_size,
        "blend_sha256": hash_file(args.output),
        "roundtrip_glb": args.roundtrip,
        "roundtrip_sha256": hash_file(args.roundtrip),
        "preview": args.preview,
        "proof_images": {
            "left_orthographic": args.left,
            "right_orthographic": args.right,
            "left_wireframe": args.wire_left,
            "right_wireframe": args.wire_right,
        },
        "objects": len(bpy.data.objects),
        "meshes": len(bpy.data.meshes),
        "materials": len(bpy.data.materials),
        "actions": len(bpy.data.actions),
        "units": "meters",
        "body_object": body.name,
        "topology": metrics,
        "expected_length_m": EXPECTED_LENGTH_M,
        "expected_body_width_m": EXPECTED_BODY_WIDTH_M,
        "scope_note": (
            "S2 R1 creates one connected editable longitudinal body control cage "
            "with quad side surfaces aligned to S1C anchors. The two planar end caps "
            "remain n-gons and door/window openings are still represented by frozen "
            "overlay components; this is not final S2 acceptance or Class-A surfacing."
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
