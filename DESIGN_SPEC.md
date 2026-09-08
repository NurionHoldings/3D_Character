# NURION Universal Eye Calibration — Alpha3

## 목표

캐릭터별 절대 좌표나 단일 Ray에 의존하지 않고, 모든 휴머노이드에서 재구성 가능한 얼굴 기준계로
평면 눈 위치를 먼저 확정한 뒤 볼록형 눈, 움직임, 표정을 순차적으로 검증한다.

## 게이트

1. **Universal Face Basis** — 머리 로컬축, 얼굴 정면, 대칭면, 눈꺼풀 개구부, Eye Unit 확정
2. **Flat Eye Placement** — 정면 X/Z와 좌우 3/4 깊이 Y를 결합한 `EyePlane.L/R` 생성
3. **Multiview Accuracy** — 정면·30°·60°·측면·상하에서 매몰/돌출/부유 0 확인
4. **Convex Conversion** — 승인된 평면을 움직이지 않고 얕은 돔·홍채·동공·반사광 생성
5. **Motion Validation** — 안전 타원 내 시선, 깜빡임, 고개 회전, 원점 복귀 검증
6. **Expression Matching** — 중립·미소·설명·공감·집중·말하기 표정과 눈의 충돌 검증

## 공통 단위

`1 Eye Unit = 해당 눈의 안쪽–바깥쪽 눈꺼풀 거리`

크기, 깊이, 돌출, 시선 이동량은 미터 절대값보다 Eye Unit 비율로 저장한다.

## 단계별 불변 규칙

- 평면 멀티뷰 PASS 전 볼록형 생성 금지
- 볼록형 PASS 전 시선·깜빡임 생성 금지
- 모션 PASS 전 표정 결합 금지
- 각 단계는 입력 해시, 증거 뷰, 좌표, 신뢰도, 후보 점수, 선택·거부 사유를 기록
- 보정 후 점수가 악화되면 직전 PASS 상태로 복원
- 개발 자산과 최종 Holdout 자산 분리

## 현재 상태

DESIGN RESET = TRUE  
GATE 1 = LOCKED PASS  
GATE 2 = LOCKED PASS (param ac799e4f…a595b5)  
GATE 3 (Convex Conversion) = LOCKED PASS (Tennis + Captain, selected LOW/LOW)  
MOTION / EXPRESSION = HOLD  
NEXT = AWAIT GO FOR MOTION VALIDATION  
SEALED = FALSE
