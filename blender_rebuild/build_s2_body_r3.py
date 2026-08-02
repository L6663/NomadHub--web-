"""S2-R3 local curvature and opening-frame repair.

R3 preserves the frozen Web/animation contract from R2 while repairing the
visible defects found in the six-view review:

- smooth wheel-well influence instead of an abrupt side-to-floor transition;
- fewer global longitudinal rings while retaining every required opening ring;
- tapered cab-door panels that follow the closed cab side surface;
- inset glass, doors and hatch covers with visible body-fixed frame gaps;
- narrower windshield opening, embedded glazing and explicit A-pillar/header
  framing;
- integrated body-colour wheel lips instead of floating black arch strips;
- additional front, wheel and zebra-stripe curvature evidence renders.
"""

import importlib.util
import json
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector


SCRIPT_DIR = Path(__file__).resolve().parent
CLEARANCE_PATH = SCRIPT_DIR / "build_s2_body_r2_clearance.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r2_clearance", CLEARANCE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R2 clearance builder: {CLEARANCE_PATH}")
clearance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(clearance)
entry = clearance.entry
builder = clearance.builder

R3_CORE_ARCH_RADIUS_M = 0.600
R3_OUTER_BLEND_RADIUS_M = 0.760
R3_WELL_HALF_WIDTH_M = 0.545
R3_CLEARANCE_RADIUS_M = 0.545
R3_CLEARANCE_BLEND_RADIUS_M = 0.680
R3_TIRE_CENTER_Z_M = 0.430
R3_CLEARANCE_MARGIN_M = 0.030
R3_FRAME_DEPTH_M = 0.018

# Reduce the windshield span so a stable A-pillar remains on both sides.
entry.WINDSHIELD_OPENING.update(
    {
        "x_min_m": -4.285,
        "x_max_m": -3.900,
        "y_min_m": -0.820,
        "y_max_m": 0.820,
        "z_center_m": 2.500,
    }
)


def smoothstep(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def nearest_axle_dx(x):
    return min(abs(x - center) for center in (builder.FRONT_AXLE_X_M, builder.REAR_AXLE_X_M))


def arch_influence(x):
    dx = nearest_axle_dx(x)
    if dx <= R3_CORE_ARCH_RADIUS_M:
        return 1.0
    if dx >= R3_OUTER_BLEND_RADIUS_M:
        return 0.0
    return 1.0 - smoothstep(
        (dx - R3_CORE_ARCH_RADIUS_M)
        / (R3_OUTER_BLEND_RADIUS_M - R3_CORE_ARCH_RADIUS_M)
    )


def clearance_influence(x):
    dx = nearest_axle_dx(x)
    if dx <= R3_CLEARANCE_RADIUS_M:
        return 1.0
    if dx >= R3_CLEARANCE_BLEND_RADIUS_M:
        return 0.0
    return 1.0 - smoothstep(
        (dx - R3_CLEARANCE_RADIUS_M)
        / (R3_CLEARANCE_BLEND_RADIUS_M - R3_CLEARANCE_RADIUS_M)
    )


def r3_ring_xs():
    values = {
        -4.495,
        -4.430,
        -4.300,
        -4.080,
        -3.900,
        -3.880,
        0.000,
        4.350,
        4.495,
    }
    for opening in entry.SIDE_OPENINGS:
        x_min = opening["x_min_m"]
        x_max = opening["x_max_m"]
        center = (x_min + x_max) / 2.0
        for value in (x_min, x_min + 0.040, center, x_max - 0.040, x_max):
            values.add(round(value, 3))
    windshield = entry.WINDSHIELD_OPENING
    wx_min = windshield["x_min_m"]
    wx_max = windshield["x_max_m"]
    for value in (
        wx_min,
        wx_min + 0.040,
        (wx_min + wx_max) / 2.0,
        wx_max - 0.040,
        wx_max,
    ):
        values.add(round(value, 3))
    for center in (builder.FRONT_AXLE_X_M, builder.REAR_AXLE_X_M):
        for offset in (
            -0.760,
            -0.680,
            -0.600,
            -0.545,
            -0.400,
            -0.200,
            0.000,
            0.200,
            0.400,
            0.545,
            0.600,
            0.680,
            0.760,
        ):
            value = center + offset
            if -4.495 < value < 4.495:
                values.add(round(value, 3))
    return tuple(sorted(values))


builder.RING_XS = r3_ring_xs()


def r3_grid_boundary_points(x, width, z_low, z_top):
    half = width / 2.0
    lower_corner = min(0.120, half * 0.12)
    roof_corner = min(0.180, half * 0.18)
    levels = list(builder.remapped_z_levels(z_low, z_top))

    arch_weight = arch_influence(x)
    clear_weight = clearance_influence(x)
    dx = nearest_axle_dx(x)

    normal_left = -half + lower_corner
    normal_right = half - lower_corner
    bottom_left = normal_left + (-R3_WELL_HALF_WIDTH_M - normal_left) * arch_weight
    bottom_right = normal_right + (R3_WELL_HALF_WIDTH_M - normal_right) * arch_weight

    floor_target = z_low
    if dx <= R3_CLEARANCE_RADIUS_M:
        floor_target = R3_TIRE_CENTER_Z_M + math.sqrt(
            max(0.0, R3_CLEARANCE_RADIUS_M ** 2 - dx ** 2)
        ) + R3_CLEARANCE_MARGIN_M
    floor_z = z_low + (max(z_low, floor_target) - z_low) * clear_weight

    if arch_weight > 0.0:
        circle_dx = min(dx, R3_CORE_ARCH_RADIUS_M)
        crown = builder.ARCH_CENTER_Z_M + math.sqrt(
            max(0.0, R3_CORE_ARCH_RADIUS_M ** 2 - circle_dx ** 2)
        )
        base_first = levels[1]
        blended_crown = base_first + (crown + 0.045 - base_first) * arch_weight
        levels[1] = max(levels[1], blended_crown, floor_z + 0.055 * arch_weight)
        levels[2] = max(levels[2], levels[1] + 0.055 * arch_weight)
        levels[3] = max(levels[3], levels[2] + 0.050 * arch_weight)
        for index in range(4, len(levels)):
            levels[index] = max(levels[index], levels[index - 1] + 0.012)
        levels[-1] = z_top
        for index in range(len(levels) - 2, 0, -1):
            levels[index] = min(levels[index], levels[index + 1] - 0.012)

    points = []
    for index in range(builder.GRID_N):
        factor = index / (builder.GRID_N - 1)
        y = bottom_left + (bottom_right - bottom_left) * factor
        points.append((x, y, floor_z))

    for index in range(1, builder.GRID_N):
        z = levels[index]
        y = half
        if index == builder.GRID_N - 1:
            y = half - roof_corner
        points.append((x, y, z))

    roof_right = half - roof_corner
    roof_left = -half + roof_corner
    for index in range(builder.GRID_N - 2, -1, -1):
        factor = index / (builder.GRID_N - 1)
        y = roof_left + (roof_right - roof_left) * factor
        points.append((x, y, z_top))

    for index in range(builder.GRID_N - 2, 0, -1):
        points.append((x, -half, levels[index]))

    if len(points) != builder.RING_SIZE:
        raise RuntimeError(f"R3 ring size {len(points)} != {builder.RING_SIZE}")
    return points


builder.grid_boundary_points = r3_grid_boundary_points


def remove_object(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        return
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data is not None and data.users == 0 and isinstance(data, bpy.types.Mesh):
        bpy.data.meshes.remove(data)


def make_box(name, dimensions, location, material, parent=None, rotation=(0.0, 0.0, 0.0), bevel=0.004):
    remove_object(name)
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}_MESH"
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler = rotation
    obj.parent = parent
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    if bevel > 0.0:
        modifier = obj.modifiers.new("R3_Frame_Bevel", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
        modifier.limit_method = "ANGLE"
    obj["nomadhub_semantic_node"] = name
    obj["s2_r3_visual_frame"] = True
    return obj


def replace_cab_door_panel(name, side_sign):
    obj = bpy.data.objects.get(name)
    if obj is None or obj.parent is None:
        raise RuntimeError(f"missing cab door panel: {name}")
    root = obj.parent
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
    vertices = [tuple(inverse @ point) for point in world_outer + world_inner]
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
    obj.location = (0.0, 0.0, 0.0)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)
    body_material = bpy.data.materials.get("MAT_BODY_SILVER")
    if body_material is not None:
        mesh.materials.append(body_material)
    if old_mesh is not None and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    obj["s2_r3_tapered_cab_panel"] = True


def side_surface_y(x, side_sign):
    return side_sign * builder.section_dimensions(x)[0] / 2.0


def make_side_frame(opening, body_root, material):
    name = opening["name"]
    side_sign = -1.0 if opening["side"] == "L" else 1.0
    x_min = opening["x_min_m"]
    x_max = opening["x_max_m"]
    z_min = opening["z_min_m"]
    z_max = opening["z_max_m"]
    if name.startswith("WINDOW"):
        border = 0.034
    elif name.startswith("HATCH"):
        border = 0.022
    else:
        border = 0.028

    y_min = side_surface_y(x_min, side_sign) + side_sign * 0.006
    y_max = side_surface_y(x_max, side_sign) + side_sign * 0.006
    dx = x_max - x_min
    dy = y_max - y_min
    length = math.hypot(dx, dy)
    rotation_z = math.atan2(dy, dx)
    y_mid = (y_min + y_max) / 2.0
    x_mid = (x_min + x_max) / 2.0

    make_box(
        f"R3_FRAME_{name}_BOTTOM",
        (length, R3_FRAME_DEPTH_M, border),
        (x_mid, y_mid, z_min),
        material,
        body_root,
        rotation=(0.0, 0.0, rotation_z),
    )
    make_box(
        f"R3_FRAME_{name}_TOP",
        (length, R3_FRAME_DEPTH_M, border),
        (x_mid, y_mid, z_max),
        material,
        body_root,
        rotation=(0.0, 0.0, rotation_z),
    )
    make_box(
        f"R3_FRAME_{name}_FRONT",
        (border, R3_FRAME_DEPTH_M, z_max - z_min),
        (x_min, y_min, (z_min + z_max) / 2.0),
        material,
        body_root,
    )
    make_box(
        f"R3_FRAME_{name}_REAR",
        (border, R3_FRAME_DEPTH_M, z_max - z_min),
        (x_max, y_max, (z_min + z_max) / 2.0),
        material,
        body_root,
    )


def inset_existing_panels():
    # Living glass panels are embedded and reduced so the body-fixed frame is visible.
    for name in (
        "GLASS_LIVING_L_01",
        "GLASS_LIVING_L_02",
        "GLASS_LIVING_L_03",
        "GLASS_LIVING_L_04",
        "GLASS_LIVING_R_01",
        "GLASS_LIVING_R_03",
        "GLASS_LIVING_R_04",
    ):
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        side_sign = -1.0 if "_L_" in name else 1.0
        obj.scale.x *= 0.925
        obj.scale.z *= 0.885
        obj.location.y = side_sign * 1.153
        obj["s2_r3_glass_inset"] = True

    panel_specs = {
        "DOOR_LIVING_R": (0.940, 0.965, 1.0),
        "HATCH_L_1": (0.945, 0.900, -1.0),
        "HATCH_L_2": (0.945, 0.900, -1.0),
        "HATCH_L_3": (0.945, 0.900, -1.0),
        "HATCH_R_1": (0.945, 0.900, 1.0),
        "HATCH_R_2": (0.945, 0.900, 1.0),
        "HATCH_R_3": (0.945, 0.900, 1.0),
    }
    for name, (scale_x, scale_z, side_sign) in panel_specs.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        obj.scale.x *= scale_x
        obj.scale.z *= scale_z
        obj.location.y = -side_sign * 0.015
        obj["s2_r3_panel_inset"] = True

    glass_positions = {
        "DOOR_DRIVER_L_GLASS": 0.035,
        "DOOR_PASSENGER_R_GLASS": -0.035,
        "DOOR_LIVING_R_GLASS": -0.025,
    }
    for name, y_value in glass_positions.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        obj.location.y = y_value
        obj.scale.x *= 0.900
        obj.scale.z *= 0.900
        obj["s2_r3_glass_inset"] = True


def integrate_wheel_lips(body_material):
    for name, side_sign in (
        ("WHEEL_ARCH_FL", -1.0),
        ("WHEEL_ARCH_FR", 1.0),
        ("WHEEL_ARCH_RL", -1.0),
        ("WHEEL_ARCH_RR", 1.0),
    ):
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            continue
        obj.data.materials.clear()
        obj.data.materials.append(body_material)
        for vertex in obj.data.vertices:
            vertex.co.y -= side_sign * 0.014
        obj["s2_r3_visual_role"] = "integrated_body_colour_wheel_lip"


def prepare_windshield(body_root, body_material, trim_material):
    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    if glass is None:
        raise RuntimeError("GLASS_WINDSHIELD missing")
    glass.scale.y *= 0.865
    glass.scale.z *= 0.910
    glass.location.x += 0.010
    glass.location.z += 0.020
    glass["s2_r3_glass_inset"] = True

    rotation_y = float(glass.rotation_euler.y)
    rotation = (0.0, rotation_y, 0.0)
    center = Vector(glass.location)
    transform = Matrix.Rotation(rotation_y, 4, "Y")

    width = 1.700
    height = 0.790
    frame = 0.050
    depth = 0.070
    for suffix, local_offset, dimensions in (
        ("TOP", Vector((0.0, 0.0, height / 2.0)), (depth, width, frame)),
        ("BOTTOM", Vector((0.0, 0.0, -height / 2.0)), (depth, width, frame)),
        ("LEFT", Vector((0.0, -width / 2.0, 0.0)), (depth, frame, height)),
        ("RIGHT", Vector((0.0, width / 2.0, 0.0)), (depth, frame, height)),
    ):
        location = center + transform @ local_offset
        make_box(
            f"R3_WINDSHIELD_FRAME_{suffix}",
            dimensions,
            tuple(location),
            trim_material,
            body_root,
            rotation=rotation,
            bevel=0.006,
        )

    # Silver outer pillars overlap the previous sharp boundary corners and tie
    # the windshield frame into the roof and cab side surface.
    for suffix, side_sign in (("L", -1.0), ("R", 1.0)):
        local_offset = Vector((0.0, side_sign * 0.900, 0.0))
        location = center + transform @ local_offset
        pillar = make_box(
            f"R3_A_PILLAR_{suffix}",
            (0.095, 0.115, 0.880),
            tuple(location),
            body_material,
            body_root,
            rotation=rotation,
            bevel=0.012,
        )
        pillar["s2_r3_visual_role"] = "a_pillar_fairing"


def r3_prepare_frozen_source():
    references = ORIGINAL_FREEZE()
    body_root = bpy.data.objects.get("BODY")
    body_material = bpy.data.materials.get("MAT_BODY_SILVER")
    trim_material = bpy.data.materials.get("MAT_TRIM")
    if body_root is None or body_material is None or trim_material is None:
        raise RuntimeError("R3 body root/materials missing")

    replace_cab_door_panel("DOOR_DRIVER_L", -1.0)
    replace_cab_door_panel("DOOR_PASSENGER_R", 1.0)
    inset_existing_panels()
    integrate_wheel_lips(body_material)
    for opening in entry.SIDE_OPENINGS:
        make_side_frame(opening, body_root, trim_material)
    prepare_windshield(body_root, body_material, trim_material)
    return references


ORIGINAL_FREEZE = builder.r1.freeze_s1c_reference
builder.r1.freeze_s1c_reference = r3_prepare_frozen_source


ORIGINAL_BUILD_CAGE = entry.build_true_opening_cage


def r3_build_control_cage(parent, material):
    body = ORIGINAL_BUILD_CAGE(parent, material)
    body["s2_stage"] = "S2_R3_LOCAL_CURVATURE_REPAIR"
    body["s2_ring_count"] = len(builder.RING_XS)
    body["s2_ring_x_m"] = json.dumps(list(builder.RING_XS))
    body["s2_r3_smooth_wheel_blend"] = True
    body["s2_r3_windshield_frame"] = True
    body["s2_r3_web_contract_preserved"] = True

    crease = body.data.attributes.get("crease_edge")
    if crease is not None:
        bm = bmesh.new()
        bm.from_mesh(body.data)
        bm.edges.ensure_lookup_table()
        for edge in bm.edges:
            if len(edge.link_faces) != 1:
                continue
            midpoint = (edge.verts[0].co + edge.verts[1].co) * 0.5
            if midpoint.x < -3.820 and midpoint.z > 2.150:
                crease.data[edge.index].value = 0.46
            else:
                crease.data[edge.index].value = 0.70
        bm.free()

    bevel = next((modifier for modifier in body.modifiers if modifier.type == "BEVEL"), None)
    if bevel is not None:
        bevel.width = 0.0045
        bevel.segments = 2
    return body


builder.build_control_cage = r3_build_control_cage


def make_zebra_material():
    material = bpy.data.materials.get("MAT_R3_ZEBRA")
    if material is not None:
        return material
    material = bpy.data.materials.new("MAT_R3_ZEBRA")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    texcoord = nodes.new("ShaderNodeTexCoord")
    wave = nodes.new("ShaderNodeTexWave")
    ramp = nodes.new("ShaderNodeValToRGB")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Z"
    wave.inputs["Scale"].default_value = 14.0
    wave.inputs["Distortion"].default_value = 0.0
    ramp.color_ramp.elements[0].position = 0.44
    ramp.color_ramp.elements[0].color = (0.01, 0.01, 0.01, 1.0)
    ramp.color_ramp.elements[1].position = 0.56
    ramp.color_ramp.elements[1].color = (0.95, 0.95, 0.95, 1.0)
    shader.inputs["Roughness"].default_value = 0.18
    shader.inputs["Metallic"].default_value = 0.25
    links.new(texcoord.outputs["Generated"], wave.inputs["Vector"])
    links.new(wave.outputs["Color"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def render_r3_evidence(args):
    scene = bpy.context.scene
    camera = bpy.data.objects.get("Camera")
    body = bpy.data.objects.get("BODY_S2_CONTROL_CAGE")
    wire = bpy.data.objects.get("BODY_S2_WIREFRAME")
    if camera is None or body is None:
        raise RuntimeError("R3 evidence camera/body missing")
    output_dir = Path(args.output).parent
    front_closeup = output_dir / "S2_R3_Front_Closeup.png"
    wheel_closeup = output_dir / "S2_R3_Wheel_Closeup.png"
    zebra_left = output_dir / "S2_R3_Zebra_Left.png"
    zebra_right = output_dir / "S2_R3_Zebra_Right.png"

    if wire is not None:
        builder.r1.set_wire_visibility(wire, False)
    body.hide_render = False
    builder.r1.render(scene, camera, str(front_closeup), (-7.4, -5.4, 4.2), (-3.95, 0.0, 1.75))
    builder.r1.render(scene, camera, str(wheel_closeup), (0.0, -8.0, 1.65), (-0.65, 0.0, 0.80), 5.8)

    original_material = body.data.materials[0] if body.data.materials else None
    zebra = make_zebra_material()
    if body.data.materials:
        body.data.materials[0] = zebra
    else:
        body.data.materials.append(zebra)
    builder.r1.render(scene, camera, str(zebra_left), (0.0, -14.0, 1.55), (0.0, 0.0, 1.45), 10.5)
    builder.r1.render(scene, camera, str(zebra_right), (0.0, 14.0, 1.55), (0.0, 0.0, 1.45), 10.5)
    if original_material is not None:
        body.data.materials[0] = original_material
    scene.frame_set(1)
    return {
        "front_closeup": str(front_closeup),
        "wheel_closeup": str(wheel_closeup),
        "zebra_left": str(zebra_left),
        "zebra_right": str(zebra_right),
    }


def patch_manifest(args, evidence):
    manifest_path = Path(args.manifest)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["iteration"] = "R3"
    payload["stage_status"] = "R3_LOCAL_CURVATURE_REPAIR_CANDIDATE"
    payload["topology"]["ring_count"] = len(builder.RING_XS)
    payload["topology"]["ring_x_m"] = list(builder.RING_XS)
    payload["r3_visual_repairs"] = {
        "smooth_wheel_arch_transition": True,
        "integrated_body_colour_wheel_lips": True,
        "tapered_cab_door_panels": True,
        "inset_glass_and_covers": True,
        "side_opening_frames": len(entry.SIDE_OPENINGS),
        "windshield_frame": True,
        "a_pillar_fairings": 2,
        "web_node_and_animation_contract_preserved": True,
    }
    payload["proof_images"].update(evidence)
    payload["blend_bytes"] = Path(args.output).stat().st_size
    payload["blend_sha256"] = builder.sha256(args.output)
    payload["roundtrip_sha256"] = builder.sha256(args.roundtrip)
    payload["scope_note"] = (
        "S2-R3 preserves the R2 Web and animation interface while repairing the "
        "windshield/A-pillar framing, cab-door fit, opening reveal, integrated wheel "
        "lips and wheel-arch curvature. Manual close-up and zebra review is still required."
    )
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    args = builder.parse_args()
    builder.main()
    scene = bpy.context.scene
    scene["nomadhub_s2_iteration"] = "R3"
    scene["s2_status"] = "R3_LOCAL_CURVATURE_REPAIR_CANDIDATE"
    evidence = render_r3_evidence(args)
    animation_mode = builder.r1.active_actions_merged_mode()
    builder.r1.export_gltf_compatible(args.roundtrip, animation_mode)
    bpy.ops.wm.save_as_mainfile(filepath=args.output, compress=True)
    Path(args.output + "1").unlink(missing_ok=True)
    patch_manifest(args, evidence)
    print("NOMADHUB_S2_R3_LOCAL_CURVATURE_REPAIR_OK")
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == "__main__":
    main()
