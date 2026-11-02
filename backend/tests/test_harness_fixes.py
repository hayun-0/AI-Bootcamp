"""분석팀 수정 라운드 회귀 테스트(하네스/계산)."""
from app.harness.runner import run_flow
from app.llm.mock import MockProvider
from app.tools.calc import compute_grade

COND = "잡색 압축품 매입가 기준, VAT 포함·물류비 제외, 자투리 실제 매입가는 견적 확인 필요"
LISTING = {
    "listing": {"waste_code": "51-03-01", "grade": "A", "total_kg": 800, "price_krw_per_kg": 300, "target_material": "pp"},
    "bags": [{"waste_code": "51-03-01", "grade": "A", "target_material": "pp", "total_kg": 800}],
    "nearby_listings": [], "factory": {"lat": 36.1, "lon": 128.4},
}


def test_grade_uses_unrounded_purity():
    g = compute_grade("pp", [{"material": "pp", "kg": 94.996}, {"material": "pe", "kg": 5.004}])
    assert g["grade"] == "B" and g["purity"] == 0.95


def test_vision_candidates_with_digits_dropped():
    llm = MockProvider(reply_fn=lambda s, u, sc: {"candidates": ["pp 777kg", "pe"]} if sc and "candidates" in sc["properties"] else "")
    bag = {"target_material": "pp", "items": [{"material": "pp", "kg": 97}, {"material": "pe", "kg": 3}], "note": "pp 777kg, pe 섞임"}
    r = run_flow("grade_bag", {"bag": bag}, llm=llm)
    assert not any("777" in c.text for c in r.public_claims)
    assert "pe" in r.results[0].data["note_candidates"]


def test_economics_and_pricing_wording():
    r = run_flow("listing_advice", LISTING, llm=None)
    texts = [c.text for c in r.public_claims]
    econ = next(c for c in r.public_claims if c.agent_id == "economics" and "판매 참고액" in c.text)
    saved = next(c for c in r.public_claims if c.agent_id == "economics" and "아낄 수 있는 비용" in c.text)
    assert COND in econ.text and econ.level == "estimate" and "assumption" in {e.kind for e in econ.evidence}
    assert "assumption" in {e.kind for e in saved.evidence}
    assert not any(w in t for t in texts for w in ("수입이 소각비", "수입의 하한", "수입의 상한"))
    price_claim = next(c for c in r.public_claims if c.agent_id == "pricing" and "올리려는 단가" in c.text)
    assert price_claim.level == "estimate" and COND in price_claim.text


def test_hazard_korean_alias_and_substring():
    for name in ("오일", "폐유 섞임", "engine oil", "OIL"):
        g = compute_grade("pp", [{"material": "pp", "kg": 99}, {"material": name, "kg": 1}])
        assert g["grade"] is None and g["hazard"] is True, name


def test_hazard_english_word_boundary():
    from app.tools.calc import compute_grade
    g = compute_grade("PP", [{"material": "PP", "kg": 96}, {"material": "aluminum foil", "kg": 4}])
    assert g["hazard"] is False and g["grade"] == "A"
