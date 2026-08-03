#!/usr/bin/env bash
set -euo pipefail

# Reuse the complete R4 build/export pipeline with the F6 builder, fail-fast
# cab-header/trapezoid checks and strict native/GLB F6 validation.
sed \
  -e 's/preflight_s2_body_r4.py/preflight_s2_body_r4_fix6.py/g' \
  -e 's/build_s2_body_r4_fix.py/build_s2_body_r4_fix6.py/g' \
  -e 's/validate_s2_body_r4.py/validate_s2_body_r4_fix6.py/g' \
  blender_rebuild/ci_s2_r4.sh | bash
