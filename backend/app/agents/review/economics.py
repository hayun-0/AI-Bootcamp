"""⑥ economics: 아낄 수 있는 소각 비용 범위와 판매 참고액 범위(⑤ 값 그대로)를 따로 표시. 모두 추정. LLM은 설명만."""
from __future__ import annotations

from app.agents._common import claim, ev, listing_basics, llm_note
from app.contracts import AgentResult
from app.tools.calc import fmt, incineration_cost

ID = "economics"


def run(ctx: dict, llm=None) -> AgentResult:
    b = listing_basics(ctx)
    claims, data = [], {}
    if b["total_kg"] is None:
        claims.append(claim(ID, "총 무게를 몰라 경제성을 계산하지 못함", "question", ev("input", "listing.total_kg")))
        return AgentResult(agent_id=ID, claims=claims, data=data)
    inc = incineration_cost(b["total_kg"])
    data["incineration"] = inc
    claims.append(claim(ID, f"소각 위탁 대신 판매하면 아낄 수 있는 비용: {fmt(inc['tons'])}톤 × 톤당 {fmt(inc['per_ton_low'])}~{fmt(inc['per_ton_high'])}원 = {fmt(inc['low'])}~{fmt(inc['high'])}원 "
                            f"(지자체 계약 전국평균, 소각재 처리 제외~포함)", "estimate",
                        ev("dataset", inc["source"]), ev("calc", "톤 × 톤당 소각비 범위"), ev("input", "listing.total_kg"),
                        ev("assumption", "소각비는 지자체 계약 전국평균 가정")))
    price = ((ctx.get("results") or {}).get("pricing") or {}).get("data", {}).get("price")
    if price:
        lo, hi = round(b["total_kg"] * price["low"]), round(b["total_kg"] * price["high"])
        data["sale"] = {"low": lo, "high": hi}
        claims.append(claim(ID, f"판매 참고액: {fmt(round(b['total_kg'], 3))} kg × {fmt(price['low'])}~{fmt(price['high'])}원/kg = {fmt(lo)}~{fmt(hi)}원 (잡색 압축품 매입가 기준, VAT 포함·물류비 제외, 자투리 실제 매입가는 견적 확인 필요)",
                            "estimate", ev("dataset", price["source"]), ev("calc", "kg × 지역별 시세 최저~최고"), ev("input", "listing.total_kg"),
                            ev("assumption", "압축품 시세를 이 마대에 적용한 참고치")))
    else:
        claims.append(claim(ID, "시세 값을 얻지 못해 판매 수입은 계산하지 못함", "question", ev("input", "results.pricing")))
    note = llm_note(ID, llm, claims, "아낄 수 있는 비용과 판매 참고액을 따로 설명하고, 둘의 크기를 서로 비교하지 마라.", ctx)
    if note:
        claims.append(note)
    return AgentResult(agent_id=ID, claims=claims, data=data, used_llm=bool(note))
