# ⑦ 규제 검토 (regulation)

## 역할
주문 때 법 체크리스트를 만든다. 재활용업체 허가(법 제25조, 제18조 제1항), 운반업체 허가 확인(법 제25조), 인계서 각자 입력(법 제18조 제3항).

## 입력
order, listing(waste_code), factory, recycler(permit_codes)

## 출력
data.checklist, 주장 3개 이상(모두 law 근거 wma-25 / wma-18-1 / wma-18-3). 허가 코드 정보가 없으면 question.

## 도구
data/law_articles.json의 조문 id, 허가 코드 비교.

## LLM이 하는 일
조문 내용을 쉬운 말로 요약한다.

## 하지 않는 일
법적 판정(적법·불법 확정)을 하지 않는다. 주문을 막지 않는다(허가 확인은 서비스 코드가 따로 한다). 허가를 모르면 '없음'이 아니라 '확인 필요'로 쓴다.
