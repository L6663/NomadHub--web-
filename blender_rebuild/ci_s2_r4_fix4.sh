#!/usr/bin/env bash
set -euo pipefail

# Reuse the complete R4 pipeline with the F4 execution shim. Validation remains
# the R4-F3 contract because F4 changes no geometry or manifest semantics.
sed \
  -e 's/preflight_s2_body_r4.py/preflight_s2_body_r4_fix4.py/g' \
  -e 's/build_s2_body_r4_fix.py/build_s2_body_r4_fix4.py/g' \
  -e 's/validate_s2_body_r4.py/validate_s2_body_r4_fix3.py/g' \
  blender_rebuild/ci_s2_r4.sh | bash
