"""⑦ regulation: 주문 때 법 체크리스트(허가·운반·인계서). 법 근거 id 필수. LLM은 조문 요약 문장만."""
from __future__ import annotations

from app.agents._common import claim, ev, llm_note
from app.contracts import AgentResult

ID = "regulation"
L25 = ev("law", "wma-25", "폐기물처리업 허가")
L18_1 = ev("law", "wma-18-1", "사업장폐기물 위탁 의무")
L18_3 = ev("law", "wma-18-3", "전자인계서")


def run(ctx: dict, llm=None) -> AgentResult:
    listing = ctx.get("listing") or {}
    recycler = ctx.get("recycler") or {}
    code = listing.get("waste_code") or (ctx.get("order") or {}).get("waste_code")
    codes = recycler.get("permit_codes")
    checklist = []
    if codes is None or code is None:
        c1 = claim(ID, "재활용업체의 허가 코드 정보가 없어 폐기물 코드와 맞는지 확인 필요 (법 제25조 허가, 법 제18조 제1항 위탁)", "question",
                   L25, L18_1, ev("input", "recycler.permit_codes"))
    elif code in codes:
        c1 = claim(ID, f"재활용업체 허가 코드에 {code}가 들어 있음. 법 제25조(처리업 허가)와 법 제18조 제1항(허가업자 위탁)에 따라 허가증 원본은 따로 확인 필요",
                   "fact", L25, L18_1, ev("input", "recycler.permit_codes, listing.waste_code"))
    else:
        c1 = claim(ID, f"재활용업체 허가 코드 목록에 {code}가 들어 있지 않음. 법 제25조(처리업 허가)와 법 제18조 제1항(허가업자 위탁) 기준으로 확인 필요",
                   "fact", L25, L18_1, ev("input", "recycler.permit_codes, listing.waste_code"))
    claims = [
        c1,
        claim(ID, "운반업체는 수락 단계에서 수집·운반업 허가(법 제25조)를 확인해야 함", "fact", L25),
        claim(ID, "인계서는 배출자·운반자·처리자가 각자 자기 칸을 전자인계서에 입력해야 함 (법 제18조 제3항). 앱은 올바로에 붙여넣을 값만 정리하고 제출하지 않음",
              "fact", L18_3),
    ]
    checklist = [{"item": "recycler_permit", "ok": (code in codes) if codes is not None and code else None},
                 {"item": "hauler_permit", "ok": None}, {"item": "handover_entry", "ok": None}]
    note = llm_note(ID, llm, claims, "법 조문을 쉬운 말로 요약하는 말투로.", ctx)
    if note:
        claims.append(note)
    return AgentResult(agent_id=ID, claims=claims, data={"checklist": checklist}, used_llm=bool(note))
