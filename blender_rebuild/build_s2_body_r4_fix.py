"""R4 integration fixes for windshield dimensions and cab-door sweep clearance."""

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


def apply_dimension(obj, axis, value):
    dimensions = list(obj.dimensions)
    dimensions[axis] = value
    obj.dimensions = dimensions


def repair_cab_surround_clearance():
    """Keep the visible surround outside the complete animated door sweep.

    The R4 preflight proved that the new visible geometry was correct in count
    and placement, but its upper outer strip and three inner reveal strips
    touched the closed door panel. The door panel itself is frozen and already
    passes the body collision gate, so only the fixed frame is moved outward
    from the panel envelope:

    - outer top surround lower edge >= 35 mm above the door panel;
    - inner top reveal lower edge >= 20 mm above the panel;
    - front/rear reveals >= 15 mm beyond the panel X limits.
    """

    for side in ("L", "R"):
        outer_top = bpy.data.objects.get(f"R3_FRAME_CAB_DOOR_{side}_TOP")
        trim_top = bpy.data.objects.get(f"R4_CAB_DOOR_TRIM_{side}_TOP")
        trim_bottom = bpy.data.objects.get(f"R4_CAB_DOOR_TRIM_{side}_BOTTOM")
        trim_front = bpy.data.objects.get(f"R4_CAB_DOOR_TRIM_{side}_FRONT")
        trim_rear = bpy.data.objects.get(f"R4_CAB_DOOR_TRIM_{side}_REAR")
        required = (outer_top, trim_top, trim_bottom, trim_front, trim_rear)
        if any(obj is None for obj in required):
            raise RuntimeError(f"R4 cab surround objects missing on side {side}")

        # The animated panel top is z=2.095 m. The outer strip still covers the
        # source opening top at z=2.170 m while clearing the moving door.
        outer_top.location.z = 2.205
        apply_dimension(outer_top, 2, 0.150)

        # Thin dark reveal around, rather than through, the door panel envelope
        # x[-4.335,-3.945], z[0.525,2.095].
        trim_top.location.z = 2.125
        apply_dimension(trim_top, 2, 0.018)
        trim_bottom.location.z = 0.495
        apply_dimension(trim_bottom, 2, 0.018)
        trim_front.location.x = -4.365
        apply_dimension(trim_front, 0, 0.018)
        trim_rear.location.x = -3.915
        apply_dimension(trim_rear, 0, 0.018)

        for obj in required:
            obj["s2_r4_animation_clearance_fixed"] = True
        outer_top["s2_r4_min_door_clearance_m"] = 0.035
        trim_top["s2_r4_min_door_clearance_m"] = 0.021
        trim_front["s2_r4_min_door_clearance_m"] = 0.021
        trim_rear["s2_r4_min_door_clearance_m"] = 0.021


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

    repair_cab_surround_clearance()


r4.apply_r4_surface_repairs = apply_r4_surface_repairs_fixed


if __name__ == "__main__":
    r4.main()
