"""P0 한 바퀴 시나리오 + 규칙 테스트."""
import importlib.util

import pytest

from tests.conftest import CODE, H, OP_TOKEN, mk_company


def setup_world(client):
    w = {}
    w["op"] = mk_company(client, "가상운영", "operator")
    w["f"] = mk_company(client, "가상사출A", "factory")
    w["f2"] = mk_company(client, "가상사출B", "factory")
    for key, name, role in (("r", "가상리사이클", "recycler"), ("h1", "가상운반1", "hauler"), ("h2", "가상운반2", "hauler")):
        w[key] = mk_company(client, name, role, permit_no="가상-허가", permit_codes=[CODE])
    return w


def make_bag(client, fid, pp_kg, other_kg, other="pe"):
    r = client.post("/v1/bags", headers=H(fid), json={
        "waste_code": CODE, "target_material": "pp", "items": [{"material": "PP", "kg": pp_kg}, {"material": other, "kg": other_kg}]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def run_scenario(client):
    w = setup_world(client)
    f, r, h1, h2, op = w["f"], w["r"], w["h1"], w["h2"], w["op"]
    # 허가 확인 전: recycler/hauler는 미확인
    assert client.post("/v1/companies", json={"name": "x", "role": "hauler", "biz_no": "1", "lat": 1, "lon": 1}).json()["verified"] is False
    for cid in (r, h1, h2):
        assert client.post(f"/v1/admin/companies/{cid}/verify", headers=H(op), json={}).json() == {"id": cid, "verified": True}

    # 마대 4개: A·B·C + 기름(통과증 없음)
    bags = [make_bag(client, f, 97, 3), make_bag(client, f, 92, 8), make_bag(client, f, 85, 15)]
    grades = [client.post(f"/v1/bags/{b}/grade", headers=H(f), json={}).json() for b in bags]
    assert [g["grade"]["grade"] for g in grades] == ["A", "B", "C"]
    assert grades[0]["qr"] == f"MDP-{grades[0]['pass_id']}-{bags[0]}" and grades[0]["run_id"]
    oily = make_bag(client, f, 80, 20, other="oil")
    g = client.post(f"/v1/bags/{oily}/grade", headers=H(f), json={}).json()
    assert g["grade"]["grade"] is None and "pass_id" not in g

    # 판매: 통과증 없는 마대는 400, A 마대로 판매
    assert client.post("/v1/listings", headers=H(f), json={"bag_ids": [oily], "mode": "now", "price_krw_per_kg": 500}).status_code == 409
    lst = client.post("/v1/listings", headers=H(f), json={"bag_ids": [bags[0]], "mode": "now", "price_krw_per_kg": 500})
    assert lst.status_code == 201 and lst.json()["status"] == "posted" and lst.json()["advice"]["flow"] == "listing_advice"
    lid = lst.json()["id"]
    assert [x["id"] for x in client.get("/v1/listings", params={"waste_code": CODE}).json()] == [lid]
    # 같은 마대를 또 묶으면 409
    assert client.post("/v1/listings", headers=H(f), json={"bag_ids": [bags[0]], "mode": "now", "price_krw_per_kg": 1}).status_code == 409

    # 주문
    o = client.post("/v1/orders", headers=H(r), json={"listing_id": lid, "freight_cap_krw": 50000})
    assert o.status_code == 201, o.text
    oid = o.json()["id"]
    assert o.json()["status"] == "payment_held" and o.json()["goods_krw"] == 50000 and o.json()["held_krw"] == 102500 and o.json()["freight_cap_krw"] == 50000 and o.json()["checklist"]["flow"] == "deal_check"
    assert client.get("/v1/listings").json() == []  # sold

    # 콜: 먼저 수락한 1곳만
    assert [c["order_id"] for c in client.get("/v1/calls", headers=H(h1)).json()] == [oid]
    ok = client.post(f"/v1/calls/{oid}/accept", headers=H(h1), json={"freight_krw": 30000})
    assert ok.json() == {"order_id": oid, "status": "dispatched", "hauler_id": h1}
    assert client.post(f"/v1/calls/{oid}/accept", headers=H(h2), json={"freight_krw": 20000}).status_code == 409
    assert client.get("/v1/calls", headers=H(h2)).json() == []

    # 수거(남의 hauler는 403, 무게 누락은 400)
    assert client.post(f"/v1/orders/{oid}/pickup", headers=H(h2), json={"bag_weights": [{"bag_id": bags[0], "kg": 100}]}).status_code == 403
    assert client.post(f"/v1/orders/{oid}/pickup", headers=H(h1), json={"bag_weights": []}).status_code == 400
    assert client.post(f"/v1/orders/{oid}/pickup", headers=H(h1), json={"bag_weights": [{"bag_id": bags[0], "kg": 100}]}).json() == {"status": "picked_up"}
    assert client.post(f"/v1/orders/{oid}/arrive", headers=H(h1), json={}).json() == {"status": "arrived"}

    # 검사 합격 → 정산
    ins = client.post(f"/v1/orders/{oid}/inspect", headers=H(r), json={"bag_weights": [{"bag_id": bags[0], "kg": 99}], "passed": True})
    assert ins.json() == {"status": "settled", "settlement": {"factory_krw": 49500, "hauler_krw": 30000, "platform_krw": 0, "refund_krw": 23000}}

    # 인계서: 남의 칸 403
    assert client.post(f"/v1/orders/{oid}/handover/processor", headers=H(f), json={"method": "x"}).status_code == 403
    assert client.post(f"/v1/orders/{oid}/handover/emitter", headers=H(h1), json={}).status_code == 403
    assert client.post(f"/v1/orders/{oid}/handover/number", headers=H(f), json={"allbaro_no": "A-1"}).status_code == 409  # 3칸 전
    e = client.post(f"/v1/orders/{oid}/handover/emitter", headers=H(f), json={}).json()
    assert e["waste_name"] and e["bags"] == [{"bag_id": bags[0], "kg": 100}] and e["carrier_name"] == "가상운반1"
    c = client.post(f"/v1/orders/{oid}/handover/carrier", headers=H(h1), json={"vehicle_no": "12가3456"}).json()
    assert c["total_kg"] == 100
    p = client.post(f"/v1/orders/{oid}/handover/processor", headers=H(r), json={"method": "R-1"}).json()
    assert p["received_kg"] == 99
    assert client.post(f"/v1/orders/{oid}/handover/number", headers=H(f), json={"allbaro_no": "AB-2026-1"}).json() == {"allbaro_no": "AB-2026-1"}
    ho = client.get(f"/v1/orders/{oid}/handover", headers=H(r)).json()
    assert ho["allbaro_no"] == "AB-2026-1" and ho["emitter"] and ho["carrier"] and ho["processor"]

    # 별점
    assert client.post("/v1/ratings", headers=H(f), json={"order_id": oid, "target": "factory", "score": 5}).status_code == 403  # 자기 자신
    assert client.post("/v1/ratings", headers=H(f), json={"order_id": oid, "target": "recycler", "score": 6}).status_code == 400
    assert client.post("/v1/ratings", headers=H(f), json={"order_id": oid, "target": "recycler", "score": 5}).status_code == 201
    assert client.post("/v1/ratings", headers=H(f), json={"order_id": oid, "target": "recycler", "score": 4}).status_code == 409  # 중복
    assert client.get(f"/v1/orders/{oid}", headers=H(f)).json()["status"] == "settled"
    assert client.post("/v1/ratings", headers=H(r), json={"order_id": oid, "target": "factory", "score": 4, "comment": "좋음"}).status_code == 201
    final = client.get(f"/v1/orders/{oid}", headers=H(h1)).json()
    assert final["status"] == "rated"
    assert [(x["from"], x["to"]) for x in final["history"]] == [
        ("ordered", "payment_held"), ("payment_held", "dispatched"), ("dispatched", "picked_up"),
        ("picked_up", "arrived"), ("arrived", "confirmed"), ("confirmed", "settled"), ("settled", "rated")]
    return w, oid


def test_full_scenario(client):
    run_scenario(client)


def test_auth_and_roles(client):
    w = setup_world(client)
    assert client.get("/v1/calls").status_code == 401
    assert client.get("/v1/calls", headers=H(999)).status_code == 401
    bag_body = {"waste_code": CODE, "target_material": "pp", "items": [{"material": "pp", "kg": 1}]}
    assert client.post("/v1/bags", headers=H(w["r"]), json=bag_body).status_code == 403
    assert client.post("/v1/bags", headers=H(w["f"]), json={"waste_code": CODE}).status_code == 400
    assert client.post("/v1/admin/companies/1/verify", headers=H(w["f"]), json={}).status_code == 403
    # 미확인 recycler는 주문 불가
    bag = client.post("/v1/bags", headers=H(w["f"]), json=bag_body).json()["id"]
    client.post(f"/v1/bags/{bag}/grade", headers=H(w["f"]), json={})
    lid = client.post("/v1/listings", headers=H(w["f"]), json={"bag_ids": [bag], "mode": "bundle", "price_krw_per_kg": 10}).json()
    assert lid["status"] == "bundle_wait"
    assert client.post("/v1/orders", headers=H(w["r"]), json={"listing_id": lid["id"], "freight_cap_krw": 50000}).status_code == 403
    # 남의 마대 등급 403
    assert client.post(f"/v1/bags/{bag}/grade", headers=H(w["f2"]), json={}).status_code == 403
    # 주문 당사자가 아니면 조회 403
    client.post(f"/v1/admin/companies/{w['r']}/verify", headers=H(w["op"]), json={})
    assert client.post("/v1/orders", headers=H(w["r"]), json={"listing_id": lid["id"], "freight_cap_krw": 50000}).status_code == 409  # bundle_wait


def test_inspect_fail_goes_disputed_and_bad_transition(client):
    w = setup_world(client)
    for k in ("r", "h1"):
        client.post(f"/v1/admin/companies/{w[k]}/verify", headers=H(w["op"]), json={})
    b = make_bag(client, w["f"], 97, 3)
    client.post(f"/v1/bags/{b}/grade", headers=H(w["f"]), json={})
    lid = client.post("/v1/listings", headers=H(w["f"]), json={"bag_ids": [b], "mode": "now", "price_krw_per_kg": 10}).json()["id"]
    oid = client.post("/v1/orders", headers=H(w["r"]), json={"listing_id": lid, "freight_cap_krw": 50000}).json()["id"]
    assert client.post(f"/v1/orders/{oid}/arrive", headers=H(w["h1"]), json={}).status_code == 403  # 아직 배정 전
    client.post(f"/v1/calls/{oid}/accept", headers=H(w["h1"]), json={"freight_krw": 1})
    assert client.post(f"/v1/orders/{oid}/arrive", headers=H(w["h1"]), json={}).status_code == 409  # 수거 전 도착
    client.post(f"/v1/orders/{oid}/pickup", headers=H(w["h1"]), json={"bag_weights": [{"bag_id": b, "kg": 100}]})
    client.post(f"/v1/orders/{oid}/arrive", headers=H(w["h1"]), json={})
    r = client.post(f"/v1/orders/{oid}/inspect", headers=H(w["r"]), json={"bag_weights": [{"bag_id": b, "kg": 90}], "passed": False})
    assert r.json() == {"status": "disputed", "dispute_reason": "검사 불합격"}
    assert client.get(f"/v1/orders/{oid}", headers=H(w["f2"])).status_code == 403


def test_rating_requires_allbaro_no(client):
    w = setup_world(client)
    for k in ("r", "h1"):
        client.post(f"/v1/admin/companies/{w[k]}/verify", headers=H(w["op"]), json={})
    b = make_bag(client, w["f"], 97, 3)
    client.post(f"/v1/bags/{b}/grade", headers=H(w["f"]), json={})
    lid = client.post("/v1/listings", headers=H(w["f"]), json={"bag_ids": [b], "mode": "now", "price_krw_per_kg": 10}).json()["id"]
    oid = client.post("/v1/orders", headers=H(w["r"]), json={"listing_id": lid, "freight_cap_krw": 50000}).json()["id"]
    assert client.post("/v1/ratings", headers=H(w["r"]), json={"order_id": oid, "target": "factory", "score": 5}).status_code == 409


def test_health(client):
    assert client.get("/v1/health").json()["ok"] is True


@pytest.mark.skipif(importlib.util.find_spec("app.harness.runner") is None, reason="B의 runner 없음")
def test_scenario_with_real_runner_llm_off(client, monkeypatch):
    from app.services import flows
    monkeypatch.undo()  # client 픽스처의 fake run_flow를 되돌려 진짜 runner 사용
    monkeypatch.setenv("LLM_PROVIDER", "off")
    monkeypatch.setenv("OPERATOR_BOOTSTRAP_TOKEN", OP_TOKEN)  # undo()가 지웠으므로 다시
    assert flows.load_run_flow() is not None
    run_scenario(client)
