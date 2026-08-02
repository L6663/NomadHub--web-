"""S2-R1 validation entrypoint bound to the accepted S1C hinge anchors.

The core validator is kept reusable. This entrypoint freezes stage-specific
engineering anchors that were accepted in S1C before running the full topology,
clearance, animation and round-trip gates.
"""

import importlib.util
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
CORE_PATH = SCRIPT_DIR / "validate_s2_body.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_validate_s2_body", CORE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load S2 validator core: {CORE_PATH}")

core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(core)

# Accepted S1C hinge-root coordinates. These are not the door panel centers.
core.EXPECTED_FROZEN_ROOT_X.update(
    {
        "DOOR_DRIVER_L_ROOT": -4.400,
        "DOOR_PASSENGER_R_ROOT": -4.400,
    }
)


if __name__ == "__main__":
    core.main()
