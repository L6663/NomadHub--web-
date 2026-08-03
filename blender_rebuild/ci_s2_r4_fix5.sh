#!/usr/bin/env bash
set -euo pipefail

# Reuse the complete R4 pipeline with the F5 builder, strict fail-fast surface
# contract and native/GLB F5 validator.
sed \
  -e 's/preflight_s2_body_r4.py/preflight_s2_body_r4_fix5.py/g' \
  -e 's/build_s2_body_r4_fix.py/build_s2_body_r4_fix5.py/g' \
  -e 's/validate_s2_body_r4.py/validate_s2_body_r4_fix5.py/g' \
  blender_rebuild/ci_s2_r4.sh | bash
