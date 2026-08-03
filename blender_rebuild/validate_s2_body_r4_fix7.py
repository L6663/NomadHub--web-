"""Strict native/GLB validator for the R4-F7 native-boundary repair."""

import importlib.util
from collections import defaultdict, deque
from pathlib import Path

import bmesh
import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
F3_PATH = SCRIPT_DIR / "validate_s2_body_r4_fix3.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_f3_validator", F3_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F3 validator: {F3_PATH}")
f3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f3)
base = f3.base

CAB_X_MIN = -4.400
CAB_X_MAX = -3.880
CAB_Z_MIN = 0.450
CAB_Z_MAX = 2.170
ORIGINAL_VISUAL_REPORT = base.r4_visual_contract_report


def boundary_components(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    boundary_edges = [edge for edge in bm.edges if len(edge.link_faces) == 1]
    adjacency = defaultdict(set)
    for edge in boundary_edges:
        a = edge.verts[0].index
        b = edge.verts[1].index
        adjacency[a].add(b)
        adjacency[b].add(a)
    unseen = set(adjacency)
    components = []
    while unseen:
        start = unseen.pop()
        component = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current]:
                if neighbor not in component:
                    component.add(neighbor)
                    unseen.discard(neighbor)
                    queue.append(neighbor)
        components.append(component)
    bm.free()
    return components


def cab_boundary_report(body, strict_source):
    if body is None or body.type != "MESH":
        return {"rows": [], "failures": ["F7 body missing"], "result": "FAIL"}
    failures = []
    rows = []
    if not bool(body.get("s2_r4_f7_native_cab_boundary_repair")):
        failures.append("F7 body native-boundary marker missing")
    if int(body.get("s2_r4_f7_cab_boundary_count", 0)) != 2:
        failures.append("F7 body cab-boundary count marker is not two")

    if strict_source:
        matches = []
        for component in boundary_components(body.data):
            points = [body.data.vertices[index].co for index in component]
            if not points:
                continue
            bounds = {
                "x_min": min(float(point.x) for point in points),
                "x_max": max(float(point.x) for point in points),
                "y_mean": sum(float(point.y) for point in points) / len(points),
                "z_min": min(float(point.z) for point in points),
                "z_max": max(float(point.z) for point in points),
                "vertex_count": len(points),
            }
            if abs(bounds["y_mean"]) < 0.90:
                continue
            if bounds["z_max"] - bounds["z_min"] < 1.20:
                continue
            if abs(bounds["x_min"] - CAB_X_MIN) > 0.16:
                continue
            if abs(bounds["x_max"] - CAB_X_MAX) > 0.16:
                continue
            matches.append(bounds)
        matches.sort(key=lambda item: item["y_mean"])
        if len(matches) != 2:
            failures.append(f"F7 source cab-loop count {len(matches)} != 2")
        for bounds in matches:
            side = "L" if bounds["y_mean"] < 0 else "R"
            row = {
                "side": side,
                "x_min_m": bounds["x_min"],
                "x_max_m": bounds["x_max"],
                "z_min_m": bounds["z_min"],
                "z_max_m": bounds["z_max"],
                "vertex_count": bounds["vertex_count"],
            }
            rows.append(row)
            for key, actual, expected in (
                ("x_min", bounds["x_min"], CAB_X_MIN),
                ("x_max", bounds["x_max"], CAB_X_MAX),
                ("z_min", bounds["z_min"], CAB_Z_MIN),
                ("z_max", bounds["z_max"], CAB_Z_MAX),
            ):
                if abs(actual - expected) > 0.002:
                    failures.append(
                        f"F7 {side} source boundary {key}={actual:.6f} != {expected:.6f}"
                    )
    return {"rows": rows, "failures": failures, "result": "PASS" if not failures else "FAIL"}


def max_dimension(obj):
    return max(float(value) for value in obj.dimensions) if obj is not None else None


def visual_report_f7(label):
    report = ORIGINAL_VISUAL_REPORT(label)
    # F7 keeps the F3 semantic nodes but changes the visible seam role from the
    # transitional F2 name to a native-opening seal. Remove only that obsolete
    # role-string failure; all presence, Web-marker and opening-match checks stay.
    failures = [
        failure
        for failure in report["failures"]
        if not (
            "R4-F3 role mismatch R4_CAB_SEAM_" in failure
            or "R4-F3 surface role mismatch: R4_CAB_SEAM_" in failure
        )
    ]

    body = bpy.data.objects.get(base.validator.BODY_NAME)
    boundary = cab_boundary_report(body, strict_source=label == "blend")
    failures.extend(boundary["failures"])

    hidden = {}
    for name in (
        "R4_CAB_RING_L",
        "R4_CAB_RING_R",
        "R4_CAB_HEADER_L",
        "R4_CAB_HEADER_R",
        "R4_WINDSHIELD_SURROUND",
    ):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{label}: F7 hidden compatibility node missing {name}")
            continue
        if not bool(obj.get("s2_r4_f7_hidden_compatibility_marker")):
            failures.append(f"{label}: F7 hidden marker flag missing {name}")
        dimension = max_dimension(obj)
        hidden[name] = dimension
        if dimension is None or dimension > 0.020:
            failures.append(
                f"{label}: F7 compatibility marker remains visible-sized {name}={dimension}"
            )

    seals = {}
    for name in ("R4_CAB_SEAM_L", "R4_CAB_SEAM_R", "R4_WINDSHIELD_TRIM"):
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"{label}: F7 native-opening seal missing {name}")
            continue
        if not bool(obj.get("s2_r4_f7_native_opening_seal")):
            failures.append(f"{label}: F7 native-opening seal marker missing {name}")
        dimension = max_dimension(obj)
        seals[name] = dimension
        if dimension is None or dimension < 0.40:
            failures.append(f"{label}: F7 visible seal is unexpectedly small {name}")

    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    if glass is None or not bool(glass.get("s2_r4_f7_native_opening_glass")):
        failures.append(f"{label}: F7 native-opening glass marker missing")

    report["r4_f7_native_cab_boundaries"] = boundary
    report["r4_f7_hidden_marker_max_dimensions_m"] = hidden
    report["r4_f7_visible_seal_max_dimensions_m"] = seals
    report["failures"] = failures
    report["result"] = "PASS" if not failures else "FAIL"
    return report


base.r4_visual_contract_report = visual_report_f7


def collect_s1c_f7(label):
    # R4 validator -> strict R2 validator -> S2 base validator -> S1C.
    s1c = base.validator.base.s1c
    original_static = s1c.STATIC_COLLISION_OBJECTS
    try:
        s1c.STATIC_COLLISION_OBJECTS = (
            base.validator.BODY_NAME,
            "FRONT_BUMPER",
            "REAR_BUMPER",
            "SIDE_SKIRT_L_FRONT",
            "SIDE_SKIRT_L_MID",
            "SIDE_SKIRT_L_REAR",
            "SIDE_SKIRT_R_FRONT",
            "SIDE_SKIRT_R_MID",
            "SIDE_SKIRT_R_REAR",
            *base.LEGACY_WHEEL_ARCHES,
            *base.R4_WHEEL_LIPS,
            "WHEEL_FL_TIRE",
            "WHEEL_FR_TIRE",
            "WHEEL_RL_TIRE",
            "WHEEL_RR_TIRE",
            "R4_WINDSHIELD_TRIM",
            "R4_CAB_SEAM_L",
            "R4_CAB_SEAM_R",
            *base.CAB_SURROUNDS,
            *base.CAB_TRIMS,
        )
        return base.validator.collect_s1c_compatibility(label)
    finally:
        s1c.STATIC_COLLISION_OBJECTS = original_static


base.collect_s1c_compatibility_with_r4 = collect_s1c_f7


if __name__ == "__main__":
    base.main()
