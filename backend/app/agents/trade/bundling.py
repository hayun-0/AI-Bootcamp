"""④ bundling: 반경 안 같은 waste_code·grade 대기 판매를 합쳐 최소 묶음(min_lot) 충족 여부 계산. LLM은 설명만."""
from __future__ import annotations

from app.agents._common import claim, ev, listing_basics, llm_note
from app.contracts import AgentResult
from app.tools.calc import fmt, haversine_km
from app.tools.data import assumptions

ID = "bundling"


def _pos(d: dict) -> tuple[float, float] | None:
    for src in (d, d.get("factory") or {}):
        if src.get("lat") is not None and src.get("lon") is not None:
            return float(src["lat"]), float(src["lon"])
    return None


def run(ctx: dict, llm=None) -> AgentResult:
    a = assumptions()
    radius, min_lot = a["bundle_radius_km"], a["min_lot_kg"]
    b = listing_basics(ctx)
    origin = _pos(ctx.get("factory") or {}) or _pos(ctx.get("listing") or {})
    matches, unknown_pos = [], 0
    for n in ctx.get("nearby_listings") or []:
        if n.get("waste_code") != b["waste_code"] or n.get("grade") != b["grade"]:
            continue
        pos = _pos(n)
        if origin is None or pos is None:
            unknown_pos += 1
            continue
        km = haversine_km(*origin, *pos)
        if km <= radius:
            matches.append({"id": n.get("id"), "total_kg": float(n.get("total_kg") or 0), "km": round(km, 2)})
    own = b["total_kg"] or 0.0
    others = sum(m["total_kg"] for m in matches)
    total = own + others
    data = {"matches": matches, "own_kg": own, "bundle_kg": total, "min_lot_kg": min_lot,
            "meets_min_lot": total >= min_lot, "unknown_position": unknown_pos}
    claims = [claim(ID, f"반경 {fmt(radius)} km 안 같은 폐기물 코드·등급의 대기 판매 {len(matches)}건, 합쳐 {fmt(round(total, 3))} kg (내 물량 {fmt(round(own, 3))} kg 포함). "
                        f"최소 묶음 {fmt(min_lot)} kg {'충족' if total >= min_lot else '미충족'}", "estimate",
                    ev("input", "nearby_listings"), ev("calc", "haversine 직선거리 ≤ bundle_radius_km, 같은 waste_code·grade 합계"),
                    ev("assumption", "bundle_radius_km·min_lot_kg(팀 가정)"))]
    if unknown_pos:
        claims.append(claim(ID, f"위치 정보가 없는 후보 {unknown_pos}건은 반경 계산에서 뺌. 위치 확인 필요", "question", ev("input", "nearby_listings")))
    note = llm_note(ID, llm, claims, "판매자에게 묶음 판매 가능성을 안내하는 말투로.", ctx)
    if note:
        claims.append(note)
    return AgentResult(agent_id=ID, claims=claims, data=data, used_llm=bool(note))
