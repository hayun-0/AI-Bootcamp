계약서(`ARCHITECTURE.md`)와 두 검증팀의 독립 검토 보고서(`sonnet_review.md`, `sol_review.md`)를 먼저 읽고 사실 관계를 확인하겠습니다.
핵심 지적 사항들의 실제 구현을 확인하기 위해 관련 백엔드 코드 파일들을 읽어보겠습니다. (읽기 전용 사실 확인)
나머지 몇 개 파일(`bundling.py`, `deps.py`, `session.py`, `tests/acceptance/test_p0_acceptance.py`)도 빠르게 확인해 모든 항목의 사실을 대조하겠습니다.
`harness/harness.yaml`과 `backend/tests/acceptance/` 쪽 파일도 확인해보겠습니다.
`/plan` 슬래시 커맨드가 포함되어 있으므로, 판정 및 수정 계획 아티팩트(`implementation_plan.md`)도 함께 생성하면서 사용자 요청의 4가지 항목(1. 대조표, 2. 판정, 3. 필수/P1 구분, 4. 계약서 수정 항목)을 간결하고 명확하게 제시하겠습니다. 먼저 `implementation_plan.md`를 작성합니다.
이제 사용자가 요청한 4가지 형식에 맞춰 한국어로 짧고 명확하게 판정 결과를 출력합니다. (파일 및 심볼에 클릭 가능한 링크 포함)지휘부 **Argon**의 코드 대조 및 최종 판정 결과입니다. (상세 수정 계획은 [implementation_plan.md](file:///home/data/.gemini/antigravity-cli/brain/9ca3259f-da06-44d4-be72-f84daa56940b/implementation_plan.md) 참고)

---

### 1. 두 검토 대조표 (양쪽 일치 vs 단독 발견)

| 구분 | 지적 항목 | 위치 | Argon 판정 | 근거 (코드 사실 확인) |
|---|---|---|---|---|
| **양쪽 일치** | 별점 `rated` 전환을 평가자가 아닌 **평가 대상(`target`)**으로 셈 | [`create_rating`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/api/ratings.py#L39-L41) | **확인** (필수) | `rated = {x.target ...}`로 되어 있어 hauler 혼자 양쪽을 평가해도 `rated`가 되고, 공장과 재활용업체가 둘 다 hauler를 평가하면 `rated`가 안 됨 |
| **양쪽 일치** | `nearby_listings`에 **공장 좌표 누락** → 묶음 추천 항상 0건 | [`create_listing`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/api/listings.py#L47-L51), [`bundling.run`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/agents/trade/bundling.py#L25-L31) | **확인** (필수) | [`brief(o)`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/api/listings.py#L21-L23)에 `lat`/`lon`이 없어 `unknown_pos`로만 빠짐 |
| **양쪽 일치** | **반올림 후** 등급 임계값 비교 (`0.94996 → 0.95 → A`) | [`compute_grade`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/tools/calc.py#L31-L43) | **확인** (필수) | `round(..., 4)` 한 값을 `th[g]`와 비교함 |
| **양쪽 일치** | `grade_bag` 오류 검사 순서 불일치 (404가 역할 403보다 먼저 나감) | [`grade_bag`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/api/bags.py#L42-L43) | **확인** (필수) | `get_or_404`가 `need_role(me, "factory")` 위에 있음 |
| **양쪽 일치** | `Infinity` / `10**100` 거대 정수 입력 시 500 에러 | [`bags.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/api/bags.py#L15), [`deps.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/api/deps.py#L11) | **타당** | `allow_inf_nan=False`는 1줄 수정이라 반영하되, 64비트 초과 정수 방어는 MVP에서 과장 |
| **양쪽 일치** | 압축품 시세를 자투리 마대에 곱해 판매 수입 추정·소각비와 단순 비교 | [`pricing.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/agents/trade/pricing.py#L21-L30), [`economics.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/agents/review/economics.py#L19-L29) | **타당** (문구만 보완) | 계약서 §5가 "⑤ 값 그대로 × 톤"을 지시했으므로 계산 공식은 계약 준수. 단, `assumption` 근거와 "압축품 기준 참고치" 단서 문구만 추가 |
| **양쪽 일치** | 마대 동시 게시(Race condition) 시 이중 리스팅 | [`create_listing`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/api/listings.py#L38-L46) | **타당** (P1) | `orders`/`calls`는 조건부 UPDATE가 있으나 `Bag.listing_id`는 ORM 대입. 단, SQLite 단일 프로세스 학생 MVP에서는 P1로 충분 |
| **양쪽 일치** | 게이트 한글 수사("삼십 퍼센트")·국제 전화번호(`+82`) 우회 | [`gates.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/harness/gates.py#L10-L20) | **과장** (P1) | P0 레드팀 방어 수준을 넘어서는 자연어 파싱 요구 |
| **양쪽 일치** | 누구나 `operator`로 공개 가입 후 셀프 승인 가능 | [`ARCHITECTURE.md`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/docs/ARCHITECTURE.md#L58) | **타당** (계약 문제) | Sol 분석대로 계약서가 허용한 P0 단순화임(구현 버그 아님) |
| **Sol 단독** | `vision` 에이전트가 `note`에서 추출한 LLM 숫자가 `public_claims`에 노출 | [`vision.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/agents/sorting/vision.py#L35-L44), [`gates.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/harness/gates.py#L34) | **확인** (필수) | `ev("assumption", ...)`가 붙어 있어 `NUMBER_OK_KINDS`를 통과함. `candidates`에서 숫자를 빼야 안전 |
| **Sol 단독** | 상태표에 `payment_held → cancelled`가 있으나 취소 API 없음 | [`orders.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/services/orders.py#L11) | **확인** (계약 문제) | 계약서 §3 API 표에 취소 엔드포인트 자체가 정의되지 않음 |
| **Sonnet 단독** | [`conftest.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/tests/conftest.py#L13)가 `app.main`을 먼저 import해 디스크 `masdae.db` 사용 | [`conftest.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/tests/conftest.py#L13), [`session.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/db/session.py#L8) | **확인** (필수) | import 시점에 `engine`이 생성되어 메모리 DB 기본값이 안 먹힘 |
| **Sonnet 단독** | 위험 재질 영문만 검사(`"오일"` 통과), 검사 무게 변동 시 정산액 미조정, Ollama 타임아웃 120초 | [`calc.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/tools/calc.py#L27), [`orders.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/api/orders.py#L183) | **과장** (P1) | `harness.yaml` 기준이 영문 리스트이고, 정산 차액 조정은 계약서 §0에서 "P0 밖"으로 명시됨 |

---

### 2. 최종 판정: **수정 후 통과 (Conditional Pass)**
- 거래 한 바퀴(가입~별점)와 Ollama 연동, 42개 테스트가 정상 동작하므로 구조 재설계나 재검토는 불필요합니다. 아래 **필수 6건(모두 1~5줄 수정)**만 반영하면 즉시 P0 통과입니다.

---

### 3. 이번 라운드 필수 수정 vs P1 이관 목록

**반드시 고칠 것 (P0 필수 — 작고 명확한 버그 6건)**
1. **별점 `rated` 전환 조건 수정** ([`ratings.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/api/ratings.py#L39-L41)): `x.target` → `x.rater_id` 기준으로 공장(`factory_id`)과 재활용업체(`recycler_id`)가 둘 다 평가했는지 확인.
2. **묶음 추천에 공장 좌표 연결** ([`listings.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/api/listings.py#L47-L50)): `nearby_listings`에 판매 공장의 `lat`, `lon`을 포함해 [`bundling.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/agents/trade/bundling.py)가 실제 반경 계산을 수행하도록 수정.
3. **등급 판정 시 반올림 전 순도 사용** ([`calc.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/tools/calc.py#L31-L43)): 임계값(`th[g]`) 비교는 원시 비율로 하고, 결과 dict의 `purity`만 반올림.
4. **Vision `note` 후보에서 숫자 제거** ([`vision.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/agents/sorting/vision.py#L35)): LLM이 반환한 `candidates`에서 숫자를 제거(또는 숫자 포함 항목 제외)하여 미검증 숫자가 `public_claims`에 나가지 않게 차단 + [`economics.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/agents/review/economics.py#L28) 판매 수입 추정에 `assumption` 근거 및 단서 문구 보강.
5. **오류 검사 순서 및 `Infinity` 입력 방어** ([`bags.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/api/bags.py#L15-L44), [`listings.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/api/listings.py#L18), [`orders.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/app/api/orders.py#L36)): `grade_bag`에서 `need_role`을 `get_or_404`보다 먼저 실행하고, float 필드에 `allow_inf_nan=False` 추가.
6. **테스트 DB 격리 순서 수정** ([`conftest.py`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend/tests/conftest.py#L1-L14)): `app.main` import 전에 `DATABASE_URL=sqlite://` 기본값 설정.

**P1로 미룰 것 (선택 — 학생 MVP 과설계 방지)**
- 동시성 경쟁 조건 방어(`listings` 마대 선점 조건부 UPDATE, `pickup`/`inspect`/`ratings` 동시 요청 락)
- 한글 수사("삼십 퍼센트", "백 퍼센트"), 단위/부호 변조, 국제 전화번호(`+82`) 정규식 고도화
- 64비트 초과 정수(`10**100`) ID/헤더 입력 방어
- 위험 재질 한글 동의어 사전("오일", "폐유" 등) 매핑
- 도착 검사 무게(`inspect_weights`) 차이에 따른 정산 금액 재계산
- `/v1/health`에서 실제 Ollama 네트워크 ping 체크

---

### 4. 계약서([`docs/ARCHITECTURE.md`](file:///mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/docs/ARCHITECTURE.md)) 자체를 고쳐야 하는 항목
1. **주문 취소(`cancelled`) 처리 (§4 주문 상태표)**: §3 API에는 취소 엔드포인트가 없는데 §4 상태표에만 `payment_held → cancelled (recycler 취소)`가 남아 있습니다. P0 범위에서 `cancelled`를 빼거나 "취소 API는 P1"로 명시해야 합니다.
2. **묶음 추천 후보의 상태 기준 (§2, §5 ④ bundling)**: `nearby_listings`에 `posted`(즉시 판매)만 넣을지 `bundle_wait`(묶음 대기)도 포함할지 명시되지 않았습니다 (`posted`, `bundle_wait` 모두 포함하는 것으로 명시 권장).
3. **정산 기준 무게 명시 (§3 `orders/{id}/inspect`)**: P0에서는 도착 검사 무게(`inspect_weights`)와 무관하게 최초 주문 금액(`goods_krw = listing.total_kg × price`)으로 정산하며 무게 차액 조정은 P0 밖임을 한 줄로 못 박아야 혼선이 없습니다.
4. **운영자(`operator`) 가입 규칙 (§3 `POST /v1/companies`)**: 누구나 `role="operator"`로 즉시 `verified=true` 가입이 가능한 것은 P0 시연·테스트 편의용 허용임을 명시해야 보안 결함 오인을 막을 수 있습니다.
