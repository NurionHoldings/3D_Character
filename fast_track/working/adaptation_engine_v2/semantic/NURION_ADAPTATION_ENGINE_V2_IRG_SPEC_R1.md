# V2-IRG-01 — Integration / Release Gate SPEC R1

**Status:** SPEC_PROPOSED / Human Spec Review **PENDING** (Human Spec PASS not declared)  
**Implementation authority:** NONE  
**Gate / Engine V2:** NOT OPEN  
**Progress:** ~96–97% (unchanged by proposal)

## Core claim

CR01 + CR02 + CR03 + CR04 → **ONE AUTHORITATIVE NURION ADAPTATION ENGINE V2 RELEASE**

원칙: 더 개발해서 완성하는 것이 아니라, 이미 Human PASS된 네 기술을 **변경 없이** 하나의 재현·감사 가능 release authority로 봉인한다.

## Absolute boundary

- CR01–CR04 = CONSUME ONLY / REOPEN DENY  
- UPSTREAM mutation / reproof / receipt rewrite / digest rebase = **DENY**  
- Upstream defect → Final Gate **BLOCKED** + 별도 신규 CR (몰래 고쳐 PASS 금지)

## Release SoT

`NURION_ADAPTATION_ENGINE_V2_RELEASE_MANIFEST.json` — Human Final PASS 후 V2 release authority SoT

## Support envelope

**SUPPORTED:** rigged+skinned Meshy-style GLB; BODY preserve + semantic adapt; FACE Blink/Jaw/Expression/Viseme; TALKING weights+V(t); >1 Meshy generalization basis  

**NOT CLAIMED:** auto-rig, global auto-weight, all topologies/generators, FBX/VRM/USD, phoneme lip-sync, speech engine, advanced facial sim, universal production  

100% = **선언된 V2 envelope의 100%** (전 세계 3D 자동변환 ≠)

## Stages (after Spec APPROVE only)

| Stage | Name |
|-------|------|
| V2-RG-P01 | Authority / Receipt / Digest Chain |
| V2-RG-P02 | Release Manifest + Support Envelope |
| V2-RG-P03 | E2E Integration / Preservation |
| V2-RG-P04 | Determinism + Generalization Regression |
| V2-RG-P05 | Release Candidate Seal |
| V2-RG-P06 | Self-Contained Human Audit Package |
| V2-RG-P07 | Human Final — only path to Engine V2 CLOSED/PASS / 100% |

P01–P06 = one fail-closed FAST-TRACK. Max agent = READY_FOR_HUMAN_AUDIT.

## Next

Human Spec Gate: **APPROVE** or **BLOCK** (SPEC-only). No implementation until APPROVED.
