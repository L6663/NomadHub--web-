"""Strict S2-R4 validator for the Web-visible surface repair candidate.

R4 reuses the fully validated R3 source cage and replaces only presentation
geometry around the windshield, cab doors and wheel lips. This validator keeps
all R2/R3 topology, opening, clearance, animation and GLB round-trip gates while
checking the new R4 visible-surface contract in Blender and in the imported GLB.
"""

import importlib.util
import json
from pathlib import Path

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
R2_ENTRY_PATH = SCRIPT_DIR / "validate_s2_body_r2_entry.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r2_strict_validator", R2_ENTRY_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load strict R2 validator: {R2_ENTRY_PATH}")
r2_entry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r2_entry)
validator = r2_entry.validator


CAB_SURROUNDS = tuple(
    f"R3_FRAME_CAB_DOOR_{side}_{suffix}"
    for side in ("L", "R")
    for suffix in ("BOTTOM", "TOP", "FRONT", "REAR")
)
CAB_TRIMS = tuple(
    f"R4_CAB_DOOR_TRIM_{side}_{suffix}"
    for side in ("L", "R")
    for suffix in ("BOTTOM", "TOP", "FRONT", "REAR")
)
R4_WHEEL_LIPS = (
    "R4_WHEEL_LIP_FL",
    "R4_WHEEL_LIP_FR",
    "R4_WHEEL_LIP_RL",
    "R4_WHEEL_LIP_RR",
)
LEGACY_WINDSHIELD_MARKERS = (
    "R3_WINDSHIELD_FRAME_TOP",
    "R3_WINDSHIELD_FRAME_BOTTOM",
    "R3_WINDSHIELD_FRAME_LEFT",
    "R3_WINDSHIELD_FRAME_RIGHT",
    "R3_A_PILLAR_L",
    "R3_A_PILLAR_R",
)
LEGACY_WHEEL_ARCHES = (
    "WHEEL_ARCH_FL",
    "WHEEL_ARCH_FR",
    "WHEEL_ARCH_RL",
    "WHEEL_ARCH_RR",
)


def dimensions(obj):
    return [float(value) for value in obj.dimensions]


def close_vector(actual, expected, tolerance=0.025):
    return all(abs(a - b) <= tolerance for a, b in zip(actual, expected))


def r4_visual_contract_report(label):
    failures = []

    surround = bpy.data.objects.get("R4_WINDSHIELD_SURROUND")
    trim = bpy.data.objects.get("R4_WINDSHIELD_TRIM")
    if surround is None or not bool(surround.get("s2_r4_web_surface")):
        failures.append(f"{label}: continuous windshield surround missing")
    elif surround.get("s2_r4_visual_role") != "continuous_windshield_surround":
        failures.append(f"{label}: windshield surround role marker missing")
    if trim is None or not bool(trim.get("s2_r4_web_surface")):
        failures.append(f"{label}: continuous windshield trim missing")
    elif trim.get("s2_r4_visual_role") != "continuous_windshield_inner_trim":
        failures.append(f"{label}: windshield trim role marker missing")

    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    glass_dims = None
    if glass is None:
        failures.append(f"{label}: GLASS_WINDSHIELD missing")
    else:
        glass_dims = dimensions(glass)
        if not bool(glass.get("s2_r4_dimensions_baked")):
            failures.append(f"{label}: windshield baked-dimension marker missing")
        if glass.get("s2_r4_visual_role") != "inset_windshield_glass":
            failures.append(f"{label}: windshield inset role marker missing")
        if not close_vector(glass_dims, (0.040, 1.700, 0.680), tolerance=0.035):
            failures.append(
                f"{label}: windshield dimensions {glass_dims} outside R4 tolerance"
            )

    surround_objects = [
        obj for obj in bpy.data.objects if bool(obj.get("s2_r4_cab_surround"))
    ]
    if len(surround_objects) != 8:
        failures.append(f"{label}: cab surround count {len(surround_objects)} != 8")
    for name in CAB_SURROUNDS:
        if bpy.data.objects.get(name) is None:
            failures.append(f"{label}: cab surround missing {name}")
    for name in CAB_TRIMS:
        if bpy.data.objects.get(name) is None:
            failures.append(f"{label}: cab inner trim missing {name}")

    buried = [
        obj for obj in bpy.data.objects if bool(obj.get("s2_r4_legacy_marker_buried"))
    ]
    if len(buried) != 6:
        failures.append(f"{label}: buried windshield marker count {len(buried)} != 6")
    for name in LEGACY_WINDSHIELD_MARKERS:
        obj = bpy.data.objects.get(name)
        if obj is None or not bool(obj.get("s2_r4_legacy_marker_buried")):
            failures.append(f"{label}: buried legacy marker missing {name}")

    for name in R4_WHEEL_LIPS:
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{label}: visual wheel lip missing {name}")
        elif not bool(obj.get("s2_r4_web_surface")):
            failures.append(f"{label}: wheel-lip Web marker missing {name}")

    for name in LEGACY_WHEEL_ARCHES:
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{label}: compatibility wheel liner missing {name}")
        elif obj.get("s2_r4_visual_role") != "recessed_compatibility_wheel_liner":
            failures.append(f"{label}: recessed wheel-liner marker missing {name}")

    body = bpy.data.objects.get(validator.BODY_NAME)
    if body is None:
        failures.append(f"{label}: {validator.BODY_NAME} missing")
    else:
        if body.get("s2_stage") != "S2_R4_WEB_SURFACE_REPAIR":
            failures.append(f"{label}: R4 body-stage marker missing")
        if not bool(body.get("s2_r4_web_contract_preserved")):
            failures.append(f"{label}: R4 Web contract marker missing")

    return {
        "label": label,
        "windshield_glass_dimensions_m": glass_dims,
        "cab_surround_piece_count": len(surround_objects),
        "cab_inner_trim_piece_count": sum(
            bpy.data.objects.get(name) is not None for name in CAB_TRIMS
        ),
        "buried_legacy_marker_count": len(buried),
        "visual_wheel_lip_count": sum(
            bpy.data.objects.get(name) is not None for name in R4_WHEEL_LIPS
        ),
        "failures": failures,
        "result": "PASS" if not failures else "FAIL",
    }


def collect_s1c_compatibility_with_r4(label):
    s1c = validator.s1c
    original_static = s1c.STATIC_COLLISION_OBJECTS
    try:
        s1c.STATIC_COLLISION_OBJECTS = (
            validator.BODY_NAME,
            "FRONT_BUMPER",
            "REAR_BUMPER",
            "SIDE_SKIRT_L_FRONT",
            "SIDE_SKIRT_L_MID",
            "SIDE_SKIRT_L_REAR",
            "SIDE_SKIRT_R_FRONT",
            "SIDE_SKIRT_R_MID",
            "SIDE_SKIRT_R_REAR",
            *LEGACY_WHEEL_ARCHES,
            *R4_WHEEL_LIPS,
            "WHEEL_FL_TIRE",
            "WHEEL_FR_TIRE",
            "WHEEL_RL_TIRE",
            "WHEEL_RR_TIRE",
            "R4_WINDSHIELD_SURROUND",
            "R4_WINDSHIELD_TRIM",
            *CAB_SURROUNDS,
            *CAB_TRIMS,
        )
        return validator.collect_s1c_compatibility(label)
    finally:
        s1c.STATIC_COLLISION_OBJECTS = original_static


def main():
    args = validator.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    clearance = json.loads(Path(args.clearance).read_text(encoding="utf-8"))

    blend_body = validator.collect_body("blend", manifest, source_topology=True)
    blend_visual = r4_visual_contract_report("blend")
    blend_s1c = collect_s1c_compatibility_with_r4("blend_s2_r4_compatibility")

    validator.clear_scene()
    bpy.ops.import_scene.gltf(filepath=args.glb)
    glb_body = validator.collect_body("glb_roundtrip", manifest, source_topology=False)
    glb_visual = r4_visual_contract_report("glb_roundtrip")
    glb_s1c = collect_s1c_compatibility_with_r4("glb_s2_r4_compatibility")

    roundtrip_failures = validator.compare_roundtrip(
        blend_body, glb_body, blend_s1c, glb_s1c
    )
    failures = []
    if manifest.get("iteration") != "R4":
        failures.append("manifest iteration is not R4")
    repairs = manifest.get("r4_visual_repairs", {})
    required_repairs = {
        "continuous_windshield_surround": True,
        "continuous_windshield_inner_trim": True,
        "cab_door_body_surrounds": 2,
        "cab_door_inner_trim_sets": 2,
        "legacy_windshield_markers_buried": 6,
        "recessed_compatibility_wheel_liners": 4,
        "integrated_visual_wheel_lips": 4,
        "source_openings_unchanged": True,
        "web_node_and_animation_contract_preserved": True,
    }
    for key, expected in required_repairs.items():
        if repairs.get(key) != expected:
            failures.append(
                f"R4 manifest marker {key}={repairs.get(key)!r} != {expected!r}"
            )
    if manifest.get("source_true_openings") is not True:
        failures.append("R4 manifest lost source true-opening marker")
    if manifest.get("true_opening_count") != 17:
        failures.append("R4 manifest true-opening count is not 17")
    if clearance.get("result") != "PASS":
        failures.append("inherited S1C clearance report is not PASS")

    failures.extend(blend_body.get("failures", []))
    failures.extend(glb_body.get("failures", []))
    failures.extend(blend_visual["failures"])
    failures.extend(glb_visual["failures"])
    failures.extend(blend_s1c.get("failures", []))
    failures.extend(glb_s1c.get("failures", []))
    failures.extend(roundtrip_failures)

    report = {
        "schema": "nomadhub-s2-r4-verification-v1",
        "stage": "S2",
        "iteration": "R4",
        "status": "PASS" if not failures else "FAIL",
        "s2_r4_ready_for_manual_visual_review": not failures,
        "s2_accepted": False,
        "blend_body": blend_body,
        "glb_body": glb_body,
        "blend_visual_contract": blend_visual,
        "glb_visual_contract": glb_visual,
        "blend_s1c_compatibility": blend_s1c,
        "glb_s1c_compatibility": glb_s1c,
        "roundtrip_failures": roundtrip_failures,
        "failures": failures,
        "scope_note": (
            "A PASS proves that R4 preserves the strict source topology, 17 true "
            "openings, frozen anchors, actions, wheel clearance and GLB round trip "
            "while carrying the continuous Web-visible windshield, cab-door and wheel "
            "surface repairs. Manual image review is still required before S2 freeze."
        ),
    }
    Path(args.report).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    if failures:
        raise RuntimeError("S2 R4 verification failed")
    print("S2_R4_TECHNICAL_AND_WEB_SURFACE_CONTRACT_PASS")


if __name__ == "__main__":
    main()
