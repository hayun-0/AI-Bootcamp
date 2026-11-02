# 계약서 애매: 성공 HTTP 코드가 생략된 조회·변경 API는 200으로 해석한다.
# 계약서 애매: 통과증 없음은 pass_id/qr의 생략 또는 null 모두 허용한다.
# 계약서 애매: payment_held에는 배정 hauler가 없으므로, 허가 확인된 운반업체의
# pickup은 배정 권한 검사보다 상태 충돌을 먼저 판단해 409로 해석한다.
# 계약서 애매: 인계서 번호·차량번호·처리방법의 형식은 미정이므로 가상 문자열을 쓴다.
# 계약서 애매: 메모리 DB 초기화 API는 없다. 테스트마다 새 회사를 HTTP로 가입시키고
# 콜 목록은 해당 주문 ID로 찾는다. DB·세션·구현 내부에는 접근하지 않는다.

import os
from itertools import count

import pytest
from fastapi.testclient import TestClient


# app을 가져오기 전에 반드시 적용한다. 실제 LLM과 파일 DB는 사용하지 않는다.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["LLM_PROVIDER"] = "off"
os.environ.setdefault("OPERATOR_BOOTSTRAP_TOKEN", "qa-token")  # v0.2: 운영자는 토큰으로만 가입

WASTE_CODE = "51-03-01"
OTHER_WASTE_CODE = "51-28-02"
PRICE = 317
FREIGHT = 12000
COMPANY_NUMBERS = count(1000000000)


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as http:
        yield http


def test_runs_on_in_memory_engine(client):
    from app.db.session import engine as _engine
    if _engine.dialect.name != "sqlite":
        pytest.skip("PostgreSQL 등 실제 DB로 돌릴 때는 메모리 DB 확인을 건너뜀")
    # 실제 get_session(override 아님)이 메모리 DB(StaticPool)를 쓰는지 확인 — 파일 DB 오염 방지
    from app.db.session import engine
    from app.main import app
    from sqlalchemy.pool import StaticPool

    assert engine.url.database in (None, "", ":memory:")
    assert isinstance(engine.pool, StaticPool)
    assert not app.dependency_overrides


def headers(company):
    return {"X-Company-Id": str(company["id"])}


def post(client, path, company=None, payload=None, expected=200):
    response = client.post(
        path,
        headers=headers(company) if company is not None else {},
        json={} if payload is None else payload,
    )
    assert response.status_code == expected, (
        f"POST {path}: expected {expected}, got "
        f"{response.status_code}: {response.text}"
    )
    return response.json()


def get(client, path, company):
    response = client.get(path, headers=headers(company))
    assert response.status_code == 200, f"GET {path}: {response.text}"
    return response.json()


def register(client, role, permit_codes=None):
    number = next(COMPANY_NUMBERS)
    payload = {
        "name": f"가상{role}-{number}",
        "role": role,
        "biz_no": str(number),
        "lat": 36.10,
        "lon": 128.38,
    }
    if role in ("recycler", "hauler"):
        payload.update(
            permit_no=f"가상허가-{number}",
            permit_codes=[WASTE_CODE] if permit_codes is None else permit_codes,
        )
    if role == "operator":  # v0.2 계약 8.2
        r = client.post("/v1/companies", json=payload, headers={"X-Operator-Token": os.environ["OPERATOR_BOOTSTRAP_TOKEN"]})
        assert r.status_code == 201, r.text
        company = r.json()
    else:
        company = post(client, "/v1/companies", payload=payload, expected=201)
    assert isinstance(company["id"], int)
    assert company["name"] == payload["name"]
    assert company["role"] == role
    assert company["verified"] is (role in ("factory", "operator"))
    if role in ("recycler", "hauler"):
        assert company["permit_codes"] == payload["permit_codes"]
    return company


def verify(client, operator, company):
    result = post(client, f"/v1/admin/companies/{company['id']}/verify", operator)
    assert result["id"] == company["id"]
    assert result["verified"] is True


@pytest.fixture
def parties(client):
    factories = [register(client, "factory") for _ in range(3)]
    recycler = register(client, "recycler")
    haulers = [register(client, "hauler") for _ in range(2)]
    operator = register(client, "operator")
    for company in [recycler, *haulers]:
        verify(client, operator, company)
    return {
        "factories": factories,
        "factory": factories[0],
        "recycler": recycler,
        "haulers": haulers,
        "operator": operator,
    }


def graded_bag(client, factory, pp_kg=97, impurity="paper", grade="A"):
    items = [{"material": "pp", "kg": pp_kg},
             {"material": impurity, "kg": 100 - pp_kg}]
    bag = post(
        client, "/v1/bags", factory,
        {"waste_code": WASTE_CODE, "target_material": "pp", "items": items},
        expected=201,
    )
    assert bag["factory_id"] == factory["id"]
    assert bag["waste_code"] == WASTE_CODE
    assert bag["target_material"] == "pp"
    assert bag["items"] == items
    assert bag["total_kg"] == pytest.approx(100)
    assert bag["status"] == "registered"
    result = post(client, f"/v1/bags/{bag['id']}/grade", factory)
    assert result["bag_id"] == bag["id"]
    assert result["run_id"]
    assert result["grade"]["target_material"] == "pp"
    assert result["grade"]["purity"] == pytest.approx(pp_kg / 100)
    assert result["grade"]["grade"] == grade
    assert result["grade"]["hazard"] is (impurity == "oil")
    if grade is None:
        assert result.get("pass_id") is None
        assert result.get("qr") is None
    else:
        assert result["pass_id"] is not None
        assert result["qr"] == f"MDP-{result['pass_id']}-{bag['id']}"
    return bag


def listing(client, factory, bag):
    result = post(
        client, "/v1/listings", factory,
        {"bag_ids": [bag["id"]], "mode": "now", "price_krw_per_kg": PRICE},
        expected=201,
    )
    assert result["status"] == "posted"
    assert result["grade"] == "A"
    assert result["waste_code"] == WASTE_CODE
    assert result["total_kg"] == pytest.approx(bag["total_kg"])
    assert result["price_krw_per_kg"] == PRICE
    return result


def order(client, recycler, sale):
    result = post(
        client, "/v1/orders", recycler, {"listing_id": sale["id"], "freight_cap_krw": FREIGHT}, expected=201,
    )
    assert result["status"] == "payment_held"
    assert result["listing_id"] == sale["id"]
    assert result["goods_krw"] == round(sale["total_kg"] * PRICE)
    return result


@pytest.fixture
def held_order(client, parties):
    bag = graded_bag(client, parties["factory"])
    sale = listing(client, parties["factory"], bag)
    return {**parties, "bag": bag, "order": order(client, parties["recycler"], sale)}


def accept(client, hauler, order_id):
    result = post(client, f"/v1/calls/{order_id}/accept", hauler,
                  {"freight_krw": FREIGHT})
    assert result["order_id"] == order_id
    assert result["status"] == "dispatched"
    assert result["hauler_id"] == hauler["id"]


def settle(client, trade):
    order_id = trade["order"]["id"]
    hauler = trade["haulers"][0]
    weights = [{"bag_id": trade["bag"]["id"], "kg": 100}]
    accept(client, hauler, order_id)
    pickup = post(client, f"/v1/orders/{order_id}/pickup", hauler,
                  {"bag_weights": weights})
    assert pickup["status"] == "picked_up"
    arrival = post(client, f"/v1/orders/{order_id}/arrive", hauler)
    assert arrival["status"] == "arrived"
    inspection = post(client, f"/v1/orders/{order_id}/inspect", trade["recycler"],
                      {"bag_weights": weights, "passed": True})
    assert inspection["status"] == "settled"
    assert inspection["settlement"]["platform_krw"] == 0
    return inspection


@pytest.fixture
def settled_order(client, held_order):
    settle(client, held_order)
    return held_order


def fill_handover(client, trade):
    base = f"/v1/orders/{trade['order']['id']}/handover"
    emitter = post(client, f"{base}/emitter", trade["factory"])
    carrier = post(client, f"{base}/carrier", trade["haulers"][0],
                   {"vehicle_no": "가상차량-01"})
    processor = post(client, f"{base}/processor", trade["recycler"],
                     {"method": "가상 PP 재활용"})
    assert emitter["company_name"] == trade["factory"]["name"]
    assert emitter["waste_code"] == WASTE_CODE
    assert emitter["bags"] == [{"bag_id": trade["bag"]["id"], "kg": 100}]
    assert carrier["company_name"] == trade["haulers"][0]["name"]
    assert carrier["vehicle_no"] == "가상차량-01"
    assert carrier["total_kg"] == pytest.approx(100)
    assert processor["company_name"] == trade["recycler"]["name"]
    assert processor["received_kg"] == pytest.approx(100)
    assert processor["method"] == "가상 PP 재활용"
    handover = get(client, base, trade["factory"])
    assert handover["emitter"] == emitter
    assert handover["carrier"] == carrier
    assert handover["processor"] == processor
    assert handover["allbaro_no"] is None


def test_contract_scenario_full_trade_to_rated(client, parties):
    factories = parties["factories"]
    a = graded_bag(client, factories[0], 97, grade="A")
    graded_bag(client, factories[1], 92, grade="B")
    graded_bag(client, factories[2], 85, grade="C")
    graded_bag(client, factories[0], 97, impurity="oil", grade=None)
    sale = listing(client, factories[0], a)
    purchase = order(client, parties["recycler"], sale)
    order_id = purchase["id"]
    for hauler in parties["haulers"]:
        calls = get(client, "/v1/calls", hauler)
        matching = [call for call in calls if call["order_id"] == order_id]
        assert len(matching) == 1
        call = matching[0]
        assert call["waste_code"] == WASTE_CODE
        assert call["total_kg"] == pytest.approx(100)
        assert call["pickup"] == {"lat": 36.10, "lon": 128.38}
        assert call["dropoff"] == {"lat": 36.10, "lon": 128.38}

    # settle의 첫 수락 직후, 수거 전에 두 번째 수락의 충돌을 확인한다.
    first, second = parties["haulers"]
    accept(client, first, order_id)
    post(client, f"/v1/calls/{order_id}/accept", second,
         {"freight_krw": FREIGHT}, expected=409)
    weights = [{"bag_id": a["id"], "kg": 100}]
    assert post(client, f"/v1/orders/{order_id}/pickup", first,
                {"bag_weights": weights})["status"] == "picked_up"
    assert post(client, f"/v1/orders/{order_id}/arrive", first)["status"] == "arrived"
    inspection = post(client, f"/v1/orders/{order_id}/inspect", parties["recycler"],
                      {"bag_weights": weights, "passed": True})
    assert inspection["status"] == "settled"
    assert inspection["settlement"]["platform_krw"] == 0
    assert get(client, f"/v1/orders/{order_id}", factories[0])["status"] == "settled"

    base = f"/v1/orders/{order_id}/handover"
    assert get(client, base, factories[0]) == {
        "emitter": None, "carrier": None, "processor": None, "allbaro_no": None,
    }
    post(client, f"{base}/emitter", parties["recycler"], expected=403)
    post(client, f"{base}/carrier", factories[0],
         {"vehicle_no": "가상차량-01"}, expected=403)
    post(client, f"{base}/processor", first,
         {"method": "가상 PP 재활용"}, expected=403)
    trade = {**parties, "bag": a, "order": purchase}
    fill_handover(client, trade)
    number = f"가상인계-{order_id}"
    assert post(client, f"{base}/number", factories[0],
                {"allbaro_no": number})["allbaro_no"] == number
    assert get(client, base, parties["recycler"])["allbaro_no"] == number
    for author, target in [(factories[0], "recycler"), (parties["recycler"], "factory")]:
        rating = post(client, "/v1/ratings", author,
                      {"order_id": order_id, "target": target, "score": 5}, expected=201)
        assert rating["id"] is not None
    assert get(client, f"/v1/orders/{order_id}", factories[0])["status"] == "rated"


def test_unverified_recycler_order_is_403(client, parties):
    buyer = register(client, "recycler")
    bag = graded_bag(client, parties["factory"])
    sale = listing(client, parties["factory"], bag)
    post(client, "/v1/orders", buyer, {"listing_id": sale["id"], "freight_cap_krw": FREIGHT}, expected=403)


def test_wrong_permit_hauler_accept_is_403(client, held_order):
    hauler = register(client, "hauler", permit_codes=[OTHER_WASTE_CODE])
    verify(client, held_order["operator"], hauler)
    post(client, f"/v1/calls/{held_order['order']['id']}/accept", hauler,
         {"freight_krw": FREIGHT}, expected=403)


def test_payment_held_pickup_is_409(client, held_order):
    # 지휘부 결정(계약 v0.1.1 검사 순서): 배정 전 pickup은 당사자 아님 403,
    # 상태 충돌 409는 배정된 운반업체가 수거 전에 arrive 할 때로 확인한다.
    order_id = held_order['order']['id']
    hauler = held_order["haulers"][0]
    post(client, f"/v1/orders/{order_id}/pickup", hauler,
         {"bag_weights": [{"bag_id": held_order["bag"]["id"], "kg": 100}]},
         expected=403)
    verify(client, held_order["operator"], hauler)
    post(client, f"/v1/calls/{order_id}/accept", hauler, {"freight_krw": FREIGHT})
    post(client, f"/v1/orders/{order_id}/arrive", hauler, expected=409)


def test_incomplete_handover_number_is_409(client, settled_order):
    base = f"/v1/orders/{settled_order['order']['id']}/handover"
    post(client, f"{base}/emitter", settled_order["factory"])
    post(client, f"{base}/carrier", settled_order["haulers"][0],
         {"vehicle_no": "가상차량-01"})
    assert get(client, base, settled_order["factory"])["processor"] is None
    post(client, f"{base}/number", settled_order["factory"],
         {"allbaro_no": "가상인계-미완성"}, expected=409)


def test_rating_without_handover_number_is_409(client, settled_order):
    fill_handover(client, settled_order)
    post(client, "/v1/ratings", settled_order["factory"],
         {"order_id": settled_order["order"]["id"], "target": "recycler", "score": 5},
         expected=409)


def test_missing_company_header_is_401(client):
    post(client, "/v1/bags", payload={
        "waste_code": WASTE_CODE,
        "target_material": "pp",
        "items": [{"material": "pp", "kg": 100}],
    }, expected=401)
