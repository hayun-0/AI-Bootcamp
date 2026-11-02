import pytest

from app.harness.runner import run_flow
from app.llm.mock import MockProvider
from app.tools.calc import compute_grade


def bag(pp, other=0.0, other_name="pe", note=None):
    items = [{"material": "PP", "kg": pp}]
    if other:
        items.append({"material": other_name, "kg": other})
    return {"id": 1, "waste_code": "51-03-01", "target_material": "pp", "items": items, "note": note}


CTX = {
    "profile_company": {"company": {"name": "가상사출A", "role": "factory", "industry": "플라스틱 사출 성형"}},
    "grade_bag": {"bag": bag(97, 3, note="pp 사출 스프루, 피이 조금 섞임")},
    "listing_advice": {
        "listing": {"waste_code": "51-03-01", "grade": "A", "total_kg": 800, "price_krw_per_kg": 300, "target_material": "pp"},
        "bags": [{"waste_code": "51-03-01", "grade": "A", "target_material": "pp", "total_kg": 800}],
        "nearby_listings": [
            {"id": 9, "waste_code": "51-03-01", "grade": "A", "total_kg": 500, "lat": 36.1, "lon": 128.4},
            {"id": 10, "waste_code": "51-03-01", "grade": "B", "total_kg": 900, "lat": 36.1, "lon": 128.4},
            {"id": 11, "waste_code": "51-03-01", "grade": "A", "total_kg": 700, "lat": 37.5, "lon": 127.0},
        ],
        "factory": {"lat": 36.1, "lon": 128.4},
    },
    "deal_check": {"order": {"id": 1}, "listing": {"waste_code": "51-03-01"}, "factory": {}, "recycler": {"permit_codes": ["51-03-01"]}},
}


@pytest.mark.parametrize("flow", list(CTX))
@pytest.mark.parametrize("mode", ["off", "mock"])
def test_each_flow_runs(flow, mode):
    llm = None if mode == "off" else MockProvider()
    r = run_flow(flow, CTX[flow], llm=llm)
    assert r.flow == flow and r.plan and len(r.results) == len(r.plan)
    assert r.public_claims and r.blocked_count == 0
    assert r.events[0].type == "plan" and r.events[-1].type == "done"
    if mode == "off":
        assert r.summary_source == "template" and r.llm["available"] is False
    else:
        assert r.summary_source == "llm" and r.llm["available"] is True
        assert any(res.used_llm for res in r.results)


def test_grade_bag_data_and_vision_candidates():
    llm = MockProvider(reply_fn=lambda s, u, sc: {"candidates": ["oil", "pe", "피이"]} if sc and "candidates" in sc["properties"] else "")
    r = run_flow("grade_bag", CTX["grade_bag"], llm=llm)
    g = r.results[1].data["grade"]
    assert g["grade"] == "A" and g["purity"] == 0.97 and not g["hazard"]
    vis = r.results[0]
    assert vis.data["note_candidates"] == ["pe"]          # 메모에 실제로 나온 말만(oil 제외), 별칭은 표준 이름으로 한 번
    assert not vis.data["note_hazard"]


@pytest.mark.parametrize("pp,other,grade", [(97, 3, "A"), (92, 8, "B"), (85, 15, "C"), (50, 50, None)])
def test_grade_thresholds(pp, other, grade):
    g = compute_grade("pp", [{"material": "PP", "kg": pp}, {"material": "pe", "kg": other}])
    assert g["grade"] == grade


def test_grade_hazard_is_none():
    g = compute_grade("PP", [{"material": "pp", "kg": 99}, {"material": "Oil", "kg": 1}])
    assert g["grade"] is None and g["hazard"] is True
    r = run_flow("grade_bag", {"bag": bag(99, 1, "oil")}, llm=None)
    assert r.results[1].data["grade"]["grade"] is None


def test_pricing_and_bundling_numbers():
    r = run_flow("listing_advice", CTX["listing_advice"], llm=None)
    pricing, bundling, econ = r.results
    assert pricing.data["price"]["source"] == "D2-PRICE" and pricing.data["recommend_gather"] is True
    assert [m["id"] for m in bundling.data["matches"]] == [9]       # 같은 등급·반경 안 1건만
    assert bundling.data["bundle_kg"] == 1300 and bundling.data["meets_min_lot"] is True
    assert econ.data["incineration"]["low"] == round(0.8 * 156241)


def test_regulation_law_refs():
    r = run_flow("deal_check", CTX["deal_check"], llm=None)
    refs = {e.ref for c in r.public_claims for e in c.evidence if e.kind == "law"}
    assert {"wma-25", "wma-18-1", "wma-18-3"} <= refs


def test_unknown_flow_and_llm_failure_do_not_raise():
    r = run_flow("nope", {}, llm=None)
    assert r.events[-1].type == "error" or any(e.type == "error" for e in r.events)
    r = run_flow("grade_bag", CTX["grade_bag"], llm=MockProvider(fail=True))
    assert r.summary_source == "template" and r.llm["available"] is False
    assert r.results[1].data["grade"]["grade"] == "A"
    r = run_flow("grade_bag", {"bag": None}, llm=None)    # 이상한 입력도 예외 없음
    assert r.run_id
