# NURION Body Motion Retarget & Rig Correction v0.5

## Final Seal Review

- Review date: 2026-08-13 (Asia/Seoul)
- Review verdict: `APPROVED_FOR_LIMITED_FINAL_SEAL`
- Seal execution: `PASS`
- Seal verdict: `SEALED_WITH_LIMITATIONS`
- Current `SEALED`: `TRUE`
- Supported domain: `LIMITED`
- Production: `NO-GO`
- RC.1: `FROZEN`; repackaging `DENY`; in-place repair `DENY`
- Prior `SEAL_DENY` (artifact set unavailable in review workspace): superseded by full-evidence re-verification

## Gate 10 Fresh Holdout

- Asset: `aibaeby-bow.zip` / Lightning Pilot / Formal Bow
- Verdict: `PASS_WITH_LIMITATIONS`
- Final seal review eligibility: `ELIGIBLE_FOR_FINAL_SEAL_REVIEW`
- Manual correction: `0`
- Asset-specific tuning: `0`
- Sibling ZIP inclusion: `DENY`

### Independently verified from the attached source

| Check | Result |
| --- | --- |
| ZIP SHA-256 | `3703b784072e791b999c2332fb4fff951e4997560ee7f92b5b49fdc743b3d54a` |
| ZIP compressed-data test | `PASS` |
| Formal Bow FBX count | `1` |
| FBX SHA-256 | `35470079f2ca6305688e793d5b9fe354cd49c18ed53c1e5b6c53b3735d867034` |
| Texture files | base color, metallic, normal, roughness (`4`) |
| Idle 15 / Gentleman's Bow mixed in | `0` |

### Accepted Gate 10 evidence

- Bone mapping, L/R and axes: `PASS`
- Joint, foot and mesh-penetration pipeline: `PASS`
- v0.4 `word_확인` face/eye synchronization at frames 90–135: `PASS`
- 24/30/60 FPS semantic preservation and three-run determinism: `PASS`
- Source ZIP/FBX/Action mutations: `0`
- Holdout residual foot slides: `9` (`HOLDOUT_FOOT_SLIDE_9`)
- Holdout mesh contact depth: `0.0 m`

The checks in this subsection are accepted from the supplied Gate 10 result. They were not recomputed in this review because the frozen RC.1 executable artifact, Blender scenes, action snapshots, v0.4 sealed artifact, and Gate 1–10 machine receipts were not present in the review workspace.

## Mandatory inherited limitations

The limited seal must disclose all of the following without suppression or automatic removal:

1. `FOOT_SLIDE_RESIDUAL_11`
2. `SHALLOW_SUSTAINED_CONTACT_ACCEPTED`
3. `GATE3_REVERSE_FOREARM_MILD_PRESERVED`
4. `HOLDOUT_FOOT_SLIDE_9`

`SHALLOW_SUSTAINED_CONTACT_ACCEPTED` remains an inherited seed limitation even though the Fresh Holdout contact depth was `0.0 m`.

## Baseline preservation

The following hashes are review locks and must not change during final seal execution:

| Baseline | SHA-256 |
| --- | --- |
| NURION Character Landmarker v0.2 | `679190e443d5814c6f7a7c41dcc7a62a52a0b02a6697e7485358d6a8853b02b2` |
| Universal Eye Calibration v0.3 RC.1 | `9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238` |
| Native Face Rig & Lip Sync v0.4 RC.1 | `10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5` |
| Body Motion Retarget v0.5 RC.1 | `1580f5871ba7737e34b0dfe99ef974aa7d3ed6b6656599aa51d08b8de5384722` |

## Review decision

Gate 1–10 evidence supported a limited final seal. A full/unqualified `PASS` remains denied because the seed and holdout residual limitations are still public. Final seal execution completed as `PASS` / `SEALED_WITH_LIMITATIONS` after full-evidence re-verification. Production remains `NO-GO`. No reprocessing, retuning, manual correction, or RC.1 repackaging is authorized.

Mismatch policy remains `SEAL_DENY_NO_IN_PLACE_REPAIR` for any future hash mismatch against the frozen baselines.

## Seal artifacts (2026-08-13)

| Artifact | Path |
| --- | --- |
| Final Seal Receipt | `dist/v0.5/V05_FINAL_SEAL_RECEIPT.json` |
| Baseline Lock | `dist/v0.5/V05_FINAL_BASELINE_LOCK.json` |
| Validation Status | `dist/v0.5/V05_VALIDATION_STATUS.json` |
| RC.1 package | `dist/v0.5/gate9/package/NURION_Body_Motion_Retarget_v0.5.0-rc.1.zip` |
