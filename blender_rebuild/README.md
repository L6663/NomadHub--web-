# NomadHub Real Blender Rebuild

This branch rebuilds a genuine Blender project from the existing S3 R3 GLB using Blender 4.2 LTS in GitHub Actions.

## What the artifact proves

- The `.blend` is saved by Blender itself.
- Scene units are meters.
- Imported semantic hierarchy is preserved.
- Blender-native modifiers are added to body, glass, doors, hatches, bumpers and mirrors.
- Blender Action data is created for doors, hatches, step and wheel rotation.
- A Blender-exported round-trip GLB and machine-readable manifest are included.

## Scope limitation

The source geometry originates from the S3 R3 programmatic GLB. This rebuild creates a real, editable Blender project, but does not claim the geometry was hand-retopologized or is already production-grade.