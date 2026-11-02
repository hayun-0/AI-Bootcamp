# ④ 묶음·수거 (bundling)

## 역할
내 판매 근처의 같은 폐기물 코드·같은 등급 대기 판매를 합쳐 최소 묶음(min_lot) 충족 여부를 계산한다.

## 입력
listing, bags, nearby_listings, factory(위경도)

## 출력
data: matches, own_kg, bundle_kg, meets_min_lot. 주장: 반경 안 건수·합계·충족 여부(estimate), 위치 없는 후보 안내(question).

## 도구
calc.haversine_km 직선거리, assumptions(bundle_radius_km, min_lot_kg).

## LLM이 하는 일
계산된 결과를 판매자에게 쉽게 풀어 쓴다.

## 하지 않는 일
묶음을 실제로 성사시키지 않는다(P0 밖). 위치를 모르는 후보를 반경 안으로 치지 않는다.
