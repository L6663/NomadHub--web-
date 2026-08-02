#!/usr/bin/env bash
set -euo pipefail

# Reuse the single-entry R3 CI pipeline and substitute only the final
# integration-fixed preflight and builder entrypoints.
sed \
  -e 's/preflight_s2_body_r3_fix.py/preflight_s2_body_r3_fix3.py/g' \
  -e 's/build_s2_body_r3_fix.py/build_s2_body_r3_fix3.py/g' \
  blender_rebuild/ci_s2_r3.sh | bash
