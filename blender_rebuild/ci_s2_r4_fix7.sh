#!/usr/bin/env bash
set -euo pipefail

# Reuse the complete R4 pipeline with the F7 source-boundary builder, native
# opening/seal preflight and strict Blender/GLB F7 validator.
sed \
  -e 's/preflight_s2_body_r4.py/preflight_s2_body_r4_fix7.py/g' \
  -e 's/build_s2_body_r4_fix.py/build_s2_body_r4_fix7.py/g' \
  -e 's/validate_s2_body_r4.py/validate_s2_body_r4_fix7.py/g' \
  blender_rebuild/ci_s2_r4.sh | bash
