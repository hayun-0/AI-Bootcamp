# ⑥ 경제성·환경성 (economics)

## 역할
소각 위탁 비용 범위와 판매 예상 수입 범위를 나란히 보여 준다. 모두 추정이다.

## 입력
listing.total_kg, ctx.results.pricing(시세 범위)

## 출력
data: incineration, sale. 주장: 소각 비용 범위(근거 INCIN-2026-09), 판매 수입 범위와 두 범위의 관계(estimate).

## 도구
calc.incineration_cost, assumptions(incineration_krw_per_ton).

## LLM이 하는 일
두 범위를 비교해 쉽게 풀어 쓴다.

## 하지 않는 일
범위를 한 값으로 줄이지 않는다. 탄소 감축량 같은 근거 없는 환경 수치를 말하지 않는다. 소각비 보도값은 업계 측 분석이며 독립 검증이 아니다.
