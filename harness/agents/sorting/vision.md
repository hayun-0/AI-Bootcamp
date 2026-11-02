# ② 사진 분류 보조 (vision)

## 역할
P0에서는 사진 대신 품목 입력(items)을 정리한다. 재질명을 소문자로 맞추고 kg을 합쳐 구성비를 계산한다.

## 입력
bag.items [{material, kg}], bag.note(선택)

## 출력
data: materials, total_kg, composition, note_candidates. 주장: 구성비(fact, 근거 input+calc), 메모 재질 후보(estimate, 근거 llm+assumption).

## 도구
calc.normalize_items (재질 합산·구성비).

## LLM이 하는 일
note가 있을 때만 메모에서 재질 이름 후보를 뽑는다(스키마 JSON). 후보는 메모에 실제로 나오는 말(별칭 포함)만, 표준 이름으로 최대 5개이며 사람 확인용이다. 메모에 위험어가 있으면 코드가 "메모에 위험 재질 언급: …(사람 확인 필요)" 주장을 만든다(근거 input).

## 하지 않는 일
등급 계산에 LLM 후보를 쓰지 않는다. 사진으로 성분을 확정하지 않는다.
