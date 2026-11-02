# v0.3 반영(지휘부 통합): 보류 금액·treat 정산 칸·regrade 단가 자리수·팔린 판매 상세 접근을 계약 9절에 맞춤
# 계약서 애매: 8.1 첫 문장의 '모두 400'과 id 행이 충돌한다. id는 행의 401/404를 우선한다.
# 계약서 애매: 8.8 '모두 헤더 필요'와 판매 상세 '누구나'는 인증된 타사 조회 허용으로 읽는다.
# 계약서 애매: cancel/resolve의 금액 응답 위치가 없다. 응답 또는 주문 상세의
# 최상위/settlement에서 확인한다. resolve는 8.3에 따라 미사용 cap도 환불하며,
# treat의 음수 factory 금액은 별도 가짜 PG 청구이므로 구매자 환불에 더하지 않는다.
# 계약서 애매: regrade 단가/처리비 범위와 확인자 history 구조는 미정이라 유효값만 사용한다.
# 계약서 애매: me/listings 기본 필드는 3절 판매 응답의 advice를 제외한 필드로 읽는다.
"""v0.2 블라인드 HTTP 인수 테스트. 구현 모듈/DB를 직접 조회하거나 조작하지 않는다."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ["LLM_PROVIDER"] = "off"
os.environ["OPERATOR_BOOTSTRAP_TOKEN"] = "qa-token"

from app.main import app  # noqa: E402 -- 반드시 위 환경변수 설정 이후 import


WASTE_CODE = "51-03-01"
WASTE_NAME = next(
    row["name"]
    for row in json.loads(
        (Path(__file__).resolve().parents[3] / "data/waste_codes.json").read_text(
            encoding="utf-8"
        )
    )
    if row["code"] == WASTE_CODE
)
HUGE_ID = 10**50
CAP = 3000
FREIGHT = 2000


def headers(company):
    return {"X-Company-Id": str(company["id"])}


def request(client, method, path, company=None, body=None, status=200):
    kwargs = {"headers": headers(company) if company else {}}
    if body is not None:
        kwargs["json"] = body
    response = client.request(method, "/v1" + path, **kwargs)
    assert response.status_code == status, (method, path, response.status_code, response.text)
    return response.json()


def fields(value, names):
    assert isinstance(value, dict), value
    assert set(names.split()) <= value.keys(), value


def company_payload(role, **overrides):
    token = uuid4().hex
    return {
        "name": f"가상 QA {role} {token}",
        "role": role,
        "biz_no": token,
        "lat": 36.1234,
        "lon": 128.4567,
        "permit_no": f"가상허가-{token}",
        "permit_codes": [WASTE_CODE] if role in {"recycler", "hauler"} else [],
        **overrides,
    }


def join(client, role, **overrides):
    response = client.post(
        "/v1/companies",
        json=company_payload(role, **overrides),
        headers={"X-Operator-Token": "qa-token"} if role == "operator" else {},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def parties(client):
    result = {role: join(client, role) for role in ("operator", "factory", "recycler", "hauler")}
    for role in ("recycler", "hauler"):
        assert result[role]["verified"] is False
        verified = request(
            client, "POST", f"/admin/companies/{result[role]['id']}/verify",
            result["operator"], {},
        )
        assert verified["verified"] is True
    return result


def bag_payload(**overrides):
    return {
        "waste_code": WASTE_CODE,
        "target_material": "pp",
        "items": [{"material": "pp", "kg": 100}],
        **overrides,
    }


def make_bag(client, parties, **overrides):
    return request(client, "POST", "/bags", parties["factory"], bag_payload(**overrides), 201)


def grade(client, parties, bag, **body):
    return request(client, "POST", f"/bags/{bag['id']}/grade", parties["factory"], body)


def make_listing(client, parties, *, price=100, mode="now"):
    bag = make_bag(client, parties)
    result = grade(client, parties, bag)
    assert result["grade"]["grade"] == "A"
    listing = request(client, "POST", "/listings", parties["factory"], {
        "bag_ids": [bag["id"]], "mode": mode, "price_krw_per_kg": price,
    }, 201)
    return bag, listing


def make_order(client, parties, *, price=100):
    bag, listing = make_listing(client, parties, price=price)
    order = request(client, "POST", "/orders", parties["recycler"], {
        "listing_id": listing["id"], "freight_cap_krw": CAP,
    }, 201)
    return bag, listing, order


def accept(client, parties, order):
    result = request(client, "POST", f"/calls/{order['id']}/accept", parties["hauler"], {
        "freight_krw": FREIGHT,
    })
    assert result["status"] == "dispatched"
    return result


def weights(bag, kg):
    return {"bag_weights": [{"bag_id": bag["id"], "kg": kg}]}


def arrive(client, parties, bag, order, *, kg=100):
    accept(client, parties, order)
    pickup = request(client, "POST", f"/orders/{order['id']}/pickup", parties["hauler"], weights(bag, kg))
    assert pickup["status"] == "picked_up"
    result = request(client, "POST", f"/orders/{order['id']}/arrive", parties["hauler"], {})
    assert result["status"] == "arrived"
    return pickup


def inspect(client, parties, bag, order, *, kg=100, passed=True):
    return request(client, "POST", f"/orders/{order['id']}/inspect", parties["recycler"], {
        **weights(bag, kg), "passed": passed, "note": "가상 QA 도착 검사",
    })


def detail(client, parties, order):
    return request(client, "GET", f"/orders/{order['id']}", parties["recycler"])


def money(response, order_detail, **expected):
    for key, amount in expected.items():
        found = [
            value[key]
            for document in (response, order_detail)
            for value in (document, document.get("settlement") or {})
            if key in value
        ]
        assert found, ("금액 필드 없음", key, response, order_detail)
        assert all(value == amount for value in found), (key, amount, found)


def assert_utc_dates(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if child is not None and (key.endswith("_at") or key == "at"):
                assert isinstance(child, str) and child.endswith("+00:00"), (key, child)
                assert datetime.fromisoformat(child).utcoffset() == timedelta(0)
            assert_utc_dates(child)
    elif isinstance(value, list):
        for child in value:
            assert_utc_dates(child)


def test_operator_signup_requires_bootstrap_token_and_nonempty_permits(client, parties):
    for supplied in ({}, {"X-Operator-Token": "wrong-token"}):
        response = client.post("/v1/companies", json=company_payload("operator"), headers=supplied)
        assert response.status_code == 403, response.text
    operator = join(client, "operator")
    assert operator["verified"] is True
    for role in ("recycler", "hauler"):
        unlicensed = join(client, role, permit_codes=[])
        request(client, "POST", f"/admin/companies/{unlicensed['id']}/verify", parties["operator"], {}, 409)


@pytest.mark.parametrize("invalid", [
    {"items": [{"material": "pp", "kg": 2001}]},
    {"items": [{"material": "pp", "kg": 1100}, {"material": "pe", "kg": 1000}]},
    {"waste_code": "does-not-exist"},
    {"items": []},
    {"items": [{"material": "pp", "kg": 1}] * 21},
    {"note": "x" * 501},
    {"note": "NUL\x00문자"},
])
def test_invalid_bag_input_is_400_without_persisting(client, parties, invalid):
    before = request(client, "GET", "/me/bags", parties["factory"])
    request(client, "POST", "/bags", parties["factory"], bag_payload(**invalid), 400)
    assert request(client, "GET", "/me/bags", parties["factory"]) == before


def test_nan_coordinates_and_unknown_permit_code_are_400(client):
    # httpx의 json= 직렬화기는 NaN을 거절하므로 HTTP 원문으로 보낸다.
    payload = company_payload("factory", lat=float("nan"))
    response = client.post("/v1/companies", content=json.dumps(payload), headers={"Content-Type": "application/json"})
    assert response.status_code == 400, response.text
    request(client, "POST", "/companies", body=company_payload("hauler", permit_codes=["does-not-exist"]), status=400)


def test_freight_and_measurement_out_of_range_do_not_change_order(client, parties):
    bag, listing = make_listing(client, parties)
    before = request(client, "GET", "/me/orders", parties["recycler"])
    request(client, "POST", "/orders", parties["recycler"], {
        "listing_id": listing["id"], "freight_cap_krw": 1e10,
    }, 400)
    assert request(client, "GET", "/me/orders", parties["recycler"]) == before
    assert request(client, "GET", f"/listings/{listing['id']}", parties["factory"])["status"] == "posted"
    order = request(client, "POST", "/orders", parties["recycler"], {
        "listing_id": listing["id"], "freight_cap_krw": CAP,
    }, 201)
    request(client, "POST", f"/calls/{order['id']}/accept", parties["hauler"], {"freight_krw": 1e10}, 400)
    assert detail(client, parties, order)["status"] == "payment_held"
    accept(client, parties, order)
    request(client, "POST", f"/orders/{order['id']}/pickup", parties["hauler"], weights(bag, 2001), 400)
    assert detail(client, parties, order)["status"] == "dispatched"
    request(client, "POST", f"/orders/{order['id']}/pickup", parties["hauler"], weights(bag, 100))
    request(client, "POST", f"/orders/{order['id']}/arrive", parties["hauler"], {})
    request(client, "POST", f"/orders/{order['id']}/inspect", parties["recycler"], {
        **weights(bag, 2001), "passed": True,
    }, 400)
    assert detail(client, parties, order)["status"] == "arrived"


def test_huge_ids_are_missing_instead_of_server_errors(client, parties):
    response = client.get("/v1/me", headers={"X-Company-Id": str(HUGE_ID)})
    assert response.status_code == 401, response.text
    for path, role in ((f"/bags/{HUGE_ID}", "factory"), (f"/listings/{HUGE_ID}", "factory"), (f"/orders/{HUGE_ID}", "recycler")):
        request(client, "GET", path, parties[role], status=404)
    request(client, "POST", "/orders", parties["recycler"], {"listing_id": HUGE_ID, "freight_cap_krw": CAP}, 404)
    request(client, "POST", "/listings", parties["factory"], {
        "bag_ids": [HUGE_ID], "mode": "now", "price_krw_per_kg": 100,
    }, 404)


def test_freight_cap_call_fields_and_unused_cap_refund(client, parties):
    bag, _, order = make_order(client, parties)
    assert order["goods_krw"] == 10000
    assert order["freight_cap_krw"] == CAP
    assert order["held_krw"] == 13500  # v0.3 9.1: round(goods×1.05)+cap
    calls = request(client, "GET", "/calls", parties["hauler"])
    call = next(row for row in calls if row["order_id"] == order["id"])
    fields(call, "order_id waste_code waste_name total_kg bag_count freight_cap_krw distance_km pickup dropoff")
    assert call["waste_name"] == WASTE_NAME
    assert call["waste_code"] == WASTE_CODE
    assert call["bag_count"] == 1 and call["total_kg"] == 100
    assert call["freight_cap_krw"] == CAP
    assert call["distance_km"] == 0  # 서로 같은 좌표로 가입한 두 회사
    for key in ("pickup", "dropoff"):
        assert call[key] == {"lat": 36.1234, "lon": 128.4567}
    request(client, "POST", f"/calls/{order['id']}/accept", parties["hauler"], {"freight_krw": CAP + 1}, 400)
    assert detail(client, parties, order)["status"] == "payment_held"
    arrive(client, parties, bag, order)
    result = inspect(client, parties, bag, order)
    assert result["status"] == "settled"
    money(result, detail(client, parties, order), factory_krw=10000, hauler_krw=FREIGHT, platform_krw=0, refund_krw=1500)  # v0.3


@pytest.mark.parametrize("kg,price", [(97, 100), (97, 100.5), (95, 100), (105, 100)])
def test_inspection_within_five_percent_uses_weight_and_half_up(client, parties, kg, price):
    bag, _, order = make_order(client, parties, price=price)
    arrive(client, parties, bag, order)
    result = inspect(client, parties, bag, order, kg=kg)
    assert result["status"] == "settled"
    factory = int((Decimal(str(kg)) * Decimal(str(price))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    money(result, detail(client, parties, order), factory_krw=factory, hauler_krw=FREIGHT, platform_krw=0,
          refund_krw=order["held_krw"] - factory - FREIGHT)


def test_large_weight_difference_warns_at_pickup_and_disputes_inspection(client, parties):
    bag, _, order = make_order(client, parties)
    pickup = arrive(client, parties, bag, order, kg=40)
    assert "등록 무게와" in pickup["weight_warning"]
    assert "60" in pickup["weight_warning"] and "%" in pickup["weight_warning"]
    recorded = detail(client, parties, order)
    assert "등록 무게와" in json.dumps(recorded["history"], ensure_ascii=False)
    result = inspect(client, parties, bag, order, kg=40)
    assert result["status"] == "disputed"
    assert "무게 차이" in result["dispute_reason"]
    assert "60" in result["dispute_reason"] and "%" in result["dispute_reason"]
    assert detail(client, parties, order)["status"] == "disputed"


def test_cancel_refunds_all_and_reopens_listing(client, parties):
    _, listing, order = make_order(client, parties)
    result = request(client, "POST", f"/orders/{order['id']}/cancel", parties["recycler"], {})
    assert result["status"] == "cancelled"
    money(result, detail(client, parties, order), refund_krw=order["held_krw"])
    assert request(client, "GET", f"/listings/{listing['id']}", parties["factory"])["status"] == "posted"
    request(client, "POST", f"/orders/{order['id']}/cancel", parties["recycler"], {}, 409)
    replacement = request(client, "POST", "/orders", parties["recycler"], {
        "listing_id": listing["id"], "freight_cap_krw": CAP,
    }, 201)
    assert replacement["held_krw"] == order["held_krw"]


@pytest.mark.parametrize("actor", ["hauler", "recycler", "operator"])
def test_release_clears_assignment_and_restores_call_without_changing_hold(client, parties, actor):
    _, _, order = make_order(client, parties)
    accept(client, parties, order)
    result = request(client, "POST", f"/orders/{order['id']}/release", parties[actor], {})
    assert result["status"] == "payment_held"
    current = detail(client, parties, order)
    assert current["hauler_id"] is None
    assert current["freight_krw"] is None
    assert current["held_krw"] == order["held_krw"]
    assert current["goods_krw"] == order["goods_krw"]
    assert current["freight_cap_krw"] == CAP
    assert any(row["order_id"] == order["id"] for row in request(client, "GET", "/calls", parties["hauler"]))
    accept(client, parties, order)


@pytest.mark.parametrize("mode", ["now", "bundle"])
def test_withdraw_releases_bags_for_resale(client, parties, mode):
    bag, listing = make_listing(client, parties, mode=mode)
    result = request(client, "POST", f"/listings/{listing['id']}/withdraw", parties["factory"], {})
    assert result["status"] == "withdrawn"
    assert request(client, "GET", f"/bags/{bag['id']}", parties["factory"])["listing_id"] is None
    request(client, "POST", "/listings", parties["factory"], {
        "bag_ids": [bag["id"]], "mode": "now", "price_krw_per_kg": 100,
    }, 201)


@pytest.mark.parametrize("resolution", ["regrade", "treat", "return"])
def test_operator_resolves_dispute_with_explicit_amounts(client, parties, resolution):
    bag, _, order = make_order(client, parties)
    arrive(client, parties, bag, order)
    assert inspect(client, parties, bag, order, kg=40, passed=False)["status"] == "disputed"
    body = {"resolution": resolution, "note": "가상 QA 운영자 허가 확인 및 중재"}
    if resolution == "regrade":
        body["new_price_krw_per_kg"] = 50.51  # v0.3: 단가 소수 2자리, 40 × 50.51 = 2020.4 → 2020원
    elif resolution == "treat":
        body["treatment_fee_krw"] = 700
    path = f"/admin/orders/{order['id']}/resolve"
    request(client, "POST", path, parties["recycler"], body, 403)
    result = request(client, "POST", path, parties["operator"], body)
    current = detail(client, parties, order)
    assert result["status"] == ("returned" if resolution == "return" else "settled")
    assert current["status"] == result["status"]
    expected_factory = {"regrade": 2020, "treat": 0, "return": 0}[resolution]  # v0.3 9.1: treat 처리비는 별도 칸
    expected_refund = order["held_krw"] - FREIGHT - (2020 if resolution == "regrade" else 0)
    money(result, current, factory_krw=expected_factory, hauler_krw=FREIGHT, platform_krw=0, refund_krw=expected_refund)
    if resolution == "treat":
        settlement = result.get("settlement", result)
        assert settlement["factory_charge_krw"] == 700 and settlement["recycler_fee_krw"] == 700
    if resolution in {"treat", "return"}:
        assert "법률 자문 확인 필요" in result["legal_note"]
    request(client, "POST", path, parties["operator"], body, 409)


def test_handover_number_locks_all_three_slots_and_sold_bag_regrade(client, parties):
    bag, _, order = make_order(client, parties)
    request(client, "POST", f"/bags/{bag['id']}/grade", parties["factory"], {}, 409)
    arrive(client, parties, bag, order)
    assert inspect(client, parties, bag, order)["status"] == "settled"
    base = f"/orders/{order['id']}/handover"
    request(client, "POST", base + "/number", parties["factory"], {"allbaro_no": "QA-미완성"}, 409)
    slots = [("emitter", "factory", {}), ("carrier", "hauler", {"vehicle_no": "가상12가3456"}),
             ("processor", "recycler", {"method": "가상 재활용"})]
    for slot, actor, body in slots:
        assert_utc_dates(request(client, "POST", base + "/" + slot, parties[actor], body))
    number = "QA-" + uuid4().hex
    request(client, "POST", base + "/number", parties["factory"], {"allbaro_no": number})
    before = request(client, "GET", base, parties["factory"])
    assert before["allbaro_no"] == number
    for slot, actor, body in slots:
        request(client, "POST", base + "/" + slot, parties[actor], body, 409)
    assert request(client, "GET", base, parties["factory"]) == before
    assert_utc_dates(before)


@pytest.mark.parametrize("hazard", ["기름", "그리스", "grease", "solvent", "용제", "페인트", "paint"])
def test_note_hazard_holds_pass_until_factory_confirmation(client, parties, hazard):
    bag = make_bag(client, parties, note=f"{hazard} 언급: 실제 혼입 여부 확인 필요")
    blocked = grade(client, parties, bag)
    assert blocked["grade"]["grade"] is None
    assert not blocked.get("pass_id") and not blocked.get("qr")
    assert "메모에 위험 재질 언급" in " ".join(blocked["grade"]["reasons"])
    cleared = grade(client, parties, bag, confirm_no_hazard=True)
    assert cleared["grade"]["grade"] == "A"
    assert cleared["grade"]["purity"] == pytest.approx(1)
    assert cleared["qr"] == f"MDP-{cleared['pass_id']}-{bag['id']}"


@pytest.mark.parametrize("hazard", ["기름", "그리스", "grease", "solvent", "용제", "페인트", "paint"])
def test_item_hazard_cannot_be_overridden_by_confirmation(client, parties, hazard):
    bag = make_bag(client, parties, items=[{"material": "pp", "kg": 99}, {"material": hazard, "kg": 1}])
    result = grade(client, parties, bag, confirm_no_hazard=True)
    assert result["grade"]["grade"] is None
    assert result["grade"]["hazard"] is True
    assert not result.get("pass_id") and not result.get("qr")


@pytest.mark.parametrize("alias", ["피피", "폴리프로필렌"])
def test_material_aliases_preserve_purity(client, parties, alias):
    bag = make_bag(client, parties, items=[{"material": alias, "kg": 97}, {"material": "pe", "kg": 3}])
    result = grade(client, parties, bag)
    assert result["grade"]["purity"] == pytest.approx(0.97)
    assert result["grade"]["grade"] == "A"
    assert result["pass_id"]


def test_unknown_material_is_reported_in_reasons(client, parties):
    unknown = "가상미등록재질"
    bag = make_bag(client, parties, items=[{"material": "pp", "kg": 97}, {"material": unknown, "kg": 3}])
    result = grade(client, parties, bag)
    assert "인식 못 한 재질: [입력값](확인 필요)" in result["grade"]["reasons"]  # v0.3 9.3: 원문 대신 [입력값]
    assert unknown not in " ".join(result["grade"]["reasons"])


def test_screen_queries_fields_ownership_and_utc_dates(client, parties):
    bag, listing, order = make_order(client, parties)
    accept(client, parties, order)
    stranger = join(client, "factory")
    for actor in parties.values():
        me = request(client, "GET", "/me", actor)
        fields(me, "id name role verified permit_codes lat lon")
        assert me["id"] == actor["id"]
    bag_fields = "id waste_code waste_name target_material total_kg status grade purity pass_id qr listing_id created_at"
    bags = request(client, "GET", "/me/bags", parties["factory"])
    own_bag = next(row for row in bags if row["id"] == bag["id"])
    fields(own_bag, bag_fields)
    assert own_bag["waste_name"] == WASTE_NAME
    assert own_bag["listing_id"] == listing["id"]
    bag_detail = request(client, "GET", f"/bags/{bag['id']}", parties["factory"])
    fields(bag_detail, bag_fields + " items reasons")
    request(client, "GET", f"/bags/{bag['id']}", stranger, status=403)
    assert not any(row["id"] == bag["id"] for row in request(client, "GET", "/me/bags", stranger))
    listings = request(client, "GET", "/me/listings", parties["factory"])
    own_listing = next(row for row in listings if row["id"] == listing["id"])
    fields(own_listing, "id status waste_code grade total_kg price_krw_per_kg bag_ids order_id")
    assert own_listing["status"] == "sold"
    assert own_listing["bag_ids"] == [bag["id"]]
    assert own_listing["order_id"] == order["id"]
    assert not any(row["id"] == listing["id"] for row in request(client, "GET", "/me/listings", stranger))
    request(client, "GET", f"/listings/{listing['id']}", stranger, status=404)  # v0.3 9.4: 팔린 판매는 제3자 404
    listing_detail = request(client, "GET", f"/listings/{listing['id']}", parties["recycler"])
    fields(listing_detail, "id status waste_code waste_name grade target_material purity_avg composition total_kg bag_count price_krw_per_kg factory_name area")
    assert listing_detail["area"] == {"lat": 36.12, "lon": 128.46}
    assert listing_detail["purity_avg"] == pytest.approx(1)
    assert listing_detail["composition"]["pp"] == pytest.approx(1)
    for role in ("factory", "recycler", "hauler"):
        orders = request(client, "GET", "/me/orders", parties[role])
        own_order = next(row for row in orders if row["id"] == order["id"])
        fields(own_order, "id status role_in_order waste_name total_kg goods_krw freight_cap_krw freight_krw counterparty_names updated_at")
        assert own_order["role_in_order"] == role
        assert own_order["waste_name"] == WASTE_NAME
        assert own_order["freight_krw"] == FREIGHT
        assert_utc_dates(orders)
        dates = [datetime.fromisoformat(row["updated_at"]) for row in orders]
        assert dates == sorted(dates, reverse=True)
    request(client, "GET", f"/orders/{order['id']}", stranger, status=403)
    assert not any(row["id"] == order["id"] for row in request(client, "GET", "/me/orders", stranger))
    current = detail(client, parties, order)
    assert current["history"]
    for entry in current["history"]:
        fields(entry, "from to by at")
    for value in (bags, bag_detail, listings, listing_detail, current):
        assert_utc_dates(value)
    _, posted = make_listing(client, parties)
    public = next(row for row in request(client, "GET", "/listings", stranger) if row["id"] == posted["id"])
    fields(public, "id status waste_code waste_name grade total_kg bag_count price_krw_per_kg factory_id factory_name")
    for path in ("/me", "/me/bags", f"/bags/{bag['id']}", "/me/listings", f"/listings/{listing['id']}", "/me/orders"):
        request(client, "GET", path, status=401)


def test_harness_redacts_configuration_and_agent_run_requires_company(client, parties):
    harness = request(client, "GET", "/harness")
    fields(harness, "teams agents flows")
    assert "llm" not in harness  # 에이전트 카드의 llm: bool 메타데이터는 허용
    def inspect_keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                assert key.lower() not in {"assumptions", "ollama", "claude", "url", "model"}, key
                inspect_keys(child)
        elif isinstance(value, list):
            for child in value:
                inspect_keys(child)
    inspect_keys(harness)
    serialized = json.dumps(harness, ensure_ascii=False)
    assert "172.20.32.1" not in serialized
    assert "11434" not in serialized
    bag = make_bag(client, parties)
    run_id = grade(client, parties, bag)["run_id"]
    request(client, "GET", f"/agent-runs/{run_id}", status=401)
    run = request(client, "GET", f"/agent-runs/{run_id}", parties["factory"])
    assert run["run_id"] == run_id


def simultaneous_posts(client, path, actor, body, count=4):
    # SQLite(특히 sqlite://의 단일 연결)는 실제 병렬 트랜잭션 재현이 약할 수 있다.
    # PostgreSQL에서도 같은 테스트를 실행해야 DB 수준의 선점 보장을 검증할 수 있다.
    barrier = Barrier(count)
    def post(_):
        barrier.wait(timeout=10)
        return client.post("/v1" + path, headers=headers(actor), json=body)
    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(post, range(count)))


def test_concurrent_sale_of_same_bag_has_exactly_one_winner(client, parties):
    from app.db.session import engine as _engine
    if _engine.dialect.name == "sqlite":
        pytest.skip("메모리 SQLite는 연결 하나를 같이 써서 진짜 동시 요청 불가. PostgreSQL에서 확인")
    bag = make_bag(client, parties)
    grade(client, parties, bag)
    responses = simultaneous_posts(client, "/listings", parties["factory"], {
        "bag_ids": [bag["id"]], "mode": "now", "price_krw_per_kg": 100,
    })
    codes = [response.status_code for response in responses]
    assert sorted(codes) == [201, 409, 409, 409], [(r.status_code, r.text) for r in responses]
    listings = request(client, "GET", "/me/listings", parties["factory"])
    assert sum(bag["id"] in row["bag_ids"] for row in listings) == 1
    winner = next(response.json() for response in responses if response.status_code == 201)
    assert request(client, "GET", f"/bags/{bag['id']}", parties["factory"])["listing_id"] == winner["id"]


def test_concurrent_pickup_has_exactly_one_winner_and_history_entry(client, parties):
    from app.db.session import engine as _engine
    if _engine.dialect.name == "sqlite":
        pytest.skip("메모리 SQLite는 연결 하나를 같이 써서 진짜 동시 요청 불가. PostgreSQL에서 확인")
    bag, _, order = make_order(client, parties)
    accept(client, parties, order)
    responses = simultaneous_posts(client, f"/orders/{order['id']}/pickup", parties["hauler"], weights(bag, 100))
    codes = [response.status_code for response in responses]
    assert sorted(codes) == [200, 409, 409, 409], [(r.status_code, r.text) for r in responses]
    current = detail(client, parties, order)
    assert current["status"] == "picked_up"
    assert sum(entry["to"] == "picked_up" for entry in current["history"]) == 1
