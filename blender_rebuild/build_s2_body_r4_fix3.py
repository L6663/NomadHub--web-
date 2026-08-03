"""S2-R4 third visual repair: opening-matched windshield and clean wheel wells.

R4-F3 keeps the accepted 17-opening source cage and every frozen Web/animation
node. It corrects only the Web-visible presentation geometry:

- the windshield plane now follows the actual source opening endpoints, giving
  a 47 degree local slope and a 0.60 m opening-plane height;
- the body surround and dark trim are narrow rings around that true opening,
  rather than a large floating rectangular slab;
- cab-door rings are moved outward and resized to mask the subdivided source
  edge without entering the animated panel envelope;
- legacy and auxiliary wheel-arch objects remain exported for compatibility,
  but are optically transparent so the source body opening is the only visible
  wheel-arch profile.
"""

import importlib.util
import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


SCRIPT_DIR = Path(__file__).resolve().parent
FIX2_PATH = SCRIPT_DIR / "build_s2_body_r4_fix2.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix2", FIX2_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F2 builder: {FIX2_PATH}")
fix2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fix2)
r4 = fix2.r4
builder = fix2.builder
entry = fix2.entry
clearance = fix2.clearance


# F2 creates temporary compatibility wheel-lip curves before F3 replaces their
# material with an invisible compatibility material. The base R4 module does
# not export the helper used by F2, so provide it here before ORIGINAL_APPLY is
# ever executed. Keeping the dependency beside the F3 entrypoint prevents a
# separate execution shim from drifting away from the workflow entrypoint.
def make_curve_polyline(name, points, bevel_depth, material, parent):
    r4.remove_object(name)
    curve = bpy.data.curves.new(f"{name}_CURVE", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = 3
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for index, point in enumerate(points):
        spline.points[index].co = (*point, 1.0)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    curve.materials.append(material)
    obj["nomadhub_semantic_node"] = name
    obj["s2_r4_f3_explicit_curve_helper"] = True
    return obj


r4.make_curve_polyline = make_curve_polyline


# The true source opening runs approximately from (-4.300, 2.350) to
# (-3.860, 2.760) in the longitudinal/vertical plane.
WINDSHIELD_DX_M = 0.440
WINDSHIELD_DZ_M = 0.410
WINDSHIELD_PLANE_HEIGHT_M = math.hypot(WINDSHIELD_DX_M, WINDSHIELD_DZ_M)
WINDSHIELD_ROTATION_Y = math.atan2(WINDSHIELD_DX_M, WINDSHIELD_DZ_M)
WINDSHIELD_CENTER = Vector((-4.080, 0.0, 2.555))

r4.R4_WINDSHIELD_CENTER = WINDSHIELD_CENTER
r4.R4_WINDSHIELD_ROTATION_Y = WINDSHIELD_ROTATION_Y


ORIGINAL_APPLY = fix2.apply_r4_f2_surface_repairs


def make_invisible_compatibility_material():
    material = bpy.data.materials.get("MAT_R4_F3_INVISIBLE_COMPATIBILITY")
    if material is None:
        material = bpy.data.materials.new("MAT_R4_F3_INVISIBLE_COMPATIBILITY")
    material.use_nodes = True
    material.diffuse_color = (0.0, 0.0, 0.0, 0.0)
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    bsdf.inputs["Alpha"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 1.0
    if bsdf.inputs.get("Transmission Weight") is not None:
        bsdf.inputs["Transmission Weight"].default_value = 0.0
    try:
        material.surface_render_method = "DITHERED"
    except (AttributeError, TypeError):
        try:
            material.blend_method = "BLEND"
        except (AttributeError, TypeError):
            pass
    return material


def rebuild_opening_matched_windshield(body_root, body_material, trim_material):
    surround = r4.make_ring_mesh(
        "R4_WINDSHIELD_SURROUND",
        1.96,
        0.68,
        1.82,
        0.59,
        0.025,
        body_material,
        body_root,
    )
    surround["s2_r4_visual_role"] = "continuous_windshield_surround"
    surround["s2_r4_f2_surface_aligned"] = True
    surround["s2_r4_f3_opening_matched"] = True

    trim = r4.make_ring_mesh(
        "R4_WINDSHIELD_TRIM",
        1.84,
        0.60,
        1.76,
        0.52,
        0.030,
        trim_material,
        body_root,
    )
    trim["s2_r4_visual_role"] = "continuous_windshield_inner_trim"
    trim["s2_r4_f2_surface_aligned"] = True
    trim["s2_r4_f3_opening_matched"] = True

    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    if glass is None:
        raise RuntimeError("GLASS_WINDSHIELD missing during R4-F3")
    inward_normal = Matrix.Rotation(WINDSHIELD_ROTATION_Y, 4, "Y") @ Vector(
        (1.0, 0.0, 0.0)
    )
    fix2.replace_with_box_mesh(
        glass,
        (0.028, 1.740, 0.500),
        WINDSHIELD_CENTER + inward_normal * 0.018,
        (0.0, WINDSHIELD_ROTATION_Y, 0.0),
        fix2.make_windshield_material(),
    )
    glass["s2_r4_f3_opening_matched"] = True
    glass["s2_r4_f3_plane_height_m"] = WINDSHIELD_PLANE_HEIGHT_M


def rebuild_cab_surface_rings(body_root, body_material, trim_material):
    for name in (
        "R4_CAB_RING_L",
        "R4_CAB_RING_R",
        "R4_CAB_SEAM_L",
        "R4_CAB_SEAM_R",
    ):
        r4.remove_object(name)

    outer = (-4.430, -3.850, 0.420, 2.220)
    body_inner = (-4.385, -3.895, 0.480, 2.150)
    seam_outer = body_inner
    seam_inner = (-4.365, -3.915, 0.505, 2.125)
    for side, side_sign in (("L", -1.0), ("R", 1.0)):
        ring = fix2.make_side_ring(
            f"R4_CAB_RING_{side}",
            side_sign,
            outer,
            body_inner,
            0.042,
            0.018,
            body_material,
            body_root,
            0.006,
            "surface_aligned_body_surround",
        )
        seam = fix2.make_side_ring(
            f"R4_CAB_SEAM_{side}",
            side_sign,
            seam_outer,
            seam_inner,
            0.048,
            0.041,
            trim_material,
            body_root,
            0.002,
            "surface_aligned_inner_seam",
        )
        ring["s2_r4_f3_source_edge_mask"] = True
        seam["s2_r4_f3_source_edge_mask"] = True


def hide_auxiliary_wheel_arches():
    hidden = make_invisible_compatibility_material()
    for name in (
        "WHEEL_ARCH_FL",
        "WHEEL_ARCH_FR",
        "WHEEL_ARCH_RL",
        "WHEEL_ARCH_RR",
        "R4_WHEEL_LIP_FL",
        "R4_WHEEL_LIP_FR",
        "R4_WHEEL_LIP_RL",
        "R4_WHEEL_LIP_RR",
    ):
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise RuntimeError(f"R4-F3 compatibility wheel object missing: {name}")
        obj.data.materials.clear()
        obj.data.materials.append(hidden)
        obj["s2_r4_f3_visual_role"] = "invisible_compatibility_reference"
        obj["s2_r4_f3_source_body_arch_only"] = True
        try:
            obj.visible_shadow = False
        except AttributeError:
            pass


def apply_r4_f3_surface_repairs():
    ORIGINAL_APPLY()
    body_root = bpy.data.objects.get("BODY")
    body_material = bpy.data.materials.get("MAT_BODY_SILVER")
    trim_material = bpy.data.materials.get("MAT_TRIM")
    if body_root is None or body_material is None or trim_material is None:
        raise RuntimeError("R4-F3 roots/materials missing")

    rebuild_opening_matched_windshield(body_root, body_material, trim_material)
    rebuild_cab_surface_rings(body_root, body_material, trim_material)
    hide_auxiliary_wheel_arches()


r4.apply_r4_surface_repairs = apply_r4_f3_surface_repairs


def patch_fix3_manifest(path):
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    repairs = payload.setdefault("r4_visual_repairs", {})
    repairs.update(
        {
            "windshield_center_m": list(WINDSHIELD_CENTER),
            "windshield_rotation_y_deg": round(
                math.degrees(WINDSHIELD_ROTATION_Y), 6
            ),
            "windshield_plane_height_m": round(WINDSHIELD_PLANE_HEIGHT_M, 6),
            "windshield_opening_matched": True,
            "cab_source_edge_masked": True,
            "auxiliary_wheel_arches_invisible": 8,
            "source_body_wheel_arch_only": True,
            "source_openings_unchanged": True,
            "web_node_and_animation_contract_preserved": True,
        }
    )
    payload["stage_status"] = "R4_F3_OPENING_MATCHED_VISUAL_CANDIDATE"
    payload["r4_fix_iteration"] = "F3"
    payload["scope_note"] = (
        "R4-F3 preserves the accepted source cage, 17 openings, frozen roots and "
        "13 Web actions. The windshield is matched to the real sloped source opening, "
        "cab rings mask the subdivided edge from outside the door sweep, and auxiliary "
        "wheel-arch nodes remain exported but visually transparent."
    )
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    fix2.main()
    args = builder.parse_args()
    patch_fix3_manifest(args.manifest)
    print("NOMADHUB_S2_R4_F3_OPENING_MATCHED_REPAIR_OK")


if __name__ == "__main__":
    main()
