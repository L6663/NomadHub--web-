"""Fail-fast gate for the R4-F6 integrated cab/windshield repair."""

import importlib.util
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PREFLIGHT_PATH = SCRIPT_DIR / "preflight_s2_body_r4_fix5.py"
PREFLIGHT_SPEC = importlib.util.spec_from_file_location(
    "nomadhub_s2_r4_f5_preflight", PREFLIGHT_PATH
)
if PREFLIGHT_SPEC is None or PREFLIGHT_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F5 preflight: {PREFLIGHT_PATH}")
preflight5 = importlib.util.module_from_spec(PREFLIGHT_SPEC)
PREFLIGHT_SPEC.loader.exec_module(preflight5)

FIX_PATH = SCRIPT_DIR / "build_s2_body_r4_fix6.py"
FIX_SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix6", FIX_PATH)
if FIX_SPEC is None or FIX_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F6 builder: {FIX_PATH}")
fixed = importlib.util.module_from_spec(FIX_SPEC)
FIX_SPEC.loader.exec_module(fixed)

# Rebind every inherited layer to F6. F5's geometry report uses its module-level
# ``fixed`` reference, while F3's visual contract lives two layers below it.
preflight5.fixed = fixed
preflight3 = preflight5.preflight3
preflight_r4 = preflight5.preflight_r4
preflight3.fixed = fixed
preflight3.r4 = fixed.r4
preflight_r4.r4_fixed = fixed
preflight_r4.r4 = fixed.r4
preflight_r4.preflight.fixed = fixed
preflight_r4.preflight.base.r3 = fixed.r4
preflight_r4.preflight.base.builder = fixed.builder
preflight_r4.preflight.base.entry = fixed.entry


def animation_preflight_f6():
    s1c = preflight_r4.preflight.base.validator.s1c
    original_static = s1c.STATIC_COLLISION_OBJECTS
    try:
        s1c.STATIC_COLLISION_OBJECTS = (
            preflight_r4.preflight.base.validator.BODY_NAME,
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
            "R4_WHEEL_LIP_FL",
            "R4_WHEEL_LIP_FR",
            "R4_WHEEL_LIP_RL",
            "R4_WHEEL_LIP_RR",
            "WHEEL_FL_TIRE",
            "WHEEL_FR_TIRE",
            "WHEEL_RL_TIRE",
            "WHEEL_RR_TIRE",
            "R4_WINDSHIELD_SURROUND",
            "R4_WINDSHIELD_TRIM",
            "R4_CAB_RING_L",
            "R4_CAB_RING_R",
            "R4_CAB_SEAM_L",
            "R4_CAB_SEAM_R",
            "R4_CAB_HEADER_L",
            "R4_CAB_HEADER_R",
        )
        return s1c.animation_collision_sweep()
    finally:
        s1c.STATIC_COLLISION_OBJECTS = original_static


preflight_r4.r4_animation_preflight = animation_preflight_f6
preflight_r4.preflight.animation_preflight = animation_preflight_f6

ORIGINAL_VISUAL_CONTRACT = preflight_r4.r4_visual_contract


def header_world_report(obj, side_sign):
    if obj is None or obj.type != "MESH" or not obj.data.vertices:
        return None
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    outward = []
    for point in points:
        surface_y = (
            side_sign * fixed.builder.section_dimensions(float(point.x))[0] / 2.0
        )
        outward.append(side_sign * (float(point.y) - surface_y))
    return {
        "z_min_m": min(float(point.z) for point in points),
        "z_max_m": max(float(point.z) for point in points),
        "outward_min_m": min(outward),
        "outward_max_m": max(outward),
    }


def visual_contract_f6():
    report = ORIGINAL_VISUAL_CONTRACT()
    # F5 required the complete annular ring itself to reach z=2.30 m. F6 moves
    # that masking duty to a separate flush body patch, so remove only that
    # superseded failure and enforce the header patch below.
    failures = [
        failure
        for failure in report["failures"]
        if "header does not cover source edge" not in failure
    ]
    bpy = preflight_r4.preflight.base.bpy

    headers = {}
    for side, side_sign in (("L", -1.0), ("R", 1.0)):
        name = f"R4_CAB_HEADER_{side}"
        obj = bpy.data.objects.get(name)
        if obj is None:
            failures.append(f"R4-F6 cab header missing: {name}")
            continue
        if not bool(obj.get("s2_r4_f6_flush_header_patch")):
            failures.append(f"R4-F6 cab-header marker missing: {name}")
        geometry = header_world_report(obj, side_sign)
        headers[name] = geometry
        if geometry is None:
            failures.append(f"R4-F6 cab-header geometry unavailable: {name}")
            continue
        if geometry["z_min_m"] > 2.130 or geometry["z_max_m"] < 2.300:
            failures.append(
                f"R4-F6 cab header does not span source ripple: {name} {geometry}"
            )
        if geometry["outward_max_m"] > 0.010:
            failures.append(
                f"R4-F6 cab header floats outside body: {name} "
                f"{geometry['outward_max_m']:.4f}m"
            )
        if geometry["outward_min_m"] < -0.012:
            failures.append(
                f"R4-F6 cab header buried too deeply: {name} "
                f"{geometry['outward_min_m']:.4f}m"
            )

    narrow_surfaces = []
    for name in (
        "R4_CAB_RING_L",
        "R4_CAB_RING_R",
        "R4_CAB_SEAM_L",
        "R4_CAB_SEAM_R",
    ):
        obj = bpy.data.objects.get(name)
        if obj is None or not bool(obj.get("s2_r4_f6_narrow_ring")):
            failures.append(f"R4-F6 narrow cab ring marker missing: {name}")
        else:
            narrow_surfaces.append(name)

    trapezoids = {}
    for name in ("R4_WINDSHIELD_SURROUND", "R4_WINDSHIELD_TRIM"):
        obj = bpy.data.objects.get(name)
        if obj is None or not bool(obj.get("s2_r4_f6_trapezoid_ring")):
            failures.append(f"R4-F6 trapezoid ring missing: {name}")
            continue
        bottom = float(obj.get("s2_r4_f6_bottom_width_m", 0.0))
        top = float(obj.get("s2_r4_f6_top_width_m", 0.0))
        trapezoids[name] = {"bottom_width_m": bottom, "top_width_m": top}
        if top - bottom < 0.040:
            failures.append(
                f"R4-F6 windshield ring lacks section growth: {name} {bottom}->{top}"
            )

    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    if glass is None or not bool(glass.get("s2_r4_f6_trapezoid_glass")):
        failures.append("R4-F6 trapezoid windshield glass marker missing")
    elif (
        float(glass.get("s2_r4_f6_top_width_m", 0.0))
        <= float(glass.get("s2_r4_f6_bottom_width_m", 0.0))
    ):
        failures.append("R4-F6 windshield glass is not wider at the top")

    report["r4_f6_headers"] = headers
    report["r4_f6_narrow_cab_surfaces"] = narrow_surfaces
    report["r4_f6_trapezoid_windshield"] = trapezoids
    report["failures"] = failures
    report["result"] = "PASS" if not failures else "FAIL"
    return report


preflight_r4.r4_visual_contract = visual_contract_f6


if __name__ == "__main__":
    preflight_r4.main()
