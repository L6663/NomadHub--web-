#!/usr/bin/env bash
set -euo pipefail

BLENDER="./blender-4.2.0-linux-x64/blender"
OUTPUT_DIR="build/output"
mkdir -p "${OUTPUT_DIR}"
export LIBGL_ALWAYS_SOFTWARE=1

"${BLENDER}" \
  --background \
  --python blender_rebuild/build_real_blend.py \
  -- \
  --output "${OUTPUT_DIR}/NomadHub_General3_V1.7_S1C.blend" \
  --roundtrip "${OUTPUT_DIR}/NomadHub_General3_V1.7_S1C_Roundtrip.glb" \
  --manifest "${OUTPUT_DIR}/BLENDER_BUILD_MANIFEST.json" \
  --preview "${OUTPUT_DIR}/NomadHub_General3_V1.7_S1C_Preview.png" \
  --clearance "${OUTPUT_DIR}/S1C_Collision_Clearance.json"

"${BLENDER}" \
  --background "${OUTPUT_DIR}/NomadHub_General3_V1.7_S1C.blend" \
  --python blender_rebuild/finalize_s1c_hierarchy.py \
  -- \
  --blend "${OUTPUT_DIR}/NomadHub_General3_V1.7_S1C.blend" \
  --roundtrip "${OUTPUT_DIR}/NomadHub_General3_V1.7_S1C_Roundtrip.glb" \
  --manifest "${OUTPUT_DIR}/BLENDER_BUILD_MANIFEST.json" \
  --preview "${OUTPUT_DIR}/NomadHub_General3_V1.7_S1C_Preview.png"

for file in \
  NomadHub_General3_V1.7_S1C.blend \
  NomadHub_General3_V1.7_S1C_Roundtrip.glb \
  NomadHub_General3_V1.7_S1C_Preview.png \
  S1C_Left_Orthographic.png \
  S1C_Right_Orthographic.png \
  S1C_Top_Orthographic.png \
  S1C_Left_Open.png \
  S1C_Right_Open.png \
  BLENDER_BUILD_MANIFEST.json \
  S1C_Collision_Clearance.json; do
  test -s "${OUTPUT_DIR}/${file}"
done

if compgen -G "${OUTPUT_DIR}/*.blend1" > /dev/null; then
  echo "Unexpected Blender backup file in delivery artifact"
  exit 1
fi

"${BLENDER}" \
  --background "${OUTPUT_DIR}/NomadHub_General3_V1.7_S1C.blend" \
  --python blender_rebuild/validate_s1c.py \
  -- \
  --glb "${OUTPUT_DIR}/NomadHub_General3_V1.7_S1C_Roundtrip.glb" \
  --clearance "${OUTPUT_DIR}/S1C_Collision_Clearance.json" \
  --report "${OUTPUT_DIR}/S1C_VERIFICATION_REPORT.json"

"${BLENDER}" \
  --background "${OUTPUT_DIR}/NomadHub_General3_V1.7_S1C.blend" \
  --python blender_rebuild/validate_s1c_hierarchy.py \
  -- \
  --glb "${OUTPUT_DIR}/NomadHub_General3_V1.7_S1C_Roundtrip.glb" \
  --report "${OUTPUT_DIR}/S1C_VERIFICATION_REPORT.json"

python - <<'PY'
import hashlib
import json
from pathlib import Path

manifest_path = Path("build/output/BLENDER_BUILD_MANIFEST.json")
verification_path = Path("build/output/S1C_VERIFICATION_REPORT.json")
clearance_path = Path("build/output/S1C_Collision_Clearance.json")
manifest = json.loads(manifest_path.read_text())
clearance = json.loads(clearance_path.read_text())
verification = json.loads(verification_path.read_text())

assert manifest["artifact_type"] == "genuine_blender_native_project"
assert manifest["stage"] == "S1C"
assert manifest["blender_version"].startswith("4.2")
assert manifest["actions"] >= 13
assert manifest["wheelbase_m"] == 5.15
assert manifest["door_glass_hierarchy"] == {
    "DOOR_DRIVER_L_GLASS": "DOOR_DRIVER_L_ROOT",
    "DOOR_PASSENGER_R_GLASS": "DOOR_PASSENGER_R_ROOT",
    "DOOR_LIVING_R_GLASS": "DOOR_LIVING_R_ROOT",
}
assert clearance["result"] == "PASS"
assert verification["result"] == "PASS"
assert verification["s2_ready"] is True
assert verification["door_glass_hierarchy"]["result"] == "PASS"

manifest["stage_status"] = "ACCEPTED"
manifest["s2_ready"] = True
manifest["verification_report"] = verification_path.name
manifest["verification_sha256"] = hashlib.sha256(verification_path.read_bytes()).hexdigest()
manifest["clearance_sha256"] = hashlib.sha256(clearance_path.read_bytes()).hexdigest()
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print("S1C_MANIFEST_AND_GATE_VALIDATED")
PY

(
  cd "${OUTPUT_DIR}"
  sha256sum \
    BLENDER_BUILD_MANIFEST.json \
    NomadHub_General3_V1.7_S1C.blend \
    NomadHub_General3_V1.7_S1C_Preview.png \
    NomadHub_General3_V1.7_S1C_Roundtrip.glb \
    S1C_Collision_Clearance.json \
    S1C_Left_Open.png \
    S1C_Left_Orthographic.png \
    S1C_Right_Open.png \
    S1C_Right_Orthographic.png \
    S1C_Top_Orthographic.png \
    S1C_VERIFICATION_REPORT.json \
    > SHA256SUMS.txt
  sha256sum -c SHA256SUMS.txt
)
