# Intent DNA — Post-V2 Hand Rig (Phase split)

- Base: `1b32c26` (`main`), 2026-09-09 KST.
- Upstream: NURION Adaptation Engine V2 = **CLOSED / PASS / CONSUME ONLY**. No reopen.
- Product context: Meshy rigged/skinned GLB → FACE + TALKING consume path already merged (PR #2). Hand/finger is **separate Post-V2 work**.

## Decision

Finger completion **must** split by input state. Difficulty differs sharply:

| Input state | Required work | Difficulty | Phase |
|-------------|---------------|------------|-------|
| Finger bones + weights OK | Name/axis normalize → motions | Medium | **P1** |
| Bones exist, names/axes differ | Auto map + axis repair | Med-High | **P1** |
| Bones exist, weights bad | Diagnose and block; no repair in HAND-01 | High | Later separate CR |
| No finger bones | Create bones + place + weights | Very High | **P2** |
| Fingers not separated in mesh | Geometry analysis / manual assets | Very High | **P2** |

**P1 first (realistic):** characters that **already have** finger bones → preserve BODY/FACE/TALKING → add wave/point/thumbs_up/fist/open.  
**P2 later:** auto bone generation + weight synthesis — separate CR, fail-closed if confidence low (Blender manual guide required).

## Order of work (do not skip)

1. Privately lock P01 axis/limit/confidence/tolerance methods from a rights-confirmed calibration set; no unsupported universal numeric threshold is allowed, and authority remains `NONE`.
2. After P01 lock only: Human **APPROVED** → `OPEN_PROTOTYPE` → `GRANTED` in order; then implement the hand-rig **diagnostic** (`DIRECT` / `ADAPTABLE` / `BLOCKED`).
3. Universal finger **mapper** (name + hierarchy + geometry; `AMBIGUOUS_FINGER_MAPPING` blocks).
4. Motion library (min set) + FACE/TALKING sync contract.
5. Independent QA gates: `HAND_RIG_PASS`, `HAND_MAPPING_PASS`, `HAND_WEIGHT_PASS` (existing-weight validation only), `HAND_MOTION_PASS`, `NEUTRAL_RETURN_PASS`, `BODY_PRESERVATION_PASS`, `FACE_TALKING_PRESERVATION_PASS`, and `GLB_RELOAD_PASS`.
6. CLI flags on sealed consume runner (`--add-hand-rig`, `--hand-motion`).
7. Only then open **HAND-02** (no-bone auto-create).

## Authority

- Change request: `POST-V2-CR-HAND-01`
- Human Spec Gate: **PENDING** (implementation **DENIED** until P01 calibration lock, then `APPROVED` + digest match → `OPEN_PROTOTYPE` → `GRANTED`)
- Samples: private only; redistribution rights required; digests in receipts, meshes not in public git

## R2 Spec Gate decision (2026-09-09)

- R1 is retained as an audit trail but superseded for new work by R2.
- R2 proposed SPEC digest: `965e3364b9d14061b4ee449caa716200a5c192614872266ba4f64195d626bfb8`, defined as SHA-256 of raw UTF-8/LF file bytes (not a Git object header or reserialization).
- `NURION_hand_L` / `NURION_hand_R` are upstream body-node names when present; semantic IDs are separate metadata and no upstream bone rename is allowed.
- P1 is append-only glTF animation work after authorization: source/body nodes, skins, IBMs, primitives, existing animations, FACE, and TALKING require a declared digest envelope. RIG-02, V05, V06, and V07 remain read-only.
- Concrete BLOCKED reasons include `NO_FINGER_BONES_HAND_UNIT_GESTURE_ONLY`, ambiguous mapping, unresolved hand skin/IBM, unacceptable existing weights, fused geometry, and preservation-envelope conflict. `HAND_WEIGHT_PASS` never permits repair.
- Future output is staging-only until all eight gates, reload, and private human visual receipt pass; atomic publish, rollback, and no-clobber are mandatory.
- Validation planned for this R2 document set: JSON parse, SHA-256 of R2 Git blob raw UTF-8/LF bytes, `git diff --check`, and lightweight pytest where available.

## Out of scope (this intent)

- Finger auto-create engine (HAND-02)
- Reopening V2 CR01–CR04 / IRG
- Publishing Meshy/user GLBs to public GitHub
