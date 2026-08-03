#!/usr/bin/env bash
set -euo pipefail

sed \
  -e 's/preflight_s2_body_r4.py/preflight_s2_body_r4_fix7b.py/g' \
  -e 's/build_s2_body_r4_fix.py/build_s2_body_r4_fix7b.py/g' \
  -e 's/validate_s2_body_r4.py/validate_s2_body_r4_fix7.py/g' \
  blender_rebuild/ci_s2_r4.sh | bash
