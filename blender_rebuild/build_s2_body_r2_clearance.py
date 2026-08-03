"""Wheel-well clearance correction for the S2-R2 true-opening cage.

The first true-opening build proved all 17 source openings, but the lower
wheel-well transition face still crossed the tire torus after subdivision.
This wrapper preserves the accepted opening topology and replaces only the
wheel-well section profile:

- a 0.72 m source arch controls the visible side opening;
- a clearance floor follows a 0.535 m circle around each frozen axle;
- the underbody is raised locally over each tire rather than spanning the
  tire with a diagonal side-to-floor quad;
- extra longitudinal support rings stabilize the profile through subdivision.
"""

import importlib.util
import json
import math
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ENTRY_PATH = SCRIPT_DIR / "build_s2_body_r2_entry.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r2_true_openings", ENTRY_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load S2 R2 true-opening entrypoint: {ENTRY_PATH}")

entry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(entry)
builder = entry.builder

SOURCE_ARCH_RADIUS_M = 0.720
WHEEL_WELL_INNER_HALF_WIDTH_M = 0.520
TIRE_CLEARANCE_PROFILE_RADIUS_M = 0.535
TIRE_CENTER_Z_M = 0.430
TIRE_CLEARANCE_MARGIN_M = 0.025

builder.ARCH_RADIUS_M = SOURCE_ARCH_RADIUS_M
builder.WHEEL_WELL_HALF_WIDTH_M = WHEEL_WELL_INNER_HALF_WIDTH_M


def nearest_axle_dx(x):
    return min(
        (abs(x - center), center)
        for center in (builder.FRONT_AXLE_X_M, builder.REAR_AXLE_X_M)
    )


def clearance_floor_height(x, z_low):
    dx, _center = nearest_axle_dx(x)
    if dx > TIRE_CLEARANCE_PROFILE_RADIUS_M:
        return z_low
    circle_height = TIRE_CENTER_Z_M + math.sqrt(
        max(0.0, TIRE_CLEARANCE_PROFILE_RADIUS_M ** 2 - dx ** 2)
    )
    return max(z_low, circle_height + TIRE_CLEARANCE_MARGIN_M)


def clearance_grid_boundary_points(x, width, z_low, z_top):
    half = width / 2
    lower_corner = min(0.120, half * 0.12)
    roof_corner = min(0.180, half * 0.18)
    levels = list(builder.remapped_z_levels(z_low, z_top))
    arch_height = builder.wheel_arch_height(x)
    floor_z = z_low

    bottom_left = -half + lower_corner
    bottom_right = half - lower_corner
    if arch_height is not None:
        floor_z = clearance_floor_height(x, z_low)
        bottom_left = -WHEEL_WELL_INNER_HALF_WIDTH_M
        bottom_right = WHEEL_WELL_INNER_HALF_WIDTH_M

        # The first three side levels form the wheel-well crown. Keeping all
        # of them above both the visible arch and the local underbody floor
        # prevents Catmull-Clark from pulling the transition back into the tire.
        levels[1] = max(levels[1], arch_height + 0.065, floor_z + 0.070)
        levels[2] = max(levels[2], arch_height + 0.125, levels[1] + 0.045)
        levels[3] = max(levels[3], arch_height + 0.185, levels[2] + 0.045)
        for index in range(4, len(levels)):
            levels[index] = max(levels[index], levels[index - 1] + 0.015)
        levels[-1] = z_top
        for index in range(len(levels) - 2, 0, -1):
            levels[index] = min(levels[index], levels[index + 1] - 0.015)

    points = []
    for index in range(builder.GRID_N):
        factor = index / (builder.GRID_N - 1)
        y = bottom_left + (bottom_right - bottom_left) * factor
        points.append((x, y, floor_z))

    for index in range(1, builder.GRID_N):
        z = levels[index]
        y = half
        if index == builder.GRID_N - 1:
            y = half - roof_corner
        points.append((x, y, z))

    roof_right = half - roof_corner
    roof_left = -half + roof_corner
    for index in range(builder.GRID_N - 2, -1, -1):
        factor = index / (builder.GRID_N - 1)
        y = roof_left + (roof_right - roof_left) * factor
        points.append((x, y, z_top))

    for index in range(builder.GRID_N - 2, 0, -1):
        points.append((x, -half, levels[index]))

    if len(points) != builder.RING_SIZE:
        raise RuntimeError(
            f"R2 clearance ring size {len(points)} != {builder.RING_SIZE}"
        )
    return points


def clearance_ring_xs():
    values = set(round(value, 3) for value in builder.RING_XS)
    for center in (builder.FRONT_AXLE_X_M, builder.REAR_AXLE_X_M):
        for offset in (
            -0.780,
            -0.720,
            -0.680,
            -0.600,
            -0.535,
            -0.480,
            -0.400,
            -0.300,
            -0.200,
            -0.100,
            0.000,
            0.100,
            0.200,
            0.300,
            0.400,
            0.480,
            0.535,
            0.600,
            0.680,
            0.720,
            0.780,
        ):
            value = center + offset
            if -4.495 < value < 4.495:
                values.add(round(value, 3))
    values.update((-4.495, 4.495))
    return tuple(sorted(values))


builder.RING_XS = clearance_ring_xs()
builder.grid_boundary_points = clearance_grid_boundary_points


def patch_clearance_manifest(path):
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["wheel_well_source_profile"] = {
        "visible_arch_radius_m": SOURCE_ARCH_RADIUS_M,
        "inner_half_width_m": WHEEL_WELL_INNER_HALF_WIDTH_M,
        "clearance_profile_radius_m": TIRE_CLEARANCE_PROFILE_RADIUS_M,
        "tire_center_z_m": TIRE_CENTER_Z_M,
        "clearance_margin_m": TIRE_CLEARANCE_MARGIN_M,
        "method": "source_topology_local_raised_floor",
    }
    payload["topology"]["ring_count"] = len(builder.RING_XS)
    payload["topology"]["ring_x_m"] = list(builder.RING_XS)
    payload["scope_note"] = (
        "S2-R2 contains 17 actual source-mesh openings, all-quad caps and "
        "source-topology wheel wells with a locally raised clearance floor. "
        "It remains a grey-model candidate pending automated and visual review."
    )
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    args = builder.parse_args()
    builder.main()
    entry.patch_manifest(args.manifest)
    patch_clearance_manifest(args.manifest)
