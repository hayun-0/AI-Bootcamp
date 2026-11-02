# ① 프로파일링 (profiling)

## 역할
공장 가입 때 업종 문자열로 나올 수 있는 부산물 후보를 알려 준다. 가입 때 고르기용 안내다.

## 입력
company.industry (업종 문자열)

## 출력
data.candidates: [{waste_code, name, keyword}]. 주장(업종 문자열은 문장에 넣지 않는 고정 문구): 후보 목록(level=estimate) 또는 좁히지 못했다는 질문(level=question).

## 도구
업종 키워드 → 폐기물 코드 표(코드 내장), data/waste_codes.json의 이름.

## LLM이 하는 일
후보 목록을 가입 담당자에게 안내하는 말투로 풀어 쓴다(새 숫자 없음).

## 하지 않는 일
실제 배출 품목을 확정하지 않는다. 폐기물 코드를 자동으로 바꾸지 않는다(분류는 지자체 확인).
