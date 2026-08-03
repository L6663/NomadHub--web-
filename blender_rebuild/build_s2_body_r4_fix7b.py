"""R4-F7b corner correction for native cab opening boundaries.

F7 correctly snapped edge vertices but a geometric corner can be nearest to both
one vertical and one horizontal engineering boundary. The first pass selected
only one side, leaving the two lower corner rows at z=0.429687 m. This shim
allows a near-tie to constrain both axes, producing exact x/z corner positions
without changing topology, vertex count, opening count or presentation trim.
"""

import importlib.util
import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
F7_PATH = SCRIPT_DIR / "build_s2_body_r4_fix7.py"
SPEC = importlib.util.spec_from_file_location("nomadhub_s2_r4_fix7", F7_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load R4-F7 builder: {F7_PATH}")
f7 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f7)

r4 = f7.r4
builder = f7.builder
entry = f7.entry
clearance = f7.clearance
CAB_X_MIN = f7.CAB_X_MIN
CAB_X_MAX = f7.CAB_X_MAX
CAB_Z_MIN = f7.CAB_Z_MIN
CAB_Z_MAX = f7.CAB_Z_MAX
WINDSHIELD_ROTATION_Y = f7.WINDSHIELD_ROTATION_Y
WINDSHIELD_PLANE_HEIGHT_M = f7.WINDSHIELD_PLANE_HEIGHT_M
WINDSHIELD_CENTER = f7.WINDSHIELD_CENTER


def snap_cab_opening_boundaries_dual_axis(body):
    mesh = body.data
    reports = []
    x_span = CAB_X_MAX - CAB_X_MIN
    z_span = CAB_Z_MAX - CAB_Z_MIN
    near_tie = 0.020

    for component, before in f7.find_cab_components(mesh):
        side_sign = -1.0 if before["y_mean"] < 0.0 else 1.0
        side_counts = {"front": 0, "rear": 0, "bottom": 0, "top": 0}
        corner_vertices = 0
        for index in component:
            vertex = mesh.vertices[index]
            x = float(vertex.co.x)
            z = float(vertex.co.z)
            distances = {
                "front": abs(x - CAB_X_MIN) / x_span,
                "rear": abs(x - CAB_X_MAX) / x_span,
                "bottom": abs(z - CAB_Z_MIN) / z_span,
                "top": abs(z - CAB_Z_MAX) / z_span,
            }
            minimum = min(distances.values())
            selected = {
                side for side, distance in distances.items()
                if distance <= minimum + near_tie
            }

            # At most one constraint per axis can be selected for this opening.
            if "front" in selected and "rear" in selected:
                selected.remove("rear" if distances["front"] <= distances["rear"] else "front")
            if "bottom" in selected and "top" in selected:
                selected.remove("top" if distances["bottom"] <= distances["top"] else "bottom")

            if "front" in selected:
                vertex.co.x = CAB_X_MIN
                side_counts["front"] += 1
            elif "rear" in selected:
                vertex.co.x = CAB_X_MAX
                side_counts["rear"] += 1
            if "bottom" in selected:
                vertex.co.z = CAB_Z_MIN
                side_counts["bottom"] += 1
            elif "top" in selected:
                vertex.co.z = CAB_Z_MAX
                side_counts["top"] += 1
            if len(selected) == 2:
                corner_vertices += 1

            x_after = float(vertex.co.x)
            vertex.co.y = side_sign * builder.section_dimensions(x_after)[0] / 2.0

        reports.append(
            {
                "side": "L" if side_sign < 0 else "R",
                "before": before,
                "snapped_vertices": len(component),
                "dual_axis_corner_vertices": corner_vertices,
                "side_counts": side_counts,
            }
        )

    mesh.update(calc_edges=True)
    body["s2_r4_f7_native_cab_boundary_repair"] = True
    body["s2_r4_f7_cab_boundary_count"] = 2
    body["s2_r4_f7b_dual_axis_corner_snap"] = True
    body["s2_r4_f7_cab_boundary_target"] = json.dumps(
        {
            "x_min_m": CAB_X_MIN,
            "x_max_m": CAB_X_MAX,
            "z_min_m": CAB_Z_MIN,
            "z_max_m": CAB_Z_MAX,
        }
    )
    body["s2_r4_f7_cab_boundary_report"] = json.dumps(reports)
    return reports


f7.snap_cab_opening_boundaries = snap_cab_opening_boundaries_dual_axis


def patch_manifest(path):
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload.setdefault("r4_visual_repairs", {}).update(
        {
            "cab_corner_dual_axis_snap": True,
            "cab_corner_snap_near_tie_normalized": 0.020,
        }
    )
    payload["stage_status"] = "R4_F7B_NATIVE_BOUNDARY_CORNER_CORRECTED_CANDIDATE"
    payload["r4_fix_iteration"] = "F7b"
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    f7.main()
    args = builder.parse_args()
    patch_manifest(args.manifest)
    print("NOMADHUB_S2_R4_F7B_DUAL_AXIS_CORNER_SNAP_OK")


if __name__ == "__main__":
    main()
