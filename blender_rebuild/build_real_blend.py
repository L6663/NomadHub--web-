import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


VEHICLE = {
    "overall_length_m": 8.990,
    "overall_width_m": 2.350,
    "overall_height_m": 3.050,
    "front_axle_x_m": -3.245,
    "rear_axle_x_m": 1.905,
    "wheelbase_m": 5.150,
    "front_overhang_m": 1.250,
    "rear_overhang_m": 2.590,
}
TOLERANCE_M = 0.002
MIN_WHEEL_ARCH_CLEARANCE_M = 0.080
MIN_DOOR_SEAM_CLEARANCE_M = 0.060

WHEEL_SPECS = {
    "WHEEL_FL": (-3.245, -1.06, 0.43),
    "WHEEL_FR": (-3.245, 1.06, 0.43),
    "WHEEL_RL": (1.905, -1.06, 0.43),
    "WHEEL_RR": (1.905, 1.06, 0.43),
}
ARCH_SPECS = {
    "WHEEL_ARCH_FL": (-3.245, -1),
    "WHEEL_ARCH_FR": (-3.245, 1),
    "WHEEL_ARCH_RL": (1.905, -1),
    "WHEEL_ARCH_RR": (1.905, 1),
}
# Left and right service hatches are intentionally independent.
# R2 is shifted rearward to clear the living door, while L3/R3 are shifted
# behind the revised rear wheel arch.
HATCH_SPECS = (
    ("HATCH_L_1", "L", -1.95),
    ("HATCH_L_2", "L", 0.35),
    ("HATCH_L_3", "L", 3.05),
    ("HATCH_R_1", "R", -1.95),
    ("HATCH_R_2", "R", 0.75),
    ("HATCH_R_3", "R", 3.05),
)
HATCH_WIDTH_M = 1.05
ARCH_RX_M = 0.510
ARCH_RZ_M = 0.435
ARCH_CENTER_Z_M = 0.400
ARCH_LIP_RADIUS_M = 0.025


def parse_args():
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--roundtrip", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--preview", required=True)
    parser.add_argument("--clearance", required=True)
    return parser.parse_args(raw)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for blocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for block in list(blocks):
            if block.users == 0:
                blocks.remove(block)


def make_material(name, color, metal=0.0, rough=0.5, transmission=0.0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Roughness"].default_value = rough
    if bsdf.inputs.get("Transmission Weight"):
        bsdf.inputs["Transmission Weight"].default_value = transmission
    if bsdf.inputs.get("Coat Weight"):
        bsdf.inputs["Coat Weight"].default_value = 0.35 if "BODY" in name else 0
    return material


def make_empty(name, location=(0, 0, 0), parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    obj.parent = parent
    return obj


def finish_mesh(obj, name, material, parent=None, bevel=0.0):
    obj.name = name
    obj.data.name = f"{name}_MESH"
    obj.parent = parent
    if material:
        obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    if bevel:
        modifier = obj.modifiers.new("NH_Bevel", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
        modifier.limit_method = "ANGLE"
    obj["nomadhub_semantic_node"] = name
    return obj


def make_box(name, dimensions, location, material, parent=None, rotation=(0, 0, 0), bevel=0.02):
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation)
    obj = bpy.context.object
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish_mesh(obj, name, material, parent, bevel)


def make_child_box(name, dimensions, location, material, parent, bevel=0.012):
    obj = make_box(name, dimensions, (0, 0, 0), material, None, bevel=bevel)
    obj.parent = parent
    obj.location = location
    return obj


def make_profile_prism(name, profile, width, material, parent):
    y = width / 2
    vertices = [(x, -y, z) for x, z in profile] + [(x, y, z) for x, z in profile]
    count = len(profile)
    faces = [tuple(range(count - 1, -1, -1)), tuple(range(count, 2 * count))]
    for index in range(count):
        nxt = (index + 1) % count
        faces.append((index, nxt, count + nxt, count + index))
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return finish_mesh(obj, name, material, parent, 0.025)


def make_arch_lip(name, center_x, side_sign, material, parent):
    curve = bpy.data.curves.new(f"{name}_CURVE", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = ARCH_LIP_RADIUS_M
    curve.bevel_resolution = 3
    spline = curve.splines.new("POLY")
    point_count = 33
    spline.points.add(point_count - 1)
    y = side_sign * 1.172
    for index in range(point_count):
        theta = math.pi - math.pi * index / (point_count - 1)
        x = center_x + ARCH_RX_M * math.cos(theta)
        z = ARCH_CENTER_Z_M + ARCH_RZ_M * math.sin(theta)
        spline.points[index].co = (x, y, z, 1.0)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    curve.materials.append(material)
    obj["nomadhub_semantic_node"] = name
    obj["wheel_arch_center_x_m"] = center_x
    obj["wheel_arch_opening_width_m"] = ARCH_RX_M * 2
    obj["wheel_arch_opening_height_m"] = ARCH_RZ_M * 2
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    obj.select_set(False)
    obj.name = name
    obj.data.name = f"{name}_MESH"
    return obj


def make_wheel(name, location, parent, body_material, rubber_material):
    root = make_empty(f"{name}_ROOT", location, parent)
    root["wheel_center_x_m"] = location[0]
    root["wheel_center_y_m"] = location[1]
    root["wheel_center_z_m"] = location[2]
    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.31,
        minor_radius=0.105,
        major_segments=32,
        minor_segments=12,
        rotation=(math.pi / 2, 0, 0),
    )
    tire = finish_mesh(bpy.context.object, f"{name}_TIRE", rubber_material, root, 0.005)
    tire.location = (0, 0, 0)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=24,
        radius=0.245,
        depth=0.12,
        rotation=(math.pi / 2, 0, 0),
    )
    rim = finish_mesh(bpy.context.object, f"{name}_RIM", body_material, root, 0.004)
    rim.location = (0, 0, 0)
    return root


def animate_rotation(root, axis, angle):
    root.rotation_mode = "XYZ"
    for frame, value in ((1, 0), (48, angle), (96, 0)):
        root.rotation_euler[axis] = value
        root.keyframe_insert("rotation_euler", index=axis, frame=frame)


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


def interval_distance(a_min, a_max, b_min, b_max):
    if a_max < b_min:
        return b_min - a_max
    if b_max < a_min:
        return a_min - b_max
    return -min(a_max, b_max) + max(a_min, b_min)


def compute_s1c_clearance():
    front_arch = (
        VEHICLE["front_axle_x_m"] - ARCH_RX_M - ARCH_LIP_RADIUS_M,
        VEHICLE["front_axle_x_m"] + ARCH_RX_M + ARCH_LIP_RADIUS_M,
    )
    rear_arch = (
        VEHICLE["rear_axle_x_m"] - ARCH_RX_M - ARCH_LIP_RADIUS_M,
        VEHICLE["rear_axle_x_m"] + ARCH_RX_M + ARCH_LIP_RADIUS_M,
    )
    door_intervals = {
        "L": (("DOOR_DRIVER_L", -4.40, -3.88),),
        "R": (
            ("DOOR_PASSENGER_R", -4.40, -3.88),
            ("DOOR_LIVING_R", -0.82, -0.04),
        ),
    }
    entries = []
    for name, side, center_x in HATCH_SPECS:
        hatch_min = center_x - HATCH_WIDTH_M / 2
        hatch_max = center_x + HATCH_WIDTH_M / 2
        arch_gaps = {
            "front": interval_distance(hatch_min, hatch_max, *front_arch),
            "rear": interval_distance(hatch_min, hatch_max, *rear_arch),
        }
        nearest_arch_name = min(arch_gaps, key=arch_gaps.get)
        nearest_arch_gap = arch_gaps[nearest_arch_name]
        door_gaps = {
            door_name: interval_distance(hatch_min, hatch_max, door_min, door_max)
            for door_name, door_min, door_max in door_intervals[side]
        }
        nearest_door_name = min(door_gaps, key=door_gaps.get)
        nearest_door_gap = door_gaps[nearest_door_name]
        entry = {
            "name": name,
            "side": side,
            "center_x_m": round(center_x, 6),
            "x_min_m": round(hatch_min, 6),
            "x_max_m": round(hatch_max, 6),
            "nearest_wheel_arch": nearest_arch_name,
            "wheel_arch_clearance_m": round(nearest_arch_gap, 6),
            "nearest_door": nearest_door_name,
            "door_seam_clearance_m": round(nearest_door_gap, 6),
            "wheel_arch_pass": nearest_arch_gap >= MIN_WHEEL_ARCH_CLEARANCE_M,
            "door_seam_pass": nearest_door_gap >= MIN_DOOR_SEAM_CLEARANCE_M,
            "overlap": nearest_arch_gap < 0 or nearest_door_gap < 0,
        }
        entries.append(entry)
    wheelbase_actual = WHEEL_SPECS["WHEEL_RL"][0] - WHEEL_SPECS["WHEEL_FL"][0]
    result = (
        abs(wheelbase_actual - VEHICLE["wheelbase_m"]) <= TOLERANCE_M
        and all(item["wheel_arch_pass"] and item["door_seam_pass"] and not item["overlap"] for item in entries)
    )
    return {
        "schema": "nomadhub-s1c-clearance-v1",
        "stage": "S1C",
        "vehicle": VEHICLE,
        "tolerance_m": TOLERANCE_M,
        "minimum_wheel_arch_clearance_m": MIN_WHEEL_ARCH_CLEARANCE_M,
        "minimum_door_seam_clearance_m": MIN_DOOR_SEAM_CLEARANCE_M,
        "wheelbase_actual_m": round(wheelbase_actual, 6),
        "wheel_arch_outer_intervals_m": {
            "front": [round(front_arch[0], 6), round(front_arch[1], 6)],
            "rear": [round(rear_arch[0], 6), round(rear_arch[1], 6)],
        },
        "service_hatches": entries,
        "result": "PASS" if result else "FAIL",
        "next_stage": "S2" if result else None,
    }


def main():
    arguments = parse_args()
    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.unit_settings.scale_length = 1
    scene.frame_start = 1
    scene.frame_end = 120
    scene.render.fps = 30

    silver = make_material("MAT_BODY_SILVER", (0.72, 0.76, 0.80), 0.18, 0.25)
    dark = make_material("MAT_TRIM", (0.04, 0.05, 0.06), 0.05, 0.32)
    glass = make_material("MAT_GLASS", (0.025, 0.07, 0.11), 0, 0.12, 0.65)
    rubber = make_material("MAT_RUBBER", (0.015, 0.018, 0.02), 0, 0.86)
    cyan = make_material("MAT_ACCENT_CYAN", (0, 0.58, 0.65), 0.1, 0.28)
    red = make_material("MAT_TAILLIGHT", (0.55, 0.02, 0.01), 0.05, 0.25)

    root = make_empty("RV_ROOT")
    body = make_empty("BODY", parent=root)
    glass_group = make_empty("GLASS", parent=root)
    doors = make_empty("DOORS", parent=root)
    hatches = make_empty("HATCHES", parent=root)
    wheels = make_empty("WHEELS", parent=root)
    roof = make_empty("ROOF", parent=root)
    lights = make_empty("LIGHTS", parent=root)
    make_empty("MIRRORS", parent=root)

    make_box("BODY_MAIN", (7.05, 2.30, 2.35), (0.80, 0, 1.48), silver, body, bevel=0.06)
    profile = [
        (-4.43, 0.35),
        (-4.38, 1.15),
        (-4.08, 2.20),
        (-3.62, 2.76),
        (-2.60, 2.76),
        (-2.60, 0.35),
    ]
    make_profile_prism("BODY_CAB", profile, 2.26, silver, body)
    make_box("FRONT_BUMPER", (0.16, 1.78, 0.23), (-4.46, 0, 0.44), dark, body, bevel=0.06)
    make_box("REAR_BUMPER", (0.16, 1.82, 0.23), (4.43, 0, 0.44), dark, body, bevel=0.06)

    skirt_segments = (
        ("FRONT", -4.25, -3.81),
        ("MID", -2.68, 1.34),
        ("REAR", 2.47, 4.00),
    )
    for side_sign, suffix in ((-1, "L"), (1, "R")):
        for segment_name, x_min, x_max in skirt_segments:
            make_box(
                f"SIDE_SKIRT_{suffix}_{segment_name}",
                (x_max - x_min, 0.10, 0.10),
                ((x_min + x_max) / 2, side_sign * 1.15, 0.245),
                dark,
                body,
                bevel=0.025,
            )

    for arch_name, (center_x, side_sign) in ARCH_SPECS.items():
        make_arch_lip(arch_name, center_x, side_sign, dark, body)

    make_box(
        "GLASS_WINDSHIELD",
        (0.055, 1.92, 0.88),
        (-4.09, 0, 2.18),
        glass,
        glass_group,
        rotation=(0, -math.radians(17), 0),
        bevel=0.035,
    )
    for side, suffix in ((-1, "L"), (1, "R")):
        make_box(f"GLASS_CAB_{suffix}", (1.0, 0.035, 0.72), (-3.48, side * 1.145, 2.02), glass, glass_group, bevel=0.04)
        for index, (x, width) in enumerate(((-1.75, 1.05), (-0.35, 1.05), (1.45, 1.30), (3.10, 0.90)), 1):
            make_box(
                f"GLASS_LIVING_{suffix}_{index:02}",
                (width, 0.035, 0.68),
                (x, side * 1.165, 2.08),
                glass,
                glass_group,
                bevel=0.045,
            )
    make_box("GLASS_REAR", (0.035, 1.35, 0.65), (4.47, 0, 1.98), glass, glass_group, bevel=0.04)

    door_specs = [
        ("DOOR_DRIVER_L_ROOT", (-4.40, -1.18, 0.45), (0.52, 0.05, 1.72), (0.26, 0, 0.86), -68),
        ("DOOR_PASSENGER_R_ROOT", (-4.40, 1.18, 0.45), (0.52, 0.05, 1.72), (0.26, 0, 0.86), 68),
        ("DOOR_LIVING_R_ROOT", (-0.82, 1.18, 0.34), (0.78, 0.05, 1.96), (0.39, 0, 0.98), 82),
    ]
    door_roots = {}
    for name, location, dimensions, local_location, degrees in door_specs:
        door_root = make_empty(name, location, doors)
        door_roots[name] = door_root
        make_child_box(name.replace("_ROOT", ""), dimensions, local_location, silver, door_root)
        animate_rotation(door_root, 2, math.radians(degrees))

    for name, side, center_x in HATCH_SPECS:
        side_sign = -1 if side == "L" else 1
        hatch_root = make_empty(f"{name}_ROOT", (center_x, side_sign * 1.18, 0.92), hatches)
        hatch_root["service_hatch_side"] = side
        hatch_root["service_hatch_center_x_m"] = center_x
        hatch_root["service_hatch_width_m"] = HATCH_WIDTH_M
        make_child_box(name, (HATCH_WIDTH_M, 0.045, 0.55), (0, 0, -0.275), silver, hatch_root)
        animate_rotation(hatch_root, 0, math.radians(70 * side_sign))

    for name, location in WHEEL_SPECS.items():
        wheel_root = make_wheel(name, location, wheels, silver, rubber)
        wheel_root.rotation_mode = "XYZ"
        wheel_root.rotation_euler[1] = 0
        wheel_root.keyframe_insert("rotation_euler", index=1, frame=1)
        wheel_root.rotation_euler[1] = math.radians(720)
        wheel_root.keyframe_insert("rotation_euler", index=1, frame=120)

    make_box("ROOF_AC", (0.95, 0.78, 0.24), (-2.05, 0, 2.91), silver, roof, bevel=0.08)
    make_box("SOLAR_ARRAY", (2.45, 1.55, 0.06), (0.05, 0, 2.82), dark, roof, bevel=0.01)
    make_box("ROOF_SKYLIGHT", (0.65, 0.55, 0.10), (1.70, 0, 2.86), glass, roof, bevel=0.04)
    make_box("AWNING_R", (4.7, 0.14, 0.16), (0.40, 1.18, 2.68), dark, roof, bevel=0.05)
    make_box("FRONT_GRILLE", (0.045, 1.28, 0.52), (-4.49, 0, 0.92), dark, lights, bevel=0.05)
    for y in (-0.73, 0.73):
        make_box("HEADLIGHT_" + ("L" if y < 0 else "R"), (0.05, 0.36, 0.20), (-4.50, y, 1.30), cyan, lights, bevel=0.06)
    for y in (-0.78, 0.78):
        make_box("TAILLIGHT_" + ("L" if y < 0 else "R"), (0.05, 0.22, 0.60), (4.50, y, 1.18), red, lights, bevel=0.05)

    for side, suffix, door_name in (
        (-1, "L", "DOOR_DRIVER_L_ROOT"),
        (1, "R", "DOOR_PASSENGER_R_ROOT"),
    ):
        mirror_root = make_empty(f"MIRROR_{suffix}_ROOT", (0.20, 0, 1.37), door_roots[door_name])
        make_child_box(f"MIRROR_{suffix}_HOUSING", (0.25, 0.23, 0.30), (-0.10, side * 0.19, 0.02), silver, mirror_root, 0.04)
        make_child_box(f"MIRROR_{suffix}_GLASS", (0.12, 0.025, 0.20), (-0.13, side * 0.31, 0.02), glass, mirror_root, 0.02)
    make_box("ACCENT_L", (4.8, 0.018, 0.07), (0.35, -1.185, 1.15), cyan, body, rotation=(0, math.radians(-2), 0), bevel=0.01)
    make_box("ACCENT_R", (4.8, 0.018, 0.07), (0.35, 1.185, 1.15), cyan, body, rotation=(0, math.radians(-2), 0), bevel=0.01)

    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (-11, -10, 7.2)
    look_at(camera, (0, 0, 1.35))
    camera.data.lens = 55

    for name, location, energy, size in (
        ("Key", (-5, -6, 9), 1800, 5),
        ("Fill", (4, -2, 6), 1100, 4),
        ("Rim", (2, 7, 8), 1300, 4),
    ):
        light_data = bpy.data.lights.new(name, "AREA")
        light_data.energy = energy
        light_data.shape = "DISK"
        light_data.size = size
        light = bpy.data.objects.new(name, light_data)
        scene.collection.objects.link(light)
        light.location = location
        look_at(light, (0, 0, 1.3))

    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = arguments.preview
    scene.world.color = (0.035, 0.045, 0.06)
    scene["nomadhub_project"] = "NomadHub General3"
    scene["nomadhub_version"] = "V1.7"
    scene["build_type"] = "BLENDER_NATIVE_S1C_REPAIR"
    scene["s1c_stage_status"] = "CANDIDATE_PENDING_ROUNDTRIP_VALIDATION"
    scene["wheelbase_m"] = VEHICLE["wheelbase_m"]

    clearance = compute_s1c_clearance()
    if clearance["result"] != "PASS":
        raise RuntimeError(f"S1C static clearance gate failed: {json.dumps(clearance, ensure_ascii=False)}")

    output_dir = Path(arguments.output).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    Path(arguments.clearance).write_text(json.dumps(clearance, ensure_ascii=False, indent=2), encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=arguments.output, compress=True)

    proof_images = {
        "perspective_closed": Path(arguments.preview),
        "left_orthographic": output_dir / "S1C_Left_Orthographic.png",
        "right_orthographic": output_dir / "S1C_Right_Orthographic.png",
        "top_orthographic": output_dir / "S1C_Top_Orthographic.png",
        "left_open": output_dir / "S1C_Left_Open.png",
        "right_open": output_dir / "S1C_Right_Open.png",
    }
    render_proof(scene, camera, proof_images["perspective_closed"], (-11, -10, 7.2), (0, 0, 1.35), 1)
    render_proof(scene, camera, proof_images["left_orthographic"], (0, -14, 1.55), (0, 0, 1.45), 1, 5.5)
    render_proof(scene, camera, proof_images["right_orthographic"], (0, 14, 1.55), (0, 0, 1.45), 1, 5.5)
    render_proof(scene, camera, proof_images["top_orthographic"], (0, 0, 14), (0, 0, 0), 1, 5.5)
    render_proof(scene, camera, proof_images["left_open"], (0, -14, 1.55), (0, 0, 1.45), 48, 5.5)
    render_proof(scene, camera, proof_images["right_open"], (0, 14, 1.55), (0, 0, 1.45), 48, 5.5)
    scene.frame_set(1)

    bpy.ops.export_scene.gltf(
        filepath=arguments.roundtrip,
        export_format="GLB",
        export_animations=True,
        export_apply=True,
        export_extras=True,
    )
    bpy.ops.wm.save_as_mainfile(filepath=arguments.output, compress=True)

    payload = {
        "artifact_type": "genuine_blender_native_project",
        "stage": "S1C",
        "stage_status": "CANDIDATE_PENDING_ROUNDTRIP_VALIDATION",
        "blender_version": bpy.app.version_string,
        "blend": arguments.output,
        "blend_bytes": Path(arguments.output).stat().st_size,
        "blend_sha256": hashlib.sha256(Path(arguments.output).read_bytes()).hexdigest(),
        "roundtrip_glb": arguments.roundtrip,
        "roundtrip_sha256": hashlib.sha256(Path(arguments.roundtrip).read_bytes()).hexdigest(),
        "preview": arguments.preview,
        "proof_images": {name: str(path) for name, path in proof_images.items()},
        "clearance_report": arguments.clearance,
        "objects": len(bpy.data.objects),
        "meshes": len(bpy.data.meshes),
        "materials": len(bpy.data.materials),
        "actions": len(bpy.data.actions),
        "units": "meters",
        "wheelbase_m": VEHICLE["wheelbase_m"],
        "front_axle_x_m": VEHICLE["front_axle_x_m"],
        "rear_axle_x_m": VEHICLE["rear_axle_x_m"],
        "service_hatch_centers_x_m": {name: center_x for name, _, center_x in HATCH_SPECS},
        "scope_note": (
            "Genuine Blender-saved S1C structural repair candidate with revised axle, "
            "wheel-arch and service-hatch coordinates. S2 remains blocked until the "
            "independent Blender/GLB round-trip validator passes."
        ),
    }
    Path(arguments.manifest).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("NOMADHUB_NATIVE_BLEND_S1C_CANDIDATE_OK")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
