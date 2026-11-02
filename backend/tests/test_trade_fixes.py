"""분석팀 수정 라운드 회귀 테스트(거래/API)."""
from tests.conftest import CODE, H, mk_company
from tests.test_trade_scenario import make_bag, setup_world


def settled_order(client):
    w = setup_world(client)
    for k in ("r", "h1"):
        client.post(f"/v1/admin/companies/{w[k]}/verify", headers=H(w["op"]), json={})
    b = make_bag(client, w["f"], 97, 3)
    client.post(f"/v1/bags/{b}/grade", headers=H(w["f"]), json={})
    lid = client.post("/v1/listings", headers=H(w["f"]), json={"bag_ids": [b], "mode": "now", "price_krw_per_kg": 10}).json()["id"]
    oid = client.post("/v1/orders", headers=H(w["r"]), json={"listing_id": lid, "freight_cap_krw": 50000}).json()["id"]
    client.post(f"/v1/calls/{oid}/accept", headers=H(w["h1"]), json={"freight_krw": 1000})
    client.post(f"/v1/orders/{oid}/pickup", headers=H(w["h1"]), json={"bag_weights": [{"bag_id": b, "kg": 100}]})
    client.post(f"/v1/orders/{oid}/arrive", headers=H(w["h1"]), json={})
    client.post(f"/v1/orders/{oid}/inspect", headers=H(w["r"]), json={"bag_weights": [{"bag_id": b, "kg": 99}], "passed": True})
    client.post(f"/v1/orders/{oid}/handover/emitter", headers=H(w["f"]), json={})
    client.post(f"/v1/orders/{oid}/handover/carrier", headers=H(w["h1"]), json={"vehicle_no": "12가3456"})
    client.post(f"/v1/orders/{oid}/handover/processor", headers=H(w["r"]), json={"method": "R-1"})
    client.post(f"/v1/orders/{oid}/handover/number", headers=H(w["f"]), json={"allbaro_no": "AB-1"})
    return w, oid


def rate(client, who, oid, target):
    r = client.post("/v1/ratings", headers=H(who), json={"order_id": oid, "target": target, "score": 4})
    assert r.status_code == 201, r.text


def status(client, w, oid):
    return client.get(f"/v1/orders/{oid}", headers=H(w["f"])).json()["status"]


def test_rated_needs_factory_and_recycler_as_raters(client):
    w, oid = settled_order(client)
    rate(client, w["h1"], oid, "factory")
    rate(client, w["h1"], oid, "recycler")          # 타깃은 공장·재활용업체지만 평가자는 운반업체뿐
    assert status(client, w, oid) == "settled"
    rate(client, w["f"], oid, "hauler")
    assert status(client, w, oid) == "settled"      # 재활용업체가 아직 안 씀
    rate(client, w["r"], oid, "hauler")
    assert status(client, w, oid) == "rated"


def test_listing_advice_sees_nearby_factory_listings(client, monkeypatch):
    from app.harness.runner import run_flow
    from app.services import flows
    monkeypatch.setattr(flows, "load_run_flow", lambda: lambda f, c: run_flow(f, c, llm=None))
    f1 = mk_company(client, "가상A", "factory", lat=36.1, lon=128.4)
    f2 = mk_company(client, "가상B", "factory", lat=36.1, lon=128.401)
    ids = []
    for f in (f1, f2):
        b = make_bag(client, f, 97, 3)
        client.post(f"/v1/bags/{b}/grade", headers=H(f), json={})
        ids.append(client.post("/v1/listings", headers=H(f), json={"bag_ids": [b], "mode": "bundle", "price_krw_per_kg": 10}))
    advice = ids[1].json()["advice"]
    bundling = next(r for r in advice["results"] if r["agent_id"] == "bundling")["data"]
    assert len(bundling["matches"]) > 0 and bundling["unknown_position"] == 0
    assert bundling["bundle_kg"] == 200


def test_grade_role_check_before_404(client):
    w = setup_world(client)
    client.post(f"/v1/admin/companies/{w['h1']}/verify", headers=H(w["op"]), json={})
    assert client.post("/v1/bags/9999/grade", headers=H(w["h1"]), json={}).status_code == 403
    assert client.post("/v1/bags/9999/grade", headers=H(w["f"]), json={}).status_code == 404


def test_infinity_inputs_rejected_and_nothing_committed(client):
    w = setup_world(client)
    f = w["f"]
    b = make_bag(client, f, 97, 3)
    client.post(f"/v1/bags/{b}/grade", headers=H(f), json={})
    r = client.post("/v1/listings", headers={**H(f), "Content-Type": "application/json"},
                    content='{"bag_ids": [%d], "mode": "now", "price_krw_per_kg": Infinity}' % b)
    assert r.status_code == 400
    assert client.get("/v1/listings").status_code == 200 and client.get("/v1/listings").json() == []
    r = client.post("/v1/bags", headers={**H(f), "Content-Type": "application/json"},
                    content='{"waste_code": "%s", "target_material": "pp", "items": [{"material": "pp", "kg": NaN}]}' % CODE)
    assert r.status_code == 400
    r = client.post("/v1/orders/1/pickup", headers={**H(w["h1"]), "Content-Type": "application/json"},
                    content='{"bag_weights": [{"bag_id": 1, "kg": Infinity}]}')
    assert r.status_code == 400
