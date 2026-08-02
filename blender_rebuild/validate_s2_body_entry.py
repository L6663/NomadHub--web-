"""S2 validator entrypoint bound to the currently frozen S1C source.

The accepted/reproducible S1C generator on main places the driver and front
passenger door hinge roots at X=-4.400 m.  validate_s2_body.py still contains
the older pre-closure value -4.020 m.  Keep the core validator unchanged and
apply the authoritative frozen anchors here before executing it.
"""

import importlib.util
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR_PATH = SCRIPT_DIR / "validate_s2_body.py"
SPEC = importlib.util.spec_from_file_location(
    "nomadhub_validate_s2_body",
    VALIDATOR_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load S2 validator: {VALIDATOR_PATH}")

validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)

validator.EXPECTED_FROZEN_ROOT_X.update(
    {
        "DOOR_DRIVER_L_ROOT": -4.400,
        "DOOR_PASSENGER_R_ROOT": -4.400,
    }
)

if __name__ == "__main__":
    validator.main()
