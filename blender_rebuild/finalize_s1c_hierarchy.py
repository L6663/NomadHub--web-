import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


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
    parser.add_argument("--blend", required=True)
    parser.add_argument("--roundtrip", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--preview", required=True)
    parser.add_argument(
        "--skip-proofs",
        action="store_true",
        help="Skip S1C proof renders when rebuilding S1C only as an upstream source.",
    )
    return parser.parse_args(raw)


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
        raise RuntimeError(f"missing door root: {parent_name}")
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


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def render_proof(scene, camera, path, location, target, frame, ortho_scale=None):
    scene.frame_set(frame)
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
    raise RuntimeError(
        "Blender glTF exporter has no Active Actions Merged animation mode"
    )


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    args = parse_args()
    scene = bpy.context.scene
    glass_material = bpy.data.materials.get("MAT_GLASS")
    if glass_material is None:
        raise RuntimeError("MAT_GLASS missing")

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

    camera = bpy.data.objects.get("Camera")
    if camera is None or camera.type != "CAMERA":
        raise RuntimeError("Camera missing")

    output_dir = Path(args.blend).parent
    proof_images = {
        "perspective_closed": Path(args.preview),
        "left_orthographic": output_dir / "S1C_Left_Orthographic.png",
        "right_orthographic": output_dir / "S1C_Right_Orthographic.png",
        "top_orthographic": output_dir / "S1C_Top_Orthographic.png",
        "left_open": output_dir / "S1C_Left_Open.png",
        "right_open": output_dir / "S1C_Right_Open.png",
    }

    scene["s1c_door_glass_hierarchy"] = "FINALIZED"
    scene["s1c_proof_render_mode"] = "SKIPPED_FOR_UPSTREAM_SOURCE" if args.skip_proofs else "FULL"
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=args.blend, compress=True)

    if not args.skip_proofs:
        render_proof(scene, camera, proof_images["perspective_closed"], (-11, -10, 7.2), (0, 0, 1.35), 1)
        render_proof(scene, camera, proof_images["left_orthographic"], (0, -14, 1.55), (0, 0, 1.45), 1, 10.5)
        render_proof(scene, camera, proof_images["right_orthographic"], (0, 14, 1.55), (0, 0, 1.45), 1, 10.5)
        render_proof(scene, camera, proof_images["top_orthographic"], (0, 0, 14), (0, 0, 0), 1, 10.5)
        render_proof(scene, camera, proof_images["left_open"], (0, -14, 1.55), (0, 0, 1.45), 48, 10.5)
        render_proof(scene, camera, proof_images["right_open"], (0, 14, 1.55), (0, 0, 1.45), 48, 10.5)
        scene.frame_set(1)

    animation_mode = active_actions_merged_mode()
    bpy.ops.export_scene.gltf(
        filepath=args.roundtrip,
        export_format="GLB",
        export_animations=True,
        export_animation_mode=animation_mode,
        export_apply=True,
        export_extras=True,
    )
    bpy.ops.wm.save_as_mainfile(filepath=args.blend, compress=True)
    Path(args.blend + "1").unlink(missing_ok=True)

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "blend_bytes": Path(args.blend).stat().st_size,
            "blend_sha256": sha256(args.blend),
            "roundtrip_sha256": sha256(args.roundtrip),
            "objects": len(bpy.data.objects),
            "meshes": len(bpy.data.meshes),
            "materials": len(bpy.data.materials),
            "actions": len(bpy.data.actions),
            "proof_images": (
                {name: str(path) for name, path in proof_images.items()}
                if not args.skip_proofs
                else {}
            ),
            "proof_render_mode": "SKIPPED_FOR_UPSTREAM_SOURCE" if args.skip_proofs else "FULL",
            "door_glass_hierarchy": {
                name: parent_name for name, parent_name, _, _ in DOOR_GLASS
            },
            "removed_static_glass": list(STATIC_GLASS_TO_REMOVE),
            "glb_animation_export_mode": animation_mode,
            "stage_status": "CANDIDATE_PENDING_HIERARCHY_VALIDATION",
        }
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("NOMADHUB_S1C_HIERARCHY_FINALIZED")
    print(json.dumps(manifest["door_glass_hierarchy"], ensure_ascii=False))
    print(f"GLB_ANIMATION_EXPORT_MODE={animation_mode}")
    print(f"S1C_PROOF_RENDER_MODE={manifest['proof_render_mode']}")


if __name__ == "__main__":
    main()
