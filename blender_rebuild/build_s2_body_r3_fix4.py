"""R3 visual cleanup after the technical contract passed.

The strict geometry/animation gates are already green. This wrapper addresses
only defects still visible in the generated evidence:

- move the cab-door trim frame to the outer door plane so it no longer
  z-fights with the subdivided body boundary;
- widen those trim strips enough to mask the rough source opening edge while
  preserving the true opening centre;
- give the windshield its own stable dark material instead of the highly
  reflective shared glass response;
- keep legacy wheel-arch reference nodes for the frozen Web contract but make
  their obsolete floating geometry transparent.
"""

import importlib.util
import json
from pathlib import Path

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
FIX3_PATH = SCRIPT_DIR / "build_s2_body_r3_fix3.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r3_fix3", FIX3_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load final technical R3 fix: {FIX3_PATH}")
fix3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fix3)
r3 = fix3.r3
builder = fix3.builder
entry = fix3.entry
clearance = fix3.clearance
fix2 = fix3.fix2
fix1 = fix2.fix1


_ORIGINAL_PREPARE = r3.r3_prepare_frozen_source


def make_windshield_material():
    material = bpy.data.materials.get("MAT_WINDSHIELD_R3")
    if material is None:
        material = bpy.data.materials.new("MAT_WINDSHIELD_R3")
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.008, 0.022, 0.035, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.30
    if bsdf.inputs.get("Transmission Weight") is not None:
        bsdf.inputs["Transmission Weight"].default_value = 0.12
    if bsdf.inputs.get("Coat Weight") is not None:
        bsdf.inputs["Coat Weight"].default_value = 0.10
    return material


def make_hidden_reference_material():
    material = bpy.data.materials.get("MAT_R3_HIDDEN_ARCH_REFERENCE")
    if material is None:
        material = bpy.data.materials.new("MAT_R3_HIDDEN_ARCH_REFERENCE")
    material.use_nodes = True
    material.diffuse_color = (0.0, 0.0, 0.0, 0.0)
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    bsdf.inputs["Alpha"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 1.0
    try:
        material.surface_render_method = "DITHERED"
    except (AttributeError, TypeError):
        try:
            material.blend_method = "BLEND"
        except (AttributeError, TypeError):
            pass
    return material


def visual_cleanup_prepare():
    references = _ORIGINAL_PREPARE()

    # The body-fixed cab frames were only 6 mm outside the source side surface,
    # so the dark trim and the subdivided boundary occupied almost the same
    # pixels. Put the trim on the outer door plane and widen its coverage.
    for side_token, side_sign in (("CAB_DOOR_L", -1.0), ("CAB_DOOR_R", 1.0)):
        for suffix in ("BOTTOM", "TOP", "FRONT", "REAR"):
            name = f"R3_FRAME_{side_token}_{suffix}"
            obj = bpy.data.objects.get(name)
            if obj is None:
                raise RuntimeError(f"cab opening frame missing: {name}")
            obj.location.y += side_sign * 0.046
            obj.scale.y *= 0.45
            if suffix in ("TOP", "BOTTOM"):
                obj.scale.z *= 2.10
            else:
                obj.scale.x *= 2.10
            obj["s2_r3_outer_trim_plane"] = True
            obj["s2_r3_boundary_mask_scale"] = 2.10

    windshield = bpy.data.objects.get("GLASS_WINDSHIELD")
    if windshield is None:
        raise RuntimeError("GLASS_WINDSHIELD missing during visual cleanup")
    windshield.data.materials.clear()
    windshield.data.materials.append(make_windshield_material())
    windshield.location.x -= 0.018
    windshield["s2_r3_dedicated_dark_glass"] = True

    # The source-topology wheel opening now supplies the visible arch. Retain
    # the four legacy semantic nodes for coordinate/Web compatibility but make
    # their obsolete arc meshes optically transparent.
    hidden_arch_material = make_hidden_reference_material()
    for name in ("WHEEL_ARCH_FL", "WHEEL_ARCH_FR", "WHEEL_ARCH_RL", "WHEEL_ARCH_RR"):
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise RuntimeError(f"legacy wheel-arch reference missing: {name}")
        obj.data.materials.clear()
        obj.data.materials.append(hidden_arch_material)
        obj["s2_r3_visual_role"] = "transparent_legacy_web_reference"

    return references


r3.r3_prepare_frozen_source = visual_cleanup_prepare
builder.r1.freeze_s1c_reference = visual_cleanup_prepare


_ORIGINAL_FINALIZE_MANIFEST = fix1.finalize_manifest


def finalize_manifest_with_visual_cleanup(args, evidence):
    _ORIGINAL_FINALIZE_MANIFEST(args, evidence)
    manifest_path = Path(args.manifest)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["r3_visual_repairs"]["cab_frame_outer_trim_plane"] = True
    payload["r3_visual_repairs"]["cab_frame_boundary_mask_scale"] = 2.10
    payload["r3_visual_repairs"]["dedicated_windshield_material"] = True
    payload["r3_visual_repairs"]["legacy_wheel_arch_nodes_transparent"] = True
    payload["r3_visual_repairs"]["web_node_and_animation_contract_preserved"] = True
    payload["scope_note"] = (
        "S2-R3 technical and animation gates pass. This visual-cleanup build also "
        "moves cab trim off the body surface, stabilizes windshield shading and "
        "retains legacy wheel-arch Web nodes as transparent references."
    )
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


fix1.finalize_manifest = finalize_manifest_with_visual_cleanup


def main():
    fix3.main()


if __name__ == "__main__":
    main()
