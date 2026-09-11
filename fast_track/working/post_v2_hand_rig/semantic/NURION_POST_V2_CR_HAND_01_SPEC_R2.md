# POST-V2-CR-HAND-01 — Human Spec (R2)

**Status:** SPEC_PROPOSED / Human Spec **PENDING** / Implementation **DENIED**

Machine SPEC: `fast_track/working/post_v2_hand_rig/semantic/NURION_POST_V2_CR_HAND_01_EXISTING_FINGER_BONES_HAND_MOTION_SPEC_R2.json`
Track: `fast_track/working/post_v2_hand_rig/semantic/NURION_POST_V2_CR_HAND_01_TRACK_V2.json`
Intent: `intent_DNA/POST_V2_HAND_RIG_P1_2026-09-09.md`

Proposed SPEC SHA-256: `965e3364b9d14061b4ee449caa716200a5c192614872266ba4f64195d626bfb8` (raw UTF-8/LF file bytes; no Git object header).

R1 is retained as an immutable audit trail and is superseded for new work by R2.

## Claim and hard boundary

P1 may eventually add append-only hand-motion animations only for a private GLB whose existing finger bones and existing weights pass conservative diagnosis. It must preserve BODY, FACE, TALKING, source bytes, and all sealed RIG-02/V05/V06/V07 evidence. Missing finger bones, ambiguous mapping, unresolved skin/IBM, or unacceptable existing weights are **BLOCKED**, not a repair invitation.

The eight required gates are:

`HAND_RIG_PASS` · `HAND_MAPPING_PASS` · `HAND_WEIGHT_PASS` · `HAND_MOTION_PASS` · `NEUTRAL_RETURN_PASS` · `BODY_PRESERVATION_PASS` · `FACE_TALKING_PRESERVATION_PASS` · `GLB_RELOAD_PASS`

`HAND_WEIGHT_PASS` validates existing weights only; it never authorizes weight repair or synthesis.

## Identity and GLB contract

`NURION_hand_L` and `NURION_hand_R` are existing upstream body-node names when present. They must never be renamed. `hand.L`, `thumb.01.L`, and similar values are separate semantic mapping IDs, recorded with upstream node index/name evidence.

Existing node rest pose, skins, inverse bind matrices, primitives, and existing animations are immutable. Each future hand motion is a newly appended animation using new accessors and explicit channels, accessors, interpolation, and rotation-only targets. A neutral return must reproduce the existing rest pose by the P01-locked comparison method.

## Required human sequence

1. Perform P01 privately: lock axes, motion limits, confidence lower-bound and second-best-margin method, and tolerance derivation from a rights-confirmed calibration set. Record only the receipt/manifest/parameter-envelope digests publicly.
2. Only after a valid P01 lock: change to **APPROVED**.
3. Then change to **OPEN_PROTOTYPE**.
4. Then, and only then, grant **GRANTED** implementation authority.

Before step 4, no code, CLI flag, candidate GLB, or automatic mapping is authorized. HAND-02 remains **NOT OPEN**.

## Private visual proof

Private visual receipts must cover front, palm, dorsum, profile, per-finger flex, fist, wave, point, thumbs-up, and simultaneous TALKING plus hand. Commit only the receipt schema and SHA-256 digests; never commit GLBs, screenshots, sample identifiers, absolute paths, or authority bundles.

## Output safety

Future execution must validate in private staging, satisfy all eight gates and GLB reload, then atomically publish to an absent final target. Existing outputs are no-clobber; every failure rolls back the final publication and remains fail-closed.
