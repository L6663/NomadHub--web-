import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--roundtrip", required=True)
    parser.add_argument("--manifest", required=True)
    return parser.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def find_object(name):
    return bpy.data.objects.get(name)


def set_principled_value(material, names, value):
    if not material or not material.use_nodes:
        return False
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if not bsdf:
        return False
    for name in names:
        socket = bsdf.inputs.get(name)
        if socket is not None:
            socket.default_value = value
            return True
    return False


def prepare_materials():
    for material in bpy.data.materials:
        material.use_nodes = True
        name = material.name.upper()
        if "GLASS" in name:
            set_principled_value(material, ["Roughness"], 0.12)
            set_principled_value(material, ["Transmission Weight", "Transmission"], 0.65)
            set_principled_value(material, ["IOR"], 1.45)
        elif "BODY" in name:
            set_principled_value(material, ["Metallic"], 0.18)
            set_principled_value(material, ["Roughness"], 0.28)
            set_principled_value(material, ["Coat Weight", "Clearcoat"], 0.35)
            set_principled_value(material, ["Coat Roughness", "Clearcoat Roughness"], 0.10)
        elif "RUBBER" in name:
            set_principled_value(material, ["Roughness"], 0.82)
        elif "CHROME" in name:
            set_principled_value(material, ["Metallic"], 0.95)
            set_principled_value(material, ["Roughness"], 0.18)


def prepare_meshes():
    modifier_summary = {}
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
        obj["nomadhub_semantic_node"] = obj.name
        obj["nomadhub_source"] = "S3_R3_GLTF_IMPORT"
        if obj.name == "BODY_SHELL":
            bevel = obj.modifiers.new(name="NH_Body_Bevel", type="BEVEL")
            bevel.width = 0.006
            bevel.segments = 2
            bevel.limit_method = "ANGLE"
            solidify = obj.modifiers.new(name="NH_Body_Thickness", type="SOLIDIFY")
            solidify.thickness = 0.012
            solidify.offset = -1.0
        elif obj.name.startswith("GLASS_"):
            solidify = obj.modifiers.new(name="NH_Glass_Thickness", type="SOLIDIFY")
            solidify.thickness = 0.004
            solidify.offset = 0.0
        elif (
            obj.name.startswith("DOOR_")
            or obj.name.startswith("HATCH_")
            or "BUMPER" in obj.name
            or "MIRROR" in obj.name
        ):
            bevel = obj.modifiers.new(name="NH_Edge_Bevel", type="BEVEL")
            bevel.width = 0.003
            bevel.segments = 2
            bevel.limit_method = "ANGLE"
        if obj.modifiers:
            modifier_summary[obj.name] = [modifier.type for modifier in obj.modifiers]
    return modifier_summary


def keyframe_rotation(obj, frame, axis_index, value):
    obj.rotation_mode = "XYZ"
    obj.rotation_euler[axis_index] = value
    obj.keyframe_insert(data_path="rotation_euler", index=axis_index, frame=frame)


def keyframe_location(obj, frame, axis_index, value):
    obj.location[axis_index] = value
    obj.keyframe_insert(data_path="location", index=axis_index, frame=frame)


def create_animation():
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 120
    scene.render.fps = 30
    door_specs = {
        "DOOR_DRIVER_L_ROOT": (2, math.radians(-68)),
        "DOOR_PASSENGER_R_ROOT": (2, math.radians(68)),
        "DOOR_LIVING_R_ROOT": (2, math.radians(82)),
    }
    hatch_specs = {
        "HATCH_L_A_ROOT": (0, math.radians(-72)),
        "HATCH_L_B_ROOT": (0, math.radians(-72)),
        "HATCH_L_C_ROOT": (0, math.radians(-72)),
        "HATCH_R_A_ROOT": (0, math.radians(72)),
        "HATCH_R_B_ROOT": (0, math.radians(72)),
        "HATCH_R_C_ROOT": (0, math.radians(72)),
    }
    animated = []
    for name, (axis, angle) in {**door_specs, **hatch_specs}.items():
        obj = find_object(name)
        if not obj:
            continue
        keyframe_rotation(obj, 1, axis, 0.0)
        keyframe_rotation(obj, 48, axis, angle)
        keyframe_rotation(obj, 96, axis, 0.0)
        animated.append(name)
    step = find_object("STEP_LIVING_R_ROOT")
    if step:
        initial = step.location.y
        keyframe_location(step, 1, 1, initial)
        keyframe_location(step, 48, 1, initial + 0.22)
        keyframe_location(step, 96, 1, initial)
        animated.append(step.name)
    for name in ("WHEEL_FL_ROOT", "WHEEL_FR_ROOT", "WHEEL_RL_ROOT", "WHEEL_RR_ROOT"):
        obj = find_object(name)
        if not obj:
            continue
        keyframe_rotation(obj, 1, 1, 0.0)
        keyframe_rotation(obj, 120, 1, math.radians(720))
        animated.append(name)
    for action in bpy.data.actions:
        action["nomadhub_generated_action"] = True
    return sorted(set(animated))


def create_collections_and_metadata(source_sha):
    scene = bpy.context.scene
    scene["nomadhub_project"] = "NomadHub General3"
    scene["nomadhub_version"] = "V1.7"
    scene["nomadhub_stage"] = "REAL_BLEND_REBUILD"
    scene["nomadhub_source_glb_sha256"] = source_sha
    scene["nomadhub_blender_version"] = bpy.app.version_string
    scene["nomadhub_units"] = "meters"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.unit_settings.scale_length = 1.0
    manifest_collection = bpy.data.collections.get("NOMADHUB_PROJECT_METADATA")
    if manifest_collection is None:
        manifest_collection = bpy.data.collections.new("NOMADHUB_PROJECT_METADATA")
        scene.collection.children.link(manifest_collection)
    marker = bpy.data.objects.new("NOMADHUB_BUILD_MANIFEST", None)
    marker.empty_display_type = "PLAIN_AXES"
    marker["generated_by"] = "Blender Python API"
    marker["source_sha256"] = source_sha
    marker["blender_version"] = bpy.app.version_string
    marker["warning"] = "Imported S3 R3 geometry with Blender-native modifiers and actions."
    manifest_collection.objects.link(marker)


def save_project(output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path), compress=True)


def export_roundtrip(output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(output_path),
        export_format="GLB",
        export_apply=True,
        export_animations=True,
        export_yup=True,
    )


def write_manifest(path, source_path, output_path, roundtrip_path, modifier_summary, animated):
    object_types = {}
    for obj in bpy.data.objects:
        object_types[obj.type] = object_types.get(obj.type, 0) + 1
    payload = {
        "project": "NomadHub General3",
        "version": "V1.7",
        "artifact_type": "genuine_blender_project",
        "blender_version": bpy.app.version_string,
        "source_glb": str(source_path),
        "source_glb_sha256": hashlib.sha256(Path(source_path).read_bytes()).hexdigest(),
        "blend_file": str(output_path),
        "blend_bytes": Path(output_path).stat().st_size,
        "blend_sha256": hashlib.sha256(Path(output_path).read_bytes()).hexdigest(),
        "roundtrip_glb": str(roundtrip_path),
        "roundtrip_glb_bytes": Path(roundtrip_path).stat().st_size,
        "roundtrip_glb_sha256": hashlib.sha256(Path(roundtrip_path).read_bytes()).hexdigest(),
        "objects": len(bpy.data.objects),
        "object_types": object_types,
        "meshes": len(bpy.data.meshes),
        "materials": len(bpy.data.materials),
        "actions": len(bpy.data.actions),
        "animated_roots": animated,
        "modifier_objects": modifier_summary,
        "scene_units": {
            "system": bpy.context.scene.unit_settings.system,
            "length_unit": bpy.context.scene.unit_settings.length_unit,
            "scale_length": bpy.context.scene.unit_settings.scale_length,
        },
        "scope_note": (
            "This is a real Blender .blend saved by Blender itself. "
            "Its geometry originates from the S3 R3 GLB and remains a rebuild/import baseline, "
            "not a claim of hand-authored production topology."
        ),
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    source_path = Path(args.input)
    output_path = Path(args.output)
    roundtrip_path = Path(args.roundtrip)
    manifest_path = Path(args.manifest)
    source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(source_path), import_pack_images=True)
    prepare_materials()
    modifier_summary = prepare_meshes()
    animated = create_animation()
    create_collections_and_metadata(source_sha)
    save_project(output_path)
    export_roundtrip(roundtrip_path)
    save_project(output_path)
    write_manifest(manifest_path, source_path, output_path, roundtrip_path, modifier_summary, animated)
    print("NOMADHUB_BLEND_BUILD_OK")
    print(json.dumps({
        "blend": str(output_path),
        "roundtrip": str(roundtrip_path),
        "manifest": str(manifest_path),
        "blender_version": bpy.app.version_string,
        "objects": len(bpy.data.objects),
        "actions": len(bpy.data.actions),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
