# V2-CR-03 SPEC R1 — PROPOSED

**TITLE:** MORPH-WEIGHT RUNTIME TALKING SEQUENCE

**Status:** `SPEC_PROPOSED` / `HUMAN_SPEC_REVIEW PENDING`  
**Implementation authority:** `NONE`  
**CR status:** `NOT OPEN`

---

## PURPOSE

CR02 R2에서 Human-PASS된 실제 facial morph deformation **VISEME_AA / VISEME_OH / VISEME_EE**를 수정하지 않고 소비하여, runtime에서 시간축 morph-weight sequence로 구동되는 **실제 TALKING animation mechanism**을 증명한다.

핵심 입력은 CR02 R2 Human-audited derived asset으로 고정한다.

---

## AUTHORITATIVE INPUT

| Field | Value |
|-------|-------|
| Derived | `Idle_15_R2_facial_deformation.glb` |
| SHA256 | `1ee90420ba39cc2e74de6624230538f4416d39ec7b34656e5b175a776c171cdd` |
| Required morphs | `VISEME_AA`, `VISEME_OH`, `VISEME_EE` |
| Upstream | CR01/CR02 = CONSUME ONLY / REOPEN DENY |

CR03에서 허용하는 것은 기존 morph geometry를 **runtime weight animation**으로 구동하는 것뿐이다.

---

## AUTHORIZED MUTATION SCOPE

**ALLOW**
- morph-weight animation track 생성
- AA/OH/EE weight keyframe 생성
- TALKING animation clip 생성
- neutral transition keyframe 생성
- runtime playback metadata 생성
- 새로운 derived artifact 생성

**DENY**
- AA/OH/EE morph POSITION 수정
- 새로운 facial morph geometry 생성
- Blink/Jaw/Expression geometry 수정
- BODY skeleton / skin weight 수정
- FACE topology 재생성
- CR01 semantic mapping / CR02 augmentation 수정
- auto re-rig / global auto-weight

---

## TALKING FUNCTIONAL CONTRACT

```
NEUTRAL → AA → transition → OH → transition → EE → NEUTRAL
```

Required: 시간축, ≥3 distinct mouth states, 실제 morph weight 변화, 실제 vertex deformation, state 간 geometry 차이, 종료 후 neutral restoration.

Illustrative timeline (NOT approved fixed timings):

| t | AA | OH | EE |
|---|----|----|----|
| 0.00 | 0 | 0 | 0 |
| 0.10 | 1 | 0 | 0 |
| 0.25 | 0 | 1 | 0 |
| 0.40 | 0 | 0 | 1 |
| 0.55 | 0 | 0 | 0 |

R1은 **sequence semantics만 고정**. duration/key timing은 구현 전 deterministic parameter로 선언한다.

**Not PASS:** clip 이름만 존재 / morph 존재(CR02 이미 PASS) / Jaw_Mouth = TALKING / JSON-only sequence (`ANIMATION_METADATA_ONLY`)

---

## PROOF LAYERS

1. **ANIMATION STRUCTURE** — `target.path = "weights"`, real timestamps/weights, CR02 facial mesh target  
2. **RUNTIME GEOMETRY** — `V(t) = V0 + ΔAA·wAA + ΔOH·wOH + ΔEE·wEE`; AA≠OH≠EE; max Δ > `1e-4`  
3. **RESTORATION** — V(start)≈V0, V(end)≈V0; error ≤ `1e-6`

---

## INDEPENDENCE

- `Jaw_Mouth` = CR02 CONSUME ONLY ≠ TALKING PASS  
- `TALKING` = timed AA/OH/EE morph-weight orchestration  
- New proof: STATIC MORPHS → TIME-VARYING WEIGHTS → ACTUAL TEMPORAL MOUTH DEFORMATION

---

## BODY REGRESSION (minimal)

POSITION / JOINTS / WEIGHTS / hierarchy unchanged; CR02 morph POSITION preserved; FACE_Rig_Root preserved; **Idle + TALKING** coexistence via embedded Idle.  
Bow/LargeBow/Handshake/Dance profile expansion = **DENY** in CR03.

---

## STAGES

| Stage | Name |
|-------|------|
| CR03-P01 | Runtime Talking Contract / Morph Binding Inspection |
| CR03-P02 | Morph-Weight Animation Injection |
| CR03-P03 | Temporal Vertex-Deformation Proof |
| CR03-P04 | Idle + TALKING Coexistence / Regression |
| CR03-P05 | Real Asset Proof Packaging |
| CR03-P06 | Human Final Audit (Agent PASS deny) |

Gates G01–G19 automatable; **G20 = HUMAN_FINAL_ONLY**.

---

## HUMAN GATES (separate)

| Gate | Meaning |
|------|---------|
| Human Spec Gate | “만들어도 된다” → implementation authorization |
| Human Final Gate | “요구사항을 충족했다” → Human PASS |

Spec PASS ≠ 기술 PASS ≠ Engine V2 OPEN.

---

## NEXT

Human Spec Gate 검토 → APPROVE 시에만 `OPEN / PROTOTYPE` + `IMPLEMENTATION AUTHORITY GRANTED`.  
그 전까지 구현 시작 금지.
