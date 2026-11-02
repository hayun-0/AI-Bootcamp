"""⑤ pricing: prices.json 최근값과 비교, 최소 묶음보다 적으면 '모아서 팔기' 추천. LLM은 설명 문장만."""
from __future__ import annotations

from app.agents._common import claim, ev, listing_basics, llm_note
from app.contracts import AgentResult
from app.tools.calc import fmt, latest_price, price_item_for
from app.tools.data import assumptions

ID = "pricing"


def run(ctx: dict, llm=None) -> AgentResult:
    b = listing_basics(ctx)
    min_lot = assumptions()["min_lot_kg"]
    claims, data = [], {"price": None, "recommend_gather": None, "relation": None}

    item = price_item_for(b["target_material"] or "")
    p = latest_price(item) if item else None
    if p:
        data["price"] = p
        claims.append(claim(ID, f"{p['item']} 최근 시세({p['date']}) 전국 {fmt(p['price'])}원/kg, 지역별 {fmt(p['low'])}~{fmt(p['high'])}원/kg (잡색 압축품 매입가 기준, 부가세 포함·물류비 제외)",
                            "fact", ev("dataset", p["source"], "환경공단 재활용 시세")))
        if b["price_krw_per_kg"] is not None:
            x = float(b["price_krw_per_kg"])
            pos = "아래" if x < p["low"] else "위" if x > p["high"] else "안"
            data["price_position"] = pos
            data["relation"] = "below" if x < p["low"] else "above" if x > p["high"] else "within"
            claims.append(claim(ID, f"올리려는 단가 {fmt(x)}원/kg은 최근 지역별 시세 범위({fmt(p['low'])}~{fmt(p['high'])}원/kg)의 {pos} (잡색 압축품 매입가 기준, VAT 포함·물류비 제외, 자투리 실제 매입가는 견적 확인 필요)", "estimate",
                                ev("input", "listing.price_krw_per_kg"), ev("calc", "단가와 지역별 최저·최고 비교"), ev("dataset", p["source"]),
                                ev("assumption", "압축품 시세를 이 마대에 적용한 참고치")))
        if b["total_kg"] is not None:
            data["sale_low_krw"], data["sale_high_krw"] = round(b["total_kg"] * p["low"]), round(b["total_kg"] * p["high"])
    else:
        claims.append(claim(ID, "입력한 재질에 맞는 시세 품목을 찾지 못해 시세 비교를 못 함", "question",
                            ev("input", "target_material")))

    if b["total_kg"] is not None:
        data["recommend_gather"] = b["total_kg"] < min_lot
        if data["recommend_gather"]:
            text = f"총 {fmt(b['total_kg'])} kg는 최소 묶음 {fmt(min_lot)} kg보다 적어 모아서 팔기를 추천"
        else:
            text = f"총 {fmt(b['total_kg'])} kg는 최소 묶음 {fmt(min_lot)} kg 이상이라 바로 팔 수 있는 양"
        claims.append(claim(ID, text, "estimate", ev("input", "listing.total_kg"), ev("calc", "total_kg < min_lot_kg"),
                            ev("assumption", "min_lot_kg(팀 가정)")))
    note = llm_note(ID, llm, claims, "판매자에게 시세와 판매 시기를 안내하는 말투로.", ctx, relation=data.get("relation"))
    if note:
        claims.append(note)
    return AgentResult(agent_id=ID, claims=claims, data=data, used_llm=bool(note))
