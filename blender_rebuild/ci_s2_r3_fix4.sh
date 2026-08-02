#!/usr/bin/env bash
set -euo pipefail

# Reuse the validated R3 CI pipeline with the visual-cleanup entrypoints.
sed \
  -e 's/preflight_s2_body_r3_fix.py/preflight_s2_body_r3_fix4.py/g' \
  -e 's/build_s2_body_r3_fix.py/build_s2_body_r3_fix4.py/g' \
  blender_rebuild/ci_s2_r3.sh | bash
