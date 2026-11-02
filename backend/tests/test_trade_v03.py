"""계약 v0.3 거래 쪽 회귀 테스트(ARCHITECTURE §9.1·9.2·9.4, docs/qa/20 N1~N7, docs/orchestra/sol_v02_review.md)."""
import threading
import time

import pytest
from sqlalchemy import select, text, update

from app.api import listings as listings_api
from app.db.models import AgentRun, Bag, BagPass, Listing, Order
from app.db.session import get_session
from app.main import app
from app.services.orders import change_status
from tests.conftest import CODE, H, PG_URL
from tests.test_trade_scenario import make_bag
from tests.test_trade_v02 import (arrived, codes, disputed, inspect, listed, ordered, pickup, resolve, run_parallel,
                                  world)

IS_PG = PG_URL.startswith("postgresql")
pg_only = pytest.mark.skipif(not IS_PG, reason="동시성은 PostgreSQL에서 확인")


def db():
    """테스트용 DB 세션(앱과 같은 엔진)."""
    return next(app.dependency_overrides[get_session]())


def grade(client, w, b):
    assert client.post(f"/v1/bags/{b}/grade", headers=H(w["f"]), json={}).status_code == 200


def sell(client, w, bag_ids, price=10):
    return client.post("/v1/listings", headers=H(w["f"]), json={"bag_ids": bag_ids, "mode": "now", "price_krw_per_kg": price})


def pure_bag(client, w, kg):
    r = client.post("/v1/bags", headers=H(w["f"]), json={"waste_code": CODE, "target_material": "pp",
                                                         "items": [{"material": "PP", "kg": kg}]})
    assert r.status_code == 201, r.text
    grade(client, w, r.json()["id"])
    return r.json()["id"]


# ── N1: 금액 int4 초과 (BigInteger) ──
def test_n1_goods_over_int4_orders_and_settles(client):
    w = world(client)
    bags = []
    for _ in range(11):
        b = make_bag(client, w["f"], 1940, 60)
        grade(client, w, b)
        bags.append(b)
    lid = sell(client, w, bags, price=100_000)
    assert lid.status_code == 201, lid.text
    o = client.post("/v1/orders", headers=H(w["r"]), json={"listing_id": lid.json()["id"], "freight_cap_krw": 10_000_000})
    assert o.status_code == 201, o.text
    assert o.json()["goods_krw"] == 2_200_000_000 and o.json()["held_krw"] == 2_310_000_000 + 10_000_000
    oid = o.json()["id"]
    assert client.post(f"/v1/calls/{oid}/accept", headers=H(w["h1"]), json={"freight_krw": 10_000_000}).status_code == 200
    ws = [{"bag_id": b, "kg": 2000} for b in bags]
    assert client.post(f"/v1/orders/{oid}/pickup", headers=H(w["h1"]), json={"bag_weights": ws}).status_code == 200
    client.post(f"/v1/orders/{oid}/arrive", headers=H(w["h1"]), json={})
    r = client.post(f"/v1/orders/{oid}/inspect", headers=H(w["r"]), json={"bag_weights": ws, "passed": True})
    assert r.json()["settlement"] == {"factory_krw": 2_200_000_000, "hauler_krw": 10_000_000, "platform_krw": 0,
                                      "refund_krw": 110_000_000}


def test_listing_goods_cap_100eok_is_400_and_leaves_bag_free(client, monkeypatch):
    w = world(client)
    b = pure_bag(client, w, 100)
    monkeypatch.setattr(listings_api, "MAX_GOODS", 999)          # 100kg × 10원 = 1,000원 > 999
    assert sell(client, w, [b]).status_code == 400
    assert client.get("/v1/me/bags", headers=H(w["f"])).json()[0]["listing_id"] is None
    monkeypatch.setattr(listings_api, "MAX_GOODS", 1000)         # 경계는 통과
    assert sell(client, w, [b]).status_code == 201


# ── §9.1 입력 반올림 ──
def test_kg_rounds_to_3_and_price_to_2_at_input(client):
    w = world(client)
    r = client.post("/v1/bags", headers=H(w["f"]), json={"waste_code": CODE, "target_material": "pp",
                                                         "items": [{"material": "PP", "kg": 1.0005}, {"material": "pe", "kg": 0.0004}]})
    assert r.status_code == 400                                  # 0.0004 → 0.000 은 0 초과가 아님
    r = client.post("/v1/bags", headers=H(w["f"]), json={"waste_code": CODE, "target_material": "pp",
                                                         "items": [{"material": "PP", "kg": 1.0005}]})
    assert r.status_code == 201 and r.json()["total_kg"] == 1.001
    b = r.json()["id"]
    grade(client, w, b)
    assert sell(client, w, [b], price=0.004).status_code == 400
    ls = sell(client, w, [b], price=1.005)
    assert ls.status_code == 201 and ls.json()["price_krw_per_kg"] == 1.01


# ── Sol: float 합 0.1+0.2 ──
def test_sol_float_sum_01_plus_02_is_exact_and_boundary_holds(client):
    w = world(client)
    b1, b2 = pure_bag(client, w, 0.1), pure_bag(client, w, 0.2)
    ls = sell(client, w, [b1, b2], price=1000)
    assert ls.status_code == 201 and ls.json()["total_kg"] == 0.3        # 0.30000000000000004 가 아님
    o = client.post("/v1/orders", headers=H(w["r"]), json={"listing_id": ls.json()["id"], "freight_cap_krw": 100}).json()
    client.post(f"/v1/calls/{o['id']}/accept", headers=H(w["h1"]), json={"freight_krw": 100})
    ws = [{"bag_id": b1, "kg": 0.1}, {"bag_id": b2, "kg": 0.2}]
    assert client.post(f"/v1/orders/{o['id']}/pickup", headers=H(w["h1"]), json={"bag_weights": ws}).status_code == 200
    client.post(f"/v1/orders/{o['id']}/arrive", headers=H(w["h1"]), json={})
    # 0.285kg = 정확히 -5% → 허용 오차 안(5% 초과 아님)
    r = client.post(f"/v1/orders/{o['id']}/inspect", headers=H(w["r"]),
                    json={"bag_weights": [{"bag_id": b1, "kg": 0.095}, {"bag_id": b2, "kg": 0.19}], "passed": True})
    assert r.json()["status"] == "settled", r.text
    assert r.json()["settlement"]["factory_krw"] == 285


# ── N5 / Sol: min() 삭감 ──
def test_n5_sol_plus_5pct_with_cap_equals_freight_pays_full(client):
    w = world(client)
    b, lid, oid = ordered(client, w, kg=100, price=10, cap=100, freight=100)
    assert client.get(f"/v1/orders/{oid}", headers=H(w["r"])).json()["held_krw"] == 1050 + 100
    pickup(client, w, oid, b, 100)
    client.post(f"/v1/orders/{oid}/arrive", headers=H(w["h1"]), json={})
    s = inspect(client, w, oid, b, 105).json()["settlement"]
    assert s == {"factory_krw": 1050, "hauler_krw": 100, "platform_krw": 0, "refund_krw": 0}


def test_n5_plus_4pct_cap_equals_freight(client):
    w = world(client)
    b, lid, oid = ordered(client, w, kg=100, price=500, cap=20000, freight=20000)
    pickup(client, w, oid, b, 100)
    client.post(f"/v1/orders/{oid}/arrive", headers=H(w["h1"]), json={})
    s = inspect(client, w, oid, b, 104).json()["settlement"]
    assert s["factory_krw"] == 52000 and s["hauler_krw"] == 20000 and s["refund_krw"] == 500


def test_plus_5pct_never_makes_refund_negative_even_when_goods_rounds_down(client):
    """goods=round(3×0.8)=2 이지만 +5% 검사의 공장 몫은 round(3.15×0.8)=3 — 보류는 반올림 전 곱으로 계산."""
    w = world(client)
    b = make_bag(client, w["f"], 2.91, 0.09)
    grade(client, w, b)
    lid = sell(client, w, [b], price=0.8).json()["id"]
    oid = client.post("/v1/orders", headers=H(w["r"]), json={"listing_id": lid, "freight_cap_krw": 100}).json()["id"]
    client.post(f"/v1/calls/{oid}/accept", headers=H(w["h1"]), json={"freight_krw": 100})
    pickup(client, w, oid, b, 3)
    client.post(f"/v1/orders/{oid}/arrive", headers=H(w["h1"]), json={})
    s = inspect(client, w, oid, b, 3.15).json()["settlement"]
    assert s["factory_krw"] == 3 and s["refund_krw"] == 0 and s["hauler_krw"] == 100


# ── N4: regrade 단가 상향 금지 ──
def test_n4_regrade_price_must_not_exceed_original(client):
    w = world(client)
    b, oid = disputed(client, w, price=10)
    assert resolve(client, w, oid, resolution="regrade", new_price_krw_per_kg=10.01).status_code == 400
    assert resolve(client, w, oid, resolution="regrade", new_price_krw_per_kg=2000).status_code == 400
    assert client.get(f"/v1/orders/{oid}", headers=H(w["op"])).json()["status"] == "disputed"
    r = resolve(client, w, oid, resolution="regrade", new_price_krw_per_kg=10)
    assert r.status_code == 200 and r.json()["settlement"]["factory_krw"] == 900


def test_regrade_cannot_pay_more_than_held(client):
    w = world(client)
    b, lid, oid = arrived(client, w, kg=100, price=10, cap=1000)
    assert inspect(client, w, oid, b, 500, passed=False).json()["status"] == "disputed"   # 500kg × 10 = 5000 > 보류
    assert resolve(client, w, oid, resolution="regrade", new_price_krw_per_kg=10).status_code == 400
    assert client.get(f"/v1/orders/{oid}", headers=H(w["op"])).json()["status"] == "disputed"


# ── §9.1 treat / return 정산 칸 ──
def test_treat_settlement_fields(client):
    w = world(client)
    b, oid = disputed(client, w)
    s = resolve(client, w, oid, resolution="treat", treatment_fee_krw=300).json()["settlement"]
    assert s["factory_krw"] == 0 and s["factory_charge_krw"] == 300 and s["recycler_fee_krw"] == 300
    assert s["hauler_krw"] == 1000 and s["refund_krw"] == 6050 - 1000


# ── N3: return이 마대를 풂 ──
def test_n3_return_frees_bags_withdraws_listing_and_removes_pass(client):
    w = world(client)
    b, oid = disputed(client, w)
    lid = client.get(f"/v1/orders/{oid}", headers=H(w["op"])).json()["listing_id"]
    rt = resolve(client, w, oid, resolution="return").json()
    assert rt["status"] == "returned" and rt["settlement"]["factory_krw"] == 0
    bag = client.get(f"/v1/bags/{b}", headers=H(w["f"])).json()
    assert bag["listing_id"] is None and bag["pass_id"] is None and bag["status"] == "registered"
    assert [l["status"] for l in client.get("/v1/me/listings", headers=H(w["f"])).json() if l["id"] == lid] == ["withdrawn"]
    assert sell(client, w, [b]).status_code == 409                      # 통과증이 없으므로 다시 등급 전에는 판매 불가
    grade(client, w, b)
    assert sell(client, w, [b]).status_code == 201


# ── Sol: 재등급 vs 판매 생성 경합 (결정적 재현) ──
def test_sol_regrade_between_checks_and_claim_is_409(client, monkeypatch):
    w = world(client)
    b = pure_bag(client, w, 100)
    real = listings_api.dsum

    def regrade_now(values):
        """판매 요청이 통과증·등급을 읽은 직후, 선점 UPDATE 전에 재등급이 끝난 상황."""
        monkeypatch.setattr(listings_api, "dsum", real)
        s = db()
        s.execute(update(Bag).where(Bag.id == b).values(grade=None, status="rejected"))
        s.query(BagPass).filter_by(bag_id=b).delete()
        s.commit()
        s.close()
        return real(values)

    monkeypatch.setattr(listings_api, "dsum", regrade_now)
    assert sell(client, w, [b]).status_code == 409
    s = db()
    assert s.get(Bag, b).listing_id is None
    s.close()


def test_listing_claim_requires_pass_and_same_grade(client, monkeypatch):
    """통과증은 있지만 마대 등급이 바뀐 경우도 선점 불가."""
    w = world(client)
    b = pure_bag(client, w, 100)
    real = listings_api.dsum

    def regrade_now(values):
        monkeypatch.setattr(listings_api, "dsum", real)
        s = db()
        s.execute(update(Bag).where(Bag.id == b).values(grade="C"))
        s.commit()
        s.close()
        return real(values)

    monkeypatch.setattr(listings_api, "dsum", regrade_now)
    assert sell(client, w, [b]).status_code == 409


# ── Sol: 재배차 뒤 이전 기사의 늦은 요청 (결정적 재현) ──
def _reassigned(client, w):
    """h1 배정 → (h1이 읽음) → release → h2 수락. h1이 읽은 Order 객체를 돌려준다."""
    b, lid, oid = ordered(client, w, freight=100)
    s = db()
    stale = s.get(Order, oid)
    assert stale.hauler_id == w["h1"]
    assert client.post(f"/v1/orders/{oid}/release", headers=H(w["h1"]), json={}).status_code == 200
    assert client.post(f"/v1/calls/{oid}/accept", headers=H(w["h2"]), json={"freight_krw": 200}).status_code == 200
    return b, oid, s, stale


@pytest.mark.parametrize("to", ["picked_up", "payment_held"])
def test_sol_stale_hauler_request_after_reaccept_is_409(client, to):
    from fastapi import HTTPException
    w = world(client)
    b, oid, s, stale = _reassigned(client, w)
    with pytest.raises(HTTPException) as e:
        change_status(s, stale, to, w["h1"])        # to=picked_up: 늦은 pickup, payment_held: 늦은 release
    assert e.value.status_code == 409
    s.rollback()
    s.close()
    o = client.get(f"/v1/orders/{oid}", headers=H(w["op"])).json()
    assert o["status"] == "dispatched" and o["hauler_id"] == w["h2"] and o["freight_krw"] == 200


def test_sol_stale_recycler_release_after_reaccept_is_409(client):
    """recycler·operator의 release도 읽은 배정 업체(h1) 기준 → 재배차 뒤 늦은 요청은 409."""
    from fastapi import HTTPException
    w = world(client)
    b, oid, s, stale = _reassigned(client, w)
    with pytest.raises(HTTPException) as e:
        change_status(s, stale, "payment_held", w["r"], note="release", hauler_id=None, freight_krw=None)
    assert e.value.status_code == 409
    s.rollback()
    s.close()
    assert client.get(f"/v1/orders/{oid}", headers=H(w["op"])).json()["hauler_id"] == w["h2"]


def test_old_hauler_http_requests_after_reassign_are_409_others_403(client):
    w = world(client)
    b, oid, s, stale = _reassigned(client, w)
    s.close()
    assert pickup(client, w, oid, b, 100).status_code == 409            # 이전 기사 → 상태 충돌
    assert client.post(f"/v1/orders/{oid}/arrive", headers=H(w["h1"]), json={}).status_code == 409
    assert client.post(f"/v1/orders/{oid}/release", headers=H(w["h1"]), json={}).status_code == 409
    assert client.get(f"/v1/orders/{oid}", headers=H(w["op"])).json()["hauler_id"] == w["h2"]
    other = client.post("/v1/companies", json={"name": "x", "role": "hauler", "biz_no": "1", "lat": 1, "lon": 1,
                                                "permit_codes": [CODE]}).json()["id"]
    assert client.post(f"/v1/orders/{oid}/release", headers=H(other), json={}).status_code == 403   # 무관한 기사


# ── Sol: 인계서 칸 저장 vs 번호 입력 (PostgreSQL 행 잠금) ──
@pg_only
def test_sol_handover_save_waits_for_order_lock_then_409(client):
    w = world(client)
    b, lid, oid = arrived(client, w)
    inspect(client, w, oid, b, 100)
    client.post(f"/v1/orders/{oid}/handover/emitter", headers=H(w["f"]), json={})
    client.post(f"/v1/orders/{oid}/handover/carrier", headers=H(w["h1"]), json={"vehicle_no": "12가3456"})
    client.post(f"/v1/orders/{oid}/handover/processor", headers=H(w["r"]), json={"method": "R-1"})
    s = db()
    s.execute(select(Order).where(Order.id == oid).with_for_update()).scalar_one()     # 번호 입력 중인 요청이 행을 잠금
    result = {}
    t = threading.Thread(target=lambda: result.update(r=client.post(
        f"/v1/orders/{oid}/handover/carrier", headers=H(w["h1"]), json={"vehicle_no": "변조"})))
    t.start()
    time.sleep(1.0)
    assert t.is_alive()                                                   # 잠금 때문에 기다리는 중
    s.execute(update(Order).where(Order.id == oid).values(allbaro_no="AB-1"))
    s.commit()
    s.close()
    t.join(10)
    assert result["r"].status_code == 409
    assert client.get(f"/v1/orders/{oid}/handover", headers=H(w["f"])).json()["carrier"]["vehicle_no"] == "12가3456"


# ── Sol: 양쪽 첫 별점 동시 ──
@pg_only
@pytest.mark.parametrize("round_", range(3))
def test_sol_concurrent_first_ratings_reach_rated(client, round_):
    w = world(client)
    b, lid, oid = arrived(client, w)
    inspect(client, w, oid, b, 100)
    client.post(f"/v1/orders/{oid}/handover/emitter", headers=H(w["f"]), json={})
    client.post(f"/v1/orders/{oid}/handover/carrier", headers=H(w["h1"]), json={"vehicle_no": "12가3456"})
    client.post(f"/v1/orders/{oid}/handover/processor", headers=H(w["r"]), json={"method": "R-1"})
    client.post(f"/v1/orders/{oid}/handover/number", headers=H(w["f"]), json={"allbaro_no": "AB-1"})
    calls = [lambda: client.post("/v1/ratings", headers=H(w["f"]), json={"order_id": oid, "target": "recycler", "score": 5}),
             lambda: client.post("/v1/ratings", headers=H(w["r"]), json={"order_id": oid, "target": "factory", "score": 4})]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(2) as ex:
        res = [f.result() for f in [ex.submit(c) for c in calls]]
    assert codes(res) == [201, 201]
    assert client.get(f"/v1/orders/{oid}", headers=H(w["op"])).json()["status"] == "rated"


# ── §9.4 AgentRun.company_ids ──
def test_agent_run_company_ids_actor_and_deal_parties(client):
    w = world(client)
    b, lid, oid = ordered(client, w)           # 등급(f) + 판매광고(f) + 주문 점검(r, f)
    s = db()
    runs = {r.flow: r.company_ids for r in s.execute(select(AgentRun)).scalars()}
    s.close()
    assert runs["grade_bag"] == [w["f"]] and runs["listing_advice"] == [w["f"]]
    assert runs["deal_check"] == sorted([w["r"], w["f"]])
    assert runs["profile_company"] in ([w["f"]], [w["f2"]])


# ── N7 / §9.4 ──
def test_n7_listing_detail_visibility_for_sold_and_withdrawn(client):
    w = world(client)
    b, lid = listed(client, w)
    assert client.get(f"/v1/listings/{lid}", headers=H(w["h2"])).status_code == 200            # posted: 누구나
    client.post("/v1/orders", headers=H(w["r"]), json={"listing_id": lid, "freight_cap_krw": 10})   # sold
    seen = lambda who: client.get(f"/v1/listings/{lid}", headers=H(w[who])).status_code
    assert seen("f") == 200 and seen("r") == 200 and seen("op") == 200
    assert seen("h2") == 404 and seen("f2") == 404
    client.post(f"/v1/calls/{client.get('/v1/me/orders', headers=H(w['r'])).json()[0]['id']}/accept",
                headers=H(w["h1"]), json={"freight_krw": 5})
    assert seen("h1") == 200                                                                # 배정된 기사도 당사자
    b2, lid2 = listed(client, w)
    client.post(f"/v1/listings/{lid2}/withdraw", headers=H(w["f"]), json={})
    wd = lambda who: client.get(f"/v1/listings/{lid2}", headers=H(w[who])).status_code
    assert wd("f") == 200 and wd("op") == 200 and wd("r") == 404 and wd("f2") == 404


def test_n7_health_llm_has_only_provider_and_available(client):
    assert set(client.get("/v1/health").json()["llm"]) == {"provider", "available"}


def test_listing_detail_composition_masks_unknown_material(client):
    """v0.3 9.3: 공개 판매 상세의 구성비에 사용자 재질명 원문 대신 [입력값]."""
    w = world(client)
    r = client.post("/v1/bags", headers=H(w["f"]), json={"waste_code": "51-03-01", "target_material": "PP",
                    "items": [{"material": "pp", "kg": 97}, {"material": "수상한재질XYZ", "kg": 3}]})
    bid = r.json()["id"]
    assert client.post(f"/v1/bags/{bid}/grade", headers=H(w["f"]), json={}).json()["grade"]["grade"] == "A"
    lid = client.post("/v1/listings", headers=H(w["f"]), json={"bag_ids": [bid], "mode": "now", "price_krw_per_kg": 100}).json()["id"]
    comp = client.get(f"/v1/listings/{lid}", headers=H(w["r"])).json()["composition"]
    assert set(comp) == {"pp", "[입력값]"} and "수상한재질XYZ".lower() not in str(comp).lower()
