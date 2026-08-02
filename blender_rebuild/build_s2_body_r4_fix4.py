"""R4-F4 execution shim: provide the missing curve-polyline helper.

R4-F3 geometry is unchanged. The previous run stopped before preflight because
R4-F2 called ``r4.make_curve_polyline`` even though the base R4 module did not
export that helper. This shim makes the dependency explicit and self-contained.
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


def main():
    f3.main()


if __name__ == "__main__":
    main()
