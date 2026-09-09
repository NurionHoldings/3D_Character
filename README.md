# NURION 3D Character

GitHub: [NurionHoldings/3D_Character](https://github.com/NurionHoldings/3D_Character)

## Product purpose

사용자가 **Meshy 등에서 받은 캐릭터(현재 V2: Meshy-style GLB)** 에 부족한 **얼굴 표정·추가 리깅(FACE / Viseme·TALKING)** 을 NURION Adaptation Engine으로 보완한 뒤, **결과물을 다운로드해 자기 플랫폼에 적용**하는 것이 목적입니다.

의도 플로우:

1. 사용자 자산 확보 (Meshy 다운로드 등)
2. 엔진 consume → 표정·리깅 증강
3. 증강본 다운로드
4. 사용자 플랫폼 적용 (예: MJN)

> **V2 support envelope (봉인):** rigged+skinned Meshy-style **GLB** → BODY 보존 + FACE/TALKING 증강.  
> **FBX 입력·원클릭 배포 UX** 는 Post-V2 Change Request (포맷 어댑터 / 제품 런타임)로 분리합니다. V2를 재개하지 않습니다.

## Authority (FIXED)

| 항목 | 상태 |
|------|------|
| NURION ADAPTATION ENGINE V2 | **CLOSED / PASS / CONSUME ONLY** |
| V2 RELEASE | **AUTHORITATIVE FINAL** |
| CR01–CR04 | HUMAN PASS / CONSUME ONLY / REOPEN DENY |
| Progress | **100%** of declared V2 support envelope |

Silent mutation / upstream rebase = **DENY**. 확장은 Post-V2 CR만.

## Public vs private

기준: **엔진(제품)은 공개 가능, 캐릭터 바이너리(사용자·Meshy 메쉬)는 재배포하지 않음.**

| 공개 (이 Repo / 공개 문서) | 비공개 (Git에 올리지 않음 · 서비스·내부만) |
|---------------------------|---------------------------------------------|
| Adaptation Engine 소스 (`fast_track/v2_*`, tools) | 사용자 업로드 FBX/GLB |
| SPEC / track / Human PASS **JSON** receipts·digest | 처리 중 임시본, 사용자별 결과 GLB/FBX |
| 지원 범위·미클레임·적용 가이드 | Meshy 원본 표본 (Idle_15, Sporty 등) |
| 공개 API/SDK **계약 문서**(있을 때) | 데모 파생 GLB (`Sporty_V2_FACE_TALKING` 등) |
| | IRG proof ZIP (메쉬 포함 감사 패키지) |
| | API 키, `.env`, 고객 배포 패키지 |
| | `.nurion_blender_tmp/`, 옛 `dist/v0.x` 캐시 |

공개 Repo에 Meshy 메쉬를 올리는 것은 **타사/사용자 자산 재배포**가 되므로 하지 않습니다. 재현은 **SHA256 핀(JSON)** 으로 하고, 바이너리는 각자가 Meshy에서 확보하거나 내부 private 채널을 씁니다.

## GitHub 추가 업로드 분류

「목적 수행을 위해 GitHub에 더 올릴 것」을 아래처럼 나눕니다.  
**(A) 공개 Repo에 추가 권장** · **(B) 비공개 채널만** · **(C) 올리지 않음** · **(D) Post-V2 이후**

### (A) 공개 `3D_Character`에 추가 권장 (코드·문서·핀)

| 항목 | 이유 | 상태 |
|------|------|------|
| 본 README (목적·공개/비공개·플로우) | 제품 의도 SoT | 본 문서 |
| `ASSETS_MANIFEST.json` (파일명↔SHA256↔CR 핀, **경로만·바이너리 없음**) | 재현·감사 핀 공개 | **추가 업로드 후보** |
| 플랫폼 적용 가이드 초안 (입력 계약, 출력 morph/clip 이름, 적용 순서) | “다운로드 후 플랫폼 적용” 공개 설명 | **추가 업로드 후보** |
| Post-V2 로드맵 메모 (FBX adapter / 업로드·다운로드 UX — **구현 아님**) | 목적(FBX)과 V2 봉인 경계 명시 | **추가 업로드 후보** |
| (선택) 스크린샷·짧은 webm **자체 제작** 데모 캡처 | 메쉬 재배포 없이 능력 설명 | 허용 시 추가 |

이미 올라가 있는 것: V2 소스, semantic SPEC, evidence JSON, tools, 랜드마커 등.

### (B) 비공개만 (공개 GitHub 업로드 금지 · private repo / Release private / 내부 스토리지)

| 항목 | 이유 |
|------|------|
| `Idle_15` Silver Starlight baseline GLB | CR01–03 입력 원본 (Meshy) |
| Sporty source / FACE / FACE+TALKING GLB | CR04·final demo 바이너리 |
| `derived_cr0*` 중간 GLB | 엔진 파생 메쉬 |
| IRG R1/R2 proof ZIP | 감사 재현용, 메쉬 포함 |
| Jake.fbx 등 외부 HR 자산 | 제3자/별도 라이선스 |
| 사용자·고객 업로드/결과물 | 서비스 비공개 데이터 |

내부 팀이 재현하려면: **private assets repo** 또는 **private Release** + `ASSETS_MANIFEST.json`의 SHA와 일치하는지 검증.

### (C) 올리지 않음 (정리·캐시)

| 항목 | 이유 |
|------|------|
| `.nurion_blender_tmp/` | Blender 임시 (~10GB) |
| `dist/v0.3`–`v0.7` 등 옛 게이트 산출 | 제품 목적과 무관 |
| 루트 중복 IRG ZIP 사본 | evidence/내부본으로 충분 |

### (D) Post-V2 (지금은 공개 “약속 문서”만, 구현·자산은 CR 후)

| 항목 | 비고 |
|------|------|
| FBX → 엔진 입력 어댑터 | V2 NOT_CLAIMED; 별도 CR |
| 상용 “완성형” 표본 (ARKit 52·혀 분리·재배포 허용) | 엔진 검증용 **새 등급** 표본; 확보 후 (B) 또는 라이선스 허용 시 정책 재검토 |
| 업로드→증강→다운로드 제품 API | 런타임/백엔드; 이 Repo와 분리 가능 |

## Layout

| Path | 내용 |
|------|------|
| `fast_track/v2_cr01` … `v2_irg` | Adaptation Engine V2 소스 (consume) |
| `fast_track/change_control` | Human Spec Gate |
| `fast_track/working/adaptation_engine_v2/semantic` | SPEC / track / release manifest |
| `fast_track/working/adaptation_engine_v2/evidence` | Human PASS receipts (JSON) |
| `nurion_character_landmarker` | Blender 랜드마커 애드온 |
| `tools/` | runners / packers |

## Quick pointers

- V2 Integration SPEC: `fast_track/working/adaptation_engine_v2/semantic/NURION_ADAPTATION_ENGINE_V2_INTEGRATION_RELEASE_GATE_SPEC_R1.json`
- Engine closed receipt: `fast_track/working/adaptation_engine_v2/evidence/NURION-V2_ENGINE_CLOSED_PASS_FINAL_receipt.json`
- Sporty final demo GLB: **local / private only** — `dist/v2_final_demo/` (not in this public repo)

## License / ownership

- **Engine source & NURION docs in this repo:** Nurion Holdings  
- **Meshy (or user) character meshes:** respective owner — **not redistributed** via this public repository
