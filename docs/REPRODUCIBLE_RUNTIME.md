# Post-V2 portable runtime and verification

The frozen V2 adaptation engine, CR01–CR04 evidence, the entire v0.6 Gate 6
source, v0.5/v0.6 seals and receipts, V07, and CCS PASS artifacts are
consume-only. This document covers only the separate Post-V2 runtime layer.

## Local verification

```bash
python -m pip install -e '.[test]'
python -m compileall -q nurion_post_v2_runtime nurion_character_landmarker/profiles
python -m pytest tests/test_post_v2_runtime.py
```

No Blender executable is required for the contract and state-machine suite.
For Blender smoke work, set `NURION_BLENDER_BIN` to an installed executable.
Never add a workstation path to source control.

## Paths and I/O policy

- The caller supplies a dedicated export root for each Post-V2 transaction.
- Post-V2 accepts a readable regular `.fbx` no larger than 512 MiB.
- Exports must remain inside the export root, match the chosen FBX/GLB format,
  and must not overwrite an existing artifact.
- Blender exports first to an in-root temporary file and publishes with an
  atomic no-clobber link only after the exporter returns `FINISHED`.

## Blender workflow safety

The new operator ID is `nurion_post_v2.precheck_import`; it performs
`PRECHECK → IMPORT_TRANSACTION → SELECT_COMMIT` and records path, size, SHA-256,
and imported-object provenance. On import failure it rolls back every new
tracked Blender data block. Source authority requires one explicit or uniquely
resolvable armature plus a skinned mesh; ambiguity aborts.

The historical full suite is not treated as a green baseline in a fresh clone:
the locked V07 canonical fixtures are absent from Git and one historical test
imports OpenCV without declaring it. Those independent baseline gaps are left
unchanged; the workflow runs the complete portable Post-V2 contract suite.

The Blender CI job is deliberately **skipped** unless `NURION_BLENDER_CI=true`.
It becomes a hard failure if configured but Blender is absent; a skipped job is
an explicit validation gap, not evidence of Blender-scene success.
