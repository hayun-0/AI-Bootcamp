from app.contracts import Claim, Evidence
from app.harness.gates import apply_gates, check_summary
from app.harness.runner import run_flow
from app.llm.mock import MockProvider


def C(text, *ev, level="fact"):
    return Claim(agent_id="t", text=text, level=level, evidence=list(ev))


INPUT = Evidence(kind="input", ref="x")


def blocked(c):
    public, n = apply_gates([c])
    return n == 1 and not public and c.blocked and c.block_reasons


def test_forbidden_phrase_blocked():
    assert blocked(C("이 마대는 재활용 불가 확정입니다", INPUT))


def test_number_without_number_evidence_blocked():
    assert blocked(C("순도는 0.97입니다", Evidence(kind="llm", ref="m")))
    assert blocked(C("순도는 0.97입니다"))      # 근거 없음


def test_phone_number_blocked():
    assert blocked(C("담당자 연락처 010-1234-5678 입니다", INPUT))


def test_unknown_law_id_blocked():
    assert blocked(C("법 제99조에 따라 확인 필요", Evidence(kind="law", ref="wma-999")))
    assert blocked(C("법 제25조 확인 필요", INPUT))            # 법을 말하는데 law 근거 없음


def test_unknown_dataset_blocked():
    assert blocked(C("시세 300원", Evidence(kind="dataset", ref="NOPE")))


def test_good_claim_passes():
    c = C("법 제25조 허가 확인 필요", Evidence(kind="law", ref="wma-25"))
    public, n = apply_gates([c])
    assert public == [c] and n == 0


def test_blocked_excluded_from_public_in_run():
    bad = C("재활용 절대 불가", INPUT)
    ok = C("정상 항목", INPUT)
    public, n = apply_gates([bad, ok])
    assert public == [ok] and n == 1


def test_summary_with_invented_number_falls_back_to_template():
    mock = MockProvider(reply_fn=lambda s, u, sc: {"summary": "순도는 99%이고 등급은 A입니다"})
    r = run_flow("grade_bag", {"bag": {"target_material": "pp", "items": [{"material": "pp", "kg": 97}, {"material": "pe", "kg": 3}]}}, llm=mock)
    assert r.summary_source == "template"
    assert "99" not in r.summary
    summary_calls = [c for c in mock.calls if c[2] and "summary" in c[2].get("properties", {})]
    assert len(summary_calls) == 2        # 첫 요청 + 재요청 1회
    assert any(e.type == "gate" and e.payload.get("target") == "summary" and not e.payload["passed"] for e in r.events)


def test_summary_retry_can_succeed():
    answers = iter(["새 숫자 77 이 있음", "PP 순도 0.97입니다"])
    mock = MockProvider(reply_fn=lambda s, u, sc: {"summary": next(answers)} if sc and "summary" in sc["properties"] else "")
    r = run_flow("grade_bag", {"bag": {"target_material": "pp", "items": [{"material": "pp", "kg": 97}, {"material": "pe", "kg": 3}]}}, llm=mock)
    assert r.summary_source == "llm" and r.summary.endswith("PP 순도 0.97입니다")


def test_check_summary_rules():
    claims = [C("총 100 kg", INPUT)]
    assert check_summary("총 100 kg입니다 [vision:1]", claims) == []
    assert check_summary("총 200 kg입니다", claims)
    assert check_summary("총 100 kg 문의 02-123-4567", claims)
