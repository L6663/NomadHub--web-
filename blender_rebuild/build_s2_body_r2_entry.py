"""Corrective entrypoint for the S2 R2 source-topology builder.

This keeps the R2 implementation reviewable while applying two validated
corrections before construction:
1. Correct the 13x13 cap-grid boundary offsets so corner vertices are not
   referenced twice.
2. Increase and support the source wheel-arch profile so Catmull-Clark
   evaluation remains clear of the frozen tires without Boolean cutters.
"""

import importlib.util
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
BUILDER_PATH = SCRIPT_DIR / "build_s2_body_r2.py"
SPEC = importlib.util.spec_from_file_location(
    "nomadhub_s2_r2_builder",
    BUILDER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load S2 R2 builder: {BUILDER_PATH}")

builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

# The frozen tire outer radius is approximately 0.415 m.  A 0.620 m source
# arch radius supplies adequate horizontal and vertical support after
# subdivision while remaining close to the accepted 1.02 m visual arch lip.
builder.ARCH_RADIUS_M = 0.620
builder.WHEEL_WELL_HALF_WIDTH_M = 0.620


def corrected_expanded_ring_xs():
    values = set(round(value, 3) for value in builder.BASE_RING_XS)
    for _, _, x_min, x_max, _, _, _ in builder.OPENINGS:
        center = (x_min + x_max) / 2
        for value in (
            x_min - 0.040,
            x_min,
            x_min + 0.040,
            center,
            x_max - 0.040,
            x_max,
            x_max + 0.040,
        ):
            if -4.495 < value < 4.495:
                values.add(round(value, 3))
    for center in (builder.FRONT_AXLE_X_M, builder.REAR_AXLE_X_M):
        for offset in (
            -0.660,
            -0.620,
            -0.580,
            -0.500,
            -0.400,
            -0.250,
            0.000,
            0.250,
            0.400,
            0.500,
            0.580,
            0.620,
            0.660,
        ):
            values.add(round(center + offset, 3))
    values.add(-4.495)
    values.add(4.495)
    return tuple(sorted(values))


def corrected_boundary_index(i, j):
    last = builder.GRID_N - 1
    if j == 0:
        return i
    if i == last:
        return last + j
    if j == last:
        # Bottom: 0..last, right: last+1..2*last,
        # therefore the first top vertex starts at 2*last+1.
        return (2 * last + 1) + (last - 1 - i)
    if i == 0:
        # The first left-side vertex starts after the top sequence.
        return (3 * last + 1) + (last - 1 - j)
    return None


builder.RING_XS = corrected_expanded_ring_xs()
builder.boundary_index = corrected_boundary_index

if __name__ == "__main__":
    builder.main()
