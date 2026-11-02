# 마대 장터 — 백엔드 설계 계약서 v0.3 (9절 > 8절 > 앞 절)

v0.1.2: Argon 판정(docs/orchestra/argon_verdict.md) 반영 — operator 가입, 정산 기준, 취소 P1, 묶음 후보 좌표, 경제성 문구 명시. 위험 재질 한글 별칭 추가.

모든 팀은 이 문서를 기준으로 작업한다. 바꿀 때는 이 문서를 먼저 고친다.
상위 설계: 노션 "백엔드 설계"(40bfdc5b…), `research_notes/29차 백엔드 설계/00_백엔드_설계.md`.

## 0. P0 범위
거래 한 바퀴: 회사 가입 → 운영자 허가 확인 → 마대 등록 → 등급(통과증) → 판매 게시 → 주문(가짜 결제 보류) → 운반 콜·수락 → 수거(마대별 무게) → 도착 → 도착 검사 → 확정·정산(가짜) → 인계서 3칸 → 인계서 번호 → 별점.
- 사진 대신 품목 입력(`items`). 결제는 가짜 PG. 위치 계산은 위경도 직선거리(haversine), PostGIS는 나중.
- DB는 SQLAlchemy 2. 개발·테스트 기본은 SQLite(`DATABASE_URL`, 기본 `sqlite:///./masdae.db`, 테스트는 메모리). **배포 DB는 Azure Database for PostgreSQL Flexible Server로 결정(2026-11-02, 학생 플랜)**. 드라이버 `postgresql+psycopg://`. 로컬 PostgreSQL 16(pgserver)에서 전체 테스트 통과 확인.
- 인증 대신 헤더 `X-Company-Id: <정수>`로 요청한 회사를 구분(P0 한정). 없거나 없는 회사면 401.
- P0 밖: 묶음 실제 성사, 검사 불합격 처리(조정·처리 전환·반송), 실제 PG, 푸시, 사진 AI, Claude 실제 호출 테스트.

## 1. 폴더와 담당
```
masdae-market/
├─ docs/ARCHITECTURE.md        지휘부(Opus)
├─ harness/                    harness.yaml(지휘부) · agents/*.md 카드(분석팀 B) · policies/(복사본)
├─ data/                       law_articles.json · prices.json · waste_codes.json · materials.json · sources.json (읽기 전용)
└─ backend/
   ├─ app/contracts.py         공통 타입 (지휘부, 수정 금지)
   ├─ app/main.py              FastAPI 앱 조립 (분석팀 A)
   ├─ app/core/                설정 (A)
   ├─ app/db/                  SQLAlchemy 모델·세션 (A)
   ├─ app/services/            주문 상태·콜·인계서·가짜 PG·별점 (A)
   ├─ app/api/                 거래 라우트 (A) · agents.py 라우트 (B)
   ├─ app/harness/             registry·runner·gates·trace (B)
   ├─ app/agents/              sorting/ trade/ review/ orchestrator.py (B)
   ├─ app/llm/                 base·ollama·claude·mock (B)
   ├─ app/tools/               데이터 읽기·계산 도구 (B)
   ├─ seed/                    구미 가상 시나리오 데이터 (A)
   └─ tests/                   test_trade_*.py (A) · test_harness_*.py (B) · acceptance/ (Sol, 이 문서만 보고 작성)
```
파이썬 실행: `backend/.venv/bin/python`, 테스트: `cd backend && .venv/bin/python -m pytest -q`.

## 2. A ↔ B 연결 (하네스 호출 지점)
B가 `app/harness/runner.py`에 아래 함수를 제공한다. A는 이 함수만 부른다.
```python
def run_flow(flow: str, ctx: dict) -> RunResult   # app.contracts.RunResult
```
| 호출 지점(A) | flow | ctx에 넣는 것 | A가 결과에서 쓰는 것 |
|---|---|---|---|
| `POST /v1/bags/{id}/grade` | `grade_bag` | `{"bag": {...bag 필드}}` | `results[grading].data["grade"]` (GradeResult dict) |
| `POST /v1/listings` 응답 | `listing_advice` | `{"listing": {...}, "bags": [...], "nearby_listings": [...], "factory": {...}}` | 응답에 `advice`(RunResult)로 그대로 첨부 |
| `POST /v1/orders` | `deal_check` | `{"order": {...}, "listing": {...}, "factory": {...}, "recycler": {...}}` | 응답에 `checklist`(RunResult) 첨부. 결과가 주문을 막지는 않음(허가 확인은 A 코드가 따로 함) |
| `POST /v1/companies` (factory) | `profile_company` | `{"company": {...}}` | 응답에 `guide`(RunResult) 첨부 |

- 등급 숫자(순도·등급)는 ③ grading의 코드 계산값만 쓴다. LLM이 등급을 바꾸지 못한다.
- `run_flow`는 LLM이 꺼져 있거나 실패해도 예외 없이 RunResult를 돌려준다(템플릿 요약, `llm.available=false`).
- 모든 RunResult는 `agent_runs` 표에 저장(A가 표를 만들고, B는 `app/harness/trace.py`의 `save_run(session, result)`를 A의 세션으로 호출). 조회: `GET /v1/agent-runs/{run_id}`(B 라우트).

## 3. API (P0, 모두 JSON, 접두사 `/v1`)
에러: 400 잘못된 입력, 401 회사 헤더 없음, 403 권한·역할·허가 없음, 404 없음, 409 상태 충돌(허용 안 되는 상태 변경, 이미 수락된 콜 등).
검사 순서(v0.1.1 지휘부 결정): 401 → 역할 403 → 404 → 당사자 403(배정 안 된 운반업체 포함) → 상태 409 → 입력 400. 예: 결제 보류 주문에 운반업체가 pickup → 아직 배정이 없으므로 403. 배정된 운반업체가 수거 전에 arrive → 409.

### 회사
| 메서드 경로 | 누가 | 요청 | 응답 |
|---|---|---|---|
| `POST /v1/companies` | 누구나(헤더 없음, **operator 공개 가입·즉시 verified는 P0 시연용 단순화. 실제 운영 전 시드·관리 토큰으로 제한**) | `{name, role, biz_no, lat, lon, permit_no?, permit_codes?: [폐기물코드], industry?}` | `201 {id, name, role, verified, permit_codes, guide?}` — factory·operator는 `verified=true`, recycler·hauler는 `false` |
| `POST /v1/admin/companies/{id}/verify` | operator | `{}` | `{id, verified: true}` |

### 마대·통과증
| `POST /v1/bags` | factory | `{waste_code, target_material, items: [{material, kg}], note?}` | `201 {id, factory_id, waste_code, target_material, items, total_kg, status:"registered"}` — total_kg = items 합 |
| `POST /v1/bags/{id}/grade` | 그 마대의 factory | `{}` | `{bag_id, grade: GradeResult, pass_id?, qr?, run_id}` — grade.grade가 null이면 pass 없음. 있으면 `pass_id`, `qr`="MDP-{pass_id}-{bag_id}" |

### 판매
| `POST /v1/listings` | factory | `{bag_ids: [..], mode: "now"|"bundle", price_krw_per_kg}` | `201 {id, status, waste_code, grade, total_kg, price_krw_per_kg, advice}` — 모든 마대가 같은 waste_code·같은 grade, 통과증 있음, 자기 마대, 다른 판매에 안 묶임. mode=bundle이면 status=`bundle_wait`, now면 `posted` |
| `GET /v1/listings?waste_code=` | 누구나 | — | `[{id, status, waste_code, grade, total_kg, price_krw_per_kg, factory_id}]` (posted만) |

### 주문·배차·검사
| `POST /v1/orders` | recycler (verified, permit_codes에 그 waste_code) | `{listing_id}` | `201 {id, status:"payment_held", goods_krw, listing_id, checklist}` — goods_krw = round(total_kg × price). 가짜 PG 보류. listing → sold |
| `GET /v1/calls` | hauler | — | 아직 수락 안 된 `payment_held` 주문 중 hauler의 permit_codes에 맞는 것 `[{order_id, waste_code, total_kg, pickup:{lat,lon}, dropoff:{lat,lon}}]` |
| `POST /v1/calls/{order_id}/accept` | hauler (verified, permit 맞음) | `{freight_krw}` | `{order_id, status:"dispatched", hauler_id}` — 먼저 수락한 1곳만, 나머지는 409 |
| `POST /v1/orders/{id}/pickup` | 배정된 hauler | `{bag_weights: [{bag_id, kg}]}` | `{status:"picked_up"}` — 주문의 모든 마대 무게 필요 |
| `POST /v1/orders/{id}/arrive` | 배정된 hauler | `{}` | `{status:"arrived"}` |
| `POST /v1/orders/{id}/inspect` | 주문한 recycler | `{bag_weights: [{bag_id, kg}], passed: bool, note?}` | 합격: `{status:"settled", settlement:{factory_krw, hauler_krw, platform_krw}}` (확정→정산 자동, platform 수수료 0 = 시범 무료). 불합격: `{status:"disputed"}` — **P0 정산은 주문 금액(goods_krw = 판매 total_kg × 단가) 기준. 검사 무게 차이에 따른 조정은 P1** |
| `GET /v1/orders/{id}` | 주문 당사자 3곳 | — | 주문 전체(상태 이력 포함 `history: [{from, to, by, at}]`) |

### 인계서 (3칸, 본인 칸만)
| `GET /v1/orders/{id}/handover` | 당사자 | — | `{emitter, carrier, processor, allbaro_no}` 각 칸은 `null` 또는 채워진 값 |
| `POST /v1/orders/{id}/handover/emitter` | 그 주문의 factory | `{}` | 칸 값: `{company_name, biz_no, waste_code, waste_name, bags: [{bag_id, kg}], carrier_name, prepared_at}` — 상태 picked_up 이후 |
| `POST /v1/orders/{id}/handover/carrier` | 배정 hauler | `{vehicle_no}` | `{company_name, vehicle_no, picked_up_at, total_kg, prepared_at}` — picked_up 이후 |
| `POST /v1/orders/{id}/handover/processor` | 주문 recycler | `{method}` | `{company_name, received_kg, method, prepared_at}` — confirmed/settled 이후 |
| `POST /v1/orders/{id}/handover/number` | 그 주문의 factory | `{allbaro_no}` | `{allbaro_no}` — 3칸 모두 채워진 뒤만(아니면 409) |
- 다른 회사 칸은 403. 값은 "올바로에 붙여넣을 값"이며 앱은 제출하지 않는다.
- waste_name은 `data/waste_codes.json`의 name.

### 별점
| `POST /v1/ratings` | 주문 당사자 | `{order_id, target: "factory"|"hauler"|"recycler", score: 1~5, comment?}` | `201 {id}` — allbaro_no가 있어야 함(없으면 409), 자기 자신 평가 403, 같은 평가자·대상 중복 409. factory와 recycler가 모두 1개 이상 남기면 주문 → `rated` |

### 기타
| `GET /v1/health` | `{ok:true, db:true, llm:{provider, model, available}}` |
| `GET /v1/agent-runs/{run_id}` | RunResult |
| `GET /v1/harness` | harness.yaml 내용 + 에이전트 카드 본문 |

## 4. 주문 상태
| 지금 | 갈 수 있는 곳 | 누가 |
|---|---|---|
| ordered | payment_held | 서버(주문 직후 가짜 PG 보류) |
| payment_held | dispatched, cancelled | hauler 수락 / recycler 취소 (**취소 API는 P1, P0에는 경로 없음**) |
| dispatched | picked_up | hauler |
| picked_up | arrived | hauler |
| arrived | confirmed, disputed | recycler 검사 |
| confirmed | settled | 서버(가짜 PG 정산) |
| settled | rated | 서버(양쪽 별점) |
- 이 표에 없는 변경은 409. 바뀔 때마다 `order_history`에 from·to·by(company_id)·at 저장.

## 5. 하네스 (분석팀 B)
- `harness/harness.yaml`이 팀·에이전트·flow·게이트·가정값의 단일 기준. 코드에 숫자 기준을 따로 적지 않는다.
- 에이전트 인터페이스: `run(ctx: dict, llm: LLMProvider | None) -> AgentResult`. 파일 1개 = 에이전트 1개.
- 실행: flow 순서대로 실행(앞 결과는 `ctx["results"][agent_id]`로 다음에 전달) → 게이트 3개 → 요약(orchestrator) → RunResult.
- 게이트: `evidence`, `wording`, `privacy` (`harness.yaml` 주석 참고). 막힌 주장은 `blocked=true`, `public_claims`에서 빠지고 `blocked_count`에 셈.
- 요약: LLM은 public_claims만 받아 요약, 주장에 없는 숫자가 있으면 게이트에서 막혀 1회 재요청 → 템플릿 요약.
- 에이전트별 P0 동작(LLM 없이도 동작해야 함):
  | 에이전트 | 코드(필수) | LLM(있으면) |
  |---|---|---|
  | ① profiling | 업종 문자열 키워드 → 나올 수 있는 부산물 후보 목록, level=`estimate`, "가입 때 고르기용 안내" | 안내 문장 |
  | ② vision | items 정규화(재질명 소문자, kg 합), 구성비 계산. note가 있으면 LLM이 재질 후보 추출 → level=`estimate`, 등급 계산에 안 씀 | note 읽기 |
  | ③ grading | 순도 = target_material kg / total kg, hazard 재질 있으면 grade=None, 기준은 assumptions.grade_thresholds | 없음 |
  | ④ bundling | nearby_listings(상태 posted·bundle_wait, 각 항목에 판매 공장 lat·lon 포함) 중 같은 waste_code·grade·반경 안 → 합계 kg, min_lot 충족 여부 | 설명 문장 |
  | ⑤ pricing | prices.json에서 target_material에 맞는 품목(예: pp → "PP 압축") 최근값, total_kg < min_lot이면 "모아서 팔기" 추천 | 설명 문장 |
  | ⑥ economics | 소각 위탁 시 드는 비용(INCIN-2026-09: 지자체 계약 전국평균, 소각재 처리 제외~포함) × 톤 = **아낄 수 있는 비용**, 판매 참고액(⑤ 잡색 압축품 매입가 × kg, VAT 포함·물류비 제외, 자투리 실제 매입가는 견적 확인 필요)을 따로 표시. level=`estimate`, `assumption` 근거 필수. '수입이 소각비보다 크다' 식 비교 문장 금지 | 설명 문장 |
  | ⑦ regulation | 체크리스트: recycler 허가(wma-25, wma-18-1), hauler 허가 확인 필요(wma-25), 인계서 각자 입력(wma-18-3) — law 근거 id 필수 | 조문 요약 문장 |
- LLM: `app/llm/base.py`의 `LLMProvider.chat(system, user, schema=None) -> LLMReply(text, data, model, ms)`. `ollama.py`(httpx, `/api/chat`, `format`=JSON 스키마, temperature 0), `claude.py`(공식 `anthropic` SDK, `messages.create`, 모델은 yaml, temperature 등 샘플링 파라미터 보내지 않음, 구조화 출력은 `output_config.format`), `mock.py`(테스트용), provider `off` → None.
- Claude SDK 사용법은 반드시 `/tmp/claude-1000/bundled-skills/2.1.310/61ee5df22b3d8c3ad4cec57e60406d6e/claude-api/python/claude-api/README.md`를 읽고 따른다(추측 금지). P0 테스트는 Claude를 실제로 부르지 않는다(키 없음).

## 6. 시드 (`backend/seed/gumi_demo.py`, 분석팀 A)
가상 회사만(실제 회사명 금지): 구미 가상 사출공장 3곳(가상사출A·B·C, 구미국가산단 근처 좌표), 재활용업체 1곳(가상리사이클, permit_codes ["51-03-01"]), 운반업체 1곳(가상운반, 같은 코드), 운영자 1곳. `python -m seed.gumi_demo`로 DB에 넣고 id 출력.

## 7. 완료 기준 (P0)
1. `pytest -q` 전부 통과 (LLM은 mock/off, Ollama 실호출 테스트는 Ollama 꺼져 있으면 skip).
2. 시나리오 테스트: 가입 → 허가 확인 → 마대 3개(PP 순도 0.97·0.92·0.85) 등록·등급(A·B·C 확인) + 기름 섞인 마대 1개(통과증 없음) → A 마대로 판매(now) → 주문 → 콜 수락(두 번째 수락 409) → 수거 → 도착 → 검사 합격 → 정산 → 인계서 3칸(남의 칸 403) → 번호 → 별점 → rated.
3. LLM_PROVIDER=off에서도 같은 시나리오 통과.
4. 금지 표현·근거 없는 숫자·전화번호가 들어간 주장은 public_claims에 없음(게이트 테스트).

## 8. v0.2 변경 (QA 반영, 2026-11-02) — 앞 절과 다르면 이 절이 우선
근거: docs/qa/10_종합.md (페르소나 6명). 사용자 결정 3개: 운임은 구매자 상한, 무게 차이 ±5% 안은 비례 정산, 불합격은 운영자 중재 후 3가지 중 선택.

### 8.1 입력 범위 (모두 400, 넘으면 DB에 아무것도 안 씀)
| 값 | 범위 |
|---|---|
| 마대 품목 kg | 0 초과 2,000 이하, 유한수. 품목 수 1~20. 마대 합계 2,000kg 이하 |
| 단가 price_krw_per_kg | 0 초과 100,000 이하 |
| 운임 freight_cap_krw, freight_krw | 1 이상 10,000,000 이하 정수 |
| 수거·검사 무게(마대별) | 0 초과 2,000 이하, 유한수 |
| lat / lon | -90~90 / -180~180, 유한수 |
| 경로 id, X-Company-Id, listing_id, bag_ids 원소 | 1 이상 2,147,483,647 이하 (넘으면 401/404처럼 '없음' 처리) |
| 문자열 | name·biz_no·vehicle_no 1~100자(공백만 불가), note·comment·method·inspect note 500자, allbaro_no 1~50자. NUL 문자 불가 |
| 배열 | bag_ids 1~50(중복 불가), permit_codes 0~30 |
| waste_code | data/waste_codes.json에 있는 코드만 (마대 등록·허가 코드 모두) |

### 8.2 회사·운영자
- `role: operator`는 공개 가입 불가(403). 운영자는 시드(`seed.gumi_demo`) 또는 환경변수 `OPERATOR_BOOTSTRAP_TOKEN`과 같은 값의 헤더 `X-Operator-Token`이 있을 때만 생성.
- recycler·hauler는 운영자 verify 전까지 verified=false(그대로). 운영자는 permit_codes가 비어 있는 업체를 verify할 수 없음(409).

### 8.3 운임 = 구매자가 정하는 상한
- `POST /v1/orders` 본문 `{listing_id, freight_cap_krw}`. 가짜 PG 보류 금액 = goods_krw + freight_cap_krw. 응답에 `freight_cap_krw`, `held_krw`.
- `GET /v1/calls` 항목: `{order_id, waste_code, waste_name, total_kg, bag_count, freight_cap_krw, distance_km, pickup:{lat,lon}, dropoff:{lat,lon}}` (distance_km = 직선거리, 소수 1자리).
- `POST /v1/calls/{order_id}/accept` `{freight_krw}`는 freight_cap_krw 이하만(넘으면 400).
- 정산 때 운반업체 = freight_krw, 남은 상한(cap − freight)은 구매자에게 돌려줌(`refund_krw`).

### 8.4 무게와 정산 (허용 오차 ±5%)
- `pickup`: 마대별 무게 저장. 합계가 판매 total_kg와 5% 넘게 다르면 응답에 `weight_warning: "등록 무게와 n% 차이"`(진행은 됨, history에 기록).
- `inspect` `{bag_weights, passed, note?}`:
  - passed=false → disputed.
  - passed=true이고 |검사 합계 − 판매 total_kg| / 판매 total_kg ≤ 0.05 → confirmed → settled. **factory_krw = round(검사 합계 kg × 단가)**, hauler_krw = freight_krw, platform_krw = 0, refund_krw = held_krw − factory_krw − hauler_krw.
  - passed=true여도 차이가 5% 초과 → disputed (`dispute_reason: "무게 차이 n%"`).
- 반올림은 원 단위 사사오입(ROUND_HALF_UP).

### 8.5 출구
| 경로 | 누가 | 언제 | 결과 |
|---|---|---|---|
| `POST /v1/orders/{id}/cancel` | 주문한 recycler | payment_held | cancelled, 보류 금액 전액 환불, 판매 → posted |
| `POST /v1/orders/{id}/release` | 배정 hauler 본인, 주문한 recycler, operator | dispatched(수거 전) | payment_held로 되돌림, 배정·운임 지움, 다시 콜 목록에 나옴 (기사 노쇼 대응) |
| `POST /v1/listings/{id}/withdraw` | 그 판매의 factory | posted, bundle_wait | withdrawn, 마대 풀림(다시 판매 가능) |
| `POST /v1/admin/orders/{id}/resolve` | operator | disputed | 본문 `{resolution, new_price_krw_per_kg?, treatment_fee_krw?, note}` |
- resolve 3가지:
  - `regrade` → settled. factory_krw = round(검사 합계 × new_price_krw_per_kg), 나머지 환불.
  - `treat` (재활용업체가 그 폐기물 처리 허가가 있다는 운영자 확인 전제) → settled. factory_krw = −treatment_fee_krw(공장이 처리비 냄, 가짜 PG), goods 전액 환불.
  - `return` → returned. goods 전액 환불, hauler_krw = freight_krw. 반송 운반 배차는 P1(문구로 안내).
- 반송·처리 전환의 적법성은 법률 자문 전(응답 `legal_note`에 "법률 자문 확인 필요" 고정 문구).

### 8.6 동시 요청
- 모든 주문 상태 변경은 `UPDATE … WHERE id=? AND status=<이전 상태>`의 영향 행 수로 판정, 0이면 409. (pickup·arrive·inspect·cancel·release·resolve 포함)
- 판매 생성 때 마대 선점은 `UPDATE bags SET listing_id=? WHERE id IN (…) AND listing_id IS NULL`, 영향 행 수가 마대 수와 다르면 전체 롤백 409.
- 인계서 칸·번호·별점: 인계서 번호 입력 후 3칸 잠김(409). UNIQUE 충돌은 409.
- 판매에 묶인(listing_id 있음) 마대는 재등급 409.

### 8.7 마대·등급 안전
- `harness.yaml` `assumptions.material_aliases`로 재질 이름을 표준 이름으로 바꾼 뒤 계산(예: 피피·폴리프로필렌·PP 자투리 → pp). 표에 없는 재질은 그대로 두고 reasons에 "인식 못 한 재질: X(확인 필요)".
- 위험어(hazard_materials)가 **note**에 있으면 통과증 보류: grade=None, reasons "메모에 위험 재질 언급(…)—품목에 넣거나 없음을 확인 후 다시 등급". 공장이 `POST /v1/bags/{id}/grade` `{confirm_no_hazard: true}`로 다시 요청하면 메모 위험어를 무시하고 계산(history에 확인자 기록). 품목(items)에 위험어가 있으면 확인으로도 못 풂.
- 위험어에 그리스·grease·solvent·용제·페인트·paint 추가.

### 8.8 화면용 조회 (모두 X-Company-Id 필요)
| 경로 | 누가 | 응답 |
|---|---|---|
| `GET /v1/me` | 모두 | `{id,name,role,verified,permit_codes,lat,lon}` |
| `GET /v1/me/bags` | factory | 내 마대 `[{id,waste_code,waste_name,target_material,total_kg,status,grade,purity,pass_id,qr,listing_id,created_at}]` |
| `GET /v1/bags/{id}` | 그 factory | 위 + items, reasons |
| `GET /v1/me/listings` | factory | 내 판매 전부(모든 상태) + bag_ids, order_id |
| `GET /v1/listings/{id}` | 누구나 | `{id,status,waste_code,waste_name,grade,target_material,purity_avg,composition:{재질:비율},total_kg,bag_count,price_krw_per_kg,factory_name,area:{lat,lon}(소수 2자리로 반올림)}` |
| `GET /v1/me/orders` | 모두(역할별 당사자 주문) | `[{id,status,role_in_order,waste_name,total_kg,goods_krw,freight_cap_krw,freight_krw,counterparty_names,updated_at}]` 최신순 |
| `GET /v1/listings` 항목에 waste_name·grade·bag_count·factory_name 추가 |
- 날짜는 모두 UTC ISO8601(+00:00 포함).

### 8.9 하네스(분석팀 B)
- Ollama `timeout_s: 15`. 한 실행(run) 안에서 LLM 호출이 한 번 실패하면 그 run의 나머지 LLM 호출은 건너뜀(템플릿). `/v1/health`의 `llm.available`은 실제 확인(Ollama `/api/tags` 1초, Claude는 키 존재 여부).
- **요약 뜻 검사(게이트 추가)**: (1) 요약·LLM 문장에 "[A-C] ?등급"이 있으면 grading 결과 등급과 같아야 함, 등급 없음이면 등급 글자 금지. (2) pricing data에 `relation: below|within|above`(입력 단가 vs 시세 범위)를 두고, 요약의 "범위 안/내·적정"·"낮"·"높" 표현이 relation과 어긋나면 차단. (3) 사용자가 쓴 문자열(회사 이름, 업종, 재질 이름, 메모)은 LLM 요약 입력에 원문으로 넣지 않음(코드가 만든 주장 문장만 넣고, 사용자 문자열은 "[입력값]"으로 가림). 업종 문자열이 공개 주장 문장에 그대로 들어가지 않게 profiling 문장도 고정 문구로.
- ② vision 후보는 메모에 실제로 나오는 단어(재질 별칭 포함)만, 최대 5개. 메모 위험어는 public 주장으로 "메모에 위험 재질 언급: …(사람 확인 필요)".
- 화면용 `summary`에서 `[agent:n]` 인용 꼬리표는 지움(검사는 지우기 전에 함).
- `/v1/harness`는 팀·에이전트·flow·카드만(LLM 주소·모델·assumptions 제외). `/v1/agent-runs/{id}`는 X-Company-Id 필요, 막힌 주장은 text를 "[차단됨]"으로 바꿔 반환.

### 8.10 v0.2 완료 기준
1. 위 각 항목에 회귀 테스트, `pytest -q` 전부 통과(SQLite) + 같은 테스트를 PostgreSQL(`DATABASE_URL=postgresql+psycopg://…`)에서도 통과.
2. QA 재현 사례(docs/qa/01~05의 '상' 항목)가 모두 막힘을 테스트로 확인.

## 9. v0.3 변경 (v0.2 재검사 반영, 2026-11-02) — 8절과 다르면 이 절이 우선
근거: docs/qa/20_v02_재검사.md(Sonnet, 수정 필요), docs/orchestra/sol_v02_review.md(Sol, 반려).

### 9.1 돈
- 금액 칸(goods·freight·held·factory·hauler·refund·fee 등)은 DB에서 BigInteger. 금액 상한은 판매 1건 100억 원(넘으면 판매 생성 400).
- kg은 소수 3자리(0.001kg), 단가는 소수 2자리로 입력 때 반올림해 저장. 합계·비율·금액 계산은 전부 `Decimal(str(값))`로(실수 덧셈 금지).
- **보류 금액 = round(goods × 1.05) + freight_cap**. 검사 무게가 +5%까지 늘어도 공장 몫을 깎지 않음(min으로 자르기 금지). refund = held − factory − hauler (항상 0 이상).
- regrade의 new_price는 원래 단가 이하만(초과 400). 
- treat 정산 칸: `factory_krw: 0`, `factory_charge_krw: 처리비`(공장이 따로 냄, 가짜 PG), `recycler_fee_krw: 처리비`(재활용업체가 받음), `hauler_krw`, `refund_krw = held − hauler`. 
- return: `factory_krw 0, hauler_krw, refund_krw = held − hauler`. 판매는 withdrawn, 마대는 listing_id 해제·통과증 삭제(status registered, 다시 등급 받아야 재판매).

### 9.2 동시 요청·순서
- 운반업체가 하는 변경(pickup·arrive·release)과 recycler·operator의 release는 `status=이전 AND hauler_id=<읽은 배정 업체>` 조건으로 UPDATE(재배차 뒤 이전 기사의 늦은 요청은 409).
- 판매 생성의 마대 선점 조건에 `pass_id IS NOT NULL AND grade=<판매 등급>` 추가(재등급과 경합 시 409).
- 인계서 칸 저장·번호 입력·별점(rated 전이)은 주문 행을 `SELECT … FOR UPDATE`로 잠근 뒤 처리(PostgreSQL). 양쪽 첫 별점이 동시에 와도 rated로 감.

### 9.3 AI 입력·출력
- **사용자 문자열은 주장(claim) 문장에 넣지 않음.** 회사 이름·업종·메모·재질 이름(별칭 표에 없는 것)은 `data`(기계용 칸)에만 두고, 문장에는 "[입력값]" 또는 표준 재질명만. reasons 문장도 같음. 그러면 LLM 입력은 자동으로 깨끗함.
- **등급·시세 판단 문장은 코드가 씀.** 요약 = 코드가 만든 사실 문장(등급, 가격이 시세보다 낮음/범위 안/높음) + LLM 문장. LLM 문장 중 등급(A/B/C·급·등급)이나 가격-시세 관계(범위·시세·적정·비싸·저렴·낮·높·초과·미만)를 말하는 문장은 통째로 뺌. 이 규칙은 LLM 설명 문장(public claims의 llm 주장)에도 같게.
- 확정처럼 말하는 표현 차단 목록 추가: "절약할 수 있", "아낄 수 있", "확실", "보장", "반드시" → 그 문장 뺌.
- 인용 꼬리표 지운 뒤 남는 ".,", ",,", "에 따라." 같은 찌꺼기 정리. 쉼표만 이어진 부분 제거.
- LLM 호출 1번에 전체 시간 상한 15초(응답이 조금씩 계속 와도 15초에 끊음).

### 9.4 접근
- `agent_runs`에 `company_ids`(요청 회사 + 그 거래 당사자들) 저장. `GET /v1/agent-runs/{id}`는 그 회사들과 operator만(아니면 404). 메모리 대체 조회는 operator만.
- `GET /v1/listings/{id}`: posted·bundle_wait는 로그인한 누구나, sold·withdrawn은 판매 공장·주문 당사자·operator만(아니면 404).
- `/v1/health`의 llm은 `{provider, available}`만(모델명 제외). `/v1/harness`는 operator가 아니면 팀·에이전트 이름·흐름만(카드 본문 제외).

### 9.5 완료 기준
- 9.1~9.4와 docs/qa/20_v02_재검사.md N1~N7, sol_v02_review.md 표의 각 행에 회귀 테스트. SQLite·PostgreSQL 모두 통과(동시성 테스트는 PostgreSQL).
