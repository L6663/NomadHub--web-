"""R4-F4 execution and closed-door clearance shim.

R4-F4 keeps the F3 windshield and wheel-arch presentation, provides the
missing curve-polyline helper explicitly, and corrects the cab annular skins so
they mask the source opening edge without entering either animated cab-door
shell. Frozen roots, 17 true openings and all Web animation names are unchanged.
"""

import importlib.util
from pathlib import Path

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
F3_PATH = SCRIPT_DIR / "build_s2_body_r4_fix3.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix3", F3_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F3 builder: {F3_PATH}")
f3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f3)

r4 = f3.r4
builder = f3.builder
entry = f3.entry
clearance = f3.clearance
WINDSHIELD_ROTATION_Y = f3.WINDSHIELD_ROTATION_Y
WINDSHIELD_PLANE_HEIGHT_M = f3.WINDSHIELD_PLANE_HEIGHT_M
WINDSHIELD_CENTER = f3.WINDSHIELD_CENTER


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
    obj["s2_r4_f4_explicit_curve_helper"] = True
    return obj


r4.make_curve_polyline = make_curve_polyline


def rebuild_cab_surface_rings_clear(body_root, body_material, trim_material):
    for name in (
        "R4_CAB_RING_L",
        "R4_CAB_RING_R",
        "R4_CAB_SEAM_L",
        "R4_CAB_SEAM_R",
    ):
        r4.remove_object(name)

    # Cab door shell occupies roughly 25-55 mm outside the nominal side skin.
    # Keep every body-fixed annular surface at or inside 19 mm, leaving at least
    # 6 mm closed-door clearance. Coverage comes from the broad X/Z annulus,
    # not by pushing the frame into the moving door volume.
    outer = (-4.440, -3.840, 0.390, 2.300)
    body_inner = (-4.380, -3.900, 0.485, 2.145)
    seam_outer = body_inner
    seam_inner = (-4.360, -3.920, 0.510, 2.120)
    for side, side_sign in (("L", -1.0), ("R", 1.0)):
        ring = f3.fix2.make_side_ring(
            f"R4_CAB_RING_{side}",
            side_sign,
            outer,
            body_inner,
            0.015,
            -0.006,
            body_material,
            body_root,
            0.007,
            "surface_aligned_body_surround",
        )
        seam = f3.fix2.make_side_ring(
            f"R4_CAB_SEAM_{side}",
            side_sign,
            seam_outer,
            seam_inner,
            0.019,
            0.015,
            trim_material,
            body_root,
            0.002,
            "surface_aligned_inner_seam",
        )
        ring["s2_r4_f3_source_edge_mask"] = True
        seam["s2_r4_f3_source_edge_mask"] = True
        ring["s2_r4_f4_max_outward_offset_m"] = 0.015
        seam["s2_r4_f4_max_outward_offset_m"] = 0.019
        ring["s2_r4_f4_min_closed_door_gap_m"] = 0.006
        seam["s2_r4_f4_min_closed_door_gap_m"] = 0.006


# apply_r4_f3_surface_repairs resolves this module global at execution time.
f3.rebuild_cab_surface_rings = rebuild_cab_surface_rings_clear


def main():
    f3.main()


if __name__ == "__main__":
    main()
