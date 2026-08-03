import argparse
import importlib.util
import json
import sys
from pathlib import Path

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
BASE_PATH = SCRIPT_DIR / "validate_s2_body.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_validate_s2_base", BASE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load S2 base validator: {BASE_PATH}")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)

base.EXPECTED_FROZEN_ROOT_X.update(
    {
        "DOOR_DRIVER_L_ROOT": -4.400,
        "DOOR_PASSENGER_R_ROOT": -4.400,
    }
)

BODY_NAME = "BODY_S2_CONTROL_CAGE"
WIRE_NAME = "BODY_S2_WIREFRAME"
EXPECTED_MODIFIERS = ("SUBSURF", "BEVEL")
EXPECTED_RING_SIZE = 48
MIN_RING_COUNT = 60
POSITION_TOLERANCE_M = 0.002
ROUNDTRIP_TOLERANCE_M = 0.010
S2_STATIC_COLLISION_OBJECTS = (
    BODY_NAME,
    "FRONT_BUMPER",
    "REAR_BUMPER",
    "SIDE_SKIRT_L_FRONT",
    "SIDE_SKIRT_L_MID",
    "SIDE_SKIRT_L_REAR",
    "SIDE_SKIRT_R_FRONT",
    "SIDE_SKIRT_R_MID",
    "SIDE_SKIRT_R_REAR",
    "WHEEL_ARCH_FL",
    "WHEEL_ARCH_FR",
    "WHEEL_ARCH_RL",
    "WHEEL_ARCH_RR",
    "WHEEL_FL_TIRE",
    "WHEEL_FR_TIRE",
    "WHEEL_RL_TIRE",
    "WHEEL_RR_TIRE",
)


def parse_args():
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", required=True)
    parser.add_argument("--clearance", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(raw)


def parse_json_property(obj, name, default):
    value = obj.get(name)
    if value is None:
        return default
    if isinstance(value, str):
        return json.loads(value)
    return value


def opening_ring_failures(manifest, body):
    failures = []
    rings = [float(value) for value in parse_json_property(body, "s2_ring_x_m", [])]
    if not rings:
        return ["S2 R2 control-ring list missing"]
    for opening in manifest.get("opening_guides", []):
        x_min = float(opening["x_min_m"])
        x_max = float(opening["x_max_m"])
        center = (x_min + x_max) / 2
        required = (x_min, x_min + 0.040, center, x_max - 0.040, x_max)
        missing = [
            value
            for value in required
            if not any(abs(value - actual) <= 0.001 for actual in rings)
        ]
        if missing:
            failures.append(f"{opening['name']} missing support-ring X values {missing}")
    return failures


def collect_body(label, manifest, source_topology):
    failures = []
    body = bpy.data.objects.get(BODY_NAME)
    if body is None or body.type != "MESH":
        return {
            "label": label,
            "result": "FAIL",
            "failures": [f"{BODY_NAME} missing or not a mesh"],
        }

    evaluated_bounds = base.object_bounds(body, evaluated=True)
    result = {
        "label": label,
        "body_name": body.name,
        "evaluated_bounds": evaluated_bounds,
    }
    if evaluated_bounds["dimensions_m"][0] < 8.80:
        failures.append("evaluated continuous body length is unexpectedly short")

    if source_topology:
        topology = base.polygon_statistics(body.data)
        connectivity = base.topology_connectivity(body.data)
        source_bounds = base.object_bounds(body, evaluated=False)
        modifier_types = tuple(modifier.type for modifier in body.modifiers)
        ring_count = int(body.get("s2_ring_count", 0))
        ring_size = int(body.get("s2_ring_size", 0))
        opening_names = parse_json_property(body, "s2_opening_guides", [])

        result.update(
            {
                "source_bounds": source_bounds,
                "topology": topology,
                "connectivity": connectivity,
                "modifier_types": list(modifier_types),
                "ring_count": ring_count,
                "ring_size": ring_size,
                "opening_guides": opening_names,
                "all_quad_caps": bool(body.get("s2_all_quad_caps")),
                "source_wheel_arch_topology": bool(body.get("s2_source_wheel_arch_topology")),
            }
        )

        source_length, source_width, _ = source_bounds["dimensions_m"]
        if abs(source_length - 8.990) > 0.015:
            failures.append(f"source body length {source_length:.6f} differs from 8.990")
        if abs(source_width - 2.300) > 0.015:
            failures.append(f"source body width {source_width:.6f} differs from 2.300")
        if topology["triangles"] != 0:
            failures.append(f"R2 source contains {topology['triangles']} triangles")
        if topology["ngons"] != 0:
            failures.append(f"R2 source contains {topology['ngons']} n-gons")
        if topology["quad_ratio"] != 1.0:
            failures.append(f"R2 source quad ratio {topology['quad_ratio']:.6f} != 1.0")
        if connectivity["connected_components"] != 1:
            failures.append(f"R2 source has {connectivity['connected_components']} components")
        if connectivity["non_manifold_edges"] != 0:
            failures.append(f"R2 source has {connectivity['non_manifold_edges']} non-manifold edges")
        if connectivity["loose_vertices"] != 0:
            failures.append(f"R2 source has {connectivity['loose_vertices']} loose vertices")
        if modifier_types != EXPECTED_MODIFIERS:
            failures.append(f"modifier order {modifier_types}, expected {EXPECTED_MODIFIERS}")
        if any(modifier.type == "BOOLEAN" for modifier in body.modifiers):
            failures.append("R2 source still contains Boolean wheel-arch modifiers")
        if bpy.data.objects.get("S2_CUTTER_ARCH_FRONT") is not None:
            failures.append("front Boolean cutter still present")
        if bpy.data.objects.get("S2_CUTTER_ARCH_REAR") is not None:
            failures.append("rear Boolean cutter still present")
        if ring_count < MIN_RING_COUNT:
            failures.append(f"R2 ring count {ring_count} < {MIN_RING_COUNT}")
        if ring_size != EXPECTED_RING_SIZE:
            failures.append(f"R2 ring size {ring_size} != {EXPECTED_RING_SIZE}")
        if not bool(body.get("s2_all_quad_caps")):
            failures.append("R2 all-quad cap marker missing")
        if not bool(body.get("s2_source_wheel_arch_topology")):
            failures.append("R2 source wheel-arch topology marker missing")
        if len(opening_names) != len(manifest.get("opening_guides", [])):
            failures.append("opening-guide count differs between body and manifest")
        failures.extend(opening_ring_failures(manifest, body))

        wire = bpy.data.objects.get(WIRE_NAME)
        if wire is None or not bool(wire.get("s2_proof_only")):
            failures.append(f"{WIRE_NAME} proof object missing or unmarked")
        for reference_name in ("S1C_BODY_MAIN_REFERENCE", "S1C_BODY_CAB_REFERENCE"):
            reference = bpy.data.objects.get(reference_name)
            if reference is None:
                failures.append(f"frozen reference missing: {reference_name}")
            elif not reference.hide_render:
                failures.append(f"frozen reference remains renderable: {reference_name}")

    frozen = base.frozen_position_report()
    wheel_clearance = base.wheel_body_clearance()
    failures.extend(frozen["failures"])
    failures.extend(wheel_clearance["failures"])
    result.update(
        {
            "frozen_positions": frozen,
            "wheel_body_clearance": wheel_clearance,
            "objects": len(bpy.data.objects),
            "meshes": len(bpy.data.meshes),
            "actions": len(bpy.data.actions),
            "failures": failures,
            "result": "PASS" if not failures else "FAIL",
        }
    )
    return result


def collect_s1c_compatibility(label):
    original_static = base.s1c.STATIC_COLLISION_OBJECTS
    try:
        base.s1c.STATIC_COLLISION_OBJECTS = S2_STATIC_COLLISION_OBJECTS
        return base.s1c.collect_scene_metrics(label)
    finally:
        base.s1c.STATIC_COLLISION_OBJECTS = original_static


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def compare_roundtrip(blend_body, glb_body, blend_s1c, glb_s1c):
    failures = []
    blend_bounds = blend_body.get("evaluated_bounds", {})
    glb_bounds = glb_body.get("evaluated_bounds", {})
    for key in ("min_m", "max_m", "dimensions_m"):
        blend_values = blend_bounds.get(key, [])
        glb_values = glb_bounds.get(key, [])
        if len(blend_values) != 3 or len(glb_values) != 3:
            failures.append(f"roundtrip body metric missing: {key}")
            continue
        for axis, (blend_value, glb_value) in enumerate(zip(blend_values, glb_values)):
            delta = abs(blend_value - glb_value)
            if delta > ROUNDTRIP_TOLERANCE_M:
                failures.append(f"body {key}[{axis}] roundtrip delta {delta:.6f} > 0.010")
    failures.extend(base.s1c.compare_roundtrip(blend_s1c, glb_s1c))
    return failures


def main():
    args = parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    clearance = json.loads(Path(args.clearance).read_text(encoding="utf-8"))

    blend_body = collect_body("blend", manifest, source_topology=True)
    blend_s1c = collect_s1c_compatibility("blend_s2_r2_compatibility")

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=args.glb)
    glb_body = collect_body("glb_roundtrip", manifest, source_topology=False)
    glb_s1c = collect_s1c_compatibility("glb_s2_r2_compatibility")

    roundtrip_failures = compare_roundtrip(blend_body, glb_body, blend_s1c, glb_s1c)
    failures = []
    if clearance.get("result") != "PASS":
        failures.append("inherited S1C clearance report is not PASS")
    failures.extend(blend_body.get("failures", []))
    failures.extend(glb_body.get("failures", []))
    failures.extend(blend_s1c.get("failures", []))
    failures.extend(glb_s1c.get("failures", []))
    failures.extend(roundtrip_failures)

    report = {
        "schema": "nomadhub-s2-r2-verification-v1",
        "stage": "S2",
        "iteration": "R2",
        "status": "PASS" if not failures else "FAIL",
        "s2_r2_ready_for_visual_review": not failures,
        "s2_accepted": False,
        "blend_body": blend_body,
        "glb_body": glb_body,
        "blend_s1c_compatibility": blend_s1c,
        "glb_s1c_compatibility": glb_s1c,
        "roundtrip_failures": roundtrip_failures,
        "failures": failures,
        "scope_note": (
            "A PASS result proves the R2 all-quad source cage, source-topology wheel arches, "
            "opening-aligned control rings, frozen-anchor compatibility and GLB roundtrip. "
            "Final S2 acceptance still requires visual and curvature review."
        ),
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if failures:
        raise RuntimeError("S2 R2 verification failed")


if __name__ == "__main__":
    main()
