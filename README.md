# NURION 3D Character

GitHub: [NurionHoldings/3D_Character](https://github.com/NurionHoldings/3D_Character)

NURION 3D 캐릭터 적응·랜드마크·페이스/토킹 파이프라인 소스 저장소입니다.

## Authority (FIXED)

| 항목 | 상태 |
|------|------|
| NURION ADAPTATION ENGINE V2 | **CLOSED / PASS / CONSUME ONLY** |
| V2 RELEASE | **AUTHORITATIVE FINAL** |
| CR01–CR04 | HUMAN PASS / CONSUME ONLY / REOPEN DENY |
| Progress | **100%** (declared V2 support envelope) |

V2를 조용히 수정하지 마세요. 확장(FBX, 다수 캐릭터, lip-sync 등)은 **Post-V2 Change Request**로 분리합니다.

## Layout

| Path | 내용 |
|------|------|
| `fast_track/v2_cr01` … `v2_irg` | Adaptation Engine V2 소스 (consume) |
| `fast_track/change_control` | Human Spec Gate |
| `fast_track/working/adaptation_engine_v2/semantic` | SPEC / track / release manifest |
| `fast_track/working/adaptation_engine_v2/evidence` | Human PASS receipts (JSON) |
| `nurion_character_landmarker` | Blender 랜드마커 애드온 |
| `tools/` | runners / packers |

대용량 GLB/FBX/ZIP·`dist/`·임시 블렌더 캐시는 Git에 포함하지 않습니다.

## Quick pointers

- V2 Integration SPEC: `fast_track/working/adaptation_engine_v2/semantic/NURION_ADAPTATION_ENGINE_V2_INTEGRATION_RELEASE_GATE_SPEC_R1.json`
- Engine closed receipt: `fast_track/working/adaptation_engine_v2/evidence/NURION-V2_ENGINE_CLOSED_PASS_FINAL_receipt.json`
- Sporty final demo (local only): `dist/v2_final_demo/Sporty_V2_FACE_TALKING.glb`

## License / ownership

Nurion Holdings — internal product source.
