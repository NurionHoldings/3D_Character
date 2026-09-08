# V2-CR-04 SPEC R1 — PROPOSED

**TITLE:** SECOND REAL MESHY ASSET GENERALIZATION

**Status:** `SPEC_PROPOSED` / `HUMAN_SPEC_REVIEW PENDING`  
**Implementation authority:** `NONE`  
**CR status:** `NOT OPEN`

---

## PURPOSE

Idle_15에서 Human-audited된 **CR01 → CR02 → CR03** 기술 체인이, 두 번째 독립 실제 Meshy 생성 캐릭터에서도 **asset-specific hardcoding 없이** 재현되는지 증명한다.

새 기술 개발이 아니라 **일반화 검증**이다.

---

## PASS MEANS / DOES NOT MEAN

**MEANS:** Idle_15 이외 두 번째 독립 실자산에서 파이프라인 재현 (Human-audited)

**DOES NOT MEAN:** 모든 Meshy 지원 · 임의 외부 캐릭터 · universal generalization · production ready · Engine V2 OPEN

---

## SECOND ASSET CONTRACT

1. **PIN SHA256 FIRST** → 그다음 CR04 실행  
2. 실제 Meshy asset · Idle_15과 다른 SHA · mesh/skin/body rig · source immutable  
3. synthetic / Idle_15 복제·변형 / cherry-pick **금지**  
4. 이 SPEC 제안 시점에는 second asset을 고르지 **않음**

---

## KEY RULES

| Rule | Value |
|------|-------|
| Bone name equality | NOT REQUIRED |
| Topology/semantic adaptability | REQUIRED |
| CR01/02/03 code | CONSUME ONLY |
| Upstream patch/repair/spec change | DENY |
| BODY re-rig / auto-weight | DENY |
| FACE | inspect → preserve or minimum CR02 augment |
| Deformation | actual GLB Δ; thresholds 1e-4 / 1e-6 (post-run mutation DENY) |
| TALKING | CR03 consume; morph exists ≠ PASS |
| Hardcoding scan | REQUIRED on production logic |

---

## STAGES (fail-closed fast-track)

P01 Intake/Pin → P02 CR01 → P03 CR02 → P04 CR03 → P05 Cross-asset → P06 Package  
**P07 / G20 = HUMAN_FINAL_ONLY**

---

## NEXT

Human Spec Gate → APPROVE 시에만 OPEN / PROTOTYPE.  
그 후 **second asset SHA pin → P01**. 구현은 APPROVE 전 금지.
