"""Fail-fast gate for R4-F4 using the explicit curve helper."""

import importlib.util
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PREFLIGHT_PATH = SCRIPT_DIR / "preflight_s2_body_r4_fix3.py"
PREFLIGHT_SPEC = importlib.util.spec_from_file_location(
    "nomadhub_s2_r4_f3_preflight", PREFLIGHT_PATH
)
if PREFLIGHT_SPEC is None or PREFLIGHT_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F3 preflight: {PREFLIGHT_PATH}")
preflight = importlib.util.module_from_spec(PREFLIGHT_SPEC)
PREFLIGHT_SPEC.loader.exec_module(preflight)

FIX_PATH = SCRIPT_DIR / "build_s2_body_r4_fix4.py"
FIX_SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix4", FIX_PATH)
if FIX_SPEC is None or FIX_SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F4 builder: {FIX_PATH}")
fixed = importlib.util.module_from_spec(FIX_SPEC)
FIX_SPEC.loader.exec_module(fixed)

preflight.fixed = fixed
preflight.r4 = fixed.r4
preflight.preflight_r4.r4_fixed = fixed
preflight.preflight_r4.r4 = fixed.r4
preflight.preflight_r4.preflight.fixed = fixed
preflight.preflight_r4.preflight.base.r3 = fixed.r4
preflight.preflight_r4.preflight.base.builder = fixed.builder
preflight.preflight_r4.preflight.base.entry = fixed.entry


if __name__ == "__main__":
    preflight.preflight_r4.main()
