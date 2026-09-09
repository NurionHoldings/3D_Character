# Post-V2 Meshy GLB local consume E2E (PR #2 hardening)

## Intent

Provide a **sealed-consume** local path for one new Meshy-style rigged+skinned `.glb`:
CR01 semantic adapt → GAP-01 facial resolve → FACE morphs → TALKING inject → report.
Does **not** reopen NURION Adaptation Engine V2.

## Sporty smoke (digest-only; no paths / no mesh bytes)

| Gate | Result |
|------|--------|
| Local E2E on Sporty baseline pin | PASS |
| FACE derived digest | `92502f6f66b82c4dc1a7138b90746b4b0e755e6e857de0c2390ae9ef6320f51a` |
| FACE+TALKING derived digest | `55601949d6fc67eaebe405e683134fc516be5d6374ca748ea8809ae12dbace4d` |
| Source baseline digest | `f3f9e343c8ba3c9a503a8423293dec90bb6be50f809f1321f4f6658b1bea133e` |
| Sporty SHA hard-pin in runner | REMOVED (any new Meshy GLB accepted structurally) |

## Fail-closed contracts (PR audit follow-up)

- `INPUT_MISSING` / `INPUT_NOT_GLB` / `INVALID_GLB_HEADER` / `UNSUPPORTED_GLB_VERSION` / `INVALID_GLB_LENGTH`
- `INPUT_TOO_LARGE` (max 512 MiB)
- `OUTPUT_ALREADY_EXISTS` — no clobber of prior FACE/TALKING/report/source copy
- `TALKING_INJECT_FAIL` / `TALKING_GLB_LOAD_FAIL` / `TALKING_BLOB_MISSING` — stop immediately
- `SOURCE_MUTATED` — input bytes must be unchanged after consume
- Reports use **fileName + sha256 + bytes** only (no absolute paths)

## Support limits (conditional)

| Supported (envelope) | Not claimed |
|----------------------|-------------|
| Meshy-style GLB, skin + body rig | Arbitrary topology / all Meshy characters |
| FACE morph augmentation + VISEME AA/OH/EE talking clip | Native ARKit 52 / phoneme lip-sync |
| Structure-conditional success | Finger-per-bone / hand gesture library |
| Local sealed consume CLI | FBX input (Post-V2 format adapter CR) |

## Public vs private

- **Public:** runner source, tests, this intent note, digests in receipts
- **Private:** Meshy meshes, `dist/v2_consume/*` GLBs, local absolute paths in operator reports

## Runner

`tools/run_v2_consume_meshy_glb.py`

## CI #8 RED → NumPy dependency fix

| Item | Detail |
|------|--------|
| Failure | CI #8 RED — `ModuleNotFoundError: No module named 'numpy'` (13 passed, 8 errors) on Python 3.10 and 3.12 |
| Cause | New E2E tests import sealed consume path → `fast_track.v2_cr02.facial_deformation` needs NumPy; local env had it, CI installed pytest only |
| Fix | `pyproject.toml` `[project.optional-dependencies].test` adds `numpy>=1.24`; workflow installs `pytest numpy` |
| Merge | Remains HOLD until new HEAD CI is GREEN |
