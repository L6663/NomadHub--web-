"""Run the extended R3 preflight against the second integration fix."""

import importlib.util
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PREFLIGHT_PATH = SCRIPT_DIR / "preflight_s2_body_r3_fix.py"
PREFLIGHT_SPEC = importlib.util.spec_from_file_location(
    "nomadhub_s2_r3_extended_preflight", PREFLIGHT_PATH
)
if PREFLIGHT_SPEC is None or PREFLIGHT_SPEC.loader is None:
    raise RuntimeError(f"unable to load extended R3 preflight: {PREFLIGHT_PATH}")
preflight = importlib.util.module_from_spec(PREFLIGHT_SPEC)
PREFLIGHT_SPEC.loader.exec_module(preflight)

FIX_PATH = SCRIPT_DIR / "build_s2_body_r3_fix2.py"
FIX_SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r3_fix2", FIX_PATH)
if FIX_SPEC is None or FIX_SPEC.loader is None:
    raise RuntimeError(f"unable to load second R3 fix: {FIX_PATH}")
fixed = importlib.util.module_from_spec(FIX_SPEC)
FIX_SPEC.loader.exec_module(fixed)

preflight.fixed = fixed
preflight.base.r3 = fixed.r3
preflight.base.builder = fixed.builder
preflight.base.entry = fixed.entry


if __name__ == "__main__":
    preflight.main()
