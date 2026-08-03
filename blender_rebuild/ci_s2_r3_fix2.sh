#!/usr/bin/env bash
set -euo pipefail

# Keep the validated single-entry CI logic in one file and substitute only the
# corrected R3 builder/preflight entrypoints for this iteration.
sed \
  -e 's/preflight_s2_body_r3_fix.py/preflight_s2_body_r3_fix2.py/g' \
  -e 's/build_s2_body_r3_fix.py/build_s2_body_r3_fix2.py/g' \
  blender_rebuild/ci_s2_r3.sh | bash
