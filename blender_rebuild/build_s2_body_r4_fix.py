"""R4 integration fix: bake the inset windshield dimensions into its mesh."""

import importlib.util
from pathlib import Path

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
R4_PATH = SCRIPT_DIR / "build_s2_body_r4.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4", R4_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R4 builder: {R4_PATH}")
r4 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r4)
builder = r4.builder
entry = r4.entry
clearance = r4.clearance


ORIGINAL_APPLY = r4.apply_r4_surface_repairs


def apply_r4_surface_repairs_fixed():
    ORIGINAL_APPLY()
    glass = bpy.data.objects.get("GLASS_WINDSHIELD")
    if glass is None:
        raise RuntimeError("R4 inset windshield missing")
    glass.dimensions = (0.040, 1.70, 0.68)
    bpy.context.view_layer.objects.active = glass
    glass.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    glass.select_set(False)
    glass["s2_r4_dimensions_baked"] = True


r4.apply_r4_surface_repairs = apply_r4_surface_repairs_fixed


if __name__ == "__main__":
    r4.main()
