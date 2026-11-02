# ③ 등급·통과증 (grading)

## 역할
순도로 등급을 정한다. 순도 = 목표 재질 kg / 전체 kg(재질명은 별칭 표준화·대소문자 무시: 피피·폴리프로필렌 → pp). 품목에 위험 재질이 하나라도 있으면 등급 없음(확인으로도 못 품). 메모(note)에 위험어가 있으면 `confirm_no_hazard`로 확인하기 전까지 등급 보류. 표에 없는 재질은 reasons에 "인식 못 한 재질: X(확인 필요)".

## 입력
bag.target_material, bag.items, bag.note, bag.confirm_no_hazard

## 출력
data.grade = GradeResult(target_material, purity, grade, hazard, reasons)를 dict로. 주장: 등급 결과 한 줄.

## 도구
calc.compute_grade. 기준은 harness.yaml assumptions(grade_thresholds A 0.95 / B 0.90 / C 0.80, hazard_materials).

## LLM이 하는 일
하지 않는다(llm: false).

## 하지 않는 일
LLM이 등급을 바꾸지 못한다. 기준 숫자를 코드에 따로 적지 않는다. 기준은 구매자 요구 스펙 확인 전 팀 가정이다.
