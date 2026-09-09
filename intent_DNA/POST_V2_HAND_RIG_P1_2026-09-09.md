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
| Bones exist, weights bad | Weight repair | High | P1 partial / later |
| No finger bones | Create bones + place + weights | Very High | **P2** |
| Fingers not separated in mesh | Geometry analysis / manual assets | Very High | **P2** |

**P1 first (realistic):** characters that **already have** finger bones → preserve BODY/FACE/TALKING → add wave/point/thumbs_up/fist/open.  
**P2 later:** auto bone generation + weight synthesis — separate CR, fail-closed if confidence low (Blender manual guide required).

## Order of work (do not skip)

1. Lock NURION hand bone standard + limits (this CR SPEC).
2. Hand-rig **diagnostic** (`DIRECT` / `ADAPTABLE` / `BLOCKED`).
3. Universal finger **mapper** (name + hierarchy + geometry; `AMBIGUOUS_FINGER_MAPPING` blocks).
4. Motion library (min set) + FACE/TALKING sync contract.
5. Independent QA gates (`HAND_RIG_PASS`, `HAND_MOTION_PASS`, `NEUTRAL_RETURN_PASS`).
6. CLI flags on sealed consume runner (`--add-hand-rig`, `--hand-motion`).
7. Only then open **HAND-02** (no-bone auto-create).

## Authority

- Change request: `POST-V2-CR-HAND-01`
- Human Spec Gate: **PENDING** (implementation **DENIED** until APPROVED + digest match + OPEN_PROTOTYPE)
- Samples: private only; redistribution rights required; digests in receipts, meshes not in public git

## Out of scope (this intent)

- Finger auto-create engine (HAND-02)
- Reopening V2 CR01–CR04 / IRG
- Publishing Meshy/user GLBs to public GitHub
