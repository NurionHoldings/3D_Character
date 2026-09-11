# POST-V2-CR-HAND-01 — Human Spec (R1)

**Status:** SPEC_PROPOSED / Human Spec **PENDING** / Implementation **DENIED**

Machine SPEC: `fast_track/working/post_v2_hand_rig/semantic/NURION_POST_V2_CR_HAND_01_EXISTING_FINGER_BONES_HAND_MOTION_SPEC_R1.json`  
Track: `fast_track/working/post_v2_hand_rig/semantic/NURION_POST_V2_CR_HAND_01_TRACK_V1.json`  
Intent: `intent_DNA/POST_V2_HAND_RIG_P1_2026-09-09.md`

## One-line claim

손가락 **뼈가 이미 있는** Meshy-style GLB에 NURION 손 표준 매핑 + 최소 손동작 clip을 추가하되, BODY/FACE/TALKING·원본 불변을 유지한다. 뼈 자동 생성은 HAND-02.

## NURION bone names (locked in SPEC)

`hand.{L|R}`, `{thumb|index|middle|ring|pinky}.{01|02|03}.{L|R}`

## Verdicts

`DIRECT` | `ADAPTABLE` | `BLOCKED`  
저신뢰 매핑: `AMBIGUOUS_FINGER_MAPPING` → 자동 적용 금지

## P1 min motions

`open`, `fist`, `wave`, `point`, `thumbs_up` (+ `neutral` return)

## Completion gates

`HAND_RIG_PASS` ∧ `HAND_MOTION_PASS` ∧ `NEUTRAL_RETURN_PASS` (+ existing FACE/TALKING consume PASS)

## CLI (after APPROVE + P08 only)

```powershell
py -3 tools/run_v2_consume_meshy_glb.py `
  --input "D:\assets\character.glb" `
  --out-dir "dist\v2_consume\character" `
  --add-hand-rig `
  --hand-motion wave,point,thumbs_up,fist,open
```

## Human action required

1. Review SPEC R1 JSON  
2. APPROVE → record `approvedSpecDigest = SHA256(SPEC file)` on TRACK  
3. Set `implementationAuthority=GRANTED`, `openStatus=OPEN_PROTOTYPE`  
4. Then P01 numeric limit lock → P02 diagnostic prototype
