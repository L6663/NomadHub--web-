#!/usr/bin/env bash
set -euo pipefail

BLENDER="./blender-4.2.0-linux-x64/blender"
SOURCE_DIR="build/source"
OUTPUT_DIR="build/output"
mkdir -p "${SOURCE_DIR}" "${OUTPUT_DIR}"
export LIBGL_ALWAYS_SOFTWARE=1

# 1. Rebuild the accepted S1C source without expensive proof renders.
"${BLENDER}" \
  --background \
  --python blender_rebuild/build_real_blend.py \
  -- \
  --output "${SOURCE_DIR}/NomadHub_General3_V1.7_S1C_SOURCE.blend" \
  --roundtrip "${SOURCE_DIR}/NomadHub_General3_V1.7_S1C_SOURCE.glb" \
  --manifest "${SOURCE_DIR}/S1C_SOURCE_MANIFEST.json" \
  --preview "${SOURCE_DIR}/S1C_SOURCE_Preview.png" \
  --clearance "${SOURCE_DIR}/S1C_Collision_Clearance.json"

"${BLENDER}" \
  --background "${SOURCE_DIR}/NomadHub_General3_V1.7_S1C_SOURCE.blend" \
  --python blender_rebuild/finalize_s1c_hierarchy.py \
  -- \
  --blend "${SOURCE_DIR}/NomadHub_General3_V1.7_S1C_SOURCE.blend" \
  --roundtrip "${SOURCE_DIR}/NomadHub_General3_V1.7_S1C_SOURCE.glb" \
  --manifest "${SOURCE_DIR}/S1C_SOURCE_MANIFEST.json" \
  --preview "${SOURCE_DIR}/S1C_SOURCE_Preview.png" \
  --skip-proofs

test -s "${SOURCE_DIR}/NomadHub_General3_V1.7_S1C_SOURCE.blend"
test -s "${SOURCE_DIR}/S1C_SOURCE_MANIFEST.json"
test -s "${SOURCE_DIR}/S1C_Collision_Clearance.json"
cp "${SOURCE_DIR}/S1C_SOURCE_MANIFEST.json" "${OUTPUT_DIR}/S2_R4_BUILD_MANIFEST.json"
cp "${SOURCE_DIR}/S1C_Collision_Clearance.json" "${OUTPUT_DIR}/S1C_Collision_Clearance.json"

# 2. Fail fast before evidence rendering. Includes the complete moving-panel
# sweep against the new windshield, cab-surround and wheel-lip surfaces.
"${BLENDER}" \
  --background "${SOURCE_DIR}/NomadHub_General3_V1.7_S1C_SOURCE.blend" \
  --python blender_rebuild/preflight_s2_body_r4.py \
  -- \
  --report "${OUTPUT_DIR}/S2_R4_PREFLIGHT_REPORT.json"

python - <<'PY'
import json
from pathlib import Path
report = json.loads(Path("build/output/S2_R4_PREFLIGHT_REPORT.json").read_text())
assert report["status"] == "PASS"
assert report["iteration"] == "R4"
assert report["opening_boundaries"]["loop_count"] == 17
assert report["opening_boundaries"]["closed_loop_count"] == 17
assert report["wheel_body_clearance"]["result"] == "PASS"
assert report["animation_collision_sweep"]["result"] == "PASS"
assert report["r4_visual_contract"]["result"] == "PASS"
print("S2_R4_FAIL_FAST_GATE_PASS")
PY

# 3. Build Blender/GLB and all R4 visual evidence only after preflight passes.
"${BLENDER}" \
  --background "${SOURCE_DIR}/NomadHub_General3_V1.7_S1C_SOURCE.blend" \
  --python blender_rebuild/build_s2_body_r4_fix.py \
  -- \
  --output "${OUTPUT_DIR}/NomadHub_General3_V1.7_S2_R4.blend" \
  --roundtrip "${OUTPUT_DIR}/NomadHub_General3_V1.7_S2_R4.glb" \
  --manifest "${OUTPUT_DIR}/S2_R4_BUILD_MANIFEST.json" \
  --preview "${OUTPUT_DIR}/S2_R4_Preview.png" \
  --left "${OUTPUT_DIR}/S2_R4_Left_Orthographic.png" \
  --right "${OUTPUT_DIR}/S2_R4_Right_Orthographic.png" \
  --top "${OUTPUT_DIR}/S2_R4_Top_Orthographic.png" \
  --wire-left "${OUTPUT_DIR}/S2_R4_Left_Wireframe.png" \
  --wire-right "${OUTPUT_DIR}/S2_R4_Right_Wireframe.png"

for file in \
  NomadHub_General3_V1.7_S2_R4.blend \
  NomadHub_General3_V1.7_S2_R4.glb \
  S2_R4_Preview.png \
  S2_R4_Left_Orthographic.png \
  S2_R4_Right_Orthographic.png \
  S2_R4_Top_Orthographic.png \
  S2_R4_Left_Wireframe.png \
  S2_R4_Right_Wireframe.png \
  S2_R4_Front_Closeup.png \
  S2_R4_Wheel_Closeup.png \
  S2_R4_Zebra_Left.png \
  S2_R4_Zebra_Right.png \
  S2_R4_BUILD_MANIFEST.json \
  S2_R4_PREFLIGHT_REPORT.json \
  S1C_Collision_Clearance.json; do
  test -s "${OUTPUT_DIR}/${file}"
done

if compgen -G "${OUTPUT_DIR}/*.blend1" > /dev/null; then
  echo "Unexpected Blender backup file in S2 R4 delivery"
  exit 1
fi

# 4. Strict native/GLB, true-opening, Web-interface and animation validation.
"${BLENDER}" \
  --background "${OUTPUT_DIR}/NomadHub_General3_V1.7_S2_R4.blend" \
  --python-expr "import sys; sys.path.insert(0, r'${GITHUB_WORKSPACE}/blender_rebuild')" \
  --python blender_rebuild/validate_s2_body_r4.py \
  -- \
  --glb "${OUTPUT_DIR}/NomadHub_General3_V1.7_S2_R4.glb" \
  --clearance "${OUTPUT_DIR}/S1C_Collision_Clearance.json" \
  --manifest "${OUTPUT_DIR}/S2_R4_BUILD_MANIFEST.json" \
  --report "${OUTPUT_DIR}/S2_R4_VERIFICATION_REPORT.json"

python - <<'PY'
import hashlib
import json
from pathlib import Path

manifest_path = Path("build/output/S2_R4_BUILD_MANIFEST.json")
report_path = Path("build/output/S2_R4_VERIFICATION_REPORT.json")
preflight_path = Path("build/output/S2_R4_PREFLIGHT_REPORT.json")
manifest = json.loads(manifest_path.read_text())
report = json.loads(report_path.read_text())
preflight = json.loads(preflight_path.read_text())

assert preflight["status"] == "PASS"
assert preflight["animation_collision_sweep"]["result"] == "PASS"
assert manifest["stage"] == "S2"
assert manifest["iteration"] == "R4"
assert manifest["body_object"] == "BODY_S2_CONTROL_CAGE"
assert manifest["actions"] >= 13
assert manifest["topology"]["ring_count"] >= 55
assert manifest["topology"]["ring_size"] >= 80
assert manifest["topology"]["quad_ratio"] == 1.0
assert manifest["topology"]["triangles"] == 0
assert manifest["topology"]["ngons"] == 0
assert manifest["modifier_types"] == ["SUBSURF", "BEVEL"]
assert manifest["source_wheel_arch_topology"] is True
assert manifest["all_quad_caps"] is True
assert manifest["source_true_openings"] is True
assert manifest["true_opening_count"] == 17
assert len(manifest["true_openings"]) == 17
assert manifest["r4_visual_repairs"]["continuous_windshield_surround"] is True
assert manifest["r4_visual_repairs"]["continuous_windshield_inner_trim"] is True
assert manifest["r4_visual_repairs"]["cab_door_body_surrounds"] == 2
assert manifest["r4_visual_repairs"]["cab_door_inner_trim_sets"] == 2
assert manifest["r4_visual_repairs"]["integrated_visual_wheel_lips"] == 4
assert manifest["r4_visual_repairs"]["source_openings_unchanged"] is True
assert manifest["r4_visual_repairs"]["web_node_and_animation_contract_preserved"] is True
assert report["status"] == "PASS"
assert report["s2_r4_ready_for_manual_visual_review"] is True
assert report["s2_accepted"] is False
assert report["blend_visual_contract"]["result"] == "PASS"
assert report["glb_visual_contract"]["result"] == "PASS"
assert report["blend_body"]["wheel_body_clearance"]["result"] == "PASS"
assert report["glb_body"]["wheel_body_clearance"]["result"] == "PASS"
assert report["blend_body"]["true_opening_topology"]["result"] == "PASS"
assert report["blend_body"]["true_opening_rays"]["result"] == "PASS"
assert report["glb_body"]["true_opening_rays"]["result"] == "PASS"
assert report["blend_s1c_compatibility"]["animation_collision_sweep"]["result"] == "PASS"
assert report["glb_s1c_compatibility"]["animation_collision_sweep"]["result"] == "PASS"

manifest["stage_status"] = "R4_TECHNICALLY_VALIDATED_MANUAL_VISUAL_REVIEW_REQUIRED"
manifest["s2_r4_ready_for_manual_visual_review"] = True
manifest["preflight_report"] = preflight_path.name
manifest["preflight_sha256"] = hashlib.sha256(preflight_path.read_bytes()).hexdigest()
manifest["verification_report"] = report_path.name
manifest["verification_sha256"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print("S2_R4_WEB_SURFACE_CANDIDATE_VALIDATED")
PY

(
  cd "${OUTPUT_DIR}"
  sha256sum \
    NomadHub_General3_V1.7_S2_R4.blend \
    NomadHub_General3_V1.7_S2_R4.glb \
    S1C_Collision_Clearance.json \
    S2_R4_BUILD_MANIFEST.json \
    S2_R4_PREFLIGHT_REPORT.json \
    S2_R4_Left_Orthographic.png \
    S2_R4_Left_Wireframe.png \
    S2_R4_Preview.png \
    S2_R4_Right_Orthographic.png \
    S2_R4_Right_Wireframe.png \
    S2_R4_Top_Orthographic.png \
    S2_R4_Front_Closeup.png \
    S2_R4_Wheel_Closeup.png \
    S2_R4_Zebra_Left.png \
    S2_R4_Zebra_Right.png \
    S2_R4_VERIFICATION_REPORT.json \
    > SHA256SUMS.txt
  sha256sum -c SHA256SUMS.txt
)
