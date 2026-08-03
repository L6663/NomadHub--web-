"""S2-R3 validator built on the strict R2 topology/roundtrip gate."""

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


def visual_contract_report(label):
    failures = []
    frames = [obj for obj in bpy.data.objects if obj.name.startswith("R3_FRAME_")]
    windshield_frames = [obj for obj in bpy.data.objects if obj.name.startswith("R3_WINDSHIELD_FRAME_")]
    pillars = [bpy.data.objects.get("R3_A_PILLAR_L"), bpy.data.objects.get("R3_A_PILLAR_R")]
    if len(frames) < 64:
        failures.append(f"{label}: side frame count {len(frames)} < 64")
    if len(windshield_frames) != 4:
        failures.append(f"{label}: windshield frame count {len(windshield_frames)} != 4")
    if any(pillar is None for pillar in pillars):
        failures.append(f"{label}: A-pillar fairing missing")

    for name in ("DOOR_DRIVER_L", "DOOR_PASSENGER_R"):
        obj = bpy.data.objects.get(name)
        if obj is None or not bool(obj.get("s2_r3_tapered_cab_panel")):
            failures.append(f"{label}: {name} tapered cab panel marker missing")

    for name in ("WHEEL_ARCH_FL", "WHEEL_ARCH_FR", "WHEEL_ARCH_RL", "WHEEL_ARCH_RR"):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{label}: {name} missing")
            continue
        if obj.get("s2_r3_visual_role") != "integrated_body_colour_wheel_lip":
            failures.append(f"{label}: {name} integrated wheel-lip marker missing")

    body = bpy.data.objects.get(validator.BODY_NAME)
    if body is None:
        failures.append(f"{label}: {validator.BODY_NAME} missing")
    else:
        if body.get("s2_stage") != "S2_R3_LOCAL_CURVATURE_REPAIR":
            failures.append(f"{label}: R3 body stage marker missing")
        if not bool(body.get("s2_r3_smooth_wheel_blend")):
            failures.append(f"{label}: smooth wheel blend marker missing")
        if not bool(body.get("s2_r3_web_contract_preserved")):
            failures.append(f"{label}: Web contract marker missing")

    return {
        "label": label,
        "side_frame_count": len(frames),
        "windshield_frame_count": len(windshield_frames),
        "a_pillar_count": sum(pillar is not None for pillar in pillars),
        "failures": failures,
        "result": "PASS" if not failures else "FAIL",
    }


def main():
    args = validator.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    clearance = json.loads(Path(args.clearance).read_text(encoding="utf-8"))

    blend_body = validator.collect_body("blend", manifest, source_topology=True)
    blend_visual = visual_contract_report("blend")
    blend_s1c = validator.collect_s1c_compatibility("blend_s2_r3_compatibility")

    validator.clear_scene()
    bpy.ops.import_scene.gltf(filepath=args.glb)
    glb_body = validator.collect_body("glb_roundtrip", manifest, source_topology=False)
    glb_visual = visual_contract_report("glb_roundtrip")
    glb_s1c = validator.collect_s1c_compatibility("glb_s2_r3_compatibility")

    roundtrip_failures = validator.compare_roundtrip(blend_body, glb_body, blend_s1c, glb_s1c)
    failures = []
    if manifest.get("iteration") != "R3":
        failures.append("manifest iteration is not R3")
    repairs = manifest.get("r3_visual_repairs", {})
    for key in (
        "smooth_wheel_arch_transition",
        "integrated_body_colour_wheel_lips",
        "tapered_cab_door_panels",
        "inset_glass_and_covers",
        "windshield_frame",
        "web_node_and_animation_contract_preserved",
    ):
        if repairs.get(key) is not True:
            failures.append(f"R3 manifest repair marker missing: {key}")
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
        "schema": "nomadhub-s2-r3-verification-v1",
        "stage": "S2",
        "iteration": "R3",
        "status": "PASS" if not failures else "FAIL",
        "s2_r3_ready_for_manual_visual_review": not failures,
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
            "A PASS proves that R3 preserves the strict R2 topology, true openings, "
            "wheel clearance, animation and GLB contract while carrying the local visual "
            "repair objects and metadata. Final S2 acceptance still requires review of "
            "the close-up and zebra evidence images."
        ),
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if failures:
        raise RuntimeError("S2 R3 verification failed")
    print("S2_R3_TECHNICAL_AND_VISUAL_CONTRACT_PASS")


if __name__ == "__main__":
    main()
