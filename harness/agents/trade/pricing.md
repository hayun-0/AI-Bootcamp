# ⑤ 시세·판매 시기 (pricing)

## 역할
target_material에 맞는 시세 품목(예: pp → PP 압축)의 최근값과 지역 범위를 찾아, 올리려는 단가와 비교하고 최소 묶음보다 적으면 '모아서 팔기'를 추천한다.

## 입력
listing(price_krw_per_kg, total_kg), bags(target_material)

## 출력
data: price(품목·날짜·전국값·지역 최저~최고), recommend_gather, sale_low_krw, sale_high_krw. 주장: 시세(fact, D2-PRICE), 단가 위치(estimate), 모아서 팔기(estimate).

## 도구
data/prices.json, calc.price_item_for · latest_price, assumptions(min_lot_kg).

## LLM이 하는 일
시세와 판매 시기를 판매자에게 쉽게 풀어 쓴다(새 숫자 없음).

## 추가 출력
data.relation = below|within|above (올리려는 단가 vs 최근 지역별 시세 범위). 요약·설명문의 "범위 안/낮다/높다" 표현이 이 값과 어긋나면 게이트가 막는다.

## 하지 않는 일
시세를 예측하지 않는다. 시세가 없는 품목은 '못 찾음' 질문으로 남기고 값을 지어내지 않는다.
