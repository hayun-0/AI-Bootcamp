# 지휘 AI (orchestrator)

## 역할
flow(규칙)가 정한 순서대로 에이전트를 돌리고, 게이트를 통과한 주장만 모아 사용자에게 보여줄 요약을 만든다.

## 입력
flow 이름과 ctx(앱이 넘긴 값). 앞 에이전트 결과는 ctx.results[에이전트id]로 다음 에이전트에 전달된다.

## 출력
RunResult: plan, results, public_claims(게이트 통과분), blocked_count, summary, summary_source(llm|template), llm 상태, events.

## 도구
harness.yaml(flows·gates·summary), gates.py(evidence·wording·privacy), trace.py(실행 기록).

## LLM이 하는 일
public_claims만 받아 쉬운 말로 요약하고 문장마다 [에이전트id:번호]를 붙인다. 요약에 주장에 없는 숫자가 있으면 게이트가 막아 1회 다시 요청하고, 또 막히면 템플릿 요약을 쓴다.

## v0.2 요약 규칙
- LLM에는 사용자 문자열(회사 이름·업종·메모·모르는 재질명)을 "[입력값]"으로 가린 주장 문장만 보낸다.
- 요약 게이트: 주장에 없는 숫자(한글 수 표현 포함), 등급 글자가 등급 결과와 다름, 시세 범위 표현이 pricing.relation과 다름, 전화번호(국제 형식 포함) → 막히면 1회 재요청 후 템플릿.
- 한 run에서 LLM이 한 번 실패하면 나머지 LLM 호출은 건너뛰고 템플릿. 화면용 summary에서는 `[agent:n]` 꼬리표를 지운다.

## 하지 않는 일
에이전트 순서를 바꾸지 않는다. 숫자·등급·법 근거를 만들지 않는다. LLM이 꺼져 있거나 실패해도 예외 없이 템플릿 요약을 돌려준다.
