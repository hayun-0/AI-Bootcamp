# 근거 규칙 (evidence rules)

모든 주장(claim)은 `evidence` 를 1개 이상 가진다. 검증팀이 아래 규칙으로 검사하고, 어기면 `blocked: true` 로 통과증에서 뺀다.

| 근거 종류 | ref 에 넣는 것 | 예 |
|---|---|---|
| `law` | `law_articles.json` 의 조문 id | `wma-rule-18-1` |
| `dataset` | `sources.json` 의 데이터셋 id | `facilities-2024`, `D2-PRICE` |
| `calc` | 계산식 | `1 − 0.05^(1/n)` |
| `assumption` | 무엇을 가정했는지 | `재질 비율 많음 30%·조금 10%` |
| `input` | 입력 필드 | `items.pvc`, `kgPerDay` |
| `llm` | 모델 이름 | `ax4-light:q4_K_M` (label: "자유 서술에서 추출(사람 확인 필요)") |

## 규칙
1. 법을 말하는 주장(법 이름·제n조·별표·시행령·시행규칙·R-x-x, 또는 law-judge 주장) → `law` 근거, id가 조문 표에 있어야 함. (citation-checker)
2. 숫자가 있는 주장 → `dataset`·`calc`·`input`·`assumption`·`law` 중 하나. (provenance-checker)
3. `estimate`·`assumption` 수준 주장 → `assumption` 또는 `calc` 근거. (provenance-checker)
4. 업체 주장 → `facilities-2024` 데이터셋 근거. (provenance-checker)
5. 금지 표현(`forbidden-phrases.json`)·단정 표현·'모름 → 없음' 금지. (wording-guard)
6. LLM 요약: 막히지 않은 주장만 받고, 문장마다 `[agent:n]` 인용, 주장에 없는 숫자 금지. 실패 시 1회 재요청 → 템플릿 요약.

## 수준 (level)
- `fact`: 입력·법·데이터에서 바로 나온 것
- `estimate`: 계산·추출로 나온 추정 (사람 확인 필요)
- `assumption`: 가정 자체를 밝히는 문장
- `question`: 아직 모르는 것·물어볼 것
