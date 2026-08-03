#!/usr/bin/env bash
set -euo pipefail

# Reuse the complete R4 build/export pipeline with the F8 cab-panel and
# glass-hugging windshield-seal repair, fail-fast gate, and strict native/GLB
# validation.
sed \
  -e 's/preflight_s2_body_r4.py/preflight_s2_body_r4_fix8.py/g' \
  -e 's/build_s2_body_r4_fix.py/build_s2_body_r4_fix8.py/g' \
  -e 's/validate_s2_body_r4.py/validate_s2_body_r4_fix8.py/g' \
  blender_rebuild/ci_s2_r4.sh | bash
